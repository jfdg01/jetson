"""Settings that survive a restart. Pure file I/O plus a headless Tk root.

Guards the two ways this breaks silently: a corrupt/absent prefs file must not stop
the panel from starting, and a stale key from an older build must not poison a
variable that no longer accepts it.
"""
import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "carla_debug_ui", Path(__file__).resolve().parents[1] / "runners/carla_debug_ui.py")
ui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui)


def test_missing_file_is_empty_prefs(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "PREFS_PATH", tmp_path / "nope.json")
    assert ui.load_prefs() == {}


def test_corrupt_file_is_empty_prefs(tmp_path, monkeypatch):
    p = tmp_path / "prefs.json"
    p.write_text("{not json")
    monkeypatch.setattr(ui, "PREFS_PATH", p)
    assert ui.load_prefs() == {}


@pytest.fixture
def root():
    tk = pytest.importorskip("tkinter")
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    r.withdraw()
    yield r
    r.destroy()


def test_round_trip(root, tmp_path, monkeypatch):
    import tkinter as tk
    monkeypatch.setattr(ui, "PREFS_PATH", tmp_path / "sub" / "prefs.json")
    saved = {"caption": "the blue van", "hold_k": 4}
    remembered = {"caption": ui.restore_pref(saved, "caption",
                                             tk.StringVar(value="the red car")),
                  "hold_k": ui.restore_pref(saved, "hold_k", tk.IntVar(value=3)),
                  "carry_crop": ui.restore_pref(saved, "carry_crop",
                                                tk.BooleanVar(value=True))}
    assert remembered["caption"].get() == "the blue van"
    assert remembered["hold_k"].get() == 4
    assert remembered["carry_crop"].get() is True   # absent key keeps the default
    ui.save_prefs(remembered)
    assert ui.load_prefs() == {"caption": "the blue van", "hold_k": 4,
                               "carry_crop": True}


def test_stale_value_reverts_to_the_code_default(root):
    import tkinter as tk
    # what an older build could leave behind: a string where the widget now wants an int
    var = ui.restore_pref({"ground_res": "1024px"}, "ground_res", tk.IntVar(value=512))
    assert var.get() == 512


def test_save_survives_an_unwritable_path(tmp_path, monkeypatch):
    import tkinter as tk
    blocker = tmp_path / "file"
    blocker.write_text("")
    monkeypatch.setattr(ui, "PREFS_PATH", blocker / "cannot" / "prefs.json")
    ui.save_prefs({})   # must not raise: a bad prefs path never blocks an exit
