# P6.7 — The handoff seam: what does it cost to start tracking?

**Status: COMPLETE.** Pre-registered 2026-07-25T18:40Z, run 2026-07-25T18:48Z–20:01Z,
written up 2026-07-25T20:10Z. **G1, G2 and G3 all PASS**; the registered claim is
`P6.7-HANDOFF-warm-vs-cold-bridge` in `thesis/claims.json`. The one thing this campaign
does **not** do is change the panel: `runners/carla_debug_ui.py` still spawns a bridge per
designation, and applying the lever lands on `main` as a separate commit (tracked as R-53).

**Origin:** an author observation from driving the live demo panel
(`runners/carla_debug_ui.py`) on 2026-07-25: *"the most problematic thing is the catch-up
time to go from locked in (whether it is from VLM or Oracle) and onto the SAM2 tracking,
this step takes right now 6 to 10 seconds, which makes the system go from usable to
practically useless."*

**ID note:** labelled `P6.7`, after `P6.6` (R-52, maintain-cost). R-45 proposes renaming
`EXP-1/2/3` to `P6.3/P6.4/P6.5`; taking `P6.7` leaves that rename free either way.

---

## The complaint is real, and the name is wrong

Mining the **64 committed live traces** in `runs/carla-ui*/trace-*/trace.jsonl` (every
follow the panel has ever logged that reached `ev="live"`):

| quantity | value | source |
|---|---|---|
| `catchup_s`, all follows | **median 6.52 s** (p25 6.16, p75 8.20, min 0.48, max 80.43) | n=64 traces |
| carry steps executed before `ev="live"` | **median 5**, and **3** in 11 of the 13 oracle follows | same |
| carry step cost @ `image_size=512` | **106.8 ms** median (p10 105.8, p90 110.5) | n=7105 steps |
| `catchup_s`, ORACLE click (`vlm_s=0.0`) | **median 6.48 s**, range 5.92–8.74, n=13 | same |
| `catchup_s`, caption follow (`vlm_s` median 4.23 s) | **median 6.54 s**, n=51 | same |
| `[bridge] model loaded in` | **1.8–2.5 s** (median 2.3), flat in `image_size` | `runs/carla-ui*/ui_bridge.err` |

Two of those rows settle the diagnosis between them:

1. **An oracle click has no backlog to drain.** The seed frame *is* the current frame, so
   "catching up" is one step. It executes 3 and still costs 6.48 s.
2. **The number is flat in the backlog.** A caption follow arrives ~21 frames behind
   (4.23 s x 5 Hz) and a click arrives 0 frames behind. Their medians differ by **0.06 s**.

A quantity that does not move when the thing it allegedly measures changes by 21 frames is
not measuring that thing. `catchup_s` is timed from `t0 = time.time()` at
`runners/carla_debug_ui.py`, immediately after

```python
proc = subprocess.Popen(
    ["ssh", "-T", "-q", "jetson", CARRY_BRIDGE.format(size=int(carry_size))], ...)
```

