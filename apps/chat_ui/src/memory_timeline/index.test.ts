import assert from "node:assert/strict";
import test from "node:test";

import { MemoryTimelineClient } from "./index.ts";

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

test("MemoryTimelineClient.list preserves provenance and retention context", async () => {
  const requests: Array<{
    path: string;
    includePayload: string | null;
    missionId: string | null;
    operationId: string | null;
    traceId: string | null;
    runId: string | null;
    artifactDir: string | null;
    operationStatus: string | null;
  }> = [];
  const restoreFetch = installFetch(async (url) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      includePayload: parsed.searchParams.get("include_payload"),
      missionId: parsed.searchParams.get("mission_id"),
      operationId: parsed.searchParams.get("operation_id"),
      traceId: parsed.searchParams.get("trace_id"),
      runId: parsed.searchParams.get("run_id"),
      artifactDir: parsed.searchParams.get("artifact_dir"),
      operationStatus: parsed.searchParams.get("operation_status"),
    });

    return jsonResponse({
      items: [
        {
          id: "evt_memory_context",
          ts: 1_777_100_000,
          kind: "memory_write",
          severity: "info",
          operation_status: "succeeded",
          domain: "operations",
          actor: "francis",
          scope: "mission.loop",
          correlation_id: "trace_memory_context",
          references: {
            mission_id: "mission_memory_context",
            operation_id: "tsk_memory_context",
            trace_id: "trace_memory_context",
            approval_id: "apr_memory_context",
            run_id: "run_memory_context",
            artifact_dir: "D:/francis/data/artifacts/memory-context",
          },
          title: "Memory context recorded",
          message: "Stored redacted mission continuity payload.",
          tags: ["mission", "redacted"],
          payload: { ticket: "FR-123", api_key: "[REDACTED:secret]" },
          provenance: {
            source: "unit_test",
            domain: "operations",
            actor: "francis",
            scope: "mission.loop",
            correlation_id: "trace_memory_context",
          },
          retention: {
            policy: "mission_trace",
            until: "2026-05-01T00:00:00Z",
            ttl_seconds: 86400,
          },
          loop: {
            ingress_plane: "P1_INTERFACE",
            active_stage: "memory",
            handoff_stage: "memory",
            handoff_action: "review_continuity",
            handoff_approval_id: "apr_memory_context",
            handoff_approval_status: "approved",
            handoff_trace_id: "trace_memory_context",
            handoff_run_id: "run_memory_context",
            handoff_artifact_dir: "D:/francis/data/artifacts/memory-context",
            current_task_approval_id: "apr_memory_context",
            current_task_approval_status: "approved",
            run_id: "run_memory_context",
            artifact_dir: "D:/francis/data/artifacts/memory-context",
            linked_operation_count: 1,
            run_ledger_count: 1,
            memory_receipt_count: 1,
          },
          meta: {
            source: "unit_test",
            retention_policy: "mission_trace",
          },
        },
      ],
      total: 1,
    });
  });

  try {
    const client = new MemoryTimelineClient("http://127.0.0.1:8000");
    const response = await client.list(
      {
        include_payload: true,
        mission_id: "mission_memory_context",
        operation_id: "tsk_memory_context",
        trace_id: "trace_memory_context",
        run_id: "run_memory_context",
        artifact_dir: "D:/francis/data/artifacts/memory-context",
        operation_status: "succeeded",
      },
      { timeoutMs: 50 },
    );

    assert.deepEqual(requests, [
      {
        path: "/memory/timeline/list",
        includePayload: "1",
        missionId: "mission_memory_context",
        operationId: "tsk_memory_context",
        traceId: "trace_memory_context",
        runId: "run_memory_context",
        artifactDir: "D:/francis/data/artifacts/memory-context",
        operationStatus: "succeeded",
      },
    ]);
    assert.equal(response.total, 1);
    assert.equal(response.items[0]?.id, "evt_memory_context");
    assert.equal(response.items[0]?.operation_status, "succeeded");
    assert.equal(response.items[0]?.payload && typeof response.items[0].payload === "object", true);
    assert.deepEqual(response.items[0]?.provenance, {
      source: "unit_test",
      domain: "operations",
      actor: "francis",
      scope: "mission.loop",
      correlation_id: "trace_memory_context",
    });
    assert.deepEqual(response.items[0]?.retention, {
      policy: "mission_trace",
      until: "2026-05-01T00:00:00Z",
      ttl_seconds: 86400,
    });
    assert.deepEqual(response.items[0]?.references, {
      mission_id: "mission_memory_context",
      operation_id: "tsk_memory_context",
      trace_id: "trace_memory_context",
      approval_id: "apr_memory_context",
      run_id: "run_memory_context",
      artifact_dir: "D:/francis/data/artifacts/memory-context",
    });
    assert.deepEqual(response.items[0]?.loop, {
      ingress_plane: "P1_INTERFACE",
      active_stage: "memory",
      handoff_stage: "memory",
      handoff_action: "review_continuity",
      handoff_approval_id: "apr_memory_context",
      handoff_approval_status: "approved",
      handoff_trace_id: "trace_memory_context",
      handoff_run_id: "run_memory_context",
      handoff_artifact_dir: "D:/francis/data/artifacts/memory-context",
      current_task_approval_id: "apr_memory_context",
      current_task_approval_status: "approved",
      run_id: "run_memory_context",
      artifact_dir: "D:/francis/data/artifacts/memory-context",
      linked_operation_count: 1,
      run_ledger_count: 1,
      memory_receipt_count: 1,
    });
    assert.equal(response.items[0]?.meta?.source, "unit_test");
  } finally {
    restoreFetch();
  }
});

