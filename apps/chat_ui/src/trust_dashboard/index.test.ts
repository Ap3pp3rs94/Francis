import assert from "node:assert/strict";
import test from "node:test";

import {
  TrustApiError,
  TrustClient,
  presentTrustCalibrationClaimEvaluation,
  trustCalibrationUiSignal,
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

test("TrustClient.adjust sends an explicit trust mutation actor", async () => {
  let capturedBody: Record<string, unknown> | null = null;
  const restoreFetch = installFetch(async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({ ok: true, status: "applied", applied: true, level: 3 });
  });

  try {
    const client = new TrustClient("http://127.0.0.1:8000", { mutationsEnabled: true, retry: { retries: 0 } });
    const result = await client.adjust({ op: "set", value: 3, reason: "test" });

    assert.equal(result.ok, true);
    assert.equal(result.level, 3);
    assert.equal(capturedBody?.op, "set");
    assert.equal(capturedBody?.actor, "chat_ui.trust");
  } finally {
    restoreFetch();
  }
});

test("TrustClient.adjust treats backend denials as mutation errors", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({ ok: false, status: "denied", error: "api_permission_denied" }),
  );

  try {
    const client = new TrustClient("http://127.0.0.1:8000", { mutationsEnabled: true, retry: { retries: 0 } });

    await assert.rejects(
      () => client.adjust({ op: "set", value: 3, actor: "chat_ui.trust" }),
      (err: unknown) => err instanceof TrustApiError && err.message === "api_permission_denied",
    );
  } finally {
    restoreFetch();
  }
});

test("TrustClient.evaluateClaim parses calibrated UI state without enabling mutations", async () => {
  let capturedUrl = "";
  let capturedMethod = "";
  let capturedBody: Record<string, unknown> | null = null;
  const restoreFetch = installFetch(async (url, init) => {
    capturedUrl = url;
    capturedMethod = String(init?.method ?? "GET");
    capturedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({
      ok: true,
      status: "evaluated",
      claim_strength: "blocked",
      requested_claim_strength: "confirmed",
      downgraded: true,
      reason: "blocked_state_readback",
      condition: "current_readback_reports_blocked",
      ui_state: "blocked_signal_required",
      surface_obligation: "state_blocker_before_progress",
      citation_obligation: "cite_current_blocking_readback",
      missing_verification: ["blocked_state_resolution"],
      allowed_surface_language: ["blocked until live readback clears"],
      forbidden_surface_language: ["done", "closed", "ready"],
      next_smallest_truthful_gap: "stage13_ui_state_coherence",
      runtime_claim_integration_ready: true,
      evaluates_supplied_evidence_only: true,
      writes_memory: false,
      writes_receipts: false,
      scores_model_output: false,
      changes_ui_confidence: false,
      enforces_runtime_claims: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      governance: {
        read_only: true,
      },
    });
  });

  try {
    const client = new TrustClient("http://127.0.0.1:8000", { retry: { retries: 0 } });
    const evaluation = await client.evaluateClaim({
      claim_text: "Stage 13 is done",
      claim_scope: "stage13",
      requested_claim_strength: "confirmed",
      evidence: {
        current_readback_reports_blocked: true,
        missing_verification: ["live_ui_readback"],
      },
    });

    assert.equal(capturedUrl, "http://127.0.0.1:8000/trust-calibration/evaluate-claim");
    assert.equal(capturedMethod, "POST");
    assert.equal(capturedBody?.claim_text, "Stage 13 is done");
    assert.equal(capturedBody?.claim_scope, "stage13");
    assert.equal(capturedBody?.requested_claim_strength, "confirmed");
    assert.deepEqual(capturedBody?.evidence, {
      current_readback_reports_blocked: true,
      missing_verification: ["live_ui_readback"],
    });

    assert.equal(evaluation.ok, true);
    assert.equal(evaluation.claim_strength, "blocked");
    assert.equal(evaluation.requested_claim_strength, "confirmed");
    assert.equal(evaluation.downgraded, true);
    assert.equal(evaluation.ui_state, "blocked_signal_required");
    assert.deepEqual(evaluation.missing_verification, ["blocked_state_resolution"]);
    assert.deepEqual(evaluation.forbidden_surface_language, ["done", "closed", "ready"]);
    assert.equal(evaluation.evaluates_supplied_evidence_only, true);
    assert.equal(evaluation.writes_memory, false);
    assert.equal(evaluation.writes_receipts, false);
    assert.equal(evaluation.changes_ui_confidence, false);
    assert.equal(evaluation.grants_execution_authority, false);
    assert.equal(evaluation.grants_mutation_authority, false);
    assert.equal(trustCalibrationUiSignal(evaluation), "blocked");
  } finally {
    restoreFetch();
  }
});

