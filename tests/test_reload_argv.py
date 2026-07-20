"""Hot-reload argv rewrite. No CARLA, no Tk -- pure list surgery."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "carla_debug_ui", Path(__file__).resolve().parents[1] / "runners/carla_debug_ui.py")
ui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui)


def test_forces_no_respawn_and_carries_the_server():
    got = ui.reload_argv(["runners/carla_debug_ui.py"], 4242)
    assert got == ["runners/carla_debug_ui.py",
                   "--auto-spawn", "0", "--adopt-pgid", "4242"]


def test_replaces_an_existing_auto_spawn_rather_than_appending():
    # the bug this guards: argparse takes the LAST value, but a stale --auto-spawn 50
    # left in place would still be there if we only appended, and a reader of the
    # command line could not tell which one won
    for form in (["--auto-spawn", "50"], ["--auto-spawn=50"]):
        got = ui.reload_argv(["ui.py", *form, "--port", "2000"], 7)
        assert got.count("--auto-spawn") == 1, got
        assert "50" not in got, got
        assert got[got.index("--auto-spawn") + 1] == "0"
        assert "--port" in got and got[got.index("--port") + 1] == "2000"


def test_second_reload_does_not_stack_pgids():
    once = ui.reload_argv(["ui.py"], 11)
    twice = ui.reload_argv(once, 11)
    assert once == twice, twice


def test_no_pgid_means_no_flag():
    # a server someone else launched: nothing for us to hand forward or kill
    assert "--adopt-pgid" not in ui.reload_argv(["ui.py"], 0)
