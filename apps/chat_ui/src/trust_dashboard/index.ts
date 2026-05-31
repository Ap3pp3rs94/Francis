/**
 * Trust Dashboard module (UI).
 *
 * Typed, defensive client + protocol layer for Francis "trust" system introspection.
 *
 * Design contract
 * ---------------
 *  1) Framework-agnostic:
 *     - NO React imports here.
 *
 *  2) Defensive parsing:
 *     - Treat all server responses as untrusted.
 *     - Accept common alias shapes and tolerate missing fields.
 *
 *  3) Forward-compatible endpoints:
 *     - Each logical endpoint returns an ordered list of candidates.
 *     - The client probes in order and tolerates 404/405 to survive route evolution.
 *
 *  4) Safe-by-default mutations:
 *     - Mutations are disabled unless explicitly enabled in client options.
 *     - Backend is still responsible for policy + approvals.
 */

export type UnixSeconds = number;

export type TrustMode = "disabled" | "policy" | "strict" | "learning" | string;

/**
 * Trust level is intentionally a number without strict bounds:
 * some systems use 0..1, others use 0..100, others use -10..+10.
 *
 * UI helpers can format it safely without assuming a specific scale.
 */
export type TrustLevel = number;

export type TrustState = {
  ts: UnixSeconds; // last updated (unix seconds)
  mode?: TrustMode;

  level: TrustLevel;

  /**
   * Optional higher-level classification:
   * e.g., "low", "medium", "high", "critical", "unknown" (backend-defined).
   */
  tier?: string;

  /**
   * Optional control flags (backend-defined).
   */
  decay_enabled?: boolean;
  growth_enabled?: boolean;

  /**
   * Optional guardrails.
   */
  min_level?: number;
  max_level?: number;

  /**
   * Optional explanation of how level was derived (backend-defined).
   */
  rationale?: string;

  /**
   * Optional provenance.
   */
  source?: string; // "computed", "manual", "imported", "bootstrap"
  actor?: string;
  domain?: string;

  meta?: Record<string, unknown>;
};

export type TrustHistoryPoint = {
  ts: UnixSeconds;
  level: TrustLevel;

  // Optional fields (backend-defined)
  tier?: string;
  reason?: string;
  source?: string;
  actor?: string;
  domain?: string;

  meta?: Record<string, unknown>;
};

export type TrustEventKind =
  | "adjust"
  | "decay"
  | "growth"
  | "policy"
  | "override"
  | "bootstrap"
  | "unknown"
  | string;

export type TrustEvent = {
  id: string;
  ts: UnixSeconds;

  kind?: TrustEventKind;

  /**
   * Delta may be omitted if the backend only records absolute levels.
   */
  delta?: number;

  /**
   * If the backend provides before/after snapshots, keep them.
   */
  before_level?: TrustLevel;
  after_level?: TrustLevel;

  reason?: string;
  actor?: string;
  domain?: string;
  source?: string;

  /**
   * Optional linkage for traceability.
   */
  correlation_id?: string;
  approval_id?: string;
  operation_id?: string;

  meta?: Record<string, unknown>;
};

export type TrustPolicy = {
  mode?: TrustMode;

  /**
   * Backend-defined thresholds, gates, or banding.
   * We keep this open-ended; UI can render it as JSON if needed.
   */
  thresholds?: Record<string, unknown>;

  /**
   * Optional rules summary for display.
   */
  summary?: string;

  /**
   * If present, can indicate what actions are allowed at what trust.
   */
  gates?: Record<string, unknown>;

  ts?: UnixSeconds;
  meta?: Record<string, unknown>;
};

export type TrustHistoryParams = {
  // window (unix seconds)
  start_ts?: UnixSeconds;
  end_ts?: UnixSeconds;

  // pagination (backend dependent)
  limit?: number;
  cursor?: string;
};

export type TrustEventsParams = {
  start_ts?: UnixSeconds;
  end_ts?: UnixSeconds;
  limit?: number;
  cursor?: string;

  kind?: string;
  actor?: string;
  domain?: string;
  search?: string;
};

export type TrustHistoryResponse = {
  items: TrustHistoryPoint[];
  next_cursor?: string;
  total?: number;
};

export type TrustEventsResponse = {
  items: TrustEvent[];
  next_cursor?: string;
  total?: number;
};

export type TrustAdjustOp = "set" | "increase" | "decrease" | string;

export type TrustAdjustRequest = {
  op: TrustAdjustOp;

  /**
   * For "set": value is required.
   * For "increase"/"decrease": delta is required (positive number recommended).
   *
   * Backend decides precedence if both are provided.
   */
  value?: TrustLevel;
  delta?: number;

  reason?: string;
  actor?: string;
  domain?: string;

  /**
   * Optional idempotency key (safe for retries).
   */
  idempotency_key?: string;

  meta?: Record<string, unknown>;
};

export type TrustAdjustResponse = {
  ok: boolean;

  /**
   * If approval-gated:
   */
  approval_id?: string;
  status?: string; // "pending" etc

  /**
   * If applied immediately:
   */
  applied?: boolean;
  level?: TrustLevel;
  ts?: UnixSeconds;

  message?: string;
  meta?: Record<string, unknown>;
};

