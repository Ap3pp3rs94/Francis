import type {
  ExplanationListQuery,
  ExplanationListResponse,
  ExplanationRecord,
} from "../explanation_explorer/index.ts";

export type ExplanationEvidenceQuery = {
  label: string;
  filters: ExplanationListQuery;
};

export type ExplanationEvidenceQueryInput = {
  traceId?: string;
  runId?: string;
  artifactDir?: string;
};

function cleanId(value: string | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

export function buildExplanationEvidenceQueries(input: ExplanationEvidenceQueryInput): ExplanationEvidenceQuery[] {
  const queries: ExplanationEvidenceQuery[] = [];
  const seen = new Set<string>();

  const push = (label: string, filters: ExplanationListQuery) => {
    if (seen.has(label)) return;
    seen.add(label);
    queries.push({ label, filters: { ...filters, limit: 8 } });
  };

  const traceId = cleanId(input.traceId);
  const runId = cleanId(input.runId);
  const artifactDir = cleanId(input.artifactDir);

  if (traceId) push(`trace=${traceId}`, { trace_id: traceId });
  if (runId) push(`run=${runId}`, { run_id: runId });
  if (artifactDir) push(`artifact=${artifactDir}`, { artifact_dir: artifactDir });

  return queries;
}

export function explanationEvidenceQueryKey(queries: ExplanationEvidenceQuery[]): string {
  return queries.map((query) => query.label).join("|");
}

export function mergeExplanationEvidenceResponses(
  responses: ExplanationListResponse[],
  limit = 10,
): ExplanationRecord[] {
  const merged = new Map<string, ExplanationRecord>();

  responses.forEach((response) => {
    response.items.forEach((item) => {
      if (!merged.has(item.id)) merged.set(item.id, item);
    });
  });

  return Array.from(merged.values())
    .sort((a, b) => b.ts - a.ts)
    .slice(0, Math.max(0, limit));
}
