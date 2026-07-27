# Supervisor scope steer — 2026-07-27T12:57Z

Status: **recorded, not acted on.** No experiment is pre-registered and no Part VII exists
as a result of this document. The author explicitly deferred that on 2026-07-27
("don't write any experiments or parts yet, though document this"). This file exists so the
steer and its measured consequences are on disk instead of in a chat log.

## What the supervisor said

Relayed by the author, 2026-07-27, three items:

1. **Focus on the tracking.** The thesis emphasis moves off single-frame grounding and onto
   the tracking side.
2. **The system will be tested on a real drone, and the piloting has to be tested too.**
3. **By September the airframe must be chosen** so the department can acquire it — roughly a
   2-3 month horizon. September's deliverable is a *drone selection*, not a flight.

Two things were asked for and are **not yet known**: the airframe (onboard Jetson vs offboard
link is undecided, the supervisor provides the vehicle) and the venue/pilot arrangement.
Both are open fields, not defaults.

The target regime, which was not previously anywhere in this repository: **attack drones at
200 km/h**, plus a failsafe requirement stated as "make the drone not kill itself".

## Why this matters more than a page rebalance

Every number in Parts I-VI was measured against ground vehicles. UAV123 cars, CARLA nadir at
45 m, a SITL follow-controller ceiling of **2,5 m/s**. The stated target moves at
**55,6 m/s** — a **22,2x** speed ratio against the fastest ownship motion ever measured here.
That is not a harder instance of the measured problem; it is a different regime, and the
thesis cannot silently inherit its numbers into it.

## The arithmetic, before any experiment

Computed by `thesis/speed_envelope.py` (committed, reproducible, self-checking). Measured
inputs are from the registry: carry **2,69 Hz** (`P4-R16-carry-rate-1024`, Orin, image_size
1024, solo, 15 W), cold acquire **4,85 s** (E18), follow ceiling **2,5 m/s** (E9-E17, SITL,
flat synthetic nadir). **Assumed** inputs — a 60 deg / 1920 px forward camera and a 50 px
inter-frame tracker tolerance — are assumptions, not measurements, and they set the geometry.
Marked as estimates per the prime directive.

Scalar consequences at 55,6 m/s:

| Quantity | Value |
|---|---|
| World motion between carry frames @ 2,69 Hz | **20,7 m** |
| Distance flown during a 4,85 s cold acquire | **269,4 m** |
| Target speed / measured ownship follow ceiling | **22,2x** |

Crossing geometry (worst case), inter-frame pixel displacement at the deployed 2,69 Hz:

| Range (m) | deg/s | px/s | px per carry frame | Hz needed for <50 px | FOV dwell (s) |
|---:|---:|---:|---:|---:|---:|
| 50 | 63,7 | 2037 | 757 | 40,7 | 1,04 |
| 100 | 31,8 | 1019 | 379 | 20,4 | 2,08 |
| 200 | 15,9 | 509 | 189 | 10,2 | 4,16 |
| 400 | 8,0 | 255 | 95 | 5,1 | 8,31 |
| 800 | 4,0 | 127 | 47 | **2,5** | 16,63 |

Approaching head-on — the *favourable* geometry, because a closing target has near-zero
angular rate and only grows in apparent size: 20,7 m of closure per frame, which is 5,4 %
apparent-size growth at 400 m rising to 70,4 % at 50 m.

### What this says

- **Cold acquire is not merely worse, it is dead.** 269 m of travel inside one blocking
  acquire. This *strengthens* the thesis rather than threatening it: at 200 km/h,
  maintain-and-deliver is not the better option, it is the only one. The R-28 scope decision
  (defend maintain-and-deliver, not select) survives this steer intact — maintain-and-deliver
  *is* the tracking claim the supervisor asked to focus on.
- **The deployed 2,69 Hz contract survives only at long range against a crossing target** —
  about 800 m on the assumed optics — and degrades to needing 40 Hz at 50 m. The engagement
  envelope is a *range* band, not a yes/no, and nobody has measured where it actually falls.
- **Head-on interception is the tractable geometry.** If the mission is intercepting an
  inbound threat rather than pursuing a crossing one, angular rate collapses and the binding
  problem becomes scale growth and re-detection, not displacement. Which geometry applies is
  a mission question for the supervisor, and it changes the answer completely.
- **The Part V premise needs re-examination at this speed.** "The pre-prompt window is free
  compute" assumed an idle stream of seconds-to-minutes. A crossing target at 200 m is inside
  a 60 deg FOV for **4,16 s** total. The idle window still exists, but it is now comparable to
  the cold-acquire time it was introduced to hide — which is exactly the quantity the premise
  depends on being large. This is a genuine open threat to the central chapter, not a caveat.

