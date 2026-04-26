/**
 * Memory Timeline module (UI).
 *
 * Typed, defensive, framework-agnostic client for Francis memory timeline events.
 *
 * What is "Memory Timeline"?
 * -------------------------
 * A unified audit/timeline feed describing memory-relevant events over time:
 *  - ledger writes / continuity updates
 *  - summaries and consolidation
 *  - retrievals (queries and hits)
 *  - embedding/index updates
 *  - governance-linked memory actions (approved/denied writes)
 *  - domain-specific memory mutations
 *
 * Design contract
 * ---------------
 *  1) Framework-agnostic:
 *     - No React imports, no UI state.
 *
 *  2) Defensive parsing:
 *     - Treat JSON as untrusted and tolerant of API drift:
 *       supports {items}, {events}, {entries}, {timeline}.
 *
 *  3) Observability:
 *     - Rich errors include HTTP status, URL, request id, and body snippet.
 *     - Optional request hooks for tracing.
 *
 *  4) Big-data ready:
 *     - Pagination + cursor support
 *     - Export as Blob + streaming export
 *     - Export progress callback (no dependencies)
 *     - Batch get (dedupe + concurrency + preserve input order)
 *
 * Endpoint conventions (override via endpoints option)
 * ---------------------------------------------------
 *   GET  /memory/timeline/list
 *   GET  /memory/timeline/get?id=...
 *   GET  /memory/timeline/export?format=json|jsonl|csv&...
 *
 * Notes
 * -----
 * - This client intentionally does NOT interpret “truth” of memory; it only
 *   transports and normalizes event representations for the UI.
 * - No secrets should ever transit through this client.
 */

/* -------------------------------------------------------------------------------------------------
 * Types — forward-compatible, UI-friendly
 * ------------------------------------------------------------------------------------------------- */

export type MemoryTimelineKind =
  | "ledger_append"
  | "ledger_compact"
  | "summary_create"
  | "summary_update"
  | "memory_write"
  | "memory_delete"
  | "retrieval_query"
  | "retrieval_hit"
  | "embedding_upsert"
  | "embedding_delete"
  | "governance_decision"
  | "approval_created"
  | "approval_resolved"
  | "tool_call"
  | "tool_result"
  | "checkpoint"
  | string;

export type MemoryTimelineSeverity = "debug" | "info" | "warning" | "error" | "critical" | string;

export type Pagination = {
  limit?: number;
  offset?: number;
  cursor?: string;
};

export type DateRange = {
  start_ts?: number; // unix seconds preferred; ms tolerated
  end_ts?: number;
};

export type MemoryTimelineListFilters = Pagination &
  DateRange & {
    kinds?: MemoryTimelineKind[];
    severity?: MemoryTimelineSeverity | string;

    domain?: string;
    actor?: string; // e.g. "francis", "user", "daemon", "worker:xyz"
    scope?: string; // optional governance scope
    correlation_id?: string; // trace/correlation id for linking events across subsystems
    trace_id?: string;
    mission_id?: string;
    operation_id?: string;
    run_id?: string;
    artifact_dir?: string;
    operation_status?: string;

    search?: string; // backend-dependent full text search
    tags?: string[];
    include_payload?: boolean; // if backend supports (otherwise ignored)
  };

export type ArtifactRef = {
  id: string;
  kind?: string;
  url?: string;
  path?: string;
  content_type?: string;
  size_bytes?: number;
  sha256?: string;
  meta?: Record<string, unknown>;
};

export type MemoryTimelineProvenance = {
  source?: string;
  domain?: string;
  actor?: string;
  scope?: string;
  correlation_id?: string;
  parent_id?: string;
};

export type MemoryTimelineRetention = {
  policy?: string;
  class?: string;
  until?: string;
  expires_at?: string;
  ttl_seconds?: number;
};

export type MemoryTimelineReferences = {
  mission_id?: string;
  operation_id?: string;
  trace_id?: string;
  approval_id?: string;
  run_id?: string;
  artifact_dir?: string;
};

export type MemoryTimelineLoop = {
  ingress_plane?: string;
  active_stage?: string;
  handoff_stage?: string;
  handoff_action?: string;
  handoff_gate?: string;
  handoff_approval_id?: string;
  handoff_operation_id?: string;
  handoff_trace_id?: string;
  handoff_run_id?: string;
  handoff_artifact_dir?: string;
  handoff_next_step?: string;
  current_task_source?: string;
  current_task_operation_id?: string;
  current_task_gate?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  current_task_next_step?: string;
  run_id?: string;
  artifact_dir?: string;
  linked_operation_count?: number;
  run_ledger_count?: number;
  memory_receipt_count?: number;
};

