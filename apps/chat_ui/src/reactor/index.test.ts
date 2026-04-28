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
