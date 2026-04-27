import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMemoryEvidenceQueries,
  memoryEvidenceQueryKey,
  mergeMemoryEvidenceResponses,
} from "./index.ts";

test("buildMemoryEvidenceQueries builds bounded mission, task, and trace filters", () => {
  const queries = buildMemoryEvidenceQueries({
    missionId: " mission_alpha ",
    operationId: "task_alpha",
    fallbackOperationId: "task_fallback",
    operationStatus: ["running", " completed "],
    traceId: "trace_alpha",
    runId: "run_alpha",
    artifactDir: "D:/francis/data/artifacts/alpha",
  });

  assert.deepEqual(queries, [
    {
      label: "mission=mission_alpha",
      filters: { mission_id: "mission_alpha", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "task=task_alpha",
      filters: { operation_id: "task_alpha", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "trace=trace_alpha",
      filters: { trace_id: "trace_alpha", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "run=run_alpha",
      filters: { run_id: "run_alpha", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "artifact=D:/francis/data/artifacts/alpha",
      filters: {
        artifact_dir: "D:/francis/data/artifacts/alpha",
        operation_status: "succeeded",
        limit: 8,
        include_payload: false,
      },
    },
  ]);
  assert.equal(
    memoryEvidenceQueryKey(queries),
    "mission=mission_alpha|task=task_alpha|trace=trace_alpha|run=run_alpha|artifact=D:/francis/data/artifacts/alpha",
  );
});

test("buildMemoryEvidenceQueries uses fallback operation id only when no linked task exists", () => {
  assert.deepEqual(
    buildMemoryEvidenceQueries({
      missionId: "",
      operationId: " ",
      fallbackOperationId: "task_selected",
      operationStatus: "queued",
      traceId: undefined,
    }),
    [
      {
        label: "task=task_selected",
        filters: { operation_id: "task_selected", limit: 8, include_payload: false },
      },
    ],
  );
});

test("buildMemoryEvidenceQueries carries failed status into bounded evidence filters", () => {
  assert.deepEqual(
    buildMemoryEvidenceQueries({
      operationId: "task_failed",
      operationStatus: " failed ",
    }),
    [
      {
        label: "task=task_failed",
        filters: {
          operation_id: "task_failed",
          operation_status: "failed",
          limit: 8,
          include_payload: false,
        },
      },
    ],
  );
});

test("buildMemoryEvidenceQueries falls back to terminal receipt references", () => {
  const queries = buildMemoryEvidenceQueries({
    missionId: "mission_selected",
    receipt: {
      operation_status: "succeeded",
      references: {
        mission_id: "mission_receipt",
        operation_id: "task_receipt",
        approval_id: "apr_receipt",
        trace_id: "trace_receipt",
        run_id: "run_receipt",
        artifact_dir: "D:/francis/data/artifacts/receipt",
      },
    },
  });

  assert.deepEqual(queries, [
    {
      label: "mission=mission_selected",
      filters: { mission_id: "mission_selected", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "task=task_receipt",
      filters: { operation_id: "task_receipt", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "approval=apr_receipt",
      filters: { approval_id: "apr_receipt", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "trace=trace_receipt",
      filters: { trace_id: "trace_receipt", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "run=run_receipt",
      filters: { run_id: "run_receipt", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "artifact=D:/francis/data/artifacts/receipt",
      filters: {
        artifact_dir: "D:/francis/data/artifacts/receipt",
        operation_status: "succeeded",
        limit: 8,
        include_payload: false,
      },
    },
  ]);
});

test("buildMemoryEvidenceQueries follows completed handoff receipt handles", () => {
  const queries = buildMemoryEvidenceQueries({
    receipt: {
      mission_id: "mission_completed",
      operation_id: "task_legacy",
      approval_id: "apr_legacy",
      trace_id: "trace_top",
      run_id: "run_top",
      artifact_dir: "D:/francis/data/artifacts/top",
      operation_status: "succeeded",
      current_task_operation_id: "task_completed",
      current_task_approval_id: "apr_completed",
      current_task_trace_id: "trace_completed",
      current_task_run_id: "run_completed",
      current_task_artifact_dir: "D:/francis/data/artifacts/completed",
      references: {
        operation_id: "task_legacy",
        trace_id: "trace_legacy",
        run_id: "run_legacy",
        artifact_dir: "D:/francis/data/artifacts/legacy",
      },
    },
  });

  assert.deepEqual(queries, [
    {
      label: "mission=mission_completed",
      filters: { mission_id: "mission_completed", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "task=task_completed",
      filters: { operation_id: "task_completed", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "approval=apr_completed",
      filters: { approval_id: "apr_completed", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "trace=trace_completed",
      filters: { trace_id: "trace_completed", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "run=run_completed",
      filters: { run_id: "run_completed", operation_status: "succeeded", limit: 8, include_payload: false },
    },
    {
      label: "artifact=D:/francis/data/artifacts/completed",
      filters: {
        artifact_dir: "D:/francis/data/artifacts/completed",
        operation_status: "succeeded",
        limit: 8,
        include_payload: false,
      },
    },
  ]);
});

test("buildMemoryEvidenceQueries follows loop-only mission receipt handles", () => {
  const queries = buildMemoryEvidenceQueries({
    receipt: {
      operation_status: "failed",
      current_task_mission_id: "mission_loop_current",
      handoff_mission_id: "mission_loop_handoff",
      current_task_operation_id: "task_loop_current",
      current_task_trace_id: "trace_loop_current",
    },
  });

  assert.deepEqual(queries, [
    {
      label: "mission=mission_loop_current",
      filters: { mission_id: "mission_loop_current", operation_status: "failed", limit: 8, include_payload: false },
    },
    {
      label: "task=task_loop_current",
      filters: { operation_id: "task_loop_current", operation_status: "failed", limit: 8, include_payload: false },
    },
    {
      label: "trace=trace_loop_current",
      filters: { trace_id: "trace_loop_current", operation_status: "failed", limit: 8, include_payload: false },
    },
  ]);
});

test("buildMemoryEvidenceQueries prefers explicit approval id for bounded approval evidence", () => {
  const queries = buildMemoryEvidenceQueries({
    approvalId: " apr_selected ",
    operationStatus: "needs_approval",
    receipt: {
      handoff_approval_id: "apr_handoff",
      references: {
        approval_id: "apr_reference",
      },
    },
  });

  assert.deepEqual(queries, [
    {
      label: "approval=apr_selected",
      filters: { approval_id: "apr_selected", limit: 8, include_payload: false },
    },
  ]);
});

test("mergeMemoryEvidenceResponses dedupes by event id, sorts newest first, and limits results", () => {
  const items = mergeMemoryEvidenceResponses(
    [
      {
        items: [
          { id: "evt_old", ts: 100, kind: "ledger_append" },
          { id: "evt_new", ts: 300, kind: "checkpoint" },
        ],
      },
      {
        items: [
          { id: "evt_middle", ts: 200, kind: "memory_write" },
          { id: "evt_new", ts: 400, kind: "checkpoint", title: "duplicate should not replace first match" },
        ],
      },
    ],
    2,
  );

  assert.deepEqual(
    items.map((item) => ({ id: item.id, ts: item.ts, title: item.title })),
    [
      { id: "evt_new", ts: 300, title: undefined },
      { id: "evt_middle", ts: 200, title: undefined },
    ],
  );
});
