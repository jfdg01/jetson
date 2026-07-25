# P6.6 — What does maintaining cost? (energy + thermal price of warm-start)

**Status: PRE-REGISTERED, NOT RUN.** Written 2026-07-25T19:40Z. Everything below the
`## Results (TBD)` line is a placeholder. A fresh session can start from this file alone.

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
| `C` carry-512 | same, `image_size=512` | what `runners/carla_debug_ui.py` actually runs (8.71 Hz) |
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

# 4. figures + tables from the run dir only (DoD-7: reproducible from results.json)
.venv-ft/bin/python experiments/2026-07-25-maintain-cost/make_proof.py \
    --run runs/p66_maintain_cost
```

## Software versions (fill in at run time)

| component | version | where |
|---|---|---|
| JetPack / L4T | TBD | `ssh jetson 'cat /etc/nv_tegra_release'` |
| Python (device) | TBD | `~/sam2-bench/.venv` |
| SAM2 weights | `facebook/sam2.1-hiera-tiny` | `~/sam2-bench/stream_carry.py:35` |
| llama.cpp build | TBD | pinned commit, see `SOURCES.md` |
| grounding GGUF | `phase3-terse100eos-1024-q8_0` + mmproj | `~/grounding/` |
| host venv | `.venv-ft` | `requirements-ft.lock.txt` |

## Deliverables (DoD-7)

Numbers are the point here, so all three are figures/tables, produced by a committed
`make_proof.py` reproducible from `runs/p66_maintain_cost/results.json`:

1. `proof/power-by-arm.png` — `VDD_IN` over time, all arms overlaid, with the idle floor
   drawn as a line and the delta annotated.
2. `proof/carry-rate-decay.png` — achieved Hz in 30 s bins vs `tj` on a twin axis, 640 and
   512. This is the G1 verdict, and it is a picture because a decay is a shape.
3. `proof/maintain-price.png` — joules per delivered box for warm vs cold as a function of
   idle-window length, with the % -of-hover band shaded and labelled as a literature range.

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

## Results (TBD)

### RQ-P6.6a — energy

| arm | `VDD_IN` mean W | over `A0` | over `A1` | `CPU_GPU_CV` W | `SOC` W | achieved Hz |
|---|---|---|---|---|---|---|
| A0 idle-bare | | — | | | | — |
| A1 idle-deployed | | | — | | | — |
| B carry-640 | | | | | | |
| C carry-512 | | | | | | |
| D ground | | | | | | |

Joules per delivered box, warm vs cold, at idle-window lengths 10 / 30 / 60 / 120 s: TBD.
Maintain as % of hover power (literature range, not measured here): TBD.

### RQ-P6.6b — sustain (G1)

| arm | Hz first 60 s | Hz last 60 s | delta % | `tj` start C | `tj` end C | G1 |
|---|---|---|---|---|---|---|
| B carry-640 | | | | | | |
| C carry-512 | | | | | | |

**Verdict:** TBD.

### Estimate vs actual

| quantity | estimate | actual | note |
|---|---|---|---|
| | | | |

### What did not work

TBD — negative results are content; record them here plainly.

---

## Status / next step

**PRE-REGISTERED, NOT RUN.** Next step is step 0 of *Exact commands* above, in a fresh
session. `run_p66.py` and `maintain_cost_dev.py` are committed alongside this file and
have **never been executed against the device** — their pure parts (tegrastats parsing,
energy integration, the arm scheduler, the G1 rate split) are covered by `tests/test_p66.py` — in `tests/`
rather than beside the scripts, because that is where `pytest.ini`'s `testpaths` looks,
so it actually runs in `make test`.
Expect the first on-device smoke to need a fix; that is what `--smoke` is for.
`make_proof.py` is **not** written yet — it is written against the real
`results.json` at analysis time rather than guessed at now, which is also what DoD-7
means by "reproducible from `runs/*/results.json`".
