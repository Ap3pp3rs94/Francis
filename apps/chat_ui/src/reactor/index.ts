export type ReactorReviewRoute =
  | "approval_queue"
  | "deadletter_candidate"
  | "deadletter_escalation"
  | "deadletter_resolution"
  | "deadletter_review"
  | "operation_run"
  | "operator_review"
  | "retry_backoff"
  | "retry_candidate"
  | "retry_due"
  | "retry_exhausted"
  | string;

export type ReactorReviewTrigger = {
  source?: string;
  type?: string;
  summary?: string;
  mission_id?: string;
  operation_id?: string;
  approval_id?: string;
};

export type ReactorReviewClassification = {
  mode?: string;
  risk_tier?: string;
  action_class?: string;
  approval_required?: boolean;
};

export type ReactorReviewDetail = {
  route?: ReactorReviewRoute;
  status?: string;
  gate?: string;
  action?: string;
  next_step?: string;
  receipt_kind?: string;
  receipt_ref?: string;
  blocker_ref?: string;
  execution_started?: boolean;
  applied?: boolean;
};

export type ReactorReviewQueueItem = {
  event_id: string;
  status?: string;
  stable_state?: string;
  created_ts?: number;
  updated_ts?: number;
  trigger?: ReactorReviewTrigger;
  classification?: ReactorReviewClassification;
  review?: ReactorReviewDetail;
};

export type ReactorReviewQueueSnapshot = {
  ok: boolean;
  items: ReactorReviewQueueItem[];
  total: number;
  available_total: number;
  limit: number;
  route?: string;
  route_counts: Record<string, number>;
  stable_state_counts: Record<string, number>;
  governance?: Record<string, unknown>;
  error?: string;
};

export type ReactorReceiptSummary = {
  kind?: string;
  receipt_id?: string;
  deadletter_id?: string;
  event_id?: string;
  status?: string;
  route?: string;
  gate?: string;
  stable_state?: string;
  next_step?: string;
  review_decision?: string;
  resolution_decision?: string;
  deadletter_resolved?: boolean;
  escalation_recorded?: boolean;
  execution_started?: boolean;
  retry_started?: boolean;
  escalation_started?: boolean;
  memory_write?: boolean;
  applied?: boolean;
};

export type ReactorDeadletterItem = {
  deadletter_id: string;
  id?: string;
  event_id?: string;
  status?: string;
  route?: string;
  gate?: string;
  stable_state?: string;
  next_step?: string;
  source_route?: string;
  source_receipt_kind?: string;
  source_receipt_ref?: string;
  review_decision?: string;
  resolution_decision?: string;
  deadletter_resolved?: boolean;
  escalation_recorded?: boolean;
  execution_started?: boolean;
  retry_started?: boolean;
  escalation_started?: boolean;
  created_ts?: number;
  updated_ts?: number;
  latest_review_receipt?: ReactorReceiptSummary;
  latest_resolution_receipt?: ReactorReceiptSummary;
};

export type ReactorDeadletterSnapshot = {
  ok: boolean;
  items: ReactorDeadletterItem[];
  total: number;
  limit: number;
  status?: string;
  governance?: Record<string, unknown>;
  error?: string;
};

export type ReactorReviewQueueParams = {
  limit?: number;
  route?: string;
};

export type ReactorDeadletterListParams = {
  limit?: number;
  status?: string;
};

export class ReactorApiError extends Error {
  status?: number;
  url?: string;

  constructor(message: string, options: { status?: number; url?: string } = {}) {
    super(message);
    this.name = "ReactorApiError";
    this.status = options.status;
    this.url = options.url;
  }
}

export class ReactorClient {
  readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
  }

  async getReviewQueue(
    params: ReactorReviewQueueParams = {},
    options: { signal?: AbortSignal; timeoutMs?: number } = {},
  ): Promise<ReactorReviewQueueSnapshot> {
    const url = new URL(`${this.baseUrl}/reactor/review_queue`);
    const limit = boundedLimit(params.limit, 20);
    url.searchParams.set("limit", String(limit));
    const route = safeString(params.route).trim();
    if (route) url.searchParams.set("route", route);

    const response = await fetchWithTimeout(url.toString(), { method: "GET", signal: options.signal }, options.timeoutMs ?? 10_000);
    if (!response.ok) {
      throw new ReactorApiError(`Reactor review queue request failed with HTTP ${response.status}`, {
        status: response.status,
        url: url.toString(),
      });
    }

    const raw = (await response.json()) as unknown;
    return parseReactorReviewQueueSnapshot(raw, { limit, route });
  }

  async listDeadletters(
    params: ReactorDeadletterListParams = {},
    options: { signal?: AbortSignal; timeoutMs?: number } = {},
  ): Promise<ReactorDeadletterSnapshot> {
    const url = new URL(`${this.baseUrl}/reactor/deadletters/list`);
    const limit = boundedLimit(params.limit, 20);
    url.searchParams.set("limit", String(limit));
    const status = safeString(params.status).trim();
    if (status) url.searchParams.set("status", status);

    const response = await fetchWithTimeout(url.toString(), { method: "GET", signal: options.signal }, options.timeoutMs ?? 10_000);
    if (!response.ok) {
      throw new ReactorApiError(`Reactor deadletter list request failed with HTTP ${response.status}`, {
        status: response.status,
        url: url.toString(),
      });
    }

    const raw = (await response.json()) as unknown;
    return parseReactorDeadletterSnapshot(raw, { limit, status });
  }
}

