from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

RUNTIME_IDENTITY = "stage18_managed_copy_runtime_v1"
HEARTBEAT_IDENTITY = "stage18_managed_copy_runtime_heartbeat_v1"
INPUT_CONTRACT = "stage18_managed_copy_work_briefing_input_v1"
OUTPUT_CONTRACT = "stage18_managed_copy_work_briefing_output_v1"
TENANT_BOUNDARY_INPUT_CONTRACT = "stage18_managed_copy_tenant_boundary_probe_input_v1"
TENANT_BOUNDARY_OUTPUT_CONTRACT = "stage18_managed_copy_tenant_boundary_probe_output_v2"
WORK_BRIEFING_OPERATION = "tenant_work_briefing"
TENANT_BOUNDARY_OPERATION = "tenant_boundary_probe"
TENANT_BOUNDARY_ID = "fixed_sibling_tenant_boundary_v1"
TENANT_BOUNDARY_RELATIVE_PATH = "tenant-b"
TENANT_DOMAIN_BOUNDARY_PATHS = {
    "tenant_data": "tenant-data",
    "tenant_memory": "tenant-memory",
    "tenant_receipts": "tenant-receipts",
    "tenant_connectors": "tenant-connectors",
    "tenant_policy": "tenant-policy",
    "tenant_support_authority": "tenant-support-authority",
}
_PRIORITIES = ("critical", "high", "normal", "low")
_STATUSES = ("open", "blocked", "done")
_PUBLIC_INPUT_BLOCKERS = frozenset(
    {
        "managed_copy_work_briefing_input_schema_invalid",
        "managed_copy_work_briefing_contract_invalid",
        "managed_copy_work_briefing_items_invalid",
        "managed_copy_work_briefing_item_schema_invalid",
        "managed_copy_work_briefing_item_invalid",
        "managed_copy_tenant_boundary_probe_input_schema_invalid",
        "managed_copy_tenant_boundary_probe_contract_invalid",
        "managed_copy_tenant_boundary_probe_input_invalid",
        "managed_copy_tenant_boundary_probe_observation_invalid",
    }
)


class ManagedCopyRuntimeInputError(ValueError):
    """A fixed public blocker raised by managed-copy input validation."""

    def __init__(self, blocker: str) -> None:
        self.blocker = blocker if blocker in _PUBLIC_INPUT_BLOCKERS else "managed_copy_runtime_input_invalid"
        super().__init__(self.blocker)


def build_work_briefing(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"contract", "items"}:
        raise ManagedCopyRuntimeInputError("managed_copy_work_briefing_input_schema_invalid")
    if payload.get("contract") != INPUT_CONTRACT:
        raise ManagedCopyRuntimeInputError("managed_copy_work_briefing_contract_invalid")
    items = payload.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ManagedCopyRuntimeInputError("managed_copy_work_briefing_items_invalid")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "title", "priority", "status"}:
            raise ManagedCopyRuntimeInputError("managed_copy_work_briefing_item_schema_invalid")
        item_id = _bounded(item.get("id"), 80)
        title = _bounded(item.get("title"), 240)
        priority = _bounded(item.get("priority"), 16)
        status = _bounded(item.get("status"), 16)
        if not item_id or item_id in seen or not title or priority not in _PRIORITIES or status not in _STATUSES:
            raise ManagedCopyRuntimeInputError("managed_copy_work_briefing_item_invalid")
        seen.add(item_id)
        normalized.append({"id": item_id, "title": title, "priority": priority, "status": status})
    candidates = sorted(
        (item for item in normalized if item["status"] == "open"),
        key=lambda item: (_PRIORITIES.index(item["priority"]), item["id"]),
    )
    result = {
        "contract": OUTPUT_CONTRACT,
        "item_count": len(normalized),
        "status_counts": {status: sum(item["status"] == status for item in normalized) for status in _STATUSES},
        "priority_counts": {
            priority: sum(item["priority"] == priority for item in normalized) for priority in _PRIORITIES
        },
        "next_action": candidates[0] if candidates else None,
        "input_fingerprint": _fingerprint(payload),
    }
    return {**result, "output_fingerprint": _fingerprint(result)}


