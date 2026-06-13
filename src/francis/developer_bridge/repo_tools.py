from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

from francis.kernel.paths import data_dir, repo_root

_ALLOWED_RECEIPT_FILENAMES = frozenset(
    {
        "denied.json",
        "error.json",
        "mismatch.json",
        "pending.json",
        "plan.json",
        "request.json",
        "result.json",
        "stderr.txt",
        "stdout.txt",
    }
)
_EXCLUDED_SEARCH_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "cache",
        "data",
        "dist",
        "node_modules",
    }
)
_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_SENSITIVE_SUFFIXES = frozenset({".key", ".pem", ".pfx", ".p12"})
_SENSITIVE_FILENAMES = frozenset(
    {
        ".env",
        ".npmrc",
        ".pypirc",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "known_hosts",
    }
)
_DEFAULT_MAX_BYTES = 256_000
_MAX_SEARCH_RESULTS = 100
_MAX_SEARCH_FILE_BYTES = 1_000_000


class DeveloperBridgeError(ValueError):
    """Raised when a read-only bridge request is denied or invalid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, object]:
        return {"ok": False, "error": self.code, "message": self.message}


def repo_status() -> dict[str, object]:
    """Return a read-only Git status snapshot for the Francis repo."""

    root = _root()
    branch = _git_text(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    commit = _git_text(root, ["rev-parse", "HEAD"])
    status_lines = _git_lines(root, ["status", "--short"])
    return {
        "kind": "developer_bridge.repo_status",
        "ok": True,
        "mode": "read_only",
        "repo_root": str(root),
        "branch": branch or "unknown",
        "commit": commit or "unknown",
        "dirty": bool(status_lines),
        "status_lines": status_lines,
        "guardrails": _guardrails(),
    }


def read_repo_file(path: str, max_bytes: int = _DEFAULT_MAX_BYTES) -> dict[str, object]:
    """Read a bounded, non-sensitive text file inside the repo root."""

    root = _root()
    max_bytes = _bounded_int(max_bytes, minimum=1, maximum=_DEFAULT_MAX_BYTES)
    target = _safe_repo_path(root, path)
    if not target.is_file():
        raise DeveloperBridgeError("file_not_found", "requested repo path is not a file")

    size = target.stat().st_size
    read_limit = min(size, max_bytes)
    data = target.read_bytes()[:read_limit]
    truncated = size > max_bytes
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DeveloperBridgeError("binary_file_denied", "only UTF-8 text files may be read") from exc
    if "\x00" in content:
        raise DeveloperBridgeError("binary_file_denied", "binary-looking files may not be read")

    return {
        "kind": "developer_bridge.repo_file",
        "ok": True,
        "path": _display_path(root, target),
        "size_bytes": size,
        "sha256": hashlib.sha256(data).hexdigest() if not truncated else None,
        "truncated": truncated,
        "content": content,
    }


def search_repo(query: str, max_results: int = 20) -> dict[str, object]:
    """Search bounded non-sensitive text files under the repo root."""

    needle = (query or "").strip()
    if not needle:
        raise DeveloperBridgeError("empty_query", "search query is required")
    root = _root()
    limit = _bounded_int(max_results, minimum=1, maximum=_MAX_SEARCH_RESULTS)
    lowered = needle.lower()
    results: list[dict[str, object]] = []
    skipped_sensitive = 0
    skipped_binary_or_large = 0

    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _EXCLUDED_SEARCH_DIRS]
        current_path = Path(current)
        for filename in filenames:
            candidate = current_path / filename
            try:
                rel = _display_path(root, candidate)
                if _is_sensitive_relpath(rel):
                    skipped_sensitive += 1
                    continue
                if candidate.stat().st_size > _MAX_SEARCH_FILE_BYTES:
                    skipped_binary_or_large += 1
                    continue
                for line_no, line in _iter_text_lines(candidate):
                    if lowered in line.lower():
                        results.append(
                            {
                                "path": rel,
                                "line": line_no,
                                "preview": line.strip()[:240],
                            }
                        )
                        break
            except (OSError, UnicodeDecodeError):
                skipped_binary_or_large += 1
                continue
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break

    return {
        "kind": "developer_bridge.search_repo",
        "ok": True,
        "query": needle,
        "max_results": limit,
        "results": results,
        "truncated": len(results) >= limit,
        "skipped_sensitive": skipped_sensitive,
        "skipped_binary_or_large": skipped_binary_or_large,
    }


def git_diff_summary() -> dict[str, object]:
    """Return Git status and diff metadata without returning patch text."""

    root = _root()
    return {
        "kind": "developer_bridge.git_diff_summary",
        "ok": True,
        "mode": "read_only_no_patch_text",
        "status_short": _git_lines(root, ["status", "--short"]),
        "unstaged_name_status": _git_lines(root, ["diff", "--name-status"]),
        "unstaged_stat": _git_lines(root, ["diff", "--stat"]),
        "staged_name_status": _git_lines(root, ["diff", "--cached", "--name-status"]),
        "staged_stat": _git_lines(root, ["diff", "--cached", "--stat"]),
        "guardrails": _guardrails(),
    }


def read_completion_ledger(max_bytes: int = _DEFAULT_MAX_BYTES) -> dict[str, object]:
    """Read the completion ledger through the same safe file path."""

    return read_repo_file("docs/operations/COMPLETION_LEDGER.md", max_bytes=max_bytes)


def read_supervised_exec_receipt(run_id: str, filename: str = "result.json", max_bytes: int = _DEFAULT_MAX_BYTES) -> dict[str, object]:
    """Read a bounded supervised-exec display artifact by run id and allowed filename."""

    safe_run_id = (run_id or "").strip()
    if not _SAFE_RUN_ID_RE.fullmatch(safe_run_id):
        raise DeveloperBridgeError("run_id_denied", "run_id must be a bounded artifact identifier")
    safe_filename = (filename or "").strip()
    if safe_filename not in _ALLOWED_RECEIPT_FILENAMES or Path(safe_filename).name != safe_filename:
        raise DeveloperBridgeError("filename_denied", "receipt filename is not in the allowed artifact filename set")

    root = _artifact_root()
    target = _real_path(root / safe_run_id / safe_filename)
    if not _path_is_under(root, target):
        raise DeveloperBridgeError("artifact_path_denied", "receipt path escaped the supervised_exec artifact root")
    if not target.is_file():
        raise DeveloperBridgeError("receipt_not_found", "requested supervised_exec receipt file was not found")

    max_bytes = _bounded_int(max_bytes, minimum=1, maximum=_DEFAULT_MAX_BYTES)
    size = target.stat().st_size
    data = target.read_bytes()[: min(size, max_bytes)]
    truncated = size > max_bytes
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DeveloperBridgeError("binary_file_denied", "receipt file is not UTF-8 text") from exc

    return {
        "kind": "developer_bridge.supervised_exec_receipt",
        "ok": True,
        "run_id": safe_run_id,
        "filename": safe_filename,
        "artifact_root": str(root),
        "size_bytes": size,
        "sha256": hashlib.sha256(data).hexdigest() if not truncated else None,
        "truncated": truncated,
        "content": content,
    }


def _root() -> Path:
    return _real_path(repo_root())


def _artifact_root() -> Path:
    return _real_path(data_dir() / "artifacts" / "supervised_exec")


def _guardrails() -> list[str]:
    return [
        "read_only",
        "repo_root_bounded",
        "sensitive_file_denial",
        "no_arbitrary_shell",
        "no_commits",
        "no_pushes",
    ]


def _git_text(root: Path, args: list[str]) -> str | None:
    lines = _git_lines(root, args)
    return lines[0] if lines else None


def _git_lines(root: Path, args: list[str]) -> list[str]:
    if not args:
        return []
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _safe_repo_path(root: Path, path: str) -> Path:
    rel = _normalize_repo_relative_path(path)
    if _is_sensitive_relpath(rel):
        raise DeveloperBridgeError("sensitive_file_denied", "requested path is denied by developer bridge sensitivity rules")
    candidate = _real_path(root / Path(rel))
    if not _path_is_under(root, candidate):
        raise DeveloperBridgeError("path_outside_repo_denied", "requested path escaped the repo root")
    return candidate


def _normalize_repo_relative_path(path: str) -> str:
    raw = (path or "").strip().replace("\\", "/")
    if not raw:
        raise DeveloperBridgeError("empty_path", "repo-relative path is required")
    if "\x00" in raw:
        raise DeveloperBridgeError("path_denied", "path may not contain null bytes")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:/", raw):
        raise DeveloperBridgeError("absolute_path_denied", "only repo-relative paths are allowed")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise DeveloperBridgeError("path_traversal_denied", "path traversal is not allowed")
    return pure.as_posix()


def _display_path(root: Path, candidate: Path) -> str:
    real_candidate = _real_path(candidate)
    if not _path_is_under(root, real_candidate):
        raise DeveloperBridgeError("path_outside_repo_denied", "path escaped the repo root")
    return real_candidate.relative_to(root).as_posix()


def _is_sensitive_relpath(relpath: str) -> bool:
    rel = relpath.replace("\\", "/")
    path = PurePosixPath(rel)
    lowered_parts = [part.lower() for part in path.parts]
    lowered_name = lowered_parts[-1] if lowered_parts else ""
    suffix = PurePosixPath(lowered_name).suffix
    return (
        ".ssh" in lowered_parts
        or lowered_name in _SENSITIVE_FILENAMES
        or lowered_name.startswith(".env.")
        or suffix in _SENSITIVE_SUFFIXES
    )


def _iter_text_lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    if "\x00" in text:
        raise UnicodeDecodeError("utf-8", b"\x00", 0, 1, "binary-looking file")
    return list(enumerate(text.splitlines(), start=1))


def _bounded_int(value: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(parsed, maximum))


def _real_path(value: str | Path) -> Path:
    return Path(os.path.realpath(os.fspath(value)))


def _path_is_under(root: Path, candidate: Path) -> bool:
    try:
        root_text = os.path.normcase(os.path.realpath(os.fspath(root)))
        candidate_text = os.path.normcase(os.path.realpath(os.fspath(candidate)))
        return os.path.commonpath([root_text, candidate_text]) == root_text
    except (OSError, ValueError):
        return False