export type TrustCalibrationClaimStrength = "confirmed" | "likely" | "uncertain" | "blocked" | string;

export type TrustCalibrationEvidence = {
  current_route_readback?: boolean;
  explicit_receipt?: boolean;
  recency_readback?: boolean;
  claim_scope_matches_evidence_scope?: boolean;
  conflicting_evidence?: boolean;
  stale_evidence?: boolean;
  supporting_evidence?: boolean;
  current_readback_reports_blocked?: boolean;
  blocked_state_readback?: boolean;
  required_authority_absent?: boolean;
  required_receipt_or_gate_missing?: boolean;
  safe_execution_precondition_met?: boolean;
  next_smallest_truthful_gap?: string;
  missing_verification?: string[];
  [key: string]: unknown;
};

export type TrustCalibrationClaimEvaluationRequest = {
  claim_text: string;
  claim_scope?: string;
  requested_claim_strength?: TrustCalibrationClaimStrength;
  evidence?: TrustCalibrationEvidence;
};

export type TrustCalibrationClaimEvaluation = {
  ok: boolean;
  status: string;
  claim_strength: TrustCalibrationClaimStrength;
  requested_claim_strength?: TrustCalibrationClaimStrength;
  downgraded: boolean;
  reason: string;
  condition: string;
  ui_state: string;
  surface_obligation: string;
  citation_obligation: string;
  missing_verification: string[];
  allowed_surface_language: string[];
  forbidden_surface_language: string[];
  next_smallest_truthful_gap: string;
  runtime_claim_integration_ready: boolean;
  evaluates_supplied_evidence_only: boolean;
  writes_memory: boolean;
  writes_receipts: boolean;
  scores_model_output: boolean;
  changes_ui_confidence: boolean;
  enforces_runtime_claims: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance?: Record<string, unknown>;
};

export type TrustCalibrationCompletionReview = {
  ok: boolean;
  status: string;
  stage13_completion_review_ready: boolean;
  stage_closure_decision_required: boolean;
  stage13_closed_by_receipt: boolean;
  operator_browser_visual_readback_observed: boolean;
  latest_operator_browser_visual_readback_receipt_id: string;
  ready_count: number;
  required_count: number;
  blockers: string[];
  next_smallest_truthful_gap: string;
  reads_receipts: boolean;
  writes_receipts: boolean;
  writes_memory: boolean;
  runs_tools: boolean;
  runs_shell: boolean;
  runs_git: boolean;
  launches_browser: boolean;
  captures_screen: boolean;
  marks_stage_closed: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance?: Record<string, unknown>;
};

export type TrustCalibrationStageClosureDecisionReadback = {
  ok: boolean;
  status: string;
  count: number;
  latest_receipt_id: string;
  latest_decision: string;
  stage13_closed_by_receipt: boolean;
  reads_receipts: boolean;
  writes_receipts: boolean;
  writes_memory: boolean;
  runs_tools: boolean;
  runs_shell: boolean;
  runs_git: boolean;
  launches_browser: boolean;
  captures_screen: boolean;
  marks_runtime_stage_state: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  next_smallest_truthful_gap: string;
  governance?: Record<string, unknown>;
};

const DEFAULT_TRUST_MUTATION_ACTOR = "chat_ui.trust";

export class TrustApiError extends Error {
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
    this.name = "TrustApiError";
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

function safeStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.map((x) => (typeof x === "string" ? x : "")).filter((s) => s.length > 0);
  return out.length ? out : undefined;
}

function normalizeUnixSeconds(ts: unknown): UnixSeconds | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  // Heuristic: if it looks like ms, normalize to seconds.
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : Math.floor(ts);
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
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

