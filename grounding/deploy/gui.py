"""Dead-simple browser GUI for the deployed aerial-grounding skill — the Part III demo.

Two tabs:
  1. **Manual grounding** — the VLM in isolation. Upload/preset image + phrase → one
     box, live on the deployed Qwen2-VL-2B Q8_0 over `ssh jetson`.
  2. **Tracking on video** — the two-tier architecture (VLM anchor seeds a fast tracker
     that coasts between anchors) on real VisDrone footage, served as pre-rendered
     `results/2026-06-25-system-demo/clips/*.mp4` (built by `grounding/deploy/video.py
     --track`). Static files, no live model needed for this tab.

Stdlib-only (no Flask/Gradio — keeps the lock-pinned `.venv-ft` untouched; PIL is
already present for drawing). Boots the Jetson GGUF server ONCE at startup and
reuses it for every request, so only the first query pays the model-load cost.

    source .venv-ft/bin/activate
    python -m grounding.deploy.gui            # then open http://127.0.0.1:8000

Inference uses the verbatim `GROUNDING_PROMPT` + `parse_bbox` contract path, identical
to the eval; the image is sent as base64 JSON (no multipart parsing).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont

from grounding.contract import parse_bbox, COORD_SCALE
from grounding.deploy.demo import PRESETS
from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
from grounding.eval.backends import JetsonBackend

_REMOTE_MODELS = {
    "q8_0": "phase3-refdrone-1024-q8_0.gguf",
    "f16": "phase3-refdrone-1024-f16.gguf",
}
_REMOTE_MMPROJ = "mmproj-phase3-refdrone-1024-f16.gguf"
_TRAIN_MAX_SIDE = 1024

_BACKEND: JetsonBackend | None = None  # booted once in main(), reused per request

# Pre-rendered Level-2 clips (VLM anchors + tracker coast on real VisDrone footage).
_CLIPS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..",
                                           "results", "2026-06-25-system-demo", "clips"))
_CLIPS = [  # (file, caption)
    ("black-suv.mp4", "the black SUV in the middle of the road"),
    ("green-bus.mp4", "the green bus"),
    ("yellow-taxi.mp4", "the yellow taxi"),
]

def _clips_html() -> str:
    panels = []
    for fn, cap in _CLIPS:
        panels.append(
            f'<figure><video src="/clips/{fn}" controls autoplay loop muted playsinline></video>'
            f'<figcaption>“{cap}”</figcaption></figure>')
    return "\n".join(panels)


_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Part III demo — grounding &amp; tracking</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem}
 h1{font-size:1.3rem} .row{margin:.6rem 0}
 input[type=text]{width:100%;padding:.5rem;font-size:1rem;box-sizing:border-box}
 button{padding:.55rem 1.2rem;font-size:1rem;cursor:pointer}
 #out img{max-width:100%;border:1px solid #ccc;margin-top:.8rem}
 #raw{color:#666;font-family:monospace;font-size:.85rem;white-space:pre-wrap}
 .muted{color:#888;font-size:.85rem}
 nav{margin:.4rem 0 1rem;border-bottom:1px solid #ddd}
 nav button{background:none;border:none;border-bottom:3px solid transparent;
   padding:.5rem .2rem;margin-right:1.2rem;font-size:1rem;color:#888}
 nav button.on{color:#000;border-bottom-color:#2a7;font-weight:600}
 section{display:none} section.on{display:block}
 figure{margin:1.2rem 0} figure video{width:100%;border:1px solid #ccc;background:#000;border-radius:4px}
 figcaption{color:#555;font-size:.9rem;margin-top:.3rem}
 .legend{font-size:.85rem;color:#666;margin:.4rem 0 0}
 .g{color:#1a9e3a;font-weight:600} .c{color:#2a86c8;font-weight:600} .o{color:#d97a16;font-weight:600}
</style></head><body>
<h1>Part III — Qwen2-VL-2B (Q8_0) on Jetson Orin Nano</h1>
<nav>
 <button data-tab="manual" class="on">Manual grounding</button>
 <button data-tab="video">Tracking on video</button>
</nav>

<section id="manual" class="on">
<p class="muted">Test the VLM in isolation: pick a preset (RefDrone val frames, varied target sizes)
or upload your own, then hit Run. One image in, one box out — live on the Orin.</p>
<div class="row" id="presets"></div>
<div class="row"><input type="file" id="img" accept="image/*"></div>
<div class="row"><input type="text" id="cap" placeholder="the white car near the building"></div>
<div class="row"><button onclick="run()">Run</button> <span id="status" class="muted"></span></div>
<div id="out"></div><div class="row"><span id="raw"></span></div>
</section>

<section id="video">
<p class="muted">The two-tier architecture on real aerial video: a <span class="g">fresh VLM
anchor</span> (~every 2.26&nbsp;s, the on-Orin cadence) seeds a fast tracker that
<span class="c">coasts</span> between anchors; the next anchor regrounds. Pre-rendered —
real Orin VLM passes on VisDrone-VID footage.</p>
__CLIPS__
<p class="legend"><span class="g">green</span> = fresh VLM box · <span class="c">cyan</span>
= tracker coasting · <span class="o">orange/red</span> = stale / lost between anchors</p>
</section>

<script>
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); document.getElementById(b.dataset.tab).classList.add('on');});
let dataUrl=null;
fetch('/presets').then(r=>r.json()).then(names=>{
  const box=document.getElementById('presets');
  names.forEach(n=>{const b=document.createElement('button');b.textContent=n;
    b.style.margin='0 .3rem .3rem 0';b.onclick=()=>loadPreset(n);box.appendChild(b);});});
async function loadPreset(n){
  const s=document.getElementById('status'); s.textContent='loading preset...';
  const j=await(await fetch('/preset?name='+encodeURIComponent(n))).json();
  dataUrl=j.image; document.getElementById('cap').value=j.caption;
  document.getElementById('out').innerHTML='<img src="'+dataUrl+'">'; s.textContent='';
}
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
            self._send(200, "text/html; charset=utf-8",
                       _PAGE.replace("__CLIPS__", _clips_html()).encode())
        elif self.path.startswith("/clips/"):
            fn = os.path.basename(self.path)  # basename: no path traversal
            if fn not in {c[0] for c in _CLIPS}:
                self._send(404, "text/plain", b"unknown clip")
                return
            with open(os.path.join(_CLIPS_DIR, fn), "rb") as f:
                self._send(200, "video/mp4", f.read())
        elif self.path == "/presets":
            self._send(200, "application/json", json.dumps(list(PRESETS)).encode())
        elif self.path.startswith("/preset?"):
            name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
            if name not in PRESETS:
                self._send(404, "text/plain", b"unknown preset")
                return
            path, caption = PRESETS[name]
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            self._send(200, "application/json", json.dumps({
                "image": "data:image/jpeg;base64," + b64, "caption": caption}).encode())
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
