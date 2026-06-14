"""
parsers.py — pure stdlib parsers for llama.cpp and tegrastats output.

All functions are side-effect-free; they take raw text and return plain dicts/lists.
"""
from __future__ import annotations

import csv
import io
import re
import statistics
from dataclasses import dataclass, field
from typing import Optional


# ── llama-bench CSV ─────────────────────────────────────────────────────────

@dataclass
class BenchRow:
    test: str           # "pp512", "tg128", "tg512"
    n_prompt: int
    n_gen: int
    avg_ts: float       # tokens/s
    stddev_ts: float    # std dev of tokens/s


def parse_bench_csv(text: str) -> list[BenchRow]:
    """Parse llama-bench -o csv output.

    Supports two common header variants (older: 'test,t/s'; newer: explicit columns).
    Returns one BenchRow per data row.
    """
    rows: list[BenchRow] = []
    reader = csv.DictReader(io.StringIO(text.strip()))
    for row in reader:
        row = {k.strip(): v.strip() for k, v in row.items() if k}

        # determine test label
        test = row.get("test") or _infer_test(row)

        # throughput: newer format has avg_ts/stddev_ts; older has a 't/s' field like "14.61 ± 0.00"
        if "avg_ts" in row:
            avg_ts = float(row["avg_ts"])
            stddev_ts = float(row.get("stddev_ts", 0))
        elif "t/s" in row:
            avg_ts, stddev_ts = _parse_pm(row["t/s"])
        else:
            continue  # unrecognised format

        n_prompt = int(row.get("n_prompt", 0))
        n_gen = int(row.get("n_gen", 0))

        rows.append(BenchRow(
            test=test,
            n_prompt=n_prompt,
            n_gen=n_gen,
            avg_ts=avg_ts,
            stddev_ts=stddev_ts,
        ))
    return rows


def _infer_test(row: dict) -> str:
    n_prompt = int(row.get("n_prompt", 0))
    n_gen = int(row.get("n_gen", 0))
    if n_prompt > 0 and n_gen == 0:
        return f"pp{n_prompt}"
    if n_gen > 0 and n_prompt == 0:
        return f"tg{n_gen}"
    return f"pp{n_prompt}+tg{n_gen}"


def _parse_pm(value: str) -> tuple[float, float]:
    """Parse '14.61 ± 0.00' or '14.61' into (avg, stddev)."""
    value = value.replace("±", "").replace("+/-", "")
    parts = value.split()
    avg = float(parts[0])
    stddev = float(parts[1]) if len(parts) > 1 else 0.0
    return avg, stddev


# ── llama-cli timing block ───────────────────────────────────────────────────

@dataclass
class LlamaCliTimings:
    load_ms: float
    prompt_eval_ms: float   # time to process all prompt tokens (≈ TTFT for long prompts)
    prompt_tokens: int
    eval_ms: float          # time for all generated tokens
    eval_tokens: int
    ttft_ms: float          # prompt_eval_ms (TTFT proxy)
    pp_ts: float            # prompt tokens/s (prefill)
    tg_ts: float            # generated tokens/s (decode)


def _parse_timing_float(s: str) -> float:
    """Parse a timing float that may use comma as decimal separator (European locale)."""
    return float(s.replace(",", "."))


def parse_llama_cli_timings(text: str) -> Optional[LlamaCliTimings]:
    """Parse timing blocks from llama-cli or llama-completion stdout/stderr.

    Handles two formats:
    - Old: 'llama_print_timings:   load time = 1234.56 ms'
    - New: '0.01.234.567 I common_perf_print:   load time = 1234,56 ms'
    Both may use '.' or ',' as the decimal separator (locale-dependent).
    """
    load = re.search(r"load time\s*=\s*([\d.,]+)\s*ms", text)
    prompt = re.search(
        r"prompt eval time\s*=\s*([\d.,]+)\s*ms\s*/\s*(\d+)\s*tokens", text
    )
    eval_ = re.search(
        r"\beval time\s*=\s*([\d.,]+)\s*ms\s*/\s*(\d+)\s*runs", text
    )
    if not (load and prompt and eval_):
        return None

    prompt_eval_ms = _parse_timing_float(prompt.group(1))
    prompt_tokens = int(prompt.group(2))
    eval_ms = _parse_timing_float(eval_.group(1))
    eval_tokens = int(eval_.group(2))

    pp_ts = prompt_tokens / (prompt_eval_ms / 1000) if prompt_eval_ms > 0 else 0.0
    tg_ts = eval_tokens / (eval_ms / 1000) if eval_ms > 0 else 0.0

    return LlamaCliTimings(
        load_ms=_parse_timing_float(load.group(1)),
        prompt_eval_ms=prompt_eval_ms,
        prompt_tokens=prompt_tokens,
        eval_ms=eval_ms,
        eval_tokens=eval_tokens,
        ttft_ms=prompt_eval_ms,
        pp_ts=pp_ts,
        tg_ts=tg_ts,
    )


