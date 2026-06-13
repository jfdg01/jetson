# Campaign manifest — 2026-06-13 model capability sweep

10 units, one per model, run **sequentially** (single device), each in its **own fresh,
isolated Claude session**. Source of truth for status is each run card's `status:` field —
this table is a human dashboard; regenerate the status column with:

```bash
for c in experiments/campaigns/2026-06-13-model-capability-sweep/runcards/*.md; do
  printf "%-34s %s\n" "$(basename "$c")" "$(grep -m1 '^status:' "$c" | awk '{print $2}')"
done
```

Design / RQs / hypotheses: [`results/2026-06-13-model-capability-sweep.md`](../../../results/2026-06-13-model-capability-sweep.md).
Methodology: [`experiments/README.md`](../../README.md).

| # | Model | Params | Family | Tier | ~Size | Acquire | Status |
|---|---|---|---|---|---|---|---|
| 01 | Qwen2.5-0.5B-Instruct | 0.5 B | Qwen2.5 | A ultralight | 397 MB | wget | TODO |
| 02 | Llama-3.2-1B-Instruct | 1 B | Llama-3.2 | A ultralight | 770 MB | wget | TODO |
| 03 | Qwen2.5-1.5B-Instruct | 1.5 B | Qwen2.5 | A light | 940 MB | wget | TODO |
| 04 | Gemma-2-2B-it | 2.6 B | Gemma-2 | B sweet-spot | 1.6 GB | wget | TODO |
| 05 | Qwen2.5-3B-Instruct | 3 B | Qwen2.5 | B sweet-spot | 1.8 GB | wget | TODO |
| 06 | Llama-3.2-3B-Instruct | 3 B | Llama-3.2 | B sweet-spot | 2.0 GB | **local** (baseline anchor) | TODO |
| 07 | Phi-3.5-mini-instruct | 3.8 B | Phi-3.5 | B sweet-spot | 2.3 GB | wget | TODO |
| 08 | Mistral-7B-Instruct-v0.3 | 7.2 B | Mistral | C heavy ⚠️ | 4.2 GB | wget | TODO |
| 09 | Qwen2.5-7B-Instruct | 7.6 B | Qwen2.5 | C heavy ⚠️ | 4.5 GB | wget | TODO |
| 10 | Meta-Llama-3.1-8B-Instruct | 8 B | Llama-3.1 | C heavy ⚠️ | 4.7 GB | wget | TODO |

⚠️ = tight fit; OOM / zram swap is a *possible and valid* result (tests H3). Qwen2.5 units
01·03·05·09 form the controlled within-family scaling spine (0.5→1.5→3→7.6 B).

## Run

```bash
# whole campaign, each unit in its own fresh session, resumable (skips DONE, halts on FAILED/BLOCKED):
experiments/run-campaign.sh experiments/campaigns/2026-06-13-model-capability-sweep

# or a single unit:
experiments/run-unit.sh experiments/campaigns/2026-06-13-model-capability-sweep/runcards/01-qwen2.5-0.5b-instruct.md
```
