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
        family="compute_substrate",
        prefixes=("/compute-substrate/submit",),
        required_actor="payload.actor_id",
        required_scope="compute:submit",
        approval_requirement=(
            "API permission allows only substrate submission; approval_required tasks still require a valid "
            "compute approval grant consumed by the substrate"
        ),
        receipt_behavior="compute capability receipt plus bounded compute status record when stores are configured",
        denial_behavior=(
            "api_permission_denied via permission_gate before service submission; substrate denials remain "
            "reported by ComputeSubstrateService"
        ),
        governance_maturity="permission_and_substrate_gated",
        notes=(
            "Route submits only through ComputeSubstrateService. It does not call SafeLocalBackend or "
            "SubstrateGovernor directly, return raw output, run shell/subprocess/network/GPU work, start "
            "background workers, or grant new execution authority."
        ),
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
        family="apprenticeship_game_teaching",
        prefixes=(
            "/apprenticeship/game-teaching-session/start",
            "/apprenticeship/game-teaching-session/stop",
        ),
        required_actor="payload.actor",
        required_scope="apprenticeship.game_teaching_session.write",
        approval_requirement=(
            "not_required_scope_gate_only; explicit target, intent, scope, success condition, and start or stop "
            "request required"
        ),
        receipt_behavior="game-teaching start receipt or review-required semantic episode receipt",
        denial_behavior="api_permission_denied via permission_gate before session state or receipt write",
        governance_maturity="permission_gated_bounded_semantic_observation",
        notes=(
            "The session records only allowlisted semantic scene transitions from Lens game observations; it does "
            "not persist raw pixels, capture input, execute replay, write memory, learn a policy, or promote a skill."
        ),
    ),
    AuthorityRule(
        family="apprenticeship_game_episode_review",
        prefixes=("/apprenticeship/game-teaching-episode/{episode_receipt_id}/review",),
        required_actor="payload.actor",
        required_scope="apprenticeship.game_teaching_episode_review.write",
        approval_requirement=(
            "not_required_scope_gate_only; a digest-valid nonempty game-teaching episode and explicit operator "
            "review decision are required"
        ),
        receipt_behavior="append-only game-teaching semantic replay review receipt with source episode digest",
        denial_behavior="api_permission_denied via permission_gate before operator review receipt write",
        governance_maturity="permission_gated_semantic_replay_review",
        notes=(
            "The route records operator review or corrections against a deterministic semantic replay; it does not "
            "execute input, mutate the source episode, generalize a policy, write memory, or promote a skill."
        ),
    ),
    AuthorityRule(
        family="apprenticeship_game_generalization",
        prefixes=("/apprenticeship/game-teaching-episode/{episode_receipt_id}/generalization-proposal",),
        required_actor="payload.actor",
        required_scope="apprenticeship.game_teaching_generalization.write",
        approval_requirement=(
            "not_required_scope_gate_only; a digest-valid operator-accepted semantic replay and explicit proposal "
            "request are required"
        ),
        receipt_behavior=(
            "digest-pinned game-teaching generalization proposal with episode, review, and replay lineage"
        ),
        denial_behavior="api_permission_denied via permission_gate before generalization proposal receipt write",
        governance_maturity="permission_gated_generalization_proposal_only",
        notes=(
            "The route extracts an inspectable semantic progression hypothesis only; it does not infer player "
            "controls, learn a gameplay policy, execute input, write memory, skillize, or promote a capability."
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
        family="apprenticeship",
        prefixes=("/apprenticeship/forge-handoff-receipt",),
        required_actor="payload.actor",
        required_scope="apprenticeship.forge_handoff.write",
        approval_requirement="not_required_scope_gate_only; prior skillization artifact receipt required",
        receipt_behavior="Stage 11 Apprenticeship Forge handoff review receipt",
        denial_behavior="api_permission_denied via permission_gate before Forge handoff receipt write",
        governance_maturity="permission_gated",
        notes=(
            "The receipt records operator review of a Forge proposal candidate boundary only; it does not write a "
            "Forge proposal, promote to Forge, register a capability, run tools, or grant authority."
        ),
    ),
    AuthorityRule(
        family="apprenticeship",
        prefixes=("/apprenticeship/stage-closure-decision",),
        required_actor="payload.actor",
        required_scope="apprenticeship.stage11.closure.write",
        approval_requirement="this is the Stage 11 operator closure decision route after completion review readiness",
        receipt_behavior="Stage 11 Apprenticeship operator stage closure decision receipt",
        denial_behavior="api_permission_denied via permission_gate before stage closure receipt write",
        governance_maturity="permission_gated",
        notes="Closure receipt does not mutate runtime stage state, write memory, promote to Forge, or grant authority.",
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
        family="knowledge_fabric",
        prefixes=("/knowledge-fabric/stage-closure-decision",),
        required_actor="payload.actor",
        required_scope="knowledge_fabric.stage12.closure.write",
        approval_requirement="this is the Stage 12 operator closure decision route after completion review readiness",
        receipt_behavior="Stage 12 Knowledge Fabric operator stage closure decision receipt",
        denial_behavior="api_permission_denied via permission_gate before stage closure receipt write",
        governance_maturity="permission_gated",
        notes="Closure receipt does not mutate runtime stage state, write memory, or write the index.",
    ),
    AuthorityRule(
        family="trust_calibration",
        prefixes=("/trust-calibration/evaluate-claim",),
        required_actor="none",
        required_scope="none_read_only_claim_evaluation_projection",
        approval_requirement="not_required_read_projection",
        receipt_behavior="none_read_projection",
        denial_behavior="malformed claims return bounded evaluation metadata",
        governance_maturity="read_projection_using_post",
        notes="POST carries a bounded claim payload for evaluation; it does not write trust calibration state.",
    ),
    AuthorityRule(
        family="trust_calibration",
        prefixes=("/trust-calibration/operator-browser-visual-readback",),
        required_actor="payload.actor",
        required_scope="trust_calibration.browser_visual_readback.write",
        approval_requirement="explicit operator browser visual readback for Stage 13 calibration evidence",
        receipt_behavior="Stage 13 operator browser visual readback receipt",
        denial_behavior="api_permission_denied via permission_gate before visual readback receipt write",
        governance_maturity="permission_gated",
        notes="Receipt records operator visual readback only; it does not launch a browser or grant execution authority.",
    ),
    AuthorityRule(
        family="trust_calibration",
        prefixes=("/trust-calibration/stage-closure-decision",),
        required_actor="payload.actor",
        required_scope="trust_calibration.stage13.closure.write",
        approval_requirement="this is the Stage 13 operator closure decision route after completion review readiness",
        receipt_behavior="Stage 13 Trust Calibration operator stage closure decision receipt",
        denial_behavior="api_permission_denied via permission_gate before stage closure receipt write",
        governance_maturity="permission_gated",
        notes="Closure receipt does not mutate runtime stage state or write memory.",
    ),
    AuthorityRule(
        family="adversarial_hardening",
        prefixes=("/adversarial-hardening/stage-closure-decision",),
        required_actor="payload.actor",
        required_scope="adversarial_hardening.stage14.closure.write",
        approval_requirement="this is the Stage 14 operator closure decision route after completion review readiness",
        receipt_behavior="Stage 14 Adversarial Hardening operator stage closure decision receipt",
        denial_behavior="api_permission_denied via permission_gate before stage closure receipt write",
        governance_maturity="permission_gated",
        notes="Closure receipt does not mutate runtime stage state, write memory, or write quarantine.",
    ),
    AuthorityRule(
        family="swarm",
        prefixes=("/swarm/stage-closure-decision",),
        required_actor="payload.actor",
        required_scope="swarm.stage15.closure.write",
        approval_requirement="this is the Stage 15 operator closure decision route after completion review readiness",
        receipt_behavior="Stage 15 Swarm operator stage closure decision receipt",
        denial_behavior="api_permission_denied via permission_gate or delegation gate before stage closure receipt write",
        governance_maturity="permission_gated",
        notes="Closure receipt does not mutate runtime stage state, write memory, or grant execution authority.",
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
        family="chatgpt_voice_bridge",
        prefixes=("/chatgpt-voice/ingress", "/chatgpt-voice/mcp-proof"),
        required_actor="payload.actor or chatgpt.voice default",
        required_scope="chatgpt.voice.bridge.write; chat.write is separately required for forwarding to /chat/send",
        approval_requirement=(
            "not_required_scope_gate_only; transcript guard must accept a usable transcript before chat forwarding; "
            "MCP proof route records connector evidence only"
        ),
        receipt_behavior=(
            "ChatGPT voice transcript ingress receipt or MCP connection proof receipt; lens overlay virtual "
            "voice-turn projection for transcripts; explicit orb left/right commands can write a bounded overlay "
            "position command request; optional forwarding passes through existing chat write gate"
        ),
        denial_behavior="api_permission_denied via permission_gate before voice ingress receipt write or chat forwarding",
        governance_maturity="permission_gated",
        notes=(
            "Transcript-only bridge: no raw audio stream, no shell/input control, no screenshots, no native "
            "ChatGPT app authority, and no execution or mutation authority beyond bounded receipt, virtual "
            "voice-turn recording, and runtime_overlay_position_only orb position command requests."
        ),
    ),
    AuthorityRule(
        family="developer_bridge",
        prefixes=("/developer-bridge/collaboration-agents/toggle",),
        required_actor="payload.actor or chat_ui.system default",
        required_scope="developer_bridge.operator_console_control",
        approval_requirement="not_required_operator_console_control_receipt",
        receipt_behavior="developer_bridge.collaboration_agent_toggle_receipt and bounded agent-control state",
        denial_behavior="unknown agent returns DeveloperBridgeError before state or receipt write",
        governance_maturity="bounded_operator_control_receipt",
        notes=(
            "Toggle changes only known collaboration participant enablement; it does not execute prompts, call "
            "models, run tools, or grant execution/mutation authority."
        ),
    ),
    AuthorityRule(
        family="developer_bridge",
        prefixes=("/developer-bridge/collaboration-message",),
        required_actor="payload.actor or chat_ui.system default",
        required_scope="developer_bridge.operator_console_control",
        approval_requirement="not_required_operator_console_message_receipt",
        receipt_behavior="developer_bridge.collaboration_prompt receipts, one per selected target",
        denial_behavior="invalid target, same source/target, disabled target, or empty message returns DeveloperBridgeError before relay write",
        governance_maturity="bounded_operator_message_receipt",
        notes=(
            "Operator messages append bounded relay receipts to Codex, Claude, and/or Francis1/Ollama. "
            "They do not execute prompts, call models directly, run tools, mutate the repo, write memory, "
            "approve actions, train a model, or grant execution/mutation authority."
        ),
    ),
    AuthorityRule(
        family="developer_bridge",
        prefixes=("/developer-bridge/francis-capability-grants",),
        required_actor="payload.actor or chat_ui.system default",
        required_scope="developer_bridge.operator_console_control",
        approval_requirement="operator_console_control_receipt_required_for_grant_deny_or_revoke",
        receipt_behavior="developer_bridge.francis_capability_grant_receipt and bounded capability-grant state",
        denial_behavior="unknown surface, invalid decision, unsafe access mode, or missing grant reason returns DeveloperBridgeError before state or receipt write",
        governance_maturity="bounded_operator_capability_grant_receipt",
        notes=(
            "Grant decisions are limited to observe/read/request/propose_plan local-model capability context. "
            "They do not execute prompts, run tools, mutate the repo, approve actions, train a model, or grant "
            "shell/execution authority."
        ),
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
        family="ingest_acquire",
        prefixes=("/ingest/acquire",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.acquire",
        approval_requirement="route-specific acquisition approval/readback remains enforced by the ingest service",
        receipt_behavior="source acquisition candidate or continuation record depending on route",
        denial_behavior="api_permission_denied via permission_gate before acquisition mutation",
        governance_maturity="permission_gated",
        notes="Acquisition routes remain scoped ingest entrypoints and do not grant general Lab execution authority.",
    ),
    AuthorityRule(
        family="ingest_forge",
        prefixes=("/ingest/forge",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.forge route-specific scope",
        approval_requirement=(
            "route-specific synthesize/review/apply/bind approval posture remains enforced by the ingest service"
        ),
        receipt_behavior="Forge synthesis, review, dry-run, apply, bind, or continuation record depending on route",
        denial_behavior="api_permission_denied via permission_gate before Forge ingest mutation",
        governance_maturity="permission_gated",
        notes="Forge ingest classification does not promote capabilities or bypass proposal/review governance.",
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/run",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.execute.run",
        approval_requirement="explicit lab run approval id and opt-in are consumed by IngestService before execution",
        receipt_behavior="Lab capability run result and bounded execution metadata from the ingest service",
        denial_behavior="api_permission_denied via permission_gate before Lab execution attempt",
        governance_maturity="permission_and_policy_gated",
        notes=(
            "This is the narrow Lab execution route; it does not grant broader repository execution authority or "
            "bypass source, approval, sandbox, and receipt controls enforced by the ingest service."
        ),
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
        prefixes=("/federation/sleep-resume-confirmation",),
        required_actor="payload.request_actor, payload.api_actor, payload.actor, or api.federation default",
        required_scope="federation.stage16.sleep_resume.confirmation.write",
        approval_requirement="explicit operator sleep/resume confirmation for Stage 16 sleep-continuity evidence",
        receipt_behavior="stage16 sleep/resume operator confirmation receipt",
        denial_behavior="api_permission_denied or governed no-receipt block before confirmation receipt write",
        governance_maturity="permission_gated",
        notes="Confirmation receipt does not write evidence, write runtime readbacks, run shell, or mark Stage 16 closed.",
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
        family="ingest_lab",
        prefixes=("/ingest/lab/approval-consumption-preflight",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="reads approval id and checks exact-action binding; does not consume approval",
        receipt_behavior="lab approval-consumption preflight receipt and runner-contract artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes="Readback proves approval/action binding and runner absence; it does not run repository code.",
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/runner-readiness",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="optional approval id readback only; does not consume approval",
        receipt_behavior="lab runner-readiness preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes="Projects sandbox, runner, isolation, resource, command, environment, and receipt-sink controls without executing repository code.",
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/runner-binding",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="optional approval id readback only; does not consume approval",
        receipt_behavior="lab runner-binding preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Projects the governed runner binding and execution-receipt sink contracts without binding a runner, "
            "consuming approval, or executing repository code."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/runner-enforcement",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="optional approval id readback only; does not consume approval",
        receipt_behavior="lab runner-enforcement preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Verifies projected runner binding and execution-receipt sink enforcement checks without binding a runner, "
            "consuming approval, or executing repository code."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/approval-consumption-handoff",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab approval-consumption handoff preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Binds an approved exact-action record to runner-enforcement readback and still blocks approval "
            "consumption, execution authority, and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/execution-receipt-sink-reservation",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab execution-receipt sink reservation receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Reserves a future execution-receipt id/path after approval handoff readback while still blocking "
            "prewrite, final write, approval consumption, execution authority, and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/runner-command-allowlist-binding",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab runner command allowlist binding receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Binds the exact-action command plan to missing allowlist controls after execution-receipt sink "
            "reservation while still blocking command execution, approval consumption, execution authority, "
            "and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/runner-command-allowlist-declaration",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab runner command allowlist declaration receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Declares exact-action command allowlist entries after command allowlist binding readback while "
            "still blocking live allowlist binding, command execution, approval consumption, execution "
            "authority, and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/runner-command-allowlist-enforcement",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab runner command allowlist enforcement preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Checks declared exact-action command allowlist entries against missing live runner enforcement "
            "controls while still blocking command execution, approval consumption, execution authority, "
            "and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/runner-sandbox-readiness",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab runner sandbox readiness preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Checks workspace, sandbox, runner, allowlist, and receipt-write controls after command allowlist "
            "enforcement readback while still blocking runner binding, command execution, approval consumption, "
            "execution authority, and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/execution-receipt-write-readiness",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab execution receipt write readiness preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Checks reserved execution receipt prewrite/final-write controls after sandbox readiness readback "
            "while still blocking execution receipt writes, command execution, approval consumption, execution "
            "authority, and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/execution-receipt-prewrite-binding",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab execution receipt prewrite binding preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Binds future lab.execution.run receipt schema, prewrite, and final-write contracts after receipt "
            "write readiness while still blocking execution receipt writes, writer implementations, command "
            "execution, approval consumption, execution authority, and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/execution-receipt-writer-preflight",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.readback",
        approval_requirement="approval id readback only; does not consume approval",
        receipt_behavior="lab execution receipt writer preflight receipt and artifact",
        denial_behavior="api_permission_denied via permission_gate before ingest receipt or artifact write",
        governance_maturity="permission_gated",
        notes=(
            "Declares future execution receipt writer path, atomic-write, and redaction boundaries after "
            "prewrite binding while still blocking execution receipt writes, writer implementations, command "
            "execution, approval consumption, execution authority, and repository execution."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/synthetic-execution-receipt-prewrite",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.receipt.write",
        approval_requirement="approved exact-action id required as readback evidence; approval is not consumed",
        receipt_behavior="synthetic no-op lab.execution.run receipt plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before execution receipt or ingest receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Writes only a synthetic/no-op execution receipt with all execution flags false. It does not run "
            "repository code, consume approval, grant execution authority, or validate the candidate."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/synthetic-execution-receipt-finalize",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.receipt.write",
        approval_requirement="approved exact-action id required as readback evidence; approval is not consumed",
        receipt_behavior="finalized synthetic no-op lab.execution.run receipt plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before execution receipt or ingest receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Finalizes only an existing synthetic/no-op execution receipt as blocked with all execution flags false. "
            "It does not run repository code, consume approval, grant execution authority, or validate the candidate."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/approval-consume-synthetic-noop",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.approval.consume",
        approval_requirement="approved exact-action id and finalized synthetic no-op execution receipt required",
        receipt_behavior="approval-consumption artifact plus ingest receipt; approved approval file is not moved",
        denial_behavior="api_permission_denied via permission_gate before approval-consumption artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Consumes an exact-action approval only for an already finalized synthetic/no-op execution receipt and "
            "records single-use evidence. It does not run repository code, grant execution authority, validate the "
            "candidate, or implement general Lab approval consumption."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/noop-runner-envelope",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.runner.noop",
        approval_requirement="consumed synthetic no-op approval record required; repository execution is not allowed",
        receipt_behavior="built-in no-op runner envelope artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before no-op runner artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Completes only a built-in no-op Lab runner envelope after synthetic no-op approval consumption. It "
            "does not execute repository commands, grant execution authority, validate the candidate, bind a live "
            "sandbox runner, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/noop-runner-transcript",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.runner.noop.transcript",
        approval_requirement="completed built-in no-op runner envelope required; repository execution is not allowed",
        receipt_behavior="built-in no-op stdout/stderr transcript artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before no-op transcript artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Records only deterministic empty stdout/stderr metadata for a completed built-in no-op envelope. It "
            "does not capture real process output, execute repository commands, store output contents, grant "
            "execution authority, validate the candidate, bind a live sandbox runner, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/noop-runner-identity-binding",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.runner.noop.identity",
        approval_requirement="completed built-in no-op transcript required; repository execution is not allowed",
        receipt_behavior="built-in no-op runner identity-binding artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before identity-binding artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Binds only the Francis-owned built-in no-op runner identity to the completed no-op proof chain. It "
            "does not bind a live runner, bind a sandbox runner, execute repository commands, capture real process "
            "output, grant execution authority, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/source-mount-readiness",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.source_mount.readiness",
        approval_requirement="completed built-in no-op runner identity required; repository execution is not allowed",
        receipt_behavior="source-mount readiness artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before source-mount readiness artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Records only that the Lab workspace source reference is read-only and that no source mount has been "
            "bound or enforced. It does not copy source contents, bind a live runner, bind a sandbox runner, execute "
            "repository commands, grant execution authority, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/source-mount-contract",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.source_mount.contract",
        approval_requirement=(
            "source-mount readiness required; contract declaration only; repository execution is not allowed"
        ),
        receipt_behavior="source-mount contract artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before source-mount contract artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Records only the future read-only source mount contract and required enforcement controls. It does "
            "not bind or enforce a live source mount, copy source contents, bind a live runner, bind a sandbox "
            "runner, execute repository commands, grant execution authority, validate the candidate, or promote "
            "capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-contract",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_contract",
        approval_requirement=(
            "runner sandbox readiness required; provider contract declaration only; repository execution is not allowed"
        ),
        receipt_behavior="sandbox provider contract artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before sandbox provider contract artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Records the future Lab sandbox provider contract and required enforcement controls. It does not bind "
            "or enforce a sandbox provider, bind a runner, execute repository commands, grant execution authority, "
            "write execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-binding",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_binding",
        approval_requirement=(
            "sandbox provider contract required; binding preflight only; repository execution is not allowed"
        ),
        receipt_behavior="sandbox provider binding preflight artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before sandbox provider binding artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Records the future Lab sandbox provider binding checklist. It does not select or verify a provider "
            "binary/service, bind or enforce a sandbox provider, bind a runner, execute repository commands, grant "
            "execution authority, write execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-selection",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_selection",
        approval_requirement=(
            "sandbox provider binding preflight required; selection/verification preflight only; repository execution "
            "is not allowed"
        ),
        receipt_behavior="sandbox provider selection preflight artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider selection artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Records requested provider kind, local provider reference metadata, and optional policy manifest "
            "metadata for a future Lab sandbox provider. It does not execute provider binaries, query services, "
            "launch containers, bind or enforce a sandbox provider, execute repository commands, grant execution "
            "authority, write execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-verifier",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_verifier",
        approval_requirement=(
            "sandbox provider selection preflight required; static identity/policy verifier preflight only; "
            "repository execution is not allowed"
        ),
        receipt_behavior="sandbox provider verifier preflight artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider verifier artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Captures static provider reference fingerprints, sanitized policy-manifest hashes, declared version "
            "evidence, and Francis verifier identity. It does not runtime-probe providers, execute provider "
            "binaries, query services, launch containers, bind or enforce a sandbox provider, execute repository "
            "commands, grant execution authority, write execution receipts, validate the candidate, or promote "
            "capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe",
        approval_requirement=(
            "sandbox provider verifier preflight required; runtime probe contract preflight only; repository "
            "execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe preflight artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider runtime probe artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Declares provider runtime-probe authorization, timeout, network-blocking, receipt, and repository "
            "separation controls. It does not execute provider binaries, query provider services, launch containers, "
            "bind or enforce a sandbox provider, execute repository commands, grant execution authority, write "
            "execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-harness",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe_harness",
        approval_requirement=(
            "sandbox provider runtime probe preflight required; harness contract preflight only; repository "
            "execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe harness preflight artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider runtime probe harness artifact "
            "or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Declares future provider runtime-probe runner, sandbox, service-query guard, output capture, and "
            "kill-switch controls. It does not perform provider runtime probes, execute provider binaries, query "
            "provider services, launch containers, bind or enforce a sandbox provider, execute repository "
            "commands, grant execution authority, write execution receipts, validate the candidate, or promote "
            "capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-runner-readiness",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe_runner_readiness",
        approval_requirement=(
            "sandbox provider runtime probe harness preflight required; probe-runner readiness contract only; "
            "repository execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe runner readiness artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider runtime probe runner readiness "
            "artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Declares the future provider runtime-probe runner interface and missing runner identity, policy, "
            "sandbox, network-block, workspace-isolation, timeout, output-capture, kill-switch, and receipt "
            "controls. It does not perform provider runtime probes, execute provider binaries, query provider "
            "services, launch containers, bind or enforce a sandbox provider, execute repository commands, grant "
            "execution authority, write execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-runner-binding",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe_runner_binding",
        approval_requirement=(
            "sandbox provider runtime probe runner readiness required; probe-runner binding preflight only; "
            "repository execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe runner binding preflight artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider runtime probe runner binding "
            "artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Declares the future provider runtime-probe runner binding contract and missing live runner "
            "implementation, identity, policy, sandbox, network-block, workspace-isolation, timeout, "
            "output-capture, kill-switch, receipt, and runtime-probe binding controls. It does not perform "
            "provider runtime probes, execute provider binaries, query provider services, launch processes or "
            "containers, bind or enforce a sandbox provider, execute repository commands, grant execution "
            "authority, write execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-runner-enforcement",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe_runner_enforcement",
        approval_requirement=(
            "sandbox provider runtime probe runner binding preflight required; probe-runner enforcement "
            "preflight only; repository execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe runner enforcement preflight artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider runtime probe runner enforcement "
            "artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Declares the future provider runtime-probe runner enforcement contract and missing live runner, "
            "runtime-probe binding, identity, policy, sandbox, network-block, workspace-isolation, timeout, "
            "output-capture, kill-switch, and receipt enforcement controls. It does not perform provider "
            "runtime probes, execute provider binaries, query provider services, launch processes or containers, "
            "bind or enforce a sandbox provider, execute repository commands, grant execution authority, write "
            "execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-execution-boundary",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe_execution_boundary",
        approval_requirement=(
            "run-boundary preflight and runtime-probe runner enforcement readback required; provider runtime "
            "probe execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe execution-boundary artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider runtime probe execution-boundary "
            "artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Records the blocked boundary between preflight evidence and any future sandbox provider runtime "
            "probe. It requires future live probe-runner enforcement, runtime-probe binding, sandbox, network, "
            "workspace, timeout, output-capture, kill-switch, and execution receipt writer controls. It does not "
            "perform provider runtime probes, execute provider binaries, query provider services, launch "
            "processes or containers, bind or enforce a sandbox provider, execute repository commands, consume "
            "approval, write execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-refuse",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe.refuse",
        approval_requirement=(
            "sandbox provider runtime probe execution-boundary readback required; refusal only; provider runtime "
            "probe execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe refusal artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandbox provider runtime probe refusal artifact or "
            "receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Records an explicit refusal when an operator or client asks Francis to runtime-probe a sandbox "
            "provider before governed probe execution exists. It depends on execution-boundary readback and does "
            "not perform provider runtime probes, execute provider binaries, query provider services, launch "
            "processes or containers, bind or enforce a sandbox provider, execute repository commands, consume "
            "approval, write execution receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-request-approval",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe.request_approval",
        approval_requirement=(
            "sandbox provider runtime probe execution-boundary readback required; creates a pending approval "
            "request only; provider runtime probe execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe approval-request artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before provider runtime probe approval-request artifact, "
            "pending approval, or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Creates an exact-action pending approval request for future sandbox provider runtime probing. It "
            "depends on execution-boundary readback and does not consume approval, perform provider runtime "
            "probes, execute provider binaries, query provider services, launch processes or containers, bind or "
            "enforce a sandbox provider, execute repository commands, write execution receipts, validate the "
            "candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-consume-approval",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe.consume_approval",
        approval_requirement=(
            "approved exact-action sandbox provider runtime probe approval required; writes a single-use "
            "consumption record only; provider runtime probe execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe approval-consumption artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before provider runtime probe approval-consumption artifact "
            "or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Consumes an approved exact-action provider runtime-probe approval as a single-use governance record. "
            "It does not perform provider runtime probes, execute provider binaries, query provider services, "
            "launch processes or containers, bind or enforce a sandbox provider, execute repository commands, "
            "write execution receipts, grant execution authority, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-invocation-boundary",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe.invocation_boundary",
        approval_requirement=(
            "consumed exact-action sandbox provider runtime probe approval required; writes a blocked invocation "
            "boundary only; provider runtime probe execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe invocation-boundary artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before provider runtime probe invocation-boundary artifact "
            "or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Binds a consumed provider runtime-probe approval to the existing execution-boundary readback and "
            "records the remaining future runner controls: policy, sandbox, network block, workspace isolation, "
            "timeout, output capture, kill switch, and execution receipt writer. It does not perform provider "
            "runtime probes, execute provider binaries, query provider services, launch processes or containers, "
            "bind or enforce a sandbox provider, execute repository commands, write execution receipts, grant "
            "execution authority, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-runner-pre-execution-boundary",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary",
        approval_requirement=(
            "recorded provider runtime-probe invocation boundary required; writes a blocked runner pre-execution "
            "boundary only; provider runtime probe execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe runner pre-execution-boundary artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before provider runtime probe runner pre-execution-boundary "
            "artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Binds the recorded provider runtime-probe invocation boundary to the next runner pre-execution control "
            "set and records the still-missing live runner identity, policy, sandbox policy, network block, timeout, "
            "output capture, kill switch, and execution receipt writer bindings. It does not perform provider "
            "runtime probes, execute provider binaries, query provider services, launch processes or containers, "
            "bind or enforce a live sandbox provider, execute repository commands, write execution receipts, grant "
            "execution authority, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandbox-provider-runtime-probe-runner-control-binding",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandbox.provider_runtime_probe.runner_control_binding",
        approval_requirement=(
            "recorded provider runtime-probe runner pre-execution boundary required; writes a blocked runner "
            "control-binding artifact only; provider runtime probe execution is not allowed"
        ),
        receipt_behavior="sandbox provider runtime probe runner control-binding artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before provider runtime probe runner control-binding artifact "
            "or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Records control-binding evidence for future provider-probe runner identity, policy, sandbox policy, "
            "network block, timeout, output capture, kill switch, and execution receipt writer preconditions while "
            "keeping all live runner, sandbox, provider, and execution bindings false. It does not perform provider "
            "runtime probes, execute provider binaries, query provider services, launch processes or containers, "
            "bind or enforce a live sandbox provider, execute repository commands, write execution receipts, grant "
            "execution authority, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandboxed-rebuild-run-test-boundary",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandboxed_rebuild_run_test.boundary",
        approval_requirement=(
            "recorded provider runtime-probe runner control-binding required; writes a blocked sandboxed "
            "rebuild/run/test boundary only; repository execution is not allowed"
        ),
        receipt_behavior="sandboxed rebuild/run/test boundary artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before sandboxed rebuild/run/test boundary artifact or "
            "receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Records the future sandboxed rebuild/run/test execution boundary that depends on provider-probe "
            "runner control-binding evidence while requiring a separate future execution approval and live runner, "
            "sandbox, network, timeout, output, kill-switch, command-allowlist, source-mount, and receipt-writer "
            "controls. It does not launch processes or containers, execute repository commands, run install/build/"
            "test steps, access the network, write to the repository, write execution receipts, validate the "
            "candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandboxed-rebuild-run-test-request-approval",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandboxed_rebuild_run_test.request_approval",
        approval_requirement=(
            "recorded sandboxed rebuild/run/test boundary required; creates a pending execution approval request "
            "only; approval is not consumed and repository execution is not allowed"
        ),
        receipt_behavior="sandboxed rebuild/run/test approval-request artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before approval request, sandboxed approval artifact, or "
            "receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Creates a pending operator approval request for future sandboxed rebuild/run/test execution after the "
            "boundary evidence exists. It does not consume approval, launch processes or containers, execute "
            "repository commands, run install/build/test steps, access the network, write to the repository, write "
            "execution receipts, validate the candidate, promote capability use, or grant execution authority."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandboxed-rebuild-run-test-consume-approval",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandboxed_rebuild_run_test.consume_approval",
        approval_requirement=(
            "approved exact-action sandboxed rebuild/run/test approval request required; writes a single-use "
            "consumption record only; repository execution is not allowed"
        ),
        receipt_behavior="sandboxed rebuild/run/test approval-consumption artifact plus ingest receipt",
        denial_behavior=(
            "api_permission_denied via permission_gate before approval-consumption artifact or receipt write"
        ),
        governance_maturity="permission_gated",
        notes=(
            "Consumes an approved sandboxed rebuild/run/test approval as single-use governance evidence while "
            "keeping execution authority absent. It does not launch processes or containers, execute repository "
            "commands, run install/build/test steps, access the network, write to the repository, write execution "
            "receipts, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandboxed-rebuild-run-test-runner-binding",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandboxed_rebuild_run_test.runner_binding",
        approval_requirement=(
            "consumed exact-action sandboxed rebuild/run/test approval required; writes a static provider-reference "
            "runner-binding preflight only; repository execution is not allowed"
        ),
        receipt_behavior="sandboxed rebuild/run/test runner-binding artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before runner-binding artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Records local sandbox provider reference and policy-manifest metadata as static preflight evidence after "
            "single-use approval consumption. It does not bind a live runner or sandbox, launch processes or "
            "containers, query provider services, execute repository commands, run install/build/test steps, access "
            "the network, write to the repository, write execution receipts, validate the candidate, or promote "
            "capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/sandboxed-rebuild-run-test-sandbox-policy",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.sandboxed_rebuild_run_test.sandbox_policy",
        approval_requirement=(
            "consumed exact-action sandboxed rebuild/run/test approval and static runner-binding preflight required; "
            "writes a conservative sandbox-policy preflight only; repository execution is not allowed"
        ),
        receipt_behavior="sandboxed rebuild/run/test sandbox-policy artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before sandbox-policy artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Records default-deny network, read-only source reference, repo-write/destructive denial, secret-storage "
            "denial, command-execution disabled state, and missing live sandbox/allowlist/receipt-writer controls. "
            "It does not bind or enforce a live sandbox, launch processes or containers, execute repository commands, "
            "run install/build/test steps, access the network, write to the repository, write execution receipts, "
            "validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_lab",
        prefixes=("/ingest/lab/run-boundary-preflight",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="ingest.lab.run_boundary.preflight",
        approval_requirement=(
            "source-mount contract, receipt-writer preflight, sandbox provider runtime-probe harness, and "
            "runtime-probe runner enforcement readbacks required; repository execution is not allowed"
        ),
        receipt_behavior="run-boundary preflight artifact plus ingest receipt",
        denial_behavior="api_permission_denied via permission_gate before run-boundary artifact or receipt write",
        governance_maturity="permission_gated",
        notes=(
            "Aggregates source-mount, sandbox provider contract/binding/selection/verifier, sandbox provider "
            "runtime-probe, sandbox provider runtime-probe harness, sandbox provider runtime-probe runner "
            "enforcement, command allowlist, receipt writer, and approval-handoff controls for a future guarded "
            "Lab run. It does not bind a live mount, bind or enforce a live runner or sandbox, runtime-probe a "
            "provider, consume approval for repository execution, write execution receipts, execute repository "
            "commands, validate the candidate, or promote capability use."
        ),
    ),
    AuthorityRule(
        family="ingest_readback",
        prefixes=("/ingest/readback",),
        required_actor="query actor",
        required_scope="ingest.lab.readback",
        approval_requirement="not_required_readback_only",
        receipt_behavior="none; reads existing source registry and ingest artifacts",
        denial_behavior="api_permission_denied via permission_gate before source/artifact readback",
        governance_maturity="permission_gated",
        notes=(
            "Lists source, repo-map, candidate, preflight, approval-consumption, approval-consumption record, "
            "no-op runner envelope, no-op runner transcript, no-op runner identity binding, runner-contract, "
            "runner-readiness, runner-binding, runner-enforcement, approval-consumption handoff, and "
            "execution-receipt sink reservation, runner command allowlist binding, and runner command "
            "allowlist declaration, allowlist enforcement preflight, runner sandbox readiness, source-mount "
            "readiness, and execution receipt write readiness, prewrite binding, writer preflight records, and synthetic execution "
            "receipts without executing repository code."
        ),
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
        family="managed_copies_integrity_evidence",
        prefixes=("/managed-copies/integrity-evidence",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.rogue_recovery.write",
        approval_requirement="exact live structural drift plus explicit confirmation",
        receipt_behavior="immutable tenant-local derived integrity evidence receipt only",
        denial_behavior="api_permission_denied before provision, isolation, or integrity inspection",
        governance_maturity="permission_gated_evidence_only",
        notes="Preserves derived drift evidence but never declares rogue status or grants containment authority.",
    ),
    AuthorityRule(
        family="managed_copies_integrity_triage_disposition",
        prefixes=("/managed-copies/integrity-triage-disposition",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.rogue_recovery.write",
        approval_requirement="exact current integrity evidence plus exact fingerprint replay and explicit confirmation",
        receipt_behavior="immutable tenant-local bounded integrity triage disposition receipt only",
        denial_behavior="api_permission_denied before provision, isolation, scan, or integrity evidence inspection",
        governance_maturity="permission_gated_triage_disposition_only",
        notes="Never declares rogue status, resolves an incident, acts on containment, or grants new authority.",
    ),
    AuthorityRule(
        family="managed_copies_tenant_access_check",
        prefixes=("/managed-copies/tenant-access-check",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.isolation_verification.write",
        approval_requirement="exact live provision and structural-isolation lineage",
        receipt_behavior="none; deterministic read-only allow or deny decision",
        denial_behavior="api_permission_denied before provision or isolation resolution",
        governance_maturity="permission_gated_application_access_boundary",
        notes="Returns no resolved path and proves no filesystem ACL, process, network, or full customer isolation.",
    ),
    AuthorityRule(
        family="managed_copies_integrity_scan",
        prefixes=("/managed-copies/integrity-scan",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.rogue_recovery.write",
        approval_requirement="exact live provision and structural-isolation lineage",
        receipt_behavior="none; read-only derived integrity findings",
        denial_behavior="api_permission_denied before provision or isolation inspection",
        governance_maturity="permission_gated_read_only_scan",
        notes="Never declares a copy rogue or grants halt, quarantine, replacement, restore, execution, or mutation authority.",
    ),
    AuthorityRule(
        family="managed_copies_rogue_detection_assessment",
        prefixes=("/managed-copies/rogue-detection-assessment",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.rogue_recovery.write",
        approval_requirement="exact live provision and structural-isolation lineage plus explicit confirmation",
        receipt_behavior="immutable redacted rogue-signal assessment receipt only",
        denial_behavior="api_permission_denied before provision, isolation, or evidence projection",
        governance_maturity="permission_gated_assessment_only",
        notes="Never declares rogue detection or grants halt, quarantine, replacement, restore, execution, or mutation authority.",
    ),
    AuthorityRule(
        family="managed_copies_safe_delta_export_artifact_plan",
        prefixes=("/managed-copies/safe-delta-export-artifact-plan",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.safe_delta.export.artifact.preflight",
        approval_requirement="exact live approved export authorization decision",
        receipt_behavior="dry-run plan only; writes no plan, receipt, artifact, manifest, or payload",
        denial_behavior="api_permission_denied before decision or lineage projection",
        governance_maturity="permission_gated_dry_run_only",
        notes="Grants no approval, export, execution, or mutation authority and uses no network.",
    ),
    AuthorityRule(
        family="managed_copies_safe_delta_export_authorization_decision",
        prefixes=("/managed-copies/safe-delta-export-authorization-decision",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.safe_delta.export.authorization.decide",
        approval_requirement="exact live pending request and explicit confirmation",
        receipt_behavior="immutable approved or rejected authorization decision receipt only",
        denial_behavior="api_permission_denied before request lineage projection or receipt write",
        governance_maturity="permission_gated_confirmed_decision_only",
        notes="Creates no export, artifact, manifest, payload, destination, credential, network, learning, or mutation effect.",
    ),
    AuthorityRule(
        family="managed_copies_safe_delta_export_authorization_request",
        prefixes=("/managed-copies/safe-delta-export-authorization-request",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.safe_delta.export.authorization.request",
        approval_requirement="fresh exact safe-delta export preflight and explicit confirmation",
        receipt_behavior="immutable pending export authorization-request receipt only",
        denial_behavior="api_permission_denied before lineage projection or request receipt write",
        governance_maturity="permission_gated_confirmed_request_only",
        notes="Creates no approval, export, artifact, manifest, payload, destination, credential, network, or learning effect.",
    ),
    AuthorityRule(
        family="managed_copies_safe_delta_export_preflight",
        prefixes=("/managed-copies/safe-delta-export-preflight",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="managed_copies.safe_delta.export.preflight",
        approval_requirement="validated approved safe-delta decision and live review, lineage, and tenant policy",
        receipt_behavior="none_dry_run_preflight_projection",
        denial_behavior="api_permission_denied before safe-delta lineage projection",
        governance_maturity="permission_gated_dry_run_preflight",
        notes=(
            "Dry-run-only eligibility projection; writes no receipt, artifact, manifest, tenant state, memory, "
            "registry, or learning and grants no export, execution, or mutation authority."
        ),
    ),
    AuthorityRule(
        family="managed_copies_runtime_evidence",
        prefixes=("/managed-copies/runtime-evidence-readback",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.runtime_evidence.write",
        approval_requirement=(
            "Stage 17 closure plus exact canonical runtime-source receipt lineage, fingerprint, and confirmation"
        ),
        receipt_behavior="immutable Stage 18 runtime-evidence receipt; exact replay is idempotent",
        denial_behavior="api_permission_denied before payload processing or filesystem creation; source failures fail closed",
        governance_maturity="permission_gated_one_requirement_recorder_fixture_runtime_producer",
        notes=(
            "The route can record copy_creation_runtime_proof only after an independent canonical verifier succeeds; "
            "the fixed fixture startup producer is independently verified but cannot satisfy production readiness; "
            "the receipt grants no runtime or tenant authority."
        ),
    ),
    AuthorityRule(
        family="managed_copies_runtime_start",
        prefixes=("/managed-copies/runtime-start",),
        required_actor="payload.request_actor",
        required_scope="managed_copies.runtime_start.execute",
        approval_requirement=(
            "separate unexpired unrevoked exact-action approval bound to the final fixed fixture launch descriptor"
        ),
        receipt_behavior="immutable launch-attempt, startup or failure, handshake, heartbeat, and fixture cleanup receipts",
        denial_behavior="api_permission_denied before payload processing, filesystem creation, or process creation",
        governance_maturity="permission_and_exact_approval_gated_fixed_fixture_startup",
        notes=(
            "Starts only the repository-owned bounded fixture runtime; no caller command, shell, service install, "
            "resident supervision, restart, production runtime, or persistent actor grant is permitted."
        ),
    ),
    AuthorityRule(
        family="managed_copies_isolation_policy_decision",
        prefixes=("/managed-copies/isolation-policy-decision",),
        required_actor="none",
        required_scope="none_read_only_isolation_policy_classification",
        approval_requirement="not_required_read_projection",
        receipt_behavior="none_read_projection",
        denial_behavior="exact schema and isolation policy rules return deterministic policy_denied classification",
        governance_maturity="read_projection_using_post",
        notes=(
            "POST carries a bounded policy-classification payload; it resolves no lineage or path, reads or writes "
            "no tenant state, and grants no access, execution, mutation, or other authority."
        ),
    ),
    AuthorityRule(
        family="managed_copies",
        prefixes=("/managed-copies",),
        required_actor="payload.request_actor, payload.api_actor, or payload.actor",
        required_scope="managed_copies route-specific write scope",
        approval_requirement=(
            "route-specific managed-copy contract/review gate; current write routes return blocked snapshots"
        ),
        receipt_behavior="managed-copy request, review, or runtime-evidence record depending on route",
        denial_behavior="api_permission_denied via permission_gate before managed-copy review or evidence mutation",
        governance_maturity="permission_gated",
        notes=(
            "Managed-copy routes preserve no-copy/no-delete/no-credential-revocation posture unless a future "
            "route-specific contract explicitly enables and receipts that behavior."
        ),
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


def _join_paths(prefix: str, path: str) -> str:
    if not prefix:
        return path
    if path == "/":
        return prefix
    return f"{prefix.rstrip('/')}/{path.lstrip('/')}"


def _iter_route_contexts(routes: Iterable[Any], prefix: str = "") -> Iterable[tuple[str, Any]]:
    for route in routes:
        original_router = getattr(route, "original_router", None)
        include_context = getattr(route, "include_context", None)
        if original_router is not None and include_context is not None:
            include_prefix = str(getattr(include_context, "prefix", "") or "").strip()
            nested_prefix = _join_paths(prefix, include_prefix) if include_prefix else prefix
            yield from _iter_route_contexts(getattr(original_router, "routes", []), nested_prefix)
            continue

        path = str(getattr(route, "path", "") or "").strip()
        if path:
            yield _join_paths(prefix, path), route


def build_mutating_route_authority_matrix(routes: Iterable[Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    for path, route in _iter_route_contexts(routes):
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
