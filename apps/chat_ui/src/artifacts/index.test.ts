import assert from "node:assert/strict";
import test from "node:test";

import { artifactOriginTraceId, ArtifactsApiError, ArtifactsClient } from "./index.ts";

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function textResponse(body: string, status = 200): Response {
  return new Response(body, { status, headers: { "content-type": "text/plain" } });
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

test("artifactOriginTraceId prefers current-task and handoff trace handles before legacy refs", () => {
  assert.equal(
    artifactOriginTraceId({
      trace_id: "trace_top",
      handoff_trace_id: "trace_handoff",
      current_task_trace_id: "trace_current",
      references: { trace_id: "trace_reference" },
    }),
    "trace_current",
  );
  assert.equal(artifactOriginTraceId({ handoff_trace_id: "trace_handoff", trace_id: "trace_top" }), "trace_handoff");
  assert.equal(artifactOriginTraceId({ references: { trace_id: "trace_reference" } }), "trace_reference");
  assert.equal(artifactOriginTraceId(undefined), "");
});

test("ArtifactsClient.inspect requests bounded artifact metadata and preserves directory entries", async () => {
  const requests: Array<{ path: string; artifactDir: string | null; limit: string | null; method: string }> = [];
  const restoreFetch = installFetch(async (url, init) => {
    const parsed = new URL(url);
    requests.push({
      path: parsed.pathname,
      artifactDir: parsed.searchParams.get("artifact_dir"),
      limit: parsed.searchParams.get("limit"),
      method: (init?.method ?? "GET").toUpperCase(),
    });

    return jsonResponse({
      ok: true,
      artifact_root: "D:/Francis/data/artifacts",
      artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
      relative_path: "supervised_exec/apr_alpha",
      exists: true,
      kind: "directory",
      originating_receipt: {
        source: "continuity.ledger",
        matched_artifact_field: "artifact_dir",
        mission_id: "msn_alpha",
        operation_id: "tsk_alpha",
        approval_id: "apr_alpha",
        trace_id: "trace_alpha",
        run_id: "run_alpha",
        artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
        operation_status: "failed",
        operation_error: "plugin_id_required",
        result_message: "Plugin id is required.",
        recovery_next_step: "review_operation_detail",
        plan_status: "in_progress",
        plan_current_step_id: "understand",
        plan_current_step_title: "Understand goal + constraints",
        plan_step_count: "4",
        plan_checkpoint_count: 3,
        active_stage: "deadletter",
        handoff_stage: "deadletter",
        handoff_action: "retry_or_deadletter",
        handoff_gate: "operator_review",
        handoff_approval_id: "apr_alpha",
        handoff_approval_status: "approved",
        handoff_operation_id: "tsk_alpha",
        handoff_trace_id: "trace_alpha",
        handoff_run_id: "run_alpha",
        handoff_artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
        current_task_source: "terminal_operation_receipt",
        current_task_gate: "operator_review",
        current_task_approval_id: "apr_alpha",
        current_task_approval_status: "approved",
        current_task_operation_id: "tsk_alpha",
        current_task_operation_name: "plugin.run",
        current_task_operation_plane: "P7_EXECUTION",
        current_task_advance_action: "run_operation",
        current_task_trace_id: "trace_alpha",
        current_task_run_id: "run_alpha",
        current_task_artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
        current_task_next_step: "review_operation_detail",
        references: {
          mission_id: "msn_alpha",
          operation_id: "tsk_alpha",
          approval_id: "apr_alpha",
          trace_id: "trace_alpha",
          run_id: "run_alpha",
          artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
        },
      },
      entries: [
        {
          name: "result.json",
          relative_path: "supervised_exec/apr_alpha/result.json",
          kind: "file",
          bytes: 64,
          modified_ts: 1770000100,
        },
        {
          name: "nested",
          relative_path: "supervised_exec/apr_alpha/nested",
          kind: "directory",
          bytes: 0,
          modified_ts: null,
        },
      ],
      entry_count: 2,
      truncated: false,
    });
  });

  try {
    const client = new ArtifactsClient("http://127.0.0.1:8000");
    const response = await client.inspect(" supervised_exec/apr_alpha ", { limit: 25, timeoutMs: 50 });

    assert.deepEqual(requests, [
      {
        path: "/artifacts/inspect",
        artifactDir: "supervised_exec/apr_alpha",
        limit: "25",
        method: "GET",
      },
    ]);
    assert.equal(response.ok, true);
    assert.equal(response.artifact_root, "D:/Francis/data/artifacts");
    assert.equal(response.artifact_dir, "D:/Francis/data/artifacts/supervised_exec/apr_alpha");
    assert.equal(response.relative_path, "supervised_exec/apr_alpha");
    assert.equal(response.exists, true);
    assert.equal(response.kind, "directory");
    assert.equal(response.entry_count, 2);
    assert.equal(response.truncated, false);
    assert.deepEqual(response.originating_receipt, {
      source: "continuity.ledger",
      matched_artifact_field: "artifact_dir",
      mission_id: "msn_alpha",
      operation_id: "tsk_alpha",
      approval_id: "apr_alpha",
      trace_id: "trace_alpha",
      run_id: "run_alpha",
      artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
      operation_status: "failed",
      operation_error: "plugin_id_required",
      result_message: "Plugin id is required.",
      recovery_next_step: "review_operation_detail",
      plan_status: "in_progress",
      plan_current_step_id: "understand",
      plan_current_step_title: "Understand goal + constraints",
      plan_step_count: 4,
      plan_checkpoint_count: 3,
      active_stage: "deadletter",
      handoff_stage: "deadletter",
      handoff_action: "retry_or_deadletter",
      handoff_gate: "operator_review",
      handoff_approval_id: "apr_alpha",
      handoff_approval_status: "approved",
      handoff_operation_id: "tsk_alpha",
      handoff_trace_id: "trace_alpha",
      handoff_run_id: "run_alpha",
      handoff_artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
      current_task_source: "terminal_operation_receipt",
      current_task_gate: "operator_review",
      current_task_approval_id: "apr_alpha",
      current_task_approval_status: "approved",
      current_task_operation_id: "tsk_alpha",
      current_task_operation_name: "plugin.run",
      current_task_operation_plane: "P7_EXECUTION",
      current_task_advance_action: "run_operation",
      current_task_trace_id: "trace_alpha",
      current_task_run_id: "run_alpha",
      current_task_artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
      current_task_next_step: "review_operation_detail",
      references: {
        mission_id: "msn_alpha",
        operation_id: "tsk_alpha",
        approval_id: "apr_alpha",
        trace_id: "trace_alpha",
        run_id: "run_alpha",
        artifact_dir: "D:/Francis/data/artifacts/supervised_exec/apr_alpha",
      },
    });
    assert.deepEqual(response.entries, [
      {
        name: "result.json",
        relative_path: "supervised_exec/apr_alpha/result.json",
        kind: "file",
        bytes: 64,
        modified_ts: 1770000100,
      },
      {
        name: "nested",
        relative_path: "supervised_exec/apr_alpha/nested",
        kind: "directory",
        bytes: 0,
        modified_ts: null,
      },
    ]);
  } finally {
    restoreFetch();
  }
});

test("ArtifactsClient.inspect preserves missing artifact state without fabricating entries", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({
      ok: false,
      error: "artifact_not_found",
      artifact_root: "D:/Francis/data/artifacts",
      artifact_dir: "D:/Francis/data/artifacts/missing/run_alpha",
      relative_path: "missing/run_alpha",
      exists: false,
      recovery_hint: "Refresh the mission or operation receipt, then inspect the latest artifact_dir handle.",
      next_step: "refresh_originating_receipt",
      retryable: true,
    }),
  );

  try {
    const client = new ArtifactsClient("http://127.0.0.1:8000");
    const response = await client.inspect("missing/run_alpha", { timeoutMs: 50 });

    assert.equal(response.ok, false);
    assert.equal(response.error, "artifact_not_found");
    assert.equal(response.exists, false);
    assert.equal(response.relative_path, "missing/run_alpha");
    assert.equal(
      response.recovery_hint,
      "Refresh the mission or operation receipt, then inspect the latest artifact_dir handle.",
    );
    assert.equal(response.next_step, "refresh_originating_receipt");
    assert.equal(response.retryable, true);
    assert.deepEqual(response.entries, []);
    assert.equal(response.kind, undefined);
  } finally {
    restoreFetch();
  }
});

