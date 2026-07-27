"""Part VII scoping arithmetic: what a 200 km/h target does to the measured contract.

Closed-form, no simulation — this exists to *size* the problem before any experiment is
pre-registered, per the 2026-07-27 supervisor steer (`thesis/SCOPE-2026-07-27-supervisor-steer.md`).

Measured inputs (all from the registry, not invented):
  CARRY_HZ   2.69  P4-R16-carry-rate-1024, Orin Nano, image_size 1024, solo, 15 W
  ACQUIRE_S  4.85  E18 cold blocking acquire
  FOLLOW_MS  2.5   E9-E17 SITL follow-controller ceiling (flat synthetic nadir texture)

Assumed inputs (NOT measured — they set the geometry and must be replaced once the
airframe and sensor are chosen):
  FOV_DEG, PX_W   a 60 deg / 1920 px forward camera
  TOL_PX          50 px of inter-frame displacement as the tracker's tolerance

ponytail: closed form, not a sim. Swap the assumed block when the sensor is picked.
"""

import math

V_KMH = 200.0
V = V_KMH / 3.6  # 55.6 m/s

# measured
CARRY_HZ = 2.69
ACQUIRE_S = 4.85
FOLLOW_MS = 2.5

# assumed — see docstring
FOV_DEG, PX_W = 60.0, 1920.0
TOL_PX = 50.0

PX_PER_DEG = PX_W / FOV_DEG
RANGES_M = (50, 100, 200, 400, 800)


def crossing_row(range_m, carry_hz=CARRY_HZ, v=V):
    """Worst-case geometry: target crosses the frame perpendicular to the line of sight."""
    deg_s = math.degrees(v / range_m)
    px_s = deg_s * PX_PER_DEG
    return deg_s, px_s, px_s / carry_hz, px_s / TOL_PX


def fov_dwell_s(range_m, v=V, fov_deg=FOV_DEG):
    """Seconds a crossing target stays inside the FOV at that range — the ceiling on the
    Part V 'pre-prompt window is free compute' premise."""
    return 2 * range_m * math.tan(math.radians(fov_deg / 2)) / v


def main():
    print(f"target {V_KMH:.0f} km/h = {V:.1f} m/s | deployed carry {CARRY_HZ} Hz\n")
    print(f"  world motion between carry frames : {V / CARRY_HZ:6.1f} m")
    print(f"  distance flown during cold acquire: {V * ACQUIRE_S:6.1f} m  ({ACQUIRE_S} s)")
    print(f"  target/ownship speed ratio        : {V / FOLLOW_MS:6.1f}x  (follow ceiling {FOLLOW_MS} m/s)\n")

    print(f"CROSSING target, inter-frame pixel displacement @ {CARRY_HZ} Hz "
          f"(assumes {FOV_DEG:.0f} deg / {PX_W:.0f} px):")
    print(f"{'range m':>8} {'deg/s':>8} {'px/s':>7} {'px/frame':>9} "
          f"{'Hz for <' + str(int(TOL_PX)) + 'px':>13} {'FOV dwell s':>12}")
    for r in RANGES_M:
        deg_s, px_s, px_frame, hz_needed = crossing_row(r)
        print(f"{r:>8} {deg_s:>8.1f} {px_s:>7.0f} {px_frame:>9.0f} "
              f"{hz_needed:>13.1f} {fov_dwell_s(r):>12.2f}")

    print("\nAPPROACHING head-on — the favourable geometry: no angular rate, only scale growth")
    print(f"{'range m':>8} {'closing/frame m':>16} {'apparent size growth %':>23}")
    d = V / CARRY_HZ
    for r in (400, 200, 100, 50):
        growth = 100 * (r / (r - d) - 1) if r > d else float("inf")
        print(f"{r:>8} {d:>16.1f} {growth:>23.1f}")

    # self-check: the two claims the document leans on
    _, _, px_frame_200, _ = crossing_row(200)
    assert px_frame_200 > TOL_PX, "crossing at 200 m must exceed tolerance, else problem is mis-sized"
    _, _, _, hz_800 = crossing_row(800)
    assert hz_800 < CARRY_HZ, "crossing at 800 m must be inside the deployed rate, else no regime survives"
    assert V * ACQUIRE_S > 200, "cold acquire must be plainly dead at this speed"
    print("\nself-check OK: crossing breaks the contract at 200 m, survives at 800 m, "
          "cold acquire is dead everywhere")


if __name__ == "__main__":
    main()
