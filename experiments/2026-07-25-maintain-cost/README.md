# P6.6 — What does maintaining cost? (energy + thermal price of warm-start)

**Status: RUN AND CLOSED.** Pre-registered 2026-07-25T19:40Z, run 2026-07-26T14:06Z-15:51Z
on the Orin at 15 W + `jetson_clocks`. Headline: **maintaining costs +5.65 W over an idle
board — 1.4-3.8% of a small copter's hover — and it does not decay over 300 s (G1 PASS,
6/6).** Full numbers under *Results*.

**Origin:** R-52 in `thesis/REMEDIATION.md`, itself opened by R-51/S6 — the author's
objection to the warm-start framing while driving the live demo panel. The scope half of
that objection is answered (caveat S6 on `P6.2-DELIVERY-warm-vs-cold-closedloop`). This
campaign answers the half that is a **missing measurement**.

**ID note:** labelled `P6.6`, not `P6.3`. R-45 proposes renaming the existing `EXP-1/2/3`
to `P6.3/P6.4/P6.5`; taking `P6.6` leaves that rename free either way. If the author
resolves R-45 differently, renumber this before it is cited.

---

## The question

Warm-start runs SAM2 continuously through the idle window to save one ~4.85 s acquire.
**Nobody has costed that.** There is no watt figure for the maintain anywhere in this
repository, and the author's own framing of warm-start is compute/timing efficiency.

Two questions, both unanswered by any prior campaign:

- **RQ-P6.6a (energy).** What does maintaining N=1 cost in watts on the deployed board,
  over idle, and what is that as a fraction of the flight power it rides on?
- **RQ-P6.6b (thermal/sustain).** Does the deployed carry **hold its rate** over a
  multi-minute idle window at 15 W? Every carry number in the repo comes from short runs.
  If the rate decays with window length, the maintained track degrades the longer the
  operator waits — a warm-start failure mode nobody has looked for.

RQ-P6.6b is the one that can hurt. A ">10% rate decay over 5 minutes" result would be a
new, unmeasured weakness in the position the thesis defends, and it would be worth more
than the energy number.

## Why this experiment, now

1. **It is a deployment number, not another accuracy number.** The thesis is about running
   local LLMs on edge hardware and is thin on device-level cost.
2. **It is Jetson-only by construction** — no CARLA, no 3090, no simulator. That attacks
   `cap09`'s own threat #1 ("todo corre en la placa" is not what was measured): this
   number is unambiguously on-device.
3. **It is cheap.** ~1.5 h wall clock, no new hardware, no interactive password
   (`tegrastats` needs no sudo; `nvpmodel`/`jetson_clocks` are NOPASSWD).

## Design

**Characterisation, not a gated claim.** The measurement is a continuous time series, so
this does **not** enter the Holm family and the n>=25 rule (which governs binary gating
arms) does not apply. Report means with spread over 3 repeats. One falsifiable prediction
is pre-registered (G1) so the run can come back negative.

### Arms — 300 s each, 3 repeats, order randomised within a repeat

