import type { OperationDetail, OperationRecord } from "../operations/index.ts";
import { parseOperationDetail, parseOperationRecord } from "../operations/index.ts";

export type MissionRecord = {
  id: string;
  status?: string;
  objective?: string;
  summary?: string;
  next_step?: string;
  requester_id?: string;
  owner_id?: string;
  priority?: number;
  risk_tier?: string;
  dependency_ids?: string[];
  dependency_count?: number;
  escalation_path?: string;
  linked_task_ids?: string[];
  linked_task_count?: number;
  deadletter_reason?: string;
  last_task_id?: string;
  last_task_status?: string;
  last_task_result_status?: string;
  last_task_reason?: string;
  last_task_gate?: string;
  last_task_next_step?: string;
  last_advance_operation_id?: string;
  last_advance_operation_name?: string;
  last_advance_operation_plane?: string;
  last_task_approval_id?: string;
  last_task_previous_approval_id?: string;
  last_task_previous_approval_status?: string;
  last_task_approval_status?: string;
  last_task_approval_replacement_kind?: string;
  last_task_approval_replacement_reason?: string;
  last_task_approval_replacement_changed_keys?: string[];
  replacement_for_mission_id?: string;
  replacement_for_status?: string;
  replacement_source_objective?: string;
  replacement_source_action?: string;
  replacement_source_target_id?: string;
  replacement_reason?: string;
  replacement_declared_by?: string;
  replacement_note?: string;
  created_at?: string;
  updated_at?: string;
  meta?: Record<string, unknown>;
};

export type MissionDependencyItem = {
  id?: string;
  kind?: string;
  state?: string;
  status?: string;
  result_status?: string;
  gate?: string;
  approval_id?: string;
  objective?: string;
  detail?: string;
  updated_at?: string;
};

export type MissionDependencyState = {
  status?: string;
  total?: number;
  resolved?: number;
  unresolved?: number;
  items?: MissionDependencyItem[];
  first_unresolved?: MissionDependencyItem;
};

export type MissionAdvanceProjection = {
  eligible?: boolean;
  action?: string;
  target_id?: string;
  reason?: string;
};

export type MissionRecoveryProjection = {
  source_status?: string;
  action?: string;
  target_id?: string;
  reason?: string;
  next_step?: string;
  operator_required?: boolean;
  automatic_retry?: boolean;
  read_only?: boolean;
  last_review_action?: string;
  last_review_outcome?: string;
  last_review_target_id?: string;
  last_review_actor?: string;
  last_reviewed_at?: string;
  replacement_mission_id?: string;
  replacement_status?: string;
  replacement_objective?: string;
  replacement_next_step?: string;
  replacement_last_task_id?: string;
  replacement_last_task_status?: string;
  replacement_updated_at?: string;
  replacement_terminal?: boolean;
  replacement_error?: string;
};

export type MissionHistoryEntry = {
  ts?: string;
  mission_id?: string;
  event?: string;
  details?: Record<string, unknown>;
};

export type MissionLoopStage = {
  status?: string;
  detail?: string;
  count?: number;
  gate?: string;
  next_step?: string;
  approval_id?: string;
  approval_status?: string;
  operation_id?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
  latest_event?: string;
  latest_receipt_status?: string;
  latest_ts?: string;
  memory_receipt_count?: number;
  latest_memory_receipt?: MissionMemoryReceipt;
  plan_status?: string;
  plan_current_step_id?: string;
  plan_current_step_title?: string;
  plan_step_count?: number;
  plan_checkpoint_count?: number;
};

export type MissionLoopHandoff = {
  stage?: string;
  action?: string;
  detail?: string;
  gate?: string;
  next_step?: string;
  approval_id?: string;
  approval_status?: string;
  operation_id?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
  latest_event?: string;
  latest_ts?: string;
};

export type MissionLoopState = {
  summary?: string;
  active_stage?: string;
  handoff?: MissionLoopHandoff;
  plan?: MissionLoopStage;
  gate?: MissionLoopStage;
  execute?: MissionLoopStage;
  trace?: MissionLoopStage;
  memory?: MissionLoopStage;
  interface?: MissionLoopStage;
};

export type MissionCurrentTask = {
  mission_id?: string;
  source?: string;
  operation_id?: string;
  operation_name?: string;
  operation_plane?: string;
  task_status?: string;
  operation_status?: string;
  result_status?: string;
  gate?: string;
  next_step?: string;
  reason?: string;
  approval_id?: string;
  approval_status?: string;
  handoff_stage?: string;
  handoff_action?: string;
  advance_action?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
  latest_receipt_event?: string;
  latest_receipt_status?: string;
  latest_receipt_ts?: string;
  last_advance_operation_id?: string;
};

export type MissionReceiptSummary = {
  linked_operation_count?: number;
  run_ledger_count?: number;
  history_count?: number;
  memory_receipt_count?: number;
  latest_memory_receipt?: MissionMemoryReceipt;
  current_operation_id?: string;
  current_operation_status?: string;
  current_gate?: string;
  current_approval_id?: string;
  current_trace_id?: string;
  current_run_id?: string;
  current_artifact_dir?: string;
  latest_run_event?: string;
  latest_run_status?: string;
  latest_run_ts?: string;
  latest_history_event?: string;
  latest_history_ts?: string;
};

export type MissionMemoryReceipt = {
  id?: string;
  source?: string;
  kind?: string;
  ts?: number;
  role?: string;
  message?: string;
  scope?: string;
  operation_status?: string;
  operation_error?: string;
  result_message?: string;
  recovery_next_step?: string;
  approval_status?: string;
  capability?: string;
  subsystem?: string;
  domain?: string;
  mission_id?: string;
  active_stage?: string;
  handoff_stage?: string;
  handoff_action?: string;
  handoff_gate?: string;
  handoff_approval_id?: string;
  handoff_approval_status?: string;
  handoff_operation_id?: string;
  handoff_trace_id?: string;
  handoff_run_id?: string;
  handoff_artifact_dir?: string;
  handoff_next_step?: string;
  current_task_source?: string;
  current_task_gate?: string;
  current_task_approval_id?: string;
  current_task_approval_status?: string;
  current_task_operation_id?: string;
  current_task_operation_name?: string;
  current_task_operation_plane?: string;
  current_task_trace_id?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  current_task_advance_action?: string;
  current_task_next_step?: string;
  memory_receipt_count?: number;
  operation_id?: string;
  trace_id?: string;
  approval_id?: string;
  run_id?: string;
  artifact_dir?: string;
  references?: {
    mission_id?: string;
    operation_id?: string;
    trace_id?: string;
    approval_id?: string;
    run_id?: string;
    artifact_dir?: string;
  };
};

export type MissionGovernanceDecision = {
  gate?: string;
  reason?: string;
  next_step?: string;
  evidence?: Record<string, unknown>;
};

export type MissionDetail = {
  ok: boolean;
  mission?: MissionRecord;
  history?: MissionHistoryEntry[];
  linked_operations?: OperationDetail[];
  run_ledger?: OperationRecord[];
  loop_state?: MissionLoopState;
  current_task?: MissionCurrentTask;
  queue_item?: MissionQueueItem;
  receipt_summary?: MissionReceiptSummary;
  memory_receipts?: MissionMemoryReceipt[];
  memory_receipt_count?: number;
  latest_memory_receipt?: MissionMemoryReceipt;
  governance?: MissionGovernanceDecision;
  error?: string;
};

export type MissionListResponse = {
  items: MissionRecord[];
  total?: number;
  limit?: number;
  error?: string;
};

export type MissionCreateRequest = {
  objective: string;
  summary?: string;
  next_step?: string;
  requester_id?: string;
  actor?: string;
  owner_id?: string;
  priority?: number;
  risk_tier?: string;
  dependency_ids?: string[];
  escalation_path?: string;
  status?: string;
  linked_task_ids?: string[];
  meta?: Record<string, unknown>;
};

export type MissionCreateResponse = {
  ok: boolean;
  mission_id?: string;
  status?: string;
  mission?: MissionRecord;
  history?: MissionHistoryEntry[];
  linked_operations?: OperationDetail[];
  run_ledger?: OperationRecord[];
  loop_state?: MissionLoopState;
  current_task?: MissionCurrentTask;
  queue_item?: MissionQueueItem;
  receipt_summary?: MissionReceiptSummary;
  memory_receipts?: MissionMemoryReceipt[];
  memory_receipt_count?: number;
  latest_memory_receipt?: MissionMemoryReceipt;
  governance?: MissionGovernanceDecision;
  message?: string;
  error?: string;
};

