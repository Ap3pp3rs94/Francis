"""Francis ingest acquisition orchestrator.

Pushes a repo through the EXISTING governed ingest/Lab pipeline:

    inspect -> extract -> classify -> plan -> prepare -> mechanical preflights
    -> [PAUSE at each real approval gate] -> resume after operator approval
    -> run_lab_capability wrapper -> receipt -> persisted promotion -> readback

It sequences the corridor between gates; it does NOT remove or auto-grant the
gates. Operator approval stays explicit (`approvals.decide` is never called from
here). It uses only production `IngestService` primitives and never calls
`SandboxExecutor` directly. Real execution still happens solely through
`run_lab_capability`, with its consumed-approval + opt-in + safe-candidate +
live-Docker gates intact.

Incompatible repos (e.g. ScreenEnv: needs Docker/display/network) are classified
and the run is BLOCKED before execution with a recommended specialized profile --
the default Lab is never weakened to accommodate them.
"""

from __future__ import annotations

import inspect
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from francis.governance import approvals

from ..ingest.runtime_requirements import classify_runtime_requirements
from ..shared.models import CapabilityCandidate
from .registry import ingest_artifact_root, utc_now, write_ingest_record_artifact

if TYPE_CHECKING:
    from .service import IngestService

ACQUISITION_STATES = (
    "pending",
    "running",
    "paused_for_approval",
    "blocked",
    "refused",
    "failed",
    "invalid",
    "completed",
    "promoted",
)

# Step kinds.
_MECHANICAL = "mechanical"
_REQUEST = "request_approval"
_CONSUME = "consume_approval"
_WRAPPER = "wrapper"

