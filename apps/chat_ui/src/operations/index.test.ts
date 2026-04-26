import assert from "node:assert/strict";
import test from "node:test";

import { OperationsClient } from "./index.ts";

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
        run_id: "run_task_alpha",
        artifact_dir: "D:/francis/data/artifacts/task_alpha",
        meta: {
          objective: "Advance morning continuity",
          orb_plane: "P7_EXECUTION",
          run_id: "run_task_alpha",
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
    assert.equal(response.operation?.run_id, "run_task_alpha");
    assert.equal(response.operation?.artifact_dir, "D:/francis/data/artifacts/task_alpha");
    assert.equal(response.operation?.meta?.orb_plane, "P7_EXECUTION");
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
