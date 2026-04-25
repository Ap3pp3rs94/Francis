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
  operation_id?: string;
  trace_id?: string;
  latest_event?: string;
  latest_ts?: string;
};

export type MissionLoopHandoff = {
  stage?: string;
  action?: string;
  detail?: string;
  gate?: string;
  next_step?: string;
  approval_id?: string;
  operation_id?: string;
  trace_id?: string;
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
};

export type MissionDetail = {
  ok: boolean;
  mission?: MissionRecord;
  history?: MissionHistoryEntry[];
  linked_operations?: OperationDetail[];
  run_ledger?: OperationRecord[];
  loop_state?: MissionLoopState;
  queue_item?: MissionQueueItem;
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
  queue_item?: MissionQueueItem;
  message?: string;
  error?: string;
};

export type MissionQueueItem = MissionRecord & {
  recommended_action?: string;
  action_target_id?: string;
  operator_hint?: string;
  advance?: MissionAdvanceProjection;
  dependency_state?: MissionDependencyState;
  last_task_id?: string;
  last_task_status?: string;
  last_task_result_status?: string;
  last_task_gate?: string;
  last_task_next_step?: string;
  last_task_reason?: string;
  last_task_approval_id?: string;
  last_task_previous_approval_id?: string;
  last_task_approval_status?: string;
  last_advance_action?: string;
  last_advance_outcome?: string;
  last_advance_operation_id?: string;
  last_advance_operation_status?: string;
  last_advance_message?: string;
  last_advance_actor?: string;
  last_advance_applied?: boolean;
  last_advance_at?: string;
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
  operation_id?: string;
  approval_id?: string;
  gate?: string;
  next_step?: string;
  history?: MissionHistoryEntry[];
  linked_operations?: OperationDetail[];
  run_ledger?: OperationRecord[];
  loop_state?: MissionLoopState;
  queue_item?: MissionQueueItem;
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
  queue_item?: MissionQueueItem;
  status?: string;
  operation_id?: string;
  approval_id?: string;
  gate?: string;
  next_step?: string;
  loop_state?: MissionLoopState;
  handoff?: MissionLoopHandoff;
  history_count?: number;
  linked_operation_count?: number;
  run_ledger_count?: number;
  message?: string;
};

