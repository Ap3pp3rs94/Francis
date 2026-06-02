from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["analyze_capability_pack_quality_docs"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
_DOC_PATH_PREFIXES = ("docs/",)
_DOC_FILE_SUFFIXES = (".md", ".mdx", ".rst", ".txt")


def analyze_capability_pack_quality_docs(
    entries: Iterable[Mapping[str, Any]],
    *,
    available_doc_paths: Iterable[str] = (),
) -> dict[str, Any]:
    available = {_normalize_available_path(path) for path in available_doc_paths}
    available.discard("")
    normalized = [_normalize_entry(entry, available_doc_paths=available) for entry in entries]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_quality_docs(packed)
    ready_pack_count = sum(1 for pack in packs if pack["ready"])
    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "ready" if packs and ready_pack_count == len(packs) and not unpacked else "blocked",
        "total_entries": len(normalized),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": len(packs) - ready_pack_count,
        "unpacked_entry_count": len(unpacked),
        "available_doc_path_count": len(available),
        "packs": packs,
        "requirements": {
            "declared_docs_required": True,
            "doc_paths_must_exist": True,
            "doc_references_must_stay_within_repo_doc_surfaces": True,
            "doc_contents_not_read": True,
            "operator_review_before_promotion": True,
        },
        "governance": {
            "read_only": True,
            "does_not_read_doc_contents": True,
            "does_not_write_receipts": True,
            "does_not_mutate_registry": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "promotion_authority": False,
            "execution_authority": False,
        },
        "next_smallest_truthful_gap": _next_gap(packs=packs, unpacked=unpacked),
    }


def _pack_quality_docs(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    packs: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        blockers = _quality_doc_blockers(grouped_entries)
        failing = [entry for entry in sorted(grouped_entries, key=_entry_sort_key) if _entry_doc_gaps(entry)]
        doc_refs = [ref for entry in grouped_entries for ref in entry["doc_references"]]
        existing_refs = [ref for ref in doc_refs if ref["exists"]]
        missing_refs = [ref for ref in doc_refs if ref["valid"] and not ref["exists"]]
        invalid_refs = [ref for ref in doc_refs if not ref["valid"]]
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": "ready" if not blockers else "blocked",
                "ready": not blockers,
                "capability_count": len(grouped_entries),
                "blockers": blockers,
                "documented_count": sum(1 for entry in grouped_entries if entry["docs"]),
                "declared_doc_reference_count": len(doc_refs),
                "existing_doc_reference_count": len(existing_refs),
                "missing_doc_reference_count": len(missing_refs),
                "invalid_doc_reference_count": len(invalid_refs),
                "doc_files": sorted({ref["path"] for ref in existing_refs if ref["path"]})[:25],
                "doc_files_truncated": len({ref["path"] for ref in existing_refs if ref["path"]}) > 25,
                "missing_doc_references_sample": [ref["raw"] for ref in missing_refs[:25]],
                "missing_doc_references_truncated": len(missing_refs) > 25,
                "invalid_doc_references_sample": [ref["raw"] for ref in invalid_refs[:25]],
                "invalid_doc_references_truncated": len(invalid_refs) > 25,
                "failing_capabilities_sample": [_entry_doc_summary(entry) for entry in failing[:25]],
                "failing_capabilities_truncated": len(failing) > 25,
            }
        )
    return packs


def _quality_doc_blockers(entries: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if any(not entry["docs"] for entry in entries):
        blockers.append("docs_missing")
    if any(any(not ref["valid"] for ref in entry["doc_references"]) for entry in entries):
        blockers.append("doc_reference_invalid")
    if any(any(ref["valid"] and not ref["exists"] for ref in entry["doc_references"]) for entry in entries):
        blockers.append("doc_reference_not_found")
    return blockers


def _entry_doc_gaps(entry: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not entry.get("docs"):
        gaps.append("docs_missing")
    refs = entry.get("doc_references")
    doc_refs = refs if isinstance(refs, list) else []
    if any(isinstance(ref, Mapping) and not ref.get("valid") for ref in doc_refs):
        gaps.append("doc_reference_invalid")
    if any(isinstance(ref, Mapping) and ref.get("valid") and not ref.get("exists") for ref in doc_refs):
        gaps.append("doc_reference_not_found")
    return gaps


def _entry_doc_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
        "doc_count": len(_list_or_empty(entry.get("docs"))),
        "gaps": _entry_doc_gaps(entry),
    }


def _normalize_entry(entry: Mapping[str, Any], *, available_doc_paths: set[str]) -> dict[str, Any]:
    raw_quality = entry.get("quality")
    quality: Mapping[str, Any] = raw_quality if isinstance(raw_quality, Mapping) else {}
    raw_metadata = entry.get("metadata")
    metadata: Mapping[str, Any] = raw_metadata if isinstance(raw_metadata, Mapping) else {}
    docs = _str_list(quality.get("docs") or entry.get("docs"))
    return {
        "capability": _text(entry.get("capability")),
        "version": _text(entry.get("version"), fallback="0.1.0"),
        "source": _label(entry.get("source")),
        "status": _label(entry.get("status")),
        "risk_tier": _label(entry.get("risk_tier"), fallback="normal"),
        "docs": docs,
        "doc_references": [_doc_reference(doc, available_doc_paths=available_doc_paths) for doc in docs],
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
        "pack_name": _text(metadata.get("pack_name") or metadata.get("capability_pack_name")),
    }


def _doc_reference(value: str, *, available_doc_paths: set[str]) -> dict[str, Any]:
    raw = value.strip()
    path = _normalize_doc_ref_path(raw)
    valid = bool(path) and _allowed_doc_path(path)
    return {
        "raw": raw,
        "path": path,
        "valid": valid,
        "exists": valid and path in available_doc_paths,
    }


def _normalize_available_path(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _normalize_doc_ref_path(value: str) -> str:
    text = _normalize_available_path(value)
    if not text or any(ch in text for ch in ("\x00", "\n", "\r")):
        return ""
    path = text.split("#", 1)[0]
    return path.strip()


def _allowed_doc_path(path: str) -> bool:
    if path.startswith("/") or ":" in path:
        return False
    parts = [part for part in path.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        return False
    if path == "README.md":
        return True
    if not path.startswith(_DOC_PATH_PREFIXES):
        return False
    return path.endswith(_DOC_FILE_SUFFIXES)


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get("capability") or ""), str(entry.get("version") or ""), str(entry.get("source") or ""))


def _next_gap(*, packs: list[dict[str, Any]], unpacked: list[dict[str, Any]]) -> str:
    if unpacked:
        return "stage17_versioned_capability_pack_metadata"
    for blocker in ("docs_missing", "doc_reference_invalid", "doc_reference_not_found"):
        if any(blocker in pack["blockers"] for pack in packs):
            return "stage17_capability_pack_quality_docs"
    if packs:
        return "stage17_capability_pack_validation_receipts"
    return "stage17_capability_pack_quality_docs"


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _label(value: Any, *, fallback: str = "unknown") -> str:
    return _text(value, fallback=fallback).lower()


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        return [str(key).strip() for key in sorted(value) if str(key).strip()]
    if isinstance(value, (list, tuple, set)):
        return [text for item in value if (text := str(item).strip())]
    text = str(value).strip()
    return [text] if text else []
