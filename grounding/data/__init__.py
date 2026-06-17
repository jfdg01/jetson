"""Dataset adapters + audit gate (Phase 1).

RefCOCO / RefDrone → the canonical single-box 0–1000 schema in `schema.py`, with
`audit.py` enforcing the well-posedness gate (one box per caption + object-size
distribution) *before* any GPU run.
"""
