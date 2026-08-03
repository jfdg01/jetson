"""The gate that stops a map swap from segfaulting the panel.

load_world may only run once the follow thread is DEAD -- it caches the episode's
world and actor handles, and libcarla segfaults on the first use after the swap
(runners/check_map_swap.py reproduces it). Told-to-stop is not stopped, so what is
tested here is that a thread which ignores its stop event reports False.
"""
import importlib.util
import threading
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "carla_debug_ui", Path(__file__).resolve().parents[1] / "runners/carla_debug_ui.py")
ui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui)


def test_no_follow_is_free_to_swap():
    assert ui.join_follow({"thread": None}) is True


def test_a_thread_that_exits_is_joined_and_forgotten():
    t = threading.Thread(target=lambda: None, daemon=True)
    t.start()
    track = {"thread": t}
    assert ui.join_follow(track, seconds=5.0) is True
    assert track["thread"] is None      # nothing left to join on the next swap


def test_a_wedged_follow_refuses_the_swap():
    # a follow blocked in the Orin grounding call: the stop event is set, it has not
    # noticed yet. Loading the map here is the crash.
    wedged = threading.Event()
    t = threading.Thread(target=wedged.wait, daemon=True)
    t.start()
    track = {"thread": t}
    try:
        assert ui.join_follow(track, seconds=0.2) is False
        assert track["thread"] is t     # still ours to wait on
    finally:
        wedged.set()
        t.join(timeout=5.0)
