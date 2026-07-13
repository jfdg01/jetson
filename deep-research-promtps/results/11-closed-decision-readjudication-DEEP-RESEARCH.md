# DR-11 — Deep Research result: re-adjudicating the closed small-VLM bake-off

Generated 2026-07-07 via deep-research harness (6 angles, 21 sources fetched, 81 claims
extracted, 25 adversarially verified 3-vote, 23 confirmed / 2 refuted). Model: claude-opus-4-8.

---

## Bottom line

The bake-off's core confound is **coordinate-format handling**. Nearly every competitor uses a
native localization format that is categorically different from the incumbent's free-text "terse
int" pixel strings. Feeding them the incumbent's format — or decoding their output with the
incumbent's parser — produces collapse-like scores that *mimic* capability loss but are recipe
bugs. Every rejection that turned on a shared coordinate parser or a fixed 512px feed is suspect.

---

## Per-model verdict

| Model | Verdict | Root cause | Fix to retest |
|---|---|---|---|
| **Qwen2.5-VL-3B** | **LIKELY PREMATURE** | Emits ABSOLUTE pixel coords as JSON (`bbox_2d`), not Qwen2-VL's normalized `[0,1000)`. A 0-1000 decode on 2.5-VL output — or a normalized-coord fine-tune — corrupts boxes into repetitive/empty predictions. Highest-probability format-mismatch victim. | Retest with absolute-pixel coords in native JSON, decoded against the smart_resize'd image dims. |
| **PaliGemma2-3B** | **LIKELY PREMATURE** (format + resolution) | Encodes boxes as 4 special `<loc0000>-<loc1023>` tokens on a 1024-bin normalized grid (order y1,x1,y2,x2) — cannot produce text integers at all. Also ships FIXED square res (224/448/896); the 512px feed is off-native in exactly the small-object regime it's built for. | Native `<loc>` tokens; feed at native 448 or 896, not 512. It's the base model in HF's official TRL grounding cookbook. |
| **Florence-2-large** | **UNJUSTIFIED SKIP — RUN IT** | Only 0.77B (~1.5GB fp16, trivial on 8GB Orin). Strong zero-shot REC: RefCOCO 56.3/61.6/51.4, RefCOCO+ 53.6/57.9/49.9, RefCOCOg 68.0/67.0 (Acc@0.5, so even higher at your looser IoU@0.25). Beats specialist SOTA UNINEXT by 0.8 when fine-tuned. | Own decoder (1000-bin loc-tokens, `post_process_generation`). LoRA on q/k/v/o_proj+linear+Conv2d+lm_head+fc2, r=8/α=8. Authors report a gain from **unfreezing** the vision encoder — your frozen-tower recipe likely understates it. |
| **SmolVLM2-500M** | **UNADJUDICATED** | No surviving evidence addressed SmolVLM2's capacity-collapse specifically. Cannot confirm or overturn. | Needs its own recipe search + rank/LR/target-module sweep before the rejection is fair. |
| **InternVL3-2B** | **UNADJUDICATED** | No surviving claim examined it. Uses its own dynamic-tiling + coordinate convention. | Was it rejected for a format/resolution reason too? Unknown — re-examine before closing. |

---

## Method finding (why the whole thing needs re-running)

Early-stopped, few-run comparison is itself a confound. Dodge et al. 2020 (arXiv 2002.06305):
same model, same hyperparameters, different random seeds → substantially different downstream
results; weight-init and data-order contribute comparably to variance; best-found-model quality
rises with trial count. **Early-stopping is safe only when each arm is already on its native,
correctly-configured recipe.** Here it baked in coordinate-format and resolution confounds — so
the ranking may reflect seed/harness luck, not capability.

---

## Minimal fair bake-off protocol

1. **Each model in its OWN native coordinate format** — Qwen2.5-VL absolute-pixel JSON, PaliGemma/Florence `<loc>` tokens, incumbent terse-int. Never a shared parser.
2. **At/near each model's native resolution** — dynamic for Qwen family; 448/896 for PaliGemma; don't force 512 on fixed-res models.
3. **Per-model-tuned LoRA**, including the vision encoder for the loc-token models (Florence authors show freezing hurts region-level tasks).
4. **Score in each model's own decoded pixel space** against GT, IoU@0.25.
5. **Multiple seeds per arm** — report variance, not a single run, before declaring a winner.

---

## Caveats (verbatim from the harness)

- Several load-bearing reproduction sources are practitioner blogs (Datature, Roboflow, HF blog), though the core facts trace to primary vendor docs / CVPR / arXiv.
- The Datature format-collapse evidence is from a dense-captioning/detection blog, not referring-grounding, and partly attributes the collapse to a training-loop bug — directional support, not proof, that the Qwen2.5-VL 33% is format-only.
- The unfreeze-vision-encoder recommendation was a **2-1** split (weaker consensus).
- All REC numbers are natural-image RefCOCO, NOT your UAV/aerial + small-target + terse-int regime — they establish "genuine contender worth running," not regime-specific performance.
- **Two claims refuted in verification:** (1) PaliGemma authors do NOT clearly reject LoRA — so "LoRA is off-recipe for PaliGemma" is unsupported. (2) The clean parse-vs-IoU separability test (a turnkey way to tell format-bug from real localization loss) did NOT hold up — there is no verified turnkey diagnostic.
- **Version-sensitive:** Qwen3-VL (post-cutoff) reportedly switched BACK to normalized [0,1000]; the absolute-vs-normalized advice is specific to Qwen2.5-VL.

## Open questions the research could not close

1. Is SmolVLM2-500M's collapse a genuine small-model grounding limit or an under-tuned LoRA? No evidence found — needs its own sweep.
2. Does the coordinate-format advantage survive on actual UAV/aerial small-target imagery? All numbers are natural-image RefCOCO.
3. What is a validated method to adjudicate "format bug vs real localization loss" for a single arm, given the separability test was refuted? A controlled format-swap ablation on a fixed model is the likely answer.
4. Was InternVL3-2B rejected for a format/resolution reason too? Unadjudicated.

## Key sources

- Qwen2.5-VL blog (absolute coords, stable JSON): https://qwenlm.github.io/blog/qwen2.5-vl/
- Qwen2-VL tech report (normalized [0,1000)): https://arxiv.org/html/2409.12191
- Qwen grounding format mismatch thread: https://github.com/QwenLM/Qwen2.5-VL/issues/866
- Qwen2.5-VL fine-tune coord-format reproduction: https://datature.io/blog/how-to-fine-tune-qwen2-5-vl
- PaliGemma architecture (`<loc>` tokens): https://developers.googleblog.com/gemma-explained-paligemma-architecture/
- PaliGemma paper (fixed res, small-object needs resolution): https://arxiv.org/html/2407.07726v1
- big_vision PaliGemma README: https://github.com/google-research/big_vision/blob/main/big_vision/configs/proj/paligemma/README.md
- HF TRL grounding cookbook: https://huggingface.co/learn/cookbook/en/fine_tuning_vlm_object_detection_grounding
- Florence-2 CVPR 2024 (REC numbers, loc-tokens): https://openaccess.thecvf.com/content/CVPR2024/papers/Xiao_Florence-2_Advancing_a_Unified_Representation_for_a_Variety_of_Vision_Tasks_CVPR_2024_paper.pdf
- Florence-2 LoRA recipe (Roboflow): https://blog.roboflow.com/fine-tune-florence-2-object-detection/
- Florence-2 unfreeze-encoder (HF blog): https://huggingface.co/blog/finetune-florence2
- Early-stopping variance (Dodge et al. 2020): https://arxiv.org/abs/2002.06305
