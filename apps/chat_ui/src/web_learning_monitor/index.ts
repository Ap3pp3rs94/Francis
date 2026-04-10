/**
 * Web Learning Monitor module (UI).
 *
 * Typed, defensive client + protocol layer for Francis Web Learning monitoring.
 *
 * Design contract
 * ---------------
 *  1) Framework-agnostic:
 *     - NO React imports here.
 *
 *  2) Defensive parsing:
 *     - Treat all server responses as untrusted JSON.
 *     - Accept alias fields and tolerate API drift.
 *
 *  3) Forward-compatible endpoints:
 *     - Each method probes multiple candidate routes (ordered) and tolerates 404/405.
 *
 *  4) Safe-by-default mutations:
 *     - Mutations are disabled unless explicitly enabled via client options.
 *     - Backend must still enforce governance / approvals.
 */

export type UnixSeconds = number;

export type WebLearningStatus = {
  ts: UnixSeconds;

  enabled: boolean;

  approvals_required?: boolean;

  // Scheduler/queue signals (optional; backend-defined)
  queue_depth?: number;
  in_flight?: number;
  concurrency?: number;

  // Operational signals (optional)
  last_run_ts?: UnixSeconds;
  last_success_ts?: UnixSeconds;
  last_error_ts?: UnixSeconds;
  last_error?: string;

  // Optional: environment/profile info
  env_profile?: string;
  run_mode?: string;

  meta?: Record<string, unknown>;
};

export type WebLearningRecordStatus =
  | "pending"
  | "fetched"
  | "parsed"
  | "ingested"
  | "quarantined"
  | "blocked"
  | "failed"
  | string;

export type WebLearningRecord = {
  id: string;
  ts: UnixSeconds;

  url: string;

  status: WebLearningRecordStatus;

  http_status?: number;
  method?: string;
  content_type?: string;

  bytes?: number;
  duration_ms?: number;

  title?: string;
  summary?: string;

  domain?: string;
  source?: string;

  approval_id?: string;
  quarantine_id?: string;

  error?: string;

  meta?: Record<string, unknown>;
};

export type WebLearningEventKind =
  | "fetch_start"
  | "fetch_end"
  | "parse"
  | "extract"
  | "ingest"
  | "quarantine"
  | "approval_requested"
  | "approval_resolved"
  | "policy_block"
  | "error"
  | string;

export type WebLearningEvent = {
  id: string;
  ts: UnixSeconds;

  kind?: WebLearningEventKind;

  url?: string;
  record_id?: string;

  status?: string;
  message?: string;

  http_status?: number;
  bytes?: number;
  duration_ms?: number;

  approval_id?: string;
  quarantine_id?: string;

  actor?: string;
  domain?: string;
  source?: string;

  correlation_id?: string;
  operation_id?: string;

  meta?: Record<string, unknown>;
};

export type WebLearningQuarantineItem = {
  id: string;
  ts: UnixSeconds;

  url: string;

  reason?: string;
  status?: string;

  record_id?: string;

  approval_id?: string;

  evidence?: string;

  domain?: string;
  source?: string;

  meta?: Record<string, unknown>;
};

export type WebLearningPolicy = {
  ts?: UnixSeconds;

  enabled?: boolean;
  approvals_required?: boolean;

  // Optional allow/deny controls (backend-defined)
  allow_domains?: string[];
  deny_domains?: string[];
  allow_patterns?: string[];
  deny_patterns?: string[];

  // Optional: rate limits, caps, etc.
  limits?: Record<string, unknown>;

  summary?: string;

  meta?: Record<string, unknown>;
};

export type CursorListResponse<T> = {
  items: T[];
  next_cursor?: string;
  total?: number;
};

export type WebLearningListParams = {
  start_ts?: UnixSeconds;
  end_ts?: UnixSeconds;

  limit?: number;
  cursor?: string;

  status?: string;
  domain?: string;
  search?: string;
};

export type WebLearningExportFormat = "json" | "jsonl" | "csv";

export type WebLearningExportRequest = {
  kind: "records" | "events" | "quarantine";

  format: WebLearningExportFormat;

  // Filters
  start_ts?: UnixSeconds;
  end_ts?: UnixSeconds;
  status?: string;
  domain?: string;
  search?: string;

  // Export shaping hints
  limit?: number;
  cursor?: string;

  // Optional UI-provided rationale
  reason?: string;

  meta?: Record<string, unknown>;
};

export type WebLearningExportResult = {
  filename: string;
  contentType: string;
  blob: Blob;
};

export type WebLearningExportProgress = {
  loadedBytes: number;
  totalBytes?: number;
};

export type WebLearningRequestLearn = {
  url: string;

  /**
   * Optional crawl controls (backend-defined).
   * Keep these generic; backend may ignore unsupported fields.
   */
  max_pages?: number;
  max_depth?: number;
  allow_external?: boolean;

  reason?: string;
  domain?: string;
  actor?: string;

  /**
   * Optional idempotency key for safe retries.
   */
  idempotency_key?: string;

  meta?: Record<string, unknown>;
};

