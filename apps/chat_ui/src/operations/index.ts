/**
 * Operations module (UI).
 *
 * A typed, defensive client for Francis "operations" telemetry and control endpoints.
 *
 * Core responsibilities:
 *  - List operational records (audit/ops events, tasks, runs) with filtering + pagination
 *  - Fetch operation details (and related log lines where supported)
 *  - Provide guarded mutation methods (create/update/delete/cancel) for forward expansion
 *  - Export data for compliance/debug workflows (json/jsonl/csv)
 *
 * Non-goals:
 *  - No React imports (framework-agnostic)
 *  - No UI state (belongs in components)
 *  - No secrets (this module only moves operational metadata)
 *
 * Forward-compatibility strategy:
 *  - Endpoints are builder functions (overrideable) to survive backend route evolution
 *  - Parsing is defensive; accepts multiple common response shapes/field aliases
 *
 * Expected backend (typical; override as needed):
 *  - GET    /operations/list
 *  - GET    /operations/{id}
 *  - POST   /operations/create
 *  - PATCH  /operations/{id}
 *  - DELETE /operations/{id}
 *  - POST   /operations/{id}/cancel
 *  - GET    /operations/export
 */

export type OperationStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "canceled"
  | "blocked"
  | "unknown"
  | string;

export type OperationSeverity = "debug" | "info" | "warning" | "error" | "critical" | string;

export type OperationPlanSummary = {
  kind?: string;
  status?: string;
  current_step_id?: string;
  current_step_title?: string;
  step_count?: number;
  checkpoint_count?: number;
};

export type OperationGovernanceDecision = {
  gate?: string;
  reason?: string;
  next_step?: string;
  evidence?: Record<string, unknown>;
  plane?: string;
  operator_hint?: string;
  action?: string;
  risk_tier?: string;
  approval_status?: string;
  required_trust?: number;
  current_trust?: number;
};

/**
 * A single operational record/event.
 *
 * Note: Some backends emit events without a stable `id`.
 * This client will synthesize a stable-ish id when missing.
 */
export type OperationRecord = {
  id: string;
  ts: number; // unix seconds (ms tolerated by parser; normalized)

  // Classification
  kind?: string; // e.g., "api_action", "daemon_tick", "tool_exec"
  name?: string; // human-friendly name (optional)
  level?: OperationSeverity;
  status?: OperationStatus;

  // Context / attribution
  actor?: string;
  domain?: string;
  approval_id?: string;
  correlation_id?: string;
  trace_id?: string;
  run_id?: string;
  span_id?: string;
  artifact_dir?: string;

  // Timing / metrics
  duration_ms?: number;

  // Payloads (untrusted)
  input?: unknown;
  output?: unknown;
  plan_summary?: OperationPlanSummary;
  error?: unknown;

  // Tags/metadata (safe surface; still untrusted)
  tags?: string[];
  meta?: Record<string, unknown>;
};

/**
 * List response (supports cursor or offset pagination).
 */
export type OperationListResponse = {
  items: OperationRecord[];
  total?: number;

  // Cursor pagination (preferred)
  next_cursor?: string;

  // Offset pagination (optional)
  offset?: number;
  limit?: number;
};

/**
 * Detail response.
 * Backends vary widely; we keep this shape flexible.
 */
export type OperationDetail = {
  operation: OperationRecord;

  // Optional related collections
  logs?: OperationRecord[];
  related?: OperationRecord[];
  memory_receipts?: OperationMemoryReceipt[];
  memory_receipt_count?: number;
  latest_memory_receipt?: OperationMemoryReceipt;

  // Optional extra metadata
  meta?: Record<string, unknown>;
};

export type OperationListParams = {
  // Pagination
  limit?: number;
  cursor?: string;
  offset?: number;

  // Filtering
  status?: string;
  level?: string;
  kind?: string;
  actor?: string;
  domain?: string;
  approval_id?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;

  // Time window (unix seconds)
  start_ts?: number;
  end_ts?: number;

  // Full-text search (backend dependent)
  search?: string;

  // Tags filtering (backend dependent)
  tags?: string[];
};

export type OperationCreateRequest = {
  /**
   * A semantic action identifier for the backend.
   * Examples:
   *  - "daemon.tick"
   *  - "plugin.run"
   *  - "system.healthcheck"
   */
  action: string;

  /**
   * Human justification (useful for audit/compliance).
   * If your backend uses approvals, this often becomes the approval reason.
   */
  reason?: string;

  /**
   * Optional domain scope.
   */
  domain?: string;

  /**
   * Optional caller identity override (usually server-derived).
   */
  actor?: string;

  /**
   * Optional mission continuity anchor. When present, the backend links the
   * created operation into that mission or returns an explicit link error.
   */
  mission_id?: string;

  /**
   * Optional idempotency key to prevent duplicates on retries.
   */
  idempotency_key?: string;

  /**
   * Request payload (NEVER put secrets here for UI workflows).
   */
  input?: unknown;

  /**
   * Forward-compatible metadata bag.
   */
  meta?: Record<string, unknown>;

  /**
   * Optional capability override when the semantic action needs explicit mapping.
   */
  capability?: string;

  /**
   * Optional audit/display objective for the queued operation.
   */
  objective?: string;

  /**
   * Optional priority and expiry controls accepted by the backend operation route.
   */
  priority?: number;
  ttl_sec?: number;
};