export type MissionReplaceRequest = {
  objective?: string;
  summary?: string;
  next_step?: string;
  owner_id?: string;
  priority?: number;
  risk_tier?: string;
  actor?: string;
  note?: string;
  meta?: Record<string, unknown>;
};

export type MissionReplaceResponse = MissionCreateResponse & {
  replacement_mission_id?: string;
  source_mission?: MissionRecord;
  source_queue_item?: MissionQueueItem;
};

export type MissionQueueItem = MissionRecord & {
  recommended_action?: string;
  action_target_id?: string;
  operator_hint?: string;
  advance?: MissionAdvanceProjection;
  recovery?: MissionRecoveryProjection;
  dependency_state?: MissionDependencyState;
  current_task?: MissionCurrentTask;
  loop_state?: MissionLoopState;
  handoff?: MissionLoopHandoff;
  receipt_summary?: MissionReceiptSummary;
  last_task_id?: string;
  last_task_status?: string;
  last_task_result_status?: string;
  last_task_gate?: string;
  last_task_next_step?: string;
  last_task_reason?: string;
  last_task_approval_id?: string;
  last_task_previous_approval_id?: string;
  last_task_previous_approval_status?: string;
  last_task_approval_status?: string;
  last_task_approval_replacement_kind?: string;
  last_task_approval_replacement_reason?: string;
  last_task_approval_replacement_changed_keys?: string[];
  last_advance_action?: string;
  last_advance_outcome?: string;
  last_advance_operation_id?: string;
  last_advance_operation_name?: string;
  last_advance_operation_plane?: string;
  last_advance_operation_status?: string;
  last_advance_message?: string;
  last_advance_actor?: string;
  last_advance_applied?: boolean;
  last_advance_at?: string;
  last_recovery_action?: string;
  last_recovery_outcome?: string;
  last_recovery_target_id?: string;
  last_recovery_message?: string;
  last_recovery_actor?: string;
  last_recovery_source_status?: string;
  last_recovery_at?: string;
  history_count?: number;
  linked_operation_count?: number;
  run_ledger_count?: number;
  latest_history_event?: string;
  latest_history_ts?: string;
  history_tail?: MissionHistoryEntry[];
};

export type MissionAdvanceRequest = {
  actor?: string;
  note?: string;
  worker_id?: string;
};

export type MissionAdvanceResponse = {
  ok: boolean;
  applied?: boolean;
  action?: string;
  mission?: MissionRecord;
  operation?: OperationRecord;
  memory_receipt?: MissionMemoryReceipt;
  operation_id?: string;
  approval_id?: string;
  gate?: string;
  next_step?: string;
  operation_error?: string;
  result_message?: string;
  recovery_next_step?: string;
  run_id?: string;
  artifact_dir?: string;
  history?: MissionHistoryEntry[];
  linked_operations?: OperationDetail[];
  run_ledger?: OperationRecord[];
  loop_state?: MissionLoopState;
  current_task?: MissionCurrentTask;
  queue_item?: MissionQueueItem;
  receipt_summary?: MissionReceiptSummary;
  memory_receipts?: MissionMemoryReceipt[];
  memory_receipt_count?: number;
  latest_memory_receipt?: MissionMemoryReceipt;
  governance?: MissionGovernanceDecision;
  status?: string;
  message?: string;
  error?: string;
};

export type MissionRunOnceRequest = {
  actor?: string;
  note?: string;
  limit?: number;
};

export type MissionRunOnceResult = {
  mission_id?: string;
  ok?: boolean;
  applied?: boolean;
  action?: string;
  mission?: MissionRecord;
  operation?: OperationRecord;
  memory_receipt?: MissionMemoryReceipt;
  queue_item?: MissionQueueItem;
  status?: string;
  operation_id?: string;
  approval_id?: string;
  gate?: string;
  next_step?: string;
  operation_error?: string;
  result_message?: string;
  recovery_next_step?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
  loop_state?: MissionLoopState;
  current_task?: MissionCurrentTask;
  handoff?: MissionLoopHandoff;
  receipt_summary?: MissionReceiptSummary;
  memory_receipts?: MissionMemoryReceipt[];
  memory_receipt_count?: number;
  latest_memory_receipt?: MissionMemoryReceipt;
  history_count?: number;
  linked_operation_count?: number;
  run_ledger_count?: number;
  governance?: MissionGovernanceDecision;
  message?: string;
};

export type MissionRunOnceResponse = {
  ok: boolean;
  items: MissionQueueItem[];
  failed: MissionQueueItem[];
  deadletter: MissionQueueItem[];
  total?: number;
  applied?: number;
  advanced?: number;
  processed?: number;
  counts?: Record<string, number>;
  results?: MissionRunOnceResult[];
  errors?: Array<Record<string, unknown>>;
  status?: string;
  error?: string;
  request?: MissionRunOnceRequest;
  governance?: MissionGovernanceDecision;
};

export type MissionQueueResponse = {
  ok: boolean;
  items: MissionQueueItem[];
  failed: MissionQueueItem[];
  deadletter: MissionQueueItem[];
  total?: number;
  error?: string;
  governance?: MissionGovernanceDecision;
};

export type MissionQueuePresentation = {
  lead?: MissionQueueItem;
  ordered: MissionQueueItem[];
  visible: MissionQueueItem[];
  total: number;
  reviewRequired: number;
  eligible: number;
  hiddenTotal: number;
  hiddenReviewRequired: number;
  hiddenEligible: number;
};

export type MissionTaskTarget = {
  linked_task_ids?: unknown[];
  last_task_id?: unknown;
  meta?: Record<string, unknown>;
};

export type MissionQueueTaskTarget = {
  action_target_id?: unknown;
  last_task_id?: unknown;
  last_advance_operation_id?: unknown;
};

export type MissionTaskHandoffTarget = {
  operation_id?: unknown;
};

export type MissionCurrentTaskTarget = {
  operation_id?: unknown;
};

export class MissionsApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(message: string, opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown }) {
    super(message);
    this.name = "MissionsApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.bodySnippet = opts?.bodySnippet;
    // @ts-expect-error Error.cause depends on TS lib target.
    this.cause = opts?.cause;
  }
}

