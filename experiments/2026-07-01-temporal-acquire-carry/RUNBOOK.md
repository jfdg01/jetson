# Executor runbook — finish temporal-carry, then E1/E2/E3

**Written:** 2026-07-02T10:51Z by the planning session. **Audience:** an executor model
(Opus/Sonnet). All decisions are pre-made; follow the IF/THEN rules literally. Do not redesign,
do not re-derive thresholds, do not skip ledger steps.

**Advisor protocol:** you have an advisor tool backed by a stronger model. Steps marked
`ADVISOR:` include a pre-written question — ask it verbatim (plus the concrete error/output you
hit) *before* improvising. Also ask the advisor whenever: a command fails twice with different
errors, a measured number lands outside the ESTIMATE range given for it, or you are about to
deviate from this runbook for any reason. Never silently deviate.

**Standing rules (from CLAUDE.md, non-negotiable):** timestamps `TZ=Europe/Madrid date
+%Y-%m-%dT%H:%MZ`; every number recorded with its config (power mode 15W, image_size, flags);
negative results recorded plainly; installs documented in the campaign README; commit after each
milestone with a descriptive message; **never push** (user's call); no emojis.

**Paths:** repo `/home/gara/jetson`, venv `.venv-ft` (host 3090), Jetson via `ssh jetson`
(user jfdg, sudo nvpmodel/jetson_clocks NOPASSWD), Jetson venv `~/sam2-bench/.venv`.
`CAMP=experiments/2026-07-01-temporal-acquire-carry`.

---

## Step A — 768 verdict, launch 640, close Phase 2

1. Wait for the 768 eval (3090, `$CAMP/raw/phase2-carry-768.log`; done when
   `$CAMP/runs/phase2-carry-768/results.json` exists). Read its `iou25`.
2. Immediately launch the 640 eval (frees no GPU until done, ~60 min):
   ```bash
   cd /home/gara/jetson && TQDM_DISABLE=1 nohup .venv-ft/bin/python \
     experiments/2026-07-01-temporal-acquire-carry/carry_eval.py --cap 300 --image-size 640 \
     --out experiments/2026-07-01-temporal-acquire-carry/runs/phase2-carry-640 \
     > experiments/2026-07-01-temporal-acquire-carry/raw/phase2-carry-640.log 2>&1 &
   ```
3. When both `results.json` exist, apply the frozen operating-point rule
   (`ACC_PASS(S) := iou25(S) >= 0.799`):
   - IF `ACC_PASS(640)` → **OP=640**. Verdict sentence: "RQ-T.2 PASS at 640: IoU@0.25 <x> within
     5 pp of 1024, 7.25 FPS solo clears the ≥5 gate."
   - ELIF `ACC_PASS(768)` → **OP=768**. Verdict: "RQ-T.2 marginal FAIL at 768: accuracy holds
     (<x>) but 4.89 FPS misses the ≥5 gate by ~3%; TensorRT campaign
     (2026-07-02-carry-trt-export) must close it."
   - ELSE → **OP=1024**. Verdict: "RQ-T.2 FAIL: no eager-PyTorch point passes both gates
     (accuracy knee above 768); TensorRT campaign mandatory."
4. Fill the Phase 2 knee table in `$CAMP/README.md` (1024/768/640/512: FPS + iou25 + verdict),
   append one row to `docs/results/part4-end-to-end.md` and the RQ-T.2 verdict line to
   `docs/questions/part4-end-to-end.md` (follow the formats already in those files). Commit:
   `temporal Phase 2 DONE: RQ-T.2 <verdict>, OP=<S>`.

## Step B — Jetson co-residency spot-check at OP

Skip if OP=1024 (already measured: 2.68 FPS unchanged co-resident). Otherwise on the Jetson,
with the Q8_0 llama-server resident (boot line = Phase 2 config paragraph in `$CAMP/README.md`;
model paths there too):
```bash
~/sam2-bench/.venv/bin/python ~/sam2-bench/jetson_carry_bench.py --image-size <OP> --tag cores-<OP>
```
Expect FPS ≈ solo value (±5%). IF it drops >10%: record it, `ADVISOR: "Co-resident SAM2 FPS at
image_size <OP> dropped from <solo> to <x> on the Orin Nano with llama-server idle-resident —
@1024 there was zero contention. What should I check before accepting this number?"`
Record in `$CAMP/README.md` (raw json lands in `~/sam2-bench/`, scp to `$CAMP/raw/phase2-jetson/`).

## Step C — Phase 3b: integrated on-device loop

Implement exactly the frozen build spec in `$CAMP/README.md` Status entry
"2026-07-02T10:55Z — Phase 3b build spec" (jetson_percept.py JSON-lines TCP server on the Jetson;
`phase3_sitl.py --remote` client patch; perception on-device, control host-side). Sequence:

1. Write `jetson_percept.py`, scp it + `stream_carry.py` to `~/sam2-bench/` on the Jetson.
2. Run its offline selfcheck on the Jetson (M0205 clip, acquire + 100 steps) BEFORE any SITL run.
3. Patch `phase3_sitl.py` (`--remote host:port`, socket client class; nothing else changes).
4. Start on Jetson: llama-server + `jetson_percept.py --port 5606 --image-size <OP>`; on host run
   the same SITL trial as Phase 3a run 2 with `--remote jetson:5606`.
5. Gate (= campaign success criterion): @0.25 m/s — control rate ≥ 5 Hz, in-FOV ≥ 0.90,
   occlusion relock. Logs to `$CAMP/raw/phase3b/`, metrics json to `$CAMP/runs/phase3b/`.
6. IF gate FAILs on control rate only and OP≠640: expected (see ESTIMATE in spec) — record
   honestly, the TensorRT campaign is the fix; still record in-FOV/relock legs.
   IF it fails on a mechanism that is NOT rate (relock never fires, RAM OOM, tracker diverges):
   `ADVISOR: "Phase 3b failed on <mechanism>, not on control rate — full symptom: <paste>. The
   runbook says a non-rate failure may redefine the follow-on campaigns; how should I proceed?"`
7. Close the campaign: README Results + Decision sections, ledger rows in all three
   `docs/*/part4-end-to-end.md` files (results row, RQ-T.5 verdict, decision entry for the
   perception-on-Jetson/control-on-host split — rationale is in the build spec). Commit:
   `temporal Phase 3b <PASS|FAIL>: integrated on-device loop at OP=<S>`.

## Step D — follow-on campaign order

Each campaign below is already pre-registered in its own folder — open its README and execute;
do not create new folders or redesign.

| Condition after Step C | Order |
|---|---|
| OP=640 and 3b PASS | E2 → E3; E1 becomes OPTIONAL (mark its README "not triggered", one-line note, no run) |
| OP=768 (rate marginal-FAIL) | E1 (light branch) → re-run 3b gate → E2 → E3 |
| OP=1024 (both smaller sizes failed accuracy) | E1 (full branch) → re-run 3b gate → E2 → E3 |
| 3b failed on a non-rate mechanism | stop, advisor (Step C.6), user decides |

- E1 = `experiments/2026-07-02-carry-trt-export/` — TensorRT encoder export (+EdgeTAM fallback)
- E2 = `experiments/2026-07-02-follow-speed-ceiling/` — 0.5/1.0/1.5 m/s with levers on
- E3 = `experiments/2026-07-02-twin-distractor/` — twin-target identity robustness

Each campaign ends with its own ledger appends + commit before the next starts.
