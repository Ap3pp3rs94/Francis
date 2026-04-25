import assert from "node:assert/strict";
import test from "node:test";

import { MissionsClient, missionCurrentOperation, missionCurrentTaskId, missionRecoveryTargetId, presentMissionQueue } from "./index.ts";

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function installFetch(handler: FetchHandler): () => void {
  const globals = globalThis as typeof globalThis & { fetch?: typeof fetch };
  const originalFetch = globals.fetch;

  globals.fetch = (async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = input instanceof Request ? input.url : input.toString();
    return await handler(url, init);
  }) as typeof fetch;

  return () => {
    if (originalFetch) {
      globals.fetch = originalFetch;
      return;
    }
    delete globals.fetch;
  };
}

function jsonRequestBody(init?: RequestInit): unknown {
  const body = init?.body;
  if (typeof body !== "string" || !body.trim()) return undefined;
  return JSON.parse(body) as unknown;
}

test("presentMissionQueue prioritizes review-required missions and reports hidden counts", () => {
  const presentation = presentMissionQueue(
    [
      {
        id: "mission_eligible_low",
        status: "queued",
        objective: "Eligible mission should not hide review-required work",
        priority: 1,
        risk_tier: "medium",
        recommended_action: "create_first_operation",
        advance: { eligible: true, action: "create_first_operation" },
      },
      {
        id: "mission_approval",
        status: "active",
        objective: "Approval gate should lead the queue",
        priority: 2,
        risk_tier: "high",
        recommended_action: "review_pending_approval",
        last_task_approval_id: "apr_alpha",
        last_task_approval_status: "pending",
        advance: { eligible: false, action: "review_pending_approval", reason: "Approval apr_alpha is pending." },
      },
      {
        id: "mission_dependency",
        status: "blocked",
        objective: "Dependency blocker should stay near the top",
        priority: 3,
        risk_tier: "critical",
        recommended_action: "wait_for_dependency",
        dependency_count: 1,
        dependency_state: {
          status: "waiting",
          total: 1,
          resolved: 0,
          unresolved: 1,
          first_unresolved: { id: "msn_blocker" },
        },
        advance: { eligible: false, action: "wait_for_dependency", target_id: "msn_blocker" },
      },
      {
        id: "mission_review_other",
        status: "queued",
        objective: "Other review work should still outrank eligible work",
        priority: 4,
        risk_tier: "medium",
        recommended_action: "raise_trust_or_reduce_risk",
        advance: { eligible: false, action: "raise_trust_or_reduce_risk" },
      },
      {
        id: "mission_eligible_high",
        status: "active",
        objective: "Eligible work remains visible once review work is surfaced",
        priority: 5,
        risk_tier: "high",
        recommended_action: "run_linked_operation",
        advance: { eligible: true, action: "run_linked_operation" },
      },
    ],
    3,
  );

  assert.equal(presentation.lead?.id, "mission_approval");
  assert.deepEqual(
    presentation.visible.map((item) => item.id),
    ["mission_approval", "mission_dependency", "mission_review_other"],
  );
  assert.equal(presentation.total, 5);
  assert.equal(presentation.reviewRequired, 3);
  assert.equal(presentation.eligible, 2);
  assert.equal(presentation.hiddenTotal, 2);
  assert.equal(presentation.hiddenReviewRequired, 0);
  assert.equal(presentation.hiddenEligible, 2);
});

test("missionCurrentTaskId prefers explicit current-task sources before linked-task fallback", () => {
  const mission = {
    linked_task_ids: ["tsk_old", "tsk_older"],
    last_task_id: "tsk_mission_current",
    meta: { last_task_id: "tsk_meta_current" },
  };

  assert.equal(
    missionCurrentTaskId(
      mission,
      { last_task_id: "tsk_queue_current", action_target_id: "tsk_action_current", last_advance_operation_id: "tsk_advance_current" },
      { operation_id: "tsk_handoff_current" },
      { operation_id: "tsk_contract_current" },
    ),
    "tsk_contract_current",
  );
  assert.equal(
    missionCurrentTaskId(
      mission,
      { last_task_id: "tsk_queue_current", action_target_id: "tsk_action_current", last_advance_operation_id: "tsk_advance_current" },
      { operation_id: "tsk_handoff_current" },
    ),
    "tsk_queue_current",
  );
  assert.equal(missionCurrentTaskId(mission, undefined, { operation_id: "tsk_handoff_current" }), "tsk_handoff_current");
  assert.equal(missionCurrentTaskId(mission), "tsk_mission_current");
  assert.equal(missionCurrentTaskId({ linked_task_ids: ["tsk_old"], meta: { last_task_id: "tsk_meta_current" } }), "tsk_meta_current");
  assert.equal(
    missionCurrentTaskId({ linked_task_ids: ["tsk_old"] }, { action_target_id: "tsk_action_current" }),
    "tsk_action_current",
  );
  assert.equal(
    missionCurrentTaskId(
      { linked_task_ids: ["tsk_old"] },
      { action_target_id: "msn_dependency", last_advance_operation_id: "tsk_advance_current" },
    ),
    "tsk_advance_current",
  );
  assert.equal(missionCurrentTaskId({ linked_task_ids: [" ", "tsk_old"] }, { action_target_id: "msn_dependency" }), "tsk_old");
});

