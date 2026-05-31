import type { OperationRecord } from "../operations";

export type TakeoverReceipt = {
  kind?: string;
  receipt_id?: string;
  session_id?: string;
  actor?: string;
  reason?: string;
  scope?: string;
  summary?: string;
  action?: string;
  goal?: string;
  operation_id?: string;
  operation_status?: string;
  trace_id?: string;
  run_id?: string;
  output_kind?: string;
  validation_outcome?: string;
  remaining_uncertainty?: string;
  next_recommendation?: string;
  control_transfer_receipt_id?: string;
  panic_stop_receipt_id?: string;
  latest_control_transfer_receipt_id?: string;
  stage8_closure_receipt_id?: string;
  control_transferred_back?: boolean;
  control_transfer_active?: boolean;
  revoked_control_transfer?: boolean;
  handback_required?: boolean;
  live_action_executed?: boolean;
  recorded_ts?: number;
  action_feed_operation_ids?: string[];
  changed_artifacts?: string[];
  trace_ids?: string[];
  run_ids?: string[];
};

export type TakeoverActionFeed = {
  ok?: boolean;
  status?: string;
  items: OperationRecord[];
  count?: number;
  limit?: number;
};

export type TakeoverStatusSnapshot = {
  ok: boolean;
  kind?: string;
  stage?: string;
  status?: string;
  stage8_closed_by_receipt?: boolean;
  stage8_latest_receipt_id?: string;
  control_mode?: {
    id?: string;
    label?: string;
    summary?: string;
  };
  pilot_indicator_visible?: boolean;
  control_transfer_ready?: boolean;
  control_transfer_active?: boolean;
  active_session_id?: string;
  latest_control_transfer_receipt?: TakeoverReceipt;
  latest_panic_stop_receipt?: TakeoverReceipt;
  latest_handback_summary_receipt?: TakeoverReceipt;
  latest_live_action_receipt?: TakeoverReceipt;
  panic_stop_ready?: boolean;
  handback_required?: boolean;
  handback_summary_ready?: boolean;
  live_delegated_action_ready?: boolean;
  action_feed?: TakeoverActionFeed;
  deliverables?: {
    control_transfer_flow?: boolean;
    live_action_feed?: boolean;
    panic_stop?: boolean;
    handback_summary?: boolean;
    pilot_visibility?: boolean;
    live_delegated_action_runtime?: boolean;
  };
  next_smallest_truthful_gap?: string;
};

export class TakeoverApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(message: string, opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown }) {
    super(message);
    this.name = "TakeoverApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.bodySnippet = opts?.bodySnippet;
    (this as Error & { cause?: unknown }).cause = opts?.cause;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function safeNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function safeBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function safeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeString(item).trim()).filter(Boolean);
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function encodeQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    const text = typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : "";
    if (text) search.set(key, text);
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

function parseReceipt(raw: unknown): TakeoverReceipt | undefined {
  if (!isRecord(raw) || !safeString(raw.receipt_id).trim()) return undefined;
  return {
    kind: safeString(raw.kind) || undefined,
    receipt_id: safeString(raw.receipt_id) || undefined,
    session_id: safeString(raw.session_id) || undefined,
    actor: safeString(raw.actor) || undefined,
    reason: safeString(raw.reason) || undefined,
    scope: safeString(raw.scope) || undefined,
    summary: safeString(raw.summary) || undefined,
    action: safeString(raw.action) || undefined,
    goal: safeString(raw.goal) || undefined,
    operation_id: safeString(raw.operation_id) || undefined,
    operation_status: safeString(raw.operation_status) || undefined,
    trace_id: safeString(raw.trace_id) || undefined,
    run_id: safeString(raw.run_id) || undefined,
    output_kind: safeString(raw.output_kind) || undefined,
    validation_outcome: safeString(raw.validation_outcome) || undefined,
    remaining_uncertainty: safeString(raw.remaining_uncertainty) || undefined,
    next_recommendation: safeString(raw.next_recommendation) || undefined,
    control_transfer_receipt_id: safeString(raw.control_transfer_receipt_id) || undefined,
    panic_stop_receipt_id: safeString(raw.panic_stop_receipt_id) || undefined,
    latest_control_transfer_receipt_id: safeString(raw.latest_control_transfer_receipt_id) || undefined,
    stage8_closure_receipt_id: safeString(raw.stage8_closure_receipt_id) || undefined,
    control_transferred_back: safeBoolean(raw.control_transferred_back),
    control_transfer_active: safeBoolean(raw.control_transfer_active),
    revoked_control_transfer: safeBoolean(raw.revoked_control_transfer),
    handback_required: safeBoolean(raw.handback_required),
    live_action_executed: safeBoolean(raw.live_action_executed),
    recorded_ts: safeNumber(raw.recorded_ts, Number.NaN) || undefined,
    action_feed_operation_ids: safeStringArray(raw.action_feed_operation_ids),
    changed_artifacts: safeStringArray(raw.changed_artifacts),
    trace_ids: safeStringArray(raw.trace_ids),
    run_ids: safeStringArray(raw.run_ids),
  };
}

