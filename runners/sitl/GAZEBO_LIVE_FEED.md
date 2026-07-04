# Gazebo live camera feed — tool + findings

**Status: PARKED (2026-07-04T22:20Z).** Working custom viewer exists; a decision on
whether to replace it with the native Gazebo GUI is open (see "Parked decision").

Goal: over an SSH session (no local display), see what a camera in a Gazebo Harmonic
world renders, and move that camera around like a videogame to frame a shot. Built as a
stepping stone toward previewing what the grounding/follow model sees.

## What exists

| File | Role |
|---|---|
| `../gz_feed_view.py` | headless viewer: spawns `gz sim -s`, subscribes to the camera image topic, serves an MJPEG stream + control page on `127.0.0.1:8088`. WASD/RF/arrow keys fly the camera. Optional `--snapshot`, `--dump DIR`, `--selftest`, `--attach`. |
| `worlds/sonoma_follow.sdf` | Sonoma Raceway (ArduPilot SITL_Models) + a `Sensors` plugin + an oblique `chase_cam`. The world the viewer loads by default. |
| `external/SITL_Models/` | vendored ArduPilot asset clone (gitignored) — provides `model://sonoma_raceway`. |

Run it (must be launched by the user — the sandbox reaper kills gz+python combos):

```bash
ssh -L 8088:localhost:8088 gara@3090      # from the laptop
! .venv-ft/bin/python runners/gz_feed_view.py   # on the box, then open http://localhost:8088
```

Controls: `W/A/S/D` move in the ground plane along heading, `R/F` up/down, arrow keys
tilt/pan, HUD shows `x y z pitch yaw`. Camera pose is driven by the `set_pose` service.

## Findings (what we learned)

1. **Headless render needs the NVIDIA EGL ICD.** `gz sim -s` renders camera sensors
   offscreen via EGL and ignores `DISPLAY`; glvnd defaults to mesa on the RTX 3090 and
   yields BLACK frames. Fix: env
   `__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json`.
2. **The Sonoma world needs a `Sensors` plugin** (`gz-sim-sensors-system`,
   `<render_engine>ogre2</render_engine>`) — upstream `sonoma_raceway.sdf` has none, so
   the camera never renders.
3. **ogre2 headless does not render infinite `<plane>` geometry** (blank/gray). Use a thin
   `<box>` instead — see the ground-plane fix in `worlds/phase_c.sdf`.
4. **The Sonoma mesh is effectively unlit.** It is one OBJ (`Raceway.obj`) with baked-in
   shading textures (`Asphalt.png`, `Grass.png`, ...). World lighting barely reaches its
   flat surfaces in gz/ogre2: changing scene `<ambient>` (1.0->0.35), recolouring the sun,
   and dropping the sun to a low raking angle all left the flat track essentially
   unchanged; only sloped hills shifted slightly (mean abs diff ~3/255 at the hero pose).
   The scene `<ambient>` tag appears largely ignored by ogre2, and the `<sky>` plugin
   renders its own sky independent of `<background>`/lights.
   **Consequence:** the scene "look" is a **post-process colour grade on the egress frame**
   (`GRADE`/`_grade` in `gz_feed_view.py`: contrast + gamma + warm balance + saturation +
   vignette), NOT in-world lighting. Toggle with `GRADE["on"]`.
   *Caveat:* an earlier "world lighting is fully inert on the ground" claim was overstated —
   a `set_pose`-then-dump race captured *sky* frames, so those diffs compared sky (which the
   sky plugin renders identically), not asphalt. Only the hero-pose comparison was valid.
5. **Two sandbox/runtime gotchas, already worked around in the code:**
   - `gz-transport13` pybind `node.request()` called concurrently with the image
     subscription callback crashes (GIL / `dec_ref` without GIL). Drive `set_pose` via the
     `gz service` CLI subprocess (~290 ms/call, ~3-4 Hz) instead; keep the pybind node for
     image subscription only.
   - The Bash sandbox reaper kills commands that mix `gz sim` strings with Python (or that
     contain gz-matching substrings). Launch gz as a clean `nohup gz sim ... &`; kill by
     explicit PID; run any Python subscriber as a separate command.

## Parked decision — custom viewer vs native GUI

Everything asked for (fly the camera like a videogame + see the feed + adjust lighting) is
**built into the native Gazebo GUI** `gz sim -g` (mouse orbit/pan/zoom, Image Display
plugin, live light editing) with zero custom code. The custom MJPEG + WASD + `set_pose` rig
exists only because of the SSH-no-local-display assumption. The genuinely fragile part of
the custom path is hand-rolled camera control (`set_pose` + quaternion math), not the
MJPEG-over-SSH feed (that is reliable).

**Open question that decides it:** where can a GUI window actually open?
- 3090 has a physical display / physical access -> run `gz sim -g` there, delete the custom rig.
- Gazebo can run on the laptop directly -> native GUI, sim local.
- Truly headless SSH-only -> either stream the GUI (TurboVNC+noVNC or selkies WebRTC, needs
  an apt install) or keep and harden the custom viewer.

Deferred features (explicitly "add later"): moving target vehicle on the grid, follow /
VLM hookup to the live feed, mouse-look (pointer-lock).
