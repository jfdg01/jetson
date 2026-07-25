"""Offline cover for P6.6's pure parts. No device, no GPU -- runs in `make test`.

The matrix itself has never been executed; these are the pieces that would silently
produce a wrong watt figure (a misparsed field, an average that ignores sample cadence,
an arm order that is not actually shuffled), so they get a check before the run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "experiments" / "2026-07-25-maintain-cost"))

from run_p66 import (g1_split, integrate, parse_tegrastats, rate_in, schedule,  # noqa: E402
                     window)

# Real line shape, captured on the board 2026-07-25T17:56Z (trimmed of fields we ignore).
LINE = ("{ts} RAM 5338/7607MB (lfb 1x4MB) SWAP 0/3803MB (cached 0MB) "
        "CPU [1%@1728,0%@1728,2%@1728,0%@1728,0%@1728,0%@1728] GR3D_FREQ {gr3d}% "
        "cpu@57.281C soc2@55.75C soc0@55.437C tj@{tj}C soc1@55.281C "
        "VDD_IN {vin}mW/{vin}mW VDD_CPU_GPU_CV {cg}mW/{cg}mW VDD_SOC {soc}mW/{soc}mW")

ANCHOR = "07-25-2026 17:56:56"


def _trace(rows):
    return "\n".join(LINE.format(ts=ts, gr3d=g, tj=tj, vin=v, cg=c, soc=s)
                     for ts, g, tj, v, c, s in rows) + "\n"


def test_parse_takes_the_instant_not_the_average():
    # the field is instant/running-average; taking the average smears arm boundaries
    line = LINE.format(ts=ANCHOR, gr3d=0, tj=56.812, vin=5348, cg=1067, soc=1384)
    line = line.replace("5348mW/5348mW", "12000mW/5348mW")
    s = parse_tegrastats(line, ANCHOR, 1000.0)[0]
    assert s["vdd_in_mw"] == 12000.0
    assert (s["vdd_cpu_gpu_cv_mw"], s["vdd_soc_mw"]) == (1067.0, 1384.0)
    assert (s["tj_c"], s["ram_mb"], s["gr3d_pct"]) == (56.812, 5338.0, 0.0)
    assert s["t"] == 1000.0


def test_parse_maps_device_local_time_onto_unix_without_the_host_timezone():
    trace = _trace([("07-25-2026 17:56:56", 0, 56.8, 5348, 1067, 1384),
                    ("07-25-2026 17:57:06", 99, 61.0, 13000, 8000, 1500)])
    a, b = parse_tegrastats(trace, ANCHOR, 1000.0)
    assert (a["t"], b["t"]) == (1000.0, 1010.0)


def test_parse_skips_junk_lines():
    trace = "tegrastats is already running\n\n" + _trace(
        [("07-25-2026 17:56:56", 0, 56.8, 5348, 1067, 1384)])
    assert len(parse_tegrastats(trace, ANCHOR, 1000.0)) == 1


def test_integrate_is_energy_over_time_not_the_sample_mean():
    # 10 s at 5 W then 1 s at 15 W: sample mean would say 10 W, the truth is ~5.9 W
    s = [{"t": 0.0, "vdd_in_mw": 5000}, {"t": 10.0, "vdd_in_mw": 5000},
         {"t": 11.0, "vdd_in_mw": 15000}]
    mean_w, joules, span = integrate(s)
    assert joules == 50.0 + 10.0
    assert span == 11.0
    assert abs(mean_w - 60.0 / 11.0) < 1e-9


def test_integrate_degrades_instead_of_dividing_by_zero():
    assert integrate([])[1] == 0.0
    assert integrate([{"t": 0.0, "vdd_in_mw": 5000}])[0] == 5.0


def test_window_clips_to_the_arm():
    s = [{"t": t, "vdd_in_mw": 5000} for t in (0, 5, 10, 15, 20)]
    assert [x["t"] for x in window(s, 5, 15)] == [5, 10, 15]


def test_rate_and_g1_split():
    # 5 Hz for the first 60 s, 2 Hz for the last 60 s of a 300 s arm -> G1 fails
    steps = [(i / 5.0, 200.0) for i in range(300)]            # 0..60 s at 5 Hz
    steps += [(60.0 + i / 2.0, 500.0) for i in range(480)]    # 60..300 s at 2 Hz
    assert abs(rate_in(steps, 0.0, 60.0) - 5.0) < 1e-6
    first, last, delta = g1_split(steps, 300.0)
    assert (round(first, 3), round(last, 3)) == (5.0, 2.0)
    assert delta > 0.10           # gate as pre-registered: >10% drop is a G1 FAIL

    flat = [(i / 5.0, 200.0) for i in range(1500)]            # 5 Hz throughout
    assert g1_split(flat, 300.0)[2] <= 0.10


def test_schedule_is_shuffled_within_a_repeat_and_seed_reproducible():
    arms = ["A0", "A1", "B", "C", "D"]
    plan = schedule(arms, 3, seed=666)
    assert len(plan) == 15
    assert plan == schedule(arms, 3, seed=666)          # the record replays
    for r in range(3):
        assert sorted(a for rep, a in plan if rep == r) == sorted(arms)
    orders = {tuple(a for rep, a in plan if rep == r) for r in range(3)}
    assert len(orders) > 1, "identical order every repeat cannot separate thermal soak"
