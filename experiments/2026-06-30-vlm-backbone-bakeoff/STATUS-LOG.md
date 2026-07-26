# 2026-06-30-vlm-backbone-bakeoff — session log

*Split out of `README.md` on 2026-07-26: this is the blow-by-blow of how the
campaign was run (launches, deviations, false starts, version pins). The README
keeps the closing entries and the verdict. Cite by quoted string, not line number
(HANDOFF invariant I8).*

- **2026-06-30T14:03Z — pre-registered, nothing run.** Suite + config + estimates frozen above.
- **2026-06-30T14:50Z — arm A (InternVL3-2B) FT LAUNCHED on the 3090.** Harness validated end-to-end
  for an off-Qwen architecture (dry-run loss=1.89, LoRA 20.8M / 0.99% trainable). lr sweep
  {1e-4,2e-4,4e-4} running under the crash-resistant launcher. Throughput ~1.06 step/s →
  ~65 min/epoch, ~3.2 h/lr, **~10 h for the full arm-A sweep**. Logs: `raw/internvl3-2b-sweep.log`.

  **Per-arm harness deviations discovered + applied (logged confounds, not controls):**
  - `OpenGVLab/InternVL3-2B-hf` (transformers-native `internvl`, loads through the generic
    `AutoModelForImageTextToText` harness — no trust_remote_code). LLM is Qwen2-based so the
    default LoRA targets (`q/k/v/o_proj`, `gate/up/down_proj`) matched and skipped the InternViT
    vision tower by construction (`freeze_vision` holds).
  - **`max_seq_len=4096`** (new `TrainConfig` field; Qwen baseline stays at 1280). InternVL
    dynamic-tiles @1024 long-edge → **measured 817..3385 tokens, median ~2100** over 30 train
    samples; the Qwen-tuned 1280 cap truncated the vision span and broke image-token alignment.
    This high token count is itself a **speed signal** for the Jetson latency stage (RQ-B.1).
  - **`gradient_checkpointing=True` + `batch_size=1` / `grad_accum=16`** (effective batch still 16).
    The ~2-3k-token sequences OOM'd at batch 2 on the 24 GB 3090 (245 MiB short at peak); both
    new `TrainConfig` knobs are off/baseline-default for Qwen so the incumbent run is byte-identical.

- **2026-06-30T15:55Z — arm A lr=1e-4 epoch-1 eval (health PASS).** parse=100%, IoU@0.25=29.0%
  (already > 20% gate at epoch 1/3), mean_iou=0.170, center_std=22.7 ≈ GT 22.9 → fully input-dependent,
  no mode collapse. Sweep continues (epochs 2-3, then lr=2e-4, 4e-4).
- **2026-06-30T18:01Z — arm A lr=1e-4 sweep leg COMPLETE** (merged + `DONE`). Per-epoch IoU@0.25:
  E1 29.0% → **E2 37.0%** → E3 35.5% (slight overfit past E2; early-stop pick = **E2 37.0%**,
  mean_iou=0.236). parse=100% all epochs, center_std 22.5-22.8 ≈ GT 22.9 throughout. lr=2e-4 leg
  now training (E1 loss=2.26 from fresh adapter). Best-of-sweep TBD after lr=2e-4, 4e-4.
- **2026-06-30T21:15Z — arm A lr=2e-4 sweep leg COMPLETE.** Per-epoch IoU@0.25: E1 27.5% →
  E2 36.5% → **E3 42.0%** (monotonic — unlike lr=1e-4 it kept climbing, best = E3, mean_iou=0.262).
  parse=100% all epochs, center_std 21.6-24.5 ≈ GT 22.9. **New sweep best: 42.0% (lr=2e-4 E3)**,
  +5pp over lr=1e-4's peak — the higher lr learns better here. lr=4e-4 (final leg) next; the
  climbing-to-E3 shape suggests 4e-4 may want >3 epochs, but epochs are fixed at 3 (pre-registered).