# The governed corridor, in proven order. Each entry: (label, service_method, kind).
# `request` steps mint a new approval and become the active threading id once the
# operator approves; mechanical/consume/wrapper steps use the current active id.
_PLAN: list[tuple[str, str, str]] = [
    ("plan_lab", "plan_lab", _MECHANICAL),
    ("prepare_workspace", "prepare_lab_workspace", _MECHANICAL),
    ("preflight_execution", "preflight_lab_execution", _MECHANICAL),
    ("request_execution_approval", "request_lab_execution_approval", _REQUEST),
    ("approval_consumption_preflight", "preflight_lab_approval_consumption", _MECHANICAL),
    ("runner_readiness", "preflight_lab_runner_readiness", _MECHANICAL),
    ("runner_binding", "preflight_lab_runner_binding", _MECHANICAL),
    ("runner_enforcement", "preflight_lab_runner_enforcement", _MECHANICAL),
    ("approval_consumption_handoff", "preflight_lab_approval_consumption_handoff", _MECHANICAL),
    ("receipt_sink_reservation", "preflight_lab_execution_receipt_sink_reservation", _MECHANICAL),
    ("cmd_allowlist_binding", "preflight_lab_runner_command_allowlist_binding", _MECHANICAL),
    ("cmd_allowlist_declaration", "preflight_lab_runner_command_allowlist_declaration", _MECHANICAL),
    ("cmd_allowlist_enforcement", "preflight_lab_runner_command_allowlist_enforcement", _MECHANICAL),
    ("runner_sandbox_readiness", "preflight_lab_runner_sandbox_readiness", _MECHANICAL),
    ("provider_contract", "preflight_lab_sandbox_provider_contract", _MECHANICAL),
    ("provider_binding", "preflight_lab_sandbox_provider_binding", _MECHANICAL),
    ("provider_selection", "preflight_lab_sandbox_provider_selection", _MECHANICAL),
    ("provider_verifier", "preflight_lab_sandbox_provider_verifier", _MECHANICAL),
    ("provider_runtime_probe", "preflight_lab_sandbox_provider_runtime_probe", _MECHANICAL),
    ("provider_runtime_probe_harness", "preflight_lab_sandbox_provider_runtime_probe_harness", _MECHANICAL),
    ("probe_runner_readiness", "preflight_lab_sandbox_provider_runtime_probe_runner_readiness", _MECHANICAL),
    ("probe_runner_binding", "preflight_lab_sandbox_provider_runtime_probe_runner_binding", _MECHANICAL),
    ("probe_runner_enforcement", "preflight_lab_sandbox_provider_runtime_probe_runner_enforcement", _MECHANICAL),
    ("receipt_write_readiness", "preflight_lab_execution_receipt_write_readiness", _MECHANICAL),
    ("receipt_prewrite_binding", "preflight_lab_execution_receipt_prewrite_binding", _MECHANICAL),
    ("receipt_writer_preflight", "preflight_lab_execution_receipt_writer", _MECHANICAL),
    ("synthetic_receipt_prewrite", "prewrite_lab_synthetic_execution_receipt", _MECHANICAL),
    ("synthetic_receipt_finalize", "finalize_lab_synthetic_execution_receipt", _MECHANICAL),
    ("consume_synthetic_noop", "consume_lab_approval_for_synthetic_execution_receipt", _MECHANICAL),
    ("noop_runner_envelope", "run_lab_noop_runner_envelope", _MECHANICAL),
    ("noop_runner_transcript", "capture_lab_noop_runner_transcript", _MECHANICAL),
    ("noop_runner_identity", "bind_lab_noop_runner_identity", _MECHANICAL),
    ("source_mount_readiness", "preflight_lab_source_mount_readiness", _MECHANICAL),
    ("source_mount_contract", "preflight_lab_source_mount_contract", _MECHANICAL),
    ("run_boundary_preflight", "preflight_lab_run_boundary", _MECHANICAL),
    ("probe_execution_boundary", "preflight_lab_sandbox_provider_runtime_probe_execution_boundary", _MECHANICAL),
    ("probe_refuse", "refuse_lab_sandbox_provider_runtime_probe", _MECHANICAL),
    ("request_probe_approval", "request_lab_sandbox_provider_runtime_probe_approval", _REQUEST),
    ("consume_probe_approval", "consume_lab_sandbox_provider_runtime_probe_approval", _CONSUME),
    ("probe_invocation_boundary", "preflight_lab_sandbox_provider_runtime_probe_invocation_boundary", _MECHANICAL),
    (
        "probe_pre_execution_boundary",
        "preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary",
        _MECHANICAL,
    ),
    ("probe_control_binding", "preflight_lab_sandbox_provider_runtime_probe_runner_control_binding", _MECHANICAL),
    ("sandboxed_boundary", "preflight_lab_sandboxed_rebuild_run_test_boundary", _MECHANICAL),
    ("request_sandboxed_approval", "request_lab_sandboxed_rebuild_run_test_approval", _REQUEST),
    ("consume_sandboxed_approval", "consume_lab_sandboxed_rebuild_run_test_approval", _CONSUME),
    ("run_lab_capability", "run_lab_capability", _WRAPPER),
]

_OK_MECHANICAL_STATUSES = frozenset(
    {"planned", "prepared", "blocked", "ready", "needs_approval", "prewritten", "consumed", "completed", "refused"}
)


