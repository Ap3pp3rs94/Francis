import type {
  MemoryTimelineEvent,
  MemoryTimelineListFilters,
  MemoryTimelineListResponse,
} from "../memory_timeline/index.ts";

export type MemoryEvidenceQuery = {
  label: string;
  filters: MemoryTimelineListFilters;
};

export type MemoryEvidenceQueryInput = {
  missionId?: string;
  operationId?: string;
  fallbackOperationId?: string;
  operationStatus?: string | string[];
  traceId?: string;
  runId?: string;
  artifactDir?: string;
};

function cleanId(value: string | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function terminalOperationStatus(value: string | string[] | undefined): string {
  const values = Array.isArray(value) ? value : [value];

  for (const raw of values) {
    const status = cleanId(raw).toLowerCase();
    if (status === "completed") return "succeeded";
    if (status === "succeeded" || status === "failed") return status;
  }

  return "";
}

export function buildMemoryEvidenceQueries(input: MemoryEvidenceQueryInput): MemoryEvidenceQuery[] {
  const queries: MemoryEvidenceQuery[] = [];
  const seen = new Set<string>();

  const push = (label: string, filters: MemoryTimelineListFilters) => {
    if (seen.has(label)) return;
    seen.add(label);
    queries.push({ label, filters: { ...filters, limit: 8, include_payload: false } });
  };

  const missionId = cleanId(input.missionId);
  const operationId = cleanId(input.operationId);
  const fallbackOperationId = cleanId(input.fallbackOperationId);
  const operationStatus = terminalOperationStatus(input.operationStatus);
  const traceId = cleanId(input.traceId);
  const runId = cleanId(input.runId);
  const artifactDir = cleanId(input.artifactDir);
  const withOperationStatus = (filters: MemoryTimelineListFilters): MemoryTimelineListFilters =>
    operationStatus ? { ...filters, operation_status: operationStatus } : filters;

  if (missionId) push(`mission=${missionId}`, withOperationStatus({ mission_id: missionId }));
  if (operationId) push(`task=${operationId}`, withOperationStatus({ operation_id: operationId }));
  else if (fallbackOperationId) push(`task=${fallbackOperationId}`, withOperationStatus({ operation_id: fallbackOperationId }));
  if (traceId) push(`trace=${traceId}`, withOperationStatus({ trace_id: traceId }));
  if (runId) push(`run=${runId}`, withOperationStatus({ run_id: runId }));
  if (artifactDir) push(`artifact=${artifactDir}`, withOperationStatus({ artifact_dir: artifactDir }));

  return queries;
}

export function memoryEvidenceQueryKey(queries: MemoryEvidenceQuery[]): string {
  return queries.map((query) => query.label).join("|");
}

export function mergeMemoryEvidenceResponses(
  responses: MemoryTimelineListResponse[],
  limit = 10,
): MemoryTimelineEvent[] {
  const merged = new Map<string, MemoryTimelineEvent>();

  responses.forEach((response) => {
    response.items.forEach((item) => {
      if (!merged.has(item.id)) merged.set(item.id, item);
    });
  });

  return Array.from(merged.values())
    .sort((a, b) => b.ts - a.ts)
    .slice(0, Math.max(0, limit));
}
