from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPORT_DIR = Path("data") / "logs" / "operations"
DEFAULT_ALLOWLIST = Path("data") / "target_tree_allowlist.txt"

# Entries that are known directories even if they have no allowlisted descendants.
KNOWN_DIR_ENTRIES: set[Path] = {
    Path(".venv"),
    Path("apps") / "chat_ui",
    Path("apps") / "chat_ui" / "node_modules",
    Path(".pytest_cache"),
    Path(".ruff_cache"),
}

# Tooling/state that must never be quarantined (even if not in the allowlist).
INTERNAL_ALWAYS_KEEP: set[Path] = {
    DEFAULT_ALLOWLIST,
    Path("tools") / "restore_tree.py",
    Path("scripts") / "restore-target-tree.ps1",
    Path("docs") / "RESTORE_TARGET_TREE.md",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore Francis working tree from an allowlist")
    parser.add_argument("--root", type=Path, default=Path("C:/Francis"), help="Repo root")
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--dry-run", action="store_true", default=True, help="Only report changes")
    parser.add_argument("--apply", action="store_true", help="Apply the restore actions")
    parser.add_argument("--yes", action="store_true", help="Confirm apply")
    parser.add_argument(
        "--quarantine-dir",
        type=Path,
        default=Path("data") / "quarantine" / f"restore_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    )
    return parser.parse_args()


def _normalize_relative(path: Path, root: Path) -> Path:
    if path.is_absolute():
        try:
            rel = path.relative_to(root)
        except ValueError:
            raise ValueError(f"Path {path} must live under {root}")
    else:
        rel = path
    parts = []
    for part in rel.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(f"Path {path} contains parent references")
        parts.append(part)
    return Path(*parts) if parts else Path(".")


def _load_allowlist(path: Path, root: Path) -> list[Path]:
    if not path.exists():
        raise FileNotFoundError(f"Allowlist missing at {path}; please paste the inventory lines there.")
    entries: list[Path] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(_normalize_relative(Path(stripped), root))
    return entries


def _safe_is_relative_to(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False


def _collect_actual_paths(root: Path) -> tuple[set[Path], set[Path]]:
    files: set[Path] = set()
    dirs: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        rel_dir = Path(dirpath).relative_to(root)
        if rel_dir != Path("."):
            dirs.add(rel_dir)
        # Avoid descending into protected/bulky directories.
        dirnames[:] = [d for d in dirnames if Path(rel_dir / d) not in KNOWN_DIR_ENTRIES and d != ".git"]
        if rel_dir in KNOWN_DIR_ENTRIES:
            continue
        for filename in filenames:
            rel_file = rel_dir / filename
            files.add(rel_file)
    return files, dirs


def _is_linklike(p: Path) -> bool:
    if p.is_symlink():
        return True
    is_junction = getattr(p, "is_junction", None)
    if callable(is_junction):
        try:
            return bool(is_junction())
        except Exception:
            return False
    return False


def _is_protected(rel: Path) -> bool:
    if not rel.parts:
        return True
    first = rel.parts[0]
    if first in (".git", "tools", "scripts", "docs"):
        return True
    if rel.parts[:3] == ("data", "logs", "operations"):
        return True
    if rel.parts[:2] == ("data", "quarantine"):
        return True
    if "__pycache__" in rel.parts:
        return True
    if rel.suffix == ".pyc":
        return True
    if rel in INTERNAL_ALWAYS_KEEP:
        return True
    if any(_safe_is_relative_to(internal, rel) for internal in INTERNAL_ALWAYS_KEEP):
        return True
    return False


def _is_dir_entry(entry: Path, allow_paths: set[Path]) -> bool:
    if entry in KNOWN_DIR_ENTRIES:
        return True
    return any(_safe_is_relative_to(other, entry) for other in allow_paths if other != entry)


def _build_allow_sets(entries: Iterable[Path]) -> tuple[set[Path], set[Path]]:
    allow_paths = set(entries)
    allow_dirs: set[Path] = {Path(".")}
    for entry in allow_paths:
        allow_dirs.add(entry)
        for i in range(1, len(entry.parts) + 1):
            ancestor = Path(*entry.parts[:i])
            allow_dirs.add(ancestor)
    return allow_paths, allow_dirs


def _has_descendant(entry: Path, allow_paths: set[Path]) -> bool:
    for other in allow_paths:
        if other == entry:
            continue
        if _safe_is_relative_to(other, entry):
            return True
    return False


def _distance(p: Path) -> int:
    return len(p.parts)


def _analyze_tree(root: Path, allow_entries: list[Path]) -> dict:
    allow_paths, allow_dirs = _build_allow_sets(allow_entries)
    actual_files, actual_dirs = _collect_actual_paths(root)

    extras_files = sorted([p for p in actual_files if p not in allow_paths and not _is_protected(p)])

    extra_dirs = []
    retained_dirs: list[Path] = []
    for directory in sorted(actual_dirs, key=_distance):
        if directory in allow_dirs:
            continue
        if _is_protected(directory):
            continue
        if any(_safe_is_relative_to(allow, directory) for allow in allow_paths):
            continue
        if any(_safe_is_relative_to(directory, kept) for kept in retained_dirs):
            continue
        retained_dirs.append(directory)
        extra_dirs.append(directory)

    missing = [entry for entry in allow_entries if not (root / entry).exists()]

    return {
        "allow_paths": allow_paths,
        "allow_dirs": allow_dirs,
        "extra_files": extras_files,
        "extra_dirs": extra_dirs,
        "missing": missing,
    }


def _summarize(report: dict) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "timestamp": timestamp,
        "missing_count": len(report["missing"]),
        "extra_files_count": len(report["extra_files"]),
        "extra_dirs_count": len(report["extra_dirs"]),
    }
    return summary


def _write_reports(root: Path, summary: dict, report: dict, apply_mode: bool, quarantine_dir: Path) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    text_path = REPORT_DIR / f"restore_tree_report_{summary['timestamp']}.txt"
    json_path = REPORT_DIR / f"restore_tree_report_{summary['timestamp']}.json"
    with text_path.open("w", encoding="utf-8") as handle:
        handle.write(f"Restore report at {summary['timestamp']}\n")
        handle.write(f"Missing entries: {summary['missing_count']}\n")
        handle.write(f"Extra files: {summary['extra_files_count']}\n")
        handle.write(f"Extra dirs: {summary['extra_dirs_count']}\n")
        handle.write(f"Apply mode: {apply_mode}\n")
        handle.write(f"Quarantine: {quarantine_dir}\n")
        if report["missing"]:
            handle.write("\nSample missing:\n")
            for entry in report["missing"][:10]:
                handle.write(f"- {entry}\n")
        if report["extra_files"]:
            handle.write("\nSample extra files:\n")
            for entry in report["extra_files"][:10]:
                handle.write(f"- {entry}\n")
        if report["extra_dirs"]:
            handle.write("\nSample extra dirs:\n")
            for entry in report["extra_dirs"][:10]:
                handle.write(f"- {entry}\n")
    payload = {
        **summary,
        "missing": [str(p) for p in report["missing"]],
        "extra_files": [str(p) for p in report["extra_files"]],
        "extra_dirs": [str(p) for p in report["extra_dirs"]],
        "apply_mode": apply_mode,
        "quarantine_dir": str(quarantine_dir),
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _git_restore(root: Path, rel_path: Path) -> bool:
    if not (root / ".git").exists():
        return False
    try:
        subprocess.run(
            ["git", "restore", "--source=HEAD", "--", str(rel_path)],
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        try:
            subprocess.run(
                ["git", "checkout", "--", str(rel_path)],
                cwd=root,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except subprocess.CalledProcessError:
            return False


def _install_venv_dependencies(root: Path) -> None:
    pip_executable = root / ".venv" / "Scripts" / "pip.exe"
    if not pip_executable.exists():
        return
    candidates = [
        root / "requirements" / "base.txt",
        root / "requirements.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            subprocess.run([str(pip_executable), "install", "-r", str(candidate)], check=True)
            return
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        subprocess.run([str(pip_executable), "install", "-e", "."], check=True)


def _ensure_quarantine_dir(root: Path, quarantine: Path) -> Path:
    if not quarantine.is_absolute():
        quarantine = root / quarantine
    allowed_parent = root / "data" / "quarantine"
    try:
        quarantine.relative_to(allowed_parent)
    except ValueError:
        raise ValueError("Quarantine directory must reside inside data\\quarantine")
    quarantine.mkdir(parents=True, exist_ok=True)
    return quarantine


def _unique_dest(dest: Path) -> Path:
    candidate = dest
    suffix = 1
    while candidate.exists():
        candidate = dest.with_name(f"{dest.name}__dup{suffix}")
        suffix += 1
    return candidate


def _apply_actions(root: Path, report: dict, quarantine_dir: Path) -> None:
    for extra in report["extra_files"]:
        src = root / extra
        if not src.exists():
            continue
        dest = quarantine_dir / extra
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(_unique_dest(dest)))
    for extra in report["extra_dirs"]:
        src = root / extra
        if not src.exists():
            continue
        dest = quarantine_dir / extra
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(_unique_dest(dest)))
    for entry in report["missing"]:
        abs_path = root / entry
        if _is_dir_entry(entry, report["allow_paths"]):
            if abs_path.exists() and abs_path.is_file():
                abs_path.unlink()
            abs_path.mkdir(parents=True, exist_ok=True)
            continue
        if not abs_path.exists():
            restored = _git_restore(root, entry)
            if not restored:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_text("", encoding="utf-8")
        if entry == Path(".venv"):
            if abs_path.exists() and abs_path.is_file():
                abs_path.unlink()
            abs_path.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "venv", str(abs_path)], check=True)
            _install_venv_dependencies(root)
        if entry == Path("apps") / "chat_ui" / "node_modules":
            chat_ui_dir = root / "apps" / "chat_ui"
            if (chat_ui_dir / "package-lock.json").exists():
                subprocess.run(["npm", "ci"], cwd=chat_ui_dir, check=True)


def main() -> int:
    args = _parse_args()
    root = args.root.resolve()
    try:
        allow_entries = _load_allowlist(args.allowlist, root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not allow_entries:
        print("Allowlist is empty; please populate target_tree_allowlist.txt", file=sys.stderr)
        return 1
    if not args.apply and not args.dry_run:
        args.dry_run = True
    if args.apply and not args.yes:
        print("Refusing to run --apply without --yes", file=sys.stderr)
        return 2
    apply_mode = bool(args.apply)
    report = _analyze_tree(root, allow_entries)
    summary = _summarize(report)
    quarantine_dir = args.quarantine_dir
    if apply_mode:
        quarantine_dir = _ensure_quarantine_dir(root, quarantine_dir)
    _write_reports(root, summary, report, apply_mode, quarantine_dir)
    print(
        f"Dry-run summary: missing={summary['missing_count']} extras={summary['extra_files_count']} dirs={summary['extra_dirs_count']}"
    )
    if apply_mode:
        _apply_actions(root, report, quarantine_dir)
        print(f"Apply actions moved extras to {quarantine_dir}")
    else:
        print("Run with --apply --yes to quarantine extras and restore missing items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
