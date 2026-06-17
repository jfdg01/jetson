"""Tests for the per-run manifest writer (v2's experiment-tracking spine)."""

from __future__ import annotations

import json

from grounding import manifest as mf


def test_capture_records_pinned_llamacpp_commit():
    m = mf.capture("eval", {"foo": "bar"})
    assert m.llamacpp_commit == mf.LLAMACPP_COMMIT
    assert m.kind == "eval"
    assert m.config == {"foo": "bar"}
    assert m.python_version  # non-empty


def test_capture_accepts_dataclass_config():
    from dataclasses import dataclass

    @dataclass
    class Cfg:
        lr: float = 1e-4
        epochs: int = 3

    m = mf.capture("train", Cfg())
    assert m.config == {"lr": 1e-4, "epochs": 3}


def test_sha256_file_roundtrip_and_missing(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("hello")
    digest = mf.sha256_file(p)
    # sha256("hello")
    assert digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert mf.sha256_file(tmp_path / "nope.txt") is None


def test_write_emits_manifest_and_run_card(tmp_path):
    m = mf.capture("parity", {"n": 200}, run_id="testrun")
    run_dir = mf.write(m, runs_dir=tmp_path, results={"mean_iou": 0.42})
    assert (run_dir / "manifest.json").is_file()
    assert (run_dir / "run-card.md").is_file()
    assert (run_dir / "results.json").is_file()

    loaded = json.loads((run_dir / "manifest.json").read_text())
    assert loaded["run_id"] == "testrun"
    assert loaded["llamacpp_commit"] == mf.LLAMACPP_COMMIT

    card = (run_dir / "run-card.md").read_text()
    assert "Run `testrun`" in card
    assert "mean_iou" in card
