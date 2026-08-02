"""One accessor for every dataset. Callers ask `data.boxes(seq)` and never learn which one it was.

Resolution is by SEQUENCE NAME, not by an argument threaded through every call site. The reason is
the recorded runs: a `raw/` JSON stores `meta["seq"]` and nothing else, so any scheme that needs a
dataset id would invalidate ~1000 files already on disk. UAV123 names are lower case (`uav2`,
`person4_1`), TLP names are CamelCase (`Basketball`, `ISS`), so they do not collide -- and `_index()`
refuses to build if they ever do, instead of silently picking one.

What stays outside: `uav123.attrs()` / `ATTRS` / `CATS` are the 12 attribute flags UAV123 ships and
TLP has no equivalent of. `difficulty.py` and `select_sequences.py` are UAV123-specific analyses, so
they keep importing `uav123` directly. Faking an empty attribute table for TLP would let those two
run and return nonsense.
"""
from __future__ import annotations

import functools
from pathlib import Path

import uav123

Box = list[float]


class Dataset:
    """Frames plus per-frame ground truth. `boxes` is xyxy, `None` where the target is absent."""

    name: str

    def sequences(self) -> list[str]:
        raise NotImplementedError

    def boxes(self, seq: str) -> list[Box | None]:
        raise NotImplementedError

    def frame_paths(self, seq: str) -> list[Path]:
        raise NotImplementedError

    def init_box(self, seq: str) -> Box | None:
        return self.boxes(seq)[0]

    def __repr__(self) -> str:
        return f"<{self.name}>"


class Uav123(Dataset):
    """Delegates to `uav123.py`, which stays as-is: it also serves the two UAV123-only analyses."""

    name = "uav123"

    def sequences(self) -> list[str]:
        return sorted(uav123.config())

    def boxes(self, seq: str) -> list[Box | None]:
        return uav123.boxes(seq)

    def frame_paths(self, seq: str) -> list[Path]:
        return uav123.frame_paths(seq)


class Tlp(Dataset):
    """`<Seq>/img/00001.jpg` + `<Seq>/groundtruth_rect.txt`, one line `frame,x,y,w,h,isLost`.

    `isLost` is the reason this dataset is here: per the authors, "If 1, the target object is not
    visible at all; else 0". UAV123 only has NaN rows, which conflate occlusion with out-of-frame.
    One flag here too -- TLP does not separate those two either.
    """

    name = "tlp"
    root = Path("/home/gara/jetson/data/TLP")

    def sequences(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if (p / "groundtruth_rect.txt").is_file())

    def boxes(self, seq: str) -> list[Box | None]:
        out: list[Box | None] = []
        text = (self.root / seq / "groundtruth_rect.txt").read_text()
        for n, ln in enumerate(text.split(), start=1):
            i, x, y, w, h, lost = (float(v) for v in ln.split(","))
            # the frame column is 1-based and dense; if it ever is not, the zip against
            # frame_paths() below would silently pair a box with the wrong image
            assert i == n, f"{seq}: GT line {n} says frame {i:.0f}"
            out.append(None if lost else [x, y, x + w, y + h])
        return out

    def frame_paths(self, seq: str) -> list[Path]:
        return sorted((self.root / seq / "img").glob("*.jpg"))


DATASETS: list[Dataset] = [Uav123(), Tlp()]


@functools.cache
def _index() -> dict[str, Dataset]:
    """Frozen for the life of the process on purpose: a run must not see the set change mid-flight
    (TLP is still downloading, so `Tlp.sequences()` grows between passes)."""
    idx: dict[str, Dataset] = {}
    for d in DATASETS:
        for s in d.sequences():
            if s in idx:
                raise KeyError(f"sequence {s!r} in both {idx[s].name} and {d.name}; "
                               "resolution by name no longer works, add an explicit dataset id")
            idx[s] = d
    return idx


def get(seq: str) -> Dataset:
    try:
        return _index()[seq]
    except KeyError:
        raise KeyError(f"unknown sequence {seq!r}; known: "
                       + ", ".join(f"{d.name}={len(d.sequences())}" for d in DATASETS)) from None


def sequences(dataset: str | None = None) -> list[str]:
    """All sequence names, or one dataset's."""
    return sorted(s for s, d in _index().items() if dataset in (None, d.name))


def boxes(seq: str) -> list[Box | None]:
    return get(seq).boxes(seq)


def frame_paths(seq: str) -> list[Path]:
    return get(seq).frame_paths(seq)


def init_box(seq: str) -> Box | None:
    return get(seq).init_box(seq)


if __name__ == "__main__":  # self-check: every sequence must have one box per frame
    idx = _index()
    print({d.name: len(d.sequences()) for d in DATASETS})
    for name in idx:
        nb, nf = len(boxes(name)), len(frame_paths(name))
        assert nb == nf, f"{name}: {nb} boxes vs {nf} frames"
        assert init_box(name) is not None, f"{name}: frame 1 has no GT, cannot initialise"
    print(f"{len(idx)} sequences, {sum(len(frame_paths(n)) for n in idx)} frames, all lengths match")
