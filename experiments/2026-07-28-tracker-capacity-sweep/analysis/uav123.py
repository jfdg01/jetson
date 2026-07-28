"""UAV123 accessors. Host-side only; the device never imports this and never sees GT.

A UAV123 sequence name is not a folder: configSeqs.m maps a name to a frame FOLDER plus a
[startFrame, endFrame] range, so the long parents are split into sub-sequences (bird1_2 ->
folder bird1, frames 775..1477). There are 143 config entries, 123 of which have annotation;
listing folders instead gives 91 and silently loses the splits.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("/home/gara/jetson/data/UAV123")
SEQ = ROOT / "data_seq/UAV123"
ANNO = ROOT / "anno/UAV123"

# Column order of anno/UAV123/att/*.txt, from the table header of DatasetAnnotation.pdf.
# NOT alphabetical. Checked: FOC agrees 1.00 with "has NaN frames", which is its definition.
ATTRS = ["SV", "ARC", "LR", "FM", "FOC", "POC", "OV", "BC", "IV", "VC", "CM", "SOB"]
CATS = ["bike", "bird", "boat", "building", "car", "group", "person", "truck", "uav", "wakeboard"]

_CFG = re.compile(
    r"name','(?P<name>[^']+)','path','[^']*?(?P<folder>[^\\']+)\\','startFrame',"
    r"(?P<start>\d+),'endFrame',(?P<end>\d+),'nz',(?P<nz>\d+),'ext','(?P<ext>[^']+)'"
)


def config() -> dict[str, tuple[str, int, int, int, str]]:
    """name -> (folder, start, end, zero_pad, ext), only names that have annotation."""
    out = {}
    for m in _CFG.finditer((ROOT / "configSeqs.m").read_text()):
        d = m.groupdict()
        if (ANNO / f"{d['name']}.txt").exists():
            out[d["name"]] = (d["folder"], int(d["start"]), int(d["end"]), int(d["nz"]), d["ext"])
    return out


def boxes(name: str) -> list[list[float] | None]:
    """GT as xyxy per frame; None where the target is fully occluded or out of frame (NaN)."""
    out = []
    for ln in (ANNO / f"{name}.txt").read_text().split():
        if "NaN" in ln:
            out.append(None)
        else:
            x, y, w, h = (float(v) for v in ln.split(","))
            out.append([x, y, x + w, y + h])
    return out


def init_box(name: str) -> list[float] | None:
    return boxes(name)[0]


def attrs(name: str) -> dict[str, int]:
    vals = [int(v) for v in (ANNO / "att" / f"{name}.txt").read_text().strip().split(",")]
    return dict(zip(ATTRS, vals))


def frame_paths(name: str) -> list[Path]:
    folder, start, end, nz, ext = config()[name]
    return [SEQ / folder / f"{i:0{nz}d}.{ext}" for i in range(start, end + 1)]


if __name__ == "__main__":  # self-check: config parse must line up with annotation length
    cfg = config()
    assert len(cfg) == 123, len(cfg)
    bad = [n for n in cfg if len(boxes(n)) != len(frame_paths(n))]
    assert not bad, bad
    print(f"{len(cfg)} sequences, {sum(len(frame_paths(n)) for n in cfg)} frames, all lengths match")
