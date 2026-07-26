"""The carry ring bound is load-bearing: too small silently changes SAM2's output.

EXP-8 measured the boundary at prune_after >= max_obj_ptrs-1 (15 stock). read_window()
derives it so a future max_obj_ptrs bump moves the ring with it instead of quietly
truncating the memory the model still reads.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "experiments" / "2026-07-01-temporal-acquire-carry"))


def test_read_window_covers_both_memories():
    from stream_carry import read_window
    # stock sam2.1-hiera-tiny: the value EXP-8 adopted
    assert read_window(SimpleNamespace(num_maskmem=7, max_obj_ptrs_in_encoder=16)) == 16
    # the bound must track whichever memory is wider, not just the pointers
    assert read_window(SimpleNamespace(num_maskmem=64, max_obj_ptrs_in_encoder=16)) == 64
    # a temporal stride multiplies how far the mask memory reaches back
    assert read_window(SimpleNamespace(num_maskmem=7, max_obj_ptrs_in_encoder=16,
                                       memory_temporal_stride_for_eval=4)) == 25
    # and it must never land under the boundary EXP-8 measured for the stock model
    assert read_window(SimpleNamespace(num_maskmem=7, max_obj_ptrs_in_encoder=16)) > 15