# ── llama.cpp load-buffer footprint ──────────────────────────────────────────

@dataclass
class LlamaLoadFootprint:
    """Exact allocation breakdown printed by llama.cpp at load (MiB).

    These are authoritative (reported by the runtime), unlike tegrastats RAM
    sampling, which under-counts mmap'd weights and can miss the load spike at
    1 s resolution. Captured with --no-mmap --verbose. See the gemma-family
    campaign §11 / RQ-G3.
    """
    model_buffer_mb: dict[str, float] = field(default_factory=dict)   # device -> MiB
    kv_buffer_mb: dict[str, float] = field(default_factory=dict)
    compute_buffer_mb: dict[str, float] = field(default_factory=dict)

    @property
    def model_total_mb(self) -> float:
        return sum(self.model_buffer_mb.values())

    @property
    def kv_total_mb(self) -> float:
        return sum(self.kv_buffer_mb.values())

    @property
    def compute_total_mb(self) -> float:
        return sum(self.compute_buffer_mb.values())

    @property
    def resident_total_mb(self) -> float:
        """Model weights + KV cache + compute buffers — true on-device footprint."""
        return self.model_total_mb + self.kv_total_mb + self.compute_total_mb


# Matches e.g.:
#   load_tensors:        CUDA0 model buffer size =  3000.50 MiB
#   llama_kv_cache:      CUDA0 KV buffer size =   512.00 MiB
#   llama_context:       CUDA0 compute buffer size =   300.25 MiB
_BUF_RE = re.compile(
    r"(?P<device>\S+)\s+(?P<kind>model|KV|compute)\s+buffer size\s*=\s*"
    r"(?P<size>[\d.,]+)\s*MiB",
    re.IGNORECASE,
)


def parse_llama_load_buffers(text: str) -> LlamaLoadFootprint:
    """Parse the per-device buffer-size lines from a llama.cpp load log.

    llama.cpp runs two passes per load: a probe/dry-run pass (all zeros for
    model and KV, but real values for compute), then the real allocation pass.
    Accumulating naively would double-count compute.  Strategy per field:
      - model: accumulate (probe=0 + real=R → R)
      - KV:    accumulate non-zeros only (skip probe zeros; sum distinct segs)
      - compute: last-wins per device (probe and real have identical values;
                 overwriting avoids the 2× duplication)
    """
    fp = LlamaLoadFootprint()
    for m in _BUF_RE.finditer(text):
        device = m.group("device")
        kind = m.group("kind").lower()
        size = float(m.group("size").replace(",", "."))
        if kind == "model":
            fp.model_buffer_mb[device] = fp.model_buffer_mb.get(device, 0.0) + size
        elif kind == "kv":
            if size > 0:  # skip probe-pass zeros; sum real KV cache segments
                fp.kv_buffer_mb[device] = fp.kv_buffer_mb.get(device, 0.0) + size
        elif kind == "compute":
            fp.compute_buffer_mb[device] = size  # last wins; probe == real value
    return fp


# ── tegrastats ───────────────────────────────────────────────────────────────

@dataclass
class TegrastatsReading:
    ram_used_mb: float
    ram_total_mb: float
    swap_used_mb: float
    gr3d_pct: float       # GPU utilisation %
    tj_c: float           # junction (max) temperature °C
    vdd_in_mw: float      # instantaneous total board power mW


