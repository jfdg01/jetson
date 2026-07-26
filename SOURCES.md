# SOURCES

External papers, models, and datasets we cite or use. One entry per source:
the link, and **where it was used** (experiment/Part). No descriptions —
the per-experiment README is the source of truth. Append; newest at the bottom.

## Models

- **Swin2SR** — `caidas/swin2SR-realworld-sr-x4-64-bsrgan-psnr`
  https://huggingface.co/caidas/swin2SR-realworld-sr-x4-64-bsrgan-psnr ·
  https://arxiv.org/abs/2209.11345
  → [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)

- **InternVL3-2B** — `OpenGVLab/InternVL3-2B-hf`
  https://huggingface.co/OpenGVLab/InternVL3-2B-hf
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm A

- **Qwen2.5-VL-3B-Instruct** — `Qwen/Qwen2.5-VL-3B-Instruct`
  https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm B

- **PaliGemma2-3B (pt-448)** — `google/paligemma2-3b-pt-448`
  https://huggingface.co/google/paligemma2-3b-pt-448
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm C

- **Florence-2-large** — `microsoft/Florence-2-large`
  https://huggingface.co/microsoft/Florence-2-large
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm D (cancelled un-run)

- **SmolVLM2-500M-Video-Instruct** — `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`
  https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm E

- **CLIP ViT-L/14 + ViT-B/32** — `openai/clip-vit-large-patch14` · `openai/clip-vit-base-patch32`
  https://huggingface.co/openai/clip-vit-large-patch14 ·
  https://huggingface.co/openai/clip-vit-base-patch32
  → [`experiments/2026-07-14-crop-select/`](experiments/2026-07-14-crop-select/README.md) P5.4
  crop-scoring pilot + recorded secondary arm (design-time pilot found vanilla crop scoring
  size-biased on 16-100 px aerial crops)

## Papers / surveys

- **Advancing Image Super-resolution Techniques in Remote Sensing: A Comprehensive Survey**
  https://arxiv.org/pdf/2505.23248
  → [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)

- **Small Object Detection: A Comprehensive Survey on Challenges, ...**
  https://arxiv.org/pdf/2503.20516
  → [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)

- **EDiffSR: An Efficient Diffusion Probabilistic Model for Remote Sensing Image Super-Resolution**
  https://arxiv.org/pdf/2310.19288
  → [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)

- **ReCLIP: A Strong Zero-Shot Baseline for Referring Expression Comprehension**
  (Subramanian et al., ACL 2022) · arXiv 2204.05991
  https://arxiv.org/abs/2204.05991
  → [`experiments/2026-07-14-crop-select/`](experiments/2026-07-14-crop-select/README.md) — the
  IPS proposal-scoring method (crop + Gaussian-blur sigma=100 isolation, summed CLIP logits)
  piloted for P5.4 candidate select; falsified at design time on small aerial crops.

- **What does CLIP know about a red circle? Visual prompt engineering for VLMs**
  (Shtedritski et al., ICCV 2023) · arXiv 2304.06712
  https://arxiv.org/abs/2304.06712
  → [`experiments/2026-07-14-crop-select/`](experiments/2026-07-14-crop-select/README.md) — the
  red-circle visual prompt behind the pilot-winning `circlectx` variant (P5.4 secondary arm).

## Datasets

- **RefDrone** — `sunzc-sunny/RefDrone`
  https://huggingface.co/datasets/sunzc-sunny/RefDrone
  → Part II / Part III grounding eval

- **AerialMind** (AAAI 2025) — `shawnliang0420/AerialMind` · arXiv 2511.21053
  https://huggingface.co/datasets/shawnliang0420/AerialMind ·
  https://github.com/shawnliang420/AerialMind
  → [`docs/dataset-survey-refdrone.md`](docs/dataset-survey-refdrone.md) §4 — candidate
  Part III/IV temporal (RMOT) dataset. Academic-only (VisDrone NC-SA chain).
- **SAM2.1 (hiera-tiny)** — `facebook/sam2.1-hiera-tiny` · `sam2==1.1.0` ·
  https://github.com/facebookresearch/sam2 — zero-shot memory-carry tier of the temporal
  acquire-carry campaign (video predictor: box prompt → per-frame mask propagation).
- **SAM2.1 (hiera-small)** — `facebook/sam2.1-hiera-small` · `sam2==1.1.0` ·
  https://huggingface.co/facebook/sam2.1-hiera-small — larger (46M vs 38.9M params) carry
  checkpoint, the capacity arm of the P5.20 A/B
  ([`experiments/2026-07-20-carry-capacity/`](experiments/2026-07-20-carry-capacity/README.md)) and
  of EXP-9's 2x2
  ([`experiments/2026-07-26-encoder-runtime-capacity/`](experiments/2026-07-26-encoder-runtime-capacity/README.md)).
  **Not deployed.** EXP-9 closed the gate P5.20 left owed — it is TensorRT-exported (`enc640_small.plan`)
  and FPS-gated on-device: it fits (547 MB peak CUDA) and clears 5 Hz (5.38), but does not win
  accuracy (delta +0.0003 [−0.0046, +0.0036], b=2/c=0 at the 6 discordant pairs n=38 needs), so G3
  is a keep-tiny. Its one real advantage is re-find, 16/110 vs tiny's 3/129.
