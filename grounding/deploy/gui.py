"""Dead-simple browser GUI for the deployed aerial-grounding skill — the Part III demo.

Tabs:
  1. **Manual grounding** — the VLM in isolation. Upload/preset image + phrase → one
     box, live on the deployed Qwen2-VL-2B Q8_0 over `ssh jetson`.
  2. **Live tracking (your video)** — the whole deployed system on an uploaded clip: the
     terse anchor acquires full-frame, re-anchors on a ROI crop while the CSRT tracker
     coasts between anchors, and re-acquires full-frame after a loss (both latency levers).
  3. **Re-anchor speedup** — full-frame anchor vs ROI-crop re-anchor, side by side, with
     the prefill/decode split for each (the prefill latency lever; see
     `results/2026-06-26-roi-demo-tab/` + `results/2026-06-25-roi-crop-anchor/`).

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
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont

from grounding.contract import COORD_SCALE, parse_bbox
from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
from grounding.deploy.video import ROI_MARGIN as _ROI_MARGIN, ROI_OUT_RES as _ROI_OUT_RES, render as _render_track
from grounding.eval.backends import JetsonBackend
from grounding.roi import crop_resize, map_to_full, roi_window

# Upload-track tab: cap an uploaded clip so it stays a few VLM anchors, not a long run.
_TRACK_MAX_S = 9  # seconds of the upload to use (≈3 anchors at the on-Orin cadence)
_TRACK_W = (
    1080  # extract/render width — small enough for a light mp4, big enough to ground
)
_TRACK_MAX_BYTES = 800 * 1024 * 1024

# terse iter-2b anchor (2026-06-26): bare 0–100 ints, Orin Q8_0 63.1% (> JSON 62.6%),
# decode −45%. Must match the terse GROUNDING_PROMPT in contract.py.
_REMOTE_MODELS = {
    "q8_0": "phase3-terse100eos-1024-q8_0.gguf",
    "f16": "phase3-terse100eos-1024-f16.gguf",
}
_REMOTE_MMPROJ = "mmproj-phase3-terse100eos-1024-f16.gguf"
_TRAIN_MAX_SIDE = 1024

_BACKEND: JetsonBackend | None = None  # booted once in main(), reused per request

# Manual-tab example images: thumbnails to click; clicking loads the image, NOT a caption.
_EXAMPLES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "examples", "images")
)
_EXAMPLES = sorted(f for f in os.listdir(_EXAMPLES_DIR) if f.endswith(".jpg"))

_VIDEO_EXAMPLES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "examples")
)
_VIDEO_EXAMPLES = sorted(f for f in os.listdir(_VIDEO_EXAMPLES_DIR) if f.endswith(".mp4"))


def _examples_html(picker: str = "pick") -> str:
    return "".join(
        f'<img src="/examples/{fn}" title="{fn}" onclick="{picker}(\'{fn}\')">'
        for fn in _EXAMPLES
    )


def _video_examples_html() -> str:
    rows = []
    for fn in _VIDEO_EXAMPLES:
        stem = os.path.splitext(fn)[0].replace("-", " ")
        rows.append(
            f'<div class="vex" onclick="vpick(\'{fn}\')" title="{stem}">'
            f'<video src="/video-examples/{fn}" preload="metadata" muted></video>'
            f'<span>{stem}</span></div>'
        )
    return "".join(rows)


_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Orin VLM</title>
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
 #examples,#cexamples,#vexamples{display:flex;flex-wrap:nowrap;gap:.4rem;overflow-x:auto;padding-bottom:.3rem}
 #examples img,#cexamples img{height:72px;flex:0 0 auto;border:2px solid #ccc;border-radius:4px;cursor:pointer;vertical-align:top}
 #examples img:hover,#cexamples img:hover{border-color:#2a7}
 .vex{flex:0 0 auto;text-align:center;cursor:pointer;border:2px solid #ccc;border-radius:4px;padding:.2rem;width:130px;vertical-align:top}
 .vex:hover{border-color:#2a7} .vex.sel{border-color:#2a7;background:#f2faf4}
 .vex video{width:126px;height:71px;object-fit:cover;display:block;border-radius:2px;pointer-events:none}
 .vex span{font-size:.72rem;color:#555;display:block;margin-top:.2rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:126px}
 .cmp{display:flex;gap:1rem;flex-wrap:wrap;margin-top:.8rem}
 .cmp figure{flex:1;min-width:280px;margin:0}
 .cmp img{width:100%;border:1px solid #ccc}
 .cmp .stat{font-family:monospace;font-size:.85rem;margin-top:.3rem}
 .banner{font-size:1.05rem;margin:.6rem 0;padding:.5rem .7rem;background:#f2faf4;border-left:4px solid #2a7;border-radius:3px}
 .anchors{display:flex;flex-direction:column;gap:1rem;margin-top:.8rem}
 .anchor-pair .astat{margin:0 0 .4rem;font-family:monospace;font-size:.78rem;color:#444;line-height:1.4}
 .anchor-imgs{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem}
 .anchor-imgs img{width:100%;border:1px solid #ccc;display:block}
</style></head><body>
<h1>Orin VLM</h1>
<nav>
 <button data-tab="manual" class="on">Manual grounding</button>
 <button data-tab="live">Live tracking (your video)</button>
 <button data-tab="compare">Re-anchor speedup</button>
</nav>

<section id="manual" class="on">
<div class="row" id="examples">__EXAMPLES__</div>
<div class="row"><input type="file" id="img" accept="image/*"></div>
<div class="row"><input type="text" id="cap" placeholder="the white car near the building"></div>
<div class="row"><button onclick="run()">Run</button> <span id="status" class="muted"></span></div>
<div id="out"></div><div class="row"><span id="raw"></span></div>
</section>

<section id="live">
<div class="row" id="vexamples">__VEXAMPLES__</div>
<div class="row"><input type="file" id="vid" accept="video/*"></div>
<div class="row"><input type="text" id="vcap" placeholder="the white car near the building"></div>
<div class="row">acquire <input type="number" id="vacquire" value="4" min="0.1" step="0.1" style="width:4rem"> s &nbsp;·&nbsp; re-anchor <input type="number" id="vanchor" value="2" min="0.1" step="0.1" style="width:4rem"> s
 <button onclick="track()">Run tracking</button> <span id="vstatus" class="muted"></span></div>
<div id="vout"></div>
<p class="legend"><span class="g">green</span> = VLM · <span class="c">cyan</span>
= CSRT tracking · <span class="o">red</span> = lost</p>
</section>

<section id="compare">
<div class="row" id="cexamples">__CEXAMPLES__</div>
<div class="row"><input type="file" id="cimg" accept="image/*"></div>
<div class="row"><input type="text" id="ccap" placeholder="the white car near the building"></div>
<div class="row"><button onclick="compare()">Compare</button> <span id="cstatus" class="muted"></span></div>
<div id="cout" class="cmp"></div>
<p class="legend"><span class="o" style="color:#d62828">red</span> = full-frame anchor ·
<span class="g">green</span> = ROI re-anchor (grey box = the crop the VLM saw)</p>
</section>

<script>
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); document.getElementById(b.dataset.tab).classList.add('on');});
let dataUrl=null;
async function pick(fn){
  const s=document.getElementById('status'); s.textContent='loading...';
  const j=await(await fetch('/example?name='+encodeURIComponent(fn))).json();
  dataUrl=j.image;  // load the image only — leave the caption for the user to type
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
let vidFile=null;
async function vpick(fn){
  document.querySelectorAll('.vex').forEach(x=>x.classList.remove('sel'));
  event.currentTarget.classList.add('sel');
  const s=document.getElementById('vstatus'); s.textContent='loading '+fn+'...';
  const blob=await(await fetch('/video-examples/'+encodeURIComponent(fn))).blob();
  vidFile=new File([blob],fn,{type:'video/mp4'});
  document.getElementById('vcap').value=fn.replace(/\\.mp4$/,'').replace(/-/g,' ');
  s.textContent='';
}
document.getElementById('vid').onchange=e=>{
  document.querySelectorAll('.vex').forEach(x=>x.classList.remove('sel'));
  vidFile=e.target.files[0]||null;
};
async function track(){
  const cap=document.getElementById('vcap').value.trim();
  const acquire=parseFloat(document.getElementById('vacquire').value)||4;
  const anchor=parseFloat(document.getElementById('vanchor').value)||2;
  if(!vidFile){alert('pick a video first');return;}
  if(!cap){alert('type a phrase first');return;}
  const s=document.getElementById('vstatus'); s.textContent='uploading + running on the Orin (this takes a bit)...';
  document.getElementById('vout').innerHTML='';
  try{
    // raw bytes in the body — base64-in-JSON overflows the browser string allocator on big files
    const url='/track?caption='+encodeURIComponent(cap)+'&acquire='+acquire+'&anchor='+anchor;
    const resp=await fetch(url,{method:'POST',body:vidFile});
    const j=await resp.json();
    if(j.error){s.textContent='error: '+j.error; return;}
    let vhtml='<video src="'+j.video+'" controls autoplay loop muted playsinline style="max-width:100%;border:1px solid #ccc;margin-top:.8rem"></video>';
    if(j.anchors&&j.anchors.length){
      vhtml+='<h4 style="margin:.8rem 0 .3rem;font-size:.9rem">Anchor passes ('+j.anchors.length+')</h4><div class="anchors">';
      j.anchors.forEach(a=>{
        const s=a.stats||{};
        const line=(s.mode?s.mode+' · ':'')
          +'fed '+(s.fed_w||'?')+'x'+(s.fed_h||'?')+' ('+(s.fed_mpx||'?')+'Mpx, '+(s.payload_kb||'?')+'KB)'
          +(s.crop_px?' · crop '+s.crop_px+'px':'')+(s.box_px?' · box '+s.box_px:'');
        const tline='prefill <b>'+(s.prompt_ms||'?')+'ms</b> · decode '+(s.predicted_ms||'?')+'ms'
          +' · transfer/queue '+(s.transfer_ms||'?')+'ms · wall '+(s.wall_ms||'?')+'ms'
          +(s.prompt_n?'  ('+s.prompt_n+' prompt toks, '+(s.predicted_n||'?')+' decode)':'');
        vhtml+='<div class="anchor-pair">'
          +'<p class="astat"><b>frame '+a.fi+' — '+a.elapsed_s+'s</b> · '+line+'<br>'+tline+'</p>'
          +'<div class="anchor-imgs"><img src="'+a.fed+'" title="crop fed to VLM"><img src="'+(a.annotated_crop||a.fed)+'" title="crop + VLM box"><img src="'+a.annotated+'" title="full frame + VLM box"></div>'
          +'</div>';});
      vhtml+='</div>';}
    document.getElementById('vout').innerHTML=vhtml;
    s.textContent=j.note||'done';
  }catch(err){s.textContent='error: '+err;}
}
let cData=null;
async function cpick(fn){
  const s=document.getElementById('cstatus'); s.textContent='loading...';
  const j=await(await fetch('/example?name='+encodeURIComponent(fn))).json();
  cData=j.image;  // load the image only — leave the caption for the user to type
  document.getElementById('cout').innerHTML='<figure><img src="'+cData+'"></figure>'; s.textContent='';
}
document.getElementById('cimg').onchange=e=>{
  const f=e.target.files[0]; if(!f)return;
  const r=new FileReader(); r.onload=()=>{cData=r.result;
    document.getElementById('cout').innerHTML='<figure><img src="'+cData+'"></figure>';}; r.readAsDataURL(f);};
async function compare(){
  const cap=document.getElementById('ccap').value.trim();
  if(!cData){alert('pick an image first');return;}
  if(!cap){alert('type a phrase first');return;}
  const s=document.getElementById('cstatus'); s.textContent='running both passes on the Orin...';
  document.getElementById('cout').innerHTML='';
  try{
    const resp=await fetch('/compare',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({image:cData,caption:cap})});
    const j=await resp.json();
    if(j.error){s.textContent='error'; document.getElementById('cout').textContent=j.error; return;}
    const fig=(d,title)=>'<figure><img src="'+d.annotated+'">'
      +'<div class="stat">'+title+'<br>prefill <b>'+d.prefill_ms+' ms</b>'
      +(d.decode_ms?' · decode '+d.decode_ms+' ms':'')+'</div></figure>';
    document.getElementById('cout').innerHTML=
      '<div class="banner">ROI re-anchor: <b>'+j.speedup+'× cheaper prefill</b> '
      +'('+j.full.prefill_ms+' → '+j.roi.prefill_ms+' ms) — same model, fewer pixels, tighter box.</div>'
      +'<div class="cmp">'+fig(j.full,'Full-frame anchor')+fig(j.roi,'ROI re-anchor (M=__MARGIN__ @__OUTRES__)')+'</div>';
    s.textContent='done';
  }catch(err){s.textContent='error'; document.getElementById('cout').textContent=err;}
}
</script></body></html>"""


