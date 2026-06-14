#!/usr/bin/env python3
"""
run_campaign.py — 10-model capability sweep on the Jetson Orin Nano 8 GB.

Run from the repo root:
    python experiments/run_campaign.py

Prerequisites (run once on the Jetson before starting):
    ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'

Options:
    --only 01,03,05    run only these unit IDs (comma-separated)
    --dry-run          print what would run without executing anything
    --skip-download    assume models already exist on device
    --start-from 05    skip units before this ID
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import re
import shlex
import statistics
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from parsers import (
    parse_bench_csv, parse_tegrastats, parse_llama_cli_timings,
    TegrastatsSummary, BenchRow,
)

# ── constants ────────────────────────────────────────────────────────────────

JETSON_HOST = "jetson"
LLAMA_BENCH      = "~/llama.cpp/build/bin/llama-bench"
LLAMA_CLI        = "~/llama.cpp/build/bin/llama-cli"
LLAMA_COMPLETION = "~/llama.cpp/build/bin/llama-completion"
LLAMA_LD    = "~/llama.cpp/build/bin:/usr/local/cuda/lib64"
MODELS_DIR  = "~/models"
EXPECTED_COMMIT = "57fe1f0"

NGL       = 99
N_CTX     = 4096
N_BATCH   = 512
PP_REPS   = 5
TG_REPS   = 3
TTFT_PROMPT = "Explain what an edge AI accelerator is in two sentences."

REPO_ROOT   = Path(__file__).parent.parent
RESULTS_DIR = REPO_ROOT / "results"
RAW_DIR     = RESULTS_DIR / "raw"
RESULTS_MD  = REPO_ROOT / "RESULTS.md"
CAMPAIGN_MD = RESULTS_DIR / "2026-06-13-model-capability-sweep.md"
CAMPAIGN_ID = "2026-06-13-model-capability-sweep"
DATE        = "2026-06-13"


# ── model catalogue ──────────────────────────────────────────────────────────

@dataclass
class ModelSpec:
    unit_id: str      # "01"
    name: str         # "Qwen2.5-0.5B-Instruct"
    params_b: float
    family: str
    tier: str
    gguf_file: str    # filename on device / HF
    hf_repo: str      # "" means already on device
    expected_mb: int


MODELS: list[ModelSpec] = [
    ModelSpec("01", "Qwen2.5-0.5B-Instruct",   0.5,  "Qwen2.5",  "A ultralight",
              "Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
              "bartowski/Qwen2.5-0.5B-Instruct-GGUF", 397),

    ModelSpec("02", "Llama-3.2-1B-Instruct",    1.0,  "Llama-3.2","A ultralight",
              "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
              "bartowski/Llama-3.2-1B-Instruct-GGUF", 770),

    ModelSpec("03", "Qwen2.5-1.5B-Instruct",    1.5,  "Qwen2.5",  "A light",
              "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
              "bartowski/Qwen2.5-1.5B-Instruct-GGUF", 940),

    ModelSpec("04", "gemma-2-2b-it",             2.6,  "Gemma-2",  "B sweet-spot",
              "gemma-2-2b-it-Q4_K_M.gguf",
              "bartowski/gemma-2-2b-it-GGUF", 1629),

    ModelSpec("05", "Qwen2.5-3B-Instruct",       3.0,  "Qwen2.5",  "B sweet-spot",
              "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
              "bartowski/Qwen2.5-3B-Instruct-GGUF", 1840),

    ModelSpec("06", "Llama-3.2-3B-Instruct",     3.0,  "Llama-3.2","B sweet-spot",
              "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
              "", 2019),   # already on device from baseline campaign

    ModelSpec("07", "Phi-3.5-mini-instruct",      3.8,  "Phi-3.5",  "B sweet-spot",
              "Phi-3.5-mini-instruct-Q4_K_M.gguf",
              "bartowski/Phi-3.5-mini-instruct-GGUF", 2282),

    ModelSpec("08", "Mistral-7B-Instruct-v0.3",   7.2,  "Mistral",  "C heavy",
              "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
              "bartowski/Mistral-7B-Instruct-v0.3-GGUF", 4170),

    ModelSpec("09", "Qwen2.5-7B-Instruct",        7.6,  "Qwen2.5",  "C heavy",
              "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
              "bartowski/Qwen2.5-7B-Instruct-GGUF", 4466),

    ModelSpec("10", "Meta-Llama-3.1-8B-Instruct", 8.0,  "Llama-3.1","C heavy",
              "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
              "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", 4692),
]


# ── SSH helpers ──────────────────────────────────────────────────────────────

def ssh(cmd: str, capture: bool = True, check: bool = True,
        timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a shell command on the Jetson via SSH."""
    full = ["ssh", JETSON_HOST, cmd]
    if capture:
        return subprocess.run(full, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL,
                              timeout=timeout, check=check)
    else:
        return subprocess.run(full, stdin=subprocess.DEVNULL,
                              timeout=timeout, check=check)


