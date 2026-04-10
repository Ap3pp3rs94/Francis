"""Recover allowlisted paths from quarantine."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _normalize_entry(path: Path, root: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    try:
        return candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Allowlist entry {path!r} is outside {root}") from exc


def _load_allowlist(path: Path, root: Path) -> list[Path]:
    if not path.exists():
        raise FileNotFoundError(f"Allowlist missing at {path}; please paste the inventory lines there.")
    entries: list[Path] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(_normalize_entry(Path(stripped), root))
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover allowlisted paths from quarantine.")
    parser.add_argument("--quarantine", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path("data") / "target_tree_allowlist.txt",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        allowed = _load_allowlist(args.allowlist, root)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    quarantine = args.quarantine if args.quarantine.is_absolute() else args.quarantine.resolve()
    restored = 0
    still_missing = []
    for entry in allowed:
        target = root / entry
        if target.exists():
            continue
        source = quarantine / entry
        if not source.exists():
            still_missing.append(entry)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.move(str(source), str(target))
        else:
            shutil.copy2(str(source), str(target))
        restored += 1
    remaining = [entry for entry in allowed if not (root / entry).exists()]
    print(f"Restored {restored} entries from {quarantine}")
    print(f"Still missing: {len(remaining)}")
    if remaining:
        for entry in remaining[:10]:
            print(f" - {entry}")
    return 0 if not remaining else 2


if __name__ == "__main__":
    sys.exit(main())
