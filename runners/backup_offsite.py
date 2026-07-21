#!/usr/bin/env python3
"""Mirror the irreplaceable part of this project to the offsite VPS.

Run:  .venv-ft/bin/python runners/backup_offsite.py [--dry-run] [--host oracle]

What "irreplaceable" means here is a judgement, and it is the whole point of
this script, so it is spelled out rather than buried in an rsync filter:

  weights   22 GB   GGUF checkpoints. The merged HF/safetensors training dir is
                    lost and no LoRA adapter survives, so these cannot be
                    re-exported. A retrain yields a *different* model and breaks
                    cell-for-cell comparability with every number in Parts II-V.
  git       ~0.5 GB `git bundle --all`: full history, every committed proof/
                    deliverable, every ledger. One file, clonable directly.
  records   ~0.8 GB Every .json/.jsonl/.csv/.log/.md/.py/.txt/.yaml under
                    experiments/ and runs/, tracked or not. These are the raw
                    measurements. Re-deriving one means re-running its GPU hours,
                    and for the SITL/CARLA runs it is not even deterministic.

Deliberately NOT copied, so the absence is a decision and not an oversight:

  data/     138 GB  VisDrone, AerialMind, COCO. Public downloads, and they do
                    not fit alongside the weights in the VPS's 74 GB.
  media     43 GB   .mp4/.png/.jpg under experiments/. Renders from seeded
                    runners. The curated ones are in proof/ and therefore
                    already inside the git bundle. Copying the rest would leave
                    the VPS at ~8 GB free, which is how you break a box that is
                    also serving other things.

Verification is sha256 on both ends, because "rsync exited 0" is a claim about a
transfer and not about the bytes that landed.
"""

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WEIGHTS = Path("/home/gara/grounding-checkpoint-backup")
REMOTE_ROOT = "jetson-offsite"

# Records live in these trees. Anything with one of these suffixes is a
# measurement; anything else in them is a render.
RECORD_ROOTS = ["experiments", "runs", "logs"]
RECORD_SUFFIXES = {
    ".json", ".jsonl", ".csv", ".log", ".md", ".py", ".txt",
    ".yaml", ".yml", ".toml", ".sh", ".bib",
}
SKIP_DIRS = {"__pycache__", ".git", ".venv", ".venv-ft", "node_modules"}
# ponytail: a size cap instead of a per-file allowlist. A .log or .jsonl over
# this is a frame dump that happened to get a text suffix, not a record.
MAX_RECORD_BYTES = 512 * 1024 * 1024


def utcstamp() -> str:
    # Project convention: Madrid wall-clock with a Z suffix, not UTC-converted.
    return datetime.now().strftime("%Y-%m-%dT%H:%MZ")


def run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run(cmd, check=True, **kw)


