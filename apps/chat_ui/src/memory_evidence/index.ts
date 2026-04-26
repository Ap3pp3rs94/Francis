import type {
  MemoryTimelineEvent,
  MemoryTimelineListFilters,
  MemoryTimelineListResponse,
} from "../memory_timeline/index.ts";

export type MemoryEvidenceQuery = {
  label: string;
  filters: MemoryTimelineListFilters;
};

export type MemoryEvidenceReceiptReference = {
  mission_id?: string;
  operation_id?: string;
  approval_id?: string;
  operation_status?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
  handoff_operation_id?: string;
  handoff_approval_id?: string;
  handoff_trace_id?: string;
  handoff_run_id?: string;
  handoff_artifact_dir?: string;
  current_task_operation_id?: string;
  current_task_approval_id?: string;
  current_task_trace_id?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  references?: {
    mission_id?: string;
    operation_id?: string;
    approval_id?: string;
    trace_id?: string;
    run_id?: string;
    artifact_dir?: string;
  };
};

export type MemoryEvidenceQueryInput = {
  missionId?: string;
  operationId?: string;
  approvalId?: string;
  fallbackOperationId?: string;
  operationStatus?: string | string[];
  traceId?: string;
  runId?: string;
  artifactDir?: string;
  receipt?: MemoryEvidenceReceiptReference;
};

function cleanId(value: string | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function receiptReferenceId(
  receipt: MemoryEvidenceReceiptReference | undefined,
  key: "mission_id" | "operation_id" | "approval_id" | "trace_id" | "run_id" | "artifact_dir",
): string {
  if (!receipt) return "";
  if (key === "operation_id") {
    return (
      cleanId(receipt.current_task_operation_id) ||
      cleanId(receipt.handoff_operation_id) ||
      cleanId(receipt.operation_id) ||
      cleanId(receipt.references?.operation_id)
    );
  }
  if (key === "approval_id") {
    return (
      cleanId(receipt.current_task_approval_id) ||
      cleanId(receipt.handoff_approval_id) ||
      cleanId(receipt.approval_id) ||
      cleanId(receipt.references?.approval_id)
    );
  }
  if (key === "trace_id") {
    return (
      cleanId(receipt.current_task_trace_id) ||
      cleanId(receipt.handoff_trace_id) ||
      cleanId(receipt.trace_id) ||
      cleanId(receipt.references?.trace_id)
    );
  }
  if (key === "run_id") {
    return (
      cleanId(receipt.current_task_run_id) ||
      cleanId(receipt.handoff_run_id) ||
      cleanId(receipt.run_id) ||
      cleanId(receipt.references?.run_id)
    );
  }
  if (key === "artifact_dir") {
    return (
      cleanId(receipt.current_task_artifact_dir) ||
      cleanId(receipt.handoff_artifact_dir) ||
      cleanId(receipt.artifact_dir) ||
      cleanId(receipt.references?.artifact_dir)
    );
  }
  return cleanId(receipt[key]) || cleanId(receipt.references?.[key]);
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

  const receipt = input.receipt;
  const missionId = cleanId(input.missionId) || receiptReferenceId(receipt, "mission_id");
  const operationId = cleanId(input.operationId) || receiptReferenceId(receipt, "operation_id");
  const approvalId = cleanId(input.approvalId) || receiptReferenceId(receipt, "approval_id");
  const fallbackOperationId = cleanId(input.fallbackOperationId);
  const operationStatus = terminalOperationStatus(input.operationStatus) || terminalOperationStatus(receipt?.operation_status);
  const traceId = cleanId(input.traceId) || receiptReferenceId(receipt, "trace_id");
  const runId = cleanId(input.runId) || receiptReferenceId(receipt, "run_id");
  const artifactDir = cleanId(input.artifactDir) || receiptReferenceId(receipt, "artifact_dir");
  const withOperationStatus = (filters: MemoryTimelineListFilters): MemoryTimelineListFilters =>
    operationStatus ? { ...filters, operation_status: operationStatus } : filters;

  if (missionId) push(`mission=${missionId}`, withOperationStatus({ mission_id: missionId }));
  if (operationId) push(`task=${operationId}`, withOperationStatus({ operation_id: operationId }));
  else if (fallbackOperationId) push(`task=${fallbackOperationId}`, withOperationStatus({ operation_id: fallbackOperationId }));
  if (approvalId) push(`approval=${approvalId}`, withOperationStatus({ approval_id: approvalId }));
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
