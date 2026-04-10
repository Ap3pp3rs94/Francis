/**
 * Industrial Control module (UI).
 *
 * This module is the typed, defensive, framework-agnostic protocol/client layer
 * for Francis’s industrial subsystem (assets, processes, simulations, telemetry,
 * and governed interventions).
 *
 * Design contract
 * ---------------
 *  1) Framework-agnostic:
 *     - No React imports, no DOM manipulation, no UI state.
 *
 *  2) Defensive parsing:
 *     - Treat all server responses as untrusted.
 *     - Tolerate API evolution; accept aliases; degrade gracefully.
 *
 *  3) Observability-first:
 *     - Rich errors: status/url/bodySnippet/requestId.
 *     - Timeouts and optional retry policy.
 *     - Optional request/response hooks for tracing.
 *
 *  4) Safety-forward control:
 *     - Read-only operations are direct.
 *     - Mutations are supported, but can be used in an approval-aware pattern.
 *     - "Unsafe direct actuation" is gated behind an explicit opt-in.
 *
 * Why this exists
 * ---------------
 * Industrial control is safety-critical and evolves quickly. The UI must remain
 * stable while backend routes/fields change. This client is the seam:
 *   UI ↔ (this file) ↔ API
 *
 * Suggested backend route shape (override via endpoints if different)
 * ------------------------------------------------------------------
 * Assets:
 *   GET    /industrial/assets
 *   GET    /industrial/assets/{id}
 *   POST   /industrial/assets
 *   PATCH  /industrial/assets/{id}
 *   DELETE /industrial/assets/{id}
 *
 * Processes:
 *   GET    /industrial/processes
 *   GET    /industrial/processes/{id}
 *   POST   /industrial/processes
 *   PATCH  /industrial/processes/{id}
 *   DELETE /industrial/processes/{id}
 *
 * Simulations:
 *   GET    /industrial/simulations
 *   GET    /industrial/simulations/{id}
 *   POST   /industrial/simulations
 *   PATCH  /industrial/simulations/{id}
 *   DELETE /industrial/simulations/{id}
 *
 * Runs:
 *   GET    /industrial/runs
 *   GET    /industrial/runs/{id}
 *   POST   /industrial/runs/start
 *   POST   /industrial/runs/{id}/cancel
 *
 * Safety validation:
 *   GET    /industrial/safety/validations
 *   POST   /industrial/safety/validate
 *
 * Telemetry:
 *   GET    /industrial/telemetry
 *
 * Interventions (governed):
 *   POST   /industrial/interventions/request     (approval-aware: creates approval)
 *   POST   /industrial/interventions/execute     (OPTIONAL; gated by unsafeDirectActuation)
 */

/* -------------------------------------------------------------------------------------------------
 * Types — stable, forward-compatible, and intentionally "string-escape-hatch"
 * ------------------------------------------------------------------------------------------------- */

export type IndustrialStatus =
  | "active"
  | "inactive"
  | "degraded"
  | "maintenance"
  | "draft"
  | "error"
  | "unknown"
  | string;

export type IndustrialRisk = "low" | "medium" | "high" | "safety_critical" | string;

export type IndustrialEntityKind = "asset" | "process" | "simulation" | "run" | "validation" | "telemetry" | string;

export type Pagination = {
  limit?: number;
  offset?: number;
  cursor?: string;
};

export type DateRange = {
  start_ts?: number; // unix seconds preferred; ms tolerated (normalized where relevant)
  end_ts?: number;
};

export type CommonListFilters = Pagination &
  DateRange & {
    search?: string;
    status?: string;
    tags?: string[];
    risk?: string;
    include_archived?: boolean;
  };

export type ArtifactRef = {
  id: string;
  kind?: string;
  path?: string; // server-side path or logical ref
  url?: string; // if server exposes signed/public URL
  content_type?: string;
  size_bytes?: number;
  sha256?: string;
  meta?: Record<string, unknown>;
};

export type IndustrialAsset = {
  id: string;
  name: string;
  asset_type?: string; // e.g., "sensor", "pump", "reactor", "controller"
  status: IndustrialStatus;
  risk?: IndustrialRisk;

  location?: string;
  tags?: string[];

  created_ts?: number;
  updated_ts?: number;
  last_seen_ts?: number;

  // Forward-compatible attachments:
  model_ref?: string; // digital twin model id/ref
  connector_ref?: string; // hardware/software connector reference
  meta?: Record<string, unknown>;
};

export type IndustrialProcess = {
  id: string;
  name: string;
  status: IndustrialStatus;
  risk?: IndustrialRisk;

  description?: string;
  domain?: string; // optional domain affiliation
  tags?: string[];

  // High-level IO graph hints (not authoritative control logic):
  inputs?: string[];
  outputs?: string[];

  created_ts?: number;
  updated_ts?: number;

  meta?: Record<string, unknown>;
};

export type IndustrialSimulation = {
  id: string;
  name: string;
  status: IndustrialStatus;
  risk?: IndustrialRisk;

  description?: string;
  engine?: string; // e.g., "custom", "pybullet", "numpy", etc.
  scenario?: string;

  // "Default" params for new runs. Never treated as secrets.
  default_params?: Record<string, unknown>;

  // Optional binding to digital twin/process/asset.
  asset_id?: string;
  process_id?: string;
  digital_twin_id?: string;

  created_ts?: number;
  updated_ts?: number;

  meta?: Record<string, unknown>;
};

export type SimulationRunStatus = "queued" | "running" | "succeeded" | "failed" | "canceled" | "unknown" | string;

export type IndustrialSimulationRun = {
  id: string;
  simulation_id?: string;
  status: SimulationRunStatus;

  requested_ts?: number;
  started_ts?: number;
  completed_ts?: number;

  requested_by?: string;
  reason?: string;

  // Params used for the run (may differ from simulation.default_params).
  params?: Record<string, unknown>;

  // Metrics/summary, if provided by backend:
  metrics?: Record<string, number>;
  summary?: string;

  artifacts?: ArtifactRef[];

  meta?: Record<string, unknown>;
};

export type SafetyValidationStatus = "pass" | "fail" | "warn" | "unknown" | string;

export type SafetyViolation = {
  code?: string;
  message: string;
  severity?: "info" | "warning" | "error" | "critical" | string;
  evidence?: unknown;
  meta?: Record<string, unknown>;
};