@dataclass
class TegrastatsSummary:
    readings: list[TegrastatsReading] = field(default_factory=list)

    def idle_readings(self, n: int = 5) -> list[TegrastatsReading]:
        """First n readings = idle baseline before model load."""
        return self.readings[:n]

    def active_readings(self, skip_idle: int = 5) -> list[TegrastatsReading]:
        """Readings after the idle window."""
        return self.readings[skip_idle:]

    @property
    def idle_w(self) -> float:
        r = self.idle_readings()
        if not r:
            return 0.0
        return statistics.mean(x.vdd_in_mw for x in r) / 1000

    @property
    def mean_w(self) -> float:
        r = self.active_readings()
        if not r:
            return 0.0
        return statistics.mean(x.vdd_in_mw for x in r) / 1000

    @property
    def peak_w(self) -> float:
        r = self.active_readings()
        if not r:
            return 0.0
        return max(x.vdd_in_mw for x in r) / 1000

    @property
    def peak_temp_c(self) -> float:
        if not self.readings:
            return 0.0
        return max(x.tj_c for x in self.readings)

    @property
    def peak_ram_mb(self) -> float:
        if not self.readings:
            return 0.0
        return max(x.ram_used_mb for x in self.readings)

    # ── swap ──────────────────────────────────────────────────────────────
    # The device almost always carries a *pre-existing* swap baseline (other
    # processes), so "swap > 0" is not evidence that inference pushed the model
    # into swap. We measure GROWTH relative to the idle baseline instead. See
    # the gemma-family campaign §11 (data-quality correction): a flat 306 MB
    # baseline was mis-flagged as a swap hit on every unit by the old
    # `any(swap > 0)` test.
    SWAP_HIT_THRESHOLD_MB: float = 50.0

    @property
    def swap_baseline_mb(self) -> float:
        """Swap in use during the idle window, before the model loads."""
        r = self.idle_readings()
        if not r:
            return 0.0
        return min(x.swap_used_mb for x in r)

    @property
    def peak_swap_mb(self) -> float:
        if not self.readings:
            return 0.0
        return max(x.swap_used_mb for x in self.readings)

    @property
    def swap_growth_mb(self) -> float:
        """How much swap grew above the idle baseline during the run."""
        return max(0.0, self.peak_swap_mb - self.swap_baseline_mb)

    @property
    def swap_hit(self) -> bool:
        """True only if swap grew meaningfully above the idle baseline."""
        return self.swap_growth_mb > self.SWAP_HIT_THRESHOLD_MB


_TEGRA_RE = re.compile(
    r"RAM (?P<ram_used>\d+)/(?P<ram_total>\d+)MB"
    r".*?SWAP (?P<swap_used>\d+)/\d+MB"
    r".*?GR3D_FREQ (?P<gr3d>\d+)%"
    r".*?tj@(?P<tj>[\d.]+)C"
    r".*?VDD_IN (?P<vdd_in>\d+)mW"
)


def parse_tegrastats(text: str) -> TegrastatsSummary:
    """Parse a tegrastats log file (one line per second) into a summary."""
    summary = TegrastatsSummary()
    for line in text.splitlines():
        m = _TEGRA_RE.search(line)
        if not m:
            continue
        summary.readings.append(TegrastatsReading(
            ram_used_mb=float(m.group("ram_used")),
            ram_total_mb=float(m.group("ram_total")),
            swap_used_mb=float(m.group("swap_used")),
            gr3d_pct=float(m.group("gr3d")),
            tj_c=float(m.group("tj")),
            vdd_in_mw=float(m.group("vdd_in")),
        ))
    return summary


# ── sanity tests (run with: python -m pytest experiments/parsers.py -v) ─────

def _test_parse_bench_csv_pm_format():
    sample = (
        "model,size,params,backend,ngl,n_batch,n_ubatch,type_k,type_v,n_threads,test,t/s\n"
        "llama 3B Q4_K_M,1.85 GiB,3.21 B,CUDA,99,512,512,f16,f16,6,pp512,570.00 ± 2.38\n"
        "llama 3B Q4_K_M,1.85 GiB,3.21 B,CUDA,99,512,512,f16,f16,6,tg128,14.61 ± 0.00\n"
    )
    rows = parse_bench_csv(sample)
    assert len(rows) == 2
    assert rows[0].test == "pp512"
    assert abs(rows[0].avg_ts - 570.0) < 0.01
    assert abs(rows[0].stddev_ts - 2.38) < 0.01
    assert rows[1].test == "tg128"
    assert abs(rows[1].avg_ts - 14.61) < 0.01


def _test_parse_bench_csv_columns_format():
    sample = (
        "build_commit,cpu_info,gpu_info,model_filename,n_batch,n_ubatch,n_threads,"
        "type_k,type_v,n_gpu_layers,n_prompt,n_gen,avg_ts,stddev_ts\n"
        "57fe1f0,Cortex-A78AE,NVIDIA,model.gguf,512,512,6,f16,f16,99,512,0,571.2,1.9\n"
        "57fe1f0,Cortex-A78AE,NVIDIA,model.gguf,512,512,6,f16,f16,99,0,128,14.55,0.03\n"
    )
    rows = parse_bench_csv(sample)
    assert len(rows) == 2
    assert rows[0].test == "pp512"
    assert rows[1].test == "tg128"


