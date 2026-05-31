from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(frozen=True)
class AuthorityRule:
    family: str
    prefixes: tuple[str, ...]
    required_actor: str
    required_scope: str
    approval_requirement: str
    receipt_behavior: str
    denial_behavior: str
    governance_maturity: str
    notes: str = ""


_RULES: tuple[AuthorityRule, ...] = (
    AuthorityRule(
        family="operations_read_batch",
        prefixes=("/operations/get_many",),
        required_actor="none",
        required_scope="none_read_only_batch_lookup",
        approval_requirement="not_required_read_projection",
        receipt_behavior="none_read_projection",
        denial_behavior="invalid ids return item-level not_found or invalid_operation_id metadata",
        governance_maturity="read_projection_using_post",
        notes="POST is used to carry a bounded id list; the route does not mutate operations.",
    ),
    AuthorityRule(
        family="executor_substrate",
        prefixes=("/executor/substrate/stage-closure-decision",),
        required_actor="payload.actor",
        required_scope="executor.stage8.closure.write",
        approval_requirement="this is the Stage 8 operator closure decision route",
        receipt_behavior="stage8 operator stage closure decision receipt",
        denial_behavior="api_permission_denied via permission_gate before closure receipt write",
        governance_maturity="permission_gated",
        notes="Closure receipt does not mutate runtime stage state or grant execution authority.",
    ),
    AuthorityRule(
        family="takeover",
        prefixes=("/takeover/control-transfer",),
        required_actor="payload.actor",
        required_scope="takeover.control.write",
        approval_requirement="explicit Pilot control-transfer receipt; Stage 8 closure receipt required first",
        receipt_behavior="stage9 takeover control-transfer receipt",
        denial_behavior="api_permission_denied via permission_gate before control-transfer receipt write",
        governance_maturity="permission_gated",
        notes="Control transfer lights Pilot mode but does not run tools, run shell, or grant executor authority.",
    ),
    AuthorityRule(
        family="takeover",
        prefixes=("/takeover/panic-stop",),
        required_actor="payload.actor",
        required_scope="takeover.panic.write",
        approval_requirement="panic stop is explicit actor-scoped Pilot revocation",
        receipt_behavior="stage9 takeover panic-stop receipt",
        denial_behavior="api_permission_denied via permission_gate before panic-stop receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Panic stop revokes Pilot control mode and cancels only active operations captured in the "
            "control-transfer action-feed receipt."
        ),
    ),
    AuthorityRule(
        family="takeover",
        prefixes=("/takeover/delegated-action",),
        required_actor="payload.actor",
        required_scope="takeover.action.write",
        approval_requirement="active Stage 9 control-transfer receipt required before delegated action execution",
        receipt_behavior="stage9 takeover live-action receipt",
        denial_behavior="api_permission_denied via permission_gate before delegated action execution",
        governance_maturity="permission_gated",
        notes="Delegated action is limited to allowlisted executor operations and does not run shell or grant authority.",
    ),
    AuthorityRule(
        family="takeover",
        prefixes=("/takeover/stage-closure-decision",),
        required_actor="payload.actor",
        required_scope="takeover.stage9.closure.write",
        approval_requirement="this is the Stage 9 operator closure decision route after completion review readiness",
        receipt_behavior="stage9 takeover operator stage closure decision receipt",
        denial_behavior="api_permission_denied via permission_gate before stage closure receipt write",
        governance_maturity="permission_gated",
        notes="Closure receipt does not mutate runtime stage state or grant execution authority.",
    ),
    AuthorityRule(
        family="takeover",
        prefixes=("/takeover/handback-summary",),
        required_actor="payload.actor",
        required_scope="takeover.handback.write",
        approval_requirement="control-transfer receipt required before handback summary",
        receipt_behavior="stage9 takeover handback-summary receipt",
        denial_behavior="api_permission_denied via permission_gate before handback-summary receipt write",
        governance_maturity="permission_gated",
        notes="Handback summary transfers control back to Assist and reports proof handles without executing work.",
    ),
    AuthorityRule(
        family="away",
        prefixes=("/away/live-progress-sample",),
        required_actor="payload.actor",
        required_scope="away.progress.write",
        approval_requirement="Stage 9 closure and Stage 10 groundwork must be ready before sample receipt write",
        receipt_behavior="Stage 10 Away live-progress sample receipt",
        denial_behavior="api_permission_denied via permission_gate before receipt write",
        governance_maturity="permission_gated",
        notes="The sample is grounded in existing Away readbacks and does not activate autonomy or run tools.",
    ),
    AuthorityRule(
        family="apprenticeship",
        prefixes=("/apprenticeship/teaching-session",),
        required_actor="payload.actor",
        required_scope="apprenticeship.teaching_session.write",
        approval_requirement="not_required_scope_gate_only; explicit teaching-session receipt payload required",
        receipt_behavior="Stage 11 Apprenticeship teaching-session receipt",
        denial_behavior="api_permission_denied via permission_gate before teaching-session receipt write",
        governance_maturity="permission_gated",
        notes=(
            "The receipt records explicit operator-supplied teaching context only; it does not write memory, "
            "run tools, run shell, or create Forge artifacts."
        ),
    ),
    AuthorityRule(
        family="apprenticeship",
        prefixes=("/apprenticeship/replay-receipt",),
        required_actor="payload.actor",
        required_scope="apprenticeship.replay_receipt.write",
        approval_requirement="not_required_scope_gate_only; prior teaching-session receipt required",
        receipt_behavior="Stage 11 Apprenticeship replay/generalization review receipt",
        denial_behavior="api_permission_denied via permission_gate before replay receipt write",
        governance_maturity="permission_gated",
        notes=(
            "The receipt records explicit operator review of replay/generalization only; it does not execute replay, "
            "write memory, run tools, run shell, or create Forge artifacts."
        ),
    ),
    AuthorityRule(
        family="apprenticeship",
        prefixes=("/apprenticeship/skillization-artifact-receipt",),
        required_actor="payload.actor",
        required_scope="apprenticeship.skillization_artifact.write",
        approval_requirement="not_required_scope_gate_only; prior replay receipt required",
        receipt_behavior="Stage 11 Apprenticeship skillization artifact review receipt",
        denial_behavior="api_permission_denied via permission_gate before skillization artifact receipt write",
        governance_maturity="permission_gated",
        notes=(
            "The receipt records an operator-reviewed skillization artifact candidate only; it does not write memory, "
            "write a skill artifact, promote to Forge, run tools, or grant authority."
        ),
    ),
    AuthorityRule(
        family="away",
        prefixes=("/away/stage-closure-decision",),
        required_actor="payload.actor",
        required_scope="away.stage10.closure.write",
        approval_requirement="this is the Stage 10 operator closure decision route after completion review readiness",
        receipt_behavior="Stage 10 Away operator stage closure decision receipt",
        denial_behavior="api_permission_denied via permission_gate before stage closure receipt write",
        governance_maturity="permission_gated",
        notes="Closure receipt does not mutate runtime stage state or grant execution authority.",
    ),
    AuthorityRule(
        family="supervised_exec",
        prefixes=("/operations/supervised-exec",),
        required_actor="payload.actor",
        required_scope="codex.supervised_exec",
        approval_requirement="payload.approval_id is passed into supervised_exec runtime when required",
        receipt_behavior="supervised_exec result and runtime artifacts",
        denial_behavior="api_permission_denied via permission_gate before execution",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="trust",
        prefixes=("/system/trust", "/trust"),
        required_actor="payload.actor",
        required_scope="trust.write",
        approval_requirement="not_required_scope_gate_only",
        receipt_behavior="trust state/audit artifact",
        denial_behavior="api_permission_denied via permission_gate before mutation",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="web_learning",
        prefixes=("/system/web-learning", "/system/web_learning", "/web-learning", "/web_learning"),
        required_actor="payload.request_actor, payload.api_actor, payload.actor, or api default",
        required_scope="web_learning.write",
        approval_requirement="route-specific approval_store remains required for approval-bound learn/quarantine/config actions",
        receipt_behavior="web_learning registry events and quarantine/request records",
        denial_behavior="api_permission_denied via permission_gate before web-learning mutation or force handling",
        governance_maturity="permission_and_policy_gated",
        notes="API actor scope is checked before route-specific policy/approval logic and before honoring force metadata.",
    ),
    AuthorityRule(
        family="system",
        prefixes=("/system",),
        required_actor="payload.actor",
        required_scope="system.write",
        approval_requirement="not_required_scope_gate_and_operator_posture",
        receipt_behavior="audit receipt or runtime state metadata depending on route",
        denial_behavior="api_permission_denied via permission_gate before mutation",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="chat",
        prefixes=("/chat/send",),
        required_actor="payload.request_actor, payload.api_actor, payload.actor, or api.chat default for generic chat; internal chat.send for /mission ingress",
        required_scope="chat.write for generic chat; missions.write for /mission ingress",
        approval_requirement="mission gates apply after /mission ingress; generic chat does not approve",
        receipt_behavior="conversation ledger; mission ingress can create mission/operation receipts",
        denial_behavior="api_permission_denied via permission_gate before generic ledger write; permission_gate or operator_posture denial for mission ingress",
        governance_maturity="permission_gated",
        notes="Generic chat ledger writes are scoped separately from mission declaration authority.",
    ),
    AuthorityRule(
        family="attachments",
        prefixes=("/attachments/upload",),
        required_actor="multipart request_actor, actor, or api.attachments default",
        required_scope="attachments.write",
        approval_requirement="not_required_currently",
        receipt_behavior="stored upload path and byte count only",
        denial_behavior="api_permission_denied via permission_gate before reading or writing upload bytes",
        governance_maturity="permission_gated",
        notes="Filename and size remain bounded; upload bytes require explicit API actor scope before persistence.",
    ),
    AuthorityRule(
        family="approval_request",
        prefixes=("/approvals/request",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="approvals.request",
        approval_requirement="creates pending approval after request-scope gate; does not decide it",
        receipt_behavior="pending approval record",
        denial_behavior="api_permission_denied via permission_gate before pending approval record write",
        governance_maturity="permission_gated",
        notes="Requesting an approval remains lower authority than deciding an approval.",
    ),
    AuthorityRule(
        family="approval_decision",
        prefixes=("/approvals/decision",),
        required_actor="payload.actor",
        required_scope="approvals.decide or delegated builder/operator authority",
        approval_requirement="this is the approval decision route",
        receipt_behavior="approval decision record and delegated approval receipt when applicable",
        denial_behavior="local-client gate and api_permission_denied via permission_gate before decision",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="plugins",
        prefixes=("/plugins",),
        required_actor="payload.actor",
        required_scope="plugins.write",
        approval_requirement="plugin run/promotion flows may require approval or proposal review receipts",
        receipt_behavior="plugin validation, proposal review, promotion, or run receipt depending on route",
        denial_behavior="api_permission_denied via permission_gate before lifecycle mutation",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="domains",
        prefixes=("/domains",),
        required_actor="payload.actor",
        required_scope="domains.write",
        approval_requirement="not_required_scope_gate_only",
        receipt_behavior="domain registry metadata",
        denial_behavior="api_permission_denied via permission_gate before mutation",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="operations",
        prefixes=("/operations",),
        required_actor="payload.actor",
        required_scope="operations.write or operations.run depending on route",
        approval_requirement="operation execution may require operation-level approval gates",
        receipt_behavior="operation record, run ledger, trace, and artifact metadata depending on route",
        denial_behavior="api_permission_denied via permission_gate before mutation or execution",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="credentials",
        prefixes=("/credentials",),
        required_actor="payload.actor",
        required_scope="credentials.write",
        approval_requirement="credential request/revoke workflow is approval-aware",
        receipt_behavior="credential request or revoke artifact",
        denial_behavior="api_permission_denied via permission_gate before mutation",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="federation",
        prefixes=("/federation",),
        required_actor="payload.request_actor, payload.api_actor, payload.actor, or api.federation default",
        required_scope="federation.write",
        approval_requirement="not_required_scope_gate_only",
        receipt_behavior="federation registry record",
        denial_behavior="api_permission_denied via permission_gate before registry load/save",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="forge",
        prefixes=("/forge",),
        required_actor="payload.actor",
        required_scope="plugins.write",
        approval_requirement="proposal decision receipt required for governed proposal review",
        receipt_behavior="plugin proposal review receipt",
        denial_behavior="api_permission_denied via permission_gate before proposal decision",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="explanation",
        prefixes=("/explanations", "/explanation"),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="explanation.write",
        approval_requirement="not_required_currently; explicit API actor scope required",
        receipt_behavior="explanation registry record",
        denial_behavior="api_permission_denied via permission_gate before registry load/save",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="memory_timeline",
        prefixes=("/memory/timeline",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="memory.timeline.write",
        approval_requirement="not_required_currently; explicit API actor scope required",
        receipt_behavior="memory timeline event record",
        denial_behavior="api_permission_denied via permission_gate before registry load/save",
        governance_maturity="permission_gated",
        notes="Event actor remains provenance; request_actor/api_actor can carry the API caller identity for scoped writes.",
    ),
    AuthorityRule(
        family="missions",
        prefixes=("/missions",),
        required_actor="payload.actor or requester/owner actor for create",
        required_scope="missions.write",
        approval_requirement="mission operations may become approval-gated before execution",
        receipt_behavior="mission state, operation linkage, memory receipt, trace/run metadata depending on route",
        denial_behavior="api_permission_denied via permission_gate before mutation",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="reactor",
        prefixes=("/reactor",),
        required_actor="payload.actor",
        required_scope="reactor.write",
        approval_requirement="not_required_scope_gate_only",
        receipt_behavior="reactor retry/deadletter/event record",
        denial_behavior="api_permission_denied via permission_gate before mutation",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="lens",
        prefixes=("/lens",),
        required_actor="payload.actor",
        required_scope="lens-specific authority approval; often system.write-backed approval request",
        approval_requirement="approval_id or authority grant receipt required for authority/execution routes",
        receipt_behavior="Lens authority grant, denial, readiness, or execution receipt",
        denial_behavior="route-specific approval/authority denial before runtime mutation",
        governance_maturity="approval_and_receipt_gated",
    ),
    AuthorityRule(
        family="telemetry_context_feedback_memory_quality",
        prefixes=("/telemetry/context/feedback/memory-quality",),
        required_actor="payload.actor",
        required_scope="memory.timeline.write",
        approval_requirement="not_required_scope_gate_only; explicit operator decision payload required",
        receipt_behavior="memory timeline event record with telemetry feedback quality aggregate",
        denial_behavior="api_permission_denied via permission_gate before memory timeline write",
        governance_maturity="permission_gated",
        notes="GET remains read-only; POST writes only bounded aggregate feedback quality through the memory timeline contract.",
    ),
    AuthorityRule(
        family="telemetry_context_feedback",
        prefixes=("/telemetry/context/feedback",),
        required_actor="payload.actor",
        required_scope="telemetry.context.feedback.write",
        approval_requirement="not_required_scope_gate_only",
        receipt_behavior="redacted explicit feedback event",
        denial_behavior="api_permission_denied via permission_gate before telemetry write",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="telemetry_terminal",
        prefixes=("/telemetry/terminal/events",),
        required_actor="payload.actor",
        required_scope="telemetry.terminal.write",
        approval_requirement="not_required_scope_gate_only",
        receipt_behavior="redacted terminal telemetry event",
        denial_behavior="api_permission_denied via permission_gate before telemetry write",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="telemetry_ide_diagnostics",
        prefixes=("/telemetry/ide-diagnostics/events",),
        required_actor="payload.actor",
        required_scope="telemetry.ide_diagnostics.write",
        approval_requirement="not_required_scope_gate_only",
        receipt_behavior="redacted IDE diagnostic telemetry event",
        denial_behavior="api_permission_denied via permission_gate before telemetry write",
        governance_maturity="permission_gated",
    ),
    AuthorityRule(
        family="industrial",
        prefixes=("/industrial",),
        required_actor="payload.request_actor, payload.api_actor, payload.actor, payload.requested_by, or api.industrial default",
        required_scope="industrial.write",
        approval_requirement="exact-action approval-store checks remain required for safety/intervention/digital-twin actions",
        receipt_behavior="industrial registry, safety validation, run, intervention, or digital-twin action record",
        denial_behavior="api_permission_denied via permission_gate before registry mutation or approval request creation",
        governance_maturity="permission_and_policy_gated",
        notes="API actor scope is checked before industrial registry writes and before exact-action approval requests.",
    ),
)


def _path_matches(rule: AuthorityRule, path: str) -> bool:
    for prefix in rule.prefixes:
        if path == prefix or path.startswith(f"{prefix}/"):
            return True
    return False


def _best_rule(path: str) -> AuthorityRule | None:
    matches = [rule for rule in _RULES if _path_matches(rule, path)]
    if not matches:
        return None
    return max(matches, key=lambda rule: max(len(prefix) for prefix in rule.prefixes))


def _route_methods(route: Any) -> list[str]:
    methods = getattr(route, "methods", None)
    if not methods:
        return []
    return sorted(method for method in methods if method in MUTATING_METHODS)


def _route_endpoint(route: Any) -> Any:
    return getattr(route, "endpoint", None)


def build_mutating_route_authority_matrix(routes: Iterable[Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    for route in routes:
        path = str(getattr(route, "path", "") or "").strip()
        if not path:
            continue
        methods = _route_methods(route)
        if not methods:
            continue

        endpoint = _route_endpoint(route)
        endpoint_name = str(getattr(route, "name", "") or getattr(endpoint, "__name__", "") or "").strip()
        endpoint_module = str(getattr(endpoint, "__module__", "") or "").strip()
        rule = _best_rule(path)
        if rule is None:
            for method in methods:
                missing.append({"method": method, "path": path, "endpoint": endpoint_name})
            continue

        for method in methods:
            entries.append(
                {
                    "method": method,
                    "path": path,
                    "endpoint": endpoint_name,
                    "module": endpoint_module,
                    "family": rule.family,
                    "required_actor": rule.required_actor,
                    "required_scope": rule.required_scope,
                    "approval_requirement": rule.approval_requirement,
                    "receipt_behavior": rule.receipt_behavior,
                    "denial_behavior": rule.denial_behavior,
                    "governance_maturity": rule.governance_maturity,
                    "notes": rule.notes,
                }
            )

    entries.sort(key=lambda item: (item["path"], item["method"], item["endpoint"]))
    missing.sort(key=lambda item: (item["path"], item["method"], item["endpoint"]))
    maturity_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for item in entries:
        maturity = str(item["governance_maturity"])
        family = str(item["family"])
        maturity_counts[maturity] = maturity_counts.get(maturity, 0) + 1
        family_counts[family] = family_counts.get(family, 0) + 1

    return {
        "ok": not missing,
        "kind": "francis.api.mutating_route_authority_matrix",
        "status": "covered" if not missing else "coverage_gap",
        "total": len(entries),
        "missing_total": len(missing),
        "entries": entries,
        "missing": missing,
        "summary": {
            "maturity_counts": dict(sorted(maturity_counts.items())),
            "family_counts": dict(sorted(family_counts.items())),
            "generated_from": "FastAPI route table plus static authority rules",
            "write_behavior_changed": False,
            "read_only_projection": True,
        },
    }
