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
  traceId?: string;
};

function cleanId(value: string | undefined): string {
  return typeof value === "string" ? value.trim() : "";
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
  const traceId = cleanId(input.traceId);

  if (missionId) push(`mission=${missionId}`, { mission_id: missionId });
  if (operationId) push(`task=${operationId}`, { operation_id: operationId });
  else if (fallbackOperationId) push(`task=${fallbackOperationId}`, { operation_id: fallbackOperationId });
  if (traceId) push(`trace=${traceId}`, { trace_id: traceId });

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
