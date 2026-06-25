"""Contract tests — the one thing in v2 that MUST NOT drift.

The whole v2 design rests on prompt/parser/metric being byte-stable and shared. These
tests lock the parser's tolerance to real model output, the metric maths, and (most
importantly) that GROUNDING_PROMPT stays byte-identical to the validated trainer.
Run: `python -m pytest tests/ -q` (or `make test`).
"""

from __future__ import annotations

import pytest

from grounding import contract as c


# ── GROUNDING_PROMPT: byte-stability ─────────────────────────────────────────────

def test_prompt_is_byte_identical_to_validated_string():
    # Terse re-LoRA (2026-06-25): four space-separated ints, no JSON. Re-pinned on
    # purpose — the model is retrained on this exact string. If it fails, the contract
    # drifted from what the fine-tuned weights were trained on.
    expected = (
        'Locate "{target}". Return the bounding box as four space-separated integers '
        'x1 y1 x2 y2, normalized from 0 to 1000.'
    )
    assert c.GROUNDING_PROMPT == expected


def test_prompt_formats_target():
    out = c.GROUNDING_PROMPT.format(target="red car")
    assert 'Locate "red car".' in out
    assert 'four space-separated integers' in out


# ── parse_bbox (terse: exactly four ints) ────────────────────────────────────────

def test_parse_clean_terse():
    assert c.parse_bbox("10 20 30 40") == [10, 20, 30, 40]


def test_parse_extra_whitespace_and_newlines():
    assert c.parse_bbox("  10   20\n30\t40 ") == [10, 20, 30, 40]


def test_parse_handles_negative():
    assert c.parse_bbox("-5 20 30 40") == [-5, 20, 30, 40]


@pytest.mark.parametrize("bad", [
    "no numbers here",
    "1 2 3",            # only three coords
    "1 2 3 4 5",        # five — extra coordinate is a parse-fail, not silent corruption
    "",
])
def test_parse_unparseable_returns_none(bad):
    assert c.parse_bbox(bad) is None


# ── normalize_bbox ───────────────────────────────────────────────────────────────

def test_normalize_basic():
    # full-image box on a 100x200 image → [0,0,1000,1000]
    assert c.normalize_bbox([0, 0, 100, 200], 100, 200) == [0, 0, 1000, 1000]


def test_normalize_clamps_overflow():
    assert c.normalize_bbox([-10, -10, 200, 400], 100, 200) == [0, 0, 1000, 1000]


# ── iou ──────────────────────────────────────────────────────────────────────────

