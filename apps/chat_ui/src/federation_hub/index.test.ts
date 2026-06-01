import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR,
  FederationClient,
  federationSleepContinuityVisibleOperatorCommands,
  federationSleepResumeConfirmationActorReadinessVisibleCommands,
  federationSleepResumeConfirmationVisibleCommands,
  isFederationSleepContinuityOperatorCommandBlockedByPendingConfirmation,
  isFederationSleepResumeConfirmationActorReadinessCurrent,
  parseFederationCompletionReview,
  parseFederationLiveRuntimeReadbacks,
  parseFederationSleepContinuityAction,
  parseFederationSleepContinuityRunbook,
  parseFederationSleepResumeConfirmationActorReadiness,
  parseFederationSleepResumeConfirmations,
  parseFederationStage16Status,
  parseFederationStage16ClosureDecisions,
  presentFederationSleepContinuity,
  presentFederationSleepContinuityAction,
  shouldAutoCheckFederationSleepResumeConfirmationActorReadiness,
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
      actor: parsed.searchParams.get("actor"),
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
        sleep_continuity_selected_action_id: "",
        sleep_continuity_action_current_ready_to_run: false,
        sleep_continuity_operator_confirmation_pending: false,
        sleep_continuity_post_confirmation_ready_to_capture: false,
        sleep_continuity_confirmation_blocker: "",
        sleep_continuity_blocked_reason: "prior_live_readback_missing",
        sleep_continuity_sleep_resume_confirmation_is_current_blocker: false,
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
        status: "post_resume_evidence_ready",
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
        selected_action_summary: {
          selected_action_id: "commit_sleep_continuity_readback",
          current_ready_to_run: true,
          operator_confirmation_pending: false,
          post_confirmation_ready_to_capture: false,
          sleep_resume_confirmation_is_current_blocker: false,
          confirmation_blocker: "",
          blocked_reason: "",
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

    if (parsed.pathname === "/federation/sleep-resume-confirmations") {
      return jsonResponse({
        ok: true,
        kind: "francis.stage16.federation.sleep_resume_operator_confirmation_receipts",
        stage: "Stage 16 / Federation",
        status: "sleep_resume_confirmation_readback_ready",
        count: 1,
        total: 1,
        latest_receipt_id: "fedsleepconfirm_ui_test",
        latest_actor: "test.federation.sleep",
        latest_decision: "operator_confirmed_sleep_resume",
        latest_pre_sleep_evidence_path:
          "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
        latest_recorded_ts: 1_800_030_360,
        receipt_readback_ready: true,
        current_pre_sleep_evidence_present: true,
        current_pre_sleep_evidence_path:
          "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
        current_pre_sleep_recorded_ts: 1_800_030_000,
        confirmation_receipt_requested_actor: parsed.searchParams.get("actor") ?? "",
        confirmation_receipt_requested_actor_ready: parsed.searchParams.get("actor") === "test.federation.sleep",
        latest_receipt_is_operator_confirmed: true,
        latest_receipt_matches_current_pre_sleep: true,
        latest_receipt_usable_for_receipt_backed_sequence: true,
        receipt_backed_sequence_ready: true,
        receipt_backed_sequence_blockers: [],
        receipt_backed_sequence_command:
          'scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -CommitEvidence -CommitReceipts -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json" -OperatorConfirmedSleepResume -RequireConfirmationReceipt -ConfirmationReceiptId fedsleepconfirm_ui_test',
        receipt_backed_sequence_copyable_command:
          'Set-Location -LiteralPath \'D:\\Francis\'; scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -CommitEvidence -CommitReceipts -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json" -OperatorConfirmedSleepResume -RequireConfirmationReceipt -ConfirmationReceiptId fedsleepconfirm_ui_test',
        confirmation_receipt_command_ready: false,
        confirmation_receipt_actor_placeholder: "",
        confirmation_receipt_command: "",
        confirmation_receipt_copyable_command: "",
        confirmation_receipt_command_requires_scope: "federation.stage16.sleep_resume.confirmation.write",
        confirmation_receipt_command_records_receipt: false,
        confirmation_receipt_command_writes_evidence: false,
        confirmation_receipt_command_marks_stage16_closed: false,
        confirmation_receipt_command_projection_only: true,
        receipt_backed_sequence_requires_confirmation_receipt: true,
        receipt_backed_sequence_writes_evidence_when_run: true,
        receipt_backed_sequence_writes_receipts_when_run: true,
        reads_receipts: true,
        writes_receipts: false,
        writes_evidence: false,
        writes_runtime_readback: false,
        marks_stage16_closed: false,
        grants_execution_authority: false,
        grants_mutation_authority: false,
        latest_receipt: {
          receipt_id: "fedsleepconfirm_ui_test",
          actor: "test.federation.sleep",
          decision: "operator_confirmed_sleep_resume",
          operator_confirmed_sleep_resume: true,
          pre_sleep_evidence_path:
            "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
          pre_sleep_recorded_ts: 1_800_030_000,
          continuity_record_id: "stage16-sleep-continuity-test",
          trace_id: "trace-stage16-sleep-continuity-test",
          recorded_ts: 1_800_030_360,
        },
        items: [
          {
            receipt_id: "fedsleepconfirm_ui_test",
            actor: "test.federation.sleep",
            decision: "operator_confirmed_sleep_resume",
            operator_confirmed_sleep_resume: true,
            pre_sleep_evidence_path:
              "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
            pre_sleep_recorded_ts: 1_800_030_000,
            continuity_record_id: "stage16-sleep-continuity-test",
            trace_id: "trace-stage16-sleep-continuity-test",
            recorded_ts: 1_800_030_360,
          },
        ],
        routes: {
          sleep_resume_confirmations: "/federation/sleep-resume-confirmations",
          sleep_resume_confirmation: "/federation/sleep-resume-confirmation",
        },
        next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
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
    const confirmations = await client.getSleepResumeConfirmations({
      limit: 3,
      actor: "test.federation.sleep",
      timeoutMs: 50,
    });
    const presentation = await client.getSleepContinuityPresentation({ timeoutMs: 50 });

    assert.deepEqual(requests, [
      { path: "/federation/status", method: "GET", limit: null, actor: null },
      { path: "/federation/live-runtime-readbacks", method: "GET", limit: "5", actor: null },
      { path: "/federation/completion-review", method: "GET", limit: null, actor: null },
      { path: "/federation/sleep-continuity-runbook", method: "GET", limit: null, actor: null },
      { path: "/federation/sleep-continuity-action", method: "GET", limit: null, actor: null },
      { path: "/federation/stage-closure-decisions", method: "GET", limit: "5", actor: null },
      { path: "/federation/sleep-resume-confirmations", method: "GET", limit: "3", actor: "test.federation.sleep" },
      { path: "/federation/sleep-continuity-action", method: "GET", limit: null, actor: null },
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
    assert.equal(status.sleep_continuity_selected_action_id, undefined);
    assert.equal(status.sleep_continuity_action_current_ready_to_run, false);
    assert.equal(status.sleep_continuity_operator_confirmation_pending, false);
    assert.equal(status.sleep_continuity_post_confirmation_ready_to_capture, false);
    assert.equal(status.sleep_continuity_confirmation_blocker, undefined);
    assert.equal(status.sleep_continuity_blocked_reason, "prior_live_readback_missing");
    assert.equal(status.sleep_continuity_sleep_resume_confirmation_is_current_blocker, false);
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

    assert.equal(runbook.status, "post_resume_evidence_ready");
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
    assert.equal(runbook.selected_action_summary?.selected_action_id, "commit_sleep_continuity_readback");
    assert.equal(runbook.selected_action_summary?.current_ready_to_run, true);
    assert.equal(runbook.selected_action_summary?.operator_confirmation_pending, false);
    assert.equal(runbook.selected_action_summary?.post_confirmation_ready_to_capture, false);
    assert.equal(runbook.selected_action_summary?.confirmation_blocker, undefined);
    assert.equal(runbook.selected_action_summary?.blocked_reason, undefined);
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

    assert.equal(confirmations.status, "sleep_resume_confirmation_readback_ready");
    assert.equal(confirmations.count, 1);
    assert.equal(confirmations.latest_receipt_id, "fedsleepconfirm_ui_test");
    assert.equal(confirmations.latest_decision, "operator_confirmed_sleep_resume");
    assert.equal(confirmations.latest_pre_sleep_evidence_path, "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json");
    assert.equal(confirmations.receipt_readback_ready, true);
    assert.equal(confirmations.current_pre_sleep_evidence_present, true);
    assert.equal(confirmations.current_pre_sleep_evidence_path, "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json");
    assert.equal(confirmations.confirmation_receipt_requested_actor, "test.federation.sleep");
    assert.equal(confirmations.confirmation_receipt_requested_actor_ready, true);
    assert.equal(confirmations.latest_receipt_is_operator_confirmed, true);
    assert.equal(confirmations.latest_receipt_matches_current_pre_sleep, true);
    assert.equal(confirmations.latest_receipt_usable_for_receipt_backed_sequence, true);
    assert.equal(confirmations.receipt_backed_sequence_ready, true);
    assert.deepEqual(confirmations.receipt_backed_sequence_blockers, []);
    assert.equal(confirmations.receipt_backed_sequence_command?.includes("-RequireConfirmationReceipt"), true);
    assert.equal(confirmations.receipt_backed_sequence_command?.includes("fedsleepconfirm_ui_test"), true);
    assert.equal(confirmations.receipt_backed_sequence_copyable_command?.includes(confirmations.receipt_backed_sequence_command ?? ""), true);
    const visibleConfirmationCommands = federationSleepResumeConfirmationVisibleCommands(confirmations);
    assert.equal(visibleConfirmationCommands.confirmation_receipt_copyable_command, undefined);
    assert.equal(
      visibleConfirmationCommands.receipt_backed_sequence_copyable_command?.includes(
        confirmations.receipt_backed_sequence_command ?? "",
      ),
      true,
    );
    assert.equal(confirmations.confirmation_receipt_command_ready, false);
    assert.equal(confirmations.confirmation_receipt_actor_placeholder, undefined);
    assert.equal(confirmations.confirmation_receipt_command, undefined);
    assert.equal(confirmations.confirmation_receipt_copyable_command, undefined);
    assert.equal(
      confirmations.confirmation_receipt_command_requires_scope,
      "federation.stage16.sleep_resume.confirmation.write",
    );
    assert.equal(confirmations.confirmation_receipt_command_records_receipt, false);
    assert.equal(confirmations.confirmation_receipt_command_writes_evidence, false);
    assert.equal(confirmations.confirmation_receipt_command_marks_stage16_closed, false);
    assert.equal(confirmations.confirmation_receipt_command_projection_only, true);
    assert.equal(confirmations.receipt_backed_sequence_requires_confirmation_receipt, true);
    assert.equal(confirmations.receipt_backed_sequence_writes_evidence_when_run, true);
    assert.equal(confirmations.receipt_backed_sequence_writes_receipts_when_run, true);
    assert.equal(confirmations.writes_receipts, false);
    assert.equal(confirmations.writes_evidence, false);
    assert.equal(confirmations.writes_runtime_readback, false);
    assert.equal(confirmations.marks_stage16_closed, false);
    assert.equal(confirmations.latest_receipt?.operator_confirmed_sleep_resume, true);
    assert.equal(confirmations.latest_receipt?.continuity_record_id, "stage16-sleep-continuity-test");

    assert.equal(presentation.state, "blocked_on_prior_live_readbacks");
    assert.deepEqual(presentation.blockers, ["live_pairing_flow_observed", "workstation_sleep_continuity_validated"]);
    assert.deepEqual(presentation.prior_live_readback_blockers, ["live_pairing_flow_observed"]);
    assert.equal(presentation.selected_step_id, undefined);
    assert.equal(presentation.post_resume_evidence_ready, true);
    assert.equal(presentation.writes_evidence_when_run, false);
    assert.equal(presentation.writes_receipts_when_run, false);
    assert.equal(presentation.mutation_available_from_ui, false);
  } finally {
    restoreFetch();
  }
});

test("parseFederationSleepResumeConfirmations preserves missing-receipt remedy command", () => {
  const confirmations = parseFederationSleepResumeConfirmations({
    ok: true,
    kind: "francis.stage16.federation.sleep_resume_operator_confirmation_receipts",
    stage: "Stage 16 / Federation",
    status: "empty",
    count: 0,
    total: 0,
    receipt_readback_ready: false,
    current_pre_sleep_evidence_present: true,
    current_pre_sleep_evidence_path:
      "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
    current_pre_sleep_recorded_ts: 1_800_030_000,
    confirmation_receipt_requested_actor: "test.federation.sleep",
    confirmation_receipt_requested_actor_ready: true,
    latest_receipt_is_operator_confirmed: false,
    latest_receipt_matches_current_pre_sleep: false,
    latest_receipt_usable_for_receipt_backed_sequence: false,
    receipt_backed_sequence_ready: false,
    receipt_backed_sequence_blockers: ["sleep_resume_confirmation_receipt_missing"],
    receipt_backed_sequence_copyable_command:
      "Set-Location -LiteralPath 'D:\\Francis'; scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -RequireConfirmationReceipt -ConfirmationReceiptId stale_or_missing",
    receipt_backed_sequence_requires_confirmation_receipt: true,
    receipt_backed_sequence_writes_evidence_when_run: false,
    receipt_backed_sequence_writes_receipts_when_run: false,
    confirmation_receipt_command_ready: true,
    confirmation_receipt_actor: "",
    confirmation_receipt_actor_bound: false,
    confirmation_receipt_actor_placeholder: "<actor_with_federation.stage16.sleep_resume.confirmation.write>",
    confirmation_receipt_command:
      "$body = @{ actor = '<actor_with_federation.stage16.sleep_resume.confirmation.write>'; operator_confirmed_sleep_resume = $true; pre_sleep_evidence_path = 'D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json' } | ConvertTo-Json -Depth 6; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/federation/sleep-resume-confirmation' -ContentType 'application/json' -Body $body",
    confirmation_receipt_copyable_command:
      "Set-Location -LiteralPath 'D:\\Francis'; $body = @{ actor = '<actor_with_federation.stage16.sleep_resume.confirmation.write>'; operator_confirmed_sleep_resume = $true; pre_sleep_evidence_path = 'D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json' } | ConvertTo-Json -Depth 6; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/federation/sleep-resume-confirmation' -ContentType 'application/json' -Body $body",
    confirmation_receipt_command_requires_scope: "federation.stage16.sleep_resume.confirmation.write",
    confirmation_receipt_command_requires_actor_substitution: true,
    confirmation_receipt_command_actor_scope: "federation.stage16.sleep_resume.confirmation.write",
    confirmation_receipt_actor_readiness_route: "/federation/sleep-resume-confirmation/actor-readiness",
    confirmation_receipt_actor_readiness_query_param: "actor",
    confirmation_receipt_command_next_readback_route: "/federation/sleep-resume-confirmations",
    confirmation_receipt_command_receipt_id_readback_field: "latest_receipt_id",
    confirmation_receipt_command_next_operator_step: "refresh_sleep_resume_confirmations_for_current_receipt_id",
    confirmation_receipt_operator_steps: [
      {
        id: "replace_actor_placeholder",
        order: 1,
        status: "ready",
        command_field: "confirmation_receipt_copyable_command",
        required_scope: "federation.stage16.sleep_resume.confirmation.write",
        requires_actor_substitution: true,
        requires_current_receipt: false,
        writes_receipts_when_run: false,
        writes_evidence_when_run: false,
        marks_stage16_closed_when_run: false,
        operator_action_required: true,
        read_only_projection: true,
      },
      {
        id: "write_sleep_resume_confirmation_receipt",
        order: 2,
        status: "ready",
        method: "POST",
        route: "/federation/sleep-resume-confirmation",
        command_field: "confirmation_receipt_copyable_command",
        required_scope: "federation.stage16.sleep_resume.confirmation.write",
        requires_actor_substitution: true,
        requires_current_receipt: false,
        writes_receipts_when_run: true,
        writes_evidence_when_run: false,
        marks_stage16_closed_when_run: false,
        operator_action_required: true,
        read_only_projection: true,
      },
      {
        id: "refresh_sleep_resume_confirmation_readback",
        order: 3,
        status: "ready",
        method: "GET",
        route: "/federation/sleep-resume-confirmations",
        readback_field: "latest_receipt_id",
        requires_actor_substitution: false,
        requires_current_receipt: false,
        writes_receipts_when_run: false,
        writes_evidence_when_run: false,
        marks_stage16_closed_when_run: false,
        operator_action_required: true,
        read_only_projection: true,
      },
      {
        id: "run_receipt_backed_post_resume_sequence",
        order: 4,
        status: "blocked_until_current_confirmation_receipt",
        command_field: "receipt_backed_sequence_copyable_command",
        requires_actor_substitution: false,
        requires_current_receipt: true,
        required_readback_field: "latest_receipt_id",
        writes_receipts_when_run: false,
        writes_evidence_when_run: false,
        marks_stage16_closed_when_run: false,
        operator_action_required: false,
        read_only_projection: true,
      },
    ],
    confirmation_receipt_command_records_receipt: true,
    confirmation_receipt_command_writes_evidence: false,
    confirmation_receipt_command_marks_stage16_closed: false,
    confirmation_receipt_command_projection_only: true,
    reads_receipts: true,
    writes_receipts: false,
    writes_evidence: false,
    writes_runtime_readback: false,
    marks_stage16_closed: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    items: [],
    routes: { sleep_resume_confirmation: "/federation/sleep-resume-confirmation" },
    next_smallest_truthful_gap: "stage16_sleep_resume_confirmation_receipt",
  });

  assert.equal(confirmations.status, "empty");
  assert.deepEqual(confirmations.receipt_backed_sequence_blockers, ["sleep_resume_confirmation_receipt_missing"]);
  assert.equal(confirmations.receipt_backed_sequence_ready, false);
  assert.equal(confirmations.receipt_backed_sequence_copyable_command?.includes("stale_or_missing"), true);
  assert.equal(confirmations.confirmation_receipt_command_ready, true);
  assert.equal(confirmations.confirmation_receipt_requested_actor, "test.federation.sleep");
  assert.equal(confirmations.confirmation_receipt_requested_actor_ready, true);
  assert.equal(confirmations.confirmation_receipt_actor, undefined);
  assert.equal(confirmations.confirmation_receipt_actor_bound, false);
  assert.equal(
    confirmations.confirmation_receipt_actor_placeholder,
    "<actor_with_federation.stage16.sleep_resume.confirmation.write>",
  );
  assert.equal(confirmations.confirmation_receipt_command?.includes("Invoke-RestMethod -Method Post"), true);
  assert.equal(
    confirmations.confirmation_receipt_command?.includes("/federation/sleep-resume-confirmation"),
    true,
  );
  assert.equal(
    confirmations.confirmation_receipt_command?.includes("operator_confirmed_sleep_resume = $true"),
    true,
  );
  assert.equal(
    confirmations.confirmation_receipt_copyable_command?.includes(
      confirmations.confirmation_receipt_command ?? "",
    ),
    true,
  );
  const visibleCommands = federationSleepResumeConfirmationVisibleCommands(confirmations);
  assert.equal(
    visibleCommands.confirmation_receipt_copyable_command?.includes(
      confirmations.confirmation_receipt_command ?? "",
    ),
    true,
  );
  assert.equal(visibleCommands.receipt_backed_sequence_copyable_command, undefined);
  assert.equal(confirmations.confirmation_receipt_command_records_receipt, true);
  assert.equal(confirmations.confirmation_receipt_command_writes_evidence, false);
  assert.equal(confirmations.confirmation_receipt_command_marks_stage16_closed, false);
  assert.equal(confirmations.confirmation_receipt_command_projection_only, true);
  assert.equal(confirmations.confirmation_receipt_command_requires_actor_substitution, true);
  assert.equal(
    confirmations.confirmation_receipt_command_actor_scope,
    "federation.stage16.sleep_resume.confirmation.write",
  );
  assert.equal(
    confirmations.confirmation_receipt_actor_readiness_route,
    "/federation/sleep-resume-confirmation/actor-readiness",
  );
  assert.equal(confirmations.confirmation_receipt_actor_readiness_query_param, "actor");
  assert.equal(
    confirmations.confirmation_receipt_command_next_readback_route,
    "/federation/sleep-resume-confirmations",
  );
  assert.equal(confirmations.confirmation_receipt_command_receipt_id_readback_field, "latest_receipt_id");
  assert.deepEqual(
    confirmations.confirmation_receipt_operator_steps.map((step) => step.id),
    [
      "replace_actor_placeholder",
      "write_sleep_resume_confirmation_receipt",
      "refresh_sleep_resume_confirmation_readback",
      "run_receipt_backed_post_resume_sequence",
    ],
  );
  assert.equal(confirmations.confirmation_receipt_operator_steps[0]?.requires_actor_substitution, true);
  assert.equal(confirmations.confirmation_receipt_operator_steps[0]?.required_scope, "federation.stage16.sleep_resume.confirmation.write");
  assert.equal(confirmations.confirmation_receipt_operator_steps[1]?.route, "/federation/sleep-resume-confirmation");
  assert.equal(confirmations.confirmation_receipt_operator_steps[1]?.writes_receipts_when_run, true);
  assert.equal(confirmations.confirmation_receipt_operator_steps[2]?.readback_field, "latest_receipt_id");
  assert.equal(confirmations.confirmation_receipt_operator_steps[3]?.requires_current_receipt, true);
  assert.equal(confirmations.confirmation_receipt_operator_steps[3]?.writes_evidence_when_run, false);
  assert.equal(confirmations.confirmation_receipt_operator_steps[3]?.marks_stage16_closed_when_run, false);

  assert.equal(
    shouldAutoCheckFederationSleepResumeConfirmationActorReadiness({
      confirmations,
      actor: DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR,
      readiness: null,
    }),
    true,
  );
  const currentReadiness = parseFederationSleepResumeConfirmationActorReadiness({
    ok: true,
    actor: DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR,
    actor_present: true,
    confirmation_receipt_actor_ready: true,
    confirmation_receipt_command_ready: true,
  });
  assert.equal(
    shouldAutoCheckFederationSleepResumeConfirmationActorReadiness({
      confirmations,
      actor: DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR,
      readiness: currentReadiness,
    }),
    false,
  );
  assert.equal(
    shouldAutoCheckFederationSleepResumeConfirmationActorReadiness({
      confirmations,
      actor: "",
      readiness: null,
    }),
    false,
  );
  const unsafeConfirmations = parseFederationSleepResumeConfirmations({
    current_pre_sleep_evidence_present: true,
    confirmation_receipt_command_ready: true,
    confirmation_receipt_actor_bound: false,
    confirmation_receipt_actor_placeholder: "<actor>",
    confirmation_receipt_actor_readiness_route: "/federation/sleep-resume-confirmation/actor-readiness",
    confirmation_receipt_actor_readiness_query_param: "actor",
    confirmation_receipt_command_requires_actor_substitution: true,
    confirmation_receipt_command_writes_evidence: true,
    confirmation_receipt_command_marks_stage16_closed: false,
    confirmation_receipt_command_projection_only: true,
  });
  assert.equal(
    shouldAutoCheckFederationSleepResumeConfirmationActorReadiness({
      confirmations: unsafeConfirmations,
      actor: DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR,
      readiness: null,
    }),
    false,
  );
});

test("parseFederationSleepResumeConfirmationActorReadiness preserves actor-bound command guards", () => {
  const readiness = parseFederationSleepResumeConfirmationActorReadiness({
    ok: true,
    kind: "francis.stage16.federation.sleep_resume_operator_confirmation_actor_readiness",
    stage: "Stage 16 / Federation",
    status: "actor_ready_for_sleep_resume_confirmation",
    actor: "test.federation.sleep",
    actor_present: true,
    actor_placeholder_rejected: false,
    required_scope: "federation.stage16.sleep_resume.confirmation.write",
    target_method: "POST",
    target_route: "/federation/sleep-resume-confirmation",
    readiness_route: "/federation/sleep-resume-confirmation/actor-readiness",
    current_pre_sleep_evidence_present: true,
    current_pre_sleep_evidence_path:
      "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_test.json",
    permission_allowed: true,
    permission_reason: "actor_has_required_scopes",
    confirmation_receipt_actor_ready: true,
    safe_to_use_in_confirmation_command: true,
    next_step: "write_sleep_resume_confirmation_receipt_after_real_sleep_resume",
    confirmation_receipt_command_ready: true,
    confirmation_receipt_actor: "test.federation.sleep",
    confirmation_receipt_actor_bound: true,
    confirmation_receipt_actor_placeholder: "",
    confirmation_receipt_command:
      "$body = @{ actor = 'test.federation.sleep'; operator_confirmed_sleep_resume = $true } | ConvertTo-Json -Depth 6",
    confirmation_receipt_copyable_command:
      "Set-Location -LiteralPath 'D:\\Francis'; $body = @{ actor = 'test.federation.sleep'; operator_confirmed_sleep_resume = $true } | ConvertTo-Json -Depth 6",
    confirmation_receipt_command_requires_scope: "federation.stage16.sleep_resume.confirmation.write",
    confirmation_receipt_command_requires_actor_substitution: false,
    confirmation_receipt_command_actor_scope: "federation.stage16.sleep_resume.confirmation.write",
    confirmation_receipt_actor_readiness_route: "/federation/sleep-resume-confirmation/actor-readiness",
    confirmation_receipt_actor_readiness_query_param: "actor",
    confirmation_receipt_command_next_readback_route: "/federation/sleep-resume-confirmations",
    confirmation_receipt_command_receipt_id_readback_field: "latest_receipt_id",
    confirmation_receipt_command_next_operator_step: "refresh_sleep_resume_confirmations_for_current_receipt_id",
    confirmation_receipt_command_records_receipt: true,
    confirmation_receipt_command_writes_evidence: false,
    confirmation_receipt_command_marks_stage16_closed: false,
    confirmation_receipt_command_projection_only: true,
    scope_remediation_required: false,
    scope_remediation_command_ready: false,
    scope_remediation_command_visible: false,
    scope_remediation_command: "",
    scope_remediation_projection_only: true,
    scope_remediation_writes_receipts: false,
    scope_remediation_writes_evidence: false,
    scope_remediation_marks_stage16_closed: false,
    scope_remediation_grants_authority: false,
    scope_remediation_would_mutate_process_environment_if_run: false,
    reads_permission_gate: true,
    writes_receipt: false,
    writes_evidence: false,
    writes_runtime_readback: false,
    marks_stage16_closed: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    next_smallest_truthful_gap: "stage16_sleep_resume_confirmation_receipt",
  });

  assert.equal(readiness.status, "actor_ready_for_sleep_resume_confirmation");
  assert.equal(readiness.actor, "test.federation.sleep");
  assert.equal(readiness.confirmation_receipt_actor_ready, true);
  assert.equal(readiness.next_step, "write_sleep_resume_confirmation_receipt_after_real_sleep_resume");
  assert.equal(readiness.safe_to_use_in_confirmation_command, true);
  assert.equal(readiness.confirmation_receipt_actor_bound, true);
  assert.equal(readiness.confirmation_receipt_command_requires_actor_substitution, false);
  assert.equal(readiness.confirmation_receipt_command?.includes("actor = 'test.federation.sleep'"), true);
  assert.equal(readiness.scope_remediation_required, false);
  assert.equal(readiness.scope_remediation_command, undefined);
  assert.equal(readiness.writes_receipt, false);
  assert.equal(readiness.writes_evidence, false);
  assert.equal(readiness.marks_stage16_closed, false);

  const visibleCommands = federationSleepResumeConfirmationActorReadinessVisibleCommands(readiness);
  assert.equal(visibleCommands.confirmation_receipt_copyable_command, readiness.confirmation_receipt_copyable_command);
  assert.equal(visibleCommands.scope_remediation_copyable_command, undefined);
});

test("parseFederationSleepResumeConfirmationActorReadiness preserves scope remediation projection", () => {
  const readiness = parseFederationSleepResumeConfirmationActorReadiness({
    ok: true,
    kind: "francis.stage16.federation.sleep_resume_operator_confirmation_actor_readiness",
    status: "actor_scope_missing",
    actor: "codex.builder",
    actor_present: true,
    actor_placeholder_rejected: false,
    required_scope: "federation.stage16.sleep_resume.confirmation.write",
    target_method: "POST",
    target_route: "/federation/sleep-resume-confirmation",
    readiness_route: "/federation/sleep-resume-confirmation/actor-readiness",
    current_pre_sleep_evidence_present: true,
    permission_allowed: false,
    permission_reason: "actor_missing_required_scope",
    confirmation_receipt_actor_ready: false,
    safe_to_use_in_confirmation_command: false,
    next_step: "grant_federation_stage16_sleep_resume_confirmation_write_scope_before_receipt",
    confirmation_receipt_command_ready: false,
    confirmation_receipt_command_requires_actor_substitution: false,
    confirmation_receipt_command_records_receipt: false,
    confirmation_receipt_command_writes_evidence: false,
    confirmation_receipt_command_marks_stage16_closed: false,
    confirmation_receipt_command_projection_only: true,
    scope_remediation_required: true,
    scope_remediation_command_ready: true,
    scope_remediation_command_visible: true,
    scope_remediation_env_var: "FRANCIS_API_ACTOR_SCOPES",
    scope_remediation_actor: "codex.builder",
    scope_remediation_required_scope: "federation.stage16.sleep_resume.confirmation.write",
    scope_remediation_policy_fragment: {
      "codex.builder": ["federation.stage16.sleep_resume.confirmation.write"],
    },
    scope_remediation_command:
      "$env:FRANCIS_API_ACTOR_SCOPES = '{\"codex.builder\":[\"federation.stage16.sleep_resume.confirmation.write\"]}'",
    scope_remediation_copyable_command:
      "$env:FRANCIS_API_ACTOR_SCOPES = '{\"codex.builder\":[\"federation.stage16.sleep_resume.confirmation.write\"]}'",
    scope_remediation_projection_only: true,
    scope_remediation_writes_receipts: false,
    scope_remediation_writes_evidence: false,
    scope_remediation_marks_stage16_closed: false,
    scope_remediation_grants_authority: false,
    scope_remediation_would_mutate_process_environment_if_run: true,
    reads_permission_gate: true,
    writes_receipt: false,
    writes_evidence: false,
    writes_runtime_readback: false,
    marks_stage16_closed: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
    next_smallest_truthful_gap: "stage16_sleep_resume_confirmation_actor_readiness",
  });

  assert.equal(readiness.status, "actor_scope_missing");
  assert.equal(DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR, "codex.builder");
  assert.equal(
    isFederationSleepResumeConfirmationActorReadinessCurrent(
      readiness,
      DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR,
    ),
    true,
  );
  assert.equal(readiness.confirmation_receipt_actor_ready, false);
  assert.equal(readiness.scope_remediation_required, true);
  assert.equal(readiness.scope_remediation_command_ready, true);
  assert.equal(readiness.scope_remediation_command_visible, true);
  assert.equal(readiness.scope_remediation_env_var, "FRANCIS_API_ACTOR_SCOPES");
  assert.equal(readiness.scope_remediation_actor, "codex.builder");
  assert.deepEqual(readiness.scope_remediation_policy_fragment, {
    "codex.builder": ["federation.stage16.sleep_resume.confirmation.write"],
  });
  assert.equal(
    readiness.scope_remediation_command?.includes("federation.stage16.sleep_resume.confirmation.write"),
    true,
  );
  assert.equal(readiness.scope_remediation_copyable_command, readiness.scope_remediation_command);
  assert.equal(readiness.scope_remediation_projection_only, true);
  assert.equal(readiness.scope_remediation_writes_receipts, false);
  assert.equal(readiness.scope_remediation_writes_evidence, false);
  assert.equal(readiness.scope_remediation_marks_stage16_closed, false);
  assert.equal(readiness.scope_remediation_grants_authority, false);
  assert.equal(readiness.scope_remediation_would_mutate_process_environment_if_run, true);
  assert.equal(readiness.writes_receipt, false);
  assert.equal(readiness.marks_stage16_closed, false);

  const visibleCommands = federationSleepResumeConfirmationActorReadinessVisibleCommands(readiness);
  assert.equal(visibleCommands.confirmation_receipt_copyable_command, undefined);
  assert.equal(visibleCommands.scope_remediation_copyable_command, readiness.scope_remediation_copyable_command);
});

test("FederationClient reads sleep-resume confirmation actor readiness without mutation", async () => {
  let request: { path: string; method: string; actor: string | null } | null = null;
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    request = {
      path: parsed.pathname,
      method: (init?.method ?? "GET").toUpperCase(),
      actor: parsed.searchParams.get("actor"),
    };

    return jsonResponse({
      ok: true,
      kind: "francis.stage16.federation.sleep_resume_operator_confirmation_actor_readiness",
      status: "actor_ready_for_sleep_resume_confirmation",
      actor: "test.federation.sleep",
      actor_present: true,
      actor_placeholder_rejected: false,
      required_scope: "federation.stage16.sleep_resume.confirmation.write",
      target_method: "POST",
      target_route: "/federation/sleep-resume-confirmation",
      readiness_route: "/federation/sleep-resume-confirmation/actor-readiness",
      current_pre_sleep_evidence_present: true,
      permission_allowed: true,
      confirmation_receipt_actor_ready: true,
      safe_to_use_in_confirmation_command: true,
      confirmation_receipt_command_ready: true,
      confirmation_receipt_actor: "test.federation.sleep",
      confirmation_receipt_actor_bound: true,
      confirmation_receipt_command:
        "$body = @{ actor = 'test.federation.sleep'; operator_confirmed_sleep_resume = $true }",
      confirmation_receipt_copyable_command:
        "Set-Location -LiteralPath 'D:\\Francis'; $body = @{ actor = 'test.federation.sleep'; operator_confirmed_sleep_resume = $true }",
      confirmation_receipt_command_requires_actor_substitution: false,
      confirmation_receipt_command_records_receipt: true,
      confirmation_receipt_command_writes_evidence: false,
      confirmation_receipt_command_marks_stage16_closed: false,
      confirmation_receipt_command_projection_only: true,
      reads_permission_gate: true,
      writes_receipt: false,
      writes_evidence: false,
      writes_runtime_readback: false,
      marks_stage16_closed: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
    });
  });

  try {
    const client = new FederationClient("http://127.0.0.1:8000");
    const readiness = await client.getSleepResumeConfirmationActorReadiness({
      actor: "test.federation.sleep",
      timeoutMs: 50,
    });

    assert.deepEqual(request, {
      path: "/federation/sleep-resume-confirmation/actor-readiness",
      method: "GET",
      actor: "test.federation.sleep",
    });
    assert.equal(readiness.confirmation_receipt_actor_ready, true);
    assert.equal(readiness.confirmation_receipt_actor_bound, true);
    assert.equal(readiness.confirmation_receipt_command_requires_actor_substitution, false);
    assert.equal(readiness.confirmation_receipt_copyable_command?.includes("test.federation.sleep"), true);
    assert.equal(readiness.writes_receipt, false);
    assert.equal(readiness.marks_stage16_closed, false);
  } finally {
    restoreFetch();
  }
});

test("isFederationSleepResumeConfirmationActorReadinessCurrent rejects stale actor-bound command state", () => {
  const readiness = parseFederationSleepResumeConfirmationActorReadiness({
    ok: true,
    status: "actor_ready_for_sleep_resume_confirmation",
    actor: "test.federation.sleep",
    actor_present: true,
    actor_placeholder_rejected: false,
    permission_allowed: true,
    confirmation_receipt_actor_ready: true,
    safe_to_use_in_confirmation_command: true,
    confirmation_receipt_command_ready: true,
    confirmation_receipt_actor: "test.federation.sleep",
    confirmation_receipt_actor_bound: true,
    confirmation_receipt_command_requires_actor_substitution: false,
    confirmation_receipt_command_records_receipt: true,
    confirmation_receipt_command_writes_evidence: false,
    confirmation_receipt_command_marks_stage16_closed: false,
    confirmation_receipt_command_projection_only: true,
    reads_permission_gate: true,
    writes_receipt: false,
    writes_evidence: false,
    writes_runtime_readback: false,
    marks_stage16_closed: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
  });
  const missingReadiness = parseFederationSleepResumeConfirmationActorReadiness({
    ok: true,
    status: "actor_missing",
    actor: "",
    actor_present: false,
    actor_placeholder_rejected: false,
    permission_allowed: false,
    confirmation_receipt_actor_ready: false,
    safe_to_use_in_confirmation_command: false,
    confirmation_receipt_command_ready: false,
    confirmation_receipt_actor_bound: false,
    confirmation_receipt_command_requires_actor_substitution: false,
    confirmation_receipt_command_records_receipt: false,
    confirmation_receipt_command_writes_evidence: false,
    confirmation_receipt_command_marks_stage16_closed: false,
    confirmation_receipt_command_projection_only: true,
    reads_permission_gate: true,
    writes_receipt: false,
    writes_evidence: false,
    writes_runtime_readback: false,
    marks_stage16_closed: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
  });

  assert.equal(isFederationSleepResumeConfirmationActorReadinessCurrent(readiness, "test.federation.sleep"), true);
  assert.equal(isFederationSleepResumeConfirmationActorReadinessCurrent(readiness, " test.federation.sleep "), true);
  assert.equal(isFederationSleepResumeConfirmationActorReadinessCurrent(readiness, "test.federation.other"), false);
  assert.equal(isFederationSleepResumeConfirmationActorReadinessCurrent(readiness, ""), false);
  assert.equal(isFederationSleepResumeConfirmationActorReadinessCurrent(missingReadiness, ""), true);
  assert.equal(isFederationSleepResumeConfirmationActorReadinessCurrent(null, "test.federation.sleep"), false);
});

test("federation sleep-continuity action parser preserves selected read-only step", () => {
  const action = parseFederationSleepContinuityAction({
    ok: true,
    kind: "francis.stage16.federation.sleep_continuity_action",
    stage: "Stage 16 / Federation",
    status: "capture_post_resume_evidence",
    action_projection_only: true,
    selected_step_id: "capture_post_resume_evidence",
    selected_step_title: "Capture post-resume evidence",
    selected_action: {
      id: "capture_post_resume_evidence",
      title: "Capture post-resume evidence",
      command:
        'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
      pre_sleep_evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
      pre_sleep_evidence_required: true,
      pre_sleep_evidence_available: true,
      post_resume_evidence_required: false,
      post_resume_evidence_available: false,
      operator_action_required: true,
      operator_confirmation_required: true,
      writes_evidence_when_run: true,
      writes_receipts_when_run: false,
      expected_output: "post-resume evidence JSON path",
    },
    primary_command:
      'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
    expected_output: "post-resume evidence JSON path",
    pre_sleep_evidence_path:
      "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
    blockers: ["workstation_sleep_continuity_validated"],
    prior_live_readback_blockers: [],
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: false,
    sleep_continuity_ready: false,
    ready_to_close: false,
    stage16_closed_by_receipt: false,
    operator_action_required: true,
    operator_confirmation_required: true,
    operator_confirmation_requirements: [
      "operator_confirms_workstation_entered_sleep_or_suspend_after_pre_sleep_evidence",
      "operator_confirms_workstation_resumed_before_post_resume_capture",
      "pre_sleep_evidence_path_matches_latest_pre_sleep_artifact",
      "post_resume_capture_uses_operator_confirmed_sleep_resume_flag",
    ],
    current_ready_to_run: false,
    operator_confirmation_pending: true,
    post_confirmation_ready_to_capture: true,
    sleep_resume_confirmation_is_current_blocker: true,
    selected_action_readiness: {
      status: "waiting_for_operator_confirmation",
      ready_to_run: false,
      run_blockers: ["operator_confirmed_sleep_resume_missing"],
      remaining_evidence_gates: ["post_resume_evidence_missing"],
      met_conditions: [
        "pre_sleep_evidence_available",
        "selected_command_requires_operator_confirmed_sleep_resume_flag",
      ],
      operator_terminal_command_ready: true,
      operator_terminal_command_visible: false,
      command_validation: [
        "selected_command_projected",
        "latest_pre_sleep_evidence_path_bound",
        "operator_confirmed_sleep_resume_flag_bound",
        "post_resume_evidence_capture_command_bound",
      ],
      command_validation_blockers: [],
      next_operator_step: "operator_write_sleep_resume_confirmation_receipt",
      selected_step_id: "capture_post_resume_evidence",
      pre_sleep_evidence_ready: true,
      post_resume_evidence_ready: false,
      operator_confirmation_required: true,
      writes_evidence_when_run: true,
      writes_receipts_when_run: false,
    },
    operator_terminal_invocation: {
      status: "command_waiting_for_operator_confirmation",
      shell: "powershell",
      working_directory: "D:\\Francis",
      command:
        'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
      copyable_command:
        'Set-Location -LiteralPath \'D:\\Francis\'; scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
      selected_step_id: "capture_post_resume_evidence",
      operator_confirmation_required: true,
      operator_confirmation_pending: true,
      copyable_after_operator_confirmation: true,
      copyable_command_visible: false,
      should_not_run_before_confirmation: true,
      must_run_after_sleep_resume: true,
      preconditions: [
        "operator_confirms_workstation_entered_sleep_or_suspend_after_pre_sleep_evidence",
        "operator_confirms_workstation_resumed_before_post_resume_capture",
        "pre_sleep_evidence_path_matches_latest_pre_sleep_artifact",
        "post_resume_capture_uses_operator_confirmed_sleep_resume_flag",
      ],
      command_validation: [
        "selected_command_projected",
        "latest_pre_sleep_evidence_path_bound",
        "operator_confirmed_sleep_resume_flag_bound",
        "post_resume_evidence_capture_command_bound",
      ],
      command_validation_blockers: [],
      run_blockers: ["operator_confirmed_sleep_resume_missing"],
      ready_to_run: false,
      operator_terminal_command_ready: true,
      operator_terminal_command_visible: false,
      manual_execution_writes_evidence: true,
      manual_execution_writes_receipts: false,
      projection_only: true,
      projection_runs_shell: false,
      projection_writes_evidence: false,
      projection_writes_receipts: false,
      projection_grants_authority: false,
    },
    operator_sleep_resume_gate: {
      status: "waiting_for_operator_sleep_resume_confirmation",
      selected_step_id: "capture_post_resume_evidence",
      confirmation_required: true,
      required_confirmation_requirements: [
        "operator_confirms_workstation_entered_sleep_or_suspend_after_pre_sleep_evidence",
        "operator_confirms_workstation_resumed_before_post_resume_capture",
        "pre_sleep_evidence_path_matches_latest_pre_sleep_artifact",
        "post_resume_capture_uses_operator_confirmed_sleep_resume_flag",
      ],
      confirmation_blocker: "operator_confirmed_sleep_resume_missing",
      operator_confirmation_blocker_present: true,
      operator_confirmation_pending: true,
      current_ready_to_run: false,
      pre_sleep_evidence_present: true,
      pre_sleep_evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
      pre_sleep_file_name: "pre_sleep_stage16.json",
      pre_sleep_recorded_ts: 1_800_030_000,
      pre_sleep_age_seconds: 300,
      pre_sleep_freshness_state: "fresh",
      continuity_record_id: "stage16-sleep-continuity-test",
      trace_id: "trace-stage16-sleep-continuity-test",
      post_resume_evidence_present: false,
      post_resume_evidence_status: "missing",
      must_sleep_after_pre_sleep_recorded_ts: true,
      must_resume_before_post_resume_capture: true,
      post_resume_capture_allowed_after_operator_confirmation: true,
      post_confirmation_ready_to_capture: true,
      sleep_resume_confirmation_is_current_blocker: true,
      operator_terminal_command_ready: true,
      operator_terminal_command_visible: false,
      ready_after_operator_confirmation: true,
      elapsed_time_is_not_confirmation: true,
      does_not_infer_sleep_from_delay: true,
      projection_only: true,
      projection_runs_shell: false,
      projection_writes_evidence: false,
      projection_writes_receipts: false,
      projection_marks_stage16_closed: false,
    },
    operator_confirmation_handoff: {
      status: "waiting_for_operator_sleep_resume_confirmation",
      selected_step_id: "capture_post_resume_evidence",
      required_confirmation_requirements: [
        "operator_confirms_workstation_entered_sleep_or_suspend_after_pre_sleep_evidence",
        "operator_confirms_workstation_resumed_before_post_resume_capture",
        "pre_sleep_evidence_path_matches_latest_pre_sleep_artifact",
        "post_resume_capture_uses_operator_confirmed_sleep_resume_flag",
      ],
      operator_confirmation_source_required: "manual_operator_confirmation_after_physical_sleep_resume",
      operator_confirmation_pending: true,
      confirmation_blocker: "operator_confirmed_sleep_resume_missing",
      pre_sleep_evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
      pre_sleep_recorded_ts: 1_800_030_000,
      must_sleep_after_pre_sleep_recorded_ts: true,
      must_resume_before_post_resume_capture: true,
      post_resume_capture_command_ready_after_confirmation: true,
      post_resume_capture_command_visible: false,
      post_resume_capture_command:
        'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
      post_resume_capture_copyable_command:
        'Set-Location -LiteralPath \'D:\\Francis\'; scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
      post_resume_sequence_available_after_confirmation: true,
      post_resume_sequence_command_visible: false,
      post_resume_sequence_command:
        'scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -CommitEvidence -CommitReceipts -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
      post_resume_sequence_copyable_command:
        'Set-Location -LiteralPath \'D:\\Francis\'; scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -CommitEvidence -CommitReceipts -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume',
      post_resume_receipt_backed_sequence_command:
        'scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -CommitEvidence -CommitReceipts -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume -RequireConfirmationReceipt -ConfirmationReceiptId <confirmation_receipt_id>',
      post_resume_receipt_backed_sequence_command_visible: false,
      post_resume_receipt_backed_sequence_copyable_command:
        'Set-Location -LiteralPath \'D:\\Francis\'; scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -CommitEvidence -CommitReceipts -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json" -OperatorConfirmedSleepResume -RequireConfirmationReceipt -ConfirmationReceiptId <confirmation_receipt_id>',
      post_resume_receipt_backed_sequence_requires_confirmation_receipt: true,
      post_resume_receipt_backed_sequence_confirmation_receipt_id_placeholder: "<confirmation_receipt_id>",
      post_resume_sequence_writes_evidence_when_run: true,
      post_resume_sequence_writes_receipts_when_run: true,
      confirmation_receipt_route: "/federation/sleep-resume-confirmation",
      confirmation_receipt_readback_route: "/federation/sleep-resume-confirmations",
      confirmation_receipt_required_scope: "federation.stage16.sleep_resume.confirmation.write",
      confirmation_receipt_payload_contract: {
        actor: "operator or delegated builder actor with federation.stage16.sleep_resume.confirmation.write",
        operator_confirmed_sleep_resume: true,
        pre_sleep_evidence_path:
          "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
        reason: "operator confirms physical sleep/suspend and resume after the pre-sleep marker",
      },
      confirmation_receipt_command_ready: true,
      confirmation_receipt_actor_placeholder: "<actor_with_federation.stage16.sleep_resume.confirmation.write>",
      confirmation_receipt_command:
        "$body = @{ actor = '<actor_with_federation.stage16.sleep_resume.confirmation.write>'; reason = 'operator confirms physical sleep/suspend and resume after the pre-sleep marker'; operator_confirmed_sleep_resume = $true; pre_sleep_evidence_path = 'D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json' } | ConvertTo-Json -Depth 6; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/federation/sleep-resume-confirmation' -ContentType 'application/json' -Body $body",
      confirmation_receipt_copyable_command:
        "Set-Location -LiteralPath 'D:\\Francis'; $body = @{ actor = '<actor_with_federation.stage16.sleep_resume.confirmation.write>'; reason = 'operator confirms physical sleep/suspend and resume after the pre-sleep marker'; operator_confirmed_sleep_resume = $true; pre_sleep_evidence_path = 'D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json' } | ConvertTo-Json -Depth 6; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/federation/sleep-resume-confirmation' -ContentType 'application/json' -Body $body",
      confirmation_receipt_command_visible: true,
      confirmation_receipt_command_requires_scope: "federation.stage16.sleep_resume.confirmation.write",
      confirmation_receipt_command_records_receipt: true,
      confirmation_receipt_command_writes_evidence: false,
      confirmation_receipt_command_marks_stage16_closed: false,
      confirmation_receipt_command_projection_only: true,
      confirmation_receipt_available_before_sequence: true,
      confirmation_receipt_required_for_receipt_backed_workflow: true,
      confirmation_receipt_writes_receipts: true,
      confirmation_receipt_writes_evidence: false,
      confirmation_receipt_marks_stage16_closed: false,
      should_not_run_before_confirmation: true,
      operator_terminal_command_ready: true,
      operator_terminal_command_visible: false,
      readback_routes: {
        status: "/federation/status",
        sleep_continuity_action: "/federation/sleep-continuity-action",
        sleep_continuity_runbook: "/federation/sleep-continuity-runbook",
        sleep_resume_confirmations: "/federation/sleep-resume-confirmations",
        completion_review: "/federation/completion-review",
      },
      proof_boundary: {
        projection_only: true,
        requires_manual_operator_confirmation: true,
        does_not_infer_sleep_from_delay: true,
        does_not_run_shell: true,
        does_not_write_evidence: true,
        does_not_write_receipts: true,
        does_not_mark_stage16_closed: true,
        does_not_grant_authority: true,
      },
    },
    after_manual_execution_readback: {
      status: "manual_execution_waiting_for_operator_confirmation",
      selected_step_id: "capture_post_resume_evidence",
      expected_output: "post-resume evidence JSON path",
      operator_terminal_command_ready: true,
      operator_terminal_command_visible: false,
      ready_to_run: false,
      run_blockers: ["operator_confirmed_sleep_resume_missing"],
      operator_confirmation_pending: true,
      should_not_expect_success_before_confirmation: true,
      refresh_routes: {
        status: "/federation/status",
        sleep_continuity_runbook: "/federation/sleep-continuity-runbook",
        sleep_continuity_action: "/federation/sleep-continuity-action",
        completion_review: "/federation/completion-review",
      },
      manual_execution_writes_evidence: true,
      manual_execution_writes_receipts: false,
      projection_only: true,
      projection_runs_shell: false,
      projection_writes_evidence: false,
      projection_writes_receipts: false,
      projection_marks_stage16_closed: false,
      expected_artifact_root: "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence",
      expected_artifact_prefix: "post_resume_",
      expected_artifact_kind: "stage16_sleep_continuity_post_resume",
      expected_status_after_success: "post_resume_evidence_ready",
      expected_action_status_after_success: "run_sleep_continuity_runtime_proof",
      expected_selected_step_id_after_success: "commit_sleep_continuity_readback",
      expected_next_step_after_success: "run_sleep_continuity_runtime_proof_with_committed_evidence",
    },
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
      sleep_resume_confirmation: "/federation/sleep-resume-confirmation",
      sleep_resume_confirmations: "/federation/sleep-resume-confirmations",
      stage_closure_decision: "/federation/stage-closure-decision",
      stage_closure_decisions: "/federation/stage-closure-decisions",
      malformed: false,
    },
    governance: {
      read_only: true,
      action_projection_only: true,
      does_not_infer_sleep_from_delay: true,
      confirmation_requirements_projected: true,
      does_not_run_selected_command: true,
      does_not_post_selected_route: true,
    },
    next_smallest_truthful_gap: "stage16_sleep_resume_confirmation_receipt",
  });

  assert.equal(action.status, "capture_post_resume_evidence");
  assert.equal(action.selected_step_id, "capture_post_resume_evidence");
  assert.equal(action.selected_step_title, "Capture post-resume evidence");
  assert.equal(action.selected_action?.id, "capture_post_resume_evidence");
  assert.equal(action.selected_action?.title, "Capture post-resume evidence");
  assert.equal(
    action.selected_action?.pre_sleep_evidence_path,
    "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
  );
  assert.equal(action.selected_action?.operator_confirmation_required, true);
  assert.equal(action.selected_action?.expected_output, "post-resume evidence JSON path");
  assert.equal(action.expected_output, "post-resume evidence JSON path");
  assert.deepEqual(action.operator_confirmation_requirements, [
    "operator_confirms_workstation_entered_sleep_or_suspend_after_pre_sleep_evidence",
    "operator_confirms_workstation_resumed_before_post_resume_capture",
    "pre_sleep_evidence_path_matches_latest_pre_sleep_artifact",
    "post_resume_capture_uses_operator_confirmed_sleep_resume_flag",
  ]);
  assert.equal(action.current_ready_to_run, false);
  assert.equal(action.operator_confirmation_pending, true);
  assert.equal(action.post_confirmation_ready_to_capture, true);
  assert.equal(action.sleep_resume_confirmation_is_current_blocker, true);
  assert.equal(action.selected_action_readiness?.status, "waiting_for_operator_confirmation");
  assert.equal(action.selected_action_readiness?.ready_to_run, false);
  assert.deepEqual(action.selected_action_readiness?.run_blockers, ["operator_confirmed_sleep_resume_missing"]);
  assert.deepEqual(action.selected_action_readiness?.remaining_evidence_gates, ["post_resume_evidence_missing"]);
  assert.deepEqual(action.selected_action_readiness?.met_conditions, [
    "pre_sleep_evidence_available",
    "selected_command_requires_operator_confirmed_sleep_resume_flag",
  ]);
  assert.equal(action.selected_action_readiness?.operator_terminal_command_ready, true);
  assert.equal(action.selected_action_readiness?.operator_terminal_command_visible, false);
  assert.deepEqual(action.selected_action_readiness?.command_validation, [
    "selected_command_projected",
    "latest_pre_sleep_evidence_path_bound",
    "operator_confirmed_sleep_resume_flag_bound",
    "post_resume_evidence_capture_command_bound",
  ]);
  assert.deepEqual(action.selected_action_readiness?.command_validation_blockers, []);
  assert.equal(action.operator_terminal_invocation?.status, "command_waiting_for_operator_confirmation");
  assert.equal(action.operator_terminal_invocation?.shell, "powershell");
  assert.equal(action.operator_terminal_invocation?.working_directory, "D:\\Francis");
  assert.equal(action.operator_terminal_invocation?.command, action.primary_command);
  assert.equal(action.operator_terminal_invocation?.copyable_command?.includes("Set-Location -LiteralPath"), true);
  assert.equal(action.operator_terminal_invocation?.operator_confirmation_required, true);
  assert.equal(action.operator_terminal_invocation?.operator_confirmation_pending, true);
  assert.equal(action.operator_terminal_invocation?.copyable_after_operator_confirmation, true);
  assert.equal(action.operator_terminal_invocation?.copyable_command_visible, false);
  assert.equal(action.operator_terminal_invocation?.should_not_run_before_confirmation, true);
  assert.equal(action.operator_terminal_invocation?.must_run_after_sleep_resume, true);
  assert.deepEqual(action.operator_terminal_invocation?.preconditions, action.operator_confirmation_requirements);
  assert.deepEqual(action.operator_terminal_invocation?.run_blockers, ["operator_confirmed_sleep_resume_missing"]);
  assert.equal(action.operator_terminal_invocation?.ready_to_run, false);
  assert.equal(action.operator_terminal_invocation?.operator_terminal_command_ready, true);
  assert.equal(action.operator_terminal_invocation?.operator_terminal_command_visible, false);
  assert.equal(action.operator_terminal_invocation?.manual_execution_writes_evidence, true);
  assert.equal(action.operator_terminal_invocation?.manual_execution_writes_receipts, false);
  assert.equal(action.operator_terminal_invocation?.projection_runs_shell, false);
  assert.equal(action.operator_terminal_invocation?.projection_writes_evidence, false);
  assert.equal(action.operator_terminal_invocation?.projection_grants_authority, false);
  assert.equal(action.operator_sleep_resume_gate?.status, "waiting_for_operator_sleep_resume_confirmation");
  assert.equal(action.operator_sleep_resume_gate?.selected_step_id, "capture_post_resume_evidence");
  assert.equal(action.operator_sleep_resume_gate?.confirmation_required, true);
  assert.deepEqual(
    action.operator_sleep_resume_gate?.required_confirmation_requirements,
    action.operator_confirmation_requirements,
  );
  assert.equal(action.operator_sleep_resume_gate?.confirmation_blocker, "operator_confirmed_sleep_resume_missing");
  assert.equal(action.operator_sleep_resume_gate?.operator_confirmation_blocker_present, true);
  assert.equal(action.operator_sleep_resume_gate?.operator_confirmation_pending, true);
  assert.equal(action.operator_sleep_resume_gate?.current_ready_to_run, false);
  assert.equal(action.operator_sleep_resume_gate?.pre_sleep_evidence_present, true);
  assert.equal(action.operator_sleep_resume_gate?.pre_sleep_file_name, "pre_sleep_stage16.json");
  assert.equal(action.operator_sleep_resume_gate?.pre_sleep_recorded_ts, 1_800_030_000);
  assert.equal(action.operator_sleep_resume_gate?.pre_sleep_age_seconds, 300);
  assert.equal(action.operator_sleep_resume_gate?.pre_sleep_freshness_state, "fresh");
  assert.equal(action.operator_sleep_resume_gate?.post_resume_evidence_present, false);
  assert.equal(action.operator_sleep_resume_gate?.post_resume_evidence_status, "missing");
  assert.equal(action.operator_sleep_resume_gate?.must_sleep_after_pre_sleep_recorded_ts, true);
  assert.equal(action.operator_sleep_resume_gate?.must_resume_before_post_resume_capture, true);
  assert.equal(action.operator_sleep_resume_gate?.post_resume_capture_allowed_after_operator_confirmation, true);
  assert.equal(action.operator_sleep_resume_gate?.post_confirmation_ready_to_capture, true);
  assert.equal(action.operator_sleep_resume_gate?.sleep_resume_confirmation_is_current_blocker, true);
  assert.equal(action.operator_sleep_resume_gate?.operator_terminal_command_visible, false);
  assert.equal(action.operator_sleep_resume_gate?.ready_after_operator_confirmation, true);
  assert.equal(action.operator_sleep_resume_gate?.elapsed_time_is_not_confirmation, true);
  assert.equal(action.operator_sleep_resume_gate?.does_not_infer_sleep_from_delay, true);
  assert.equal(action.operator_sleep_resume_gate?.projection_runs_shell, false);
  assert.equal(action.operator_sleep_resume_gate?.projection_marks_stage16_closed, false);
  assert.equal(action.operator_confirmation_handoff?.status, "waiting_for_operator_sleep_resume_confirmation");
  assert.equal(action.operator_confirmation_handoff?.selected_step_id, "capture_post_resume_evidence");
  assert.deepEqual(
    action.operator_confirmation_handoff?.required_confirmation_requirements,
    action.operator_confirmation_requirements,
  );
  assert.equal(
    action.operator_confirmation_handoff?.operator_confirmation_source_required,
    "manual_operator_confirmation_after_physical_sleep_resume",
  );
  assert.equal(action.operator_confirmation_handoff?.operator_confirmation_pending, true);
  assert.equal(action.operator_confirmation_handoff?.confirmation_blocker, "operator_confirmed_sleep_resume_missing");
  assert.equal(action.operator_confirmation_handoff?.pre_sleep_recorded_ts, 1_800_030_000);
  assert.equal(action.operator_confirmation_handoff?.must_sleep_after_pre_sleep_recorded_ts, true);
  assert.equal(action.operator_confirmation_handoff?.must_resume_before_post_resume_capture, true);
  assert.equal(action.operator_confirmation_handoff?.post_resume_capture_command_ready_after_confirmation, true);
  assert.equal(action.operator_confirmation_handoff?.post_resume_capture_command_visible, false);
  assert.equal(action.operator_confirmation_handoff?.post_resume_capture_command?.includes("-OperatorConfirmedSleepResume"), true);
  assert.equal(action.operator_confirmation_handoff?.post_resume_sequence_available_after_confirmation, true);
  assert.equal(action.operator_confirmation_handoff?.post_resume_sequence_command_visible, false);
  assert.equal(
    action.operator_confirmation_handoff?.post_resume_sequence_command?.includes(
      "federation-stage16-sleep-continuity-post-resume-sequence.ps1",
    ),
    true,
  );
  assert.equal(action.operator_confirmation_handoff?.post_resume_sequence_command?.includes("-CommitReceipts"), true);
  assert.equal(
    action.operator_confirmation_handoff?.post_resume_receipt_backed_sequence_command?.includes(
      "-RequireConfirmationReceipt",
    ),
    true,
  );
  assert.equal(
    action.operator_confirmation_handoff?.post_resume_receipt_backed_sequence_command?.includes(
      "-ConfirmationReceiptId <confirmation_receipt_id>",
    ),
    true,
  );
  assert.equal(
    action.operator_confirmation_handoff?.post_resume_receipt_backed_sequence_copyable_command?.includes(
      action.operator_confirmation_handoff.post_resume_receipt_backed_sequence_command ?? "",
    ),
    true,
  );
  assert.equal(action.operator_confirmation_handoff?.post_resume_receipt_backed_sequence_command_visible, false);
  assert.equal(action.operator_confirmation_handoff?.post_resume_receipt_backed_sequence_requires_confirmation_receipt, true);
  assert.equal(
    action.operator_confirmation_handoff?.post_resume_receipt_backed_sequence_confirmation_receipt_id_placeholder,
    "<confirmation_receipt_id>",
  );
  assert.equal(action.operator_confirmation_handoff?.post_resume_sequence_writes_evidence_when_run, true);
  assert.equal(action.operator_confirmation_handoff?.post_resume_sequence_writes_receipts_when_run, true);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_route, "/federation/sleep-resume-confirmation");
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_readback_route,
    "/federation/sleep-resume-confirmations",
  );
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_required_scope,
    "federation.stage16.sleep_resume.confirmation.write",
  );
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_command_ready, true);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_command_visible, true);
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_actor_placeholder,
    "<actor_with_federation.stage16.sleep_resume.confirmation.write>",
  );
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_command?.includes("Invoke-RestMethod -Method Post"),
    true,
  );
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_command?.includes(
      "http://127.0.0.1:8000/federation/sleep-resume-confirmation",
    ),
    true,
  );
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_command?.includes(
      "operator_confirmed_sleep_resume = $true",
    ),
    true,
  );
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_copyable_command?.includes(
      action.operator_confirmation_handoff.confirmation_receipt_command ?? "",
    ),
    true,
  );
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_command_requires_scope,
    "federation.stage16.sleep_resume.confirmation.write",
  );
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_command_records_receipt, true);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_command_writes_evidence, false);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_command_marks_stage16_closed, false);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_command_projection_only, true);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_available_before_sequence, true);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_required_for_receipt_backed_workflow, true);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_writes_receipts, true);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_writes_evidence, false);
  assert.equal(action.operator_confirmation_handoff?.confirmation_receipt_marks_stage16_closed, false);
  assert.equal(
    action.operator_confirmation_handoff?.confirmation_receipt_payload_contract?.pre_sleep_evidence_path,
    "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
  );
  assert.equal(action.operator_confirmation_handoff?.should_not_run_before_confirmation, true);
  assert.equal(action.operator_confirmation_handoff?.operator_terminal_command_ready, true);
  assert.equal(action.operator_confirmation_handoff?.operator_terminal_command_visible, false);
  assert.equal(action.operator_confirmation_handoff?.readback_routes.status, "/federation/status");
  assert.equal(
    action.operator_confirmation_handoff?.readback_routes.sleep_resume_confirmations,
    "/federation/sleep-resume-confirmations",
  );
  assert.equal(action.operator_confirmation_handoff?.proof_boundary.projection_only, true);
  assert.equal(action.operator_confirmation_handoff?.proof_boundary.does_not_run_shell, true);
  assert.equal(action.operator_confirmation_handoff?.proof_boundary.does_not_mark_stage16_closed, true);
  assert.equal(
    action.after_manual_execution_readback?.status,
    "manual_execution_waiting_for_operator_confirmation",
  );
  assert.equal(action.after_manual_execution_readback?.selected_step_id, "capture_post_resume_evidence");
  assert.deepEqual(action.after_manual_execution_readback?.run_blockers, ["operator_confirmed_sleep_resume_missing"]);
  assert.equal(action.after_manual_execution_readback?.operator_confirmation_pending, true);
  assert.equal(action.after_manual_execution_readback?.operator_terminal_command_visible, false);
  assert.equal(action.after_manual_execution_readback?.should_not_expect_success_before_confirmation, true);
  assert.equal(
    action.after_manual_execution_readback?.expected_artifact_root,
    "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence",
  );
  assert.equal(action.after_manual_execution_readback?.expected_artifact_prefix, "post_resume_");
  assert.equal(action.after_manual_execution_readback?.expected_artifact_kind, "stage16_sleep_continuity_post_resume");
  assert.equal(action.after_manual_execution_readback?.expected_status_after_success, "post_resume_evidence_ready");
  assert.equal(
    action.after_manual_execution_readback?.expected_action_status_after_success,
    "run_sleep_continuity_runtime_proof",
  );
  assert.equal(
    action.after_manual_execution_readback?.expected_selected_step_id_after_success,
    "commit_sleep_continuity_readback",
  );
  assert.equal(action.after_manual_execution_readback?.refresh_routes.status, "/federation/status");
  assert.equal(
    action.after_manual_execution_readback?.refresh_routes.sleep_continuity_action,
    "/federation/sleep-continuity-action",
  );
  assert.equal(action.after_manual_execution_readback?.projection_runs_shell, false);
  assert.equal(action.after_manual_execution_readback?.projection_marks_stage16_closed, false);
  assert.equal(
    action.selected_action_readiness?.next_operator_step,
    "operator_write_sleep_resume_confirmation_receipt",
  );
  assert.equal(action.primary_command?.includes("-OperatorConfirmedSleepResume"), true);
  assert.equal(
    action.pre_sleep_evidence_path,
    "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
  );
  assert.deepEqual(action.prior_live_readback_blockers, []);
  assert.equal(action.action_projection_only, true);
  assert.equal(action.mutation_available_from_ui, false);
  assert.equal(action.writes_evidence, false);
  assert.equal(action.writes_receipts, false);
  assert.equal(action.writes_registry, false);
  assert.equal(action.writes_memory, false);
  assert.equal(action.runs_tools, false);
  assert.equal(action.runs_shell, false);
  assert.equal(action.runs_git, false);
  assert.equal(action.launches_browser, false);
  assert.equal(action.captures_screen, false);
  assert.equal(action.grants_execution_authority, false);
  assert.equal(action.grants_mutation_authority, false);
  assert.equal(action.marks_stage16_closed, false);
  assert.equal(action.routes.sleep_continuity_action, "/federation/sleep-continuity-action");
  assert.equal(action.routes.sleep_continuity_runbook, "/federation/sleep-continuity-runbook");
  assert.equal(action.routes.sleep_resume_confirmation, "/federation/sleep-resume-confirmation");
  assert.equal(action.routes.sleep_resume_confirmations, "/federation/sleep-resume-confirmations");
  assert.equal(action.routes.stage_closure_decision, "/federation/stage-closure-decision");
  assert.equal(action.routes.stage_closure_decisions, "/federation/stage-closure-decisions");
  assert.equal(action.routes.malformed, undefined);
  assert.equal(action.governance?.read_only, true);
  assert.equal(action.governance?.action_projection_only, true);
  assert.equal(action.governance?.does_not_infer_sleep_from_delay, true);
  assert.equal(action.governance?.confirmation_requirements_projected, true);
  assert.equal(action.governance?.does_not_run_selected_command, true);
  assert.equal(action.governance?.does_not_post_selected_route, true);

  const presentation = presentFederationSleepContinuityAction(action);
  assert.equal(presentation.state, "capture_post_resume_evidence");
  assert.equal(presentation.status_label, "Capture post-resume evidence");
  assert.equal(presentation.selected_step_id, "capture_post_resume_evidence");
  assert.equal(presentation.selected_step_title, "Capture post-resume evidence");
  assert.equal(presentation.primary_command?.includes("-OperatorConfirmedSleepResume"), true);
  assert.equal(presentation.expected_output, "post-resume evidence JSON path");
  assert.equal(presentation.readback_route, "/federation/sleep-continuity-action");
  assert.equal(presentation.runbook_route, "/federation/sleep-continuity-runbook");
  assert.equal(presentation.closure_decision_route, "/federation/stage-closure-decision");
  assert.equal(
    presentation.pre_sleep_evidence_path,
    "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
  );
  assert.deepEqual(presentation.blockers, ["workstation_sleep_continuity_validated"]);
  assert.deepEqual(presentation.prior_live_readback_blockers, []);
  assert.equal(presentation.pre_sleep_evidence_ready, true);
  assert.equal(presentation.post_resume_evidence_ready, false);
  assert.equal(presentation.operator_action_required, true);
  assert.equal(presentation.operator_confirmation_required, true);
  assert.deepEqual(presentation.operator_confirmation_requirements, action.operator_confirmation_requirements);
  assert.equal(presentation.current_ready_to_run, false);
  assert.equal(presentation.operator_confirmation_pending, true);
  assert.equal(presentation.post_confirmation_ready_to_capture, true);
  assert.equal(presentation.sleep_resume_confirmation_is_current_blocker, true);
  assert.equal(presentation.selected_action_readiness?.status, "waiting_for_operator_confirmation");
  assert.deepEqual(presentation.selected_action_readiness?.run_blockers, ["operator_confirmed_sleep_resume_missing"]);
  assert.deepEqual(presentation.selected_action_readiness?.met_conditions, [
    "pre_sleep_evidence_available",
    "selected_command_requires_operator_confirmed_sleep_resume_flag",
  ]);
  assert.equal(presentation.selected_action_readiness?.operator_terminal_command_ready, true);
  assert.equal(presentation.selected_action_readiness?.operator_terminal_command_visible, false);
  assert.deepEqual(presentation.selected_action_readiness?.command_validation, [
    "selected_command_projected",
    "latest_pre_sleep_evidence_path_bound",
    "operator_confirmed_sleep_resume_flag_bound",
    "post_resume_evidence_capture_command_bound",
  ]);
  assert.equal(presentation.operator_terminal_invocation?.status, "command_waiting_for_operator_confirmation");
  assert.equal(presentation.operator_terminal_invocation?.copyable_command?.includes(action.primary_command ?? ""), true);
  assert.equal(presentation.operator_terminal_invocation?.operator_confirmation_pending, true);
  assert.equal(presentation.operator_terminal_invocation?.must_run_after_sleep_resume, true);
  assert.equal(presentation.operator_terminal_invocation?.copyable_command_visible, false);
  assert.equal(presentation.operator_terminal_invocation?.operator_terminal_command_visible, false);
  assert.equal(presentation.operator_terminal_invocation?.projection_only, true);
  assert.equal(isFederationSleepContinuityOperatorCommandBlockedByPendingConfirmation(presentation), true);
  const visibleCommands = federationSleepContinuityVisibleOperatorCommands(presentation);
  assert.equal(visibleCommands.blocked_by_pending_confirmation, true);
  assert.equal(visibleCommands.primary_command, undefined);
  assert.equal(visibleCommands.operator_terminal_copyable_command, undefined);
  assert.equal(visibleCommands.post_resume_capture_copyable_command, undefined);
  assert.equal(visibleCommands.post_resume_sequence_copyable_command, undefined);
  assert.equal(visibleCommands.post_resume_receipt_backed_sequence_copyable_command, undefined);
  assert.equal(
    visibleCommands.confirmation_receipt_copyable_command?.includes(
      "http://127.0.0.1:8000/federation/sleep-resume-confirmation",
    ),
    true,
  );
  assert.equal(presentation.operator_sleep_resume_gate?.status, "waiting_for_operator_sleep_resume_confirmation");
  assert.equal(presentation.operator_sleep_resume_gate?.pre_sleep_age_seconds, 300);
  assert.equal(presentation.operator_sleep_resume_gate?.current_ready_to_run, false);
  assert.equal(presentation.operator_sleep_resume_gate?.operator_confirmation_pending, true);
  assert.equal(presentation.operator_sleep_resume_gate?.operator_terminal_command_visible, false);
  assert.equal(presentation.operator_sleep_resume_gate?.post_confirmation_ready_to_capture, true);
  assert.equal(presentation.operator_sleep_resume_gate?.ready_after_operator_confirmation, true);
  assert.equal(presentation.operator_sleep_resume_gate?.does_not_infer_sleep_from_delay, true);
  assert.equal(presentation.operator_confirmation_handoff?.status, "waiting_for_operator_sleep_resume_confirmation");
  assert.equal(presentation.operator_confirmation_handoff?.operator_confirmation_pending, true);
  assert.equal(presentation.operator_confirmation_handoff?.operator_terminal_command_visible, false);
  assert.equal(
    presentation.operator_confirmation_handoff?.post_resume_capture_command_ready_after_confirmation,
    true,
  );
  assert.equal(presentation.operator_confirmation_handoff?.post_resume_capture_command_visible, false);
  assert.equal(presentation.operator_confirmation_handoff?.post_resume_sequence_available_after_confirmation, true);
  assert.equal(presentation.operator_confirmation_handoff?.post_resume_sequence_command_visible, false);
  assert.equal(presentation.operator_confirmation_handoff?.post_resume_sequence_writes_receipts_when_run, true);
  assert.equal(
    presentation.operator_confirmation_handoff?.post_resume_receipt_backed_sequence_requires_confirmation_receipt,
    true,
  );
  assert.equal(presentation.operator_confirmation_handoff?.post_resume_receipt_backed_sequence_command_visible, false);
  assert.equal(presentation.operator_confirmation_handoff?.confirmation_receipt_route, "/federation/sleep-resume-confirmation");
  assert.equal(presentation.operator_confirmation_handoff?.confirmation_receipt_command_ready, true);
  assert.equal(presentation.operator_confirmation_handoff?.confirmation_receipt_command_visible, true);
  assert.equal(presentation.operator_confirmation_handoff?.confirmation_receipt_command_records_receipt, true);
  assert.equal(presentation.operator_confirmation_handoff?.confirmation_receipt_command_projection_only, true);
  assert.equal(presentation.operator_confirmation_handoff?.confirmation_receipt_writes_receipts, true);
  assert.equal(presentation.operator_confirmation_handoff?.confirmation_receipt_marks_stage16_closed, false);
  assert.equal(presentation.operator_confirmation_handoff?.proof_boundary.does_not_run_shell, true);
  assert.equal(
    presentation.after_manual_execution_readback?.status,
    "manual_execution_waiting_for_operator_confirmation",
  );
  assert.equal(presentation.after_manual_execution_readback?.operator_confirmation_pending, true);
  assert.equal(presentation.after_manual_execution_readback?.operator_terminal_command_visible, false);
  assert.equal(
    presentation.after_manual_execution_readback?.expected_next_step_after_success,
    "run_sleep_continuity_runtime_proof_with_committed_evidence",
  );
  assert.equal(presentation.after_manual_execution_readback?.projection_marks_stage16_closed, false);
  assert.equal(presentation.writes_evidence_when_run, true);
  assert.equal(presentation.writes_receipts_when_run, false);
  assert.equal(presentation.mutation_available_from_ui, false);
  assert.equal(presentation.next_smallest_truthful_gap, "stage16_sleep_resume_confirmation_receipt");
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
    status: "post_resume_evidence_ready",
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

  assert.equal(runbook.status, "post_resume_evidence_ready");
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
      status: "pre_sleep_evidence_available",
      evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stage16.json",
      continuity_record_id: "stage16-sleep-continuity-test",
      trace_id: "trace-stage16-sleep-continuity-test",
    },
    latest_post_resume_evidence: {
      present: false,
      status: "missing",
      linked_to_latest_pre_sleep: false,
    },
    sleep_continuity_selected_action_id: "capture_post_resume_evidence",
    sleep_continuity_action_current_ready_to_run: false,
    sleep_continuity_operator_confirmation_pending: true,
    sleep_continuity_post_confirmation_ready_to_capture: true,
    sleep_continuity_confirmation_blocker: "operator_confirmed_sleep_resume_missing",
    sleep_continuity_blocked_reason: "operator_confirmed_sleep_resume_missing",
    sleep_continuity_sleep_resume_confirmation_is_current_blocker: true,
    sleep_continuity_confirmation_receipt_command_ready: true,
    sleep_continuity_confirmation_receipt_command_visible: true,
    sleep_continuity_confirmation_receipt_command:
      "$body = @{ actor = '<actor_with_federation.stage16.sleep_resume.confirmation.write>'; operator_confirmed_sleep_resume = $true } | ConvertTo-Json -Depth 6; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/federation/sleep-resume-confirmation' -ContentType 'application/json' -Body $body",
    sleep_continuity_confirmation_receipt_copyable_command:
      "Set-Location -LiteralPath 'D:\\Francis'; $body = @{ actor = '<actor_with_federation.stage16.sleep_resume.confirmation.write>'; operator_confirmed_sleep_resume = $true } | ConvertTo-Json -Depth 6; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/federation/sleep-resume-confirmation' -ContentType 'application/json' -Body $body",
    sleep_continuity_confirmation_receipt_command_requires_scope:
      "federation.stage16.sleep_resume.confirmation.write",
    sleep_continuity_confirmation_receipt_command_requires_actor_substitution: true,
    sleep_continuity_confirmation_receipt_command_next_readback_route: "/federation/sleep-resume-confirmations",
    sleep_continuity_confirmation_receipt_command_receipt_id_readback_field: "latest_receipt_id",
    sleep_continuity_confirmation_receipt_command_records_receipt: true,
    sleep_continuity_confirmation_receipt_command_writes_evidence: false,
    sleep_continuity_confirmation_receipt_command_marks_stage16_closed: false,
    sleep_continuity_confirmation_receipt_command_projection_only: true,
    sleep_continuity_next_step: "write_sleep_resume_confirmation_receipt",
    ready_count: 6,
    required_count: 6,
    next_smallest_truthful_gap: "stage16_sleep_resume_confirmation_receipt",
  });
  const runbook = parseFederationSleepContinuityRunbook({
    ok: true,
    status: "pre_sleep_evidence_ready",
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
    next_smallest_truthful_gap: "stage16_sleep_resume_confirmation_receipt",
  });

  const presentation = presentFederationSleepContinuity(status, runbook);

  assert.equal(presentation.state, "capture_post_resume_evidence");
  assert.equal(presentation.selected_step_id, "capture_post_resume_evidence");
  assert.equal(presentation.primary_command?.includes("-OperatorConfirmedSleepResume"), true);
  assert.deepEqual(presentation.blockers, ["workstation_sleep_continuity_validated"]);
  assert.equal(presentation.pre_sleep_evidence_ready, true);
  assert.equal(presentation.post_resume_evidence_ready, false);
  assert.equal(presentation.sleep_continuity_ready, false);
  assert.equal(status.latest_pre_sleep_evidence?.status, "pre_sleep_evidence_available");
  assert.equal(status.latest_pre_sleep_evidence?.continuity_record_id, "stage16-sleep-continuity-test");
  assert.equal(status.latest_pre_sleep_evidence?.trace_id, "trace-stage16-sleep-continuity-test");
  assert.equal(status.latest_post_resume_evidence?.status, "missing");
  assert.equal(status.latest_post_resume_evidence?.linked_to_latest_pre_sleep, false);
  assert.equal(status.sleep_continuity_selected_action_id, "capture_post_resume_evidence");
  assert.equal(status.sleep_continuity_action_current_ready_to_run, false);
  assert.equal(status.sleep_continuity_operator_confirmation_pending, true);
  assert.equal(status.sleep_continuity_post_confirmation_ready_to_capture, true);
  assert.equal(status.sleep_continuity_confirmation_blocker, "operator_confirmed_sleep_resume_missing");
  assert.equal(status.sleep_continuity_blocked_reason, "operator_confirmed_sleep_resume_missing");
  assert.equal(status.sleep_continuity_sleep_resume_confirmation_is_current_blocker, true);
  assert.equal(status.sleep_continuity_confirmation_receipt_command_ready, true);
  assert.equal(status.sleep_continuity_confirmation_receipt_command_visible, true);
  assert.equal(
    status.sleep_continuity_confirmation_receipt_command?.includes("Invoke-RestMethod -Method Post"),
    true,
  );
  assert.equal(
    status.sleep_continuity_confirmation_receipt_command?.includes("/federation/sleep-resume-confirmation"),
    true,
  );
  assert.equal(
    status.sleep_continuity_confirmation_receipt_command?.includes("operator_confirmed_sleep_resume = $true"),
    true,
  );
  assert.equal(
    status.sleep_continuity_confirmation_receipt_copyable_command?.includes(
      status.sleep_continuity_confirmation_receipt_command ?? "",
    ),
    true,
  );
  assert.equal(
    status.sleep_continuity_confirmation_receipt_command_requires_scope,
    "federation.stage16.sleep_resume.confirmation.write",
  );
  assert.equal(status.sleep_continuity_confirmation_receipt_command_requires_actor_substitution, true);
  assert.equal(
    status.sleep_continuity_confirmation_receipt_command_next_readback_route,
    "/federation/sleep-resume-confirmations",
  );
  assert.equal(status.sleep_continuity_confirmation_receipt_command_receipt_id_readback_field, "latest_receipt_id");
  assert.equal(status.sleep_continuity_confirmation_receipt_command_records_receipt, true);
  assert.equal(status.sleep_continuity_confirmation_receipt_command_writes_evidence, false);
  assert.equal(status.sleep_continuity_confirmation_receipt_command_marks_stage16_closed, false);
  assert.equal(status.sleep_continuity_confirmation_receipt_command_projection_only, true);
  assert.equal(status.sleep_continuity_next_step, "write_sleep_resume_confirmation_receipt");
  assert.equal(presentation.ready_to_close, false);
  assert.equal(presentation.operator_action_required, true);
  assert.equal(presentation.operator_confirmation_required, true);
  assert.equal(presentation.writes_evidence_when_run, true);
  assert.equal(presentation.writes_receipts_when_run, false);
  assert.equal(presentation.mutation_available_from_ui, false);
  assert.equal(presentation.next_smallest_truthful_gap, "stage16_sleep_resume_confirmation_receipt");
});