export type WebLearningRequestLearnResponse = {
  ok: boolean;

  request_id?: string;

  // If approval-gated:
  approval_id?: string;
  status?: string;

  // If executed immediately:
  record_id?: string;

  message?: string;
  meta?: Record<string, unknown>;
};

export type WebLearningSetEnabledRequest = {
  enabled: boolean;
  reason?: string;
  domain?: string;
  actor?: string;
  meta?: Record<string, unknown>;
};

export type WebLearningSetEnabledResponse = {
  ok: boolean;

  approval_id?: string;
  status?: string;

  applied?: boolean;
  enabled?: boolean;
  ts?: UnixSeconds;

  message?: string;
  meta?: Record<string, unknown>;
};

export type WebLearningQuarantineDecisionAction = "release" | "delete" | "keep" | string;

export type WebLearningQuarantineDecisionRequest = {
  id: string;
  action: WebLearningQuarantineDecisionAction;

  reason?: string;
  domain?: string;
  actor?: string;

  meta?: Record<string, unknown>;
};

export type WebLearningQuarantineDecisionResponse = {
  ok: boolean;

  approval_id?: string;
  status?: string;

  applied?: boolean;

  message?: string;
  meta?: Record<string, unknown>;
};

export class WebLearningApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly requestId?: string;
  readonly bodySnippet?: string;
  readonly timedOut?: boolean;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; requestId?: string; bodySnippet?: string; timedOut?: boolean; cause?: unknown },
  ) {
    super(message);
    this.name = "WebLearningApiError";
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
 * tiny utils
 * ------------------------------------------------------------------------------------------------- */

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeBool(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function normalizeUnixSeconds(ts: unknown): UnixSeconds | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  // Heuristic: ms vs seconds
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : Math.floor(ts);
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function encodeQuery(params: Record<string, unknown> | undefined): string {
  if (!params) return "";
  const sp = new URLSearchParams();

  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;

    if (Array.isArray(v)) {
      for (const item of v) {
        if (item === undefined || item === null) continue;
        const s = String(item).trim();
        if (s) sp.append(k, s);
      }
      continue;
    }

    if (typeof v === "boolean") {
      sp.set(k, v ? "1" : "0");
      continue;
    }

    const s = String(v).trim();
    if (s) sp.set(k, s);
  }

  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

function headerRequestId(headers: Headers): string | undefined {
  const keys = ["x-request-id", "x-correlation-id", "x-trace-id", "request-id"];
  for (const k of keys) {
    const v = headers.get(k);
    if (v && v.trim()) return v.trim();
  }
  return undefined;
}

async function readTextSnippet(res: Response, maxChars = 4096): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

function backoffMs(attempt: number, base = 250, cap = 4_000): number {
  const pow = 2 ** clamp(attempt, 0, 10);
  const raw = clamp(base * pow, base, cap);
  const jitter = Math.floor(Math.random() * clamp(raw * 0.2, 25, 450));
  return raw + jitter;
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;

  await new Promise<void>((resolve, reject) => {
    const t = window.setTimeout(() => {
      cleanup();
      resolve();
    }, ms);

    const onAbort = () => {
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };

    const cleanup = () => {
      window.clearTimeout(t);
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

function guessFilename(kind: string, format: WebLearningExportFormat): string {
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const ext = format === "jsonl" ? "jsonl" : format;
  return `francis-web-learning-${kind}-${ts}.${ext}`;
}

function parseContentDispositionFilename(cd: string | null): string | null {
  if (!cd) return null;
  // Very defensive parser: supports filename="x" and filename*=UTF-8''x
  const mStar = cd.match(/filename\*\s*=\s*([^']*)''([^;]+)/i);
  if (mStar && mStar[2]) {
    try {
      return decodeURIComponent(mStar[2].trim().replace(/^"|"$/g, ""));
    } catch {
      return mStar[2].trim().replace(/^"|"$/g, "");
    }
  }
  const m = cd.match(/filename\s*=\s*([^;]+)/i);
  if (m && m[1]) return m[1].trim().replace(/^"|"$/g, "");
  return null;
}

/* -------------------------------------------------------------------------------------------------
 * parsing (defensive, alias-tolerant)
 * ------------------------------------------------------------------------------------------------- */

function parseStatus(raw: unknown): WebLearningStatus | null {
  if (!isRecord(raw)) return null;

  // Accept { status: {...} } or direct object.
  const obj = isRecord(raw.status) ? (raw.status as Record<string, unknown>) : raw;

  const enabled = safeBool(obj.enabled, safeBool(obj.web_learning_enabled, false));

  const ts =
    normalizeUnixSeconds(obj.ts) ??
    normalizeUnixSeconds(obj.updated_ts) ??
    normalizeUnixSeconds(obj.time) ??
    Math.floor(Date.now() / 1000);

  const s: WebLearningStatus = { ts, enabled };

  const approvalsRequired = safeBool(obj.approvals_required, safeBool(obj.approval_required, false));
  if (typeof obj.approvals_required === "boolean" || typeof obj.approval_required === "boolean") {
    s.approvals_required = approvalsRequired;
  }

  const q = safeNumber(obj.queue_depth, 0) || safeNumber(obj.queue, 0);
  if (q > 0) s.queue_depth = q;

  const inFlight = safeNumber(obj.in_flight, 0) || safeNumber(obj.inflight, 0);
  if (inFlight > 0) s.in_flight = inFlight;

  const conc = safeNumber(obj.concurrency, 0) || safeNumber(obj.workers, 0);
  if (conc > 0) s.concurrency = conc;

  const lastRun = normalizeUnixSeconds(obj.last_run_ts) ?? normalizeUnixSeconds(obj.last_run);
  if (lastRun) s.last_run_ts = lastRun;

  const lastSuccess = normalizeUnixSeconds(obj.last_success_ts) ?? normalizeUnixSeconds(obj.last_success);
  if (lastSuccess) s.last_success_ts = lastSuccess;

  const lastErrTs = normalizeUnixSeconds(obj.last_error_ts) ?? normalizeUnixSeconds(obj.last_error_time);
  if (lastErrTs) s.last_error_ts = lastErrTs;

  const lastErr = safeString(obj.last_error, safeString(obj.error, ""));
  if (lastErr) s.last_error = lastErr;

  const env = safeString(obj.env_profile, "");
  if (env) s.env_profile = env;

  const mode = safeString(obj.run_mode, "");
  if (mode) s.run_mode = mode;

  if (isRecord(obj.meta)) s.meta = obj.meta as Record<string, unknown>;

  return s;
}

function parseRecord(raw: unknown): WebLearningRecord | null {
  if (!isRecord(raw)) return null;

  const url = safeString(raw.url, safeString(raw.uri, ""));
  if (!url) return null;

  const ts =
    normalizeUnixSeconds(raw.ts) ??
    normalizeUnixSeconds(raw.completed_ts) ??
    normalizeUnixSeconds(raw.time) ??
    normalizeUnixSeconds(raw.started_ts) ??
    Math.floor(Date.now() / 1000);

  const id =
    safeString(raw.id, "") ||
    safeString(raw.record_id, "") ||
    safeString(raw.rid, "") ||
    `${ts}_${url}`;

  const status = safeString(raw.status, safeString(raw.state, "unknown"));

  const r: WebLearningRecord = { id, ts, url, status };

  const http = safeNumber(raw.http_status, 0) || safeNumber(raw.status_code, 0);
  if (http > 0) r.http_status = http;

  const method = safeString(raw.method, "");
  if (method) r.method = method;

  const ct = safeString(raw.content_type, safeString(raw.mime, ""));
  if (ct) r.content_type = ct;

  const bytes = safeNumber(raw.bytes, 0) || safeNumber(raw.size, 0);
  if (bytes > 0) r.bytes = bytes;

  const dur = safeNumber(raw.duration_ms, 0) || safeNumber(raw.latency_ms, 0);
  if (dur > 0) r.duration_ms = dur;

  const title = safeString(raw.title, "");
  if (title) r.title = title;

  const summary = safeString(raw.summary, safeString(raw.excerpt, ""));
  if (summary) r.summary = summary;

  const domain = safeString(raw.domain, safeString(raw.host, ""));
  if (domain) r.domain = domain;

  const source = safeString(raw.source, "");
  if (source) r.source = source;

  const approvalId = safeString(raw.approval_id, "");
  if (approvalId) r.approval_id = approvalId;

  const quarantineId = safeString(raw.quarantine_id, "");
  if (quarantineId) r.quarantine_id = quarantineId;

  const err = safeString(raw.error, safeString(raw.err, ""));
  if (err) r.error = err;

  if (isRecord(raw.meta)) r.meta = raw.meta as Record<string, unknown>;

  return r;
}

function parseEvent(raw: unknown): WebLearningEvent | null {
  if (!isRecord(raw)) return null;

  const ts = normalizeUnixSeconds(raw.ts) ?? normalizeUnixSeconds(raw.time);
  if (!ts) return null;

  const id =
    safeString(raw.id, "") ||
    safeString(raw.event_id, "") ||
    safeString(raw.eid, "") ||
    safeString(raw.correlation_id, "") ||
    `wev_${ts}`;

  const e: WebLearningEvent = { id, ts };

  const kind = safeString(raw.kind, safeString(raw.type, ""));
  if (kind) e.kind = kind;

  const url = safeString(raw.url, safeString(raw.uri, ""));
  if (url) e.url = url;

  const recordId = safeString(raw.record_id, safeString(raw.rid, ""));
  if (recordId) e.record_id = recordId;

  const status = safeString(raw.status, "");
  if (status) e.status = status;

  const message = safeString(raw.message, safeString(raw.detail, ""));
  if (message) e.message = message;

  const http = safeNumber(raw.http_status, 0) || safeNumber(raw.status_code, 0);
  if (http > 0) e.http_status = http;

  const bytes = safeNumber(raw.bytes, 0) || safeNumber(raw.size, 0);
  if (bytes > 0) e.bytes = bytes;

  const dur = safeNumber(raw.duration_ms, 0) || safeNumber(raw.latency_ms, 0);
  if (dur > 0) e.duration_ms = dur;

  const approvalId = safeString(raw.approval_id, "");
  if (approvalId) e.approval_id = approvalId;

  const quarantineId = safeString(raw.quarantine_id, "");
  if (quarantineId) e.quarantine_id = quarantineId;

  const actor = safeString(raw.actor, safeString(raw.user, ""));
  if (actor) e.actor = actor;

  const domain = safeString(raw.domain, safeString(raw.host, ""));
  if (domain) e.domain = domain;

  const source = safeString(raw.source, "");
  if (source) e.source = source;

  const correlationId = safeString(raw.correlation_id, safeString(raw.correlationId, ""));
  if (correlationId) e.correlation_id = correlationId;

  const opId = safeString(raw.operation_id, safeString(raw.op_id, ""));
  if (opId) e.operation_id = opId;

  if (isRecord(raw.meta)) e.meta = raw.meta as Record<string, unknown>;

  return e;
}

function parseQuarantineItem(raw: unknown): WebLearningQuarantineItem | null {
  if (!isRecord(raw)) return null;

  const url = safeString(raw.url, safeString(raw.uri, ""));
  if (!url) return null;

  const ts =
    normalizeUnixSeconds(raw.ts) ??
    normalizeUnixSeconds(raw.time) ??
    normalizeUnixSeconds(raw.created_ts) ??
    Math.floor(Date.now() / 1000);

  const id =
    safeString(raw.id, "") ||
    safeString(raw.quarantine_id, "") ||
    safeString(raw.qid, "") ||
    `${ts}_${url}`;

  const q: WebLearningQuarantineItem = { id, ts, url };

  const reason = safeString(raw.reason, safeString(raw.rationale, ""));
  if (reason) q.reason = reason;

  const status = safeString(raw.status, "");
  if (status) q.status = status;

  const recordId = safeString(raw.record_id, "");
  if (recordId) q.record_id = recordId;

  const approvalId = safeString(raw.approval_id, "");
  if (approvalId) q.approval_id = approvalId;

  const evidence = safeString(raw.evidence, safeString(raw.detail, ""));
  if (evidence) q.evidence = evidence;

  const domain = safeString(raw.domain, safeString(raw.host, ""));
  if (domain) q.domain = domain;

  const source = safeString(raw.source, "");
  if (source) q.source = source;

  if (isRecord(raw.meta)) q.meta = raw.meta as Record<string, unknown>;

  return q;
}

function parseListResponse<T>(raw: unknown, parseItem: (x: unknown) => T | null): CursorListResponse<T> {
  // Accept JSONL string
  if (typeof raw === "string") {
    const lines = raw.split(/\r?\n/).map((s) => s.trim()).filter((s) => s.length > 0);
    const items: T[] = [];
    for (const line of lines) {
      try {
        const obj = JSON.parse(line) as unknown;
        const it = parseItem(obj);
        if (it) items.push(it);
      } catch {
        // ignore
      }
    }
    return { items };
  }

  if (Array.isArray(raw)) {
    return { items: raw.map(parseItem).filter((x): x is T => x !== null) };
  }

  if (!isRecord(raw)) return { items: [] };

  const arr =
    (Array.isArray(raw.items) ? raw.items :
    Array.isArray(raw.records) ? raw.records :
    Array.isArray(raw.events) ? raw.events :
    Array.isArray(raw.entries) ? raw.entries :
    Array.isArray(raw.log) ? raw.log :
    Array.isArray(raw.quarantine) ? raw.quarantine :
    []) as unknown[];

  const items = arr.map(parseItem).filter((x): x is T => x !== null);

  const nextCursor =
    safeString(raw.next_cursor, "") ||
    safeString(raw.nextCursor, "") ||
    safeString(raw.cursor, "") ||
    undefined;

  const total = safeNumber(raw.total, 0) || safeNumber(raw.count, 0) || 0;

  return {
    items,
    next_cursor: nextCursor || undefined,
    total: total > 0 ? total : undefined,
  };
}

function parsePolicy(raw: unknown): WebLearningPolicy | null {
  if (!isRecord(raw)) return null;

  const obj = isRecord(raw.policy) ? (raw.policy as Record<string, unknown>) : raw;

  const p: WebLearningPolicy = {};

  const ts = normalizeUnixSeconds(obj.ts);
  if (ts) p.ts = ts;

  if (typeof obj.enabled === "boolean") p.enabled = obj.enabled;
  if (typeof obj.approvals_required === "boolean") p.approvals_required = obj.approvals_required;

  const allowDomains = Array.isArray(obj.allow_domains) ? obj.allow_domains : Array.isArray(obj.allowDomains) ? obj.allowDomains : null;
  if (allowDomains) p.allow_domains = allowDomains.map((x: unknown) => safeString(x, "")).filter((s: string) => s.length > 0);

  const denyDomains = Array.isArray(obj.deny_domains) ? obj.deny_domains : Array.isArray(obj.denyDomains) ? obj.denyDomains : null;
  if (denyDomains) p.deny_domains = denyDomains.map((x: unknown) => safeString(x, "")).filter((s: string) => s.length > 0);

  const allowPatterns = Array.isArray(obj.allow_patterns) ? obj.allow_patterns : Array.isArray(obj.allowPatterns) ? obj.allowPatterns : null;
  if (allowPatterns) p.allow_patterns = allowPatterns.map((x: unknown) => safeString(x, "")).filter((s: string) => s.length > 0);

  const denyPatterns = Array.isArray(obj.deny_patterns) ? obj.deny_patterns : Array.isArray(obj.denyPatterns) ? obj.denyPatterns : null;
  if (denyPatterns) p.deny_patterns = denyPatterns.map((x: unknown) => safeString(x, "")).filter((s: string) => s.length > 0);

  if (isRecord(obj.limits)) p.limits = obj.limits as Record<string, unknown>;

  const summary = safeString(obj.summary, safeString(obj.description, ""));
  if (summary) p.summary = summary;

  if (isRecord(obj.meta)) p.meta = obj.meta as Record<string, unknown>;

  return p;
}

/* -------------------------------------------------------------------------------------------------
 * endpoints
 * ------------------------------------------------------------------------------------------------- */

export type WebLearningEndpoints = {
  status: () => string[];
  policy: () => string[];

  records: (q?: WebLearningListParams) => string[];
  events: (q?: WebLearningListParams) => string[];
  quarantine: (q?: WebLearningListParams) => string[];

  /**
   * Export routes. Backends may implement:
   *  - POST /web_learning/export (body: request)
   *  - GET  /web_learning/records/export?format=csv...
   */
  export: (kind: WebLearningExportRequest["kind"], format: WebLearningExportFormat, q?: WebLearningListParams) => string[];

  // Mutations (approval/policy gated server-side)
  requestLearn: () => string[];
  setEnabled: () => string[];
  decideQuarantine: (id?: string) => string[];
};

export function defaultWebLearningEndpoints(): WebLearningEndpoints {
  return {
    status: () => [
      "/web_learning/status",
      "/web-learning/status",
      "/system/web_learning/status",
      "/system/web-learning/status",
      "/web_learning",
      "/web-learning",
    ],

    policy: () => [
      "/web_learning/policy",
      "/web-learning/policy",
      "/web_learning/config",
      "/web-learning/config",
      "/system/web_learning/policy",
      "/system/web-learning/policy",
    ],

    records: (q) => {
      const qs = encodeQuery({
        start_ts: q?.start_ts,
        end_ts: q?.end_ts,
        limit: q?.limit,
        cursor: q?.cursor,
        status: q?.status,
        domain: q?.domain,
        search: q?.search,
      });

      return [
        `/web_learning/records${qs}`,
        `/web-learning/records${qs}`,
        `/web_learning/recent${qs}`,
        `/web-learning/recent${qs}`,
        `/web_learning/log/records${qs}`,
      ];
    },

    events: (q) => {
      const qs = encodeQuery({
        start_ts: q?.start_ts,
        end_ts: q?.end_ts,
        limit: q?.limit,
        cursor: q?.cursor,
        status: q?.status,
        domain: q?.domain,
        search: q?.search,
      });

      return [
        `/web_learning/events${qs}`,
        `/web-learning/events${qs}`,
        `/web_learning/log${qs}`,
        `/web-learning/log${qs}`,
        `/web_learning/audit${qs}`,
      ];
    },

    quarantine: (q) => {
      const qs = encodeQuery({
        start_ts: q?.start_ts,
        end_ts: q?.end_ts,
        limit: q?.limit,
        cursor: q?.cursor,
        status: q?.status,
        domain: q?.domain,
        search: q?.search,
      });

      return [
        `/web_learning/quarantine${qs}`,
        `/web-learning/quarantine${qs}`,
        `/web_learning/quarantine/items${qs}`,
        `/web-learning/quarantine/items${qs}`,
      ];
    },

    export: (kind, format, q) => {
      const qs = encodeQuery({
        format,
        start_ts: q?.start_ts,
        end_ts: q?.end_ts,
        limit: q?.limit,
        cursor: q?.cursor,
        status: q?.status,
        domain: q?.domain,
        search: q?.search,
      });

      // Prefer POST /export (body) but allow GET routes too.
      return [
        `/web_learning/export`, // POST
        `/web-learning/export`, // POST
        `/web_learning/${kind}/export${qs}`, // GET
        `/web-learning/${kind}/export${qs}`, // GET
        `/web_learning/export/${kind}${qs}`, // GET
        `/web-learning/export/${kind}${qs}`, // GET
      ];
    },

    requestLearn: () => [
      "/web_learning/request",
      "/web-learning/request",
      "/web_learning/learn",
      "/web-learning/learn",
      "/web_learning/enqueue",
      "/web-learning/enqueue",
    ],

    setEnabled: () => [
      "/web_learning/enabled",
      "/web-learning/enabled",
      "/web_learning/toggle",
      "/web-learning/toggle",
      "/web_learning/config",
      "/web-learning/config",
    ],

    decideQuarantine: (id) => {
      if (id) {
        return [
          `/web_learning/quarantine/${encodeURIComponent(id)}/decide`,
          `/web-learning/quarantine/${encodeURIComponent(id)}/decide`,
          `/web_learning/quarantine/${encodeURIComponent(id)}`,
          `/web-learning/quarantine/${encodeURIComponent(id)}`,
        ];
      }
      return [
        "/web_learning/quarantine/decide",
        "/web-learning/quarantine/decide",
        "/web_learning/quarantine/resolve",
        "/web-learning/quarantine/resolve",
      ];
    },
  };
}

export type RetryPolicy = {
  retries?: number; // default 1
  retryMethods?: string[]; // default ["GET", "HEAD"]
  retryStatusCodes?: number[]; // default [429, 502, 503, 504]
};

export type WebLearningClientOptions = {
  endpoints?: WebLearningEndpoints;
  defaultTimeoutMs?: number;

  mutationsEnabled?: boolean;

  bearerTokenProvider?: () => string | null;
  headersExtra?: Record<string, string>;

  retry?: RetryPolicy;
};

type TimeoutFetchInit = RequestInit & {
  timeoutMs?: number;
  bearerToken?: string | null;
  headersExtra?: Record<string, string>;
};

export class WebLearningClient {
  readonly baseUrl: string;
  readonly endpoints: WebLearningEndpoints;
  readonly defaultTimeoutMs: number;
  readonly mutationsEnabled: boolean;

  readonly retry: Required<RetryPolicy>;

  private readonly bearerTokenProvider?: () => string | null;
  private readonly headersExtra?: Record<string, string>;

  constructor(baseUrl: string, opts?: WebLearningClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("WebLearningClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultWebLearningEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
    this.mutationsEnabled = Boolean(opts?.mutationsEnabled ?? false);

    this.bearerTokenProvider = opts?.bearerTokenProvider;
    this.headersExtra = opts?.headersExtra;

    const r = opts?.retry ?? {};
    this.retry = {
      retries: typeof r.retries === "number" ? r.retries : 1,
      retryMethods: Array.isArray(r.retryMethods) && r.retryMethods.length ? r.retryMethods : ["GET", "HEAD"],
      retryStatusCodes: Array.isArray(r.retryStatusCodes) && r.retryStatusCodes.length ? r.retryStatusCodes : [429, 502, 503, 504],
    };
  }

  private url(path: string): string {
    const p = path.startsWith("/") ? path : `/${path}`;
    return `${this.baseUrl}${p}`;
  }

  private init(opts?: { signal?: AbortSignal; timeoutMs?: number }): TimeoutFetchInit {
    return {
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
      bearerToken: this.bearerTokenProvider?.() ?? null,
      headersExtra: this.headersExtra,
    };
  }

  private async fetchWithTimeout(url: string, init?: TimeoutFetchInit): Promise<Response> {
    const timeoutMs = init?.timeoutMs ?? this.defaultTimeoutMs;
    const { signal: externalSignal, bearerToken, headersExtra, ...fetchInit } = init ?? {};

    const controller = new AbortController();
    let timedOut = false;

    let timeoutId: number | null = null;
    if (timeoutMs > 0) {
      timeoutId = window.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);
    }

    const onExternalAbort = () => controller.abort();
    if (externalSignal) {
      if (externalSignal.aborted) onExternalAbort();
      else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }

    try {
      const headers = new Headers(fetchInit.headers ?? undefined);
      if (!headers.has("Accept")) headers.set("Accept", "application/json");

      const method = safeString(fetchInit.method, "GET").toUpperCase();
      const hasBody = "body" in fetchInit && fetchInit.body !== undefined && fetchInit.body !== null;
      if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

      if (bearerToken) headers.set("Authorization", `Bearer ${bearerToken}`);
      if (headersExtra) for (const [k, v] of Object.entries(headersExtra)) headers.set(k, v);

      return await fetch(url, { ...fetchInit, headers, signal: controller.signal });
    } catch (err) {
      if (timedOut) {
        throw new WebLearningApiError(`Request timed out after ${timeoutMs}ms`, { url, timedOut: true, cause: err });
      }
      throw err;
    } finally {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      if (externalSignal && !externalSignal.aborted) externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }

  private async fetchJson(url: string, init?: TimeoutFetchInit): Promise<{ res: Response; json: unknown }> {
    const method = safeString(init?.method, "GET").toUpperCase();
    const canRetry = this.retry.retryMethods.map((m) => m.toUpperCase()).includes(method);

    let lastErr: unknown = null;

    for (let attempt = 0; attempt <= this.retry.retries; attempt++) {
      try {
        const res = await this.fetchWithTimeout(url, init);

        if (!res.ok) {
          const snippet = await readTextSnippet(res);
          const reqId = headerRequestId(res.headers);

          const err = new WebLearningApiError(`HTTP ${res.status} for web-learning request`, {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
          });

          const shouldRetry = this.retry.retryStatusCodes.includes(res.status);
          if (attempt < this.retry.retries && canRetry && shouldRetry) {
            lastErr = err;
            await sleep(backoffMs(attempt), init?.signal ?? undefined);
            continue;
          }

          throw err;
        }

        try {
          const json = await res.json();
          return { res, json };
        } catch (parseErr) {
          const snippet = await readTextSnippet(res);
          const reqId = headerRequestId(res.headers);
          throw new WebLearningApiError("Failed to parse JSON response", {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
            cause: parseErr,
          });
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") throw err;
        if (err instanceof WebLearningApiError && err.timedOut) throw err;

        lastErr = err;
        if (attempt < this.retry.retries && canRetry) {
          await sleep(backoffMs(attempt), init?.signal ?? undefined);
          continue;
        }
        throw err;
      }
    }

    throw lastErr instanceof Error ? lastErr : new Error("Web-learning request failed");
  }

  private async fetchFirstOkJson(
    candidates: string[],
    init: TimeoutFetchInit,
  ): Promise<{ url: string; res: Response; json: unknown }> {
    let lastErr: unknown = null;

    for (const path of candidates) {
      const url = this.url(path);
      try {
        const { res, json } = await this.fetchJson(url, init);
        return { url, res, json };
      } catch (err) {
        lastErr = err;
        if (err instanceof WebLearningApiError && (err.status === 404 || err.status === 405)) continue;
        throw err;
      }
    }

    if (lastErr instanceof Error) throw lastErr;
    throw new Error("No web-learning endpoints responded successfully");
  }

  async getStatus(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<WebLearningStatus | null> {
    const { json } = await this.fetchFirstOkJson(this.endpoints.status(), this.init(opts));
    return parseStatus(json);
  }

  async getPolicy(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<WebLearningPolicy | null> {
    const { json } = await this.fetchFirstOkJson(this.endpoints.policy(), this.init(opts));
    return parsePolicy(json);
  }

  async listRecords(
    params?: WebLearningListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<CursorListResponse<WebLearningRecord>> {
    const limit = typeof params?.limit === "number" ? clamp(Math.floor(params.limit), 1, 10_000) : 200;
    const candidates = this.endpoints.records({ ...params, limit });

    const { json } = await this.fetchFirstOkJson(candidates, this.init(opts));
    const parsed = parseListResponse(json, parseRecord);

    // Newest first by default for operator relevance.
    parsed.items.sort((a, b) => b.ts - a.ts);
    return parsed;
  }

  async listEvents(
    params?: WebLearningListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<CursorListResponse<WebLearningEvent>> {
    const limit = typeof params?.limit === "number" ? clamp(Math.floor(params.limit), 1, 10_000) : 200;
    const candidates = this.endpoints.events({ ...params, limit });

    const { json } = await this.fetchFirstOkJson(candidates, this.init(opts));
    const parsed = parseListResponse(json, parseEvent);

    parsed.items.sort((a, b) => b.ts - a.ts);
    return parsed;
  }

  async listQuarantine(
    params?: WebLearningListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<CursorListResponse<WebLearningQuarantineItem>> {
    const limit = typeof params?.limit === "number" ? clamp(Math.floor(params.limit), 1, 10_000) : 200;
    const candidates = this.endpoints.quarantine({ ...params, limit });

    const { json } = await this.fetchFirstOkJson(candidates, this.init(opts));
    const parsed = parseListResponse(json, parseQuarantineItem);

    parsed.items.sort((a, b) => b.ts - a.ts);
    return parsed;
  }

  async requestLearn(
    req: WebLearningRequestLearn,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<WebLearningRequestLearnResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("WebLearningClient.requestLearn is disabled (mutationsEnabled=false).");
    }

    const url = (req?.url || "").trim();
    if (!url) throw new Error("requestLearn requires req.url");

    const candidates = this.endpoints.requestLearn();

    // POST everywhere
    const init: TimeoutFetchInit = {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(req),
    };

    const { json } = await this.fetchFirstOkJson(candidates, init);

    if (!isRecord(json)) return { ok: true };

    return {
      ok: safeBool((json as Record<string, unknown>).ok, true),
      request_id: safeString((json as Record<string, unknown>).request_id, "") || undefined,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      record_id: safeString((json as Record<string, unknown>).record_id, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      meta: isRecord((json as Record<string, unknown>).meta) ? ((json as Record<string, unknown>).meta as Record<string, unknown>) : undefined,
    };
  }

  async setEnabled(
    req: WebLearningSetEnabledRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<WebLearningSetEnabledResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("WebLearningClient.setEnabled is disabled (mutationsEnabled=false).");
    }

    const candidates = this.endpoints.setEnabled();
    const init: TimeoutFetchInit = {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(req),
    };

    const { json } = await this.fetchFirstOkJson(candidates, init);

    if (!isRecord(json)) return { ok: true, applied: false };

    return {
      ok: safeBool((json as Record<string, unknown>).ok, true),
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      applied: safeBool((json as Record<string, unknown>).applied, false),
      enabled: typeof (json as Record<string, unknown>).enabled === "boolean" ? ((json as Record<string, unknown>).enabled as boolean) : undefined,
      ts: normalizeUnixSeconds((json as Record<string, unknown>).ts),
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      meta: isRecord((json as Record<string, unknown>).meta) ? ((json as Record<string, unknown>).meta as Record<string, unknown>) : undefined,
    };
  }

  async decideQuarantine(
    req: WebLearningQuarantineDecisionRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<WebLearningQuarantineDecisionResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("WebLearningClient.decideQuarantine is disabled (mutationsEnabled=false).");
    }

    const id = (req?.id || "").trim();
    if (!id) throw new Error("decideQuarantine requires req.id");

    const candidates = this.endpoints.decideQuarantine(id);

    const init: TimeoutFetchInit = {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(req),
    };

    const { json } = await this.fetchFirstOkJson(candidates, init);

    if (!isRecord(json)) return { ok: true };

    return {
      ok: safeBool((json as Record<string, unknown>).ok, true),
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      applied: safeBool((json as Record<string, unknown>).applied, false),
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      meta: isRecord((json as Record<string, unknown>).meta) ? ((json as Record<string, unknown>).meta as Record<string, unknown>) : undefined,
    };
  }

  /**
   * Export helper:
   *  - Prefers POST /export with request body when supported.
   *  - Falls back to GET /<kind>/export?format=...
   *
   * Returns a Blob and inferred filename.
   */
  async export(
    req: WebLearningExportRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number; onProgress?: (p: WebLearningExportProgress) => void },
  ): Promise<WebLearningExportResult> {
    const candidates = this.endpoints.export(req.kind, req.format, {
      start_ts: req.start_ts,
      end_ts: req.end_ts,
      status: req.status,
      domain: req.domain,
      search: req.search,
      limit: req.limit,
      cursor: req.cursor,
    });

    // Try POST first (if candidate ends with /export)
    // then try GET fallbacks.
    let lastErr: unknown = null;

    for (const path of candidates) {
      const url = this.url(path);

      const isPost = path.endsWith("/export");
      const init: TimeoutFetchInit = {
        ...this.init(opts),
        method: isPost ? "POST" : "GET",
        body: isPost ? JSON.stringify(req) : undefined,
      };

      try {
        const res = await this.fetchWithTimeout(url, init);

        if (!res.ok) {
          const snippet = await readTextSnippet(res);
          const reqId = headerRequestId(res.headers);

          const err = new WebLearningApiError(`HTTP ${res.status} for web-learning export`, {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
          });

          if (err.status === 404 || err.status === 405) {
            lastErr = err;
            continue;
          }

          throw err;
        }

        const contentType = res.headers.get("content-type") || "application/octet-stream";
        const cd = res.headers.get("content-disposition");
        const suggested = parseContentDispositionFilename(cd);
        const fallback = guessFilename(req.kind, req.format);
        const filename = suggested || fallback;

        // Stream with progress when possible.
        if (opts?.onProgress && res.body) {
          const totalStr = res.headers.get("content-length");
          const total = totalStr ? Number(totalStr) : undefined;
          let loaded = 0;

          const reader = res.body.getReader();
          const chunks: Uint8Array[] = [];

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            if (value) {
              chunks.push(value);
              loaded += value.byteLength;
              opts.onProgress({ loadedBytes: loaded, totalBytes: Number.isFinite(total ?? NaN) ? total : undefined });
            }
          }

          return { filename, contentType, blob: new Blob(chunks, { type: contentType }) };
        }

        const blob = await res.blob();
        return { filename, contentType, blob };
      } catch (err) {
        lastErr = err;
        if (err instanceof WebLearningApiError && (err.status === 404 || err.status === 405)) continue;
        throw err;
      }
    }

    if (lastErr instanceof Error) throw lastErr;
    throw new Error("No web-learning export endpoints responded successfully");
  }
}

/* -------------------------------------------------------------------------------------------------
 * UI helpers
 * ------------------------------------------------------------------------------------------------- */

export function toLocaleTime(tsSeconds?: number): string {
  if (!tsSeconds || !Number.isFinite(tsSeconds)) return "";
  const ms = tsSeconds > 10_000_000_000 ? tsSeconds : tsSeconds * 1000;
  return new Date(ms).toLocaleString();
}

export function formatBytes(n?: number): string {
  if (!n || !Number.isFinite(n) || n <= 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  const digits = v < 10 ? 2 : v < 100 ? 1 : 0;
  return `${v.toFixed(digits)} ${units[i]}`;
}

export function formatMs(ms?: number): string {
  if (!ms || !Number.isFinite(ms) || ms <= 0) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)}s`;
}
