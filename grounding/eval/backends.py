"""Backend-agnostic inference interface (Phase 0).

The whole point of v2 is that the SAME grounding skill is measured identically
across runtimes, so the deployment-fidelity gap (HF bf16 85% → GGUF F16 62% →
Q8_0 55%) is a measured quantity, not a post-hoc surprise. Each backend takes an
image + a caption, applies the verbatim `grounding.contract.GROUNDING_PROMPT`,
and returns raw model text; scoring is done once, centrally, by `harness.py`.

Filled in at Phase 0 startup.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from grounding.contract import IMAGE_SIZE

# Local CPU-only llama.cpp build at the pinned commit (see DECISIONS.md, Phase 0b).
# Override with LLAMACPP_BIN_DIR if the build lives elsewhere.
_DEFAULT_LLAMACPP_BIN = "/tmp/llama.cpp-57fe1f0/build/bin"


def _llama_server_chat(base_url: str, image_path: str, caption: str,
                       max_side: int, *, timeout: int = 300,
                       stats: dict | None = None) -> str:
    """POST one (image, caption) to a llama.cpp `/v1/chat/completions` endpoint.

    Shared by `GGUFBackend` (local CPU server) and `JetsonBackend` (remote server
    over an ssh tunnel) so both runtimes send byte-identical requests — the image is
    long-edge-resized to `max_side` with the SAME `_resize_keep_aspect` the HF arm
    uses, saved as lossless PNG, base64'd; the verbatim `GROUNDING_PROMPT` is the
    user text; greedy (`temperature=0`), `cache_prompt=False`, `max_tokens` from the
    contract. Keeping this in one place means the only residual between local-GGUF
    and Jetson is the hardware, not the request.

    If `stats` is given, it is filled in-place with a per-call breakdown: the fed
    image dims, the request payload size (the bytes that cross the ssh tunnel), the
    client round-trip wall, and the server-side prefill/decode token counts + ms
    (from llama.cpp's `timings`). `transfer_ms` = wall − prefill − decode isolates
    everything that is NOT Orin compute (tunnel transfer + JSON + queue) — the number
    that answers "is ssh the bottleneck?".
    """
    import base64
    import json
    import tempfile
    import time
    import urllib.request

    from PIL import Image

    from grounding.contract import GROUNDING_PROMPT, MAX_NEW_TOKENS

    img = Image.open(image_path).convert("RGB")
    img = _resize_keep_aspect(img, max_side)
    prompt = GROUNDING_PROMPT.format(target=caption)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
        img.save(tmp.name)  # lossless PNG — identical pixels to the HF arm
        b64 = base64.b64encode(open(tmp.name, "rb").read()).decode()

    payload = json.dumps({
        "model": "vlm",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": MAX_NEW_TOKENS,
        "temperature": 0.0,  # greedy / deterministic
        "cache_prompt": False,
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    wall_ms = (time.perf_counter() - t0) * 1000.0
    if stats is not None:
        t = data.get("timings") or {}
        prompt_ms = float(t.get("prompt_ms", 0.0))
        predicted_ms = float(t.get("predicted_ms", 0.0))
        stats.update({
            "fed_w": img.width, "fed_h": img.height,
            "fed_mpx": round(img.width * img.height / 1e6, 3),
            "payload_kb": round(len(payload) / 1024, 1),
            "wall_ms": round(wall_ms),
            "prompt_n": t.get("prompt_n"), "prompt_ms": round(prompt_ms),
            "predicted_n": t.get("predicted_n"), "predicted_ms": round(predicted_ms),
            # everything not Orin compute: tunnel transfer + JSON + server queue
            "transfer_ms": round(wall_ms - prompt_ms - predicted_ms),
        })
    return data["choices"][0]["message"].get("content") or ""


def _wait_for_health(base_url: str, proc, timeout_s: int) -> None:
    """Block until `<base_url>/health` reports ok, or raise (proc may be None for remote)."""
    import time
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f"llama-server exited early (code {proc.returncode})")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=3) as r:
                if b"ok" in r.read():
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"llama-server not healthy after {timeout_s}s")


def _resize_keep_aspect(img, max_side: int):
    """Downscale so the long edge == max_side (no-op if already smaller).

    Lifted verbatim from `run_stage3_finetune._resize_keep_aspect`. Coordinates are
    normalized to 0–COORD_SCALE, so resizing the pixels is metric-safe; we keep the
    exact same resize the checkpoint was trained/evaluated under.
    """
    from PIL import Image

    w, h = img.size
    scale = max_side / max(w, h)
    if scale >= 1.0:
        return img
    return img.resize((int(w * scale), int(h * scale)), Image.BILINEAR)


@runtime_checkable
class Backend(Protocol):
    """One inference runtime behind a uniform call."""

    name: str  # "hf" | "gguf" | "jetson"

    def generate(self, image_path: str, caption: str) -> str:
        """Run the model on one (image, caption) and return raw output text."""
        ...


class HFBackend:
    """HuggingFace transformers backend (bf16 reference; local RTX 3090).

    This is the *fidelity reference*: every other backend is measured as a delta
    from this number. The inference path (PIL load → long-edge resize to
    `contract.IMAGE_SIZE` → `GROUNDING_PROMPT.format` → chat template →
    greedy decode → decode new tokens only) is lifted verbatim from the validated
    Part-I trainer `run_stage3_finetune.evaluate()`, so the harness reproduces the
    Part-I in-domain number on `smolvlm_ft3`.

    Uses the generic `AutoModelForImageTextToText` so the same backend can host the
    Phase-0c spine candidates (SmolVLM / PaliGemma / Qwen2-VL / …) unchanged.
    """

    name = "hf"

    def __init__(self, model_path: str, *, device: str = "cuda", dtype: str = "bfloat16",
                 max_side: int = IMAGE_SIZE):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.model_path = model_path
        self.device = device
        # Input long-edge resize (the Phase-2 resolution lever). Default = the
        # Part-I/Phase-0 IMAGE_SIZE=512, so existing numbers reproduce unchanged.
        # A whole-image resize keeps the 0–COORD_SCALE box invariant (coords are
        # normalized to the *original* image), so this is metric-safe with no box
        # remapping. Mutable so a sweep can load the model once and vary resolution.
        self.max_side = max_side
        torch_dtype = getattr(torch, dtype)

        # Merged Stage-3 checkpoints ship a processor save with the
        # extra_special_tokens-as-list bug; weights are fine, so fall back to the
        # base processor if the checkpoint's processor won't load.
        try:
            self.processor = AutoProcessor.from_pretrained(model_path)
        except Exception:
            from grounding.contract import MODEL_ID
            self.processor = AutoProcessor.from_pretrained(MODEL_ID)

        self.model = AutoModelForImageTextToText.from_pretrained(
            model_path, torch_dtype=torch_dtype,
        ).to(device)
        self.model.eval()

    def generate(self, image_path: str, caption: str) -> str:
        import torch
        from PIL import Image

        from grounding.contract import GROUNDING_PROMPT, MAX_NEW_TOKENS

        img = Image.open(image_path).convert("RGB")
        img = _resize_keep_aspect(img, self.max_side)

        prompt = GROUNDING_PROMPT.format(target=caption)
        messages = [{"role": "user", "content": [
            {"type": "image"}, {"type": "text", "text": prompt},
        ]}]
        text = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=[text], images=[img], return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
        new_tokens = out[0, inputs["input_ids"].shape[1]:]
        return self.processor.decode(new_tokens, skip_special_tokens=True)


class GGUFBackend:
    """llama.cpp GGUF backend (F16 / Q8_0) via a managed local `llama-server`.

    This is the runtime that exposes the **deployment-fidelity gap**: the Idefics3
    image-preprocessing path inside llama.cpp diverges from HF's, costing −23pp on
    the *same* checkpoint and the *same* resized pixels (the Part-I finding this
    whole phase exists to make a known quantity).

    Methodology lifted verbatim from the Part-I `run_stage3_g3_parity` GGUF arm so
    the self-check is directly comparable:
      - the image is resized to `contract.IMAGE_SIZE` long-edge with the *same*
        `_resize_keep_aspect` the HF arm uses, then saved as **lossless PNG** and
        base64'd — so both backends see identical pixels and the only residual is
        each runtime's own internal preprocessing;
      - the verbatim `GROUNDING_PROMPT` is sent as the user-message text (the
        server applies the model's chat template), `max_tokens=MAX_NEW_TOKENS`,
        `cache_prompt=False`.

    Decoding is **greedy** (`temperature=0`) for determinism — a deliberate, small
    departure from the Part-I GGUF arm (which used server-default sampling); the gap
    is preprocessing-dominated so this does not move the parity number materially,
    and it makes the v2 harness reproducible. The backend boots a CPU-only
    `llama-server` (the build at the pinned llama.cpp commit) on a free local port,
    waits for `/health`, and tears it down on `close()`.
    """

    name = "gguf"

    def __init__(
        self,
        model_path: str,
        mmproj_path: str,
        *,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
        bin_dir: str | None = None,
        startup_timeout_s: int = 120,
        max_side: int = IMAGE_SIZE,
    ):
        import socket
        import subprocess

        self.model_path = model_path
        self.mmproj_path = mmproj_path
        # Input long-edge resize (Phase-2 resolution lever); default IMAGE_SIZE=512
        # for back-compat with the Phase-0 parity numbers. Phase-4 passes 1024 to
        # match the resolution the Phase-3 checkpoint was trained/evaluated under.
        self.max_side = max_side
        self.bin_dir = bin_dir or os.environ.get("LLAMACPP_BIN_DIR", _DEFAULT_LLAMACPP_BIN)
        server_bin = os.path.join(self.bin_dir, "llama-server")
        if not os.path.exists(server_bin):
            raise FileNotFoundError(
                f"llama-server not found at {server_bin}; build llama.cpp at the "
                f"pinned commit or set LLAMACPP_BIN_DIR (see DECISIONS.md Phase 0b)."
            )
        for p, what in ((model_path, "model"), (mmproj_path, "mmproj")):
            if not os.path.exists(p):
                raise FileNotFoundError(f"GGUF {what} not found: {p}")

        # Grab a free port by binding to :0 then releasing it.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]

        env = dict(os.environ, LD_LIBRARY_PATH=self.bin_dir)
        cmd = [
            server_bin, "-m", model_path, "--mmproj", mmproj_path,
            "-ngl", str(n_gpu_layers), "-c", str(n_ctx),
            "--port", str(self.port), "--host", "127.0.0.1",
        ]
        self._log = open(f"/tmp/grounding_llama_server_{self.port}.log", "w")
        self._proc = subprocess.Popen(cmd, env=env, stdout=self._log, stderr=self._log)

        # Wait for /health to report ok (or the process to die).
        base = f"http://127.0.0.1:{self.port}"
        try:
            _wait_for_health(base, self._proc, startup_timeout_s)
        except RuntimeError:
            self._log.flush()
            self.close()
            raise
        self._base = base

    def generate(self, image_path: str, caption: str) -> str:
        return _llama_server_chat(self._base, image_path, caption, self.max_side)

    def close(self) -> None:
        proc = getattr(self, "_proc", None)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        log = getattr(self, "_log", None)
        if log is not None and not log.closed:
            log.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class JetsonBackend:
    """Remote llama.cpp `llama-server` on the Jetson Orin Nano (deployment target).

    This is the runtime that produces the **deployment number** the whole v2 effort
    is designed backwards from: the GGUF skill served on the actual edge device, with
    CUDA offload, at the same pinned llama.cpp commit as the local build (so backend
    version is not a confound — only the hardware differs).

    Mechanics: boot `llama-server` on the Jetson over `ssh jetson` (backgrounded,
    GPU-offloaded with `-ngl`), open an `ssh -N -L` tunnel forwarding a free local
    port to the remote server, then reuse the exact same `_llama_server_chat` request
    path as `GGUFBackend` — so the local-GGUF and Jetson arms send byte-identical
    requests and the F16↔Q8 disambiguation is apples-to-apples across both. `close()`
    tears down the tunnel and kills the remote server.
    """

    name = "jetson"

    def __init__(
        self,
        remote_model_path: str,
        remote_mmproj_path: str,
        *,
        ssh_host: str = "jetson",
        remote_bin_dir: str = "/home/jfdg/llama.cpp/build/bin",
        remote_port: int = 18080,
        n_ctx: int = 4096,
        n_gpu_layers: int = 99,
        startup_timeout_s: int = 240,
        max_side: int = IMAGE_SIZE,
    ):
        import socket
        import subprocess

        self.ssh_host = ssh_host
        self.remote_model_path = remote_model_path
        self.remote_mmproj_path = remote_mmproj_path
        self.remote_port = remote_port
        self.max_side = max_side
        self._remote_pid: int | None = None
        self._tunnel: subprocess.Popen | None = None

        server_bin = f"{remote_bin_dir}/llama-server"
        remote_log = f"/tmp/grounding_llama_server_{remote_port}.log"
        # Backgrounded remote server; print its PID so we can kill it on close().
        #
        # Memory discipline for the 8 GB unified-memory Orin Nano (DECISIONS.md
        # 2026-06-18): the batch eval sends independent images, so the server's
        # prompt cache is pure waste — and its default (`--cache-ram 8192`, an 8 GB
        # cache) plus auto multi-slot (`--parallel -1`) OOM-killed the server mid-run
        # (slots 0–3 each saving ~870-tok idle prompts). Force a single slot, disable
        # the prompt cache (`--cache-ram 0`), and stop idle-slot saving so host
        # memory stays flat across all 439 samples.
        remote_cmd = (
            f"env LD_LIBRARY_PATH={remote_bin_dir} nohup {server_bin} "
            f"-m {remote_model_path} --mmproj {remote_mmproj_path} "
            f"-ngl {n_gpu_layers} -c {n_ctx} "
            f"-np 1 --cache-ram 0 --no-cache-idle-slots "
            f"--port {remote_port} --host 127.0.0.1 "
            f"> {remote_log} 2>&1 & echo $!"
        )
        out = subprocess.run(
            ["ssh", ssh_host, remote_cmd],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode != 0:
            raise RuntimeError(f"failed to start remote llama-server: {out.stderr.strip()}")
        try:
            self._remote_pid = int(out.stdout.strip().split()[-1])
        except (ValueError, IndexError):
            raise RuntimeError(f"could not parse remote PID from: {out.stdout!r}")

        # Free local port for the tunnel head.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.local_port = s.getsockname()[1]

        # ssh -N -L <local>:127.0.0.1:<remote> jetson  (forward only, no shell).
        self._tunnel = subprocess.Popen(
            ["ssh", "-N",
             "-o", "ExitOnForwardFailure=yes",
             "-L", f"{self.local_port}:127.0.0.1:{remote_port}",
             ssh_host],
        )

        base = f"http://127.0.0.1:{self.local_port}"
        try:
            # proc=None: health is gated on the *remote* server, reached via the
            # tunnel; the local tunnel process staying up is necessary but not
            # sufficient, so we poll /health (which round-trips to the Jetson).
            _wait_for_health(base, None, startup_timeout_s)
        except RuntimeError:
            self.close()
            raise
        self._base = base

    def generate(self, image_path: str, caption: str) -> str:
        return _llama_server_chat(self._base, image_path, caption, self.max_side)

    def generate_stats(self, image_path: str, caption: str, stats: dict) -> str:
        """Like `generate`, but fills `stats` with the per-call timing/size breakdown."""
        return _llama_server_chat(self._base, image_path, caption, self.max_side,
                                  stats=stats)

    def close(self) -> None:
        import subprocess

        tunnel = getattr(self, "_tunnel", None)
        if tunnel is not None and tunnel.poll() is None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=10)
            except Exception:
                tunnel.kill()
        pid = getattr(self, "_remote_pid", None)
        if pid is not None:
            try:
                subprocess.run(["ssh", self.ssh_host, f"kill {pid} 2>/dev/null || true"],
                               timeout=30, capture_output=True)
            except Exception:
                pass
            self._remote_pid = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
