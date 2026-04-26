import assert from "node:assert/strict";
import test from "node:test";

import {
  buildExplanationEvidenceQueries,
  explanationEvidenceQueryKey,
  mergeExplanationEvidenceResponses,
} from "./index.ts";

test("buildExplanationEvidenceQueries builds bounded receipt filters", () => {
  const queries = buildExplanationEvidenceQueries({
    traceId: " trace_alpha ",
    runId: "run_alpha",
    artifactDir: "D:/francis/data/artifacts/alpha",
  });

  assert.deepEqual(queries, [
    {
      label: "trace=trace_alpha",
      filters: { trace_id: "trace_alpha", limit: 8 },
    },
    {
      label: "run=run_alpha",
      filters: { run_id: "run_alpha", limit: 8 },
    },
    {
      label: "artifact=D:/francis/data/artifacts/alpha",
      filters: { artifact_dir: "D:/francis/data/artifacts/alpha", limit: 8 },
    },
  ]);
  assert.equal(
    explanationEvidenceQueryKey(queries),
    "trace=trace_alpha|run=run_alpha|artifact=D:/francis/data/artifacts/alpha",
  );
});

test("buildExplanationEvidenceQueries ignores empty receipt handles", () => {
  assert.deepEqual(
    buildExplanationEvidenceQueries({
      traceId: "",
      runId: " ",
      artifactDir: undefined,
    }),
    [],
  );
});

test("mergeExplanationEvidenceResponses dedupes by id, sorts newest first, and limits results", () => {
  const items = mergeExplanationEvidenceResponses(
    [
      {
        items: [
          { id: "exp_old", ts: 100, kind: "audit" },
          { id: "exp_new", ts: 300, kind: "decision" },
        ],
      },
      {
        items: [
          { id: "exp_middle", ts: 200, kind: "tool_trace" },
          { id: "exp_new", ts: 400, kind: "decision", title: "duplicate should not replace first match" },
        ],
      },
    ],
    2,
  );

  assert.deepEqual(
    items.map((item) => ({ id: item.id, ts: item.ts, title: item.title })),
    [
      { id: "exp_new", ts: 300, title: undefined },
      { id: "exp_middle", ts: 200, title: undefined },
    ],
  );
});
