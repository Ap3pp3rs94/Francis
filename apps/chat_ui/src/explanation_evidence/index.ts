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
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
  approval_id?: string;
  handoff_approval_id?: string;
  handoff_trace_id?: string;
  handoff_run_id?: string;
  handoff_artifact_dir?: string;
  current_task_approval_id?: string;
  current_task_trace_id?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  references?: {
    approval_id?: string;
    trace_id?: string;
    run_id?: string;
    artifact_dir?: string;
  };
};

export type ExplanationEvidenceQueryInput = {
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
  key: "approval_id" | "trace_id" | "run_id" | "artifact_dir",
): string {
  if (!receipt) return "";
  if (key === "approval_id") {
    return (
      cleanId(receipt.approval_id) ||
      cleanId(receipt.current_task_approval_id) ||
      cleanId(receipt.handoff_approval_id) ||
      cleanId(receipt.references?.approval_id)
    );
  }
  if (key === "trace_id") {
    return (
      cleanId(receipt.trace_id) ||
      cleanId(receipt.current_task_trace_id) ||
      cleanId(receipt.handoff_trace_id) ||
      cleanId(receipt.references?.trace_id)
    );
  }
  if (key === "run_id") {
    return (
      cleanId(receipt.run_id) ||
      cleanId(receipt.current_task_run_id) ||
      cleanId(receipt.handoff_run_id) ||
      cleanId(receipt.references?.run_id)
    );
  }
  return (
    cleanId(receipt.artifact_dir) ||
    cleanId(receipt.current_task_artifact_dir) ||
    cleanId(receipt.handoff_artifact_dir) ||
    cleanId(receipt.references?.artifact_dir)
  );
}

export function buildExplanationEvidenceQueries(input: ExplanationEvidenceQueryInput): ExplanationEvidenceQuery[] {
  const queries: ExplanationEvidenceQuery[] = [];
  const seen = new Set<string>();

  const push = (label: string, filters: ExplanationListQuery) => {
    if (seen.has(label)) return;
    seen.add(label);
    queries.push({ label, filters: { ...filters, limit: 8 } });
  };

  const approvalId = cleanId(input.approvalId) || receiptReferenceId(input.receipt, "approval_id");
  const traceId = cleanId(input.traceId) || receiptReferenceId(input.receipt, "trace_id");
  const runId = cleanId(input.runId) || receiptReferenceId(input.receipt, "run_id");
  const artifactDir = cleanId(input.artifactDir) || receiptReferenceId(input.receipt, "artifact_dir");

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