so it is **tracker cold-start**: ssh spawn + Python interpreter + `import torch/cv2/sam2` +
`SAM2VideoPredictor.from_pretrained` + first-forward CUDA warm-up + `StreamCarry.__init__`,
and then a drain that costs 3 steps ~= 0.32 s. Of the ~6.5 s, **2.3 s is attributed**
(the bridge's own load print) and **~3.9 s has no measured number anywhere in this
repository.**

### The asymmetry nobody wrote down

The panel already learned this lesson once, for the *other* model. From `get_backend()`:

> Booting it costs ~10 s of ssh + model load, and charging that to the first acquire is a
> lie in the wrong direction: it made a live COLD delivery read 18.8 s against the ~4.85 s
> the thesis measures, because the first click paid for the server. Prewarmed at startup
> and locked, so the number on screen is acquire and nothing else.

`CARLA_DEBUG_UI.md` records the result: 18.84 s -> 10.23 s. The **SAM2 carry bridge got no
equivalent**, and per-follow spawn is not recorded as a decision in any `DECISIONS` file,
README or commit message — it is an unexamined default. The harnesses do the opposite:
`runners/run_p62_flight.py` says "Launch the bridge ONCE here so its ~7 s model load
overlaps CARLA world setup", and `select_exp2.py`, `select_exp3.py` and `carry_res_sweep.py`
all re-send `init` to one live bridge across many cells. **Bridge reuse is exercised code
that was never written up.**

### Why this is a thesis number and not a bug report

Every published delivery latency in this thesis **excludes** tracker start-up by
construction: `runners/p62_producers.py` brackets `acquire_s` around `_seed_box` only, and
the panel stamps `_mark_delivered()` before `orin_carry(...)` is even called. P6.2-DELIVERY
therefore measures a world in which the tracker is already running.

That omission is *conservative* for the flagship — a COLD arm forced to pay start-up would
look worse, not better, so nothing retracts. But it is an assumption, and P6.7 is what turns
it into a measurement: **the deployed panel does not have a resident tracker, and the
harness assumed one.** P6.2-DELIVERY's own caveat already points here: *"an acquire pruned
to ~1 s would put the deployed carry inside its already-demonstrated envelope"*. The seam
between a correct box and a running track is the last unmeasured segment of that path.

## Questions

- **RQ-P6.7a (decomposition, descriptive).** Where do the ~6.5 s go? Five stages, medians
  and IQR, at the deployed configuration.
- **RQ-P6.7b (primary, gated).** Does a **resident, pre-warmed** carry bridge cut
  designation -> live latency versus the deployed per-follow spawn? Paired over 25 clips.
- **RQ-P6.7c (quality, gated non-inferiority).** Does the fast path deliver the *same
  track*? A handoff that is fast because it latched a different car is a regression.
- **RQ-P6.7d (residency gate).** Does a permanently-resident SAM2 survive on 8 GB beside
  the resident `llama-server`, and does grounding latency regress when it does?
- **RQ-P6.7e (parameters, non-gating).** With the constant removed, what does the catch-up
  policy `CATCHUP_JUMP` actually buy? Only meaningful if G1 passes.

## Design

### The lever under test

Not new machinery — the pattern already in the same file, applied to the tracker:

```
hoist the Popen out of orin_carry() into the startup prewarm thread beside get_backend();
warm CUDA with one throwaway init+step on a synthetic frame;
per follow, re-send ("init", jpg, box) instead of respawning;
keep _stop_current()'s kill for window-close only.
```

Skipped deliberately: a supervisor / restart-on-death wrapper. Add it only if RQ-P6.7d
records an `rc=-9`.

### Arms — paired, 25 clips, 2 designation lags

| arm | bridge lifecycle | stands for |
|---|---|---|
| `COLD` | `ssh` spawn at designation time, exactly as deployed | the baseline the author is complaining about |
| `WARM` | bridge spawned, model loaded and CUDA-warmed **before** the trial; designation sends only `init` | the lever |

crossed with the **designation lag**, applied as a stub the way P6.2-DELIVERY applied the
cold acquire lag:

| lag | stands for | backlog at designation |
|---|---|---|
| `0.0 s` | ORACLE / Shift-click designation | 0 frames |
| `4.85 s` | whole-frame VLM caption grounding (R-34 / P6.2 acquire) | ~24 frames @ 5 Hz |

4 cells x 25 clips = **100 carry runs**. Both arms see the same clip, the same target and
the same designation frame, so every comparison is paired.

Arm `PIPELINE` (spawn the bridge concurrently with grounding instead of after it) is
pre-registered as a **conditional fallback**: it runs only if `WARM` fails the RQ-P6.7d
memory gate. It caps the win at `max(0, establishment - grounding)` ~= 2 s rather than
~0.5 s, and it does nothing at all for the oracle path, where there is no grounding to hide
behind.

### Substrate — the CARLA GT bank, replayed at 5 Hz

`experiments/2026-07-21-carla-gt-bank/runs/bank/clip00..clip24`: **25 clips, 1200 frames
each at dt=0.05, per-frame GT boxes for every vehicle, `complete: true`**, five altitudes
(40/60/80/100/120 m) x five seeds. Every clip is an independent generative draw, so
`n_effective = n_rows = 25` by the same argument `score_p62.score_delivery` makes for
P6.2-DELIVERY — no `_s`-style subsequences, no clustering.

**Why replay and not live CARLA + SITL.** Every term under test is device-side: ssh, the
Python interpreter, the SAM2 weights, the CUDA context, `init_state`. None of them can tell
whether the JPEG on the wire came from a live sensor or from disk. Replay buys determinism,
a paired design, GT boxes for RQ-P6.7c, and no CARLA boot per trial. What replay does *not*
buy is the closed loop — so **P6.7 makes no control-coupling claim**; P6.2-COUPLING owns
that, and it already closed as a bounded null.

The feed is paced at **5 Hz wall-clock** (the panel's `CAM_HZ`), taking every 4th frame of
the 20 Hz clip. Wall-clock pacing is not decoration: it is what makes the backlog grow while
the tracker is starting, which is the entire mechanism under test. Each trial carries for
**100 fed frames = 20 s**.

### Instrumentation — the decomposition, with no clock sync

Host-side arrival times plus two scalars the bridge already reports. No wire-protocol change
(the framed stdout stream is untouched, so the panel keeps working); the only device-side
edit is **one line** — a `[bridge] up` marker on **stderr** as the first statement of
`carry_ssh_bridge.py`, before the heavy imports, because otherwise ssh startup and
`import torch` are one lump and they have different fixes.

| stage | measured as | what it would take to fix |
|---|---|---|
| `ssh_spawn` | host `Popen` -> `[bridge] up` on stderr | ssh `ControlMaster`, or residency |
| `import` | `[bridge] up` -> `[bridge] model loaded` minus reported `load_s` | residency only |
| `weights` | the bridge's own reported `load_s` | residency only |
| `warmup_init` | `[bridge] model loaded` -> `init` ack | a throwaway warm-up step |
| `drain` | `init` ack -> first step with `lag <= 1` | `CATCHUP_JUMP` (RQ-P6.7e) |

`t_handoff` = designation -> first step at `lag <= 1` = the sum of all five. This is
byte-for-byte the panel's own `catchup_s` definition, so the baseline arm is directly
comparable to the 64 traces above.

### Gates, pre-registered

- **G1 (RQ-P6.7b, primary).** Median `t_handoff` under `WARM` <= **1.0 s**, and the paired
  `WARM`-vs-`COLD` difference significant by two-sided Wilcoxon signed-rank at n=25 per lag.
  Reference for the 1.0 s target: the 5 legacy traces at 0.48–1.16 s that predate the
  per-follow spawn.
- **G2 (RQ-P6.7c, non-inferiority).** `WARM` median IoU against the GT box over the 20 s
  window >= `COLD` median IoU **minus 0.02**, paired, reported with a CI in the
  P6.2-COUPLING bounded-null style. Plus: no increase in identity-swap episodes and no drop
  in the fraction of steps with a box.
- **G3 (RQ-P6.7d, kill condition).** 25 consecutive designations against **one** resident
  bridge with `llama-server` resident: **zero** `rc=-9`. And `ground_ms` over 25 paired
  grounding calls must not regress by more than **15%** with SAM2 resident.
  *If G3 fails, arm `WARM` is dead as deployed*, arm `PIPELINE` runs, and the negative is
  the result.
- **RQ-P6.7e has no gate.** It is a curve: `CATCHUP_JUMP` in {1 (replay every frame), 12
  (deployed), inf (jump straight to live)} at the 4.85 s lag, scored on `t_handoff` *and*
  on whether the jump across the gap latches the wrong vehicle.

Resolution is **not** swept. EXP-1 owns the carry-resolution elbow and R-46 is open on which
value is "deployed"; the matrix runs at `image_size=512`, the value
`runners/carla_debug_ui.py` actually ships, and says so on every number.

## Estimates, up front (these are ESTIMATES)

| quantity | estimate | basis |
|---|---|---|
| wall clock, main matrix | ~40 min | 25 clips x 2 lags x (COLD ~27 s + WARM ~21 s) |
| wall clock, all of it | ~1.5 h | + RQ-d probe (~5 min) + RQ-e sweep (~26 min) + staging |
| `ssh_spawn` | 0.5–1.5 s | unmeasured; this is the term with no prior |
| `import` (torch + sam2 on Orin) | 2.5–4.0 s | the ~3.9 s residual has to live mostly here |
| `weights` (`from_pretrained`) | 1.8–2.5 s | measured, `ui_bridge.err` |
| `warmup_init` | 0.5–1.5 s | first CUDA forward + `init_state` |
| `drain` @ lag 0.0 s | ~0.1 s | 1 step at 106.8 ms |
| `drain` @ lag 4.85 s | 0.3–0.5 s | 3–5 steps at 106.8 ms with `CATCHUP_JUMP=12` |
| **`t_handoff` COLD** | **6.0–8.0 s** | reproduces the 64-trace median 6.52 s |
| **`t_handoff` WARM** | **0.4–0.8 s** | `warmup_init` + `drain` only |
| G1 | **holds** | the legacy traces already did 0.48 s on this seam |
| G2 | **holds** | identical computation; only the process start moves |
| G3 memory | **holds, tight** | `MemAvailable` 2112 MB with `llama-server` at 4.0 GB RSS |
| G3 `ground_ms` | 0–15% slower | unmeasured; SAM2 resident is new GPU contention |

The honest risk is G3. `import torch` on an Orin cannot be made fast, so if a resident SAM2
does not fit beside `llama-server`, residency is unavailable and the only remaining lever is
`PIPELINE`, which does nothing for the oracle path. Record estimate-vs-actual for every row.

## Restrictions and invariants

- **SAM2 runs ONLY on the Jetson** (standing constraint, 2026-07-24). No 3090 arm exists;
  the host only replays JPEGs and holds the clock. `machine=jetson-orin-nano-8gb`.
- **15 W + `jetson_clocks`.** No MAXN_SUPER on this board. Confirm with `nvpmodel -q` and
  record it (`NV Power Mode: 15W` at write time).
- **`llama-server` stays resident for the whole matrix.** It is resident in deployment; a
  measurement taken with it stopped would be a memory budget nobody flies.
- **Look at it (I5).** Every arm dumps an overlay PNG at the moment of `lag <= 1` and one
  mid-window, and no verdict is written before those are opened with the Read tool. A run
  with no frame is INVALID, not "probably fine".
- **The wire protocol does not change.** The panel must keep working against the same
  bridge, so all new instrumentation is stderr-only.

## Software versions

| component | version | where |
|---|---|---|
| host Python | 3.12 (`.venv-ft`) | torch 2.6.0+cu124, cv2 4.13.0 |
| Jetson Python | 3.10.12 (`~/sam2-bench/.venv`) | torch 2.8.0 |
| Jetson L4T | R36 REVISION 5.0, GCID 43688277 | `/etc/nv_tegra_release` |
| SAM2 | `facebook/sam2.1-hiera-tiny`, `image_size=512` | `stream_carry.MODEL` |
| grounding | `phase3-terse100eos-1024-q8_0.gguf` + mmproj f16 | resident `llama-server`, port 18080 |
| power mode | 15 W | `nvpmodel -q` |

## Exact commands

```bash
# 0. pre-flight: power mode, what is resident, free memory
ssh jetson 'sudo nvpmodel -q; free -m | head -2; ps -eo pid,pcpu,rss,comm --sort=-rss | head -4'

# 1. stage the instrumented bridge (idempotent; stderr-only change, edited IN PLACE at
#    its one canonical location so the live panel picks it up too)
scp experiments/2026-07-24-p62-showcase/carry_ssh_bridge.py jetson:~/sam2-bench/

# 2. smoke: one clip, both arms, both lags -- then LOOK at the overlays
.venv-ft/bin/python experiments/2026-07-25-handoff-latency/handoff_p67.py \
    --clips clip00 --out runs/p67/smoke

# 3. the matrix
.venv-ft/bin/python experiments/2026-07-25-handoff-latency/handoff_p67.py \
    --out runs/p67/matrix

# 4. residency gate (RQ-P6.7d)
.venv-ft/bin/python experiments/2026-07-25-handoff-latency/residency_p67.py \
    --out runs/p67/residency

# 5. catch-up policy sweep (RQ-P6.7e), only if G1 passed
.venv-ft/bin/python experiments/2026-07-25-handoff-latency/handoff_p67.py \
    --sweep-jump 1,12,999 --lags 4.85 --out runs/p67/jump

# 6. figures + tables, reproducible from the run dirs only (DoD-7)
.venv-ft/bin/python experiments/2026-07-25-handoff-latency/make_proof.py --run runs/p67
```

## Deliverables (DoD-7)

1. `proof/stage-budget.png` — stacked stage bars, COLD vs WARM, both lags. The
   decomposition figure; stands alone even if the lever failed.
2. `proof/paired-handoff.png` — per-clip slope plot of `t_handoff` COLD -> WARM, with the
   G2 quality CI beside it.
3. `proof/seam-<arm>.png` — the overlay at `lag <= 1` in each arm on the same clip. The
   behaviour is the point: where the box is when the track finally goes live.

## Ledger updates owed on completion

- `docs/results/part6-*.md` — one row per cell.
- `docs/questions/part6-*.md` — RQ-P6.7a..e with one-line verdicts.
- `docs/decisions/part6-*.md` — **the bridge lifecycle decision**, which is the thing that
  was never recorded. What was chosen, why, what was given up.
- `thesis/claims.json` — one claim, `machine=jetson-orin-nano-8gb`. Note R-39: registering
  it re-runs Holm over Part VI (family m=2 -> 3). P6.2-DELIVERY moves 1.907e-06 ->
  2.861e-06 and still rejects by an enormous margin; the arithmetic is checked before the
  claim lands, not after.
- `thesis/REMEDIATION.md` — new task row, and R-46 gains a datapoint on what "deployed"
  means for the carry resolution.
- `runners/carla_debug_ui.py` — apply the lever **only if G1 and G3 both pass**, on `main`,
  as a separate commit from this campaign.

## Results

**Run 2026-07-25T18:48Z–20:01Z.** 100 matrix cells (25 clips x 2 lags x 2 arms), 50 residency
probes, 75 sweep cells. SAM2 on the Jetson Orin Nano at 15 W throughout, `image_size=512`;
`llama-server` resident the whole time; the host only replays JPEGs and holds the clock.
`machine=jetson-orin-nano-8gb`. n_effective = n_rows = 25 (independent CARLA generative
seeds, the P6.2-DELIVERY argument), so no clip-clustering deflation applies.

### RQ-P6.7a — decomposition

Medians over 25 clips per cell. The stage medians do not sum exactly to the `t_handoff`
median — each column is a median taken independently.

| stage | lag 0.0 s, COLD | lag 4.85 s, COLD | WARM (both lags) |
|---|---|---|---|
| `ssh_spawn` | 0.301 s | 0.307 s | 0 (paid once, at panel start-up) |
| `import` (torch + cv2 + sam2) | **2.846 s** | **2.893 s** | 0 |
| `weights` (`from_pretrained`) | 1.800 s | 1.800 s | 0 |
| `warmup_init` (first CUDA forward + `init_state`) | 0.670 s | 0.670 s | 0.120 s / 0.121 s |
| `drain` (backlog to `lag <= 1`) | 0.361 s | 0.658 s | 0.178 s / 0.392 s |
| **`t_handoff`** | **6.148 s** (IQR 5.95–6.20) | **6.311 s** (IQR 6.17–6.51) | **0.299 s** (IQR 0.30–0.30) / **0.515 s** (0.51–0.53) |
| `steps_to_live` | 3 (range 3–4) | 6 (5–7) | 1 (1–1) / 4 (4–4) |

**4.95 s of the 6.15 s — 80% — is process start-up that has nothing to do with the target,
the operator, or the scene**: ssh 0.30 + `import` 2.85 + weights 1.80. The single largest
term is `import torch`, and it is larger than every other term combined. Only 0.36 s is the
"catching up" the name promised.

The replay substrate reproduces the deployed number it was built to explain: COLD's
`steps_to_live = 3` at lag 0 matches the panel's 11-of-13 oracle traces exactly, and
COLD's 6.148 s median sits on the live 64-trace p25 of 6.16 s (live median 6.52 s).

### RQ-P6.7b — the lever (G1) = **PASS**

| lag | COLD median | WARM median | speed-up | discordant pairs | Wilcoxon p | G1 |
|---|---|---|---|---|---|---|
| 0.0 s | 6.148 s | **0.299 s** | **20.6x** | 25/25, all one way | **5.96e-08** | PASS |
| 4.85 s | 6.311 s | **0.515 s** | **12.3x** | 25/25, all one way | **1.23e-05** | PASS |

Both gates cleared: WARM median <= 1.0 s and the paired difference is significant at n=25.
The two p-values come from the same test on data of the same shape and differ only in
method. At lag 0, `5.96e-08` is the exact floor for a two-sided signed-rank test at n=25
(2/2^25) — every clip moved the same way, so no smaller p exists at this n. At lag 4.85 two
clips happen to share an identical paired difference (5.7946 s), and a tie in `|d|` makes
scipy's `method="auto"` fall back to the normal approximation, which reports **1.228e-05**;
forcing `method="exact"` on the same numbers returns 5.96e-08. The registry
(`grounding/stats.py::paired_continuous`) uses the default, so **1.228e-05 is the registered
value** — the conservative one, and the claim is quoted at it. WARM's spread is remarkable:
IQR 0.30–0.30 s at lag 0, because with the process already alive the handoff is one
`init` (0.12 s) plus one carry step (0.18 s) and nothing else varies.

### RQ-P6.7c — quality (G2) = **PASS**, and the fast path is also the *better* track

| lag | metric | COLD | WARM | paired median delta [95% CI] | p | G2 |
|---|---|---|---|---|---|---|
| 0.0 s | median IoU vs GT | 0.000 | **0.674** | **+0.049 [+0.006, +0.502]** | 0.00021 | PASS |
| 0.0 s | box-present fraction | 1.000 | 1.000 | +0.000 [+0.000, +0.010] | 0.027 | PASS |
| 0.0 s | identity-swap episodes (total) | 79 | **68** | 0 [−1, 0] | 0.11 | PASS |
| 4.85 s | median IoU vs GT | 0.000 | 0.000 | +0.000 [+0.000, +0.005] | 0.123 | PASS (uninformative) |
| 4.85 s | box-present fraction | 1.000 | 1.000 | +0.000 [+0.000, +0.009] | 0.065 | PASS |
| 4.85 s | identity-swap episodes (total) | 85 | 75 | 0 [−1, 0] | 0.358 | PASS |

CIs are 20 000-resample percentile bootstraps of the paired median difference; n=24 for the
IoU rows because `clip01`'s target leaves frame before COLD's tracker exists, so that clip
has no COLD post-live window to pair against (latency is still scored on all 25 — machine
cost does not care whether the target is visible).

**Read the lag-4.85 rows as uninformative, not as reassurance.** G2 passes there over a
floor: both arms sit at median IoU 0.000, so non-inferiority is satisfied by both arms being
equally broken. The informative comparison is lag 0.

Counting clips that stay on target (median IoU >= 0.25), paired per clip:

| lag | COLD | WARM | WARM-only wins | COLD-only wins | exact McNemar p |
|---|---|---|---|---|---|
| 0.0 s | 11/24 | **20/25** | **8** | **0** | **0.0078** |
| 4.85 s | 7/24 | 10/25 | 4 | 1 | 0.375 |

### The finding the pre-registration did not anticipate

The cold start does not only *delay* the track — **it loses it**, and the loss is gated by
target size:

| altitude | median seed-box area | lag 0: COLD | lag 0: WARM | lag 4.85: COLD | lag 4.85: WARM |
|---|---|---|---|---|---|
| 40 m | 1595 px² | 4/5 | 5/5 | 3/5 | 4/5 |
| 60 m | 659 px² | 2/4 | 4/5 | 2/4 | 2/5 |
| 80 m | 289 px² | 1/5 | 4/5 | 0/5 | 1/5 |
| 100 m | 132 px² | 2/5 | 4/5 | 1/5 | 1/5 |
| 120 m | 160 px² | 2/5 | 3/5 | 1/5 | 2/5 |

(cells = clips with post-live median IoU >= 0.25)

**Mechanism, from the traces.** `CATCHUP_JUMP = 12` at `CAM_HZ = 5` means one SAM2 step
crosses **2.4 s of world**. A tracker that took 6.15 s to boot wakes to a ~31-frame backlog
and its *first* carry step is that 2.4 s hop. On `clip03` (100 m, seed box 7x17 px) the very
first step already reads IoU 0.000: the mask has jumped onto an unrelated patch of overpass
60 px away and never comes back (`box_frac` 0.11). At 40 m, where the car is 26x42 px, the
same hop is survivable and COLD reaches IoU 0.881.

So the causal chain is **cold start-up -> long backlog -> large temporal jumps -> lost
track**, and the latency lever fixes the quality problem as a side effect: WARM at lag 0 has
no backlog at all, so its first step is a 0.2 s hop.

This also explains why lag 4.85 degrades *both* arms. A 4.85 s grounding lag builds a
24-frame backlog no matter how warm the bridge is, so WARM's drain is still two 2.4 s hops
and it drops to 10/25. **The bridge lifecycle and the catch-up policy are two independent
failure modes on the same seam**, which is what makes RQ-P6.7e load-bearing rather than a
parameter footnote.

### RQ-P6.7d — residency (G3) = **PASS**

| quantity | value | limit | G3 |
|---|---|---|---|
| `rc=-9` over designations on one resident bridge | **0 / 50** | 0 over 25 | PASS |
| `MemAvailable` floor, `llama-server` only | 2258 MB | — | — |
| `MemAvailable` floor, + SAM2 resident | **1315 MB** | > 0 | PASS |
| `ground_ms` median, SAM2 absent | 3791.1 ms | — | — |
| `ground_ms` median, SAM2 resident | **3791.2 ms** | <= 4359.8 ms (+15%) | PASS |

The pre-registration called G3 "the honest risk". It is not close. A resident SAM2 costs the
VLM **x1.000** — the two medians differ by 0.1 ms across 25 paired requests with genuine
per-request spread (baseline 3738.4–3876.5 ms, resident 3738.6–3842.3 ms; server-side
`prompt_ms` 3163.0 vs 3163.3). Grounding output was checked for sanity, not just latency:
`"13 41 23 53"`, the terse contract format.

The memory half came free: the matrix's WARM pass already put **50** consecutive
designations through a single bridge with `llama-server` up, twice the 25 asked for, with
zero non-zero return codes. 1315 MB of headroom remains.

**`PIPELINE`, the pre-registered fallback arm, was not run** — it exists only for the case
where G3 fails, and G3 passed.

### RQ-P6.7e — catch-up policy (no gate)

75 WARM cells, 25 clips x `CATCHUP_JUMP` in {1, 12, 999}, all at the 4.85 s lag — the lag
where the backlog is real. `999` means "one step, straight to the live frame": the seed box
is applied and SAM2 is asked to find the object 4.85 s later with nothing in between.

| `CATCHUP_JUMP` | median `t_handoff` | range | median steps to live | median IoU | on target (IoU >= 0.25) | swaps |
|---|---|---|---|---|---|---|
| 1 — replay every frame | 5.312 s | 5.161–5.363 | 50 | **0.596** | **17 / 25** | 79 |
| 12 — deployed | **0.517 s** | 0.503–0.558 | 4 | 0.000 | 10 / 25 | 75 |
| 999 — jump to live | **0.314 s** | 0.306–0.334 | 2 | 0.000 | 8 / 25 | 75 |

The two axes move against each other and the crossing is not gentle. Paired exact McNemar on
the per-clip on-target outcome: `j1` vs `j999` **b=11, c=2, p=0.0225**; `j1` vs `j12` b=9,
c=2, p=0.0654; `j12` vs `j999` b=4, c=2, p=0.6875. These are **descriptive** — RQ-e was
pre-registered without a gate, the claim is not in `thesis/claims.json`, and none of these
p-values is Holm-corrected. Read them as the shape of a curve, not as three verdicts.

Three things follow.

1. **Replaying the gap works and costs the entire win.** `j1` is the only setting that keeps
   a usable median IoU, and it lands at 5.31 s — worse than the 4.85 s of world it is
   crossing, and 10x the G1 bar. A resident bridge that then spends five seconds replaying is
   a cold start with extra steps.
2. **12 and 999 are the same policy.** p=0.6875, identical swap counts, identical zero median
   IoU. By the time the tracker has skipped 12 frames the identity is already gone, so the
   deployed value is not buying anything over jumping straight to live at this lag. Tuning
   `CATCHUP_JUMP` between them is not a lever.
3. **The residual is grounding latency, not the bridge.** The gap exists because the box was
   drawn on a frame 4.85 s old. `j999` is the honest test of "just use the stale box on the
   live frame" and it fails 17/25 — the object has moved out from under the box. So the next
   lever is upstream (ground faster, or re-ground at the live frame once the tracker is
   already warm), not a better way to cross a gap that should not be there.

Verified by looking (I5): `runs/p67/jump/clip18-WARM-lag4.85-j1/seam-live.png` shows the
track box on the target at n=236 (IoU 0.551), and the same clip at `j999`
(`clip18-WARM-lag4.85-j999/seam-live.png`, n=140) shows the track box left behind on the road
while the GT box has moved up the frame — IoU 0.000. Same clip, same seed, different policy.

### Estimate vs actual

| quantity | estimate | actual | note |
|---|---|---|---|
| `ssh_spawn` | 0.5–1.5 s | **0.301 s** | below the range — `ssh` to a LAN host on an open ControlMaster-free channel is cheaper than assumed |
| `import` (torch + sam2) | 2.5–4.0 s | **2.846 s** | in range, and the single largest term; this is the one that cannot be optimised, only avoided |
| `weights` (`from_pretrained`) | 1.8–2.5 s | **1.800 s** | at the bottom of the range; the prior came from `ui_bridge.err` and held exactly |
| `warmup_init` | 0.5–1.5 s | **0.670 s** | in range |
| `drain` @ lag 0.0 | ~0.1 s | **0.361 s** | 3.6x the estimate: the estimate assumed 1 step at 106.8 ms, the harness measured a median of 3 steps because the world keeps moving during `init_state` |
| `drain` @ lag 4.85 | 0.3–0.5 s | **0.658 s** | above the range, same cause — 6 steps, not 3–5 |
| **`t_handoff` COLD** | 6.0–8.0 s | **6.148 / 6.311 s** | bottom of the range; reproduces the live 64-trace p25 (median 6.52 s) |
| **`t_handoff` WARM** | 0.4–0.8 s | **0.299 / 0.515 s** | lag 4.85 in range; lag 0 came in *below* it |
| G1 | holds | **PASS** | by 2x at the worse lag |
| G2 | holds | **PASS** | and better than "holds": at lag 0 WARM strictly beats COLD on IoU and on-target clips |
| G3 memory | holds, tight | **PASS, not tight** | 1315 MB floor, 0/50 kills |
| G3 `ground_ms` | 0–15% slower | **x1.000** | bottom of the range; the estimate's premise (new GPU contention) did not materialise for an idle-resident tracker |
| wall clock, main matrix | ~40 min | **41 min** | 18:48–19:29 |
| wall clock, residency (G3) | ~5 min | **4 min** | 19:29–19:33 |
| wall clock, RQ-e sweep | ~26 min | **28 min** | 19:34–20:01; the `jump=1` cells do replay every frame (~148 steps against ~103) but the other two thirds are faster, and it netted out |
| wall clock, all of it | ~1.5 h | **1 h 13 min** | 18:48–20:01, smoke excluded |

The estimate that was wrong in a way that mattered is **`drain`**. It was built from
"backlog / `CATCHUP_JUMP`" and forgot that the backlog keeps growing while the tracker
initialises — which is exactly the mechanism that turned out to lose the track, not just
delay it.

### What did not work, and what surprised

- **The panel's own metric was measuring the wrong thing.** `catchup_s` differs by 0.06 s
  between an oracle click (0 frames of backlog) and a caption follow (~21 frames). A metric
  named for catch-up that is invariant to the size of the backlog is not measuring catch-up.
  It is dominated by a term nobody had ever decomposed.
- **`import torch` is 46% of the seam.** No flag fixes this. It is why the answer is
  residency and not optimisation: the only way to not pay 2.85 s is to have already paid it.
- **The pre-registration measured latency and assumed quality would follow.** G2 was written
  as a non-inferiority guard — "WARM must not be *worse*" — because the arms run identical
  computation. That framing missed the real finding: the arms do **not** run identical
  computation, because a 6.15 s start-up hands SAM2 a different (much harder) first step.
  The correct question was never asked in the pre-registration and had to be answered from
  the data: `on_target` clip counts, McNemar b=8 c=0 p=0.0078 at lag 0.
- **The lag-4.85 quality rows are a floor, not a result.** Both arms sit at median IoU
  0.000, so "no significant difference" there says nothing about non-inferiority. Reported
  as uninformative rather than folded into the PASS.
- **G3 was called the honest risk and was not close.** The prediction was that a resident
  SAM2 would contend with `llama-server` on an 8 GB board. It costs x1.000 and leaves
  1315 MB. The prediction was wrong in the direction that makes the lever deployable.

### Deviations from the pre-registration

- **Run outputs were written to the repo-root `runs/p67/`, which `.gitignore` blocks by
  design** (`/runs/` is ignored because "a bare `/runs/` at repo root is always a
  cwd-relative accident"). The pre-registered command block asked for exactly that path, so
  the deviation is in the pre-registration, not in the execution. Corrected at completion by
  moving the tree to `experiments/2026-07-25-handoff-latency/runs/p67/`, where the
  `results.json` files are committed and the heavy per-cell PNG/JSONL output stays ignored.
  `thesis/claims.json` cites the corrected paths; `make_proof.py --run` takes the run root,
  so the figures reproduce from either location.
- **The registered p-value is the normal-approximation one, not the exact one.** See RQ-b:
  scipy's default method is what `grounding/stats.py::paired_continuous` uses, a tie in
  `|d|` at lag 4.85 s sends it to the approximation, and the campaign quotes the registry
  rather than the more favourable exact value. `make_proof.py` was changed to match the
  registry after the run, so the figure and the claim cannot disagree.
- **`PIPELINE` was not run.** Pre-registered as a fallback arm conditional on a G3 failure;
  G3 passed, so the condition never fired. Not a silent omission — the condition is in the
  frozen gate text.
- **The matrix ran at `image_size=512`, while EXP-1 adopted 640 as the deployed carry
  resolution.** Pre-registered deliberately (resolution is EXP-1's knob, R-46 open), and
  recorded here as an R-46 datapoint: the start-up terms are resolution-independent, so the
  conclusion holds, but the sub-second WARM figure is quoted at 512.

### Proof deliverables, as produced

Eight, up from the three pre-registered — RQ-e and the unanticipated track-loss finding each
earned their own. All regenerate from the run dirs alone:
`make_proof.py --run experiments/2026-07-25-handoff-latency/runs/p67`.

1. `proof/stage-budget.png` — stacked stage bars, COLD vs WARM, both lags, from
   `runs/p67/matrix/results.json`. Shows where the 6.15 s goes: `ssh_spawn` 0.301 +
   `import` 2.846 + `weights` 1.800 + `warmup_init` 0.670 = 4.95 s of process start-up,
   against a WARM bar that is `drain` and nothing else. The decomposition answer to RQ-a;
   it stands alone even if the lever had failed.
2. `proof/paired-handoff.png` — per-clip slope plot of `t_handoff`, COLD -> WARM, both lags,
   same source. 25/25 lines fall, none cross; the G1 bar at 1.0 s is drawn. This is the
   registered claim in one picture (lag 4.85: 6.311 -> 0.515 s, Wilcoxon p=1.228e-05).
3. `proof/quality-paired.png` — paired IoU and the bootstrap deltas for G2. The lag-0 panel
   carries the result (median 0.000 -> 0.674, delta +0.049 CI [+0.006, +0.502]); the
   lag-4.85 panel is shown sitting on the floor in both arms, which is why that row is
   reported as uninformative rather than as a pass.
4. `proof/jump-tradeoff.png` — RQ-e, from `runs/p67/jump/results.json`: median `t_handoff`
   (left axis) against the fraction of 25 clips still on target (right axis) for
   `CATCHUP_JUMP` in {1, 12, 999} at lag 4.85 s. The two bars move opposite ways at every
   step; only `jump=1` clears the track and only `jump=1` misses the 1.0 s line.
5. `proof/seam-COLD.png` and `proof/seam-WARM.png` — the latency pair: the same clip, the
   same seed, the frame at which the track first goes live in each arm
   (`runs/p67/matrix/clip00-*-lag4.85-j12/`, first clip that succeeded in both arms, chosen
   alphabetically). WARM goes live at frame **144** with IoU **0.964**; COLD at frame
   **272** with IoU 0.568. 128 bank frames at dt=0.05 is 6.4 s of world that the operator
   spends staring at nothing. Both arms are on target here — clip00 is one COLD survives,
   and the caption says so rather than implying the pair shows a loss.
6. `proof/loss-COLD.png` and `proof/loss-WARM.png` — the failure pair, and the negative
   half: `clip01` at lag 0, the first of the eight discordant clips behind the b=8 c=0
   track-loss finding (deterministic rule in `make_proof.py::loss_frames`, not eyeballed).
   WARM goes live at frame **44**, box on the car, IoU **0.739**. COLD goes live at frame
   **169** with **no box at all** (`iou=None`) — the mask came back empty, and the GT box
   has by then reached the top edge of the frame. Proof that the cold seam does not merely
   arrive late: it arrives with nothing. `clip01` is also the clip missing from the lag-0
   IoU panel of `quality-paired.png` (n=24 paired of 25) — it drops out of the *quality*
   comparison precisely because COLD has no box to score, which is why the track-loss
   finding had to be counted separately rather than read off the IoU test.