type TimeoutFetchInit = RequestInit & {
  timeoutMs?: number;
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function safeBoolean(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function safeStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.map((item) => (typeof item === "string" ? item.trim() : "")).filter((item) => item.length > 0);
  return out.length ? out : undefined;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

async function readTextSnippet(res: Response, maxChars = 1200): Promise<string> {
  try {
    const text = await res.text();
    return text.slice(0, maxChars);
  } catch {
    return "";
  }
}

async function fetchWithTimeout(url: string, init?: TimeoutFetchInit): Promise<Response> {
  const timeoutMs = Math.max(1000, Math.floor(init?.timeoutMs ?? 20_000));
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(new Error(`Mission request timed out after ${timeoutMs}ms`)), timeoutMs);

  try {
    const signal = init?.signal
      ? AbortSignal.any
        ? AbortSignal.any([init.signal, controller.signal])
        : controller.signal
      : controller.signal;
    const response = await fetch(url, {
      ...init,
      signal,
      headers: {
        Accept: "application/json, text/plain;q=0.9, */*;q=0.8",
        ...(init?.headers ?? {}),
      },
    });
    return response;
  } catch (err) {
    if (err instanceof MissionsApiError) throw err;
    throw new MissionsApiError("Mission request failed", { url, cause: err });
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchJson(url: string, init?: TimeoutFetchInit): Promise<unknown> {
  const res = await fetchWithTimeout(url, init);
  if (!res.ok) {
    const snippet = await readTextSnippet(res);
    throw new MissionsApiError(`HTTP ${res.status} for mission request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function parseMissionRecord(raw: unknown): MissionRecord | undefined {
  if (!isRecord(raw)) return undefined;

  const id = safeString(raw.id) || safeString(raw.mission_id);
  if (!id) return undefined;

  const record: MissionRecord = {
    id,
    status: safeString(raw.status, "") || undefined,
    objective: safeString(raw.objective, "") || undefined,
    summary: safeString(raw.summary, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    requester_id: safeString(raw.requester_id, "") || undefined,
    owner_id: safeString(raw.owner_id, "") || undefined,
    priority: safeNumber(raw.priority, 0) || undefined,
    risk_tier: safeString(raw.risk_tier, "") || undefined,
    dependency_ids: safeStringArray(raw.dependency_ids),
    dependency_count: safeNumber(raw.dependency_count, 0) || undefined,
    escalation_path: safeString(raw.escalation_path, "") || undefined,
    linked_task_ids: safeStringArray(raw.linked_task_ids),
    linked_task_count: safeNumber(raw.linked_task_count, 0) || undefined,
    deadletter_reason: safeString(raw.deadletter_reason, "") || undefined,
    last_task_id: safeString(raw.last_task_id, "") || undefined,
    last_task_status: safeString(raw.last_task_status, "") || undefined,
    last_task_result_status: safeString(raw.last_task_result_status, "") || undefined,
    last_task_reason: safeString(raw.last_task_reason, "") || undefined,
    last_task_gate: safeString(raw.last_task_gate, "") || undefined,
    last_task_next_step: safeString(raw.last_task_next_step, "") || undefined,
    last_advance_operation_id: safeString(raw.last_advance_operation_id, "") || undefined,
    last_advance_operation_name: safeString(raw.last_advance_operation_name, "") || undefined,
    last_advance_operation_plane: safeString(raw.last_advance_operation_plane, "") || undefined,
    last_task_approval_id: safeString(raw.last_task_approval_id, "") || undefined,
    last_task_previous_approval_id: safeString(raw.last_task_previous_approval_id, "") || undefined,
    last_task_previous_approval_status: safeString(raw.last_task_previous_approval_status, "") || undefined,
    last_task_approval_status: safeString(raw.last_task_approval_status, "") || undefined,
    last_task_approval_replacement_kind: safeString(raw.last_task_approval_replacement_kind, "") || undefined,
    last_task_approval_replacement_reason: safeString(raw.last_task_approval_replacement_reason, "") || undefined,
    last_task_approval_replacement_changed_keys: safeStringArray(raw.last_task_approval_replacement_changed_keys),
    replacement_for_mission_id: safeString(raw.replacement_for_mission_id, "") || undefined,
    replacement_for_status: safeString(raw.replacement_for_status, "") || undefined,
    replacement_source_objective: safeString(raw.replacement_source_objective, "") || undefined,
    replacement_source_action: safeString(raw.replacement_source_action, "") || undefined,
    replacement_source_target_id: safeString(raw.replacement_source_target_id, "") || undefined,
    replacement_reason: safeString(raw.replacement_reason, "") || undefined,
    replacement_declared_by: safeString(raw.replacement_declared_by, "") || undefined,
    replacement_note: safeString(raw.replacement_note, "") || undefined,
    created_at: safeString(raw.created_at, "") || undefined,
    updated_at: safeString(raw.updated_at, "") || undefined,
    meta: isRecord(raw.meta) ? raw.meta : undefined,
  };

  return record;
}

function parseMissionDependencyItem(raw: unknown): MissionDependencyItem | undefined {
  if (!isRecord(raw)) return undefined;
  return {
    id: safeString(raw.id, "") || undefined,
    kind: safeString(raw.kind, "") || undefined,
    state: safeString(raw.state, "") || undefined,
    status: safeString(raw.status, "") || undefined,
    result_status: safeString(raw.result_status, "") || undefined,
    gate: safeString(raw.gate, "") || undefined,
    approval_id: safeString(raw.approval_id, "") || undefined,
    objective: safeString(raw.objective, "") || undefined,
    detail: safeString(raw.detail, "") || undefined,
    updated_at: safeString(raw.updated_at, "") || undefined,
  };
}

function parseMissionDependencyState(raw: unknown): MissionDependencyState | undefined {
  if (!isRecord(raw)) return undefined;
  const items = Array.isArray(raw.items)
    ? raw.items.map(parseMissionDependencyItem).filter((item): item is MissionDependencyItem => item !== undefined)
    : [];
  return {
    status: safeString(raw.status, "") || undefined,
    total: safeNumber(raw.total, 0),
    resolved: safeNumber(raw.resolved, 0),
    unresolved: safeNumber(raw.unresolved, 0),
    items,
    first_unresolved: parseMissionDependencyItem(raw.first_unresolved),
  };
}

function parseMissionAdvanceProjection(raw: unknown): MissionAdvanceProjection | undefined {
  if (!isRecord(raw)) return undefined;
  const projection: MissionAdvanceProjection = {
    eligible: safeBoolean(raw.eligible, false),
    action: safeString(raw.action, "") || undefined,
    target_id: safeString(raw.target_id, "") || undefined,
    reason: safeString(raw.reason, "") || undefined,
  };
  if (!projection.eligible && !projection.action && !projection.target_id && !projection.reason) return undefined;
  return projection;
}

function parseMissionRecoveryProjection(raw: unknown): MissionRecoveryProjection | undefined {
  if (!isRecord(raw)) return undefined;
  const projection: MissionRecoveryProjection = {
    source_status: safeString(raw.source_status, "") || undefined,
    action: safeString(raw.action, "") || undefined,
    target_id: safeString(raw.target_id, "") || undefined,
    reason: safeString(raw.reason, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    operator_required: safeBoolean(raw.operator_required, false),
    automatic_retry: safeBoolean(raw.automatic_retry, false),
    read_only: safeBoolean(raw.read_only, false),
    last_review_action: safeString(raw.last_review_action, "") || undefined,
    last_review_outcome: safeString(raw.last_review_outcome, "") || undefined,
    last_review_target_id: safeString(raw.last_review_target_id, "") || undefined,
    last_review_actor: safeString(raw.last_review_actor, "") || undefined,
    last_reviewed_at: safeString(raw.last_reviewed_at, "") || undefined,
    replacement_mission_id: safeString(raw.replacement_mission_id, "") || undefined,
    replacement_status: safeString(raw.replacement_status, "") || undefined,
    replacement_objective: safeString(raw.replacement_objective, "") || undefined,
    replacement_next_step: safeString(raw.replacement_next_step, "") || undefined,
    replacement_last_task_id: safeString(raw.replacement_last_task_id, "") || undefined,
    replacement_last_task_status: safeString(raw.replacement_last_task_status, "") || undefined,
    replacement_updated_at: safeString(raw.replacement_updated_at, "") || undefined,
    replacement_terminal: safeBoolean(raw.replacement_terminal, false),
    replacement_error: safeString(raw.replacement_error, "") || undefined,
  };
  if (
    !projection.source_status &&
    !projection.action &&
    !projection.target_id &&
    !projection.reason &&
    !projection.next_step &&
    !projection.operator_required &&
    !projection.automatic_retry &&
    !projection.read_only &&
    !projection.last_review_action &&
    !projection.last_review_outcome &&
    !projection.last_review_target_id &&
    !projection.last_review_actor &&
    !projection.last_reviewed_at &&
    !projection.replacement_mission_id &&
    !projection.replacement_status &&
    !projection.replacement_objective &&
    !projection.replacement_next_step &&
    !projection.replacement_last_task_id &&
    !projection.replacement_last_task_status &&
    !projection.replacement_updated_at &&
    !projection.replacement_terminal &&
    !projection.replacement_error
  ) {
    return undefined;
  }
  return projection;
}

function parseMissionQueueItem(raw: unknown): MissionQueueItem | undefined {
  const record = parseMissionRecord(raw);
  if (!record || !isRecord(raw)) return record;

  return {
    ...record,
    recommended_action: safeString(raw.recommended_action, "") || undefined,
    action_target_id: safeString(raw.action_target_id, "") || undefined,
    operator_hint: safeString(raw.operator_hint, "") || undefined,
    advance: parseMissionAdvanceProjection(raw.advance),
    recovery: parseMissionRecoveryProjection(raw.recovery),
    dependency_state: parseMissionDependencyState(raw.dependency_state),
    current_task: parseMissionCurrentTask(raw.current_task),
    loop_state: parseMissionLoopState(raw.loop_state),
    handoff: parseMissionLoopHandoff(raw.handoff),
    receipt_summary: parseMissionReceiptSummary(raw.receipt_summary),
    last_task_id: safeString(raw.last_task_id, "") || undefined,
    last_task_status: safeString(raw.last_task_status, "") || undefined,
    last_task_result_status: safeString(raw.last_task_result_status, "") || undefined,
    last_task_gate: safeString(raw.last_task_gate, "") || undefined,
    last_task_next_step: safeString(raw.last_task_next_step, "") || undefined,
    last_task_reason: safeString(raw.last_task_reason, "") || undefined,
    last_task_approval_id: safeString(raw.last_task_approval_id, "") || undefined,
    last_task_previous_approval_id: safeString(raw.last_task_previous_approval_id, "") || undefined,
    last_task_previous_approval_status: safeString(raw.last_task_previous_approval_status, "") || undefined,
    last_task_approval_status: safeString(raw.last_task_approval_status, "") || undefined,
    last_task_approval_replacement_kind: safeString(raw.last_task_approval_replacement_kind, "") || undefined,
    last_task_approval_replacement_reason: safeString(raw.last_task_approval_replacement_reason, "") || undefined,
    last_task_approval_replacement_changed_keys: safeStringArray(raw.last_task_approval_replacement_changed_keys),
    last_advance_action: safeString(raw.last_advance_action, "") || undefined,
    last_advance_outcome: safeString(raw.last_advance_outcome, "") || undefined,
    last_advance_operation_id: safeString(raw.last_advance_operation_id, "") || undefined,
    last_advance_operation_name: safeString(raw.last_advance_operation_name, "") || undefined,
    last_advance_operation_plane: safeString(raw.last_advance_operation_plane, "") || undefined,
    last_advance_operation_status: safeString(raw.last_advance_operation_status, "") || undefined,
    last_advance_message: safeString(raw.last_advance_message, "") || undefined,
    last_advance_actor: safeString(raw.last_advance_actor, "") || undefined,
    last_advance_applied: safeBoolean(raw.last_advance_applied, false),
    last_advance_at: safeString(raw.last_advance_at, "") || undefined,
    last_recovery_action: safeString(raw.last_recovery_action, "") || undefined,
    last_recovery_outcome: safeString(raw.last_recovery_outcome, "") || undefined,
    last_recovery_target_id: safeString(raw.last_recovery_target_id, "") || undefined,
    last_recovery_message: safeString(raw.last_recovery_message, "") || undefined,
    last_recovery_actor: safeString(raw.last_recovery_actor, "") || undefined,
    last_recovery_source_status: safeString(raw.last_recovery_source_status, "") || undefined,
    last_recovery_at: safeString(raw.last_recovery_at, "") || undefined,
    history_count: safeNumber(raw.history_count, 0) || undefined,
    linked_operation_count: safeNumber(raw.linked_operation_count, 0) || undefined,
    run_ledger_count: safeNumber(raw.run_ledger_count, 0) || undefined,
    latest_history_event: safeString(raw.latest_history_event, "") || undefined,
    latest_history_ts: safeString(raw.latest_history_ts, "") || undefined,
    history_tail: Array.isArray(raw.history_tail)
      ? raw.history_tail.map(parseMissionHistoryEntry).filter((item): item is MissionHistoryEntry => item !== null)
      : undefined,
  };
}

function parseMissionHistoryEntry(raw: unknown): MissionHistoryEntry | null {
  if (!isRecord(raw)) return null;
  return {
    ts: safeString(raw.ts, "") || undefined,
    mission_id: safeString(raw.mission_id, "") || undefined,
    event: safeString(raw.event, "") || undefined,
    details: isRecord(raw.details) ? raw.details : undefined,
  };
}

function parseMissionLoopStage(raw: unknown): MissionLoopStage | undefined {
  if (!isRecord(raw)) return undefined;

  const stage: MissionLoopStage = {
    status: safeString(raw.status, "") || undefined,
    detail: safeString(raw.detail, "") || undefined,
    count: safeNumber(raw.count, 0) || undefined,
    gate: safeString(raw.gate, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    approval_id: safeString(raw.approval_id, "") || undefined,
    approval_status: safeString(raw.approval_status, "") || undefined,
    operation_id: safeString(raw.operation_id, "") || undefined,
    trace_id: safeString(raw.trace_id, "") || undefined,
    run_id: safeString(raw.run_id, "") || undefined,
    artifact_dir: safeString(raw.artifact_dir, "") || undefined,
    latest_event: safeString(raw.latest_event, "") || undefined,
    latest_receipt_status: safeString(raw.latest_receipt_status, "") || undefined,
    latest_ts: safeString(raw.latest_ts, "") || undefined,
    memory_receipt_count: safeNumber(raw.memory_receipt_count, 0) || undefined,
    latest_memory_receipt: parseMissionMemoryReceipt(raw.latest_memory_receipt),
    plan_status: safeString(raw.plan_status, "") || undefined,
    plan_current_step_id: safeString(raw.plan_current_step_id, "") || undefined,
    plan_current_step_title: safeString(raw.plan_current_step_title, "") || undefined,
    plan_step_count: safeNumber(raw.plan_step_count, 0) || undefined,
    plan_checkpoint_count: safeNumber(raw.plan_checkpoint_count, 0) || undefined,
  };

  if (
    !stage.status &&
    !stage.detail &&
    !stage.operation_id &&
    !stage.approval_id &&
    !stage.approval_status &&
    !stage.trace_id &&
    !stage.run_id &&
    !stage.artifact_dir &&
    !stage.latest_event &&
    !stage.latest_receipt_status &&
    !stage.latest_ts &&
    !stage.next_step &&
    !stage.memory_receipt_count &&
    !stage.latest_memory_receipt &&
    !stage.plan_status &&
    !stage.plan_current_step_id &&
    !stage.plan_current_step_title &&
    !stage.plan_step_count &&
    !stage.plan_checkpoint_count
  ) {
    return undefined;
  }
  return stage;
}

function parseMissionLoopHandoff(raw: unknown): MissionLoopHandoff | undefined {
  if (!isRecord(raw)) return undefined;

  const handoff: MissionLoopHandoff = {
    stage: safeString(raw.stage, "") || undefined,
    action: safeString(raw.action, "") || undefined,
    detail: safeString(raw.detail, "") || undefined,
    gate: safeString(raw.gate, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    approval_id: safeString(raw.approval_id, "") || undefined,
    approval_status: safeString(raw.approval_status, "") || undefined,
    operation_id: safeString(raw.operation_id, "") || undefined,
    trace_id: safeString(raw.trace_id, "") || undefined,
    run_id: safeString(raw.run_id, "") || undefined,
    artifact_dir: safeString(raw.artifact_dir, "") || undefined,
    latest_event: safeString(raw.latest_event, "") || undefined,
    latest_ts: safeString(raw.latest_ts, "") || undefined,
  };

  if (
    !handoff.stage &&
    !handoff.action &&
    !handoff.detail &&
    !handoff.operation_id &&
    !handoff.approval_id &&
    !handoff.approval_status &&
    !handoff.trace_id &&
    !handoff.run_id &&
    !handoff.artifact_dir &&
    !handoff.latest_event &&
    !handoff.latest_ts &&
    !handoff.next_step
  ) {
    return undefined;
  }
  return handoff;
}

function parseMissionLoopState(raw: unknown): MissionLoopState | undefined {
  if (!isRecord(raw)) return undefined;

  const state: MissionLoopState = {
    summary: safeString(raw.summary, "") || undefined,
    active_stage: safeString(raw.active_stage, "") || undefined,
    handoff: parseMissionLoopHandoff(raw.handoff),
    plan: parseMissionLoopStage(raw.plan),
    gate: parseMissionLoopStage(raw.gate),
    execute: parseMissionLoopStage(raw.execute),
    trace: parseMissionLoopStage(raw.trace),
    memory: parseMissionLoopStage(raw.memory),
    interface: parseMissionLoopStage(raw.interface),
  };

  if (
    !state.summary &&
    !state.active_stage &&
    !state.handoff &&
    !state.plan &&
    !state.gate &&
    !state.execute &&
    !state.trace &&
    !state.memory &&
    !state.interface
  ) {
    return undefined;
  }
  return state;
}

function parseMissionCurrentTask(raw: unknown): MissionCurrentTask | undefined {
  if (!isRecord(raw)) return undefined;

  const task: MissionCurrentTask = {
    mission_id: safeString(raw.mission_id, "") || undefined,
    source: safeString(raw.source, "") || undefined,
    operation_id: safeString(raw.operation_id, "") || undefined,
    operation_name: safeString(raw.operation_name, "") || undefined,
    operation_plane: safeString(raw.operation_plane, "") || undefined,
    task_status: safeString(raw.task_status, "") || undefined,
    operation_status: safeString(raw.operation_status, "") || undefined,
    result_status: safeString(raw.result_status, "") || undefined,
    gate: safeString(raw.gate, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    reason: safeString(raw.reason, "") || undefined,
    approval_id: safeString(raw.approval_id, "") || undefined,
    approval_status: safeString(raw.approval_status, "") || undefined,
    handoff_stage: safeString(raw.handoff_stage, "") || undefined,
    handoff_action: safeString(raw.handoff_action, "") || undefined,
    advance_action: safeString(raw.advance_action, "") || undefined,
    trace_id: safeString(raw.trace_id, "") || undefined,
    run_id: safeString(raw.run_id, "") || undefined,
    artifact_dir: safeString(raw.artifact_dir, "") || undefined,
    latest_receipt_event: safeString(raw.latest_receipt_event, "") || undefined,
    latest_receipt_status: safeString(raw.latest_receipt_status, "") || undefined,
    latest_receipt_ts: safeString(raw.latest_receipt_ts, "") || undefined,
    last_advance_operation_id: safeString(raw.last_advance_operation_id, "") || undefined,
  };

  if (
    !task.mission_id &&
    !task.operation_id &&
    !task.operation_name &&
    !task.operation_plane &&
    !task.task_status &&
    !task.operation_status &&
    !task.result_status &&
    !task.gate &&
    !task.next_step &&
    !task.approval_id &&
    !task.handoff_action &&
    !task.advance_action &&
    !task.run_id &&
    !task.artifact_dir &&
    !task.latest_receipt_event &&
    !task.latest_receipt_status
  ) {
    return undefined;
  }
  return task;
}

function parseMissionReceiptSummary(raw: unknown): MissionReceiptSummary | undefined {
  if (!isRecord(raw)) return undefined;
  const summary: MissionReceiptSummary = {
    linked_operation_count: safeNumber(raw.linked_operation_count, 0) || undefined,
    run_ledger_count: safeNumber(raw.run_ledger_count, 0) || undefined,
    history_count: safeNumber(raw.history_count, 0) || undefined,
    memory_receipt_count: safeNumber(raw.memory_receipt_count, 0) || undefined,
    latest_memory_receipt: parseMissionMemoryReceipt(raw.latest_memory_receipt),
    current_operation_id: safeString(raw.current_operation_id, "") || undefined,
    current_operation_status: safeString(raw.current_operation_status, "") || undefined,
    current_gate: safeString(raw.current_gate, "") || undefined,
    current_approval_id: safeString(raw.current_approval_id, "") || undefined,
    current_trace_id: safeString(raw.current_trace_id, "") || undefined,
    current_run_id: safeString(raw.current_run_id, "") || undefined,
    current_artifact_dir: safeString(raw.current_artifact_dir, "") || undefined,
    latest_run_event: safeString(raw.latest_run_event, "") || undefined,
    latest_run_status: safeString(raw.latest_run_status, "") || undefined,
    latest_run_ts: safeString(raw.latest_run_ts, "") || undefined,
    latest_history_event: safeString(raw.latest_history_event, "") || undefined,
    latest_history_ts: safeString(raw.latest_history_ts, "") || undefined,
  };
  if (
    !summary.linked_operation_count &&
    !summary.run_ledger_count &&
    !summary.history_count &&
    !summary.memory_receipt_count &&
    !summary.latest_memory_receipt &&
    !summary.current_operation_id &&
    !summary.current_run_id &&
    !summary.current_artifact_dir &&
    !summary.latest_run_event &&
    !summary.latest_history_event
  ) {
    return undefined;
  }
  return summary;
}

function parseMissionMemoryReceipt(raw: unknown): MissionMemoryReceipt | undefined {
  if (!isRecord(raw)) return undefined;
  const referencesRaw = isRecord(raw.references) ? raw.references : {};
  const mission_id = safeString(raw.mission_id, "") || safeString(referencesRaw.mission_id, "") || undefined;
  const operation_id = safeString(raw.operation_id, "") || safeString(referencesRaw.operation_id, "") || undefined;
  const trace_id = safeString(raw.trace_id, "") || safeString(referencesRaw.trace_id, "") || undefined;
  const approval_id = safeString(raw.approval_id, "") || safeString(referencesRaw.approval_id, "") || undefined;
  const run_id = safeString(raw.run_id, "") || safeString(referencesRaw.run_id, "") || undefined;
  const artifact_dir = safeString(raw.artifact_dir, "") || safeString(referencesRaw.artifact_dir, "") || undefined;
  const references = {
    mission_id,
    operation_id,
    trace_id,
    approval_id,
    run_id,
    artifact_dir,
  };
  const receipt: MissionMemoryReceipt = {
    id: safeString(raw.id, "") || undefined,
    source: safeString(raw.source, "") || undefined,
    kind: safeString(raw.kind, "") || undefined,
    ts: safeNumber(raw.ts, 0) || undefined,
    role: safeString(raw.role, "") || undefined,
    message: safeString(raw.message, "") || undefined,
    scope: safeString(raw.scope, "") || undefined,
    operation_status: safeString(raw.operation_status, "") || undefined,
    operation_error: safeString(raw.operation_error, "") || undefined,
    result_message: safeString(raw.result_message, "") || undefined,
    recovery_next_step: safeString(raw.recovery_next_step, "") || undefined,
    approval_status: safeString(raw.approval_status, "") || undefined,
    capability: safeString(raw.capability, "") || undefined,
    subsystem: safeString(raw.subsystem, "") || undefined,
    domain: safeString(raw.domain, "") || undefined,
    mission_id,
    active_stage: safeString(raw.active_stage, "") || undefined,
    handoff_stage: safeString(raw.handoff_stage, "") || undefined,
    handoff_action: safeString(raw.handoff_action, "") || undefined,
    handoff_gate: safeString(raw.handoff_gate, "") || undefined,
    handoff_approval_id: safeString(raw.handoff_approval_id, "") || undefined,
    handoff_approval_status: safeString(raw.handoff_approval_status, "") || undefined,
    handoff_operation_id: safeString(raw.handoff_operation_id, "") || undefined,
    handoff_trace_id: safeString(raw.handoff_trace_id, "") || undefined,
    handoff_run_id: safeString(raw.handoff_run_id, "") || undefined,
    handoff_artifact_dir: safeString(raw.handoff_artifact_dir, "") || undefined,
    handoff_next_step: safeString(raw.handoff_next_step, "") || undefined,
    current_task_source: safeString(raw.current_task_source, "") || undefined,
    current_task_gate: safeString(raw.current_task_gate, "") || undefined,
    current_task_approval_id: safeString(raw.current_task_approval_id, "") || undefined,
    current_task_approval_status: safeString(raw.current_task_approval_status, "") || undefined,
    current_task_operation_id: safeString(raw.current_task_operation_id, "") || undefined,
    current_task_operation_name: safeString(raw.current_task_operation_name, "") || undefined,
    current_task_operation_plane: safeString(raw.current_task_operation_plane, "") || undefined,
    current_task_trace_id: safeString(raw.current_task_trace_id, "") || undefined,
    current_task_run_id: safeString(raw.current_task_run_id, "") || undefined,
    current_task_artifact_dir: safeString(raw.current_task_artifact_dir, "") || undefined,
    current_task_advance_action: safeString(raw.current_task_advance_action, "") || undefined,
    current_task_next_step: safeString(raw.current_task_next_step, "") || undefined,
    memory_receipt_count: safeNumber(raw.memory_receipt_count, 0) || undefined,
    operation_id,
    trace_id,
    approval_id,
    run_id,
    artifact_dir,
  };
  if (Object.values(references).some((value) => value)) receipt.references = references;
  if (
    !receipt.id &&
    !receipt.source &&
    !receipt.kind &&
    !receipt.message &&
    !receipt.scope &&
    !receipt.operation_status &&
    !receipt.operation_error &&
    !receipt.result_message &&
    !receipt.recovery_next_step &&
    !receipt.approval_status &&
    !receipt.domain &&
    !receipt.active_stage &&
    !receipt.handoff_action &&
    !receipt.handoff_gate &&
    !receipt.handoff_approval_id &&
    !receipt.handoff_approval_status &&
    !receipt.handoff_operation_id &&
    !receipt.handoff_next_step &&
    !receipt.current_task_gate &&
    !receipt.current_task_approval_id &&
    !receipt.current_task_approval_status &&
    !receipt.current_task_operation_id &&
    !receipt.current_task_operation_name &&
    !receipt.current_task_operation_plane &&
    !receipt.current_task_advance_action &&
    !receipt.current_task_next_step &&
    !receipt.memory_receipt_count &&
    !receipt.references
  ) {
    return undefined;
  }
  return receipt;
}

function parseMissionMemoryReceipts(raw: unknown): MissionMemoryReceipt[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(parseMissionMemoryReceipt).filter((item): item is MissionMemoryReceipt => item !== undefined);
}

function parseMissionGovernance(raw: unknown): MissionGovernanceDecision | undefined {
  if (!isRecord(raw)) return undefined;
  const governance: MissionGovernanceDecision = {
    gate: safeString(raw.gate, "") || undefined,
    reason: safeString(raw.reason, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    evidence: isRecord(raw.evidence) ? raw.evidence : undefined,
  };
  if (!governance.gate && !governance.reason && !governance.next_step && !governance.evidence) return undefined;
  return governance;
}

function parseMissionDetail(json: unknown, idHint = ""): MissionDetail {
  if (!isRecord(json)) {
    return {
      ok: false,
      mission: idHint ? { id: idHint } : undefined,
      history: [],
      linked_operations: [],
      run_ledger: [],
      error: typeof json === "string" ? json : "invalid_mission_payload",
    };
  }

  const mission = parseMissionRecord(json.mission) ?? parseMissionRecord(json) ?? (idHint ? { id: idHint } : undefined);
  const history = Array.isArray(json.history)
    ? json.history.map(parseMissionHistoryEntry).filter((item): item is MissionHistoryEntry => item !== null)
    : [];
  const linked_operations = Array.isArray(json.linked_operations)
    ? json.linked_operations
        .map((item) => parseOperationDetail(item, mission?.id ?? idHint))
        .filter((item): item is OperationDetail => item !== null)
    : [];
  const run_ledger = Array.isArray(json.run_ledger)
    ? json.run_ledger
        .map((item) => {
          const parsed = parseOperationRecord(item);
          if (!parsed || !isRecord(item)) return parsed;
          const mergedMeta: Record<string, unknown> = {
            ...(isRecord(parsed.meta) ? parsed.meta : {}),
          };
          if (safeString(item.operation_id)) mergedMeta.operation_id = safeString(item.operation_id);
          if (safeString(item.operation_name)) mergedMeta.operation_name = safeString(item.operation_name);
          if (safeString(item.operation_status)) mergedMeta.operation_status = safeString(item.operation_status);
          if (!Object.keys(mergedMeta).length) return parsed;
          return { ...parsed, meta: mergedMeta };
        })
        .filter((item): item is OperationRecord => item !== null)
    : [];
  const memory_receipts = parseMissionMemoryReceipts(json.memory_receipts);
  const latest_memory_receipt = parseMissionMemoryReceipt(json.latest_memory_receipt) ?? memory_receipts[0];
  const memory_receipt_count = safeNumber(json.memory_receipt_count, Number.NaN);

  return {
    ok: safeBoolean(json.ok, Boolean(mission)),
    mission,
    history,
    linked_operations,
    run_ledger,
    loop_state: parseMissionLoopState(json.loop_state),
    current_task: parseMissionCurrentTask(json.current_task),
    queue_item: parseMissionQueueItem(json.queue_item),
    receipt_summary: parseMissionReceiptSummary(json.receipt_summary),
    memory_receipts,
    memory_receipt_count: Number.isFinite(memory_receipt_count)
      ? memory_receipt_count
      : memory_receipts.length || undefined,
    latest_memory_receipt,
    governance: parseMissionGovernance(json.governance),
    error: safeString(json.error, "") || undefined,
  };
}

function parseMissionDetailParts(json: Record<string, unknown>, missionId = ""): Pick<
  MissionDetail,
  | "history"
  | "linked_operations"
  | "run_ledger"
  | "loop_state"
  | "current_task"
  | "queue_item"
  | "receipt_summary"
  | "memory_receipts"
  | "memory_receipt_count"
  | "latest_memory_receipt"
  | "governance"
> {
  const parsed = parseMissionDetail(json, missionId);
  return {
    history: parsed.history,
    linked_operations: parsed.linked_operations,
    run_ledger: parsed.run_ledger,
    loop_state: parsed.loop_state,
    current_task: parsed.current_task,
    queue_item: parsed.queue_item,
    receipt_summary: parsed.receipt_summary,
    memory_receipts: parsed.memory_receipts,
    memory_receipt_count: parsed.memory_receipt_count,
    latest_memory_receipt: parsed.latest_memory_receipt,
    governance: parsed.governance,
  };
}

function parseMissionListResponse(json: unknown): MissionListResponse {
  if (!isRecord(json)) {
    return {
      items: [],
      total: 0,
      limit: 0,
      error: typeof json === "string" ? json : "invalid_mission_list_payload",
    };
  }

  const items = Array.isArray(json.items)
    ? json.items.map(parseMissionRecord).filter((item): item is MissionRecord => item !== undefined)
    : [];

  return {
    items,
    total: safeNumber(json.total, items.length) || undefined,
    limit: safeNumber(json.limit, 0) || undefined,
    error: safeString(json.error, "") || undefined,
  };
}

function parseMissionCreateResponse(json: unknown): MissionCreateResponse {
  if (!isRecord(json)) {
    return {
      ok: false,
      error: typeof json === "string" ? json : "invalid_mission_create_payload",
    };
  }

  return {
    ok: safeBoolean(json.ok, false),
    mission_id: safeString(json.mission_id, "") || undefined,
    status: safeString(json.status, "") || undefined,
    mission: parseMissionRecord(json.mission),
    ...parseMissionDetailParts(json, safeString(json.mission_id, "")),
    governance: parseMissionGovernance(json.governance),
    message: safeString(json.message, "") || undefined,
    error: safeString(json.error, "") || undefined,
  };
}

function parseMissionReplaceResponse(json: unknown): MissionReplaceResponse {
  if (!isRecord(json)) {
    return {
      ok: false,
      error: typeof json === "string" ? json : "invalid_mission_replace_payload",
    };
  }

  return {
    ok: safeBoolean(json.ok, false),
    mission_id: safeString(json.mission_id, "") || safeString(json.replacement_mission_id, "") || undefined,
    replacement_mission_id: safeString(json.replacement_mission_id, "") || undefined,
    status: safeString(json.status, "") || undefined,
    mission: parseMissionRecord(json.mission),
    source_mission: parseMissionRecord(json.source_mission),
    source_queue_item: parseMissionQueueItem(json.source_queue_item),
    ...parseMissionDetailParts(json, safeString(json.replacement_mission_id, "") || safeString(json.mission_id, "")),
    governance: parseMissionGovernance(json.governance),
    message: safeString(json.message, "") || undefined,
    error: safeString(json.error, "") || undefined,
  };
}

function parseMissionAdvanceResponse(json: unknown): MissionAdvanceResponse {
  if (!isRecord(json)) {
    return {
      ok: false,
      error: typeof json === "string" ? json : "invalid_mission_advance_payload",
    };
  }

  return {
    ok: safeBoolean(json.ok, false),
    applied: safeBoolean(json.applied, false),
    action: safeString(json.action, "") || undefined,
    mission: parseMissionRecord(json.mission),
    operation: parseOperationRecord(json.operation) ?? undefined,
    memory_receipt: parseMissionMemoryReceipt(json.memory_receipt),
    operation_id: safeString(json.operation_id, "") || undefined,
    approval_id: safeString(json.approval_id, "") || undefined,
    gate: safeString(json.gate, "") || undefined,
    next_step: safeString(json.next_step, "") || undefined,
    operation_error: safeString(json.operation_error, "") || undefined,
    result_message: safeString(json.result_message, "") || undefined,
    recovery_next_step: safeString(json.recovery_next_step, "") || undefined,
    run_id: safeString(json.run_id, "") || undefined,
    artifact_dir: safeString(json.artifact_dir, "") || undefined,
    ...parseMissionDetailParts(json, safeString(json.mission_id, "")),
    governance: parseMissionGovernance(json.governance),
    status: safeString(json.status, "") || undefined,
    message: safeString(json.message, "") || undefined,
    error: safeString(json.error, "") || undefined,
  };
}

function parseMissionRunOnceResult(raw: unknown): MissionRunOnceResult | null {
  if (!isRecord(raw)) return null;
  return {
    mission_id: safeString(raw.mission_id, "") || undefined,
    ok: safeBoolean(raw.ok, false),
    applied: safeBoolean(raw.applied, false),
    action: safeString(raw.action, "") || undefined,
    mission: parseMissionRecord(raw.mission),
    operation: parseOperationRecord(raw.operation) ?? undefined,
    memory_receipt: parseMissionMemoryReceipt(raw.memory_receipt),
    queue_item: parseMissionQueueItem(raw.queue_item),
    status: safeString(raw.status, "") || undefined,
    operation_id: safeString(raw.operation_id, "") || undefined,
    approval_id: safeString(raw.approval_id, "") || undefined,
    gate: safeString(raw.gate, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    operation_error: safeString(raw.operation_error, "") || undefined,
    result_message: safeString(raw.result_message, "") || undefined,
    recovery_next_step: safeString(raw.recovery_next_step, "") || undefined,
    trace_id: safeString(raw.trace_id, "") || undefined,
    run_id: safeString(raw.run_id, "") || undefined,
    artifact_dir: safeString(raw.artifact_dir, "") || undefined,
    loop_state: parseMissionLoopState(raw.loop_state),
    current_task: parseMissionCurrentTask(raw.current_task),
    handoff: parseMissionLoopHandoff(raw.handoff),
    receipt_summary: parseMissionReceiptSummary(raw.receipt_summary),
    memory_receipts: parseMissionMemoryReceipts(raw.memory_receipts),
    memory_receipt_count: safeNumber(raw.memory_receipt_count, 0) || undefined,
    latest_memory_receipt: parseMissionMemoryReceipt(raw.latest_memory_receipt),
    governance: parseMissionGovernance(raw.governance),
    history_count: safeNumber(raw.history_count, 0) || undefined,
    linked_operation_count: safeNumber(raw.linked_operation_count, 0) || undefined,
    run_ledger_count: safeNumber(raw.run_ledger_count, 0) || undefined,
    message: safeString(raw.message, "") || undefined,
  };
}

function parseMissionRunOnceResponse(json: unknown): MissionRunOnceResponse {
  if (!isRecord(json)) {
    return {
      ok: false,
      items: [],
      failed: [],
      deadletter: [],
      error: typeof json === "string" ? json : "invalid_mission_run_once_payload",
    };
  }

  const items = Array.isArray(json.items)
    ? json.items.map(parseMissionQueueItem).filter((item): item is MissionQueueItem => item !== undefined)
    : [];
  const deadletter = Array.isArray(json.deadletter)
    ? json.deadletter.map(parseMissionQueueItem).filter((item): item is MissionQueueItem => item !== undefined)
    : [];
  const failed = Array.isArray(json.failed)
    ? json.failed.map(parseMissionQueueItem).filter((item): item is MissionQueueItem => item !== undefined)
    : [];
  const results = Array.isArray(json.results)
    ? json.results.map(parseMissionRunOnceResult).filter((item): item is MissionRunOnceResult => item !== null)
    : [];
  const errors = Array.isArray(json.errors)
    ? json.errors.filter((item): item is Record<string, unknown> => isRecord(item))
    : [];
  const counts = isRecord(json.counts)
    ? Object.fromEntries(
        Object.entries(json.counts).flatMap(([key, value]) =>
          typeof value === "number" && Number.isFinite(value) ? [[key, value]] : [],
        ),
      )
    : undefined;
  let request: MissionRunOnceRequest | undefined;
  if (isRecord(json.request)) {
    request = {};
    const actor = safeString(json.request.actor, "");
    const note = safeString(json.request.note, "");
    const limit = safeNumber(json.request.limit, 0);
    if (actor) request.actor = actor;
    if (note) request.note = note;
    if (limit) request.limit = limit;
    if (Object.keys(request).length === 0) request = undefined;
  }

  return {
    ok: safeBoolean(json.ok, false),
    items,
    failed,
    deadletter,
    total: safeNumber(json.total, 0) || undefined,
    applied: safeNumber(json.applied, 0) || undefined,
    advanced: safeNumber(json.advanced, 0) || undefined,
    processed: safeNumber(json.processed, 0) || undefined,
    counts,
    results,
    errors,
    status: safeString(json.status, "") || undefined,
    error: safeString(json.error, "") || undefined,
    request,
    governance: parseMissionGovernance(json.governance),
  };
}

function parseMissionQueueResponse(json: unknown): MissionQueueResponse {
  if (!isRecord(json)) {
    return {
      ok: false,
      items: [],
      failed: [],
      deadletter: [],
      error: typeof json === "string" ? json : "invalid_mission_queue_payload",
    };
  }

  const items = Array.isArray(json.items)
    ? json.items.map(parseMissionQueueItem).filter((item): item is MissionQueueItem => item !== undefined)
    : [];
  const deadletter = Array.isArray(json.deadletter)
    ? json.deadletter.map(parseMissionQueueItem).filter((item): item is MissionQueueItem => item !== undefined)
    : [];
  const failed = Array.isArray(json.failed)
    ? json.failed.map(parseMissionQueueItem).filter((item): item is MissionQueueItem => item !== undefined)
    : [];

  return {
    ok: safeBoolean(json.ok, false),
    items,
    failed,
    deadletter,
    total: safeNumber(json.total, items.length) || undefined,
    error: safeString(json.error, "") || undefined,
    governance: parseMissionGovernance(json.governance),
  };
}

function missionQueueNeedsReview(item: MissionQueueItem): boolean {
  return item.advance?.eligible !== true;
}

function missionQueueHasPendingApproval(item: MissionQueueItem): boolean {
  const approvalId = safeString(item.last_task_approval_id, "").trim();
  if (!approvalId) return false;
  const approvalStatus = safeString(item.last_task_approval_status, "").trim().toLowerCase();
  return approvalStatus === "" || approvalStatus === "pending" || approvalStatus === "requested" || approvalStatus === "needs_review";
}

function missionQueueHasUnresolvedDependency(item: MissionQueueItem): boolean {
  const dependencyState = item.dependency_state;
  const total = Math.max(0, safeNumber(dependencyState?.total, safeNumber(item.dependency_count, 0)));
  const resolved = Math.max(0, safeNumber(dependencyState?.resolved, 0));
  const unresolved = Math.max(0, safeNumber(dependencyState?.unresolved, total - resolved));
  if (unresolved > 0) return true;
  const action = safeString(item.recommended_action, "").trim();
  return action === "wait_for_dependency" || action === "resolve_dependency_blocker";
}

function missionQueueStatusRank(item: MissionQueueItem): number {
  const status = safeString(item.status, "").trim().toLowerCase();
  if (status === "blocked" || status === "deadlettered" || status === "deadletter") return 0;
  if (status === "active") return 1;
  if (status === "queued") return 2;
  return 3;
}

function missionQueueRiskRank(item: MissionQueueItem): number {
  switch (safeString(item.risk_tier, "").trim().toLowerCase()) {
    case "critical":
      return 0;
    case "high":
      return 1;
    case "medium":
      return 2;
    case "normal":
      return 3;
    case "low":
      return 4;
    default:
      return 5;
  }
}

function missionQueueSeverityRank(item: MissionQueueItem): number {
  if (!missionQueueNeedsReview(item)) return 3;
  if (missionQueueHasPendingApproval(item)) return 0;
  if (missionQueueHasUnresolvedDependency(item)) return 1;
  return 2;
}

function firstLinkedMissionTaskId(mission: MissionTaskTarget | null | undefined): string {
  if (!mission || !Array.isArray(mission.linked_task_ids)) return "";
  for (const taskId of mission.linked_task_ids) {
    const cleaned = safeString(taskId).trim();
    if (cleaned) return cleaned;
  }
  return "";
}

export function missionCurrentTaskId(
  mission: MissionTaskTarget | null | undefined,
  queueItem?: MissionQueueTaskTarget,
  handoff?: MissionTaskHandoffTarget,
  currentTask?: MissionCurrentTaskTarget,
): string {
  const currentTaskOperationId = safeString(currentTask?.operation_id).trim();
  if (currentTaskOperationId) return currentTaskOperationId;

  const queueLastTaskId = safeString(queueItem?.last_task_id).trim();
  if (queueLastTaskId) return queueLastTaskId;

  const handoffOperationId = safeString(handoff?.operation_id).trim();
  if (handoffOperationId) return handoffOperationId;

  const missionLastTaskId = safeString(mission?.last_task_id).trim();
  if (missionLastTaskId) return missionLastTaskId;

  const metaLastTaskId = isRecord(mission?.meta) ? safeString(mission.meta.last_task_id).trim() : "";
  if (metaLastTaskId) return metaLastTaskId;

  const actionTargetId = safeString(queueItem?.action_target_id).trim();
  if (actionTargetId.startsWith("tsk_")) return actionTargetId;

  const lastAdvanceOperationId = safeString(queueItem?.last_advance_operation_id).trim();
  if (lastAdvanceOperationId) return lastAdvanceOperationId;

  return firstLinkedMissionTaskId(mission);
}

export function missionRecoveryTargetId(
  mission: MissionTaskTarget | null | undefined,
  queueItem?: MissionQueueTaskTarget,
  handoff?: MissionTaskHandoffTarget,
  currentTask?: MissionCurrentTaskTarget,
): string {
  const actionTargetId = safeString(queueItem?.action_target_id).trim();
  if (actionTargetId.startsWith("msn_")) return actionTargetId;
  return missionCurrentTaskId(mission, queueItem, handoff, currentTask);
}

function operationDetailId(detail: OperationDetail | null | undefined): string {
  return safeString(detail?.operation?.id).trim();
}

export function missionCurrentOperation(linkedOperations: OperationDetail[], currentTaskId: string): OperationRecord | null {
  const current = currentTaskId
    ? linkedOperations.find((detail) => operationDetailId(detail) === currentTaskId)
    : undefined;
  return (current ?? linkedOperations[0])?.operation ?? null;
}

export function presentMissionQueue(items: MissionQueueItem[], limit = 4): MissionQueuePresentation {
  const ranked = items
    .map((item, index) => ({
      item,
      index,
      reviewRequired: missionQueueNeedsReview(item),
      severityRank: missionQueueSeverityRank(item),
      statusRank: missionQueueStatusRank(item),
      priority: safeNumber(item.priority, 0),
      riskRank: missionQueueRiskRank(item),
    }))
    .sort((left, right) => {
      if (left.reviewRequired !== right.reviewRequired) return left.reviewRequired ? -1 : 1;
      if (left.severityRank !== right.severityRank) return left.severityRank - right.severityRank;
      if (left.priority !== right.priority) return right.priority - left.priority;
      if (left.statusRank !== right.statusRank) return left.statusRank - right.statusRank;
      if (left.riskRank !== right.riskRank) return left.riskRank - right.riskRank;
      return left.index - right.index;
    });
  const ordered = ranked.map((entry) => entry.item);
  const safeLimit = Number.isFinite(limit) ? Math.max(0, Math.floor(limit)) : ordered.length;
  const visible = ordered.slice(0, safeLimit);
  const reviewRequired = ordered.filter((item) => missionQueueNeedsReview(item)).length;
  const eligible = Math.max(0, ordered.length - reviewRequired);
  const hidden = ordered.slice(visible.length);
  const hiddenReviewRequired = hidden.filter((item) => missionQueueNeedsReview(item)).length;
  const hiddenEligible = Math.max(0, hidden.length - hiddenReviewRequired);
  return {
    lead: ordered[0],
    ordered,
    visible,
    total: ordered.length,
    reviewRequired,
    eligible,
    hiddenTotal: hidden.length,
    hiddenReviewRequired,
    hiddenEligible,
  };
}

export class MissionsClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
  }

  private missionUrl(missionId: string): string {
    const cleaned = (missionId || "").trim();
    if (!cleaned) throw new Error("Mission id is required");
    return `${this.baseUrl}/missions/${encodeURIComponent(cleaned)}`;
  }

  private listUrl(limit?: number, status?: string): string {
    const url = new URL(`${this.baseUrl}/missions/list`);
    if (typeof limit === "number" && Number.isFinite(limit) && limit > 0) {
      url.searchParams.set("limit", String(Math.max(1, Math.floor(limit))));
    }
    const cleanedStatus = safeString(status, "").trim();
    if (cleanedStatus) {
      url.searchParams.set("status", cleanedStatus);
    }
    return url.toString();
  }

  private queueUrl(limit?: number, includeTerminal?: boolean): string {
    const url = new URL(`${this.baseUrl}/missions/queue`);
    if (typeof limit === "number" && Number.isFinite(limit) && limit > 0) {
      url.searchParams.set("limit", String(Math.max(1, Math.floor(limit))));
    }
    if (includeTerminal === true) {
      url.searchParams.set("include_terminal", "true");
    }
    return url.toString();
  }

  private createUrl(): string {
    return `${this.baseUrl}/missions/create`;
  }

  private advanceUrl(missionId: string): string {
    return `${this.missionUrl(missionId)}/advance`;
  }

  private replaceUrl(missionId: string): string {
    return `${this.missionUrl(missionId)}/replace`;
  }

  private runOnceUrl(): string {
    return `${this.baseUrl}/missions/run_once`;
  }

  async list(
    opts?: { signal?: AbortSignal; timeoutMs?: number; limit?: number; status?: string },
  ): Promise<MissionListResponse> {
    const json = await fetchJson(this.listUrl(opts?.limit, opts?.status), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    return parseMissionListResponse(json);
  }

  async queue(opts?: {
    signal?: AbortSignal;
    timeoutMs?: number;
    limit?: number;
    includeTerminal?: boolean;
  }): Promise<MissionQueueResponse> {
    const json = await fetchJson(this.queueUrl(opts?.limit, opts?.includeTerminal), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    return parseMissionQueueResponse(json);
  }

  async create(
    req: MissionCreateRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<MissionCreateResponse> {
    const actor = safeString(req.actor, "").trim() || safeString(req.requester_id, "").trim() || "chat_ui.operations";
    const json = await fetchJson(this.createUrl(), {
      method: "POST",
      body: JSON.stringify({ ...req, actor }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      headers: {
        "Content-Type": "application/json",
      },
    });
    return parseMissionCreateResponse(json);
  }

  async advance(
    missionId: string,
    req?: MissionAdvanceRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<MissionAdvanceResponse> {
    const json = await fetchJson(this.advanceUrl(missionId), {
      method: "POST",
      body: JSON.stringify(req ?? {}),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      headers: {
        "Content-Type": "application/json",
      },
    });
    return parseMissionAdvanceResponse(json);
  }

  async replace(
    missionId: string,
    req?: MissionReplaceRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<MissionReplaceResponse> {
    const json = await fetchJson(this.replaceUrl(missionId), {
      method: "POST",
      body: JSON.stringify(req ?? {}),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      headers: {
        "Content-Type": "application/json",
      },
    });
    return parseMissionReplaceResponse(json);
  }

  async runOnce(
    req?: MissionRunOnceRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<MissionRunOnceResponse> {
    const json = await fetchJson(this.runOnceUrl(), {
      method: "POST",
      body: JSON.stringify(req ?? {}),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      headers: {
        "Content-Type": "application/json",
      },
    });
    return parseMissionRunOnceResponse(json);
  }

  async get(missionId: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<MissionDetail> {
    const json = await fetchJson(this.missionUrl(missionId), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    return parseMissionDetail(json, missionId);
  }
}