- **2026-07-01T08:55Z — arm A (InternVL3-2B) SWEEP COMPLETE. Winner: lr=4e-4 E3 = 47.5%.**
  Full per-epoch IoU@0.25 grid (parse=100%, center_std 21.6-24.5 ≈ GT 22.9 throughout — no collapse anywhere):

  | lr | E1 | E2 | E3 | best | shape |
  |---|---|---|---|---|---|
  | 1e-4 | 29.0 | **37.0** | 35.5 | 37.0 | peaks E2, slight overfit |
  | 2e-4 | 27.5 | 36.5 | **42.0** | 42.0 | monotonic |
  | 4e-4 | 30.0 | 43.5 | **47.5** | **47.5** | monotonic, steepest |

  **Read:** accuracy rises with lr across the whole swept range; the best leg (4e-4) was still
  climbing at E3 (+4pp E2→E3), so 3 epochs is likely **undertrained** for InternVL3-2B — the 47.5%
  is a *floor*, not a converged number. **Caveat for the cross-arm comparison:** 47.5% sits well
  below the Qwen2-VL-2B incumbent (Phase-3 LoRA 59.5% HF / 62.6% Q8_0 Jetson) at the same r=16 LoRA /
  3-epoch / lr-swept protocol — arm A (the strongest prior) **underperforms the incumbent** under the
  pre-registered budget. The undertraining flag + 4e-4-edge-of-grid both say the protocol may be
  pinching InternVL specifically (its ~2-3k-token tiled sequences see fewer effective updates/epoch);
  record as a confounded loss, not a clean one. Final whole-frame re-score of the merged lr=4e-4
  ckpt running now (authoritative number for the RESULTS row).
- **2026-07-01T09:10Z — arm A authoritative accuracy = 48.5%** (whole-frame re-score of the merged
  lr=4e-4 ckpt: n=200, parse=100%, IoU@0.25=48.5%, mean_iou=0.298, center_std=22.3; ~1pp over the
  in-loop E3 = greedy-decode noise on merged-vs-adapter weights). Arm A accuracy half DONE; its
  Jetson export+latency half is **blocked** on the open llama.cpp-internvl-mmproj question (separate
  workstream, not gating the rest of the sweep).
- **2026-07-01T09:12Z — arm B (Qwen2.5-VL-3B-Instruct) FT — OOM on first launch, fixed, relaunched.**
  First launch mirrored the incumbent exactly (batch 2 / grad_accum 8 / **no** grad-ckpt / max_seq_len
  1280). The forward-only `--dry-run` PASSed (LoRA 37.2M / 0.98% trainable, loss=5.30) but the **batch-2
  backward OOM'd by 72 MiB** on the 3090's 24 GB at step <50 — a forward-only dry-run can't see the
  backward's activation peak. **Fix:** `gradient_checkpointing=True` (recompute activations in backward,
  frees several GB); kept batch 2 / ga 8, so the *only* new confound vs the 2B incumbent is grad-ckpt,
  not the batch size. Relaunched (PID 286757); now stepping past the OOM point (2051 steps/epoch = 4101/2
  confirms batch 2; GPU 23.2/24 GB, holding). **Lesson logged:** the bake-off dry-run gate is forward-only
  and under-tests memory for ≥3B arms — treat first-50-steps as the real OOM gate. lr sweep {1e-4,2e-4,4e-4},
  log `raw/qwen2.5-vl-3b-sweep.log`. The only clean deltas vs the 62.6% baseline remain +1B params + the
  Qwen2.5 vision encoder (+ grad-ckpt, which is numerically ~neutral).
