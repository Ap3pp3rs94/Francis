import assert from "node:assert/strict";
import test from "node:test";

import { TakeoverClient, parseTakeoverStatusSnapshot } from "./index.ts";

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

test("parseTakeoverStatusSnapshot preserves handback proof handles", () => {
  const parsed = parseTakeoverStatusSnapshot({
    ok: true,
    kind: "francis.stage9.takeover.status",
    stage: "Stage 9 / Takeover (Pilot Mode)",
    status: "ready",
    stage8_closed_by_receipt: true,
    stage8_latest_receipt_id: "exec_stage8_closure_alpha",
    control_mode: { id: "assist", label: "Assist" },
    control_transfer_active: false,
    handback_summary_ready: true,
    latest_control_transfer_receipt: {
      kind: "francis.stage9.takeover.control_transfer_receipt",
      receipt_id: "takeover_transfer_alpha",
      session_id: "pilot_alpha",
      scope: "bounded proof",
      stage8_closure_receipt_id: "exec_stage8_closure_alpha",
      action_feed_operation_ids: ["tsk_alpha"],
    },
    latest_panic_stop_receipt: {
      kind: "francis.stage9.takeover.panic_stop_receipt",
      receipt_id: "takeover_panic_alpha",
      session_id: "pilot_alpha",
      revoked_control_transfer: true,
    },
    latest_handback_summary_receipt: {
      kind: "francis.stage9.takeover.handback_summary_receipt",
      receipt_id: "takeover_handback_alpha",
      session_id: "pilot_alpha",
      control_transfer_receipt_id: "takeover_transfer_alpha",
      panic_stop_receipt_id: "takeover_panic_alpha",
      summary: "Control returned",
      validation_outcome: "tests passed",
      remaining_uncertainty: "ci pending",
      next_recommendation: "surface in UI",
      changed_artifacts: ["D:/Francis/file.py"],
      trace_ids: ["trace_alpha"],
      run_ids: ["run_alpha"],
      control_transferred_back: true,
    },
    action_feed: {
      items: [
        {
          id: "tsk_alpha",
          ts: 1_800_000_000,
          status: "succeeded",
          name: "plan.create",
          trace_id: "trace_alpha",
          run_id: "run_alpha",
          artifact_dir: "D:/Francis/file.py",
          objective: "Advance pilot work",
        },
      ],
      count: 1,
    },
    deliverables: {
      control_transfer_flow: true,
      live_action_feed: true,
      panic_stop: true,
      handback_summary: true,
      pilot_visibility: true,
    },
    next_smallest_truthful_gap: "stage9_operator_surface_contract",
  });

  assert.equal(parsed.ok, true);
  assert.equal(parsed.status, "ready");
  assert.equal(parsed.stage8_latest_receipt_id, "exec_stage8_closure_alpha");
  assert.equal(parsed.latest_control_transfer_receipt?.receipt_id, "takeover_transfer_alpha");
  assert.equal(parsed.latest_control_transfer_receipt?.action_feed_operation_ids?.[0], "tsk_alpha");
  assert.equal(parsed.latest_panic_stop_receipt?.receipt_id, "takeover_panic_alpha");
  assert.equal(parsed.latest_handback_summary_receipt?.receipt_id, "takeover_handback_alpha");
  assert.equal(parsed.latest_handback_summary_receipt?.control_transfer_receipt_id, "takeover_transfer_alpha");
  assert.equal(parsed.latest_handback_summary_receipt?.panic_stop_receipt_id, "takeover_panic_alpha");
  assert.equal(parsed.latest_handback_summary_receipt?.changed_artifacts?.[0], "D:/Francis/file.py");
  assert.equal(parsed.latest_handback_summary_receipt?.trace_ids?.[0], "trace_alpha");
  assert.equal(parsed.action_feed?.items[0]?.id, "tsk_alpha");
  assert.equal(parsed.action_feed?.items[0]?.meta?.objective, "Advance pilot work");
  assert.equal(parsed.deliverables?.handback_summary, true);
  assert.equal(parsed.next_smallest_truthful_gap, "stage9_operator_surface_contract");
});

test("TakeoverClient.getStatus requests the bounded takeover status route", async () => {
  const requests: Array<{ path: string; limit: string | null; method: string }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      limit: parsed.searchParams.get("limit"),
      method: (init?.method ?? "GET").toUpperCase(),
    });
    return jsonResponse({
      ok: true,
      status: "pilot_active",
      control_mode: { id: "pilot", label: "Pilot" },
      control_transfer_active: true,
      latest_control_transfer_receipt: {
        receipt_id: "takeover_transfer_beta",
        session_id: "pilot_beta",
      },
      action_feed: { items: [] },
    });
  });

  try {
    const client = new TakeoverClient("http://127.0.0.1:8000/");
    const response = await client.getStatus({ limit: 16 }, { timeoutMs: 50 });

    assert.deepEqual(requests, [{ path: "/takeover/status", limit: "16", method: "GET" }]);
    assert.equal(response.status, "pilot_active");
    assert.equal(response.control_mode?.id, "pilot");
    assert.equal(response.latest_control_transfer_receipt?.receipt_id, "takeover_transfer_beta");
  } finally {
    restoreFetch();
  }
});