test("missionRecoveryTargetId preserves dependency missions but routes operation links through current task", () => {
  const mission = {
    linked_task_ids: ["tsk_old"],
    meta: { last_task_id: "tsk_meta_current" },
  };

  assert.equal(
    missionRecoveryTargetId(mission, { action_target_id: "msn_dependency", last_task_id: "tsk_current" }),
    "msn_dependency",
  );
  assert.equal(
    missionRecoveryTargetId(mission, { action_target_id: "tsk_stale", last_task_id: "tsk_current" }, undefined, {
      operation_id: "tsk_contract_current",
    }),
    "tsk_contract_current",
  );
  assert.equal(missionRecoveryTargetId(mission, { action_target_id: "tsk_stale", last_task_id: "tsk_current" }), "tsk_current");
  assert.equal(missionRecoveryTargetId(mission, { action_target_id: "tsk_stale" }), "tsk_meta_current");
});

test("missionCurrentOperation selects the current linked operation before first-linked fallback", () => {
  const linkedOperations = [
    {
      operation: {
        id: "tsk_old",
        ts: 1710000000,
        status: "queued",
        meta: { approval_id: "apr_old" },
      },
      logs: [],
    },
    {
      operation: {
        id: "tsk_current",
        ts: 1710000001,
        status: "blocked",
        meta: { approval_id: "apr_current" },
      },
      logs: [],
    },
  ];

  assert.equal(missionCurrentOperation(linkedOperations, "tsk_current")?.id, "tsk_current");
  assert.equal(missionCurrentOperation(linkedOperations, "tsk_missing")?.id, "tsk_old");
  assert.equal(missionCurrentOperation(linkedOperations, "")?.id, "tsk_old");
  assert.equal(missionCurrentOperation([], "tsk_current"), null);
});

test("MissionsClient.list requests the bounded mission list route and parses mission records", async () => {
  const requests: Array<{ path: string; limit: string | null; status: string | null }> = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      limit: parsed.searchParams.get("limit"),
      status: parsed.searchParams.get("status"),
    });

    return jsonResponse({
      items: [
        {
          id: "mission_alpha",
          status: "queued",
          objective: "Carry the first governed request",
          next_step: "Inspect linked task",
          owner_id: "owner.alpha",
          dependency_ids: ["dep_one", "dep_two"],
          dependency_count: 2,
          escalation_path: "Review with operator if blocked.",
          linked_task_ids: ["tsk_alpha"],
          linked_task_count: 1,
          last_task_id: "tsk_alpha",
          last_task_status: "blocked",
          last_task_result_status: "needs_approval",
          last_task_gate: "approvals_gate",
          last_task_next_step: "review_pending_approval",
          last_task_reason: "Approval apr_alpha is pending.",
          last_advance_operation_id: "tsk_alpha",
        },
      ],
      total: 1,
      limit: 25,
    });
  });

  try {
    const client = new MissionsClient("http://127.0.0.1:8000");
    const response = await client.list({ limit: 25, status: "queued", timeoutMs: 50 });

    assert.deepEqual(requests, [{ path: "/missions/list", limit: "25", status: "queued" }]);
    assert.equal(response.total, 1);
    assert.equal(response.limit, 25);
    assert.equal(response.items.length, 1);
    assert.equal(response.items[0]?.id, "mission_alpha");
    assert.equal(response.items[0]?.owner_id, "owner.alpha");
    assert.deepEqual(response.items[0]?.dependency_ids, ["dep_one", "dep_two"]);
    assert.equal(response.items[0]?.dependency_count, 2);
    assert.equal(response.items[0]?.escalation_path, "Review with operator if blocked.");
    assert.equal(response.items[0]?.linked_task_ids?.[0], "tsk_alpha");
    assert.equal(response.items[0]?.last_task_id, "tsk_alpha");
    assert.equal(response.items[0]?.last_task_status, "blocked");
    assert.equal(response.items[0]?.last_task_result_status, "needs_approval");
    assert.equal(response.items[0]?.last_task_gate, "approvals_gate");
    assert.equal(response.items[0]?.last_task_next_step, "review_pending_approval");
    assert.equal(response.items[0]?.last_task_reason, "Approval apr_alpha is pending.");
    assert.equal(response.items[0]?.last_advance_operation_id, "tsk_alpha");
  } finally {
    restoreFetch();
  }
});

