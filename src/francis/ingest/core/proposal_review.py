"""Deterministic governance evaluators + records for the Forge synthesis corridor.

This module is the bounded, non-applying review layer that sits *after* the
local builder produced a proposal artifact (`builder.local.ollama.run`) and
*before* anything could ever be applied. It contains only deterministic, offline
logic: a unified-diff parser, a scope evaluator (allowed/forbidden/file-count), a
bounded third-party copy-overlap detector against the ingested source tree, a
secret/network/destructive token scan, and the dataclass records for each brick
in the corridor.

Francis posture (ingest is a *capability* of Francis, never Francis authority):

* Nothing here applies a patch, writes to the repo, executes a command, consumes
  an approval, validates a candidate, or promotes a capability.
* A verdict is only ever computed over the *full* proposal text whose sha256
  matches the digest recorded on the builder run. Truncated/absent text yields an
  honest ``indeterminate`` verdict -- never a clean signal over partial content
  (no fake progress signals).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Bounds for the copy-overlap scan so review stays cheap and offline.
_COPY_SHINGLE_TOKENS = 8
_COPY_MAX_SOURCE_FILES = 400
_COPY_MAX_FILE_BYTES = 256_000
_COPY_OVERLAP_FLAG_RATIO = 0.30
_COPY_SCANNABLE_SUFFIXES = (
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cs",
    ".sh",
    ".toml",
    ".cfg",
    ".ini",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
)

_SECRET_TOKENS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "private_key",
    "client_secret",
    "access_token",
    "bearer ",
    "aws_secret",
    "-----begin",
)
_NETWORK_TOKENS = (
    "http://",
    "https://",
    "socket.connect",
    "urllib.request",
    "requests.get",
    "requests.post",
    "httpx.",
    "curl ",
    "wget ",
    "subprocess",
)
_DESTRUCTIVE_TOKENS = (
    "rm -rf",
    "shutil.rmtree",
    "os.remove",
    "os.unlink",
    "drop table",
    "truncate ",
    "git push --force",
    "format(",
    ":(){",
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [text for item in value if (text := _safe_str(item).strip())]


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8", errors="replace"
    )
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def text_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(_safe_str(value).encode("utf-8", errors="replace")).hexdigest()


def _normalize_path(value: str) -> str:
    return _safe_str(value).replace("\\", "/").strip().lstrip("./")


def _matches_any(path: str, patterns: list[str]) -> bool:
    norm = _normalize_path(path).lower()
    for pattern in patterns:
        pat = _normalize_path(pattern).lower()
        if not pat:
            continue
        if fnmatch.fnmatchcase(norm, pat):
            return True
        # Directory-prefix globs like "src/francis/ingest/**".
        if pat.endswith("/**") and (norm == pat[:-3] or norm.startswith(pat[:-2])):
            return True
        if pat.endswith("**") and norm.startswith(pat[:-2]):
            return True
    return False


# --------------------------------------------------------------------------- #
# Diff parsing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ParsedDiff:
    is_diff: bool
    well_formed: bool
    files: list[str] = field(default_factory=list)
    added_lines: list[str] = field(default_factory=list)
    removed_line_count: int = 0
    hunk_count: int = 0
    malformations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Do not persist raw added source lines (could carry third-party code or
        # secrets); only counts + a digest are kept in records.
        data["added_line_count"] = len(self.added_lines)
        data.pop("added_lines", None)
        return data


_DIFF_GIT_RE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)\s*$")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")


def _diff_file_marker_path(line: str, marker: str) -> str | None:
    prefix = f"{marker} "
    if not line.startswith(prefix):
        return None
    value = line[len(prefix) :].strip()
    if "\t" in value:
        value = value.split("\t", 1)[0].strip()
    if value.startswith(("a/", "b/")):
        value = value[2:]
    return value.replace("\\", "/").strip()


def parse_unified_diff(text: str) -> ParsedDiff:
    raw = _safe_str(text)
    lower = raw.lower()
    is_diff = "diff --git " in lower or "\n--- " in ("\n" + lower) or lower.lstrip().startswith("--- ")
    if not is_diff:
        return ParsedDiff(is_diff=False, well_formed=False)

    files: list[str] = []
    added: list[str] = []
    removed = 0
    hunks = 0
    malformations: list[str] = []
    in_hunk = False
    saw_file_header = False

    for line in raw.splitlines():
        git_match = _DIFF_GIT_RE.match(line)
        if git_match:
            files.append(_normalize_path(git_match.group("b")))
            in_hunk = False
            saw_file_header = True
            continue
        plus_file = None if line.startswith("+++ +") else _diff_file_marker_path(line, "+++")
        if plus_file is not None:
            path = _normalize_path(plus_file)
            if path and path != "dev/null":
                files.append(path)
            saw_file_header = True
            in_hunk = False
            continue
        if _diff_file_marker_path(line, "---") is not None:
            saw_file_header = True
            in_hunk = False
            continue
        if _HUNK_RE.match(line):
            hunks += 1
            in_hunk = True
            continue
        if in_hunk:
            if line.startswith("+"):
                added.append(line[1:])
            elif line.startswith("-"):
                removed += 1

    if not files:
        malformations.append("diff_declares_no_files")
    if hunks == 0:
        malformations.append("diff_has_no_hunks")
    if not saw_file_header:
        malformations.append("diff_missing_file_headers")

    return ParsedDiff(
        is_diff=True,
        well_formed=not malformations,
        files=sorted(dict.fromkeys(files)),
        added_lines=added,
        removed_line_count=removed,
        hunk_count=hunks,
        malformations=sorted(set(malformations)),
    )


# --------------------------------------------------------------------------- #
# Scope / secret / copy evaluators
# --------------------------------------------------------------------------- #
def scope_findings(
    parsed: ParsedDiff,
    *,
    allowed_files: list[str],
    forbidden_files: list[str],
    max_files_changed: int,
) -> tuple[list[str], list[str]]:
    """Return (blockers, touched_outside_scope) for the parsed proposal."""

    blockers: list[str] = []
    outside: list[str] = []
    if not parsed.files:
        return blockers, outside
    for path in parsed.files:
        if _matches_any(path, forbidden_files):
            blockers.append(f"touches_forbidden_file:{path}")
            outside.append(path)
            continue
        if allowed_files and not _matches_any(path, allowed_files):
            blockers.append(f"touches_file_outside_allowed_scope:{path}")
            outside.append(path)
    if max_files_changed >= 0 and len(parsed.files) > max_files_changed:
        blockers.append(f"exceeds_max_files_changed:{len(parsed.files)}>{max_files_changed}")
    return sorted(set(blockers)), sorted(set(outside))


def token_scan_findings(added_lines: list[str]) -> list[str]:
    findings: list[str] = []
    blob = "\n".join(added_lines).lower()
    if any(tok in blob for tok in _SECRET_TOKENS):
        findings.append("proposal_contains_secret_like_token")
    if any(tok in blob for tok in _NETWORK_TOKENS):
        findings.append("proposal_contains_network_token")
    if any(tok in blob for tok in _DESTRUCTIVE_TOKENS):
        findings.append("proposal_contains_destructive_token")
    return findings


def _shingles(tokens: list[str], width: int) -> set[str]:
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def copy_overlap_findings(
    added_lines: list[str],
    *,
    source_root: str,
) -> tuple[list[str], dict[str, Any]]:
    """Bounded third-party copy detection.

    Computes shingle overlap between the proposal's added lines and the ingested
    source tree. High overlap is evidence the proposal may be copying third-party
    implementation code rather than conceptually rebuilding it. Read-only and
    bounded; never executes source.
    """

    added_tokens = _tokenize("\n".join(added_lines))
    added_shingles = _shingles(added_tokens, _COPY_SHINGLE_TOKENS)
    metrics: dict[str, Any] = {
        "added_shingles": len(added_shingles),
        "source_files_scanned": 0,
        "max_overlap_ratio": 0.0,
        "max_overlap_file": "",
        "shingle_width": _COPY_SHINGLE_TOKENS,
    }
    if not added_shingles:
        return [], metrics

    root = Path(source_root)
    if not root.exists() or not root.is_dir():
        metrics["source_root_available"] = False
        return [], metrics
    metrics["source_root_available"] = True

    source_shingles: set[str] = set()
    scanned = 0
    max_ratio = 0.0
    max_file = ""
    for path in sorted(root.rglob("*")):
        if scanned >= _COPY_MAX_SOURCE_FILES:
            break
        if not path.is_file() or path.suffix.lower() not in _COPY_SCANNABLE_SUFFIXES:
            continue
        if ".git" in path.parts:
            continue
        try:
            if path.stat().st_size > _COPY_MAX_FILE_BYTES:
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned += 1
        file_shingles = _shingles(_tokenize(content), _COPY_SHINGLE_TOKENS)
        if not file_shingles:
            continue
        source_shingles |= file_shingles
        overlap = added_shingles & file_shingles
        ratio = len(overlap) / max(1, len(added_shingles))
        if ratio > max_ratio:
            max_ratio = ratio
            max_file = _normalize_path(str(path.relative_to(root)))

    metrics["source_files_scanned"] = scanned
    metrics["max_overlap_ratio"] = round(max_ratio, 4)
    metrics["max_overlap_file"] = max_file
    findings: list[str] = []
    if max_ratio >= _COPY_OVERLAP_FLAG_RATIO:
        findings.append(f"possible_third_party_copy:{max_file}:{metrics['max_overlap_ratio']}")
    return findings, metrics


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BuilderProposalReview:
    id: str
    builder_run_id: str
    spec_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    actor: str
    created_at: str
    verdict: str  # "clean" | "blocked" | "indeterminate"
    status: str  # "reviewed" | "blocked" | "indeterminate"
    proposal_kind: str  # "patch" | "plan" | "empty"
    digest_verified: bool
    recorded_response_digest: str
    supplied_text_digest: str
    diff: dict[str, Any]
    touched_files: list[str]
    files_outside_scope: list[str]
    blockers: list[str]
    findings: list[str]
    copy_overlap: dict[str, Any]
    allowed_files: list[str]
    forbidden_files: list[str]
    max_files_changed: int
    # Truth booleans: a review is evidence only.
    patch_applied: bool = False
    wrote_to_repo: bool = False
    executed: bool = False
    network_accessed: bool = False
    approval_consumed: bool = False
    candidate_validated: bool = False
    capability_promoted: bool = False
    execution_authority: bool = False
    store_file_contents: bool = False
    receipts: list[str] = field(default_factory=list)
    artifact_path: str = ""
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "BuilderProposalReview | None":
        if not isinstance(value, dict):
            return None
        rid = _safe_str(value.get("id")).strip()
        if not rid:
            return None
        return cls(
            id=rid,
            builder_run_id=_safe_str(value.get("builder_run_id")).strip(),
            spec_id=_safe_str(value.get("spec_id")).strip(),
            source_id=_safe_str(value.get("source_id")).strip(),
            candidate_id=_safe_str(value.get("candidate_id")).strip(),
            candidate_name=_safe_str(value.get("candidate_name")).strip(),
            actor=_safe_str(value.get("actor")).strip() or "francis/system",
            created_at=_safe_str(value.get("created_at")).strip(),
            verdict=_safe_str(value.get("verdict")).strip() or "indeterminate",
            status=_safe_str(value.get("status")).strip() or "indeterminate",
            proposal_kind=_safe_str(value.get("proposal_kind")).strip() or "empty",
            digest_verified=bool(value.get("digest_verified", False)),
            recorded_response_digest=_safe_str(value.get("recorded_response_digest")).strip(),
            supplied_text_digest=_safe_str(value.get("supplied_text_digest")).strip(),
            diff=_dict_value(value.get("diff")),
            touched_files=_string_list(value.get("touched_files")),
            files_outside_scope=_string_list(value.get("files_outside_scope")),
            blockers=_string_list(value.get("blockers")),
            findings=_string_list(value.get("findings")),
            copy_overlap=_dict_value(value.get("copy_overlap")),
            allowed_files=_string_list(value.get("allowed_files")),
            forbidden_files=_string_list(value.get("forbidden_files")),
            max_files_changed=int(value.get("max_files_changed") or 0),
            receipts=_string_list(value.get("receipts")),
            artifact_path=_safe_str(value.get("artifact_path")).strip(),
            schema_version=int(value.get("schema_version") or 1),
        )


def review_id(builder_run_id: str) -> str:
    digest = hashlib.sha256(_safe_str(builder_run_id).encode("utf-8")).hexdigest()[:12]
    return f"proposal_review_{digest}"


# --------------------------------------------------------------------------- #
# Conservative unified-diff applier (scratch-only; never forces a fuzzy match)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FileApplyResult:
    path: str
    status: str  # "applied" | "rejected" | "skipped"
    is_new_file: bool
    before_digest: str
    after_digest: str
    reject_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _split_file_diffs(diff_text: str) -> list[tuple[str, bool, list[str]]]:
    """Split a unified diff into (path, is_new_file, body_lines) per file."""

    files: list[tuple[str, bool, list[str]]] = []
    current_path = ""
    is_new = False
    body: list[str] = []
    saw_minus_devnull = False

    def flush() -> None:
        if current_path:
            files.append((current_path, is_new, list(body)))

    for line in _safe_str(diff_text).splitlines():
        if line.startswith("diff --git "):
            flush()
            current_path, is_new, body, saw_minus_devnull = "", False, [], False
            continue
        minus_path = _diff_file_marker_path(line, "---")
        if minus_path is not None:
            saw_minus_devnull = minus_path in ("dev/null", "/dev/null")
            continue
        plus_path = None if line.startswith("+++ +") else _diff_file_marker_path(line, "+++")
        if plus_path is not None:
            current_path = plus_path
            is_new = saw_minus_devnull
            body = []
            continue
        if _HUNK_RE.match(line) or body or line.startswith(("+", "-", " ", "@@", "\\")):
            if current_path:
                body.append(line)
    flush()
    return files


_HUNK_HEADER_RE = re.compile(r"^@@ -(?P<os>\d+)(?:,(?P<oc>\d+))? \+(?P<ns>\d+)(?:,(?P<nc>\d+))? @@")


def _scratch_relative_parts(path: str) -> tuple[str, ...] | None:
    clean = _safe_str(path).replace("\\", "/").strip()
    if not clean or clean in ("dev/null", "/dev/null"):
        return None
    if clean.startswith("/") or re.match(r"^[A-Za-z]:", clean):
        return None
    parts = tuple(part for part in clean.split("/") if part)
    if not parts or any(part in (".", "..") for part in parts):
        return None
    return parts


def _resolve_scratch_target(root: Path, relative_path: str) -> Path | None:
    parts = _scratch_relative_parts(relative_path)
    if parts is None:
        return None
    try:
        resolved_root = root.resolve()
        target = resolved_root.joinpath(*parts).resolve()
        target.relative_to(resolved_root)
    except Exception:
        return None
    return target


def _apply_file_body(original: str, body: list[str], *, is_new_file: bool) -> tuple[str | None, str]:
    """Apply one file's hunk body. Returns (new_text, reject_reason).

    Conservative: any context/removed-line mismatch rejects the whole file. No
    fuzzy matching, no offset search beyond the declared hunk start.
    """

    original_lines = original.splitlines() if original else []
    if is_new_file or not original:
        added = [ln[1:] for ln in body if ln.startswith("+")]
        if not added:
            return None, "new_file_has_no_added_lines"
        return "\n".join(added) + "\n", ""

    out: list[str] = []
    cursor = 0  # index into original_lines already consumed
    i = 0
    while i < len(body):
        header = _HUNK_HEADER_RE.match(body[i])
        if header is None:
            i += 1
            continue
        old_start = int(header.group("os"))
        target = max(0, old_start - 1)
        if target < cursor or target > len(original_lines):
            return None, "hunk_start_out_of_order"
        out.extend(original_lines[cursor:target])
        cursor = target
        i += 1
        while i < len(body) and not _HUNK_HEADER_RE.match(body[i]):
            seg = body[i]
            if seg.startswith("\\"):  # "\ No newline at end of file"
                i += 1
                continue
            tag, text = (seg[0], seg[1:]) if seg else (" ", "")
            if tag == " ":
                if cursor >= len(original_lines) or original_lines[cursor] != text:
                    return None, "context_mismatch"
                out.append(original_lines[cursor])
                cursor += 1
            elif tag == "-":
                if cursor >= len(original_lines) or original_lines[cursor] != text:
                    return None, "removed_line_mismatch"
                cursor += 1
            elif tag == "+":
                out.append(text)
            else:
                return None, "unexpected_diff_line"
            i += 1
    out.extend(original_lines[cursor:])
    return "\n".join(out) + "\n", ""


def apply_unified_diff_to_tree(
    diff_text: str,
    tree_root: str,
    *,
    forbidden_files: list[str] | None = None,
) -> list[FileApplyResult]:
    """Apply a unified diff to files under ``tree_root`` ONLY (a scratch copy).

    Enforces the forbidden-path write guard: any file matching ``forbidden_files``
    is rejected without writing. Returns a per-file report. Callers must ensure
    ``tree_root`` is a Francis-owned scratch tree, never the real source repo.
    """

    root = Path(tree_root)
    forbidden = forbidden_files or []
    results: list[FileApplyResult] = []
    for path, is_new, body in _split_file_diffs(diff_text):
        if not path or path in ("dev/null", "/dev/null"):
            continue
        before = ""
        if _matches_any(path, forbidden):
            results.append(FileApplyResult(path, "rejected", is_new, "", "", "forbidden_path_write_guard"))
            continue
        target = _resolve_scratch_target(root, path)
        if target is None:
            results.append(FileApplyResult(path, "rejected", is_new, "", "", "path_escapes_scratch_tree"))
            continue
        if target.exists() and target.is_file():
            try:
                before = target.read_text(encoding="utf-8", errors="replace")
            except Exception:
                before = ""
        before_digest = text_digest(before) if before else ""
        new_text, reason = _apply_file_body(before, body, is_new_file=is_new)
        if new_text is None:
            results.append(FileApplyResult(path, "rejected", is_new, before_digest, "", reason))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_text, encoding="utf-8")
        results.append(FileApplyResult(path, "applied", is_new, before_digest, text_digest(new_text), ""))
    return results


__all__ = [
    "BuilderProposalReview",
    "FileApplyResult",
    "ParsedDiff",
    "apply_unified_diff_to_tree",
    "copy_overlap_findings",
    "parse_unified_diff",
    "review_id",
    "scope_findings",
    "stable_hash",
    "text_digest",
    "token_scan_findings",
]