@dataclass
class IngestAcquisitionStep:
    label: str
    method: str
    kind: str
    status: str = "pending"
    ok: bool = False
    error: str = ""
    blockers: list[str] = field(default_factory=list)
    approval_id: str = ""
    ts: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IngestAcquisitionRun:
    id: str
    source_id: str
    source_path: str
    candidate_id: str
    candidate_name: str
    actor: str
    opt_in: bool
    lab_image: str
    state: str = "pending"
    created_at: str = ""
    updated_at: str = ""
    current_index: int = 0
    active_approval_id: str = ""
    pending_approval_id: str = ""
    approvals: dict[str, str] = field(default_factory=dict)
    classification: dict[str, Any] = field(default_factory=dict)
    steps: list[IngestAcquisitionStep] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [s.to_dict() for s in self.steps]
        return data

    @classmethod
    def from_dict(cls, value: Any) -> "IngestAcquisitionRun | None":
        if not isinstance(value, dict):
            return None
        rid = str(value.get("id") or "").strip()
        if not rid:
            return None
        steps = [
            IngestAcquisitionStep(
                label=str(s.get("label") or ""),
                method=str(s.get("method") or ""),
                kind=str(s.get("kind") or ""),
                status=str(s.get("status") or "pending"),
                ok=bool(s.get("ok", False)),
                error=str(s.get("error") or ""),
                blockers=[str(b) for b in s.get("blockers") or []],
                approval_id=str(s.get("approval_id") or ""),
                ts=str(s.get("ts") or ""),
            )
            for s in value.get("steps") or []
            if isinstance(s, dict)
        ]
        run = cls(
            id=rid,
            source_id=str(value.get("source_id") or ""),
            source_path=str(value.get("source_path") or ""),
            candidate_id=str(value.get("candidate_id") or ""),
            candidate_name=str(value.get("candidate_name") or ""),
            actor=str(value.get("actor") or "francis/system"),
            opt_in=bool(value.get("opt_in", False)),
            lab_image=str(value.get("lab_image") or ""),
            state=str(value.get("state") or "pending"),
            created_at=str(value.get("created_at") or ""),
            updated_at=str(value.get("updated_at") or ""),
            current_index=int(value.get("current_index") or 0),
            active_approval_id=str(value.get("active_approval_id") or ""),
            pending_approval_id=str(value.get("pending_approval_id") or ""),
            approvals={str(k): str(v) for k, v in (value.get("approvals") or {}).items()},
            classification=value.get("classification") or {},
            steps=steps,
            result=value.get("result") or {},
            warnings=[str(w) for w in value.get("warnings") or []],
        )
        return run


def _pending_ids() -> set[str]:
    d = approvals.pending_dir()
    return {p.stem for p in d.glob("*.json")} if d.exists() else set()


def _is_approved(approval_id: str) -> bool:
    if not approval_id:
        return False
    return (approvals.approved_dir() / f"{approval_id}.json").exists()