test("federation sleep-continuity presentation surfaces post-resume evidence conflicts", () => {
  const status = parseFederationStage16Status({
    ok: true,
    stage16_status: "stage16_contracts_ready_completion_blocked",
    stage16_completion_review_ready: false,
    live_runtime_readback_ready: true,
    completion_review_blockers: ["workstation_sleep_continuity_validated"],
    sleep_continuity_status: "post_resume_evidence_conflict",
    sleep_continuity_ready: false,
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: false,
    post_resume_evidence_conflict: true,
    latest_post_resume_evidence: {
      present: false,
      status: "pre_sleep_path_mismatch",
      candidate_evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\post_resume_mismatch.json",
      expected_pre_sleep_evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_latest.json",
      candidate_pre_sleep_evidence_path:
        "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_stale.json",
      linked_to_latest_pre_sleep: false,
      conflict_detected: true,
    },
    sleep_continuity_next_step: "recapture_post_resume_evidence_for_latest_pre_sleep",
    ready_count: 6,
    required_count: 6,
    next_smallest_truthful_gap: "stage16_sleep_continuity_runtime_readback",
  });
  const runbook = parseFederationSleepContinuityRunbook({
    ok: true,
    status: "post_resume_evidence_conflict",
    runbook_only: true,
    prerequisite_readbacks_ready: true,
    sleep_continuity_readback_id: "workstation_sleep_continuity_validated",
    sleep_continuity_ready: false,
    pre_sleep_evidence_ready: true,
    post_resume_evidence_ready: false,
    post_resume_evidence_conflict: true,
    ready_to_close: false,
    stage16_closed_by_receipt: false,
    missing_readbacks: ["workstation_sleep_continuity_validated"],
    steps: [
      {
        id: "capture_post_resume_evidence",
        command:
          'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath "D:\\Francis\\data\\test_runs\\federation-stage16-sleep-continuity-evidence\\pre_sleep_latest.json" -OperatorConfirmedSleepResume',
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

  assert.equal(status.post_resume_evidence_conflict, true);
  assert.equal(runbook.post_resume_evidence_conflict, true);
  assert.equal(status.latest_post_resume_evidence?.status, "pre_sleep_path_mismatch");
  assert.equal(presentation.state, "capture_post_resume_evidence");
  assert.equal(presentation.post_resume_evidence_ready, false);
  assert.equal(presentation.post_resume_evidence_conflict, true);
  assert.equal(status.sleep_continuity_next_step, "recapture_post_resume_evidence_for_latest_pre_sleep");
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
    sleep_continuity_selected_action_id: "commit_sleep_continuity_readback",
    sleep_continuity_action_current_ready_to_run: true,
    sleep_continuity_operator_confirmation_pending: false,
    sleep_continuity_post_confirmation_ready_to_capture: false,
    sleep_continuity_confirmation_blocker: "",
    sleep_continuity_blocked_reason: "",
    sleep_continuity_sleep_resume_confirmation_is_current_blocker: false,
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

  assert.equal(status.sleep_continuity_selected_action_id, "commit_sleep_continuity_readback");
  assert.equal(status.sleep_continuity_action_current_ready_to_run, true);
  assert.equal(status.sleep_continuity_operator_confirmation_pending, false);
  assert.equal(status.sleep_continuity_post_confirmation_ready_to_capture, false);
  assert.equal(status.sleep_continuity_confirmation_blocker, undefined);
  assert.equal(status.sleep_continuity_sleep_resume_confirmation_is_current_blocker, false);
  assert.equal(presentation.state, "run_sleep_continuity_runtime_proof");
  assert.equal(presentation.selected_step_id, "commit_sleep_continuity_readback");
  assert.equal(presentation.primary_command?.includes("federation-stage16-sleep-continuity-runtime-proof.ps1"), true);
  assert.equal(presentation.operator_confirmation_required, false);
  assert.equal(isFederationSleepContinuityOperatorCommandBlockedByPendingConfirmation(presentation), false);
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