test("ArtifactsClient.inspect preserves loop-only originating receipt handles", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({
      ok: true,
      artifact_dir: "D:/Francis/data/artifacts/loop_only/run_receipt",
      relative_path: "loop_only/run_receipt",
      exists: true,
      kind: "directory",
      originating_receipt: {
        source: "continuity.ledger",
        matched_artifact_field: "current_task_artifact_dir",
        mission_id: "msn_loop_current",
        operation_id: "tsk_loop_current",
        approval_id: "apr_loop_current",
        trace_id: "trace_loop_current",
        run_id: "run_loop_current",
        artifact_dir: "D:/Francis/data/artifacts/loop_only/run_receipt",
        current_task_mission_id: "msn_loop_current",
        handoff_mission_id: "msn_loop_handoff",
        current_task_previous_approval_id: "apr_loop_previous",
        current_task_previous_approval_status: "approved",
        references: {
          mission_id: "msn_loop_current",
          operation_id: "tsk_loop_current",
          approval_id: "apr_loop_current",
          trace_id: "trace_loop_current",
          run_id: "run_loop_current",
          artifact_dir: "D:/Francis/data/artifacts/loop_only/run_receipt",
        },
      },
      entries: [],
      entry_count: 0,
      truncated: false,
    }),
  );

  try {
    const client = new ArtifactsClient("http://127.0.0.1:8000");
    const response = await client.inspect("loop_only/run_receipt", { timeoutMs: 50 });

    assert.deepEqual(response.originating_receipt, {
      source: "continuity.ledger",
      matched_artifact_field: "current_task_artifact_dir",
      mission_id: "msn_loop_current",
      operation_id: "tsk_loop_current",
      approval_id: "apr_loop_current",
      trace_id: "trace_loop_current",
      run_id: "run_loop_current",
      artifact_dir: "D:/Francis/data/artifacts/loop_only/run_receipt",
      current_task_mission_id: "msn_loop_current",
      handoff_mission_id: "msn_loop_handoff",
      current_task_previous_approval_id: "apr_loop_previous",
      current_task_previous_approval_status: "approved",
      references: {
        mission_id: "msn_loop_current",
        operation_id: "tsk_loop_current",
        approval_id: "apr_loop_current",
        trace_id: "trace_loop_current",
        run_id: "run_loop_current",
        artifact_dir: "D:/Francis/data/artifacts/loop_only/run_receipt",
      },
    });
  } finally {
    restoreFetch();
  }
});

