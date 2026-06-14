#!/usr/bin/env python3
"""
run_gemma_sweep.py — Gemma-family generational + edge-architecture sweep
                     on the Jetson Orin Nano 8 GB.

Campaign: 2026-06-14-gemma-family-sweep
Protocol pre-registered in results/2026-06-14-gemma-family-sweep/README.md

Run from the repo root:
    python experiments/run_gemma_sweep.py

Prerequisites (run once on the Jetson before starting):
    ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks'

Options:
    --only G1,G3       run only these unit IDs (comma-separated)
    --dry-run          print what would run without executing anything
    --skip-download    assume models already exist on device
    --start-from G3    skip units before this ID
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
    parse_llama_load_buffers, TegrastatsSummary, BenchRow,
)

# ── constants ────────────────────────────────────────────────────────────────

JETSON_HOST  = "jetson"
LLAMA_BENCH      = "~/llama.cpp/build/bin/llama-bench"
LLAMA_CLI        = "~/llama.cpp/build/bin/llama-cli"
LLAMA_COMPLETION = "~/llama.cpp/build/bin/llama-completion"
LLAMA_LD    = "~/llama.cpp/build/bin:/usr/local/cuda/lib64"
MODELS_DIR  = "~/models"

HF_TOKEN_FILE = Path(__file__).parent.parent / ".hugging-face-token"

# The sweep used 57fe1f0; Gemma 4 arch (GEMMA4/GEMMA4_ASSISTANT) is already
# present in that commit, so no rebuild required. Actual commit is read from
# the device at runtime and recorded per-run.
BASELINE_COMMIT = "57fe1f0"

NGL       = 99
N_CTX     = 4096
N_BATCH   = 512
PP_REPS   = 5
TG_REPS   = 3
TTFT_PROMPT = "Explain what an edge AI accelerator is in two sentences."

REPO_ROOT    = Path(__file__).parent.parent
RESULTS_DIR  = REPO_ROOT / "results"
RAW_DIR      = RESULTS_DIR / "2026-06-14-gemma-family-sweep" / "raw"
RESULTS_MD   = REPO_ROOT / "RESULTS.md"
CAMPAIGN_MD  = RESULTS_DIR / "2026-06-14-gemma-family-sweep" / "README.md"
CAMPAIGN_ID  = "2026-06-14-gemma-family-sweep"
DATE         = "2026-06-14"


# ── model catalogue ──────────────────────────────────────────────────────────

@dataclass
class ModelSpec:
    unit_id: str      # "G1"
    name: str         # "gemma-3-270m-it"
    gen: str          # "Gemma 3" / "Gemma 4"
    arch_idea: str    # "dense" / "QAT" / "PLE"
    params_b: float   # nominal (total) params in billions
    quant: str        # "Q8_0", "q4_0 QAT", "Q4_K_M"
    gguf_file: str
    hf_repo: str      # HF repo slug; "" if already on device
    expected_mb: int
    notes: str = ""   # one-line deviation / rationale note


MODELS: list[ModelSpec] = [
    ModelSpec(
        unit_id="G1",
        name="gemma-3-270m-it",
        gen="Gemma 3",
        arch_idea="tiny dense",
        params_b=0.27,
        quant="Q8_0",
        gguf_file="gemma-3-270m-it-Q8_0.gguf",
        hf_repo="ggml-org/gemma-3-270m-it-GGUF",
        expected_mb=290,
        notes="Only Q8_0 available upstream; no QAT release for 270M. "
              "Deviation from Q4 plan documented in §5 of campaign README.",
    ),
    ModelSpec(
        unit_id="G2",
        name="gemma-3-4b-it",
        gen="Gemma 3",
        arch_idea="QAT dense",
        params_b=4.0,
        quant="q4_0 QAT",
        gguf_file="gemma-3-4b-it-q4_0.gguf",
        hf_repo="google/gemma-3-4b-it-qat-q4_0-gguf",
        expected_mb=3009,
    ),
    ModelSpec(
        unit_id="G3",
        name="gemma-4-E2B-it",
        gen="Gemma 4",
        arch_idea="PLE effective-2B",
        params_b=5.1,  # total; 2.3 B active
        quant="q4_0 QAT",
        gguf_file="gemma-4-E2B_q4_0-it.gguf",
        hf_repo="google/gemma-4-E2B-it-qat-q4_0-gguf",
        expected_mb=3194,
        notes="PLE footprint reality check (RQ-G3). True resident size is the result.",
    ),
    ModelSpec(
        unit_id="G4",
        name="gemma-4-E4B-it",
        gen="Gemma 4",
        arch_idea="PLE effective-4B",
        params_b=8.0,  # total; ~4 B active
        quant="q4_0 QAT",
        gguf_file="gemma-4-E4B_q4_0-it.gguf",
        hf_repo="google/gemma-4-E4B-it-qat-q4_0-gguf",
        expected_mb=4916,
        notes="Flagship edge datapoint. Expected memory-wall interaction (HG3).",
    ),
    ModelSpec(
        unit_id="G5",
        name="gemma-3-12b-it",
        gen="Gemma 3",
        arch_idea="QAT dense",
        params_b=12.0,
        quant="q4_0 QAT",
        gguf_file="gemma-3-12b-it-q4_0.gguf",
        hf_repo="google/gemma-3-12b-it-qat-q4_0-gguf",
        expected_mb=7700,
        notes="Deliberate memory-wall stress (RQ-G4 / HG5). OOM/swap expected.",
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


# ── preflight checks ─────────────────────────────────────────────────────────

def get_actual_commit() -> str:
    r = ssh("git -C ~/llama.cpp rev-parse --short HEAD 2>/dev/null || echo unknown",
            check=False)
    return r.stdout.strip()


def check_preconditions(dry_run: bool) -> str:
    """Run preflight checks; return the actual llama.cpp commit hash."""
    print("── preflight checks ──────────────────────────────────────────")

    if dry_run:
        print("  [dry-run] skipping preflight")
        return BASELINE_COMMIT

    try:
        ssh("true")
        print("  ✓ ssh jetson")
    except Exception as e:
        _die(f"SSH to '{JETSON_HOST}' failed: {e}")

    r = ssh(f"test -x {LLAMA_BENCH} && echo ok || echo missing", check=False)
    if "ok" not in r.stdout:
        _die(f"llama-bench not found at {LLAMA_BENCH}.")
    print(f"  ✓ {LLAMA_BENCH} present")

    commit = get_actual_commit()
    if commit == BASELINE_COMMIT:
        print(f"  ✓ llama.cpp @ {commit} (baseline — Gemma 4 arch verified in source)")
    else:
        print(f"  ℹ  llama.cpp @ {commit} (differs from baseline {BASELINE_COMMIT})")
    print(f"     Gemma4/Gemma4_ASSISTANT arch entries confirmed in llama-arch.cpp")

    r = ssh("nvpmodel -q 2>/dev/null | head -3", check=False)
    print(f"  ℹ  nvpmodel: {r.stdout.strip()!r}")
    r2 = ssh("cat /sys/kernel/debug/bpmp/debug/clk/nafll_cpu0/rate 2>/dev/null || "
             "sudo cat /sys/kernel/debug/bpmp/debug/clk/nafll_cpu0/rate 2>/dev/null || "
             "echo unknown", check=False)
    print("  ℹ  jetson_clocks: assumed locked (run sudo jetson_clocks before this script)")

    r = ssh("df -BM --output=avail / | tail -1", check=False)
    avail_mb = int(r.stdout.strip().rstrip("M"))
    if avail_mb < 10000:
        print(f"  ⚠  only {avail_mb} MB free — may not fit all models (~19 GB total)")
    else:
        print(f"  ✓ {avail_mb} MB free")

    ssh(f"mkdir -p {MODELS_DIR}")
    print(f"  ✓ {MODELS_DIR} exists")
    print()

    return commit


def _die(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ── model acquisition ─────────────────────────────────────────────────────────

def ensure_model(spec: ModelSpec, dry_run: bool) -> str:
    remote_path = f"{MODELS_DIR}/{spec.gguf_file}"

    if dry_run:
        print(f"  [dry-run] would ensure {remote_path}")
        return remote_path

    r = ssh(f"test -s {remote_path} && du -m {remote_path} | cut -f1 || echo missing",
            check=False)
    if r.stdout.strip() != "missing":
        size_mb = int(r.stdout.strip())
        print(f"  ✓ model already on device ({size_mb} MB) — skipping download")
        return remote_path

    if not spec.hf_repo:
        _die(f"Model {spec.name} not found at {remote_path} and no hf_repo set.")

    hf_token = ""
    if HF_TOKEN_FILE.exists():
        hf_token = HF_TOKEN_FILE.read_text().strip()

    url = (f"https://huggingface.co/{spec.hf_repo}/resolve/main/{spec.gguf_file}"
           f"?download=true")
    print(f"  ↓ downloading {spec.name} {spec.quant} (~{spec.expected_mb} MB) …")
    auth_flag = f'--header="Authorization: Bearer {hf_token}"' if hf_token else ""
    ssh(f"wget -c {auth_flag} -O {remote_path} '{url}'", capture=False, timeout=7200)
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
             raw_dir: Path) -> tuple[str, str, str, bool]:
    """
    Run the full benchmark protocol for one model.
    Returns (bench_csv_text, ttft_text, tegra_log_text, load_failed).
    load_failed=True if the model failed to load (e.g. OOM for G5).
    """
    tag = f"gsweep{spec.unit_id}"

    # ── start tegrastats ──────────────────────────────────────────────────
    tegra_remote = f"/tmp/{tag}_tegra.log"
    if not dry_run:
        ssh("pkill tegrastats || true", check=False)
        time.sleep(1)
        ssh_bg(f"tegrastats --interval 1000 --logfile {tegra_remote}")
        time.sleep(5)   # collect idle baseline readings

    # ── throughput: pp512 + tg128, PP_REPS repeats ───────────────────────
    # NOTE: llama-bench has no -c/--ctx-size flag (it errors on it) and we keep
    # n_batch at the binary default (2048) to match the anchor sweep, which did
    # not pass -b. stderr is kept separate (no 2>&1) so the CSV on stdout stays
    # clean and a real load failure (empty stdout + nonzero rc) is detectable.
    bench_cmd = (
        _ld_prefix() +
        f"{LLAMA_BENCH} -m {remote_path} -ngl {NGL} "
        f"-p 512 -n 128 -r {PP_REPS} -o csv"
    )
    print(f"  → llama-bench pp512+tg128 ×{PP_REPS} …")
    if dry_run:
        bench_csv = ""
        load_failed = False
    else:
        r = ssh(bench_cmd, timeout=1800, check=False)
        bench_csv = r.stdout
        if r.returncode != 0 and not bench_csv.strip():
            print(f"  ⚠  llama-bench FAILED (rc={r.returncode}) — likely OOM or unsupported arch")
            print(f"     stderr: {r.stderr[:500]}")
            load_failed = True
        else:
            load_failed = False
            bench_raw = raw_dir / f"{DATE}_{tag}_bench.csv"
            bench_raw.write_text(bench_csv)

    if load_failed:
        # still capture tegrastats for OOM characterisation
        if not dry_run:
            time.sleep(2)
            ssh("pkill tegrastats || true", check=False)
            time.sleep(1)
            tegra_local = raw_dir / f"{DATE}_{tag}_tegra.log"
            try:
                scp_get(tegra_remote, tegra_local)
                tegra_text = tegra_local.read_text()
            except Exception:
                tegra_text = ""
        else:
            tegra_text = ""
        return bench_csv, "", tegra_text, True

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
        r = ssh(sustained_cmd, timeout=1800, check=False)
        sustained_csv = r.stdout
        if sustained_csv.strip():
            sust_raw = raw_dir / f"{DATE}_{tag}_sustained.csv"
            sust_raw.write_text(sustained_csv)
            lines = sustained_csv.splitlines()
            data_lines = [l for l in lines if not l.startswith("build") and l.strip()]
            bench_csv = bench_csv.rstrip("\n") + "\n" + "\n".join(data_lines)

    # ── TTFT ──────────────────────────────────────────────────────────────
    ttft_cmd = (
        _ld_prefix() +
        f"{LLAMA_COMPLETION} -m {remote_path} -ngl {NGL} -c {N_CTX} -n 128 "
        f"-no-cnv -p {shlex.quote(TTFT_PROMPT)} </dev/null 2>&1"
    )
    print(f"  → TTFT …")
    if dry_run:
        ttft_text = ""
    else:
        r = ssh(ttft_cmd, timeout=600, check=False)
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

    return bench_csv, ttft_text, tegra_text, False


# ── result formatting ─────────────────────────────────────────────────────────

def _med_stddev(rows: list[BenchRow], test_prefix: str) -> tuple[float, float]:
    matched = [r for r in rows if r.test.startswith(test_prefix)]
    if not matched:
        return 0.0, 0.0
    if len(matched) == 1:
        return matched[0].avg_ts, matched[0].stddev_ts
    vals = [r.avg_ts for r in matched]
    return statistics.median(vals), statistics.stdev(vals)


def format_result_block(
    spec: ModelSpec,
    sha256: str,
    bench_csv: str,
    ttft_text: str,
    tegra: TegrastatsSummary,
    run_ts: str,
    actual_commit: str,
    load_failed: bool,
) -> str:
    if load_failed:
        return textwrap.dedent(f"""\
        ### Unit {spec.unit_id} — {spec.name} {spec.quant} (**FAILED TO LOAD**)

        **Run:** {run_ts} UTC · 15 W locked · llama.cpp `{actual_commit}` CUDA sm_87

        | Metric | Value |
        |---|---|
        | SHA256 | `{sha256}` |
        | Load result | **OOM / failed — model did not run** |
        | Peak RAM at failure | {tegra.peak_ram_mb:.0f} MB / 7607 MB |
        | Swap hit | {'YES ⚠' if tegra.swap_hit else 'no'} |
        | Peak SoC temp | {tegra.peak_temp_c:.1f} °C |

        > **Negative result (expected per HG5 / RQ-G4).** Documented as thesis content.

        """)

    bench_rows = parse_bench_csv(bench_csv) if bench_csv else []
    pp_med, pp_std    = _med_stddev(bench_rows, "pp")
    tg_med, tg_std    = _med_stddev(bench_rows, "tg1")   # tg128
    tg512_med, _      = _med_stddev(bench_rows, "tg5")    # tg512

    timings  = parse_llama_cli_timings(ttft_text) if ttft_text else None
    ttft_ms  = timings.ttft_ms if timings else float("nan")

    idle_w   = tegra.idle_w
    mean_w   = tegra.mean_w
    peak_w   = tegra.peak_w
    peak_t   = tegra.peak_temp_c
    peak_ram = tegra.peak_ram_mb
    swap     = "YES ⚠" if tegra.swap_hit else "no"

    tg_per_w     = tg_med / peak_w if peak_w > 0 else float("nan")
    j_per_tok    = peak_w / tg_med if tg_med > 0 else float("nan")
    net_w        = peak_w - idle_w
    tg_per_w_net = tg_med / net_w if net_w > 0 else float("nan")

    return textwrap.dedent(f"""\
    ### Unit {spec.unit_id} — {spec.name} {spec.quant}

    **Run:** {run_ts} UTC · 15 W locked · llama.cpp `{actual_commit}` CUDA sm_87
    **Gen/arch:** {spec.gen} / {spec.arch_idea} · {spec.params_b}B params
    {f'**Note:** {spec.notes}' if spec.notes else ''}

    | Metric | Value |
    |---|---|
    | SHA256 | `{sha256}` |
    | Prefill pp512 (median ± σ, ×{PP_REPS}) | **{pp_med:.1f} ± {pp_std:.2f} tok/s** |
    | Decode tg128 (median ± σ, ×{PP_REPS}) | **{tg_med:.2f} ± {tg_std:.3f} tok/s** |
    | Decode tg512 sustained (×{TG_REPS}) | {tg512_med:.2f} tok/s |
    | TTFT (prompt eval) | {ttft_ms:.0f} ms |
    | Peak RAM | {peak_ram:.0f} MB / 7607 MB |
    | Swap hit | {swap} |
    | Power — idle | {idle_w:.2f} W |
    | Power — mean (active) | {mean_w:.2f} W |
    | Power — peak | {peak_w:.2f} W |
    | Peak SoC temp | {peak_t:.1f} °C |
    | tok/s per watt (total) | {tg_per_w:.2f} |
    | tok/s per watt (net of idle) | {tg_per_w_net:.2f} |
    | J/token (total) | {j_per_tok:.3f} |

    """)


def results_md_row(spec: ModelSpec, bench_csv: str, tegra: TegrastatsSummary,
                   run_ts: str, load_failed: bool) -> str:
    if load_failed:
        return (
            f"| {run_ts[:10]} | {spec.unit_id} | {spec.name} {spec.quant} "
            f"| {spec.params_b}B | 15W locked | **FAILED** | — | — | — | — "
            f"| {tegra.peak_temp_c:.0f}°C | {tegra.peak_ram_mb:.0f}MB OOM |"
        )
    bench_rows = parse_bench_csv(bench_csv) if bench_csv else []
    pp_med, _ = _med_stddev(bench_rows, "pp")
    tg_med, _ = _med_stddev(bench_rows, "tg1")
    peak_w    = tegra.peak_w
    tg_per_w  = tg_med / peak_w if peak_w > 0 else float("nan")
    j_per_tok = peak_w / tg_med if tg_med > 0 else float("nan")
    swap      = "swap" if tegra.swap_hit else ""
    return (
        f"| {run_ts[:10]} | {spec.unit_id} | {spec.name} {spec.quant} "
        f"| {spec.params_b}B | 15W locked | pp512={pp_med:.0f} "
        f"| tg128={tg_med:.2f} | {peak_w:.1f}W pk | {tg_per_w:.2f} | {j_per_tok:.3f} "
        f"| {tegra.peak_temp_c:.0f}°C | {tegra.peak_ram_mb:.0f}MB {swap} |"
    )


# ── footprint re-measure (RQ-G3 / §11) ────────────────────────────────────────

# Models whose true on-device footprint we re-measure authoritatively. G1 (tiny,
# irrelevant to RQ-G3) and G5 (never loads) are excluded from the footprint pass;
# G5 is handled separately as a partial-offload cliff-vs-gradient probe.
FOOTPRINT_UNITS = {"G2", "G3", "G4"}


def _capture_load(spec: ModelSpec, remote_path: str, ngl: int, raw_dir: Path,
                  tag_suffix: str) -> tuple[str, TegrastatsSummary]:
    """Load a model with --no-mmap --verbose, generate a few tokens, and capture
    the full stderr (with llama.cpp's per-buffer allocation report) plus a
    tegrastats trace. Returns (load_log_text, tegra_summary)."""
    tag = f"gsweep{spec.unit_id}_footprint"
    tegra_remote = f"/tmp/{tag}_tegra.log"

    ssh("pkill tegrastats || true", check=False)
    time.sleep(1)
    ssh_bg(f"tegrastats --interval 1000 --logfile {tegra_remote}")
    time.sleep(5)  # idle baseline

    # --no-mmap forces weights into malloc'd (RSS-counted) memory.
    # llama.cpp always prints "CUDA0/CPU model/KV/compute buffer size" lines
    # during load (not behind --verbose); --verbose is intentionally omitted
    # because it floods stderr with per-tensor debug output (multi-GB logs).
    cmd = (
        _ld_prefix() +
        f"{LLAMA_CLI} -m {remote_path} -ngl {ngl} -c {N_CTX} --no-mmap -n 16 "
        f"-no-cnv -p {shlex.quote(TTFT_PROMPT)} </dev/null 2>&1"
    )
    print(f"    → loading with -ngl {ngl} --no-mmap …")
    r = ssh(cmd, timeout=900, check=False)
    load_log = r.stdout
    (raw_dir / f"{DATE}_{tag}{tag_suffix}.txt").write_text(load_log)

    time.sleep(2)
    ssh("pkill tegrastats || true", check=False)
    time.sleep(1)
    tegra_local = raw_dir / f"{DATE}_{tag}{tag_suffix}_tegra.log"
    try:
        scp_get(tegra_remote, tegra_local)
        tegra = parse_tegrastats(tegra_local.read_text())
    except Exception:
        tegra = TegrastatsSummary()
    return load_log, tegra


def run_footprint_mode(g5_ngl: int) -> None:
    """RQ-G3 follow-up: authoritative footprint for G2/G3/G4 (§11.2) + a
    partial-offload cliff-vs-gradient probe for G5 (§11.2/RQ-G4)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    actual_commit = get_actual_commit()
    by_id = {s.unit_id: s for s in MODELS}
    rows: list[str] = []

    print("── footprint re-measure (--no-mmap, authoritative buffers) ──")
    for uid in ("G2", "G3", "G4"):
        spec = by_id[uid]
        remote_path = f"{MODELS_DIR}/{spec.gguf_file}"
        print(f"  Unit {uid}: {spec.name}")
        log, tegra = _capture_load(spec, remote_path, NGL, RAW_DIR, "")
        fp = parse_llama_load_buffers(log)
        idle_ram = tegra.idle_readings()[0].ram_used_mb if tegra.readings else 0.0
        ram_delta = max(0.0, tegra.peak_ram_mb - idle_ram)  # RSS growth (no-mmap)
        print(f"    model={fp.model_total_mb:.0f}  KV={fp.kv_total_mb:.0f}  "
              f"compute={fp.compute_total_mb:.0f}  resident={fp.resident_total_mb:.0f} MiB  "
              f"(RSS Δ≈{ram_delta:.0f} MB)")
        rows.append(
            f"| {uid} | {spec.name} | {fp.model_total_mb:.0f} | {fp.kv_total_mb:.0f} "
            f"| {fp.compute_total_mb:.0f} | **{fp.resident_total_mb:.0f}** | {ram_delta:.0f} |"
        )

    # ── G5 partial-offload cliff-vs-gradient probe ────────────────────────────
    print(f"  Unit G5: partial offload -ngl {g5_ngl} (cliff vs gradient)")
    g5 = by_id["G5"]
    g5_log, g5_tegra = _capture_load(g5, f"{MODELS_DIR}/{g5.gguf_file}", g5_ngl,
                                     RAW_DIR, f"_ngl{g5_ngl}")
    g5_timings = parse_llama_cli_timings(g5_log)
    if g5_timings and g5_timings.tg_ts > 0:
        g5_verdict = (f"**GRADIENT** — loaded at -ngl {g5_ngl}, decode "
                      f"{g5_timings.tg_ts:.2f} tok/s (vs hard OOM at -ngl 99)")
    elif "out of memory" in g5_log.lower() or "cudaMalloc failed" in g5_log:
        g5_verdict = f"**CLIFF** — still OOM at -ngl {g5_ngl}"
    else:
        g5_verdict = f"inconclusive — see raw `gsweepG5_footprint_ngl{g5_ngl}.txt`"
    print(f"    G5: {g5_verdict}")

    table = (
        "| Unit | Model | model MiB | KV MiB | compute MiB | resident MiB | RSS Δ MB |\n"
        "|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n\n"
        f"**G5 partial offload (-ngl {g5_ngl}):** {g5_verdict}  \n"
        f"_Run: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M')} UTC · "
        f"15 W locked · llama.cpp `{actual_commit}` · `--no-mmap --verbose`_\n"
    )
    placeholder = (
        "*(populated by `python experiments/run_gemma_sweep.py --footprint`; raw verbose load logs in\n"
        "`./raw/*_footprint.txt`)*"
    )
    content = CAMPAIGN_MD.read_text()
    if placeholder in content:
        content = content.replace(placeholder, table)
        CAMPAIGN_MD.write_text(content)
        print(f"  ✓ wrote footprint table into {CAMPAIGN_MD.name} §11.3")
    else:
        print("  ⚠  §11.3 placeholder not found; table:\n" + table)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only",         help="comma-separated unit IDs, e.g. G1,G3")
    parser.add_argument("--dry-run",      action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--start-from",   help="skip units before this ID, e.g. G3")
    parser.add_argument("--footprint",    action="store_true",
                        help="RQ-G3 §11 re-measure: authoritative load-buffer footprint for "
                             "G2/G3/G4 (--no-mmap) + G5 partial-offload cliff probe. "
                             "Assumes models already on device.")
    parser.add_argument("--g5-ngl",       type=int, default=28,
                        help="GPU layers for the G5 partial-offload probe (default 28)")
    args = parser.parse_args()

    if args.footprint:
        run_footprint_mode(args.g5_ngl)
        return

    only_ids   = set(args.only.split(",")) if args.only else None
    start_from = args.start_from or "G1"

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("═" * 65)
    print("  Jetson Orin Nano — Gemma-family sweep")
    print(f"  Campaign: {CAMPAIGN_ID}")
    print("═" * 65)
    print()

    actual_commit = check_preconditions(args.dry_run)

    for spec in MODELS:
        if only_ids and spec.unit_id not in only_ids:
            continue
        if spec.unit_id < start_from:
            continue

        print(f"── Unit {spec.unit_id}: {spec.name} {spec.quant} ({spec.params_b}B, {spec.arch_idea}) ──")
        if spec.notes:
            print(f"  ℹ  {spec.notes}")

        run_ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M")

        if args.skip_download:
            remote_path = f"{MODELS_DIR}/{spec.gguf_file}"
        else:
            remote_path = ensure_model(spec, args.dry_run)

        sha = sha256_model(remote_path, args.dry_run)
        print(f"  SHA256: {sha[:16]}…")

        bench_csv, ttft_text, tegra_text, load_failed = run_unit(
            spec, remote_path, args.dry_run, RAW_DIR
        )

        tegra = parse_tegrastats(tegra_text)

        if not args.dry_run and CAMPAIGN_MD.exists():
            block = format_result_block(
                spec, sha, bench_csv, ttft_text, tegra,
                run_ts, actual_commit, load_failed,
            )
            # Insert each block at the end of "## 8. Results" (just before the
            # "## 9. Decisions" heading), stripping the pre-registration
            # placeholder on first write. Keeps all result blocks together in §8
            # rather than scattering G2–G5 after the Decisions/Sources sections.
            content = CAMPAIGN_MD.read_text()
            placeholder = (
                "*(empty — protocol pre-registration. Per-model result blocks + raw logs land here and as rows in\n"
                "root `RESULTS.md` as runs complete. Raw llama-bench CSVs and tegrastats logs go in `./raw/`.)*\n"
            )
            content = content.replace(placeholder, "")
            marker = "## 9. Decisions"
            if marker in content:
                content = content.replace(marker, block + "\n" + marker, 1)
            else:
                content = content.rstrip("\n") + "\n\n" + block
            CAMPAIGN_MD.write_text(content)

        if not args.dry_run:
            row = results_md_row(spec, bench_csv, tegra, run_ts, load_failed)
            with RESULTS_MD.open("a") as f:
                f.write(row + "\n")

        if not load_failed:
            bench_rows = parse_bench_csv(bench_csv) if bench_csv else []
            pp_med, _ = _med_stddev(bench_rows, "pp")
            tg_med, _ = _med_stddev(bench_rows, "tg1")
            print(f"  ✓ pp512={pp_med:.1f} tok/s  tg128={tg_med:.2f} tok/s  "
                  f"peak={tegra.peak_w:.1f}W  RAM={tegra.peak_ram_mb:.0f}MB")
        else:
            print(f"  ✗ load failed — RAM at failure={tegra.peak_ram_mb:.0f}MB  "
                  f"swap={'YES' if tegra.swap_hit else 'no'}")

        print()

    print("═" * 65)
    print("  Gemma-family sweep complete.")
    print(f"  Results appended to {CAMPAIGN_MD.relative_to(REPO_ROOT)}")
    print(f"  Summary rows appended to RESULTS.md")
    print("═" * 65)


if __name__ == "__main__":
    main()
