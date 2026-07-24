#!/usr/bin/env python3
"""P6.2-DELIVERY paired matrix: WARM vs COLD closed-loop follow over N CARLA scenarios.

The flagship Part-VI runner. Boots the EXPENSIVE backends ONCE -- Jetson q8_0 grounding,
3090 SAM2 carry, one airborne SITL copter, one CARLA world+camera -- then, per seeded
scenario: respawns traffic deterministically, screens it (GT-only admission), and flies a
paired WARM and COLD gating flight. Scored by score_p62.score_delivery (exact McNemar
deflated to distinct scenarios). See experiments/2026-07-23-p62-delivery/README.md (frozen).

Faithfulness invariants (D-part6):
- Grounding runs on the Jetson, ALWAYS (quantization moves the box). Carry on the 3090
  (E1 parity 1.000 -> device-identical boxes) rate-capped to the device's 2.69 Hz.
- No latency/throughput number is read off this rig; the verdict is a follow PASS/FAIL.
- Async real-time sim: WARM and COLD share a SCENARIO (seed+target+condition+speed), not a
  byte-identical frame stream -- that non-determinism is the deliberate schedule-noise the
  effect margin must clear (README Determinism).

Run offline logic check:  .venv-ft/bin/python runners/run_p62_matrix.py --selftest
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runners"))

import carla_render as cr
from carla_render import FOV, H, TOWN, W
from run_p62_flight import (MavlinkFlight, OracleStubProducer, actor_box,
                            build_grounding_carry, fly_once, iou, match_actor)
from p62_producers import WarmColdProducer
import score_p62

ACQUIRE_WINDOW_S = 4.85          # E18-n25 cold Jetson acquire wall-clock (the staleness window)
SPEED_BAND_KMH = (6.9, 9.0)      # ~1.9-2.5 m/s on-screen, the E10 real-follow ceiling band
CAPTION = "the police vehicle"   # distinctive target => grounding isolates delivery from
                                 # referring-expression ambiguity (probe6: locks charger IoU
                                 # 0.44 at 45m; 'the car'/'in the center' hit distractors)
TARGET_BP = "vehicle.dodge.charger_police_2020"
RENDER_ALT = 45.0                # nadir AGL where cars ~40px, in the grounder's scale (probe4)


# --- scene composition (once per world) ------------------------------------

def hide_baked_vehicles(world):
    """Town10HD bakes ~48 parked-car MESHES into the map -- not actors, no GT, untrackable,
    yet they dominate single-frame grounding. Hide them so every visible car is a real actor."""
    import carla
    env = []
    for lab in ("Car", "Truck", "Bus", "Motorcycle", "Bicycle"):
        if hasattr(carla.CityObjectLabel, lab):
            env += list(world.get_environment_objects(getattr(carla.CityObjectLabel, lab)))
    if env:
        world.enable_environment_objects({o.id for o in env}, False)
    return len(env)


def densest_base(world, radius=40.0):
    """CARLA (x,y) of the spawn point with the most neighbours within radius = a busy road/
    intersection. NED (0,0) renders here so the flight is over traffic, not the empty plaza."""
    pts = [s.location for s in world.get_map().get_spawn_points()]
    best, bn = None, -1
    for p in pts:
        n = sum(1 for q in pts if q is not p and p.distance(q) < radius)
        if n > bn:
            bn, best = n, p
    return best, bn


def fresh_frame(world, min_advance=4, timeout_ticks=40):
    """Return a camera frame delivered AFTER a big camera move. Async CARLA lags transforms
    by a frame or two; waiting on the frame COUNTER (not N ticks) avoids grounding a stale
    image (the 'look at it' staleness trap that made probe2's overlay lie)."""
    with cr._lock:
        n0 = cr._latest["n"]
    for _ in range(timeout_ticks):
        world.wait_for_tick()
        with cr._lock:
            if cr._latest["n"] - n0 >= min_advance and cr._latest["bgr"] is not None:
                return cr._latest["bgr"].copy()
    with cr._lock:
        return None if cr._latest["bgr"] is None else cr._latest["bgr"].copy()


def spawn_target(world, base):
    """Spawn the distinctive target (police charger) dead-centre on the road base, frozen.
    Returns the actor, or None if the spot is blocked. Caller enables autopilot+speed after
    the G6 grounding frame so the target is centred when the phrase is grounded."""
    import carla
    bp = world.get_blueprint_library().find(TARGET_BP)
    sp = min(world.get_map().get_spawn_points(), key=lambda s: s.location.distance(base))
    for dz in (0.3, 1.0, 2.0):
        t = world.try_spawn_actor(bp, carla.Transform(
            carla.Location(base.x, base.y, sp.location.z + dz), sp.rotation))
        if t is not None:
            t.set_autopilot(False)
            t.set_target_velocity(carla.Vector3D(0, 0, 0))
            for _ in range(8):
                world.wait_for_tick()
            return t
    return None


# --- scenario construction (deterministic in the seed) ---------------------

def _weathers():
    """Condition rotation (covariate, not a factor): (name, params) presets."""
    import carla
    return [("ClearNoon", carla.WeatherParameters.ClearNoon),
            ("CloudyNoon", carla.WeatherParameters.CloudyNoon),
            ("WetNoon", carla.WeatherParameters.WetNoon),
            ("ClearSunset", carla.WeatherParameters.ClearSunset)]


def seed_speed_kmh(k):
    """Target Traffic-Manager speed for scenario k, inside the followable band. Deterministic."""
    lo, hi = SPEED_BAND_KMH
    return round(lo + ((k * 7) % 5) / 4.0 * (hi - lo), 2)   # 5 rungs, seed-varied


def respawn_traffic(world, client, n, seed, weather=None):
    """Destroy current traffic, respawn n vehicles deterministically for `seed`. Returns list.

    Mirrors cr.setup_world's spawn logic but parametrized by seed so each scenario is an
    independent generative draw (README: unit = distinct traffic seed). Reuses the existing
    camera; only the vehicles change.
    """
    import carla
    olds = list(world.get_actors().filter("vehicle.*"))
    if olds:
        client.apply_batch([carla.command.DestroyActor(v) for v in olds])
        for _ in range(8):
            world.wait_for_tick()          # let the destroys land before respawning
    tm = client.get_trafficmanager(8000)
    tm.set_synchronous_mode(False)
    tm.set_random_device_seed(seed)
    rng = random.Random(seed)
    bp_lib = world.get_blueprint_library()
    car_bps = [b for b in bp_lib.filter("vehicle.*")
               if int(b.get_attribute("number_of_wheels")) == 4 and "police" not in b.id]
    spawns = world.get_map().get_spawn_points()
    rng.shuffle(spawns)
    vehicles = []
    for sp in spawns[:n]:
        v = world.try_spawn_actor(rng.choice(car_bps), sp)
        if v is not None:
            v.set_autopilot(True, 8000)
            vehicles.append(v)
    if weather is not None:
        world.set_weather(weather)
    for _ in range(10):
        world.wait_for_tick()              # let autopilot start moving before we screen
    return vehicles, tm


def set_target_speed(tm, target, kmh):
    """Speed-limit the target into the follow band; ignore_lights so it never stalls at a red.

    A target stopped at a red would let COLD tie trivially (README engineers a genuinely
    moving target); the distractors keep obeying lights.
    """
    tm.set_desired_speed(target, kmh)
    tm.ignore_lights_percentage(target, 100)


def verify_grounding_locks(world, cam, target, vehicles, bboxes, acquire, alt, k_frames=8):
    """G6 screen: does the operator's phrase ground OUR target within the idle window?

    Camera nadir over the render base (the frozen target sits dead-centre), then ground CAPTION
    on up to k_frames successive fresh frames -- the warm-start premise is that the pre-prompt
    idle stream gives grounding many shots, not one. Passes on the FIRST frame that locks the
    target (per-frame grounding is ~50-70% here, so a single frame under-admits). Returns
    (locked, log). Genuine screen: if no frame in the window locks, the scenario is rejected.
    `vehicles` must include the target so match_actor can resolve it.
    """
    cam.set_transform(cr.ned_to_carla(0.0, 0.0, -alt, pitch_deg=-90.0))
    attempts = []
    for j in range(k_frames):
        fr = fresh_frame(world)
        if fr is None:
            continue
        box = acquire(fr, W, H)
        snap = world.get_snapshot()
        cam_tf = cam.get_transform()
        on = match_actor(vehicles, bboxes, snap, cam_tf, box, W, H, FOV) if box else None
        gt = actor_box(bboxes[target.id], snap.find(target.id).get_transform(), cam_tf, W, H, FOV)
        li = round(float(iou(box, gt)), 3) if (box and gt) else 0.0
        locked = bool(on is not None and on.id == target.id)
        attempts.append({"j": j, "box": [round(v, 1) for v in box] if box else None,
                         "matched_id": (on.id if on else None), "lock_iou": li})
        if locked:
            return True, {"target_type": target.type_id, "target_id": target.id,
                          "lock_frame": j, "lock_iou": li, "attempts": len(attempts),
                          "locked": True, "box": attempts[-1]["box"]}
    return False, {"target_type": target.type_id, "target_id": target.id,
                   "locked": False, "attempts": len(attempts), "history": attempts[-3:]}


# --- admission (GT-only, before any gating flight) -------------------------

def admit_decision(world_disp, car_len, grounding_locked, oracle_coverage, *, cov_thresh=0.5):
    """Pure admission logic (README screens a + b + G6). Testable without a sim."""
    moved = world_disp >= car_len            # (a) target moved >= 1 box-width in 4.85 s
    followable = oracle_coverage >= cov_thresh   # (b) physically followable at the E10 ceiling
    ok = bool(moved and grounding_locked and followable)
    return ok, {"moved": bool(moved), "grounded": bool(grounding_locked),
                "followable": bool(followable), "world_disp_m": round(world_disp, 2),
                "car_len_m": round(car_len, 2), "oracle_coverage": round(oracle_coverage, 3)}


def screen_target_motion(world, target):
    """(a): target ground displacement over the 4.85 s acquire window, vs its own length."""
    p0 = target.get_transform().location
    t0 = time.time()
    while time.time() - t0 < ACQUIRE_WINDOW_S:
        world.wait_for_tick()
    p1 = target.get_transform().location
    disp = ((p1.x - p0.x) ** 2 + (p1.y - p0.y) ** 2) ** 0.5
    car_len = 2.0 * target.bounding_box.extent.x
    return disp, car_len


# --- per-flight harness ----------------------------------------------------

def flight_args(arm, out, *, t_prompt, seconds, caption, alt, latency=0.0, oracle_drive=False):
    return argparse.Namespace(
        arm=arm, out=str(out), t_prompt=t_prompt, seconds=seconds, caption=caption,
        alt=alt, pitch=-90.0, pose="mavlink", latency=latency, town=TOWN,
        vehicles=0, prune_after=32, ssh_host="jetson", oracle_drive=oracle_drive)


def one_flight(arm, world, cam, vehicles, target, bboxes, flight, producer, out, *,
               t_prompt, seconds, caption, alt, scenario, reset=True, oracle_drive=False):
    """Reset copter (unless caller already did), run one fly_once, stamp scenario. Returns res|None."""
    if reset:
        flight.reset()
    args = flight_args(arm, out, t_prompt=t_prompt, seconds=seconds, caption=caption,
                       alt=alt, oracle_drive=oracle_drive)
    try:
        res = fly_once(world, cam, vehicles, target, bboxes, producer.slot, producer, flight, args, out)
    except Exception as e:
        print(f"  [{arm} seed{scenario}] fly_once FAILED: {type(e).__name__}: {e}", flush=True)
        return None
    finally:
        producer.close()
    res["scenario"] = scenario
    (Path(out) / "results.json").write_text(json.dumps(res, indent=2))
    return res


def _spawn_scene(world, client, seed, weather, base, kmh):
    """Distractor traffic + a FROZEN centred target. The target is released by the CALLER at
    flight-loop start (after flight.reset()), NOT here: releasing before the copter reaches its
    start pose lets the target drive off-frame during the reset, so the WARM seed lands off-screen
    (pilot bug: seed_box x=-129). Returns (all_vehicles_incl_target, target, tm) or (None,None,None)."""
    vehicles, tm = respawn_traffic(world, client, 40, seed, weather)
    if not vehicles:
        return None, None, None
    target = spawn_target(world, base)          # frozen at centre (spawn_target holds it 8 ticks)
    if target is None:
        return None, None, None
    return vehicles + [target], target, tm


def run_scenario(k, seed, world, client, cam, base, alt, acquire, carry_factory, flight,
                 t_prompt, seconds, screen_seconds, out_root, reps, oracle=False):
    """Screen scenario k; if admitted, fly paired WARM+COLD (with rep flights). Returns record.

    oracle=True isolates the closed-loop DELIVERY variable from the nadir-grounding
    center-bias (probe8: off-centre target lock 0/8 -- the deployed q8_0 grounder is
    non-discriminative among clutter at 45m nadir). The operator DESIGNATES the target
    (GT box seeds the real SAM2 carry); grounding is removed from the quantitative arm.
    WARM vs COLD is then pure warm-start delivery: idle-follow vs a ~4.85s stale acquire.
    G6 (grounding screen) is skipped; admission is motion (a) + oracle-followability (b).
    """
    wname, weather = _weathers()[k % 4]
    kmh = seed_speed_kmh(k)
    vehicles, tm = respawn_traffic(world, client, 40, seed, weather)
    if not vehicles:
        return {"scenario": k, "seed": seed, "admitted": False, "reason": "no vehicles spawned"}
    target = spawn_target(world, base)                       # dedicated charger, frozen at centre
    if target is None:
        return {"scenario": k, "seed": seed, "admitted": False, "reason": "target spot blocked"}
    allv = vehicles + [target]
    bboxes = {v.id: v.bounding_box for v in allv}           # cache the ~17ms RPC once

    if oracle:
        glog = {"oracle": True, "source": "operator-designation (GT box)"}
    else:
        # G6: does 'the police vehicle' ground OUR charger? (genuine screen, target is known)
        locked, glog = verify_grounding_locks(world, cam, target, allv, bboxes, acquire, alt)
        if not locked:
            print(f"  seed{k} seed_val={seed} REJECT grounding: {glog}", flush=True)
            return {"scenario": k, "seed": seed, "admitted": False, "reason": "grounding", "grounding": glog}
    target.set_autopilot(True, 8000)                        # release the target to drive
    set_target_speed(tm, target, kmh)
    for _ in range(6):
        world.wait_for_tick()

    # -- admission screens (a) motion, (b) followability --
    disp, car_len = screen_target_motion(world, target)
    oscreen = out_root / f"screen_seed{k:02d}"
    flight.reset()
    oracle_prod = OracleStubProducer(_fresh_slot(), latency_s=0.0)
    oargs = flight_args("oracle", oscreen, t_prompt=t_prompt, seconds=screen_seconds, caption="", alt=alt)
    try:
        ores = fly_once(world, cam, allv, target, bboxes, oracle_prod.slot, oracle_prod,
                        flight, oargs, oscreen)
        coverage = float(ores["coverage"])
    except Exception as e:
        print(f"  [screen seed{k}] oracle FAILED: {type(e).__name__}: {e}", flush=True)
        coverage = 0.0
    finally:
        oracle_prod.close()

    admitted, info = admit_decision(disp, car_len, True, coverage)  # G6 already passed above
    info.update(seed=seed, kmh=kmh, weather=wname, target_type=target.type_id, grounding=glog)
    print(f"  seed{k} seed_val={seed} admit={admitted} {info}", flush=True)
    rec = {"scenario": k, "seed": seed, "admitted": admitted,
           "target_type": target.type_id, "screen": info}
    if not admitted:
        return rec

    # -- paired gating flights (WARM then COLD); caller sets reps>1 for noise-band seeds --
    for arm in ("warm", "cold"):
        for r in range(reps):
            allv2, tgt, tm2 = _spawn_scene(world, client, seed, weather, base, kmh)  # frozen target
            if tgt is None:
                print(f"  [{arm} seed{k}] scene respawn blocked -- skip flight", flush=True)
                continue
            bb = {v.id: v.bounding_box for v in allv2}
            tag = f"{arm}_seed{k:02d}" + (f"_r{r}" if reps > 1 else "")
            flight.reset()                                  # copter to origin; target STILL frozen at centre
            tgt.set_autopilot(True, 8000)                   # release NOW: target starts from centre, in-frame
            set_target_speed(tm2, tgt, kmh)
            for _ in range(2):
                world.wait_for_tick()
            prod = WarmColdProducer(_fresh_slot(), acquire, carry_factory,
                                    mode=arm, t_prompt=t_prompt, w=W, h=H,
                                    oracle_gt=oracle, cold_latency_s=ACQUIRE_WINDOW_S)
            res = one_flight(arm, world, cam, allv2, tgt, bb, flight, prod, out_root / tag,
                             t_prompt=t_prompt, seconds=seconds, caption=CAPTION, alt=alt,
                             scenario=k, reset=False)         # already reset+released above
            if res is not None:
                print(f"  [{tag}] coverage={res['coverage']} lock_frames={res['genuine_lock_frames']}"
                      f" seeded={res['producer'].get('seeded')}", flush=True)
    return rec


def _fresh_slot():
    from run_p62_flight import LatestDetectionSlot
    return LatestDetectionSlot()


# --- driver ----------------------------------------------------------------

def run(args):
    import carla
    out_root = Path(args.out); out_root.mkdir(parents=True, exist_ok=True)
    client = carla.Client(args.host, args.port); client.set_timeout(60.0)
    print(f"connected: server {client.get_server_version()}", flush=True)
    world, cam, _ = cr.setup_world(client, args.town, args.vehicles)   # boots world+camera once
    n_hidden = hide_baked_vehicles(world)                             # remove untrackable parked cars
    base, nbr = densest_base(world)                                   # render over the busiest road
    cr.BASE_N, cr.BASE_E = float(base.x), float(base.y)
    mode_str = "ORACLE-DESIGNATION (grounding removed; GT-box seed)" if args.oracle else f"VLM grounding caption='{CAPTION}'"
    print(f"hid {n_hidden} baked vehicle meshes; render base CARLA=({base.x:.1f},{base.y:.1f}) "
          f"neighbours={nbr}; alt={args.alt}m mode={mode_str}", flush=True)

    backend, acquire, carry_factory, close_backends = build_grounding_carry(
        CAPTION, args.prune_after, args.ssh_host, out_root / "_acq")
    flight = MavlinkFlight(args.mavlink_url, args.alt, kp_lat=args.kp_lat, max_v=args.max_v)

    bank, k, attempt = [], 0, 0
    try:
        while len(bank) < args.n and attempt < args.max_attempts:
            seed = args.seed0 + attempt * 101
            reps = args.reps if k < args.noise_band else 1
            rec = run_scenario(k, seed, world, client, cam, base, args.alt, acquire, carry_factory,
                               flight, args.t_prompt, args.seconds, args.screen_seconds,
                               out_root, reps=reps, oracle=args.oracle)
            attempt += 1
            (out_root / "bank.jsonl").open("a").write(json.dumps(rec) + "\n")
            if rec["admitted"]:
                bank.append(rec); k += 1
        print(f"admitted {len(bank)}/{args.n} scenarios in {attempt} attempts", flush=True)
        if len(bank) < args.n:
            print(f"WARNING: admission short of target ({len(bank)}<{args.n}) at "
                  f"max_attempts={args.max_attempts} -- scored on what admitted", flush=True)
    finally:
        flight.close()
        close_backends()
        cam.stop(); cam.destroy()
        client.apply_batch([carla.command.DestroyActor(v)
                            for v in world.get_actors().filter("vehicle.*")])

    delivery = score_p62.score_delivery(out_root)
    (out_root / "delivery.json").write_text(json.dumps(delivery, indent=2))
    print(json.dumps(delivery, indent=2))
    print("NOT verified until the written overlays are opened and viewed.")
    return delivery


# --- P6.2-COUPLING: re-fly the admitted DELIVERY seeds, DECOUPLED (oracle drives) ----

def _admitted_from_bank(coupled_root):
    """Admitted (scenario, seed) pairs from a DELIVERY run's bank.jsonl -- the coupled
    arm's own seeds, re-flown decoupled so the only difference is who steers the PID."""
    bank = Path(coupled_root) / "bank.jsonl"
    if not bank.exists():
        raise SystemExit(f"no bank.jsonl under {coupled_root} -- run DELIVERY first")
    recs = [json.loads(l) for l in bank.read_text().splitlines() if l.strip()]
    return [(r["scenario"], r["seed"]) for r in recs if r.get("admitted")]


def refly_decoupled(k, seed, world, client, cam, base, alt, carry_factory, flight,
                    t_prompt, seconds, out_root):
    """One DECOUPLED warm flight for admitted scenario k: identical warm perception
    (oracle_gt seed + SAM2 carry) but the oracle actor_box drives the PID. Same scene
    construction as the coupled DELIVERY WARM arm (respawn_traffic + frozen centred
    target), so the pair differs only in the control input. Returns res|None."""
    wname, weather = _weathers()[k % 4]
    kmh = seed_speed_kmh(k)
    allv, tgt, tm = _spawn_scene(world, client, seed, weather, base, kmh)   # frozen centred target
    if tgt is None:
        print(f"  [decoupled seed{k}] scene respawn blocked -- skip", flush=True)
        return None
    bb = {v.id: v.bounding_box for v in allv}
    flight.reset()                                     # copter to origin; target STILL frozen at centre
    tgt.set_autopilot(True, 8000)                      # release NOW: target starts centred, in-frame
    set_target_speed(tm, tgt, kmh)
    for _ in range(2):
        world.wait_for_tick()
    prod = WarmColdProducer(_fresh_slot(), None, carry_factory,       # acquire=None: oracle seed only
                            mode="warm", t_prompt=t_prompt, w=W, h=H,
                            oracle_gt=True, cold_latency_s=ACQUIRE_WINDOW_S)
    res = one_flight("decoupled", world, cam, allv, tgt, bb, flight, prod,
                     out_root / f"decoupled_seed{k:02d}",
                     t_prompt=t_prompt, seconds=seconds, caption=CAPTION, alt=alt,
                     scenario=k, reset=False, oracle_drive=True)
    if res is not None:
        print(f"  [decoupled_seed{k:02d}] coverage={res['coverage']} "
              f"lock_frames={res['genuine_lock_frames']} seeded={res['producer'].get('seeded')}",
              flush=True)
    return res


def run_coupling(args):
    """P6.2-COUPLING driver: re-fly every admitted DELIVERY seed with the DECOUPLED arm
    (oracle drives the PID), then Wilcoxon coupled-vs-decoupled per-seed follow-error.
    Coupled arm = the DELIVERY WARM flights, reused from disk (never re-flown)."""
    import carla
    if Path(args.out).resolve() == Path(args.coupled_root).resolve():
        raise SystemExit("--out must differ from --coupled-root (would clobber the coupled arm)")
    admitted = _admitted_from_bank(args.coupled_root)
    out_root = Path(args.out); out_root.mkdir(parents=True, exist_ok=True)
    client = carla.Client(args.host, args.port); client.set_timeout(60.0)
    print(f"connected: server {client.get_server_version()}; {len(admitted)} admitted seeds "
          f"from {args.coupled_root}", flush=True)
    world, cam, _ = cr.setup_world(client, args.town, args.vehicles)
    n_hidden = hide_baked_vehicles(world)
    base, nbr = densest_base(world)
    cr.BASE_N, cr.BASE_E = float(base.x), float(base.y)
    print(f"hid {n_hidden} baked meshes; render base=({base.x:.1f},{base.y:.1f}) nbr={nbr}; "
          f"alt={args.alt}m DECOUPLED (oracle drives PID; warm track scored, not steering)", flush=True)

    _, _, carry_factory, close_backends = build_grounding_carry(   # carry_only: no Jetson boot
        CAPTION, args.prune_after, args.ssh_host, out_root / "_acq", carry_only=True)
    flight = MavlinkFlight(args.mavlink_url, args.alt, kp_lat=args.kp_lat, max_v=args.max_v)
    try:
        for k, seed in admitted:
            refly_decoupled(k, seed, world, client, cam, base, args.alt, carry_factory, flight,
                            args.t_prompt, args.seconds, out_root)
    finally:
        flight.close()
        close_backends()
        cam.stop(); cam.destroy()
        client.apply_batch([carla.command.DestroyActor(v)
                            for v in world.get_actors().filter("vehicle.*")])

    coupling = score_p62.score_coupling(args.coupled_root, out_root)
    (out_root / "coupling.json").write_text(json.dumps(coupling, indent=2))
    print(json.dumps(coupling, indent=2))
    print("NOT verified until the written overlays are opened and viewed.")
    return coupling


# --- P6.2-SHOWCASE: one WARM flight, SAM2 carry routed LITERALLY to the Jetson --------

def run_showcase(args):
    """P6.2-SHOWCASE flight half: ONE closed-loop WARM flight whose SAM2 carry runs on the
    Orin over ssh-stdio (build_grounding_carry showcase_ssh=True), with a 3090 twin scored
    for in-rig parity. Reuses the DELIVERY geometry EXACTLY -- densest_base render + a frozen
    centred target released from centre -- so the target is in-frame at the warm seed (the
    run_p62_flight nearest-to-origin path seeded off-screen). Oracle designation, no grounding
    in the loop (P6's novelty is the loop, not grounding). parity.json is written by the carry's
    close() into out/_acq."""
    import carla
    out_root = Path(args.out); out_root.mkdir(parents=True, exist_ok=True)
    client = carla.Client(args.host, args.port); client.set_timeout(60.0)
    print(f"connected: server {client.get_server_version()}", flush=True)
    world, cam, _ = cr.setup_world(client, args.town, args.vehicles)
    n_hidden = hide_baked_vehicles(world)
    base, nbr = densest_base(world)
    cr.BASE_N, cr.BASE_E = float(base.x), float(base.y)
    print(f"hid {n_hidden} baked meshes; render base=({base.x:.1f},{base.y:.1f}) nbr={nbr}; "
          f"alt={args.alt}m SHOWCASE (carry on Jetson via ssh-stdio; 3090 twin for parity)",
          flush=True)

    backend, acquire, carry_factory, close_backends = build_grounding_carry(
        CAPTION, args.prune_after, args.ssh_host, out_root / "_acq", showcase_ssh=True)
    flight = MavlinkFlight(args.mavlink_url, args.alt, kp_lat=args.kp_lat, max_v=args.max_v)
    res = None
    try:
        wname, weather = _weathers()[0]
        kmh = seed_speed_kmh(0)
        allv, tgt, tm = _spawn_scene(world, client, args.seed0, weather, base, kmh)
        if tgt is None:
            raise SystemExit("showcase: target spawn blocked -- rerun (traffic occupies the centre)")
        bb = {v.id: v.bounding_box for v in allv}
        flight.reset()                                  # copter to origin; bridge model-loads meanwhile
        tgt.set_autopilot(True, 8000)                   # release from centre -> in-frame at warm seed
        set_target_speed(tm, tgt, kmh)
        for _ in range(2):
            world.wait_for_tick()
        prod = WarmColdProducer(_fresh_slot(), acquire, carry_factory,
                                mode="warm", t_prompt=args.t_prompt, w=W, h=H,
                                oracle_gt=True, cold_latency_s=ACQUIRE_WINDOW_S)
        res = one_flight("warm", world, cam, allv, tgt, bb, flight, prod, out_root / "flight",
                         t_prompt=args.t_prompt, seconds=args.seconds, caption=CAPTION,
                         alt=args.alt, scenario=0, reset=False)
    finally:
        flight.close()
        close_backends()                                # writes _acq/parity.json
        cam.stop(); cam.destroy()
        client.apply_batch([carla.command.DestroyActor(v)
                            for v in world.get_actors().filter("vehicle.*")])
    if res is not None:
        print(f"coverage={res['coverage']} lock_frames={res['genuine_lock_frames']} "
              f"seeded={res['producer'].get('seeded')} seed_box={res['producer'].get('seed_box')}",
              flush=True)
    print("NOT verified until the written overlays + parity.json are opened and viewed.")
    return res


# --- offline selftest (pure logic; no CARLA / no Jetson) -------------------

def _selftest():
    # speed band: every scenario's target speed sits inside the followable band
    lo, hi = SPEED_BAND_KMH
    speeds = {seed_speed_kmh(k) for k in range(25)}
    assert all(lo <= s <= hi for s in speeds), speeds
    assert len(speeds) >= 4, f"speed draw not varied enough: {speeds}"

    # condition rotation cycles through the 4 presets
    assert len({k % 4 for k in range(4)}) == 4

    # admission: all three screens must pass
    ok, info = admit_decision(world_disp=5.0, car_len=4.0, grounding_locked=True, oracle_coverage=0.8)
    assert ok and info["moved"] and info["grounded"] and info["followable"], info
    assert not admit_decision(3.0, 4.0, True, 0.8)[0], "static target must be rejected"   # (a) fails
    assert not admit_decision(5.0, 4.0, False, 0.8)[0], "grounding miss must be rejected"  # G6 fails
    assert not admit_decision(5.0, 4.0, True, 0.3)[0], "unfollowable must be rejected"      # (b) fails

    # displacement math: a target moving 2 m/s for 4.85 s covers ~9.7 m >> a ~4.6 m car
    disp = 2.0 * ACQUIRE_WINDOW_S
    assert admit_decision(disp, 4.6, True, 0.6)[0], "a 2 m/s target should clear screen (a)"
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--town", default=TOWN)
    ap.add_argument("--vehicles", type=int, default=40)
    ap.add_argument("--mavlink-url", default="tcp:127.0.0.1:5760")
    ap.add_argument("--alt", type=float, default=RENDER_ALT)
    ap.add_argument("--n", type=int, default=25, help="admitted scenarios to reach")
    ap.add_argument("--noise-band", type=int, default=3, help="first B seeds get --reps reps/arm")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--t-prompt", type=float, default=8.0)
    ap.add_argument("--seconds", type=float, default=20.0, help="gating flight length")
    ap.add_argument("--screen-seconds", type=float, default=14.0, help="oracle screen flight length")
    ap.add_argument("--seed0", type=int, default=20260723)
    ap.add_argument("--max-attempts", type=int, default=60, help="cap seed draws (no silent loop)")
    ap.add_argument("--prune-after", type=int, default=32)
    ap.add_argument("--kp-lat", type=float, default=0.05,
                    help="PID lateral gain (m/s per px); 0.02 default lags at 2.69Hz carry")
    ap.add_argument("--max-v", type=float, default=4.0, help="PID velocity clamp (m/s)")
    ap.add_argument("--ssh-host", default="jetson")
    ap.add_argument("--oracle", action="store_true",
                    help="operator-designation arm: seed carry from GT box, skip G6 grounding "
                         "(isolates closed-loop delivery from the nadir-grounding center-bias)")
    ap.add_argument("--out", default="runs/p62_delivery")
    ap.add_argument("--showcase", action="store_true",
                    help="P6.2-SHOWCASE: ONE warm flight, SAM2 carry on the Jetson via ssh-stdio "
                         "(3090 twin scored for parity); reuses the DELIVERY centred-target geometry")
    ap.add_argument("--coupling", action="store_true",
                    help="P6.2-COUPLING: re-fly admitted DELIVERY seeds DECOUPLED (oracle drives "
                         "the PID); coupled arm = the DELIVERY WARM flights, reused from disk")
    ap.add_argument("--coupled-root", default="runs/p62_delivery",
                    help="(coupling) DELIVERY run whose admitted WARM flights are the coupled arm")
    args = ap.parse_args()
    if args.selftest:
        _selftest(); return
    if args.showcase:
        run_showcase(args); return
    if args.coupling:
        run_coupling(args); return
    run(args)


if __name__ == "__main__":
    main()
