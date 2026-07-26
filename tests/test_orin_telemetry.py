"""Offline cover for the panel's Orin dashboard parser. No device, no GPU.

Everything here is unit conversion, which is exactly what fails silently: mV x mA is
watts only if you divide by 1e6, and `gpu.0/load` is per-mille, so treating it as a
percent reads 99.9% busy as 10% busy and looks entirely plausible on screen.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.orin_telemetry import parse  # noqa: E402

# Real block, `cat`ed off the Orin 2026-07-26T18:05Z with the board idle.
IDLE = ["4952", "1120", "4944", "248", "4944", "288", "56468", "0",
        "MemTotal:        7789948 kB", "MemAvailable:    6249540 kB"]


def test_idle_block_matches_the_rails_p66_measured():
    r = parse(IDLE)
    # VDD_IN, and the two sub-rails P6.6 reports beside it. Idle here is the same
    # ~5.2 W floor arm A0 measured through tegrastats on these same rails.
    assert r["vdd_in_w"] == pytest.approx(5.546, abs=1e-3)
    assert r["cpu_gpu_cv_w"] == pytest.approx(1.226, abs=1e-3)
    assert r["soc_w"] == pytest.approx(1.424, abs=1e-3)
    assert r["tj_c"] == pytest.approx(56.468, abs=1e-6)
    assert r["gpu_pct"] == 0.0
    # used = total - available, not total - free: the page cache is not consumption,
    # and calling it consumption would show a 7 GB board as permanently full.
    assert r["ram_used_gb"] == pytest.approx(1.540, abs=1e-3)
    assert r["ram_total_gb"] == pytest.approx(7.790, abs=1e-3)


def test_gpu_load_is_per_mille_not_percent():
    assert parse(["4952", "1120", "4944", "248", "4944", "288", "56468", "999",
                  *IDLE[8:]])["gpu_pct"] == 99.9


def test_short_block_raises_instead_of_shifting_fields():
    # `cat` of a fixed file list is positional: one unreadable path would slide every
    # field along and print a temperature as watts. Fail loudly instead.
    with pytest.raises(AssertionError):
        parse(IDLE[:-3])
