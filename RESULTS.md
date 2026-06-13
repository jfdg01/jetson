# RESULTS — Jetson Orin Nano Edge-LLM Benchmarks

Running ledger across all experiment campaigns. Append, never overwrite.
Each row links to the detailed writeup in `results/`. See `CLAUDE.md` for the
fields every run must capture.

| Date | Power mode | Runtime | Model / quant | Prefill tok/s | Decode tok/s | TTFT | Peak mem | Mean / peak W | tok/s·W⁻¹ | Writeup |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-13 | 15W (locked) ¹ | llama.cpp 57fe1f0 CUDA sm_87 | Llama-3.2-3B-Instruct Q4_K_M | 570.0 ± 2.4 | 14.53 ± 0.02 | n/a ² | 1.87 GiB wts | 12.5 / 13.6 | ≈1.1 (≈1.7 net) | results/2026-06-13-llamacpp-upper-bound.md |

¹ 25 W MAXN_SUPER not available without a firmware update; declined for now. This is the **15 W-locked** ceiling — see `DECISIONS.md`.
² TTFT not separately captured this run; `llama-bench` reports pp/tg throughput, not first-token latency. Add via `llama-cli` timing in a follow-up.
Power = total board VDD_IN, mean / peak W during decode. Idle baseline 5.24 W. Peak SoC temp 66.9 °C, no throttling.
