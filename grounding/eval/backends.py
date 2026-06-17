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

# Local CPU-only llama.cpp build at the pinned commit (see DECISIONS.md, Phase 0b).
# Override with LLAMACPP_BIN_DIR if the build lives elsewhere.
_DEFAULT_LLAMACPP_BIN = "/tmp/llama.cpp-57fe1f0/build/bin"


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

    def __init__(self, model_path: str, *, device: str = "cuda", dtype: str = "bfloat16"):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.model_path = model_path
        self.device = device
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

        from grounding.contract import GROUNDING_PROMPT, IMAGE_SIZE, MAX_NEW_TOKENS

        img = Image.open(image_path).convert("RGB")
        img = _resize_keep_aspect(img, IMAGE_SIZE)

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
    ):
        import socket
        import subprocess
        import time
        import urllib.request

        self.model_path = model_path
        self.mmproj_path = mmproj_path
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
        deadline = time.time() + startup_timeout_s
        while time.time() < deadline:
            if self._proc.poll() is not None:
                self._log.flush()
                raise RuntimeError(
                    f"llama-server exited early (code {self._proc.returncode}); "
                    f"see {self._log.name}"
                )
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=3) as r:
                    if b"ok" in r.read():
                        break
            except Exception:
                time.sleep(1)
        else:
            self.close()
            raise RuntimeError(f"llama-server not healthy after {startup_timeout_s}s")
        self._base = base

    def generate(self, image_path: str, caption: str) -> str:
        import base64
        import json
        import tempfile
        import urllib.request

        from PIL import Image

        from grounding.contract import GROUNDING_PROMPT, IMAGE_SIZE, MAX_NEW_TOKENS

        img = Image.open(image_path).convert("RGB")
        img = _resize_keep_aspect(img, IMAGE_SIZE)
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
            f"{self._base}/v1/chat/completions", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"].get("content") or ""

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
    """Remote llama.cpp on the Jetson over `ssh jetson` (deployment target)."""

    name = "jetson"

    def __init__(self, remote_model_path: str, remote_mmproj_path: str):
        raise NotImplementedError("filled in at Phase 0 startup")

    def generate(self, image_path: str, caption: str) -> str:
        raise NotImplementedError("filled in at Phase 0 startup")