test("MissionsClient.create posts a mission declaration and preserves the returned mission envelope", async () => {
  const requests: Array<{ path: string; method: string; body: unknown }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const path = new URL(url).pathname;
    requests.push({
      path,
      method: (init?.method ?? "GET").toUpperCase(),
      body: jsonRequestBody(init),
    });

    return jsonResponse({
      ok: true,
      mission_id: "mission_beta",
      status: "queued",
      message: "created",
      mission: {
        id: "mission_beta",
        status: "queued",
        objective: "Carry the first operator-declared governed request",
        summary: "Created from the UI composer.",
        next_step: "Run the linked task once it exists.",
        requester_id: "chat_ui.operations",
        owner_id: "owner.beta",
        dependency_ids: ["dep_beta"],
        dependency_count: 1,
        escalation_path: "Deadletter if the first operation cannot be linked.",
      },
      history: [{ ts: "2026-04-21T19:40:00+00:00", mission_id: "mission_beta", event: "created" }],
      linked_operations: [],
      run_ledger: [],
      loop_state: {
        active_stage: "plan",
        handoff: {
          stage: "plan",
          action: "link_operation",
          detail: "Declare or link a bounded operation before execution, trace, or memory can progress.",
        },
      },
    });
  });

  try {
    const client = new MissionsClient("http://127.0.0.1:8000");
    const response = await client.create(
      {
        objective: "Carry the first operator-declared governed request",
        summary: "Created from the UI composer.",
        next_step: "Run the linked task once it exists.",
        requester_id: "chat_ui.operations",
        owner_id: "owner.beta",
        dependency_ids: ["dep_beta"],
        escalation_path: "Deadletter if the first operation cannot be linked.",
      },
      { timeoutMs: 50 },
    );

    assert.deepEqual(requests, [
      {
        path: "/missions/create",
        method: "POST",
        body: {
          objective: "Carry the first operator-declared governed request",
          summary: "Created from the UI composer.",
          next_step: "Run the linked task once it exists.",
          requester_id: "chat_ui.operations",
          owner_id: "owner.beta",
          dependency_ids: ["dep_beta"],
          escalation_path: "Deadletter if the first operation cannot be linked.",
        },
      },
    ]);
    assert.equal(response.ok, true);
    assert.equal(response.mission_id, "mission_beta");
    assert.equal(response.status, "queued");
    assert.equal(response.message, "created");
    assert.equal(response.mission?.id, "mission_beta");
    assert.equal(response.mission?.requester_id, "chat_ui.operations");
    assert.equal(response.mission?.owner_id, "owner.beta");
    assert.deepEqual(response.mission?.dependency_ids, ["dep_beta"]);
    assert.equal(response.mission?.dependency_count, 1);
    assert.equal(response.mission?.escalation_path, "Deadletter if the first operation cannot be linked.");
    assert.equal(response.history?.[0]?.event, "created");
    assert.equal(response.loop_state?.active_stage, "plan");
    assert.equal(response.loop_state?.handoff?.action, "link_operation");
  } finally {
    restoreFetch();
  }
});

test("MissionsClient.advance posts a bounded mission-advance request and preserves the returned operation envelope", async () => {
  const requests: Array<{ path: string; method: string; body: unknown }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const path = new URL(url).pathname;
    requests.push({
      path,
      method: (init?.method ?? "GET").toUpperCase(),
      body: jsonRequestBody(init),
    });

    return jsonResponse({
      ok: true,
      applied: true,
      action: "run_linked_operation",
      operation_id: "tsk_mission_alpha",
      approval_id: "apr_mission_alpha",
      gate: "approvals_gate",
      next_step: "approve_exact_action",
      status: "succeeded",
      message: "operation_run",
      mission: {
        id: "mission_alpha",
        status: "completed",
        objective: "Carry the linked operation",
      },
      operation: {
        id: "tsk_mission_alpha",
        ts: 1710000000,
        status: "succeeded",
        kind: "delegated_task",
        name: "plan.create",
        meta: { orb_plane: "P7_EXECUTION" },
      },
      history: [{ ts: "2026-04-21T19:45:00+00:00", mission_id: "mission_alpha", event: "advance_receipt" }],
      linked_operations: [
        {
          ok: true,
          operation: {
            id: "tsk_mission_alpha",
            ts: 1710000000,
            status: "queued",
            kind: "delegated_task",
            name: "plan.create",
            meta: { approval_id: "apr_mission_alpha" },
          },
          logs: [],
        },
      ],
      run_ledger: [],
      loop_state: {
        active_stage: "gate",
        handoff: {
          stage: "gate",
          action: "review_pending_approval",
          approval_id: "apr_mission_alpha",
          operation_id: "tsk_mission_alpha",
          detail: "Review the active governance hold before the linked operation can continue.",
        },
      },
    });
  });

  try {
    const client = new MissionsClient("http://127.0.0.1:8000");
    const response = await client.advance(
      "mission_alpha",
      { actor: "chat_ui.orb", note: "advance_from_ui", worker_id: "chat_ui.orb" },
      { timeoutMs: 50 },
    );

    assert.deepEqual(requests, [
      {
        path: "/missions/mission_alpha/advance",
        method: "POST",
        body: {
          actor: "chat_ui.orb",
          note: "advance_from_ui",
          worker_id: "chat_ui.orb",
        },
      },
    ]);
    assert.equal(response.ok, true);
    assert.equal(response.applied, true);
    assert.equal(response.action, "run_linked_operation");
    assert.equal(response.operation_id, "tsk_mission_alpha");
    assert.equal(response.approval_id, "apr_mission_alpha");
    assert.equal(response.gate, "approvals_gate");
    assert.equal(response.next_step, "approve_exact_action");
    assert.equal(response.status, "succeeded");
    assert.equal(response.mission?.status, "completed");
    assert.equal(response.operation?.id, "tsk_mission_alpha");
    assert.equal(response.operation?.meta?.orb_plane, "P7_EXECUTION");
    assert.equal(response.history?.[0]?.event, "advance_receipt");
    assert.equal(response.linked_operations?.[0]?.operation?.id, "tsk_mission_alpha");
    assert.equal(response.loop_state?.active_stage, "gate");
    assert.equal(response.loop_state?.handoff?.action, "review_pending_approval");
    assert.equal(response.loop_state?.handoff?.approval_id, "apr_mission_alpha");
  } finally {
    restoreFetch();
  }
});

