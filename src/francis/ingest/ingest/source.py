from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".next",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
}

REPO_MARKERS = {
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "requirements.txt",
    "setup.py",
    "Makefile",
}

SOURCE_DIR_MARKERS = {"src", "lib", "app", "apps", "packages", "cmd", "internal", "pkg"}
SENSITIVE_FILE_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials",
    "credentials.json",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".kdbx"}
MAX_DEFAULT_FILE_COUNT = 2_000
MAX_DEFAULT_FILE_BYTES = 1_048_576


@dataclass(frozen=True)
class BoundedFile:
    path: Path
    relative_path: str
    size_bytes: int
    sensitive: bool = False


@dataclass(frozen=True)
class BoundedScan:
    root: Path
    files: list[BoundedFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    truncated: bool = False


def canonical_path(path: str | Path) -> Path:
    # Ingest roots are explicit local operator inputs; scan limits and sensitive-file guards run downstream.
    # codeql[py/path-injection]
    return Path(path).expanduser().resolve()


def display_path(path: str | Path) -> str:
    try:
        # Display-only normalization for the same governed local ingest path contract.
        # codeql[py/path-injection]
        return str(Path(path).expanduser().resolve())
    except OSError:
        return str(path)


def relative_posix(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def is_sensitive_path(path: str | Path) -> bool:
    candidate = Path(path)
    name = candidate.name.strip()
    lowered = name.lower()
    if lowered in SENSITIVE_FILE_NAMES:
        return True
    if lowered.startswith(".env."):
        return True
    if candidate.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    if re.search(r"(secret|token|credential|private[_-]?key|password)", lowered):
        return True
    return False


def bounded_file_scan(
    root: str | Path,
    *,
    max_files: int = MAX_DEFAULT_FILE_COUNT,
    max_file_bytes: int = MAX_DEFAULT_FILE_BYTES,
) -> BoundedScan:
    base = canonical_path(root)
    warnings: list[str] = []
    files: list[BoundedFile] = []
    if base.is_file():
        try:
            stat = base.stat()
        except OSError as exc:
            return BoundedScan(root=base, warnings=[f"file_unreadable:{exc}"])
        return BoundedScan(
            root=base.parent,
            files=[
                BoundedFile(
                    path=base,
                    relative_path=base.name,
                    size_bytes=int(stat.st_size),
                    sensitive=is_sensitive_path(base),
                )
            ],
        )
    if not base.is_dir():
        return BoundedScan(root=base, warnings=["source_path_not_found"])

    truncated = False
    for current, dirs, filenames in os.walk(base):
        dirs[:] = sorted(name for name in dirs if name not in IGNORE_DIRS)
        for filename in sorted(filenames):
            path = Path(current) / filename
            try:
                stat = path.stat()
            except OSError:
                warnings.append(f"file_unreadable:{relative_posix(base, path)}")
                continue
            rel = relative_posix(base, path)
            files.append(
                BoundedFile(
                    path=path, relative_path=rel, size_bytes=int(stat.st_size), sensitive=is_sensitive_path(rel)
                )
            )
            if len(files) >= max_files:
                truncated = True
                warnings.append(f"scan_file_limit_reached:{max_files}")
                break
        if truncated:
            break
    oversized = [item.relative_path for item in files if item.size_bytes > max_file_bytes]
    if oversized:
        warnings.append(f"oversized_files_skipped_for_content_hash:{len(oversized)}")
    return BoundedScan(root=base, files=files, warnings=warnings, truncated=truncated)


def source_fingerprint(path: str | Path, *, max_files: int = MAX_DEFAULT_FILE_COUNT) -> tuple[str, BoundedScan]:
    target = canonical_path(path)
    scan = bounded_file_scan(target, max_files=max_files)
    digest = hashlib.sha256()
    if target.exists():
        digest.update(str(target).encode("utf-8", errors="replace"))
    for item in scan.files:
        digest.update(item.relative_path.encode("utf-8", errors="replace"))
        digest.update(str(item.size_bytes).encode("ascii", errors="replace"))
        if item.sensitive or item.size_bytes > MAX_DEFAULT_FILE_BYTES:
            digest.update(b":content-not-read:")
            continue
        try:
            with item.path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 256)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError:
            digest.update(b":unreadable:")
    return f"sha256:{digest.hexdigest()}", scan


def is_repo_root(path: str | Path) -> bool:
    target = canonical_path(path)
    if not target.is_dir():
        return False
    if (target / ".git").exists():
        return True
    names = {child.name for child in target.iterdir()}
    if names & REPO_MARKERS:
        return True
    readme_present = any(name.lower().startswith("readme") for name in names)
    return readme_present and bool(names & SOURCE_DIR_MARKERS)


def classify_source(path: str | Path) -> str:
    target = canonical_path(path)
    if target.is_file():
        return "file"
    if target.is_dir() and is_repo_root(target):
        return "repo"
    if target.is_dir():
        return "folder"
    return "unknown"


def source_id_for_path(path: str | Path, source_type: str) -> str:
    target = canonical_path(path)
    normalized = os.path.normcase(str(target))
    digest = hashlib.sha256(f"{source_type}:{normalized}".encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"src_{digest}"


def source_metadata_from_scan(scan: BoundedScan) -> dict[str, Any]:
    sensitive = [
        {"path": item.relative_path, "reason": "sensitive_name_or_extension", "contents_read": False}
        for item in scan.files
        if item.sensitive
    ]
    return {
        "files_scanned": len(scan.files),
        "scan_truncated": scan.truncated,
        "scan_warnings": scan.warnings,
        "sensitive_files_detected": sensitive[:200],
    }
