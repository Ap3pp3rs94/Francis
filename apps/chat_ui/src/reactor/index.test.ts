import assert from "node:assert/strict";
import test from "node:test";

import { ReactorApiError, ReactorClient, parseReactorReviewQueueSnapshot } from "./index.ts";

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

test("ReactorClient.getReviewQueue reads the review queue without mutation authority", async () => {
  const requests: Array<{ path: string; method: string; limit: string | null; route: string | null }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
      route: parsed.searchParams.get("route"),
    });

    return jsonResponse({
      ok: true,
      items: [
        {
          event_id: "evt_approval",
          status: "blocked",
          stable_state: "blocked_for_approval",
          created_ts: "1770000400",
          trigger: {
            source: "mission.loop",
            type: "mission_operation",
            summary: "Mission operation requires approval.",
            mission_id: "msn_alpha",
            operation_id: "task_alpha",
            approval_id: "apr_alpha",
          },
          classification: {
            mode: "approval_required",
            risk_tier: "medium",
            action_class: "operation.run",
            approval_required: true,
          },
          review: {
            route: "approval_queue",
            status: "blocked",
            gate: "requires_approval",
            action: "review_approval",
            next_step: "Operator must approve before dispatch.",
            receipt_kind: "reactor.blocked_dispatch",
            receipt_ref: "evt_approval:dispatch:1",
            execution_started: false,
            applied: false,
          },
        },
      ],
      total: 1,
      available_total: 3,
      limit: 8,
      route_counts: {
        approval_queue: 1,
        retry_candidate: "2",
      },
      stable_state_counts: {
        blocked_for_approval: 1,
      },
      governance: {
        read_only: true,
        execution_authority: false,
        approval_authority: false,
      },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000/");
    const snapshot = await client.getReviewQueue({ limit: 8 });

    assert.deepEqual(requests, [
      {
        path: "/reactor/review_queue",
        method: "GET",
        limit: "8",
        route: null,
      },
    ]);
    assert.equal(snapshot.ok, true);
    assert.equal(snapshot.items[0]?.event_id, "evt_approval");
    assert.equal(snapshot.items[0]?.trigger?.approval_id, "apr_alpha");
    assert.equal(snapshot.items[0]?.classification?.approval_required, true);
    assert.equal(snapshot.items[0]?.review?.route, "approval_queue");
    assert.equal(snapshot.items[0]?.created_ts, 1770000400);
    assert.equal(snapshot.route_counts.retry_candidate, 2);
    assert.equal(snapshot.governance?.execution_authority, false);
    assert.equal(snapshot.governance?.approval_authority, false);
  } finally {
    restoreFetch();
  }
});

