"""Backend-agnostic evaluation spine (Phase 0).

`backends.py` hides HF / GGUF / Jetson behind one interface; `harness.py` runs a
backend over a dataset and scores it through `grounding.contract`; `parity.py`
quantifies the HF↔GGUF↔Jetson fidelity gap (the −23pp probe) before training.
"""