export type OperationCreateResponse = {
  ok: boolean;
  operation_id?: string;
  operation?: OperationRecord;

  /**
   * If the server routes this through approvals/governance, it may return
   * an approval id for the UI to track in the approvals queue.
   */
  approval_id?: string;

  status?: OperationStatus;
  message?: string;
  error?: string;
  governance?: OperationGovernanceDecision;
  mission_id?: string;
  mission_linked?: boolean;
  mission_link_error?: string;
};

export type OperationUpdateRequest = {
  /**
   * Patch-friendly partial updates. Keep this minimal; backend decides policy.
   */
  status?: OperationStatus;
  tags?: string[];
  meta?: Record<string, unknown>;

  /**
   * Optional operator note (audit-friendly).
   */
  note?: string;
};

export type OperationUpdateResponse = {
  ok: boolean;
  operation?: OperationRecord;
  status?: OperationStatus;
  message?: string;
  error?: string;
  governance?: OperationGovernanceDecision;
};

export type OperationCancelRequest = {
  reason?: string;
};

export type OperationCancelResponse = {
  ok: boolean;
  status?: OperationStatus;
  message?: string;
  error?: string;
  governance?: OperationGovernanceDecision;
};

export type OperationRunRequest = {
  worker_id?: string;
};

export type OperationMemoryReceipt = {
  source?: string;
  kind?: string;
  ts?: number;
  role?: string;
  message?: string;
  mission_id?: string;
  operation_id?: string;
  trace_id?: string;
  approval_id?: string;
  run_id?: string;
  artifact_dir?: string;
  scope?: string;
  operation_status?: string;
  approval_status?: string;
  capability?: string;
  subsystem?: string;
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
  current_task_approval_id?: string;
  current_task_approval_status?: string;
  current_task_previous_approval_id?: string;
  current_task_previous_approval_status?: string;
  current_task_operation_id?: string;
  current_task_operation_name?: string;
  current_task_operation_plane?: string;
  current_task_advance_action?: string;
  current_task_gate?: string;
  current_task_trace_id?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  current_task_next_step?: string;
  memory_receipt_count?: number;
  plan_status?: string;
  plan_current_step_id?: string;
  plan_current_step_title?: string;
  plan_step_count?: number;
  plan_checkpoint_count?: number;
  references?: {
    mission_id?: string;
    operation_id?: string;
    trace_id?: string;
    approval_id?: string;
    run_id?: string;
    artifact_dir?: string;
  };
};

export type OperationRunResponse = {
  ok: boolean;
  operation?: OperationRecord;
  memory_receipt?: OperationMemoryReceipt;
  status?: OperationStatus;
  message?: string;
  error?: string;
  governance?: OperationGovernanceDecision;
};

export type OperationRunOnceRequest = {
  queue?: string;
  kind?: string;
  concurrency?: number;
  heartbeat_s?: number;
  profile?: string;
  run_mode?: string;
  log_level?: string;
};

export type OperationRunOnceResponse = {
  ok: boolean;
  exit_code?: number;
  status?: OperationStatus;
  message?: string;
  error?: string;
  governance?: OperationGovernanceDecision;
};

export type OperationDeleteRequest = {
  reason?: string;
};

export type OperationDeleteResponse = {
  ok: boolean;
  status?: OperationStatus;
  message?: string;
  error?: string;
  governance?: OperationGovernanceDecision;
};

export type OperationsExportFormat = "json" | "jsonl" | "csv";

export class OperationsApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "OperationsApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.bodySnippet = opts?.bodySnippet;
    // @ts-expect-error - Error.cause may not exist depending on TS lib target
    this.cause = opts?.cause;
  }
}

/* ----------------------------- utilities (pure) ----------------------------- */

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function safeStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.map((x) => (typeof x === "string" ? x : "")).filter((x) => x.length > 0);
  return out.length ? out : undefined;
}

function parseOperationPlanSummary(output: unknown): OperationPlanSummary | undefined {
  if (!isRecord(output)) return undefined;

  const kind = safeString(output.kind) || undefined;
  const hasPlanFields =
    "plan_status" in output ||
    "plan_current_step_id" in output ||
    "plan_current_step_title" in output ||
    "plan_step_count" in output ||
    "plan_checkpoint_count" in output;

  if (kind !== "plan.create.result" && !hasPlanFields) return undefined;

  const rawStepCount = safeNumber(output.plan_step_count, Number.NaN);
  const rawCheckpointCount = safeNumber(output.plan_checkpoint_count, Number.NaN);

  const summary: OperationPlanSummary = {
    kind,
    status: safeString(output.plan_status) || undefined,
    current_step_id: safeString(output.plan_current_step_id) || undefined,
    current_step_title: safeString(output.plan_current_step_title) || undefined,
    step_count: Number.isFinite(rawStepCount) ? Math.max(0, Math.floor(rawStepCount)) : undefined,
    checkpoint_count: Number.isFinite(rawCheckpointCount)
      ? Math.max(0, Math.floor(rawCheckpointCount))
      : undefined,
  };

  if (
    !summary.kind &&
    !summary.status &&
    !summary.current_step_id &&
    !summary.current_step_title &&
    summary.step_count === undefined &&
    summary.checkpoint_count === undefined
  ) {
    return undefined;
  }

  return summary;
}

