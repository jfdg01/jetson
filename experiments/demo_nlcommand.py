#!/usr/bin/env python3
"""
demo_nlcommand.py — Toy natural-language drone command system (thesis demo).

A drone frame + a natural-language command → structured drone action.

Examples:
    "follow that white car"       → FOLLOW + grounded bbox → velocity setpoint
    "zoom on that red bird"       → ZOOM   + grounded bbox → crop directive
    "turn around the right corner"→ TURN   + direction     → yaw setpoint (no VLM needed)
    "track the blue truck"        → FOLLOW + grounded bbox → velocity setpoint

The VLM (SmolVLM-500M-Instruct Q8_0) runs on the Jetson Orin Nano 8 GB via
llama-server. This script either assumes the server is already up (default)
or starts it via SSH (--start-server).

Usage:
    source .venv/bin/activate
    python experiments/demo_nlcommand.py \\
        --image path/to/frame.jpg \\
        --command "follow that white car" \\
        [--start-server] \\
        [--out annotated.jpg]   # requires Pillow: pip install Pillow

Outputs:
    JSON action block to stdout.
    If --out given and Pillow is installed: annotated image saved to that path.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# ── reuse from run_grounding_probe ────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

JETSON_HOST  = "jetson"
LLAMA_SERVER = "~/llama.cpp/build/bin/llama-server"
LLAMA_LD     = "~/llama.cpp/build/bin:/usr/local/cuda/lib64"
MODELS_DIR   = "~/models"
SERVER_PORT  = 8080
NGL          = 99
SERVER_HEALTH_TIMEOUT_S = 180

SMOLVLM_500M_GGUF   = f"{MODELS_DIR}/SmolVLM-500M-Instruct-Q8_0.gguf"
SMOLVLM_500M_MMPROJ = f"{MODELS_DIR}/mmproj-SmolVLM-500M-Instruct-f16.gguf"

IMG_W_DEFAULT = 640
IMG_H_DEFAULT = 480


# ── bbox ──────────────────────────────────────────────────────────────────────

@dataclass
class Bbox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def w(self) -> float:
        return self.x2 - self.x1

    @property
    def h(self) -> float:
        return self.y2 - self.y1

    def is_valid(self, img_w: int, img_h: int) -> bool:
        return (0 <= self.x1 < self.x2 <= img_w) and (0 <= self.y1 < self.y2 <= img_h)

    def is_degenerate(self, img_w: int, img_h: int,
                      max_area_frac: float = 0.70) -> bool:
        """True if the box covers most of the image (model said 'whole frame').

        SmolVLM sometimes returns the full image bbox when it can't locate the
        referent. Treat any box covering > max_area_frac of the image as a
        grounding failure rather than a successful detection.
        """
        box_area = self.w * self.h
        img_area = img_w * img_h
        return img_area > 0 and (box_area / img_area) > max_area_frac


def _parse_bbox_json(text: str, img_w: int, img_h: int) -> Optional[Bbox]:
    """Multi-fallback bbox extractor to handle SmolVLM's inconsistent output formats.

    Tries in order:
    1. Strict JSON {"x1":..,"y1":..,"x2":..,"y2":..} (double-quote, any field order)
    2. Python-dict single-quote variant
    3. Any list/array of exactly 4 numbers in the response (last resort)
    """
    text = text.strip()
    if text.lower() in ("null", "none", ""):
        return None

    def _try_xyxy(x1, y1, x2, y2) -> Optional[Bbox]:
        try:
            box = Bbox(float(x1), float(y1), float(x2), float(y2))
            return box if box.is_valid(img_w, img_h) else None
        except (ValueError, TypeError):
            return None

    # 1. strict JSON key-order
    m = re.search(
        r'["\']?x1["\']?\s*:\s*(-?[\d.]+).*?["\']?y1["\']?\s*:\s*(-?[\d.]+)'
        r'.*?["\']?x2["\']?\s*:\s*(-?[\d.]+).*?["\']?y2["\']?\s*:\s*(-?[\d.]+)',
        text, re.S,
    )
    if m:
        b = _try_xyxy(*m.groups())
        if b:
            return b

    # 2. any-order key match (JSON or Python dict, double- or single-quoted keys)
    coords = dict(re.findall(r'["\']?(x[12]|y[12])["\']?\s*:\s*(-?[\d.]+)', text))
    if len(coords) == 4:
        b = _try_xyxy(coords.get("x1"), coords.get("y1"),
                      coords.get("x2"), coords.get("y2"))
        if b:
            return b

    # 3. last resort: extract first list of exactly 4 numbers
    lists = re.findall(r'\[([^\]]+)\]', text)
    for lst in lists:
        nums = re.findall(r'-?[\d]+(?:\.[\d]+)?', lst)
        if len(nums) == 4:
            b = _try_xyxy(*nums)
            if b:
                return b

    return None


# ── NL command parser ─────────────────────────────────────────────────────────

FOLLOW_VERBS = re.compile(
    r"\b(follow|track|chase|tail|pursue|keep[ -]on)\b", re.I
)
ZOOM_VERBS = re.compile(
    r"\b(zoom(?:[ -]in)?(?:[ -]on)?|focus(?:[ -]on)?|get[ -]closer[ -]to)\b", re.I
)
TURN_VERBS = re.compile(
    r"\b(turn|rotate|yaw|swing|orbit)\b", re.I
)
DIRECTION_TOKENS = re.compile(
    r"\b(left|right|north|south|east|west|around|back(?:ward)?|clockwise|counter[- ]?clockwise)\b",
    re.I,
)
# strip filler words to get the referent ("that white car" → "white car")
REFERENT_STRIP = re.compile(
    r"^(a|an|the|that|this|those|these)\b\s*", re.I
)


@dataclass
class ParsedCommand:
    verb: str           # FOLLOW | ZOOM | TURN | UNKNOWN
    referent: Optional[str]   # object description (for FOLLOW/ZOOM)
    direction: Optional[str]  # yaw direction (for TURN)
    raw: str


def parse_nl_command(text: str) -> ParsedCommand:
    t = text.strip()

    if TURN_VERBS.search(t):
        m = DIRECTION_TOKENS.search(t)
        direction = m.group(1).lower() if m else None
        return ParsedCommand(verb="TURN", referent=None, direction=direction, raw=t)

    if FOLLOW_VERBS.search(t):
        verb = "FOLLOW"
    elif ZOOM_VERBS.search(t):
        verb = "ZOOM"
    else:
        verb = "UNKNOWN"

    # extract referent: everything after the verb (and any filler)
    stripped = FOLLOW_VERBS.sub("", ZOOM_VERBS.sub("", t)).strip()
    # remove leading prepositions and articles
    stripped = re.sub(r"^(on|at|in|to|the|that|this|a|an)\b\s*", "", stripped, flags=re.I)
    stripped = REFERENT_STRIP.sub("", stripped).strip()
    referent = stripped if stripped else None

    return ParsedCommand(verb=verb, referent=referent, direction=None, raw=t)


# ── VLM prompt ────────────────────────────────────────────────────────────────

def _grounding_prompt(referent: str, img_w: int, img_h: int) -> str:
    return (
        f"Give the bounding box of '{referent}' as JSON "
        f'{{\"x1\":...,\"y1\":...,\"x2\":...,\"y2\":...}} in pixel coordinates. '
        f"Image size is {img_w}×{img_h}. If not present, reply null."
    )


# ── HTTP client ───────────────────────────────────────────────────────────────

def _img_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _img_mime(path: Path) -> str:
    return "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"


def _build_payload(img_b64: str, mime: str, prompt: str, max_tokens: int = 100) -> bytes:
    return json.dumps({
        "model": "vlm",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "max_tokens": max_tokens,
        "cache_prompt": False,
        "__verbose": True,
    }).encode()


def _post(payload: bytes, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        f"http://localhost:{SERVER_PORT}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _extract_text(resp: dict) -> str:
    try:
        return resp["choices"][0]["message"].get("content") or ""
    except Exception:
        return ""


def _extract_latency_ms(resp: dict) -> float:
    try:
        t = resp.get("__verbose", {}).get("timings", {})
        return t.get("prompt_ms", 0.0) + t.get("predicted_ms", 0.0)
    except Exception:
        return 0.0


# ── server lifecycle ──────────────────────────────────────────────────────────

def _ssh(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", JETSON_HOST, cmd],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600,
    )


def _ssh_bg(cmd: str) -> None:
    wrapped = f"nohup sh -c {repr(cmd)} </dev/null >/dev/null 2>&1 &"
    subprocess.run(["ssh", JETSON_HOST, wrapped], check=True, timeout=30)


def _wait_health(timeout_s: int = SERVER_HEALTH_TIMEOUT_S) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(
                f"http://localhost:{SERVER_PORT}/health", timeout=3)
            if b"ok" in r.read():
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def start_server() -> subprocess.Popen:
    """Start SmolVLM-500M on Jetson + SSH port-forward. Returns the pf process."""
    server_cmd = (
        f"export LD_LIBRARY_PATH={LLAMA_LD}; "
        f"{LLAMA_SERVER} -m {SMOLVLM_500M_GGUF} --mmproj {SMOLVLM_500M_MMPROJ} "
        f"-ngl {NGL} --port {SERVER_PORT} -v "
        f"> /tmp/demo_vlm_server.log 2>&1"
    )
    print(f"  starting llama-server on {JETSON_HOST} …")
    _ssh_bg(server_cmd)

    pf = subprocess.Popen(
        ["ssh", "-N", "-L", f"{SERVER_PORT}:localhost:{SERVER_PORT}", JETSON_HOST],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    print(f"  waiting for server health (up to {SERVER_HEALTH_TIMEOUT_S}s) …")
    if not _wait_health(SERVER_HEALTH_TIMEOUT_S):
        pf.terminate()
        raise RuntimeError("llama-server did not become healthy — check /tmp/demo_vlm_server.log on Jetson")

    print("  server healthy")
    return pf


def stop_server(pf: subprocess.Popen) -> None:
    _ssh("pkill -f llama-server || true")
    time.sleep(2)
    pf.terminate()
    try:
        pf.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pf.kill()


def ensure_port_forward() -> subprocess.Popen:
    """Open SSH port-forward only (assumes server already running on Jetson)."""
    pf = subprocess.Popen(
        ["ssh", "-N", "-L", f"{SERVER_PORT}:localhost:{SERVER_PORT}", JETSON_HOST],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print("  waiting for server health …")
    if not _wait_health(20):
        pf.terminate()
        raise RuntimeError(
            f"llama-server not reachable on {JETSON_HOST}:{SERVER_PORT}. "
            "Start it first or use --start-server."
        )
    print("  server reachable")
    return pf


# ── JPEG dimensions from raw bytes (no PIL needed) ────────────────────────────

def _jpeg_dims(path: Path) -> tuple[int, int]:
    """Return (width, height) from a JPEG file by scanning SOF markers."""
    import struct
    data = path.read_bytes()
    i = 0
    while i < len(data) - 10:
        if data[i] == 0xFF and data[i + 1] in (0xC0, 0xC1, 0xC2):
            h = struct.unpack_from(">H", data, i + 5)[0]
            w = struct.unpack_from(">H", data, i + 7)[0]
            return w, h
        # skip marker + length
        if data[i] == 0xFF and data[i + 1] != 0xFF:
            if data[i + 1] in (0xD8, 0xD9):
                i += 2
            else:
                length = struct.unpack_from(">H", data, i + 2)[0]
                i += 2 + length
        else:
            i += 1
    return IMG_W_DEFAULT, IMG_H_DEFAULT


def _png_dims(path: Path) -> tuple[int, int]:
    import struct
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return IMG_W_DEFAULT, IMG_H_DEFAULT
    w = struct.unpack_from(">I", data, 16)[0]
    h = struct.unpack_from(">I", data, 20)[0]
    return w, h


def image_dims(path: Path) -> tuple[int, int]:
    suf = path.suffix.lower()
    if suf in (".jpg", ".jpeg"):
        return _jpeg_dims(path)
    if suf == ".png":
        return _png_dims(path)
    return IMG_W_DEFAULT, IMG_H_DEFAULT


# ── controller stub: bbox → velocity setpoint ─────────────────────────────────

def bbox_to_velocity(bbox: Bbox, img_w: int, img_h: int,
                     kp: float = 0.02) -> dict:
    """Proportional controller: image-plane offset → lateral velocity setpoints.

    Positive vx = move drone right (east), positive vy = move drone forward (north).
    These match the Phase B CascadePID sign convention.
    """
    err_x = (bbox.cx - img_w / 2) / img_w   # [-0.5, +0.5]
    err_y = (bbox.cy - img_h / 2) / img_h   # [-0.5, +0.5]
    return {
        "vx_ms": round(kp * err_x, 4),
        "vy_ms": round(-kp * err_y, 4),   # image y down → world y north is inverted
        "yaw_rate_dps": 0.0,
    }


def turn_to_yaw(direction: Optional[str]) -> dict:
    """Map a turn direction word → yaw rate setpoint (deg/s)."""
    YAW_RATE = 20.0  # deg/s for a gentle turn
    d = (direction or "").lower()
    if d in ("right", "east", "clockwise"):
        yaw = YAW_RATE
    elif d in ("left", "west", "counter-clockwise", "counterclockwise"):
        yaw = -YAW_RATE
    elif d in ("around", "backward", "back"):
        yaw = YAW_RATE * 2  # 180° — keep turning
    else:
        yaw = YAW_RATE  # default: clockwise
    return {"vx_ms": 0.0, "vy_ms": 0.0, "yaw_rate_dps": yaw}


# ── annotated image output ────────────────────────────────────────────────────

def _annotate_with_pillow(
    image_path: Path, bbox: Optional[Bbox], label: str, out_path: Path
) -> None:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    if bbox is not None:
        draw.rectangle(
            [(bbox.x1, bbox.y1), (bbox.x2, bbox.y2)],
            outline=(0, 255, 0), width=3,
        )
        # label above the box
        try:
            font = ImageFont.load_default(size=16)
        except TypeError:
            font = ImageFont.load_default()
        draw.rectangle(
            [(bbox.x1, max(0, bbox.y1 - 20)), (bbox.x1 + len(label) * 9, bbox.y1)],
            fill=(0, 255, 0),
        )
        draw.text((bbox.x1 + 2, max(0, bbox.y1 - 18)), label, fill=(0, 0, 0), font=font)
    img.save(out_path)
    print(f"  annotated image saved → {out_path}")


def save_annotated(image_path: Path, bbox: Optional[Bbox],
                   label: str, out_path: Path) -> None:
    try:
        _annotate_with_pillow(image_path, bbox, label, out_path)
    except ImportError:
        print(
            f"  [no Pillow] install with: pip install Pillow — "
            f"annotated image not saved"
        )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image",   required=True, help="Path to drone frame (JPEG/PNG)")
    parser.add_argument("--command", required=True, help='Natural-language command e.g. "follow that white car"')
    parser.add_argument("--start-server", action="store_true",
                        help="Start llama-server on Jetson (takes ~60s)")
    parser.add_argument("--keep-server", action="store_true",
                        help="With --start-server: do not stop the server on exit (useful for multi-command testing)")
    parser.add_argument("--out", metavar="PATH",
                        help="Save annotated image to this path (requires Pillow)")
    parser.add_argument("--width",  type=int, default=0,
                        help="Force image width (auto-detected from file if 0)")
    parser.add_argument("--height", type=int, default=0,
                        help="Force image height (auto-detected from file if 0)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"ERROR: image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    # ── auto-detect image dims ────────────────────────────────────────────────
    img_w, img_h = (
        (args.width, args.height) if args.width and args.height
        else image_dims(image_path)
    )
    print(f"  image: {image_path.name}  ({img_w}×{img_h})")

    # ── parse command ─────────────────────────────────────────────────────────
    cmd = parse_nl_command(args.command)
    print(f"  command: {args.command!r}")
    print(f"  parsed:  verb={cmd.verb}  referent={cmd.referent!r}  dir={cmd.direction!r}")

    result: dict = {
        "command_raw": cmd.raw,
        "verb": cmd.verb,
        "referent": cmd.referent,
        "direction": cmd.direction,
        "image": image_path.name,
        "image_size": f"{img_w}x{img_h}",
        "vlm_used": False,
        "bbox": None,
        "vlm_raw": None,
        "vlm_latency_ms": None,
        "setpoint": None,
        "parse_ok": False,
    }

    # ── TURN: no VLM needed ───────────────────────────────────────────────────
    if cmd.verb == "TURN":
        sp = turn_to_yaw(cmd.direction)
        result["setpoint"] = sp
        result["parse_ok"] = True
        print(f"\n  → TURN: yaw_rate={sp['yaw_rate_dps']} deg/s")
        print(json.dumps(result, indent=2))
        return

    if cmd.referent is None:
        print("  WARNING: could not extract a referent from the command; no VLM call.")
        print(json.dumps(result, indent=2))
        return

    # ── FOLLOW / ZOOM: ground the referent ───────────────────────────────────
    pf: Optional[subprocess.Popen] = None
    try:
        if args.start_server:
            pf = start_server()
        else:
            pf = ensure_port_forward()

        # warmup call (first call has CUDA graph compilation overhead ~180ms)
        print(f"\n  VLM warmup call …")
        warmup_prompt = _grounding_prompt(cmd.referent, img_w, img_h)
        warmup_payload = _build_payload(
            _img_b64(image_path), _img_mime(image_path), warmup_prompt, max_tokens=150
        )
        try:
            _post(warmup_payload, timeout=60)
            print("  warmup done")
        except Exception as e:
            print(f"  warmup failed: {e} (continuing)")

        # actual grounding call
        print(f"  grounding '{cmd.referent}' in {image_path.name} …")
        prompt = _grounding_prompt(cmd.referent, img_w, img_h)
        payload = _build_payload(
            _img_b64(image_path), _img_mime(image_path), prompt, max_tokens=150
        )
        t0 = time.time()
        resp = _post(payload, timeout=120)
        wall_ms = (time.time() - t0) * 1000
        raw_text = _extract_text(resp)
        vlm_ms = _extract_latency_ms(resp) or wall_ms

        result["vlm_used"] = True
        result["vlm_raw"] = raw_text
        result["vlm_latency_ms"] = round(vlm_ms, 1)

        bbox = _parse_bbox_json(raw_text, img_w, img_h)
        if bbox is not None and bbox.is_degenerate(img_w, img_h):
            print(f"  VLM returned whole-image bbox (degenerate) — treating as no-detection")
            result["vlm_raw"] = raw_text
            result["vlm_latency_ms"] = round(vlm_ms, 1)
            print(json.dumps(result, indent=2))
            return
        if bbox is not None:
            result["bbox"] = {"x1": bbox.x1, "y1": bbox.y1,
                              "x2": bbox.x2, "y2": bbox.y2,
                              "cx": round(bbox.cx, 1), "cy": round(bbox.cy, 1)}
            result["parse_ok"] = True

            sp = bbox_to_velocity(bbox, img_w, img_h)
            if cmd.verb == "ZOOM":
                result["setpoint"] = {
                    "action": "CROP_TO_BBOX",
                    "crop_px": {"x1": bbox.x1, "y1": bbox.y1,
                                "x2": bbox.x2, "y2": bbox.y2},
                }
            else:
                result["setpoint"] = sp

            print(f"  VLM raw:   {raw_text!r}")
            print(f"  bbox:      x1={bbox.x1:.0f} y1={bbox.y1:.0f} x2={bbox.x2:.0f} y2={bbox.y2:.0f}")
            print(f"  latency:   {vlm_ms:.0f} ms  (wall {wall_ms:.0f} ms)")
            print(f"  setpoint:  {result['setpoint']}")
        else:
            print(f"  VLM raw (no bbox):  {raw_text!r}")
            print(f"  latency:           {vlm_ms:.0f} ms")
            print(f"  → referent '{cmd.referent}' not grounded (model replied: {raw_text!r})")

    finally:
        if pf is not None:
            if args.start_server and not args.keep_server:
                stop_server(pf)
            else:
                pf.terminate()
                try:
                    pf.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pf.kill()

    # ── annotated image ───────────────────────────────────────────────────────
    if args.out and bbox is not None:
        save_annotated(image_path, bbox, cmd.referent or "", Path(args.out))
    elif args.out and bbox is None:
        print(f"  (no bbox to annotate — {args.out} not written)")

    print()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