test("ArtifactsClient.inspect does not preserve artifact file contents from drifted responses", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({
      ok: true,
      artifact_dir: "D:/Francis/data/artifacts/plugins/demo",
      relative_path: "plugins/demo",
      exists: true,
      kind: "directory",
      content: "raw secret content should not be carried",
      payload: { token: "raw secret content should not be carried" },
      entries: [
        {
          name: "stdout.txt",
          relative_path: "plugins/demo/stdout.txt",
          kind: "file",
          bytes: 18,
          content: "raw stdout",
          text: "raw stdout",
        },
      ],
      entry_count: 1,
    }),
  );

  try {
    const client = new ArtifactsClient("http://127.0.0.1:8000");
    const response = await client.inspect("plugins/demo", { timeoutMs: 50 });
    const rawResponse = response as unknown as Record<string, unknown>;
    const rawEntry = response.entries[0] as unknown as Record<string, unknown>;

    assert.equal(response.ok, true);
    assert.equal(response.entries.length, 1);
    assert.equal("content" in rawResponse, false);
    assert.equal("payload" in rawResponse, false);
    assert.equal("content" in rawEntry, false);
    assert.equal("text" in rawEntry, false);
  } finally {
    restoreFetch();
  }
});

test("ArtifactsClient.inspect throws structured errors for HTTP failures", async () => {
  const restoreFetch = installFetch(async () => textResponse("artifact service unavailable", 503));

  try {
    const client = new ArtifactsClient("http://127.0.0.1:8000");
    await assert.rejects(
      () => client.inspect("plugins/demo", { timeoutMs: 50 }),
      (error: unknown) => {
        assert.equal(error instanceof ArtifactsApiError, true);
        const apiError = error as ArtifactsApiError;
        assert.equal(apiError.status, 503);
        assert.match(apiError.bodySnippet ?? "", /artifact service unavailable/);
        assert.match(apiError.url ?? "", /\/artifacts\/inspect/);
        return true;
      },
    );
  } finally {
    restoreFetch();
  }
});
