#!/usr/bin/env python3
"""Grab the live demo panel's window to a PNG, so a UI claim can be looked at.

The repo rule is that any claim about what something LOOKS like must be backed by an
image opened with the Read tool -- and a Tk layout fails visually while exiting 0 just
as readily as a render does (invisible entries, a white checkbox, a tab strip overlapping
its frame: all found by screenshot, none by reading code).

    .venv-ft/bin/python runners/ui_shot.py                      # -> runs/ui/panel.png
    .venv-ft/bin/python runners/ui_shot.py --out /tmp/a.png --name "CARLA debug"
    .venv-ft/bin/python runners/ui_shot.py --crop-h 260         # just the control strip

`xwd -id` reads the WINDOW's own contents, not the screen region under it. That matters
twice: an x11grab of the panel's geometry on this 5120x1440 two-monitor desktop returns
whatever is actually on top (the first attempt at this screenshotted a browser), and the
xwd path needs neither focus nor a raise, so grabbing does not steal the operator's
screen. `--screen` keeps the old region grab for the case where xwd is unavailable.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


def is_client(wid):
    """Does this id own the pixels, or is it the WM's frame around them?

    The window manager reparents the app's window into a frame of its own and copies
    the name onto it, so a name search returns both -- and the frame is the BIGGER of
    the two (it adds the title bar), which is how picking "the largest" produced a
    black grab with a title bar on it. Only the real client window carries WM_STATE.
    """
    out = subprocess.run(["xprop", "-id", wid, "WM_STATE"],
                         capture_output=True, text=True).stdout
    return "window state" in out


def pick_window(name):
    """(id, x, y, w, h) for the biggest CLIENT window matching `name`."""
    ids = subprocess.run(["xdotool", "search", "--name", name],
                         capture_output=True, text=True).stdout.split()
    if not ids:
        sys.exit(f"no window named {name!r} -- is the panel running?")
    ids = [w for w in ids if is_client(w)] or ids
    best = None
    for wid in ids:
        out = subprocess.run(["xdotool", "getwindowgeometry", wid],
                             capture_output=True, text=True).stdout
        pos = size = None
        for line in out.splitlines():
            if "Position:" in line:
                pos = line.split("Position:")[1].split("(")[0].strip()
            if "Geometry:" in line:
                size = line.split("Geometry:")[1].strip()
        if not pos or not size:
            continue
        x, y = (int(v) for v in pos.split(","))
        w, h = (int(v) for v in size.split("x"))
        if best is None or w * h > best[3] * best[4]:
            best = (wid, x, y, w, h)
    if best is None:
        sys.exit(f"window {name!r} has no readable geometry")
    return best


def grab_window(wid, out):
    """xwd the window's own pixels, then let ffmpeg decode xwd -> png."""
    xwd = out.with_suffix(".xwd")
    with open(xwd, "wb") as f:
        subprocess.run(["xwd", "-id", str(wid)], stdout=f, check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(xwd), str(out)],
                   check=True)
    xwd.unlink(missing_ok=True)


def grab_screen(x, y, w, h, out):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab",
                    "-video_size", f"{w}x{h}", "-i", f":0.0+{x},{y}",
                    "-frames:v", "1", str(out)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="CARLA debug")
    ap.add_argument("--out", default="runs/ui/panel.png")
    ap.add_argument("--crop-h", type=int, default=0,
                    help="keep only the top N rows (the control strip)")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--screen", action="store_true",
                    help="grab the screen region instead of the window's own pixels "
                         "(shows whatever is on top -- only for when xwd fails)")
    args = ap.parse_args()

    wid, x, y, w, h = pick_window(args.name)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.screen:
        grab_screen(x, y, w, h, out)
    else:
        grab_window(wid, out)
    img = cv2.imread(str(out))
    if img is None:
        sys.exit(f"ffmpeg wrote {out} but it does not decode")
    if args.crop_h:
        img = img[:args.crop_h]
    if args.scale != 1.0:
        img = cv2.resize(img, None, fx=args.scale, fy=args.scale,
                         interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out), img)
    # The classic silent failure: a grab of an unmapped or occluded window is one flat
    # colour, which reads as "the panel is dark themed" if nobody checks.
    flat = (np.bincount(img.reshape(-1, 3) @ np.array([1, 256, 65536]),
                        minlength=1).max() / (img.shape[0] * img.shape[1]))
    print(f"{out}  {img.shape[1]}x{img.shape[0]}  most-common colour {flat:.1%}")
    if flat > 0.99:
        sys.exit("FAIL: >99% one colour -- that is an unmapped window, not a screenshot")


if __name__ == "__main__":
    main()