async function readTextSnippet(res: Response, maxChars = 2048): Promise<string> {
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

/* -------------------------------------------------------------------------------------------------
 * parsing (defensive, alias-tolerant)
 * ------------------------------------------------------------------------------------------------- */

function parseTrustState(raw: unknown): TrustState | null {
  if (!isRecord(raw)) return null;

  // Accept { state: {...} } or direct object.
  const obj = isRecord(raw.state) ? (raw.state as Record<string, unknown>) : raw;

  const level =
    safeNumber(obj.level, NaN) ||
    safeNumber(obj.score, NaN) ||
    safeNumber(obj.value, NaN);

  if (!Number.isFinite(level)) return null;

  const ts =
    normalizeUnixSeconds(obj.ts) ??
    normalizeUnixSeconds(obj.updated_ts) ??
    normalizeUnixSeconds(obj.time) ??
    Math.floor(Date.now() / 1000);

  const state: TrustState = {
    ts,
    level,
  };

  const mode = safeString(obj.mode, safeString(obj.trust_mode, ""));
  if (mode) state.mode = mode;

  const tier = safeString(obj.tier, safeString(obj.band, ""));
  if (tier) state.tier = tier;

  if (typeof obj.decay_enabled === "boolean") state.decay_enabled = obj.decay_enabled;
  else if (typeof obj.decayEnabled === "boolean") state.decay_enabled = obj.decayEnabled;

  if (typeof obj.growth_enabled === "boolean") state.growth_enabled = obj.growth_enabled;
  else if (typeof obj.growthEnabled === "boolean") state.growth_enabled = obj.growthEnabled;

  const minLevel = safeNumber(obj.min_level, NaN) || safeNumber(obj.min, NaN);
  const maxLevel = safeNumber(obj.max_level, NaN) || safeNumber(obj.max, NaN);
  if (Number.isFinite(minLevel)) state.min_level = minLevel;
  if (Number.isFinite(maxLevel)) state.max_level = maxLevel;

  const rationale = safeString(obj.rationale, safeString(obj.reason, ""));
  if (rationale) state.rationale = rationale;

  const source = safeString(obj.source, "");
  if (source) state.source = source;

  const actor = safeString(obj.actor, safeString(obj.user, ""));
  if (actor) state.actor = actor;

  const domain = safeString(obj.domain, safeString(obj.domain_id, ""));
  if (domain) state.domain = domain;

  if (isRecord(obj.meta)) state.meta = obj.meta as Record<string, unknown>;

  return state;
}

function parseHistoryPoint(raw: unknown): TrustHistoryPoint | null {
  if (!isRecord(raw)) return null;

  const ts = normalizeUnixSeconds(raw.ts) ?? normalizeUnixSeconds(raw.time);
  if (!ts) return null;

  const level = safeNumber(raw.level, NaN) || safeNumber(raw.score, NaN) || safeNumber(raw.value, NaN);
  if (!Number.isFinite(level)) return null;

  const p: TrustHistoryPoint = { ts, level };

  const tier = safeString(raw.tier, safeString(raw.band, ""));
  if (tier) p.tier = tier;

  const reason = safeString(raw.reason, safeString(raw.rationale, ""));
  if (reason) p.reason = reason;

  const source = safeString(raw.source, "");
  if (source) p.source = source;

  const actor = safeString(raw.actor, safeString(raw.user, ""));
  if (actor) p.actor = actor;

  const domain = safeString(raw.domain, safeString(raw.domain_id, ""));
  if (domain) p.domain = domain;

  if (isRecord(raw.meta)) p.meta = raw.meta as Record<string, unknown>;

  return p;
}

function parseTrustEvent(raw: unknown): TrustEvent | null {
  if (!isRecord(raw)) return null;

  const ts = normalizeUnixSeconds(raw.ts) ?? normalizeUnixSeconds(raw.time);
  if (!ts) return null;

  const id =
    safeString(raw.id) ||
    safeString(raw.event_id) ||
    safeString(raw.eid) ||
    safeString(raw.correlation_id) ||
    "";

  const kind = safeString(raw.kind, safeString(raw.type, safeString(raw.event, "")));
  const reason = safeString(raw.reason, safeString(raw.rationale, ""));
  const actor = safeString(raw.actor, safeString(raw.user, ""));
  const domain = safeString(raw.domain, safeString(raw.domain_id, ""));
  const source = safeString(raw.source, "");

  const delta =
    Number.isFinite(safeNumber(raw.delta, NaN)) ? safeNumber(raw.delta, NaN) :
    Number.isFinite(safeNumber(raw.change, NaN)) ? safeNumber(raw.change, NaN) :
    undefined;

  const beforeLevel =
    Number.isFinite(safeNumber(raw.before_level, NaN)) ? safeNumber(raw.before_level, NaN) :
    Number.isFinite(safeNumber(raw.before, NaN)) ? safeNumber(raw.before, NaN) :
    undefined;

  const afterLevel =
    Number.isFinite(safeNumber(raw.after_level, NaN)) ? safeNumber(raw.after_level, NaN) :
    Number.isFinite(safeNumber(raw.after, NaN)) ? safeNumber(raw.after, NaN) :
    undefined;

  const correlationId = safeString(raw.correlation_id, safeString(raw.correlationId, ""));
  const approvalId = safeString(raw.approval_id, "");
  const operationId = safeString(raw.operation_id, safeString(raw.op_id, ""));

  const ev: TrustEvent = {
    id: id || `tev_${ts}_${safeStringArray([kind, actor, domain].join("|"))}`,
    ts,
  };

  if (kind) ev.kind = kind;
  if (typeof delta === "number" && Number.isFinite(delta)) ev.delta = delta;
  if (typeof beforeLevel === "number" && Number.isFinite(beforeLevel)) ev.before_level = beforeLevel;
  if (typeof afterLevel === "number" && Number.isFinite(afterLevel)) ev.after_level = afterLevel;

  if (reason) ev.reason = reason;
  if (actor) ev.actor = actor;
  if (domain) ev.domain = domain;
  if (source) ev.source = source;

  if (correlationId) ev.correlation_id = correlationId;
  if (approvalId) ev.approval_id = approvalId;
  if (operationId) ev.operation_id = operationId;

  if (isRecord(raw.meta)) ev.meta = raw.meta as Record<string, unknown>;

  return ev;
}

function parseTrustHistoryResponse(raw: unknown): TrustHistoryResponse {
  // Accept JSONL string fallback: each line is a JSON object.
  if (typeof raw === "string") {
    const lines = raw.split(/\r?\n/).map((s) => s.trim()).filter((s) => s.length > 0);
    const points: TrustHistoryPoint[] = [];
    for (const line of lines) {
      try {
        const obj = JSON.parse(line) as unknown;
        const p = parseHistoryPoint(obj);
        if (p) points.push(p);
      } catch {
        // ignore
      }
    }
    return { items: points };
  }

  if (Array.isArray(raw)) {
    return { items: raw.map(parseHistoryPoint).filter((x): x is TrustHistoryPoint => x !== null) };
  }

  if (!isRecord(raw)) return { items: [] };

  const arr =
    (Array.isArray(raw.items) ? raw.items :
    Array.isArray(raw.history) ? raw.history :
    Array.isArray(raw.points) ? raw.points :
    Array.isArray(raw.entries) ? raw.entries :
    []) as unknown[];

  const items = arr.map(parseHistoryPoint).filter((x): x is TrustHistoryPoint => x !== null);

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

function parseTrustEventsResponse(raw: unknown): TrustEventsResponse {
  if (typeof raw === "string") {
    const lines = raw.split(/\r?\n/).map((s) => s.trim()).filter((s) => s.length > 0);
    const items: TrustEvent[] = [];
    for (const line of lines) {
      try {
        const obj = JSON.parse(line) as unknown;
        const e = parseTrustEvent(obj);
        if (e) items.push(e);
      } catch {
        // ignore
      }
    }
    return { items };
  }

  if (Array.isArray(raw)) {
    return { items: raw.map(parseTrustEvent).filter((x): x is TrustEvent => x !== null) };
  }

  if (!isRecord(raw)) return { items: [] };

  const arr =
    (Array.isArray(raw.items) ? raw.items :
    Array.isArray(raw.events) ? raw.events :
    Array.isArray(raw.entries) ? raw.entries :
    Array.isArray(raw.log) ? raw.log :
    []) as unknown[];

  const items = arr.map(parseTrustEvent).filter((x): x is TrustEvent => x !== null);

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

function parseTrustPolicy(raw: unknown): TrustPolicy | null {
  if (!isRecord(raw)) return null;

  const obj = isRecord(raw.policy) ? (raw.policy as Record<string, unknown>) : raw;

  const policy: TrustPolicy = {};

  const mode = safeString(obj.mode, "");
  if (mode) policy.mode = mode;

  if (isRecord(obj.thresholds)) policy.thresholds = obj.thresholds as Record<string, unknown>;
  if (isRecord(obj.gates)) policy.gates = obj.gates as Record<string, unknown>;

  const summary = safeString(obj.summary, safeString(obj.description, ""));
  if (summary) policy.summary = summary;

  const ts = normalizeUnixSeconds(obj.ts);
  if (ts) policy.ts = ts;

  if (isRecord(obj.meta)) policy.meta = obj.meta as Record<string, unknown>;

  return policy;
}

function parseTrustCalibrationClaimEvaluation(raw: unknown): TrustCalibrationClaimEvaluation | null {
  if (!isRecord(raw)) return null;

  const claimStrength = safeString(raw.claim_strength, "").trim();
  if (!claimStrength) return null;

  const requestedClaimStrength = safeString(raw.requested_claim_strength, "").trim();

  return {
    ok: safeBool(raw.ok, true),
    status: safeString(raw.status, ""),
    claim_strength: claimStrength,
    requested_claim_strength: requestedClaimStrength || undefined,
    downgraded: safeBool(raw.downgraded, false),
    reason: safeString(raw.reason, ""),
    condition: safeString(raw.condition, ""),
    ui_state: safeString(raw.ui_state, ""),
    surface_obligation: safeString(raw.surface_obligation, ""),
    citation_obligation: safeString(raw.citation_obligation, ""),
    missing_verification: safeStringArray(raw.missing_verification) ?? [],
    allowed_surface_language: safeStringArray(raw.allowed_surface_language) ?? [],
    forbidden_surface_language: safeStringArray(raw.forbidden_surface_language) ?? [],
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
    runtime_claim_integration_ready: safeBool(raw.runtime_claim_integration_ready, false),
    evaluates_supplied_evidence_only: safeBool(raw.evaluates_supplied_evidence_only, false),
    writes_memory: safeBool(raw.writes_memory, false),
    writes_receipts: safeBool(raw.writes_receipts, false),
    scores_model_output: safeBool(raw.scores_model_output, false),
    changes_ui_confidence: safeBool(raw.changes_ui_confidence, false),
    enforces_runtime_claims: safeBool(raw.enforces_runtime_claims, false),
    grants_execution_authority: safeBool(raw.grants_execution_authority, false),
    grants_mutation_authority: safeBool(raw.grants_mutation_authority, false),
    governance: isRecord(raw.governance) ? (raw.governance as Record<string, unknown>) : undefined,
  };
}

function parseTrustCalibrationCompletionReview(raw: unknown): TrustCalibrationCompletionReview | null {
  if (!isRecord(raw)) return null;

  const status = safeString(raw.status, "").trim();
  if (!status) return null;

  return {
    ok: safeBool(raw.ok, true),
    status,
    stage13_completion_review_ready: safeBool(raw.stage13_completion_review_ready, false),
    stage_closure_decision_required: safeBool(raw.stage_closure_decision_required, false),
    stage13_closed_by_receipt: safeBool(raw.stage13_closed_by_receipt, false),
    operator_browser_visual_readback_observed: safeBool(raw.operator_browser_visual_readback_observed, false),
    latest_operator_browser_visual_readback_receipt_id: safeString(
      raw.latest_operator_browser_visual_readback_receipt_id,
      "",
    ),
    ready_count: safeNumber(raw.ready_count, 0),
    required_count: safeNumber(raw.required_count, 0),
    blockers: safeStringArray(raw.blockers) ?? [],
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
    reads_receipts: safeBool(raw.reads_receipts, false),
    writes_receipts: safeBool(raw.writes_receipts, false),
    writes_memory: safeBool(raw.writes_memory, false),
    runs_tools: safeBool(raw.runs_tools, false),
    runs_shell: safeBool(raw.runs_shell, false),
    runs_git: safeBool(raw.runs_git, false),
    launches_browser: safeBool(raw.launches_browser, false),
    captures_screen: safeBool(raw.captures_screen, false),
    marks_stage_closed: safeBool(raw.marks_stage_closed, false),
    grants_execution_authority: safeBool(raw.grants_execution_authority, false),
    grants_mutation_authority: safeBool(raw.grants_mutation_authority, false),
    governance: isRecord(raw.governance) ? (raw.governance as Record<string, unknown>) : undefined,
  };
}

function parseTrustCalibrationStageClosureDecisionReadback(
  raw: unknown,
): TrustCalibrationStageClosureDecisionReadback | null {
  if (!isRecord(raw)) return null;

  const status = safeString(raw.status, "").trim();
  if (!status) return null;

  return {
    ok: safeBool(raw.ok, true),
    status,
    count: safeNumber(raw.count, 0),
    latest_receipt_id: safeString(raw.latest_receipt_id, ""),
    latest_decision: safeString(raw.latest_decision, ""),
    stage13_closed_by_receipt: safeBool(raw.stage13_closed_by_receipt, false),
    reads_receipts: safeBool(raw.reads_receipts, false),
    writes_receipts: safeBool(raw.writes_receipts, false),
    writes_memory: safeBool(raw.writes_memory, false),
    runs_tools: safeBool(raw.runs_tools, false),
    runs_shell: safeBool(raw.runs_shell, false),
    runs_git: safeBool(raw.runs_git, false),
    launches_browser: safeBool(raw.launches_browser, false),
    captures_screen: safeBool(raw.captures_screen, false),
    marks_runtime_stage_state: safeBool(raw.marks_runtime_stage_state, false),
    grants_execution_authority: safeBool(raw.grants_execution_authority, false),
    grants_mutation_authority: safeBool(raw.grants_mutation_authority, false),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
    governance: isRecord(raw.governance) ? (raw.governance as Record<string, unknown>) : undefined,
  };
}

/* -------------------------------------------------------------------------------------------------
 * endpoints (overrideable)
 * ------------------------------------------------------------------------------------------------- */

export type TrustEndpoints = {
  state: () => string[];
  history: (q?: TrustHistoryParams) => string[];
  events: (q?: TrustEventsParams) => string[];
  policy: () => string[];

  /**
   * Read-only evaluator: POST body supplies a claim and explicit evidence.
   * The backend returns calibrated language/UI obligations without mutating state.
   */
  claimEvaluation: () => string[];
  completionReview: () => string[];
  stageClosureDecisions: (q?: { limit?: number }) => string[];

  /**
   * Mutations (approval/policy gated server-side).
   */
  adjust: () => string[];
};

export function defaultTrustEndpoints(): TrustEndpoints {
  return {
    state: () => ["/trust/state", "/trust/current", "/trust", "/system/trust/state", "/system/trust"],

    history: (q) => {
      const qs = encodeQuery({
        start_ts: q?.start_ts,
        end_ts: q?.end_ts,
        limit: q?.limit,
        cursor: q?.cursor,
      });
      return [
        `/trust/history${qs}`,
        `/trust/levels/history${qs}`,
        `/trust/timeline${qs}`,
        `/system/trust/history${qs}`,
      ];
    },

    events: (q) => {
      const qs = encodeQuery({
        start_ts: q?.start_ts,
        end_ts: q?.end_ts,
        limit: q?.limit,
        cursor: q?.cursor,
        kind: q?.kind,
        actor: q?.actor,
        domain: q?.domain,
        search: q?.search,
      });
      return [
        `/trust/events${qs}`,
        `/trust/log${qs}`,
        `/trust/audit${qs}`,
        `/system/trust/events${qs}`,
      ];
    },

    policy: () => ["/trust/policy", "/trust/config", "/trust/settings", "/system/trust/policy", "/system/trust/config"],

    claimEvaluation: () => ["/trust-calibration/evaluate-claim"],
    completionReview: () => ["/trust-calibration/completion-review"],
    stageClosureDecisions: (q) => {
      const qs = encodeQuery({ limit: q?.limit });
      return [`/trust-calibration/stage-closure-decisions${qs}`];
    },

    adjust: () => ["/trust/adjust", "/trust/mutate", "/trust/set", "/system/trust/adjust", "/system/trust/mutate"],
  };
}

export type RetryPolicy = {
  retries?: number; // default 1
  retryMethods?: string[]; // default ["GET", "HEAD"]
  retryStatusCodes?: number[]; // default [429, 502, 503, 504]
};

export type TrustClientOptions = {
  endpoints?: TrustEndpoints;
  defaultTimeoutMs?: number;

  /**
   * Mutations disabled unless explicitly enabled.
   */
  mutationsEnabled?: boolean;

  /**
   * Optional bearer token supplier (caller-owned). Prefer cookies for production.
   */
  bearerTokenProvider?: () => string | null;

  /**
   * Extra headers (caller-owned).
   */
  headersExtra?: Record<string, string>;

  /**
   * Retry defaults tuned for local dev flakiness without hiding real errors.
   */
  retry?: RetryPolicy;
};

type TimeoutFetchInit = RequestInit & {
  timeoutMs?: number;
  bearerToken?: string | null;
  headersExtra?: Record<string, string>;
};

export class TrustClient {
  readonly baseUrl: string;
  readonly endpoints: TrustEndpoints;
  readonly defaultTimeoutMs: number;
  readonly mutationsEnabled: boolean;

  readonly retry: Required<RetryPolicy>;

  private readonly bearerTokenProvider?: () => string | null;
  private readonly headersExtra?: Record<string, string>;

  constructor(baseUrl: string, opts?: TrustClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("TrustClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultTrustEndpoints();
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

  private async fetchWithTimeout(url: string, init?: TimeoutFetchInit): Promise<{ res: Response; elapsedMs: number }> {
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

    const start = performance.now();

    try {
      const headers = new Headers(fetchInit.headers ?? undefined);
      if (!headers.has("Accept")) headers.set("Accept", "application/json");

      const method = safeString(fetchInit.method, "GET").toUpperCase();
      const hasBody = "body" in fetchInit && fetchInit.body !== undefined && fetchInit.body !== null;
      if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

      if (bearerToken) headers.set("Authorization", `Bearer ${bearerToken}`);
      if (headersExtra) for (const [k, v] of Object.entries(headersExtra)) headers.set(k, v);

      const res = await fetch(url, { ...fetchInit, headers, signal: controller.signal });
      const elapsedMs = Math.max(0, Math.round(performance.now() - start));
      return { res, elapsedMs };
    } catch (err) {
      if (timedOut) {
        throw new TrustApiError(`Request timed out after ${timeoutMs}ms`, { url, timedOut: true, cause: err });
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
        const { res } = await this.fetchWithTimeout(url, init);

        if (!res.ok) {
          const snippet = await readTextSnippet(res);
          const reqId = headerRequestId(res.headers);

          const err = new TrustApiError(`HTTP ${res.status} for trust request`, {
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
          throw new TrustApiError("Failed to parse JSON response", {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
            cause: parseErr,
          });
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") throw err;
        if (err instanceof TrustApiError && err.timedOut) throw err;

        lastErr = err;
        if (attempt < this.retry.retries && canRetry) {
          await sleep(backoffMs(attempt), init?.signal ?? undefined);
          continue;
        }
        throw err;
      }
    }

    throw lastErr instanceof Error ? lastErr : new Error("Trust request failed");
  }

  private async fetchFirstOk(
    candidates: string[],
    init: TimeoutFetchInit,
  ): Promise<{ url: string; json: unknown; res: Response }> {
    let lastErr: unknown = null;

    for (const path of candidates) {
      const url = this.url(path);

      try {
        const { res, json } = await this.fetchJson(url, init);
        return { url, res, json };
      } catch (err) {
        lastErr = err;

        if (err instanceof TrustApiError && (err.status === 404 || err.status === 405)) {
          // Route not found / wrong verb -> try next candidate
          continue;
        }

        // Hard failures should surface.
        throw err;
      }
    }

    if (lastErr instanceof Error) throw lastErr;
    throw new Error("No trust endpoints responded successfully");
  }

  async getState(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<TrustState | null> {
    const { json } = await this.fetchFirstOk(this.endpoints.state(), this.init(opts));
    return parseTrustState(json);
  }

  async getPolicy(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<TrustPolicy | null> {
    const { json } = await this.fetchFirstOk(this.endpoints.policy(), this.init(opts));
    return parseTrustPolicy(json);
  }

  async listHistory(
    params?: TrustHistoryParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<TrustHistoryResponse> {
    const limit = typeof params?.limit === "number" ? clamp(Math.floor(params.limit), 1, 10_000) : 200;
    const candidates = this.endpoints.history({ ...params, limit });

    const { json } = await this.fetchFirstOk(candidates, this.init(opts));
    const parsed = parseTrustHistoryResponse(json);

    // Sort ascending by ts (stable timeline)
    parsed.items.sort((a, b) => a.ts - b.ts);
    return parsed;
  }

  async listEvents(
    params?: TrustEventsParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<TrustEventsResponse> {
    const limit = typeof params?.limit === "number" ? clamp(Math.floor(params.limit), 1, 10_000) : 100;
    const candidates = this.endpoints.events({ ...params, limit });

    const { json } = await this.fetchFirstOk(candidates, this.init(opts));
    const parsed = parseTrustEventsResponse(json);

    // Sort descending by ts (newest first)
    parsed.items.sort((a, b) => b.ts - a.ts);
    return parsed;
  }

  async evaluateClaim(
    req: TrustCalibrationClaimEvaluationRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<TrustCalibrationClaimEvaluation> {
    const claimText = (req?.claim_text ?? "").trim();
    if (!claimText) throw new Error("TrustClient.evaluateClaim requires req.claim_text");

    const requestedClaimStrength = safeString(req.requested_claim_strength, "").trim();
    const claimScope = safeString(req.claim_scope, "").trim();
    const body = {
      claim_text: claimText,
      claim_scope: claimScope || undefined,
      requested_claim_strength: requestedClaimStrength || undefined,
      evidence: isRecord(req.evidence) ? req.evidence : {},
    };

    const { json, res } = await this.fetchFirstOk(this.endpoints.claimEvaluation(), {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(body),
    });
    const parsed = parseTrustCalibrationClaimEvaluation(json);
    if (!parsed) {
      throw new TrustApiError("Invalid trust calibration claim evaluation response.", {
        status: res.status,
      });
    }
    if (!parsed.ok) {
      throw new TrustApiError(parsed.reason || parsed.status || "Trust calibration claim evaluation failed.", {
        status: res.status,
      });
    }
    return parsed;
  }

  async getTrustCalibrationCompletionReview(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<TrustCalibrationCompletionReview> {
    const { json, res } = await this.fetchFirstOk(this.endpoints.completionReview(), this.init(opts));
    const parsed = parseTrustCalibrationCompletionReview(json);
    if (!parsed) {
      throw new TrustApiError("Invalid trust calibration completion review response.", {
        status: res.status,
      });
    }
    if (!parsed.ok) {
      throw new TrustApiError(parsed.status || "Trust calibration completion review failed.", {
        status: res.status,
      });
    }
    return parsed;
  }

  async getTrustCalibrationStageClosureDecisions(
    params?: { limit?: number },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<TrustCalibrationStageClosureDecisionReadback> {
    const limit = typeof params?.limit === "number" ? clamp(Math.floor(params.limit), 1, 100) : 20;
    const { json, res } = await this.fetchFirstOk(this.endpoints.stageClosureDecisions({ limit }), this.init(opts));
    const parsed = parseTrustCalibrationStageClosureDecisionReadback(json);
    if (!parsed) {
      throw new TrustApiError("Invalid trust calibration stage closure decision response.", {
        status: res.status,
      });
    }
    if (!parsed.ok) {
      throw new TrustApiError(parsed.status || "Trust calibration stage closure decision readback failed.", {
        status: res.status,
      });
    }
    return parsed;
  }

  async adjust(
    req: TrustAdjustRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<TrustAdjustResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("TrustClient.adjust is disabled (mutationsEnabled=false).");
    }

    const op = (req?.op || "").trim();
    if (!op) throw new Error("TrustClient.adjust requires req.op");

    const candidates = this.endpoints.adjust();
    const body = { ...req, actor: req.actor?.trim() || DEFAULT_TRUST_MUTATION_ACTOR };
    const { json, res } = await this.fetchFirstOk(candidates, {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(body),
    });

    if (!isRecord(json)) return { ok: true };
    if (safeBool((json as Record<string, unknown>).ok, true) === false) {
      throw new TrustApiError(
        safeString((json as Record<string, unknown>).error, "") ||
          safeString((json as Record<string, unknown>).message, "") ||
          "Trust mutation failed.",
        {
          status: res.status,
        },
      );
    }

    return {
      ok: safeBool((json as Record<string, unknown>).ok, true),
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      applied: safeBool((json as Record<string, unknown>).applied, false),
      level: Number.isFinite(safeNumber((json as Record<string, unknown>).level, NaN))
        ? safeNumber((json as Record<string, unknown>).level, NaN)
        : undefined,
      ts: normalizeUnixSeconds((json as Record<string, unknown>).ts),
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      meta: isRecord((json as Record<string, unknown>).meta) ? ((json as Record<string, unknown>).meta as Record<string, unknown>) : undefined,
    };
  }
}

/* -------------------------------------------------------------------------------------------------
 * UI helpers (still framework-agnostic)
 * ------------------------------------------------------------------------------------------------- */

export type TrustCalibrationUiSignal = "confirmed" | "likely" | "uncertain" | "blocked" | "missing";

export type TrustCalibrationPresentation = {
  signal: TrustCalibrationUiSignal;
  badge_status: "ready" | "running" | "dormant" | "blocked";
  badge_label: string;
  headline: string;
  detail: string;
  surface_obligation: string;
  citation_obligation: string;
  next_smallest_truthful_gap: string;
  missing_verification: string[];
  allowed_surface_language: string[];
  forbidden_surface_language: string[];
  downgraded: boolean;
  runtime_claim_integration_ready: boolean;
  strong_claim_allowed: boolean;
  blocked_claim_required: boolean;
  must_name_missing_verification: boolean;
  side_effects_denied: boolean;
};

export function trustCalibrationUiSignal(
  evaluation?: TrustCalibrationClaimEvaluation | null,
): TrustCalibrationUiSignal {
  if (!evaluation) return "missing";

  const strength = safeString(evaluation.claim_strength, "").trim().toLowerCase();
  if (strength === "confirmed" || strength === "likely" || strength === "uncertain" || strength === "blocked") {
    return strength;
  }

  const uiState = safeString(evaluation.ui_state, "").trim().toLowerCase();
  if (uiState.includes("blocked")) return "blocked";
  if (uiState.includes("cautious") || uiState.includes("likely")) return "likely";
  if (uiState.includes("uncertain") || uiState.includes("neutral")) return "uncertain";
  return "uncertain";
}

export function presentTrustCalibrationClaimEvaluation(
  evaluation?: TrustCalibrationClaimEvaluation | null,
): TrustCalibrationPresentation {
  const signal = trustCalibrationUiSignal(evaluation);
  if (!evaluation) {
    return {
      signal,
      badge_status: "dormant",
      badge_label: "not loaded",
      headline: "No calibration readback",
      detail: "The UI has no trust calibration evaluator response for this claim yet.",
      surface_obligation: "load_evaluator_readback_before_confidence_claim",
      citation_obligation: "none_until_readback_loaded",
      next_smallest_truthful_gap: "stage13_ui_state_coherence",
      missing_verification: ["trust_calibration_claim_evaluation"],
      allowed_surface_language: ["not evaluated"],
      forbidden_surface_language: ["done", "closed", "confirmed"],
      downgraded: false,
      runtime_claim_integration_ready: false,
      strong_claim_allowed: false,
      blocked_claim_required: false,
      must_name_missing_verification: true,
      side_effects_denied: true,
    };
  }

  const missingVerification = evaluation.missing_verification;
  const sideEffectsDenied =
    !evaluation.writes_memory &&
    !evaluation.writes_receipts &&
    !evaluation.changes_ui_confidence &&
    !evaluation.enforces_runtime_claims &&
    !evaluation.grants_execution_authority &&
    !evaluation.grants_mutation_authority;
  const badgeStatus =
    signal === "confirmed" ? "ready" : signal === "likely" ? "running" : signal === "blocked" ? "blocked" : "dormant";
  const headline =
    signal === "confirmed"
      ? "Confirmed by current evidence"
      : signal === "likely"
        ? "Likely with named verification gap"
        : signal === "blocked"
          ? "Blocked; progress claim denied"
          : "Uncertain; next check required";
  const detail =
    evaluation.reason ||
    evaluation.condition ||
    evaluation.surface_obligation ||
    evaluation.next_smallest_truthful_gap ||
    "No evaluator reason provided.";

  return {
    signal,
    badge_status: badgeStatus,
    badge_label: signal,
    headline,
    detail,
    surface_obligation: evaluation.surface_obligation,
    citation_obligation: evaluation.citation_obligation,
    next_smallest_truthful_gap: evaluation.next_smallest_truthful_gap,
    missing_verification: missingVerification,
    allowed_surface_language: evaluation.allowed_surface_language,
    forbidden_surface_language: evaluation.forbidden_surface_language,
    downgraded: evaluation.downgraded,
    runtime_claim_integration_ready: evaluation.runtime_claim_integration_ready,
    strong_claim_allowed: signal === "confirmed" && !evaluation.downgraded && missingVerification.length === 0,
    blocked_claim_required: signal === "blocked",
    must_name_missing_verification: missingVerification.length > 0,
    side_effects_denied: sideEffectsDenied,
  };
}

export function formatTrustLevel(level: number): string {
  if (!Number.isFinite(level)) return "—";
  // If looks like 0..1, display as percent too (without assuming it's required).
  if (level >= 0 && level <= 1) {
    return `${(level * 100).toFixed(1)}% (${level.toFixed(3)})`;
  }
  // Otherwise show numeric with reasonable precision.
  const abs = Math.abs(level);
  const digits = abs < 10 ? 3 : abs < 100 ? 2 : 1;
  return level.toFixed(digits);
}

export function toLocaleTime(tsSeconds?: number): string {
  if (!tsSeconds || !Number.isFinite(tsSeconds)) return "";
  const ms = tsSeconds > 10_000_000_000 ? tsSeconds : tsSeconds * 1000;
  return new Date(ms).toLocaleString();
}
