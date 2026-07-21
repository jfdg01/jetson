"""R-15 — the per-item rows must reconstruct the aggregates, exactly.

The point of `EvalReport.items` is that a campaign can be re-paired against another
arm years later. That only holds if the rows are the same evidence the headline
scalars were computed from. This test is the ratchet: change one and not the other
and it fails.

Run: `python -m pytest tests/ -q` (or `make test`).
"""

from __future__ import annotations

import json

from grounding import contract as c
from grounding.data.schema import GroundingSample
from grounding.eval.harness import evaluate


class _ScriptedBackend:
    """Returns canned model text, so the harness is the only thing under test."""

    name = "scripted"

    def __init__(self, texts):
        self._texts = list(texts)
        self._i = 0

    def generate(self, image_path, caption):  # noqa: ARG002 - signature is the contract
        text = self._texts[self._i]
        self._i += 1
        return text


def _samples(n):
    return [GroundingSample(image_path=f"/img/{i}.jpg", caption=f"thing {i}",
                            bbox=[10, 10, 50, 50], img_w=640, img_h=480,
                            source="test") for i in range(n)]


def _fixture():
    # hit, near-miss, unparseable, exact
    texts = ["12 12 48 48", "60 60 90 90", "sorry, I cannot", "10 10 50 50"]
    return _ScriptedBackend(texts), _samples(len(texts))


def test_items_reconstruct_every_aggregate():
    backend, samples = _fixture()
    r = evaluate(backend, samples)

    assert len(r.items) == r.n == 4
    parsed = [it for it in r.items if it["parsed"]]
    assert r.parse_rate == len(parsed) / r.n
    assert r.iou_gate_pass_rate == sum(it["gate_pass"] for it in r.items) / r.n
    assert abs(r.mean_iou - sum(it["iou"] for it in parsed) / len(parsed)) < 1e-6
    assert abs(r.center_std - c.center_std([it["pred"] for it in parsed])) < 1e-9


def test_unparseable_row_is_recorded_not_dropped():
    """A miss that vanishes from the rows is how a re-analysis silently inflates."""
    backend, samples = _fixture()
    r = evaluate(backend, samples)
    bad = [it for it in r.items if not it["parsed"]]
    assert len(bad) == 1
    assert bad[0]["pred"] is None and bad[0]["iou"] == 0.0
    assert bad[0]["raw"] == "sorry, I cannot"


def test_rows_carry_their_pairing_key():
    """Pairing on position is how two arms get joined on the wrong rows."""
    backend, samples = _fixture()
    r = evaluate(backend, samples)
    for it, s in zip(r.items, samples):
        assert it["image_path"] == s.image_path
        assert it["caption"] == s.caption
        assert it["gt"] == list(s.bbox)


def test_items_path_writes_one_json_object_per_line(tmp_path):
    backend, samples = _fixture()
    out = tmp_path / "nested" / "items.jsonl"
    r = evaluate(backend, samples, items_path=out)
    rows = [json.loads(ln) for ln in out.read_text().splitlines()]
    assert rows == [dict(it) for it in r.items]


def test_limit_truncates_rows_and_aggregates_together():
    backend, samples = _fixture()
    r = evaluate(backend, samples, limit=2)
    assert r.n == 2 and len(r.items) == 2
    assert r.parse_rate == 1.0


def _png(tmp_path, name, w=640, h=480):
    from PIL import Image
    p = tmp_path / name
    Image.new("RGB", (w, h), (40, 80, 120)).save(p)
    return str(p)


def test_roi_arm_emits_rows_too(tmp_path):
    """R-14 pairs the ROI arm against the full-frame arm, so it needs rows as well."""
    from grounding.roi import evaluate_roi

    samples = [GroundingSample(image_path=_png(tmp_path, f"{i}.png"),
                               caption=f"thing {i}", bbox=[100, 100, 200, 200],
                               img_w=640, img_h=480, source="test")
               for i in range(3)]
    # in-crop coords: dead centre, a corner, then unparseable
    backend = _ScriptedBackend(["400 400 600 600", "0 0 20 20", "no box here"])
    r = evaluate_roi(backend, samples, margin=1.0, out_res=None)

    assert len(r.items) == r.n == 3
    parsed = [it for it in r.items if it["parsed"]]
    assert len(parsed) == 2
    assert r.parse_rate == 2 / 3
    assert r.iou_gate_pass_rate == sum(it["gate_pass"] for it in r.items) / r.n
    assert abs(r.mean_iou - sum(it["iou"] for it in parsed) / len(parsed)) < 1e-6
    for it, s in zip(r.items, samples):
        assert it["image_path"] == s.image_path and it["caption"] == s.caption
        # the crop window is what a ROI-vs-full disagreement is usually about
        assert len(it["win"]) == 4
    assert parsed[0]["pred"] != parsed[0]["pred_in_crop"], "crop coords must be mapped back"