function parseOperationGovernance(raw: unknown): OperationGovernanceDecision | undefined {
  if (!isRecord(raw)) return undefined;

  const requiredTrust = safeNumber(raw.required_trust, Number.NaN);
  const currentTrust = safeNumber(raw.current_trust, Number.NaN);
  const governance: OperationGovernanceDecision = {
    gate: safeString(raw.gate) || undefined,
    reason: safeString(raw.reason) || undefined,
    next_step: safeString(raw.next_step) || undefined,
    evidence: isRecord(raw.evidence) ? raw.evidence : undefined,
    plane: safeString(raw.plane) || undefined,
    operator_hint: safeString(raw.operator_hint) || undefined,
    action: safeString(raw.action) || undefined,
    risk_tier: safeString(raw.risk_tier) || undefined,
    approval_status: safeString(raw.approval_status) || undefined,
    required_trust: Number.isFinite(requiredTrust) ? requiredTrust : undefined,
    current_trust: Number.isFinite(currentTrust) ? currentTrust : undefined,
  };

  if (Object.values(governance).some((value) => value !== undefined)) return governance;
  return undefined;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeUnixSeconds(ts: unknown): number {
  const n = safeNumber(ts, 0);
  if (n <= 0) return 0;
  // Heuristic: if it looks like ms, convert to seconds
  if (n > 10_000_000_000) return Math.floor(n / 1000);
  return Math.floor(n);
}

/**
 * Small deterministic hash (FNV-1a 32-bit) to synthesize ids when missing.
 * Not cryptographic (not for security), just stable-ish keys for UI rendering.
 */
function fnv1a32(input: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    // 32-bit multiply by FNV prime (via shifts)
    hash = (hash + ((hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24))) >>> 0;
  }
  return hash >>> 0;
}

