import assert from "node:assert/strict";
import test from "node:test";

import {
  FederationClient,
  parseFederationCompletionReview,
  parseFederationLiveRuntimeReadbacks,
  parseFederationStage16Status,
  parseFederationStage16ClosureDecisions,
} from "./index.ts";

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function installFetch(handler: FetchHandler): () => void {
  const globals = globalThis as typeof globalThis & {
    fetch?: typeof fetch;
    window?: { setTimeout: typeof setTimeout; clearTimeout: typeof clearTimeout };
  };
  const originalFetch = globals.fetch;
  const originalWindow = globals.window;

  globals.window = {
    setTimeout,
    clearTimeout,
  };
  globals.fetch = (async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = input instanceof Request ? input.url : input.toString();
    return await handler(url, init);
  }) as typeof fetch;

  return () => {
    if (originalFetch) {
      globals.fetch = originalFetch;
    } else {
      delete globals.fetch;
    }
    if (originalWindow) {
      globals.window = originalWindow;
    } else {
      delete globals.window;
    }
  };
}

test("FederationClient reads Stage 16 live readback gap without enabling mutations", async () => {
  const requests: Array<{ path: string; method: string; limit: string | null }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      limit: parsed.searchParams.get("limit"),
    });

    if (parsed.pathname === "/federation/status") {
      return jsonResponse({
        ok: true,
        status: "ready",
        stage: "Stage 16 / Federation",
        stage16_status: "stage16_contracts_ready_completion_blocked",
        stage16_completion_review_ready: false,
        live_runtime_readback_ready: false,
        completion_review_blockers: ["live_pairing_flow_observed", "workstation_sleep_continuity_validated"],
        ready_count: 6,
        required_count: 6,
        next_smallest_truthful_gap: "stage16_live_federation_runtime_readback",
      });
    }

    if (parsed.pathname === "/federation/live-runtime-readbacks") {
      return jsonResponse({
        ok: true,
        kind: "francis.stage16.federation.live_runtime_readback_receipts",
        stage: "Stage 16 / Federation",
        status: "empty",
        count: 0,
        receipt_ready_count: 0,
        ready_count: 0,
        required_count: 5,
        completion_eligible_readback_count: 0,
        readback_receipts_ready: false,
        live_runtime_readback_ready: false,
        missing_readbacks: ["live_pairing_flow_observed", "workstation_sleep_continuity_validated"],
        checks: [
          {
            id: "live_pairing_flow_observed",
            passed: false,
            receipt_ready: false,
            completion_evidence: false,
            status: "not_observed",
            receipt_id: "",
            evidence: "no live_pairing_flow_observed receipt has been recorded",
          },
        ],
        next_smallest_truthful_gap: "stage16_live_federation_runtime_readback",
      });
    }

    if (parsed.pathname === "/federation/completion-review") {
      return jsonResponse({
        ok: true,
        kind: "francis.stage16.federation.completion_review",
        stage: "Stage 16 / Federation",
        status: "blocked",
        contract_readiness_ready: true,
        live_runtime_readback_ready: false,
        stage16_completion_review_ready: false,
        ready_to_close: false,
        stage_closure_decision_required: false,
        blockers: ["live_pairing_flow_observed", "workstation_sleep_continuity_validated"],
        ready_count: 6,
        required_count: 6,
        live_ready_count: 0,
        live_required_count: 5,
        next_smallest_truthful_gap: "stage16_live_federation_runtime_readback",
      });
    }

    if (parsed.pathname === "/federation/stage-closure-decisions") {
      return jsonResponse({
        ok: true,
        kind: "francis.stage16.federation.stage16_operator_stage_closure_decision_receipts",
        stage: "Stage 16 / Federation",
        status: "empty",
        count: 0,
        total: 0,
        receipt_readback_ready: false,
        stage16_closed_by_receipt: false,
        marks_runtime_stage_state: false,
        reads_receipts: true,
        writes_receipts: false,
        writes_registry: false,
        writes_memory: false,
        runs_tools: false,
        runs_shell: false,
        runs_git: false,
        launches_browser: false,
        captures_screen: false,
        grants_execution_authority: false,
        grants_mutation_authority: false,
        items: [],
        next_smallest_truthful_gap: "stage16_operator_stage_closure_decision",
      });
    }

    return jsonResponse({ ok: false }, 404);
  });

  try {
    const client = new FederationClient("http://127.0.0.1:8000");
    const status = await client.getStatus({ timeoutMs: 50 });
    const readbacks = await client.getLiveRuntimeReadbacks({ limit: 5, timeoutMs: 50 });
    const review = await client.getCompletionReview({ timeoutMs: 50 });
    const closure = await client.getStageClosureDecisions({ limit: 5, timeoutMs: 50 });

    assert.deepEqual(requests, [
      { path: "/federation/status", method: "GET", limit: null },
      { path: "/federation/live-runtime-readbacks", method: "GET", limit: "5" },
      { path: "/federation/completion-review", method: "GET", limit: null },
      { path: "/federation/stage-closure-decisions", method: "GET", limit: "5" },
    ]);
    assert.equal(status.stage16_status, "stage16_contracts_ready_completion_blocked");
    assert.equal(status.stage16_completion_review_ready, false);
    assert.equal(status.live_runtime_readback_ready, false);
    assert.deepEqual(status.completion_review_blockers, [
      "live_pairing_flow_observed",
      "workstation_sleep_continuity_validated",
    ]);
    assert.equal(status.next_smallest_truthful_gap, "stage16_live_federation_runtime_readback");

    assert.equal(readbacks.status, "empty");
    assert.equal(readbacks.count, 0);
    assert.equal(readbacks.receipt_ready_count, 0);
    assert.equal(readbacks.ready_count, 0);
    assert.equal(readbacks.required_count, 5);
    assert.equal(readbacks.completion_eligible_readback_count, 0);
    assert.equal(readbacks.readback_receipts_ready, false);
    assert.equal(readbacks.live_runtime_readback_ready, false);
    assert.deepEqual(readbacks.missing_readbacks, [
      "live_pairing_flow_observed",
      "workstation_sleep_continuity_validated",
    ]);
    assert.equal(readbacks.checks[0]?.id, "live_pairing_flow_observed");
    assert.equal(readbacks.checks[0]?.passed, false);
    assert.equal(readbacks.checks[0]?.receipt_ready, false);
    assert.equal(readbacks.checks[0]?.completion_evidence, false);

    assert.equal(review.status, "blocked");
    assert.equal(review.contract_readiness_ready, true);
    assert.equal(review.live_runtime_readback_ready, false);
    assert.equal(review.stage16_completion_review_ready, false);
    assert.equal(review.ready_to_close, false);
    assert.equal(review.stage_closure_decision_required, false);
    assert.equal(review.live_ready_count, 0);
    assert.equal(review.live_required_count, 5);
    assert.deepEqual(review.blockers, ["live_pairing_flow_observed", "workstation_sleep_continuity_validated"]);

    assert.equal(closure.status, "empty");
    assert.equal(closure.count, 0);
    assert.equal(closure.total, 0);
    assert.equal(closure.receipt_readback_ready, false);
    assert.equal(closure.stage16_closed_by_receipt, false);
    assert.equal(closure.marks_runtime_stage_state, false);
    assert.equal(closure.reads_receipts, true);
    assert.equal(closure.writes_receipts, false);
    assert.equal(closure.writes_registry, false);
    assert.equal(closure.writes_memory, false);
    assert.equal(closure.runs_tools, false);
    assert.equal(closure.runs_shell, false);
    assert.equal(closure.runs_git, false);
    assert.equal(closure.launches_browser, false);
    assert.equal(closure.captures_screen, false);
    assert.equal(closure.grants_execution_authority, false);
    assert.equal(closure.grants_mutation_authority, false);
  } finally {
    restoreFetch();
  }
});