export function parseReactorReviewQueueSnapshot(
  raw: unknown,
  defaults: { limit?: number; route?: string } = {},
): ReactorReviewQueueSnapshot {
  const record = isRecord(raw) ? raw : {};
  const rawItems = Array.isArray(record.items) ? record.items : [];
  const items = rawItems.map(parseReactorReviewQueueItem).filter((item): item is ReactorReviewQueueItem => Boolean(item));
  const route = safeString(record.route).trim() || safeString(defaults.route).trim();
  const limit = Math.max(0, safeNumber(record.limit, boundedLimit(defaults.limit, 20)));
  const total = Math.max(0, safeNumber(record.total, items.length));
  const availableTotal = Math.max(0, safeNumber(record.available_total, total));
  const governance = isRecord(record.governance) ? record.governance : undefined;
  const error = safeString(record.error).trim();

  return {
    ok: typeof record.ok === "boolean" ? record.ok : error.length === 0,
    items,
    total,
    available_total: availableTotal,
    limit,
    route: route || undefined,
    route_counts: parseCountMap(record.route_counts),
    stable_state_counts: parseCountMap(record.stable_state_counts),
    governance,
    error: error || undefined,
  };
}

export function parseReactorReviewQueueItem(raw: unknown): ReactorReviewQueueItem | null {
  const record = isRecord(raw) ? raw : null;
  if (!record) return null;
  const eventId = safeString(record.event_id).trim() || safeString(record.id).trim();
  if (!eventId) return null;

  const createdTs = optionalNumber(record.created_ts);
  const updatedTs = optionalNumber(record.updated_ts);
  const trigger = parseTrigger(record.trigger);
  const classification = parseClassification(record.classification);
  const review = parseReview(record.review);

  return {
    event_id: eventId,
    status: optionalString(record.status),
    stable_state: optionalString(record.stable_state),
    created_ts: createdTs,
    updated_ts: updatedTs,
    trigger,
    classification,
    review,
  };
}

export function parseReactorDeadletterSnapshot(
  raw: unknown,
  defaults: { limit?: number; status?: string } = {},
): ReactorDeadletterSnapshot {
  const record = isRecord(raw) ? raw : {};
  const rawItems = Array.isArray(record.items) ? record.items : [];
  const items = rawItems.map(parseReactorDeadletterItem).filter((item): item is ReactorDeadletterItem => Boolean(item));
  const status = safeString(record.status).trim() || safeString(defaults.status).trim();
  const limit = Math.max(0, safeNumber(record.limit, boundedLimit(defaults.limit, 20)));
  const total = Math.max(0, safeNumber(record.total, items.length));
  const governance = isRecord(record.governance) ? record.governance : undefined;
  const error = safeString(record.error).trim();

  return {
    ok: typeof record.ok === "boolean" ? record.ok : error.length === 0,
    items,
    total,
    limit,
    status: status || undefined,
    governance,
    error: error || undefined,
  };
}

export function parseReactorDeadletterItem(raw: unknown): ReactorDeadletterItem | null {
  const record = isRecord(raw) ? raw : null;
  if (!record) return null;
  const deadletterId = safeString(record.deadletter_id).trim() || safeString(record.id).trim();
  if (!deadletterId) return null;

  return {
    deadletter_id: deadletterId,
    id: optionalString(record.id),
    event_id: optionalString(record.event_id),
    status: optionalString(record.status),
    route: optionalString(record.route),
    gate: optionalString(record.gate),
    stable_state: optionalString(record.stable_state),
    next_step: optionalString(record.next_step),
    source_route: optionalString(record.source_route),
    source_receipt_kind: optionalString(record.source_receipt_kind),
    source_receipt_ref: optionalString(record.source_receipt_ref),
    review_decision: optionalString(record.review_decision),
    resolution_decision: optionalString(record.resolution_decision),
    deadletter_resolved: optionalBoolean(record.deadletter_resolved),
    escalation_recorded: optionalBoolean(record.escalation_recorded),
    execution_started: optionalBoolean(record.execution_started),
    retry_started: optionalBoolean(record.retry_started),
    escalation_started: optionalBoolean(record.escalation_started),
    created_ts: optionalNumber(record.created_ts),
    updated_ts: optionalNumber(record.updated_ts),
    latest_review_receipt: parseReceipt(record.latest_review_receipt),
    latest_resolution_receipt: parseReceipt(record.latest_resolution_receipt),
  };
}

