import assert from "node:assert/strict";
import test from "node:test";

import {
  FederationClient,
  parseFederationCompletionReview,
  parseFederationLiveRuntimeReadbacks,
  parseFederationSleepContinuityAction,
  parseFederationSleepContinuityRunbook,
  parseFederationStage16Status,
  parseFederationStage16ClosureDecisions,
  presentFederationSleepContinuity,
  presentFederationSleepContinuityAction,
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
        sleep_continuity_status: "blocked_on_prior_live_readbacks",
        sleep_continuity_ready: false,
        pre_sleep_evidence_ready: false,
        post_resume_evidence_ready: false,
        latest_pre_sleep_evidence: {
          present: false,
        },
        latest_post_resume_evidence: {
          present: false,
        },
        sleep_continuity_next_step: "stage16_live_federation_runtime_readback",
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

    if (parsed.pathname === "/federation/sleep-continuity-runbook") {
      return jsonResponse({
        ok: true,
        kind: "francis.stage16.federation.sleep_continuity_runbook",
        stage: "Stage 16 / Federation",
        status: "ready_for_operator_sleep_resume",
        runbook_only: true,
        prerequisite_readback_ids: [
          "live_pairing_flow_observed",
          "live_selective_sync_observed",
          "live_remote_approval_roundtrip_observed",
          "live_revocation_roundtrip_observed",
        ],
        prerequisite_readbacks_ready: true,
        sleep_continuity_readback_id: "workstation_sleep_continuity_validated",
        sleep_continuity_ready: false,
        pre_sleep_evidence_ready: true,
        pre_sleep_evidence: {
          present: true,
          evidence_path: "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
          continuity_record_id: "stage16-sleep-continuity-test",
          metadata_only: true,
          contains_raw_private_data: false,
          writes_runtime_readback: false,
          marks_stage16_closed: false,
        },
        post_resume_evidence_ready: true,
        post_resume_evidence: {
          present: true,
          evidence_path:
            "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\post_resume_test.json",
          linked_to_latest_pre_sleep: true,
          operator_confirmed_sleep_resume: true,
          continuity_available_after_resume: true,
          writes_runtime_readback: false,
          marks_stage16_closed: false,
        },
        ready_to_close: false,
        stage16_closed_by_receipt: false,
        missing_readbacks: ["workstation_sleep_continuity_validated"],
        current_readback: {
          ready_count: 4,
          required_count: 5,
          missing_readbacks: ["workstation_sleep_continuity_validated"],
        },
        completion_review: {
          ready_to_close: false,
          blockers: ["workstation_sleep_continuity_validated"],
        },
        stage_closure_decision: {
          status: "empty",
          stage16_closed_by_receipt: false,
        },
        steps: [
          {
            id: "capture_pre_sleep_evidence",
            title: "Capture pre-sleep evidence",
            command: "scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PreSleep -CommitEvidence",
            latest_evidence_path:
              "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
            operator_action_required: true,
            operator_confirmation_required: false,
            writes_evidence_when_run: true,
            writes_receipts_when_run: false,
          },
          {
            id: "capture_post_resume_evidence",
            command:
              'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json" -OperatorConfirmedSleepResume',
            pre_sleep_evidence_required: true,
            pre_sleep_evidence_available: true,
            post_resume_evidence_required: false,
            post_resume_evidence_available: false,
            operator_action_required: true,
            operator_confirmation_required: true,
            writes_evidence_when_run: true,
            writes_receipts_when_run: false,
          },
          {
            id: "commit_sleep_continuity_readback",
            command:
              'scripts/federation-stage16-sleep-continuity-runtime-proof.ps1 -Mode Status -CommitReceipts -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json" -PostResumeEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\post_resume_test.json"',
            pre_sleep_evidence_required: true,
            pre_sleep_evidence_available: true,
            post_resume_evidence_required: true,
            post_resume_evidence_available: true,
            operator_action_required: false,
            operator_confirmation_required: false,
            writes_evidence_when_run: false,
            writes_receipts_when_run: true,
          },
          {
            id: "record_operator_stage_closure_decision",
            method: "POST",
            route: "/federation/stage-closure-decision",
            required_scope: "federation.stage16.closure.write",
            operator_action_required: true,
            operator_confirmation_required: true,
            writes_evidence_when_run: false,
            writes_receipts_when_run: true,
          },
        ],
        writes_evidence: false,
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
        marks_stage16_closed: false,
        next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
      });
    }

    if (parsed.pathname === "/federation/sleep-continuity-action") {
      return jsonResponse({
        ok: true,
        kind: "francis.stage16.federation.sleep_continuity_action",
        stage: "Stage 16 / Federation",
        status: "blocked_on_prior_live_readbacks",
        action_projection_only: true,
        selected_step_id: "",
        selected_action: {},
        primary_command: "",
        primary_route: "",
        method: "",
        required_scope: "",
        evidence_path: "",
        blockers: ["live_pairing_flow_observed", "workstation_sleep_continuity_validated"],
        prior_live_readback_blockers: ["live_pairing_flow_observed"],
        pre_sleep_evidence_ready: false,
        post_resume_evidence_ready: true,
        sleep_continuity_ready: false,
        ready_to_close: false,
        stage16_closed_by_receipt: false,
        operator_action_required: false,
        operator_confirmation_required: false,
        writes_evidence_when_run: false,
        writes_receipts_when_run: false,
        mutation_available_from_ui: false,
        writes_evidence: false,
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
        marks_stage16_closed: false,
        routes: {
          sleep_continuity_action: "/federation/sleep-continuity-action",
          sleep_continuity_runbook: "/federation/sleep-continuity-runbook",
          stage_closure_decision: "/federation/stage-closure-decision",
          ignored_number: 123,
        },
        governance: {
          read_only: true,
          action_projection_only: true,
          prior_live_readback_blockers_take_precedence: true,
          does_not_run_selected_command: true,
          does_not_post_selected_route: true,
        },
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
    const runbook = await client.getSleepContinuityRunbook({ timeoutMs: 50 });
    const action = await client.getSleepContinuityAction({ timeoutMs: 50 });
    const closure = await client.getStageClosureDecisions({ limit: 5, timeoutMs: 50 });
    const presentation = await client.getSleepContinuityPresentation({ timeoutMs: 50 });

    assert.deepEqual(requests, [
      { path: "/federation/status", method: "GET", limit: null },
      { path: "/federation/live-runtime-readbacks", method: "GET", limit: "5" },
      { path: "/federation/completion-review", method: "GET", limit: null },
      { path: "/federation/sleep-continuity-runbook", method: "GET", limit: null },
      { path: "/federation/sleep-continuity-action", method: "GET", limit: null },
      { path: "/federation/stage-closure-decisions", method: "GET", limit: "5" },
      { path: "/federation/sleep-continuity-action", method: "GET", limit: null },
    ]);
    assert.equal(status.stage16_status, "stage16_contracts_ready_completion_blocked");
    assert.equal(status.stage16_completion_review_ready, false);
    assert.equal(status.live_runtime_readback_ready, false);
    assert.deepEqual(status.completion_review_blockers, [
      "live_pairing_flow_observed",
      "workstation_sleep_continuity_validated",
    ]);
    assert.equal(status.sleep_continuity_status, "blocked_on_prior_live_readbacks");
    assert.equal(status.sleep_continuity_ready, false);
    assert.equal(status.pre_sleep_evidence_ready, false);
    assert.equal(status.post_resume_evidence_ready, false);
    assert.equal(status.latest_pre_sleep_evidence?.present, false);
    assert.equal(status.latest_post_resume_evidence?.present, false);
    assert.equal(status.sleep_continuity_next_step, "stage16_live_federation_runtime_readback");
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

    assert.equal(runbook.status, "ready_for_operator_sleep_resume");
    assert.equal(runbook.runbook_only, true);
    assert.equal(runbook.prerequisite_readbacks_ready, true);
    assert.equal(runbook.sleep_continuity_readback_id, "workstation_sleep_continuity_validated");
    assert.equal(runbook.sleep_continuity_ready, false);
    assert.equal(runbook.pre_sleep_evidence_ready, true);
    assert.equal(runbook.pre_sleep_evidence?.continuity_record_id, "stage16-sleep-continuity-test");
    assert.equal(runbook.post_resume_evidence_ready, true);
    assert.equal(runbook.post_resume_evidence?.linked_to_latest_pre_sleep, true);
    assert.equal(runbook.ready_to_close, false);
    assert.equal(runbook.stage16_closed_by_receipt, false);
    assert.deepEqual(runbook.missing_readbacks, ["workstation_sleep_continuity_validated"]);
    assert.deepEqual(
      runbook.steps.map((step) => step.id),
      [
        "capture_pre_sleep_evidence",
        "capture_post_resume_evidence",
        "commit_sleep_continuity_readback",
        "record_operator_stage_closure_decision",
      ],
    );
    assert.equal(runbook.steps[1]?.operator_confirmation_required, true);
    assert.equal(runbook.steps[1]?.pre_sleep_evidence_available, true);
    assert.equal(runbook.steps[2]?.writes_receipts_when_run, true);
    assert.equal(runbook.steps[2]?.pre_sleep_evidence_required, true);
    assert.equal(runbook.steps[2]?.post_resume_evidence_available, true);
    assert.equal(runbook.steps[3]?.route, "/federation/stage-closure-decision");
    assert.equal(runbook.writes_evidence, false);
    assert.equal(runbook.writes_receipts, false);
    assert.equal(runbook.runs_shell, false);
    assert.equal(runbook.grants_execution_authority, false);
    assert.equal(runbook.marks_stage16_closed, false);
    assert.equal(runbook.next_smallest_truthful_gap, "stage16_sleep_continuity_runtime_readback");

    assert.equal(action.kind, "francis.stage16.federation.sleep_continuity_action");
    assert.equal(action.status, "blocked_on_prior_live_readbacks");
    assert.equal(action.action_projection_only, true);
    assert.equal(action.selected_step_id, undefined);
    assert.equal(action.selected_action, undefined);
    assert.deepEqual(action.blockers, ["live_pairing_flow_observed", "workstation_sleep_continuity_validated"]);
    assert.deepEqual(action.prior_live_readback_blockers, ["live_pairing_flow_observed"]);
    assert.equal(action.post_resume_evidence_ready, true);
    assert.equal(action.operator_confirmation_required, false);
    assert.equal(action.writes_evidence_when_run, false);
    assert.equal(action.writes_receipts_when_run, false);
    assert.equal(action.mutation_available_from_ui, false);
    assert.equal(action.runs_shell, false);
    assert.equal(action.grants_mutation_authority, false);
    assert.equal(action.governance?.prior_live_readback_blockers_take_precedence, true);
    assert.equal(action.governance?.does_not_run_selected_command, true);
    assert.equal(action.next_smallest_truthful_gap, "stage16_live_federation_runtime_readback");
    assert.equal(action.routes.sleep_continuity_action, "/federation/sleep-continuity-action");
    assert.equal(action.routes.sleep_continuity_runbook, "/federation/sleep-continuity-runbook");
    assert.equal(action.routes.stage_closure_decision, "/federation/stage-closure-decision");
    assert.equal(action.routes.ignored_number, undefined);

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

    assert.equal(presentation.state, "blocked_on_prior_live_readbacks");
    assert.deepEqual(presentation.blockers, ["live_pairing_flow_observed", "workstation_sleep_continuity_validated"]);
    assert.equal(presentation.selected_step_id, undefined);
    assert.equal(presentation.post_resume_evidence_ready, true);
    assert.equal(presentation.writes_evidence_when_run, false);
    assert.equal(presentation.writes_receipts_when_run, false);
    assert.equal(presentation.mutation_available_from_ui, false);
  } finally {
    restoreFetch();
  }
});

test("federation sleep-continuity action parser preserves selected read-only step", () => {
  const action = parseFederationSleepContinuityAction({
    ok: true,
    kind: "francis.stage16.federation.sleep_continuity_action",
    stage: "Stage 16 / Federation",
    status: "capture_post_resume_evidence",
    action_projection_only: true,
    selected_step_id: "capture_post_resume_evidence",
    selected_action: {
      id: "capture_post_resume_evidence",
      command:
        'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
      pre_sleep_evidence_required: true,
      pre_sleep_evidence_available: true,
      post_resume_evidence_required: false,
      post_resume_evidence_available: false,
      operator_action_required: true,
      operator_confirmation_required: true,
      writes_evidence_when_run: true,
      writes_receipts_when_run: false,
    },
    primary_command:
      'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
    blockers: ["workstation_sleep_continuity_validated"],
    prior_live_readback_blockers: [],
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: false,
    sleep_continuity_ready: false,
    ready_to_close: false,
    stage16_closed_by_receipt: false,
    operator_action_required: true,
    operator_confirmation_required: true,
    writes_evidence_when_run: true,
    writes_receipts_when_run: false,
    mutation_available_from_ui: false,
    writes_evidence: false,
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
    marks_stage16_closed: false,
    routes: {
      sleep_continuity_action: "/federation/sleep-continuity-action",
      sleep_continuity_runbook: "/federation/sleep-continuity-runbook",
      stage_closure_decisions: "/federation/stage-closure-decisions",
      malformed: false,
    },
    governance: {
      read_only: true,
      action_projection_only: true,
      does_not_run_selected_command: true,
      does_not_post_selected_route: true,
    },
    next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
  });

  assert.equal(action.status, "capture_post_resume_evidence");
  assert.equal(action.selected_step_id, "capture_post_resume_evidence");
  assert.equal(action.selected_action?.id, "capture_post_resume_evidence");
  assert.equal(action.selected_action?.operator_confirmation_required, true);
  assert.equal(action.primary_command?.includes("-OperatorConfirmedSleepResume"), true);
  assert.deepEqual(action.prior_live_readback_blockers, []);
  assert.equal(action.mutation_available_from_ui, false);
  assert.equal(action.writes_evidence, false);
  assert.equal(action.runs_shell, false);
  assert.equal(action.grants_execution_authority, false);
  assert.equal(action.routes.sleep_continuity_action, "/federation/sleep-continuity-action");
  assert.equal(action.routes.sleep_continuity_runbook, "/federation/sleep-continuity-runbook");
  assert.equal(action.routes.stage_closure_decisions, "/federation/stage-closure-decisions");
  assert.equal(action.routes.malformed, undefined);
  assert.equal(action.governance?.does_not_post_selected_route, true);

  const presentation = presentFederationSleepContinuityAction(action);
  assert.equal(presentation.state, "capture_post_resume_evidence");
  assert.equal(presentation.status_label, "Capture post-resume evidence");
  assert.equal(presentation.selected_step_id, "capture_post_resume_evidence");
  assert.equal(presentation.primary_command?.includes("-OperatorConfirmedSleepResume"), true);
  assert.deepEqual(presentation.blockers, ["workstation_sleep_continuity_validated"]);
  assert.equal(presentation.pre_sleep_evidence_ready, true);
  assert.equal(presentation.post_resume_evidence_ready, false);
  assert.equal(presentation.operator_action_required, true);
  assert.equal(presentation.operator_confirmation_required, true);
  assert.equal(presentation.writes_evidence_when_run, true);
  assert.equal(presentation.writes_receipts_when_run, false);
  assert.equal(presentation.mutation_available_from_ui, false);
  assert.equal(presentation.next_smallest_truthful_gap, "stage16_sleep_continuity_runtime_readback");
});

test("federation Stage 16 parsers preserve ready receipt-backed posture", () => {
  const status = parseFederationStage16Status({
    ok: true,
    stage16_status: "stage16_completion_review_ready",
    stage16_completion_review_ready: true,
    live_runtime_readback_ready: true,
    completion_review_blockers: [],
    sleep_continuity_status: "validated",
    sleep_continuity_ready: true,
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: true,
    latest_pre_sleep_evidence: {
      present: true,
      evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
    },
    latest_post_resume_evidence: {
      present: true,
      evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\post_resume_test.json",
    },
    sleep_continuity_next_step: "record_stage16_operator_stage_closure_decision",
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
  const runbook = parseFederationSleepContinuityRunbook({
    ok: true,
    status: "ready_for_operator_sleep_resume",
    runbook_only: true,
    prerequisite_readback_ids: [
      "live_pairing_flow_observed",
      "live_selective_sync_observed",
      "live_remote_approval_roundtrip_observed",
      "live_revocation_roundtrip_observed",
    ],
    prerequisite_readbacks_ready: true,
    sleep_continuity_readback_id: "workstation_sleep_continuity_validated",
    sleep_continuity_ready: false,
    pre_sleep_evidence_ready: true,
    pre_sleep_evidence: {
      present: true,
      evidence_path: "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
      continuity_record_id: "stage16-sleep-continuity-test",
      metadata_only: true,
    },
    post_resume_evidence_ready: true,
    post_resume_evidence: {
      present: true,
      evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\post_resume_test.json",
      linked_to_latest_pre_sleep: true,
    },
    ready_to_close: false,
    stage16_closed_by_receipt: false,
    missing_readbacks: ["workstation_sleep_continuity_validated"],
    current_readback: {
      ready_count: 4,
      required_count: 5,
    },
    completion_review: {
      ready_to_close: false,
      stage16_completion_review_ready: false,
    },
    stage_closure_decision: {
      status: "empty",
    },
    steps: [
      {
        id: "capture_pre_sleep_evidence",
        command: "scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PreSleep -CommitEvidence",
        latest_evidence_path:
          "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
        operator_action_required: true,
        operator_confirmation_required: false,
        writes_evidence_when_run: true,
        writes_receipts_when_run: false,
      },
      {
        id: "record_operator_stage_closure_decision",
        method: "POST",
        route: "/federation/stage-closure-decision",
        required_scope: "federation.stage16.closure.write",
        pre_sleep_evidence_required: false,
        pre_sleep_evidence_available: false,
        post_resume_evidence_required: false,
        post_resume_evidence_available: false,
        payload_contract: {
          decision: "close_stage16",
        },
        operator_action_required: true,
        operator_confirmation_required: true,
        writes_evidence_when_run: false,
        writes_receipts_when_run: true,
      },
    ],
    writes_evidence: false,
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
    marks_stage16_closed: false,
    next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
  });

  assert.equal(status.stage16_completion_review_ready, true);
  assert.equal(status.live_runtime_readback_ready, true);
  assert.deepEqual(status.completion_review_blockers, []);
  assert.equal(status.sleep_continuity_status, "validated");
  assert.equal(status.sleep_continuity_ready, true);
  assert.equal(status.pre_sleep_evidence_ready, true);
  assert.equal(status.post_resume_evidence_ready, true);
  assert.equal(
    status.latest_pre_sleep_evidence?.evidence_path,
    "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
  );
  assert.equal(
    status.latest_post_resume_evidence?.evidence_path,
    "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\post_resume_test.json",
  );
  assert.equal(status.sleep_continuity_next_step, "record_stage16_operator_stage_closure_decision");
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

  assert.equal(runbook.status, "ready_for_operator_sleep_resume");
  assert.equal(runbook.runbook_only, true);
  assert.equal(runbook.prerequisite_readbacks_ready, true);
  assert.equal(runbook.sleep_continuity_ready, false);
  assert.equal(runbook.pre_sleep_evidence_ready, true);
  assert.equal(runbook.pre_sleep_evidence?.continuity_record_id, "stage16-sleep-continuity-test");
  assert.equal(runbook.post_resume_evidence_ready, true);
  assert.equal(runbook.post_resume_evidence?.linked_to_latest_pre_sleep, true);
  assert.deepEqual(runbook.missing_readbacks, ["workstation_sleep_continuity_validated"]);
  assert.equal(runbook.current_readback?.ready_count, 4);
  assert.equal(runbook.completion_review?.ready_to_close, false);
  assert.equal(runbook.stage_closure_decision?.status, "empty");
  assert.equal(runbook.steps[0]?.id, "capture_pre_sleep_evidence");
  assert.equal(
    runbook.steps[0]?.latest_evidence_path,
    "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
  );
  assert.equal(runbook.steps[1]?.route, "/federation/stage-closure-decision");
  assert.equal(runbook.steps[1]?.payload_contract?.decision, "close_stage16");
  assert.equal(runbook.writes_evidence, false);
  assert.equal(runbook.writes_receipts, false);
  assert.equal(runbook.runs_git, false);
  assert.equal(runbook.grants_mutation_authority, false);
  assert.equal(runbook.marks_stage16_closed, false);
  assert.equal(runbook.next_smallest_truthful_gap, "stage16_sleep_continuity_runtime_readback");
});

test("federation sleep-continuity presentation gates post-resume capture on operator confirmation", () => {
  const status = parseFederationStage16Status({
    ok: true,
    stage16_status: "stage16_contracts_ready_completion_blocked",
    stage16_completion_review_ready: false,
    live_runtime_readback_ready: true,
    completion_review_blockers: ["workstation_sleep_continuity_validated"],
    sleep_continuity_status: "pre_sleep_evidence_ready",
    sleep_continuity_ready: false,
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: false,
    latest_pre_sleep_evidence: {
      present: true,
      evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
    },
    latest_post_resume_evidence: {
      present: false,
    },
    sleep_continuity_next_step: "run_post_resume_evidence_with_operator_confirmation",
    ready_count: 6,
    required_count: 6,
    next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
  });
  const runbook = parseFederationSleepContinuityRunbook({
    ok: true,
    status: "ready_for_operator_sleep_resume",
    runbook_only: true,
    prerequisite_readbacks_ready: true,
    sleep_continuity_readback_id: "workstation_sleep_continuity_validated",
    sleep_continuity_ready: false,
    pre_sleep_evidence_ready: true,
    pre_sleep_evidence: {
      present: true,
      evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
    },
    post_resume_evidence_ready: false,
    post_resume_evidence: {
      present: false,
    },
    ready_to_close: false,
    stage16_closed_by_receipt: false,
    missing_readbacks: ["workstation_sleep_continuity_validated"],
    steps: [
      {
        id: "capture_post_resume_evidence",
        command:
          'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
        pre_sleep_evidence_required: true,
        pre_sleep_evidence_available: true,
        post_resume_evidence_required: false,
        post_resume_evidence_available: false,
        operator_action_required: true,
        operator_confirmation_required: true,
        writes_evidence_when_run: true,
        writes_receipts_when_run: false,
      },
    ],
    writes_evidence: false,
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
    marks_stage16_closed: false,
    next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
  });

  const presentation = presentFederationSleepContinuity(status, runbook);

  assert.equal(presentation.state, "capture_post_resume_evidence");
  assert.equal(presentation.selected_step_id, "capture_post_resume_evidence");
  assert.equal(presentation.primary_command?.includes("-OperatorConfirmedSleepResume"), true);
  assert.deepEqual(presentation.blockers, ["workstation_sleep_continuity_validated"]);
  assert.equal(presentation.pre_sleep_evidence_ready, true);
  assert.equal(presentation.post_resume_evidence_ready, false);
  assert.equal(presentation.sleep_continuity_ready, false);
  assert.equal(presentation.ready_to_close, false);
  assert.equal(presentation.operator_action_required, true);
  assert.equal(presentation.operator_confirmation_required, true);
  assert.equal(presentation.writes_evidence_when_run, true);
  assert.equal(presentation.writes_receipts_when_run, false);
  assert.equal(presentation.mutation_available_from_ui, false);
  assert.equal(presentation.next_smallest_truthful_gap, "stage16_sleep_continuity_runtime_readback");
});

test("federation sleep-continuity presentation advances to runtime proof after post-resume evidence", () => {
  const status = parseFederationStage16Status({
    ok: true,
    stage16_status: "stage16_contracts_ready_completion_blocked",
    stage16_completion_review_ready: false,
    live_runtime_readback_ready: true,
    completion_review_blockers: ["workstation_sleep_continuity_validated"],
    sleep_continuity_status: "post_resume_evidence_ready",
    sleep_continuity_ready: false,
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: true,
    sleep_continuity_next_step: "run_sleep_continuity_runtime_proof",
    ready_count: 6,
    required_count: 6,
    next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
  });
  const runbook = parseFederationSleepContinuityRunbook({
    ok: true,
    status: "ready_for_runtime_proof",
    runbook_only: true,
    prerequisite_readbacks_ready: true,
    sleep_continuity_readback_id: "workstation_sleep_continuity_validated",
    sleep_continuity_ready: false,
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: true,
    ready_to_close: false,
    stage16_closed_by_receipt: false,
    missing_readbacks: ["workstation_sleep_continuity_validated"],
    steps: [
      {
        id: "commit_sleep_continuity_readback",
        command:
          'scripts/federation-stage16-sleep-continuity-runtime-proof.ps1 -Mode Status -CommitReceipts -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -PostResumeEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\post_resume_stage16.json"',
        pre_sleep_evidence_required: true,
        pre_sleep_evidence_available: true,
        post_resume_evidence_required: true,
        post_resume_evidence_available: true,
        operator_action_required: true,
        operator_confirmation_required: false,
        writes_evidence_when_run: false,
        writes_receipts_when_run: true,
      },
    ],
    writes_evidence: false,
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
    marks_stage16_closed: false,
    next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
  });

  const presentation = presentFederationSleepContinuity(status, runbook);

  assert.equal(presentation.state, "run_sleep_continuity_runtime_proof");
  assert.equal(presentation.selected_step_id, "commit_sleep_continuity_readback");
  assert.equal(presentation.primary_command?.includes("federation-stage16-sleep-continuity-runtime-proof.ps1"), true);
  assert.equal(presentation.operator_confirmation_required, false);
  assert.equal(presentation.writes_evidence_when_run, false);
  assert.equal(presentation.writes_receipts_when_run, true);
  assert.equal(presentation.mutation_available_from_ui, false);
});

test("federation sleep-continuity presentation separates closure action from closed receipt", () => {
  const status = parseFederationStage16Status({
    ok: true,
    stage16_status: "stage16_completion_review_ready",
    stage16_completion_review_ready: true,
    live_runtime_readback_ready: true,
    completion_review_blockers: [],
    sleep_continuity_status: "validated",
    sleep_continuity_ready: true,
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: true,
    sleep_continuity_next_step: "record_stage16_operator_stage_closure_decision",
    ready_count: 6,
    required_count: 6,
    next_smallest_truthful_gap: "stage16_operator_stage_closure_decision",
  });
  const runbook = parseFederationSleepContinuityRunbook({
    ok: true,
    status: "ready_to_close",
    runbook_only: true,
    prerequisite_readbacks_ready: true,
    sleep_continuity_readback_id: "workstation_sleep_continuity_validated",
    sleep_continuity_ready: true,
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: true,
    ready_to_close: true,
    stage16_closed_by_receipt: false,
    missing_readbacks: [],
    steps: [
      {
        id: "record_operator_stage_closure_decision",
        method: "POST",
        route: "/federation/stage-closure-decision",
        required_scope: "federation.stage16.closure.write",
        operator_action_required: true,
        operator_confirmation_required: true,
        writes_evidence_when_run: false,
        writes_receipts_when_run: true,
      },
    ],
    writes_evidence: false,
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
    marks_stage16_closed: false,
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
    next_smallest_truthful_gap: "stage16_ledger_closure",
  });

  const closureAction = presentFederationSleepContinuity(status, runbook);
  const closed = presentFederationSleepContinuity(status, runbook, closure);

  assert.equal(closureAction.state, "record_stage16_closure_decision");
  assert.equal(closureAction.primary_route, "/federation/stage-closure-decision");
  assert.equal(closureAction.required_scope, "federation.stage16.closure.write");
  assert.equal(closureAction.operator_confirmation_required, true);
  assert.equal(closureAction.writes_receipts_when_run, true);
  assert.equal(closureAction.mutation_available_from_ui, false);

  assert.equal(closed.state, "stage16_closed");
  assert.equal(closed.stage16_closed_by_receipt, true);
  assert.equal(closed.selected_step_id, undefined);
  assert.equal(closed.writes_receipts_when_run, false);
  assert.equal(closed.mutation_available_from_ui, false);
});
