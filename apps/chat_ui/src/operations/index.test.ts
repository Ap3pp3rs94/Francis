import assert from "node:assert/strict";
import test from "node:test";

import { OperationsClient, parseOperationRecord } from "./index.ts";

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

function jsonRequestBody(init?: RequestInit): unknown {
  const body = init?.body;
  if (typeof body !== "string" || !body.trim()) return undefined;
  return JSON.parse(body) as unknown;
}

test("OperationsClient.list requests receipt handle filters and preserves returned handles", async () => {
  const requests: Array<{
    path: string;
    approvalId: string | null;
    traceId: string | null;
    runId: string | null;
    artifactDir: string | null;
    method: string;
  }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      approvalId: parsed.searchParams.get("approval_id"),
      traceId: parsed.searchParams.get("trace_id"),
      runId: parsed.searchParams.get("run_id"),
      artifactDir: parsed.searchParams.get("artifact_dir"),
      method: (init?.method ?? "GET").toUpperCase(),
    });

    return jsonResponse({
      items: [
        {
          id: "task_trace_alpha",
          ts: 1_710_000_100,
          status: "succeeded",
          name: "plugin.run",
          meta: { approval_id: "apr_task_alpha" },
          trace_id: "trace_task_alpha",
          run_id: "run_task_alpha",
          artifact_dir: "D:/francis/data/artifacts/task_trace_alpha",
        },
      ],
    });
  });

  try {
    const client = new OperationsClient("http://127.0.0.1:8000");
    const response = await client.list(
      {
        approval_id: "apr_task_alpha",
        trace_id: "trace_task_alpha",
        run_id: "run_task_alpha",
        artifact_dir: "D:/francis/data/artifacts/task_trace_alpha",
      },
      { timeoutMs: 50 },
    );

    assert.deepEqual(requests, [
      {
        path: "/operations/list",
        approvalId: "apr_task_alpha",
        traceId: "trace_task_alpha",
        runId: "run_task_alpha",
        artifactDir: "D:/francis/data/artifacts/task_trace_alpha",
        method: "GET",
      },
    ]);
    assert.equal(response.items[0]?.id, "task_trace_alpha");
    assert.equal(response.items[0]?.meta?.approval_id, "apr_task_alpha");
    assert.equal(response.items[0]?.trace_id, "trace_task_alpha");
    assert.equal(response.items[0]?.run_id, "run_task_alpha");
    assert.equal(response.items[0]?.artifact_dir, "D:/francis/data/artifacts/task_trace_alpha");
  } finally {
    restoreFetch();
  }
});

test("parseOperationRecord preserves trace handles from operation metadata", () => {
  const parsed = parseOperationRecord({
    id: "task_meta_handles",
    ts: 1_710_000_120,
    status: "succeeded",
    name: "plugin.run",
    meta: {
      trace_id: "trace_meta_alpha",
    },
    input: {
      meta: {
        run_id: "run_input_meta_alpha",
        artifact_dir: "D:/francis/data/artifacts/meta-alpha",
      },
    },
    output: {
      approval_id: "apr_output_meta_alpha",
    },
  });

  assert.equal(parsed?.id, "task_meta_handles");
  assert.equal(parsed?.approval_id, "apr_output_meta_alpha");
  assert.equal(parsed?.trace_id, "trace_meta_alpha");
  assert.equal(parsed?.run_id, "run_input_meta_alpha");
  assert.equal(parsed?.artifact_dir, "D:/francis/data/artifacts/meta-alpha");
});

test("parseOperationRecord preserves plan revision summaries", () => {
  const parsed = parseOperationRecord({
    id: "task_plan_revision",
    ts: 1_710_000_130,
    status: "succeeded",
    name: "plan.revise",
    output: {
      kind: "plan.revise.result",
      plan_status: "revised",
      plan_current_step_id: "understand",
      plan_current_step_title: "Understand goal + constraints",
      plan_step_count: 7,
      plan_checkpoint_count: 3,
    },
  });

  assert.equal(parsed?.plan_summary?.kind, "plan.revise.result");
  assert.equal(parsed?.plan_summary?.status, "revised");
  assert.equal(parsed?.plan_summary?.current_step_id, "understand");
  assert.equal(parsed?.plan_summary?.current_step_title, "Understand goal + constraints");
  assert.equal(parsed?.plan_summary?.step_count, 7);
  assert.equal(parsed?.plan_summary?.checkpoint_count, 3);
});