| arm | what runs on the Jetson | why it is here |
|---|---|---|
| `A0` idle-bare | nothing; `llama-server` **stopped** | the floor |
| `A1` idle-deployed | `llama-server` resident and idle, no requests | the *real* deployed floor — grounding has to be loaded to be ready. Found resident at 4.0 GB RSS while writing this |
| `B` carry-640 | SAM2 carry stepping frames, `image_size=640` | the EXP-1 adopted default (5.76 Hz) |
| `C` carry-512 | same, `image_size=512` | one rung *below* the deployed elbow (8.71 Hz), so the table can price what dropping under 640 buys in watts — EXP-1 already priced what it costs in IoU (96% of 1024's). **Corrected 2026-07-26 (R-46):** this row used to read "what `carla_debug_ui.py` actually runs", which stopped being true when the panel's carry dropdown was clamped to a 640 default; the panel runs arm B |
| `D` ground | repeated deployed q8_0 grounds via `JetsonBackend` | energy per cold acquire, for the per-box comparison |

Order is randomised inside each repeat so a monotone thermal soak cannot be read as an
arm effect; between arms the board idles until `tj` returns within 2 C of the A0 median.

### Instrumentation

`tegrastats --interval 500`, logged on-device to a file, pulled afterwards. Fields taken:

- `VDD_IN` — **total module power**, the number to report.
- `VDD_CPU_GPU_CV`, `VDD_SOC` — the split, so "where did it go" is answerable.
- `tj@` — junction temperature, for RQ-P6.6b.
- `RAM`, `GR3D_FREQ` — sanity (an arm that never touched the GPU did not run).

Verified format on the board 2026-07-25T17:56Z:

```
07-25-2026 17:56:56 RAM 5338/7607MB ... GR3D_FREQ 0% ... tj@56.812C ...
VDD_IN 5348mW/5348mW VDD_CPU_GPU_CV 1067mW/1067mW VDD_SOC 1384mW/1384mW
```

Both `mW` figures are `instant/running-average`; the parser takes the **instant** one and
integrates it itself, because the running average is over the whole `tegrastats` lifetime
and would smear the arm boundaries.

### Carry driver

The carry arms run **entirely on the device** — frames read from the local disk
(`~/sam2-bench/clip`, 100 JPEGs already there), not streamed from the host. Rationale: in
a real deployment the frames come from the on-board camera, so putting the host's ssh
transport inside the measured loop would attribute network and JPEG-encode cost to the
maintain. The existing `carry_ssh_bridge.py` transport is therefore **not** used here.

The 100-frame clip is **looped** for the full 300 s. This measures cost and rate, not
tracking accuracy — the carry's box will wander when the clip wraps, and that is
irrelevant to watts and to steps/s. Stated here so a later reader does not mistake this
for a tracking run.

Carry runs **unthrottled** (no rate cap): the deployed panel lets it run as fast as it
can, unthrottled is the worst case for energy, and the achieved-Hz-over-time curve is
exactly the RQ-P6.6b measurement. A rate-capped run would hide a throttle by construction.

### Pre-registered prediction

**G1 (RQ-P6.6b):** the carry's achieved rate in the **last** 60 s of a 300 s arm is within
**10%** of its rate in the first 60 s, for both 640 and 512.
*If G1 fails*, the finding is the decay curve and its `tj` correlate, and the warm-start
position acquires a stated window-length limit. That is a publishable negative and it is
the reason this arm is 300 s and not 30 s.

RQ-P6.6a has no gate — there is no prior number to gate against. It is reported as watts
over idle, joules per delivered box, and a percentage of hover power, with the hover
figure clearly labelled as a **literature range, not measured here** (this project has no
airframe).

## Estimates, up front (these are ESTIMATES)

| quantity | estimate | basis |
|---|---|---|
| wall clock | ~1.5 h | 5 arms x 3 repeats x 300 s = 75 min + cooldowns |
| `A0` idle `VDD_IN` | ~4.5 W | 5.35 W measured with `llama-server` resident |
| `A1` idle-deployed `VDD_IN` | ~5.3 W | measured 2026-07-25T17:56Z, board otherwise quiet |
| `B` carry-640 `VDD_IN` | 11-13 W | 15 W cap, GPU-bound encoder |
| `C` carry-512 `VDD_IN` | 10-12 W | cheaper encode, higher rate — may wash out |
| `D` ground `VDD_IN` | ~14-15 W peaks | prefill saturates; 3680 ms prefill per R-13 |
| maintain over idle | **+5 to +8 W** | the headline estimate |
| as % of hover | **~2-5%** | 150-400 W hover for a small copter (literature) |
| G1 | **holds** | 15 W is a low cap; expect no hard throttle |

If the maintain really is ~3% of hover power, the answer to "is warm worth it" becomes
*yes, and here is the price* — which is the number the author asked to showcase. Record
estimate-vs-actual for every row above.

## Restrictions and invariants

- **SAM2 runs ONLY on the Jetson** (standing constraint). No 3090 arm exists here at all.
- **15 W + `jetson_clocks`.** This board has no MAXN_SUPER — only 15 W and 7 W. Confirm
  with `nvpmodel -q` and record it (`NV Power Mode: 15W` at write time).
- **The board must be otherwise quiet.** A leftover `llama-server` (4.0 GB RSS) was
  resident while this was written — that is arm `A1`, and it must be **stopped** for `A0`.
  Record `ps -eo pid,pcpu,rss,comm --sort=-rss | head` before and after every arm.
- No X session work, no other ssh sessions doing anything, no `--smoke` panel pointed at
  the device during the run.

## Exact commands (to be run next session)

```bash
# 0. pre-flight: record power mode, thermals, what is resident
ssh jetson 'nvpmodel -q; sudo jetson_clocks --show | head -3; \
            ps -eo pid,pcpu,rss,comm --sort=-rss | head'

# 1. stage the device-side driver (idempotent)
scp experiments/2026-07-25-maintain-cost/maintain_cost_dev.py jetson:~/sam2-bench/

# 2. smoke: one 20 s carry arm, confirms the parser sees a power delta at all
.venv-ft/bin/python experiments/2026-07-25-maintain-cost/run_p66.py --smoke

# 3. the matrix
.venv-ft/bin/python experiments/2026-07-25-maintain-cost/run_p66.py \
    --arms A0,A1,B,C,D --seconds 300 --repeats 3 --out runs/p66_maintain_cost

# 4. figures + tables from the run dirs only (DoD-7: reproducible from results.json).
#    No args = both run dirs with B_r2 excluded, i.e. exactly the reported numbers.
.venv-ft/bin/python experiments/2026-07-25-maintain-cost/make_proof.py

# 4b. the arm-B rerun, as run (see "What did not work")
.venv-ft/bin/python experiments/2026-07-25-maintain-cost/run_p66.py \
    --arms B --repeats 1 --seconds 300 \
    --out experiments/2026-07-25-maintain-cost/runs/p66_b_clean
```

## Software versions (fill in at run time)

| component | version | where |
|---|---|---|
| JetPack / L4T | R36 (release) rev 5.0, GCID 43688277, 2026-01-16 | `ssh jetson 'cat /etc/nv_tegra_release'` |
| Python (device) | 3.10.12 | `~/sam2-bench/.venv` |
| SAM2 weights | `facebook/sam2.1-hiera-tiny` | `~/sam2-bench/stream_carry.py:35` |
| llama.cpp build | `57fe1f0`, GNU 11.4.0 aarch64 | pinned commit, see `SOURCES.md` |
| grounding GGUF | `phase3-terse100eos-1024-q8_0` + mmproj | `~/grounding/` |
| host venv | `.venv-ft` | `requirements-ft.lock.txt` |

## Deliverables (DoD-7)

Numbers are the point here, so all three are figures/tables, produced by a committed
`make_proof.py` reproducible from `runs/p66_maintain_cost/results.json`:

1. `proof/power-by-arm.png` — `VDD_IN` over time, all five arms overlaid (3 repeats each,
   the extra repeats drawn faint), the idle floor as a dotted line, each arm's delta over
   it in the legend. **What it shows:** two flat bands and nothing in between — idle at
   5.20 W with `A0` and `A1` indistinguishable, and every working arm at 10.7-11.5 W. The
   sawtooth in the carry arms is the per-step SAM2 loop. Run: `p66_maintain_cost` +
   `p66_b_clean`, B_r2 excluded.
2. `proof/carry-rate-decay.png` — achieved Hz in 30 s bins (solid, left axis) vs `tj`
   (dashed, right axis), for 640 and 512, all repeats. **What it shows:** the G1 verdict as
   a shape — both rate lines are flat for the full 300 s while `tj` climbs ~8 C and
   saturates at ~65 C. This is the figure that says the maintain window is not thermally
   limited at 300 s.
3. `proof/maintain-price.png` — left: joules to deliver one box, warm vs cold, against
   idle-window length, with the 9.9 s break-even marked; right: the maintain delta as a
   percentage of hover across a 150-400 W hover band, labelled on the axis as a literature
   range, not measured here. **What it shows:** the price of warm-start is ~1.9x the energy
   of cold by a 2-minute idle window, and 1.4-3.8% of flight power either way.

## Ledger updates owed on completion

- RESULTS row(s) under Part VI (`docs/results/part6-flight.md`).
- QUESTIONS entries for RQ-P6.6a / RQ-P6.6b (`docs/questions/part6-flight.md`).
- DECISIONS only if a non-trivial choice is made during the run.
- `thesis/claims.json` — **only if** G1 fails and a claim is made from it; a
  characterisation curve is not a gated claim and must not be added as one.
- R-52 in `thesis/REMEDIATION.md` moves to DONE with the number in it.
- `cap09` P6 bullet ("Lo que no se midió: cuánto cuesta mantener") gets its number, and
  `cap10`'s future-work bullet loses this item.

---

## Results — RUN 2026-07-26T14:06Z to 15:51Z, `machine=jetson-orin-nano`, 15 W + `jetson_clocks`

Every number below is the **median of 3 repeats**, from `runs/p66_maintain_cost/results.json`
plus `runs/p66_b_clean/results.json` (see *What did not work* for why arm B has a second run
dir). Repeat-to-repeat spread of `VDD_IN` mean is 0.010-0.036 W in every arm, so the medians
are quoted to 0.01 W and the deltas below are two orders of magnitude larger than the noise.

### RQ-P6.6a — energy

| arm | `VDD_IN` mean W | over `A0` | over `A1` | `CPU_GPU_CV` W | `SOC` W | achieved Hz | J per carried frame |
|---|---|---|---|---|---|---|---|
| A0 idle-bare | 5.195 | — | +0.002 | 0.989 | 1.386 | — | — |
| A1 idle-deployed | 5.193 | -0.002 | — | 0.989 | 1.385 | — | — |
| B carry-640 | 10.842 | +5.647 | +5.649 | 4.128 | 2.263 | 6.273 | 1.728 |
| C carry-512 | 10.689 | +5.494 | +5.496 | 4.135 | 2.211 | 10.043 | 1.064 |
| D ground (repeated q8_0 acquires) | 11.504 | +6.309 | +6.311 | 4.292 | 2.457 | — | — |

**The maintain price is +5.65 W** over an idle board, and the whole of it is SAM2's:
`A1 - A0 = -0.002 W`, i.e. a *resident* `llama-server` holding the deployed q8_0 model
(4.2 GB RSS, `ram_max` 4169 MB vs 1524 MB bare) draws nothing measurable while it is not
being asked anything. Warm-start's memory residency is free; only the carry costs.

Joules to deliver one box, warm (maintain the whole idle window, 0 s stale) vs cold (idle,
then a 4.85 s blocking acquire at arm D's power, 4.85 s stale):

| idle window before the prompt | warm J | cold J | warm / cold |
|---|---|---|---|
| 10 s | 108.4 | 107.7 | 1.01x |
| 30 s | 325.3 | 211.6 | 1.54x |
| 60 s | 650.5 | 367.4 | 1.77x |
| 120 s | 1301.0 | 679.0 | 1.92x |

**Break-even is a 9.9 s idle window** — maintaining for ~10 s costs what one cold acquire
costs. Past that, warm is strictly more energy for strictly less staleness, capping at
~1.9x by 2 minutes (the ratio asymptotes to `P_carry / P_idle = 2.09x`).

As a fraction of flight power: +5.65 W is **1.4% of a 400 W hover and 3.8% of a 150 W
hover**. The hover figure is a **literature range for a small copter, not measured here** —
this project has no airframe, and the band is drawn on `proof/maintain-price.png` as a range
for exactly that reason.

Third result, unasked for and the most useful of the three: **carry power is rail-bound, not
work-bound.** 512 runs 1.60x the rate of 640 (10.043 vs 6.273 Hz) at 0.15 W *less* power, so
joules per carried frame falls 38% (1.728 to 1.064 J). Both arms sit at `GR3D_FREQ` 99% and
both land ~10.7-10.8 W: at 15 W the GPU is saturated either way and the resolution knob buys
throughput at constant draw. EXP-1 picked 640 on the accuracy elbow alone; the energy axis
points the same way as its 512 result, harder.

### RQ-P6.6b — sustain (G1)

| arm | repeat | Hz first 60 s | Hz last 60 s | delta % | `tj` start C | `tj` end C | G1 |
|---|---|---|---|---|---|---|---|
| B carry-640 | r0 | 6.267 | 6.283 | +0.27% | 56.3 | 65.1 | PASS |
| B carry-640 | r1 | 6.233 | 6.267 | +0.53% | 56.9 | 65.3 | PASS |
| B carry-640 | rerun | 6.250 | 6.267 | +0.27% | 57.8 | 65.5 | PASS |
| C carry-512 | r0 | 10.033 | 10.050 | +0.17% | 58.4 | 65.2 | PASS |
| C carry-512 | r1 | 10.000 | 10.050 | +0.50% | 58.7 | 65.3 | PASS |
| C carry-512 | r2 | 10.000 | 10.050 | +0.50% | 57.4 | 65.6 | PASS |

**Verdict: G1 PASSES, 6/6 carry arms, and the sign is up, not down.** Every arm ends the
300 s window *faster* than it started it, by +0.17% to +0.53% — one bin of jitter, not a
trend. `tj` soaks from ~57 C to ~65 C and flattens there (visible in
`proof/carry-rate-decay.png`), which is well inside the 15 W envelope and never triggers a
clock cut. The warm-start position therefore acquires **no stated window-length limit** from
thermals at 300 s. What this does not license: 300 s is the measured window, and a 20-minute
loiter is an extrapolation, not a result.

### Estimate vs actual

| quantity | estimate | actual | note |
|---|---|---|---|
| wall clock | ~1.5 h | 1 h 39 min (14:06-15:45) + 6 min for the B rerun | cooldowns ran 0.3-164.5 s, none timed out |
| `A0` idle `VDD_IN` | ~4.5 W | 5.195 W | estimate was low; it was extrapolated down from a 5.35 W reading that had `llama-server` resident, and residency turns out to cost nothing, so the 5.35 W *was* the floor |
| `A1` idle-deployed | ~5.3 W | 5.193 W | good |
| `B` carry-640 | 11-13 W | 10.842 W | below the band — the 15 W cap is not reached even at 99% `GR3D` |
| `C` carry-512 | 10-12 W | 10.689 W | in band; the "may wash out" hedge was right on power and wrong on rate, which went up 1.6x |
| `D` ground | ~14-15 W peaks | 11.504 W mean, 11.85 W max sample | clearly low; prefill saturates the GPU but not the 15 W rail |
| maintain over idle | +5 to +8 W | **+5.65 W** | in band, at the low end |
| as % of hover | ~2-5% | **1.4-3.8%** | slightly cheaper than estimated |
| G1 | holds | **holds, 6/6, +0.5% worst** | no throttle at all |

The systematic error is one-directional: **every power estimate was high except the idle
floor.** The board does not approach its 15 W cap under any arm measured here — the worst
single sample in the whole matrix is 12.28 W (and that one is contaminated; the worst clean
sample is 11.85 W, in arm D). A 15 W-capped Orin Nano running SAM2 flat out at 99% GPU sits
at ~11 W, so the cap is not the binding constraint on the carry — the GPU's own throughput
is. (Worst clean sample: 11.885 W in `D_r2`.)

### What did not work

**Arm B repeat 2 is excluded and was re-run.** At 15:12-15:17, mid-arm, the CARLA debug
panel was started on the host; `runners/carla_debug_ui.py:2827` prewarms the Orin at
start-up, so it booted `llama-server` and spawned a SAM2 carry bridge on the device inside a
measurement window. The contamination is visible on both axes and in memory:

| B arm | `VDD_IN` mean W | achieved Hz | `ram_max` MB |
|---|---|---|---|
| B_r0 | 10.837 | 6.280 | 3497 |
| B_r1 | 10.842 | 6.273 | 3243 |
| **B_r2 (excluded)** | **10.929** | **5.987** | **7460** |
| B rerun (`runs/p66_b_clean`) | 10.867 | 6.273 | 3453 |

`ram_max` more than doubles, the rate drops 4.7% below both clean repeats, and the mean
power rises — a second GPU consumer, not a property of the carry. The rerun reproduces the
clean repeats to 0.03 W and 0.000 Hz, so arm B is reported on three clean repeats and B_r2
is dropped by name (`make_proof.py --exclude p66_maintain_cost:B_r2`, which is also its
default). The record is kept rather than deleted: it is the only measurement here of what a
second consumer does to the carry, and 4.7% of the rate for one competing process is a
number worth having.

**`results.json` is written once, at the very end.** If the driver had died at 15:40 the
whole 1.5 h would have been lost from the host side — only the per-arm `/tmp/p66_*.json`
files on the device would have survived (they are now archived into
`runs/p66_maintain_cost/device_json/`, and a fixture rebuilt from them is how `make_proof.py`
was developed before the matrix finished). An incremental write after each arm is the
obvious fix and is *not* applied to `run_p66.py`, because editing the as-run driver after the
run would break the correspondence between the committed script and the numbers. It belongs
in whatever runs next.

**Nothing else failed.** No arm timed out its cooldown, no smoke fix was needed on the
device driver, and the parser saw the power delta on the first attempt.

---

## Status / next step

**DONE.** The matrix ran clean on the first attempt — no on-device smoke fix was needed, and
the pure parts (tegrastats parsing, energy integration, the arm scheduler, the G1 rate split)
were already covered by `tests/test_p66.py`. Both drivers and `make_proof.py` are committed
beside this file, and running `make_proof.py` with no arguments reproduces every figure and
every number in *Results* from the two run dirs.

Ledger state: RESULTS, QUESTIONS and DECISIONS entries appended under Part VI; R-52 closed in
`thesis/REMEDIATION.md`; `cap09` and `cap10` updated. **Nothing added to
`thesis/claims.json`** — G1 passed, so there is no gated claim here, and a characterisation
curve must not be registered as one (pre-registered rule, held).

Follow-ups this run opened, none of them blocking:

- **512 is cheaper per carried frame than 640 by 38%** at identical draw. EXP-1 chose 640 on
  accuracy; the energy axis argues for 512 and nobody has checked whether that changes the
  deployed default. `grounding/contract.py:CARRY_IMAGE_SIZE` stays 640 until it does.
- **`CARRY_HZ = 5.76`** in `grounding/contract.py` comes from EXP-1's mixed-clip measurement;
  this campaign's clean 300 s carry at the same 640 gives 6.273 Hz on a single 100-frame
  clip. Different conditions, not a contradiction — but the constant is now the more
  pessimistic of two measurements and should say which it is.
- **An incremental `results.json`** write, per arm, in whatever driver comes next.
