"""AerialMind loader for the temporal carry eval (Phase 0).

On-disk layout (data/AerialMind/, gitignored, 93 sequences):
  image_02/<seq>/NNNNNNN.jpg          frames (integer names; some seqs also carry
                                      stray .txt beside the jpgs -- ignored)
  labels_with_ids/<seq>/NNNNNNN.txt   JDE lines: class tid cx cy w h  (normalized)
  expression/<seq>/<text>.json        {"label": {"<frame>": [tid, ...]}}

Everything is exposed in *pixel* xyxy at native frame resolution -- SAM2 is
prompted in pixels, and the carry metrics are plain pixel IoU.

    python experiments/2026-07-01-temporal-acquire-carry/aerialmind.py   # selfcheck
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

Box = Tuple[float, float, float, float]  # x1 y1 x2 y2, pixels

ROOT = Path(__file__).resolve().parents[2] / "data" / "AerialMind"

# a track vanishing for >= this many labeled-frame slots counts as an occlusion event
GAP_MIN_FRAMES = 3


@dataclass
class Track:
    tid: int
    boxes: Dict[int, Box]  # frame number -> pixel box

    @property
    def start(self) -> int:
        return min(self.boxes)

    @property
    def end(self) -> int:
        return max(self.boxes)

    @property
    def length(self) -> int:
        return len(self.boxes)

    def gaps(self) -> List[Tuple[int, int]]:
        """(gap_start_frame, gap_len) runs of >= GAP_MIN_FRAMES missing frames
        strictly inside [start, end] -- the occlusion/out-of-view events."""
        frames = sorted(self.boxes)
        out = []
        for a, b in zip(frames, frames[1:]):
            if b - a - 1 >= GAP_MIN_FRAMES:
                out.append((a + 1, b - a - 1))
        return out


@dataclass
class Sequence:
    name: str
    img_dir: Path
    frame_nums: List[int]  # sorted integer frame names with a .jpg on disk
    width: int
    height: int
    _tracks: Dict[int, Track] = field(default_factory=dict, repr=False)

    def frame_path(self, frame: int) -> Path:
        return self.img_dir / f"{frame:07d}.jpg"

    def tracks(self) -> Dict[int, Track]:
        """tid -> Track, parsed lazily from labels_with_ids (class column ignored)."""
        if self._tracks:
            return self._tracks
        lab_dir = ROOT / "labels_with_ids" / self.name
        for f in lab_dir.glob("*.txt"):
            frame = int(f.stem)
            for line in f.read_text().splitlines():
                p = line.split()
                if len(p) < 6:
                    continue
                tid = int(p[1])
                cx, cy, w, h = (float(v) for v in p[2:6])
                # labels extend past the frame for half-out-of-view targets; clamp
                box = (
                    max(0.0, (cx - w / 2) * self.width),
                    max(0.0, (cy - h / 2) * self.height),
                    min(float(self.width), (cx + w / 2) * self.width),
                    min(float(self.height), (cy + h / 2) * self.height),
                )
                if box[0] < box[2] and box[1] < box[3]:  # drop fully-outside boxes
                    self._tracks.setdefault(tid, Track(tid, {})).boxes[frame] = box
        return self._tracks

    def labels_at(self, frame: int) -> Dict[int, Box]:
        """tid -> box for one frame (from the parsed tracks)."""
        return {
            tid: t.boxes[frame] for tid, t in self.tracks().items() if frame in t.boxes
        }

    def expressions(self) -> List[Tuple[str, Dict[int, List[int]]]]:
        """(expression text, {frame -> [matching tids]}) -- acquire-tier ground truth."""
        out = []
        for f in sorted((ROOT / "expression" / self.name).glob("*.json")):
            lab = json.loads(f.read_text())["label"]
            out.append((f.stem, {int(k): list(v) for k, v in lab.items()}))
        return out


def load_sequences(limit: int | None = None) -> List[Sequence]:
    from PIL import Image

    seqs = []
    for d in sorted((ROOT / "image_02").iterdir()):
        if not d.is_dir():
            continue
        nums = sorted(int(f[:-4]) for f in os.listdir(d) if f.endswith(".jpg"))
        if not nums:
            continue
        with Image.open(d / f"{nums[0]:07d}.jpg") as im:
            w, h = im.size
        seqs.append(Sequence(d.name, d, nums, w, h))
        if limit and len(seqs) >= limit:
            break
    return seqs


def pick_eval_tracks(seq: Sequence, n: int = 2, min_len: int = 50) -> List[Track]:
    """Longest track + longest track WITH an occlusion gap (the permanence probe).
    ponytail: two tracks/seq spans 93 seqs cheaply; raise n if Phase 0 needs power."""
    cands = [t for t in seq.tracks().values() if t.length >= min_len]
    cands.sort(key=lambda t: t.length, reverse=True)
    picked = cands[:1]
    for t in cands[1:]:
        if len(picked) >= n:
            break
        if t.gaps() and not picked[0].gaps():
            picked.append(t)
    for t in cands[1:]:
        if len(picked) >= n:
            break
        if t not in picked:
            picked.append(t)
    return picked


def _selfcheck() -> None:
    seqs = load_sequences()
    assert len(seqs) == 93, f"expected 93 sequences, got {len(seqs)}"
    s = next(x for x in seqs if x.name == "uav0000077_00720_v")
    tracks = s.tracks()
    assert tracks, "no tracks parsed"
    for t in list(tracks.values())[:20]:
        for fr, (x1, y1, x2, y2) in t.boxes.items():
            assert 0 <= x1 < x2 <= s.width and 0 <= y1 < y2 <= s.height, (
                s.name,
                t.tid,
                fr,
                (x1, y1, x2, y2),
            )
    exprs = s.expressions()
    assert exprs and all(isinstance(k, int) for _, lab in exprs for k in lab)
    picked = pick_eval_tracks(s)
    assert picked and all(p.length >= 50 for p in picked)
    n_gap = sum(1 for x in seqs for t in pick_eval_tracks(x) if t.gaps())
    print(
        f"  selfcheck PASS  93 seqs  {s.name}: {len(tracks)} tracks, "
        f"{len(exprs)} expressions, {s.width}x{s.height}; "
        f"picked tracks with occlusion gaps across dataset: {n_gap}"
    )


if __name__ == "__main__":
    _selfcheck()
