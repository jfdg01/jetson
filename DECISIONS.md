# DECISIONS — project-wide decision log

Cross-cutting decisions and their rationale, most recent first. Campaign-specific
decisions live in the relevant `results/*.md`. Format defined in `CLAUDE.md`.

---

### 2026-06-14T22:00 — Install ffmpeg on Jetson for llama-server image decoding

- **Decision:** Install `ffmpeg` on the Jetson (`sudo apt install -y ffmpeg`).
- **Alternatives considered:** (a) pass image file paths via `file://` URL (blocked by server unless `--media-path` set, and then limited to that directory); (b) rebuild llama.cpp with a different image backend; (c) install ffmpeg.
- **Reasoning:** `llama-server` uses `ffprobe` (part of ffmpeg) to detect image/audio/video format when loading from base64 buffers. Without it, the server returns "Failed to load image or audio file" on every image request. ffmpeg is standard dev tooling with no downside.
- **Tradeoff / cost accepted:** None significant. ffmpeg is ~50MB installed.
- **Revisit when:** Never — this is a permanent tooling dependency for VLM work on the Jetson.

### 2026-06-14T21:00 — VLM measurement instrument: llama-server, not llama-mtmd-cli

- **Decision:** Use `llama-server` + Python `urllib` client as the timing instrument. `llama-bench` and `llama-mtmd-cli` were ruled out.
- **Alternatives considered:** (a) `llama-bench` (no image support confirmed); (b) `llama-mtmd-cli --perf -v` (single-shot only, can't do warm multi-frame); (c) `llama-server` with `cache_prompt: false`.
- **Reasoning:** `llama-bench` has no `--image` flag (confirmed). `llama-mtmd-cli` can only do single-shot inference per process invocation; two separate processes each pay CUDA graph compilation (~180ms), making warm-state measurement impossible from the CLI. `llama-server` keeps the model and CUDA graphs loaded across requests; `cache_prompt: false` ensures each request processes the full prompt from scratch (correct model for per-frame drone use). `timings.prompt_ms` in the `__verbose` response field includes CLIP encode time (verified empirically: `prompt_ms + predicted_ms ≈ wall-clock`). Also confirmed that `llama-mtmd-cli -hf` requires HTTPS (not built in `57fe1f0`), so model downloads must be done via `wget`.
- **Tradeoff / cost accepted:** `llama-server` adds small JSON serialization overhead (measured <10ms). Requires `ffmpeg` for image decoding (installed 2026-06-14).
- **Revisit when:** A later llama.cpp build adds image support to llama-bench with per-frame timing.

### 2026-06-14T21:00 — Architecture fork deferred to empirical result

- **Decision:** Defer the end-to-end-VLM vs. decomposed (detector + LLM) architecture decision to the VLM feasibility campaign result. The campaign's measured per-frame latency vs. required control rate (0.5–2 Hz) is the decision criterion. Not pre-deciding in favour of either architecture.
- **Alternatives considered:** (a) Adopt decomposed immediately (YOLO + LLM) as the practical choice; (b) adopt end-to-end VLM as the thesis-coherent narrative choice; (c) this — run the experiment and let the numbers decide.
- **Reasoning:** The 0.5–2 Hz control rate target is plausible even at 500 ms–2 s per-frame (the drone's own controller holds between high-level updates). A SmolVLM-256M smoke test produced a rough additive lower bound of ~744 ms (277 ms CLIP + 362 ms prefill + 105 ms decode) on a **cold, single-slice 512×512 image with a 14-token decode** — this is NOT a warm per-frame measurement (CUDA graph compilation fired mid-generation), underestimates image token count at campaign resolution (1280×720 will tile into more slices), and uses a shorter decode than the campaign will. **Do not interpret as "1.3 Hz viable."** A warm, 1280×720, 30-token measurement is required before any viability claim. Deciding before measuring would bias the framing. "End-to-end VLM can't close a tracking loop" is a valid thesis finding if the data show it; the decomposed path is the fallback documented in the thesis, not the default assumption.
- **Tradeoff / cost accepted:** Thesis narrative depends on what the data show. If end-to-end is too slow, the decomposed path needs its own measurement campaign.
- **Revisit when:** VLM campaign results are in. Decision criterion: if best-fitting VLM warm per_frame_ms ≤ 2000 ms AND grounding is correct → end-to-end viable; otherwise → document why decomposed is necessary.

---

### 2026-06-14T19:30 — Fix footprint parser (compute double-count) and drop --verbose from load probe

- **Decision:** Remove `--verbose` from the `_capture_load` command in `run_gemma_sweep.py`, and fix `parse_llama_load_buffers` in `parsers.py` to use **last-wins for compute buffers** and **zero-filtered accumulation for KV buffers** (skipping the probe pass's all-zero KV lines).
- **Alternatives considered:** (a) keep `--verbose` and filter by timestamp/pass; (b) take only the first occurrence of each buffer type; (c) this — minimal targeted fix with clear reasoning per field.
- **Reasoning:** llama.cpp runs two allocation passes per load: a probe/dry-run (model=0, KV=0, compute=real) and the real allocation (model=real, KV=real, compute=real). The original accumulating parser double-counted compute buffers (probe_value + real_value = 2×real). `--verbose` was intended to surface buffer-size lines, but those lines appear in normal (non-verbose) output anyway; `--verbose` only added GGML per-tensor debug output (2.3 GB for G2, 425 MB for G3) that flooded SSH buffers and left a stray llama-cli process on the Jetson for >10 min. Without `--verbose`, logs are tens of KB per model. Side effect of the stray process: it consumed 3.3 GB of RAM on the Jetson, causing subsequent footprint re-runs to falsely OOM.
- **Tradeoff / cost accepted:** The G2 footprint numbers come from the original (verbose) log parsed with the fixed parser (only 14 buffer-size lines in 2.3 GB, confirmed by grep). G4 cannot be measured with `--no-mmap` regardless of verbose flag (4.7 GiB malloc > free RAM on 8 GB Jetson); tegrastats 4374 MB remains the best estimate for G4.
- **Revisit when:** llama.cpp changes its buffer-reporting format, or a tegrastats-inline footprint approach makes the separate probe run unnecessary.

### 2026-06-14T18:30 — Correct two tegrastats-derived metrics post-hoc (swap + footprint), don't re-run the sweep

- **Decision:** After the gemma-family sweep, fix **two derived metrics in place** rather than re-running the campaign: (1) swap detection switched from `any(swap > 0)` to **growth over idle baseline** (`swap_growth_mb`, 50 MB threshold); (2) **true footprint** for RQ-G3 re-measured authoritatively via llama.cpp's own per-buffer load report (`--no-mmap --verbose`, new `--footprint` mode) instead of trusting tegrastats peak-RAM sampling. Directly measured throughput/power/TTFT numbers stand unchanged.
- **Alternatives considered:** (a) full re-sweep of all five units; (b) leave the numbers and footnote the caveats; (c) this — targeted parser fix + a ~20 min footprint-only re-run of G2/G3/G4 (+ G5 partial-offload probe).
- **Reasoning:** The expensive, device-bound measurements (pp/tg/TTFT/power) were never in question — only two *derived* fields were wrong: swap was a flat ~300 MB pre-existing baseline mis-flagged on every unit, and tegrastats RAM under-counts mmap'd weights (E2B's 2968 MB < its 3194 MB GGUF, an impossibility for resident weights). A full re-sweep would burn hours reconfirming good data. RQ-G3 (true PLE footprint) is the campaign's headline question, so it alone justified a small, focused re-measure using the runtime's own allocation report (authoritative, no sampling).
- **Tradeoff / cost accepted:** Footprint comes from a separate `--no-mmap` run, not the original benchmarked run, so it's a *characterisation* of the same model+ctx rather than a byte-exact reading of the benchmarked process. `--no-mmap` also changes the load path vs the original (mmap) runs — acceptable because we want the resident-allocation breakdown, which mmap obscures.
- **Revisit when:** the harness is changed to capture llama.cpp buffer sizes inline during the main benchmark run (would make the separate footprint pass unnecessary); or a quant-sensitivity sub-study re-runs these models anyway.

### 2026-06-14T17:00 — llama.cpp build gate for Gemma 4 (no rebuild required)

- **Decision:** Proceed with the existing `57fe1f0` llama.cpp binary for the Gemma-family sweep, including Gemma 4 (E2B/E4B) units. **No rebuild.**
- **Alternatives considered:** (a) Rebuild at a later commit with explicit Gemma 4 QAT GGUF testing; (b) proceed and fall back to rebuild only on runtime failure.
- **Reasoning:** Inspected `src/llama-arch.cpp` on the device at commit `57fe1f0`; the file contains `GEMMA4` and `GEMMA4_ASSISTANT` architecture enum entries and their string mappings. Gemma 4 shipped 2026-04-02 and QAT checkpoints 2026-06-05; `57fe1f0` post-dates both. The §7 gate in the campaign README is satisfied by source inspection rather than a live load probe. If a runtime failure occurs (e.g. `unknown tensor`), rebuilding at the latest commit is pre-approved and must be documented per the campaign README §7 protocol: record new commit hash, build flags, and note the runtime variable change on all affected rows.
- **Tradeoff / cost accepted:** Source inspection is not as definitive as a live model load. If Gemma 4 QAT GGUFs use a tensor name introduced after `57fe1f0`, we will learn this at runtime (unit G3/G4 will error). The fallback (rebuild) is low-risk.
- **Revisit when:** Unit G3 or G4 fails with an architecture/tensor error at runtime — at that point, rebuild, update this entry, and re-run.

### 2026-06-14T13:30 — Use llama-completion (not llama-cli) for TTFT measurement

- **Decision:** Switch the TTFT capture command from `llama-cli -no-cnv` to `llama-completion -no-cnv`, redirect stdin from `/dev/null` on the remote command, and add `stdin=subprocess.DEVNULL` to all local SSH subprocess calls.
- **Alternatives considered:** (a) keep `llama-cli` with different flags; (b) use `llama-server` endpoint; (c) parse TTFT from `llama-bench` output.
- **Reasoning:** `llama-cli` in build `57fe1f0` dropped `-no-cnv` support and dropped users into an interactive loop that flooded stdout indefinitely. `pkill -f tegrastats` was also replaced with `pkill tegrastats` (name-only match) because `-f` matched the word "tegrastats" in the SSH shell's own argv, killing the SSH connection (exit 255). The timing format changed in `llama-completion` (timestamp prefix; comma decimal separators from European locale); `parsers.py` was updated to handle both old and new formats.
- **Tradeoff / cost accepted:** TTFT prompt is ~9–11 tokens (short-prompt latency), not a 512-token prefill. Values (38–204 ms) represent latency lower bounds.
- **Revisit when:** llama.cpp is rebuilt; recheck if `llama-cli` restores `-no-cnv`.

### 2026-06-14T13:30 — Sequential automated sweep via run_campaign.py (not per-unit run cards)

- **Decision:** Run the 10-model sweep via `experiments/run_campaign.py` Python orchestrator rather than the isolated-Claude-session methodology designed 2026-06-13.
- **Alternatives considered:** The run-card / isolated-session methodology (see below).
- **Reasoning:** The orchestrator was already written, thoroughly debugged, and covers the full protocol. `run-unit.sh` driver was not yet built. Single device means no parallelism benefit from fan-out. The orchestrator produced identical data with less setup friction.
- **Tradeoff / cost accepted:** No per-unit context isolation. Acceptable because the orchestrator is deterministic code, not a language model that can drift between units.
- **Revisit when:** A campaign needs per-unit qualitative judgment (e.g. §7 capability eval) — then isolated Claude sessions are more appropriate.

### 2026-06-13T15:05 — Execute each experiment unit in a fresh, isolated Claude session

- **Decision:** Adopt an **isolated-session execution methodology** (in `experiments/`): every
  campaign is decomposed into independent **units** (for the model sweep, one unit per model),
  and **each unit is run by a freshly spawned, cold Claude session** initialized only from
  `CLAUDE.md` + a single self-contained **run card**. The repo filesystem is the message bus —
  run cards in, result blocks / `RESULTS.md` rows / raw logs out; no session shares another's
  in-memory context. A constant `bootstrap-prompt.md` enforces the restriction (one unit only,
  capture failures, fulfil the output contract, then STOP; BLOCKED+stop on ambiguity, never
  guess). Cards carry `status:` (TODO/RUNNING/DONE/FAILED/BLOCKED) as the single source of
  truth; `run-unit.sh` / `run-campaign.sh` spawn sessions via `claude -p`, sequential and
  resumable.
- **Alternatives considered:** (a) one long-lived session driving all ~10 models; (b) Agent-tool
  sub-agents fanned out from an orchestrator session; (c) this — independent headless `claude -p`
  sessions per unit.
- **Reasoning:** Fresh context per unit is an **experimental control**, not just tooling: it
  eliminates cross-run context contamination (earlier models' numbers/debugging can't bias later
  setup or interpretation) and forces every unit through the identical protocol by construction.
  It also stays within context budget (a 10-model sweep would overflow one session) and is
  reproducible/resumable (a unit = a versioned file; re-run = re-spawn). (a) contaminates and
  overflows; (b) keeps a long-lived orchestrator whose context still grows per spawned summary,
  and the Jetson is a single device so the fan-out parallelism sub-agents buy is unusable anyway.
- **Tradeoff / cost accepted:** Each unit pays cold-start overhead (re-reads `CLAUDE.md`,
  re-derives device state) and no live cross-unit synthesis — synthesis is a separate pass that
  reads the on-disk results. Hands-off runs default to `--permission-mode bypassPermissions`,
  acceptable only because this is the operator's own testbed device with a scoped sudo allowlist;
  tighten via `CLAUDE_PERM=acceptEdits` + `--allowedTools` if needed.
- **Revisit when:** A campaign genuinely needs live cross-unit reasoning mid-run (→ orchestrator +
  sub-agents), units can run concurrently on independent hardware (→ parallel dispatch), or the
  cold-start re-derivation cost becomes material (→ a cached device-state preamble).

---

### 2026-06-13T14:42 — Sudo on the Jetson: scoped passwordless for bench commands

- **Decision:** `jfdg` has NOPASSWD sudo for a tight, full-path command allowlist only,
  via `/etc/sudoers.d/10-jetson-bench` — `/usr/sbin/nvpmodel`, `/usr/bin/jetson_clocks`,
  `/usr/bin/tegrastats` (a `BENCH_CMDS` `Cmnd_Alias`). Everything else still requires the
  password. Expand the allowlist by adding a tool's absolute path to `BENCH_CMDS`, then
  `sudo visudo -cf /etc/sudoers.d/10-jetson-bench`. This is a consolidation of three
  same-day decisions: (1) full passwordless installed, (2) reverted once the device became
  reachable off-LAN via Tailscale, (3) scoped allowlist restored hands-off automation
  without standing full root.
- **Alternatives considered:** Blanket `NOPASSWD: ALL`; no NOPASSWD (pipe via `sudo -S`
  every time); this scoped allowlist.
- **Reasoning:** The scoped allowlist is the right balance now that the node is reachable
  off-LAN (Tailscale): it keeps power-mode flips, clock locking, and `tegrastats` logging
  hands-off while full paths + a curated alias keep the blast radius small and the intent
  auditable.
- **Tradeoff / cost accepted:** Any new privileged tool needs a one-line edit + re-validate
  before automation can use it passwordless — that friction is intentional (forces a
  conscious choice to widen privilege). File installed `0440 root:root`; `visudo -c`
  validates all of `/etc/sudoers.d/` OK.
- **Revisit when:** A new benchmark tool needs root (expand `BENCH_CMDS`); the allowlist
  grows large enough to warrant rethinking the trust model; or the device is repurposed
  or exposed to an untrusted network.

---

### 2026-06-13T14:30 — Remote access to the Jetson via Tailscale (WireGuard mesh)

- **Decision:** Enrolled the Jetson into the operator's existing Tailscale tailnet
  (account `javier.fco.dibo.gomez@`) for access from outside the LAN. Transport-only: no
  Tailscale-SSH/ACL mode — the existing OpenSSH `sshd` + `~/.ssh/jfdg01` key are
  unchanged; Tailscale only provides the network path. Brought up with
  `tailscale up --hostname=jetson --accept-dns=false`. Jetson tailnet IP: `100.127.45.66`.
  3090 workstation already on the tailnet (`100.103.89.71`). Added SSH alias
  `jetson-remote` → `100.127.45.66` (raw tailnet IP, not MagicDNS) in `~/.ssh/config`;
  LAN alias `jetson` → `192.168.1.136` retained for local low-latency use. Key expiry
  should be disabled for the `jetson` node in the Tailscale admin console (Machines →
  jetson → Disable key expiry) so the testbed doesn't drop off at the default ~180-day
  expiry.
- **Alternatives considered:** (a) Tailscale mesh; (b) Cloudflare Tunnel; (c) reverse SSH
  through a VPS (autossh/systemd); (d) public port-forward + DDNS.
- **Reasoning:** Tailscale needs no port-forwarding/router access, traverses NAT/CGNAT,
  self-heals across reboots and IP changes, gives a stable `100.x` address, and the 3090
  was already enrolled (zero account setup). It doesn't widen the public attack surface
  (no internet-facing sshd), unlike (d). Used the raw tailnet IP rather than a MagicDNS
  hostname because the tailnet reports a DNS health warning ("can't reach configured DNS
  servers"); a raw IP removes the DNS dependency entirely. `--accept-dns=false` so the
  broken MagicDNS resolver can't affect the Jetson's name resolution.
- **Tradeoff / cost accepted:** Dependency on a third-party coordination service (Tailscale
  control plane) and on the operator's identity provider for node auth. No hostname
  convenience until MagicDNS is fixed (raw IP only). Combined with the scoped
  passwordless-sudo entry, the device is now privileged-command-accessible from anywhere
  on the tailnet — acceptable because tailnet membership is gated by the operator's SSO
  and the device key.
- **Revisit when:** MagicDNS is fixed (switch alias to a hostname); or if a
  self-hosted/no-third-party path becomes a requirement (→ reverse SSH + VPS); or the
  device is exposed to an untrusted network.

---

### 2026-06-13T14:17 — Upper bound = 15 W with locked clocks

- **Decision:** Treat the **15 W locked-clock** config as today's upper bound. Did **not**
  enable 25 W MAXN_SUPER this session.
- **Alternatives considered:** Enable MAXN_SUPER via firmware/bootloader update + updated
  nvpmodel profile.
- **Reasoning:** The active nvpmodel profile (`p3767-0003`) only defines 15 W/7 W;
  unlocking Super requires a bootloader/firmware update. A failed flash leaves the device
  unbootable, and physical access is not available to recover from a brick.
- **Tradeoff / cost accepted:** Today's "upper bound" is the 15 W ceiling, not the absolute
  silicon ceiling. The 25 W Super number will be a separate, higher data point in a later
  session.
- **Revisit when:** A session where a firmware update is reasonable (physical access
  available as a fallback).

---

### 2026-06-13T13:50 — Build llama.cpp natively on the Orin, not cross-compiled locally

- **Decision:** Build llama.cpp directly on the Jetson (aarch64, CUDA `sm_87`) rather than
  building on the x86_64 workstation and copying the binary over.
- **Alternatives considered:** (a) Native on-device build; (b) cross-compile on the x86_64
  box with an aarch64 toolchain; (c) NVIDIA `jetson-containers` prebuilt images.
- **Reasoning:** Binaries are architecture-specific — an x86_64 build can't run on the ARM
  Orin. A correct cross-compile needs an aarch64 cross-toolchain + aarch64 CUDA target
  libs, which is fragile and slower to set up than the native build already underway.
  Critically, llama.cpp is built once and reused across all ~10 models — it's a one-time
  cost, not per-model.
- **Tradeoff / cost accepted:** Native build is slow on the 6-core CPU (~15–25 min, CUDA
  kernel compilation dominates). Accepted because it's one-time.
- **Revisit when:** We need frequent rebuilds (tracking llama.cpp master, sweeping build
  flags) — then switch to `jetson-containers` or a beefier aarch64 build host.

---

### 2026-06-13T13:45 — Runtime: llama.cpp (CUDA), not Ollama

- **Decision:** Use llama.cpp built with CUDA as the benchmarking runtime.
- **Alternatives considered:** Ollama (quick); llama.cpp (CUDA); both.
- **Reasoning:** `llama-bench` gives clean, separated prefill (pp) vs decode (tg)
  throughput and is the standard for reproducible thesis numbers. Ollama exposes only a
  coarser eval rate and adds overhead.
- **Tradeoff / cost accepted:** More setup (cmake install + on-device CUDA build).
- **Revisit when:** We want an easy-to-reproduce cross-check — add Ollama as a secondary,
  looser data source.

---

### 2026-06-13T13:40 — Headline model: Llama-3.2-3B-Instruct Q4_K_M

- **Decision:** Use Llama-3.2-3B-Instruct `Q4_K_M` as the first/most-solid general model.
- **Alternatives considered:** Llama-3.2-1B (max raw tok/s); Qwen2.5-7B (capability
  ceiling, tight fit).
- **Reasoning:** Best balance of "genuinely useful" and "fits 8 GB comfortably with KV
  headroom" — the README sweet spot. ~9 more models follow to cover the size/quant
  spectrum.
- **Tradeoff / cost accepted:** Not the absolute max-tok/s point (a 1B would be faster) nor
  the capability ceiling (7B) — those are separate data points in the broader sweep.
- **Revisit when:** Running the broader ~10-model sweep.