- **SAM2.1 (hiera-base-plus)** — `facebook/sam2.1-hiera-base-plus` · `sam2==1.1.0` ·
  https://huggingface.co/facebook/sam2.1-hiera-base-plus — 80.8M-param carry checkpoint, measured
  once in EXP-9's Stage 0 census. Pulled in specifically to replace an inherited assumption with a
  measurement: P5.20 rejected it at design time as undeployable, and it in fact **loads and steps
  co-resident with the q8_0 VLM on 8 GB with 1059 MB to spare**. Rejected on **rate** instead —
  241.8 ms/step = 4.14 Hz, under E1's ≥ 5 Hz co-resident gate.

- **UAV123** — aerial single-object-tracking benchmark (Mueller et al., ECCV 2016) ·
  https://cemse.kaust.edu.sa/ivul/uav123 · mirror
  https://huggingface.co/datasets/xche32/UAV123
  → [`experiments/2026-07-03-real-video-replay/`](experiments/2026-07-03-real-video-replay/README.md)
  — real-footage GT (per-frame `x,y,w,h`, 30 fps) for the E18 wall-clock replay scoring.

- **Gazebo Fuel "Hatchback" model** (OpenRobotics / Nate Koenig, `nate@osrfoundation.org`) ·
  https://app.gazebosim.org/OpenRobotics/fuel/models/Hatchback · vendored under
  [`runners/sitl/models/hatchback_{white,blue,red}/`](runners/sitl/models/) (three copies of the same
  mesh; `map_Kd`/`map_Ka` rewritten from remote Fuel URLs to local paths)
  → [`experiments/2026-07-17-sim-scenegen/`](experiments/2026-07-17-sim-scenegen/README.md) — the
  colour-distinct same-class vehicle assets for the P5.7 select-arena scene generator. **Note:** the
  vendored textures do **not** load under this rig (the Fuel "Hatchback blue" material even points at
  the *white* model's texture), and localising the map paths still rendered the body white — vehicle
  colour therefore comes from a solid `<material>` override in the spawn SDF, not from the model's
  textures (P5.7 design finding, `curation/probe_texture_stays_white.png`).

- **Gazebo Sim 8.14.0 (Harmonic)** · https://gazebosim.org/docs/harmonic — headless simulator
  (`gz sim -s` + Sensors/ogre2 + EGL) behind the P5.7 scene generator
  ([`runners/scenegen.py`](runners/scenegen.py),
  [`runners/sitl/worlds/select_arena.sdf`](runners/sitl/worlds/select_arena.sdf)). P5.7 found its
  `gz service` CLI request path unreliable under per-frame churn (~0.42%/call `RecvSrvRequest() ...
  Host unreachable`), which is what blocked that campaign — see the experiment README.

- **CARLA 0.9.16** (Dosovitskiy, Ros, Codevilla, López, Koltun — *CARLA: An Open Urban Driving
  Simulator*, CoRL 2017; originating at CVC Barcelona) · https://carla.org ·
  paper https://arxiv.org/abs/1711.03938 · packaged Linux release
  `CARLA_0.9.16.tar.gz` (8346095504 bytes) from https://tiny.carla.org/carla-0-9-16-linux,
  installed to `~/carla/CARLA_0.9.16/` (outside the repo); client `carla==0.9.16` (cp312 wheel,
  zero transitive deps) pinned in `requirements-ft.txt`
  → [`experiments/2026-07-20-p61-carla-renderer/`](experiments/2026-07-20-p61-carla-renderer/README.md)
  — the Part VI renderer, replacing Gazebo as the pose-slaved view. Used for its photoreal Unreal
  Engine towns (`Town10HD_Opt`), autonomous traffic manager, and Python API; SITL remains the
  physics and the control stack is unchanged. **Version note:** 0.9.16 is the first release with
  cp312 wheels (0.9.15 stops at cp310), and 0.10.0 has a newer tag but an *older* release date
  (2024-12-19 vs 2025-09-16) and moved to UE5 with a reduced map set.

- **"A Step-by-Step Guide to Creating a Robust Autonomous Drone Testing Pipeline"** (Jiang, Deng,
  Schroder et al., Macquarie University; arXiv 2506.11400v1, 2025) ·
  https://arxiv.org/abs/2506.11400 · https://arxiv.org/html/2506.11400v1
  → [`experiments/PART6-PROPOSAL-closed-loop-flight.md`](experiments/PART6-PROPOSAL-closed-loop-flight.md)
  — **methodology reference only, no numbers taken from it.** A guide/survey paper (not a results
  paper: no latency, throughput or accuracy tables) proposing a four-stage drone validation pipeline
  — SIL (AirSim + Unreal + ROS) -> HIL (real PX4/ArduPilot flight controller, simulated sensors) ->
  controlled indoor real-world (safety nets + motion capture) -> in-field. Used here for two things:
  (1) it names the stage Part VI occupies — the `run_phase_c.py` rig (ArduCopter SITL as physics,
  CARLA as pose-slaved renderer, VLM->ByteTrack->PID->MAVLink closed) is textbook **SIL**, and
  Parts I-V sat *below* SIL entirely (replayed video, no vehicle in the loop), which is the gap P6.2
  closes; (2) its limitations section independently states the sim-to-real caveat this repo already
  measured — simulators "rely on generalized models rather than detailed, system-specific
  characterizations", and data-driven perception modules resist formal verification — matching the
  P5.17 finding that the reference contract grounds 56/56 clean sim renders, so sim select results
  do not transfer to real imagery. **Not adopted:** its perception is fiducial (ArUco) + TPH-YOLOv5,
  with no open-vocabulary or VLM grounding; its SIL simulator choice (AirSim) is superseded here by
  CARLA per P6.1; and its HIL stage needs Pixhawk hardware this project does not have and P6.2 does
  not require.
