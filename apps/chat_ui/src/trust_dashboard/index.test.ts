import assert from "node:assert/strict";
import test from "node:test";

import { TrustApiError, TrustClient, trustCalibrationUiSignal } from "./index.ts";

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
