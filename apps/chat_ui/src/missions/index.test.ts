import assert from "node:assert/strict";
import test from "node:test";

import { MissionsClient } from "./index.ts";

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
      counts: { queued: 1, blocked: 1, deadlettered: 0 },
      items: [
        {
          id: "mission_blocked",
          status: "blocked",
          objective: "Resolve governed blocker",
          recommended_action: "raise_trust_or_reduce_risk",
          action_target_id: "tsk_blocked",
          operator_hint: "Mission requires operator intervention.",
        },
      ],
      deadletter: [],
      results: [
        {
          mission_id: "mission_ready",
          ok: true,
          applied: true,
          action: "create_first_operation",
          mission: { id: "mission_ready", status: "queued" },
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
    assert.equal(response.items[0]?.recommended_action, "raise_trust_or_reduce_risk");
    assert.equal(response.results?.[0]?.mission_id, "mission_ready");
    assert.equal(response.results?.[0]?.operation_id, "tsk_ready");
    assert.equal(response.results?.[0]?.approval_id, "apr_ready");
    assert.equal(response.results?.[0]?.gate, "approvals_gate");
    assert.equal(response.results?.[0]?.next_step, "approve_exact_action");
    assert.equal(response.results?.[0]?.mission?.id, "mission_ready");
    assert.equal(response.results?.[0]?.loop_state?.active_stage, "gate");
    assert.equal(response.results?.[0]?.handoff?.action, "review_pending_approval");
    assert.equal(response.results?.[0]?.handoff?.approval_id, "apr_ready");
    assert.equal(response.results?.[0]?.history_count, 3);
    assert.equal(response.results?.[0]?.linked_operation_count, 1);
    assert.equal(response.results?.[0]?.run_ledger_count, 2);
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
  } finally {
    restoreFetch();
  }
});
