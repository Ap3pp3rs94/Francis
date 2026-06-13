"""Forge synthesis orchestrator: ingest *pushes* native synthesis end-to-end.

Where the acquisition orchestrator drives the governed Lab corridor for a
candidate, this orchestrator drives the governed *synthesis* corridor: it makes
ingest push a candidate through

    compile spec -> builder proposal -> digest-gated review -> apply preflight
    -> [PAUSE at the real francis.forge.apply operator gate] -> resume after
       operator approval -> consume -> apply boundary (refusal) -> validation plan

It only sequences the corridor between gates; it never removes or auto-grants a
gate (`approvals.decide` is never called here), never applies a patch, never runs
a command, never validates or promotes. Real apply stays impossible by
construction -- the boundary refuses until a separate governed applier exists.

Ingest is a *capability* of Francis, not Francis authority.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from francis.governance import approvals

from .registry import utc_now, write_ingest_record_artifact

if TYPE_CHECKING:
    from .service import IngestService

SYNTHESIS_STATES = (
    "pending",
    "running",
    "paused_for_approval",
    "blocked",
    "refused",
    "indeterminate",
    "failed",
    "completed",
)


@dataclass
class ForgeSynthesisStep:
    label: str
    status: str = "pending"
    ok: bool = False
    detail: str = ""
    ts: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ForgeSynthesisRun:
    id: str
    source_id: str
    source_path: str
    candidate_id: str
    candidate_name: str
    actor: str
    state: str = "pending"
    created_at: str = ""
    updated_at: str = ""
    spec_id: str = ""
    builder_run_id: str = ""
    review_verdict: str = ""
    pending_approval_id: str = ""
    approval_id: str = ""
    steps: list[ForgeSynthesisStep] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [s.to_dict() for s in self.steps]
        return data

    @classmethod
    def from_dict(cls, value: Any) -> "ForgeSynthesisRun | None":
        if not isinstance(value, dict):
            return None
        rid = str(value.get("id") or "").strip()
        if not rid:
            return None
        steps = [
            ForgeSynthesisStep(
                label=str(s.get("label") or ""),
                status=str(s.get("status") or "pending"),
                ok=bool(s.get("ok", False)),
                detail=str(s.get("detail") or ""),
                ts=str(s.get("ts") or ""),
            )
            for s in value.get("steps") or []
            if isinstance(s, dict)
        ]
        return cls(
            id=rid,
            source_id=str(value.get("source_id") or ""),
            source_path=str(value.get("source_path") or ""),
            candidate_id=str(value.get("candidate_id") or ""),
            candidate_name=str(value.get("candidate_name") or ""),
            actor=str(value.get("actor") or "francis/system"),
            state=str(value.get("state") or "pending"),
            created_at=str(value.get("created_at") or ""),
            updated_at=str(value.get("updated_at") or ""),
            spec_id=str(value.get("spec_id") or ""),
            builder_run_id=str(value.get("builder_run_id") or ""),
            review_verdict=str(value.get("review_verdict") or ""),
            pending_approval_id=str(value.get("pending_approval_id") or ""),
            approval_id=str(value.get("approval_id") or ""),
            steps=steps,
            result=value.get("result") or {},
            warnings=[str(w) for w in value.get("warnings") or []],
        )


def _is_approved(approval_id: str) -> bool:
    if not approval_id:
        return False
    return (approvals.approved_dir() / f"{approval_id}.json").exists()


class ForgeSynthesisOrchestrator:
    """Drives the governed synthesis corridor, pausing at the real apply gate."""

    def __init__(self, service: "IngestService") -> None:
        self.svc = service

    # -- public API ----------------------------------------------------------
    def synthesize_capability(
        self,
        source_or_path: str | Path,
        candidate_ref: str = "",
        *,
        actor: str = "francis/system",
        builder_client: Any | None = None,
        allowed_files: list[str] | None = None,
        forbidden_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """Push a candidate through synthesis to the apply approval gate."""

        source = self.svc._record_from_source_or_path(source_or_path, actor=actor)
        self.svc.inspect_repo(source.canonical_path, actor=actor)
        source = self.svc.sources.get(source.id) or source
        candidate = self.svc._candidate_from_ref(source, candidate_ref or "inspect_project_structure", actor=actor)
        if candidate is None:
            return {"ok": False, "status": "failed", "error": "no_candidate_available", "source_id": source.id}

        run = ForgeSynthesisRun(
            id=f"synth_{utc_now().replace(':', '').replace('-', '').replace('+', '')}_{uuid.uuid4().hex[:8]}",
            source_id=source.id,
            source_path=source.canonical_path,
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            actor=actor,
            created_at=utc_now(),
            state="running",
        )
        return self._drive_to_gate(
            run,
            builder_client=builder_client,
            allowed_files=allowed_files,
            forbidden_files=forbidden_files,
        )

    def continue_synthesis_after_approval(self, run_id: str, *, actor: str = "francis/system") -> dict[str, Any]:
        run = self._load_run(run_id)
        if run is None:
            return {"ok": False, "status": "failed", "error": "synthesis_run_not_found", "id": run_id}
        if run.state != "paused_for_approval":
            return {"ok": False, "status": run.state, "error": "run_not_paused", **run.to_dict()}
        if not _is_approved(run.pending_approval_id):
            return {
                "ok": True,
                "status": "paused_for_approval",
                "error": "approval_not_yet_granted",
                "pending_approval_id": run.pending_approval_id,
                **run.to_dict(),
            }
        run.approval_id = run.pending_approval_id
        run.pending_approval_id = ""
        run.state = "running"
        return self._resume_after_gate(run)

    # -- internals -----------------------------------------------------------
    def _step(self, run: ForgeSynthesisRun, label: str, ok: bool, status: str, detail: str = "") -> None:
        run.steps.append(ForgeSynthesisStep(label=label, status=status, ok=ok, detail=detail, ts=utc_now()))

    def _drive_to_gate(
        self,
        run: ForgeSynthesisRun,
        *,
        builder_client: Any | None,
        allowed_files: list[str] | None,
        forbidden_files: list[str] | None,
    ) -> dict[str, Any]:
        repo = run.source_path
        cand = run.candidate_name

        # 1. Compile a Francis-native capability spec (deterministic).
        spec_res = self.svc.compile_capability_spec(
            repo, cand, actor=run.actor, allowed_files=allowed_files, forbidden_files=forbidden_files
        )
        if not spec_res.get("ok"):
            self._step(run, "compile_spec", False, str(spec_res.get("status")), str(spec_res.get("error")))
            run.state = "blocked"
            run.warnings.append("compile_spec_failed")
            return self._finish(run)
        run.spec_id = str((spec_res.get("capability_spec") or {}).get("id") or "")
        self._step(run, "compile_spec", True, "compiled", run.spec_id)

        # 2. Builder proposal (localhost Ollama, or injected client for tests).
        builder = self.svc._run_builder_for_synthesis(
            repo,
            cand,
            actor=run.actor,
            client=builder_client,
            allowed_files=allowed_files,
            forbidden_files=forbidden_files,
        )
        builder_status = str(builder.get("status"))
        run.builder_run_id = str((builder.get("builder_run") or {}).get("builder_run_id") or "")
        if not builder.get("ok") or builder_status not in ("proposed", "completed"):
            self._step(run, "builder_proposal", False, builder_status, run.builder_run_id)
            run.state = "blocked"
            run.warnings.append(f"builder_unavailable:{builder_status}")
            run.result = {"builder_status": builder_status, "patch_applied": False, "executed": False}
            return self._finish(run)
        proposal_text = str(builder.get("proposed_patch_text") or builder.get("plan_text") or "")
        self._step(run, "builder_proposal", True, builder_status, run.builder_run_id)

        # 3. Digest-gated review of the FULL proposal text.
        review = self.svc.review_builder_proposal(repo, run.builder_run_id, proposal_text, actor=run.actor)
        run.review_verdict = str(review.get("verdict"))
        self._step(run, "review", review.get("verdict") == "clean", run.review_verdict, "")
        if run.review_verdict != "clean":
            run.state = "indeterminate" if run.review_verdict == "indeterminate" else "blocked"
            run.warnings.append(f"review_not_clean:{run.review_verdict}")
            run.result = {
                "review_verdict": run.review_verdict,
                "blockers": (review.get("builder_proposal_review") or {}).get("blockers", []),
                "patch_applied": False,
                "executed": False,
            }
            return self._finish(run)

        # 4. Apply preflight (exact-action projection).
        pf = self.svc.preflight_forge_apply(repo, run.builder_run_id, actor=run.actor)
        if pf.get("status") != "needs_approval":
            self._step(run, "apply_preflight", False, str(pf.get("status")), "")
            run.state = "blocked"
            run.warnings.append("apply_preflight_not_ready")
            return self._finish(run)
        self._step(run, "apply_preflight", True, "needs_approval", "")

        # 5. Request the real operator apply approval, then STOP.
        rq = self.svc.request_forge_apply_approval(repo, run.builder_run_id, actor=run.actor)
        approval_id = str((rq.get("forge_apply_approval_request") or {}).get("approval_id") or "")
        if not approval_id:
            self._step(run, "request_apply_approval", False, str(rq.get("status")), "")
            run.state = "blocked"
            run.warnings.append("apply_approval_request_failed")
            return self._finish(run)
        self._step(run, "request_apply_approval", True, "needs_approval", approval_id)
        run.pending_approval_id = approval_id
        run.state = "paused_for_approval"
        return self._finish(run)  # operator must approve francis.forge.apply

    def _resume_after_gate(self, run: ForgeSynthesisRun) -> dict[str, Any]:
        repo = run.source_path

        # 6. Consume the approved exact-action approval (single-use).
        consume = self.svc.consume_forge_apply_approval(repo, run.builder_run_id, run.approval_id, actor=run.actor)
        if consume.get("status") != "consumed":
            self._step(run, "consume_apply_approval", False, str(consume.get("status")), "")
            run.state = "blocked"
            run.warnings.append("apply_approval_consumption_blocked")
            return self._finish(run)
        self._step(run, "consume_apply_approval", True, "consumed", run.approval_id)

        # 7. Apply boundary -- refused (no governed applier exists).
        boundary = self.svc.boundary_forge_apply(repo, run.builder_run_id, run.approval_id, actor=run.actor)
        self._step(run, "apply_boundary", False, str(boundary.get("status")), "apply_refused")

        # 8. Validation plan projection (runs nothing).
        plan = self.svc.plan_forge_validation(repo, run.builder_run_id, actor=run.actor)
        self._step(run, "validation_plan", True, str(plan.get("status")), "")

        run.state = "refused"  # the honest terminal state: approved, consumed, apply refused
        run.result = {
            "review_verdict": run.review_verdict,
            "apply_refused": True,
            "patch_applied": False,
            "wrote_to_repo": False,
            "executed": False,
            "candidate_validated": False,
            "capability_promoted": False,
            "validation_plan_id": str((plan.get("forge_validation_plan") or {}).get("id") or ""),
        }
        return self._finish(run)

    def _finish(self, run: ForgeSynthesisRun) -> dict[str, Any]:
        run.updated_at = utc_now()
        artifact_path = write_ingest_record_artifact(
            "forge_synthesis_runs", run.id, {"forge_synthesis_run": run.to_dict()}
        )
        payload = run.to_dict()
        payload["artifact_path"] = str(artifact_path)
        payload["ok"] = run.state not in ("failed",)
        payload["status"] = run.state
        return payload

    def _load_run(self, run_id: str) -> ForgeSynthesisRun | None:
        from .service_base import _load_ingest_record_payload

        data = _load_ingest_record_payload("forge_synthesis_runs", "forge_synthesis_run", run_id)
        return ForgeSynthesisRun.from_dict(data)


__all__ = [
    "SYNTHESIS_STATES",
    "ForgeSynthesisOrchestrator",
    "ForgeSynthesisRun",
    "ForgeSynthesisStep",
]
