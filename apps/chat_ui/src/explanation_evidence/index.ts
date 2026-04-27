import type {
  ExplanationListQuery,
  ExplanationListResponse,
  ExplanationRecord,
} from "../explanation_explorer/index.ts";

export type ExplanationEvidenceQuery = {
  label: string;
  filters: ExplanationListQuery;
};

export type ExplanationEvidenceReceiptReference = {
  mission_id?: string;
  operation_id?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
  approval_id?: string;
  handoff_operation_id?: string;
  handoff_approval_id?: string;
  handoff_trace_id?: string;
  handoff_run_id?: string;
  handoff_artifact_dir?: string;
  handoff_mission_id?: string;
  current_task_operation_id?: string;
  current_task_approval_id?: string;
  current_task_trace_id?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  current_task_mission_id?: string;
  references?: {
    mission_id?: string;
    operation_id?: string;
    approval_id?: string;
    trace_id?: string;
    run_id?: string;
    artifact_dir?: string;
  };
};

export type ExplanationEvidenceQueryInput = {
  missionId?: string;
  operationId?: string;
  approvalId?: string;
  traceId?: string;
  runId?: string;
  artifactDir?: string;
  receipt?: ExplanationEvidenceReceiptReference;
};

function cleanId(value: string | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function receiptReferenceId(
  receipt: ExplanationEvidenceReceiptReference | undefined,
  key: "mission_id" | "operation_id" | "approval_id" | "trace_id" | "run_id" | "artifact_dir",
): string {
  if (!receipt) return "";
  if (key === "mission_id") {
    return (
      cleanId(receipt.current_task_mission_id) ||
      cleanId(receipt.handoff_mission_id) ||
      cleanId(receipt.mission_id) ||
      cleanId(receipt.references?.mission_id)
    );
  }
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

export function buildExplanationEvidenceQueries(input: ExplanationEvidenceQueryInput): ExplanationEvidenceQuery[] {
  const queries: ExplanationEvidenceQuery[] = [];
  const seen = new Set<string>();

  const push = (label: string, filters: ExplanationListQuery) => {
    if (seen.has(label)) return;
    seen.add(label);
    queries.push({ label, filters: { ...filters, limit: 8 } });
  };

  const missionId = cleanId(input.missionId) || receiptReferenceId(input.receipt, "mission_id");
  const operationId = cleanId(input.operationId) || receiptReferenceId(input.receipt, "operation_id");
  const approvalId = cleanId(input.approvalId) || receiptReferenceId(input.receipt, "approval_id");
  const traceId = cleanId(input.traceId) || receiptReferenceId(input.receipt, "trace_id");
  const runId = cleanId(input.runId) || receiptReferenceId(input.receipt, "run_id");
  const artifactDir = cleanId(input.artifactDir) || receiptReferenceId(input.receipt, "artifact_dir");

  if (missionId) push(`mission=${missionId}`, { mission_id: missionId });
  if (operationId) push(`task=${operationId}`, { operation_id: operationId });
  if (approvalId) push(`approval=${approvalId}`, { approval_id: approvalId });
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
