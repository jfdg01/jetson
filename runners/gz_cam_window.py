#!/usr/bin/env python3
"""
gz_cam_window.py -- one OpenCV window showing a live Gazebo camera topic.

Subscribes to an ALREADY-RUNNING `gz sim` and shows the frames. It does not
start or configure the simulator -- run `gz sim` yourself first.

    .venv-ft/bin/python runners/gz_cam_window.py                    # auto-pick topic
    .venv-ft/bin/python runners/gz_cam_window.py -t /some/image     # explicit

Keys: f = fullscreen toggle, s = save frame to ./gz_cam_<n>.png, q/ESC = quit.

Exists because `gz gui -s ImageDisplay` segfaults (standalone mode has no
MainWindow, and ImageDisplay's OnTopic notifies it unconditionally), and the
docked panel inside the main Gazebo window is fiddly to size.
"""
import argparse
import os
import subprocess
import sys
import threading

import cv2  # from the venv -- import BEFORE touching sys.path
import numpy as np

sys.path.append("/usr/lib/python3/dist-packages")  # APPEND: gz-transport13 / gz-msgs10 only;
# must not front-shadow the venv's numpy/cv2 (different ABI -> native crash, no traceback)
from gz.msgs10.image_pb2 import Image, PixelFormatType  # noqa: E402
from gz.transport13 import Node  # noqa: E402

_latest = {"rgb": None}
_lock = threading.Lock()

# ponytail: only the formats a gz camera sensor actually emits. Add on demand.
_CHANNELS = {"RGB_INT8": 3, "BGR_INT8": 3, "L_INT8": 1}


def _find_topic():
    """First /image topic gz knows about. One camera is the common case."""
    out = subprocess.run(["gz", "topic", "-l"], capture_output=True, text=True).stdout
    cams = [t for t in out.split() if t.endswith("/image")]
    if not cams:
        sys.exit("no /image topic found -- is `gz sim` running?")
    if len(cams) > 1:
        print("multiple camera topics, using the first:", *cams, sep="\n  ")
    return cams[0]


def _on_image(msg: Image):
    fmt = PixelFormatType.Name(msg.pixel_format_type)
    ch = _CHANNELS.get(fmt)
    if ch is None:
        print(f"unsupported pixel format {fmt}", file=sys.stderr)
        return
    buf = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width, ch)
    bgr = buf[:, :, ::-1] if fmt == "RGB_INT8" else buf
    with _lock:
        _latest["rgb"] = np.ascontiguousarray(bgr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-t", "--topic", help="camera image topic (default: autodetect)")
    args = ap.parse_args()

    topic = args.topic or _find_topic()
    node = Node()
    if not node.subscribe(Image, topic, _on_image):
        sys.exit(f"subscribe failed: {topic}")
    print(f"subscribed: {topic}\nkeys: f=fullscreen  s=save  q=quit")

    win, saved, full = "gz camera", 0, False
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    while True:
        with _lock:
            frame = _latest["rgb"]
        if frame is not None:
            cv2.imshow(win, frame)
        k = cv2.waitKey(20) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("f"):
            full = not full
            cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if full else cv2.WINDOW_NORMAL)
        if k == ord("s") and frame is not None:
            path = f"gz_cam_{saved}.png"
            cv2.imwrite(path, frame)
            print("wrote", path)
            saved += 1
        if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
            break
    cv2.destroyAllWindows()
    # ponytail: gz-transport's Node dtor aborts at interpreter shutdown
    # ("terminate called without an active exception"). Nothing to flush -- just leave.
    os._exit(0)


if __name__ == "__main__":
    main()