def test_iou_identical_is_one():
    assert c.iou([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)


def test_iou_disjoint_is_zero():
    assert c.iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0


def test_iou_half_overlap():
    # [0,0,10,10] vs [5,0,15,10]: inter=50, union=150 → 1/3
    assert c.iou([0, 0, 10, 10], [5, 0, 15, 10]) == pytest.approx(1 / 3)


# ── center_std (mode-collapse sentinel) ──────────────────────────────────────────

def test_center_std_zero_for_constant_boxes():
    # collapsed model: same box every time → sentinel ~0
    boxes = [[10, 10, 20, 20]] * 5
    assert c.center_std(boxes) == 0.0


def test_center_std_positive_for_spread_boxes():
    boxes = [[0, 0, 10, 10], [500, 500, 510, 510], [900, 900, 910, 910]]
    assert c.center_std(boxes) > 0.0


def test_center_std_ignores_none_and_handles_too_few():
    assert c.center_std([None, [1, 1, 2, 2]]) == 0.0   # <2 real boxes
    assert c.center_std([]) == 0.0


# ── temporal: center_error ───────────────────────────────────────────────────────

def test_center_error_zero_for_same_box():
    assert c.center_error([0, 0, 10, 10], [0, 0, 10, 10]) == 0.0


def test_center_error_euclidean():
    # centre (5,5) vs (8,9): dx=3, dy=4 → 5.0
    assert c.center_error([0, 0, 10, 10], [3, 4, 13, 14]) == pytest.approx(5.0)


# ── temporal: sot_success (visible-frame IoU) ────────────────────────────────────

def test_sot_success_all_hit():
    pred = [[0, 0, 10, 10], [5, 5, 15, 15]]
    gt   = [[0, 0, 10, 10], [5, 5, 15, 15]]
    assert c.sot_success(pred, gt) == 1.0


def test_sot_success_scores_only_visible_frames():
    # frame 1 has gt=None (target not visible) → excluded from denominator
    pred = [[0, 0, 10, 10], [0, 0, 10, 10], [99, 99, 100, 100]]
    gt   = [[0, 0, 10, 10], None,           [0, 0, 10, 10]]
    # 2 visible frames; frame0 hit, frame2 miss → 0.5
    assert c.sot_success(pred, gt) == pytest.approx(0.5)


def test_sot_success_none_pred_on_visible_is_miss():
    assert c.sot_success([None], [[0, 0, 10, 10]]) == 0.0


def test_sot_success_no_visible_frame_is_zero():
    assert c.sot_success([[0, 0, 10, 10]], [None]) == 0.0


# ── temporal: sot_success_auc ────────────────────────────────────────────────────

def test_sot_success_auc_perfect_track_is_one():
    # identical boxes hit at every threshold incl. 1.0 → AUC 1.0
    pred = [[0, 0, 10, 10]]
    gt   = [[0, 0, 10, 10]]
    assert c.sot_success_auc(pred, gt) == pytest.approx(1.0)


def test_sot_success_auc_between_zero_and_one():
    # half-overlap IoU = 1/3: success=1 for thresholds ≤ 1/3, else 0
    pred = [[0, 0, 10, 10]]
    gt   = [[5, 0, 15, 10]]
    auc = c.sot_success_auc(pred, gt)
    # thresholds 0.00..0.30 (7 of 21) ≤ 1/3 → 7/21
    assert auc == pytest.approx(7 / 21)


# ── temporal: sot_precision (centre-error) ───────────────────────────────────────

def test_sot_precision_within_radius():
    # centre offset 5 px ≤ 20 px default → hit
    pred = [[3, 4, 13, 14]]
    gt   = [[0, 0, 10, 10]]
    assert c.sot_precision(pred, gt) == 1.0


def test_sot_precision_outside_radius_misses():
    pred = [[100, 0, 110, 10]]   # centre 105 vs 5 → 100 px > 20
    gt   = [[0, 0, 10, 10]]
    assert c.sot_precision(pred, gt) == 0.0


def test_sot_precision_custom_threshold():
    pred = [[30, 0, 40, 10]]     # centre 35 vs 5 → 30 px
    gt   = [[0, 0, 10, 10]]
    assert c.sot_precision(pred, gt, threshold_px=50.0) == 1.0
    assert c.sot_precision(pred, gt, threshold_px=10.0) == 0.0


# ── temporal: count_id_switches ──────────────────────────────────────────────────

def test_count_id_switches_none_for_steady_lock():
    assert c.count_id_switches(["van", "van", "van"]) == 0


def test_count_id_switches_skips_unlocked_gaps():
    # van → (gap) → van is NOT a switch; van → car IS
    assert c.count_id_switches(["van", None, "van", "car"]) == 1


def test_count_id_switches_multiple():
    assert c.count_id_switches(["a", "b", "a"]) == 2


# ── temporal: identity_purity ────────────────────────────────────────────────────

def test_identity_purity_all_correct():
    assert c.identity_purity(["van", "van", None, "van"], "van") == 1.0


def test_identity_purity_wrong_lock_low_purity():
    # steady lock on the wrong object: 0 switches but 0 purity
    locked = ["car", "car", "car"]
    assert c.count_id_switches(locked) == 0
    assert c.identity_purity(locked, "van") == 0.0


def test_identity_purity_no_lock_is_zero():
    assert c.identity_purity([None, None], "van") == 0.0


# ── temporal: reacquisition_frames ───────────────────────────────────────────────

def test_reacquisition_initial_acquisition_at_frame_zero():
    # starts visible, locked correctly immediately → 0-frame acquisition
    visible = [True, True, True]
    correct = [True, True, True]
    assert c.reacquisition_frames(visible, correct) == [0]


def test_reacquisition_after_absence():
    # visible, then absent, then reappears and takes 2 frames to re-lock
    visible = [True,  False, True,  True,  True]
    correct = [True,  False, False, False, True]
    # event 0: frame0 correct immediately → 0
    # event 1: reappears frame2, correct at frame4 → 2
    assert c.reacquisition_frames(visible, correct) == [0, 2]


def test_reacquisition_failed_before_relock_is_none():
    # reappears at frame2 but leaves at frame3 before any correct lock
    visible = [True,  False, True,  False]
    correct = [True,  False, False, False]
    assert c.reacquisition_frames(visible, correct) == [0, None]


def test_reacquisition_never_visible_is_empty():
    assert c.reacquisition_frames([False, False], [False, False]) == []


# ── temporal: oracle_coverage (all-frame) ────────────────────────────────────────

def test_oracle_coverage_denominator_is_full_clip():
    # 4 frames, target visible+covered in 2 → 0.5 even though one frame is out-of-frame
    pred = [[0, 0, 10, 10], None,           [0, 0, 10, 10], [99, 99, 100, 100]]
    gt   = [[0, 0, 10, 10], None,           [0, 0, 10, 10], [0, 0, 10, 10]]
    assert c.oracle_coverage(pred, gt) == pytest.approx(0.5)


def test_oracle_coverage_differs_from_sot_success():
    # one covered frame + one out-of-frame frame:
    #   sot_success = 1.0 (1 visible, hit); oracle_coverage = 0.5 (denom = 2)
    pred = [[0, 0, 10, 10], None]
    gt   = [[0, 0, 10, 10], None]
    assert c.sot_success(pred, gt) == 1.0
    assert c.oracle_coverage(pred, gt) == pytest.approx(0.5)


def test_oracle_coverage_empty_clip_is_zero():
    assert c.oracle_coverage([], []) == 0.0


# ── temporal: following_error ────────────────────────────────────────────────────

def test_following_error_mean_over_copresent_frames():
    # offsets 0 and 5 over two co-present frames → mean 2.5
    pred = [[0, 0, 10, 10], [3, 4, 13, 14]]
    gt   = [[0, 0, 10, 10], [0, 0, 10, 10]]
    assert c.following_error(pred, gt) == pytest.approx(2.5)


def test_following_error_ignores_frames_missing_a_box():
    # only frame0 has both boxes → mean = its offset (0)
    pred = [[0, 0, 10, 10], None,           [0, 0, 10, 10]]
    gt   = [[0, 0, 10, 10], [0, 0, 10, 10], None]
    assert c.following_error(pred, gt) == pytest.approx(0.0)


def test_following_error_none_when_never_copresent():
    assert c.following_error([None], [[0, 0, 10, 10]]) is None


# ── temporal: track_loss_events ──────────────────────────────────────────────────

def test_track_loss_events_counts_runs_over_timeout():
    # visible throughout; untracked run of length 3 with timeout 2 → 1 event
    visible = [True, True,  True,  True,  True]
    correct = [True, False, False, False, True]
    assert c.track_loss_events(visible, correct, timeout=2) == 1


def test_track_loss_events_short_gap_not_counted():
    # untracked run of length 1, timeout 2 → 0
    visible = [True, True,  True]
    correct = [True, False, True]
    assert c.track_loss_events(visible, correct, timeout=2) == 0


def test_track_loss_events_absence_does_not_count():
    # frames where the target is not visible are not "loss" — they are legitimate gaps
    visible = [True,  False, False, True]
    correct = [True,  False, False, True]
    assert c.track_loss_events(visible, correct, timeout=1) == 0


def test_track_loss_events_two_separate_runs():
    visible = [True, True,  True,  True, True,  True,  True]
    correct = [True, False, False, True, False, False, True]
    assert c.track_loss_events(visible, correct, timeout=2) == 2


def test_track_loss_events_rejects_zero_timeout():
    with pytest.raises(ValueError):
        c.track_loss_events([True], [False], timeout=0)