export type MemoryTimelineEvent = {
  id: string;
  ts: number; // unix seconds
  kind: MemoryTimelineKind;

  severity?: MemoryTimelineSeverity;

  // Provenance / linkage
  domain?: string;
  actor?: string;
  scope?: string;

  correlation_id?: string;
  parent_id?: string;

  // Human-facing summary
  title?: string;
  message?: string;

  // Tags + hints for UI
  tags?: string[];
  operation_status?: string;

  /**
   * Payload is deliberately untyped: the memory timeline may carry heterogeneous
   * content (retrieval query params, embedding stats, approval refs, etc.).
   *
   * UI should treat it as untrusted, render carefully.
   */
  payload?: unknown;

  artifacts?: ArtifactRef[];

  provenance?: MemoryTimelineProvenance;
  retention?: MemoryTimelineRetention;
  references?: MemoryTimelineReferences;
  loop?: MemoryTimelineLoop;

  meta?: Record<string, unknown>;
};

export type MemoryTimelineListResponse = {
  items: MemoryTimelineEvent[];
  total?: number;
  next_cursor?: string;
};

export type MemoryTimelineGetResponse = {
  item: MemoryTimelineEvent | null;
};

export type MemoryTimelineExportFormat = "json" | "jsonl" | "csv";

/* -------------------------------------------------------------------------------------------------
 * Errors — rich, structured, debuggable
 * ------------------------------------------------------------------------------------------------- */

export class MemoryTimelineApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly requestId?: string;
  readonly bodySnippet?: string;
  readonly timedOut?: boolean;

  constructor(
    message: string,
    opts?: {
      status?: number;
      url?: string;
      requestId?: string;
      bodySnippet?: string;
      timedOut?: boolean;
      cause?: unknown;
    },
  ) {
    super(message);
    this.name = "MemoryTimelineApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.requestId = opts?.requestId;
    this.bodySnippet = opts?.bodySnippet;
    this.timedOut = opts?.timedOut;
    // @ts-expect-error - Error.cause not always in TS lib target
    this.cause = opts?.cause;
  }
}

/* -------------------------------------------------------------------------------------------------
 * Utilities — tiny, dependency-free
 * ------------------------------------------------------------------------------------------------- */

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function safeOptionalNumber(v: unknown): number | undefined {
  if (typeof v === "number" && Number.isFinite(v)) return Math.trunc(v);
  if (typeof v !== "string") return undefined;

  const parsed = Number(v.trim());
  return Number.isFinite(parsed) ? Math.trunc(parsed) : undefined;
}

function safeStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.map((x) => (typeof x === "string" ? x : "")).filter((s) => s.length > 0);
  return out.length ? out : undefined;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeTsToSeconds(ts: unknown): number | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  // Heuristic: seconds vs ms
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : Math.floor(ts);
}

function headerRequestId(headers: Headers): string | undefined {
  const keys = ["x-request-id", "x-correlation-id", "x-trace-id", "request-id"];
  for (const k of keys) {
    const v = headers.get(k);
    if (v && v.trim()) return v.trim();
  }
  return undefined;
}

function buildQuery(params: Record<string, unknown>): string {
  const qs = new URLSearchParams();

  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;

    if (Array.isArray(v)) {
      // Repeatable keys are easiest for servers to parse.
      for (const item of v) {
        if (item === undefined || item === null) continue;
        const s = String(item).trim();
        if (s) qs.append(k, s);
      }
      continue;
    }

    const s = String(v).trim();
    if (s) qs.set(k, s);
  }

  const out = qs.toString();
  return out ? `?${out}` : "";
}

