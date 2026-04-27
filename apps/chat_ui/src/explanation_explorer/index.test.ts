import assert from "node:assert/strict";
import test from "node:test";

import { ExplanationClient } from "./index.ts";

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

test("ExplanationClient.list requests trace and artifact filters", async () => {
  const requests: Array<{
    path: string;
    missionId: string | null;
    operationId: string | null;
    traceId: string | null;
    artifactDir: string | null;
    approvalId: string | null;
    limit: string | null;
    method: string;
  }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      missionId: parsed.searchParams.get("mission_id"),
      operationId: parsed.searchParams.get("operation_id"),
      traceId: parsed.searchParams.get("trace_id"),
      artifactDir: parsed.searchParams.get("artifact_dir"),
      approvalId: parsed.searchParams.get("approval_id"),
      limit: parsed.searchParams.get("limit"),
      method: (init?.method ?? "GET").toUpperCase(),
    });

    return jsonResponse({
      items: [
        {
          id: "exp-trace-alpha",
          ts: 1_700_000_001,
          kind: "tool_trace",
          severity: "info",
          title: "Tool trace",
          trace_id: "trace_alpha",
          artifact_dir: "runs/run_alpha/artifacts",
          domain: "operations",
          operation_status: "succeeded",
          operation_error: "plugin_id_required",
          result_message: "Plugin id is required.",
          recovery_next_step: "review_operation_detail",
          current_task_source: "terminal_operation_receipt",
          current_task_operation_name: "plan.create",
          current_task_operation_plane: "P9_OBSERVABILITY",
          current_task_advance_action: "run_linked_operation",
          current_task_gate: "operator_review",
          current_task_next_step: "review_completed_mission",
          plan_status: "in_progress",
          plan_current_step_id: "understand",
          plan_current_step_title: "Understand goal + constraints",
          plan_step_count: "4",
          plan_checkpoint_count: 3,
          references: {
            mission_id: "msn_alpha",
            operation_id: "tsk_alpha",
            approval_id: "apr_alpha",
            trace_id: "trace_alpha",
            run_id: "run_alpha",
            artifact_dir: "runs/run_alpha/artifacts",
          },
          meta: {
            run_id: "run_alpha",
            mission_id: "msn_alpha",
            operation_id: "tsk_alpha",
            approval_id: "apr_alpha",
          },
        },
      ],
    });
  });

  try {
    const client = new ExplanationClient("http://127.0.0.1:8000");
    const response = await client.list({
      mission_id: "msn_alpha",
      operation_id: "tsk_alpha",
      trace_id: "trace_alpha",
      artifact_dir: "runs/run_alpha/artifacts",
      approval_id: "apr_alpha",
      limit: 25,
      timeoutMs: 50,
    });

    assert.deepEqual(requests, [
      {
        path: "/explanations/list",
        missionId: "msn_alpha",
        operationId: "tsk_alpha",
        traceId: "trace_alpha",
        artifactDir: "runs/run_alpha/artifacts",
        approvalId: "apr_alpha",
        limit: "25",
        method: "GET",
      },
    ]);
    assert.equal(response.items.length, 1);
    assert.equal(response.items[0]?.id, "exp-trace-alpha");
    assert.equal(response.items[0]?.trace_id, "trace_alpha");
    assert.equal(response.items[0]?.run_id, "run_alpha");
    assert.equal(response.items[0]?.mission_id, "msn_alpha");
    assert.equal(response.items[0]?.operation_id, "tsk_alpha");
    assert.equal(response.items[0]?.approval_id, "apr_alpha");
    assert.equal(response.items[0]?.artifact_dir, "runs/run_alpha/artifacts");
    assert.equal(response.items[0]?.operation_status, "succeeded");
    assert.equal(response.items[0]?.operation_error, "plugin_id_required");
    assert.equal(response.items[0]?.result_message, "Plugin id is required.");
    assert.equal(response.items[0]?.recovery_next_step, "review_operation_detail");
    assert.equal(response.items[0]?.current_task_source, "terminal_operation_receipt");
    assert.equal(response.items[0]?.current_task_operation_id, "tsk_alpha");
    assert.equal(response.items[0]?.current_task_operation_name, "plan.create");
    assert.equal(response.items[0]?.current_task_operation_plane, "P9_OBSERVABILITY");
    assert.equal(response.items[0]?.current_task_advance_action, "run_linked_operation");
    assert.equal(response.items[0]?.current_task_gate, "operator_review");
    assert.equal(response.items[0]?.current_task_trace_id, "trace_alpha");
    assert.equal(response.items[0]?.current_task_run_id, "run_alpha");
    assert.equal(response.items[0]?.current_task_artifact_dir, "runs/run_alpha/artifacts");
    assert.equal(response.items[0]?.current_task_next_step, "review_completed_mission");
    assert.equal(response.items[0]?.plan_status, "in_progress");
    assert.equal(response.items[0]?.plan_current_step_id, "understand");
    assert.equal(response.items[0]?.plan_current_step_title, "Understand goal + constraints");
    assert.equal(response.items[0]?.plan_step_count, 4);
    assert.equal(response.items[0]?.plan_checkpoint_count, 3);
    assert.deepEqual(response.items[0]?.references, {
      mission_id: "msn_alpha",
      operation_id: "tsk_alpha",
      approval_id: "apr_alpha",
      trace_id: "trace_alpha",
      run_id: "run_alpha",
      artifact_dir: "runs/run_alpha/artifacts",
    });
  } finally {
    restoreFetch();
  }
});

