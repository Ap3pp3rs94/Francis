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
          meta: { run_id: "run_alpha", approval_id: "apr_alpha" },
        },
      ],
    });
  });

  try {
    const client = new ExplanationClient("http://127.0.0.1:8000");
    const response = await client.list({
      trace_id: "trace_alpha",
      artifact_dir: "runs/run_alpha/artifacts",
      approval_id: "apr_alpha",
      limit: 25,
      timeoutMs: 50,
    });

    assert.deepEqual(requests, [
      {
        path: "/explanations/list",
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
    assert.equal(response.items[0]?.approval_id, "apr_alpha");
    assert.equal(response.items[0]?.artifact_dir, "runs/run_alpha/artifacts");
  } finally {
    restoreFetch();
  }
});

test("ExplanationClient.get and export preserve receipt linkage", async () => {
  const requests: Array<{
    path: string;
    id: string | null;
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
        meta: { approval_id: "apr_detail" },
      },
      content: { outcome: "linked" },
    });
  });

  try {
    const client = new ExplanationClient("http://127.0.0.1:8000");
    const detail = await client.get("exp-trace-detail", { timeoutMs: 50 });
    await client.export("json", {
      trace_id: "trace_detail",
      artifact_dir: "runs/run_detail/artifacts",
      approval_id: "apr_detail",
      timeoutMs: 50,
    });

    assert.equal(detail?.trace_id, "trace_detail");
    assert.equal(detail?.artifact_dir, "runs/run_detail/artifacts");
    assert.equal(detail?.approval_id, "apr_detail");
    assert.deepEqual(requests, [
      {
        path: "/explanations/get",
        id: "exp-trace-detail",
        traceId: null,
        artifactDir: null,
        approvalId: null,
        method: "GET",
      },
      {
        path: "/explanations/export",
        id: null,
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