export type SafetyValidation = {
  id: string;
  ts: number;

  target_kind?: IndustrialEntityKind;
  target_id?: string;

  status: SafetyValidationStatus;
  risk?: IndustrialRisk;

  summary?: string;
  violations?: SafetyViolation[];

  artifacts?: ArtifactRef[];
  meta?: Record<string, unknown>;
};

export type TelemetryPoint = {
  ts: number;
  source_id?: string; // asset_id / simulation_id / etc.
  fields: Record<string, number | string | boolean | null>;
  quality?: string;
  meta?: Record<string, unknown>;
};

export type TelemetryQuery = DateRange & {
  source_id?: string;
  metric_keys?: string[];
  limit?: number;
};

export type IndustrialActionMode = "request" | "execute" | string;

export type IndustrialInterventionRequest = {
  mode?: IndustrialActionMode; // default "request"
  target_kind: IndustrialEntityKind;
  target_id: string;

  action: string; // e.g., "start", "stop", "set_setpoint", "calibrate", "deploy_model"
  reason?: string; // justification (governance-friendly)
  dry_run?: boolean; // strongly recommended default true at UI level

  // Non-secret, structured parameters.
  params?: Record<string, unknown>;

  // Optional safety/governance metadata:
  risk?: IndustrialRisk;
  domain?: string;
  actor?: string;

  meta?: Record<string, unknown>;
};

export type IndustrialInterventionResponse = {
  ok: boolean;
  status?: string;

  // Approval-aware fields (preferred):
  request_id?: string;
  approval_id?: string;

  // Execution result fields (if backend supports direct execution):
  result_id?: string;
  message?: string;

  meta?: Record<string, unknown>;
};

/* -------------------------------------------------------------------------------------------------
 * Errors — explicit, structured, debuggable
 * ------------------------------------------------------------------------------------------------- */

export class IndustrialControlApiError extends Error {
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
    this.name = "IndustrialControlApiError";
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
 * Utilities — tiny, local, dependency-free
 * ------------------------------------------------------------------------------------------------- */

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeBoolean(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function safeStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.map((x) => (typeof x === "string" ? x : "")).filter(Boolean);
  return out.length ? out : undefined;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeTsToSeconds(ts: unknown): number | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  // Heuristic: seconds vs milliseconds
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : Math.floor(ts);
}

function encodePathSegment(id: string): string {
  return encodeURIComponent(id);
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function backoffMs(attempt: number, base = 250, cap = 5_000): number {
  // Exponential backoff with jitter; attempt starts at 0.
  const pow = 2 ** clamp(attempt, 0, 10);
  const raw = clamp(base * pow, base, cap);
  const jitter = Math.floor(Math.random() * clamp(raw * 0.2, 25, 500));
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

async function readTextSnippet(res: Response, maxChars = 2048): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

function headerRequestId(headers: Headers): string | undefined {
  const candidates = ["x-request-id", "x-correlation-id", "x-trace-id", "request-id"];
  for (const k of candidates) {
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
      for (const item of v) {
        if (item === undefined || item === null) continue;
        qs.append(k, String(item));
      }
      continue;
    }

    qs.set(k, String(v));
  }

  const s = qs.toString();
  return s ? `?${s}` : "";
}

/* -------------------------------------------------------------------------------------------------
 * Parsing — tolerate drift, support aliases, normalize
 * ------------------------------------------------------------------------------------------------- */

function parseArtifact(raw: unknown): ArtifactRef | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const a: ArtifactRef = { id };

  const kind = safeString(raw.kind, "");
  if (kind) a.kind = kind;

  const path = safeString(raw.path, "");
  if (path) a.path = path;

  const url = safeString(raw.url, "");
  if (url) a.url = url;

  const ct = safeString(raw.content_type, safeString(raw.contentType, ""));
  if (ct) a.content_type = ct;

  const size = safeNumber(raw.size_bytes, safeNumber(raw.sizeBytes, 0));
  if (size > 0) a.size_bytes = size;

  const sha = safeString(raw.sha256, "");
  if (sha) a.sha256 = sha;

  if (isRecord(raw.meta)) a.meta = raw.meta;

  return a;
}

function parseAsset(raw: unknown): IndustrialAsset | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, safeString(raw.asset_id, ""));
  if (!id) return null;

  const name = safeString(raw.name, id);

  const status = safeString(raw.status, "unknown");
  const asset_type = safeString(raw.asset_type, safeString(raw.type, ""));
  const risk = safeString(raw.risk, "");

  const a: IndustrialAsset = {
    id,
    name,
    status,
  };

  if (asset_type) a.asset_type = asset_type;
  if (risk) a.risk = risk;

  const loc = safeString(raw.location, "");
  if (loc) a.location = loc;

  const tags = safeStringArray(raw.tags);
  if (tags) a.tags = tags;

  const created = normalizeTsToSeconds(raw.created_ts ?? raw.createdTs);
  if (created) a.created_ts = created;

  const updated = normalizeTsToSeconds(raw.updated_ts ?? raw.updatedTs);
  if (updated) a.updated_ts = updated;

  const lastSeen = normalizeTsToSeconds(raw.last_seen_ts ?? raw.lastSeenTs);
  if (lastSeen) a.last_seen_ts = lastSeen;

  const modelRef = safeString(raw.model_ref, safeString(raw.digital_twin_id, ""));
  if (modelRef) a.model_ref = modelRef;

  const connRef = safeString(raw.connector_ref, "");
  if (connRef) a.connector_ref = connRef;

  if (isRecord(raw.meta)) a.meta = raw.meta;

  return a;
}

function parseProcess(raw: unknown): IndustrialProcess | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, safeString(raw.process_id, ""));
  if (!id) return null;

  const name = safeString(raw.name, id);
  const status = safeString(raw.status, "unknown");
  const risk = safeString(raw.risk, "");

  const p: IndustrialProcess = {
    id,
    name,
    status,
  };

  if (risk) p.risk = risk;

  const desc = safeString(raw.description, "");
  if (desc) p.description = desc;

  const domain = safeString(raw.domain, "");
  if (domain) p.domain = domain;

  const tags = safeStringArray(raw.tags);
  if (tags) p.tags = tags;

  const inputs = safeStringArray(raw.inputs);
  if (inputs) p.inputs = inputs;

  const outputs = safeStringArray(raw.outputs);
  if (outputs) p.outputs = outputs;

  const created = normalizeTsToSeconds(raw.created_ts ?? raw.createdTs);
  if (created) p.created_ts = created;

  const updated = normalizeTsToSeconds(raw.updated_ts ?? raw.updatedTs);
  if (updated) p.updated_ts = updated;

  if (isRecord(raw.meta)) p.meta = raw.meta;

  return p;
}