- **2026-07-01T12:20Z — arm B lr=1e-4 leg COMPLETE.** Per-epoch IoU@0.25: E1 **56.0%** / E2 55.0% /
  E3 55.5% (@0.25 saturates ~55-56%; mean_iou climbs 0.352 → 0.384 → 0.413 = boxes tightening under a
  flat threshold count). parse=100%, center_std 21.6-22.3 ≈ GT 22.9. Best = E1 56.0%. Already far above
  arm A's whole sweep (best 47.5%) and near the 62.6% incumbent — **on lr=1e-4, which for arm A was the
  weakest leg** (+10pp came from 2e-4/4e-4). lr=2e-4, 4e-4 legs next; if the arm-A lr-shape repeats,
  arm B's best could clear the incumbent.
- **2026-07-01T14:05Z — arm B lr=2e-4 leg COMPLETE.** Per-epoch IoU@0.25: E1 48.0% / E2 **60.5%** /
  E3 59.0% (mean_iou monotonic 0.312 → 0.444 → 0.453, but @0.25 turned over at E2 — E3's tighter
  mean box didn't add threshold-crossers). parse=100%, center_std 22.0-22.2 ≈ GT 22.9. Best =
  E2 60.5%, +4.5pp over the lr=1e-4 leg (56.0%) and 2.1pp under the 62.6% incumbent. The arm-A
  lr-shape repeats (2e-4 > 1e-4); **lr=4e-4 (final leg) is the one that could clear the incumbent.**
- **2026-07-01T16:12Z — arm B (Qwen2.5-VL-3B) SWEEP COMPLETE. Winner: lr=2e-4 E2 = 60.5%.** Full grid
  (IoU@0.25 per epoch): lr=1e-4 56.0/55.0/55.5 (best E1), lr=2e-4 48.0/**60.5**/59.0 (best E2), lr=4e-4
  49.5/58.5/59.5 (best E3). parse=100% throughout, center_std 20.7-22.3 ≈ GT 22.9 (no collapse). Unlike
  arm A (monotonic, 4e-4 steepest), arm B **peaks at lr=2e-4** and plateaus ~58-60% across 2e-4/4e-4 —
  it saturates the @0.25 metric near 60% and higher lr just trades E2↔E3 placement (lr=4e-4 E3 has the
  tightest boxes, mean_iou=0.489, but not more @0.25 crossers). **Best 60.5% lands 2.1pp under the 62.6%
  Q8_0 incumbent** under the same fixed 3-epoch budget — the extra 1B params + grad-ckpt do NOT beat the
  2B incumbent on accuracy here. Whole-frame re-score of the winning lr=2e-4 merged checkpoint (final-epoch
  E3 merge, not the E2 peak): n=200, parse=100%, **IoU@0.25=58.0%**, mean_iou=0.447, center_std=22.1.
  Caveat mirrors arm A: the in-loop early-stop pick (E2 60.5%) and the re-scored artifact (E3 58.0%)
  differ because the merge saves the last epoch, not the best — the deployable number is the 58.0%
  re-score unless we re-merge E2. Next: arm C (PaliGemma2-3B@448, grad-ckpt pre-set) on the freed GPU;
  arm B Jetson export+latency is a bf16 3B GGUF (Qwen2.5-VL is llama.cpp-supported, unlike arm A's InternVL).

  **Crash-resistance infra (per user requirement, 2026-06-30):** added to the shared trainer —
  atomic mid-epoch adapter save every 300 steps (`latest/`), atomic per-epoch adapters (`epochN/`,
  the resume source), **epoch-level resume** on restart (warm-start from highest `epochN`, bounds a
  crash to <1 epoch ≈ 65 min), append-mode CSVs (no truncation on crash), per-lr `DONE` sentinel so
  the sweep skips finished lrs, and `launch_arm.sh` (8-retry auto-restart). Verified: `latest/`
  landed atomically at step 300, no `.tmp` leftover.
- **2026-07-01T11:35Z — arm C (PaliGemma2-3B pt-448) FT LAUNCHED on the 3090.** Dry-run PASS
  (loss=2.97, LoRA 23.8M / 0.777% trainable, grad-ckpt on). lr sweep {1e-4,2e-4,4e-4} running under
  the crash-resistant launcher; E1 loss 3.19 → ~1.17 by step 450. Throughput ~1.52 s/step @220W
  (see fan note) → ~52 min/epoch, ~2.6 h/lr, **~8 h for the full arm-C sweep**. Logs:
  `raw/paligemma2-3b-sweep.log` (note: PaliGemma's processor prints a per-collate "passing both text
  and images" notice that neither `TRANSFORMERS_VERBOSITY=error` nor a `warnings` filter suppresses —
  cosmetic; grep `E[0-9] step` for the loss trend).

  **Per-arm harness deviation (logged confound):** PaliGemma has **no chat template**. The shared
  trainer + eval backends now branch on `processor.chat_template is None` → PaliGemma-native path:
  plain prompt (no `apply_chat_template`), target passed as `suffix=` so the processor builds the
  masked `labels` itself (prefix+image −100, suffix supervised, `<eos>` appended), and plain-prompt
  generation at eval. Text backbone is Gemma2, so the default LoRA targets (`q/k/v/o_proj`,
  `gate/up/down_proj`) matched and the SigLIP vision tower stayed frozen by construction. Fixed
  448×448 square input (processor squishes regardless), but coords are normalized `[0,100]` to the
  original image → scale-invariant, **no coordinate confound** from the squish. The `chat_template is
  None` branch is inert for the Qwen incumbent (byte-identical path preserved). Gated model: launcher
  exports `HF_TOKEN` from `.hugging-face-token`.

- **2026-07-01T11:20Z — GPU fan/power finding (train box, RTX 3090, driver 595).** User asked to run
  fans at ~80% (93% under load is too loud). **`GPUTargetFanSpeed` is firmware-blocked on this card:**
  Coolbits=4 is active (`/etc/X11/xorg.conf.d/20-nvidia-coolbits.conf`, confirmed in Xorg.0.log) and
  `GPUFanControlState=1` assigns cleanly, but every `GPUTargetFanSpeed` assignment throws "Unknown
  Error" — even under load, both fans, standalone or combined. The attribute reads/queries fine and
  claims writable (range 0–100, target type Fan); the driver/VBIOS just rejects the write. No
  nvidia-settings path exists; `coolgpus` / a second X on `:1` also fail (`:0` holds DRM master).
  **Power cap is the only working noise lever** (auto fan curve tracks temp): measured 260W→93% fan
  / 1.33 s·step⁻¹, 230W→~83% / ~1.4, **220W→~75% / 1.52 (chosen)**, 200W→60% / 1.6 (a sharp curve step
  sits between 200–230W). Set `sudo nvidia-smi -pl 220` for the rest of the campaign: ~75% fan at
  ~14% throughput cost. Fan reverted to auto (`GPUFanControlState=0`) — never left in manual with no
  valid target. Not persistent across reboot; re-apply `-pl 220` if the box restarts mid-campaign.
- **2026-07-01T12:10Z — arms D/E scoped + arm B export blocker found (parallel prep while C trains).**
  CPU-side probes (no GPU contention) locked the remaining arms:
  - **Arm E = `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`** (`smolvlm`, Llama text backbone).
    SmolVLMProcessor HAS a chat template → **fits the shared harness unchanged** (same path as the
    Qwen incumbent / arm B); LoRA targets match, vision frozen by construction. Config written
    (`configs/smolvlm2-500m.py`). Two notes: (1) its processor hard-depends on **`num2words`** —
    installed into `.venv-ft`, added to `requirements-ft.txt` (run `make lock` to pin); (2) the
    pre-registered "384-tile" is wrong for this checkpoint — its native tile is **512**
    (`max_image_size.longest_edge=512`), so `image_size=512` (one native tile, speed-floor intent).
    Token count / fit to be confirmed by a dry-run before launch (GPU-gated on arm C finishing).
  - **Arm D = `microsoft/Florence-2-large`** confirmed **encoder-decoder** (`florence2` /
    `florence2_language`), no chat template, native `<loc_N>` output. It does **not** load through the
    causal `AutoModelForImageTextToText` harness — needs the pre-registered separate **Seq2Seq** path
    (HF `Seq2SeqTrainer` or a custom enc-dec loop) plus a decision on native-loc vs terse-int contract.
    The hardest arm; build deferred until the GPU frees (validation is GPU-gated).
  - **Arm B Jetson export BLOCKER:** the pinned converter `/tmp/llama.cpp-57fe1f0/convert_hf_to_gguf.py`
    is **gone** (tmp cleared on the reboot). Export needs llama.cpp re-cloned at commit `57fe1f0`, AND
    whether that pinned commit supports **Qwen2.5-VL** vision-tower mmproj is **unverified** (the
    incumbent was Qwen2-VL, older) — a potential pinned-commit wall analogous to arm A's InternVL
    uncertainty. Logged; conversion is CPU-side (GPU-free) once the converter is restored.
- **2026-07-01T12:07Z — arm B Jetson export FIXED + bench running; arm A deployment BLOCKED (characterized).**
  Both prior blockers resolved to root cause; llama.cpp re-cloned at `57fe1f0` and **verified end-to-end**
  (converter `conversion/qwenvl.py` registers `Qwen2_5_VLForConditionalGeneration`; runtime `clip.cpp`/
  `mtmd.cpp` handle both `QWEN25VL` and `INTERNVL` projector types; Jetson build is at the exact same
  commit `57fe1f0…`).
  - **Arm B export cause of earlier exit-1:** the `to_gguf` wrapper shells out to bare `python`, which
    resolved to the system pyenv (no torch) instead of `.venv-ft`. Fix: run the export with `.venv-ft/bin`
    on `PATH`. All three GGUFs then built clean (Q8_0 3.1 GB, f16 5.8 GB, mmproj-f16 1.3 GB). **Arm B
    dual-path Jetson bench is running now** (n=439, Q8_0, whole-frame 1024 + ROI M=2.0@512) via the new
    `jetson_bench.py` driver (deploys, serves `llama-server` ngl=99, loops `generate_stats` so IoU +
    prefill/decode/wall come from one pass). Early read (n=43 WF): IoU@0.25 ≈ 46%, wall ≈ 6000 ms — i.e.
    the 3B is both **less accurate and slower** than the 2B incumbent (63.1% / 4400 ms). Full numbers land
    in the Results table.
  - **Arm A (`InternVL3-2B-hf`) Jetson export BLOCKED — format incompatibility at the pinned commit (a
    documented negative, not a transient).** InternVL *is* supported by `57fe1f0` (both converter and
    runtime), but the **transformers-native `-hf` checkpoint layout doesn't match the converter's
    expectations**: (1) mmproj — the InternVL mmproj filter accepts only `model.vision_tower.*` /
    `model.multi_modal_projector.*`, while our merged checkpoint uses top-level `vision_tower.*` /
    `multi_modal_projector.*` (no `model.` prefix) → **zero vision tensors matched** (`n_tensors=0`,
    empty mmproj); (2) LLM half — the converter takes the SentencePiece path and dies on a missing
    `tokenizer.model`, which the Qwen2-BPE backbone doesn't ship. Deploying arm A would require either
    **patching the pinned converter** (breaks the "same commit as the Jetson build" invariant — a
    controlled variable) or **checkpoint-key surgery + tokenizer grafting** on the *worst-performing arm*
    (48.5% WF, well below the 62.6% incumbent), risking a silently-misaligned GGUF (a wrong latency
    number is worse than none). Decision: **record the blocker with root cause, latency = N/A (not
    stack-native-deployable at `57fe1f0` without format surgery).** Arm A is thus a double negative —
    accuracy laggard *and* off-stack to deploy — so it is not a spine candidate regardless. (This is the
    "off-stack deployment effort" the Risks section pre-registered for C/D, biting A too.) Empty partial
    GGUF removed.
- **2026-07-01T15:05Z — arm B dual-path bench DONE + ROI collapse VERIFIED; arm A/B Results rows filled.**
  Full n=439 Jetson Q8_0 (`raw/qwen2.5-vl-3b-jetson.json`): **WF** parse=100%, IoU@0.25=**53.1%**,
  mean_iou=0.399, center_std=21.6, prefill 837 tok/5002 ms, decode 12 tok/842 ms, wall 5990 ms; **ROI
  M=2.0@512** parse=100%, IoU@0.25=**33.0%**, mean_iou=0.170, center_std=22.9, prefill 385 tok/1916 ms,
  decode 12 tok/838 ms, wall 2817 ms. The ROI number **inverts** the incumbent ordering (2B: ROI 85.2% >>
  WF 63.1%; 3B: ROI 33.0% << WF 53.1%), so per the no-unverified-claims rule I cross-checked it against the
  **canonical harness** (`harness.evaluate` + `roi.evaluate_roi`, independent of `jetson_bench.py`): n=40 gave
  WF 42.5% / ROI 20.0% — same collapse, **confirmed real**. Recorded arm B's two rows + arm A's accuracy-only
  row (latency=N/A-blocked) in the Results table and wrote Findings. Arms A and B are both **eliminated**.
- **2026-07-01T15:05Z — infra fix: stray root `runs/` leak closed.** `manifest.write(runs_dir="runs")`
  defaults to a *cwd-relative* path; drivers launched from the repo root (this campaign's `trainer` / `to_gguf`)
  leaked provenance to `/home/gara/jetson/runs/` instead of the experiment tree (the sibling
  `whole-frame-resolution` experiment avoided it only because it ran from *inside* its own dir). Fix:
  `trainer.py` and `to_gguf.py` now pass a config-derived `runs_dir` (the run's `output_dir` / exported
  `checkpoint`) so the manifest co-locates with its artifact, cwd-independent; added `/runs/` to `.gitignore`
  as a guard (root `/runs/` is always a leak); moved the 7 stray records into
  `runs/<arm>/<lr>/<id>/`. Caveat: arm C's *already-running* process still has the old code in memory, so
  its remaining per-lr manifests re-leak to root until relaunch — harmless (guarded), re-swept at sweep end.
- **2026-07-01T15:25Z — arm D contract DECIDED + CPU-validated bridge landed (GPU-free prep during the
  arm-C wait).** Resolved the open "native-loc vs terse-int" question: **score Florence-2 in its NATIVE
  `<loc_N>` format and convert to the shared IoU space**, not force the terse-int target on it. Rationale:
  the RQ is "which backbone locates best per Jetson-second"; target format is each architecture's native
  interface, so evaluate every arm at its strength and compare on the format-agnostic IoU@0.25 (arms A/B
  already showed a foreign contract handicaps a backbone). Given up: target-format is no longer held constant
  across arms. Built + **CPU-validated the contract bridge** `florence_loc.py` (render GT→`<loc_N>`, parse via
  the processor's own `post_process_generation`); because loc bins are resolution-independent fractions, both
  directions run in the [0,100] contract space via `image_size=(100,100)`, so Florence output lands directly
  on `GroundingSample.bbox`. Self-check round-trips at ≤0.05-unit drift (half a loc bin). Wrote
  `configs/florence2-large.py` (image_size 768, BART-decoder LoRA surface). The enc-dec **training driver**
  (`run_florence.py`) is deliberately deferred until the GPU frees — it can only be validated live, so it is
  not written blind. Confirmed on CPU: Florence has 1000 `<loc_*>` tokens, `chat_template is None` (would
  mis-route through the shared trainer's PaliGemma `suffix=` branch → separate driver required),
  `AutoModelForCausalLM(trust_remote_code=True)`.
- **2026-07-01T17:55Z — arm C DONE (eliminated); arm E LAUNCHED; arm D driver written + CPU-validated.**
  - **Arm C (PaliGemma2-3B@448) complete.** Sweep winner **lr=2e-4, in-loop IoU@0.25 = 57.0%** (E3;
    lr1e-4 51.5%, lr4e-4 50.5% — 2e-4 clearly best, all monotonic to E3). Whole-frame re-score of the
    winning merged E3 checkpoint: n=200, parse=100%, **IoU@0.25 = 56.0%**, mean_iou=0.391, center_std=22.1.
    **−6.6pp under the 62.6% incumbent** — the strongest non-baseline arm so far but still below it. FT
    wall ≈2.6 h/leg (est ~2–2.5h, in range). Row filled. Jetson export (TensorRT/ONNX, off-stack like A)
    still pending — latency TBD. Same in-loop-peak vs re-score caveat as A/B (merge saves last epoch = the peak here, so no gap).
  - **Waiter bug fixed (root cause of the earlier missed notification).** The background completion
    waiter used `pgrep -f "run_arm.py --arm paligemma2-3b"`, whose pattern **matched the waiter's own
    command line** → the `until ! pgrep` loop never exited (self-match). Killed it manually; arm C's
    python had already exited cleanly. New waiters watch the launcher **PID** (`kill -0 $PID`), which
    cannot self-match. Also swept one fresh root `runs/` leak from arm C's old in-memory code into
    `runs/paligemma2-3b/lr0.0004/`; root `runs/` now clean.
  - **Arm E (SmolVLM2-500M) LAUNCHED on the 3090.** Dry-run initially failed: SmolVLM/Idefics3
    processors need `images` grouped **per-text** (list-of-lists), not the flat list Qwen2-VL (arm B)
    takes — added a `_images_arg()` branch (keyed on processor class name) in both the trainer collate
    and `eval/backends.py` so the fix doesn't touch the already-passed arms. Dry-run then PASS (loss=2.76,
    LoRA 9.6M / 1.85% trainable). Sweep {1e-4,2e-4,4e-4} running under the crash-resistant launcher; E1
    loss 2.12 → 1.12 by step 300. Throughput ~1.6 s/step → ~55 min/epoch, **~8 h for the full sweep**
    (the 500M is small per-param but still 3 lr × 3 epochs × 2051 steps). Logs: `raw/smolvlm2-500m-sweep.log`.
  - **Arm D (Florence-2) driver written + CPU-validated (`run_florence.py`).** The pre-registered enc-dec
    Seq2Seq path: `AutoModelForCausalLM(trust_remote_code=True, attn_implementation="eager")` (Florence's
    old remote modeling lacks `_supports_sdpa`), a Florence collate (task-token+caption input, `caption<loc_N>`
    decoder labels via `florence_loc.render_target`), and a `FlorenceBackend` that generates loc tokens,
    parses via `florence_loc.parse_bbox`, and **returns the box as the terse-int string** so
    `harness.evaluate` + `contract.iou` + all crash-resistance/eval-CSV machinery are reused **unchanged**.
    LoRA is scoped to the `language_model` subtree by full-name match (DaViT's MLP also uses `fc1/fc2`, so a
    bare suffix list would leak into the vision tower and break freeze_vision). Two fixes found during CPU
    validation: (1) Florence remote code needs **`einops` + `timm`** — installed into `.venv-ft`, added to
    `requirements-ft.txt` + pinned in the lock (einops 0.8.2, timm 1.0.27); (2) Florence doesn't cast
    `pixel_values` to the weight dtype (Qwen did internally) → explicit bf16 cast in collate + generate.
    CPU dry-run gets past load / LoRA-scoping / collate / into the forward cleanly (bf16 CPU forward is just
    slow); **final live validation is GPU-gated behind arm E.** `launch_arm.sh` now takes an optional driver
    arg (`run_florence.py`) so arm D reuses the same 8-retry restart + epoch-resume wrapper.
