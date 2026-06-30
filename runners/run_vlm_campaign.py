#!/usr/bin/env python3
"""
run_vlm_campaign.py — VLM feasibility campaign for drone vision commands.
                       Jetson Orin Nano 8 GB.

Campaign: 2026-06-14-vlm-feasibility
Protocol pre-registered in experiments/2026-06-14-vlm-feasibility/README.md

Run from the repo root:
    python runners/run_vlm_campaign.py

Prerequisites (run once on the Jetson before starting):
    ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'
    ffmpeg installed on Jetson (sudo apt install -y ffmpeg)

Options:
    --only V1,V3       run only these unit IDs (comma-separated)
    --dry-run          print what would run without executing
    --skip-download    assume models already on device
    --start-from V3    skip units before this ID
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import re
import statistics
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from parsers import (
    parse_tegrastats, parse_vlm_server_timings,
    TegrastatsSummary, VLMFrameTimings,
)

# ── constants ────────────────────────────────────────────────────────────────

JETSON_HOST  = "jetson"
LLAMA_SERVER = "~/llama.cpp/build/bin/llama-server"
LLAMA_LD     = "~/llama.cpp/build/bin:/usr/local/cuda/lib64"
MODELS_DIR   = "~/models"
SERVER_PORT  = 8080

HF_TOKEN_FILE   = Path(__file__).parent.parent / ".hugging-face-token"
REPO_ROOT       = Path(__file__).parent.parent
RESULTS_DIR     = REPO_ROOT / "results"
CAMPAIGN_DIR    = RESULTS_DIR / "2026-06-14-vlm-feasibility"
RAW_DIR         = CAMPAIGN_DIR / "raw"
RESULTS_MD      = REPO_ROOT / "RESULTS.md"
CAMPAIGN_MD     = CAMPAIGN_DIR / "README.md"
CAMPAIGN_ID     = "2026-06-14-vlm-feasibility"
DATE            = "2026-06-14"
BASELINE_COMMIT = "57fe1f0"

TEST_IMAGES = [
    CAMPAIGN_DIR / "test-images" / "highway-with-firetruck.jpg",
    CAMPAIGN_DIR / "test-images" / "multiple-collision.jpg",
    CAMPAIGN_DIR / "test-images" / "white-van-crash.jpeg",
]

NGL            = 99
N_FRAMES       = 5    # measurement frames after warmup
N_OUTPUT_TOKENS = 50  # max tokens to generate per frame
SERVER_HEALTH_TIMEOUT_S = 180

PROMPT = (
    "You are a drone flight controller. "
    "What object should the drone follow in this image? "
    'Reply in JSON: {"action": "follow", "target": "<object description>"}'
)


# ── model catalogue ──────────────────────────────────────────────────────────

@dataclass
class ModelSpec:
    unit_id: str
    name: str
    params_b: float
    quant: str
    gguf_file: str          # text model filename in ~/models/
    mmproj_file: str        # mmproj filename in ~/models/
    hf_repo_text: str       # "" if already on device
    hf_repo_mmproj: str
    expected_mb_text: int   # 0 if already on device
    expected_mb_mmproj: int
    is_gated: bool
    server_extra_args: str = ""   # extra flags appended to llama-server command
    notes: str = ""


MODELS: list[ModelSpec] = [
    ModelSpec(
        unit_id="V1",
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
        notes="Both files downloaded in previous session.",
    ),
    ModelSpec(
        unit_id="V2",
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
    ),
    ModelSpec(
        unit_id="V3",
        name="gemma-3-4b-it",
        params_b=4.0,
        quant="q4_0",
        gguf_file="gemma-3-4b-it-q4_0.gguf",
        mmproj_file="mmproj-model-f16.gguf",
        hf_repo_text="",   # already on device from G2 campaign
        hf_repo_mmproj="ggml-org/gemma-3-4b-it-GGUF",
        expected_mb_text=0,
        expected_mb_mmproj=900,
        is_gated=True,
        notes="Text weights on device (G2 campaign). Only mmproj needs downloading.",
    ),
    ModelSpec(
        unit_id="V4",
        name="gemma-4-E2B-it",
        params_b=5.1,
        quant="q4_0 QAT",
        gguf_file="gemma-4-E2B_q4_0-it.gguf",
        mmproj_file="mmproj-gemma-4-E2B-it-Q8_0.gguf",
        hf_repo_text="",   # already on device from G3 campaign
        hf_repo_mmproj="ggml-org/gemma-4-E2B-it-GGUF",
        expected_mb_text=0,
        expected_mb_mmproj=400,
        is_gated=True,
        server_extra_args="--reasoning off",
        notes="Text weights on device (G3 campaign). Thinking model — reasoning disabled for drone use (latency). First run (thinking-on) recorded in §13 results.",
    ),
    ModelSpec(
        unit_id="V5",
        name="gemma-4-E4B-it",
        params_b=8.0,
        quant="q4_0 QAT",
        gguf_file="gemma-4-E4B_q4_0-it.gguf",
        mmproj_file="mmproj-gemma-4-E4B-it-Q8_0.gguf",
        hf_repo_text="",   # already on device from G4 campaign
        hf_repo_mmproj="ggml-org/gemma-4-E4B-it-GGUF",
        expected_mb_text=0,
        expected_mb_mmproj=850,
        is_gated=True,
        server_extra_args="--reasoning off",
        notes="Stretch goal. Thinking model — reasoning disabled for drone use. First run (thinking-on) recorded in §13 results.",
    ),
]


# ── SSH helpers ──────────────────────────────────────────────────────────────

def ssh(cmd: str, capture: bool = True, check: bool = True,
        timeout: int = 600) -> subprocess.CompletedProcess:
    full = ["ssh", JETSON_HOST, cmd]
    if capture:
        return subprocess.run(full, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL,
                              timeout=timeout, check=check)
    else:
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


# ── preflight ────────────────────────────────────────────────────────────────

def get_actual_commit() -> str:
    r = ssh("git -C ~/llama.cpp rev-parse --short HEAD 2>/dev/null || echo unknown",
            check=False)
    return r.stdout.strip()


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

    r = ssh("which ffprobe 2>/dev/null && echo ok || echo missing", check=False)
    if "ok" not in r.stdout:
        _die("ffprobe not found on Jetson. Install with: sudo apt install -y ffmpeg")
    print("  ✓ ffprobe (ffmpeg) present on Jetson")

    commit = get_actual_commit()
    if commit == BASELINE_COMMIT:
        print(f"  ✓ llama.cpp @ {commit} (baseline)")
    else:
        print(f"  ℹ  llama.cpp @ {commit} (differs from baseline {BASELINE_COMMIT})")

    r = ssh("nvpmodel -q 2>/dev/null | head -3", check=False)
    print(f"  ℹ  nvpmodel: {r.stdout.strip()!r}")
    print("  ℹ  jetson_clocks: assumed locked (run sudo jetson_clocks before this script)")

    r = ssh("df -BM --output=avail / | tail -1", check=False)
    avail_mb = int(r.stdout.strip().rstrip("M"))
    if avail_mb < 5000:
        print(f"  ⚠  only {avail_mb} MB free — may not fit all mmproj files")
    else:
        print(f"  ✓ {avail_mb} MB free")

    for img in TEST_IMAGES:
        if not img.exists():
            _die(f"Test image missing: {img}. Commit images to test-images/ first.")
    print(f"  ✓ all {len(TEST_IMAGES)} test images present locally")

    ssh(f"mkdir -p {MODELS_DIR}")
    print(f"  ✓ {MODELS_DIR} exists on device")
    print()
    return commit


# ── model acquisition ─────────────────────────────────────────────────────────

def _hf_token() -> str:
    if HF_TOKEN_FILE.exists():
        return HF_TOKEN_FILE.read_text().strip()
    return ""


def _ensure_file(remote_path: str, hf_repo: str, filename: str,
                 expected_mb: int, is_gated: bool, dry_run: bool,
                 label: str) -> None:
    if dry_run:
        print(f"  [dry-run] would ensure {remote_path}")
        return

    r = ssh(f"test -s {remote_path} && du -m {remote_path} | cut -f1 || echo missing",
            check=False)
    if r.stdout.strip() != "missing":
        size_mb = int(r.stdout.strip())
        print(f"  ✓ {label} already on device ({size_mb} MB)")
        return

    if not hf_repo:
        # Text model marked as on-device but file missing — abort
        _die(f"{label} not found at {remote_path} and no download repo set "
             f"(should already be on device from a prior campaign).")

    token = _hf_token() if is_gated else ""
    url = (f"https://huggingface.co/{hf_repo}/resolve/main/{filename}"
           f"?download=true")
    size_hint = f" (~{expected_mb} MB)" if expected_mb > 0 else ""
    print(f"  ↓ downloading {label}{size_hint} …")
    auth_flag = f'--header="Authorization: Bearer {token}"' if token else ""
    ssh(f"wget -c {auth_flag} -O {remote_path} '{url}'", capture=False, timeout=7200)
    print(f"  ✓ downloaded {label}")


def ensure_model(spec: ModelSpec, dry_run: bool) -> tuple[str, str]:
    """Download (if needed) text model and mmproj. Returns (text_path, mmproj_path)."""
    text_path   = f"{MODELS_DIR}/{spec.gguf_file}"
    mmproj_path = f"{MODELS_DIR}/{spec.mmproj_file}"

    _ensure_file(text_path, spec.hf_repo_text, spec.gguf_file,
                 spec.expected_mb_text, spec.is_gated, dry_run, "text model")
    _ensure_file(mmproj_path, spec.hf_repo_mmproj, spec.mmproj_file,
                 spec.expected_mb_mmproj, spec.is_gated, dry_run, "mmproj")
    return text_path, mmproj_path


def sha256_file(remote_path: str, dry_run: bool) -> str:
    if dry_run:
        return "dry-run"
    r = ssh(f"sha256sum {remote_path}")
    return r.stdout.split()[0]


# ── HTTP client helpers ───────────────────────────────────────────────────────

def _img_mime(path: Path) -> str:
    return "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"


def _img_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _build_payload(img_b64: str, mime: str) -> bytes:
    return json.dumps({
        "model": "vlm",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                {"type": "text", "text": PROMPT},
            ]
        }],
        "max_tokens": N_OUTPUT_TOKENS,
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
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        if not content.strip():
            # Thinking models (Gemma-4) put chain-of-thought in reasoning_content;
            # content stays empty until thinking completes. Surface whatever we have.
            reasoning = msg.get("reasoning_content") or ""
            if reasoning:
                return f"[thinking-only: {reasoning[:120]}…]"
        return content
    except Exception:
        return "(parse error)"


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


# ── benchmark execution ───────────────────────────────────────────────────────

def run_unit(spec: ModelSpec, text_path: str, mmproj_path: str,
             dry_run: bool, raw_dir: Path
             ) -> tuple[list[VLMFrameTimings], list[str], TegrastatsSummary,
                        str, int, bool]:
    """
    Measure per-frame VLM latency for one model.

    Returns:
        timings        — N_FRAMES VLMFrameTimings (measurement frames only, post-warmup)
        capability_log — one response string per measurement frame
        tegra          — tegrastats summary
        server_log     — raw server -v log (for image-token probe)
        load_s         — seconds from server start to first /health ok
        load_failed    — True if server never became healthy (OOM or crash)
    """
    tag = f"vlm{spec.unit_id}"
    tegra_remote  = f"/tmp/{tag}_tegra.log"
    server_log_remote = f"/tmp/{tag}_server.log"

    if dry_run:
        extra = f" {spec.server_extra_args}" if spec.server_extra_args else ""
        server_cmd = (
            _ld_prefix() +
            f"{LLAMA_SERVER} -m {text_path} --mmproj {mmproj_path} "
            f"-ngl {NGL} --port {SERVER_PORT} -v{extra} "
            f"> {server_log_remote} 2>&1"
        )
        print(f"  [dry-run] server: {server_cmd}")
        print(f"  [dry-run] would send 1 warmup + {N_FRAMES} measurement frames")
        return [], [], TegrastatsSummary(), "", 0, False

    # ── tegrastats ────────────────────────────────────────────────────────
    ssh("pkill tegrastats || true", check=False)
    time.sleep(1)
    ssh_bg(f"tegrastats --interval 1000 --logfile {tegra_remote}")
    time.sleep(5)  # idle baseline

    # ── start server ──────────────────────────────────────────────────────
    extra = f" {spec.server_extra_args}" if spec.server_extra_args else ""
    server_cmd = (
        _ld_prefix() +
        f"{LLAMA_SERVER} -m {text_path} --mmproj {mmproj_path} "
        f"-ngl {NGL} --port {SERVER_PORT} -v{extra} "
        f"> {server_log_remote} 2>&1"
    )
    ssh_bg(server_cmd)
    server_start_t = time.time()

    # ── open SSH port-forward (local 8080 → Jetson 8080) ─────────────────
    pf = subprocess.Popen(
        ["ssh", "-N", "-L", f"{SERVER_PORT}:localhost:{SERVER_PORT}", JETSON_HOST],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    load_failed   = False
    load_s        = 0
    timings_list: list[VLMFrameTimings] = []
    capability_log: list[str] = []

    try:
        print(f"  ⏳ waiting for server health (up to {SERVER_HEALTH_TIMEOUT_S}s) …")
        healthy = _wait_health(SERVER_HEALTH_TIMEOUT_S)
        load_s = int(time.time() - server_start_t)

        if not healthy:
            print(f"  ✗ server did not become healthy after {load_s}s — likely OOM")
            load_failed = True
        else:
            print(f"  ✓ server healthy in {load_s}s")

            # ── warmup (throwaway, any image) ─────────────────────────────
            print("  → warmup frame …")
            warmup_img = TEST_IMAGES[0]
            try:
                _post(_build_payload(_img_b64(warmup_img), _img_mime(warmup_img)))
                print("  ✓ warmup done — CUDA graphs compiled")
            except Exception as e:
                print(f"  ⚠  warmup failed: {e}")

            # ── measurement frames ────────────────────────────────────────
            for i in range(N_FRAMES):
                img_path = TEST_IMAGES[i % len(TEST_IMAGES)]
                print(f"  → frame {i+1}/{N_FRAMES} ({img_path.name}) …")
                t0 = time.time()
                try:
                    resp_text = _post(
                        _build_payload(_img_b64(img_path), _img_mime(img_path))
                    )
                except Exception as e:
                    print(f"     ⚠  request failed: {e}")
                    continue
                wall_ms = (time.time() - t0) * 1000
                t = parse_vlm_server_timings(resp_text)
                cap = _response_text(resp_text)
                capability_log.append(f"[{img_path.name}] {cap}")
                if t:
                    timings_list.append(t)
                    print(f"     per_frame_ms={t.per_frame_ms:.0f}  "
                          f"(prompt={t.prompt_ms:.0f} + decode={t.predicted_ms:.0f})  "
                          f"wall={wall_ms:.0f}ms  hz={t.per_frame_hz:.2f}")
                else:
                    print(f"     ⚠  timings parse failed; wall={wall_ms:.0f}ms")
                    print(f"     response: {resp_text[:200]}")

    finally:
        # always clean up server and tunnel
        ssh("pkill -f llama-server || true", check=False)
        time.sleep(2)
        pf.terminate()
        try:
            pf.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pf.kill()

    # ── stop tegrastats + pull logs ───────────────────────────────────────
    time.sleep(1)
    ssh("pkill tegrastats || true", check=False)
    time.sleep(1)

    server_log_local = raw_dir / f"{DATE}_{tag}_server.log"
    tegra_local      = raw_dir / f"{DATE}_{tag}_tegra.log"
    cap_local        = raw_dir / f"{DATE}_{tag}_capability.txt"

    try:
        scp_get(server_log_remote, server_log_local)
        server_log = server_log_local.read_text()
    except Exception as e:
        print(f"  ⚠  could not pull server log: {e}")
        server_log = ""

    try:
        scp_get(tegra_remote, tegra_local)
        tegra_text = tegra_local.read_text()
    except Exception as e:
        print(f"  ⚠  could not pull tegrastats log: {e}")
        tegra_text = ""

    if capability_log:
        cap_local.write_text("\n".join(capability_log))

    return timings_list, capability_log, parse_tegrastats(tegra_text), \
           server_log, load_s, load_failed


# ── server-log parsing helper ─────────────────────────────────────────────────

def _image_tokens_from_server_log(log: str) -> int:
    """Return the largest n_tokens_batch seen in a server -v log.

    This is a proxy for image token count: the image patch tokens form one large
    batch, much bigger than the small text-token batch. Returns 0 if not found.
    """
    matches = re.findall(r"n_tokens_batch\s*=\s*(\d+)", log)
    if not matches:
        return 0
    return max(int(m) for m in matches)


# ── result formatting ─────────────────────────────────────────────────────────

def _med_std(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    if len(vals) == 1:
        return vals[0], 0.0
    return statistics.median(vals), statistics.stdev(vals)


def format_result_block(
    spec: ModelSpec,
    sha_text: str,
    sha_mmproj: str,
    timings: list[VLMFrameTimings],
    capability_log: list[str],
    tegra: TegrastatsSummary,
    server_log: str,
    load_s: int,
    run_ts: str,
    actual_commit: str,
    load_failed: bool,
) -> str:
    header = (
        f"### Unit {spec.unit_id} — {spec.name} {spec.quant}"
    )
    run_line = (
        f"**Run:** {run_ts} UTC · 15 W locked · llama.cpp `{actual_commit}` CUDA sm_87  \n"
        f"**Params:** {spec.params_b}B"
        + (f"  \n**Note:** {spec.notes}" if spec.notes else "")
    )

    if load_failed:
        return textwrap.dedent(f"""\
        {header} (**FAILED TO LOAD**)

        {run_line}

        | Metric | Value |
        |---|---|
        | text SHA256 | `{sha_text}` |
        | mmproj SHA256 | `{sha_mmproj}` |
        | Load result | **OOM / server never healthy — model did not run** |
        | Peak RAM at failure | {tegra.peak_ram_mb:.0f} MB / 7607 MB |
        | Swap hit | {'YES ⚠' if tegra.swap_hit else 'no'} |
        | Peak SoC temp | {tegra.peak_temp_c:.1f} °C |

        > **Negative result.** Documented as thesis content.

        """)

    pf_vals  = [t.per_frame_ms  for t in timings]
    prom_vals = [t.prompt_ms    for t in timings]
    pred_vals = [t.predicted_ms for t in timings]

    pf_med,   pf_std   = _med_std(pf_vals)
    prom_med, prom_std = _med_std(prom_vals)
    pred_med, pred_std = _med_std(pred_vals)
    hz = 1000.0 / pf_med if pf_med > 0 else 0.0

    img_tokens = _image_tokens_from_server_log(server_log)
    prompt_n   = int(statistics.median([t.prompt_n for t in timings])) if timings else 0
    predicted_n = int(statistics.median([t.predicted_n for t in timings])) if timings else 0

    idle_w  = tegra.idle_w
    mean_w  = tegra.mean_w
    peak_w  = tegra.peak_w
    peak_t  = tegra.peak_temp_c
    peak_ram = tegra.peak_ram_mb
    swap     = "YES ⚠" if tegra.swap_hit else "no"

    cap_block = ""
    if capability_log:
        cap_lines = "\n".join(f"  - {line}" for line in capability_log)
        cap_block = f"\n**Capability samples (N=5 frames):**\n{cap_lines}\n"

    return textwrap.dedent(f"""\
    {header}

    {run_line}

    | Metric | Value |
    |---|---|
    | text SHA256 | `{sha_text}` |
    | mmproj SHA256 | `{sha_mmproj}` |
    | Server load time | {load_s} s to /health ok |
    | **per_frame_ms** (median ± σ, N={len(timings)}) | **{pf_med:.0f} ± {pf_std:.0f} ms** |
    | **per_frame_hz** | **{hz:.2f} Hz** |
    | prompt_ms (CLIP + prefill) | {prom_med:.0f} ± {prom_std:.0f} ms |
    | predicted_ms (decode) | {pred_med:.0f} ± {pred_std:.0f} ms |
    | prompt_n (image + text tokens) | {prompt_n} |
    | predicted_n (output tokens, median) | {predicted_n} |
    | image_tokens (server log proxy) | {img_tokens if img_tokens else '—'} |
    | Peak RAM | {peak_ram:.0f} MB / 7607 MB |
    | Swap hit | {swap} |
    | Power — idle | {idle_w:.2f} W |
    | Power — mean (active) | {mean_w:.2f} W |
    | Power — peak | {peak_w:.2f} W |
    | Peak SoC temp | {peak_t:.1f} °C |
    {cap_block}
    """)


def results_md_row(spec: ModelSpec, timings: list[VLMFrameTimings],
                   tegra: TegrastatsSummary, server_log: str,
                   run_ts: str, load_failed: bool) -> str:
    if load_failed:
        return (
            f"| {run_ts[:10]} | {spec.unit_id} | {spec.name} {spec.quant} "
            f"| {spec.params_b}B | 15W locked vlm-server | **FAILED** "
            f"| — | — | — | {tegra.peak_ram_mb:.0f}MB OOM |"
        )
    pf_vals = [t.per_frame_ms for t in timings]
    pf_med, _ = _med_std(pf_vals)
    hz = 1000.0 / pf_med if pf_med > 0 else 0.0
    img_tokens = _image_tokens_from_server_log(server_log)
    return (
        f"| {run_ts[:10]} | {spec.unit_id} | {spec.name} {spec.quant} "
        f"| {spec.params_b}B | 15W locked vlm-server "
        f"| per_frame={pf_med:.0f}ms | {hz:.2f}Hz "
        f"| img_tok={img_tokens} "
        f"| {tegra.mean_w:.1f}W mean | {tegra.peak_ram_mb:.0f}MB "
        f"| {'swap' if tegra.swap_hit else ''} |"
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only",          help="comma-separated unit IDs, e.g. V1,V3")
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--start-from",   help="skip units before this ID, e.g. V3")
    args = parser.parse_args()

    only_ids   = set(args.only.split(",")) if args.only else None
    start_from = args.start_from or "V1"

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("═" * 65)
    print("  Jetson Orin Nano — VLM feasibility campaign")
    print(f"  Campaign: {CAMPAIGN_ID}")
    print("═" * 65)
    print()

    actual_commit = check_preconditions(args.dry_run)

    for spec in MODELS:
        if only_ids and spec.unit_id not in only_ids:
            continue
        if spec.unit_id < start_from:
            continue

        print(f"── Unit {spec.unit_id}: {spec.name} {spec.quant} ({spec.params_b}B) ──")
        if spec.notes:
            print(f"  ℹ  {spec.notes}")

        run_ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M")

        if args.skip_download:
            text_path   = f"{MODELS_DIR}/{spec.gguf_file}"
            mmproj_path = f"{MODELS_DIR}/{spec.mmproj_file}"
        else:
            text_path, mmproj_path = ensure_model(spec, args.dry_run)

        sha_text   = sha256_file(text_path,   args.dry_run)
        sha_mmproj = sha256_file(mmproj_path, args.dry_run)
        print(f"  SHA256 text:   {sha_text[:16]}…")
        print(f"  SHA256 mmproj: {sha_mmproj[:16]}…")

        timings, cap_log, tegra, server_log, load_s, load_failed = run_unit(
            spec, text_path, mmproj_path, args.dry_run, RAW_DIR
        )

        if not args.dry_run and CAMPAIGN_MD.exists():
            block = format_result_block(
                spec, sha_text, sha_mmproj, timings, cap_log, tegra,
                server_log, load_s, run_ts, actual_commit, load_failed,
            )
            content = CAMPAIGN_MD.read_text()
            placeholder = "*(to be filled in post-run)*"
            content = content.replace(placeholder, "", 1)
            marker = "### Summary table"
            if marker in content:
                content = content.replace(marker, block + "\n" + marker, 1)
            else:
                content = content.rstrip("\n") + "\n\n" + block
            CAMPAIGN_MD.write_text(content)

        if not args.dry_run:
            row = results_md_row(spec, timings, tegra, server_log, run_ts, load_failed)
            with RESULTS_MD.open("a") as f:
                f.write(row + "\n")

        if not load_failed and timings:
            pf_vals = [t.per_frame_ms for t in timings]
            pf_med, pf_std = _med_std(pf_vals)
            hz = 1000.0 / pf_med if pf_med > 0 else 0.0
            print(f"  ✓ per_frame={pf_med:.0f}±{pf_std:.0f}ms  "
                  f"hz={hz:.2f}  "
                  f"RAM={tegra.peak_ram_mb:.0f}MB  "
                  f"mean={tegra.mean_w:.1f}W")
        elif load_failed:
            print(f"  ✗ load failed — RAM={tegra.peak_ram_mb:.0f}MB  "
                  f"swap={'YES' if tegra.swap_hit else 'no'}")

        print()

    print("═" * 65)
    print("  VLM feasibility campaign complete.")
    if not args.dry_run:
        print(f"  Results in {CAMPAIGN_MD.relative_to(REPO_ROOT)}")
        print(f"  Summary rows appended to RESULTS.md")
    print("═" * 65)


if __name__ == "__main__":
    main()
