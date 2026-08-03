"""Why changing the map killed the panel, and what makes it stop.

Needs a running CARLA on --port. Nothing here touches the Jetson.

A carla.World / carla.Actor handle belongs to ONE episode. `client.load_world()`
starts a new one, and anything still holding an old handle dereferences freed
memory inside libcarla: SIGSEGV or std::terminate in whatever thread got there
first. Neither is a Python exception, so the panel's try/except never sees it --
the process is simply gone. The UI had two such holders: the carry thread (it
caches `world` + the vehicle list for the life of a follow) and the traffic
manager (it steps every vehicle still registered with it).

  stale     carry-shaped reader thread runs across the swap      -> expect DEAD
  driving   cars left on autopilot at swap time                  -> expect DEAD
  fixed     reader joined AND autopilot handed back, then swap   -> expect SURVIVED
  paused    same as fixed, but from synchronous mode             -> expect SURVIVED
  race      like fixed, but the swap follows the spawn instantly -> expect DEAD
            (the traffic manager registers batch-spawned vehicles asynchronously, so
            a handback that arrives before the registration does may not stick)
  destroy   race, but our cars are DESTROYED before the swap      -> expect DEAD
  tmoff     race, but the traffic manager is SHUT DOWN first      -> ?

Run:  .venv-ft/bin/python runners/check_map_swap.py fixed
"""
import argparse
import faulthandler
import random
import sys
import threading
import time

import carla

MODES = ("stale", "driving", "fixed", "paused", "race", "destroy", "tmoff")


def spawn(client, world, n):
    """n autopilot cars, ids only. Same shape as the panel's spawn_vehicles."""
    bps = sorted(world.get_blueprint_library().filter("vehicle.*"), key=lambda b: b.id)
    pts = world.get_map().get_spawn_points()
    random.Random(0).shuffle(pts)
    port = client.get_trafficmanager().get_port()
    batch = [carla.command.SpawnActor(bps[i % len(bps)], p).then(
                 carla.command.SetAutopilot(carla.command.FutureActor, True, port))
             for i, p in enumerate(pts[:n])]
    ids = [r.actor_id for r in client.apply_batch_sync(batch, True) if not r.error]
    world.wait_for_tick()
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=MODES)
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--cars", type=int, default=20)
    args = ap.parse_args()

    # turns the segfault into a traceback that names the guilty thread and line
    faulthandler.enable()

    client = carla.Client("127.0.0.1", args.port)
    client.set_timeout(60.0)
    world = client.get_world()
    here = world.get_map().name.split("/")[-1]
    towns = [m.split("/")[-1] for m in client.get_available_maps()]
    nxt = next(m for m in towns if m != here and m.startswith("Town") and "Opt" not in m)
    print(f"mode={args.mode} {here} -> {nxt}", flush=True)

    ids = spawn(client, world, args.cars)
    print(f"spawned {len(ids)}", flush=True)

    stop = threading.Event()
    steps = {"n": 0}

    def reader():
        """The carry loop's shape: ONE captured world + vehicle list, re-read forever."""
        w = client.get_world()                                    # captured once
        vehicles = [(v, v.bounding_box) for v in w.get_actors().filter("vehicle.*")]
        while not stop.is_set():
            snap = w.get_snapshot()                               # 1 RPC/step
            for v, _bb in vehicles:
                s = snap.find(v.id)
                if s is not None:
                    s.get_transform()
            steps["n"] += 1
            time.sleep(0.03)

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    time.sleep(0.0 if args.mode in ("race", "destroy", "tmoff") else 2.0)
    print(f"reader running, {steps['n']} steps", flush=True)

    if args.mode != "stale":
        stop.set()
        th.join(timeout=15.0)
        print(f"reader joined (alive={th.is_alive()})", flush=True)

    if args.mode not in ("stale", "driving"):
        port = client.get_trafficmanager().get_port()
        for a in world.get_actors(ids):
            a.set_autopilot(False, port)
        world.wait_for_tick()
        print("autopilot handed back", flush=True)

    if args.mode == "destroy":
        client.apply_batch_sync([carla.command.DestroyActor(i) for i in ids], True)
        world.wait_for_tick()
        print("our cars destroyed", flush=True)

    if args.mode == "tmoff":
        client.get_trafficmanager().shut_down()
        print("traffic manager shut down", flush=True)

    if args.mode == "paused":
        s = world.get_settings()
        s.synchronous_mode, s.fixed_delta_seconds = True, 0.05
        world.apply_settings(s)
        client.get_trafficmanager().set_synchronous_mode(True)
        print("paused (sync, nothing ticking)", flush=True)

    print("load_world...", flush=True)
    t0 = time.time()
    client.load_world(nxt)
    print(f"load_world returned in {time.time() - t0:.1f}s", flush=True)

    w = client.get_world()
    if args.mode == "paused":
        # leave the server async, or the next client to connect blocks on a tick
        # nobody is sending
        s = w.get_settings()
        s.synchronous_mode, s.fixed_delta_seconds = False, None
        w.apply_settings(s)
        client.get_trafficmanager().set_synchronous_mode(False)
    if args.mode == "tmoff":
        # a TM that cannot be rebuilt after the swap is not a fix: the panel needs it
        spawn(client, w, 5)
        print("traffic manager rebuilt, 5 cars driving", flush=True)
    time.sleep(3.0)          # the crash lands a beat after the swap, not during it
    print(f"SURVIVED on {w.get_map().name} (reader steps={steps['n']})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
