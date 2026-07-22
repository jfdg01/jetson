#!/usr/bin/env python3
"""R-13 device half -- OWLv2 inference on the Jetson. Scoring happens off-device.

This script does NOT score anything. It runs the detector and dumps raw boxes
plus per-forward latency; `score_r13.py` on the host scores them through
`grounding/contract.py`, which is the single scoring path for every number in
the thesis. Splitting it that way keeps the detector arm from quietly acquiring
its own metric.

    ~/sam2-bench/.venv/bin/python run_r13_device.py --manifest samples.jsonl --out raw.jsonl

Three text variants per sample, one forward each, ordered most to least
charitable to the detector:

  full   the whole referring expression        ("the white vans near the intersection")
  phrase the noun phrase, adjectives kept      ("white vans")
  head   the bare head noun                    ("vans")

`phrase` is an addition to the pre-registration, which named only `full` and
`head`. A bare head noun throws away the appearance words OWLv2 is actually
built to score, so a detector that failed on `head` alone could be dismissed as
strawmanned. `phrase` is what a real decomposed system would extract, and it
costs one extra forward pass per sample.

The oracle is computed off-device from the top-k boxes of every arm -- it needs
the GT, so it is a selection rule, not a system, and it never runs here.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import torch
from PIL import Image
from transformers import Owlv2ForObjectDetection, Owlv2Processor

MODEL_ID = "google/owlv2-base-patch16-ensemble"
TOPK = 10

# Cut the expression at the first relational/spatial marker. Deliberately dumb and
# deterministic -- no LLM, which would smuggle the expensive model into the cheap arm.
_PREPS = (" next to ", " near ", " beside ", " behind ", " in front of ", " on the ",
          " on ", " in ", " at ", " under ", " above ", " over ", " across ", " along ",
          " with ", " that ", " which ", " who ", " is ", " are ", " was ", " were ",
          " to the ", " by the ", " from ", " between ", " among ", " beneath ", " and ")
# Verb stems, matched with a LEADING space and no trailing one, so they also fire at
# end-of-string ("the black cars park"). Without these the head noun comes back as a
# verb -- the first pass of this extractor returned head="parks" for "the gray van
# parks on the right", which would have handed OWLv2 a query no detector can ground.
_VERBS = ("park", "walk", "drive", "move", "wait", "stand", "ride", "travel", "cross",
          "stop", "run", "sit", "gather", "line", "head", "turn", "pass", "carry",
          "locate", "situate", "position", "surround", "occupy", "approach", "follow",
          "navigate", "wear", "make", "add", "rest", "span", "push", "hold", "lead",
          "form", "dot", "feature", "include", "appear", "remain", "weave", "flank",
          "traverse", "await", "queue", "load", "unload", "haul", "tow", "share")


def _forms(stem: str) -> tuple[str, ...]:
    """Inflect a verb stem. Naive concatenation gives 'driveing', which matches
    nothing and let 'red cars driving' through with head='driving'."""
    if stem.endswith("e"):
        return (stem, stem + "s", stem + "d", stem[:-1] + "ing")
    if stem.endswith("y"):
        return (stem, stem[:-1] + "ies", stem[:-1] + "ied", stem + "ing")
    return (stem, stem + "s", stem + "ed", stem + "ing")


# Leading space, no trailing one, so a verb also fires at end-of-string
# ("the black cars park").
CUTS = _PREPS + tuple(f" {f}" for v in _VERBS for f in _forms(v))
ARTICLES = ("the ", "a ", "an ", "this ", "that ", "these ", "those ")


def noun_phrase(caption: str) -> str:
    """Referring expression -> noun phrase, adjectives kept. Deterministic."""
    t = caption.strip().lower().rstrip(".").strip()
    for art in ARTICLES:
        if t.startswith(art):
            t = t[len(art):]
            break
    cut = len(t)
    for marker in CUTS:
        i = t.find(marker)
        if i != -1:
            cut = min(cut, i)
    t = t[:cut].strip()
    return re.sub(r"\s+", " ", t) or caption.strip().lower().rstrip(".")


def head_noun(phrase: str) -> str:
    """Noun phrase -> bare head noun (its last word)."""
    words = phrase.split()
    return words[-1] if words else phrase


@torch.no_grad()
def detect(model, proc, image: Image.Image, text: str, device: str) -> dict:
    """One forward pass. Returns the top-k boxes in ORIGINAL pixel coords.

    `truncation=True` is load-bearing, not hygiene: OWLv2's text encoder has
    `max_position_embeddings = 16`, so a query of 17+ tokens crashes the forward
    pass outright (`size of tensor a (17) must match tensor b (16)`). That is an
    architectural ceiling on how long a referring expression this detector can
    even represent, and `n_truncated` in the output records where it bit.
    """
    n_tok = len(proc.tokenizer(text)["input_ids"])
    inputs = proc(text=[[text]], images=image, return_tensors="pt",
                  truncation=True, max_length=16).to(device)
    if device == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    out = model(**inputs)
    if device == "cuda":
        torch.cuda.synchronize()
    fwd_ms = (time.perf_counter() - t0) * 1000

    # OWLv2 pads to a square before resizing to 960; post_process needs the
    # UNPADDED size or every box comes back stretched. Passing the true (h, w)
    # is what maps the boxes back to original pixels.
    w, h = image.size
    res = proc.post_process_grounded_object_detection(
        outputs=out, target_sizes=torch.tensor([[h, w]]), threshold=0.0)[0]
    scores = res["scores"].float().cpu()
    boxes = res["boxes"].float().cpu()
    k = min(TOPK, scores.numel())
    trunc = n_tok > 16
    if k == 0:
        return {"boxes": [], "scores": [], "fwd_ms": round(fwd_ms, 2),
                "n_tok": n_tok, "truncated": trunc}
    top = torch.topk(scores, k)
    return {
        "boxes": [[round(v, 2) for v in boxes[i].tolist()] for i in top.indices],
        "scores": [round(v, 5) for v in top.values.tolist()],
        "fwd_ms": round(fwd_ms, 2), "n_tok": n_tok, "truncated": trunc,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True, help="jsonl: image_path, caption, gt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", default=".", help="prefix for image_path")
    ap.add_argument("--n", type=int, default=0, help="cap samples (0 = all); smoke lever")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    samples = [json.loads(l) for l in Path(args.manifest).read_text().splitlines() if l.strip()]
    if args.n:
        samples = samples[:args.n]

    t0 = time.time()
    proc = Owlv2Processor.from_pretrained(MODEL_ID)
    model = Owlv2ForObjectDetection.from_pretrained(
        MODEL_ID, dtype=torch.float16).to(device).eval()
    load_s = round(time.time() - t0, 1)
    print(f"[r13] {MODEL_ID} on {device} in {load_s}s, "
          f"{sum(p.numel() for p in model.parameters())/1e6:.1f}M params", flush=True)

    root = Path(args.root)
    fh = Path(args.out).open("w")
    t_run = time.time()
    for i, s in enumerate(samples):
        img = Image.open(root / s["image_path"]).convert("RGB")
        phrase = noun_phrase(s["caption"])
        head = head_noun(phrase)
        rec = {"i": i, "image_path": s["image_path"], "caption": s["caption"],
               "gt": s["gt"], "img_wh": list(img.size),
               "text": {"full": s["caption"].strip().lower().rstrip("."),
                        "phrase": phrase, "head": head}}
        for arm, text in rec["text"].items():
            rec[arm] = detect(model, proc, img, text, device)
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        if (i + 1) % 25 == 0:
            el = time.time() - t_run
            print(f"  [r13] {i+1}/{len(samples)}  {el/(i+1):.2f}s/sample  "
                  f"eta {(len(samples)-i-1)*el/(i+1)/60:.1f}min", flush=True)
    fh.close()

    peak = torch.cuda.max_memory_allocated() / 1048576 if device == "cuda" else 0
    meta = {"model": MODEL_ID, "device": device, "dtype": "float16", "topk": TOPK,
            "n": len(samples), "load_s": load_s,
            "run_s": round(time.time() - t_run, 1),
            "peak_cuda_mb": round(peak, 1),
            "transformers": __import__("transformers").__version__,
            "torch": torch.__version__}
    Path(args.out).with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[r13] done {meta}", flush=True)


if __name__ == "__main__":
    main()
