from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

__all__ = ["analyze_capability_pack_lineage"]

_STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
_PROPOSAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_PROPOSAL_PATH_MARKER = "/artifacts/plugins/proposals/"


def analyze_capability_pack_lineage(
    entries: Iterable[Mapping[str, Any]],
    *,
    available_proposal_ids: Iterable[str] = (),
    available_proposal_paths: Iterable[str] = (),
) -> dict[str, Any]:
    available_ids = {_normalize_proposal_id(value) for value in available_proposal_ids}
    available_ids.discard("")
    available_paths = {_normalize_available_path(value) for value in available_proposal_paths}
    available_paths.discard("")
    available_ids.update(_proposal_id_from_path(path) for path in available_paths)
    available_ids.discard("")

    normalized = [
        _normalize_entry(entry, available_proposal_ids=available_ids, available_proposal_paths=available_paths)
        for entry in entries
    ]
    normalized = [entry for entry in normalized if entry["capability"]]
    unpacked = [entry for entry in normalized if not entry["pack_id"]]
    packed = [entry for entry in normalized if entry["pack_id"]]
    packs = _pack_lineage(packed)
    ready_pack_count = sum(1 for pack in packs if pack["ready"])
    return {
        "stage": _STAGE17_CAPABILITY_ECONOMY_STAGE,
        "status": "ready" if packs and ready_pack_count == len(packs) and not unpacked else "blocked",
        "total_entries": len(normalized),
        "pack_total": len(packs),
        "ready_pack_count": ready_pack_count,
        "blocked_pack_count": len(packs) - ready_pack_count,
        "unpacked_entry_count": len(unpacked),
        "available_proposal_count": len(available_ids),
        "available_proposal_path_count": len(available_paths),
        "packs": packs,
        "requirements": {
            "proposal_lineage_required_for_staged": True,
            "proposal_ids_must_exist": True,
            "proposal_paths_must_stay_within_plugin_proposals": True,
            "proposal_bodies_not_read": True,
            "operator_review_remains_separate_gate": True,
        },
        "governance": {
            "read_only": True,
            "does_not_read_proposal_bodies": True,
            "does_not_write_proposals": True,
            "does_not_write_receipts": True,
            "does_not_mutate_registry": True,
            "does_not_approve_proposals": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "proposal_approval_authority": False,
            "promotion_authority": False,
            "execution_authority": False,
        },
        "next_smallest_truthful_gap": _next_gap(packs=packs, unpacked=unpacked),
    }