function synthId(seedParts: Array<string | number | undefined>): string {
  const seed = seedParts.map((p) => (p === undefined ? "" : String(p))).join("|");
  return `op_${fnv1a32(seed).toString(36)}`;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function encodeQuery(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();

  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;

    if (Array.isArray(v)) {
      for (const item of v) {
        if (item === undefined || item === null) continue;
        const s = typeof item === "string" || typeof item === "number" || typeof item === "boolean" ? String(item) : "";
        if (s) sp.append(k, s);
      }
      continue;
    }

    const s =
      typeof v === "string" || typeof v === "number" || typeof v === "boolean" ? String(v) : "";

    if (s) sp.set(k, s);
  }

  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

async function readTextSnippet(res: Response, maxChars = 2048): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

type TimeoutFetchInit = RequestInit & { timeoutMs?: number };

/**
 * Fetch with a hard timeout, while also respecting an external AbortSignal.
 * We "merge" signals by wiring external abort into our internal AbortController.
 */
async function fetchWithTimeout(url: string, init?: TimeoutFetchInit): Promise<Response> {
  const { timeoutMs = 20_000, signal: externalSignal, ...fetchInit } = init ?? {};

  const controller = new AbortController();
  let timedOut = false;

  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null;
  if (timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
  }

  const onExternalAbort = () => controller.abort();

  if (externalSignal) {
    if (externalSignal.aborted) {
      onExternalAbort();
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }

  try {
    const headers = new Headers(fetchInit.headers ?? undefined);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    // Only set Content-Type if a body exists and caller didn't set it
    if (fetchInit.body !== undefined && fetchInit.body !== null) {
      if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    }

    const res = await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });

    return res;
  } catch (err) {
    if (timedOut) {
      throw new OperationsApiError(`Timeout after ${timeoutMs}ms`, { url, cause: err });
    }
    throw err;
  } finally {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
    if (externalSignal && !externalSignal.aborted) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

/**
 * Fetch and parse JSON if possible; if content-type isn't JSON, fall back to text.
 * This supports backends that return:
 *  - JSON
 *  - JSON-as-text
 *  - JSONL (handled by parse helpers at higher layer if used)
 */
async function fetchAny(url: string, init?: TimeoutFetchInit): Promise<unknown> {
  const res = await fetchWithTimeout(url, init);

  if (!res.ok) {
    const snippet = await readTextSnippet(res);
    throw new OperationsApiError(`HTTP ${res.status} for operations request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  const ct = (res.headers.get("content-type") || "").toLowerCase();
  if (ct.includes("application/json") || ct.includes("+json")) {
    return await res.json();
  }

  const text = await res.text();
  // Best-effort JSON parse even when content-type is wrong
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function fetchBlob(url: string, init?: TimeoutFetchInit): Promise<Blob> {
  const res = await fetchWithTimeout(url, init);

  if (!res.ok) {
    const snippet = await readTextSnippet(res);
    throw new OperationsApiError(`HTTP ${res.status} for operations request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  return await res.blob();
}

/* ----------------------------- parsing (defensive) ----------------------------- */

export function parseOperationRecord(raw: unknown): OperationRecord | null {
  if (!isRecord(raw)) return null;

  // id aliases
  const id =
    safeString(raw.id) ||
    safeString(raw.operation_id) ||
    safeString(raw.op_id) ||
    safeString(raw.run_id) ||
    "";

  // ts aliases
  const ts =
    normalizeUnixSeconds(raw.ts) ||
    normalizeUnixSeconds(raw.timestamp) ||
    normalizeUnixSeconds(raw.time) ||
    normalizeUnixSeconds(raw.created_ts);

  // core fields
  const kind = safeString(raw.kind) || safeString(raw.type) || safeString(raw.event) || undefined;
  const name = safeString(raw.name) || undefined;

  const level =
    (safeString(raw.level) || safeString(raw.severity) || undefined) as OperationSeverity | undefined;

  const status =
    (safeString(raw.status) || safeString(raw.state) || safeString(raw.result) || undefined) as
      | OperationStatus
      | undefined;

  const actor = safeString(raw.actor) || safeString(raw.user) || safeString(raw.principal) || undefined;
  const domain = safeString(raw.domain) || safeString(raw.domain_id) || undefined;

  const correlation_id =
    safeString(raw.correlation_id) || safeString(raw.correlationId) || safeString(raw.corr_id) || undefined;

  const meta = isRecord(raw.meta) ? raw.meta : undefined;

  const duration_ms =
    safeNumber(raw.duration_ms, 0) || safeNumber(raw.elapsed_ms, 0) || safeNumber(raw.latency_ms, 0) || 0;

  const message = safeString(raw.message) || safeString(raw.msg) || safeString(raw.summary) || "";

  const tags = safeStringArray(raw.tags);

  // payload aliases
  const input =
    "input" in raw ? raw.input :
    "request" in raw ? raw.request :
    "payload" in raw ? raw.payload :
    "context" in raw ? raw.context :
    undefined;
  const inputMeta = isRecord(input) && isRecord(input.meta) ? input.meta : undefined;

  const trace_id =
    safeString(raw.trace_id) ||
    safeString(raw.traceId) ||
    safeString(meta?.trace_id) ||
    safeString(meta?.traceId) ||
    safeString(inputMeta?.trace_id) ||
    safeString(inputMeta?.traceId) ||
    undefined;
  const run_id =
    safeString(raw.run_id) ||
    safeString(raw.runId) ||
    safeString(meta?.run_id) ||
    safeString(meta?.runId) ||
    safeString(inputMeta?.run_id) ||
    safeString(inputMeta?.runId) ||
    undefined;
  const span_id = safeString(raw.span_id) || safeString(raw.spanId) || undefined;
  const artifact_dir =
    safeString(raw.artifact_dir) ||
    safeString(raw.artifact_path) ||
    safeString(meta?.artifact_dir) ||
    safeString(meta?.artifact_path) ||
    safeString(inputMeta?.artifact_dir) ||
    safeString(inputMeta?.artifact_path) ||
    undefined;

  const output =
    "output" in raw ? raw.output :
    "response" in raw ? raw.response :
    "result" in raw ? raw.result :
    undefined;
  const outputRecord = isRecord(output) ? output : undefined;
  const approval_id =
    safeString(raw.approval_id) ||
    safeString(raw.approvalId) ||
    safeString(meta?.approval_id) ||
    safeString(meta?.approvalId) ||
    safeString(inputMeta?.approval_id) ||
    safeString(inputMeta?.approvalId) ||
    safeString(outputRecord?.approval_id) ||
    safeString(outputRecord?.approvalId) ||
    undefined;
  const plan_summary = parseOperationPlanSummary(output);

  const error =
    "error" in raw ? raw.error :
    "exception" in raw ? raw.exception :
    undefined;

  const stableId = id || synthId([ts, kind, status, actor, domain, message]);

  if (!stableId) return null;
  if (!ts) {
    // If no timestamp, still allow record but set to "now" (last resort).
    // This keeps UI stable if backend omits ts for some reason.
    const now = Math.floor(Date.now() / 1000);
    return {
      id: stableId,
      ts: now,
      kind,
      name,
      level,
      status,
      actor,
      domain,
      approval_id,
      correlation_id,
      trace_id,
      run_id,
      span_id,
      artifact_dir,
      duration_ms: duration_ms > 0 ? duration_ms : undefined,
      message: message || undefined,
      tags,
      meta,
      input,
      output,
      plan_summary,
      error,
    };
  }

  return {
    id: stableId,
    ts,
    kind,
    name,
    level,
    status,
    actor,
    domain,
    approval_id,
    correlation_id,
    trace_id,
    run_id,
    span_id,
    artifact_dir,
    duration_ms: duration_ms > 0 ? duration_ms : undefined,
    message: message || undefined,
    tags,
    meta,
    input,
    output,
    plan_summary,
    error,
  };
}

function parseOperationListResponse(json: unknown, params?: OperationListParams): OperationListResponse {
  const limit = typeof params?.limit === "number" ? clamp(params.limit, 1, 10_000) : undefined;
  const offset = typeof params?.offset === "number" ? Math.max(0, Math.floor(params.offset)) : undefined;

  // Case 1: array payload
  if (Array.isArray(json)) {
    const items = json.map(parseOperationRecord).filter((x): x is OperationRecord => x !== null);
    return { items, limit, offset };
  }

  // Case 2: record with items-ish field
  if (!isRecord(json)) return { items: [], limit, offset };

  const rawItems =
    (Array.isArray(json.items) ? json.items :
    Array.isArray(json.entries) ? json.entries :
    Array.isArray(json.operations) ? json.operations :
    Array.isArray(json.logs) ? json.logs :
    Array.isArray(json.records) ? json.records :
    []) as unknown[];

  const items = rawItems.map(parseOperationRecord).filter((x): x is OperationRecord => x !== null);

  const total =
    safeNumber(json.total, 0) ||
    safeNumber(json.count, 0) ||
    safeNumber(json.total_count, 0) ||
    undefined;

  const next_cursor =
    safeString(json.next_cursor) ||
    safeString(json.nextCursor) ||
    safeString(json.cursor) ||
    safeString(json.next) ||
    undefined;

  return {
    items,
    total: total && total > 0 ? total : undefined,
    next_cursor,
    limit,
    offset,
  };
}

export function parseOperationDetail(json: unknown, idHint: string): OperationDetail | null {
  // Some backends return { operation: {...}, logs: [...] }
  if (isRecord(json)) {
    const opRaw = isRecord(json.operation) ? json.operation : isRecord(json.item) ? json.item : json;
    const operation = parseOperationRecord(opRaw);

    if (!operation) {
      // Try: server might return { id, ... } but we failed parse because of shape drift.
      // As a last resort, synthesize minimal record for UI.
      const now = Math.floor(Date.now() / 1000);
      return {
        operation: { id: idHint, ts: now, status: "unknown" },
      };
    }

    const logsRaw =
      Array.isArray(json.logs) ? json.logs :
      Array.isArray(json.entries) ? json.entries :
      Array.isArray(json.events) ? json.events :
      undefined;

    const logs = Array.isArray(logsRaw)
      ? logsRaw.map(parseOperationRecord).filter((x): x is OperationRecord => x !== null)
      : undefined;

    const relatedRaw = Array.isArray(json.related) ? json.related : undefined;
    const related = Array.isArray(relatedRaw)
      ? relatedRaw.map(parseOperationRecord).filter((x): x is OperationRecord => x !== null)
      : undefined;

    const meta = isRecord(json.meta) ? json.meta : undefined;
    const memoryReceipts = Array.isArray(json.memory_receipts)
      ? json.memory_receipts
          .map(parseOperationMemoryReceipt)
          .filter((item): item is OperationMemoryReceipt => Boolean(item))
      : [];
    const latestMemoryReceipt = parseOperationMemoryReceipt(json.latest_memory_receipt);
    const memoryReceiptCount =
      safeNumber(json.memory_receipt_count, Number.NaN) ||
      (memoryReceipts.length ? memoryReceipts.length : latestMemoryReceipt ? 1 : 0);

    return {
      operation,
      logs: logs && logs.length ? logs : undefined,
      related: related && related.length ? related : undefined,
      memory_receipts: memoryReceipts.length ? memoryReceipts : undefined,
      memory_receipt_count: memoryReceiptCount > 0 ? Math.floor(memoryReceiptCount) : undefined,
      latest_memory_receipt: latestMemoryReceipt,
      meta,
    };
  }

  // Some backends return just the operation object
  const op = parseOperationRecord(json);
  if (!op) return null;

  return { operation: op };
}

function parseOperationMemoryReceipt(raw: unknown): OperationMemoryReceipt | undefined {
  if (!isRecord(raw)) return undefined;

  const referencesRaw = isRecord(raw.references) ? raw.references : {};
  const references = {
    mission_id: safeString(referencesRaw.mission_id) || safeString(raw.mission_id) || undefined,
    operation_id: safeString(referencesRaw.operation_id) || safeString(raw.operation_id) || undefined,
    trace_id: safeString(referencesRaw.trace_id) || safeString(raw.trace_id) || undefined,
    approval_id: safeString(referencesRaw.approval_id) || safeString(raw.approval_id) || undefined,
    run_id: safeString(referencesRaw.run_id) || safeString(raw.run_id) || undefined,
    artifact_dir: safeString(referencesRaw.artifact_dir) || safeString(raw.artifact_dir) || undefined,
  };

  const rawPlanStepCount = safeNumber(raw.plan_step_count, Number.NaN);
  const rawPlanCheckpointCount = safeNumber(raw.plan_checkpoint_count, Number.NaN);
  const rawMemoryReceiptCount = safeNumber(raw.memory_receipt_count, Number.NaN);

  const receipt: OperationMemoryReceipt = {
    source: safeString(raw.source) || undefined,
    kind: safeString(raw.kind) || undefined,
    ts: safeNumber(raw.ts, 0) || undefined,
    role: safeString(raw.role) || undefined,
    message: safeString(raw.message) || undefined,
    mission_id: safeString(raw.mission_id) || references.mission_id,
    operation_id: safeString(raw.operation_id) || references.operation_id,
    trace_id: safeString(raw.trace_id) || references.trace_id,
    approval_id: safeString(raw.approval_id) || references.approval_id,
    run_id: safeString(raw.run_id) || references.run_id,
    artifact_dir: safeString(raw.artifact_dir) || references.artifact_dir,
    scope: safeString(raw.scope) || undefined,
    operation_status: safeString(raw.operation_status) || undefined,
    approval_status: safeString(raw.approval_status) || undefined,
    capability: safeString(raw.capability) || undefined,
    subsystem: safeString(raw.subsystem) || undefined,
    active_stage: safeString(raw.active_stage) || undefined,
    handoff_stage: safeString(raw.handoff_stage) || undefined,
    handoff_action: safeString(raw.handoff_action) || undefined,
    handoff_gate: safeString(raw.handoff_gate) || undefined,
    handoff_approval_id: safeString(raw.handoff_approval_id) || undefined,
    handoff_approval_status: safeString(raw.handoff_approval_status) || undefined,
    handoff_operation_id: safeString(raw.handoff_operation_id) || undefined,
    handoff_trace_id: safeString(raw.handoff_trace_id) || undefined,
    handoff_run_id: safeString(raw.handoff_run_id) || undefined,
    handoff_artifact_dir: safeString(raw.handoff_artifact_dir) || undefined,
    handoff_next_step: safeString(raw.handoff_next_step) || undefined,
    current_task_source: safeString(raw.current_task_source) || undefined,
    current_task_approval_id: safeString(raw.current_task_approval_id) || undefined,
    current_task_approval_status: safeString(raw.current_task_approval_status) || undefined,
    current_task_previous_approval_id: safeString(raw.current_task_previous_approval_id) || undefined,
    current_task_previous_approval_status: safeString(raw.current_task_previous_approval_status) || undefined,
    current_task_operation_id: safeString(raw.current_task_operation_id) || undefined,
    current_task_operation_name: safeString(raw.current_task_operation_name) || undefined,
    current_task_operation_plane: safeString(raw.current_task_operation_plane) || undefined,
    current_task_advance_action: safeString(raw.current_task_advance_action) || undefined,
    current_task_gate: safeString(raw.current_task_gate) || undefined,
    current_task_trace_id: safeString(raw.current_task_trace_id) || undefined,
    current_task_run_id: safeString(raw.current_task_run_id) || undefined,
    current_task_artifact_dir: safeString(raw.current_task_artifact_dir) || undefined,
    current_task_next_step: safeString(raw.current_task_next_step) || undefined,
    memory_receipt_count: Number.isFinite(rawMemoryReceiptCount)
      ? Math.max(0, Math.floor(rawMemoryReceiptCount))
      : undefined,
    plan_status: safeString(raw.plan_status) || undefined,
    plan_current_step_id: safeString(raw.plan_current_step_id) || undefined,
    plan_current_step_title: safeString(raw.plan_current_step_title) || undefined,
    plan_step_count: Number.isFinite(rawPlanStepCount) ? Math.max(0, Math.floor(rawPlanStepCount)) : undefined,
    plan_checkpoint_count: Number.isFinite(rawPlanCheckpointCount)
      ? Math.max(0, Math.floor(rawPlanCheckpointCount))
      : undefined,
  };

  if (Object.values(references).some((value) => value)) receipt.references = references;
  if (Object.values(receipt).some((value) => value !== undefined)) return receipt;
  return undefined;
}

/* ----------------------------- endpoints (overrideable) ----------------------------- */

export type OperationsEndpoints = {
  list: () => string;
  get: (operationId: string) => string;
  getMany?: () => string;

  create?: () => string;
  update?: (operationId: string) => string;
  cancel?: (operationId: string) => string;
  run?: (operationId: string) => string;
  runOnce?: () => string;
  delete?: (operationId: string) => string;

  export?: () => string;
};

export function defaultOperationsEndpoints(): OperationsEndpoints {
  return {
    list: () => "/operations/list",
    get: (id: string) => `/operations/${encodeURIComponent(id)}`,
    // Optional endpoints (backend-dependent)
    getMany: () => "/operations/get_many",
    create: () => "/operations/create",
    update: (id: string) => `/operations/${encodeURIComponent(id)}`,
    cancel: (id: string) => `/operations/${encodeURIComponent(id)}/cancel`,
    run: (id: string) => `/operations/${encodeURIComponent(id)}/run`,
    runOnce: () => "/operations/run-once",
    delete: (id: string) => `/operations/${encodeURIComponent(id)}`,
    export: () => "/operations/export",
  };
}

export type OperationsClientOptions = {
  endpoints?: OperationsEndpoints;
  defaultTimeoutMs?: number;

  /**
   * Default list limit if caller doesn't specify.
   * Keeps UI from accidentally requesting huge pages.
   */
  defaultListLimit?: number;
};

export class OperationsClient {
  readonly baseUrl: string;
  readonly endpoints: OperationsEndpoints;
  readonly defaultTimeoutMs: number;
  readonly defaultListLimit: number;

  constructor(baseUrl: string, opts?: OperationsClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) {
      throw new Error("OperationsClient requires a non-empty baseUrl");
    }

    this.endpoints = opts?.endpoints ?? defaultOperationsEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;

    const lim = typeof opts?.defaultListLimit === "number" ? opts.defaultListLimit : 200;
    this.defaultListLimit = clamp(Math.floor(lim), 1, 10_000);
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  /**
   * List operations with filters + pagination.
   * Supports cursor and/or offset patterns (backend-dependent).
   */
  async list(
    params?: OperationListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperationListResponse> {
    const limit = typeof params?.limit === "number" ? params.limit : this.defaultListLimit;

    const qs = encodeQuery({
      ...params,
      limit,
    });

    const url = this.url(`${this.endpoints.list()}${qs}`);
    const json = await fetchAny(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    return parseOperationListResponse(json, { ...params, limit });
  }

  /**
   * Get an operation detail record by id.
   */
  async get(
    operationId: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperationDetail | null> {
    const id = (operationId || "").trim();
    if (!id) throw new Error("OperationsClient.get requires a non-empty operationId");

    const url = this.url(this.endpoints.get(id));
    const json = await fetchAny(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    return parseOperationDetail(json, id);
  }

  /**
   * Batch get.
   *
   * Strategy:
   *  - If backend supports getMany endpoint: call it (POST with ids)
   *  - Else: fallback to parallel individual get() calls (bounded concurrency)
   *
   * This method deduplicates ids internally to avoid redundant requests.
   */
  async getMany(
    ids: string[],
    opts?: { signal?: AbortSignal; timeoutMs?: number; concurrency?: number },
  ): Promise<Array<OperationDetail | null>> {
    const cleaned = (ids || []).map((x) => (x || "").trim()).filter((x) => x.length > 0);
    if (!cleaned.length) return [];

    // Dedupe, but preserve output order
    const unique = Array.from(new Set(cleaned));

    if (this.endpoints.getMany) {
      const url = this.url(this.endpoints.getMany());
      const json = await fetchAny(url, {
        method: "POST",
        body: JSON.stringify({ ids: unique }),
        signal: opts?.signal,
        timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
      });

      // Accept shapes:
      //  - { items: [ { operation: ... }, ... ] }
      //  - { operations: [ ... ] }
      //  - [ ... ]
      let list: unknown[] = [];
      if (Array.isArray(json)) {
        list = json;
      } else if (isRecord(json)) {
        list =
          (Array.isArray(json.items) ? json.items :
          Array.isArray(json.operations) ? json.operations :
          Array.isArray(json.entries) ? json.entries :
          []) as unknown[];
      }

      const parsedById = new Map<string, OperationDetail | null>();
      for (const item of list) {
        const detail = parseOperationDetail(item, "");
        if (detail?.operation?.id) parsedById.set(detail.operation.id, detail);
      }

      // Rebuild in original order (including duplicates)
      return cleaned.map((id) => parsedById.get(id) ?? null);
    }

    // Fallback: bounded parallel get
    const concurrency = clamp(Math.floor(opts?.concurrency ?? 6), 1, 32);

    const resultsById = new Map<string, OperationDetail | null>();
    const queue = [...unique];

    const workers = Array.from({ length: Math.min(concurrency, queue.length) }).map(async () => {
      while (queue.length) {
        if (opts?.signal?.aborted) break;
        const next = queue.shift();
        if (!next) break;

        try {
          const detail = await this.get(next, { signal: opts?.signal, timeoutMs: opts?.timeoutMs });
          resultsById.set(next, detail);
        } catch (err) {
          // Do not explode the batch on one failure; store null for that id.
          // Caller can decide how to display/report failures.
          // (If you want fail-fast, do it at the UI layer.)
          resultsById.set(next, null);
          void err;
        }
      }
    });

    await Promise.all(workers);

    return cleaned.map((id) => resultsById.get(id) ?? null);
  }

  /**
   * Create an operation (backend-dependent).
   * Often used for operator-triggered runs, health checks, or queued tasks.
   */
  async create(
    req: OperationCreateRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperationCreateResponse> {
    if (!this.endpoints.create) {
      throw new Error("OperationsClient.create is not configured (endpoints.create missing)");
    }

    const url = this.url(this.endpoints.create());
    const json = await fetchAny(url, {
      method: "POST",
      body: JSON.stringify(req),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true };

    const operation = parseOperationRecord(json.operation);
    const error = safeString(json.error) || undefined;
    const missionLinkError = safeString(json.mission_link_error) || undefined;
    const governance = parseOperationGovernance(json.governance);

    return {
      ok: Boolean(json.ok ?? true),
      operation_id: safeString(json.operation_id) || safeString(json.id) || undefined,
      operation: operation ?? undefined,
      approval_id: safeString(json.approval_id) || undefined,
      status: (safeString(json.status) || undefined) as OperationStatus | undefined,
      message: safeString(json.message) || error || missionLinkError || governance?.next_step || undefined,
      error,
      governance,
      mission_id: safeString(json.mission_id) || undefined,
      mission_linked: typeof json.mission_linked === "boolean" ? json.mission_linked : undefined,
      mission_link_error: missionLinkError,
    };
  }

  /**
   * Update operation metadata/status (backend-dependent).
   * Use for operator notes, tagging, or lifecycle state changes when permitted by policy.
   */
  async update(
    operationId: string,
    patch: OperationUpdateRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperationUpdateResponse> {
    if (!this.endpoints.update) {
      throw new Error("OperationsClient.update is not configured (endpoints.update missing)");
    }

    const id = (operationId || "").trim();
    if (!id) throw new Error("OperationsClient.update requires a non-empty operationId");

    const url = this.url(this.endpoints.update(id));
    const json = await fetchAny(url, {
      method: "PATCH",
      body: JSON.stringify(patch),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true };

    const op = parseOperationRecord(isRecord(json.operation) ? json.operation : json.operation);
    const error = safeString(json.error) || undefined;
    const governance = parseOperationGovernance(json.governance);

    return {
      ok: Boolean(json.ok ?? true),
      operation: op ?? undefined,
      status: (safeString(json.status) || undefined) as OperationStatus | undefined,
      message: safeString(json.message) || error || governance?.next_step || undefined,
      error,
      governance,
    };
  }

  /**
   * Cancel an operation (backend-dependent).
   */
  async cancel(
    operationId: string,
    req?: OperationCancelRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperationCancelResponse> {
    if (!this.endpoints.cancel) {
      throw new Error("OperationsClient.cancel is not configured (endpoints.cancel missing)");
    }

    const id = (operationId || "").trim();
    if (!id) throw new Error("OperationsClient.cancel requires a non-empty operationId");

    const url = this.url(this.endpoints.cancel(id));
    const json = await fetchAny(url, {
      method: "POST",
      body: JSON.stringify(req ?? {}),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true };

    const error = safeString(json.error) || undefined;
    const governance = parseOperationGovernance(json.governance);

    return {
      ok: Boolean(json.ok ?? true),
      status: (safeString(json.status) || undefined) as OperationStatus | undefined,
      message: safeString(json.message) || error || governance?.next_step || undefined,
      error,
      governance,
    };
  }

  /**
   * Run an operation immediately (backend-dependent).
   */
  async run(
    operationId: string,
    req?: OperationRunRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperationRunResponse> {
    if (!this.endpoints.run) {
      throw new Error("OperationsClient.run is not configured (endpoints.run missing)");
    }

    const id = (operationId || "").trim();
    if (!id) throw new Error("OperationsClient.run requires a non-empty operationId");

    const url = this.url(this.endpoints.run(id));
    const json = await fetchAny(url, {
      method: "POST",
      body: JSON.stringify(req ?? {}),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true };

    const op = parseOperationRecord(isRecord(json.operation) ? json.operation : json.operation);
    const error = safeString(json.error) || undefined;
    const governance = parseOperationGovernance(json.governance);

    return {
      ok: Boolean(json.ok ?? true),
      operation: op ?? undefined,
      memory_receipt: parseOperationMemoryReceipt(json.memory_receipt),
      status: (safeString(json.status) || undefined) as OperationStatus | undefined,
      message: safeString(json.message) || error || governance?.next_step || undefined,
      error,
      governance,
    };
  }

  /**
   * Run a single bounded worker cycle (backend-dependent).
   */
  async runOnce(
    req?: OperationRunOnceRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperationRunOnceResponse> {
    if (!this.endpoints.runOnce) {
      throw new Error("OperationsClient.runOnce is not configured (endpoints.runOnce missing)");
    }

    const url = this.url(this.endpoints.runOnce());
    const json = await fetchAny(url, {
      method: "POST",
      body: JSON.stringify(req ?? {}),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true };

    const error = safeString(json.error) || undefined;
    const governance = parseOperationGovernance(json.governance);

    return {
      ok: Boolean(json.ok ?? true),
      exit_code: typeof json.exit_code === "number" && Number.isFinite(json.exit_code) ? json.exit_code : undefined,
      status: (safeString(json.status) || undefined) as OperationStatus | undefined,
      message: safeString(json.message) || error || governance?.next_step || undefined,
      error,
      governance,
    };
  }

  /**
   * Delete/purge an operation record (backend-dependent; often restricted).
   */
  async delete(
    operationId: string,
    req?: OperationDeleteRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OperationDeleteResponse> {
    if (!this.endpoints.delete) {
      throw new Error("OperationsClient.delete is not configured (endpoints.delete missing)");
    }

    const id = (operationId || "").trim();
    if (!id) throw new Error("OperationsClient.delete requires a non-empty operationId");

    const url = this.url(this.endpoints.delete(id));
    const json = await fetchAny(url, {
      method: "DELETE",
      body: JSON.stringify(req ?? {}),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true };

    const error = safeString(json.error) || undefined;
    const governance = parseOperationGovernance(json.governance);

    return {
      ok: Boolean(json.ok ?? true),
      status: (safeString(json.status) || undefined) as OperationStatus | undefined,
      message: safeString(json.message) || error || governance?.next_step || undefined,
      error,
      governance,
    };
  }

  /**
   * Export operations data (backend-dependent).
   * Intended for compliance/debug workflows.
   *
   * Typical backend behaviors:
   *  - Returns CSV/JSON/JSONL as a file download
   *  - Uses query params for filters
   */
  async export(
    format: OperationsExportFormat,
    params?: OperationListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<Blob> {
    if (!this.endpoints.export) {
      throw new Error("OperationsClient.export is not configured (endpoints.export missing)");
    }

    const qs = encodeQuery({
      ...(params ?? {}),
      format,
    });

    const url = this.url(`${this.endpoints.export()}${qs}`);
    return await fetchBlob(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
  }
}