def collect_records() -> list[str]:
    """Repo-relative paths of every measurement record."""
    out = []
    for root_name in RECORD_ROOTS:
        root = REPO / root_name
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if Path(name).suffix.lower() not in RECORD_SUFFIXES:
                    continue
                p = Path(dirpath) / name
                try:
                    if p.stat().st_size > MAX_RECORD_BYTES:
                        print(f"  skip (too big for a record): {p.relative_to(REPO)}")
                        continue
                except OSError:
                    continue
                out.append(str(p.relative_to(REPO)))
    return sorted(out)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="oracle", help="ssh alias of the offsite box")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-weights", action="store_true",
                    help="records + git only (they take seconds; weights take an hour)")
    args = ap.parse_args()

    host, dry = args.host, args.dry_run
    rsync_base = ["rsync", "-a", "--partial", "--info=progress2"]
    if dry:
        rsync_base.append("--dry-run")

    print(f"[{utcstamp()}] offsite backup -> {host}:~/{REMOTE_ROOT}")

    # Refuse to fill the remote disk. Under 40 GB free means the weights do not
    # fit with headroom, and a full disk breaks whatever else the box is doing.
    free_kb = int(subprocess.run(
        ["ssh", host, "df --output=avail -k / | tail -1"],
        check=True, capture_output=True, text=True).stdout.strip())
    free_gb = free_kb / 2**20
    print(f"  remote free: {free_gb:.1f} GB")
    if free_gb < 40 and not args.skip_weights:
        print("  ABORT: under 40 GB free, weights would not fit with headroom.")
        return 1

    if not dry:
        run(["ssh", host, f"mkdir -p ~/{REMOTE_ROOT}/{{weights,git,records}}"])

    # --- git: one bundle, full history -------------------------------------
    print("\n[git] bundling all refs")
    with tempfile.TemporaryDirectory() as td:
        bundle = Path(td) / "jetson.bundle"
        run(["git", "-C", str(REPO), "bundle", "create", str(bundle), "--all"])
        head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
        local_hash = sha256(bundle)
        print(f"  HEAD {head[:12]}  sha256 {local_hash[:16]}...  "
              f"{bundle.stat().st_size / 2**30:.2f} GB")
        if not dry:
            run(rsync_base + [str(bundle), f"{host}:~/{REMOTE_ROOT}/git/jetson.bundle"])
            remote_hash = subprocess.run(
                ["ssh", host, f"sha256sum ~/{REMOTE_ROOT}/git/jetson.bundle"],
                check=True, capture_output=True, text=True).stdout.split()[0]
            assert remote_hash == local_hash, f"bundle corrupt: {remote_hash} != {local_hash}"
            print("  bundle sha256 VERIFIED")

    # --- records: small, many ----------------------------------------------
    records = collect_records()
    total = sum((REPO / r).stat().st_size for r in records)
    print(f"\n[records] {len(records)} files, {total / 2**30:.2f} GB")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("\n".join(records) + "\n")
        listfile = fh.name
    try:
        run(rsync_base + [f"--files-from={listfile}", str(REPO) + "/",
                          f"{host}:~/{REMOTE_ROOT}/records/"])
    finally:
        os.unlink(listfile)

    # --- weights: big, few, already sha-verified against the Jetson ---------
    if not args.skip_weights:
        print(f"\n[weights] {WEIGHTS}")
        if not WEIGHTS.is_dir():
            print("  ABORT: local weights mirror missing")
            return 1
        run(rsync_base + [str(WEIGHTS) + "/", f"{host}:~/{REMOTE_ROOT}/weights/"])
        if not dry:
            print("  verifying sha256 on the remote (this reads 22 GB, ~2 min)")
            r = subprocess.run(
                ["ssh", host, f"cd ~/{REMOTE_ROOT}/weights && sha256sum -c SHA256SUMS"],
                capture_output=True, text=True)
            bad = [l for l in r.stdout.splitlines() if not l.endswith(": OK")]
            print(f"  {len(r.stdout.splitlines()) - len(bad)} OK, {len(bad)} FAILED")
            for l in bad:
                print(f"    {l}")
            if r.returncode != 0:
                return 1

    # --- a README on the remote, so the copy explains itself ----------------
    if not dry:
        readme = f"""# jetson thesis - offsite copy

Written {utcstamp()} by runners/backup_offsite.py from the workstation.
Repo HEAD at copy time: {head}

    git/jetson.bundle   full history, all refs. `git clone jetson.bundle jetson`
    weights/            {len(list(WEIGHTS.glob('*.gguf')))} GGUFs, sha256-verified against SHA256SUMS
    records/            {len(records)} measurement files, tree layout preserved

NOT here, on purpose: data/ (138 GB of public datasets - VisDrone, AerialMind,
COCO) and the 43 GB of rendered .mp4/.png under experiments/. The renders come
back from seeded runners; the curated ones are inside the bundle already. Both
were excluded because they do not fit in this box's disk, not because they were
forgotten.

To restore: clone the bundle, re-download the datasets, rsync weights/ back to
the Jetson at /home/jfdg/grounding/, and re-run the runners for any render you
actually need.
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(readme)
            tmp_readme = fh.name
        try:
            run(["rsync", "-a", tmp_readme, f"{host}:~/{REMOTE_ROOT}/README.md"])
        finally:
            os.unlink(tmp_readme)

    print(f"\n[{utcstamp()}] done. Remote usage:")
    subprocess.run(["ssh", host, f"du -sh ~/{REMOTE_ROOT}/*; df -h / | tail -1"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