def _test_parse_tegrastats():
    line = (
        "06-13-2026 14:17:07 RAM 3308/7607MB (lfb 32x4MB) SWAP 11/3804MB (cached 0MB) "
        "CPU [0%@1510] GR3D_FREQ 99% cpu@61.5C soc2@60.2C soc0@58.0C gpu@62.3C "
        "tj@62.4C soc1@59.9C VDD_IN 12517mW/10898mW VDD_CPU_GPU_CV 4959mW/3943mW "
        "VDD_SOC 2562mW/2282mW\n"
    )
    summary = parse_tegrastats(line * 10)
    assert len(summary.readings) == 10
    assert summary.readings[0].ram_used_mb == 3308
    assert summary.readings[0].tj_c == 62.4
    assert summary.readings[0].vdd_in_mw == 12517
    assert summary.peak_w == 12517 / 1000


def _test_swap_growth_detection():
    # Flat swap (gemma case): pre-existing 306 MB baseline, never grows -> no hit.
    flat = (
        "RAM 1357/7607MB (lfb 7x2MB) SWAP 306/3804MB (cached 1MB) "
        "GR3D_FREQ 0% tj@54.6C VDD_IN 5237mW/5237mW\n"
    )
    s_flat = parse_tegrastats(flat * 20)
    assert s_flat.swap_baseline_mb == 306
    assert s_flat.swap_growth_mb == 0
    assert s_flat.swap_hit is False

    # Real growth (10-model-sweep case): 11 MB idle -> 206 MB during decode -> hit.
    idle = (
        "RAM 1000/7607MB SWAP 11/3804MB GR3D_FREQ 0% tj@50.0C VDD_IN 5200mW/5200mW\n"
    )
    busy = (
        "RAM 5000/7607MB SWAP 206/3804MB GR3D_FREQ 99% tj@65.0C VDD_IN 13000mW/13000mW\n"
    )
    s_grow = parse_tegrastats(idle * 5 + busy * 15)
    assert s_grow.swap_baseline_mb == 11
    assert s_grow.peak_swap_mb == 206
    assert s_grow.swap_growth_mb == 195
    assert s_grow.swap_hit is True


def _test_parse_llama_load_buffers():
    text = (
        "load_tensors:        CUDA0 model buffer size =  3000.50 MiB\n"
        "load_tensors:          CPU model buffer size =   200.00 MiB\n"
        "llama_kv_cache:      CUDA0 KV buffer size =   512.00 MiB\n"
        "llama_context:       CUDA0 compute buffer size =   300.25 MiB\n"
    )
    fp = parse_llama_load_buffers(text)
    assert abs(fp.model_total_mb - 3200.50) < 0.01
    assert abs(fp.kv_total_mb - 512.00) < 0.01
    assert abs(fp.compute_total_mb - 300.25) < 0.01
    assert abs(fp.resident_total_mb - 4012.75) < 0.01


def _test_parse_llama_cli_timings():
    text = (
        "llama_print_timings:        load time =    1234.56 ms\n"
        "llama_print_timings:  sample time =      12.34 ms /   128 runs\n"
        "llama_print_timings:   prompt eval time =    894.56 ms /   512 tokens "
        "(    1.75 ms per token,   572.37 tokens per second)\n"
        "llama_print_timings:        eval time =   8765.43 ms /   127 runs "
        "(   69.02 ms per token,    14.49 tokens per second)\n"
        "llama_print_timings:       total time =   9660.00 ms /   639 tokens\n"
    )
    t = parse_llama_cli_timings(text)
    assert t is not None
    assert abs(t.ttft_ms - 894.56) < 0.01
    assert abs(t.pp_ts - 572.37) < 1.0
    assert abs(t.tg_ts - 14.49) < 0.5


if __name__ == "__main__":
    _test_parse_bench_csv_pm_format()
    _test_parse_bench_csv_columns_format()
    _test_parse_tegrastats()
    _test_swap_growth_detection()
    _test_parse_llama_load_buffers()
    _test_parse_llama_cli_timings()
    print("all parsers tests passed")