test("OperationsClient.run posts the bounded worker request to the operation run route", async () => {
  const requests: Array<{ path: string; method: string; body: unknown }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const path = new URL(url).pathname;
    requests.push({
      path,
      method: (init?.method ?? "GET").toUpperCase(),
      body: jsonRequestBody(init),
    });

    return jsonResponse({
      ok: true,
      status: "running",
      message: "operation_started",
      operation: {
        id: "task_alpha",
        ts: 1_710_000_100,
        status: "running",
        name: "plan.create",
        trace_id: "trace_task_alpha",
        run_id: "run_task_alpha",
        artifact_dir: "D:/francis/data/artifacts/task_alpha",
        output: {
          kind: "plan.create.result",
          plan_status: "in_progress",
          plan_current_step_id: "understand",
          plan_current_step_title: "Understand goal + constraints",
          plan_step_count: 4,
          plan_checkpoint_count: 3,
        },
        meta: {
          objective: "Advance morning continuity",
          orb_plane: "P7_EXECUTION",
          run_id: "run_task_alpha",
        },
      },
      memory_receipt: {
        source: "continuity.ledger",
        kind: "ledger_append",
        ts: 1770000300,
        role: "system",
        message: "Mission operation completed: mission=mission_alpha operation=task_alpha status=succeeded",
        scope: "mission.loop",
        operation_status: "succeeded",
        approval_status: "approved",
        capability: "plan.create",
        subsystem: "operations.runtime",
        current_task_operation_name: "plugin.run",
        current_task_operation_plane: "P7_EXECUTION",
        current_task_advance_action: "run_operation",
        plan_status: "in_progress",
        plan_current_step_id: "understand",
        plan_current_step_title: "Understand goal + constraints",
        plan_step_count: 4,
        plan_checkpoint_count: 3,
        references: {
          mission_id: "mission_alpha",
          operation_id: "task_alpha",
          trace_id: "trace_task_alpha",
          approval_id: "apr_task_alpha",
          run_id: "run_task_alpha",
          artifact_dir: "D:/francis/data/artifacts/task_alpha",
        },
      },
    });
  });

  try {
    const client = new OperationsClient("http://127.0.0.1:8000");
    const response = await client.run("task_alpha", { worker_id: "chat_ui.operations" }, { timeoutMs: 50 });

    assert.deepEqual(requests, [
      {
        path: "/operations/task_alpha/run",
        method: "POST",
        body: { worker_id: "chat_ui.operations" },
      },
    ]);
    assert.equal(response.ok, true);
    assert.equal(response.status, "running");
    assert.equal(response.message, "operation_started");
    assert.equal(response.operation?.id, "task_alpha");
    assert.equal(response.operation?.status, "running");
    assert.equal(response.operation?.trace_id, "trace_task_alpha");
    assert.equal(response.operation?.run_id, "run_task_alpha");
    assert.equal(response.operation?.artifact_dir, "D:/francis/data/artifacts/task_alpha");
    assert.equal(response.operation?.plan_summary?.kind, "plan.create.result");
    assert.equal(response.operation?.plan_summary?.status, "in_progress");
    assert.equal(response.operation?.plan_summary?.current_step_id, "understand");
    assert.equal(response.operation?.plan_summary?.current_step_title, "Understand goal + constraints");
    assert.equal(response.operation?.plan_summary?.step_count, 4);
    assert.equal(response.operation?.plan_summary?.checkpoint_count, 3);
    assert.equal(response.operation?.meta?.orb_plane, "P7_EXECUTION");
    assert.equal(response.memory_receipt?.source, "continuity.ledger");
    assert.equal(response.memory_receipt?.kind, "ledger_append");
    assert.equal(response.memory_receipt?.scope, "mission.loop");
    assert.equal(response.memory_receipt?.operation_status, "succeeded");
    assert.equal(response.memory_receipt?.approval_status, "approved");
    assert.equal(response.memory_receipt?.capability, "plan.create");
    assert.equal(response.memory_receipt?.subsystem, "operations.runtime");
    assert.equal(response.memory_receipt?.current_task_operation_name, "plugin.run");
    assert.equal(response.memory_receipt?.current_task_operation_plane, "P7_EXECUTION");
    assert.equal(response.memory_receipt?.current_task_advance_action, "run_operation");
    assert.equal(response.memory_receipt?.plan_status, "in_progress");
    assert.equal(response.memory_receipt?.plan_current_step_id, "understand");
    assert.equal(response.memory_receipt?.plan_current_step_title, "Understand goal + constraints");
    assert.equal(response.memory_receipt?.plan_step_count, 4);
    assert.equal(response.memory_receipt?.plan_checkpoint_count, 3);
    assert.equal(response.memory_receipt?.references?.mission_id, "mission_alpha");
    assert.equal(response.memory_receipt?.references?.operation_id, "task_alpha");
    assert.equal(response.memory_receipt?.references?.trace_id, "trace_task_alpha");
    assert.equal(response.memory_receipt?.references?.approval_id, "apr_task_alpha");
    assert.equal(response.memory_receipt?.references?.run_id, "run_task_alpha");
    assert.equal(response.memory_receipt?.references?.artifact_dir, "D:/francis/data/artifacts/task_alpha");
  } finally {
    restoreFetch();
  }
});