test("TrustClient.evaluateClaim rejects malformed calibration responses", async () => {
  const restoreFetch = installFetch(async () => jsonResponse({ ok: true, status: "evaluated" }));

  try {
    const client = new TrustClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    await assert.rejects(
      () =>
        client.evaluateClaim({
          claim_text: "Runtime is ready",
          evidence: { supporting_evidence: true },
        }),
      (err: unknown) =>
        err instanceof TrustApiError && err.message === "Invalid trust calibration claim evaluation response.",
    );
  } finally {
    restoreFetch();
  }
});

test("TrustClient reads Stage 13 completion review and closure receipts without mutations", async () => {
  const capturedUrls: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    capturedUrls.push(url);
    if (url.endsWith("/trust-calibration/completion-review")) {
      return jsonResponse({
        ok: true,
        status: "blocked",
        stage13_completion_review_ready: false,
        stage_closure_decision_required: false,
        stage13_closed_by_receipt: false,
        operator_browser_visual_readback_observed: false,
        latest_operator_browser_visual_readback_receipt_id: "",
        ready_count: 6,
        required_count: 7,
        blockers: ["operator_browser_visual_readback_observed", "all_deliverables_ready"],
        next_smallest_truthful_gap: "stage13_operator_browser_visual_readback",
        reads_receipts: true,
        writes_receipts: false,
        writes_memory: false,
        runs_tools: false,
        runs_shell: false,
        runs_git: false,
        launches_browser: false,
        captures_screen: false,
        marks_stage_closed: false,
        grants_execution_authority: false,
        grants_mutation_authority: false,
      });
    }
    return jsonResponse({
      ok: true,
      status: "empty",
      count: 0,
      latest_receipt_id: "",
      latest_decision: "",
      stage13_closed_by_receipt: false,
      reads_receipts: true,
      writes_receipts: false,
      writes_memory: false,
      runs_tools: false,
      runs_shell: false,
      runs_git: false,
      launches_browser: false,
      captures_screen: false,
      marks_runtime_stage_state: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      next_smallest_truthful_gap: "stage13_completion_review",
    });
  });

  try {
    const client = new TrustClient("http://127.0.0.1:8000", { retry: { retries: 0 } });
    const review = await client.getTrustCalibrationCompletionReview();
    const closure = await client.getTrustCalibrationStageClosureDecisions({ limit: 10 });

    assert.deepEqual(capturedUrls, [
      "http://127.0.0.1:8000/trust-calibration/completion-review",
      "http://127.0.0.1:8000/trust-calibration/stage-closure-decisions?limit=10",
    ]);
    assert.equal(review.status, "blocked");
    assert.equal(review.stage13_completion_review_ready, false);
    assert.equal(review.stage_closure_decision_required, false);
    assert.equal(review.ready_count, 6);
    assert.equal(review.required_count, 7);
    assert.deepEqual(review.blockers, ["operator_browser_visual_readback_observed", "all_deliverables_ready"]);
    assert.equal(review.writes_receipts, false);
    assert.equal(review.writes_memory, false);
    assert.equal(review.runs_shell, false);
    assert.equal(review.launches_browser, false);
    assert.equal(review.captures_screen, false);
    assert.equal(review.marks_stage_closed, false);

    assert.equal(closure.status, "empty");
    assert.equal(closure.stage13_closed_by_receipt, false);
    assert.equal(closure.latest_receipt_id, "");
    assert.equal(closure.writes_receipts, false);
    assert.equal(closure.writes_memory, false);
    assert.equal(closure.runs_git, false);
    assert.equal(closure.next_smallest_truthful_gap, "stage13_completion_review");
  } finally {
    restoreFetch();
  }
});

