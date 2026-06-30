# DECISIONS — Part II (v2 Principled Rebuild)

> Decision log for the v2 principled rebuild. Index: [`../../DECISIONS.md`](../../DECISIONS.md).
> Per-experiment decisions also live in `experiments/<campaign>/README.md`. ★ = headline decision.
> **Append** — add each new decision at the **bottom** (chronological, oldest first; matches RESULTS/QUESTIONS).

---

### 2026-06-17T00:00 — Principled rebuild: branch `v2/principled-rebuild`, shared contract, fidelity-before-GPU

- **Chosen:** (a) Consolidated Part I onto `main`, branched `v2/principled-rebuild`. (b) Archive not delete: legacy trainers/exporters → `runners/legacy/`. (c) Importable `grounding/` package; `contract.py` as single source of truth. (d) Phase arc 0–4.
- **Root causes addressed:** (1) −23 pp runtime + −7 pp quant (Idefics3 preprocessing) discovered after training → Phase-0 fidelity gate before GPU. (2) Tiny-object 512 resolution ceiling → Phase-2 as explicit pre-registered variable.
</content>
### 2026-06-17T12:00 — v2 operational toolchain

- **(a) deps:** `uv` + `requirements-ft.lock.txt` frozen from live `.venv-ft` (not re-resolved — avoids bumping the validated cu124 stack).
- **(b) experiment tracking:** `grounding/manifest.py` — per-run `manifest.json` + `run-card.md`: git SHA, pinned llama.cpp commit, lockfile sha256, dataset sha256, full config.
- **(c) testing:** `pytest` 9.1.0 in `requirements-dev.txt`; 22 tests locking prompt byte-string, parser, IoU/center_std maths.
- **(d) llama.cpp pinned:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`.
- **(e) Makefile:** `test/sync/dev/lock/env-ft`.
- **Why:** Cross-backend comparability is the binding constraint. Pytest turns "five copies silently diverged" (Part-I failure) into a CI-style guarantee.

### 2026-06-17T12:30 — RefCOCO loader in Phase 0 (read-only)

- `grounding/data/refcoco.py` read-only during Phase 0. Lifts exact subset construction from Part-I `run_stage3_finetune.RefCOCODataset` so n=100 seed-42 subset is identical → 85.0% ≈ 82.5% comparison valid. Phase-1 audit stats added on top.

### 2026-06-17T14:30 — Phase 0b: GGUF fidelity gap on local CPU llama.cpp

- **Setup:** CPU-only llama.cpp at pinned `57fe1f0`; mmproj scp'd from Jetson. Greedy decode (determinism > reproducing Part-I exact magnitude). `eval/parity.py` composes three committed manifests.
- **Results:** HF 85.0% → F16 **69.0%** (runtime **−16.0 pp**) → Q8_0 **67.0%** (quant −2.0 pp). Runtime ≫ quant confirmed.

### 2026-06-17T16:00 — Phase 0c.1: disqualify PaliGemma 2 + Florence-2 before download

- **Method:** Deployment-backwards filter — grep `paligemma|florence` in `clip.cpp` at `57fe1f0` → 0 hits = zero projector support. Disqualified at zero cost (no download).
- **Survivors:** SmolVLM-500M (IDEFICS3) + Qwen2-VL-2B (QWEN2VL, `conversion/qwenvl.py`).

### 2026-06-17T16:30 — Phase 0c.2: select Qwen2-VL-2B as v2 spine ★

- **Probe results (n=100, seed-42, RefCOCO val, HF bf16 greedy):**

| Model | IoU@0.25 | Parse | center_std | HF→F16 gap |
|-------|----------|-------|------------|------------|
| **Qwen2-VL-2B** | **15.0%** | **24%** | **162.1 (healthy)** | **−2 pp** |
| SmolVLM-500M | 0.0% | 9% | 61.3 (collapsed) | −16 pp |

- **Chosen:** Qwen2-VL-2B — grounding-native (real zero-shot floor), deployment fidelity 8× better, native dynamic resolution attacks binding constraint #2.

### 2026-06-17T18:00 — Phase 1: one-box well-posed filter; budget 4101/439 ★

- **Audit results (CPU-only, no GPU):** RefDrone train mean 3.80 boxes/caption, **33.2% well-posed → 4101 train / 439 val**. Aerial object @512: **median ≈16 px, p25 6–10 px** vs RefCOCO control median 172 px.
- **Gate:** fails on raw corpus (0.332), passes on filtered subset (1.000). Confirms ill-posed target as Stage-2 root cause.
- **Significance:** Object-size measurement establishes resolution as dominant downstream lever.

### 2026-06-17T20:00 — Phase 2: `max_side=1024` as input long-edge ★

- **Resolution ladder (base Qwen2-VL-2B, n=439, no training):**

| Resolution | IoU@0.25 | Parse | center_std |
|-----------|----------|-------|------------|
| 512 | 4.1% | 100% | 129.1 |
| 768 | 10.7% | 100% | 157.9 |
| **1024** | **30.3%** | 91.8% | 192.0 |
| 1280 | 38.7% | 92.0% | 196.1 |

- **Chosen:** 1024 — largest marginal jump (768→1024 = +19.6 pp), captures ~78% of 1280 ceiling at ~35% fewer visual tokens.
- **1280 not chosen:** +8.4 pp but ~1.56× visual tokens; past the elbow; kept as explicit Phase-3 lever.

### 2026-06-18T00:30 — Phase 3 PASS: Qwen2-VL-2B LoRA on RefDrone well-posed ★

- **Config:** LoRA r16/α32/dropout0.05 on LLM attn+MLP (vision frozen, 18.5 M params = 0.83%), lr 2e-4, 3 epochs, batch 2×grad_accum 8, bf16, seed 42, `max_side=1024`, RefDrone well-posed (4101 train / 439 val).
- **Results:** In-loop val epoch1/2/3 = 63.0 / 65.0 / 65.0%. **Authoritative full-val n=439 = 59.5% IoU@0.25, parse 100%, mean_iou 0.451, center_std 215.2** (vs Phase-2 base-1024: 30.3%).
- **Reserved levers not used** (gate cleared at epoch 1): `largest_box_aug`, `max_side=1280`, RefCOCO warm-start via `init_from`.
- **Significance:** Part-I 19.5% narrow miss → v2 59.5%. Gain decomposes into two independently measured levers: resolution (4.1%→30.3% zero-shot) × fine-tune (30.3%→59.5%).

### 2026-06-18T00:45 — Auto-continuation: OS crontab (not harness CronCreate)

- **Chosen:** `scripts/auto_continue.sh` every 15 min by user crontab. Guard ladder: STOP sentinel → DONE sentinel → `flock` (no concurrent runs) → `pgrep -x claude` (defer to live session) → `timeout 3h`. Headless `claude -p --dangerously-skip-permissions`; never pushes; `.auto-continue/BLOCKED.md` for human-needed items.
- **Why CronCreate rejected:** `durable:true` not honored — schedule died with session on token exhaustion.
- **Trade-off:** ≤15 min resume latency. Unattended headless agent mitigated by kill switch, DONE auto-stop, repo-scoped `--add-dir`.

### 2026-06-18T00:50 — Jetson power: 15 W only (no 25 W MAXN_SUPER on this unit)

- `nvpmodel -q` on device lists only modes 0 = 15 W (max) and 1 = 7 W. CLAUDE.md mention of 25 W MAXN_SUPER does not apply to this board/firmware. All Phase-4 evals at mode 0 + `jetson_clocks` locked.

### 2026-06-18T00:55 — mmproj reuse: regenerate from merged checkpoint (bit-equivalent to base)

- Vision frozen in Phase-3 → mmproj tensors unchanged from base. Confirmed by identical byte size (1334666400 B). Regenerated for self-contained provenance; one mmproj serves base and fine-tune.

### 2026-06-18T01:00 — Jetson 8 GB OOM fix: `-np 1 --cache-ram 0 --no-cache-idle-slots`

- **Why:** Default `--cache-ram 8192 MiB` on unified 8 GB collides with model weights + KV + CUDA context. F16 eval crashed at sample 64/439 (server SIGKILL). Fix: stable ~5.8 GB RSS, ~1.3 GB headroom. Single-stream eval needs no multi-slot or prompt caching.

### 2026-06-18T01:15 — Phase 4 gate runs on the Jetson, not local CPU

- **Why:** Jetson is the deployment target; CUDA = seconds/sample vs CPU-hours; same pinned llama.cpp commit. Trusting HF number without on-device eval is exactly the Part-I mistake (−23 pp gap invisible until measured on real backend).

### 2026-06-18T01:30 — Phase 4 PASS: Q8_0 as deployment artifact; Part-I fidelity gap eliminated ★

- **Results (Orin Q8_0, 15 W, n=439 RefDrone val):** HF 59.5% → F16 **62.2%** (−2.7 pp runtime gap) → Q8_0 **62.6%** (−0.5 pp quant gap). Both clear the 57.5% fidelity floor. Q8_0 chosen over F16: 1.65 vs 3.09 GB at indistinguishable accuracy.
- **Significance:** SmolVLM/Idefics3 had −23 pp runtime + −7 pp quant. Qwen2-VL = −2.7 pp. Phase-0 spine selection eliminated the binding constraint. **Phases 0–4 all green.**

