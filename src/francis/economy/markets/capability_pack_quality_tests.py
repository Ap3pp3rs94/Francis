from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["analyze_capability_pack_quality_tests"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
_TEST_PATH_PREFIXES = ("tests/", "apps/chat_ui/src/", "apps/chat_ui/tests/")
_TEST_FILE_SUFFIXES = (".py", ".ts", ".tsx")


def analyze_capability_pack_quality_tests(
    entries: Iterable[Mapping[str, Any]],
    *,
    available_test_paths: Iterable[str] = (),
) -> dict[str, Any]:
    available = {_normalize_available_path(path) for path in available_test_paths}
    available.discard("")
    normalized = [_normalize_entry(entry, available_test_paths=available) for entry in entries]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_quality_tests(packed)
    ready_pack_count = sum(1 for pack in packs if pack["ready"])
    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "ready" if packs and ready_pack_count == len(packs) and not unpacked else "blocked",
        "total_entries": len(normalized),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": len(packs) - ready_pack_count,
        "unpacked_entry_count": len(unpacked),
        "available_test_path_count": len(available),
        "packs": packs,
        "requirements": {
            "declared_tests_required": True,
            "test_paths_must_exist": True,
            "test_references_must_stay_within_repo_test_surfaces": True,
            "test_contents_not_read": True,
            "operator_review_before_promotion": True,
        },
        "governance": {
            "read_only": True,
            "does_not_read_test_contents": True,
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


def _pack_quality_tests(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    packs: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        blockers = _quality_test_blockers(grouped_entries)
        failing = [entry for entry in sorted(grouped_entries, key=_entry_sort_key) if _entry_test_gaps(entry)]
        test_refs = [ref for entry in grouped_entries for ref in entry["test_references"]]
        existing_refs = [ref for ref in test_refs if ref["exists"]]
        missing_refs = [ref for ref in test_refs if ref["valid"] and not ref["exists"]]
        invalid_refs = [ref for ref in test_refs if not ref["valid"]]
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": "ready" if not blockers else "blocked",
                "ready": not blockers,
                "capability_count": len(grouped_entries),
                "blockers": blockers,
                "tested_count": sum(1 for entry in grouped_entries if entry["tests"]),
                "declared_test_reference_count": len(test_refs),
                "existing_test_reference_count": len(existing_refs),
                "missing_test_reference_count": len(missing_refs),
                "invalid_test_reference_count": len(invalid_refs),
                "test_files": sorted({ref["path"] for ref in existing_refs if ref["path"]})[:25],
                "test_files_truncated": len({ref["path"] for ref in existing_refs if ref["path"]}) > 25,
                "missing_test_references_sample": [ref["raw"] for ref in missing_refs[:25]],
                "missing_test_references_truncated": len(missing_refs) > 25,
                "invalid_test_references_sample": [ref["raw"] for ref in invalid_refs[:25]],
                "invalid_test_references_truncated": len(invalid_refs) > 25,
                "failing_capabilities_sample": [_entry_test_summary(entry) for entry in failing[:25]],
                "failing_capabilities_truncated": len(failing) > 25,
            }
        )
    return packs


def _quality_test_blockers(entries: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if any(not entry["tests"] for entry in entries):
        blockers.append("tests_missing")
    if any(any(not ref["valid"] for ref in entry["test_references"]) for entry in entries):
        blockers.append("test_reference_invalid")
    if any(any(ref["valid"] and not ref["exists"] for ref in entry["test_references"]) for entry in entries):
        blockers.append("test_reference_not_found")
    return blockers


def _entry_test_gaps(entry: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not entry.get("tests"):
        gaps.append("tests_missing")
    refs = entry.get("test_references")
    test_refs = refs if isinstance(refs, list) else []
    if any(isinstance(ref, Mapping) and not ref.get("valid") for ref in test_refs):
        gaps.append("test_reference_invalid")
    if any(isinstance(ref, Mapping) and ref.get("valid") and not ref.get("exists") for ref in test_refs):
        gaps.append("test_reference_not_found")
    return gaps


def _entry_test_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
        "test_count": len(_list_or_empty(entry.get("tests"))),
        "gaps": _entry_test_gaps(entry),
    }


def _normalize_entry(entry: Mapping[str, Any], *, available_test_paths: set[str]) -> dict[str, Any]:
    raw_quality = entry.get("quality")
    quality: Mapping[str, Any] = raw_quality if isinstance(raw_quality, Mapping) else {}
    raw_metadata = entry.get("metadata")
    metadata: Mapping[str, Any] = raw_metadata if isinstance(raw_metadata, Mapping) else {}
    tests = _str_list(quality.get("tests") or entry.get("tests"))
    return {
        "capability": _text(entry.get("capability")),
        "version": _text(entry.get("version"), fallback="0.1.0"),
        "source": _label(entry.get("source")),
        "status": _label(entry.get("status")),
        "risk_tier": _label(entry.get("risk_tier"), fallback="normal"),
        "tests": tests,
        "test_references": [_test_reference(test, available_test_paths=available_test_paths) for test in tests],
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
        "pack_name": _text(metadata.get("pack_name") or metadata.get("capability_pack_name")),
    }


def _test_reference(value: str, *, available_test_paths: set[str]) -> dict[str, Any]:
    raw = value.strip()
    path = _normalize_test_ref_path(raw)
    valid = bool(path) and _allowed_test_path(path)
    return {
        "raw": raw,
        "path": path,
        "valid": valid,
        "exists": valid and path in available_test_paths,
    }


def _normalize_available_path(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _normalize_test_ref_path(value: str) -> str:
    text = _normalize_available_path(value)
    if not text or any(ch in text for ch in ("\x00", "\n", "\r")):
        return ""
    path = text.split("::", 1)[0]
    if "#" in path:
        path = path.split("#", 1)[0]
    return path.strip()


def _allowed_test_path(path: str) -> bool:
    if path.startswith("/") or ":" in path:
        return False
    parts = [part for part in path.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        return False
    if not path.startswith(_TEST_PATH_PREFIXES):
        return False
    return path.endswith(_TEST_FILE_SUFFIXES)


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get("capability") or ""), str(entry.get("version") or ""), str(entry.get("source") or ""))


def _next_gap(*, packs: list[dict[str, Any]], unpacked: list[dict[str, Any]]) -> str:
    if unpacked:
        return "stage17_versioned_capability_pack_metadata"
    for blocker in ("tests_missing", "test_reference_invalid", "test_reference_not_found"):
        if any(blocker in pack["blockers"] for pack in packs):
            return "stage17_capability_pack_quality_tests"
    if packs:
        return "stage17_capability_pack_quality_docs"
    return "stage17_capability_pack_quality_tests"


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
