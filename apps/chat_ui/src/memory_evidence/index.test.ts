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
