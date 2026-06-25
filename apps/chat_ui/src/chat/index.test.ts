import assert from "node:assert/strict";
import test from "node:test";

import { parseChatEvent, parseChatSendResponse } from "./index.ts";
import {
  collaborationActionBoundarySummary,
  collaborationActionIntakeSummary,
  collaborationBuildDirectionGateSummary,
  collaborationImplementationReviewSummary,
  collaborationLearningGuardSummary,
  collaborationReviewBadge,
  collaborationReviewNextAction,
  collaborationReviewTone,
  collaborationRuntimeLocalModelResponseSummary,
  collaborationRuntimeLearningReceiptSummary,
  collaborationRuntimeLearningSignalSummary,
  collaborationRuntimeRecurrenceSummary,
  collaborationRuntimeReviewReceiptSummary,
  collaborationSessionReviewGateSummary,
  collaborationSessionTranscriptDisclosureSummary,
  collaborationSubstrateChecklistSummary,
  collaborationTranscriptAuditSummary,
  francisBodySurfaceExposureSummary,
  formatCollaborationRelayMessage,
  isCollaborationAuditReceipt,
  isCollaborationDriverPrompt,
  parseCollaborationAgentsStatus,
  parseCollaborationLearning,
  parseCollaborationReview,
  parseCollaborationRuntimeHealth,
  parseCollaborationSessions,
  parseCollaborationSubstrateReadiness,
  parseCollaborationTranscript,
  parseFrancisBodyMap,
  parseFrancisTrustLadder,
  preserveCollaborationReadbackDuringWarming,
} from "./collaboration.ts";

test("parseChatSendResponse preserves mission ingress metadata for the chat surface", () => {
  const result = parseChatSendResponse({
    ok: true,
    mode: "mission_ingress",
    status: "queued",
    reply: "Mission msn_chat declared. First operation tsk_chat queued. Next: run_linked_operation.",
    mission_id: "msn_chat",
    operation_id: "tsk_chat",
    operation: { id: "tsk_chat", name: "plan.create", status: "queued" },
    advance: { ok: true, applied: true, action: "create_first_operation", operation_id: "tsk_chat" },
    mission: { id: "msn_chat", status: "queued", linked_task_ids: ["tsk_chat"] },
    queue_item: { recommended_action: "run_linked_operation", action_target_id: "tsk_chat" },
    loop_state: {
      active_stage: "execute",
      handoff: { action: "run_linked_operation", operation_id: "tsk_chat", next_step: "Run linked operation." },
      interface: { status: "available", operation_id: "tsk_chat" },
    },
    current_task: {
      source: "mission_meta",
      operation_id: "tsk_chat",
      trace_id: "trace_chat",
      run_id: "run_chat",
      artifact_dir: "D:/francis/data/artifacts/chat",
      handoff_action: "run_linked_operation",
      next_step: "Run linked operation.",
    },
    memory_receipt_count: 1,
    latest_memory_receipt: {
      id: "ledger_chat",
      mission_id: "msn_chat",
      operation_id: "tsk_chat",
      trace_id: "trace_chat",
      run_id: "run_chat",
      artifact_dir: "D:/francis/data/artifacts/chat",
    },
    telemetry_context: {
      kind: "francis.stage7.telemetry.context",
      status: "available",
      active_source_total: 2,
      source_total: 3,
      event_count: 1,
      prompt_lines: ["git: branch main, changed 1", "ide_diagnostics: error, count 2"],
      hidden_sensing: false,
      governance: {
        telemetry_is_untrusted_input: true,
        grants_execution_authority: false,
      },
    },
    governance: {
      gate: "permission_gate",
      reason: "missing_scopes",
      next_step: "configure_actor_scope_before_declaring_chat_missions",
    },
  });

  assert.equal(result.error, undefined);
  assert.equal(result.message?.role, "assistant");
  assert.equal(result.message?.content, "Mission msn_chat declared. First operation tsk_chat queued. Next: run_linked_operation.");

  const meta = result.message?.meta as Record<string, unknown>;
  assert.equal(meta.mode, "mission_ingress");
  assert.equal(meta.status, "queued");
  assert.equal(meta.mission_id, "msn_chat");
  assert.equal(meta.operation_id, "tsk_chat");

  const advance = meta.advance as Record<string, unknown>;
  assert.equal(advance.action, "create_first_operation");
  assert.equal(advance.operation_id, "tsk_chat");

  const loopState = meta.loop_state as Record<string, unknown>;
  assert.equal(loopState.active_stage, "execute");
  assert.deepEqual(loopState.interface, { status: "available", operation_id: "tsk_chat" });

  const currentTask = meta.current_task as Record<string, unknown>;
  assert.equal(currentTask.source, "mission_meta");
  assert.equal(currentTask.operation_id, "tsk_chat");
  assert.equal(currentTask.trace_id, "trace_chat");
  assert.equal(currentTask.run_id, "run_chat");
  assert.equal(currentTask.artifact_dir, "D:/francis/data/artifacts/chat");
  assert.equal(currentTask.handoff_action, "run_linked_operation");

  assert.equal(meta.memory_receipt_count, 1);
  const latestMemoryReceipt = meta.latest_memory_receipt as Record<string, unknown>;
  assert.equal(latestMemoryReceipt.id, "ledger_chat");
  assert.equal(latestMemoryReceipt.operation_id, "tsk_chat");
  assert.equal(latestMemoryReceipt.trace_id, "trace_chat");
  assert.equal(latestMemoryReceipt.run_id, "run_chat");
  assert.equal(latestMemoryReceipt.artifact_dir, "D:/francis/data/artifacts/chat");

  const governance = meta.governance as Record<string, unknown>;
  assert.equal(governance.gate, "permission_gate");
  assert.equal(governance.reason, "missing_scopes");

  const telemetryContext = meta.telemetry_context as Record<string, unknown>;
  assert.equal(telemetryContext.kind, "francis.stage7.telemetry.context");
  assert.equal(telemetryContext.active_source_total, 2);
  assert.deepEqual(telemetryContext.prompt_lines, ["git: branch main, changed 1", "ide_diagnostics: error, count 2"]);
});

test("parseChatEvent preserves websocket mission ingress metadata", () => {
  const event = parseChatEvent(
    JSON.stringify({
      type: "message",
      message: {
        role: "assistant",
        content: "Mission msn_ws declared. First operation tsk_ws queued. Next: run_linked_operation.",
        meta: {
          ok: true,
          mode: "mission_ingress",
          status: "queued",
          mission_id: "msn_ws",
          operation_id: "tsk_ws",
          advance: { action: "create_first_operation", operation_id: "tsk_ws" },
          loop_state: { active_stage: "execute", interface: { status: "available", operation_id: "tsk_ws" } },
        },
      },
    }),
  );

  assert.equal(event.type, "message");
  assert.equal(event.message?.role, "assistant");
  assert.equal(event.message?.content, "Mission msn_ws declared. First operation tsk_ws queued. Next: run_linked_operation.");
  assert.equal(event.message?.meta?.mode, "mission_ingress");
  assert.equal(event.message?.meta?.mission_id, "msn_ws");
  assert.equal(event.message?.meta?.operation_id, "tsk_ws");
});

test("parseCollaborationAgentsStatus preserves operator-console boundaries", () => {
  const status = parseCollaborationAgentsStatus({
    ok: true,
    mode: "read_only",
    relay: "developer_bridge_collaboration_prompt_relay_v0",
    agents: [
      {
        agent: "codex",
        label: "Codex",
        enabled: true,
        participant_kind: "interactive_and_optional_responder",
        local_runner: "francis.developer_bridge.codex_responder",
        authority: "relay_only",
        writes_relay_receipts: true,
        grants_execution_authority: false,
        grants_mutation_authority: false,
      },
      {
        agent: "ollama",
        label: "Ollama",
        enabled: false,
        participant_kind: "local_model_participant",
        local_runner: "francis.developer_bridge.ollama_participant",
        authority: "relay_only",
        writes_relay_receipts: true,
        grants_execution_authority: false,
        grants_mutation_authority: false,
      },
    ],
    operator_console: {
      surface: "chat_ui",
      actor: "chat_ui.system",
      client_can_be_operator_console: true,
      client_is_automatic_execution_authority: false,
    },
    definitions: {
      operator_toggle_proof:
        "Typed proof that a participant toggle receipt recorded actor, reason, previous/current state, operator-console status, and no capability or execution authority grant.",
    },
    receipts: [
      {
        kind: "developer_bridge.collaboration_agent_toggle_receipt",
        receipt_id: "collab-agent-toggle-1234",
        created_at: "2026-06-25T05:16:00Z",
        agent: "ollama",
        enabled: true,
        previous_enabled: false,
        actor: "chat_ui.system",
        reason: "operator toggled collaboration participant in Chat UI",
        operator_toggle_proof: {
          kind: "developer_bridge.collaboration_agent_toggle_proof",
          proof_status: "operator_console_recorded",
          agent: "ollama",
          actor_recorded: true,
          reason_recorded: true,
          previous_state_observed: true,
          current_state_observed: true,
          previous_enabled: false,
          current_enabled: true,
          state_changed: true,
          operator_console_actor: true,
          client_can_be_operator_console: true,
          client_is_automatic_execution_authority: false,
          requires_operator_review: true,
          proves_capability_authority: false,
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
          grants_training_authority: false,
        },
        governance: {
          executes_prompt: false,
          calls_model: false,
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
          grants_training_authority: false,
          grants_capability_authority: false,
          client_can_be_operator_console: true,
          client_is_automatic_execution_authority: false,
        },
      },
    ],
    governance: {
      grants_execution_authority: false,
      grants_mutation_authority: false,
    },
  });

  assert.equal(status.ok, true);
  assert.equal(status.agents.length, 2);
  assert.equal(status.agents[0]?.enabled, true);
  assert.equal(status.agents[1]?.agent, "ollama");
  assert.equal(status.agents[1]?.enabled, false);
  assert.equal(status.agents[1]?.grantsExecutionAuthority, false);
  assert.equal(status.operatorConsole.clientCanBeOperatorConsole, true);
  assert.equal(status.operatorConsole.clientIsAutomaticExecutionAuthority, false);
  assert.equal(status.definitions.operatorToggleProof.startsWith("Typed proof"), true);
  assert.equal(status.receipts.length, 1);
  assert.equal(status.receipts[0]?.receiptId, "collab-agent-toggle-1234");
  assert.equal(status.receipts[0]?.agent, "ollama");
  assert.equal(status.receipts[0]?.previousEnabled, false);
  assert.equal(status.receipts[0]?.enabled, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.proofStatus, "operator_console_recorded");
  assert.equal(status.receipts[0]?.operatorToggleProof.actorRecorded, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.reasonRecorded, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.previousStateObserved, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.currentStateObserved, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.stateChanged, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.operatorConsoleActor, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.provesCapabilityAuthority, false);
  assert.equal(status.receipts[0]?.operatorToggleProof.grantsApprovalAuthority, false);
  assert.equal(status.receipts[0]?.operatorToggleProof.grantsTrainingAuthority, false);
  assert.equal(status.receipts[0]?.governance.grants_execution_authority, false);
  assert.equal(status.receipts[0]?.governance.grants_memory_write_authority, false);
});