def build_tenant_boundary_probe(
    payload: object,
    *,
    approved_input_read: bool,
    sibling_boundary_absent: bool,
    domain_boundaries_absent: dict[str, bool],
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"contract", "probe_id", "tenant_marker"}:
        raise ManagedCopyRuntimeInputError("managed_copy_tenant_boundary_probe_input_schema_invalid")
    if payload.get("contract") != TENANT_BOUNDARY_INPUT_CONTRACT:
        raise ManagedCopyRuntimeInputError("managed_copy_tenant_boundary_probe_contract_invalid")
    probe_id = _bounded(payload.get("probe_id"), 80)
    tenant_marker = _bounded(payload.get("tenant_marker"), 160)
    if not probe_id or not tenant_marker:
        raise ManagedCopyRuntimeInputError("managed_copy_tenant_boundary_probe_input_invalid")
    if (
        type(approved_input_read) is not bool
        or type(sibling_boundary_absent) is not bool
        or not isinstance(domain_boundaries_absent, dict)
        or set(domain_boundaries_absent) != set(TENANT_DOMAIN_BOUNDARY_PATHS)
        or any(type(value) is not bool for value in domain_boundaries_absent.values())
    ):
        raise ManagedCopyRuntimeInputError("managed_copy_tenant_boundary_probe_observation_invalid")
    bounded_domains_proven = all(domain_boundaries_absent.values())
    result = {
        "contract": TENANT_BOUNDARY_OUTPUT_CONTRACT,
        "operation": TENANT_BOUNDARY_OPERATION,
        "probe_id": probe_id,
        "approved_tenant_input_read": approved_input_read,
        "approved_tenant_input_fingerprint": _fingerprint(payload),
        "sibling_boundary_id": TENANT_BOUNDARY_ID,
        "sibling_tenant_boundary_absent": sibling_boundary_absent,
        "domain_boundaries_absent": {
            domain: domain_boundaries_absent[domain] for domain in TENANT_DOMAIN_BOUNDARY_PATHS
        },
        "bounded_isolation_domains_proven": bounded_domains_proven,
        "bounded_cross_tenant_denial": approved_input_read and sibling_boundary_absent and bounded_domains_proven,
        "fixture_runtime": False,
        "comprehensive_tenant_isolation_proven": False,
    }
    return {**result, "output_fingerprint": _fingerprint(result)}


def build_runtime_operation_preview(payload: object) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("contract") == TENANT_BOUNDARY_INPUT_CONTRACT:
        return build_tenant_boundary_probe(
            payload,
            approved_input_read=False,
            sibling_boundary_absent=False,
            domain_boundaries_absent={domain: False for domain in TENANT_DOMAIN_BOUNDARY_PATHS},
        )
    return build_work_briefing(payload)


def runtime_operation_name(payload: object) -> str:
    preview = build_runtime_operation_preview(payload)
    return str(preview.get("operation") or WORK_BRIEFING_OPERATION)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    for name in (
        "tenant-root",
        "state-dir",
        "input-path",
        "copy-id",
        "tenant-key",
        "pilot-run-id",
        "runtime-nonce",
    ):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--lease-seconds", required=True, type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        tenant_root = Path(args.tenant_root).resolve(strict=True)
        state_dir = Path(args.state_dir).resolve(strict=True)
        input_path = Path(args.input_path).resolve(strict=True)
    except OSError:
        return 2
    try:
        state_dir.relative_to(tenant_root)
        input_path.relative_to(tenant_root)
    except ValueError:
        return 2
    identity = {
        "kind": "francis.stage18.managed_copies.runtime_handshake",
        "runtime_identity": RUNTIME_IDENTITY,
        "fixture_runtime": False,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "copy_id": args.copy_id,
        "tenant_key": args.tenant_key,
        "pilot_run_id": args.pilot_run_id,
        "runtime_nonce_hash": hashlib.sha256(args.runtime_nonce.encode()).hexdigest(),
    }
    _write_atomic(state_dir / "handshake.json", identity)
    try:
        source = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(source, dict) and source.get("contract") == TENANT_BOUNDARY_INPUT_CONTRACT:
            sibling_boundary = tenant_root.parent / TENANT_BOUNDARY_RELATIVE_PATH
            output = build_tenant_boundary_probe(
                source,
                approved_input_read=input_path.is_file(),
                sibling_boundary_absent=not sibling_boundary.exists(),
                domain_boundaries_absent={
                    domain: not (tenant_root / relative_path).exists()
                    for domain, relative_path in TENANT_DOMAIN_BOUNDARY_PATHS.items()
                },
            )
            operation_name = TENANT_BOUNDARY_OPERATION
            output_name = "tenant_boundary_probe"
        else:
            output = build_work_briefing(source)
            operation_name = WORK_BRIEFING_OPERATION
            output_name = "briefing"
        _write_atomic(state_dir / f"{output_name}.json", output)
        operation = {
            "kind": "francis.stage18.managed_copies.runtime_operation_receipt",
            "operation": operation_name,
            "status": "completed",
            "copy_id": args.copy_id,
            "tenant_key": args.tenant_key,
            "pilot_run_id": args.pilot_run_id,
            "runtime_nonce_hash": identity["runtime_nonce_hash"],
            "input_fingerprint": output.get("input_fingerprint", output.get("approved_tenant_input_fingerprint")),
            "output_fingerprint": output["output_fingerprint"],
            "fixture_runtime": False,
            "recorded_at_unix_ms": int(time.time() * 1000),
        }
        operation["receipt_fingerprint"] = _fingerprint(operation)
        _write_atomic(state_dir / "operation.json", operation)
    except (OSError, ValueError, json.JSONDecodeError):
        return 4
    deadline = time.monotonic() + args.lease_seconds
    sequence = 0
    while time.monotonic() < deadline and not (state_dir / "stop.signal").exists():
        sequence += 1
        _write_atomic(
            state_dir / "heartbeat.json",
            {
                **identity,
                "kind": "francis.stage18.managed_copies.runtime_heartbeat",
                "heartbeat_identity": HEARTBEAT_IDENTITY,
                "ready": True,
                "operation_completed": True,
                "sequence": sequence,
                "observed_at_unix_ms": int(time.time() * 1000),
            },
        )
        time.sleep(0.1)
    return 0


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bounded(value: object, limit: int) -> str:
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= limit else ""


if __name__ == "__main__":
    raise SystemExit(main())