function parseSimulation(raw: unknown): IndustrialSimulation | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, safeString(raw.simulation_id, ""));
  if (!id) return null;

  const name = safeString(raw.name, id);
  const status = safeString(raw.status, "unknown");
  const risk = safeString(raw.risk, "");

  const s: IndustrialSimulation = {
    id,
    name,
    status,
  };

  if (risk) s.risk = risk;

  const desc = safeString(raw.description, "");
  if (desc) s.description = desc;

  const engine = safeString(raw.engine, "");
  if (engine) s.engine = engine;

  const scenario = safeString(raw.scenario, "");
  if (scenario) s.scenario = scenario;

  if (isRecord(raw.default_params)) s.default_params = raw.default_params;

  const assetId = safeString(raw.asset_id, "");
  if (assetId) s.asset_id = assetId;

  const processId = safeString(raw.process_id, "");
  if (processId) s.process_id = processId;

  const twinId = safeString(raw.digital_twin_id, "");
  if (twinId) s.digital_twin_id = twinId;

  const created = normalizeTsToSeconds(raw.created_ts ?? raw.createdTs);
  if (created) s.created_ts = created;

  const updated = normalizeTsToSeconds(raw.updated_ts ?? raw.updatedTs);
  if (updated) s.updated_ts = updated;

  if (isRecord(raw.meta)) s.meta = raw.meta;

  return s;
}

function parseRun(raw: unknown): IndustrialSimulationRun | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, safeString(raw.run_id, ""));
  if (!id) return null;

  const status = safeString(raw.status, "unknown");
  const r: IndustrialSimulationRun = { id, status };

  const simId = safeString(raw.simulation_id, "");
  if (simId) r.simulation_id = simId;

  const requested = normalizeTsToSeconds(raw.requested_ts ?? raw.requestedTs);
  if (requested) r.requested_ts = requested;

  const started = normalizeTsToSeconds(raw.started_ts ?? raw.startedTs);
  if (started) r.started_ts = started;

  const completed = normalizeTsToSeconds(raw.completed_ts ?? raw.completedTs);
  if (completed) r.completed_ts = completed;

  const by = safeString(raw.requested_by, safeString(raw.actor, ""));
  if (by) r.requested_by = by;

  const reason = safeString(raw.reason, "");
  if (reason) r.reason = reason;

  if (isRecord(raw.params)) r.params = raw.params;

  if (isRecord(raw.metrics)) {
    const m: Record<string, number> = {};
    for (const [k, v] of Object.entries(raw.metrics)) {
      if (typeof v === "number" && Number.isFinite(v)) m[k] = v;
    }
    if (Object.keys(m).length) r.metrics = m;
  }

  const summary = safeString(raw.summary, "");
  if (summary) r.summary = summary;

  const artifactsRaw = Array.isArray(raw.artifacts) ? raw.artifacts : Array.isArray(raw.outputs) ? raw.outputs : undefined;
  if (artifactsRaw) {
    const artifacts = artifactsRaw.map(parseArtifact).filter((x): x is ArtifactRef => x !== null);
    if (artifacts.length) r.artifacts = artifacts;
  }

  if (isRecord(raw.meta)) r.meta = raw.meta;

  return r;
}

function parseSafetyViolation(raw: unknown): SafetyViolation | null {
  if (!isRecord(raw)) return null;
  const msg = safeString(raw.message, "");
  if (!msg) return null;

  const v: SafetyViolation = { message: msg };

  const code = safeString(raw.code, "");
  if (code) v.code = code;

  const sev = safeString(raw.severity, "");
  if (sev) v.severity = sev;

  if ("evidence" in raw) v.evidence = raw.evidence;
  if (isRecord(raw.meta)) v.meta = raw.meta;

  return v;
}

function parseSafetyValidation(raw: unknown): SafetyValidation | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, safeString(raw.validation_id, ""));
  if (!id) return null;

  const ts = normalizeTsToSeconds(raw.ts) ?? 0;
  const status = safeString(raw.status, "unknown");

  const v: SafetyValidation = {
    id,
    ts,
    status,
  };

  const tk = safeString(raw.target_kind, "");
  if (tk) v.target_kind = tk;

  const tid = safeString(raw.target_id, "");
  if (tid) v.target_id = tid;

  const risk = safeString(raw.risk, "");
  if (risk) v.risk = risk;

  const summary = safeString(raw.summary, "");
  if (summary) v.summary = summary;

  const violationsRaw = Array.isArray(raw.violations) ? raw.violations : undefined;
  if (violationsRaw) {
    const violations = violationsRaw.map(parseSafetyViolation).filter((x): x is SafetyViolation => x !== null);
    if (violations.length) v.violations = violations;
  }

  const artifactsRaw = Array.isArray(raw.artifacts) ? raw.artifacts : undefined;
  if (artifactsRaw) {
    const artifacts = artifactsRaw.map(parseArtifact).filter((x): x is ArtifactRef => x !== null);
    if (artifacts.length) v.artifacts = artifacts;
  }

  if (isRecord(raw.meta)) v.meta = raw.meta;

  return v;
}

function parseTelemetryPoint(raw: unknown): TelemetryPoint | null {
  if (!isRecord(raw)) return null;

  const ts = normalizeTsToSeconds(raw.ts);
  if (!ts) return null;

  const fieldsRaw = isRecord(raw.fields) ? raw.fields : isRecord(raw.data) ? raw.data : null;
  if (!fieldsRaw) return null;

  const fields: Record<string, number | string | boolean | null> = {};
  for (const [k, v] of Object.entries(fieldsRaw)) {
    if (typeof v === "number" && Number.isFinite(v)) fields[k] = v;
    else if (typeof v === "string") fields[k] = v;
    else if (typeof v === "boolean") fields[k] = v;
    else if (v === null) fields[k] = null;
  }

  const p: TelemetryPoint = { ts, fields };

  const sourceId = safeString(raw.source_id, safeString(raw.asset_id, ""));
  if (sourceId) p.source_id = sourceId;

  const q = safeString(raw.quality, "");
  if (q) p.quality = q;

  if (isRecord(raw.meta)) p.meta = raw.meta;

  return p;
}

/* -------------------------------------------------------------------------------------------------
 * Endpoints — override-friendly mapping
 * ------------------------------------------------------------------------------------------------- */