test("ExplanationClient.get and export preserve receipt linkage", async () => {
  const requests: Array<{
    path: string;
    id: string | null;
    missionId: string | null;
    operationId: string | null;
    traceId: string | null;
    artifactDir: string | null;
    approvalId: string | null;
    method: string;
  }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      id: parsed.searchParams.get("id"),
      missionId: parsed.searchParams.get("mission_id"),
      operationId: parsed.searchParams.get("operation_id"),
      traceId: parsed.searchParams.get("trace_id"),
      artifactDir: parsed.searchParams.get("artifact_dir"),
      approvalId: parsed.searchParams.get("approval_id"),
      method: (init?.method ?? "GET").toUpperCase(),
    });

    if (parsed.pathname === "/explanations/export") {
      return jsonResponse({ items: [] });
    }

    return jsonResponse({
      ok: true,
      item: {
        id: "exp-trace-detail",
        ts: 1_700_000_002,
        kind: "audit",
        trace_id: "trace_detail",
        artifact_dir: "runs/run_detail/artifacts",
        loop: {
          operation_error: "approval_pending",
          result_message: "Operation is waiting on approval.",
          recovery_next_step: "review_pending_approval",
          plan_status: "in_progress",
          plan_current_step_id: "understand",
          plan_current_step_title: "Understand goal + constraints",
          plan_step_count: 4,
          plan_checkpoint_count: "3",
        },
        current_task_operation_name: "plan.create",
        current_task_operation_plane: "P9_OBSERVABILITY",
        current_task_advance_action: "run_linked_operation",
        meta: {
          mission_id: "msn_detail",
          operation_id: "tsk_detail",
          approval_id: "apr_detail",
        },
      },
      content: { outcome: "linked" },
    });
  });

  try {
    const client = new ExplanationClient("http://127.0.0.1:8000");
    const detail = await client.get("exp-trace-detail", { timeoutMs: 50 });
    await client.export("json", {
      mission_id: "msn_detail",
      operation_id: "tsk_detail",
      trace_id: "trace_detail",
      artifact_dir: "runs/run_detail/artifacts",
      approval_id: "apr_detail",
      timeoutMs: 50,
    });

    assert.equal(detail?.trace_id, "trace_detail");
    assert.equal(detail?.artifact_dir, "runs/run_detail/artifacts");
    assert.equal(detail?.mission_id, "msn_detail");
    assert.equal(detail?.operation_id, "tsk_detail");
    assert.equal(detail?.approval_id, "apr_detail");
    assert.equal(detail?.current_task_operation_name, "plan.create");
    assert.equal(detail?.current_task_operation_plane, "P9_OBSERVABILITY");
    assert.equal(detail?.current_task_advance_action, "run_linked_operation");
    assert.equal(detail?.plan_status, "in_progress");
    assert.equal(detail?.plan_current_step_id, "understand");
    assert.equal(detail?.plan_current_step_title, "Understand goal + constraints");
    assert.equal(detail?.plan_step_count, 4);
    assert.equal(detail?.plan_checkpoint_count, 3);
    assert.equal(detail?.operation_error, "approval_pending");
    assert.equal(detail?.result_message, "Operation is waiting on approval.");
    assert.equal(detail?.recovery_next_step, "review_pending_approval");
    assert.deepEqual(requests, [
      {
        path: "/explanations/get",
        id: "exp-trace-detail",
        missionId: null,
        operationId: null,
        traceId: null,
        artifactDir: null,
        approvalId: null,
        method: "GET",
      },
      {
        path: "/explanations/export",
        id: null,
        missionId: "msn_detail",
        operationId: "tsk_detail",
        traceId: "trace_detail",
        artifactDir: "runs/run_detail/artifacts",
        approvalId: "apr_detail",
        method: "GET",
      },
    ]);
  } finally {
    restoreFetch();
  }
});