def _pack_lineage(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault((entry["pack_id"], entry["pack_version"]), []).append(entry)

    packs: list[dict[str, Any]] = []
    for (pack_id, pack_version), grouped_entries in sorted(grouped.items()):
        blockers = _lineage_blockers(grouped_entries)
        failing = [entry for entry in sorted(grouped_entries, key=_entry_sort_key) if _entry_lineage_gaps(entry)]
        required_entries = [entry for entry in grouped_entries if entry["requires_proposal_lineage"]]
        present_ids = {
            entry["proposal_id"]
            for entry in required_entries
            if entry["proposal_lineage_present"] and entry["proposal_id"]
        }
        packs.append(
            {
                "pack_id": pack_id,
                "pack_version": pack_version,
                "pack_name": grouped_entries[0]["pack_name"],
                "status": "ready" if not blockers else "blocked",
                "ready": not blockers,
                "capability_count": len(grouped_entries),
                "requires_proposal_lineage_count": len(required_entries),
                "proposal_lineage_present_count": sum(
                    1 for entry in required_entries if entry["proposal_lineage_present"]
                ),
                "proposal_id_missing_count": sum(
                    1 for entry in required_entries if "proposal_id_missing" in _entry_lineage_gaps(entry)
                ),
                "proposal_not_found_count": sum(
                    1 for entry in required_entries if "proposal_not_found" in _entry_lineage_gaps(entry)
                ),
                "proposal_invalid_count": sum(
                    1
                    for entry in required_entries
                    if any(gap in _entry_lineage_gaps(entry) for gap in _INVALID_LINEAGE_GAPS)
                ),
                "blockers": blockers,
                "proposal_ids": sorted(present_ids)[:25],
                "proposal_ids_truncated": len(present_ids) > 25,
                "failing_capabilities_sample": [_entry_lineage_summary(entry) for entry in failing[:25]],
                "failing_capabilities_truncated": len(failing) > 25,
            }
        )
    return packs


_INVALID_LINEAGE_GAPS = ("proposal_id_invalid", "proposal_path_invalid")


def _lineage_blockers(entries: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if any(
        entry["requires_proposal_lineage"] and "proposal_id_missing" in _entry_lineage_gaps(entry) for entry in entries
    ):
        blockers.append("proposal_id_missing")
    if any("proposal_id_invalid" in _entry_lineage_gaps(entry) for entry in entries):
        blockers.append("proposal_id_invalid")
    if any("proposal_path_invalid" in _entry_lineage_gaps(entry) for entry in entries):
        blockers.append("proposal_path_invalid")
    if any(
        entry["requires_proposal_lineage"] and "proposal_not_found" in _entry_lineage_gaps(entry) for entry in entries
    ):
        blockers.append("proposal_not_found")
    return blockers


def _entry_lineage_gaps(entry: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    proposal_id = str(entry.get("proposal_id") or "")
    proposal_path = str(entry.get("proposal_path") or "")
    id_valid = bool(entry.get("proposal_id_valid"))
    path_valid = bool(entry.get("proposal_path_valid"))
    requires_lineage = bool(entry.get("requires_proposal_lineage"))
    if requires_lineage and not proposal_id and not proposal_path:
        gaps.append("proposal_id_missing")
    if proposal_id and not id_valid:
        gaps.append("proposal_id_invalid")
    if proposal_path and not path_valid:
        gaps.append("proposal_path_invalid")
    if (
        requires_lineage
        and (proposal_id or proposal_path)
        and id_valid
        and path_valid
        and not entry.get("proposal_lineage_present")
    ):
        gaps.append("proposal_not_found")
    return gaps


def _entry_lineage_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capability": str(entry.get("capability") or ""),
        "version": str(entry.get("version") or ""),
        "source": str(entry.get("source") or ""),
        "status": str(entry.get("status") or ""),
        "risk_tier": str(entry.get("risk_tier") or ""),
        "proposal_id": str(entry.get("proposal_id") or ""),
        "proposal_path": str(entry.get("proposal_path") or ""),
        "gaps": _entry_lineage_gaps(entry),
    }


def _normalize_entry(
    entry: Mapping[str, Any],
    *,
    available_proposal_ids: set[str],
    available_proposal_paths: set[str],
) -> dict[str, Any]:
    raw_metadata = entry.get("metadata")
    metadata: Mapping[str, Any] = raw_metadata if isinstance(raw_metadata, Mapping) else {}
    proposal_id = _text(entry.get("proposal_id") or metadata.get("proposal_id") or metadata.get("forge_proposal_id"))
    proposal_path = _text(
        entry.get("proposal_path") or metadata.get("proposal_path") or metadata.get("forge_proposal_path")
    )
    proposal_id_valid = not proposal_id or _allowed_proposal_id(proposal_id)
    proposal_path_normalized = _normalize_proposal_path(proposal_path)
    proposal_path_valid = not proposal_path or _allowed_proposal_path(
        proposal_path_normalized,
        available_proposal_paths=available_proposal_paths,
    )
    derived_proposal_id = _proposal_id_from_path(proposal_path_normalized)
    lineage_present = (
        proposal_id_valid
        and proposal_path_valid
        and (
            (bool(proposal_id) and proposal_id in available_proposal_ids)
            or (bool(derived_proposal_id) and derived_proposal_id in available_proposal_ids)
            or (bool(proposal_path_normalized) and proposal_path_normalized in available_proposal_paths)
        )
    )
    status = _label(entry.get("status"))
    return {
        "capability": _text(entry.get("capability")),
        "version": _text(entry.get("version"), fallback="0.1.0"),
        "source": _label(entry.get("source")),
        "status": status,
        "risk_tier": _label(entry.get("risk_tier"), fallback="normal"),
        "requires_proposal_lineage": status == "staged",
        "proposal_id": proposal_id,
        "proposal_id_valid": proposal_id_valid,
        "proposal_path": proposal_path,
        "proposal_path_normalized": proposal_path_normalized,
        "proposal_path_valid": proposal_path_valid,
        "proposal_lineage_present": lineage_present,
        "pack_id": _text(metadata.get("pack_id") or metadata.get("capability_pack_id")),
        "pack_version": _text(metadata.get("pack_version") or metadata.get("capability_pack_version")),
        "pack_name": _text(metadata.get("pack_name") or metadata.get("capability_pack_name")),
    }


def _normalize_available_path(value: str) -> str:
    return _normalize_proposal_path(value)


def _normalize_proposal_id(value: Any) -> str:
    text = _text(value)
    if text.endswith(".json"):
        text = text[:-5]
    return text if _allowed_proposal_id(text) else ""


def _normalize_proposal_path(value: Any) -> str:
    text = _text(value).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _allowed_proposal_id(value: str) -> bool:
    return bool(_PROPOSAL_ID_RE.match(value))


def _allowed_proposal_path(path: str, *, available_proposal_paths: set[str]) -> bool:
    if not path or any(ch in path for ch in ("\x00", "\n", "\r")):
        return False
    parts = [part for part in path.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        return False
    if not path.endswith(".json"):
        return False
    proposal_id = _proposal_id_from_path(path)
    if not proposal_id or not _allowed_proposal_id(proposal_id):
        return False
    if path.startswith(("proposals/", "artifacts/plugins/proposals/", "data/artifacts/plugins/proposals/")):
        return True
    return _PROPOSAL_PATH_MARKER in path and path in available_proposal_paths


def _proposal_id_from_path(path: str) -> str:
    normalized = _normalize_proposal_path(path)
    if not normalized.endswith(".json"):
        return ""
    name = normalized.rsplit("/", 1)[-1]
    return _normalize_proposal_id(name)


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get("capability") or ""), str(entry.get("version") or ""), str(entry.get("source") or ""))


def _next_gap(*, packs: list[dict[str, Any]], unpacked: list[dict[str, Any]]) -> str:
    if unpacked:
        return "stage17_versioned_capability_pack_metadata"
    for blocker in ("proposal_id_missing", "proposal_id_invalid", "proposal_path_invalid", "proposal_not_found"):
        if any(blocker in pack["blockers"] for pack in packs):
            return "stage17_capability_pack_lineage"
    if packs:
        return "stage17_capability_pack_promotion_receipts"
    return "stage17_capability_pack_lineage"


def _text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _label(value: Any, *, fallback: str = "unknown") -> str:
    return _text(value, fallback=fallback).lower()
