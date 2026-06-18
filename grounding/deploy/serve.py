"""Jetson deployment + the deployment-fidelity gate (Phase 4b).

Closes the loop the v2 design opened: pushes an exported GGUF (+ its `mmproj`) to
the Jetson Orin Nano, serves it through `llama-server` with CUDA offload, scores it
over the full RefDrone val with the *same* contract path every other backend uses,
and gates the deployed IoU against the committed HF reference within the
Phase-0-characterised fidelity budget.

**Why the gate lives here, on the device (DECISIONS.md 2026-06-18):** the Jetson is
the real deployment target, has CUDA (seconds/sample vs the CPU-hours an n=439 GGUF
eval at 1024px costs locally), and runs the *same pinned llama.cpp commit* as the
local build, so backend version is not a confound — only the hardware differs. The
F16↔Q8 disambiguation that Part-I conflated (−23pp runtime + −7pp quant, stacked
and only seen post-hoc) is therefore measured here, on the actual fine-tuned aerial
model, with preprocessing held fixed by the shared `_llama_server_chat` request path.
"""

from __future__ import annotations

import os
import subprocess

from grounding.eval.backends import JetsonBackend

# Where the GGUF artifacts land on the device. Self-contained per checkpoint so
# multiple skills can coexist; gitignored remote-side (it's a deploy target, not a repo).
_DEFAULT_REMOTE_DIR = "/home/jfdg/grounding"


def push(local_path: str, remote_dir: str = _DEFAULT_REMOTE_DIR, *,
         ssh_host: str = "jetson") -> str:
    """`scp` one artifact to `remote_dir` on the Jetson; return its remote path.

    Idempotent by size: if a same-named remote file already has the same byte count,
    the copy is skipped (the GGUFs are multi-GB; re-pushing on every run is wasteful).
    """
    name = os.path.basename(local_path)
    remote_path = f"{remote_dir}/{name}"
    local_size = os.path.getsize(local_path)

    subprocess.run(["ssh", ssh_host, f"mkdir -p {remote_dir}"], check=True, timeout=30)
    probe = subprocess.run(
        ["ssh", ssh_host, f"stat -c %s {remote_path} 2>/dev/null || echo MISSING"],
        capture_output=True, text=True, timeout=30,
    )
    remote_size = probe.stdout.strip()
    if remote_size == str(local_size):
        print(f"[deploy] reuse remote {name} ({local_size / 1e9:.2f} GB, sizes match)",
              flush=True)
        return remote_path

    print(f"[deploy] scp {name} -> {ssh_host}:{remote_dir} ({local_size / 1e9:.2f} GB)...",
          flush=True)
    subprocess.run(["scp", local_path, f"{ssh_host}:{remote_path}"], check=True)
    return remote_path


def deploy(gguf_path: str, mmproj_path: str, *,
           remote_dir: str = _DEFAULT_REMOTE_DIR, ssh_host: str = "jetson",
           n_gpu_layers: int = 99, n_ctx: int = 4096,
           max_side: int = 1024, startup_timeout_s: int = 300) -> JetsonBackend:
    """Push the GGUF + mmproj to the Jetson and return a ready `JetsonBackend`.

    Full GPU offload (`n_gpu_layers=99`) by default — Qwen2-VL-2B fits the 8 GB
    unified memory. `max_side=1024` matches the resolution the Phase-3 checkpoint was
    trained/evaluated under (do not change it without re-stating the comparison).
    """
    remote_gguf = push(gguf_path, remote_dir, ssh_host=ssh_host)
    remote_mmproj = push(mmproj_path, remote_dir, ssh_host=ssh_host)
    return JetsonBackend(
        remote_gguf, remote_mmproj,
        ssh_host=ssh_host, n_gpu_layers=n_gpu_layers, n_ctx=n_ctx,
        max_side=max_side, startup_timeout_s=startup_timeout_s,
    )


def verify_deployment(backend: JetsonBackend, *, hf_iou_gate: float,
                      fidelity_budget_pp: float, split: str = "val",
                      max_samples: int = 0) -> bool:
    """Gate: deployed IoU within `fidelity_budget_pp` of the HF reference.

    Scores `backend` over RefDrone `split` and returns whether the deployed
    IoU@0.25 pass-rate is no worse than `hf_iou_gate − fidelity_budget_pp/100`.
    Prints the contract metrics and the measured drop so the result is legible in
    the run log; the caller persists the manifest + parity table.
    """
    from grounding.data.refdrone import load_refdrone
    from grounding.eval.harness import evaluate

    samples = load_refdrone(split, max_samples=max_samples)
    print(f"[deploy] verifying over RefDrone '{split}' (n={len(samples)})...", flush=True)
    report = evaluate(backend, samples, progress_every=max(1, len(samples) // 10))

    drop_pp = (hf_iou_gate - report.iou_gate_pass_rate) * 100
    floor = hf_iou_gate - fidelity_budget_pp / 100
    passed = report.iou_gate_pass_rate >= floor
    print(f"[deploy] deployed IoU@0.25={report.iou_gate_pass_rate:.1%} "
          f"(HF={hf_iou_gate:.1%}, drop={drop_pp:+.1f}pp, "
          f"budget={fidelity_budget_pp:.1f}pp, floor={floor:.1%}) "
          f"-> {'PASS' if passed else 'FAIL'}", flush=True)
    return passed