test("OperationsClient.get preserves operation memory receipt summaries", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({
      operation: {
        id: "task_memory_alpha",
        ts: 1_710_000_200,
        status: "succeeded",
        name: "plugin.run",
        meta: {
          mission_id: "mission_alpha",
          memory_receipt_count: 1,
          latest_memory_receipt: {
            source: "continuity.ledger",
            kind: "ledger_append",
            operation_status: "succeeded",
            references: {
              mission_id: "mission_alpha",
              operation_id: "task_memory_alpha",
              run_id: "run_memory_alpha",
            },
          },
        },
      },
      memory_receipt_count: 1,
      latest_memory_receipt: {
        source: "continuity.ledger",
        kind: "ledger_append",
        operation_status: "succeeded",
        current_task_operation_name: "plugin.run",
        current_task_operation_plane: "P7_EXECUTION",
        current_task_advance_action: "run_operation",
        plan_status: "in_progress",
        plan_current_step_id: "understand",
        plan_current_step_title: "Understand goal + constraints",
        plan_step_count: 4,
        plan_checkpoint_count: 3,
        references: {
          mission_id: "mission_alpha",
          operation_id: "task_memory_alpha",
          run_id: "run_memory_alpha",
        },
      },
      memory_receipts: [
        {
          source: "continuity.ledger",
          kind: "ledger_append",
          operation_status: "succeeded",
          current_task_operation_name: "plugin.run",
          current_task_operation_plane: "P7_EXECUTION",
          current_task_advance_action: "run_operation",
          plan_status: "in_progress",
          plan_current_step_id: "understand",
          plan_current_step_title: "Understand goal + constraints",
          plan_step_count: 4,
          plan_checkpoint_count: 3,
          references: {
            mission_id: "mission_alpha",
            operation_id: "task_memory_alpha",
            run_id: "run_memory_alpha",
          },
        },
      ],
    }),
  );

  try {
    const client = new OperationsClient("http://127.0.0.1:8000");
    const detail = await client.get("task_memory_alpha", { timeoutMs: 50 });

    assert.equal(detail?.operation.id, "task_memory_alpha");
    assert.equal(detail?.memory_receipt_count, 1);
    assert.equal(detail?.latest_memory_receipt?.source, "continuity.ledger");
    assert.equal(detail?.latest_memory_receipt?.references?.mission_id, "mission_alpha");
    assert.equal(detail?.latest_memory_receipt?.references?.operation_id, "task_memory_alpha");
    assert.equal(detail?.latest_memory_receipt?.references?.run_id, "run_memory_alpha");
    assert.equal(detail?.latest_memory_receipt?.current_task_operation_name, "plugin.run");
    assert.equal(detail?.latest_memory_receipt?.current_task_operation_plane, "P7_EXECUTION");
    assert.equal(detail?.latest_memory_receipt?.current_task_advance_action, "run_operation");
    assert.equal(detail?.latest_memory_receipt?.plan_status, "in_progress");
    assert.equal(detail?.latest_memory_receipt?.plan_current_step_id, "understand");
    assert.equal(detail?.latest_memory_receipt?.plan_current_step_title, "Understand goal + constraints");
    assert.equal(detail?.latest_memory_receipt?.plan_step_count, 4);
    assert.equal(detail?.latest_memory_receipt?.plan_checkpoint_count, 3);
    assert.equal(detail?.memory_receipts?.[0]?.references?.operation_id, "task_memory_alpha");
    assert.equal(detail?.memory_receipts?.[0]?.current_task_operation_name, "plugin.run");
    assert.equal(detail?.memory_receipts?.[0]?.current_task_operation_plane, "P7_EXECUTION");
    assert.equal(detail?.memory_receipts?.[0]?.current_task_advance_action, "run_operation");
    assert.equal(detail?.memory_receipts?.[0]?.plan_status, "in_progress");
    assert.equal(detail?.memory_receipts?.[0]?.plan_current_step_id, "understand");
    assert.equal(detail?.memory_receipts?.[0]?.plan_current_step_title, "Understand goal + constraints");
    assert.equal(detail?.memory_receipts?.[0]?.plan_step_count, 4);
    assert.equal(detail?.memory_receipts?.[0]?.plan_checkpoint_count, 3);
  } finally {
    restoreFetch();
  }
});