export type IndustrialControlEndpoints = {
  // Health / discovery
  health: () => string;

  // Assets
  listAssets: () => string;
  getAsset: (id: string) => string;
  createAsset: () => string;
  updateAsset: (id: string) => string;
  deleteAsset: (id: string) => string;

  // Processes
  listProcesses: () => string;
  getProcess: (id: string) => string;
  createProcess: () => string;
  updateProcess: (id: string) => string;
  deleteProcess: (id: string) => string;

  // Simulations
  listSimulations: () => string;
  getSimulation: (id: string) => string;
  createSimulation: () => string;
  updateSimulation: (id: string) => string;
  deleteSimulation: (id: string) => string;

  // Runs
  listRuns: () => string;
  getRun: (id: string) => string;
  startRun: () => string;
  cancelRun: (id: string) => string;

  // Safety
  listSafetyValidations: () => string;
  validateSafety: () => string;

  // Telemetry
  telemetry: () => string;

  // Interventions (governed)
  requestIntervention: () => string;
  executeIntervention: () => string; // optional server capability
};

export function defaultIndustrialControlEndpoints(): IndustrialControlEndpoints {
  return {
    health: () => "/industrial/health",

    listAssets: () => "/industrial/assets",
    getAsset: (id) => `/industrial/assets/${encodePathSegment(id)}`,
    createAsset: () => "/industrial/assets",
    updateAsset: (id) => `/industrial/assets/${encodePathSegment(id)}`,
    deleteAsset: (id) => `/industrial/assets/${encodePathSegment(id)}`,

    listProcesses: () => "/industrial/processes",
    getProcess: (id) => `/industrial/processes/${encodePathSegment(id)}`,
    createProcess: () => "/industrial/processes",
    updateProcess: (id) => `/industrial/processes/${encodePathSegment(id)}`,
    deleteProcess: (id) => `/industrial/processes/${encodePathSegment(id)}`,

    listSimulations: () => "/industrial/simulations",
    getSimulation: (id) => `/industrial/simulations/${encodePathSegment(id)}`,
    createSimulation: () => "/industrial/simulations",
    updateSimulation: (id) => `/industrial/simulations/${encodePathSegment(id)}`,
    deleteSimulation: (id) => `/industrial/simulations/${encodePathSegment(id)}`,

    listRuns: () => "/industrial/runs",
    getRun: (id) => `/industrial/runs/${encodePathSegment(id)}`,
    startRun: () => "/industrial/runs/start",
    cancelRun: (id) => `/industrial/runs/${encodePathSegment(id)}/cancel`,

    listSafetyValidations: () => "/industrial/safety/validations",
    validateSafety: () => "/industrial/safety/validate",

    telemetry: () => "/industrial/telemetry",

    requestIntervention: () => "/industrial/interventions/request",
    executeIntervention: () => "/industrial/interventions/execute",
  };
}

/* -------------------------------------------------------------------------------------------------
 * Client — fetch, retry, timeout, and methods
 * ------------------------------------------------------------------------------------------------- */

export type IndustrialControlClientHooks = {
  onRequest?: (info: {
    url: string;
    method: string;
    attempt: number;
    timeoutMs: number;
    tags?: string[];
  }) => void;

  onResponse?: (info: {
    url: string;
    method: string;
    status: number;
    requestId?: string;
    elapsedMs: number;
    attempt: number;
  }) => void;
};

export type IndustrialControlRetryPolicy = {
  retries?: number; // default 0
  // Only idempotent methods are retried by default.
  retryMethods?: string[]; // default: ["GET", "HEAD"]
  retryStatusCodes?: number[]; // default: [429, 502, 503, 504]
};

export type IndustrialControlClientOptions = {
  endpoints?: IndustrialControlEndpoints;
  defaultTimeoutMs?: number; // default 20s
  hooks?: IndustrialControlClientHooks;
  retry?: IndustrialControlRetryPolicy;

  /**
   * Safety valve:
   * If true, allows calling executeIntervention(). This should only be enabled
   * in trusted operator environments, and still relies on backend enforcement.
   *
   * Default: false (request-only pattern).
   */
  unsafeDirectActuation?: boolean;
};

type TimeoutMergedFetchInit = RequestInit & { timeoutMs?: number };

export class IndustrialControlClient {
  readonly baseUrl: string;
  readonly endpoints: IndustrialControlEndpoints;
  readonly defaultTimeoutMs: number;
  readonly hooks?: IndustrialControlClientHooks;
  readonly retry: Required<IndustrialControlRetryPolicy>;
  readonly unsafeDirectActuation: boolean;