test("MissionsClient.runOnce posts the bounded mission queue request and preserves queue outcomes", async () => {
  const requests: Array<{ path: string; method: string; body: unknown }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const path = new URL(url).pathname;
    requests.push({
      path,
      method: (init?.method ?? "GET").toUpperCase(),
      body: jsonRequestBody(init),
    });

    return jsonResponse({
      ok: true,
      total: 2,
      applied: 2,
      advanced: 1,
      processed: 3,
      counts: { queued: 1, blocked: 1, failed: 1, deadlettered: 1 },
      items: [
        {
          id: "mission_blocked",
          status: "blocked",
          objective: "Resolve governed blocker",
          recommended_action: "raise_trust_or_reduce_risk",
          action_target_id: "tsk_blocked",
          operator_hint: "Mission requires operator intervention.",
          advance: {
            eligible: false,
            action: "raise_trust_or_reduce_risk",
            target_id: "tsk_blocked",
            reason: "A linked task is blocked by trust posture.",
          },
          current_task: {
            mission_id: "mission_blocked",
            source: "mission_meta",
            operation_id: "tsk_blocked",
            task_status: "accepted",
            result_status: "blocked",
            gate: "trust_gate",
            handoff_action: "raise_trust_or_reduce_risk",
          },
          dependency_state: {
            status: "blocked",
            total: 2,
            resolved: 1,
            unresolved: 1,
            first_unresolved: {
              id: "msn_dependency",
              kind: "mission",
              state: "blocked",
              status: "failed",
            },
            items: [
              {
                id: "msn_dependency",
                kind: "mission",
                state: "blocked",
                status: "failed",
              },
            ],
          },
          history_count: 2,
          latest_history_event: "mission_ticked",
          latest_history_ts: "2026-04-15T12:10:00Z",
          history_tail: [
            { ts: "2026-04-15T12:00:00Z", mission_id: "mission_blocked", event: "created", details: {} },
            {
              ts: "2026-04-15T12:10:00Z",
              mission_id: "mission_blocked",
              event: "mission_ticked",
              details: { status: "blocked" },
            },
          ],
        },
      ],
      failed: [
        {
          id: "mission_failed",
          status: "failed",
          objective: "Review failed work",
          recommended_action: "retry_or_deadletter",
          action_target_id: "tsk_failed",
          operator_hint: "The latest linked task failed. Retry the work or deadletter the mission.",
          recovery: {
            source_status: "failed",
            action: "retry_or_deadletter",
            target_id: "tsk_failed",
            reason: "The latest linked task failed. Retry the work or deadletter the mission.",
            next_step: "Review the failed linked task, then retry through existing governed operation paths or deadletter explicitly.",
            operator_required: true,
            automatic_retry: false,
            read_only: true,
            last_review_action: "retry_or_deadletter",
            last_review_outcome: "requires_operator",
            last_review_target_id: "tsk_failed",
            last_review_actor: "chat_ui.orb",
            last_reviewed_at: "2026-04-15T12:30:00Z",
          },
          last_recovery_action: "retry_or_deadletter",
          last_recovery_outcome: "requires_operator",
          last_recovery_target_id: "tsk_failed",
          last_recovery_actor: "chat_ui.orb",
          last_recovery_source_status: "failed",
          last_recovery_at: "2026-04-15T12:30:00Z",
        },
      ],
      deadletter: [
        {
          id: "mission_dead",
          status: "deadlettered",
          objective: "Review deadlettered work",
          recommended_action: "review_deadletter",
          action_target_id: "tsk_dead",
          deadletter_reason: "operator_abandoned_after_governance_hold",
          recovery: {
            source_status: "deadlettered",
            action: "review_deadletter",
            target_id: "tsk_dead",
            reason: "operator_abandoned_after_governance_hold",
            next_step: "Review receipts and declare replacement work.",
            operator_required: true,
            automatic_retry: false,
            read_only: true,
          },
        },
      ],
      results: [
        {
          mission_id: "mission_ready",
          ok: true,
          applied: true,
          action: "create_first_operation",
          mission: { id: "mission_ready", status: "queued" },
          queue_item: {
            id: "mission_ready",
            status: "blocked",
            objective: "Ready mission now needs approval review",
            recommended_action: "review_pending_approval",
            action_target_id: "tsk_ready",
            last_task_id: "tsk_ready",
            last_task_approval_id: "apr_ready",
            last_task_approval_status: "pending",
            last_advance_action: "create_first_operation",
            last_advance_outcome: "queued",
            last_advance_operation_id: "tsk_ready",
            current_task: {
              mission_id: "mission_ready",
              source: "mission_meta",
              operation_id: "tsk_ready",
              gate: "approvals_gate",
              approval_id: "apr_ready",
              approval_status: "pending",
              handoff_action: "review_pending_approval",
            },
            advance: {
              eligible: false,
              action: "review_pending_approval",
              target_id: "tsk_ready",
              reason: "Approval apr_ready is pending before the mission can continue.",
            },
            history_count: 3,
            latest_history_event: "advance_receipt",
            latest_history_ts: "2026-04-15T12:20:00Z",
            history_tail: [
              {
                ts: "2026-04-15T12:15:00Z",
                mission_id: "mission_ready",
                event: "mission_ticked",
                details: { status: "queued" },
              },
              {
                ts: "2026-04-15T12:20:00Z",
                mission_id: "mission_ready",
                event: "advance_receipt",
                details: { applied: true },
              },
            ],
          },
          status: "queued",
          operation_id: "tsk_ready",
          approval_id: "apr_ready",
          gate: "approvals_gate",
          next_step: "approve_exact_action",
          loop_state: {
            active_stage: "gate",
            handoff: {
              stage: "gate",
              action: "review_pending_approval",
              detail: "Review the active governance hold before the linked operation can continue.",
              approval_id: "apr_ready",
              operation_id: "tsk_ready",
            },
          },
          current_task: {
            mission_id: "mission_ready",
            source: "mission_meta",
            operation_id: "tsk_ready",
            task_status: "accepted",
            operation_status: "queued",
            result_status: "pending",
            gate: "approvals_gate",
            next_step: "approve_exact_action",
            approval_id: "apr_ready",
            approval_status: "pending",
            handoff_stage: "gate",
            handoff_action: "review_pending_approval",
            latest_receipt_event: "governance_hold",
          },
          handoff: {
            stage: "gate",
            action: "review_pending_approval",
            detail: "Review the active governance hold before the linked operation can continue.",
            approval_id: "apr_ready",
            operation_id: "tsk_ready",
          },
          history_count: 3,
          linked_operation_count: 1,
          run_ledger_count: 2,
          receipt_summary: {
            linked_operation_count: 1,
            run_ledger_count: 2,
            history_count: 3,
            current_operation_id: "tsk_ready",
            current_operation_status: "queued",
            current_gate: "approvals_gate",
            current_approval_id: "apr_ready",
            current_trace_id: "trace_ready",
            latest_run_event: "governance_hold",
            latest_run_status: "queued",
            latest_run_ts: "2026-04-15T12:20:00Z",
            latest_history_event: "advance_receipt",
            latest_history_ts: "2026-04-15T12:20:00Z",
          },
          message: "operation_created",
        },
      ],
      errors: [],
    });
  });

  try {
    const client = new MissionsClient("http://127.0.0.1:8000");
    const response = await client.runOnce(
      { actor: "chat_ui.operations", note: "run_queue_once_from_ui", limit: 6 },
      { timeoutMs: 50 },
    );

    assert.deepEqual(requests, [
      {
        path: "/missions/run_once",
        method: "POST",
        body: {
          actor: "chat_ui.operations",
          note: "run_queue_once_from_ui",
          limit: 6,
        },
      },
    ]);
    assert.equal(response.ok, true);
    assert.equal(response.total, 2);
    assert.equal(response.applied, 2);
    assert.equal(response.advanced, 1);
    assert.equal(response.processed, 3);
    assert.equal(response.counts?.blocked, 1);
    assert.equal(response.counts?.failed, 1);
    assert.equal(response.failed[0]?.recovery?.action, "retry_or_deadletter");
    assert.equal(response.failed[0]?.recovery?.source_status, "failed");
    assert.equal(response.failed[0]?.recovery?.target_id, "tsk_failed");
    assert.equal(response.failed[0]?.recovery?.automatic_retry, false);
    assert.equal(response.failed[0]?.recovery?.last_review_action, "retry_or_deadletter");
    assert.equal(response.failed[0]?.recovery?.last_review_outcome, "requires_operator");
    assert.equal(response.failed[0]?.recovery?.last_review_target_id, "tsk_failed");
    assert.equal(response.failed[0]?.last_recovery_action, "retry_or_deadletter");
    assert.equal(response.failed[0]?.last_recovery_outcome, "requires_operator");
    assert.equal(response.failed[0]?.last_recovery_actor, "chat_ui.orb");
    assert.equal(response.failed[0]?.last_recovery_source_status, "failed");
    assert.equal(response.deadletter[0]?.recovery?.action, "review_deadletter");
    assert.equal(response.deadletter[0]?.recovery?.source_status, "deadlettered");
    assert.equal(response.deadletter[0]?.recovery?.target_id, "tsk_dead");
    assert.equal(response.deadletter[0]?.recovery?.operator_required, true);
    assert.equal(response.deadletter[0]?.recovery?.automatic_retry, false);
    assert.equal(response.deadletter[0]?.recovery?.read_only, true);
    assert.equal(response.items[0]?.recommended_action, "raise_trust_or_reduce_risk");
    assert.equal(response.items[0]?.advance?.eligible, false);
    assert.equal(response.items[0]?.advance?.action, "raise_trust_or_reduce_risk");
    assert.equal(response.items[0]?.advance?.target_id, "tsk_blocked");
    assert.equal(response.items[0]?.current_task?.source, "mission_meta");
    assert.equal(response.items[0]?.current_task?.operation_id, "tsk_blocked");
    assert.equal(response.items[0]?.current_task?.gate, "trust_gate");
    assert.equal(response.items[0]?.dependency_state?.status, "blocked");
    assert.equal(response.items[0]?.dependency_state?.unresolved, 1);
    assert.equal(response.items[0]?.dependency_state?.first_unresolved?.id, "msn_dependency");
    assert.equal(response.items[0]?.dependency_state?.items?.[0]?.kind, "mission");
    assert.equal(response.items[0]?.history_count, 2);
    assert.equal(response.items[0]?.latest_history_event, "mission_ticked");
    assert.equal(response.items[0]?.latest_history_ts, "2026-04-15T12:10:00Z");
    assert.equal(response.items[0]?.history_tail?.[1]?.event, "mission_ticked");
    assert.equal(response.results?.[0]?.mission_id, "mission_ready");
    assert.equal(response.results?.[0]?.operation_id, "tsk_ready");
    assert.equal(response.results?.[0]?.approval_id, "apr_ready");
    assert.equal(response.results?.[0]?.queue_item?.recommended_action, "review_pending_approval");
    assert.equal(response.results?.[0]?.queue_item?.last_task_approval_id, "apr_ready");
    assert.equal(response.results?.[0]?.queue_item?.last_task_approval_status, "pending");
    assert.equal(response.results?.[0]?.queue_item?.last_advance_action, "create_first_operation");
    assert.equal(response.results?.[0]?.queue_item?.last_advance_outcome, "queued");
    assert.equal(response.results?.[0]?.queue_item?.current_task?.operation_id, "tsk_ready");
    assert.equal(response.results?.[0]?.queue_item?.current_task?.approval_id, "apr_ready");
    assert.equal(response.results?.[0]?.queue_item?.advance?.eligible, false);
    assert.equal(response.results?.[0]?.queue_item?.advance?.action, "review_pending_approval");
    assert.equal(response.results?.[0]?.queue_item?.history_count, 3);
    assert.equal(response.results?.[0]?.queue_item?.latest_history_event, "advance_receipt");
    assert.equal(response.results?.[0]?.queue_item?.history_tail?.[1]?.event, "advance_receipt");
    assert.equal(response.results?.[0]?.gate, "approvals_gate");
    assert.equal(response.results?.[0]?.next_step, "approve_exact_action");
    assert.equal(response.results?.[0]?.mission?.id, "mission_ready");
    assert.equal(response.results?.[0]?.loop_state?.active_stage, "gate");
    assert.equal(response.results?.[0]?.current_task?.source, "mission_meta");
    assert.equal(response.results?.[0]?.current_task?.operation_id, "tsk_ready");
    assert.equal(response.results?.[0]?.current_task?.task_status, "accepted");
    assert.equal(response.results?.[0]?.current_task?.gate, "approvals_gate");
    assert.equal(response.results?.[0]?.current_task?.approval_id, "apr_ready");
    assert.equal(response.results?.[0]?.current_task?.handoff_action, "review_pending_approval");
    assert.equal(response.results?.[0]?.handoff?.action, "review_pending_approval");
    assert.equal(response.results?.[0]?.handoff?.approval_id, "apr_ready");
    assert.equal(response.results?.[0]?.history_count, 3);
    assert.equal(response.results?.[0]?.linked_operation_count, 1);
    assert.equal(response.results?.[0]?.run_ledger_count, 2);
    assert.equal(response.results?.[0]?.receipt_summary?.current_operation_id, "tsk_ready");
    assert.equal(response.results?.[0]?.receipt_summary?.current_gate, "approvals_gate");
    assert.equal(response.results?.[0]?.receipt_summary?.latest_run_event, "governance_hold");
  } finally {
    restoreFetch();
  }
});

