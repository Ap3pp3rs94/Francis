from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

__all__ = ["analyze_capability_pack_validation_receipts"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
_RECEIPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_RECEIPT_PATH_MARKER = "/artifacts/plugins/validations/"


def analyze_capability_pack_validation_receipts(
    entries: Iterable[Mapping[str, Any]],
    *,
    available_receipt_ids: Iterable[str] = (),
    available_receipt_paths: Iterable[str] = (),
) -> dict[str, Any]:
    available_ids = {_normalize_receipt_id(value) for value in available_receipt_ids}
    available_ids.discard("")
    available_paths = {_normalize_available_path(value) for value in available_receipt_paths}
    available_paths.discard("")
    available_ids.update(_receipt_id_from_path(path) for path in available_paths)
    available_ids.discard("")

    normalized = [
        _normalize_entry(entry, available_receipt_ids=available_ids, available_receipt_paths=available_paths)
        for entry in entries
    ]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_validation_receipts(packed)
    ready_pack_count = sum(1 for pack in packs if pack["ready"])
    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "ready" if packs and ready_pack_count == len(packs) and not unpacked else "blocked",
        "total_entries": len(normalized),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": len(packs) - ready_pack_count,
        "unpacked_entry_count": len(unpacked),
        "available_validation_receipt_count": len(available_ids),
        "available_validation_receipt_path_count": len(available_paths),
        "packs": packs,
        "requirements": {
            "validation_receipts_required_for_generated": True,
            "validation_receipts_required_for_forge": True,
            "validation_receipts_required_before_promotion": True,
            "validation_receipt_ids_must_exist": True,
            "validation_receipt_paths_must_stay_within_plugin_validations": True,
            "validation_receipt_bodies_not_read": True,
        },
        "governance": {
            "read_only": True,
            "does_not_read_receipt_bodies": True,
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


def _pack_validation_receipts(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    packs: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        blockers = _validation_receipt_blockers(grouped_entries)
        failing = [entry for entry in sorted(grouped_entries, key=_entry_sort_key) if _entry_receipt_gaps(entry)]
        required_entries = [entry for entry in grouped_entries if entry["requires_validation_receipt"]]
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": "ready" if not blockers else "blocked",
                "ready": not blockers,
                "capability_count": len(grouped_entries),
                "requires_validation_receipt_count": len(required_entries),
                "validation_receipt_present_count": sum(
                    1 for entry in required_entries if entry["validation_receipt_present"]
                ),
                "validation_receipt_missing_count": sum(
                    1 for entry in required_entries if "validation_receipt_missing" in _entry_receipt_gaps(entry)
                ),
                "validation_receipt_not_found_count": sum(
                    1 for entry in required_entries if "validation_receipt_not_found" in _entry_receipt_gaps(entry)
                ),
                "validation_receipt_invalid_count": sum(
                    1
                    for entry in required_entries
                    if any(gap in _entry_receipt_gaps(entry) for gap in _INVALID_RECEIPT_GAPS)
                ),
                "blockers": blockers,
                "validation_receipt_ids": sorted(
                    {
                        entry["validation_receipt_id"]
                        for entry in required_entries
                        if entry["validation_receipt_present"] and entry["validation_receipt_id"]
                    }
                )[:25],
                "validation_receipt_ids_truncated": len(
                    {
                        entry["validation_receipt_id"]
                        for entry in required_entries
                        if entry["validation_receipt_present"] and entry["validation_receipt_id"]
                    }
                )
                > 25,
                "failing_capabilities_sample": [_entry_receipt_summary(entry) for entry in failing[:25]],
                "failing_capabilities_truncated": len(failing) > 25,
            }
        )
    return packs


_INVALID_RECEIPT_GAPS = ("validation_receipt_id_invalid", "validation_receipt_path_invalid")


def _validation_receipt_blockers(entries: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if any(
        entry["requires_validation_receipt"] and "validation_receipt_missing" in _entry_receipt_gaps(entry)
        for entry in entries
    ):
        blockers.append("validation_receipt_missing")
    if any("validation_receipt_id_invalid" in _entry_receipt_gaps(entry) for entry in entries):
        blockers.append("validation_receipt_id_invalid")
    if any("validation_receipt_path_invalid" in _entry_receipt_gaps(entry) for entry in entries):
        blockers.append("validation_receipt_path_invalid")
    if any(
        entry["requires_validation_receipt"] and "validation_receipt_not_found" in _entry_receipt_gaps(entry)
        for entry in entries
    ):
        blockers.append("validation_receipt_not_found")
    return blockers


def _entry_receipt_gaps(entry: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    receipt_id = str(entry.get("validation_receipt_id") or "")
    receipt_path = str(entry.get("validation_receipt_path") or "")
    id_valid = bool(entry.get("validation_receipt_id_valid"))
    path_valid = bool(entry.get("validation_receipt_path_valid"))
    requires_receipt = bool(entry.get("requires_validation_receipt"))
    if requires_receipt and not receipt_id and not receipt_path:
        gaps.append("validation_receipt_missing")
    if receipt_id and not id_valid:
        gaps.append("validation_receipt_id_invalid")
    if receipt_path and not path_valid:
        gaps.append("validation_receipt_path_invalid")
    if (
        requires_receipt
        and (receipt_id or receipt_path)
        and id_valid
        and path_valid
        and not entry.get("validation_receipt_present")
    ):
        gaps.append("validation_receipt_not_found")
    return gaps


def _entry_receipt_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
        "validation_receipt_id": str(entry.get("validation_receipt_id") or ""),
        "validation_receipt_path": str(entry.get("validation_receipt_path") or ""),
        "gaps": _entry_receipt_gaps(entry),
    }


def _normalize_entry(
    entry: Mapping[str, Any],
    *,
    available_receipt_ids: set[str],
    available_receipt_paths: set[str],
) -> dict[str, Any]:
    raw_metadata = entry.get("metadata")
    metadata: Mapping[str, Any] = raw_metadata if isinstance(raw_metadata, Mapping) else {}
    validation_receipt_id = _text(entry.get("validation_receipt_id") or metadata.get("validation_receipt_id"))
    validation_receipt_path = _text(entry.get("validation_receipt_path") or metadata.get("validation_receipt_path"))
    receipt_id_valid = not validation_receipt_id or _allowed_receipt_id(validation_receipt_id)
    receipt_path_normalized = _normalize_receipt_path(validation_receipt_path)
    receipt_path_valid = not validation_receipt_path or _allowed_receipt_path(
        receipt_path_normalized,
        available_receipt_paths=available_receipt_paths,
    )
    derived_receipt_id = _receipt_id_from_path(receipt_path_normalized)
    receipt_present = (
        receipt_id_valid
        and receipt_path_valid
        and (
            (bool(validation_receipt_id) and validation_receipt_id in available_receipt_ids)
            or (bool(derived_receipt_id) and derived_receipt_id in available_receipt_ids)
            or (bool(receipt_path_normalized) and receipt_path_normalized in available_receipt_paths)
        )
    )
    source = _label(entry.get("source"))
    status = _label(entry.get("status"))
    return {
        "capability": _text(entry.get("capability")),
        "version": _text(entry.get("version"), fallback="0.1.0"),
        "source": source,
        "status": status,
        "risk_tier": _label(entry.get("risk_tier"), fallback="normal"),
        "requires_validation_receipt": _requires_validation_receipt(source=source, status=status),
        "validation_receipt_id": validation_receipt_id,
        "validation_receipt_id_valid": receipt_id_valid,
        "validation_receipt_path": validation_receipt_path,
        "validation_receipt_path_normalized": receipt_path_normalized,
        "validation_receipt_path_valid": receipt_path_valid,
        "validation_receipt_present": receipt_present,
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
        "pack_name": _text(metadata.get("pack_name") or metadata.get("capability_pack_name")),
    }


def _requires_validation_receipt(*, source: str, status: str) -> bool:
    return source in {"forge", "generated"} and status in {"staged", "promoted"}


def _normalize_available_path(value: str) -> str:
    return _normalize_receipt_path(value)


def _normalize_receipt_id(value: Any) -> str:
    text = _text(value)
    if text.endswith(".json"):
        text = text[:-5]
    return text if _allowed_receipt_id(text) else ""


def _normalize_receipt_path(value: Any) -> str:
    text = _text(value).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _allowed_receipt_id(value: str) -> bool:
    return bool(_RECEIPT_ID_RE.match(value))


def _allowed_receipt_path(path: str, *, available_receipt_paths: set[str]) -> bool:
    if not path or any(ch in path for ch in ("\x00", "\n", "\r")):
        return False
    parts = [part for part in path.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        return False
    if not path.endswith(".json"):
        return False
    receipt_id = _receipt_id_from_path(path)
    if not receipt_id or not _allowed_receipt_id(receipt_id):
        return False
    if path.startswith(("validations/", "artifacts/plugins/validations/", "data/artifacts/plugins/validations/")):
        return True
    return _RECEIPT_PATH_MARKER in path and path in available_receipt_paths


def _receipt_id_from_path(path: str) -> str:
    normalized = _normalize_receipt_path(path)
    if not normalized.endswith(".json"):
        return ""
    name = normalized.rsplit("/", 1)[-1]
    return _normalize_receipt_id(name)


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get("capability") or ""), str(entry.get("version") or ""), str(entry.get("source") or ""))


def _next_gap(*, packs: list[dict[str, Any]], unpacked: list[dict[str, Any]]) -> str:
    if unpacked:
        return "stage17_versioned_capability_pack_metadata"
    for blocker in (
        "validation_receipt_missing",
        "validation_receipt_id_invalid",
        "validation_receipt_path_invalid",
        "validation_receipt_not_found",
    ):
        if any(blocker in pack["blockers"] for pack in packs):
            return "stage17_capability_pack_validation_receipts"
    if packs:
        return "stage17_capability_pack_lineage"
    return "stage17_capability_pack_validation_receipts"


def _text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _label(value: Any, *, fallback: str = "unknown") -> str:
    return _text(value, fallback=fallback).lower()
