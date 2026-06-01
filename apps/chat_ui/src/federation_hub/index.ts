/**
 * Federation Hub module (UI).
 *
 * Framework-agnostic client + types for federation observability and governance-adjacent actions.
 *
 * Scope (UI-safe):
 *  - List federation instances (membership)
 *  - Get instance detail (metadata + health + capabilities)
 *  - Batch instance get (client-side fan-out; no new backend contract)
 *  - List delegations (who delegated what to whom)
 *  - List consensus logs (audit trail) with optional date range filtering
 *  - List shared knowledge metadata (no raw secrets)
 *
 * Non-goals:
 *  - No React imports
 *  - No direct secret handling
 *  - No direct remote "execute" or "health check action" from browser
 *
 * Endpoints:
 *  - Defaults are conventional and can be overridden via options to match backend contracts.
 */

export type FederationInstanceStatus =
  | "online"
  | "offline"
  | "degraded"
  | "joining"
  | "leaving"
  | "banned"
  | "unknown"
  | string;

export type FederationCapability =
  | "api"
  | "daemon"
  | "workers"
  | "memory"
  | "vectorstore"
  | "web_learning"
  | "industrial"
  | "simulation"
  | "plugins"
  | string;

export type FederationInstance = {
  id: string;
  name?: string;

  status?: FederationInstanceStatus;

  // Network/identity
  endpoint?: string; // e.g., https://host:port (metadata only)
  region?: string;
  role?: string;

  // Timestamps (unix seconds preferred; ms tolerated by consumers)
  first_seen_ts?: number;
  last_seen_ts?: number;

  // Capability surface (metadata)
  capabilities?: FederationCapability[];

  // Governance hints
  trust_level?: number;
  requires_approval?: boolean;

  // Forward-compatible metadata
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type FederationInstanceDetail = FederationInstance & {
  // Optional health/status summary bags
  health?: Record<string, unknown>;
  inventory?: Record<string, unknown>;
};

export type FederationDelegationStatus = "pending" | "active" | "revoked" | "expired" | string;

export type FederationDelegation = {
  id: string;
  ts: number;

  from?: string;
  to?: string;

  scope?: string; // delegation scope label
  status?: FederationDelegationStatus;

  reason?: string;

  // Forward-compatible metadata
  meta?: Record<string, unknown>;
};

export type ConsensusLogLevel = "info" | "warning" | "error" | "critical" | string;

export type ConsensusLogEntry = {
  id?: string;
  ts: number;

  level?: ConsensusLogLevel;
  kind?: string;

  instance_id?: string;
  term?: number;
  index?: number;

  message?: string;

  // Forward-compatible payload
  meta?: Record<string, unknown>;
};

export type SharedKnowledgeKind = "document" | "fact" | "schema" | "policy" | "embedding_set" | string;

export type SharedKnowledgeItem = {
  id: string;
  ts?: number;

  kind?: SharedKnowledgeKind;
  title?: string;

  // Provenance
  source_instance_id?: string;
  domain?: string;

  // Forward-compatible metadata (never secrets)
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type FederationStage16Status = {
  ok: boolean;
  status?: string;
  stage?: string;
  stage16_status?: string;
  stage16_completion_review_ready: boolean;
  live_runtime_readback_ready: boolean;
  completion_review_blockers: string[];
  sleep_continuity_status?: string;
  sleep_continuity_ready: boolean;
  pre_sleep_evidence_ready: boolean;
  post_resume_evidence_ready: boolean;
  latest_pre_sleep_evidence?: Record<string, unknown>;
  latest_post_resume_evidence?: Record<string, unknown>;
  sleep_continuity_next_step?: string;
  ready_count: number;
  required_count: number;
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationLiveRuntimeReadbackCheck = {
  id: string;
  passed: boolean;
  receipt_ready: boolean;
  completion_evidence: boolean;
  status?: string;
  receipt_id?: string;
  proof_kind?: string;
  source_node_id?: string;
  paired_node_id?: string;
  trace_id?: string;
  evidence?: string;
};

export type FederationLiveRuntimeReadbacks = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  count: number;
  receipt_ready_count: number;
  ready_count: number;
  required_count: number;
  completion_eligible_readback_count: number;
  readback_receipts_ready: boolean;
  live_runtime_readback_ready: boolean;
  missing_readbacks: string[];
  checks: FederationLiveRuntimeReadbackCheck[];
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationCompletionReview = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  contract_readiness_ready: boolean;
  live_runtime_readback_ready: boolean;
  stage16_completion_review_ready: boolean;
  ready_to_close: boolean;
  stage_closure_decision_required: boolean;
  blockers: string[];
  ready_count: number;
  required_count: number;
  live_ready_count: number;
  live_required_count: number;
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationStage16ClosureReceipt = {
  receipt_id: string;
  actor?: string;
  decision?: string;
  completion_review_ready: boolean;
  stage16_completion_review_ready: boolean;
  live_runtime_readback_ready: boolean;
  stage16_closed_by_receipt: boolean;
  recorded_ts?: number;
};

export type FederationStage16ClosureDecisions = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  count: number;
  total: number;
  latest_receipt_id?: string;
  latest_decision?: string;
  receipt_readback_ready: boolean;
  stage16_closed_by_receipt: boolean;
  marks_runtime_stage_state: boolean;
  reads_receipts: boolean;
  writes_receipts: boolean;
  writes_registry: boolean;
  writes_memory: boolean;
  runs_tools: boolean;
  runs_shell: boolean;
  runs_git: boolean;
  launches_browser: boolean;
  captures_screen: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  latest_receipt?: FederationStage16ClosureReceipt;
  items: FederationStage16ClosureReceipt[];
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepContinuityRunbookStep = {
  id: string;
  title?: string;
  command?: string;
  latest_evidence_path?: string;
  method?: string;
  route?: string;
  required_scope?: string;
  expected_output?: string;
  pre_sleep_evidence_required: boolean;
  pre_sleep_evidence_available: boolean;
  post_resume_evidence_required: boolean;
  post_resume_evidence_available: boolean;
  operator_action_required: boolean;
  operator_confirmation_required: boolean;
  writes_evidence_when_run: boolean;
  writes_receipts_when_run: boolean;
  payload_contract?: Record<string, unknown>;
};

export type FederationSleepContinuityRunbook = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  runbook_only: boolean;
  prerequisite_readback_ids: string[];
  prerequisite_readbacks_ready: boolean;
  sleep_continuity_readback_id?: string;
  sleep_continuity_ready: boolean;
  pre_sleep_evidence?: Record<string, unknown>;
  pre_sleep_evidence_ready: boolean;
  post_resume_evidence?: Record<string, unknown>;
  post_resume_evidence_ready: boolean;
  ready_to_close: boolean;
  stage16_closed_by_receipt: boolean;
  missing_readbacks: string[];
  current_readback?: Record<string, unknown>;
  completion_review?: Record<string, unknown>;
  stage_closure_decision?: Record<string, unknown>;
  steps: FederationSleepContinuityRunbookStep[];
  writes_evidence: boolean;
  writes_receipts: boolean;
  writes_registry: boolean;
  writes_memory: boolean;
  runs_tools: boolean;
  runs_shell: boolean;
  runs_git: boolean;
  launches_browser: boolean;
  captures_screen: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  marks_stage16_closed: boolean;
  routes: Record<string, string>;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepContinuityActionState =
  | "blocked_on_prior_live_readbacks"
  | "capture_pre_sleep_evidence"
  | "capture_post_resume_evidence"
  | "run_sleep_continuity_runtime_proof"
  | "record_stage16_closure_decision"
  | "stage16_closed";

export type FederationSleepContinuityPresentation = {
  state: FederationSleepContinuityActionState;
  status_label: string;
  selected_step_id?: string;
  primary_command?: string;
  primary_route?: string;
  method?: string;
  required_scope?: string;
  evidence_path?: string;
  blockers: string[];
  pre_sleep_evidence_ready: boolean;
  post_resume_evidence_ready: boolean;
  sleep_continuity_ready: boolean;
  ready_to_close: boolean;
  stage16_closed_by_receipt: boolean;
  operator_action_required: boolean;
  operator_confirmation_required: boolean;
  writes_evidence_when_run: boolean;
  writes_receipts_when_run: boolean;
  mutation_available_from_ui: boolean;
  next_smallest_truthful_gap?: string;
};

export type FederationSleepContinuityActionReadback = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: FederationSleepContinuityActionState | string;
  action_projection_only: boolean;
  selected_step_id?: string;
  selected_action?: FederationSleepContinuityRunbookStep;
  primary_command?: string;
  primary_route?: string;
  method?: string;
  required_scope?: string;
  evidence_path?: string;
  blockers: string[];
  prior_live_readback_blockers: string[];
  pre_sleep_evidence_ready: boolean;
  post_resume_evidence_ready: boolean;
  sleep_continuity_ready: boolean;
  ready_to_close: boolean;
  stage16_closed_by_receipt: boolean;
  operator_action_required: boolean;
  operator_confirmation_required: boolean;
  writes_evidence_when_run: boolean;
  writes_receipts_when_run: boolean;
  mutation_available_from_ui: boolean;
  writes_evidence: boolean;
  writes_receipts: boolean;
  writes_registry: boolean;
  writes_memory: boolean;
  runs_tools: boolean;
  runs_shell: boolean;
  runs_git: boolean;
  launches_browser: boolean;
  captures_screen: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  marks_stage16_closed: boolean;
  routes: Record<string, string>;
  governance?: Record<string, unknown>;
  next_smallest_truthful_gap?: string;
};

export type FederationListResponse<T> = { items: T[] };

export class FederationApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "FederationApiError";
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

function optionalString(v: unknown): string | undefined {
  const text = safeString(v);
  return text || undefined;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeTs(ts: number): number {
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : ts;
}

function safeBoolean(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function stringList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map((x) => safeString(x)).filter((x) => x.length > 0);
}

function stringRecord(v: unknown): Record<string, string> {
  if (!isRecord(v)) return {};
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(v)) {
    const safeKey = safeString(key);
    const safeValue = safeString(value);
    if (safeKey && safeValue) out[safeKey] = safeValue;
  }
  return out;
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

async function readTextSnippet(res: Response, maxChars = 2048): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

type TimeoutMergedFetchInit = RequestInit & { timeoutMs?: number };

async function fetchWithTimeout(url: string, init?: TimeoutMergedFetchInit): Promise<Response> {
  const { timeoutMs = 20_000, signal: externalSignal, ...fetchInit } = init ?? {};

  const controller = new AbortController();

  let timeoutId: number | null = null;
  if (timeoutMs > 0) {
    timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  }

  const onExternalAbort = () => controller.abort();

  if (externalSignal) {
    if (externalSignal.aborted) onExternalAbort();
    else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }

  try {
    const headers = new Headers(fetchInit.headers ?? undefined);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (fetchInit.body !== undefined && fetchInit.body !== null) {
      if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    }

    return await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new FederationApiError("Federation request aborted/timed out", { url, cause: err });
    }
    throw new FederationApiError("Federation request failed", { url, cause: err });
  } finally {
    if (timeoutId !== null) window.clearTimeout(timeoutId);
    if (externalSignal && !externalSignal.aborted) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

async function fetchJson(url: string, init?: TimeoutMergedFetchInit): Promise<unknown> {
  const res = await fetchWithTimeout(url, init);

  if (!res.ok) {
    const snippet = await readTextSnippet(res);
    throw new FederationApiError(`HTTP ${res.status} for federation request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  return await res.json();
}

function parseInstance(raw: unknown): FederationInstance | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, safeString(raw.instance_id, ""));
  if (!id) return null;

  const inst: FederationInstance = { id };

  const name = safeString(raw.name, "");
  if (name) inst.name = name;

  const status = safeString(raw.status, "");
  if (status) inst.status = status;

  const endpoint = safeString(raw.endpoint, safeString(raw.url, ""));
  if (endpoint) inst.endpoint = endpoint;

  const region = safeString(raw.region, "");
  if (region) inst.region = region;

  const role = safeString(raw.role, "");
  if (role) inst.role = role;

  const firstSeen = safeNumber(raw.first_seen_ts, 0);
  if (firstSeen > 0) inst.first_seen_ts = normalizeTs(firstSeen);

  const lastSeen = safeNumber(raw.last_seen_ts, 0);
  if (lastSeen > 0) inst.last_seen_ts = normalizeTs(lastSeen);

  if (Array.isArray(raw.capabilities)) {
    const caps = (raw.capabilities as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (caps.length) inst.capabilities = caps;
  }

  const trust = safeNumber(raw.trust_level, NaN);
  if (Number.isFinite(trust)) inst.trust_level = trust;

  if (typeof raw.requires_approval === "boolean") inst.requires_approval = raw.requires_approval;

  if (Array.isArray(raw.tags)) {
    const tags = (raw.tags as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (tags.length) inst.tags = tags;
  }

  if (isRecord(raw.meta)) inst.meta = raw.meta;

  return inst;
}

function parseInstanceDetail(raw: unknown): FederationInstanceDetail | null {
  if (!isRecord(raw)) return null;

  const baseRaw = isRecord(raw.item) ? raw.item : raw;
  const base = parseInstance(baseRaw);
  if (!base) return null;

  const detail: FederationInstanceDetail = { ...base };

  const health = (raw as Record<string, unknown>).health;
  if (isRecord(health)) detail.health = health;

  const inventory = (raw as Record<string, unknown>).inventory;
  if (isRecord(inventory)) detail.inventory = inventory;

  return detail;
}

function parseDelegation(raw: unknown): FederationDelegation | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const ts = safeNumber(raw.ts, safeNumber(raw.created_ts, 0));
  const d: FederationDelegation = { id, ts: ts ? normalizeTs(ts) : 0 };

  const from = safeString(raw.from, safeString(raw.from_instance_id, ""));
  if (from) d.from = from;

  const to = safeString(raw.to, safeString(raw.to_instance_id, ""));
  if (to) d.to = to;

  const scope = safeString(raw.scope, safeString(raw.scope_id, ""));
  if (scope) d.scope = scope;

  const status = safeString(raw.status, "");
  if (status) d.status = status;

  const reason = safeString(raw.reason, "");
  if (reason) d.reason = reason;

  if (isRecord(raw.meta)) d.meta = raw.meta;

  return d;
}

function parseConsensusLog(raw: unknown): ConsensusLogEntry | null {
  if (!isRecord(raw)) return null;

  const ts = safeNumber(raw.ts, safeNumber(raw.created_ts, 0));
  if (!ts) return null;

  const e: ConsensusLogEntry = { ts: normalizeTs(ts) };

  const id = safeString(raw.id, "");
  if (id) e.id = id;

  const level = safeString(raw.level, safeString(raw.severity, ""));
  if (level) e.level = level;

  const kind = safeString(raw.kind, "");
  if (kind) e.kind = kind;

  const instanceId = safeString(raw.instance_id, "");
  if (instanceId) e.instance_id = instanceId;

  const term = safeNumber(raw.term, NaN);
  if (Number.isFinite(term)) e.term = term;

  const index = safeNumber(raw.index, NaN);
  if (Number.isFinite(index)) e.index = index;

  const msg = safeString(raw.message, safeString(raw.msg, ""));
  if (msg) e.message = msg;

  if (isRecord(raw.meta)) e.meta = raw.meta;

  return e;
}

function parseSharedKnowledge(raw: unknown): SharedKnowledgeItem | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const item: SharedKnowledgeItem = { id };

  const ts = safeNumber(raw.ts, safeNumber(raw.created_ts, 0));
  if (ts > 0) item.ts = normalizeTs(ts);

  const kind = safeString(raw.kind, "");
  if (kind) item.kind = kind;

  const title = safeString(raw.title, safeString(raw.name, ""));
  if (title) item.title = title;

  const src = safeString(raw.source_instance_id, safeString(raw.source, ""));
  if (src) item.source_instance_id = src;

  const domain = safeString(raw.domain, "");
  if (domain) item.domain = domain;

  if (Array.isArray(raw.tags)) {
    const tags = (raw.tags as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (tags.length) item.tags = tags;
  }

  if (isRecord(raw.meta)) item.meta = raw.meta;

  return item;
}

export function parseFederationStage16Status(raw: unknown): FederationStage16Status {
  const body = isRecord(raw) ? raw : {};
  return {
    ok: safeBoolean(body.ok),
    status: optionalString(body.status),
    stage: optionalString(body.stage),
    stage16_status: optionalString(body.stage16_status),
    stage16_completion_review_ready: safeBoolean(body.stage16_completion_review_ready),
    live_runtime_readback_ready: safeBoolean(body.live_runtime_readback_ready),
    completion_review_blockers: stringList(body.completion_review_blockers),
    sleep_continuity_status: optionalString(body.sleep_continuity_status),
    sleep_continuity_ready: safeBoolean(body.sleep_continuity_ready),
    pre_sleep_evidence_ready: safeBoolean(body.pre_sleep_evidence_ready),
    post_resume_evidence_ready: safeBoolean(body.post_resume_evidence_ready),
    latest_pre_sleep_evidence: isRecord(body.latest_pre_sleep_evidence)
      ? body.latest_pre_sleep_evidence
      : undefined,
    latest_post_resume_evidence: isRecord(body.latest_post_resume_evidence)
      ? body.latest_post_resume_evidence
      : undefined,
    sleep_continuity_next_step: optionalString(body.sleep_continuity_next_step),
    ready_count: safeNumber(body.ready_count, 0),
    required_count: safeNumber(body.required_count, 0),
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function parseLiveRuntimeReadbackCheck(raw: unknown): FederationLiveRuntimeReadbackCheck | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id);
  if (!id) return null;
  return {
    id,
    passed: safeBoolean(raw.passed),
    receipt_ready: safeBoolean(raw.receipt_ready),
    completion_evidence: safeBoolean(raw.completion_evidence),
    status: optionalString(raw.status),
    receipt_id: optionalString(raw.receipt_id),
    proof_kind: optionalString(raw.proof_kind),
    source_node_id: optionalString(raw.source_node_id),
    paired_node_id: optionalString(raw.paired_node_id),
    trace_id: optionalString(raw.trace_id),
    evidence: optionalString(raw.evidence),
  };
}

export function parseFederationLiveRuntimeReadbacks(raw: unknown): FederationLiveRuntimeReadbacks {
  const body = isRecord(raw) ? raw : {};
  const checks = Array.isArray(body.checks)
    ? body.checks.map(parseLiveRuntimeReadbackCheck).filter((x): x is FederationLiveRuntimeReadbackCheck => x !== null)
    : [];
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    count: safeNumber(body.count, 0),
    receipt_ready_count: safeNumber(body.receipt_ready_count, 0),
    ready_count: safeNumber(body.ready_count, 0),
    required_count: safeNumber(body.required_count, 0),
    completion_eligible_readback_count: safeNumber(body.completion_eligible_readback_count, 0),
    readback_receipts_ready: safeBoolean(body.readback_receipts_ready),
    live_runtime_readback_ready: safeBoolean(body.live_runtime_readback_ready),
    missing_readbacks: stringList(body.missing_readbacks),
    checks,
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

export function parseFederationCompletionReview(raw: unknown): FederationCompletionReview {
  const body = isRecord(raw) ? raw : {};
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    contract_readiness_ready: safeBoolean(body.contract_readiness_ready),
    live_runtime_readback_ready: safeBoolean(body.live_runtime_readback_ready),
    stage16_completion_review_ready: safeBoolean(body.stage16_completion_review_ready),
    ready_to_close: safeBoolean(body.ready_to_close),
    stage_closure_decision_required: safeBoolean(body.stage_closure_decision_required),
    blockers: stringList(body.blockers),
    ready_count: safeNumber(body.ready_count, 0),
    required_count: safeNumber(body.required_count, 0),
    live_ready_count: safeNumber(body.live_ready_count, 0),
    live_required_count: safeNumber(body.live_required_count, 0),
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function parseFederationStage16ClosureReceipt(raw: unknown): FederationStage16ClosureReceipt | null {
  if (!isRecord(raw)) return null;
  const receiptId = safeString(raw.receipt_id);
  if (!receiptId) return null;
  const recordedTs = safeNumber(raw.recorded_ts, 0);
  return {
    receipt_id: receiptId,
    actor: optionalString(raw.actor),
    decision: optionalString(raw.decision),
    completion_review_ready: safeBoolean(raw.completion_review_ready),
    stage16_completion_review_ready: safeBoolean(raw.stage16_completion_review_ready),
    live_runtime_readback_ready: safeBoolean(raw.live_runtime_readback_ready),
    stage16_closed_by_receipt: safeBoolean(raw.stage16_closed_by_receipt),
    recorded_ts: recordedTs > 0 ? normalizeTs(recordedTs) : undefined,
  };
}

export function parseFederationStage16ClosureDecisions(raw: unknown): FederationStage16ClosureDecisions {
  const body = isRecord(raw) ? raw : {};
  const items = Array.isArray(body.items)
    ? body.items
        .map(parseFederationStage16ClosureReceipt)
        .filter((x): x is FederationStage16ClosureReceipt => x !== null)
    : [];
  const latestReceipt = parseFederationStage16ClosureReceipt(body.latest_receipt);
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    count: safeNumber(body.count, 0),
    total: safeNumber(body.total, 0),
    latest_receipt_id: optionalString(body.latest_receipt_id),
    latest_decision: optionalString(body.latest_decision),
    receipt_readback_ready: safeBoolean(body.receipt_readback_ready),
    stage16_closed_by_receipt: safeBoolean(body.stage16_closed_by_receipt),
    marks_runtime_stage_state: safeBoolean(body.marks_runtime_stage_state),
    reads_receipts: safeBoolean(body.reads_receipts),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_registry: safeBoolean(body.writes_registry),
    writes_memory: safeBoolean(body.writes_memory),
    runs_tools: safeBoolean(body.runs_tools),
    runs_shell: safeBoolean(body.runs_shell),
    runs_git: safeBoolean(body.runs_git),
    launches_browser: safeBoolean(body.launches_browser),
    captures_screen: safeBoolean(body.captures_screen),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    latest_receipt: latestReceipt ?? undefined,
    items,
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function parseFederationSleepContinuityRunbookStep(raw: unknown): FederationSleepContinuityRunbookStep | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id);
  if (!id) return null;
  return {
    id,
    title: optionalString(raw.title),
    command: optionalString(raw.command),
    latest_evidence_path: optionalString(raw.latest_evidence_path),
    method: optionalString(raw.method),
    route: optionalString(raw.route),
    required_scope: optionalString(raw.required_scope),
    expected_output: optionalString(raw.expected_output),
    pre_sleep_evidence_required: safeBoolean(raw.pre_sleep_evidence_required),
    pre_sleep_evidence_available: safeBoolean(raw.pre_sleep_evidence_available),
    post_resume_evidence_required: safeBoolean(raw.post_resume_evidence_required),
    post_resume_evidence_available: safeBoolean(raw.post_resume_evidence_available),
    operator_action_required: safeBoolean(raw.operator_action_required),
    operator_confirmation_required: safeBoolean(raw.operator_confirmation_required),
    writes_evidence_when_run: safeBoolean(raw.writes_evidence_when_run),
    writes_receipts_when_run: safeBoolean(raw.writes_receipts_when_run),
    payload_contract: isRecord(raw.payload_contract) ? raw.payload_contract : undefined,
  };
}

export function parseFederationSleepContinuityRunbook(raw: unknown): FederationSleepContinuityRunbook {
  const body = isRecord(raw) ? raw : {};
  const steps = Array.isArray(body.steps)
    ? body.steps
        .map(parseFederationSleepContinuityRunbookStep)
        .filter((x): x is FederationSleepContinuityRunbookStep => x !== null)
    : [];
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    runbook_only: safeBoolean(body.runbook_only),
    prerequisite_readback_ids: stringList(body.prerequisite_readback_ids),
    prerequisite_readbacks_ready: safeBoolean(body.prerequisite_readbacks_ready),
    sleep_continuity_readback_id: optionalString(body.sleep_continuity_readback_id),
    sleep_continuity_ready: safeBoolean(body.sleep_continuity_ready),
    pre_sleep_evidence: isRecord(body.pre_sleep_evidence) ? body.pre_sleep_evidence : undefined,
    pre_sleep_evidence_ready: safeBoolean(body.pre_sleep_evidence_ready),
    post_resume_evidence: isRecord(body.post_resume_evidence) ? body.post_resume_evidence : undefined,
    post_resume_evidence_ready: safeBoolean(body.post_resume_evidence_ready),
    ready_to_close: safeBoolean(body.ready_to_close),
    stage16_closed_by_receipt: safeBoolean(body.stage16_closed_by_receipt),
    missing_readbacks: stringList(body.missing_readbacks),
    current_readback: isRecord(body.current_readback) ? body.current_readback : undefined,
    completion_review: isRecord(body.completion_review) ? body.completion_review : undefined,
    stage_closure_decision: isRecord(body.stage_closure_decision) ? body.stage_closure_decision : undefined,
    steps,
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_registry: safeBoolean(body.writes_registry),
    writes_memory: safeBoolean(body.writes_memory),
    runs_tools: safeBoolean(body.runs_tools),
    runs_shell: safeBoolean(body.runs_shell),
    runs_git: safeBoolean(body.runs_git),
    launches_browser: safeBoolean(body.launches_browser),
    captures_screen: safeBoolean(body.captures_screen),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    routes: stringRecord(body.routes),
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

export function parseFederationSleepContinuityAction(raw: unknown): FederationSleepContinuityActionReadback {
  const body = isRecord(raw) ? raw : {};
  const selectedAction = parseFederationSleepContinuityRunbookStep(body.selected_action);
  return {
    ok: safeBoolean(body.ok),
    kind: optionalString(body.kind),
    stage: optionalString(body.stage),
    status: optionalString(body.status),
    action_projection_only: safeBoolean(body.action_projection_only),
    selected_step_id: optionalString(body.selected_step_id),
    selected_action: selectedAction ?? undefined,
    primary_command: optionalString(body.primary_command),
    primary_route: optionalString(body.primary_route),
    method: optionalString(body.method),
    required_scope: optionalString(body.required_scope),
    evidence_path: optionalString(body.evidence_path),
    blockers: stringList(body.blockers),
    prior_live_readback_blockers: stringList(body.prior_live_readback_blockers),
    pre_sleep_evidence_ready: safeBoolean(body.pre_sleep_evidence_ready),
    post_resume_evidence_ready: safeBoolean(body.post_resume_evidence_ready),
    sleep_continuity_ready: safeBoolean(body.sleep_continuity_ready),
    ready_to_close: safeBoolean(body.ready_to_close),
    stage16_closed_by_receipt: safeBoolean(body.stage16_closed_by_receipt),
    operator_action_required: safeBoolean(body.operator_action_required),
    operator_confirmation_required: safeBoolean(body.operator_confirmation_required),
    writes_evidence_when_run: safeBoolean(body.writes_evidence_when_run),
    writes_receipts_when_run: safeBoolean(body.writes_receipts_when_run),
    mutation_available_from_ui: safeBoolean(body.mutation_available_from_ui),
    writes_evidence: safeBoolean(body.writes_evidence),
    writes_receipts: safeBoolean(body.writes_receipts),
    writes_registry: safeBoolean(body.writes_registry),
    writes_memory: safeBoolean(body.writes_memory),
    runs_tools: safeBoolean(body.runs_tools),
    runs_shell: safeBoolean(body.runs_shell),
    runs_git: safeBoolean(body.runs_git),
    launches_browser: safeBoolean(body.launches_browser),
    captures_screen: safeBoolean(body.captures_screen),
    grants_execution_authority: safeBoolean(body.grants_execution_authority),
    grants_mutation_authority: safeBoolean(body.grants_mutation_authority),
    marks_stage16_closed: safeBoolean(body.marks_stage16_closed),
    routes: stringRecord(body.routes),
    governance: isRecord(body.governance) ? body.governance : undefined,
    next_smallest_truthful_gap: optionalString(body.next_smallest_truthful_gap),
  };
}

function findFederationSleepContinuityStep(
  runbook: FederationSleepContinuityRunbook | undefined,
  id: string,
): FederationSleepContinuityRunbookStep | undefined {
  return runbook?.steps.find((step) => step.id === id);
}

function singleSleepContinuityBlocker(blockers: string[]): boolean {
  return blockers.length === 1 && blockers[0] === "workstation_sleep_continuity_validated";
}

function hasPriorLiveReadbackBlocker(blockers: string[]): boolean {
  return blockers.some((blocker) => blocker !== "workstation_sleep_continuity_validated");
}

const federationSleepContinuityLabelByState: Record<FederationSleepContinuityActionState, string> = {
  blocked_on_prior_live_readbacks: "Blocked on prior live readbacks",
  capture_pre_sleep_evidence: "Capture pre-sleep evidence",
  capture_post_resume_evidence: "Capture post-resume evidence",
  run_sleep_continuity_runtime_proof: "Run sleep-continuity runtime proof",
  record_stage16_closure_decision: "Record Stage 16 closure decision",
  stage16_closed: "Stage 16 closed by receipt",
};

function federationSleepContinuityActionState(value: unknown): FederationSleepContinuityActionState {
  const state = safeString(value);
  if (state in federationSleepContinuityLabelByState) return state as FederationSleepContinuityActionState;
  return "blocked_on_prior_live_readbacks";
}

function labelForFederationSleepContinuityState(state: FederationSleepContinuityActionState): string {
  return federationSleepContinuityLabelByState[state];
}

function buildFederationSleepContinuityPresentation(
  state: FederationSleepContinuityActionState,
  opts: {
    status: FederationStage16Status;
    runbook?: FederationSleepContinuityRunbook;
    closure?: FederationStage16ClosureDecisions;
    selectedStep?: FederationSleepContinuityRunbookStep;
    blockers: string[];
    preSleepEvidenceReady: boolean;
    postResumeEvidenceReady: boolean;
    sleepContinuityReady: boolean;
    readyToClose: boolean;
    stage16ClosedByReceipt: boolean;
  },
): FederationSleepContinuityPresentation {
  const selectedStep = opts.selectedStep;
  return {
    state,
    status_label: labelForFederationSleepContinuityState(state),
    selected_step_id: selectedStep?.id,
    primary_command: selectedStep?.command,
    primary_route: selectedStep?.route,
    method: selectedStep?.method,
    required_scope: selectedStep?.required_scope,
    evidence_path: selectedStep?.latest_evidence_path,
    blockers: opts.blockers,
    pre_sleep_evidence_ready: opts.preSleepEvidenceReady,
    post_resume_evidence_ready: opts.postResumeEvidenceReady,
    sleep_continuity_ready: opts.sleepContinuityReady,
    ready_to_close: opts.readyToClose,
    stage16_closed_by_receipt: opts.stage16ClosedByReceipt,
    operator_action_required: selectedStep?.operator_action_required ?? false,
    operator_confirmation_required: selectedStep?.operator_confirmation_required ?? false,
    writes_evidence_when_run: selectedStep?.writes_evidence_when_run ?? false,
    writes_receipts_when_run: selectedStep?.writes_receipts_when_run ?? false,
    mutation_available_from_ui: false,
    next_smallest_truthful_gap:
      opts.status.next_smallest_truthful_gap ??
      opts.runbook?.next_smallest_truthful_gap ??
      opts.closure?.next_smallest_truthful_gap,
  };
}

export function presentFederationSleepContinuity(
  status: FederationStage16Status,
  runbook?: FederationSleepContinuityRunbook,
  closure?: FederationStage16ClosureDecisions,
): FederationSleepContinuityPresentation {
  const preSleepEvidenceReady = status.pre_sleep_evidence_ready || runbook?.pre_sleep_evidence_ready === true;
  const postResumeEvidenceReady = status.post_resume_evidence_ready || runbook?.post_resume_evidence_ready === true;
  const sleepContinuityReady = status.sleep_continuity_ready || runbook?.sleep_continuity_ready === true;
  const readyToClose = status.stage16_completion_review_ready || runbook?.ready_to_close === true;
  const stage16ClosedByReceipt =
    closure?.stage16_closed_by_receipt === true ||
    runbook?.stage16_closed_by_receipt === true ||
    status.stage16_status === "stage16_closed_by_receipt";
  const blockers =
    status.completion_review_blockers.length > 0 ? status.completion_review_blockers : runbook?.missing_readbacks ?? [];

  let state: FederationSleepContinuityActionState = "blocked_on_prior_live_readbacks";
  let selectedStep: FederationSleepContinuityRunbookStep | undefined;
  if (stage16ClosedByReceipt) {
    state = "stage16_closed";
  } else if (hasPriorLiveReadbackBlocker(blockers)) {
    state = "blocked_on_prior_live_readbacks";
  } else if (readyToClose) {
    state = "record_stage16_closure_decision";
    selectedStep = findFederationSleepContinuityStep(runbook, "record_operator_stage_closure_decision");
  } else if (postResumeEvidenceReady) {
    state = "run_sleep_continuity_runtime_proof";
    selectedStep = findFederationSleepContinuityStep(runbook, "commit_sleep_continuity_readback");
  } else if (preSleepEvidenceReady) {
    state = "capture_post_resume_evidence";
    selectedStep = findFederationSleepContinuityStep(runbook, "capture_post_resume_evidence");
  } else if (singleSleepContinuityBlocker(blockers) || runbook?.status === "ready_for_operator_sleep_resume") {
    state = "capture_pre_sleep_evidence";
    selectedStep = findFederationSleepContinuityStep(runbook, "capture_pre_sleep_evidence");
  }

  return buildFederationSleepContinuityPresentation(state, {
    status,
    runbook,
    closure,
    selectedStep,
    blockers,
    preSleepEvidenceReady,
    postResumeEvidenceReady,
    sleepContinuityReady,
    readyToClose,
    stage16ClosedByReceipt,
  });
}

export function presentFederationSleepContinuityAction(
  action: FederationSleepContinuityActionReadback,
): FederationSleepContinuityPresentation {
  const state = federationSleepContinuityActionState(action.status);
  const selectedStep = action.selected_action;
  return {
    state,
    status_label: labelForFederationSleepContinuityState(state),
    selected_step_id: action.selected_step_id,
    primary_command: action.primary_command ?? selectedStep?.command,
    primary_route: action.primary_route ?? selectedStep?.route,
    method: action.method ?? selectedStep?.method,
    required_scope: action.required_scope ?? selectedStep?.required_scope,
    evidence_path: action.evidence_path ?? selectedStep?.latest_evidence_path,
    blockers: action.blockers,
    pre_sleep_evidence_ready: action.pre_sleep_evidence_ready,
    post_resume_evidence_ready: action.post_resume_evidence_ready,
    sleep_continuity_ready: action.sleep_continuity_ready,
    ready_to_close: action.ready_to_close,
    stage16_closed_by_receipt: action.stage16_closed_by_receipt,
    operator_action_required: action.operator_action_required || selectedStep?.operator_action_required === true,
    operator_confirmation_required:
      action.operator_confirmation_required || selectedStep?.operator_confirmation_required === true,
    writes_evidence_when_run: action.writes_evidence_when_run || selectedStep?.writes_evidence_when_run === true,
    writes_receipts_when_run: action.writes_receipts_when_run || selectedStep?.writes_receipts_when_run === true,
    mutation_available_from_ui: false,
    next_smallest_truthful_gap: action.next_smallest_truthful_gap,
  };
}

export type FederationEndpoints = {
  status: () => string;
  completionReview: () => string;
  sleepContinuityRunbook: () => string;
  sleepContinuityAction: () => string;
  stageClosureDecisions: (q?: { limit?: number }) => string;
  liveRuntimeReadbacks: (q?: { limit?: number }) => string;

  instancesList: (q?: { status?: string; limit?: number; offset?: number; tags?: string[] }) => string;
  instanceGet: (id: string) => string;

  delegationsList: (q?: { status?: string; limit?: number; offset?: number }) => string;

  consensusLogsList: (q?: {
    level?: string;
    instance_id?: string;
    limit?: number;
    offset?: number;
    start_ts?: number;
    end_ts?: number;
  }) => string;

  sharedKnowledgeList: (q?: { kind?: string; domain?: string; limit?: number; offset?: number; tags?: string[] }) => string;
};

export function defaultFederationEndpoints(): FederationEndpoints {
  return {
    status: () => "/federation/status",
    completionReview: () => "/federation/completion-review",
    sleepContinuityRunbook: () => "/federation/sleep-continuity-runbook",
    sleepContinuityAction: () => "/federation/sleep-continuity-action",
    stageClosureDecisions: (q) => `/federation/stage-closure-decisions${buildQuery({ limit: q?.limit })}`,
    liveRuntimeReadbacks: (q) => `/federation/live-runtime-readbacks${buildQuery({ limit: q?.limit })}`,

    instancesList: (q) =>
      `/federation/instances/list${buildQuery({
        status: q?.status,
        limit: q?.limit,
        offset: q?.offset,
        tags: q?.tags,
      })}`,
    instanceGet: (id) => `/federation/instances/get${buildQuery({ id })}`,

    delegationsList: (q) =>
      `/federation/delegations/list${buildQuery({
        status: q?.status,
        limit: q?.limit,
        offset: q?.offset,
      })}`,

    consensusLogsList: (q) =>
      `/federation/consensus_logs/list${buildQuery({
        level: q?.level,
        instance_id: q?.instance_id,
        limit: q?.limit,
        offset: q?.offset,
        start_ts: typeof q?.start_ts === "number" ? normalizeTs(q.start_ts) : undefined,
        end_ts: typeof q?.end_ts === "number" ? normalizeTs(q.end_ts) : undefined,
      })}`,

    sharedKnowledgeList: (q) =>
      `/federation/shared_knowledge/list${buildQuery({
        kind: q?.kind,
        domain: q?.domain,
        limit: q?.limit,
        offset: q?.offset,
        tags: q?.tags,
      })}`,
  };
}

export type FederationClientOptions = {
  endpoints?: FederationEndpoints;
  defaultTimeoutMs?: number;
};

export class FederationClient {
  readonly baseUrl: string;
  readonly endpoints: FederationEndpoints;
  readonly defaultTimeoutMs: number;

  constructor(baseUrl: string, opts?: FederationClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("FederationClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultFederationEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  async getStatus(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<FederationStage16Status> {
    const json = await fetchJson(this.url(this.endpoints.status()), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationStage16Status(json);
  }

  async getLiveRuntimeReadbacks(opts?: {
    limit?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationLiveRuntimeReadbacks> {
    const json = await fetchJson(this.url(this.endpoints.liveRuntimeReadbacks({ limit: opts?.limit })), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationLiveRuntimeReadbacks(json);
  }

  async getCompletionReview(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<FederationCompletionReview> {
    const json = await fetchJson(this.url(this.endpoints.completionReview()), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationCompletionReview(json);
  }

  async getSleepContinuityRunbook(opts?: {
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepContinuityRunbook> {
    const json = await fetchJson(this.url(this.endpoints.sleepContinuityRunbook()), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationSleepContinuityRunbook(json);
  }

  async getSleepContinuityAction(opts?: {
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepContinuityActionReadback> {
    const json = await fetchJson(this.url(this.endpoints.sleepContinuityAction()), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationSleepContinuityAction(json);
  }

  async getStageClosureDecisions(opts?: {
    limit?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationStage16ClosureDecisions> {
    const json = await fetchJson(this.url(this.endpoints.stageClosureDecisions({ limit: opts?.limit })), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseFederationStage16ClosureDecisions(json);
  }

  async getSleepContinuityPresentation(opts?: {
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationSleepContinuityPresentation> {
    const action = await this.getSleepContinuityAction(opts);
    return presentFederationSleepContinuityAction(action);
  }

  async listInstances(opts?: {
    status?: FederationInstanceStatus;
    limit?: number;
    offset?: number;
    tags?: string[];
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationListResponse<FederationInstance>> {
    const url = this.url(
      this.endpoints.instancesList({
        status: opts?.status as string | undefined,
        limit: opts?.limit,
        offset: opts?.offset,
        tags: opts?.tags,
      }),
    );

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).instances)
        ? ((json as Record<string, unknown>).instances as unknown[])
        : [];

    const items = raw.map(parseInstance).filter((x): x is FederationInstance => x !== null);
    return { items };
  }

  async getInstance(
    id: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<FederationInstanceDetail | null> {
    const safeId = (id || "").trim();
    if (!safeId) return null;

    const url = this.url(this.endpoints.instanceGet(safeId));
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    return parseInstanceDetail(json);
  }

  /**
   * Batch instance get (client-side fan-out).
   * No new backend contract required.
   *
   * - Dedupes ids
   * - Concurrency-limited
   * - Preserves original order; omits nulls
   */
  async getInstances(
    ids: string[],
    opts?: {
      signal?: AbortSignal;
      timeoutMs?: number;
      concurrency?: number;
      tolerateFailures?: boolean;
    },
  ): Promise<FederationInstanceDetail[]> {
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

    const resultMap = new Map<string, FederationInstanceDetail | null>();
    for (const id of unique) resultMap.set(id, null);

    let cursor = 0;
    const worker = async () => {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const i = cursor++;
        if (i >= unique.length) return;

        const id = unique[i];
        try {
          const d = await this.getInstance(id, { signal: opts?.signal, timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs });
          resultMap.set(id, d);
        } catch (err) {
          if (!tolerateFailures) throw err;
          resultMap.set(id, null);
        }
      }
    };

    await Promise.all(Array.from({ length: Math.min(concurrency, unique.length) }, () => worker()));

    const out: FederationInstanceDetail[] = [];
    for (const id of original) {
      const v = resultMap.get(id) ?? null;
      if (v) out.push(v);
    }
    return out;
  }

  async listDelegations(opts?: {
    status?: FederationDelegationStatus;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationListResponse<FederationDelegation>> {
    const url = this.url(
      this.endpoints.delegationsList({
        status: opts?.status as string | undefined,
        limit: opts?.limit,
        offset: opts?.offset,
      }),
    );

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).delegations)
        ? ((json as Record<string, unknown>).delegations as unknown[])
        : [];

    const items = raw.map(parseDelegation).filter((x): x is FederationDelegation => x !== null);
    return { items };
  }

  async listConsensusLogs(opts?: {
    level?: ConsensusLogLevel;
    instance_id?: string;
    start_ts?: number;
    end_ts?: number;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationListResponse<ConsensusLogEntry>> {
    const url = this.url(
      this.endpoints.consensusLogsList({
        level: opts?.level as string | undefined,
        instance_id: opts?.instance_id,
        start_ts: opts?.start_ts,
        end_ts: opts?.end_ts,
        limit: opts?.limit,
        offset: opts?.offset,
      }),
    );

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).logs)
        ? ((json as Record<string, unknown>).logs as unknown[])
        : [];

    const items = raw.map(parseConsensusLog).filter((x): x is ConsensusLogEntry => x !== null);
    return { items };
  }

  async listSharedKnowledge(opts?: {
    kind?: SharedKnowledgeKind;
    domain?: string;
    tags?: string[];
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<FederationListResponse<SharedKnowledgeItem>> {
    const url = this.url(
      this.endpoints.sharedKnowledgeList({
        kind: opts?.kind as string | undefined,
        domain: opts?.domain,
        tags: opts?.tags,
        limit: opts?.limit,
        offset: opts?.offset,
      }),
    );

    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).knowledge)
        ? ((json as Record<string, unknown>).knowledge as unknown[])
        : [];

    const items = raw.map(parseSharedKnowledge).filter((x): x is SharedKnowledgeItem => x !== null);
    return { items };
  }
}
