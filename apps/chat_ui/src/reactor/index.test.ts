import assert from "node:assert/strict";
import test from "node:test";

import {
  ReactorApiError,
  ReactorClient,
  parseReactorOperatorVisibilitySummary,
  parseReactorReviewQueueSnapshot,
} from "./index.ts";

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

test("ReactorClient.getOperatorVisibilitySummary reads backend visibility without authority claims", async () => {
  const requests: Array<{ path: string; method: string; limit: string | null }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
    });

    return jsonResponse({
      ok: true,
      kind: "reactor.operator_visibility.summary",
      status: "ready",
      limit: "5",
      next_step: "review_active_reactor_queue",
      event_total: "2",
      review_queue_total: 1,
      deadletter_total: 0,
      retry_schedule_total: 0,
      external_delivery_total: 0,
      recovery_receipt_total: 0,
      proposal_review_history_total: 1,
      attention: {
        review_queue_total: 1,
        due_retry_total: "0",
        proposal_review_ready_total: 1,
      },
      counts: {
        review_route: {
          approval_queue: 1,
        },
        proposal_review_outcome: {
          proposal_review_ready: "1",
        },
      },
      readback_surfaces: {
        review_queue: "/reactor/review_queue",
        proposal_review_history: "/reactor/proposal_reviews/history/list",
      },
      latest_review_items: [
        {
          event_id: "evt_visibility_review",
          status: "blocked",
          stable_state: "awaiting_approval",
          trigger: {
            source: "user_request",
            summary: "Approval-gated mutation needs operator visibility.",
            approval_id: "apr_visibility",
          },
          review: {
            route: "approval_queue",
            gate: "approval_required",
            next_step: "review_approval_before_dispatch",
            execution_started: false,
            applied: false,
          },
        },
      ],
      latest_proposal_reviews: [
        {
          kind: "reactor.proposal_review.history.readback",
          event_id: "evt_visibility_proposal",
          status: "dispatch_completed",
          stable_state: "proposal_review_inspected",
          summary: "Inspect Forge proposal visibility through Reactor.",
          route: "proposal_review",
          outcome: "proposal_review_ready",
          proposal_id: "proposal_visibility",
          plugin_id: "generated.visibility",
          quality_ready: true,
          readback_only: true,
          proposal_decision_applied: false,
          promotion_applied: false,
          execution_started: false,
          memory_write: false,
          verified: true,
        },
      ],
      ready_external_delivery_processor_items: [],
      governance: {
        execution_authority: false,
        dispatch_authority: false,
        approval_authority: false,
        retry_authority: false,
        external_delivery_authority: false,
        proposal_decision_authority: false,
        promotion_authority: false,
        memory_write: false,
      },
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000/");
    const summary = await client.getOperatorVisibilitySummary({ limit: 5 });

    assert.deepEqual(requests, [
      {
        path: "/reactor/operator_visibility/summary",
        method: "GET",
        limit: "5",
      },
    ]);
    assert.equal(summary.ok, true);
    assert.equal(summary.kind, "reactor.operator_visibility.summary");
    assert.equal(summary.event_total, 2);
    assert.equal(summary.review_queue_total, 1);
    assert.equal(summary.proposal_review_history_total, 1);
    assert.equal(summary.attention.review_queue_total, 1);
    assert.equal(summary.counts.review_route?.approval_queue, 1);
    assert.equal(summary.readback_surfaces.proposal_review_history, "/reactor/proposal_reviews/history/list");
    assert.equal(summary.latest_review_items[0]?.event_id, "evt_visibility_review");
    assert.equal(summary.latest_review_items[0]?.trigger?.approval_id, "apr_visibility");
    assert.equal(summary.latest_review_items[0]?.review?.execution_started, false);
    assert.equal(summary.latest_proposal_reviews[0]?.event_id, "evt_visibility_proposal");
    assert.equal(summary.latest_proposal_reviews[0]?.proposal_id, "proposal_visibility");
    assert.equal(summary.latest_proposal_reviews[0]?.quality_ready, true);
    assert.equal(summary.latest_proposal_reviews[0]?.readback_only, true);
    assert.equal(summary.latest_proposal_reviews[0]?.promotion_applied, false);
    assert.equal(summary.latest_proposal_reviews[0]?.memory_write, false);
    assert.equal(summary.governance?.execution_authority, false);
    assert.equal(summary.governance?.approval_authority, false);
    assert.equal(summary.governance?.promotion_authority, false);
    assert.equal(summary.governance?.memory_write, false);
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

test("ReactorClient.listEvents preserves proposal review receipts without authority claims", async () => {
  const requests: Array<{
    path: string;
    method: string;
    limit: string | null;
    triggerSource: string | null;
    stableState: string | null;
    receiptKind: string | null;
  }> = [];
  const restoreFetch = installFetch((url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
      triggerSource: parsed.searchParams.get("trigger_source"),
      stableState: parsed.searchParams.get("stable_state"),
      receiptKind: parsed.searchParams.get("receipt_kind"),
    });

    return jsonResponse({
      ok: true,
      items: [
        {
          event_id: "evt_forge_review",
          status: "dispatch_completed",
          stable_state: "proposal_review_inspected",
          updated_ts: "1770001200",
          trigger: {
            source: "forge_proposal",
            type: "forge_proposal",
            summary: "Inspect Forge proposal before operator decision.",
            metadata: {
              proposal_id: "proposal_reactor_ui",
            },
          },
          classification: {
            mode: "pilot",
            risk_tier: "normal",
            action_class: "proposal_review",
            approval_required: false,
          },
          latest_dispatch_execution_receipt: {
            kind: "reactor.dispatch.execution.receipt",
            receipt_id: "evt_forge_review_dispatch_execution_1",
            event_id: "evt_forge_review",
            status: "completed",
            outcome: "proposal_review_ready",
            route: "proposal_review",
            stable_state: "proposal_review_inspected",
            next_step: "eligible_for_operator_review_decision",
            proposal_id: "proposal_reactor_ui",
            plugin_id: "generated.reactor_ui",
            proposal_status: "staged",
            quality_ready: true,
            missing_requirements: [],
            review_status: "staged",
            validation_receipt_id: "validation_reactor_ui",
            readback_only: true,
            proposal_decision_applied: false,
            promotion_applied: false,
            execution_started: false,
            dispatch_applied: true,
            verified: true,
            completion_claim_allowed: true,
            memory_write: false,
          },
          latest_verification_receipt: {
            kind: "reactor.verification.receipt",
            receipt_id: "evt_forge_review_verification_1",
            status: "passed",
            route: "proposal_review",
            verified: true,
            execution_started: false,
            dispatch_applied: true,
            memory_write: false,
          },
          latest_stable_return: {
            kind: "reactor.stable_return.receipt",
            receipt_id: "evt_forge_review_stable_return_1",
            route: "proposal_review",
            stable_state: "proposal_review_inspected",
            execution_started: false,
            dispatch_applied: true,
            memory_write: false,
          },
        },
      ],
      total: 1,
      limit: 6,
    });
  });

  try {
    const client = new ReactorClient("http://127.0.0.1:8000");
    const snapshot = await client.listEvents({
      limit: 6,
      trigger_source: "forge_proposal",
      stable_state: "proposal_review_inspected",
      receipt_kind: "reactor.dispatch.execution.receipt",
    });

    assert.deepEqual(requests, [
      {
        path: "/reactor/events/list",
        method: "GET",
        limit: "6",
        triggerSource: "forge_proposal",
        stableState: "proposal_review_inspected",
        receiptKind: "reactor.dispatch.execution.receipt",
      },
    ]);
    assert.equal(snapshot.ok, true);
    assert.equal(snapshot.trigger_source, "forge_proposal");
    assert.equal(snapshot.stable_state, "proposal_review_inspected");
    assert.equal(snapshot.receipt_kind, "reactor.dispatch.execution.receipt");
    assert.equal(snapshot.items[0]?.event_id, "evt_forge_review");
    assert.equal(snapshot.items[0]?.trigger?.proposal_id, "proposal_reactor_ui");
    assert.equal(snapshot.items[0]?.classification?.action_class, "proposal_review");
    const receipt = snapshot.items[0]?.latest_dispatch_execution_receipt;
    assert.equal(receipt?.kind, "reactor.dispatch.execution.receipt");
    assert.equal(receipt?.route, "proposal_review");
    assert.equal(receipt?.proposal_id, "proposal_reactor_ui");
    assert.equal(receipt?.plugin_id, "generated.reactor_ui");
    assert.equal(receipt?.quality_ready, true);
    assert.equal(receipt?.readback_only, true);
    assert.equal(receipt?.proposal_decision_applied, false);
    assert.equal(receipt?.promotion_applied, false);
    assert.equal(receipt?.execution_started, false);
    assert.equal(receipt?.memory_write, false);
    assert.equal(snapshot.items[0]?.latest_verification_receipt?.verified, true);
    assert.equal(snapshot.items[0]?.latest_stable_return?.dispatch_applied, true);
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

test("parseReactorOperatorVisibilitySummary drops malformed nested items and preserves errors", () => {
  const summary = parseReactorOperatorVisibilitySummary({
    ok: false,
    error: "reactor_visibility_unavailable",
    latest_review_items: [{ no_id: true }, { id: "evt_review_fallback", review: { route: "retry_due" } }],
    latest_proposal_reviews: [{ no_id: true }, { id: "evt_proposal_fallback", proposal_id: "proposal_fallback" }],
    ready_external_delivery_processor_items: [{ no_id: true }, { deadletter_id: "rdl_ready", delivery_processor_ready: true }],
    attention: { due_retry_total: "2" },
    counts: { retry_status: { due: "2" } },
    readback_surfaces: { retry_schedules: "/reactor/retries/list", empty: "" },
  });

  assert.equal(summary.ok, false);
  assert.equal(summary.error, "reactor_visibility_unavailable");
  assert.equal(summary.latest_review_items.length, 1);
  assert.equal(summary.latest_review_items[0]?.event_id, "evt_review_fallback");
  assert.equal(summary.latest_proposal_reviews.length, 1);
  assert.equal(summary.latest_proposal_reviews[0]?.proposal_id, "proposal_fallback");
  assert.equal(summary.ready_external_delivery_processor_items.length, 1);
  assert.equal(summary.ready_external_delivery_processor_items[0]?.deadletter_id, "rdl_ready");
  assert.equal(summary.ready_external_delivery_processor_items[0]?.delivery_processor_ready, true);
  assert.equal(summary.attention.due_retry_total, 2);
  assert.equal(summary.counts.retry_status?.due, 2);
  assert.equal(summary.readback_surfaces.retry_schedules, "/reactor/retries/list");
  assert.equal(summary.readback_surfaces.empty, undefined);
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
