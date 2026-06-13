from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_display_value
from francis.kernel.paths import data_dir

from ..shared.models import CapabilityCandidate, Receipt, SourceRecord

INGEST_LAYOUT_DIRS = ("incoming", "processing", "indexed", "studied", "needs-permission", "failed", "archived")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def ingest_root() -> Path:
    return data_dir() / "ingest"


def ingest_artifact_root() -> Path:
    return data_dir() / "artifacts" / "ingest"


def ensure_ingest_layout() -> dict[str, str]:
    root = ingest_root()
    layout: dict[str, str] = {"root": str(root)}
    for name in INGEST_LAYOUT_DIRS:
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        layout[name.replace("-", "_")] = str(path)
    for name in (
        "repo_maps",
        "capabilities",
        "lab_approval_consumptions",
        "lab_approval_consumption_handoffs",
        "lab_approval_consumption_preflights",
        "lab_approval_requests",
        "lab_noop_runner_envelopes",
        "lab_noop_runner_identity_bindings",
        "lab_noop_runner_transcripts",
        "lab_source_mount_readiness",
        "lab_source_mount_contracts",
        "lab_execution_receipt_sink_reservations",
        "lab_receipt_prewrite_bindings",
        "lab_receipt_writer_preflights",
        "lab_receipt_write_readiness",
        "lab_run_boundary_preflights",
        "lab_sandbox_provider_bindings",
        "lab_sandbox_provider_contracts",
        "lab_sandbox_provider_selections",
        "lab_sandbox_provider_verifier_preflights",
        "lab_sandbox_provider_runtime_probe_preflights",
        "lab_runtime_probe_harness_preflights",
        "lab_runtime_probe_runner_readiness",
        "lab_runtime_probe_runner_bindings",
        "lab_runtime_probe_runner_enforcements",
        "lab_runtime_probe_execution_boundaries",
        "lab_runtime_probe_refusals",
        "lab_runtime_probe_approval_requests",
        "lab_runtime_probe_approval_consumptions",
        "lab_runtime_probe_invocation_boundaries",
        "lab_runtime_probe_preexec_boundaries",
        "lab_runtime_probe_control_bindings",
        "lab_sandboxed_rebuild_run_test_boundaries",
        "lab_sandboxed_rebuild_run_test_approval_requests",
        "lab_sandboxed_rebuild_run_test_approval_consumptions",
        "lab_sandboxed_rebuild_run_test_runner_bindings",
        "lab_sandboxed_rebuild_run_test_sandbox_policies",
        "lab_plans",
        "lab_preflights",
        "lab_refusals",
        "lab_execution_receipts",
        "lab_execution_runs",
        "acquisitions",
        "capability_specs",
        "builder_runs",
        "builder_proposal_reviews",
        "forge_apply_preflights",
        "forge_apply_approval_requests",
        "forge_apply_approval_consumptions",
        "forge_apply_boundaries",
        "forge_validation_plans",
        "forge_synthesis_runs",
        "forge_apply_dryruns",
        "forge_dryrun_workspaces",
        "forge_synthesized_sources",
        "lab_runner_bindings",
        "lab_runner_command_allowlists",
        "lab_runner_command_allowlist_declarations",
        "lab_cmd_allowlist_enforcements",
        "lab_sandbox_readiness",
        "lab_runner_contracts",
        "lab_runner_enforcement_preflights",
        "lab_runner_readiness",
        "lab_workspaces",
        "receipts",
    ):
        path = ingest_artifact_root() / name
        path.mkdir(parents=True, exist_ok=True)
        layout[f"artifact_{name}"] = str(path)
    return layout


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    display_payload = redact_governed_display_value(payload)
    out = display_payload if isinstance(display_payload, dict) else {}
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _new_receipt_id(operation: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", operation.strip().lower()).strip("-")[:42] or "operation"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"ingest_receipt_{stamp}_{slug}_{uuid.uuid4().hex[:8]}"


class SourceRegistry:
    def __init__(self, path: Path | None = None) -> None:
        ensure_ingest_layout()
        self.path = path or (ingest_root() / "_source_registry.json")

    def load(self) -> dict[str, Any]:
        raw = _load_json(self.path)
        sources = raw.get("sources")
        if not isinstance(sources, dict):
            sources = {}
        normalized: dict[str, Any] = {
            "version": 1,
            "updated_at": str(raw.get("updated_at") or utc_now()),
            "sources": {},
        }
        for key, value in sources.items():
            record = SourceRecord.from_dict(value)
            if record is not None:
                normalized["sources"][str(key)] = record.to_dict()
        return normalized

    def save(self, registry: dict[str, Any]) -> None:
        payload = {
            "version": int(registry.get("version") or 1),
            "updated_at": utc_now(),
            "sources": registry.get("sources") if isinstance(registry.get("sources"), dict) else {},
        }
        _atomic_write_json(self.path, payload)

    def upsert(self, record: SourceRecord) -> SourceRecord:
        registry = self.load()
        registry["sources"][record.id] = record.to_dict()
        self.save(registry)
        return record

    def get(self, source_id: str) -> SourceRecord | None:
        registry = self.load()
        raw = registry["sources"].get(source_id)
        return SourceRecord.from_dict(raw)

    def list(self) -> list[SourceRecord]:
        registry = self.load()
        records = []
        for value in registry["sources"].values():
            record = SourceRecord.from_dict(value)
            if record is not None:
                records.append(record)
        return sorted(records, key=lambda item: (item.updated_at, item.id), reverse=True)


class CapabilityRegistry:
    def __init__(self, path: Path | None = None) -> None:
        ensure_ingest_layout()
        self.path = path or (ingest_root() / "_capability_registry.json")

    def load(self) -> dict[str, Any]:
        raw = _load_json(self.path)
        candidates = raw.get("candidates")
        if not isinstance(candidates, dict):
            candidates = {}
        normalized: dict[str, Any] = {
            "version": 1,
            "updated_at": str(raw.get("updated_at") or utc_now()),
            "candidates": {},
        }
        for key, value in candidates.items():
            candidate = CapabilityCandidate.from_dict(value)
            if candidate is not None:
                normalized["candidates"][str(key)] = candidate.to_dict()
        return normalized

    def save(self, registry: dict[str, Any]) -> None:
        payload = {
            "version": int(registry.get("version") or 1),
            "updated_at": utc_now(),
            "candidates": registry.get("candidates") if isinstance(registry.get("candidates"), dict) else {},
        }
        _atomic_write_json(self.path, payload)

    def replace_for_source(
        self, source_id: str, candidates: Iterable[CapabilityCandidate]
    ) -> list[CapabilityCandidate]:
        registry = self.load()
        existing = registry["candidates"]
        for candidate_id in list(existing):
            raw = existing.get(candidate_id)
            if isinstance(raw, dict) and str(raw.get("source_id")) == source_id:
                existing.pop(candidate_id, None)
        stored = list(candidates)
        for candidate in stored:
            existing[candidate.id] = candidate.to_dict()
        self.save(registry)
        return stored

    def list_for_source(self, source_id: str) -> list[CapabilityCandidate]:
        registry = self.load()
        out: list[CapabilityCandidate] = []
        for value in registry["candidates"].values():
            candidate = CapabilityCandidate.from_dict(value)
            if candidate is not None and candidate.source_id == source_id:
                out.append(candidate)
        return sorted(out, key=lambda item: item.id)


class ReceiptWriter:
    def __init__(self, receipts_dir: Path | None = None) -> None:
        ensure_ingest_layout()
        self.receipts_dir = receipts_dir or (ingest_artifact_root() / "receipts")

    def write(
        self,
        *,
        operation: str,
        source_id: str,
        actor: str = "francis/system",
        input_paths: list[str] | None = None,
        input_hashes: list[str] | None = None,
        files_inspected_count: int = 0,
        result_status: str = "ok",
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        generated_artifact_paths: list[str] | None = None,
        validation_performed: list[str] | None = None,
    ) -> tuple[Receipt, Path]:
        receipt = Receipt(
            id=_new_receipt_id(operation),
            timestamp=utc_now(),
            operation=operation,
            source_id=source_id,
            actor=actor.strip() or "francis/system",
            input_paths=input_paths or [],
            input_hashes=input_hashes or [],
            files_inspected_count=max(0, int(files_inspected_count)),
            result_status=result_status.strip() or "ok",
            warnings=warnings or [],
            errors=errors or [],
            generated_artifact_paths=generated_artifact_paths or [],
            validation_performed=validation_performed or [],
        )
        path = self.receipts_dir / f"{receipt.id}.json"
        _atomic_write_json(path, receipt.to_dict())
        return receipt, path


def write_ingest_artifact(kind: str, source_id: str, payload: dict[str, Any]) -> Path:
    safe_kind = re.sub(r"[^a-z0-9_-]+", "-", kind.strip().lower()).strip("-") or "artifact"
    path = ingest_artifact_root() / safe_kind / f"{source_id}.json"
    _atomic_write_json(path, payload)
    return path


def write_ingest_record_artifact(kind: str, artifact_id: str, payload: dict[str, Any]) -> Path:
    safe_kind = re.sub(r"[^a-z0-9_-]+", "-", kind.strip().lower()).strip("-") or "artifact"
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", artifact_id.strip()).strip("-") or "record"
    path = ingest_artifact_root() / safe_kind / f"{safe_id}.json"
    _atomic_write_json(path, payload)
    return path


def lab_workspace_root(workspace_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", workspace_id.strip()).strip("-") or "workspace"
    return ingest_artifact_root() / "lab_workspaces" / safe_id