async function readTextSnippet(res: Response, maxChars = 2048): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function backoffMs(attempt: number, base = 250, cap = 5_000): number {
  const pow = 2 ** clamp(attempt, 0, 10);
  const raw = clamp(base * pow, base, cap);
  const jitter = Math.floor(Math.random() * clamp(raw * 0.2, 25, 500));
  return raw + jitter;
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;

  await new Promise<void>((resolve, reject) => {
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
      if (signal.aborted) {
        cleanup();
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

/* -------------------------------------------------------------------------------------------------
 * Parsing — tolerant of API drift and alias fields
 * ------------------------------------------------------------------------------------------------- */

function parseArtifact(raw: unknown): ArtifactRef | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const a: ArtifactRef = { id };

  const kind = safeString(raw.kind, "");
  if (kind) a.kind = kind;

  const url = safeString(raw.url, "");
  if (url) a.url = url;

  const path = safeString(raw.path, "");
  if (path) a.path = path;

  const ct = safeString(raw.content_type, safeString(raw.contentType, ""));
  if (ct) a.content_type = ct;

  const size = safeNumber(raw.size_bytes, safeNumber(raw.sizeBytes, 0));
  if (size > 0) a.size_bytes = size;

  const sha = safeString(raw.sha256, "");
  if (sha) a.sha256 = sha;

  if (isRecord(raw.meta)) a.meta = raw.meta;

  return a;
}

function parseProvenance(raw: unknown, fallback: Record<string, unknown>): MemoryTimelineProvenance | undefined {
  const sourceRecord = isRecord(raw) ? raw : {};
  const p: MemoryTimelineProvenance = {};

  const source = safeString(sourceRecord.source, safeString(fallback.source, ""));
  if (source) p.source = source;

  const domain = safeString(sourceRecord.domain, safeString(fallback.domain, ""));
  if (domain) p.domain = domain;

  const actor = safeString(sourceRecord.actor, safeString(fallback.actor, safeString(fallback.role, "")));
  if (actor) p.actor = actor;

  const scope = safeString(sourceRecord.scope, safeString(fallback.scope, safeString(fallback.scope_id, "")));
  if (scope) p.scope = scope;

  const corr = safeString(
    sourceRecord.correlation_id,
    safeString(fallback.correlation_id, safeString(fallback.trace_id, safeString(fallback.correlationId, ""))),
  );
  if (corr) p.correlation_id = corr;

  const parent = safeString(sourceRecord.parent_id, safeString(fallback.parent_id, safeString(fallback.parentId, "")));
  if (parent) p.parent_id = parent;

  return Object.keys(p).length ? p : undefined;
}

function parseRetention(raw: unknown, fallback: Record<string, unknown>): MemoryTimelineRetention | undefined {
  const sourceRecord = isRecord(raw) ? raw : {};
  const r: MemoryTimelineRetention = {};

  const policy = safeString(sourceRecord.policy, safeString(fallback.retention_policy, safeString(fallback.retentionPolicy, "")));
  if (policy) r.policy = policy;

  const retentionClass = safeString(
    sourceRecord.class,
    safeString(fallback.retention_class, safeString(fallback.retentionClass, "")),
  );
  if (retentionClass) r.class = retentionClass;

  const until = safeString(sourceRecord.until, safeString(fallback.retention_until, safeString(fallback.retentionUntil, "")));
  if (until) r.until = until;

  const expiresAt = safeString(sourceRecord.expires_at, safeString(fallback.expires_at, safeString(fallback.expiresAt, "")));
  if (expiresAt) r.expires_at = expiresAt;

  const ttlSeconds = safeNumber(sourceRecord.ttl_seconds, safeNumber(fallback.ttl_seconds, safeNumber(fallback.ttlSeconds, 0)));
  if (ttlSeconds > 0) r.ttl_seconds = ttlSeconds;

  return Object.keys(r).length ? r : undefined;
}

function parseReferences(raw: unknown, fallback: Record<string, unknown>): MemoryTimelineReferences | undefined {
  const sourceRecord = isRecord(raw) ? raw : {};
  const r: MemoryTimelineReferences = {};

  const missionId = safeString(sourceRecord.mission_id, safeString(fallback.mission_id, ""));
  if (missionId) r.mission_id = missionId;

  const operationId = safeString(
    sourceRecord.operation_id,
    safeString(fallback.operation_id, safeString(fallback.task_id, "")),
  );
  if (operationId) r.operation_id = operationId;

  const traceId = safeString(sourceRecord.trace_id, safeString(fallback.trace_id, ""));
  if (traceId) r.trace_id = traceId;

  const approvalId = safeString(sourceRecord.approval_id, safeString(fallback.approval_id, ""));
  if (approvalId) r.approval_id = approvalId;

  const runId = safeString(sourceRecord.run_id, safeString(fallback.run_id, ""));
  if (runId) r.run_id = runId;

  const artifactDir = safeString(
    sourceRecord.artifact_dir,
    safeString(fallback.artifact_dir, safeString(fallback.artifact_path, "")),
  );
  if (artifactDir) r.artifact_dir = artifactDir;

  return Object.keys(r).length ? r : undefined;
}

function parseLoop(raw: unknown, fallback: Record<string, unknown>): MemoryTimelineLoop | undefined {
  const sourceRecord = isRecord(raw) ? raw : {};
  const loop: MemoryTimelineLoop = {};

  const stringKeys = [
    "ingress_plane",
    "active_stage",
    "handoff_stage",
    "handoff_action",
    "handoff_gate",
    "handoff_approval_id",
    "handoff_operation_id",
    "handoff_trace_id",
    "handoff_run_id",
    "handoff_artifact_dir",
    "handoff_next_step",
    "current_task_source",
    "current_task_operation_id",
    "current_task_gate",
    "current_task_run_id",
    "current_task_artifact_dir",
    "current_task_next_step",
    "run_id",
    "artifact_dir",
  ] as const;

  for (const key of stringKeys) {
    const value = safeString(sourceRecord[key], safeString(fallback[key], ""));
    if (value) loop[key] = value;
  }

  const numberKeys = ["linked_operation_count", "run_ledger_count", "memory_receipt_count"] as const;
  for (const key of numberKeys) {
    const value = safeOptionalNumber(sourceRecord[key] ?? fallback[key]);
    if (value !== undefined) loop[key] = value;
  }

  return Object.keys(loop).length ? loop : undefined;
}

function parseEvent(raw: unknown): MemoryTimelineEvent | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, safeString(raw.event_id, safeString(raw.uuid, "")));
  if (!id) return null;

  const ts =
    normalizeTsToSeconds(raw.ts) ??
    normalizeTsToSeconds(raw.created_ts) ??
    normalizeTsToSeconds(raw.time) ??
    0;

  if (!ts) return null;

  const kind = safeString(raw.kind, safeString(raw.type, "unknown"));

  const e: MemoryTimelineEvent = {
    id,
    ts,
    kind,
  };

  const severity = safeString(raw.severity, safeString(raw.level, ""));
  if (severity) e.severity = severity;

  const operationStatus = safeString(
    raw.operation_status,
    isRecord(raw.meta) ? safeString(raw.meta.operation_status, "") : "",
  );
  if (operationStatus) e.operation_status = operationStatus;

  const domain = safeString(raw.domain, "");
  if (domain) e.domain = domain;

  const actor = safeString(raw.actor, safeString(raw.role, ""));
  if (actor) e.actor = actor;

  const scope = safeString(raw.scope, safeString(raw.scope_id, ""));
  if (scope) e.scope = scope;

  const corr = safeString(raw.correlation_id, safeString(raw.trace_id, safeString(raw.correlationId, "")));
  if (corr) e.correlation_id = corr;

  const parent = safeString(raw.parent_id, safeString(raw.parentId, ""));
  if (parent) e.parent_id = parent;

  const title = safeString(raw.title, "");
  if (title) e.title = title;

  const msg = safeString(raw.message, safeString(raw.summary, safeString(raw.content, "")));
  if (msg) e.message = msg;

  const tags = safeStringArray(raw.tags);
  if (tags) e.tags = tags;

  // payload is intentionally untrusted/opaque; pass through as-is
  if ("payload" in raw) e.payload = raw.payload;
  else if ("data" in raw) e.payload = raw.data;

  const artifactsRaw = Array.isArray(raw.artifacts) ? raw.artifacts : Array.isArray(raw.files) ? raw.files : undefined;
  if (artifactsRaw) {
    const artifacts = artifactsRaw.map(parseArtifact).filter((x): x is ArtifactRef => x !== null);
    if (artifacts.length) e.artifacts = artifacts;
  }

  if (isRecord(raw.meta)) e.meta = raw.meta;

  const provenance = parseProvenance(raw.provenance, { ...raw, ...(isRecord(raw.meta) ? raw.meta : {}) });
  if (provenance) e.provenance = provenance;

  const retention = parseRetention(raw.retention, isRecord(raw.meta) ? raw.meta : {});
  if (retention) e.retention = retention;

  const references = parseReferences(raw.references, { ...raw, ...(isRecord(raw.meta) ? raw.meta : {}) });
  if (references) e.references = references;

  const loop = parseLoop(raw.loop, { ...raw, ...(isRecord(raw.meta) ? raw.meta : {}) });
  if (loop) e.loop = loop;

  return e;
}

/* -------------------------------------------------------------------------------------------------
 * Endpoints — override-friendly mapping
 * ------------------------------------------------------------------------------------------------- */

export type MemoryTimelineEndpoints = {
  list: (q?: MemoryTimelineListFilters) => string;
  get: (id: string) => string;
  export: (q?: MemoryTimelineListFilters & { format?: MemoryTimelineExportFormat }) => string;
};

export function defaultMemoryTimelineEndpoints(): MemoryTimelineEndpoints {
  return {
    list: (q) =>
      `/memory/timeline/list${buildQuery({
        limit: q?.limit,
        offset: q?.offset,
        cursor: q?.cursor,
        start_ts: normalizeTsToSeconds(q?.start_ts),
        end_ts: normalizeTsToSeconds(q?.end_ts),
        severity: q?.severity,
        domain: q?.domain,
        actor: q?.actor,
        scope: q?.scope,
        correlation_id: q?.correlation_id,
        trace_id: q?.trace_id,
        mission_id: q?.mission_id,
        operation_id: q?.operation_id,
        run_id: q?.run_id,
        artifact_dir: q?.artifact_dir,
        operation_status: q?.operation_status,
        search: q?.search,
        include_payload: q?.include_payload ? "1" : undefined,
        tags: q?.tags,
        kinds: q?.kinds,
      })}`,

    get: (id) => `/memory/timeline/get${buildQuery({ id })}`,

    export: (q) =>
      `/memory/timeline/export${buildQuery({
        format: (q as { format?: MemoryTimelineExportFormat } | undefined)?.format,
        limit: q?.limit,
        offset: q?.offset,
        cursor: q?.cursor,
        start_ts: normalizeTsToSeconds(q?.start_ts),
        end_ts: normalizeTsToSeconds(q?.end_ts),
        severity: q?.severity,
        domain: q?.domain,
        actor: q?.actor,
        scope: q?.scope,
        correlation_id: q?.correlation_id,
        trace_id: q?.trace_id,
        mission_id: q?.mission_id,
        operation_id: q?.operation_id,
        run_id: q?.run_id,
        artifact_dir: q?.artifact_dir,
        operation_status: q?.operation_status,
        search: q?.search,
        tags: q?.tags,
        kinds: q?.kinds,
      })}`,
  };
}

/* -------------------------------------------------------------------------------------------------
 * Client — timeout, retry, export progress, batch get
 * ------------------------------------------------------------------------------------------------- */

export type MemoryTimelineClientHooks = {
  onRequest?: (info: { url: string; method: string; attempt: number; timeoutMs: number }) => void;
  onResponse?: (info: { url: string; method: string; status: number; elapsedMs: number; requestId?: string; attempt: number }) => void;
};

export type RetryPolicy = {
  retries?: number; // default 0
  retryMethods?: string[]; // default ["GET", "HEAD"]
  retryStatusCodes?: number[]; // default [429, 502, 503, 504]
};

export type MemoryTimelineClientOptions = {
  endpoints?: MemoryTimelineEndpoints;
  defaultTimeoutMs?: number; // default 20s
  hooks?: MemoryTimelineClientHooks;
  retry?: RetryPolicy;
};

type TimeoutMergedFetchInit = RequestInit & { timeoutMs?: number };

export class MemoryTimelineClient {
  readonly baseUrl: string;
  readonly endpoints: MemoryTimelineEndpoints;
  readonly defaultTimeoutMs: number;
  readonly hooks?: MemoryTimelineClientHooks;
  readonly retry: Required<RetryPolicy>;

  constructor(baseUrl: string, opts?: MemoryTimelineClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("MemoryTimelineClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultMemoryTimelineEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;

    const r = opts?.retry ?? {};
    this.retry = {
      retries: typeof r.retries === "number" ? r.retries : 0,
      retryMethods: Array.isArray(r.retryMethods) && r.retryMethods.length ? r.retryMethods : ["GET", "HEAD"],
      retryStatusCodes: Array.isArray(r.retryStatusCodes) && r.retryStatusCodes.length ? r.retryStatusCodes : [429, 502, 503, 504],
    };

    this.hooks = opts?.hooks;
  }

  private url(path: string): string {
    const p = path.startsWith("/") ? path : `/${path}`;
    return `${this.baseUrl}${p}`;
  }

  private async fetchWithTimeout(url: string, init?: TimeoutMergedFetchInit): Promise<{ res: Response; elapsedMs: number }> {
    const timeoutMs = init?.timeoutMs ?? this.defaultTimeoutMs;
    const { signal: externalSignal, ...fetchInit } = init ?? {};

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
      if (externalSignal.aborted) onExternalAbort();
      else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }

    const start = performance.now();

    try {
      const headers = new Headers(fetchInit.headers ?? undefined);
      if (!headers.has("Accept")) headers.set("Accept", "application/json");

      const method = safeString(fetchInit.method, "GET").toUpperCase();
      const hasBody = "body" in fetchInit && fetchInit.body !== undefined && fetchInit.body !== null;
      if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

      const res = await fetch(url, { ...fetchInit, headers, signal: controller.signal });
      const elapsedMs = Math.max(0, Math.round(performance.now() - start));
      return { res, elapsedMs };
    } catch (err) {
      if (timedOut) {
        throw new MemoryTimelineApiError(`Request timed out after ${timeoutMs}ms`, { url, timedOut: true, cause: err });
      }
      throw err;
    } finally {
      if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
      if (externalSignal && !externalSignal.aborted) externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }

  private async fetchJson(url: string, init?: TimeoutMergedFetchInit): Promise<unknown> {
    const method = safeString(init?.method, "GET").toUpperCase();
    const retries = this.retry.retries;
    const canRetry = this.retry.retryMethods.map((m) => m.toUpperCase()).includes(method);

    let lastErr: unknown;

    for (let attempt = 0; attempt <= retries; attempt++) {
      this.hooks?.onRequest?.({ url, method, attempt, timeoutMs: init?.timeoutMs ?? this.defaultTimeoutMs });

      try {
        const { res, elapsedMs } = await this.fetchWithTimeout(url, init);
        const reqId = headerRequestId(res.headers);

        this.hooks?.onResponse?.({ url, method, status: res.status, elapsedMs, requestId: reqId, attempt });

        if (!res.ok) {
          const snippet = await readTextSnippet(res);
          const apiErr = new MemoryTimelineApiError(`HTTP ${res.status} for memory timeline request`, {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
          });

          const shouldRetryStatus = this.retry.retryStatusCodes.includes(res.status);
          if (attempt < retries && canRetry && shouldRetryStatus) {
            lastErr = apiErr;
            await sleep(backoffMs(attempt), init?.signal);
            continue;
          }

          throw apiErr;
        }

        try {
          return await res.json();
        } catch (err) {
          const snippet = await readTextSnippet(res);
          throw new MemoryTimelineApiError("Failed to parse JSON response", {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
            cause: err,
          });
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") throw err;
        if (err instanceof MemoryTimelineApiError && err.timedOut) throw err;

        lastErr = err;

        if (attempt < retries && canRetry) {
          await sleep(backoffMs(attempt), init?.signal);
          continue;
        }
        throw err;
      }
    }

    throw lastErr instanceof Error ? lastErr : new Error("Memory timeline request failed");
  }

  private async fetchBlobWithProgress(
    url: string,
    opts?: {
      signal?: AbortSignal;
      timeoutMs?: number;
      onProgress?: (loadedBytes: number, totalBytes?: number) => void;
    },
  ): Promise<Blob> {
    const { res } = await this.fetchWithTimeout(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    if (!res.ok) {
      const reqId = headerRequestId(res.headers);
      const snippet = await readTextSnippet(res);
      throw new MemoryTimelineApiError(`HTTP ${res.status} for memory timeline export`, {
        status: res.status,
        url,
        requestId: reqId,
        bodySnippet: snippet,
      });
    }

    // If no progress callback or no streaming body, fall back to res.blob().
    if (!opts?.onProgress || !res.body) {
      return await res.blob();
    }

    const totalHeader = res.headers.get("content-length");
    const total = totalHeader ? Number(totalHeader) : undefined;

    const reader = res.body.getReader();
    const chunks: Uint8Array[] = [];
    let loaded = 0;

    // Stream -> buffer in memory to build Blob (still much safer for UX: progress + large download)
    // For true zero-copy, use exportStream().
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (value) {
        chunks.push(value);
        loaded += value.byteLength;
        try {
          opts.onProgress(loaded, Number.isFinite(total) ? total : undefined);
        } catch {
          // never let progress callbacks break export
        }
      }
    }

    return new Blob(chunks);
  }

  /**
   * List timeline events (filters/pagination supported).
   */
  async list(
    filters?: MemoryTimelineListFilters,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<MemoryTimelineListResponse> {
    const url = this.url(this.endpoints.list(filters));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).events)
          ? ((json as Record<string, unknown>).events as unknown[])
          : Array.isArray((json as Record<string, unknown>).entries)
            ? ((json as Record<string, unknown>).entries as unknown[])
            : Array.isArray((json as Record<string, unknown>).timeline)
              ? ((json as Record<string, unknown>).timeline as unknown[])
              : [];

    const items = raw.map(parseEvent).filter((x): x is MemoryTimelineEvent => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString(
      (json as Record<string, unknown>).next_cursor,
      safeString((json as Record<string, unknown>).cursor, ""),
    );

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  /**
   * Get a single event by id.
   */
  async get(
    id: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<MemoryTimelineGetResponse> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("MemoryTimelineClient.get requires a non-empty id");

    const url = this.url(this.endpoints.get(clean));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    // Accept { item: {...} } or direct object, or { event: {...} }
    const raw =
      isRecord(json) && isRecord((json as Record<string, unknown>).item)
        ? (json as Record<string, unknown>).item
        : isRecord(json) && isRecord((json as Record<string, unknown>).event)
          ? (json as Record<string, unknown>).event
          : json;

    return { item: parseEvent(raw) };
  }

  /**
   * Batch get (nitpick implementation):
   * - Dedupes ids
   * - Concurrency-limited fan-out
   * - Preserves original order; omits nulls
   */
  async getMany(
    ids: string[],
    opts?: { signal?: AbortSignal; timeoutMs?: number; concurrency?: number; tolerateFailures?: boolean },
  ): Promise<MemoryTimelineEvent[]> {
    const original = (ids ?? []).map((s) => (s || "").trim()).filter((s) => s.length > 0);
    if (original.length === 0) return [];

    const unique: string[] = [];
    const seen = new Set<string>();
    for (const id of original) {
      if (!seen.has(id)) {
        seen.add(id);
        unique.push(id);
      }
    }

    const concurrency = Math.min(Math.max(Math.floor(opts?.concurrency ?? 6), 1), 16);
    const tolerateFailures = Boolean(opts?.tolerateFailures ?? true);

    const resultMap = new Map<string, MemoryTimelineEvent | null>();
    for (const id of unique) resultMap.set(id, null);

    let cursor = 0;
    const worker = async (): Promise<void> => {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const i = cursor++;
        if (i >= unique.length) return;

        const id = unique[i];
        try {
          const r = await this.get(id, { signal: opts?.signal, timeoutMs: opts?.timeoutMs });
          resultMap.set(id, r.item);
        } catch (err) {
          if (!tolerateFailures) throw err;
          resultMap.set(id, null);
        }
      }
    };

    await Promise.all(Array.from({ length: Math.min(concurrency, unique.length) }, () => worker()));

    const out: MemoryTimelineEvent[] = [];
    for (const id of original) {
      const v = resultMap.get(id) ?? null;
      if (v) out.push(v);
    }
    return out;
  }

  /**
   * Export timeline data as a Blob.
   * Supports optional progress callback (nitpick implementation).
   */
  async export(
    format: MemoryTimelineExportFormat,
    filters?: MemoryTimelineListFilters,
    opts?: { signal?: AbortSignal; timeoutMs?: number; onProgress?: (loadedBytes: number, totalBytes?: number) => void },
  ): Promise<Blob> {
    const url = this.url(this.endpoints.export({ ...filters, format }));
    return await this.fetchBlobWithProgress(url, {
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      onProgress: opts?.onProgress,
    });
  }

  /**
   * Streaming export for large datasets (nitpick implementation).
   * Returns the response ReadableStream (if the browser exposes it).
   */
  async exportStream(
    format: MemoryTimelineExportFormat,
    filters?: MemoryTimelineListFilters,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<ReadableStream<Uint8Array> | null> {
    const url = this.url(this.endpoints.export({ ...filters, format }));
    const { res } = await this.fetchWithTimeout(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    if (!res.ok) {
      const reqId = headerRequestId(res.headers);
      const snippet = await readTextSnippet(res);
      throw new MemoryTimelineApiError(`HTTP ${res.status} for memory timeline export stream`, {
        status: res.status,
        url,
        requestId: reqId,
        bodySnippet: snippet,
      });
    }

    return res.body ?? null;
  }
}
