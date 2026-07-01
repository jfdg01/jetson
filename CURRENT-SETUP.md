# Current setup — status of the 2026-07-01 flow audit

The original draft here walked the deployed flow step-by-step and ranked four leads.
The walk-through duplicated the code and is gone (repo rule: link, don't duplicate —
the flow is `grounding/deploy/video.py` docstrings + `contract.py` + `backends.py`).
What remains is where each lead landed:

1. **The acquire constant that lied (`ACQUIRE_PERIOD_S=2.0` vs the documented 4.8 s)** —
   **RESOLVED 2026-07-02.** That was one symptom of a wider undocumented drift
   (M=4.0 @1024 no-upscale, matching no measured number); the gated config
   (M=2.0 @512 upscaled, acquire 4.8 s, 85.2% IoU@0.25) is restored. See
   [`docs/decisions/part4-end-to-end.md`](docs/decisions/part4-end-to-end.md).
2. **PNG-over-ssh transfer overhead per anchor** — live. A JPEG/PNG knob exists on the
   request path (`b3d4192`); the real fix is killing the tunnel: the orchestrator runs
   on the Orin. Owned by the temporal campaign
   ([`experiments/2026-07-01-temporal-acquire-carry/`](experiments/2026-07-01-temporal-acquire-carry/README.md)).
3. **`cache_prompt=False` re-prefills the template every call** — live, one-flag test,
   small win. Also owned by the temporal campaign's orchestrator work.
4. **The real Part IV gap: the closed loop has never seen real VLM latency / parse-fails**
   (T3/T4 passed on a perfect, instant oracle) — this is the temporal campaign's Phase 1:
   inject measured latency/error distributions into the SITL slice before integrating.

When leads 2–4 land, this file has no purpose; delete it.