test("federation Stage 16 parsers preserve ready receipt-backed posture", () => {
  const status = parseFederationStage16Status({
    ok: true,
    stage16_status: "stage16_completion_review_ready",
    stage16_completion_review_ready: true,
    live_runtime_readback_ready: true,
    completion_review_blockers: [],
    ready_count: 6,
    required_count: 6,
    next_smallest_truthful_gap: "stage16_operator_stage_closure_decision",
  });
  const readbacks = parseFederationLiveRuntimeReadbacks({
    ok: true,
    status: "ready",
    count: 5,
    receipt_ready_count: 5,
    ready_count: 5,
    required_count: 5,
    completion_eligible_readback_count: 5,
    readback_receipts_ready: true,
    live_runtime_readback_ready: true,
    missing_readbacks: [],
    checks: [
      {
        id: "live_remote_approval_roundtrip_observed",
        passed: true,
        receipt_ready: true,
        completion_evidence: true,
        status: "observed",
        receipt_id: "fedlive_live_remote_approval_roundtrip_observed_test",
        proof_kind: "live_runtime_probe",
        source_node_id: "workstation",
        paired_node_id: "phone",
        trace_id: "trace-fed-live",
        evidence: "remote approval roundtrip observed",
      },
    ],
    next_smallest_truthful_gap: "stage16_completion_review",
  });
  const review = parseFederationCompletionReview({
    ok: true,
    status: "ready",
    contract_readiness_ready: true,
    live_runtime_readback_ready: true,
    stage16_completion_review_ready: true,
    ready_to_close: true,
    stage_closure_decision_required: true,
    blockers: [],
    ready_count: 6,
    required_count: 6,
    live_ready_count: 5,
    live_required_count: 5,
    next_smallest_truthful_gap: "stage16_operator_stage_closure_decision",
  });
  const closure = parseFederationStage16ClosureDecisions({
    ok: true,
    status: "stage_closure_decision_readback_ready",
    count: 1,
    total: 1,
    latest_receipt_id: "fedstage16close_test",
    latest_decision: "close_stage16",
    receipt_readback_ready: true,
    stage16_closed_by_receipt: true,
    marks_runtime_stage_state: false,
    reads_receipts: true,
    writes_receipts: false,
    writes_registry: false,
    writes_memory: false,
    runs_tools: false,
    runs_shell: false,
    runs_git: false,
    launches_browser: false,
    captures_screen: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    latest_receipt: {
      receipt_id: "fedstage16close_test",
      actor: "codex.builder",
      decision: "close_stage16",
      completion_review_ready: true,
      stage16_completion_review_ready: true,
      live_runtime_readback_ready: true,
      stage16_closed_by_receipt: true,
      recorded_ts: 1_800_020_000,
    },
    items: [
      {
        receipt_id: "fedstage16close_test",
        actor: "codex.builder",
        decision: "close_stage16",
        completion_review_ready: true,
        stage16_completion_review_ready: true,
        live_runtime_readback_ready: true,
        stage16_closed_by_receipt: true,
        recorded_ts: 1_800_020_000,
      },
    ],
    next_smallest_truthful_gap: "stage16_ledger_closure",
  });

  assert.equal(status.stage16_completion_review_ready, true);
  assert.equal(status.live_runtime_readback_ready, true);
  assert.deepEqual(status.completion_review_blockers, []);
  assert.equal(status.next_smallest_truthful_gap, "stage16_operator_stage_closure_decision");

  assert.equal(readbacks.live_runtime_readback_ready, true);
  assert.equal(readbacks.readback_receipts_ready, true);
  assert.equal(readbacks.receipt_ready_count, 5);
  assert.equal(readbacks.ready_count, 5);
  assert.equal(readbacks.completion_eligible_readback_count, 5);
  assert.equal(readbacks.checks[0]?.receipt_id, "fedlive_live_remote_approval_roundtrip_observed_test");
  assert.equal(readbacks.checks[0]?.proof_kind, "live_runtime_probe");
  assert.equal(readbacks.checks[0]?.trace_id, "trace-fed-live");
  assert.equal(readbacks.next_smallest_truthful_gap, "stage16_completion_review");

  assert.equal(review.ready_to_close, true);
  assert.equal(review.stage_closure_decision_required, true);
  assert.equal(review.live_ready_count, 5);
  assert.equal(review.next_smallest_truthful_gap, "stage16_operator_stage_closure_decision");

  assert.equal(closure.status, "stage_closure_decision_readback_ready");
  assert.equal(closure.count, 1);
  assert.equal(closure.latest_receipt_id, "fedstage16close_test");
  assert.equal(closure.latest_decision, "close_stage16");
  assert.equal(closure.receipt_readback_ready, true);
  assert.equal(closure.stage16_closed_by_receipt, true);
  assert.equal(closure.marks_runtime_stage_state, false);
  assert.equal(closure.writes_memory, false);
  assert.equal(closure.runs_shell, false);
  assert.equal(closure.grants_execution_authority, false);
  assert.equal(closure.latest_receipt?.decision, "close_stage16");
  assert.equal(closure.items[0]?.recorded_ts, 1_800_020_000);
  assert.equal(closure.next_smallest_truthful_gap, "stage16_ledger_closure");
});