  constructor(baseUrl: string, opts?: IndustrialControlClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("IndustrialControlClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultIndustrialControlEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;

    const retry = opts?.retry ?? {};
    this.retry = {
      retries: typeof retry.retries === "number" ? retry.retries : 0,
      retryMethods: Array.isArray(retry.retryMethods) && retry.retryMethods.length ? retry.retryMethods : ["GET", "HEAD"],
      retryStatusCodes:
        Array.isArray(retry.retryStatusCodes) && retry.retryStatusCodes.length ? retry.retryStatusCodes : [429, 502, 503, 504],
    };

    this.hooks = opts?.hooks;
    this.unsafeDirectActuation = Boolean(opts?.unsafeDirectActuation);
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

    const start = performance.now();

    try {
      const headers = new Headers(fetchInit.headers ?? undefined);
      if (!headers.has("Accept")) headers.set("Accept", "application/json");

      // Only set Content-Type automatically when caller is likely sending JSON.
      const method = safeString(fetchInit.method, "GET").toUpperCase();
      const hasBody = "body" in fetchInit && fetchInit.body !== undefined && fetchInit.body !== null;
      if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

      const res = await fetch(url, {
        ...fetchInit,
        headers,
        signal: controller.signal,
      });

      const elapsedMs = Math.max(0, Math.round(performance.now() - start));
      return { res, elapsedMs };
    } catch (err) {
      const elapsedMs = Math.max(0, Math.round(performance.now() - start));

      // Timeout is modeled as AbortError in fetch().
      if (timedOut) {
        throw new IndustrialControlApiError(`Request timed out after ${timeoutMs}ms`, {
          url,
          timedOut: true,
          cause: err,
        });
      }

      // If the caller aborted, preserve AbortError semantics for UI-level cancellation logic.
      throw err;
    } finally {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      if (externalSignal && !externalSignal.aborted) externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }

  private async fetchJson(url: string, init?: TimeoutMergedFetchInit & { tags?: string[] }): Promise<unknown> {
    const method = safeString(init?.method, "GET").toUpperCase();
    const retries = this.retry.retries;
    const canRetryMethod = this.retry.retryMethods.map((m) => m.toUpperCase()).includes(method);

    let lastErr: unknown;

    for (let attempt = 0; attempt <= retries; attempt++) {
      const timeoutMs = init?.timeoutMs ?? this.defaultTimeoutMs;
      this.hooks?.onRequest?.({ url, method, attempt, timeoutMs, tags: init?.tags });

      try {
        const { res, elapsedMs } = await this.fetchWithTimeout(url, init);

        const reqId = headerRequestId(res.headers);
        this.hooks?.onResponse?.({ url, method, status: res.status, requestId: reqId, elapsedMs, attempt });

        if (!res.ok) {
          const snippet = await readTextSnippet(res);
          const apiErr = new IndustrialControlApiError(`HTTP ${res.status} for industrial request`, {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
          });

          const shouldRetryStatus = this.retry.retryStatusCodes.includes(res.status);
          if (attempt < retries && canRetryMethod && shouldRetryStatus) {
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
          throw new IndustrialControlApiError("Failed to parse JSON response", {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
            cause: err,
          });
        }
      } catch (err) {
        // Do not retry AbortError by default (cancellation / timeout).
        if (err instanceof DOMException && err.name === "AbortError") throw err;
        if (err instanceof IndustrialControlApiError && err.timedOut) throw err;

        lastErr = err;

        if (attempt < retries && canRetryMethod) {
          await sleep(backoffMs(attempt), init?.signal);
          continue;
        }

        throw err;
      }
    }

    // Should not reach; defensive:
    throw lastErr instanceof Error ? lastErr : new Error("Industrial request failed");
  }

  private async fetchBlob(url: string, init?: TimeoutMergedFetchInit): Promise<Blob> {
    const method = safeString(init?.method, "GET").toUpperCase();
    const { res } = await this.fetchWithTimeout(url, init);

    if (!res.ok) {
      const reqId = headerRequestId(res.headers);
      const snippet = await readTextSnippet(res);
      throw new IndustrialControlApiError(`HTTP ${res.status} for industrial blob request`, {
        status: res.status,
        url,
        requestId: reqId,
        bodySnippet: snippet,
      });
    }

    return await res.blob();
  }

  /* -----------------------------------------------------------------------------------------------
   * Health
   * --------------------------------------------------------------------------------------------- */

  async health(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<{ ok: boolean; status?: string; ts?: number }> {
    const url = this.url(this.endpoints.health());
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs, tags: ["health"] });

    if (!isRecord(json)) return { ok: true };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      status: safeString((json as Record<string, unknown>).status, ""),
      ts: normalizeTsToSeconds((json as Record<string, unknown>).ts),
    };
  }

  /* -----------------------------------------------------------------------------------------------
   * Assets — list/get/create/update/delete
   * --------------------------------------------------------------------------------------------- */

  async listAssets(
    filters?: CommonListFilters & { asset_type?: string },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ items: IndustrialAsset[]; total?: number; next_cursor?: string }> {
    const base = this.url(this.endpoints.listAssets());

    const q = buildQuery({
      limit: filters?.limit,
      offset: filters?.offset,
      cursor: filters?.cursor,
      search: filters?.search,
      status: filters?.status,
      risk: filters?.risk,
      include_archived: filters?.include_archived,
      asset_type: filters?.asset_type,
      tags: filters?.tags,
      start_ts: normalizeTsToSeconds(filters?.start_ts),
      end_ts: normalizeTsToSeconds(filters?.end_ts),
    });

    const json = await this.fetchJson(`${base}${q}`, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["assets", "list"],
    });

    if (!isRecord(json)) return { items: [] };

    const rawItems =
      Array.isArray((json as Record<string, unknown>).items) ? ((json as Record<string, unknown>).items as unknown[]) : [];
    const items = rawItems.map(parseAsset).filter((x): x is IndustrialAsset => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString((json as Record<string, unknown>).next_cursor, safeString((json as Record<string, unknown>).cursor, ""));

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  async getAsset(id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<IndustrialAsset | null> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("getAsset requires a non-empty id");

    const url = this.url(this.endpoints.getAsset(clean));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs, tags: ["assets", "get"] });

    // Accept { item: {...} } or direct object
    const raw = isRecord(json) && isRecord((json as Record<string, unknown>).item) ? (json as Record<string, unknown>).item : json;
    return parseAsset(raw);
  }

