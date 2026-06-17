"""Backend-agnostic inference interface (Phase 0).

The whole point of v2 is that the SAME grounding skill is measured identically
across runtimes, so the deployment-fidelity gap (HF bf16 85% → GGUF F16 62% →
Q8_0 55%) is a measured quantity, not a post-hoc surprise. Each backend takes an
image + a caption, applies the verbatim `grounding.contract.GROUNDING_PROMPT`,
and returns raw model text; scoring is done once, centrally, by `harness.py`.

Filled in at Phase 0 startup.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


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
    """llama.cpp GGUF backend (F16 / Q8_0); exercises the Idefics3 preprocessing path."""

    name = "gguf"

    def __init__(self, model_path: str, mmproj_path: str, *, n_ctx: int = 4096):
        raise NotImplementedError("filled in at Phase 0 startup")

    def generate(self, image_path: str, caption: str) -> str:
        raise NotImplementedError("filled in at Phase 0 startup")


class JetsonBackend:
    """Remote llama.cpp on the Jetson over `ssh jetson` (deployment target)."""

    name = "jetson"

    def __init__(self, remote_model_path: str, remote_mmproj_path: str):
        raise NotImplementedError("filled in at Phase 0 startup")

    def generate(self, image_path: str, caption: str) -> str:
        raise NotImplementedError("filled in at Phase 0 startup")