function parseActionFeedItem(raw: unknown): OperationRecord | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id).trim();
  if (!id) return null;
  return {
    id,
    ts: Math.floor(safeNumber(raw.ts, Date.now() / 1000)),
    status: safeString(raw.status) || "unknown",
    name: safeString(raw.name) || undefined,
    actor: safeString(raw.actor) || undefined,
    mission_id: safeString(raw.mission_id) || undefined,
    trace_id: safeString(raw.trace_id) || undefined,
    run_id: safeString(raw.run_id) || undefined,
    artifact_dir: safeString(raw.artifact_dir) || undefined,
    meta: {
      objective: safeString(raw.objective) || undefined,
      result_status: safeString(raw.result_status) || undefined,
      orb_plane: "P7_EXECUTION",
    },
  };
}

function parseActionFeed(raw: unknown): TakeoverActionFeed {
  if (!isRecord(raw)) return { items: [] };
  const rawItems = Array.isArray(raw.items) ? raw.items : [];
  const items = rawItems.map(parseActionFeedItem).filter((item): item is OperationRecord => item !== null);
  return {
    ok: safeBoolean(raw.ok),
    status: safeString(raw.status) || undefined,
    items,
    count: safeNumber(raw.count, items.length),
    limit: safeNumber(raw.limit, 0) || undefined,
  };
}

export function parseTakeoverStatusSnapshot(raw: unknown): TakeoverStatusSnapshot {
  if (!isRecord(raw)) return { ok: false, action_feed: { items: [] } };
  const controlMode = isRecord(raw.control_mode) ? raw.control_mode : {};
  const deliverables = isRecord(raw.deliverables) ? raw.deliverables : {};
  return {
    ok: Boolean(raw.ok),
    kind: safeString(raw.kind) || undefined,
    stage: safeString(raw.stage) || undefined,
    status: safeString(raw.status) || undefined,
    stage8_closed_by_receipt: safeBoolean(raw.stage8_closed_by_receipt),
    stage8_latest_receipt_id: safeString(raw.stage8_latest_receipt_id) || undefined,
    control_mode: {
      id: safeString(controlMode.id) || undefined,
      label: safeString(controlMode.label) || undefined,
      summary: safeString(controlMode.summary) || undefined,
    },
    pilot_indicator_visible: safeBoolean(raw.pilot_indicator_visible),
    control_transfer_ready: safeBoolean(raw.control_transfer_ready),
    control_transfer_active: safeBoolean(raw.control_transfer_active),
    active_session_id: safeString(raw.active_session_id) || undefined,
    latest_control_transfer_receipt: parseReceipt(raw.latest_control_transfer_receipt),
    latest_panic_stop_receipt: parseReceipt(raw.latest_panic_stop_receipt),
    latest_handback_summary_receipt: parseReceipt(raw.latest_handback_summary_receipt),
    latest_live_action_receipt: parseReceipt(raw.latest_live_action_receipt),
    panic_stop_ready: safeBoolean(raw.panic_stop_ready),
    handback_required: safeBoolean(raw.handback_required),
    handback_summary_ready: safeBoolean(raw.handback_summary_ready),
    live_delegated_action_ready: safeBoolean(raw.live_delegated_action_ready),
    action_feed: parseActionFeed(raw.action_feed),
    deliverables: {
      control_transfer_flow: safeBoolean(deliverables.control_transfer_flow),
      live_action_feed: safeBoolean(deliverables.live_action_feed),
      panic_stop: safeBoolean(deliverables.panic_stop),
      handback_summary: safeBoolean(deliverables.handback_summary),
      pilot_visibility: safeBoolean(deliverables.pilot_visibility),
      live_delegated_action_runtime: safeBoolean(deliverables.live_delegated_action_runtime),
    },
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap) || undefined,
  };
}

async function readTextSnippet(res: Response, maxChars = 2048): Promise<string> {
  try {
    const text = await res.text();
    return text.length > maxChars ? `${text.slice(0, maxChars)}...` : text;
  } catch {
    return "";
  }
}

type TimeoutFetchInit = RequestInit & { timeoutMs?: number };

async function fetchJson(url: string, init?: TimeoutFetchInit): Promise<unknown> {
  const { timeoutMs = 20_000, signal: externalSignal, ...fetchInit } = init ?? {};
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId =
    timeoutMs > 0
      ? globalThis.setTimeout(() => {
          timedOut = true;
          controller.abort();
        }, timeoutMs)
      : null;
  const onExternalAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) onExternalAbort();
    else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }
  try {
    const headers = new Headers(fetchInit.headers ?? undefined);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    const response = await fetch(url, { ...fetchInit, headers, signal: controller.signal });
    if (!response.ok) {
      const snippet = await readTextSnippet(response);
      throw new TakeoverApiError(`HTTP ${response.status} for takeover request`, {
        status: response.status,
        url,
        bodySnippet: snippet,
      });
    }
    return await response.json();
  } catch (err) {
    if (timedOut) throw new TakeoverApiError(`Timeout after ${timeoutMs}ms`, { url, cause: err });
    throw err;
  } finally {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
    if (externalSignal && !externalSignal.aborted) externalSignal.removeEventListener("abort", onExternalAbort);
  }
}

export class TakeoverClient {
  readonly baseUrl: string;
  readonly defaultTimeoutMs: number;

  constructor(baseUrl: string, opts?: { timeoutMs?: number }) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    this.defaultTimeoutMs = opts?.timeoutMs ?? 20_000;
  }

  async getStatus(
    params?: { limit?: number },
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<TakeoverStatusSnapshot> {
    const url = `${this.baseUrl}/takeover/status${encodeQuery({ limit: params?.limit })}`;
    const json = await fetchJson(url, {
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });
    return parseTakeoverStatusSnapshot(json);
  }
}