def scp_get(remote: str, local: Path) -> None:
    """Copy a file from the Jetson to a local path."""
    subprocess.run(["scp", f"{JETSON_HOST}:{remote}", str(local)],
                   check=True, timeout=120)


def ssh_bg(cmd: str) -> None:
    """Start a command on the Jetson in the background (fire-and-forget)."""
    wrapped = f"nohup sh -c {repr(cmd)} </dev/null >/dev/null 2>&1 &"
    subprocess.run(["ssh", JETSON_HOST, wrapped], check=True, timeout=30)


# ── preflight checks ─────────────────────────────────────────────────────────

def check_preconditions(dry_run: bool) -> None:
    print("── preflight checks ──────────────────────────────────────────")

    if dry_run:
        print("  [dry-run] skipping preflight")
        return

    # 1. SSH reachable
    try:
        ssh("true")
        print("  ✓ ssh jetson")
    except Exception as e:
        _die(f"SSH to '{JETSON_HOST}' failed: {e}")

    # 2. llama-bench binary at expected path
    r = ssh(f"test -x {LLAMA_BENCH} && echo ok || echo missing", check=False)
    if "ok" not in r.stdout:
        _die(f"llama-bench not found at {LLAMA_BENCH}. "
             "Build llama.cpp on the device first (see DECISIONS.md).")
    print(f"  ✓ {LLAMA_BENCH} present")

    # 3. llama.cpp commit
    r = ssh(f"git -C ~/llama.cpp rev-parse --short HEAD 2>/dev/null || echo unknown",
            check=False)
    commit = r.stdout.strip()
    if commit != EXPECTED_COMMIT:
        print(f"  ⚠  llama.cpp commit is {commit!r}, expected {EXPECTED_COMMIT!r} "
              f"— results may differ from baseline")
    else:
        print(f"  ✓ llama.cpp @ {commit}")

    # 4. power mode
    r = ssh("nvpmodel -q 2>/dev/null | head -3", check=False)
    print(f"  ℹ  nvpmodel: {r.stdout.strip()!r}")
    print("  ⚠  Ensure you ran: ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'")

    # 5. disk space
    r = ssh("df -BM --output=avail / | tail -1", check=False)
    avail_mb = int(r.stdout.strip().rstrip("M"))
    if avail_mb < 6000:
        print(f"  ⚠  only {avail_mb} MB free on / — may not fit all models")
    else:
        print(f"  ✓ {avail_mb} MB free")

    # 6. models dir
    ssh(f"mkdir -p {MODELS_DIR}")
    print(f"  ✓ {MODELS_DIR} exists")

    print()