test("OperationsClient.runOnce posts a single bounded worker cycle request", async () => {
  const requests: Array<{ path: string; method: string; body: unknown }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const path = new URL(url).pathname;
    requests.push({
      path,
      method: (init?.method ?? "GET").toUpperCase(),
      body: jsonRequestBody(init),
    });

    return jsonResponse({
      ok: true,
      exit_code: 0,
    });
  });

  try {
    const client = new OperationsClient("http://127.0.0.1:8000");
    const response = await client.runOnce(
      {
        queue: "default",
        kind: "default",
        concurrency: 1,
        heartbeat_s: 0.25,
        profile: "dev",
        run_mode: "api",
        log_level: "INFO",
      },
      { timeoutMs: 50 },
    );

    assert.deepEqual(requests, [
      {
        path: "/operations/run-once",
        method: "POST",
        body: {
          queue: "default",
          kind: "default",
          concurrency: 1,
          heartbeat_s: 0.25,
          profile: "dev",
          run_mode: "api",
          log_level: "INFO",
        },
      },
    ]);
    assert.equal(response.ok, true);
    assert.equal(response.exit_code, 0);
    assert.equal(response.error, undefined);
  } finally {
    restoreFetch();
  }
});

test("OperationsClient.create posts the governed operation request envelope and preserves approval handoff fields", async () => {
  const requests: Array<{ path: string; method: string; body: unknown }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const path = new URL(url).pathname;
    requests.push({
      path,
      method: (init?.method ?? "GET").toUpperCase(),
      body: jsonRequestBody(init),
    });

    return jsonResponse({
      ok: true,
      operation_id: "tsk_compose_alpha",
      mission_id: "mission_alpha",
      mission_linked: true,
      approval_id: "apr_compose_alpha",
      status: "queued",
      message: "created",
      operation: {
        id: "tsk_compose_alpha",
        ts: 1777160000,
        status: "queued",
        actor: "chat_ui.operations",
        meta: { mission_id: "mission_alpha" },
      },
    });
  });

  try {
    const client = new OperationsClient("http://127.0.0.1:8000");
    const response = await client.create(
      {
        action: "plan.create",
        reason: "operator_requested",
        actor: "chat_ui.operations",
        mission_id: "mission_alpha",
        input: { goal: "Capture the next governed plan step" },
        objective: "Create a governed plan for the current operator objective",
        priority: 5,
      },
      { timeoutMs: 50 },
    );

    assert.deepEqual(requests, [
      {
        path: "/operations/create",
        method: "POST",
        body: {
          action: "plan.create",
          reason: "operator_requested",
          actor: "chat_ui.operations",
          mission_id: "mission_alpha",
          input: { goal: "Capture the next governed plan step" },
          objective: "Create a governed plan for the current operator objective",
          priority: 5,
        },
      },
    ]);
    assert.equal(response.ok, true);
    assert.equal(response.operation_id, "tsk_compose_alpha");
    assert.equal(response.operation?.id, "tsk_compose_alpha");
    assert.equal(response.operation?.meta?.mission_id, "mission_alpha");
    assert.equal(response.mission_id, "mission_alpha");
    assert.equal(response.mission_linked, true);
    assert.equal(response.mission_link_error, undefined);
    assert.equal(response.approval_id, "apr_compose_alpha");
    assert.equal(response.status, "queued");
    assert.equal(response.message, "created");
  } finally {
    restoreFetch();
  }
});

test("OperationsClient.create preserves created operation context when mission linking fails", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({
      ok: false,
      operation_id: "tsk_unlinked_alpha",
      mission_id: "mission_missing",
      mission_linked: false,
      mission_link_error: "not_found",
      status: "queued",
      message: "created_with_mission_link_error",
      operation: {
        id: "tsk_unlinked_alpha",
        ts: 1777160000,
        status: "queued",
        meta: { mission_id: "mission_missing" },
      },
    }),
  );

  try {
    const client = new OperationsClient("http://127.0.0.1:8000");
    const response = await client.create({
      action: "plan.create",
      reason: "operator_requested",
      actor: "chat_ui.operations",
      mission_id: "mission_missing",
      input: { goal: "Preserve unlinked task context" },
    });

    assert.equal(response.ok, false);
    assert.equal(response.operation_id, "tsk_unlinked_alpha");
    assert.equal(response.operation?.id, "tsk_unlinked_alpha");
    assert.equal(response.mission_id, "mission_missing");
    assert.equal(response.mission_linked, false);
    assert.equal(response.mission_link_error, "not_found");
    assert.equal(response.message, "created_with_mission_link_error");
  } finally {
    restoreFetch();
  }
});
