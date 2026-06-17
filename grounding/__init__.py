"""v2 grounding package — the principled rebuild (Part II).

Everything here is organised around `grounding.contract` (the single source of
truth for prompt / parser / metric) and a *fidelity-before-GPU* workflow. See
`grounding/README.md` for the module map and the fill-in-at-step-startup
convention. Only `contract.py` is implemented today; every other module is a
skeleton fleshed out at the start of the phase that needs it.
"""