def _die(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ── model acquisition ─────────────────────────────────────────────────────────

def ensure_model(spec: ModelSpec, dry_run: bool) -> str:
    """Return the remote model path; download if needed."""
    remote_path = f"{MODELS_DIR}/{spec.gguf_file}"

    if dry_run:
        print(f"  [dry-run] would ensure {remote_path}")
        return remote_path

    # check if already present and non-empty
    r = ssh(f"test -s {remote_path} && du -m {remote_path} | cut -f1 || echo missing",
            check=False)
    if r.stdout.strip() != "missing":
        size_mb = int(r.stdout.strip())
        print(f"  ✓ model already on device ({size_mb} MB) — skipping download")
        return remote_path

    if not spec.hf_repo:
        _die(f"Model {spec.name} is marked as local-only but not found at {remote_path}. "
             "Copy it to the device manually.")

    url = (f"https://huggingface.co/{spec.hf_repo}/resolve/main/{spec.gguf_file}"
           f"?download=true")
    print(f"  ↓ downloading {spec.name} (~{spec.expected_mb} MB) …")
    # wget -c = resume partial; -q = quiet progress to stdout won't spam logs
    ssh(f"wget -c -O {remote_path} '{url}'", capture=False,
        timeout=3600)  # up to 1 h for large models
    print(f"  ✓ downloaded")
    return remote_path


def sha256_model(remote_path: str, dry_run: bool) -> str:
    if dry_run:
        return "dry-run"
    r = ssh(f"sha256sum {remote_path}")
    return r.stdout.split()[0]


# ── benchmark execution ───────────────────────────────────────────────────────

def _ld_prefix() -> str:
    return f"export LD_LIBRARY_PATH={LLAMA_LD}; "


def run_unit(spec: ModelSpec, remote_path: str, dry_run: bool,
             raw_dir: Path) -> tuple[str, str, str]:
    """
    Run the full benchmark protocol for one model.
    Returns (bench_csv_text, ttft_text, tegra_log_text).
    """
    tag = f"msweep{spec.unit_id}"

    # ── start tegrastats ──────────────────────────────────────────────────
    tegra_remote = f"/tmp/{tag}_tegra.log"
    if not dry_run:
        ssh("pkill tegrastats || true", check=False)
        time.sleep(1)
        ssh_bg(f"tegrastats --interval 1000 --logfile {tegra_remote}")
        time.sleep(5)   # collect a few idle readings

    # ── throughput: pp512 + tg128, PP_REPS repeats ───────────────────────
    bench_cmd = (
        _ld_prefix() +
        f"{LLAMA_BENCH} -m {remote_path} -ngl {NGL} "
        f"-p 512 -n 128 -r {PP_REPS} -o csv"
    )
    print(f"  → llama-bench pp512+tg128 ×{PP_REPS} …")
    if dry_run:
        bench_csv = ""
    else:
        r = ssh(bench_cmd, timeout=900)
        bench_csv = r.stdout
        bench_raw = raw_dir / f"{DATE}_{tag}_bench.csv"
        bench_raw.write_text(bench_csv)

    # ── sustained decode: tg512, TG_REPS repeats ─────────────────────────
    sustained_cmd = (
        _ld_prefix() +
        f"{LLAMA_BENCH} -m {remote_path} -ngl {NGL} "
        f"-n 512 -r {TG_REPS} -o csv"
    )
    print(f"  → llama-bench tg512 ×{TG_REPS} …")
    if dry_run:
        sustained_csv = ""
    else:
        r = ssh(sustained_cmd, timeout=900)
        sustained_csv = r.stdout
        sust_raw = raw_dir / f"{DATE}_{tag}_sustained.csv"
        sust_raw.write_text(sustained_csv)
        # merge sustained into bench_csv for convenience
        # (skip the header on sustained_csv)
        lines = sustained_csv.splitlines()
        data_lines = [l for l in lines if not l.startswith("build") and l.strip()]
        bench_csv = bench_csv.rstrip("\n") + "\n" + "\n".join(data_lines)

    # ── TTFT: single generation, read timings block ───────────────────────
    ttft_cmd = (
        _ld_prefix() +
        f"{LLAMA_COMPLETION} -m {remote_path} -ngl {NGL} -c {N_CTX} -n 128 "
        f"-no-cnv -p {shlex.quote(TTFT_PROMPT)} </dev/null 2>&1"
    )
    print(f"  → llama-cli TTFT …")
    if dry_run:
        ttft_text = ""
    else:
        r = ssh(ttft_cmd, timeout=600)
        ttft_text = r.stdout
        ttft_raw = raw_dir / f"{DATE}_{tag}_ttft.txt"
        ttft_raw.write_text(ttft_text)

    # ── stop tegrastats + pull log ────────────────────────────────────────
    if not dry_run:
        time.sleep(2)
        ssh("pkill tegrastats || true", check=False)
        time.sleep(1)
        tegra_local = raw_dir / f"{DATE}_{tag}_tegra.log"
        try:
            scp_get(tegra_remote, tegra_local)
            tegra_text = tegra_local.read_text()
        except Exception as e:
            print(f"  ⚠  could not pull tegrastats log: {e}")
            tegra_text = ""
    else:
        tegra_text = ""

    return bench_csv, ttft_text, tegra_text


# ── result formatting ─────────────────────────────────────────────────────────

def _med_stddev(rows: list[BenchRow], test_prefix: str) -> tuple[float, float]:
    """Return (median, std) of avg_ts for rows whose test starts with test_prefix.

    When llama-bench outputs a single aggregated row (new default with -r N),
    avg_ts/stddev_ts in that row already represent the across-rep statistics,
    so we use them directly rather than computing cross-row stdev (which is 0).
    """
    matched = [r for r in rows if r.test.startswith(test_prefix)]
    if not matched:
        return 0.0, 0.0
    if len(matched) == 1:
        return matched[0].avg_ts, matched[0].stddev_ts
    vals = [r.avg_ts for r in matched]
    med = statistics.median(vals)
    std = statistics.stdev(vals)
    return med, std


def format_result_block(
    spec: ModelSpec,
    sha256: str,
    bench_csv: str,
    ttft_text: str,
    tegra: TegrastatsSummary,
    run_ts: str,
) -> str:
    """Return a Markdown subsection for the campaign result doc."""

    bench_rows = parse_bench_csv(bench_csv) if bench_csv else []
    pp_med, pp_std  = _med_stddev(bench_rows, "pp")
    tg_med, tg_std  = _med_stddev(bench_rows, "tg1")   # tg128
    tg512_med, _    = _med_stddev(bench_rows, "tg5")    # tg512

    timings = parse_llama_cli_timings(ttft_text) if ttft_text else None
    ttft_ms  = timings.ttft_ms if timings else float("nan")

    idle_w  = tegra.idle_w
    mean_w  = tegra.mean_w
    peak_w  = tegra.peak_w
    peak_t  = tegra.peak_temp_c
    peak_ram = tegra.peak_ram_mb
    swap    = "YES ⚠" if tegra.swap_hit else "no"

    tg_per_w = tg_med / peak_w if peak_w > 0 else float("nan")
    j_per_tok = peak_w / tg_med if tg_med > 0 else float("nan")
    net_w = peak_w - idle_w
    tg_per_w_net = tg_med / net_w if net_w > 0 else float("nan")

    return textwrap.dedent(f"""\
    ### Unit {spec.unit_id} — {spec.name} Q4_K_M

    **Run:** {run_ts} UTC · 15 W locked · llama.cpp `{EXPECTED_COMMIT}` CUDA sm_87

    | Metric | Value |
    |---|---|
    | SHA256 | `{sha256}` |
    | Prefill pp512 (median ± σ, ×{PP_REPS}) | **{pp_med:.1f} ± {pp_std:.2f} tok/s** |
    | Decode tg128 (median ± σ, ×{PP_REPS}) | **{tg_med:.2f} ± {tg_std:.3f} tok/s** |
    | Decode tg512 sustained (×{TG_REPS}) | {tg512_med:.2f} tok/s |
    | TTFT (prompt eval, 512-tok prompt) | {ttft_ms:.0f} ms |
    | Peak RAM | {peak_ram:.0f} MB / 7607 MB |
    | Swap hit | {swap} |
    | Power — idle | {idle_w:.2f} W |
    | Power — mean (active window) | {mean_w:.2f} W |
    | Power — peak | {peak_w:.2f} W |
    | Peak SoC temp | {peak_t:.1f} °C |
    | tok/s per watt (total) | {tg_per_w:.2f} |
    | tok/s per watt (net of idle) | {tg_per_w_net:.2f} |
    | J/token (total) | {j_per_tok:.3f} |

    """)


def results_md_row(spec: ModelSpec, bench_csv: str, tegra: TegrastatsSummary,
                   run_ts: str) -> str:
    """Return one pipe-delimited row for RESULTS.md."""
    bench_rows = parse_bench_csv(bench_csv) if bench_csv else []
    pp_med, _   = _med_stddev(bench_rows, "pp")
    tg_med, _   = _med_stddev(bench_rows, "tg1")
    peak_w      = tegra.peak_w
    tg_per_w    = tg_med / peak_w if peak_w > 0 else float("nan")
    j_per_tok   = peak_w / tg_med if tg_med > 0 else float("nan")
    swap        = "swap" if tegra.swap_hit else ""
    return (
        f"| {run_ts[:10]} | {spec.unit_id} | {spec.name} Q4_K_M "
        f"| {spec.params_b}B | 15W locked | pp512={pp_med:.0f} "
        f"| tg128={tg_med:.2f} | {peak_w:.1f}W pk | {tg_per_w:.2f} | {j_per_tok:.3f} "
        f"| {tegra.peak_temp_c:.0f}°C | {tegra.peak_ram_mb:.0f}MB {swap} |"
    )


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only",        help="comma-separated unit IDs to run, e.g. 01,03")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--start-from",  help="skip units before this ID")
    args = parser.parse_args()

    only_ids = set(args.only.split(",")) if args.only else None
    start_from = args.start_from or "01"

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("═" * 65)
    print("  Jetson Orin Nano — 10-model capability sweep")
    print(f"  Campaign: {CAMPAIGN_ID}")
    print("═" * 65)
    print()

    check_preconditions(args.dry_run)

    # ensure campaign doc has a ## Results heading
    if not args.dry_run and CAMPAIGN_MD.exists():
        content = CAMPAIGN_MD.read_text()
        if "## Results" not in content:
            CAMPAIGN_MD.write_text(content.rstrip("\n") + "\n\n## Results\n\n")

    for spec in MODELS:
        if only_ids and spec.unit_id not in only_ids:
            continue
        if spec.unit_id < start_from:
            continue

        print(f"── Unit {spec.unit_id}: {spec.name} ({spec.params_b}B, {spec.tier}) ──")

        run_ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M")

        # acquire model
        if args.skip_download or not spec.hf_repo:
            remote_path = f"{MODELS_DIR}/{spec.gguf_file}"
        else:
            remote_path = ensure_model(spec, args.dry_run)

        sha = sha256_model(remote_path, args.dry_run)
        print(f"  SHA256: {sha[:16]}…")

        # run benchmarks
        bench_csv, ttft_text, tegra_text = run_unit(
            spec, remote_path, args.dry_run, RAW_DIR
        )

        # parse
        tegra = parse_tegrastats(tegra_text)

        # write result block into campaign doc
        if not args.dry_run and CAMPAIGN_MD.exists():
            block = format_result_block(spec, sha, bench_csv, ttft_text, tegra, run_ts)
            with CAMPAIGN_MD.open("a") as f:
                f.write(block)

        # append row to RESULTS.md
        if not args.dry_run:
            row = results_md_row(spec, bench_csv, tegra, run_ts)
            with RESULTS_MD.open("a") as f:
                f.write(row + "\n")

        pp_rows = parse_bench_csv(bench_csv) if bench_csv else []
        pp_med, _ = _med_stddev(pp_rows, "pp")
        tg_med, _ = _med_stddev(pp_rows, "tg1")
        print(f"  ✓ done — pp512={pp_med:.0f} tok/s  tg128={tg_med:.2f} tok/s"
              f"  peak={tegra.peak_w:.1f}W  temp={tegra.peak_temp_c:.0f}°C")
        print()

    print("═" * 65)
    print("  Sweep complete. Results in:")
    print(f"    {CAMPAIGN_MD}")
    print(f"    {RESULTS_MD}")
    print(f"    {RAW_DIR}/")
    print("═" * 65)


if __name__ == "__main__":
    main()
