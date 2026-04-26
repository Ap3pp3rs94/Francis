import assert from "node:assert/strict";
import test from "node:test";

import { ApprovalsApiError, ApprovalsClient } from "./index.ts";

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

test("ApprovalsClient.list preserves bounded approval projection fields", async () => {
  const requests: string[] = [];
  const restoreFetch = installFetch(async (url) => {
    requests.push(new URL(url).pathname + new URL(url).search);
    return jsonResponse({
      items: [
        {
          id: "apr_projection",
          ts: 1710000456,
          action: "plugin.run",
          reason: "Deploy production plugin step",
          status: "pending",
          request_kind: "plugin.run.request",
          previous_approval_id: "apr_old",
          previous_approval_status: "approved",
          replacement_kind: "plugin.run.mismatch",
          replacement_reason: "approval_payload_mismatch",
          replacement_expected_payload_keys: ["action", "input", "plugin_id"],
          replacement_previous_payload_keys: ["action", "input", "plugin_id"],
          replacement_changed_keys: ["input"],
          operation_id: "tsk_projection",
          mission_id: "msn_projection",
          operation_status: "queued",
          operation_result_status: "needs_approval",
          gate: "approvals_gate",
          next_step: "approve_exact_action",
          trace_id: "trace_projection",
          run_id: "run_projection",
          artifact_dir: "D:/Francis/.data/artifacts/supervised_exec/run_projection",
          payload_summary: {
            requested_action: "deploy",
            plugin_id: "plugin.deploy",
            risk_tier: "critical",
            required_trust: 5,
            input_keys: ["target"],
            params_keys: ["region"],
          },
        },
      ],
    });
  });

  try {
    const client = new ApprovalsClient("http://127.0.0.1:8000");
    const result = await client.list({ status: "pending", limit: 20 });

    assert.deepEqual(requests, ["/approvals/list?status=pending&limit=20"]);
    assert.equal(result.items.length, 1);
    assert.equal(result.items[0]?.request_kind, "plugin.run.request");
    assert.equal(result.items[0]?.previous_approval_id, "apr_old");
    assert.equal(result.items[0]?.replacement_kind, "plugin.run.mismatch");
    assert.equal(result.items[0]?.replacement_reason, "approval_payload_mismatch");
    assert.deepEqual(result.items[0]?.replacement_expected_payload_keys, ["action", "input", "plugin_id"]);
    assert.deepEqual(result.items[0]?.replacement_previous_payload_keys, ["action", "input", "plugin_id"]);
    assert.deepEqual(result.items[0]?.replacement_changed_keys, ["input"]);
    assert.equal(result.items[0]?.operation_id, "tsk_projection");
    assert.equal(result.items[0]?.mission_id, "msn_projection");
    assert.equal(result.items[0]?.operation_status, "queued");
    assert.equal(result.items[0]?.operation_result_status, "needs_approval");
    assert.equal(result.items[0]?.gate, "approvals_gate");
    assert.equal(result.items[0]?.next_step, "approve_exact_action");
    assert.equal(result.items[0]?.trace_id, "trace_projection");
    assert.equal(result.items[0]?.run_id, "run_projection");
    assert.equal(result.items[0]?.artifact_dir, "D:/Francis/.data/artifacts/supervised_exec/run_projection");
    assert.equal(result.items[0]?.payload_summary?.requested_action, "deploy");
    assert.equal(result.items[0]?.payload_summary?.plugin_id, "plugin.deploy");
    assert.equal(result.items[0]?.payload_summary?.required_trust, 5);
    assert.deepEqual(result.items[0]?.payload_summary?.input_keys, ["target"]);
    assert.deepEqual(result.items[0]?.payload_summary?.params_keys, ["region"]);
  } finally {
    restoreFetch();
  }
});

test("ApprovalsClient.decide sends an explicit approval actor", async () => {
  let capturedBody: Record<string, unknown> | null = null;
  const restoreFetch = installFetch(async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({ ok: true, status: "approved", item: { id: "apr_1", ts: 1, action: "plugin.run", status: "approved" } });
  });

  try {
    const client = new ApprovalsClient("http://127.0.0.1:8000");
    const result = await client.decide({ id: "apr_1", action: "approve" });

    assert.equal(result.ok, true);
    assert.equal(capturedBody?.id, "apr_1");
    assert.equal(capturedBody?.action, "approve");
    assert.equal(capturedBody?.actor, "chat_ui.approvals");
  } finally {
    restoreFetch();
  }
});

test("ApprovalsClient.decide treats backend denials as decision errors", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({ ok: false, status: "denied", error: "api_permission_denied" }),
  );

  try {
    const client = new ApprovalsClient("http://127.0.0.1:8000");

    await assert.rejects(
      () => client.decide({ id: "apr_denied", action: "approve", actor: "chat_ui.approvals" }),
      (err: unknown) => err instanceof ApprovalsApiError && err.message === "api_permission_denied",
    );
  } finally {
    restoreFetch();
  }
});