None of the above is a result. It is closed-form scoping arithmetic over already-measured
inputs, and its purpose is to show that the September airframe choice is a *requirements*
problem that can be attacked from the existing rig with no new hardware.

## Consequences for the writing programme

Against `thesis/REMEDIATION.md`:

- **W-4 resolves, in the "budget moves" direction.** cap08 is budgeted at 4 pages against an
  8-9 page scaffold. With tracking and real flight as the focus, the scaffold is right and the
  budget is wrong. No rewriting needed.
- **W-2 inverts.** It read "cap04 is the weakest chapter and needs the most work" — 2 930
  words / 26 specs against an 11-page target. cap04 is single-frame grounding (Parts I-II),
  which this steer de-prioritises. The correct action is to shrink the budget to fit the
  scaffold, not to thicken the scaffold. This is a *reduction* in work.
- **W-3 narrows.** Part III has no `proof/` and Part III is tracking, so those figures stay
  mandatory. The Part I-II figures (fidelity gap, backbone bake-off) drop to optional, since
  they fed the chapter that is now shrinking.
- **W-1 stays deferred, for a new reason.** Not "scope unconfirmed" any more — scope is now
  confirmed. It waits because cap08 cannot be written around a campaign that does not exist,
  and because the speed-regime threat above may change what caps 7 and 9 are allowed to claim.
  Caps 1-7 and 9-10 are not blocked by the airframe.
- **cap09 gains a threat that did not exist before.** Every result in this thesis was measured
  in a speed regime 22x below the stated target. That belongs in "amenazas a la validez"
  whether or not anything ever flies.

## Proposed page rebalance — PROPOSED, NOT APPLIED

`00-esquema.md` is **unmodified**. This is the proposal awaiting the author's decision;
zero-sum at the existing 80-page body, so it is a redistribution and not a request for room.

| Cap. | Title | R-18 budget | Proposed | Rationale |
|---|---|---:|---:|---|
| 1 | Introducción | 5 | 5 | — |
| 2 | Estado del arte | 8 | **6** | Thinnest scaffold (22 specs), the only chapter that defends nothing |
| 3 | Plataforma, método, métricas | 10 | 10 | — |
| 4 | Grounding de un solo frame | 11 | **7** | De-prioritised by the steer; also fits its actual scaffold, closing W-2 by reduction |
| 5 | Permanencia de objeto | 11 | 11 | Tracking core — untouched |
| 6 | El arco de la latencia | 8 | **6** | Zero Holm survivors, 14/15 claims at n_eff <= 6; the E18 n=25 survivor stays |
| 7 | Grounding anticipatorio | 12 | 12 | Tracking core, carries the one properly-powered claim — untouched |
| 8 | Del lazo cerrado simulado al vuelo real | 4 | **12** | Absorbs P6.2 at its real scaffold size and leaves room for the real-flight half |
| 9 | Amenazas a la validez | 7 | 7 | Content grows (speed regime) but the budget holds |
| 10 | Conclusiones y trabajo futuro | 4 | 4 | — |

Total 80, unchanged. -8 from caps 2/4/6, +8 to cap08.

Real flight is proposed to live **inside cap08 as its second half**, not as an eleventh
chapter; splitting it later is one line in `thesis/borrador/assemble.py`'s `CHAPTERS` list.

What is given up by this proposal, stated so it is auditable: cap04 loses 4 pages of
single-frame grounding narrative, which is where Parts I-II live, so the exploratory campaign
work compresses to near-table form. cap02's literature coverage thins by 2 pages. cap06 loses
2 more pages on top of the 2 that R-18 already took, leaving E2-E17 close to pure tabulation.

## Open fields — needed before any Part VII can be designed

1. **Airframe and where the compute sits.** Onboard Jetson vs video-down/commands-up. This
   changes the latency contract, not just the packaging.
2. **Engagement geometry.** Head-on interception vs crossing pursuit. Per the table above
   these differ by more than an order of magnitude in tracker demand.
3. **Sensor.** FOV and resolution are currently assumed; every pixel figure here moves with them.
4. **Venue, pilot, and what "not kill itself" is measured as.** Failsafe behaviour is
   qualitative until someone writes the pass criterion.
5. **Whether a real flight lands inside the thesis timeline at all**, or whether September's
   airframe choice is the deliverable and flight is future work in cap10.

## Not done here, deliberately

No `experiments/PART7-*` proposal, no campaign directory, no matrix, no pre-registration, no
edit to `00-esquema.md` or the chapter scaffolds. The author deferred all of it on 2026-07-27.
