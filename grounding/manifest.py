"""Per-run provenance manifests — v2's experiment-tracking spine.

We track experiments with **plain files**, not a tracking server: every run writes a
`manifest.json` (machine-readable) plus a `run-card.md` (human-readable) into its own
`experiments/runs/<run_id>/` directory. This matches the repo's lab-notebook ethos (greppable,
diffable, committable, survives into the thesis) and adds no daemon or cloud
dependency. See DECISIONS.md (Part II) for why this over MLflow/W&B.

The binding constraint v2 is organised around is *cross-backend comparability*: the
−23pp HF↔GGUF gap is sensitive to the exact llama.cpp build and the exact Python
env. A manifest therefore captures everything needed to recover "which bits ran":

  - git SHA + dirty flag of this repo
  - the pinned llama.cpp commit (LLAMACPP_COMMIT below)
  - sha256 of the dependency lock (requirements-ft.lock.txt)
  - sha256 of the dataset, when a run consumes one
  - the full run config (any JSON-serialisable dict, e.g. asdict(TrainConfig))
  - python version + platform

Stdlib-only (subprocess, hashlib, json, ...) so it imports anywhere `contract.py`
does — including a backend process that must not depend on torch.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# --- Pinned external runtime versions -------------------------------------------
# The Jetson llama.cpp checkout v2 is built/measured against. The fidelity gap is
# runtime-version-sensitive, so this commit is a binding artifact: re-pin (and
# re-baseline parity) only deliberately, and log it in DECISIONS.md when you do.
LLAMACPP_COMMIT = "57fe1f07c3b6a1de3f4fff19098e2056a85275b7"

# Path to the dependency lock, relative to repo root (hashed into every manifest).
LOCKFILE_NAME = "requirements-ft.lock.txt"


def _repo_root() -> Path:
    """Repo root = the directory containing this package's parent."""
    return Path(__file__).resolve().parent.parent


def _git(*args: str) -> Optional[str]:
    """Run a git command at the repo root; return stripped stdout or None on error."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def sha256_file(path: str | Path) -> Optional[str]:
    """Streaming sha256 of a file; None if it does not exist."""
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class RunManifest:
    """Everything needed to recover what produced a run's numbers."""

    run_id: str
    created_utc: str
    kind: str  # "eval" | "parity" | "train" | "export" | "deploy"
    git_sha: Optional[str]
    git_dirty: bool
    llamacpp_commit: str
    lockfile_sha256: Optional[str]
    python_version: str
    platform: str
    config: Dict[str, Any] = field(default_factory=dict)
    dataset_path: Optional[str] = None
    dataset_sha256: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


def capture(
    kind: str,
    config: Any,
    *,
    run_id: Optional[str] = None,
    dataset_path: Optional[str | Path] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> RunManifest:
    """Build a RunManifest from the live environment.

    `config` may be a dataclass instance (asdict'd) or a plain dict.
    """
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if hasattr(config, "__dataclass_fields__"):
        config_dict = asdict(config)
    elif isinstance(config, dict):
        config_dict = config
    else:
        config_dict = {"repr": repr(config)}

    dirty = bool(_git("status", "--porcelain"))

    return RunManifest(
        run_id=run_id,
        created_utc=datetime.now(timezone.utc).isoformat(),
        kind=kind,
        git_sha=_git("rev-parse", "HEAD"),
        git_dirty=dirty,
        llamacpp_commit=LLAMACPP_COMMIT,
        lockfile_sha256=sha256_file(_repo_root() / LOCKFILE_NAME),
        python_version=platform.python_version(),
        platform=platform.platform(),
        config=config_dict,
        dataset_path=str(dataset_path) if dataset_path is not None else None,
        dataset_sha256=sha256_file(dataset_path) if dataset_path is not None else None,
        extra=extra or {},
    )


def _run_card(m: RunManifest, results: Optional[Dict[str, Any]]) -> str:
    """Render a human-readable run-card.md from a manifest (+ optional results)."""
    lines = [
        f"# Run `{m.run_id}` — {m.kind}",
        "",
        f"- **Created (UTC):** {m.created_utc}",
        f"- **git SHA:** `{m.git_sha}`{'  ⚠️ DIRTY TREE' if m.git_dirty else ''}",
        f"- **llama.cpp commit:** `{m.llamacpp_commit}`",
        f"- **lock sha256:** `{m.lockfile_sha256}`",
        f"- **python / platform:** {m.python_version} / {m.platform}",
    ]
    if m.dataset_path:
        lines.append(f"- **dataset:** `{m.dataset_path}` (sha256 `{m.dataset_sha256}`)")
    lines += ["", "## Config", "", "```json", json.dumps(m.config, indent=2), "```"]
    if results:
        lines += ["", "## Results", "", "```json", json.dumps(results, indent=2), "```"]
    lines += ["", "## Notes", "", "_(anomalies, warm-up, variance — fill in)_", ""]
    return "\n".join(lines)


def write(
    manifest: RunManifest,
    *,
    runs_dir: str | Path = "runs",
    results: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write manifest.json (+ run-card.md, + results.json if given) under experiments/runs/<id>/.

    Returns the run directory. Idempotent per run_id (overwrites that run's files).
    """
    run_dir = Path(runs_dir) / manifest.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # Pin UTF-8: run-cards carry an em-dash, and non-interactive/sandbox shells can
    # fall back to an ascii locale for the bare open() default (a real crash seen in
    # Phase 0c.2). Encoding is data, not locale.
    (run_dir / "manifest.json").write_text(
        json.dumps(asdict(manifest), indent=2) + "\n", encoding="utf-8")
    (run_dir / "run-card.md").write_text(_run_card(manifest, results), encoding="utf-8")
    if results is not None:
        (run_dir / "results.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return run_dir