export type MissionRunOnceResponse = {
  ok: boolean;
  items: MissionQueueItem[];
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

function parseMissionQueueItem(raw: unknown): MissionQueueItem | undefined {
  const record = parseMissionRecord(raw);
  if (!record || !isRecord(raw)) return record;

  return {
    ...record,
    recommended_action: safeString(raw.recommended_action, "") || undefined,
    action_target_id: safeString(raw.action_target_id, "") || undefined,
    operator_hint: safeString(raw.operator_hint, "") || undefined,
    advance: parseMissionAdvanceProjection(raw.advance),
    dependency_state: parseMissionDependencyState(raw.dependency_state),
    last_task_id: safeString(raw.last_task_id, "") || undefined,
    last_task_status: safeString(raw.last_task_status, "") || undefined,
    last_task_result_status: safeString(raw.last_task_result_status, "") || undefined,
    last_task_gate: safeString(raw.last_task_gate, "") || undefined,
    last_task_next_step: safeString(raw.last_task_next_step, "") || undefined,
    last_task_reason: safeString(raw.last_task_reason, "") || undefined,
    last_task_approval_id: safeString(raw.last_task_approval_id, "") || undefined,
    last_task_previous_approval_id: safeString(raw.last_task_previous_approval_id, "") || undefined,
    last_task_approval_status: safeString(raw.last_task_approval_status, "") || undefined,
    last_advance_action: safeString(raw.last_advance_action, "") || undefined,
    last_advance_outcome: safeString(raw.last_advance_outcome, "") || undefined,
    last_advance_operation_id: safeString(raw.last_advance_operation_id, "") || undefined,
    last_advance_operation_status: safeString(raw.last_advance_operation_status, "") || undefined,
    last_advance_message: safeString(raw.last_advance_message, "") || undefined,
    last_advance_actor: safeString(raw.last_advance_actor, "") || undefined,
    last_advance_applied: safeBoolean(raw.last_advance_applied, false),
    last_advance_at: safeString(raw.last_advance_at, "") || undefined,
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
    operation_id: safeString(raw.operation_id, "") || undefined,
    trace_id: safeString(raw.trace_id, "") || undefined,
    latest_event: safeString(raw.latest_event, "") || undefined,
    latest_ts: safeString(raw.latest_ts, "") || undefined,
  };

  if (
    !stage.status &&
    !stage.detail &&
    !stage.operation_id &&
    !stage.approval_id &&
    !stage.trace_id &&
    !stage.latest_event &&
    !stage.latest_ts &&
    !stage.next_step
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
    operation_id: safeString(raw.operation_id, "") || undefined,
    trace_id: safeString(raw.trace_id, "") || undefined,
    latest_event: safeString(raw.latest_event, "") || undefined,
    latest_ts: safeString(raw.latest_ts, "") || undefined,
  };

  if (
    !handoff.stage &&
    !handoff.action &&
    !handoff.detail &&
    !handoff.operation_id &&
    !handoff.approval_id &&
    !handoff.trace_id &&
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
  };

  if (
    !state.summary &&
    !state.active_stage &&
    !state.handoff &&
    !state.plan &&
    !state.gate &&
    !state.execute &&
    !state.trace &&
    !state.memory
  ) {
    return undefined;
  }
  return state;
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

  return {
    ok: safeBoolean(json.ok, Boolean(mission)),
    mission,
    history,
    linked_operations,
    run_ledger,
    loop_state: parseMissionLoopState(json.loop_state),
    queue_item: parseMissionQueueItem(json.queue_item),
    error: safeString(json.error, "") || undefined,
  };
}

function parseMissionDetailParts(json: Record<string, unknown>, missionId = ""): Pick<
  MissionDetail,
  "history" | "linked_operations" | "run_ledger" | "loop_state" | "queue_item"
> {
  const parsed = parseMissionDetail(json, missionId);
  return {
    history: parsed.history,
    linked_operations: parsed.linked_operations,
    run_ledger: parsed.run_ledger,
    loop_state: parsed.loop_state,
    queue_item: parsed.queue_item,
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
    operation_id: safeString(json.operation_id, "") || undefined,
    approval_id: safeString(json.approval_id, "") || undefined,
    gate: safeString(json.gate, "") || undefined,
    next_step: safeString(json.next_step, "") || undefined,
    ...parseMissionDetailParts(json, safeString(json.mission_id, "")),
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
    queue_item: parseMissionQueueItem(raw.queue_item),
    status: safeString(raw.status, "") || undefined,
    operation_id: safeString(raw.operation_id, "") || undefined,
    approval_id: safeString(raw.approval_id, "") || undefined,
    gate: safeString(raw.gate, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    loop_state: parseMissionLoopState(raw.loop_state),
    handoff: parseMissionLoopHandoff(raw.handoff),
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

  return {
    ok: safeBoolean(json.ok, false),
    items,
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
): string {
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
): string {
  const actionTargetId = safeString(queueItem?.action_target_id).trim();
  if (actionTargetId.startsWith("msn_")) return actionTargetId;
  return missionCurrentTaskId(mission, queueItem, handoff);
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

  private createUrl(): string {
    return `${this.baseUrl}/missions/create`;
  }

  private advanceUrl(missionId: string): string {
    return `${this.missionUrl(missionId)}/advance`;
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

  async create(
    req: MissionCreateRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<MissionCreateResponse> {
    const json = await fetchJson(this.createUrl(), {
      method: "POST",
      body: JSON.stringify(req),
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