test("MissionsClient.get preserves the mission loop state used by the ORB mission inspector", async () => {
  const requests: Array<{ path: string; method: string }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
    });

    return jsonResponse({
      ok: true,
      mission: {
        id: "mission_loop",
        status: "blocked",
        objective: "Carry the plan-gate-execute-trace-memory loop",
      },
      history: [
        { ts: "2026-04-15T12:00:00Z", mission_id: "mission_loop", event: "created", details: {} },
        { ts: "2026-04-15T12:05:00Z", mission_id: "mission_loop", event: "advance_receipt", details: { applied: true } },
      ],
      linked_operations: [
        {
          operation: {
            id: "tsk_loop",
            ts: 1710000000,
            status: "queued",
            kind: "delegated_task",
            name: "plugin.run",
            trace_id: "trace_loop",
            meta: {
              orb_plane: "P3_GOVERNANCE",
              approval_id: "apr_loop",
              governance: { gate: "approvals_gate", next_step: "review_pending_approval" },
            },
          },
          logs: [],
        },
      ],
      run_ledger: [
        {
          id: "tsk_loop:evt:0",
          ts: 1710000001,
          status: "queued",
          name: "governance_hold",
          meta: { operation_id: "tsk_loop" },
        },
      ],
      queue_item: {
        id: "mission_loop",
        status: "blocked",
        objective: "Carry the plan-gate-execute-trace-memory loop",
        recommended_action: "review_pending_approval",
        action_target_id: "tsk_loop",
        operator_hint: "Approval apr_loop is pending before execution can continue.",
        last_task_id: "tsk_loop",
        last_task_approval_id: "apr_loop",
        last_task_previous_approval_id: "apr_old_loop",
        last_task_approval_status: "pending",
        last_advance_action: "run_linked_operation",
        last_advance_outcome: "requires_operator",
        last_advance_operation_id: "tsk_loop",
        last_advance_operation_status: "blocked",
        last_advance_message: "Approval apr_loop is pending before execution can continue.",
        last_advance_actor: "test.missions",
        last_advance_applied: false,
        last_advance_at: "2026-04-15T12:05:00Z",
        advance: {
          eligible: false,
          action: "review_pending_approval",
          target_id: "tsk_loop",
          reason: "Mission requires approval apr_loop before advancing.",
        },
      },
      current_task: {
        mission_id: "mission_loop",
        source: "mission_meta",
        operation_id: "tsk_loop",
        task_status: "accepted",
        operation_status: "queued",
        result_status: "pending",
        gate: "approvals_gate",
        next_step: "review_pending_approval",
        reason: "Approval apr_loop is pending before execution can continue.",
        approval_id: "apr_loop",
        approval_status: "pending",
        handoff_stage: "gate",
        handoff_action: "review_pending_approval",
        trace_id: "trace_loop",
        latest_receipt_event: "governance_hold",
        latest_receipt_ts: "2024-03-09T16:00:01Z",
        last_advance_operation_id: "tsk_loop",
      },
      receipt_summary: {
        linked_operation_count: 1,
        run_ledger_count: 1,
        history_count: 2,
        current_operation_id: "tsk_loop",
        current_operation_status: "queued",
        current_gate: "approvals_gate",
        current_approval_id: "apr_loop",
        current_trace_id: "trace_loop",
        latest_run_event: "governance_hold",
        latest_run_status: "queued",
        latest_run_ts: "2024-03-09T16:00:01Z",
        latest_history_event: "advance_receipt",
        latest_history_ts: "2026-04-15T12:05:00Z",
      },
      loop_state: {
        summary: "The mission is waiting on a governance decision before it can continue.",
        active_stage: "gate",
        handoff: {
          stage: "gate",
          action: "review_pending_approval",
          detail: "Review the active governance hold before the linked operation can continue.",
          gate: "approvals_gate",
          next_step: "review_pending_approval",
          approval_id: "apr_loop",
          operation_id: "tsk_loop",
        },
        plan: { status: "ready", detail: "1 linked operation(s) declared for this mission.", count: 1, operation_id: "tsk_loop" },
        gate: {
          status: "needs_approval",
          detail: "Governance is actively holding the current linked operation through gate approvals_gate, approval apr_loop.",
          gate: "approvals_gate",
          next_step: "review_pending_approval",
          approval_id: "apr_loop",
          operation_id: "tsk_loop",
        },
        execute: {
          status: "queued",
          detail: "The latest linked operation is currently queued.",
          operation_id: "tsk_loop",
          next_step: "review_pending_approval",
        },
        trace: {
          status: "recorded",
          detail: "Trace receipts are available through 1 trace id(s), 1 run-ledger receipt(s).",
          count: 2,
          operation_id: "tsk_loop",
          trace_id: "trace_loop",
          latest_event: "governance_hold",
          latest_ts: "2024-03-09T16:00:01Z",
        },
        memory: {
          status: "recorded",
          detail: "2 mission continuity receipt(s) are stored in local history.",
          count: 2,
          latest_event: "advance_receipt",
          latest_ts: "2026-04-15T12:05:00Z",
        },
      },
    });
  });

  try {
    const client = new MissionsClient("http://127.0.0.1:8000");
    const response = await client.get("mission_loop", { timeoutMs: 50 });

    assert.deepEqual(requests, [{ path: "/missions/mission_loop", method: "GET" }]);
    assert.equal(response.ok, true);
    assert.equal(response.mission?.id, "mission_loop");
    assert.equal(response.loop_state?.active_stage, "gate");
    assert.equal(response.loop_state?.handoff?.stage, "gate");
    assert.equal(response.loop_state?.handoff?.action, "review_pending_approval");
    assert.equal(response.loop_state?.handoff?.approval_id, "apr_loop");
    assert.equal(response.loop_state?.handoff?.operation_id, "tsk_loop");
    assert.equal(response.loop_state?.gate?.status, "needs_approval");
    assert.equal(response.loop_state?.gate?.approval_id, "apr_loop");
    assert.equal(response.loop_state?.gate?.next_step, "review_pending_approval");
    assert.equal(response.loop_state?.execute?.next_step, "review_pending_approval");
    assert.equal(response.loop_state?.trace?.trace_id, "trace_loop");
    assert.equal(response.loop_state?.trace?.latest_event, "governance_hold");
    assert.equal(response.loop_state?.trace?.latest_ts, "2024-03-09T16:00:01Z");
    assert.equal(response.loop_state?.memory?.latest_event, "advance_receipt");
    assert.equal(response.loop_state?.memory?.latest_ts, "2026-04-15T12:05:00Z");
    assert.equal(response.queue_item?.recommended_action, "review_pending_approval");
    assert.equal(response.queue_item?.action_target_id, "tsk_loop");
    assert.equal(response.queue_item?.advance?.eligible, false);
    assert.equal(response.queue_item?.advance?.action, "review_pending_approval");
    assert.equal(response.queue_item?.advance?.target_id, "tsk_loop");
    assert.equal(response.queue_item?.last_task_approval_id, "apr_loop");
    assert.equal(response.queue_item?.last_task_previous_approval_id, "apr_old_loop");
    assert.equal(response.queue_item?.last_task_approval_status, "pending");
    assert.equal(response.queue_item?.last_advance_action, "run_linked_operation");
    assert.equal(response.queue_item?.last_advance_outcome, "requires_operator");
    assert.equal(response.queue_item?.last_advance_operation_id, "tsk_loop");
    assert.equal(response.queue_item?.last_advance_operation_status, "blocked");
    assert.equal(response.queue_item?.last_advance_applied, false);
    assert.equal(response.current_task?.source, "mission_meta");
    assert.equal(response.current_task?.operation_id, "tsk_loop");
    assert.equal(response.current_task?.task_status, "accepted");
    assert.equal(response.current_task?.operation_status, "queued");
    assert.equal(response.current_task?.result_status, "pending");
    assert.equal(response.current_task?.gate, "approvals_gate");
    assert.equal(response.current_task?.approval_id, "apr_loop");
    assert.equal(response.current_task?.approval_status, "pending");
    assert.equal(response.current_task?.handoff_stage, "gate");
    assert.equal(response.current_task?.handoff_action, "review_pending_approval");
    assert.equal(response.current_task?.trace_id, "trace_loop");
    assert.equal(response.current_task?.latest_receipt_event, "governance_hold");
    assert.equal(response.current_task?.latest_receipt_ts, "2024-03-09T16:00:01Z");
    assert.equal(response.receipt_summary?.linked_operation_count, 1);
    assert.equal(response.receipt_summary?.run_ledger_count, 1);
    assert.equal(response.receipt_summary?.history_count, 2);
    assert.equal(response.receipt_summary?.current_operation_id, "tsk_loop");
    assert.equal(response.receipt_summary?.current_operation_status, "queued");
    assert.equal(response.receipt_summary?.current_gate, "approvals_gate");
    assert.equal(response.receipt_summary?.current_approval_id, "apr_loop");
    assert.equal(response.receipt_summary?.current_trace_id, "trace_loop");
    assert.equal(response.receipt_summary?.latest_run_event, "governance_hold");
    assert.equal(response.receipt_summary?.latest_history_event, "advance_receipt");
  } finally {
    restoreFetch();
  }
});
