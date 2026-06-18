"""Dead-simple browser GUI for the deployed aerial-grounding skill.

Stdlib-only (no Flask/Gradio — keeps the lock-pinned `.venv-ft` untouched; PIL is
already present for drawing). Boots the Jetson GGUF server ONCE at startup and
reuses it for every request, so only the first query pays the model-load cost.

    source .venv-ft/bin/activate
    python -m grounding.deploy.gui            # then open http://127.0.0.1:8000

Upload an aerial image, type a phrase ("the white car near the building"), hit
Run — the predicted box is drawn on the image in the browser. The image is sent
as base64 JSON (no multipart parsing); inference uses the verbatim
`GROUNDING_PROMPT` + `parse_bbox` contract path, identical to the eval.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageDraw, ImageFont

from grounding.contract import parse_bbox, COORD_SCALE
from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
from grounding.eval.backends import JetsonBackend

_REMOTE_MODELS = {
    "q8_0": "phase3-refdrone-1024-q8_0.gguf",
    "f16": "phase3-refdrone-1024-f16.gguf",
}
_REMOTE_MMPROJ = "mmproj-phase3-refdrone-1024-f16.gguf"
_TRAIN_MAX_SIDE = 1024

_BACKEND: JetsonBackend | None = None  # booted once in main(), reused per request

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Aerial grounding demo</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem}
 h1{font-size:1.3rem} .row{margin:.6rem 0}
 input[type=text]{width:100%;padding:.5rem;font-size:1rem;box-sizing:border-box}
 button{padding:.55rem 1.2rem;font-size:1rem;cursor:pointer}
 #out img{max-width:100%;border:1px solid #ccc;margin-top:.8rem}
 #raw{color:#666;font-family:monospace;font-size:.85rem;white-space:pre-wrap}
 .muted{color:#888;font-size:.85rem}
</style></head><body>
<h1>Aerial grounding — Qwen2-VL-2B (Q8_0) on Jetson Orin Nano</h1>
<p class="muted">Upload an aerial/drone image, describe one object, hit Run.</p>
<div class="row"><input type="file" id="img" accept="image/*"></div>
<div class="row"><input type="text" id="cap" placeholder="the white car near the building"></div>
<div class="row"><button onclick="run()">Run</button> <span id="status" class="muted"></span></div>
<div id="out"></div><div class="row"><span id="raw"></span></div>
<script>
let dataUrl=null;
document.getElementById('img').onchange=e=>{
  const f=e.target.files[0]; if(!f)return;
  const r=new FileReader(); r.onload=()=>{dataUrl=r.result;
    document.getElementById('out').innerHTML='<img src="'+dataUrl+'">';}; r.readAsDataURL(f);};
async function run(){
  const cap=document.getElementById('cap').value.trim();
  if(!dataUrl){alert('pick an image first');return;}
  if(!cap){alert('type a phrase first');return;}
  const s=document.getElementById('status'); s.textContent='running...';
  document.getElementById('raw').textContent='';
  try{
    const resp=await fetch('/infer',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({image:dataUrl,caption:cap})});
    const j=await resp.json();
    if(j.error){s.textContent='error'; document.getElementById('raw').textContent=j.error; return;}
    document.getElementById('out').innerHTML='<img src="'+j.annotated+'">';
    document.getElementById('raw').textContent='box '+JSON.stringify(j.box)+'   raw: '+j.raw;
    s.textContent='done';
  }catch(err){s.textContent='error'; document.getElementById('raw').textContent=err;}
}
</script></body></html>"""


def _annotate(png_bytes: bytes, box_norm: list[int], caption: str) -> bytes:
    """Draw a normalized 0..COORD_SCALE box on the image; return PNG bytes."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    x1, y1, x2, y2 = (box_norm[0] / COORD_SCALE * w, box_norm[1] / COORD_SCALE * h,
                      box_norm[2] / COORD_SCALE * w, box_norm[3] / COORD_SCALE * h)
    draw = ImageDraw.Draw(img)
    lw = max(2, round(min(w, h) / 200))
    draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=lw)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(14, round(min(w, h) / 40)))
    except OSError:
        font = ImageFont.load_default()
    label = caption if len(caption) <= 60 else caption[:57] + "..."
    ty = max(0, y1 - (lw + 18))
    draw.rectangle([x1, ty, x1 + 9 * len(label), ty + 18], fill=(255, 0, 0))
    draw.text((x1 + 2, ty), label, fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", _PAGE.encode())
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):  # noqa: N802
        if self.path != "/infer":
            self._send(404, "text/plain", b"not found")
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n))
            caption = req["caption"]
            header, b64 = req["image"].split(",", 1)  # strip "data:image/...;base64,"
            png_bytes = base64.b64decode(b64)

            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tf:
                tf.write(png_bytes)
                tf.flush()
                raw = _BACKEND.generate(tf.name, caption)

            box = parse_bbox(raw)
            if box is None:
                self._send(200, "application/json",
                           json.dumps({"error": f"unparseable output: {raw!r}"}).encode())
                return
            annotated = base64.b64encode(_annotate(png_bytes, box, caption)).decode()
            self._send(200, "application/json", json.dumps({
                "box": box, "raw": raw,
                "annotated": "data:image/png;base64," + annotated,
            }).encode())
        except Exception as e:  # noqa: BLE001 — surface any failure to the browser
            self._send(200, "application/json", json.dumps({"error": str(e)}).encode())

    def log_message(self, *_):  # quiet the per-request stderr spam
        pass


def main(argv: list[str] | None = None) -> int:
    global _BACKEND
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--quant", choices=list(_REMOTE_MODELS), default="q8_0")
    ap.add_argument("--remote-dir", default=_DEFAULT_REMOTE_DIR)
    ap.add_argument("--ssh-host", default="jetson")
    ap.add_argument("--max-side", type=int, default=_TRAIN_MAX_SIDE)
    args = ap.parse_args(argv)

    remote_model = f"{args.remote_dir}/{_REMOTE_MODELS[args.quant]}"
    remote_mmproj = f"{args.remote_dir}/{_REMOTE_MMPROJ}"

    print(f"[gui] booting Jetson {args.quant} server (a few seconds)...", flush=True)
    _BACKEND = JetsonBackend(remote_model, remote_mmproj,
                             ssh_host=args.ssh_host, max_side=args.max_side)
    try:
        httpd = ThreadingHTTPServer((args.host, args.port), _Handler)
        print(f"[gui] open http://{args.host}:{args.port}  (Ctrl-C to stop)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[gui] shutting down...", flush=True)
    finally:
        _BACKEND.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