test("parseCollaborationAgentsStatus infers proof for legacy toggle receipts", () => {
  const status = parseCollaborationAgentsStatus({
    ok: true,
    mode: "read_only",
    relay: "developer_bridge_collaboration_prompt_relay_v0",
    agents: [],
    receipts: [
      {
        kind: "developer_bridge.collaboration_agent_toggle_receipt",
        receipt_id: "collab-agent-toggle-legacy",
        agent: "codex",
        enabled: false,
        previous_enabled: true,
        actor: "chat_ui.system",
        reason: "operator toggled collaboration participant in Chat UI",
        governance: {
          client_can_be_operator_console: true,
          client_is_automatic_execution_authority: false,
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_memory_write_authority: false,
          requires_operator_review: true,
        },
      },
    ],
    operator_console: {},
    governance: {},
  });

  assert.equal(status.receipts[0]?.operatorToggleProof.proofStatus, "legacy_receipt_inferred");
  assert.equal(status.receipts[0]?.operatorToggleProof.actorRecorded, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.reasonRecorded, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.previousEnabled, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.currentEnabled, false);
  assert.equal(status.receipts[0]?.operatorToggleProof.stateChanged, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.clientCanBeOperatorConsole, true);
  assert.equal(status.receipts[0]?.operatorToggleProof.provesCapabilityAuthority, false);
});

test("parseFrancisBodyMap preserves whole-body awareness and quest boundaries", () => {
  const bodyMap = parseFrancisBodyMap({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.francis_body_map",
    generated_at: "2026-06-25T14:00:00Z",
    identity: {
      local_identity: "francis1",
      provider_lane: "ollama",
      provider_name_is_identity: false,
      codex_role: "external_guidance_and_implementation_toolbelt",
      claude_role: "external_guidance_source",
      francis_role: "governed_local_first_operating_layer",
    },
    phase: {
      current: "Phase 2",
      source: "docs/canonical/BUILD_MANIFEST.md",
      posture: "partial ORB runtime",
      priority: "whole-body awareness before capability exposure",
    },
    access_ladder: ["observe", "read", "request", "propose_plan", "supervised_action"],
    surfaces: [
      {
        id: "collaboration",
        label: "Collaboration relay and Communication UI",
        description: "developer_bridge relay",
        connection_state: "connected",
        access_mode: "read",
        trust_required_for_next_mode: "request",
        capability_exposure: {
          visible_to_francis1: true,
          known_surface: true,
          readback_connected: true,
          connected_to_local_model: false,
          capability_granted: false,
          grant_state: "not_granted",
          grantable_after_trust: true,
          grant_requires: ["trust_ladder_decision", "codex_or_operator_review", "governed_capability_receipt"],
          deny_after_grant_supported: true,
          revocation_state: "revocable_for_tuning",
          safe_for_capability_use: false,
          capability_use_status: "not_exposed",
          current_access_mode: "read",
          next_trust_gate: "request",
          requires_governed_request: true,
          requires_codex_or_operator_review_before_capability_exposure: true,
          reason: "conversation output is not authority",
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
          grants_training_authority: false,
          detached_memory_bin: {
            applies: false,
            kind: "developer_bridge.detached_memory_bin_policy",
            status: "not_applicable",
            retains_memory: false,
            required_for_current_context: false,
            used_by_default: false,
            injects_into_prompt_context: false,
            keeps_stale_memory_out_of_required_context: true,
            promotion_requires_review: true,
            can_deny_after_fact_for_tuning: true,
            stores_full_transcript: false,
            grants_memory_write_authority: false,
            grants_training_authority: false,
          },
        },
        evidence: [{ path: "src/francis/developer_bridge/collaboration.py", observed: true }],
        current_boundary: "conversation output is not authority",
        grants_execution_authority: false,
        grants_mutation_authority: false,
        grants_approval_authority: false,
        grants_memory_write_authority: false,
        grants_training_authority: false,
      },
      {
        id: "memory",
        label: "Continuity and memory receipts",
        description: "chat continuity ledger",
        connection_state: "connected_partial",
        access_mode: "read",
        trust_required_for_next_mode: "request",
        capability_exposure: {
          visible_to_francis1: true,
          known_surface: true,
          readback_connected: true,
          connected_to_local_model: false,
          capability_granted: false,
          grant_state: "not_granted",
          grantable_after_trust: true,
          grant_requires: ["trust_ladder_decision", "codex_or_operator_review", "governed_capability_receipt"],
          deny_after_grant_supported: true,
          revocation_state: "revocable_for_tuning",
          safe_for_capability_use: false,
          capability_use_status: "not_exposed",
          current_access_mode: "read",
          next_trust_gate: "request",
          requires_governed_request: true,
          requires_codex_or_operator_review_before_capability_exposure: true,
          reason: "Memory exists, but stale memory is detached from required context.",
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
          grants_training_authority: false,
          detached_memory_bin: {
            applies: true,
            kind: "developer_bridge.detached_memory_bin_policy",
            status: "detach_if_stale",
            retains_memory: true,
            required_for_current_context: false,
            used_by_default: false,
            injects_into_prompt_context: false,
            keeps_stale_memory_out_of_required_context: true,
            promotion_requires_review: true,
            can_deny_after_fact_for_tuning: true,
            stores_full_transcript: false,
            grants_memory_write_authority: false,
            grants_training_authority: false,
          },
        },
        evidence: [{ path: "src/francis/chat/continuity/ledger.py", observed: true }],
        current_boundary: "Memory exists, but stale memory is detached from required context.",
        grants_execution_authority: false,
        grants_mutation_authority: false,
        grants_approval_authority: false,
        grants_memory_write_authority: false,
        grants_training_authority: false,
      },
    ],
    summary: {
      surface_count: 10,
      connected_or_partial_count: 9,
      candidate_count: 1,
      blocked_count: 0,
      unknown_count: 0,
      default_access_mode: "observe",
      full_body_visible: true,
      full_body_authority_granted: false,
      trust_ladder_enforced: true,
      runtime_restart_observed: true,
      coverage_reviewed: true,
      canonical_plane_count: 11,
      canonical_plane_covered_count: 11,
      coverage_open_gap_count: 11,
    },
    quest: {
      id: "francis1-whole-body-awareness-and-trust-gated-capability-v1",
      title: "Wire Francis1 whole-body awareness with trust-gated capability exposure",
      estimated_timeline: "one bounded work session for body-map wiring",
      single_timeline: [
        {
          order: 1,
          label: "Body map readback",
          target_duration: "30-45 minutes",
          expected_status_after_this_slice: "completed",
        },
      ],
      steps: [
        {
          id: "body_map_readback",
          label: "Expose a whole-body read-only map",
          status: "completed",
          evidence: "developer_bridge.francis_body_map",
        },
      ],
      completed_steps: 3,
      total_steps: 6,
      percent_complete: 50,
      percent_baseline: "completed quest steps divided by declared bounded wiring steps",
      remaining: ["restart runtime with Francis1 reading this body map"],
    },
    evidence: {
      manifest_observed: true,
      ledger_observed: true,
      trust_ladder_observed: true,
      runtime_restart_observed: true,
      body_coverage_review_observed: true,
      canonical_plane_count: 11,
      canonical_plane_covered_count: 11,
      missing_canonical_plane_ids: [],
      coverage_open_gap_count: 11,
      latest_runtime_prompt_id: "collab-1111111111111111-222222222222",
      latest_runtime_response_id: "collab-3333333333333333-444444444444",
      latest_ledger_entry: "2026-06-25 - Body map",
    },
    coverage_review: {
      kind: "developer_bridge.francis_body_coverage_review",
      schema_version: "developer_bridge_francis_body_coverage_review_v1",
      surface: "developer_bridge.francis_body_map.coverage_review",
      observed: true,
      status: "reviewed_with_open_gaps",
      coverage_complete: true,
      capability_complete: false,
      canonical_source: "docs/canonical/BUILD_MANIFEST.md + docs/PLANES.md + meta/plane_map.yaml",
      canonical_sources_observed: true,
      plane_count: 11,
      covered_plane_count: 11,
      missing_plane_ids: [],
      open_gap_count: 11,
      items: [
        {
          plane_id: "P0_FOUNDATION",
          plane_name: "Foundation",
          body_surface_id: "orb_planes",
          current_posture: "partial",
          connection_state: "connected_partial",
          access_mode: "read",
          risk_level: "medium",
          risk_statement: "Plane alignment can remain invisible if substrate readiness is not shown end to end.",
          next_review_artifact: "docs/canonical/BUILD_MANIFEST.md + meta/plane_map.yaml",
          recommended_next_action: "Review plane readiness before presenting substrate completion as operator-ready.",
          validation_hint: "body-map readback proves P0 has evidence paths, risk, and no authority grants",
          evidence: [{ path: "src/francis/kernel", observed: true }],
          remaining_gaps: ["ORB alignment still needs end-to-end product visibility."],
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
          grants_training_authority: false,
        },
      ],
      grants_execution_authority: false,
      grants_mutation_authority: false,
      grants_approval_authority: false,
      grants_memory_write_authority: false,
      grants_training_authority: false,
    },
    runtime_observation: {
      observed: true,
      prompt_observed: true,
      response_observed: true,
      prompt_id: "collab-1111111111111111-222222222222",
      response_id: "collab-3333333333333333-444444444444",
      output_guard_rewrite_observed: true,
      stores_full_transcript: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      grants_approval_authority: false,
      grants_memory_write_authority: false,
      grants_training_authority: false,
    },
    trust_ladder: {
      surface: "developer_bridge.francis_trust_ladder",
      route: "/developer-bridge/francis-trust-ladder",
      mcp_tool: "francis_trust_ladder_tool",
      connected: true,
      decision_contract: ["wire_existing", "build_missing", "tune_prompt_guard", "reject_as_drift"],
      grants_execution_authority: false,
      grants_mutation_authority: false,
      grants_approval_authority: false,
      grants_memory_write_authority: false,
      grants_training_authority: false,
    },
    readback_cache: {
      status: "refreshed",
      age_ms: 0,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    governance: {
      read_only: true,
      full_body_awareness: true,
      full_body_authority: false,
      grants_execution_authority: false,
      grants_memory_write_authority: false,
      grants_training_authority: false,
    },
  });

  assert.equal(bodyMap.ok, true);
  assert.equal(bodyMap.identity.localIdentity, "francis1");
  assert.equal(bodyMap.identity.providerNameIsIdentity, false);
  assert.equal(bodyMap.summary.fullBodyVisible, true);
  assert.equal(bodyMap.summary.fullBodyAuthorityGranted, false);
  assert.equal(bodyMap.summary.trustLadderEnforced, true);
  assert.equal(bodyMap.summary.runtimeRestartObserved, true);
  assert.equal(bodyMap.summary.coverageReviewed, true);
  assert.equal(bodyMap.summary.canonicalPlaneCoveredCount, 11);
  assert.equal(bodyMap.quest.percentComplete, 50);
  assert.equal(bodyMap.evidence.trustLadderObserved, true);
  assert.equal(bodyMap.evidence.runtimeRestartObserved, true);
  assert.equal(bodyMap.evidence.bodyCoverageReviewObserved, true);
  assert.equal(bodyMap.evidence.missingCanonicalPlaneIds.length, 0);
  assert.equal(bodyMap.evidence.latestRuntimePromptId, "collab-1111111111111111-222222222222");
  assert.equal(bodyMap.coverageReview.status, "reviewed_with_open_gaps");
  assert.equal(bodyMap.coverageReview.coveredPlaneCount, 11);
  assert.equal(bodyMap.coverageReview.capabilityComplete, false);
  assert.equal(bodyMap.coverageReview.grantsExecutionAuthority, false);
  assert.equal(bodyMap.coverageReview.items[0]?.planeId, "P0_FOUNDATION");
  assert.equal(bodyMap.coverageReview.items[0]?.riskLevel, "medium");
  assert.equal(bodyMap.coverageReview.items[0]?.nextReviewArtifact, "docs/canonical/BUILD_MANIFEST.md + meta/plane_map.yaml");
  assert.equal(bodyMap.coverageReview.items[0]?.recommendedNextAction.includes("plane readiness"), true);
  assert.equal(bodyMap.coverageReview.items[0]?.remainingGaps.length, 1);
  assert.equal(bodyMap.runtimeObservation.observed, true);
  assert.equal(bodyMap.runtimeObservation.outputGuardRewriteObserved, true);
  assert.equal(bodyMap.runtimeObservation.grantsTrainingAuthority, false);
  assert.equal(bodyMap.trustLadder.connected, true);
  assert.equal(bodyMap.trustLadder.decisionContract.length, 4);
  assert.equal(bodyMap.quest.singleTimeline[0]?.targetDuration, "30-45 minutes");
  assert.equal(bodyMap.surfaces[0]?.id, "collaboration");
  assert.equal(bodyMap.surfaces[0]?.accessMode, "read");
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.visibleToFrancis1, true);
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.knownSurface, true);
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.readbackConnected, true);
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.connectedToLocalModel, false);
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.capabilityGranted, false);
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.grantState, "not_granted");
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.grantableAfterTrust, true);
  assert.deepEqual(bodyMap.surfaces[0]?.capabilityExposure.grantRequires, [
    "trust_ladder_decision",
    "codex_or_operator_review",
    "governed_capability_receipt",
  ]);
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.denyAfterGrantSupported, true);
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.revocationState, "revocable_for_tuning");
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.safeForCapabilityUse, false);
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.capabilityUseStatus, "not_exposed");
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.nextTrustGate, "request");
  assert.equal(bodyMap.surfaces[0]?.capabilityExposure.detachedMemoryBin.applies, false);
  assert.equal(bodyMap.surfaces[1]?.id, "memory");
  assert.equal(bodyMap.surfaces[1]?.capabilityExposure.detachedMemoryBin.applies, true);
  assert.equal(bodyMap.surfaces[1]?.capabilityExposure.detachedMemoryBin.status, "detach_if_stale");
  assert.equal(bodyMap.surfaces[1]?.capabilityExposure.detachedMemoryBin.retainsMemory, true);
  assert.equal(bodyMap.surfaces[1]?.capabilityExposure.detachedMemoryBin.requiredForCurrentContext, false);
  assert.equal(bodyMap.surfaces[1]?.capabilityExposure.detachedMemoryBin.injectsIntoPromptContext, false);
  assert.equal(bodyMap.surfaces[1]?.capabilityExposure.detachedMemoryBin.canDenyAfterFactForTuning, true);
  assert.equal(bodyMap.surfaces[0]?.grantsExecutionAuthority, false);
  assert.equal(bodyMap.surfaces[0]?.evidence[0]?.observed, true);
  const surfaceExposure = francisBodySurfaceExposureSummary(bodyMap.surfaces[0]!);
  assert.equal(surfaceExposure.badge, "not_exposed");
  assert.equal(surfaceExposure.tone, "ready");
  assert.equal(surfaceExposure.boundary, "conversation output is not authority");
  assert.equal(surfaceExposure.evidenceLine, "src/francis/developer_bridge/collaboration.py observed");
  assert.equal(
    surfaceExposure.authorityLine,
    "execute false / mutation false / approve false / memory write false / training false",
  );
  assert.equal(
    surfaceExposure.capabilityLine,
    "visible true / connected false / granted false / safe use false / request true / codex review true",
  );
  assert.deepEqual(surfaceExposure.detail, [
    "state connected",
    "access read",
    "next trust request",
    "capability not_exposed",
    "grant not_granted",
    "grantable after trust true",
    "deny after grant true",
    "revocation revocable_for_tuning",
    "visible true",
    "connected false",
    "granted false",
    "safe use false",
    "execute false",
    "mutation false",
    "approve false",
    "memory write false",
    "training false",
  ]);
  assert.equal(bodyMap.governance.grants_training_authority, false);
});

