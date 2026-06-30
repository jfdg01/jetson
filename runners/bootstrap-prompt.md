You are executing ONE experiment unit in the Jetson Orin Nano edge-LLM thesis testbed.
You are a fresh session: your ONLY context is the project `CLAUDE.md` (already loaded) and
the run card below. Treat the run card as your complete and exclusive set of instructions.

YOUR RUN CARD: {{RUNCARD}}

Do this, in order:

1. Read the run card in full. Read it before doing anything else. Follow the project
   `CLAUDE.md` conventions (lab-notebook prime directive, device access, metric fields).
2. Set the run card `status:` to RUNNING.
3. Verify every Precondition. If any precondition is unmet, ambiguous, or the card
   contradicts what you observe on the device: set `status: BLOCKED`, write a short note in
   the card explaining exactly what is missing or unclear, and STOP. Do NOT guess, do NOT
   improvise around it, do NOT substitute a different model/config.
4. Execute the Procedure EXACTLY as written. Change only the one variable the card declares;
   keep every controlled variable (power mode, quant, context, runtime, prompt) at the
   stated value. Do not "optimize" or deviate.
5. Capture ALL mandatory metrics — including failures. OOM kills, thermal throttling, swap
   thrash, load errors, anomalies: these are REQUIRED results, never silently dropped. If the
   run errors out, that is a valid outcome — record it.
6. Fulfil the Output contract precisely: write the raw logs to the stated paths, write the
   detail block into the campaign's `experiments/*.md`, and append exactly one row to `RESULTS.md`
   (append, never overwrite). Report the config next to every number.
7. Set the run card `status:` to DONE (clean success) or FAILED (ran but errored/OOM/throttle,
   with the negative result documented).
8. STOP. Your job was this ONE unit. Do NOT start another unit, do NOT edit other run cards,
   do NOT run unrelated experiments, do NOT update the design/pre-registration doc.

Restrictions, restated: one unit only; exact protocol; failures are data; everything goes to
disk before you stop; when in doubt, BLOCKED + stop, never guess.
