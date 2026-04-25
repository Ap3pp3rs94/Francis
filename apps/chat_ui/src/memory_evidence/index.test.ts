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
    traceId: "trace_alpha",
  });

  assert.deepEqual(queries, [
    {
      label: "mission=mission_alpha",
      filters: { mission_id: "mission_alpha", limit: 8, include_payload: false },
    },
    {
      label: "task=task_alpha",
      filters: { operation_id: "task_alpha", limit: 8, include_payload: false },
    },
    {
      label: "trace=trace_alpha",
      filters: { trace_id: "trace_alpha", limit: 8, include_payload: false },
    },
  ]);
  assert.equal(memoryEvidenceQueryKey(queries), "mission=mission_alpha|task=task_alpha|trace=trace_alpha");
});

test("buildMemoryEvidenceQueries uses fallback operation id only when no linked task exists", () => {
  assert.deepEqual(
    buildMemoryEvidenceQueries({
      missionId: "",
      operationId: " ",
      fallbackOperationId: "task_selected",
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
