"""Per-module run manifests: which geo codes a process attempted, completed, and failed.

A module writes `_manifest.json` beside its CSV outputs after a run. Merge reads
these back and warns loudly when a module left regions unfinished, so a partial
run (e.g. 30 of 200 geo codes failed) is visible instead of silently
consolidating into an under-reporting merged table. The manifest also records
the config hash and timings, giving `--no-overwrite` resumes an auditable record
of what actually completed.
"""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path

from loguru import logger


def config_hash(cfg) -> str:
    """Short stable hash of the resolved config, tying a manifest to the run that produced it."""
    try:
        payload = asdict(cfg) if is_dataclass(cfg) else cfg
        blob = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        blob = repr(cfg)
    return sha1(blob.encode()).hexdigest()[:10]


def write_run_manifest(
    output_dir: Path,
    process: str,
    attempted,
    succeeded,
    failed,
    *,
    cfg=None,
    duration_s: float | None = None,
    extra: dict | None = None,
) -> Path:
    """Write `<output_dir>/_manifest.json` and log a prominent error if any region failed.

    Returns the manifest path. Codes are stringified so numeric census codes
    round-trip through JSON unchanged.
    """
    attempted = [str(c) for c in attempted]
    succeeded = [str(c) for c in succeeded]
    failed = [str(c) for c in failed]
    manifest = {
        "process": process,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config_hash": config_hash(cfg) if cfg is not None else None,
        "n_attempted": len(attempted),
        "n_succeeded": len(succeeded),
        "n_failed": len(failed),
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
    }
    if duration_s is not None:
        manifest["duration_s"] = round(duration_s, 2)
    if extra:
        manifest.update(extra)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "_manifest.json"
    path.write_text(json.dumps(manifest, indent=2))

    if failed:
        logger.error(f"{process}: {len(failed)}/{len(attempted)} regions FAILED: {failed} (see {path})")
    else:
        logger.info(f"{process}: {len(succeeded)}/{len(attempted)} regions succeeded (manifest: {path.name})")
    return path


def read_run_manifest(output_dir: Path) -> dict | None:
    """The `_manifest.json` in output_dir, or None when it is absent or unreadable."""
    path = Path(output_dir) / "_manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def warn_on_incomplete_runs(base_dir: Path, module_dirs: dict[str, Path]) -> list[str]:
    """Warn for each module whose manifest records failed regions. Returns modules with failures.

    `module_dirs` maps a display name to the directory holding that module's
    outputs (and manifest). Modules with no manifest (run before manifests
    existed, or never run) are skipped silently — the merge already reports
    missing outputs separately.
    """
    incomplete = []
    for name, directory in module_dirs.items():
        manifest = read_run_manifest(directory)
        if manifest and manifest.get("n_failed"):
            incomplete.append(name)
            logger.warning(
                f"{name}: {manifest['n_failed']} of {manifest['n_attempted']} regions failed in the last run "
                f"({manifest.get('failed')}) — the merged table will under-report them. "
                "Re-run that module before trusting the output."
            )
    return incomplete