test("MemoryTimelineClient derives context from explicit meta when top-level context is sparse", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({
      event: {
        id: "evt_meta_context",
        ts: 1_777_100_010,
        kind: "ledger_append",
        actor: "user",
        correlation_id: "trace_meta_context",
        meta: {
          source: "continuity.ledger",
          mission_id: "mission_meta_context",
          operation_id: "tsk_meta_context",
          trace_id: "trace_meta_context",
          run_id: "run_meta_context",
          artifact_dir: "D:/francis/data/artifacts/meta-context",
          handoff_approval_id: "apr_meta_context",
          handoff_approval_status: "pending",
          current_task_approval_id: "apr_meta_context",
          current_task_approval_status: "pending",
          active_stage: "memory",
          run_ledger_count: "1",
          retention_policy: "continuity_tail",
          ttl_seconds: 3600,
        },
      },
    }),
  );

  try {
    const client = new MemoryTimelineClient("http://127.0.0.1:8000");
    const response = await client.get("evt_meta_context", { timeoutMs: 50 });

    assert.equal(response.item?.id, "evt_meta_context");
    assert.deepEqual(response.item?.provenance, {
      source: "continuity.ledger",
      actor: "user",
      correlation_id: "trace_meta_context",
    });
    assert.deepEqual(response.item?.retention, {
      policy: "continuity_tail",
      ttl_seconds: 3600,
    });
    assert.deepEqual(response.item?.references, {
      mission_id: "mission_meta_context",
      operation_id: "tsk_meta_context",
      trace_id: "trace_meta_context",
      run_id: "run_meta_context",
      artifact_dir: "D:/francis/data/artifacts/meta-context",
    });
    assert.deepEqual(response.item?.loop, {
      active_stage: "memory",
      handoff_approval_id: "apr_meta_context",
      handoff_approval_status: "pending",
      current_task_approval_id: "apr_meta_context",
      current_task_approval_status: "pending",
      run_id: "run_meta_context",
      artifact_dir: "D:/francis/data/artifacts/meta-context",
      run_ledger_count: 1,
    });
  } finally {
    restoreFetch();
  }
});
