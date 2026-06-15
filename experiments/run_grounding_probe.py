#!/usr/bin/env python3
"""
run_grounding_probe.py — Phase A zero-shot grounding probe (Stage 1 baseline).
                          Jetson Orin Nano 8 GB.

Campaign: 2026-06-14-stage1-baseline / Phase A
Protocol pre-registered in results/2026-06-14-stage1-baseline/README.md

Prerequisites:
  1. RefDrone annotations downloaded locally:
       huggingface-cli download datasets/sunzc-sunny/RefDrone --repo-type dataset \\
         --local-dir /path/to/refdrone-annotations
  2. VisDrone 2019-DET images downloaded locally (filenames match annotation image_ids).
  3. jetson_clocks locked on device.

Run from repo root:
    python experiments/run_grounding_probe.py \\
        --refdrone-ann /path/to/RefDrone_val_mdetr.json \\
        --visdrone-images /path/to/VisDrone2019-DET/images/val \\
        [--only S1,S2] [--dry-run] [--skip-download] [--pilot-only]

Options:
    --only S1,S2       run only these unit IDs (S1=SmolVLM-256M, S2=SmolVLM-500M)
    --dry-run          print commands without executing
    --skip-download    assume models already on device
    --pilot-only       run 5-image format pilot only; exit before bulk run
    --n-sample N       override sample size (default 50)
    --seed SEED        random seed for sample (default 42)
    --format A|B       force a specific prompt format; skip pilot
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import math
import random
import re
import statistics
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from parsers import parse_tegrastats, TegrastatsSummary

# ── constants ────────────────────────────────────────────────────────────────

JETSON_HOST  = "jetson"
LLAMA_SERVER = "~/llama.cpp/build/bin/llama-server"
LLAMA_LD     = "~/llama.cpp/build/bin:/usr/local/cuda/lib64"
MODELS_DIR   = "~/models"
SERVER_PORT  = 8080

HF_TOKEN_FILE = Path(__file__).parent.parent / ".hugging-face-token"
REPO_ROOT     = Path(__file__).parent.parent
RESULTS_DIR   = REPO_ROOT / "results"
CAMPAIGN_DIR  = RESULTS_DIR / "2026-06-14-stage1-baseline"
RAW_DIR       = CAMPAIGN_DIR / "raw"
RESULTS_MD    = REPO_ROOT / "RESULTS.md"
PHASE_A_MD    = CAMPAIGN_DIR / "phase-a-grounding-probe.md"

DATE            = "2026-06-14"
BASELINE_COMMIT = "57fe1f0"
NGL             = 99
SERVER_HEALTH_TIMEOUT_S = 180

N_SAMPLE_DEFAULT = 50
SEED_DEFAULT     = 42
PILOT_N          = 5   # images per format in format pilot

# ── model catalogue ──────────────────────────────────────────────────────────

@dataclass
class ModelSpec:
    unit_id: str
    name: str
    params_b: float
    quant: str
    gguf_file: str
    mmproj_file: str
    hf_repo_text: str
    hf_repo_mmproj: str
    expected_mb_text: int
    expected_mb_mmproj: int
    is_gated: bool
    server_extra_args: str = ""
    notes: str = ""


MODELS: list[ModelSpec] = [
    ModelSpec(
        unit_id="S1",
        name="SmolVLM-256M-Instruct",
        params_b=0.26,
        quant="Q8_0",
        gguf_file="SmolVLM-256M-Instruct-Q8_0.gguf",
        mmproj_file="mmproj-SmolVLM-256M-Instruct-f16.gguf",
        hf_repo_text="ggml-org/SmolVLM-256M-Instruct-GGUF",
        hf_repo_mmproj="ggml-org/SmolVLM-256M-Instruct-GGUF",
        expected_mb_text=167,
        expected_mb_mmproj=182,
        is_gated=False,
        notes="Both files already on device from VLM feasibility campaign (V1).",
    ),
    ModelSpec(
        unit_id="S2",
        name="SmolVLM-500M-Instruct",
        params_b=0.50,
        quant="Q8_0",
        gguf_file="SmolVLM-500M-Instruct-Q8_0.gguf",
        mmproj_file="mmproj-SmolVLM-500M-Instruct-f16.gguf",
        hf_repo_text="ggml-org/SmolVLM-500M-Instruct-GGUF",
        hf_repo_mmproj="ggml-org/SmolVLM-500M-Instruct-GGUF",
        expected_mb_text=522,
        expected_mb_mmproj=182,
        is_gated=False,
        notes="Both files already on device from VLM feasibility campaign (V2).",
    ),
]

# ── prompt formats ────────────────────────────────────────────────────────────

def prompt_format_a(expression: str, width: int, height: int) -> str:
    """JSON output format — explicit field names, absolute pixels."""
    return (
        f"Give the bounding box of '{expression}' as JSON "
        f'{{\"x1\":...,\"y1\":...,\"x2\":...,\"y2\":...}} in pixel coordinates. '
        f"Image size is {width}×{height}. If not present, reply null."
    )


def prompt_format_b(expression: str, _width: int, _height: int) -> str:
    """Plain csv format — minimal tokens, absolute pixels."""
    return (
        f"Locate '{expression}' in the image. "
        f"Reply with only: x1,y1,x2,y2 in pixel coordinates. "
        f"If not present, reply 'none'."
    )


PROMPT_FORMATS = {"A": prompt_format_a, "B": prompt_format_b}

# ── bbox utilities ────────────────────────────────────────────────────────────

@dataclass
class Bbox:
    x1: float
    y1: float
    x2: float
    y2: float

    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    def is_valid(self, w: int, h: int) -> bool:
        return (0 <= self.x1 < self.x2 <= w) and (0 <= self.y1 < self.y2 <= h)


def iou(a: Bbox, b: Bbox) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a.area() + b.area() - inter
    return inter / union if union > 0 else 0.0


def xywh_to_xyxy(x: float, y: float, w: float, h: float) -> Bbox:
    """Convert RefDrone MDETR annotation [x,y,w,h] to Bbox."""
    return Bbox(x1=x, y1=y, x2=x + w, y2=y + h)


def parse_response_a(text: str, img_w: int, img_h: int) -> Optional[Bbox]:
    """Parse format-A JSON response into a Bbox. Returns None on parse failure."""
    text = text.strip()
    if text.lower() in ("null", "none", ""):
        return None
    m = re.search(
        r'\{[^}]*"x1"\s*:\s*(-?[\d.]+)[^}]*"y1"\s*:\s*(-?[\d.]+)'
        r'[^}]*"x2"\s*:\s*(-?[\d.]+)[^}]*"y2"\s*:\s*(-?[\d.]+)[^}]*\}',
        text,
    )
    if not m:
        # try permissive variant (fields in any order)
        coords = dict(re.findall(r'"(x[12]|y[12])"\s*:\s*(-?[\d.]+)', text))
        if len(coords) == 4:
            try:
                box = Bbox(float(coords["x1"]), float(coords["y1"]),
                           float(coords["x2"]), float(coords["y2"]))
                return box if box.is_valid(img_w, img_h) else None
            except (ValueError, KeyError):
                return None
        return None
    try:
        box = Bbox(float(m.group(1)), float(m.group(2)),
                   float(m.group(3)), float(m.group(4)))
        return box if box.is_valid(img_w, img_h) else None
    except ValueError:
        return None


def parse_response_b(text: str, img_w: int, img_h: int) -> Optional[Bbox]:
    """Parse format-B csv response into a Bbox. Returns None on parse failure."""
    text = text.strip()
    if text.lower() in ("none", "null", ""):
        return None
    m = re.search(r"(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)", text)
    if not m:
        return None
    try:
        box = Bbox(float(m.group(1)), float(m.group(2)),
                   float(m.group(3)), float(m.group(4)))
        return box if box.is_valid(img_w, img_h) else None
    except ValueError:
        return None


RESPONSE_PARSERS = {"A": parse_response_a, "B": parse_response_b}


def _test_bbox_utils() -> None:
    b1 = xywh_to_xyxy(10, 10, 20, 20)
    b2 = Bbox(20, 20, 40, 40)
    assert abs(iou(b1, b2) - 100.0 / (400 + 400 - 100)) < 1e-6, "iou broken"

    # format A parsing
    r = parse_response_a('{"x1": 10, "y1": 20, "x2": 100, "y2": 80}', 640, 480)
    assert r is not None and r.x1 == 10, "parse_a broken"
    assert parse_response_a("null", 640, 480) is None
    assert parse_response_a("garbage text", 640, 480) is None

    # format B parsing
    r = parse_response_b("10, 20, 100, 80", 640, 480)
    assert r is not None and r.y2 == 80, "parse_b broken"
    assert parse_response_b("none", 640, 480) is None

    print("  ✓ bbox util tests passed")


# ── dataset loading ───────────────────────────────────────────────────────────

@dataclass
class GroundingItem:
    image_id: int
    image_filename: str
    image_path: Path          # absolute local path
    img_w: int
    img_h: int
    expression: str
    gt_bbox: Bbox             # XYXY absolute pixels


def load_refdrone_sample(
    ann_json: Path,
    images_dir: Path,
    n_sample: int,
    seed: int,
) -> tuple[list[GroundingItem], dict]:
    """Load RefDrone MDETR JSON, filter to single-target, sample n_sample items.

    Returns (sample, stats) where stats has filter counts for the results file.
    """
    with open(ann_json) as f:
        data = json.load(f)

    images_by_id: dict[int, dict] = {img["id"]: img for img in data["images"]}

    # group annotations by image_id
    anns_by_image: dict[int, list[dict]] = {}
    for ann in data["annotations"]:
        anns_by_image.setdefault(ann["image_id"], []).append(ann)

    # RefDrone bbox format: [x, y, width, height] absolute pixels (XYWH)
    total_images = len(images_by_id)
    single_target_items: list[GroundingItem] = []
    skipped_multi = 0
    skipped_missing = 0

    for img_id, img_info in images_by_id.items():
        anns = anns_by_image.get(img_id, [])
        if len(anns) != 1:
            skipped_multi += 1
            continue

        ann = anns[0]
        filename = img_info["file_name"]
        img_path = images_dir / filename
        if not img_path.exists():
            skipped_missing += 1
            continue

        x, y, w, h = ann["bbox"]
        if w <= 0 or h <= 0:
            # [0,0,0,0] no-target entries: RefDrone includes these in the single-annotation
            # count but they represent expressions with no visible referent — skip them.
            skipped_multi += 1
            continue
        gt = xywh_to_xyxy(x, y, w, h)

        # RefDrone: expression is in the image record's 'caption' field,
        # not in the annotation (confirmed from RefDrone_val_mdetr.json).
        expression = img_info.get("caption") or ""
        if not expression:
            skipped_multi += 1  # no expression = unusable
            continue

        single_target_items.append(GroundingItem(
            image_id=img_id,
            image_filename=filename,
            image_path=img_path,
            img_w=img_info["width"],
            img_h=img_info["height"],
            expression=expression,
            gt_bbox=gt,
        ))

    rng = random.Random(seed)
    rng.shuffle(single_target_items)
    sample = single_target_items[:n_sample]

    stats = {
        "total_images": total_images,
        "single_target": len(single_target_items),
        "skipped_multi_or_no_expr": skipped_multi,
        "skipped_missing_image": skipped_missing,
        "sampled": len(sample),
        "seed": seed,
    }
    return sample, stats


# ── SSH helpers ───────────────────────────────────────────────────────────────

def ssh(cmd: str, capture: bool = True, check: bool = True,
        timeout: int = 600) -> subprocess.CompletedProcess:
    full = ["ssh", JETSON_HOST, cmd]
    if capture:
        return subprocess.run(full, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=timeout, check=check)
    return subprocess.run(full, stdin=subprocess.DEVNULL,
                          timeout=timeout, check=check)


def scp_get(remote: str, local: Path) -> None:
    subprocess.run(["scp", f"{JETSON_HOST}:{remote}", str(local)],
                   check=True, timeout=120)


def ssh_bg(cmd: str) -> None:
    wrapped = f"nohup sh -c {repr(cmd)} </dev/null >/dev/null 2>&1 &"
    subprocess.run(["ssh", JETSON_HOST, wrapped], check=True, timeout=30)


def _ld_prefix() -> str:
    return f"export LD_LIBRARY_PATH={LLAMA_LD}; "


def _die(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ── preflight ─────────────────────────────────────────────────────────────────

def check_preconditions(dry_run: bool) -> str:
    print("── preflight checks ──────────────────────────────────────────")
    if dry_run:
        print("  [dry-run] skipping preflight")
        return BASELINE_COMMIT

    try:
        ssh("true")
        print("  ✓ ssh jetson")
    except Exception as e:
        _die(f"SSH to '{JETSON_HOST}' failed: {e}")

    r = ssh(f"test -x {LLAMA_SERVER} && echo ok || echo missing", check=False)
    if "ok" not in r.stdout:
        _die(f"llama-server not found at {LLAMA_SERVER}.")
    print(f"  ✓ {LLAMA_SERVER} present")

    r = ssh("git -C ~/llama.cpp rev-parse --short HEAD 2>/dev/null || echo unknown",
            check=False)
    commit = r.stdout.strip()
    if commit == BASELINE_COMMIT:
        print(f"  ✓ llama.cpp @ {commit} (baseline)")
    else:
        print(f"  ℹ  llama.cpp @ {commit} (differs from baseline {BASELINE_COMMIT})")

    r = ssh("nvpmodel -q 2>/dev/null | head -3", check=False)
    print(f"  ℹ  nvpmodel: {r.stdout.strip()!r}")
    r = ssh("df -BM --output=avail / | tail -1", check=False)
    avail_mb = int(r.stdout.strip().rstrip("M"))
    if avail_mb < 2000:
        print(f"  ⚠  only {avail_mb} MB free — may not fit SmolVLM files")
    else:
        print(f"  ✓ {avail_mb} MB free")
    return commit


# ── model acquisition ─────────────────────────────────────────────────────────

def _hf_token() -> str:
    return HF_TOKEN_FILE.read_text().strip() if HF_TOKEN_FILE.exists() else ""


def _ensure_file(remote_path: str, hf_repo: str, filename: str,
                 expected_mb: int, is_gated: bool,
                 dry_run: bool, label: str) -> None:
    if dry_run:
        print(f"  [dry-run] would ensure {remote_path}")
        return
    r = ssh(f"test -s {remote_path} && du -m {remote_path} | cut -f1 || echo missing",
            check=False)
    if r.stdout.strip() != "missing":
        print(f"  ✓ {label} already on device ({r.stdout.strip()} MB)")
        return
    token = _hf_token() if is_gated else ""
    url = f"https://huggingface.co/{hf_repo}/resolve/main/{filename}?download=true"
    size_hint = f" (~{expected_mb} MB)" if expected_mb > 0 else ""
    print(f"  ↓ downloading {label}{size_hint} …")
    auth_flag = f'--header="Authorization: Bearer {token}"' if token else ""
    ssh(f"wget -c {auth_flag} -O {remote_path} '{url}'", capture=False, timeout=7200)
    print(f"  ✓ downloaded {label}")


def ensure_model(spec: ModelSpec, dry_run: bool) -> tuple[str, str]:
    text_path   = f"{MODELS_DIR}/{spec.gguf_file}"
    mmproj_path = f"{MODELS_DIR}/{spec.mmproj_file}"
    _ensure_file(text_path, spec.hf_repo_text, spec.gguf_file,
                 spec.expected_mb_text, spec.is_gated, dry_run, "text model")
    _ensure_file(mmproj_path, spec.hf_repo_mmproj, spec.mmproj_file,
                 spec.expected_mb_mmproj, spec.is_gated, dry_run, "mmproj")
    return text_path, mmproj_path


# ── HTTP client helpers ────────────────────────────────────────────────────────

def _img_mime(path: Path) -> str:
    return "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"


def _img_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _build_payload(img_b64: str, mime: str, prompt_text: str,
                   max_tokens: int = 100) -> bytes:
    return json.dumps({
        "model": "vlm",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                {"type": "text", "text": prompt_text},
            ],
        }],
        "max_tokens": max_tokens,
        "cache_prompt": False,
        "__verbose": True,
    }).encode()


def _post(payload: bytes, timeout: int = 300) -> str:
    req = urllib.request.Request(
        f"http://localhost:{SERVER_PORT}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode()


def _response_text(json_text: str) -> str:
    try:
        data = json.loads(json_text)
        return data["choices"][0]["message"].get("content") or ""
    except Exception:
        return ""


def _response_ms(json_text: str) -> float:
    """Return prompt_ms + decode_ms from __verbose timings, or 0 on failure."""
    try:
        data = json.loads(json_text)
        t = data.get("__verbose", {}).get("timings", {})
        return t.get("prompt_ms", 0) + t.get("predicted_ms", 0)
    except Exception:
        return 0.0


def _wait_health(timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(
                f"http://localhost:{SERVER_PORT}/health", timeout=3)
            if b"ok" in r.read():
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


# ── server lifecycle ──────────────────────────────────────────────────────────

def start_server(spec: ModelSpec, text_path: str, mmproj_path: str,
                 dry_run: bool) -> tuple[subprocess.Popen, bool, int]:
    """Start llama-server + port-forward. Returns (pf_proc, load_failed, load_s)."""
    tag = f"grounding{spec.unit_id}"
    server_log_remote = f"/tmp/{tag}_server.log"

    extra = f" {spec.server_extra_args}" if spec.server_extra_args else ""
    server_cmd = (
        _ld_prefix() +
        f"{LLAMA_SERVER} -m {text_path} --mmproj {mmproj_path} "
        f"-ngl {NGL} --port {SERVER_PORT} -v{extra} "
        f"> {server_log_remote} 2>&1"
    )

    if dry_run:
        print(f"  [dry-run] server: {server_cmd}")
        dummy = subprocess.Popen(["true"])
        return dummy, False, 0

    ssh_bg(server_cmd)
    start_t = time.time()

    pf = subprocess.Popen(
        ["ssh", "-N", "-L", f"{SERVER_PORT}:localhost:{SERVER_PORT}", JETSON_HOST],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    print(f"  ⏳ waiting for server health (up to {SERVER_HEALTH_TIMEOUT_S}s) …")
    healthy = _wait_health(SERVER_HEALTH_TIMEOUT_S)
    load_s = int(time.time() - start_t)

    if not healthy:
        print(f"  ✗ server did not become healthy after {load_s}s — likely OOM")
        return pf, True, load_s

    print(f"  ✓ server healthy in {load_s}s")
    return pf, False, load_s


def stop_server(pf: subprocess.Popen) -> None:
    ssh("pkill -f llama-server || true", check=False)
    time.sleep(2)
    pf.terminate()
    try:
        pf.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pf.kill()


# ── format pilot ──────────────────────────────────────────────────────────────

@dataclass
class PilotResult:
    fmt: str
    parse_count: int
    total: int
    responses: list[str] = field(default_factory=list)

    @property
    def parse_rate(self) -> float:
        return self.parse_count / self.total if self.total > 0 else 0.0


def run_format_pilot(
    pilot_items: list[GroundingItem],
    fmt: str,
    parse_fn,
    dry_run: bool,
) -> PilotResult:
    """Run PILOT_N images with a given format; return parse count."""
    result = PilotResult(fmt=fmt, parse_count=0, total=len(pilot_items))

    for item in pilot_items:
        prompt = PROMPT_FORMATS[fmt](item.expression, item.img_w, item.img_h)
        payload = _build_payload(
            _img_b64(item.image_path), _img_mime(item.image_path), prompt, max_tokens=80
        )
        if dry_run:
            print(f"    [dry-run] would send: {prompt[:80]}…")
            result.responses.append("[dry-run]")
            result.parse_count += 1
            continue
        try:
            raw = _post(payload)
            text = _response_text(raw)
            box = parse_fn(text, item.img_w, item.img_h)
            result.responses.append(text)
            if box is not None:
                result.parse_count += 1
                status = f"✓ parsed  box={box.x1:.0f},{box.y1:.0f},{box.x2:.0f},{box.y2:.0f}"
            else:
                status = f"✗ no parse  raw={text[:60]!r}"
            print(f"      [{item.image_filename}] {status}")
        except Exception as e:
            result.responses.append(f"(error: {e})")
            print(f"      [{item.image_filename}] ✗ request error: {e}")

    return result


# ── bulk grounding probe ───────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    item: GroundingItem
    raw_response: str
    predicted_box: Optional[Bbox]
    iou_score: float          # 0.0 if no predicted box
    wall_ms: float


def run_bulk_probe(
    sample: list[GroundingItem],
    fmt: str,
    parse_fn,
    dry_run: bool,
) -> list[ProbeResult]:
    results: list[ProbeResult] = []

    for i, item in enumerate(sample):
        prompt = PROMPT_FORMATS[fmt](item.expression, item.img_w, item.img_h)
        payload = _build_payload(
            _img_b64(item.image_path), _img_mime(item.image_path), prompt, max_tokens=80
        )

        if dry_run:
            results.append(ProbeResult(
                item=item, raw_response="[dry-run]", predicted_box=None,
                iou_score=0.0, wall_ms=0.0,
            ))
            if (i + 1) % 10 == 0:
                print(f"  [dry-run] {i+1}/{len(sample)} done")
            continue

        t0 = time.time()
        try:
            raw = _post(payload, timeout=60)
            wall_ms = (time.time() - t0) * 1000
            text = _response_text(raw)
            box = parse_fn(text, item.img_w, item.img_h)
            score = iou(box, item.gt_bbox) if box is not None else 0.0
            results.append(ProbeResult(
                item=item, raw_response=text, predicted_box=box,
                iou_score=score, wall_ms=wall_ms,
            ))
            if (i + 1) % 10 == 0 or i < 3:
                parsed_str = f"iou={score:.3f}" if box else "no-parse"
                print(f"  {i+1:3d}/{len(sample)}  [{item.image_filename}]  {parsed_str}")
        except Exception as e:
            wall_ms = (time.time() - t0) * 1000
            print(f"  {i+1:3d}/{len(sample)}  ✗ error: {e}")
            results.append(ProbeResult(
                item=item, raw_response=f"(error: {e})", predicted_box=None,
                iou_score=0.0, wall_ms=wall_ms,
            ))

    return results


# ── aggregate metrics ─────────────────────────────────────────────────────────

@dataclass
class ProbeMetrics:
    n_total: int
    n_parsed: int
    n_iou25: int
    n_iou50: int
    mean_iou: float
    median_wall_ms: float
    hz: float

    @property
    def parse_rate(self) -> float:
        return self.n_parsed / self.n_total if self.n_total > 0 else 0.0

    @property
    def iou25_rate(self) -> float:
        return self.n_iou25 / self.n_parsed if self.n_parsed > 0 else 0.0

    @property
    def iou50_rate(self) -> float:
        return self.n_iou50 / self.n_parsed if self.n_parsed > 0 else 0.0


def compute_metrics(results: list[ProbeResult]) -> ProbeMetrics:
    n_total = len(results)
    parsed = [r for r in results if r.predicted_box is not None]
    n_parsed = len(parsed)
    n_iou25 = sum(1 for r in parsed if r.iou_score >= 0.25)
    n_iou50 = sum(1 for r in parsed if r.iou_score >= 0.50)
    ious = [r.iou_score for r in parsed]
    mean_iou = statistics.mean(ious) if ious else 0.0
    walls = [r.wall_ms for r in results if r.wall_ms > 0]
    median_wall = statistics.median(walls) if walls else 0.0
    hz = 1000.0 / median_wall if median_wall > 0 else 0.0
    return ProbeMetrics(
        n_total=n_total,
        n_parsed=n_parsed,
        n_iou25=n_iou25,
        n_iou50=n_iou50,
        mean_iou=mean_iou,
        median_wall_ms=median_wall,
        hz=hz,
    )


# ── result formatting ─────────────────────────────────────────────────────────

def format_result_block(
    spec: ModelSpec,
    fmt: str,
    pilot: Optional[PilotResult],
    metrics: ProbeMetrics,
    tegra: TegrastatsSummary,
    load_s: int,
    run_ts: str,
    actual_commit: str,
    dataset_stats: dict,
    load_failed: bool,
) -> str:
    header = f"### Unit {spec.unit_id} — {spec.name} {spec.quant}"
    run_line = (
        f"**Run:** {run_ts} UTC · 15 W locked · llama.cpp `{actual_commit}` CUDA sm_87  \n"
        f"**Dataset:** RefDrone val split, N={dataset_stats['sampled']}, "
        f"seed={dataset_stats['seed']}, single-target filter "
        f"({dataset_stats['single_target']}/{dataset_stats['total_images']} images)  \n"
        f"**Prompt format:** {fmt}"
        + (f"  \n**Note:** {spec.notes}" if spec.notes else "")
    )

    if load_failed:
        return textwrap.dedent(f"""\
        {header} (**FAILED TO LOAD**)

        {run_line}

        | Metric | Value |
        |---|---|
        | Load result | **OOM / server never healthy** |
        | Peak RAM at failure | {tegra.peak_ram_mb:.0f} MB |

        > **Negative result.** Documented as thesis content.

        """)

    pilot_line = ""
    if pilot:
        pilot_line = (
            f"| Format pilot | Format {pilot.fmt}: "
            f"{pilot.parse_count}/{pilot.total} parsed "
            f"({pilot.parse_rate*100:.0f}%) |\n"
        )

    return textwrap.dedent(f"""\
    {header}

    {run_line}

    | Metric | Value |
    |---|---|
    | Server load time | {load_s} s |
    {pilot_line}| **Parse rate** | **{metrics.n_parsed}/{metrics.n_total} ({metrics.parse_rate*100:.1f}%)** |
    | **IoU@0.25** (of parsed) | **{metrics.n_iou25}/{metrics.n_parsed} ({metrics.iou25_rate*100:.1f}%)** |
    | **IoU@0.5** (of parsed) | **{metrics.n_iou50}/{metrics.n_parsed} ({metrics.iou50_rate*100:.1f}%)** |
    | **Mean IoU** (of parsed) | **{metrics.mean_iou:.3f}** |
    | Median wall ms / frame | {metrics.median_wall_ms:.0f} ms |
    | **Hz** (grounding rate) | **{metrics.hz:.2f} Hz** |
    | Peak RAM | {tegra.peak_ram_mb:.0f} MB |
    | Swap hit | {'YES ⚠' if tegra.swap_hit else 'no'} |
    | Power — mean (active) | {tegra.mean_w:.2f} W |
    | Peak SoC temp | {tegra.peak_temp_c:.1f} °C |

    """)


def results_md_row(spec: ModelSpec, fmt: str, metrics: ProbeMetrics,
                   tegra: TegrastatsSummary, run_ts: str, load_failed: bool) -> str:
    if load_failed:
        return (
            f"| {run_ts[:10]} | {spec.unit_id} | {spec.name} {spec.quant} "
            f"| Phase A grounding | 15W locked | **LOAD FAILED** | — | — | — |"
        )
    return (
        f"| {run_ts[:10]} | {spec.unit_id} | {spec.name} {spec.quant} "
        f"| Phase A grounding | 15W locked "
        f"| format={fmt} parse={metrics.parse_rate*100:.0f}% "
        f"iou@0.25={metrics.iou25_rate*100:.0f}% "
        f"iou@0.5={metrics.iou50_rate*100:.0f}% "
        f"mean_iou={metrics.mean_iou:.3f} "
        f"| {metrics.hz:.2f}Hz "
        f"| {tegra.peak_ram_mb:.0f}MB {'swap' if tegra.swap_hit else ''} |"
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refdrone-ann",   required=True,
                        help="Path to RefDrone_val_mdetr.json")
    parser.add_argument("--visdrone-images", required=True,
                        help="Directory of VisDrone images referenced in annotation")
    parser.add_argument("--only",           help="comma-separated unit IDs, e.g. S1,S2")
    parser.add_argument("--dry-run",        action="store_true")
    parser.add_argument("--skip-download",  action="store_true")
    parser.add_argument("--pilot-only",     action="store_true",
                        help="Run format pilot only; skip bulk run")
    parser.add_argument("--n-sample",       type=int, default=N_SAMPLE_DEFAULT)
    parser.add_argument("--seed",           type=int, default=SEED_DEFAULT)
    parser.add_argument("--format",         choices=["A", "B"],
                        help="Force format; skip pilot")
    args = parser.parse_args()

    only_ids = set(args.only.split(",")) if args.only else None
    ann_path = Path(args.refdrone_ann)
    img_dir  = Path(args.visdrone_images)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("═" * 65)
    print("  Jetson Orin Nano — Stage 1 Phase A grounding probe")
    print("═" * 65)
    print()

    # ── dataset ───────────────────────────────────────────────────────────────
    if args.dry_run:
        print(f"[dry-run] would load dataset from {ann_path}")
        sample, dataset_stats = [], {
            "total_images": 0, "single_target": 0,
            "skipped_multi_or_no_expr": 0, "skipped_missing_image": 0,
            "sampled": args.n_sample, "seed": args.seed,
        }
    else:
        print(f"Loading RefDrone from {ann_path} …")
        sample, dataset_stats = load_refdrone_sample(
            ann_path, img_dir, args.n_sample, args.seed
        )
        print(f"  total images:          {dataset_stats['total_images']}")
        print(f"  single-target:         {dataset_stats['single_target']}")
        print(f"  skipped multi/no-expr: {dataset_stats['skipped_multi_or_no_expr']}")
        print(f"  skipped missing image: {dataset_stats['skipped_missing_image']}")
        print(f"  sampled (seed={args.seed}): {dataset_stats['sampled']}")
        if len(sample) < args.n_sample:
            print(f"  ⚠  only {len(sample)} items available (wanted {args.n_sample})")
        print()

    actual_commit = check_preconditions(args.dry_run)
    print()

    # ── per-model loop ────────────────────────────────────────────────────────
    for spec in MODELS:
        if only_ids and spec.unit_id not in only_ids:
            continue

        print(f"── Unit {spec.unit_id}: {spec.name} {spec.quant} ──")
        if spec.notes:
            print(f"  ℹ  {spec.notes}")

        run_ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M")

        if args.skip_download:
            text_path   = f"{MODELS_DIR}/{spec.gguf_file}"
            mmproj_path = f"{MODELS_DIR}/{spec.mmproj_file}"
        else:
            text_path, mmproj_path = ensure_model(spec, args.dry_run)

        # ── tegrastats ────────────────────────────────────────────────────────
        tag = f"grounding{spec.unit_id}"
        tegra_remote = f"/tmp/{tag}_tegra.log"
        tegra_local  = RAW_DIR / f"{DATE}_{tag}_tegra.log"

        if not args.dry_run:
            ssh("pkill tegrastats || true", check=False)
            time.sleep(1)
            ssh_bg(f"tegrastats --interval 1000 --logfile {tegra_remote}")
            time.sleep(5)

        # ── start server ──────────────────────────────────────────────────────
        pf, load_failed, load_s = start_server(
            spec, text_path, mmproj_path, args.dry_run
        )

        pilot_result: Optional[PilotResult] = None
        probe_results: list[ProbeResult] = []
        chosen_fmt = args.format or "A"

        try:
            if load_failed:
                pass  # skip inference; tegrastats + cleanup happens in finally

            else:
                # ── warmup ────────────────────────────────────────────────────
                if not args.dry_run and sample:
                    warmup_item = sample[0]
                    warmup_prompt = prompt_format_a(
                        warmup_item.expression, warmup_item.img_w, warmup_item.img_h
                    )
                    print("  → warmup frame …")
                    try:
                        _post(_build_payload(
                            _img_b64(warmup_item.image_path),
                            _img_mime(warmup_item.image_path),
                            warmup_prompt,
                        ))
                        print("  ✓ warmup done")
                    except Exception as e:
                        print(f"  ⚠  warmup failed: {e}")

                # ── format pilot (unless format forced) ───────────────────────
                if args.format:
                    print(f"  ℹ  prompt format forced to {args.format}")
                    chosen_fmt = args.format
                else:
                    pilot_items = sample[:PILOT_N]
                    print(f"  ── format pilot (N={PILOT_N} per format) ──")
                    results_a = run_format_pilot(
                        pilot_items, "A", RESPONSE_PARSERS["A"], args.dry_run
                    )
                    results_b = run_format_pilot(
                        pilot_items, "B", RESPONSE_PARSERS["B"], args.dry_run
                    )
                    print(
                        f"  format A: {results_a.parse_count}/{PILOT_N} parsed "
                        f"({results_a.parse_rate*100:.0f}%)"
                    )
                    print(
                        f"  format B: {results_b.parse_count}/{PILOT_N} parsed "
                        f"({results_b.parse_rate*100:.0f}%)"
                    )
                    if results_a.parse_rate >= results_b.parse_rate:
                        chosen_fmt = "A"
                        pilot_result = results_a
                    else:
                        chosen_fmt = "B"
                        pilot_result = results_b
                    print(f"  → selected format {chosen_fmt} for bulk run")

                if args.pilot_only:
                    print("  ℹ  --pilot-only: skipping bulk run")
                    continue

                # ── bulk run ──────────────────────────────────────────────────
                print(f"  ── bulk run: N={len(sample)} images, format {chosen_fmt} ──")
                probe_results = run_bulk_probe(
                    sample, chosen_fmt, RESPONSE_PARSERS[chosen_fmt], args.dry_run
                )

        finally:
            if not args.dry_run:
                stop_server(pf)
                time.sleep(1)
                ssh("pkill tegrastats || true", check=False)
                time.sleep(1)
                try:
                    scp_get(tegra_remote, tegra_local)
                    tegra_text = tegra_local.read_text()
                except Exception as e:
                    print(f"  ⚠  could not pull tegrastats: {e}")
                    tegra_text = ""
                tegra = parse_tegrastats(tegra_text)
            else:
                tegra = TegrastatsSummary()

        if args.dry_run or args.pilot_only:
            continue

        metrics = compute_metrics(probe_results)

        print(
            f"  ✓ parse={metrics.parse_rate*100:.1f}%  "
            f"iou@0.25={metrics.iou25_rate*100:.1f}%  "
            f"iou@0.5={metrics.iou50_rate*100:.1f}%  "
            f"mean_iou={metrics.mean_iou:.3f}  "
            f"hz={metrics.hz:.2f}  RAM={tegra.peak_ram_mb:.0f}MB"
        )

        # ── write results ─────────────────────────────────────────────────────
        block = format_result_block(
            spec, chosen_fmt, pilot_result, metrics, tegra,
            load_s, run_ts, actual_commit, dataset_stats, load_failed,
        )

        if PHASE_A_MD.exists():
            content = PHASE_A_MD.read_text()
            marker = "*(results to be filled in post-run)*"
            if marker in content:
                content = content.replace(marker, block, 1)
            else:
                content = content.rstrip("\n") + "\n\n" + block
            PHASE_A_MD.write_text(content)

        row = results_md_row(spec, chosen_fmt, metrics, tegra, run_ts, load_failed)
        with RESULTS_MD.open("a") as f:
            f.write(row + "\n")

        # ── raw responses ─────────────────────────────────────────────────────
        raw_out = RAW_DIR / f"{DATE}_{tag}_responses.jsonl"
        with open(raw_out, "w") as f:
            for r in probe_results:
                f.write(json.dumps({
                    "image": r.item.image_filename,
                    "expression": r.item.expression,
                    "gt": [r.item.gt_bbox.x1, r.item.gt_bbox.y1,
                           r.item.gt_bbox.x2, r.item.gt_bbox.y2],
                    "pred": ([r.predicted_box.x1, r.predicted_box.y1,
                               r.predicted_box.x2, r.predicted_box.y2]
                             if r.predicted_box else None),
                    "iou": r.iou_score,
                    "raw_response": r.raw_response,
                    "wall_ms": r.wall_ms,
                }) + "\n")
        print(f"  ✓ raw responses saved to {raw_out.relative_to(REPO_ROOT)}")
        print()

    print("═" * 65)
    print("  Phase A grounding probe complete.")
    print(f"  Results in {PHASE_A_MD.relative_to(REPO_ROOT)}")
    print(f"  Summary rows appended to RESULTS.md")
    print("═" * 65)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Running unit tests …")
        _test_bbox_utils()
        print("All tests passed.")
    else:
        main()