  async createAsset(
    req: Partial<IndustrialAsset> & { name: string },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; item?: IndustrialAsset; id?: string }> {
    const url = this.url(this.endpoints.createAsset());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(req),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["assets", "create"],
    });

    if (!isRecord(json)) return { ok: true };

    const ok = Boolean((json as Record<string, unknown>).ok ?? true);
    const id = safeString((json as Record<string, unknown>).id, "");
    const itemRaw = (json as Record<string, unknown>).item;
    const item = parseAsset(itemRaw);

    return { ok, id: id || item?.id, item: item ?? undefined };
  }

  async updateAsset(
    id: string,
    updates: Partial<IndustrialAsset>,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; item?: IndustrialAsset; id?: string }> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("updateAsset requires a non-empty id");

    const url = this.url(this.endpoints.updateAsset(clean));
    const json = await this.fetchJson(url, {
      method: "PATCH",
      body: JSON.stringify({ id: clean, ...updates }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["assets", "update"],
    });

    if (!isRecord(json)) return { ok: true, id: clean };

    const ok = Boolean((json as Record<string, unknown>).ok ?? true);
    const outId = safeString((json as Record<string, unknown>).id, clean);
    const item = parseAsset((json as Record<string, unknown>).item);

    return { ok, id: outId, item: item ?? undefined };
  }

  async deleteAsset(
    id: string,
    reason?: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; id: string; status?: string }> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("deleteAsset requires a non-empty id");

    const url = this.url(this.endpoints.deleteAsset(clean));
    const json = await this.fetchJson(url, {
      method: "DELETE",
      body: JSON.stringify({ id: clean, reason: reason || undefined }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["assets", "delete"],
    });

    if (!isRecord(json)) return { ok: true, id: clean };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, clean),
      status: safeString((json as Record<string, unknown>).status, ""),
    };
  }

  /* -----------------------------------------------------------------------------------------------
   * Processes — list/get/create/update/delete
   * --------------------------------------------------------------------------------------------- */

  async listProcesses(
    filters?: CommonListFilters,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ items: IndustrialProcess[]; total?: number; next_cursor?: string }> {
    const base = this.url(this.endpoints.listProcesses());

    const q = buildQuery({
      limit: filters?.limit,
      offset: filters?.offset,
      cursor: filters?.cursor,
      search: filters?.search,
      status: filters?.status,
      risk: filters?.risk,
      include_archived: filters?.include_archived,
      tags: filters?.tags,
      start_ts: normalizeTsToSeconds(filters?.start_ts),
      end_ts: normalizeTsToSeconds(filters?.end_ts),
    });

    const json = await this.fetchJson(`${base}${q}`, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["processes", "list"],
    });

    if (!isRecord(json)) return { items: [] };

    const rawItems =
      Array.isArray((json as Record<string, unknown>).items) ? ((json as Record<string, unknown>).items as unknown[]) : [];
    const items = rawItems.map(parseProcess).filter((x): x is IndustrialProcess => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString((json as Record<string, unknown>).next_cursor, safeString((json as Record<string, unknown>).cursor, ""));

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  async getProcess(id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<IndustrialProcess | null> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("getProcess requires a non-empty id");

    const url = this.url(this.endpoints.getProcess(clean));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs, tags: ["processes", "get"] });

    const raw = isRecord(json) && isRecord((json as Record<string, unknown>).item) ? (json as Record<string, unknown>).item : json;
    return parseProcess(raw);
  }

  async createProcess(
    req: Partial<IndustrialProcess> & { name: string },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; item?: IndustrialProcess; id?: string }> {
    const url = this.url(this.endpoints.createProcess());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(req),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["processes", "create"],
    });

    if (!isRecord(json)) return { ok: true };

    const ok = Boolean((json as Record<string, unknown>).ok ?? true);
    const id = safeString((json as Record<string, unknown>).id, "");
    const item = parseProcess((json as Record<string, unknown>).item);

    return { ok, id: id || item?.id, item: item ?? undefined };
  }

  async updateProcess(
    id: string,
    updates: Partial<IndustrialProcess>,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; item?: IndustrialProcess; id?: string }> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("updateProcess requires a non-empty id");

    const url = this.url(this.endpoints.updateProcess(clean));
    const json = await this.fetchJson(url, {
      method: "PATCH",
      body: JSON.stringify({ id: clean, ...updates }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["processes", "update"],
    });

    if (!isRecord(json)) return { ok: true, id: clean };

    const ok = Boolean((json as Record<string, unknown>).ok ?? true);
    const outId = safeString((json as Record<string, unknown>).id, clean);
    const item = parseProcess((json as Record<string, unknown>).item);

    return { ok, id: outId, item: item ?? undefined };
  }

  async deleteProcess(
    id: string,
    reason?: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; id: string; status?: string }> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("deleteProcess requires a non-empty id");

    const url = this.url(this.endpoints.deleteProcess(clean));
    const json = await this.fetchJson(url, {
      method: "DELETE",
      body: JSON.stringify({ id: clean, reason: reason || undefined }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["processes", "delete"],
    });

    if (!isRecord(json)) return { ok: true, id: clean };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, clean),
      status: safeString((json as Record<string, unknown>).status, ""),
    };
  }

  /* -----------------------------------------------------------------------------------------------
   * Simulations — list/get/create/update/delete
   * --------------------------------------------------------------------------------------------- */

  async listSimulations(
    filters?: CommonListFilters & { engine?: string; asset_id?: string; process_id?: string; digital_twin_id?: string },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ items: IndustrialSimulation[]; total?: number; next_cursor?: string }> {
    const base = this.url(this.endpoints.listSimulations());

    const q = buildQuery({
      limit: filters?.limit,
      offset: filters?.offset,
      cursor: filters?.cursor,
      search: filters?.search,
      status: filters?.status,
      risk: filters?.risk,
      include_archived: filters?.include_archived,
      tags: filters?.tags,
      engine: filters?.engine,
      asset_id: filters?.asset_id,
      process_id: filters?.process_id,
      digital_twin_id: filters?.digital_twin_id,
      start_ts: normalizeTsToSeconds(filters?.start_ts),
      end_ts: normalizeTsToSeconds(filters?.end_ts),
    });

    const json = await this.fetchJson(`${base}${q}`, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["simulations", "list"],
    });

    if (!isRecord(json)) return { items: [] };

    const rawItems =
      Array.isArray((json as Record<string, unknown>).items) ? ((json as Record<string, unknown>).items as unknown[]) : [];
    const items = rawItems.map(parseSimulation).filter((x): x is IndustrialSimulation => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString((json as Record<string, unknown>).next_cursor, safeString((json as Record<string, unknown>).cursor, ""));

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  async getSimulation(id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<IndustrialSimulation | null> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("getSimulation requires a non-empty id");

    const url = this.url(this.endpoints.getSimulation(clean));
    const json = await this.fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["simulations", "get"],
    });

    const raw = isRecord(json) && isRecord((json as Record<string, unknown>).item) ? (json as Record<string, unknown>).item : json;
    return parseSimulation(raw);
  }

  async createSimulation(
    req: Partial<IndustrialSimulation> & { name: string },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; item?: IndustrialSimulation; id?: string }> {
    const url = this.url(this.endpoints.createSimulation());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify(req),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["simulations", "create"],
    });

    if (!isRecord(json)) return { ok: true };

    const ok = Boolean((json as Record<string, unknown>).ok ?? true);
    const id = safeString((json as Record<string, unknown>).id, "");
    const item = parseSimulation((json as Record<string, unknown>).item);

    return { ok, id: id || item?.id, item: item ?? undefined };
  }

  async updateSimulation(
    id: string,
    updates: Partial<IndustrialSimulation>,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; item?: IndustrialSimulation; id?: string }> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("updateSimulation requires a non-empty id");

    const url = this.url(this.endpoints.updateSimulation(clean));
    const json = await this.fetchJson(url, {
      method: "PATCH",
      body: JSON.stringify({ id: clean, ...updates }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["simulations", "update"],
    });

    if (!isRecord(json)) return { ok: true, id: clean };

    const ok = Boolean((json as Record<string, unknown>).ok ?? true);
    const outId = safeString((json as Record<string, unknown>).id, clean);
    const item = parseSimulation((json as Record<string, unknown>).item);

    return { ok, id: outId, item: item ?? undefined };
  }

  async deleteSimulation(
    id: string,
    reason?: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; id: string; status?: string }> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("deleteSimulation requires a non-empty id");

    const url = this.url(this.endpoints.deleteSimulation(clean));
    const json = await this.fetchJson(url, {
      method: "DELETE",
      body: JSON.stringify({ id: clean, reason: reason || undefined }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["simulations", "delete"],
    });

    if (!isRecord(json)) return { ok: true, id: clean };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, clean),
      status: safeString((json as Record<string, unknown>).status, ""),
    };
  }

  /* -----------------------------------------------------------------------------------------------
   * Runs — list/get/start/cancel + export-friendly helpers
   * --------------------------------------------------------------------------------------------- */

  async listRuns(
    filters?: CommonListFilters & { simulation_id?: string },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ items: IndustrialSimulationRun[]; total?: number; next_cursor?: string }> {
    const base = this.url(this.endpoints.listRuns());

    const q = buildQuery({
      limit: filters?.limit,
      offset: filters?.offset,
      cursor: filters?.cursor,
      search: filters?.search,
      status: filters?.status,
      include_archived: filters?.include_archived,
      simulation_id: filters?.simulation_id,
      start_ts: normalizeTsToSeconds(filters?.start_ts),
      end_ts: normalizeTsToSeconds(filters?.end_ts),
    });

    const json = await this.fetchJson(`${base}${q}`, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["runs", "list"],
    });

    if (!isRecord(json)) return { items: [] };

    const rawItems =
      Array.isArray((json as Record<string, unknown>).items) ? ((json as Record<string, unknown>).items as unknown[]) : [];
    const items = rawItems.map(parseRun).filter((x): x is IndustrialSimulationRun => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString((json as Record<string, unknown>).next_cursor, safeString((json as Record<string, unknown>).cursor, ""));

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  async getRun(id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<IndustrialSimulationRun | null> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("getRun requires a non-empty id");

    const url = this.url(this.endpoints.getRun(clean));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs, tags: ["runs", "get"] });

    const raw = isRecord(json) && isRecord((json as Record<string, unknown>).item) ? (json as Record<string, unknown>).item : json;
    return parseRun(raw);
  }

  async startRun(
    req: {
      simulation_id: string;
      reason?: string;
      params?: Record<string, unknown>;
      dry_run?: boolean;
    },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; run?: IndustrialSimulationRun; id?: string; approval_id?: string; request_id?: string }> {
    const simId = (req.simulation_id || "").trim();
    if (!simId) throw new Error("startRun requires simulation_id");

    const url = this.url(this.endpoints.startRun());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({
        simulation_id: simId,
        reason: req.reason || undefined,
        params: req.params ?? undefined,
        dry_run: safeBoolean(req.dry_run, false),
      }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["runs", "start"],
    });

    if (!isRecord(json)) return { ok: true };

    const ok = Boolean((json as Record<string, unknown>).ok ?? true);
    const run = parseRun((json as Record<string, unknown>).run ?? (json as Record<string, unknown>).item);
    const id = safeString((json as Record<string, unknown>).id, "");
    const approvalId = safeString((json as Record<string, unknown>).approval_id, "");
    const requestId = safeString((json as Record<string, unknown>).request_id, "");

    return {
      ok,
      run: run ?? undefined,
      id: id || run?.id,
      approval_id: approvalId || undefined,
      request_id: requestId || undefined,
    };
  }

  async cancelRun(
    id: string,
    reason?: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; id: string; status?: string }> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("cancelRun requires a non-empty id");

    const url = this.url(this.endpoints.cancelRun(clean));
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ id: clean, reason: reason || undefined }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["runs", "cancel"],
    });

    if (!isRecord(json)) return { ok: true, id: clean };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, clean),
      status: safeString((json as Record<string, unknown>).status, ""),
    };
  }

  /**
   * Optional: Export run results as a file.
   * This is backend-dependent; override endpoints or implement route server-side.
   *
   * Convention used here:
   *   GET /industrial/runs/export?format=json|csv&start_ts=&end_ts=&simulation_id=
   *
   * If not supported server-side, calling this will raise IndustrialControlApiError.
   */
  async exportRuns(
    opts?: {
      format?: "json" | "csv";
      filters?: DateRange & { simulation_id?: string; status?: string };
      signal?: AbortSignal;
      timeoutMs?: number;
    },
  ): Promise<Blob> {
    const format = opts?.format ?? "json";
    const base = this.url("/industrial/runs/export");

    const q = buildQuery({
      format,
      simulation_id: opts?.filters?.simulation_id,
      status: opts?.filters?.status,
      start_ts: normalizeTsToSeconds(opts?.filters?.start_ts),
      end_ts: normalizeTsToSeconds(opts?.filters?.end_ts),
    });

    return await this.fetchBlob(`${base}${q}`, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
  }

  /**
   * Optional: Streaming export for large datasets.
   * Backend-dependent. Returns ReadableStream if available.
   */
  async exportRunsStream(
    opts?: {
      format?: "json" | "csv";
      filters?: DateRange & { simulation_id?: string; status?: string };
      signal?: AbortSignal;
      timeoutMs?: number;
    },
  ): Promise<ReadableStream<Uint8Array> | null> {
    const format = opts?.format ?? "json";
    const base = this.url("/industrial/runs/export");

    const q = buildQuery({
      format,
      simulation_id: opts?.filters?.simulation_id,
      status: opts?.filters?.status,
      start_ts: normalizeTsToSeconds(opts?.filters?.start_ts),
      end_ts: normalizeTsToSeconds(opts?.filters?.end_ts),
    });

    const { res } = await this.fetchWithTimeout(`${base}${q}`, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!res.ok) {
      const reqId = headerRequestId(res.headers);
      const snippet = await readTextSnippet(res);
      throw new IndustrialControlApiError(`HTTP ${res.status} for industrial export stream`, {
        status: res.status,
        url: `${base}${q}`,
        requestId: reqId,
        bodySnippet: snippet,
      });
    }

    return res.body ?? null;
  }

  /* -----------------------------------------------------------------------------------------------
   * Safety validation — list + validate
   * --------------------------------------------------------------------------------------------- */

  async listSafetyValidations(
    filters?: CommonListFilters & { target_kind?: string; target_id?: string },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ items: SafetyValidation[]; total?: number; next_cursor?: string }> {
    const base = this.url(this.endpoints.listSafetyValidations());

    const q = buildQuery({
      limit: filters?.limit,
      offset: filters?.offset,
      cursor: filters?.cursor,
      status: filters?.status,
      target_kind: filters?.target_kind,
      target_id: filters?.target_id,
      start_ts: normalizeTsToSeconds(filters?.start_ts),
      end_ts: normalizeTsToSeconds(filters?.end_ts),
    });

    const json = await this.fetchJson(`${base}${q}`, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["safety", "list"],
    });

    if (!isRecord(json)) return { items: [] };

    const rawItems =
      Array.isArray((json as Record<string, unknown>).items) ? ((json as Record<string, unknown>).items as unknown[]) : [];
    const items = rawItems.map(parseSafetyValidation).filter((x): x is SafetyValidation => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString((json as Record<string, unknown>).next_cursor, safeString((json as Record<string, unknown>).cursor, ""));

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  async validateSafety(
    req: {
      target_kind: IndustrialEntityKind;
      target_id: string;
      reason?: string;
      params?: Record<string, unknown>;
      dry_run?: boolean;
    },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ ok: boolean; validation?: SafetyValidation; id?: string; approval_id?: string; request_id?: string }> {
    const tk = (req.target_kind || "").trim();
    const tid = (req.target_id || "").trim();
    if (!tk || !tid) throw new Error("validateSafety requires target_kind and target_id");

    const url = this.url(this.endpoints.validateSafety());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({
        target_kind: tk,
        target_id: tid,
        reason: req.reason || undefined,
        params: req.params ?? undefined,
        dry_run: safeBoolean(req.dry_run, true),
      }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["safety", "validate"],
    });

    if (!isRecord(json)) return { ok: true };

    const ok = Boolean((json as Record<string, unknown>).ok ?? true);
    const v = parseSafetyValidation((json as Record<string, unknown>).validation ?? (json as Record<string, unknown>).item);
    const id = safeString((json as Record<string, unknown>).id, "");
    const approvalId = safeString((json as Record<string, unknown>).approval_id, "");
    const requestId = safeString((json as Record<string, unknown>).request_id, "");

    return {
      ok,
      validation: v ?? undefined,
      id: id || v?.id,
      approval_id: approvalId || undefined,
      request_id: requestId || undefined,
    };
  }

  /* -----------------------------------------------------------------------------------------------
   * Telemetry — read-only queries
   * --------------------------------------------------------------------------------------------- */

  async telemetry(
    q: TelemetryQuery,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<{ items: TelemetryPoint[]; total?: number; next_cursor?: string }> {
    const base = this.url(this.endpoints.telemetry());

    const qs = buildQuery({
      source_id: q.source_id,
      start_ts: normalizeTsToSeconds(q.start_ts),
      end_ts: normalizeTsToSeconds(q.end_ts),
      limit: q.limit,
      metric_keys: q.metric_keys,
    });

    const json = await this.fetchJson(`${base}${qs}`, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["telemetry", "query"],
    });

    if (!isRecord(json)) return { items: [] };

    const rawItems =
      Array.isArray((json as Record<string, unknown>).items) ? ((json as Record<string, unknown>).items as unknown[]) : [];
    const items = rawItems.map(parseTelemetryPoint).filter((x): x is TelemetryPoint => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString((json as Record<string, unknown>).next_cursor, safeString((json as Record<string, unknown>).cursor, ""));

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  /* -----------------------------------------------------------------------------------------------
   * Interventions — governed request/execute pattern
   * --------------------------------------------------------------------------------------------- */

  /**
   * Request an intervention (preferred).
   * The backend should create an approval item and return approval_id.
   *
   * NOTE: This client never assumes approval is granted; it only submits intent.
   */
  async requestIntervention(
    req: IndustrialInterventionRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<IndustrialInterventionResponse> {
    const targetKind = (req.target_kind || "").trim();
    const targetId = (req.target_id || "").trim();
    const action = (req.action || "").trim();

    if (!targetKind || !targetId || !action) {
      throw new Error("requestIntervention requires target_kind, target_id, and action");
    }

    const url = this.url(this.endpoints.requestIntervention());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({
        ...req,
        mode: "request",
        target_kind: targetKind,
        target_id: targetId,
        action,
        // Encourage safe defaults at UI boundary:
        dry_run: req.dry_run ?? true,
      }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["interventions", "request"],
    });

    if (!isRecord(json)) return { ok: true };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      status: safeString((json as Record<string, unknown>).status, ""),
      request_id: safeString((json as Record<string, unknown>).request_id, ""),
      approval_id: safeString((json as Record<string, unknown>).approval_id, ""),
      result_id: safeString((json as Record<string, unknown>).result_id, ""),
      message: safeString((json as Record<string, unknown>).message, ""),
      meta: isRecord((json as Record<string, unknown>).meta) ? ((json as Record<string, unknown>).meta as Record<string, unknown>) : undefined,
    };
  }

  /**
   * Execute an intervention directly (optional, safety-gated).
   *
   * This should generally be disabled in the browser UI and handled by backend
   * workflows (approval → execute) unless you're in a highly controlled operator
   * console context.
   */
  async executeIntervention(
    req: IndustrialInterventionRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<IndustrialInterventionResponse> {
    if (!this.unsafeDirectActuation) {
      throw new Error(
        "executeIntervention is disabled (unsafeDirectActuation=false). Use requestIntervention() or enable explicit opt-in.",
      );
    }

    const targetKind = (req.target_kind || "").trim();
    const targetId = (req.target_id || "").trim();
    const action = (req.action || "").trim();

    if (!targetKind || !targetId || !action) {
      throw new Error("executeIntervention requires target_kind, target_id, and action");
    }

    const url = this.url(this.endpoints.executeIntervention());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({
        ...req,
        mode: "execute",
        target_kind: targetKind,
        target_id: targetId,
        action,
        dry_run: req.dry_run ?? false,
      }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
      tags: ["interventions", "execute"],
    });

    if (!isRecord(json)) return { ok: true };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      status: safeString((json as Record<string, unknown>).status, ""),
      request_id: safeString((json as Record<string, unknown>).request_id, ""),
      approval_id: safeString((json as Record<string, unknown>).approval_id, ""),
      result_id: safeString((json as Record<string, unknown>).result_id, ""),
      message: safeString((json as Record<string, unknown>).message, ""),
      meta: isRecord((json as Record<string, unknown>).meta) ? ((json as Record<string, unknown>).meta as Record<string, unknown>) : undefined,
    };
  }
}