test("ReactorClient.getReviewQueue preserves route filters", async () => {
  const requests: Array<{ route: string | null; limit: string | null }> = [];
  const restoreFetch = installFetch((url) => {
    const parsed = new URL(url);
    requests.push({
      route: parsed.searchParams.get("route"),
      limit: parsed.searchParams.get("limit"),
    });
    return jsonResponse({
      ok: true,
      route: "deadletter_escalation",
      items: [
        {
          event_id: "evt_deadletter_escalation",
          stable_state: "deadletter_escalation_pending",
          review: {
            route: "deadletter_escalation",
            status: "escalation_pending",
            gate: "reactor_deadletter_resolution",
            action: "track_escalation_pending_external_or_operator_followup",
            next_step: "track_escalation_pending_external_or_operator_followup",
            receipt_kind: "reactor.deadletter.resolution.receipt",
            receipt_ref: "rdl_alpha_resolution_escalation_pending",
            execution_started: false,
            applied: true,
          },
        },
      ],
      total: 1,
      available_total: 1,
      limit: 20,
      route_counts: { deadletter_escalation: 1 },
      stable_state_counts: { deadletter_escalation_pending: 1 },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    const snapshot = await client.getReviewQueue({ route: "deadletter_escalation", limit: 20 });

    assert.deepEqual(requests, [{ route: "deadletter_escalation", limit: "20" }]);
    assert.equal(snapshot.route, "deadletter_escalation");
    assert.equal(snapshot.items[0]?.stable_state, "deadletter_escalation_pending");
    assert.equal(snapshot.items[0]?.review?.route, "deadletter_escalation");
    assert.equal(snapshot.items[0]?.review?.receipt_kind, "reactor.deadletter.resolution.receipt");
    assert.equal(snapshot.items[0]?.review?.execution_started, false);
    assert.equal(snapshot.items[0]?.review?.applied, true);
    assert.equal(snapshot.route_counts.deadletter_escalation, 1);
  } finally {
    restoreFetch();
  }
});

test("ReactorClient.getReviewQueue preserves escalation handoff route filters", async () => {
  const requests: Array<{ route: string | null; limit: string | null }> = [];
  const restoreFetch = installFetch((url) => {
    const parsed = new URL(url);
    requests.push({
      route: parsed.searchParams.get("route"),
      limit: parsed.searchParams.get("limit"),
    });
    return jsonResponse({
      ok: true,
      route: "deadletter_escalation_handoff",
      items: [
        {
          event_id: "evt_deadletter_handoff",
          stable_state: "deadletter_escalation_handoff_recorded",
          review: {
            route: "deadletter_escalation_handoff",
            status: "handoff_recorded",
            gate: "reactor_deadletter_escalation_handoff",
            action: "track_escalation_handoff_until_acknowledged",
            next_step: "operator_or_external_escalation_must_acknowledge_before_recovery_execution",
            receipt_kind: "reactor.deadletter.escalation_handoff.receipt",
            receipt_ref: "rdl_alpha_escalation_handoff",
            execution_started: false,
            applied: true,
          },
        },
      ],
      total: 1,
      available_total: 1,
      limit: 20,
      route_counts: { deadletter_escalation_handoff: 1 },
      stable_state_counts: { deadletter_escalation_handoff_recorded: 1 },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    const snapshot = await client.getReviewQueue({ route: "deadletter_escalation_handoff", limit: 20 });

    assert.deepEqual(requests, [{ route: "deadletter_escalation_handoff", limit: "20" }]);
    assert.equal(snapshot.route, "deadletter_escalation_handoff");
    assert.equal(snapshot.items[0]?.stable_state, "deadletter_escalation_handoff_recorded");
    assert.equal(snapshot.items[0]?.review?.route, "deadletter_escalation_handoff");
    assert.equal(snapshot.items[0]?.review?.receipt_kind, "reactor.deadletter.escalation_handoff.receipt");
    assert.equal(snapshot.items[0]?.review?.execution_started, false);
    assert.equal(snapshot.items[0]?.review?.applied, true);
    assert.equal(snapshot.route_counts.deadletter_escalation_handoff, 1);
  } finally {
    restoreFetch();
  }
});

test("ReactorClient.getReviewQueue preserves escalation acknowledgement route filters", async () => {
  const requests: Array<{ route: string | null; limit: string | null }> = [];
  const restoreFetch = installFetch((url) => {
    const parsed = new URL(url);
    requests.push({
      route: parsed.searchParams.get("route"),
      limit: parsed.searchParams.get("limit"),
    });
    return jsonResponse({
      ok: true,
      route: "deadletter_escalation_acknowledgement",
      items: [
        {
          event_id: "evt_deadletter_acknowledgement",
          stable_state: "deadletter_escalation_acknowledged",
          review: {
            route: "deadletter_escalation_acknowledgement",
            status: "acknowledged",
            gate: "reactor_deadletter_escalation_acknowledgement",
            action: "wait_for_explicit_recovery_execution_boundary_after_acknowledgement",
            next_step: "wait_for_explicit_recovery_execution_boundary_after_acknowledgement",
            receipt_kind: "reactor.deadletter.escalation_acknowledgement.receipt",
            receipt_ref: "rdl_alpha_escalation_acknowledgement",
            execution_started: false,
            applied: true,
          },
        },
      ],
      total: 1,
      available_total: 1,
      limit: 20,
      route_counts: { deadletter_escalation_acknowledgement: 1 },
      stable_state_counts: { deadletter_escalation_acknowledged: 1 },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    const snapshot = await client.getReviewQueue({ route: "deadletter_escalation_acknowledgement", limit: 20 });

    assert.deepEqual(requests, [{ route: "deadletter_escalation_acknowledgement", limit: "20" }]);
    assert.equal(snapshot.route, "deadletter_escalation_acknowledgement");
    assert.equal(snapshot.items[0]?.stable_state, "deadletter_escalation_acknowledged");
    assert.equal(snapshot.items[0]?.review?.route, "deadletter_escalation_acknowledgement");
    assert.equal(snapshot.items[0]?.review?.receipt_kind, "reactor.deadletter.escalation_acknowledgement.receipt");
    assert.equal(snapshot.items[0]?.review?.execution_started, false);
    assert.equal(snapshot.items[0]?.review?.applied, true);
    assert.equal(snapshot.route_counts.deadletter_escalation_acknowledgement, 1);
  } finally {
    restoreFetch();
  }
});

test("ReactorClient.listDeadletters reads disposition history without mutation authority", async () => {
  const requests: Array<{ path: string; method: string; limit: string | null; status: string | null }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
      status: parsed.searchParams.get("status"),
    });

    return jsonResponse({
      ok: true,
      items: [
        {
          deadletter_id: "rdl_resolved",
          event_id: "evt_resolved",
          status: "resolved",
          route: "deadletter_resolution",
          stable_state: "deadletter_resolved",
          next_step: "keep_deadletter_resolution_receipt_for_audit",
          source_receipt_kind: "reactor.deadletter_candidate.receipt",
          source_receipt_ref: "candidate_resolved",
          resolution_decision: "resolved_no_action",
          deadletter_resolved: true,
          escalation_recorded: false,
          execution_started: false,
          retry_started: false,
          escalation_started: false,
          created_ts: "1770000800",
          updated_ts: "1770000900",
          latest_resolution_receipt: {
            kind: "reactor.deadletter.resolution.receipt",
            receipt_id: "rdl_resolved_resolution_resolved_no_action",
            status: "resolved",
            route: "deadletter_resolution",
            resolution_decision: "resolved_no_action",
            deadletter_resolved: true,
            execution_started: false,
            retry_started: false,
            escalation_started: false,
            memory_write: false,
          },
        },
      ],
      total: 1,
      limit: 6,
      status: "resolved",
      governance: {
        execution_authority: false,
        deadletter_resolution_authority: false,
        escalation_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    const snapshot = await client.listDeadletters({ status: "resolved", limit: 6 });

    assert.deepEqual(requests, [
      {
        path: "/reactor/deadletters/list",
        method: "GET",
        limit: "6",
        status: "resolved",
      },
    ]);
    assert.equal(snapshot.ok, true);
    assert.equal(snapshot.status, "resolved");
    assert.equal(snapshot.items[0]?.deadletter_id, "rdl_resolved");
    assert.equal(snapshot.items[0]?.status, "resolved");
    assert.equal(snapshot.items[0]?.route, "deadletter_resolution");
    assert.equal(snapshot.items[0]?.stable_state, "deadletter_resolved");
    assert.equal(snapshot.items[0]?.deadletter_resolved, true);
    assert.equal(snapshot.items[0]?.execution_started, false);
    assert.equal(snapshot.items[0]?.latest_resolution_receipt?.kind, "reactor.deadletter.resolution.receipt");
    assert.equal(snapshot.items[0]?.latest_resolution_receipt?.memory_write, false);
    assert.equal(snapshot.governance?.execution_authority, false);
  } finally {
    restoreFetch();
  }
});

test("ReactorClient.listDeadletters preserves escalation handoff receipts without authority claims", async () => {
  const requests: Array<{ path: string; method: string; limit: string | null; status: string | null }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
      status: parsed.searchParams.get("status"),
    });

    return jsonResponse({
      ok: true,
      items: [
        {
          deadletter_id: "rdl_handoff",
          event_id: "evt_handoff",
          status: "escalation_handoff_recorded",
          route: "deadletter_escalation_handoff",
          stable_state: "deadletter_escalation_handoff_recorded",
          next_step: "operator_or_external_escalation_must_acknowledge_before_recovery_execution",
          source_receipt_kind: "reactor.deadletter.resolution.receipt",
          source_receipt_ref: "rdl_handoff_resolution_escalation_pending",
          resolution_decision: "escalation_pending",
          deadletter_resolved: false,
          escalation_recorded: true,
          escalation_handoff_recorded: true,
          execution_started: false,
          retry_started: false,
          escalation_started: false,
          latest_escalation_handoff_receipt: {
            kind: "reactor.deadletter.escalation_handoff.receipt",
            receipt_id: "rdl_handoff_escalation_handoff",
            status: "handoff_recorded",
            route: "deadletter_escalation_handoff",
            resolution_decision: "escalation_pending",
            escalation_handoff_recorded: true,
            external_escalation_started: false,
            execution_started: false,
            retry_started: false,
            escalation_started: false,
            memory_write: false,
          },
        },
      ],
      total: 1,
      limit: 6,
      status: "escalation_handoff_recorded",
      governance: {
        execution_authority: false,
        retry_authority: false,
        escalation_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    const snapshot = await client.listDeadletters({ status: "escalation_handoff_recorded", limit: 6 });

    assert.deepEqual(requests, [
      {
        path: "/reactor/deadletters/list",
        method: "GET",
        limit: "6",
        status: "escalation_handoff_recorded",
      },
    ]);
    assert.equal(snapshot.ok, true);
    assert.equal(snapshot.items[0]?.status, "escalation_handoff_recorded");
    assert.equal(snapshot.items[0]?.route, "deadletter_escalation_handoff");
    assert.equal(snapshot.items[0]?.escalation_recorded, true);
    assert.equal(snapshot.items[0]?.escalation_handoff_recorded, true);
    assert.equal(snapshot.items[0]?.execution_started, false);
    assert.equal(snapshot.items[0]?.latest_escalation_handoff_receipt?.kind, "reactor.deadletter.escalation_handoff.receipt");
    assert.equal(snapshot.items[0]?.latest_escalation_handoff_receipt?.external_escalation_started, false);
    assert.equal(snapshot.items[0]?.latest_escalation_handoff_receipt?.memory_write, false);
    assert.equal(snapshot.governance?.execution_authority, false);
    assert.equal(snapshot.governance?.escalation_authority, false);
  } finally {
    restoreFetch();
  }
});

test("ReactorClient.listDeadletters preserves escalation acknowledgement receipts without authority claims", async () => {
  const requests: Array<{ path: string; method: string; limit: string | null; status: string | null }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
      status: parsed.searchParams.get("status"),
    });

    return jsonResponse({
      ok: true,
      items: [
        {
          deadletter_id: "rdl_acknowledged",
          event_id: "evt_acknowledged",
          status: "escalation_acknowledged",
          route: "deadletter_escalation_acknowledgement",
          stable_state: "deadletter_escalation_acknowledged",
          next_step: "wait_for_explicit_recovery_execution_boundary_after_acknowledgement",
          source_receipt_kind: "reactor.deadletter.escalation_handoff.receipt",
          source_receipt_ref: "rdl_acknowledged_escalation_handoff",
          resolution_decision: "escalation_pending",
          deadletter_resolved: false,
          escalation_recorded: true,
          escalation_handoff_recorded: true,
          escalation_acknowledged: true,
          external_escalation_started: false,
          recovery_started: false,
          execution_started: false,
          retry_started: false,
          escalation_started: false,
          latest_escalation_acknowledgement_receipt: {
            kind: "reactor.deadletter.escalation_acknowledgement.receipt",
            receipt_id: "rdl_acknowledged_escalation_acknowledgement",
            status: "acknowledged",
            route: "deadletter_escalation_acknowledgement",
            resolution_decision: "escalation_pending",
            escalation_acknowledged: true,
            external_escalation_started: false,
            recovery_started: false,
            execution_started: false,
            retry_started: false,
            escalation_started: false,
            memory_write: false,
          },
        },
      ],
      total: 1,
      limit: 6,
      status: "escalation_acknowledged",
      governance: {
        execution_authority: false,
        retry_authority: false,
        escalation_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    const snapshot = await client.listDeadletters({ status: "escalation_acknowledged", limit: 6 });

    assert.deepEqual(requests, [
      {
        path: "/reactor/deadletters/list",
        method: "GET",
        limit: "6",
        status: "escalation_acknowledged",
      },
    ]);
    assert.equal(snapshot.ok, true);
    assert.equal(snapshot.items[0]?.status, "escalation_acknowledged");
    assert.equal(snapshot.items[0]?.route, "deadletter_escalation_acknowledgement");
    assert.equal(snapshot.items[0]?.escalation_recorded, true);
    assert.equal(snapshot.items[0]?.escalation_handoff_recorded, true);
    assert.equal(snapshot.items[0]?.escalation_acknowledged, true);
    assert.equal(snapshot.items[0]?.external_escalation_started, false);
    assert.equal(snapshot.items[0]?.recovery_started, false);
    assert.equal(snapshot.items[0]?.execution_started, false);
    assert.equal(
      snapshot.items[0]?.latest_escalation_acknowledgement_receipt?.kind,
      "reactor.deadletter.escalation_acknowledgement.receipt",
    );
    assert.equal(snapshot.items[0]?.latest_escalation_acknowledgement_receipt?.external_escalation_started, false);
    assert.equal(snapshot.items[0]?.latest_escalation_acknowledgement_receipt?.recovery_started, false);
    assert.equal(snapshot.items[0]?.latest_escalation_acknowledgement_receipt?.memory_write, false);
    assert.equal(snapshot.governance?.execution_authority, false);
    assert.equal(snapshot.governance?.escalation_authority, false);
  } finally {
    restoreFetch();
  }
});

test("ReactorClient.listDeadletters preserves recovery request and dispatch receipts without authority claims", async () => {
  const requests: Array<{ path: string; method: string; limit: string | null; status: string | null }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
      status: parsed.searchParams.get("status"),
    });

    return jsonResponse({
      ok: true,
      items: [
        {
          deadletter_id: "rdl_recovery_requested",
          event_id: "evt_recovery_requested",
          status: "recovery_requested",
          route: "deadletter_recovery_request",
          stable_state: "deadletter_recovery_requested",
          next_step: "wait_for_explicit_recovery_dispatch_attempt",
          source_receipt_kind: "reactor.deadletter.escalation_acknowledgement.receipt",
          source_receipt_ref: "rdl_recovery_requested_escalation_acknowledgement",
          resolution_decision: "escalation_pending",
          escalation_recorded: true,
          escalation_handoff_recorded: true,
          escalation_acknowledged: true,
          recovery_requested: true,
          recovery_dispatched: false,
          recovery_started: false,
          execution_started: false,
          latest_recovery_request_receipt: {
            kind: "reactor.deadletter.recovery_request.receipt",
            receipt_id: "rdl_recovery_requested_recovery_request",
            status: "recovery_requested",
            route: "deadletter_recovery_request",
            stable_state: "deadletter_recovery_requested",
            recovery_requested: true,
            recovery_event_id: "evt_recovery_dispatch",
            recovery_started: false,
            execution_started: false,
            memory_write: false,
          },
        },
        {
          deadletter_id: "rdl_recovery_dispatched",
          event_id: "evt_recovery_dispatched",
          status: "recovery_dispatched",
          route: "deadletter_recovery_dispatch",
          stable_state: "deadletter_recovery_dispatched",
          next_step: "keep_recovery_dispatch_receipt_for_audit",
          source_receipt_kind: "reactor.deadletter.recovery_request.receipt",
          source_receipt_ref: "rdl_recovery_dispatched_recovery_request",
          recovery_requested: true,
          recovery_dispatched: true,
          recovery_started: true,
          execution_started: true,
          latest_recovery_dispatch_receipt: {
            kind: "reactor.deadletter.recovery_dispatch.receipt",
            receipt_id: "rdl_recovery_dispatched_recovery_dispatch",
            status: "recovery_dispatched",
            route: "deadletter_recovery_dispatch",
            stable_state: "deadletter_recovery_dispatched",
            recovery_requested: true,
            recovery_dispatched: true,
            recovery_request_receipt_id: "rdl_recovery_dispatched_recovery_request",
            recovery_started: true,
            execution_started: true,
            memory_write: false,
          },
        },
      ],
      total: 2,
      limit: 6,
      status: "recovery_dispatched",
      governance: {
        execution_authority: false,
        retry_authority: false,
        escalation_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    const snapshot = await client.listDeadletters({ status: "recovery_dispatched", limit: 6 });

    assert.deepEqual(requests, [
      {
        path: "/reactor/deadletters/list",
        method: "GET",
        limit: "6",
        status: "recovery_dispatched",
      },
    ]);
    assert.equal(snapshot.ok, true);
    assert.equal(snapshot.items[0]?.status, "recovery_requested");
    assert.equal(snapshot.items[0]?.recovery_requested, true);
    assert.equal(snapshot.items[0]?.recovery_dispatched, false);
    assert.equal(snapshot.items[0]?.latest_recovery_request_receipt?.kind, "reactor.deadletter.recovery_request.receipt");
    assert.equal(snapshot.items[0]?.latest_recovery_request_receipt?.recovery_event_id, "evt_recovery_dispatch");
    assert.equal(snapshot.items[0]?.latest_recovery_request_receipt?.memory_write, false);
    assert.equal(snapshot.items[1]?.status, "recovery_dispatched");
    assert.equal(snapshot.items[1]?.route, "deadletter_recovery_dispatch");
    assert.equal(snapshot.items[1]?.recovery_requested, true);
    assert.equal(snapshot.items[1]?.recovery_dispatched, true);
    assert.equal(snapshot.items[1]?.latest_recovery_dispatch_receipt?.kind, "reactor.deadletter.recovery_dispatch.receipt");
    assert.equal(
      snapshot.items[1]?.latest_recovery_dispatch_receipt?.recovery_request_receipt_id,
      "rdl_recovery_dispatched_recovery_request",
    );
    assert.equal(snapshot.items[1]?.latest_recovery_dispatch_receipt?.execution_started, true);
    assert.equal(snapshot.governance?.execution_authority, false);
  } finally {
    restoreFetch();
  }
});

test("parseReactorReviewQueueSnapshot drops malformed items and preserves route errors", () => {
  const snapshot = parseReactorReviewQueueSnapshot({
    ok: false,
    error: "event_store_unavailable",
    items: [{ no_id: true }, { id: "evt_fallback", review: { route: "deadletter_candidate" } }],
  });

  assert.equal(snapshot.ok, false);
  assert.equal(snapshot.error, "event_store_unavailable");
  assert.equal(snapshot.items.length, 1);
  assert.equal(snapshot.items[0]?.event_id, "evt_fallback");
  assert.equal(snapshot.items[0]?.review?.route, "deadletter_candidate");
});

test("ReactorClient.getReviewQueue throws ReactorApiError on HTTP failures", async () => {
  const restoreFetch = installFetch(() => jsonResponse({ ok: false }, 503));

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    await assert.rejects(
      () => client.getReviewQueue(),
      (err: unknown) => {
        assert.ok(err instanceof ReactorApiError);
        assert.equal(err.status, 503);
        assert.match(err.message, /HTTP 503/);
        return true;
      },
    );
  } finally {
    restoreFetch();
  }
});
