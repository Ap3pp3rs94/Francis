"""Lens <-> MCP perception bridge (read-only).

This is the first conduit from the Lens/Orb body to the MCP nervous system. It is
deliberately a SMALL, read-only rung toward embodiment:

- It lets the Lens surface *perceive* through MCP read-only tools (the senses):
  health, repo/git readback, screen/session readback, takeover/input status, and
  receipt readback.
- It is NOT a residency claim, NOT supervision, and grants NO execution authority.
  Every payload says so explicitly (``resident: False``).
- It refuses any mutating / approval-gated MCP tool AT THE BRIDGE. It never offers a
  second path around a gate: mutating tools must go through their own MCP approval
  surface, not through perception. The allowlist is derived structurally from the
  MCP tool registry (``read_only and not requires_approval``), so it cannot drift
  open silently.
- Every perception (and every refusal) writes a receipt with provenance, so a live
  caller leaves auditable evidence that the body reached the nervous system.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_display_value
from francis.kernel.paths import data_dir
from francis.mcp_gateway.tools import list_tools as _mcp_list_tools
from francis.mcp_gateway.tools import run_tool as _mcp_run_tool

LENS_MCP_PERCEPTION_SURFACE = "lens.mcp.perception"
LENS_MCP_PERCEIVE_ROUTE = "/lens/mcp/perceive"
LENS_MCP_CONTRACT_ROUTE = "/lens/mcp/contract"
LENS_MCP_RECEIPTS_ROUTE = "/lens/mcp/receipts"


def _now_s() -> int:
    return int(time.time())


def _safe_str(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _receipt_root() -> Path:
    return data_dir() / "lens" / "mcp_perception"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    return redacted if isinstance(redacted, dict) else {}


def _perceivable_tools() -> list[dict[str, Any]]:
    """Read-only, non-approval MCP tools the body may perceive through.

    Derived structurally from the MCP registry so the perception surface tracks the
    nervous system and never silently widens to a mutating tool.
    """

    return [
        tool
        for tool in _mcp_list_tools()
        if bool(tool.get("read_only")) and not bool(tool.get("requires_approval"))
    ]


def _perceivable_tool_names() -> set[str]:
    return {_safe_str(tool.get("name")) for tool in _perceivable_tools()}


def _honesty() -> dict[str, Any]:
    return {
        "bridge": "lens_mcp_perception_v0",
        "read_only": True,
        "resident": False,
        "supervision": False,
        "mutates_repo": False,
        "raw_shell": False,
        "raw_input": False,
        "screenshots": False,
        "pixels": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "approval_path": "mutating_tools_use_their_own_mcp_approval_surface_not_perception",
    }


def lens_mcp_perception_contract() -> dict[str, Any]:
    """Read-only contract: which MCP tools the Lens body may perceive through."""

    perceivable = _perceivable_tools()
    return {
        "kind": "francis.lens.mcp.perception.contract",
        "ok": True,
        "status": "ready",
        "surface": LENS_MCP_PERCEPTION_SURFACE,
        "perceivable_tools": [
            {"name": _safe_str(t.get("name")), "description": _safe_str(t.get("description"))}
            for t in perceivable
        ],
        "perceivable_tool_count": len(perceivable),
        "refused_tool_note": (
            "mutating or approval-gated MCP tools are refused at the bridge; "
            "use the tool's own MCP approval surface"
        ),
        "governance": _honesty(),
    }


def _record_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    actor = _safe_str(payload.get("actor"), "unknown")
    tool = _safe_str(payload.get("tool"))
    decision = _safe_str(payload.get("decision"))
    digest_src = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
    digest = hashlib.sha256(digest_src).hexdigest()[:16]
    receipt_id = f"lens-mcp-{decision}-{digest}"
    receipt = {
        "kind": "francis.lens.mcp.perception.receipt",
        "receipt_id": receipt_id,
        "id": receipt_id,
        "created_ts": ts,
        "surface": LENS_MCP_PERCEPTION_SURFACE,
        "actor": actor,
        "tool": tool,
        "decision": decision,
        "mcp_status": _safe_str(payload.get("mcp_status")),
        "mcp_authority": _safe_str(payload.get("mcp_authority")),
        "reason": _safe_str(payload.get("reason")),
        "governance": _honesty(),
    }
    path = _receipt_root() / f"{receipt_id}.json"
    display = _display(receipt)
    _atomic_write_json(path, display)
    display["receipt_path"] = str(path)
    return display


def lens_perceive_via_mcp(tool: str, args: dict[str, Any] | None = None, *, actor: str = "unknown") -> dict[str, Any]:
    """Perceive through one read-only MCP tool, leaving a receipt.

    Refuses any tool not on the structurally-derived read-only allowlist. Never calls
    a mutating or approval-gated MCP tool. Never claims residency.
    """

    clean_tool = _safe_str(tool)
    clean_actor = _safe_str(actor, "unknown")
    allow = _perceivable_tool_names()

    if clean_tool not in allow:
        known = {_safe_str(t.get("name")) for t in _mcp_list_tools()}
        reason = "tool_not_read_only_perceivable" if clean_tool in known else "unknown_tool"
        receipt = _record_receipt(
            {"actor": clean_actor, "tool": clean_tool, "decision": "refused", "reason": reason}
        )
        return {
            "kind": "francis.lens.mcp.perception",
            "ok": False,
            "status": "refused",
            "surface": LENS_MCP_PERCEPTION_SURFACE,
            "tool": clean_tool,
            "actor": clean_actor,
            "error": reason,
            "perceivable_tools": sorted(allow),
            "receipt": receipt,
            "governance": _honesty(),
        }

    result = _mcp_run_tool(clean_tool, args or {})
    governance = result.get("governance") if isinstance(result.get("governance"), dict) else {}
    receipt = _record_receipt(
        {
            "actor": clean_actor,
            "tool": clean_tool,
            "decision": "perceived",
            "mcp_status": result.get("status"),
            "mcp_authority": governance.get("authority"),
        }
    )
    return {
        "kind": "francis.lens.mcp.perception",
        "ok": bool(result.get("ok")),
        "status": "perceived",
        "surface": LENS_MCP_PERCEPTION_SURFACE,
        "tool": clean_tool,
        "actor": clean_actor,
        "mcp_result": result,
        "receipt": receipt,
        "governance": _honesty(),
    }


def lens_mcp_perception_receipts(limit: int = 10) -> dict[str, Any]:
    """Read newest perception receipts (auditable evidence of body->nervous-system calls)."""

    root = _receipt_root()
    safe_limit = max(1, min(int(limit or 10), 100))
    receipts: list[dict[str, Any]] = []
    if root.exists():
        paths = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:safe_limit]
        for path in paths:
            try:
                receipts.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return {
        "kind": "francis.lens.mcp.perception.receipts",
        "ok": True,
        "status": "ready",
        "surface": LENS_MCP_PERCEPTION_SURFACE,
        "count": len(receipts),
        "receipts": receipts,
        "governance": _honesty(),
    }


__all__ = [
    "LENS_MCP_PERCEPTION_SURFACE",
    "LENS_MCP_PERCEIVE_ROUTE",
    "LENS_MCP_CONTRACT_ROUTE",
    "LENS_MCP_RECEIPTS_ROUTE",
    "lens_mcp_perception_contract",
    "lens_perceive_via_mcp",
    "lens_mcp_perception_receipts",
]