def _annotate(
    png_bytes: bytes,
    box_norm: list[int],
    caption: str,
    *,
    color: tuple = (255, 0, 0),
    window: tuple | None = None,
) -> bytes:
    """Draw a normalized 0..COORD_SCALE box on the image; return PNG bytes.

    `color` sets the box/label colour; `window` (pixel XYXY) optionally outlines the
    ROI crop region the VLM actually saw (drawn faint, so the compare tab can show
    "this is all the model looked at")."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    x1, y1, x2, y2 = (
        box_norm[0] / COORD_SCALE * w,
        box_norm[1] / COORD_SCALE * h,
        box_norm[2] / COORD_SCALE * w,
        box_norm[3] / COORD_SCALE * h,
    )
    draw = ImageDraw.Draw(img)
    lw = max(2, round(min(w, h) / 200))
    if window is not None:
        draw.rectangle(list(window), outline=(120, 120, 120), width=max(1, lw - 1))
    draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(14, round(min(w, h) / 40)))
    except OSError:
        font = ImageFont.load_default()
    label = caption if len(caption) <= 60 else caption[:57] + "..."
    ty = max(0, y1 - (lw + 18))
    draw.rectangle([x1, ty, x1 + 9 * len(label), ty + 18], fill=color)
    draw.text((x1 + 2, ty), label, fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _timed_post(
    img: Image.Image, caption: str, max_side: int
) -> tuple[str, float, float]:
    """One verbose POST to the already-booted server → (raw, prefill_ms, decode_ms).

    Mirrors `backends._llama_server_chat` (verbatim GROUNDING_PROMPT, greedy,
    cache_prompt off) but (1) asks for server timings via "__verbose" so we can show
    the prefill/decode split, and (2) takes a PIL image so a pre-cropped ROI is sent
    as-is (pass a large max_side to skip re-resize). Falls back to wall-clock prefill
    if the server omits timings."""
    import time
    import urllib.request

    from grounding.contract import GROUNDING_PROMPT, MAX_NEW_TOKENS
    from grounding.eval.backends import _resize_keep_aspect

    img = _resize_keep_aspect(img.convert("RGB"), max_side)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
        img.save(tmp.name)
        b64 = base64.b64encode(open(tmp.name, "rb").read()).decode()
    payload = json.dumps(
        {
            "model": "vlm",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": GROUNDING_PROMPT.format(target=caption),
                        },
                    ],
                }
            ],
            "max_tokens": MAX_NEW_TOKENS,
            "temperature": 0.0,
            "cache_prompt": False,
            "__verbose": True,
        }
    ).encode()
    req = urllib.request.Request(
        f"{_BACKEND._base}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode())
    wall_ms = (time.perf_counter() - t0) * 1000.0
    raw = data["choices"][0]["message"].get("content") or ""
    t = data.get("timings")
    if not t and isinstance(data.get("__verbose"), dict):
        t = data["__verbose"].get("timings")
    if t and "prompt_ms" in t:
        return raw, float(t["prompt_ms"]), float(t.get("predicted_ms", 0.0))
    return raw, wall_ms, 0.0  # ponytail: server omitted timings → wall-clock prefill


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            page = (
                _PAGE.replace("__EXAMPLES__", _examples_html())
                .replace("__CEXAMPLES__", _examples_html("cpick"))
                .replace("__VEXAMPLES__", _video_examples_html())
                .replace("__MARGIN__", f"{_ROI_MARGIN:g}")
                .replace("__OUTRES__", str(_ROI_OUT_RES))
            )
            self._send(200, "text/html; charset=utf-8", page.encode())
        elif self.path.startswith("/examples/"):
            fn = os.path.basename(self.path)  # basename: no path traversal
            if fn not in _EXAMPLES:
                self._send(404, "text/plain", b"unknown example")
                return
            with open(os.path.join(_EXAMPLES_DIR, fn), "rb") as f:
                self._send(200, "image/jpeg", f.read())
        elif self.path.startswith("/video-examples/"):
            fn = os.path.basename(self.path.split("?")[0])
            if fn not in _VIDEO_EXAMPLES:
                self._send(404, "text/plain", b"unknown video")
                return
            with open(os.path.join(_VIDEO_EXAMPLES_DIR, fn), "rb") as f:
                self._send(200, "video/mp4", f.read())
        elif self.path.startswith("/example?"):
            fn = parse_qs(urlparse(self.path).query).get("name", [""])[0]
            if fn not in _EXAMPLES:
                self._send(404, "text/plain", b"unknown example")
                return
            with open(os.path.join(_EXAMPLES_DIR, fn), "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            self._send(
                200,
                "application/json",
                json.dumps({"image": "data:image/jpeg;base64," + b64}).encode(),
            )
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        handler = {
            "/infer": self._infer,
            "/track": self._track,
            "/compare": self._compare,
        }.get(parsed.path)
        if handler is None:
            self._send(404, "text/plain", b"not found")
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            if parsed.path == "/track":
                # /track POSTs the raw video bytes (no base64 — big files overflow the
                # browser string allocator); caption + timings ride in the query string.
                q = parse_qs(parsed.query)
                out = handler(
                    {
                        "video_bytes": body,
                        "caption": q.get("caption", [""])[0],
                        "acquire_s": q.get("acquire", ["4.0"])[0],
                        "period_s": q.get("anchor", ["2.0"])[0],
                    }
                )
            else:
                out = handler(json.loads(body))
        except Exception as e:  # noqa: BLE001 — surface any failure to the browser
            out = {"error": str(e)}
        self._send(200, "application/json", json.dumps(out).encode())

    def _infer(self, req: dict) -> dict:
        caption = req["caption"]
        _, b64 = req["image"].split(",", 1)  # strip "data:image/...;base64,"
        png_bytes = base64.b64decode(b64)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tf:
            tf.write(png_bytes)
            tf.flush()
            raw = _BACKEND.generate(tf.name, caption)
        box = parse_bbox(raw)
        if box is None:
            return {"error": f"unparseable output: {raw!r}"}
        annotated = base64.b64encode(_annotate(png_bytes, box, caption)).decode()
        return {
            "box": box,
            "raw": raw,
            "annotated": "data:image/png;base64," + annotated,
        }

    def _compare(self, req: dict) -> dict:
        """ROI re-anchor vs full-frame, side by side, on one uploaded image.

        Full-frame pass = acquire (the box + its prefill cost). Then crop around that
        box (margin M, upscaled to OUT_RES) and re-anchor — the cheap per-frame pass a
        following loop would actually run. Returns both annotated images + the prefill/
        decode split for each, so the speed *and* the super-resolution tightening are
        both visible. (Live, on the deployed Q8_0 — a qualitative on-device check of the
        results/2026-06-25-roi-crop-anchor finding, which was quantified on HF bf16.)"""
        caption = req["caption"]
        _, b64 = req["image"].split(",", 1)
        png_bytes = base64.b64decode(b64)
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

        # 1) full-frame acquire — the deploy resize (max_side) the server normally uses.
        raw_f, pf_ms, df_ms = _timed_post(img, caption, _BACKEND.max_side)
        box_f = parse_bbox(raw_f)
        if box_f is None:
            return {"error": f"full-frame pass unparseable: {raw_f!r}"}

        # 2) ROI re-anchor — crop around the acquired box, upscale to the budget.
        win = roi_window(box_f, img.width, img.height, _ROI_MARGIN)
        crop = crop_resize(img, win, _ROI_OUT_RES, upscale=False)
        raw_r, pr_ms, dr_ms = _timed_post(crop, caption, 10**9)  # crop is pre-sized
        box_r = parse_bbox(raw_r)
        if box_r is None:
            return {"error": f"ROI pass unparseable: {raw_r!r}"}
        box_roi = map_to_full(box_r, win, img.width, img.height)

        ann_f = _annotate(png_bytes, box_f, caption, color=(214, 40, 40))
        ann_r = _annotate(png_bytes, box_roi, caption, color=(26, 158, 58), window=win)
        speedup = pf_ms / pr_ms if pr_ms else 0.0
        return {
            "full": {
                "annotated": "data:image/png;base64,"
                + base64.b64encode(ann_f).decode(),
                "prefill_ms": round(pf_ms),
                "decode_ms": round(df_ms),
                "box": box_f,
            },
            "roi": {
                "annotated": "data:image/png;base64,"
                + base64.b64encode(ann_r).decode(),
                "prefill_ms": round(pr_ms),
                "decode_ms": round(dr_ms),
                "box": box_roi,
            },
            "speedup": round(speedup, 2),
        }

    def _track(self, req: dict) -> dict:
        """Whole-system run on an uploaded clip → annotated mp4 (full-res h264, one
        box/frame). Terse anchor (full-frame acquire → ROI-crop re-anchor) + CSRT
        coasting; slow (a few ssh VLM passes), single-user demo only."""
        caption = req["caption"]
        acquire_s = float(req.get("acquire_s", 4.0) or 4.0)
        period_s = float(req.get("period_s", 2.0) or 2.0)
        vid_bytes = req["video_bytes"]
        anchors_out = []

        def _on_anchor(fi, fed_pil, box, full_pil, elapsed_s, stats):
            def _b64png(img):
                buf = io.BytesIO(); img.save(buf, "PNG")
                return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            fed_b64 = _b64png(fed_pil)
            if box is not None:
                buf = io.BytesIO(); full_pil.save(buf, "PNG")
                ann_b64 = "data:image/png;base64," + base64.b64encode(
                    _annotate(buf.getvalue(), box, caption, color=(40, 190, 70))
                ).decode()
                buf2 = io.BytesIO(); fed_pil.save(buf2, "PNG")
                win = stats.get("roi_win")
                if win is not None:
                    # box is in full-frame coords; invert map_to_full to get crop coords
                    wx0, wy0, wx1, wy1 = win
                    rw, rh = wx1 - wx0, wy1 - wy0
                    fw, fh = full_pil.width, full_pil.height
                    crop_box = [
                        round((box[0] / COORD_SCALE * fw - wx0) / rw * COORD_SCALE),
                        round((box[1] / COORD_SCALE * fh - wy0) / rh * COORD_SCALE),
                        round((box[2] / COORD_SCALE * fw - wx0) / rw * COORD_SCALE),
                        round((box[3] / COORD_SCALE * fh - wy0) / rh * COORD_SCALE),
                    ]
                else:
                    crop_box = box  # full-frame anchor: fed_pil IS the full frame
                ann_crop_b64 = "data:image/png;base64," + base64.b64encode(
                    _annotate(buf2.getvalue(), crop_box, caption, color=(40, 190, 70))
                ).decode()
            else:
                ann_b64 = _b64png(full_pil)
                ann_crop_b64 = fed_b64
            anchors_out.append({
                "fi": fi, "fed": fed_b64, "annotated_crop": ann_crop_b64,
                "annotated": ann_b64, "elapsed_s": round(elapsed_s, 2), "stats": stats,
            })

        vf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        of = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        try:
            vf.write(vid_bytes)
            vf.close()
            of.close()
            _render_track(
                vf.name,
                caption,
                of.name,
                _BACKEND,
                stride=1,
                period_s=period_s,
                acquire_s=acquire_s,
                track=True,
                max_seconds=_TRACK_MAX_S,
                on_anchor=_on_anchor,
            )
            mp4_b64 = base64.b64encode(open(of.name, "rb").read()).decode()
        finally:
            os.unlink(vf.name)
            os.unlink(of.name)
        return {
            "video": "data:video/mp4;base64," + mp4_b64,
            "note": "done — terse anchor + ROI re-anchor + CSRT coast",
            "anchors": anchors_out,
        }

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
    _BACKEND = JetsonBackend(
        remote_model, remote_mmproj, ssh_host=args.ssh_host, max_side=args.max_side
    )
    try:
        httpd = ThreadingHTTPServer((args.host, args.port), _Handler)
        print(
            f"[gui] open http://{args.host}:{args.port}  (Ctrl-C to stop)", flush=True
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[gui] shutting down...", flush=True)
    finally:
        _BACKEND.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
