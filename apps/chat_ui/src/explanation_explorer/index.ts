/**
 * Explanation Explorer module (UI).
 *
 * Framework-agnostic client + types for explanation/audit artifacts.
 *
 * Concept:
 *  - Explanations are operator-visible artifacts that answer:
 *      "What happened?", "Why did it happen?", "What inputs/policy/tooling drove it?"
 *  - This module is READ-ONLY by default (audit trail).
 *
 * Supports:
 *  - List explanation records (filters + date range + keyword search)
 *  - Get explanation detail by id
 *  - Batch get (dedup + retry + concurrency-limited) for multi-detail UI views
 *  - Export trails (json/csv) as Blob with optional progress callback
 *  - Streaming export (ReadableStream) for large datasets
 *
 * Non-goals:
 *  - No React imports
 *  - No mutation endpoints (writes belong in governance subsystems)
 *
 * Endpoints:
 *  - Defaults are conventional and can be overridden via options.
 */

export type ExplanationKind =
  | "decision"
  | "policy_eval"
  | "tool_trace"
  | "planner"
  | "reasoning"
  | "audit"
  | string;

export type ExplanationSeverity = "debug" | "info" | "warning" | "error" | "critical" | string;

export type ExplanationReceiptReferences = {
  mission_id?: string;
  operation_id?: string;
  approval_id?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
};