test("TrustClient records explicit browser visual readback through opt-in mutation path", async () => {
  let capturedUrl = "";
  let capturedMethod = "";
  let capturedBody: Record<string, unknown> | null = null;
  const restoreFetch = installFetch(async (url, init) => {
    capturedUrl = url;
    capturedMethod = String(init?.method ?? "GET");
    capturedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({
      ok: true,
      status: "recorded",
      receipt_id: "trust_calibration_browser_visual_ui_test",
      actor: "chat_ui.trust_calibration",
      reason: "operator_clicked_stage13_browser_visual_readback_in_orb_shell",
      operator_browser_visual_readback_observed: true,
      claim_guard_visible: true,
      missing_verification_visible: true,
      forbidden_language_visible: true,
      side_effect_guard_visible: true,
      next_gap_visible: true,
      writes_receipt: true,
      writes_memory: false,
      runs_tools: false,
      runs_shell: false,
      runs_git: false,
      launches_browser: false,
      captures_screen: false,
      grants_execution_authority: false,
      grants_mutation_authority: false,
      next_smallest_truthful_gap: "stage13_completion_review",
      governance: {
        required_scope: "trust_calibration.browser_visual_readback.write",
        records_supplied_visual_readback_only: true,
      },
    });
  });

  try {
    const readOnlyClient = new TrustClient("http://127.0.0.1:8000", { retry: { retries: 0 } });
    await assert.rejects(
      () =>
        readOnlyClient.recordTrustCalibrationOperatorBrowserVisualReadback({
          reason: "blocked",
          claim_guard_visible: true,
          missing_verification_visible: true,
          forbidden_language_visible: true,
          side_effect_guard_visible: true,
          next_gap_visible: true,
        }),
      /mutationsEnabled=false/,
    );

    const client = new TrustClient("http://127.0.0.1:8000", { mutationsEnabled: true, retry: { retries: 0 } });
    const receipt = await client.recordTrustCalibrationOperatorBrowserVisualReadback({
      actor: "chat_ui.trust_calibration",
      reason: "operator_clicked_stage13_browser_visual_readback_in_orb_shell",
      claim_text: "Stage 13 trust calibration claim state is visible in the operator shell",
      surface_id: "francis-trust-calibration",
      browser_name: "test browser",
      viewport: "1440x1200",
      artifact_paths: [],
      claim_guard_visible: true,
      missing_verification_visible: true,
      forbidden_language_visible: true,
      side_effect_guard_visible: true,
      next_gap_visible: true,
    });

    assert.equal(capturedUrl, "http://127.0.0.1:8000/trust-calibration/operator-browser-visual-readback");
    assert.equal(capturedMethod, "POST");
    assert.equal(capturedBody?.actor, "chat_ui.trust_calibration");
    assert.equal(capturedBody?.surface_id, "francis-trust-calibration");
    assert.equal(capturedBody?.claim_guard_visible, true);
    assert.equal(capturedBody?.missing_verification_visible, true);
    assert.equal(receipt.ok, true);
    assert.equal(receipt.receipt_id, "trust_calibration_browser_visual_ui_test");
    assert.equal(receipt.operator_browser_visual_readback_observed, true);
    assert.equal(receipt.writes_receipt, true);
    assert.equal(receipt.writes_memory, false);
    assert.equal(receipt.runs_tools, false);
    assert.equal(receipt.runs_shell, false);
    assert.equal(receipt.launches_browser, false);
    assert.equal(receipt.captures_screen, false);
    assert.equal(receipt.grants_execution_authority, false);
    assert.equal(receipt.grants_mutation_authority, false);
    assert.equal(receipt.governance?.required_scope, "trust_calibration.browser_visual_readback.write");
  } finally {
    restoreFetch();
  }
});

test("presentTrustCalibrationClaimEvaluation preserves blocked and missing-verification obligations", () => {
  const presentation = presentTrustCalibrationClaimEvaluation({
    ok: true,
    status: "evaluated",
    claim_strength: "blocked",
    requested_claim_strength: "confirmed",
    downgraded: true,
    reason: "current_readback_reports_blocked",
    condition: "blocked_state_readback",
    ui_state: "blocked_signal_required",
    surface_obligation: "state_blocker_before_progress",
    citation_obligation: "cite_current_blocking_readback",
    missing_verification: ["blocked_state_resolution"],
    allowed_surface_language: ["blocked until live readback clears"],
    forbidden_surface_language: ["done", "closed", "ready"],
    next_smallest_truthful_gap: "stage13_ui_state_coherence",
    runtime_claim_integration_ready: true,
    evaluates_supplied_evidence_only: true,
    writes_memory: false,
    writes_receipts: false,
    scores_model_output: false,
    changes_ui_confidence: false,
    enforces_runtime_claims: false,
    grants_execution_authority: false,
    grants_mutation_authority: false,
  });

  assert.equal(presentation.signal, "blocked");
  assert.equal(presentation.badge_status, "blocked");
  assert.equal(presentation.headline, "Blocked; progress claim denied");
  assert.equal(presentation.detail, "current_readback_reports_blocked");
  assert.equal(presentation.strong_claim_allowed, false);
  assert.equal(presentation.blocked_claim_required, true);
  assert.equal(presentation.must_name_missing_verification, true);
  assert.equal(presentation.side_effects_denied, true);
  assert.deepEqual(presentation.forbidden_surface_language, ["done", "closed", "ready"]);
  assert.deepEqual(presentation.missing_verification, ["blocked_state_resolution"]);
});

test("presentTrustCalibrationClaimEvaluation does not fabricate confidence before readback", () => {
  const presentation = presentTrustCalibrationClaimEvaluation(null);

  assert.equal(presentation.signal, "missing");
  assert.equal(presentation.badge_status, "dormant");
  assert.equal(presentation.badge_label, "not loaded");
  assert.equal(presentation.strong_claim_allowed, false);
  assert.equal(presentation.blocked_claim_required, false);
  assert.equal(presentation.must_name_missing_verification, true);
  assert.equal(presentation.runtime_claim_integration_ready, false);
  assert.equal(presentation.next_smallest_truthful_gap, "stage13_ui_state_coherence");
  assert.deepEqual(presentation.missing_verification, ["trust_calibration_claim_evaluation"]);
  assert.deepEqual(presentation.forbidden_surface_language, ["done", "closed", "confirmed"]);
});