class IngestAcquisitionOrchestrator:
    """Drives the governed acquisition corridor, pausing at real approval gates."""

    def __init__(self, service: "IngestService", *, provider_dir: Path | None = None) -> None:
        self.svc = service
        # Static provider reference + policy manifest for the provider-* preflights.
        self._provider_dir = provider_dir or (ingest_artifact_root() / "_acquisition_provider")

    # -- public API ----------------------------------------------------------
    def acquire_source_candidate(
        self,
        source_or_path: str | Path,
        candidate_id: str = "",
        *,
        opt_in: bool = False,
        actor: str = "francis/system",
        lab_image: str = "",
    ) -> dict[str, Any]:
        """Start an acquisition. Runs setup + corridor until the first approval gate."""

        source = self.svc._record_from_source_or_path(source_or_path, actor=actor)
        self.svc.inspect_repo(source.canonical_path, actor=actor)
        source = self.svc.sources.get(source.id) or source
        cands = self.svc.extract_candidates(source.id, actor=actor).get("candidates") or []
        candidate = self._select_candidate(source.id, cands, candidate_id, actor=actor)
        if candidate is None:
            return {"ok": False, "status": "failed", "error": "no_candidate_available", "source_id": source.id}

        run = IngestAcquisitionRun(
            id=f"acq_{utc_now().replace(':', '').replace('-', '').replace('+', '')}_{uuid.uuid4().hex[:8]}",
            source_id=source.id,
            source_path=source.canonical_path,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            actor=actor,
            opt_in=opt_in,
            lab_image=lab_image,
            created_at=utc_now(),
            state="running",
        )

        # Runtime-requirement classification (read-only). Gate EXECUTION on
        # default-Lab-incompatible repos; never weaken the Lab.
        repo_map = self.svc._load_repo_map(source)
        if repo_map is not None:
            req = classify_runtime_requirements(repo_map)
            run.classification = req.to_dict()
            needs_execution = bool(getattr(candidate.permissions_required, "execute", False))
            if needs_execution and not req.default_lab_compatible:
                run.warnings.append("execution_candidate_not_default_lab_compatible")
                run.state = "blocked"
                run.result = {
                    "reason": "requires_specialized_lab_profile",
                    "recommended_lab_profile": req.recommended_lab_profile,
                    "executed": False,
                    "network_accessed": False,
                }
                return self._finish(run)

        return self._drive(run)

    def continue_acquisition_after_approval(self, run_id: str, *, actor: str = "") -> dict[str, Any]:
        """Resume a paused run after the operator has approved the pending gate."""

        run = self._load_run(run_id)
        if run is None:
            return {"ok": False, "status": "failed", "error": "acquisition_run_not_found", "id": run_id}
        if run.state != "paused_for_approval":
            return {"ok": False, "status": run.state, "error": "run_not_paused", **run.to_dict()}
        if not _is_approved(run.pending_approval_id):
            # Still waiting on the operator; do not auto-grant.
            return {
                "ok": True,
                "status": "paused_for_approval",
                "error": "approval_not_yet_granted",
                "pending_approval_id": run.pending_approval_id,
                **run.to_dict(),
            }
        # Approval granted: the minted id becomes the active threading id.
        run.active_approval_id = run.pending_approval_id
        run.pending_approval_id = ""
        run.state = "running"
        return self._drive(run)

    # -- internals -----------------------------------------------------------
    def _select_candidate(
        self, source_id: str, cands: list[dict[str, Any]], candidate_id: str, *, actor: str
    ) -> CapabilityCandidate | None:
        target = (candidate_id or "").strip()
        chosen: dict[str, Any] | None = None
        if target:
            chosen = next((c for c in cands if c.get("id") == target or c.get("name") == target), None)
        if chosen is None:
            # Safe default: the always-present read-only inspect candidate.
            chosen = next((c for c in cands if c.get("name") == "inspect_project_structure"), None)
        if chosen is None and cands:
            chosen = cands[0]
        return CapabilityCandidate.from_dict(chosen) if chosen else None

    def _provider_kwargs(self) -> dict[str, str]:
        if self._provider_dir is None:
            return {}
        ref = self._provider_dir / "provider_ref.json"
        manifest = self._provider_dir / "provider_policy.json"
        if not ref.exists():
            ref.parent.mkdir(parents=True, exist_ok=True)
            ref.write_text('{"provider":"docker","kind":"local_cli"}\n', encoding="utf-8")
        if not manifest.exists():
            manifest.write_text(
                '{"network":"deny","filesystem":"readonly_source","destructive":false}\n', encoding="utf-8"
            )
        return {
            "provider_kind": "docker",
            "provider_reference": str(ref),
            "provider_policy_manifest": str(manifest),
        }

    def _call(self, method: str, approval_id: str) -> dict[str, Any]:
        fn = getattr(self.svc, method)
        params = inspect.signature(fn).parameters
        kwargs: dict[str, Any] = {}
        if "actor" in params:
            kwargs["actor"] = self._actor
        if approval_id and "approval_id" in params:
            kwargs["approval_id"] = approval_id
        if method == "run_lab_capability" and "opt_in" in params:
            kwargs["opt_in"] = self._opt_in
        for k, v in self._provider_kwargs().items():
            if k in params:
                kwargs[k] = v
        return fn(self._repo, self._cand_name, **kwargs)

    def _drive(self, run: IngestAcquisitionRun) -> dict[str, Any]:
        self._repo = run.source_path
        self._cand_name = run.candidate_name
        self._actor = run.actor
        self._opt_in = run.opt_in

        while run.current_index < len(_PLAN):
            label, method, kind = _PLAN[run.current_index]
            step = IngestAcquisitionStep(label=label, method=method, kind=kind, ts=utc_now())

            if kind == _REQUEST:
                before = _pending_ids()
                res = self._call(method, run.active_approval_id)
                step.ok = bool(res.get("ok"))
                step.status = str(res.get("status") or "")
                step.error = str(res.get("error") or "")
                step.blockers = [str(b) for b in res.get("blockers") or []]
                minted = sorted(_pending_ids() - before)
                if not step.ok or not minted:
                    step.status = step.status or "failed"
                    run.steps.append(step)
                    run.state = "failed" if not step.ok else "blocked"
                    run.warnings.append(f"approval_request_failed:{label}")
                    return self._finish(run)
                new_id = minted[0]
                step.approval_id = new_id
                run.steps.append(step)
                # Map gate -> A/B/C for readability.
                run.approvals[chr(ord("A") + sum(1 for s in run.steps if s.kind == _REQUEST) - 1)] = new_id
                run.pending_approval_id = new_id
                run.current_index += 1
                run.state = "paused_for_approval"
                return self._finish(run)  # STOP -- operator must approve

            res = self._call(method, run.active_approval_id)
            step.ok = bool(res.get("ok"))
            step.status = str(res.get("status") or "")
            step.error = str(res.get("error") or "")
            step.blockers = [str(b) for b in res.get("blockers") or []]
            step.approval_id = run.active_approval_id
            run.steps.append(step)

            if kind == _WRAPPER:
                run_rec = res.get("lab_execution_run") or {}
                run.result = {
                    "ok": step.ok,
                    "execution_mode": run_rec.get("execution_mode") or res.get("execution_mode"),
                    "exit_code": run_rec.get("exit_code"),
                    "validation_status": run_rec.get("validation_status") or res.get("status"),
                    "executed": run_rec.get("executed", False),
                    "network_accessed": run_rec.get("network_accessed", False),
                    "promotion_from": (res.get("promotion") or {}).get("from_status"),
                    "promotion_to": (res.get("promotion") or {}).get("to_status"),
                    "promoted": (res.get("promotion") or {}).get("promoted", False),
                    "receipt_path": res.get("receipt_path"),
                    "run_artifact_path": res.get("artifact_path"),
                }
                if not step.ok:
                    run.state = "refused" if str(res.get("status")) == "blocked" else "failed"
                elif run.result.get("promoted"):
                    run.state = "promoted"
                elif run.result.get("validation_status") == "VALID":
                    run.state = "completed"
                elif run.result.get("execution_mode") == "real":
                    run.state = "invalid"
                else:
                    run.state = "completed"
                run.current_index += 1
                return self._finish(run)

            if kind == _CONSUME and (not step.ok or step.status != "consumed"):
                run.state = "blocked"
                run.warnings.append(f"approval_consumption_blocked:{label}")
                return self._finish(run)
            if kind == _MECHANICAL and not step.ok and step.status not in _OK_MECHANICAL_STATUSES:
                run.state = "blocked"
                run.warnings.append(f"mechanical_step_blocked:{label}:{step.error}")
                return self._finish(run)

            run.current_index += 1

        run.state = run.state if run.state in ("promoted", "completed", "invalid") else "completed"
        return self._finish(run)

    def _finish(self, run: IngestAcquisitionRun) -> dict[str, Any]:
        run.updated_at = utc_now()
        artifact_path = write_ingest_record_artifact("acquisitions", run.id, {"ingest_acquisition_run": run.to_dict()})
        payload = run.to_dict()
        payload["artifact_path"] = str(artifact_path)
        payload["ok"] = run.state not in ("failed",)
        payload["status"] = run.state
        return payload

    def _load_run(self, run_id: str) -> IngestAcquisitionRun | None:
        from .service_base import _load_ingest_record_payload  # local import to avoid cycle

        data = _load_ingest_record_payload("acquisitions", "ingest_acquisition_run", run_id)
        return IngestAcquisitionRun.from_dict(data)


__all__ = [
    "ACQUISITION_STATES",
    "IngestAcquisitionStep",
    "IngestAcquisitionRun",
    "IngestAcquisitionOrchestrator",
]