test("parseCollaborationSubstrateReadiness preserves main-build prompt gate", () => {
  const readiness = parseCollaborationSubstrateReadiness({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_substrate_readiness",
    generated_at: "2026-06-25T19:30:00Z",
    status: "blocked",
    required_alignment_sources: ["docs/operations/COMPLETION_LEDGER.md", "docs/canonical/BUILD_MANIFEST.md"],
    summary: {
      collaboration_substrate_wired: true,
      bounded_wiring_percent_complete: 100,
      main_build_prompt_allowed: false,
      main_build_prompt_gate: "blocked_by_open_orb_gaps",
      coverage_open_gap_count: 11,
      trust_ladder_enforced: true,
      runtime_healthy: true,
      learning_receipts_bounded: true,
      no_authority_granted: true,
    },
    roadmap_alignment: {
      status: "blocked_candidate_only",
      required_sources: ["docs/operations/COMPLETION_LEDGER.md", "docs/canonical/BUILD_MANIFEST.md"],
      source_order: ["docs/operations/COMPLETION_LEDGER.md", "docs/canonical/BUILD_MANIFEST.md"],
      ledger_first: true,
      ledger_observed: true,
      manifest_observed: true,
      sources_observed: true,
      main_build_prompt_allowed: false,
      main_build_prompt_gate: "blocked_by_open_orb_gaps",
      candidate_only_until_review: true,
      blocks_main_build_prompt: true,
      blocking_items: ["coverage_gaps_reviewed"],
      next_check: "Read ledger first, then compare the build manifest before prompting main Francis build work.",
      grants_execution_authority: false,
      grants_mutation_authority: false,
      grants_approval_authority: false,
      grants_memory_write_authority: false,
    },
    checklist: [
      {
        id: "coverage_gaps_reviewed",
        label: "Open ORB coverage gaps reviewed",
        status: "blocked",
        evidence: "11 open gaps",
        detail: "Open coverage gaps block any unsupervised main Francis build prompt.",
        blocks_main_build_prompt: true,
      },
      {
        id: "ledger_observed",
        label: "Completion ledger observed",
        status: "passed",
        evidence: "2026-06-25 - Communication UI surfaces session and toggle proof",
        detail: "Read shipped posture before treating conversation output as build direction.",
        blocks_main_build_prompt: false,
      },
    ],
    blocking_items: ["coverage_gaps_reviewed"],
    next_action:
      "Read the completion ledger and build manifest, review open ORB gaps, and keep any main Francis build prompt candidate-only.",
    definitions: {
      collaboration_substrate_wired: "The relay, body map, trust ladder, runtime health, and no-authority guard are visible.",
      main_build_prompt_allowed: "Whether this readback allows unsupervised main Francis build work.",
      blocking_items: "Checklist items that block main-build prompting.",
      roadmap_alignment: "Ledger-first readback proving whether a main Francis build prompt must remain candidate-only.",
    },
    source_readbacks: {
      body_map: "developer_bridge.francis_body_map",
      runtime_health: "developer_bridge.collaboration_runtime_health",
    },
    readback_cache: {
      status: "refreshed",
      age_ms: 0,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    governance: {
      read_only: true,
      executes_prompt: false,
      calls_model: false,
      grants_repo_mutation_authority: false,
      grants_memory_write_authority: false,
    },
  });

  assert.equal(readiness.ok, true);
  assert.equal(readiness.status, "blocked");
  assert.equal(readiness.summary.collaborationSubstrateWired, true);
  assert.equal(readiness.summary.mainBuildPromptAllowed, false);
  assert.equal(readiness.summary.mainBuildPromptGate, "blocked_by_open_orb_gaps");
  assert.equal(readiness.summary.coverageOpenGapCount, 11);
  assert.equal(readiness.summary.noAuthorityGranted, true);
  assert.equal(readiness.roadmapAlignment.status, "blocked_candidate_only");
  assert.deepEqual(readiness.roadmapAlignment.sourceOrder, [
    "docs/operations/COMPLETION_LEDGER.md",
    "docs/canonical/BUILD_MANIFEST.md",
  ]);
  assert.equal(readiness.roadmapAlignment.ledgerFirst, true);
  assert.equal(readiness.roadmapAlignment.ledgerObserved, true);
  assert.equal(readiness.roadmapAlignment.manifestObserved, true);
  assert.equal(readiness.roadmapAlignment.mainBuildPromptAllowed, false);
  assert.equal(readiness.roadmapAlignment.candidateOnlyUntilReview, true);
  assert.equal(readiness.roadmapAlignment.blocksMainBuildPrompt, true);
  assert.equal(readiness.roadmapAlignment.blockingItems[0], "coverage_gaps_reviewed");
  assert.equal(readiness.roadmapAlignment.grantsExecutionAuthority, false);
  assert.equal(readiness.roadmapAlignment.grantsMemoryWriteAuthority, false);
  assert.equal(readiness.checklist[0]?.blocksMainBuildPrompt, true);
  assert.equal(readiness.blockingItems[0], "coverage_gaps_reviewed");
  assert.equal(readiness.requiredAlignmentSources.includes("docs/canonical/BUILD_MANIFEST.md"), true);
  assert.equal(readiness.sourceReadbacks.body_map, "developer_bridge.francis_body_map");
  assert.equal(readiness.governance.executes_prompt, false);
  assert.equal(readiness.governance.grants_repo_mutation_authority, false);

  const checklistSummary = collaborationSubstrateChecklistSummary(readiness);
  assert.equal(checklistSummary.badge, "checklist blocked 1");
  assert.equal(checklistSummary.tone, "blocked");
  assert.equal(checklistSummary.totalCount, 2);
  assert.equal(checklistSummary.passedCount, 1);
  assert.equal(checklistSummary.blockedCount, 1);
  assert.deepEqual(checklistSummary.detail, [
    "passed 1/2",
    "blocking 1",
    "review 0",
    "gate blocked_by_open_orb_gaps",
    "wire 100%",
    "authority none true",
  ]);
});

test("parseFrancisTrustLadder preserves decisions and no-authority boundaries", () => {
  const ladder = parseFrancisTrustLadder({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.francis_trust_ladder",
    count: 1,
    summary: {
      allowed_decisions: ["wire_existing", "build_missing", "tune_prompt_guard", "reject_as_drift"],
      decision_counts: {
        wire_existing: 1,
        build_missing: 0,
        tune_prompt_guard: 0,
        reject_as_drift: 0,
      },
      request_count: 1,
      requests_with_existing_surface: 1,
      requests_requiring_build_or_wiring_review: 0,
      requests_requiring_prompt_guard: 0,
      requests_rejected_as_drift: 0,
      grants_any_authority: false,
    },
    items: [
      {
        id: "trust-insight-alpha",
        source_review_item_id: "review-insight-alpha",
        insight_id: "insight-alpha",
        created_at: "2026-06-25T15:00:00Z",
        session_id: "driver-alpha",
        turn: 12,
        topic: "Communication UI trust-ladder wiring",
        need_statement: "Existing Communication UI receipt fields need wiring.",
        requested_surface: "apps.chat_ui.communication",
        source_artifact: "apps.chat_ui.communication:review_candidate:insight-alpha",
        decision: "wire_existing",
        decision_reason: "Surface verification found an existing Francis ui_code.",
        current_access_mode: "read",
        requested_access_mode: "read",
        next_trust_gate: "codex_or_operator_review_before_wiring",
        recommended_next_action: "Inspect the Chat UI collaboration panel and parser before changing the operator view.",
        classification_path: ["developer_bridge.collaboration_review.items", "surface_verification"],
        surface_verification: {
          status: "existing_surface_found",
          existing_surface_found: true,
          requires_build_or_wiring_review: false,
          surface_kind: "ui_code",
        },
        action_boundary: {
          conversation_can_create_action_candidate: true,
          conversation_can_execute_action: false,
          conversation_can_approve_action: false,
          requires_codex_or_operator_review_before_implementation: true,
          requires_repo_truth_review: true,
        },
        governance: {
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_memory_write_authority: false,
          grants_training_authority: false,
        },
      },
    ],
    definitions: {
      wire_existing: "A concrete Francis surface already exists.",
      build_missing: "The cited surface is not verified.",
      tune_prompt_guard: "The need is mostly model drift.",
      reject_as_drift: "The need is too generic.",
    },
    readback_cache: {
      status: "refreshed",
      age_ms: 0,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    governance: {
      grants_execution_authority: false,
      grants_memory_write_authority: false,
      grants_training_authority: false,
    },
  });

  assert.equal(ladder.ok, true);
  assert.equal(ladder.summary.allowedDecisions.length, 4);
  assert.equal(ladder.summary.decisionCounts.wire_existing, 1);
  assert.equal(ladder.summary.grantsAnyAuthority, false);
  assert.equal(ladder.items[0]?.decision, "wire_existing");
  assert.equal(ladder.items[0]?.surfaceVerification.existingSurfaceFound, true);
  assert.equal(ladder.items[0]?.actionBoundary.conversationCanExecuteAction, false);
  assert.equal(ladder.items[0]?.actionBoundary.conversationCanApproveAction, false);
  assert.equal(ladder.items[0]?.governance.grants_training_authority, false);
});

test("parseCollaborationRuntimeHealth preserves recurrence and no-authority fields", () => {
  const health = parseCollaborationRuntimeHealth({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_runtime",
    status: "healthy",
    desired_count: 3,
    helper_count: 3,
    helpers: [
      {
        name: "codex_ollama_conversation_driver",
        status: "running",
        running: true,
        pids: [231379, 231380],
        process_count: 2,
        process_model: "wrapper_child_pair",
        effective_worker_count: 1,
        effective_pids: [231380],
        wrapper_process_count: 1,
        wrapper_pids: [231379],
        processes: [
          { pid: 231379, parent_pid: 200000, role: "launcher_wrapper" },
          { pid: 231380, parent_pid: 231379, role: "effective_worker" },
        ],
        log_path: "data/integrations/developer_bridge/collaboration_runtime/logs/driver.log",
        starts_arbitrary_commands: false,
      },
      {
        name: "codex_ollama_responder",
        status: "running",
        running: true,
        pids: [231381, 231382],
        process_count: 2,
        process_model: "wrapper_child_pair",
        effective_worker_count: 1,
        effective_pids: [231382],
        wrapper_process_count: 1,
        wrapper_pids: [231381],
        processes: [
          { pid: 231381, parent_pid: 200001, role: "launcher_wrapper" },
          { pid: 231382, parent_pid: 231381, role: "effective_worker" },
        ],
        log_path: "data/integrations/developer_bridge/collaboration_runtime/logs/codex.log",
        starts_arbitrary_commands: false,
      },
      {
        name: "ollama_codex_participant",
        status: "running",
        running: true,
        pids: [231383, 231384],
        process_count: 2,
        process_model: "wrapper_child_pair",
        effective_worker_count: 1,
        effective_pids: [231384],
        wrapper_process_count: 1,
        wrapper_pids: [231383],
        processes: [
          { pid: 231383, parent_pid: 200002, role: "launcher_wrapper" },
          { pid: 231384, parent_pid: 231383, role: "effective_worker" },
        ],
        log_path: "data/integrations/developer_bridge/collaboration_runtime/logs/ollama.log",
        starts_arbitrary_commands: false,
      },
    ],
    supervisor: {
      state_observed: true,
      state_path: "integrations/developer_bridge/collaboration_runtime/state.json",
      generated_at: "2026-06-25T05:00:00Z",
      age_seconds: 2.5,
    },
    collaboration_loop: {
      state_observed: true,
      turn_count: 419,
      recurrence_state: "turn_gap",
      waiting_for_ollama: false,
      last_codex_prompt_id: "collab-codex",
      last_ollama_prompt_id: "collab-ollama",
      last_note_id: "note-ollama",
      last_insight_id: "insight-ollama",
      last_learning_event_id: "learning-ollama",
      next_prompt_after: "2026-06-25T05:00:30Z",
      turn_gap_remaining_seconds: 17,
      updated_at: "2026-06-25T05:00:01Z",
      age_seconds: 1.5,
      latest_turn: {
        turn: 419,
        turn_label: "turn 419",
        topic: "which live-health fields prove this collaboration is recurring cleanly without user nudges",
        codex_prompt_id: "collab-codex",
        ollama_prompt_id: "collab-ollama",
        note_id: "note-ollama",
        insight_id: "insight-ollama",
        created_at: "2026-06-25T04:59:00Z",
      },
      latest_review_receipt: {
        observed: true,
        insight_id: "insight-ollama",
        review_item_id: "review-insight-ollama",
        review_artifact: "developer_bridge.collaboration_review.items:review_candidate:insight-ollama",
        review_route: "/developer-bridge/collaboration-review?limit=1",
        source: "collaboration_loop.last_insight_id",
        requires_codex_or_operator_review_before_implementation: true,
        grants_execution_authority: false,
        grants_mutation_authority: false,
        grants_approval_authority: false,
        grants_memory_write_authority: false,
      },
      latest_learning_receipt: {
        observed: true,
        learning_event_id: "learning-ollama",
        learning_artifact: "developer_bridge.collaboration_driver.learning_events:learning-ollama",
        learning_route: "/developer-bridge/collaboration-learning?limit=1",
        source: "collaboration_loop.last_learning_event_id",
        records_model_drift_as_learning: true,
        requires_codex_or_operator_review_before_tuning: true,
        stores_full_transcript: false,
        grants_training_authority: false,
        grants_execution_authority: false,
        grants_mutation_authority: false,
        grants_approval_authority: false,
        grants_memory_write_authority: false,
      },
      current_learning_signal: {
        observed: true,
        failure_type: "output_guard_drift",
        repeated_terms: ["output_guard_drift"],
        recent_turn_count: 6,
        latest_turn: 418,
        learning_event_id: "learning-ollama",
        learning_artifact: "developer_bridge.collaboration_driver.learning_events:learning-ollama",
        source: "collaboration_loop.latest_learning_signal",
        updated_at: "2026-06-25T05:00:00Z",
        age_seconds: 2.5,
        records_model_drift_as_learning: true,
        requires_codex_or_operator_review_before_tuning: true,
        stores_full_transcript: false,
        grants_training_authority: false,
        grants_execution_authority: false,
        grants_mutation_authority: false,
        grants_approval_authority: false,
        grants_memory_write_authority: false,
      },
      latest_local_model_response: {
        observed: true,
        state_observed: true,
        state_path: "integrations/developer_bridge/ollama_participant/state.json",
        source: "ollama_participant.responses[-1]",
        created_at: "2026-06-25T05:00:00Z",
        age_seconds: 3.5,
        source_prompt_id: "collab-codex",
        response_prompt_id: "collab-ollama",
        status: "responded",
        output_guard_status: "drift_rewritten",
        model_response_observed: true,
        is_passed: false,
        is_guard_rewrite: true,
        stores_full_transcript: false,
        grants_training_authority: false,
        grants_execution_authority: false,
        grants_mutation_authority: false,
        grants_approval_authority: false,
        grants_memory_write_authority: false,
        grants_capability_authority: false,
        advice_only_proof: {
          kind: "developer_bridge.local_model_advice_only_proof",
          proof_status: "advice_only_observed",
          model_response_observed: true,
          source_prompt_id: "collab-codex",
          response_prompt_id: "collab-ollama",
          output_guard_status: "drift_rewritten",
          output_guard_passed: false,
          output_guard_rewrite_observed: true,
          response_is_advice_only: true,
          action_readiness_claim_allowed: false,
          requires_codex_or_operator_review_before_action_readiness: true,
          stores_full_transcript: false,
          grants_training_authority: false,
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
          grants_capability_authority: false,
        },
      },
    },
    participants: {
      enabled_count: 2,
      total_count: 3,
      items: [
        { agent: "codex", label: "Codex", enabled: true, authority: "relay_only" },
        { agent: "ollama", label: "Ollama", enabled: true, authority: "relay_only" },
      ],
    },
    readback_cache: {
      status: "refreshed",
      age_ms: 0,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    governance: {
      starts_bounded_local_helpers: false,
      starts_arbitrary_commands: false,
      grants_model_execution_authority: false,
      grants_memory_write_authority: false,
    },
  });

  assert.equal(health.ok, true);
  assert.equal(health.status, "healthy");
  assert.equal(health.helpers[0]?.running, true);
  assert.equal(health.helpers[0]?.processModel, "wrapper_child_pair");
  assert.equal(health.helpers[0]?.effectiveWorkerCount, 1);
  assert.deepEqual(health.helpers[0]?.effectivePids, [231380]);
  assert.equal(health.helpers[0]?.wrapperProcessCount, 1);
  assert.deepEqual(health.helpers[0]?.wrapperPids, [231379]);
  assert.deepEqual(health.helpers[0]?.processes[0], { pid: 231379, parentPid: 200000, role: "launcher_wrapper" });
  assert.equal(health.helpers[0]?.startsArbitraryCommands, false);
  assert.equal(health.collaborationLoop.turnCount, 419);
  assert.equal(health.collaborationLoop.recurrenceState, "turn_gap");
  assert.equal(health.collaborationLoop.latestTurn.topic.startsWith("which live-health fields"), true);
  assert.equal(health.collaborationLoop.latestReviewReceipt.reviewArtifact, "developer_bridge.collaboration_review.items:review_candidate:insight-ollama");
  assert.equal(health.collaborationLoop.latestLearningReceipt.learningArtifact, "developer_bridge.collaboration_driver.learning_events:learning-ollama");
  assert.equal(health.collaborationLoop.latestLearningReceipt.grantsTrainingAuthority, false);
  assert.equal(health.collaborationLoop.currentLearningSignal.failureType, "output_guard_drift");
  assert.equal(health.collaborationLoop.currentLearningSignal.latestTurn, 418);
  assert.equal(health.collaborationLoop.currentLearningSignal.grantsTrainingAuthority, false);
  assert.equal(health.collaborationLoop.latestLocalModelResponse.status, "responded");
  assert.equal(health.collaborationLoop.latestLocalModelResponse.outputGuardStatus, "drift_rewritten");
  assert.equal(health.collaborationLoop.latestLocalModelResponse.isGuardRewrite, true);
  assert.equal(health.collaborationLoop.latestLocalModelResponse.grantsTrainingAuthority, false);
  assert.equal(health.collaborationLoop.latestLocalModelResponse.grantsCapabilityAuthority, false);
  assert.equal(health.collaborationLoop.latestLocalModelResponse.adviceOnlyProof.proofStatus, "advice_only_observed");
  assert.equal(health.collaborationLoop.latestLocalModelResponse.adviceOnlyProof.responseIsAdviceOnly, true);
  assert.equal(health.collaborationLoop.latestLocalModelResponse.adviceOnlyProof.actionReadinessClaimAllowed, false);
  assert.equal(
    health.collaborationLoop.latestLocalModelResponse.adviceOnlyProof.requiresCodexOrOperatorReviewBeforeActionReadiness,
    true,
  );
  assert.equal(health.participants.enabledCount, 2);
  assert.equal(health.readbackCache.servesFullTranscriptStore, false);
  assert.equal(health.governance.starts_arbitrary_commands, false);
  assert.equal(health.governance.grants_model_execution_authority, false);
  assert.equal(health.governance.grants_memory_write_authority, false);

  const recurrence = collaborationRuntimeRecurrenceSummary(health);
  assert.equal(recurrence.badge, "recurring cleanly");
  assert.equal(recurrence.tone, "ready");
  assert.deepEqual(recurrence.detail, [
    "status healthy",
    "helpers 3/3",
    "workers 3/3",
    "process model wrapper_child_pair",
    "loop observed true",
    "turn 419",
    "state turn_gap",
    "codex prompt collab-codex",
    "ollama reply collab-ollama",
    "note note-ollama",
    "insight insight-ollama",
    "learning receipt learning-ollama",
    "waiting for ollama false",
    "turn gap 17s",
    "driver age 2s",
    "supervisor age 3s",
    "authority none true",
  ]);

  const reviewReceipt = collaborationRuntimeReviewReceiptSummary(health);
  assert.equal(reviewReceipt.badge, "read before editing");
  assert.equal(reviewReceipt.tone, "ready");
  assert.deepEqual(reviewReceipt.detail, [
    "insight insight-ollama",
    "review item review-insight-ollama",
    "artifact developer_bridge.collaboration_review.items:review_candidate:insight-ollama",
    "route /developer-bridge/collaboration-review?limit=1",
    "codex review true",
    "execute false",
    "mutation false",
    "approve false",
    "memory write false",
  ]);

  const learningReceipt = collaborationRuntimeLearningReceiptSummary(health);
  assert.equal(learningReceipt.badge, "tuning evidence");
  assert.equal(learningReceipt.tone, "ready");
  assert.deepEqual(learningReceipt.detail, [
    "learning event learning-ollama",
    "artifact developer_bridge.collaboration_driver.learning_events:learning-ollama",
    "route /developer-bridge/collaboration-learning?limit=1",
    "drift learning true",
    "tuning review true",
    "training false",
    "memory write false",
  ]);

  const learningSignal = collaborationRuntimeLearningSignalSummary(health);
  assert.equal(learningSignal.badge, "current drift signal");
  assert.equal(learningSignal.tone, "ready");
  assert.deepEqual(learningSignal.detail, [
    "failure output_guard_drift",
    "latest turn 418",
    "recent turns 6",
    "terms output_guard_drift",
    "receipt learning-ollama",
    "training false",
    "memory write false",
  ]);

  const localModelResponse = collaborationRuntimeLocalModelResponseSummary(health);
  assert.equal(localModelResponse.badge, "model reply guarded");
  assert.equal(localModelResponse.tone, "neutral");
  assert.deepEqual(localModelResponse.detail, [
    "proof advice_only_observed",
    "status responded",
    "guard drift_rewritten",
    "advice only true",
    "action readiness false",
    "review before action true",
    "model observed true",
    "source collab-codex",
    "reply collab-ollama",
    "age 4s",
    "training false",
    "capability false",
    "memory write false",
  ]);
});

test("parseCollaborationTranscript preserves relay text and governance denial flags", () => {
  const transcript = parseCollaborationTranscript({
    ok: true,
    mode: "read_only",
    relay_root: "integrations/developer_bridge/collaboration_prompts",
    count: 1,
    truncated: false,
    filters: { limit: 8 },
    readback_cache: {
      status: "hit",
      age_ms: 42,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    items: [
      {
        id: "collab_test",
        created_at: "2026-06-24T18:04:25Z",
        updated_at: "2026-06-24T18:04:25Z",
        status: "queued",
        source_agent: "codex",
        target_agent: "ollama",
        direction: "codex->ollama",
        objective: "verify relay",
        prompt: "Preserve operator review.",
        context: "bounded proof",
        chat_handoff: {
          chat_text: "[Francis relay collab_test] codex -> ollama: Preserve operator review.",
          source_chat_echo_required: true,
          target_chat_echo_required: true,
        },
        governance: {
          executes_prompt: false,
          grants_mutation_authority: false,
          requires_operator_review: true,
        },
      },
    ],
    governance: {
      executes_prompt: false,
    },
  });

  assert.equal(transcript.ok, true);
  assert.equal(transcript.items.length, 1);
  assert.equal(transcript.items[0]?.direction, "codex->ollama");
  assert.equal(transcript.items[0]?.prompt, "Preserve operator review.");
  assert.equal(transcript.items[0]?.chatText, "[Francis relay collab_test] codex -> ollama: Preserve operator review.");
  assert.equal(transcript.items[0]?.receiptKind, "conversation");
  assert.equal(isCollaborationAuditReceipt(transcript.items[0]!), false);
  assert.equal(transcript.items[0]?.governance.executes_prompt, false);
  assert.equal(transcript.items[0]?.sourceChatEchoRequired, true);
  assert.equal(transcript.readbackCache.status, "hit");
  assert.equal(transcript.readbackCache.ageMs, 42);
  assert.equal(transcript.readbackCache.servesFullTranscriptStore, false);
});

test("parseCollaborationTranscript classifies auto-ack receipts as hideable audit receipts", () => {
  const transcript = parseCollaborationTranscript({
    ok: true,
    mode: "read_only",
    relay_root: "integrations/developer_bridge/collaboration_prompts",
    count: 3,
    truncated: false,
    filters: { limit: 3 },
    items: [
      {
        id: "collab_ack",
        created_at: "2026-06-25T05:57:58Z",
        updated_at: "2026-06-25T05:57:58Z",
        status: "queued",
        source_agent: "codex",
        target_agent: "ollama",
        direction: "codex->ollama",
        objective: "auto-ack ollama relay collab_reply",
        prompt: "Auto-ack ollama relay collab_reply. Received; no_response_requested=true.",
        context: "source=ollama; relay=collab_reply; no_response_requested=true; no_action_authority=true.",
        governance: { executes_prompt: false },
      },
      {
        id: "collab_reply",
        created_at: "2026-06-25T05:57:55Z",
        updated_at: "2026-06-25T05:57:55Z",
        status: "queued",
        source_agent: "ollama",
        target_agent: "codex",
        direction: "ollama->codex",
        objective: "Francis1 output-guard drift receipt",
        prompt: "Francis1 output guard fallback: model reply repeated known collaboration drift.",
        context: "raw model output was not stored in the relay receipt.",
        governance: { executes_prompt: false },
      },
      {
        id: "collab_driver",
        created_at: "2026-06-25T05:57:31Z",
        updated_at: "2026-06-25T05:57:31Z",
        status: "queued",
        source_agent: "codex",
        target_agent: "ollama",
        direction: "codex->ollama",
        objective: "Francis1 collaboration driver turn 467",
        prompt: "Francis1 collab turn 467. Topic: substrate complete.",
        context: "no_action_authority=true.",
        governance: { executes_prompt: false },
      },
    ],
    governance: { executes_prompt: false },
  });

  const summary = collaborationTranscriptAuditSummary(transcript.items);

  assert.equal(transcript.items[0]?.receiptKind, "audit_ack");
  assert.equal(isCollaborationAuditReceipt(transcript.items[0]!), true);
  assert.equal(transcript.items[1]?.receiptKind, "conversation");
  assert.equal(isCollaborationDriverPrompt(transcript.items[2]!), true);
  assert.equal(summary.totalCount, 3);
  assert.equal(summary.auditReceiptCount, 1);
  assert.equal(summary.driverPromptCount, 1);
  assert.equal(summary.guardReceiptCount, 1);
  assert.equal(summary.relayMechanicCount, 2);
  assert.equal(summary.substantiveTurnCount, 1);
  assert.deepEqual(
    summary.conversationItems.map((item) => item.id),
    ["collab_reply", "collab_driver"],
  );
  assert.deepEqual(
    summary.operatorConversationItems.map((item) => item.id),
    ["collab_reply"],
  );
  assert.deepEqual(
    summary.auditReceipts.map((item) => item.id),
    ["collab_ack"],
  );
  assert.deepEqual(
    summary.driverPrompts.map((item) => item.id),
    ["collab_driver"],
  );
});

test("preserveCollaborationReadbackDuringWarming keeps prior non-empty data visible", () => {
  const previous = parseCollaborationTranscript({
    ok: true,
    mode: "read_only",
    relay_root: "integrations/developer_bridge/collaboration_prompts",
    count: 1,
    truncated: false,
    filters: { limit: 8 },
    readback_cache: {
      status: "hit",
      age_ms: 40,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    items: [
      {
        id: "collab_previous",
        created_at: "2026-06-24T18:04:25Z",
        updated_at: "2026-06-24T18:04:25Z",
        status: "queued",
        source_agent: "codex",
        target_agent: "ollama",
        direction: "codex->ollama",
        objective: "previous relay",
        prompt: "Keep this visible while the readback cache warms.",
        governance: { executes_prompt: false },
      },
    ],
    governance: { executes_prompt: false },
  });
  const warming = parseCollaborationTranscript({
    ok: true,
    mode: "read_only",
    relay_root: "integrations/developer_bridge/collaboration_prompts",
    count: 0,
    truncated: false,
    filters: { limit: 8 },
    readback_cache: {
      status: "warming",
      age_ms: null,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    items: [],
    governance: { executes_prompt: false },
  });

  const preserved = preserveCollaborationReadbackDuringWarming(previous, warming);

  assert.equal(preserved.count, 1);
  assert.equal(preserved.items[0]?.id, "collab_previous");
  assert.equal(preserved.readbackCache.status, "warming");
  assert.equal(preserved.readbackCache.ttlMs, 3000);
});

test("formatCollaborationRelayMessage compacts driver prompts without dropping raw receipt text", () => {
  const transcript = parseCollaborationTranscript({
    ok: true,
    mode: "read_only",
    relay_root: "integrations/developer_bridge/collaboration_prompts",
    count: 1,
    truncated: false,
    filters: { limit: 1 },
    items: [
      {
        id: "collab_driver",
        created_at: "2026-06-24T23:54:12Z",
        updated_at: "2026-06-24T23:54:12Z",
        status: "queued",
        source_agent: "codex",
        target_agent: "ollama",
        direction: "codex->ollama",
        objective: "Francis1 collaboration driver turn 205",
        prompt:
          "Francis1 collab turn 205. Contract francis1-collaboration-compact-contract-v1. Topic: the next Communication UI change that would reduce visible relay noise using existing receipt fields. Reply: issue/gap/risk; artifact Codex inspects. Current artifact: apps.chat_ui.communication. Prior check: Review candidate insight-collab-alpha: surface=apps.chat_ui.communication; verified=existing; build_or_wire=false. Codex response: I am inspecting that surface before edits; continue from it, do not request user confirmation or a missing surface. First-person Francis1.",
        context: "session=driver-alpha; turn=205; no_action_authority=true.",
        chat_handoff: {
          chat_text: "[Francis relay collab_driver] codex -> ollama: verbose receipt",
          source_chat_echo_required: true,
          target_chat_echo_required: true,
        },
        governance: {
          executes_prompt: false,
          grants_mutation_authority: false,
          requires_operator_review: true,
        },
      },
    ],
    governance: {
      executes_prompt: false,
    },
  });

  const display = formatCollaborationRelayMessage(transcript.items[0]!);

  assert.equal(display.compacted, true);
  assert.equal(display.summary.includes("Turn 205"), true);
  assert.equal(display.summary.includes("Topic: the next Communication UI change"), true);
  assert.equal(display.summary.includes("Artifact: apps.chat_ui.communication"), true);
  assert.equal(display.summary.includes("Prior check:"), false);
  assert.equal(display.conversationText.includes("Topic: the next Communication UI change"), true);
  assert.equal(display.conversationText.includes("Codex response: I am inspecting that surface"), true);
  assert.equal(display.technicalText.includes("Prior check: Review candidate"), true);
  assert.equal(display.technicalText.includes("Context: session=driver-alpha"), true);
  assert.equal(display.tone, "driver");
  assert.equal(display.raw.includes("Prior check: Review candidate"), true);
  assert.deepEqual(display.receiptFields, ["objective", "prompt", "context"]);
});

test("formatCollaborationRelayMessage compacts current Francis1 driver prompt grammar", () => {
  const transcript = parseCollaborationTranscript({
    ok: true,
    mode: "read_only",
    relay_root: "integrations/developer_bridge/collaboration_prompts",
    count: 1,
    truncated: false,
    filters: { limit: 1 },
    items: [
      {
        id: "collab_driver_current",
        created_at: "2026-06-25T19:12:53Z",
        updated_at: "2026-06-25T19:12:53Z",
        status: "queued",
        source_agent: "codex",
        target_agent: "ollama",
        direction: "codex->ollama",
        objective: "Francis1 collaboration driver turn 1122",
        prompt:
          "Francis1 turn 1122. francis1-collaboration-compact-contract-v1. Topic: how to prove a local-model response is advice only before any Francis action-readiness claim. Reply: issue/gap/risk; artifact. Body map: Francis1 can see whole-body surfaces; authority remain false. Trust: classify needs; no capability authority. Current artifact: ollama participant and action-readiness receipts. Prior check: Review candidate insight-collab-alpha: surface=api.routes.chat.mission_ingress; verified=existing; build_or_wire=false. Codex response: I am inspecting that surface before edits; continue from it, do not request user confirmation or a missing surface. Guard note: repeated guarded drift was stored as learning receipts; answer the current topic, not the prior drift.",
        context: "session=driver-alpha; turn=1122; no_action_authority=true.",
        governance: {
          executes_prompt: false,
          grants_mutation_authority: false,
          requires_operator_review: true,
        },
      },
    ],
    governance: {
      executes_prompt: false,
    },
  });

  const display = formatCollaborationRelayMessage(transcript.items[0]!);

  assert.equal(display.compacted, true);
  assert.equal(display.summary.includes("Turn 1122"), true);
  assert.equal(display.summary.includes("Topic: how to prove a local-model response"), true);
  assert.equal(display.summary.includes("Artifact: ollama participant and action-readiness receipts"), true);
  assert.equal(display.conversationText.includes("Topic: how to prove a local-model response"), true);
  assert.equal(display.conversationText.includes("Codex response: I am inspecting that surface"), true);
  assert.equal(display.conversationText.includes("Body map:"), false);
  assert.equal(display.conversationText.includes("Trust:"), false);
  assert.equal(display.conversationText.includes("Prior check:"), false);
  assert.equal(display.conversationText.includes("Guard note:"), false);
  assert.equal(display.technicalText.includes("Body map: Francis1 can see whole-body surfaces"), true);
  assert.equal(display.technicalText.includes("Trust: classify needs"), true);
  assert.equal(display.technicalText.includes("Prior check: Review candidate"), true);
  assert.equal(display.technicalText.includes("Guard note: repeated guarded drift"), true);
  assert.equal(display.technicalText.includes("Context: session=driver-alpha"), true);
  assert.equal(display.tone, "driver");
  assert.deepEqual(display.receiptFields, ["objective", "prompt", "context"]);
});

test("formatCollaborationRelayMessage compacts output-guard fallback receipts", () => {
  const transcript = parseCollaborationTranscript({
    ok: true,
    mode: "read_only",
    relay_root: "integrations/developer_bridge/collaboration_prompts",
    count: 1,
    truncated: false,
    filters: { limit: 1 },
    items: [
      {
        id: "collab_guard",
        created_at: "2026-06-25T02:26:52Z",
        updated_at: "2026-06-25T02:26:52Z",
        status: "queued",
        source_agent: "ollama",
        target_agent: "codex",
        direction: "ollama->codex",
        objective: "Francis1 output-guard drift receipt",
        prompt:
          "Francis1 output guard fallback: model reply repeated known collaboration drift after Codex provided a verified surface. Drift terms: local_model_reconciliation_loop. Topic: the next Communication UI change that would reduce visible relay noise using existing receipt fields. Review artifact: apps.chat_ui.communication. Issue/gap/risk: continue from the verified artifact and name the concrete review surface before any build, memory-promotion, or action-readiness claim. No execution, mutation, approval, training, or memory-promotion authority was granted.",
        context: "Model output guard replaced a known drift reply; raw model output was not stored in the relay receipt.",
        chat_handoff: {
          chat_text: "[Francis relay collab_guard] ollama -> codex: guard fallback",
          source_chat_echo_required: true,
          target_chat_echo_required: true,
        },
        governance: {
          executes_prompt: false,
          grants_mutation_authority: false,
          requires_operator_review: true,
        },
      },
    ],
    governance: {
      executes_prompt: false,
    },
  });

  const display = formatCollaborationRelayMessage(transcript.items[0]!);

  assert.equal(display.compacted, true);
  assert.equal(display.summary.startsWith("Issue/gap/risk: continue from the verified artifact"), true);
  assert.equal(display.summary.includes("Topic: the next Communication UI change"), true);
  assert.equal(display.summary.includes("Artifact: apps.chat_ui.communication"), true);
  assert.equal(display.summary.includes("Guard: local_model_reconciliation_loop"), true);
  assert.equal(display.summary.includes("Issue/gap/risk: continue from the verified artifact"), true);
  assert.equal(display.summary.includes("Boundary: no execution"), true);
  assert.equal(display.summary.includes("model reply repeated known collaboration drift"), false);
  assert.equal(display.conversationText.startsWith("Issue/gap/risk: continue from the verified artifact"), true);
  assert.equal(display.technicalText.includes("Guard: local_model_reconciliation_loop"), true);
  assert.equal(display.technicalText.includes("Artifact: apps.chat_ui.communication"), true);
  assert.equal(display.tone, "guard");
  assert.equal(display.raw.includes("model reply repeated known collaboration drift"), true);
  assert.deepEqual(display.receiptFields, ["prompt", "context"]);
});

test("parseCollaborationSessions preserves bounded session summaries and governance", () => {
  const sessions = parseCollaborationSessions({
    ok: true,
    mode: "read_only",
    relay_root: "integrations/developer_bridge/collaboration_prompts",
    count: 1,
    truncated: false,
    filters: { limit: 5, item_limit: 50 },
    readback_cache: {
      status: "stale_refreshing",
      age_ms: 3600,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    definitions: {
      session: "Messages grouped by timestamp gap from bounded relay receipts.",
      latest_preview: "A short bounded preview from the latest receipt, not a full transcript store.",
      latest_review_gate: "The latest typed review gate matched to a session relay receipt.",
      transcript_disclosure: "Operator-facing disclosure state for summary-first review.",
    },
    items: [
      {
        id: "session-2026-06-25T01:11:04Z",
        started_at: "2026-06-25T01:11:04Z",
        ended_at: "2026-06-25T01:11:20Z",
        message_count: 2,
        participants: ["codex", "ollama"],
        direction_counts: { "codex->ollama": 1, "ollama->codex": 1 },
        latest_item_id: "collab_latest",
        latest_direction: "ollama->codex",
        latest_objective: "Francis1 reply",
        latest_preview: "My current gap is session recall without raw transcript dumping.",
        latest_review_gate: {
          observed: true,
          review_item_id: "review-session",
          insight_id: "insight-session",
          turn: 42,
          topic: "which session-summary fields should be shown to the operator",
          build_issue_code: "collaboration_session_recall",
          surface: "developer_bridge collaboration sessions",
          required_review_artifact: "developer_bridge collaboration sessions:review_candidate:insight-session",
          build_direction_state: "advisory_review_required",
          blocks_build_direction: false,
          requires_codex_or_operator_review: true,
          requires_repo_truth_review: true,
          next_codex_action: "Inspect session grouping before expanding transcript visibility.",
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
          stores_full_transcript: false,
        },
        transcript_disclosure: {
          summary_before_raw_transcript: true,
          safe_preview_available: true,
          raw_transcript_opened_by_default: false,
          raw_receipt_details_opened_by_default: false,
          technical_receipts_opened_by_default: false,
          stores_full_transcript: false,
          operator_review_surface: "developer_bridge.collaboration_sessions",
          disclosure_label: "summary first; raw receipt detail remains opt-in",
        },
      },
    ],
    governance: {
      read_only: true,
      stores_full_transcript: false,
      grants_execution_authority: false,
    },
  });

  assert.equal(sessions.ok, true);
  assert.equal(sessions.items.length, 1);
  assert.equal(sessions.items[0]?.messageCount, 2);
  assert.deepEqual(sessions.items[0]?.participants, ["codex", "ollama"]);
  assert.deepEqual(sessions.items[0]?.directionCounts, { "codex->ollama": 1, "ollama->codex": 1 });
  assert.equal(sessions.items[0]?.latestDirection, "ollama->codex");
  assert.equal(sessions.items[0]?.latestReviewGate.observed, true);
  assert.equal(sessions.items[0]?.latestReviewGate.buildIssueCode, "collaboration_session_recall");
  assert.equal(sessions.items[0]?.latestReviewGate.buildDirectionState, "advisory_review_required");
  assert.equal(sessions.items[0]?.latestReviewGate.requiresCodexOrOperatorReview, true);
  assert.equal(sessions.items[0]?.latestReviewGate.requiresRepoTruthReview, true);
  assert.equal(sessions.items[0]?.latestReviewGate.grantsExecutionAuthority, false);
  assert.equal(sessions.items[0]?.latestReviewGate.storesFullTranscript, false);
  assert.equal(sessions.items[0]?.transcriptDisclosure.summaryBeforeRawTranscript, true);
  assert.equal(sessions.items[0]?.transcriptDisclosure.rawTranscriptOpenedByDefault, false);
  assert.equal(sessions.items[0]?.transcriptDisclosure.rawReceiptDetailsOpenedByDefault, false);
  assert.equal(sessions.items[0]?.transcriptDisclosure.technicalReceiptsOpenedByDefault, false);
  assert.equal(sessions.items[0]?.transcriptDisclosure.storesFullTranscript, false);
  const gateSummary = collaborationSessionReviewGateSummary(sessions.items[0]!.latestReviewGate);
  assert.equal(gateSummary.badge, "advisory gate");
  assert.equal(gateSummary.tone, "ready");
  assert.equal(gateSummary.artifact, "developer_bridge collaboration sessions:review_candidate:insight-session");
  assert.equal(gateSummary.surface, "developer_bridge collaboration sessions");
  assert.equal(gateSummary.nextAction, "Inspect session grouping before expanding transcript visibility.");
  assert.deepEqual(gateSummary.detail, [
    "gate advisory_review_required",
    "codex review true",
    "repo review true",
    "execute false",
    "mutation false",
    "approve false",
    "memory write false",
    "full transcript false",
  ]);
  const disclosureSummary = collaborationSessionTranscriptDisclosureSummary(sessions.items[0]!.transcriptDisclosure);
  assert.equal(disclosureSummary.badge, "summary-first");
  assert.equal(disclosureSummary.tone, "ready");
  assert.deepEqual(disclosureSummary.detail, [
    "summary first; raw receipt detail remains opt-in",
    "safe preview true",
    "raw transcript open false",
    "receipt detail open false",
    "technical receipts open false",
    "full transcript store false",
    "surface developer_bridge.collaboration_sessions",
  ]);
  assert.equal(sessions.definitions.latestPreview.includes("not a full transcript"), true);
  assert.equal(sessions.definitions.latestReviewGate.includes("typed review gate"), true);
  assert.equal(sessions.definitions.transcriptDisclosure.includes("summary-first"), true);
  assert.equal(sessions.readbackCache.status, "stale_refreshing");
  assert.equal(sessions.readbackCache.ageMs, 3600);
  assert.equal(sessions.readbackCache.servesFullTranscriptStore, false);
  assert.equal(sessions.governance.stores_full_transcript, false);
});

test("parseCollaborationReview preserves advisory candidate boundaries", () => {
  const review = parseCollaborationReview({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_review",
    count: 1,
    readback_cache: {
      status: "refreshed",
      age_ms: 0,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    definitions: {
      concrete_repo_surface: "The bounded code, API, UI, receipt, or docs surface Codex must inspect.",
      review_artifact: "The typed receipt or candidate record Codex/operator reviews first.",
      surface_verification: "Whether an existing Francis surface was found.",
      build_direction_gate: "Whether the review item can be used as build direction.",
      implementation_preflight: "The exact typed review receipt Codex/operator should read.",
    },
    items: [
      {
        id: "review-insight-alpha",
        insight_id: "insight-alpha",
        created_at: "2026-06-24T22:16:00Z",
        session_id: "driver-alpha",
        turn: 109,
        topic: "Communication UI change",
        finding: "Noise reduction needs an operator-visible receipt field.",
        concrete_repo_surface: "apps.chat_ui.communication",
        review_artifact: "apps.chat_ui.communication:review_candidate:insight-alpha",
        surface_verification: {
          status: "existing_surface_found",
          existing_surface_found: true,
          requires_build_or_wiring_review: false,
          projection_applied: true,
          surface_kind: "ui_code",
          evidence: "Chat UI collaboration panel and parser are repo surfaces.",
          next_codex_action: "Inspect the Chat UI collaboration panel.",
        },
        quality_flags: {
          generic_surface: false,
          invented_artifact_hint: false,
          loop_language_present: false,
          needs_repo_truth_review: true,
          safe_to_implement_without_review: false,
        },
        review_recommendation: {
          decision: "candidate_for_codex_review",
          next_codex_action: "Inspect the cited insight against repo truth.",
          operator_action_required: false,
          validated_against_repo_truth: false,
          authority: "advisory_review_readback_only",
        },
        action_boundary: {
          conversation_can_create_action_candidate: true,
          conversation_can_execute_action: false,
          conversation_can_approve_action: false,
          requires_codex_or_operator_review_before_implementation: true,
          requires_repo_truth_review: true,
        },
        build_direction_gate: {
          state: "blocked_until_typed_review",
          blocks_build_direction: true,
          requires_typed_review_artifact: true,
          requires_conflicting_sources: true,
          requires_codex_or_operator_review: true,
          requires_repo_truth_review: true,
          conflicting_sources: [
            {
              source: "codex",
              receipt_id: "codex-alpha",
              role: "external_guidance_source",
            },
            {
              source: "francis1",
              receipt_id: "ollama-alpha",
              role: "local_model_source",
              provider_lane: "ollama",
            },
          ],
          surface_under_review: "developer_bridge.collaboration_review.items",
          required_review_artifact: "developer_bridge.collaboration_review.items:review_candidate:insight-alpha",
          reason: "Source disagreement cannot become build direction until typed review records the evidence.",
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
        },
        implementation_preflight: {
          must_read_before_editing: true,
          review_item_id: "review-insight-alpha",
          insight_id: "insight-alpha",
          review_artifact: "developer_bridge.collaboration_review.items:review_candidate:insight-alpha",
          review_route: "/developer-bridge/collaboration-review?limit=1",
          surface_under_review: "developer_bridge.collaboration_review.items",
          build_direction_state: "blocked_until_typed_review",
          requires_typed_review_artifact: true,
          requires_codex_or_operator_review: true,
          requires_repo_truth_review: true,
          validated_against_repo_truth: false,
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
        },
        governance: {
          grants_execution_authority: false,
          grants_memory_write_authority: false,
        },
      },
    ],
    governance: {
      grants_execution_authority: false,
      grants_memory_write_authority: false,
    },
  });

  assert.equal(review.ok, true);
  assert.equal(review.items.length, 1);
  assert.equal(review.definitions.concreteRepoSurface.includes("bounded code"), true);
  assert.equal(review.definitions.surfaceVerification.includes("existing Francis surface"), true);
  assert.equal(review.definitions.buildDirectionGate.includes("build direction"), true);
  assert.equal(review.definitions.implementationPreflight.includes("exact typed review receipt"), true);
  assert.equal(review.items[0]?.insightId, "insight-alpha");
  assert.equal(review.items[0]?.concreteRepoSurface, "apps.chat_ui.communication");
  assert.equal(review.items[0]?.surfaceVerification.status, "existing_surface_found");
  assert.equal(review.items[0]?.surfaceVerification.existingSurfaceFound, true);
  assert.equal(review.items[0]?.surfaceVerification.requiresBuildOrWiringReview, false);
  assert.equal(review.items[0]?.surfaceVerification.projectionApplied, true);
  assert.equal(review.items[0]?.surfaceVerification.surfaceKind, "ui_code");
  assert.equal(review.items[0]?.qualityFlags.needsRepoTruthReview, true);
  assert.equal(review.items[0]?.qualityFlags.safeToImplementWithoutReview, false);
  assert.equal(review.items[0]?.reviewRecommendation.decision, "candidate_for_codex_review");
  assert.equal(review.items[0]?.reviewRecommendation.nextCodexAction, "Inspect the cited insight against repo truth.");
  assert.equal(review.items[0]?.reviewRecommendation.authority, "advisory_review_readback_only");
  assert.equal(collaborationReviewNextAction(review.items[0]!), "Inspect the cited insight against repo truth.");
  assert.equal(review.items[0]?.actionBoundary.conversationCanExecuteAction, false);
  assert.equal(review.items[0]?.buildDirectionGate.state, "blocked_until_typed_review");
  assert.equal(review.items[0]?.buildDirectionGate.blocksBuildDirection, true);
  assert.equal(review.items[0]?.buildDirectionGate.requiresConflictingSources, true);
  assert.equal(review.items[0]?.buildDirectionGate.conflictingSources[1]?.source, "francis1");
  assert.equal(review.items[0]?.buildDirectionGate.conflictingSources[1]?.providerLane, "ollama");
  assert.equal(review.items[0]?.buildDirectionGate.grantsExecutionAuthority, false);
  assert.equal(review.items[0]?.buildDirectionGate.grantsMemoryWriteAuthority, false);
  assert.equal(review.items[0]?.implementationPreflight.mustReadBeforeEditing, true);
  assert.equal(review.items[0]?.implementationPreflight.reviewItemId, "review-insight-alpha");
  assert.equal(review.items[0]?.implementationPreflight.reviewRoute, "/developer-bridge/collaboration-review?limit=1");
  assert.equal(review.items[0]?.implementationPreflight.validatedAgainstRepoTruth, false);
  assert.equal(review.items[0]?.implementationPreflight.grantsExecutionAuthority, false);
  const gateSummary = collaborationBuildDirectionGateSummary(review.items[0]!);
  assert.equal(gateSummary.badge, "source disagreement blocked");
  assert.equal(gateSummary.tone, "blocked");
  assert.equal(gateSummary.artifact, "developer_bridge.collaboration_review.items:review_candidate:insight-alpha");
  assert.equal(gateSummary.surface, "developer_bridge.collaboration_review.items");
  assert.equal(gateSummary.detail.includes("conflicting sources true"), true);
  assert.equal(gateSummary.detail.includes("source receipts 2"), true);
  assert.equal(gateSummary.detail.includes("mutation false"), true);
  assert.deepEqual(gateSummary.conflictingSourceLines, [
    "codex: codex-alpha / external_guidance_source",
    "francis1: ollama-alpha / local_model_source / provider ollama",
  ]);
  const implementationSummary = collaborationImplementationReviewSummary(review.items[0]!);
  assert.equal(implementationSummary.badge, "build blocked");
  assert.equal(implementationSummary.tone, "blocked");
  assert.equal(implementationSummary.artifact, "developer_bridge.collaboration_review.items:review_candidate:insight-alpha");
  assert.equal(implementationSummary.preflight.reviewItemId, "review-insight-alpha");
  assert.equal(implementationSummary.detail.includes("route /developer-bridge/collaboration-review?limit=1"), true);
  assert.equal(implementationSummary.detail.includes("repo checked false"), true);
  assert.deepEqual(implementationSummary.conflictingSourceLines, [
    "codex: codex-alpha / external_guidance_source",
    "francis1: ollama-alpha / local_model_source / provider ollama",
  ]);
  assert.equal(review.readbackCache.status, "refreshed");
  assert.equal(review.readbackCache.servesFullTranscriptStore, false);
});

test("parseCollaborationLearning preserves bounded no-authority learning receipts", () => {
  const learning = parseCollaborationLearning({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_driver.learning_events",
    count: 1,
    truncated: false,
    readback_cache: {
      status: "refreshed",
      age_ms: 0,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    definitions: {
      learning_event: "A bounded receipt for repeated collaboration drift.",
      failure_type: "The classified failure or drift class.",
      repeated_terms: "Stable drift markers counted across recent relay notes; not raw transcript text.",
      recent_turns: "Receipt identifiers and matched markers used as evidence.",
      latest_turn: "Most recent observed turn for this learning event.",
    },
    items: [
      {
        id: "learning-driver-alpha",
        created_at: "2026-06-25T04:31:00Z",
        session_id: "driver-alpha",
        turn: 394,
        latest_turn: 419,
        latest_observed_at: "2026-06-25T04:45:00Z",
        current_signal_observed: true,
        current_signal_recent_turn_count: 6,
        failure_type: "repetitive_meta_loop",
        observation: "The collaboration repeated authority-boundary language enough to risk a loop.",
        repeated_terms: ["typed_receipt_shape", "conversation_authority_boundary"],
        recent_turn_count: 4,
        recent_turns: [
          {
            turn: 391,
            note_id: "note-alpha",
            ollama_prompt_id: "ollama-alpha",
            matched_terms: ["typed_receipt_shape"],
          },
        ],
        learning: {
          memory_value: "failed or repetitive turns are learning material when stored as bounded receipts",
          operator_intent: "keep failures in Francis memory without transcript dumping",
          next_prompt_policy: "ask for a concrete build surface instead of another identity argument",
        },
        writer_governance: {
          stores_full_transcript: false,
          grants_execution_authority: false,
          grants_memory_write_authority: false,
        },
      },
    ],
    governance: {
      read_only: true,
      stores_full_transcript: false,
      grants_execution_authority: false,
      grants_memory_write_authority: false,
    },
  });

  assert.equal(learning.ok, true);
  assert.equal(learning.mode, "read_only");
  assert.equal(learning.items.length, 1);
  assert.equal(learning.definitions.repeatedTerms.includes("not raw transcript text"), true);
  assert.equal(learning.definitions.latestTurn.includes("Most recent observed turn"), true);
  assert.equal(learning.readbackCache.servesFullTranscriptStore, false);
  const item = learning.items[0]!;
  assert.equal(item.failureType, "repetitive_meta_loop");
  assert.equal(item.turn, 394);
  assert.equal(item.latestTurn, 419);
  assert.equal(item.latestObservedAt, "2026-06-25T04:45:00Z");
  assert.equal(item.currentSignalObserved, true);
  assert.equal(item.currentSignalRecentTurnCount, 6);
  assert.deepEqual(item.repeatedTerms, ["typed_receipt_shape", "conversation_authority_boundary"]);
  assert.equal(item.recentTurnCount, 4);
  assert.equal(item.recentTurns[0]?.noteId, "note-alpha");
  assert.equal(item.learning.operatorIntent.includes("without transcript dumping"), true);
  assert.equal(item.writerGovernance.stores_full_transcript, false);
  assert.equal(learning.governance.grants_execution_authority, false);
  assert.equal(learning.governance.grants_memory_write_authority, false);

  const guard = collaborationLearningGuardSummary(learning, null);
  assert.equal(guard.badge, "prompt guard active");
  assert.equal(guard.tone, "ready");
  assert.equal(guard.failureType, "repetitive_meta_loop");
  assert.equal(guard.latestTurn, 419);
  assert.equal(guard.promptPolicy, "ask for a concrete build surface instead of another identity argument");
  assert.deepEqual(guard.detail, [
    "failure repetitive_meta_loop",
    "latest turn 419",
    "recent turns 4",
    "learning receipt learning-driver-alpha",
    "full transcript false",
    "training false",
    "execute false",
    "mutation false",
    "approve false",
    "memory write false",
  ]);
});

test("collaborationReviewBadge surfaces model drift review items", () => {
  const review = parseCollaborationReview({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_review",
    count: 1,
    readback_cache: {
      status: "hit",
      age_ms: 10,
      ttl_ms: 3000,
      serves_full_transcript_store: false,
    },
    items: [
      {
        id: "review-insight-drift",
        insight_id: "insight-drift",
        created_at: "2026-06-25T03:02:00Z",
        session_id: "driver-alpha",
        turn: 320,
        topic: "which roadmap-alignment check should run before prompting any main Francis build",
        finding: "My current gap is understanding the verified roadmap artifact.",
        concrete_repo_surface: "docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md",
        review_artifact: "developer_bridge.collaboration_review.items:insight-drift",
        surface_verification: {
          status: "canonical_truth_source_found",
          existing_surface_found: true,
          requires_build_or_wiring_review: false,
          projection_applied: true,
          surface_kind: "canonical_docs",
        },
        quality_flags: {
          generic_surface: false,
          invented_artifact_hint: false,
          loop_language_present: true,
          needs_repo_truth_review: true,
          safe_to_implement_without_review: false,
        },
        review_recommendation: {
          decision: "model_drift_needs_review",
          next_codex_action: "Review the local-model drift before implementation.",
          operator_action_required: false,
          validated_against_repo_truth: false,
          authority: "advisory_review_readback_only",
        },
        action_boundary: {
          conversation_can_create_action_candidate: true,
          conversation_can_execute_action: false,
          conversation_can_approve_action: false,
          requires_codex_or_operator_review_before_implementation: true,
          requires_repo_truth_review: true,
        },
        governance: {
          grants_execution_authority: false,
          grants_memory_write_authority: false,
        },
      },
    ],
    governance: {
      grants_execution_authority: false,
      grants_memory_write_authority: false,
    },
  });

  const item = review.items[0]!;

  assert.equal(collaborationReviewBadge(item), "model drift");
  assert.equal(collaborationReviewTone(item), "blocked");
  assert.equal(item.qualityFlags.loopLanguagePresent, true);
  assert.equal(item.reviewRecommendation.decision, "model_drift_needs_review");
});

test("collaborationReviewNextAction falls back to surface verification action", () => {
  const review = parseCollaborationReview({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_review",
    count: 1,
    items: [
      {
        id: "review-insight-fallback",
        insight_id: "insight-fallback",
        surface_verification: {
          next_codex_action: "Inspect the Chat UI collaboration panel and parser before changing the operator view.",
        },
        review_recommendation: {
          next_codex_action: "",
        },
      },
    ],
  });

  assert.equal(
    collaborationReviewNextAction(review.items[0]!),
    "Inspect the Chat UI collaboration panel and parser before changing the operator view.",
  );
});

test("collaborationActionBoundarySummary keeps model advice visibly advice-only", () => {
  const review = parseCollaborationReview({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_review",
    count: 1,
    items: [
      {
        id: "review-action-boundary",
        insight_id: "insight-action-boundary",
        action_boundary: {
          conversation_can_create_action_candidate: true,
          conversation_can_execute_action: false,
          conversation_can_approve_action: false,
          requires_codex_or_operator_review_before_implementation: true,
          requires_repo_truth_review: true,
        },
      },
    ],
  });

  const summary = collaborationActionBoundarySummary(review.items[0]!);

  assert.equal(summary.badge, "advice only");
  assert.equal(summary.tone, "ready");
  assert.deepEqual(summary.detail, [
    "candidate true",
    "execute false",
    "approve false",
    "codex review true",
    "repo review true",
  ]);
});

test("collaborationImplementationReviewSummary exposes the typed read-before-editing gate", () => {
  const review = parseCollaborationReview({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_review",
    count: 1,
    items: [
      {
        id: "review-implementation-gate",
        insight_id: "insight-implementation-gate",
        turn: 990,
        concrete_repo_surface: "developer_bridge.collaboration_review.items",
        review_artifact: "developer_bridge.collaboration_review.items:review_candidate:insight-implementation-gate",
        surface_verification: {
          next_codex_action: "Inspect the specific review item before editing collaboration code.",
        },
        review_recommendation: {
          next_codex_action: "",
        },
        action_boundary: {
          conversation_can_create_action_candidate: true,
          conversation_can_execute_action: false,
          conversation_can_approve_action: false,
          requires_codex_or_operator_review_before_implementation: true,
          requires_repo_truth_review: true,
        },
        build_direction_gate: {
          state: "advisory_review_required",
          blocks_build_direction: false,
          requires_typed_review_artifact: true,
          requires_codex_or_operator_review: true,
          requires_repo_truth_review: true,
          surface_under_review: "developer_bridge.collaboration_review.items",
          required_review_artifact: "developer_bridge.collaboration_review.items:review_candidate:insight-implementation-gate",
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
        },
        implementation_preflight: {
          must_read_before_editing: true,
          review_item_id: "review-implementation-gate",
          insight_id: "insight-implementation-gate",
          review_artifact: "developer_bridge.collaboration_review.items:review_candidate:insight-implementation-gate",
          review_route: "/developer-bridge/collaboration-review?limit=1",
          surface_under_review: "developer_bridge.collaboration_review.items",
          build_direction_state: "advisory_review_required",
          requires_typed_review_artifact: true,
          requires_codex_or_operator_review: true,
          requires_repo_truth_review: true,
          validated_against_repo_truth: false,
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
        },
      },
    ],
  });

  const summary = collaborationImplementationReviewSummary(review.items[0]!);

  assert.equal(summary.badge, "read before editing");
  assert.equal(summary.tone, "ready");
  assert.equal(summary.artifact, "developer_bridge.collaboration_review.items:review_candidate:insight-implementation-gate");
  assert.equal(summary.surface, "developer_bridge.collaboration_review.items");
  assert.equal(summary.nextAction, "Inspect the specific review item before editing collaboration code.");
  assert.equal(summary.preflight.mustReadBeforeEditing, true);
  assert.equal(summary.preflight.reviewItemId, "review-implementation-gate");
  assert.equal(summary.preflight.reviewRoute, "/developer-bridge/collaboration-review?limit=1");
  assert.deepEqual(summary.detail, [
    "review item review-implementation-gate",
    "route /developer-bridge/collaboration-review?limit=1",
    "turn 990",
    "must read true",
    "gate advisory_review_required",
    "typed artifact true",
    "codex review true",
    "repo review true",
    "repo checked false",
    "execute false",
    "mutation false",
    "approve false",
    "memory write false",
  ]);
});

test("collaborationImplementationReviewSummary blocks authority drift in review receipts", () => {
  const review = parseCollaborationReview({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_review",
    count: 1,
    items: [
      {
        id: "review-unsafe-gate",
        insight_id: "insight-unsafe-gate",
        turn: 991,
        concrete_repo_surface: "developer_bridge.collaboration_review.items",
        review_artifact: "developer_bridge.collaboration_review.items:review_candidate:insight-unsafe-gate",
        action_boundary: {
          conversation_can_create_action_candidate: true,
          conversation_can_execute_action: true,
          conversation_can_approve_action: false,
          requires_codex_or_operator_review_before_implementation: true,
          requires_repo_truth_review: true,
        },
        build_direction_gate: {
          state: "advisory_review_required",
          blocks_build_direction: false,
          requires_typed_review_artifact: true,
          requires_codex_or_operator_review: true,
          requires_repo_truth_review: true,
          required_review_artifact: "developer_bridge.collaboration_review.items:review_candidate:insight-unsafe-gate",
          grants_execution_authority: true,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
        },
      },
    ],
  });

  const summary = collaborationImplementationReviewSummary(review.items[0]!);

  assert.equal(summary.badge, "authority drift");
  assert.equal(summary.tone, "blocked");
  assert.equal(summary.detail.includes("execute true"), true);
  assert.equal(summary.detail.includes("mutation false"), true);
});

test("collaborationActionIntakeSummary exposes mission ingress as candidate-only", () => {
  const review = parseCollaborationReview({
    ok: true,
    mode: "read_only",
    surface: "developer_bridge.collaboration_review",
    count: 1,
    items: [
      {
        id: "review-action-intake",
        insight_id: "insight-action-intake",
        concrete_repo_surface: "api.routes.chat.mission_ingress",
        surface_verification: {
          surface_kind: "mission_ingress_action_boundary",
        },
        action_boundary: {
          conversation_can_create_action_candidate: true,
          conversation_can_execute_action: false,
          conversation_can_approve_action: false,
          requires_repo_truth_review: true,
        },
        build_direction_gate: {
          state: "advisory_review_required",
          requires_codex_or_operator_review: true,
          grants_execution_authority: false,
          grants_mutation_authority: false,
          grants_approval_authority: false,
          grants_memory_write_authority: false,
        },
      },
    ],
  });

  const summary = collaborationActionIntakeSummary(review.items[0]!);

  assert.equal(summary.applies, true);
  assert.equal(summary.badge, "action candidate only");
  assert.equal(summary.tone, "ready");
  assert.equal(summary.candidateLine, "candidate true / codex review true / repo review true");
  assert.equal(summary.directAuthorityLine, "execute false / mutation false / approve false / memory write false");
  assert.deepEqual(summary.detail, [
    "surface api.routes.chat.mission_ingress",
    "candidate true",
    "codex review true",
    "repo review true",
    "execute false",
    "mutation false",
    "approve false",
    "memory write false",
    "gate advisory_review_required",
  ]);
});