export type ExplanationRecord = {
  id: string;
  ts: number; // unix seconds preferred; ms tolerated

  kind: ExplanationKind;
  severity?: ExplanationSeverity;

  title?: string;
  summary?: string;

  // Scoping / linkage
  run_id?: string;
  trace_id?: string;
  artifact_dir?: string;
  mission_id?: string;
  operation_id?: string;
  operation_status?: string;
  operation_error?: string;
  result_message?: string;
  recovery_next_step?: string;
  domain?: string;
  conversation_id?: string;
  approval_id?: string;
  plugin_id?: string;
  references?: ExplanationReceiptReferences;
  current_task_source?: string;
  current_task_approval_id?: string;
  current_task_approval_status?: string;
  current_task_operation_id?: string;
  current_task_operation_name?: string;
  current_task_operation_plane?: string;
  current_task_advance_action?: string;
  current_task_gate?: string;
  current_task_trace_id?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  current_task_next_step?: string;

  // Forward-compatible metadata
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type ExplanationDetail = ExplanationRecord & {
  /**
   * Full content is intentionally flexible:
   * - may include policy tree, tool calls, inputs/outputs, redactions, etc.
   */
  content?: Record<string, unknown> | string;

  // Optional structured fields for common cases
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  policy?: Record<string, unknown>;
  tools?: Array<Record<string, unknown>>;
};

export type ExplanationListResponse = {
  items: ExplanationRecord[];
};

export type ExplanationExportFormat = "json" | "csv";

/**
 * List query (read-only).
 * All filters are optional and backend-dependent.
 */
export type ExplanationListQuery = {
  limit?: number;
  offset?: number;

  kind?: ExplanationKind;
  severity?: ExplanationSeverity;

  domain?: string;
  run_id?: string;
  trace_id?: string;
  artifact_dir?: string;
  mission_id?: string;
  operation_id?: string;
  conversation_id?: string;
  approval_id?: string;
  plugin_id?: string;

  tags?: string[];

  /** Date range filtering (unix seconds preferred; ms tolerated) */
  start_ts?: number;
  end_ts?: number;

  /** Keyword search (backend-dependent semantics) */
  search?: string;
};

export class ExplanationApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "ExplanationApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.bodySnippet = opts?.bodySnippet;
    // @ts-expect-error - Error.cause not always in TS lib target
    this.cause = opts?.cause;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    const text = safeString(value).trim();
    if (text) return text;
  }
  return "";
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function parseReceiptReferences(raw: unknown): ExplanationReceiptReferences | undefined {
  if (!isRecord(raw)) return undefined;

  const references: ExplanationReceiptReferences = {};
  const missionId = firstString(raw.mission_id, raw.missionId);
  const operationId = firstString(
    raw.operation_id,
    raw.operationId,
    raw.task_id,
    raw.taskId,
    raw.current_task_operation_id,
    raw.currentTaskOperationId,
  );
  const approvalId = firstString(raw.approval_id, raw.approvalId, raw.current_task_approval_id, raw.currentTaskApprovalId);
  const traceId = firstString(raw.trace_id, raw.traceId, raw.current_task_trace_id, raw.currentTaskTraceId);
  const runId = firstString(raw.run_id, raw.runId, raw.current_task_run_id, raw.currentTaskRunId);
  const artifactDir = firstString(
    raw.artifact_dir,
    raw.artifactDir,
    raw.artifact_path,
    raw.artifactPath,
    raw.current_task_artifact_dir,
    raw.currentTaskArtifactDir,
  );

  if (missionId) references.mission_id = missionId;
  if (operationId) references.operation_id = operationId;
  if (approvalId) references.approval_id = approvalId;
  if (traceId) references.trace_id = traceId;
  if (runId) references.run_id = runId;
  if (artifactDir) references.artifact_dir = artifactDir;

  return Object.keys(references).length > 0 ? references : undefined;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeTs(ts: number): number {
  // Heuristic: seconds vs ms
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : ts;
}

function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (typeof v === "string" && v.trim() === "") continue;

    if (Array.isArray(v)) {
      const joined = v.map((x) => String(x)).filter((s) => s.length > 0).join(",");
      if (joined) usp.set(k, joined);
      continue;
    }

    usp.set(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

function clampInt(n: number, min: number, max: number): number {
  const x = Math.floor(n);
  return x < min ? min : x > max ? max : x;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const t = globalThis.setTimeout(() => {
      cleanup();
      resolve();
    }, ms);

    const onAbort = () => {
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };

    const cleanup = () => {
      globalThis.clearTimeout(t);
      if (signal) signal.removeEventListener("abort", onAbort);
    };

    if (signal) {
      if (signal.aborted) onAbort();
      else signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

function isTransientError(err: unknown): boolean {
  // Conservative: retry only on likely transient conditions.
  if (err instanceof ExplanationApiError) {
    const s = err.status ?? 0;
    // Retry server errors & gateway timeouts.
    return s === 408 || s === 429 || (s >= 500 && s <= 599);
  }
  if (err instanceof DOMException && err.name === "AbortError") {
    // Abort could be user cancellation; treat as non-retry (caller decides).
    return false;
  }
  // Fetch/network errors often surface as TypeError in browsers.
  if (err instanceof TypeError) return true;

  return false;
}

function normalizeAcceptForExport(format: ExplanationExportFormat): string {
  if (format === "csv") return "text/csv,application/json;q=0.9,*/*;q=0.8";
  return "application/json,text/csv;q=0.3,*/*;q=0.2";
}

async function readTextSnippet(res: Response, maxChars = 2048): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

type TimeoutMergedFetchInit = RequestInit & { timeoutMs?: number };

/**
 * Abort wiring helper:
 *  - timeoutMs: abort after deadline (covers header fetch + body read)
 *  - external signal: caller cancellation
 *
 * Cleanup must be called when the response body has been fully consumed
 * (or the stream is cancelled) to avoid timers/listeners hanging around.
 */
function createAbortWiring(opts?: { timeoutMs?: number; signal?: AbortSignal }): {
  signal: AbortSignal;
  cleanup: () => void;
  timedOut: () => boolean;
} {
  const external = opts?.signal;
  const timeoutMs = typeof opts?.timeoutMs === "number" ? opts.timeoutMs : 20_000;

  const controller = new AbortController();
  let didTimeout = false;

  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null;
  if (timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => {
      didTimeout = true;
      controller.abort();
    }, timeoutMs);
  }

  const onExternalAbort = () => controller.abort();

  if (external) {
    if (external.aborted) onExternalAbort();
    else external.addEventListener("abort", onExternalAbort, { once: true });
  }

  const cleanup = () => {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
    if (external) external.removeEventListener("abort", onExternalAbort);
  };

  return {
    signal: controller.signal,
    cleanup,
    timedOut: () => didTimeout,
  };
}

async function fetchResponse(
  url: string,
  init?: TimeoutMergedFetchInit,
): Promise<{ res: Response; cleanup: () => void; timedOut: () => boolean }> {
  const wiring = createAbortWiring({ timeoutMs: init?.timeoutMs, signal: init?.signal });

  try {
    const headers = new Headers(init?.headers ?? undefined);

    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (init?.body !== undefined && init?.body !== null) {
      if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    }

    const res = await fetch(url, {
      ...init,
      headers,
      signal: wiring.signal,
    });

    return { res, cleanup: wiring.cleanup, timedOut: wiring.timedOut };
  } catch (err) {
    wiring.cleanup();

    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ExplanationApiError(wiring.timedOut() ? "Explanation request timed out" : "Explanation request aborted", {
        url,
        cause: err,
      });
    }

    throw new ExplanationApiError("Explanation request failed", { url, cause: err });
  }
}

async function fetchJson(url: string, init?: TimeoutMergedFetchInit): Promise<unknown> {
  const { res, cleanup } = await fetchResponse(url, init);
  try {
    if (!res.ok) {
      const snippet = await readTextSnippet(res);
      throw new ExplanationApiError(`HTTP ${res.status} for explanation request`, {
        status: res.status,
        url,
        bodySnippet: snippet,
      });
    }
    return await res.json();
  } finally {
    cleanup();
  }
}

async function fetchBlob(url: string, init?: TimeoutMergedFetchInit): Promise<Blob> {
  const { res, cleanup } = await fetchResponse(url, init);
  try {
    if (!res.ok) {
      const snippet = await readTextSnippet(res);
      throw new ExplanationApiError(`HTTP ${res.status} for explanation export`, {
        status: res.status,
        url,
        bodySnippet: snippet,
      });
    }
    return await res.blob();
  } finally {
    cleanup();
  }
}

function parseExplanationRecord(raw: unknown): ExplanationRecord | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const tsRaw = safeNumber(raw.ts, safeNumber(raw.created_ts, 0));
  const ts = tsRaw ? normalizeTs(tsRaw) : 0;

  const kind = safeString(raw.kind, "audit");

  const rec: ExplanationRecord = {
    id,
    ts,
    kind,
  };

  const sev = safeString(raw.severity, "");
  if (sev) rec.severity = sev;

  const title = safeString(raw.title, "");
  if (title) rec.title = title;

  const summary = safeString(raw.summary, "");
  if (summary) rec.summary = summary;

  const meta = isRecord(raw.meta) ? raw.meta : {};
  const loop = isRecord(raw.loop) ? raw.loop : {};
  const references = parseReceiptReferences(raw.references);

  const runId = firstString(raw.run_id, raw.runId, references?.run_id, meta.run_id, meta.runId);
  if (runId) rec.run_id = runId;

  const traceId = firstString(raw.trace_id, raw.traceId, references?.trace_id);
  if (traceId) rec.trace_id = traceId;

  const artifactDir = firstString(raw.artifact_dir, raw.artifactDir, references?.artifact_dir);
  if (artifactDir) rec.artifact_dir = artifactDir;

  const missionId = firstString(raw.mission_id, raw.missionId, references?.mission_id, meta.mission_id, meta.missionId);
  if (missionId) rec.mission_id = missionId;

  const operationId = firstString(
    raw.operation_id,
    raw.operationId,
    references?.operation_id,
    meta.operation_id,
    meta.operationId,
  );
  if (operationId) rec.operation_id = operationId;

  const operationStatus = firstString(raw.operation_status, raw.operationStatus, loop.operation_status, meta.operation_status);
  if (operationStatus) rec.operation_status = operationStatus;

  const operationError = firstString(raw.operation_error, raw.operationError, loop.operation_error, meta.operation_error);
  if (operationError) rec.operation_error = operationError;

  const resultMessage = firstString(raw.result_message, raw.resultMessage, loop.result_message, meta.result_message);
  if (resultMessage) rec.result_message = resultMessage;

  const recoveryNextStep = firstString(
    raw.recovery_next_step,
    raw.recoveryNextStep,
    loop.recovery_next_step,
    meta.recovery_next_step,
  );
  if (recoveryNextStep) rec.recovery_next_step = recoveryNextStep;

  const domain = safeString(raw.domain, "");
  if (domain) rec.domain = domain;

  const conversationId = safeString(raw.conversation_id, safeString(raw.thread_id, ""));
  if (conversationId) rec.conversation_id = conversationId;

  const approvalId = firstString(
    raw.approval_id,
    raw.approvalId,
    references?.approval_id,
    meta.approval_id,
    meta.approvalId,
  );
  if (approvalId) rec.approval_id = approvalId;

  const pluginId = safeString(raw.plugin_id, "");
  if (pluginId) rec.plugin_id = pluginId;

  if (references) rec.references = references;

  const currentTaskSource = firstString(raw.current_task_source, raw.currentTaskSource, loop.current_task_source, meta.current_task_source);
  if (currentTaskSource) rec.current_task_source = currentTaskSource;

  const currentTaskApprovalId = firstString(
    raw.current_task_approval_id,
    raw.currentTaskApprovalId,
    loop.current_task_approval_id,
    meta.current_task_approval_id,
    references?.approval_id,
  );
  if (currentTaskApprovalId) rec.current_task_approval_id = currentTaskApprovalId;

  const currentTaskApprovalStatus = firstString(
    raw.current_task_approval_status,
    raw.currentTaskApprovalStatus,
    loop.current_task_approval_status,
    meta.current_task_approval_status,
  );
  if (currentTaskApprovalStatus) rec.current_task_approval_status = currentTaskApprovalStatus;

  const currentTaskOperationId = firstString(
    raw.current_task_operation_id,
    raw.currentTaskOperationId,
    loop.current_task_operation_id,
    meta.current_task_operation_id,
    references?.operation_id,
  );
  if (currentTaskOperationId) rec.current_task_operation_id = currentTaskOperationId;

  const currentTaskOperationName = firstString(
    raw.current_task_operation_name,
    raw.currentTaskOperationName,
    loop.current_task_operation_name,
    meta.current_task_operation_name,
  );
  if (currentTaskOperationName) rec.current_task_operation_name = currentTaskOperationName;

  const currentTaskOperationPlane = firstString(
    raw.current_task_operation_plane,
    raw.currentTaskOperationPlane,
    loop.current_task_operation_plane,
    meta.current_task_operation_plane,
  );
  if (currentTaskOperationPlane) rec.current_task_operation_plane = currentTaskOperationPlane;

  const currentTaskAdvanceAction = firstString(
    raw.current_task_advance_action,
    raw.currentTaskAdvanceAction,
    loop.current_task_advance_action,
    meta.current_task_advance_action,
  );
  if (currentTaskAdvanceAction) rec.current_task_advance_action = currentTaskAdvanceAction;

  const currentTaskGate = firstString(raw.current_task_gate, raw.currentTaskGate, loop.current_task_gate, meta.current_task_gate);
  if (currentTaskGate) rec.current_task_gate = currentTaskGate;

  const currentTaskTraceId = firstString(
    raw.current_task_trace_id,
    raw.currentTaskTraceId,
    loop.current_task_trace_id,
    meta.current_task_trace_id,
    references?.trace_id,
  );
  if (currentTaskTraceId) rec.current_task_trace_id = currentTaskTraceId;

  const currentTaskRunId = firstString(
    raw.current_task_run_id,
    raw.currentTaskRunId,
    loop.current_task_run_id,
    meta.current_task_run_id,
    references?.run_id,
  );
  if (currentTaskRunId) rec.current_task_run_id = currentTaskRunId;

  const currentTaskArtifactDir = firstString(
    raw.current_task_artifact_dir,
    raw.currentTaskArtifactDir,
    loop.current_task_artifact_dir,
    meta.current_task_artifact_dir,
    references?.artifact_dir,
  );
  if (currentTaskArtifactDir) rec.current_task_artifact_dir = currentTaskArtifactDir;

  const currentTaskNextStep = firstString(
    raw.current_task_next_step,
    raw.currentTaskNextStep,
    loop.current_task_next_step,
    meta.current_task_next_step,
  );
  if (currentTaskNextStep) rec.current_task_next_step = currentTaskNextStep;

  if (Array.isArray(raw.tags)) {
    const tags = (raw.tags as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (tags.length) rec.tags = tags;
  }

  if (isRecord(raw.meta)) rec.meta = raw.meta;

  return rec;
}

function parseExplanationDetail(raw: unknown): ExplanationDetail | null {
  if (!isRecord(raw)) return null;

  const baseRaw = isRecord(raw.item) ? raw.item : raw;
  const base = parseExplanationRecord(baseRaw);
  if (!base) return null;

  const detail: ExplanationDetail = { ...base };

  const content = (raw as Record<string, unknown>).content;
  if (typeof content === "string") detail.content = content;
  else if (isRecord(content)) detail.content = content;

  const inputs = (raw as Record<string, unknown>).inputs;
  if (isRecord(inputs)) detail.inputs = inputs;

  const outputs = (raw as Record<string, unknown>).outputs;
  if (isRecord(outputs)) detail.outputs = outputs;

  const policy = (raw as Record<string, unknown>).policy;
  if (isRecord(policy)) detail.policy = policy;

  const tools = (raw as Record<string, unknown>).tools;
  if (Array.isArray(tools)) {
    detail.tools = tools.filter(isRecord);
  }

  return detail;
}

export type ExplanationEndpoints = {
  list: (q?: ExplanationListQuery) => string;
  get: (id: string) => string;
  export: (q: ExplanationListQuery & { format: ExplanationExportFormat }) => string;
};

export function defaultExplanationEndpoints(): ExplanationEndpoints {
  return {
    list: (q) =>
      `/explanations/list${buildQuery({
        limit: q?.limit,
        offset: q?.offset,
        kind: q?.kind,
        severity: q?.severity,
        domain: q?.domain,
        run_id: q?.run_id,
        trace_id: q?.trace_id,
        artifact_dir: q?.artifact_dir,
        mission_id: q?.mission_id,
        operation_id: q?.operation_id,
        conversation_id: q?.conversation_id,
        approval_id: q?.approval_id,
        plugin_id: q?.plugin_id,
        tags: q?.tags,
        start_ts: typeof q?.start_ts === "number" ? normalizeTs(q.start_ts) : undefined,
        end_ts: typeof q?.end_ts === "number" ? normalizeTs(q.end_ts) : undefined,
        search: q?.search,
      })}`,
    get: (id) => `/explanations/get${buildQuery({ id })}`,
    export: (q) =>
      `/explanations/export${buildQuery({
        format: q.format,
        limit: q.limit,
        offset: q.offset,
        kind: q.kind,
        severity: q.severity,
        domain: q.domain,
        run_id: q.run_id,
        trace_id: q.trace_id,
        artifact_dir: q.artifact_dir,
        mission_id: q.mission_id,
        operation_id: q.operation_id,
        conversation_id: q.conversation_id,
        approval_id: q.approval_id,
        plugin_id: q.plugin_id,
        tags: q.tags,
        start_ts: typeof q.start_ts === "number" ? normalizeTs(q.start_ts) : undefined,
        end_ts: typeof q.end_ts === "number" ? normalizeTs(q.end_ts) : undefined,
        search: q.search,
      })}`,
  };
}

export type ExplanationClientOptions = {
  endpoints?: ExplanationEndpoints;
  defaultTimeoutMs?: number;
};

export class ExplanationClient {
  readonly baseUrl: string;
  readonly endpoints: ExplanationEndpoints;
  readonly defaultTimeoutMs: number;

  constructor(baseUrl: string, opts?: ExplanationClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("ExplanationClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultExplanationEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  async list(opts?: ExplanationListQuery & { signal?: AbortSignal; timeoutMs?: number }): Promise<ExplanationListResponse> {
    const url = this.url(this.endpoints.list(opts));

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).records)
        ? ((json as Record<string, unknown>).records as unknown[])
        : [];

    const items = raw.map(parseExplanationRecord).filter((x): x is ExplanationRecord => x !== null);
    return { items };
  }

  async get(id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<ExplanationDetail | null> {
    const safeId = (id || "").trim();
    if (!safeId) return null;

    const url = this.url(this.endpoints.get(safeId));
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    return parseExplanationDetail(json);
  }

  async getMany(
    ids: string[],
    opts?: {
      signal?: AbortSignal;
      timeoutMs?: number;
      concurrency?: number;
      tolerateFailures?: boolean;
      retries?: number;
      retryBaseMs?: number;
    },
  ): Promise<ExplanationDetail[]> {
    const original = (ids ?? []).map((s) => (s || "").trim()).filter((s) => s.length > 0);
    if (original.length === 0) return [];

    // Deduplicate while preserving first-seen order
    const unique: string[] = [];
    const seen = new Set<string>();
    for (const id of original) {
      if (!seen.has(id)) {
        seen.add(id);
        unique.push(id);
      }
    }

    const concurrency = clampInt(opts?.concurrency ?? 6, 1, 16);
    const tolerateFailures = Boolean(opts?.tolerateFailures ?? true);
    const retries = clampInt(opts?.retries ?? 0, 0, 5);
    const retryBaseMs = clampInt(opts?.retryBaseMs ?? 250, 50, 2000);

    // Fetch map for unique IDs
    const results = new Map<string, ExplanationDetail | null>();
    for (const id of unique) results.set(id, null);

    let cursor = 0;

    const fetchOneWithRetry = async (id: string): Promise<ExplanationDetail | null> => {
      let attempt = 0;
      // eslint-disable-next-line no-constant-condition
      while (true) {
        try {
          return await this.get(id, {
            signal: opts?.signal,
            timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
          });
        } catch (err) {
          if (err instanceof DOMException && err.name === "AbortError") throw err;

          if (attempt >= retries || !isTransientError(err)) {
            if (!tolerateFailures) throw err;
            return null;
          }

          // Exponential backoff with small jitter
          const backoff = retryBaseMs * 2 ** attempt + Math.floor(Math.random() * 100);
          attempt += 1;
          await sleep(backoff, opts?.signal);
        }
      }
    };

    const worker = async () => {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const i = cursor++;
        if (i >= unique.length) return;
        const id = unique[i];

        const detail = await fetchOneWithRetry(id);
        results.set(id, detail);
      }
    };

    await Promise.all(Array.from({ length: Math.min(concurrency, unique.length) }, () => worker()));

    // Rebuild output preserving original order and duplicates
    const out: ExplanationDetail[] = [];
    for (const id of original) {
      const d = results.get(id) ?? null;
      if (d) out.push(d);
    }
    return out;
  }

  async export(
    format: ExplanationExportFormat,
    filters?: ExplanationListQuery & { signal?: AbortSignal; timeoutMs?: number },
    onProgress?: (loaded: number, total: number) => void,
  ): Promise<Blob> {
    const q: ExplanationListQuery & { format: ExplanationExportFormat } = { ...(filters ?? {}), format };
    const url = this.url(this.endpoints.export(q));

    if (!onProgress) {
      return await fetchBlob(url, {
        method: "GET",
        headers: { Accept: normalizeAcceptForExport(format) },
        signal: filters?.signal,
        timeoutMs: filters?.timeoutMs ?? this.defaultTimeoutMs,
      });
    }

    const { res, cleanup } = await fetchResponse(url, {
      method: "GET",
      headers: { Accept: normalizeAcceptForExport(format) },
      signal: filters?.signal,
      timeoutMs: filters?.timeoutMs ?? this.defaultTimeoutMs,
    });

    try {
      if (!res.ok) {
        const snippet = await readTextSnippet(res);
        throw new ExplanationApiError(`HTTP ${res.status} for explanation export`, {
          status: res.status,
          url,
          bodySnippet: snippet,
        });
      }

      const totalHeader = res.headers.get("Content-Length");
      const total = totalHeader ? Number.parseInt(totalHeader, 10) : -1;

      const body = res.body;
      if (!body) {
        const blob = await res.blob();
        onProgress(blob.size, total);
        return blob;
      }

      const reader = body.getReader();
      const chunks: Uint8Array[] = [];
      let loaded = 0;

      onProgress(0, total);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) {
          chunks.push(value);
          loaded += value.byteLength;
          onProgress(loaded, total);
        }
      }

      const contentType =
        res.headers.get("Content-Type") ?? (format === "csv" ? "text/csv" : "application/json");

      return new Blob(chunks, { type: contentType });
    } finally {
      cleanup();
    }
  }

  async exportStream(
    format: ExplanationExportFormat,
    filters?: ExplanationListQuery & { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<ReadableStream<Uint8Array>> {
    const q: ExplanationListQuery & { format: ExplanationExportFormat } = { ...(filters ?? {}), format };
    const url = this.url(this.endpoints.export(q));

    const { res, cleanup } = await fetchResponse(url, {
      method: "GET",
      headers: { Accept: normalizeAcceptForExport(format) },
      signal: filters?.signal,
      timeoutMs: filters?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!res.ok) {
      try {
        const snippet = await readTextSnippet(res);
        throw new ExplanationApiError(`HTTP ${res.status} for explanation export`, {
          status: res.status,
          url,
          bodySnippet: snippet,
        });
      } finally {
        cleanup();
      }
    }

    const body = res.body;
    if (!body) {
      cleanup();
      throw new ExplanationApiError("Explanation export stream unavailable (response.body is null)", { url });
    }

    const reader = body.getReader();

    return new ReadableStream<Uint8Array>({
      start(controller) {
        const pump = (): void => {
          reader
            .read()
            .then(({ done, value }) => {
              if (done) {
                try {
                  controller.close();
                } finally {
                  cleanup();
                }
                return;
              }
              if (value) controller.enqueue(value);
              pump();
            })
            .catch((err) => {
              try {
                controller.error(err);
              } finally {
                cleanup();
              }
            });
        };
        pump();
      },
      cancel(reason) {
        try {
          void reader.cancel(reason);
        } finally {
          cleanup();
        }
      },
    });
  }
}