function parseReceipt(raw: unknown): ReactorReceiptSummary | undefined {
  const record = isRecord(raw) ? raw : null;
  if (!record) return undefined;
  const receipt: ReactorReceiptSummary = {
    kind: optionalString(record.kind),
    receipt_id: optionalString(record.receipt_id),
    deadletter_id: optionalString(record.deadletter_id),
    event_id: optionalString(record.event_id),
    status: optionalString(record.status),
    route: optionalString(record.route),
    gate: optionalString(record.gate),
    stable_state: optionalString(record.stable_state),
    next_step: optionalString(record.next_step),
    review_decision: optionalString(record.review_decision),
    resolution_decision: optionalString(record.resolution_decision),
    deadletter_resolved: optionalBoolean(record.deadletter_resolved),
    escalation_recorded: optionalBoolean(record.escalation_recorded),
    execution_started: optionalBoolean(record.execution_started),
    retry_started: optionalBoolean(record.retry_started),
    escalation_started: optionalBoolean(record.escalation_started),
    memory_write: optionalBoolean(record.memory_write),
    applied: optionalBoolean(record.applied),
  };
  return hasAnyValue(receipt) ? receipt : undefined;
}

function parseTrigger(raw: unknown): ReactorReviewTrigger | undefined {
  const record = isRecord(raw) ? raw : null;
  if (!record) return undefined;
  const trigger: ReactorReviewTrigger = {
    source: optionalString(record.source),
    type: optionalString(record.type),
    summary: optionalString(record.summary),
    mission_id: optionalString(record.mission_id),
    operation_id: optionalString(record.operation_id),
    approval_id: optionalString(record.approval_id),
  };
  return hasAnyValue(trigger) ? trigger : undefined;
}

function parseClassification(raw: unknown): ReactorReviewClassification | undefined {
  const record = isRecord(raw) ? raw : null;
  if (!record) return undefined;
  const classification: ReactorReviewClassification = {
    mode: optionalString(record.mode),
    risk_tier: optionalString(record.risk_tier),
    action_class: optionalString(record.action_class),
    approval_required: typeof record.approval_required === "boolean" ? record.approval_required : undefined,
  };
  return hasAnyValue(classification) ? classification : undefined;
}

function parseReview(raw: unknown): ReactorReviewDetail | undefined {
  const record = isRecord(raw) ? raw : null;
  if (!record) return undefined;
  const review: ReactorReviewDetail = {
    route: optionalString(record.route),
    status: optionalString(record.status),
    gate: optionalString(record.gate),
    action: optionalString(record.action),
    next_step: optionalString(record.next_step),
    receipt_kind: optionalString(record.receipt_kind),
    receipt_ref: optionalString(record.receipt_ref),
    blocker_ref: optionalString(record.blocker_ref),
    execution_started: typeof record.execution_started === "boolean" ? record.execution_started : undefined,
    applied: typeof record.applied === "boolean" ? record.applied : undefined,
  };
  return hasAnyValue(review) ? review : undefined;
}

function parseCountMap(raw: unknown): Record<string, number> {
  const record = isRecord(raw) ? raw : null;
  if (!record) return {};
  const counts: Record<string, number> = {};
  for (const [key, value] of Object.entries(record)) {
    const cleanKey = safeString(key).trim();
    if (!cleanKey) continue;
    counts[cleanKey] = Math.max(0, safeNumber(value, 0));
  }
  return counts;
}

function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  if (init.signal || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return fetch(url, init);
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...init, signal: controller.signal }).finally(() => clearTimeout(timeout));
}

function boundedLimit(value: unknown, fallback: number): number {
  const parsed = Math.trunc(safeNumber(value, fallback));
  return Math.max(1, Math.min(parsed, 100));
}

function optionalString(value: unknown): string | undefined {
  const cleaned = safeString(value).trim();
  return cleaned || undefined;
}

function optionalNumber(value: unknown): number | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  const parsed = safeNumber(value, Number.NaN);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function optionalBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function hasAnyValue(record: Record<string, unknown>): boolean {
  return Object.values(record).some((value) => value !== undefined && value !== "");
}

function safeString(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function safeNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeBaseUrl(value: string): string {
  const cleaned = value.trim();
  if (!cleaned) return "";
  return cleaned.replace(/\/+$/, "");
}
