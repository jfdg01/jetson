---
unit_id: <campaign-slug>-NN
campaign: <campaign-slug>            # matches results/<date>-<campaign>.md
title: <one-line unit name>          # e.g. "Qwen2.5-0.5B-Instruct Q4_K_M @ 15W locked"
status: TODO                         # TODO | RUNNING | DONE | FAILED | BLOCKED
created: <YYYY-MM-DD>
---

# Unit: <title>

> Executed by a fresh, isolated session via `experiments/run-unit.sh`. Your only context is
> `CLAUDE.md` + this card. See `experiments/README.md` for the methodology.

## Objective
<One sentence: the single thing this unit measures and why it exists in the campaign.>

## Preconditions  (verify ALL; if any fails → status: BLOCKED, note why, STOP)
- [ ] Device reachable: `ssh jetson true` succeeds.
- [ ] Runtime present: `<path>/llama-bench --version` matches the pinned commit `<hash>`.
- [ ] Disk headroom on NVMe for the model file (`df -h /`).
- [ ] <any unit-specific precondition>

## Inputs  (record exactly — no source = not reproducible)
| Field | Value |
|---|---|
| Model | <full name> |
| Params | <N>B |
| Quant | <e.g. Q4_K_M> |
| GGUF repo | <HF repo> |
| Revision | <commit/branch> |
| File | <filename.gguf> |
| SHA256 | <fill at acquisition; verify after download> |
| Expected size | <GB> |

## Controlled config  (DO NOT change — these are held constant across the campaign)
- Power mode: <e.g. 15 W (ID=0), clocks LOCKED via `sudo jetson_clocks`>
- Runtime: <llama.cpp commit + flags>
- Context / batch: <n_ctx / n_batch>
- Offload: <-ngl 99>
- Prompt / shapes: <pp512 / tg128, repeats=5>

## Procedure  (run EXACTLY; the variable for this unit is ONLY the model)
```bash
# 1. Device state
ssh jetson 'sudo nvpmodel -m 0 && sudo jetson_clocks && tegrastats --interval 1000 --logfile /tmp/<unit_id>_tegra.log &'
# 2. Acquire model (record SHA256), stage on NVMe
# 3. Throughput: llama-bench -m <model> -ngl 99 -p 512 -n 128 -r 5  (+ tg512 sustained)
# 4. Latency: llama-cli timing pass for TTFT
# 5. Memory: peak RAM + unified GPU; flag if zram swap touched
# 6. Stop tegrastats; extract idle/mean/peak W, peak temp, throttle events
# 7. Pull logs back to results/raw/
```

## Output contract  (all of these, before you stop)
- [ ] Raw logs → `results/raw/<date>_<unit_id>_*.{log,csv}`
- [ ] Detail block appended to `results/<date>-<campaign>.md` with EVERY mandatory metric
      field from `CLAUDE.md` (pp, tg, TTFT, peak mem + swap flag, idle/mean/peak W, temp +
      throttle, tok/s·W⁻¹, J/token) and the config next to each number.
- [ ] Exactly one row appended to `RESULTS.md` (append-only).
- [ ] This card `status:` set to DONE or FAILED.

## Done criteria
- [ ] All output-contract items complete.
- [ ] Numbers reported as median ± σ over the declared repeats (not a cherry-picked best).

## Failure handling  (failures are data, not dead ends)
- OOM / swap thrash / throttle / load error → still write the detail block describing the
  failure: the error text, suspected cause, and workaround (or "unresolved"). Set
  `status: FAILED`. Do NOT retry with a changed config to "make it work" — that would be a
  different unit; note the idea as a follow-up instead.

## Guardrails  (the restriction)
- This card is ONE unit. Do not start another, edit sibling cards, or touch the
  pre-registration design doc.
- Keep every controlled-config value fixed. The only thing that distinguishes this unit from
  its siblings is the model.
- Ambiguous or blocked → `status: BLOCKED`, note it, STOP. Never guess.
