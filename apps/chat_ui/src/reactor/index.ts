export type ReactorReviewRoute =
  | "approval_queue"
  | "deadletter_candidate"
  | "deadletter_escalation"
  | "deadletter_escalation_acknowledgement"
  | "deadletter_escalation_handoff"
  | "deadletter_recovery_dispatch"
  | "deadletter_recovery_request"
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
  proposal_id?: string;
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
  proposal_id?: string;
  plugin_id?: string;
  status?: string;
  outcome?: string;
  route?: string;
  gate?: string;
  stable_state?: string;
  next_step?: string;
  proposal_status?: string;
  quality_ready?: boolean;
  missing_requirements?: string[];
  review_status?: string;
  review_receipt_id?: string;
  validation_receipt_id?: string;
  validation_receipt_path?: string;
  review_decision?: string;
  resolution_decision?: string;
  deadletter_resolved?: boolean;
  escalation_recorded?: boolean;
  escalation_acknowledged?: boolean;
  escalation_handoff_recorded?: boolean;
  external_escalation_started?: boolean;
  recovery_requested?: boolean;
  recovery_dispatched?: boolean;
  recovery_event_id?: string;
  recovery_request_receipt_id?: string;
  recovery_started?: boolean;
  readback_only?: boolean;
  proposal_decision_applied?: boolean;
  promotion_applied?: boolean;
  verified?: boolean;
  completion_claim_allowed?: boolean;
  dispatch_applied?: boolean;
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
  escalation_acknowledged?: boolean;
  escalation_handoff_recorded?: boolean;
  external_escalation_started?: boolean;
  recovery_requested?: boolean;
  recovery_dispatched?: boolean;
  recovery_started?: boolean;
  execution_started?: boolean;
  retry_started?: boolean;
  escalation_started?: boolean;
  created_ts?: number;
  updated_ts?: number;
  latest_review_receipt?: ReactorReceiptSummary;
  latest_resolution_receipt?: ReactorReceiptSummary;
  latest_escalation_handoff_receipt?: ReactorReceiptSummary;
  latest_escalation_acknowledgement_receipt?: ReactorReceiptSummary;
  latest_recovery_request_receipt?: ReactorReceiptSummary;
  latest_recovery_dispatch_receipt?: ReactorReceiptSummary;
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

export type ReactorEventItem = {
  event_id: string;
  id?: string;
  status?: string;
  stable_state?: string;
  created_ts?: number;
  updated_ts?: number;
  trigger?: ReactorReviewTrigger;
  classification?: ReactorReviewClassification;
  latest_dispatch_execution_receipt?: ReactorReceiptSummary;
  latest_verification_receipt?: ReactorReceiptSummary;
  latest_stable_return?: ReactorReceiptSummary;
};

export type ReactorEventSnapshot = {
  ok: boolean;
  items: ReactorEventItem[];
  total: number;
  limit: number;
  status?: string;
  trigger_source?: string;
  stable_state?: string;
  blocker_route?: string;
  review_route?: string;
  receipt_kind?: string;
  error?: string;
};

export type ReactorProposalReviewHistoryItem = {
  event_id: string;
  status?: string;
  stable_state?: string;
  summary?: string;
  route?: string;
  outcome?: string;
  next_step?: string;
  proposal_id?: string;
  plugin_id?: string;
  proposal_status?: string;
  quality_ready?: boolean;
  missing_requirements?: string[];
  review_status?: string;
  review_receipt_id?: string;
  validation_receipt_id?: string;
  validation_receipt_path?: string;
  readback_only?: boolean;
  proposal_decision_applied?: boolean;
  promotion_applied?: boolean;
  execution_started?: boolean;
  dispatch_applied?: boolean;
  memory_write?: boolean;
  verified?: boolean;
};

export type ReactorExternalDeliveryProcessorItem = {
  readiness_id?: string;
  delivery_id?: string;
  deadletter_id?: string;
  event_id?: string;
  status?: string;
  route?: string;
  delivery_status?: string;
  delivery_processor_status?: string;
  delivery_processor_ready?: boolean;
  delivery_processor_blockers?: string[];
  external_delivery_started?: boolean;
  external_escalation_started?: boolean;
  blockers?: string[];
  next_step?: string;
};

export type ReactorExternalDeliverySenderItem = {
  readiness_id?: string;
  delivery_id?: string;
  deadletter_id?: string;
  event_id?: string;
  status?: string;
  route?: string;
  delivery_status?: string;
  external_delivery_sender_status?: string;
  external_delivery_sender_ready?: boolean;
  external_delivery_sender_blockers?: string[];
  external_delivery_sender_attempted?: boolean;
  external_sender_adapter?: string;
  external_sender_status?: string;
  external_sender_blocker?: string;
  delivery_processor_completed?: boolean;
  local_outbox_processor_completed?: boolean;
  external_delivery_started?: boolean;
  external_message_sent?: boolean;
  external_network_send?: boolean;
  external_escalation_started?: boolean;
  execution_started?: boolean;
  memory_write?: boolean;
  next_step?: string;
  governance?: Record<string, unknown>;
};

export type ReactorExternalDeliverySenderContract = {
  kind?: string;
  status?: string;
  route?: string;
  gate?: string;
  supported_external_sender_adapters: string[];
  external_sender_required_fields: string[];
  external_delivery_sender_ready?: boolean;
  external_sender_contract_ready?: boolean;
  external_sender_contract_blocker?: string;
  missing_requirements?: string[];
  external_delivery_started?: boolean;
  external_message_sent?: boolean;
  external_network_send?: boolean;
  completion_claim_allowed?: boolean;
  next_step?: string;
  governance?: Record<string, unknown>;
};

export type ReactorOperatorVisibilitySummary = {
  ok: boolean;
  kind?: string;
  status?: string;
  limit: number;
  next_step?: string;
  event_total: number;
  review_queue_total: number;
  deadletter_total: number;
  retry_schedule_total: number;
  external_delivery_total: number;
  external_delivery_sender_readiness_total: number;
  external_delivery_sender_contract_status?: string;
  external_delivery_sender_contract_ready?: boolean;
  external_delivery_sender_contract_blocker?: string;
  supported_external_sender_adapters: string[];
  supported_external_sender_adapter_total: number;
  external_sender_required_fields: string[];
  recovery_receipt_total: number;
  proposal_review_history_total: number;
  attention: Record<string, number>;
  counts: Record<string, Record<string, number>>;
  readback_surfaces: Record<string, string>;
  latest_review_items: ReactorReviewQueueItem[];
  latest_proposal_reviews: ReactorProposalReviewHistoryItem[];
  ready_external_delivery_processor_items: ReactorExternalDeliveryProcessorItem[];
  ready_external_delivery_sender_items: ReactorExternalDeliverySenderItem[];
  blocked_external_delivery_sender_items: ReactorExternalDeliverySenderItem[];
  external_delivery_sender_contract?: ReactorExternalDeliverySenderContract;
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

export type ReactorEventListParams = {
  limit?: number;
  status?: string;
  trigger_source?: string;
  stable_state?: string;
  blocker_route?: string;
  review_route?: string;
  receipt_kind?: string;
};

export type ReactorOperatorVisibilityParams = {
  limit?: number;
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

  async getOperatorVisibilitySummary(
    params: ReactorOperatorVisibilityParams = {},
    options: { signal?: AbortSignal; timeoutMs?: number } = {},
  ): Promise<ReactorOperatorVisibilitySummary> {
    const url = new URL(`${this.baseUrl}/reactor/operator_visibility/summary`);
    const limit = boundedLimit(params.limit, 10);
    url.searchParams.set("limit", String(limit));

    const response = await fetchWithTimeout(url.toString(), { method: "GET", signal: options.signal }, options.timeoutMs ?? 10_000);
    if (!response.ok) {
      throw new ReactorApiError(`Reactor operator visibility request failed with HTTP ${response.status}`, {
        status: response.status,
        url: url.toString(),
      });
    }

    const raw = (await response.json()) as unknown;
    return parseReactorOperatorVisibilitySummary(raw, { limit });
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

  async listEvents(
    params: ReactorEventListParams = {},
    options: { signal?: AbortSignal; timeoutMs?: number } = {},
  ): Promise<ReactorEventSnapshot> {
    const url = new URL(`${this.baseUrl}/reactor/events/list`);
    const limit = boundedLimit(params.limit, 20);
    url.searchParams.set("limit", String(limit));
    const status = safeString(params.status).trim();
    const triggerSource = safeString(params.trigger_source).trim();
    const stableState = safeString(params.stable_state).trim();
    const blockerRoute = safeString(params.blocker_route).trim();
    const reviewRoute = safeString(params.review_route).trim();
    const receiptKind = safeString(params.receipt_kind).trim();
    if (status) url.searchParams.set("status", status);
    if (triggerSource) url.searchParams.set("trigger_source", triggerSource);
    if (stableState) url.searchParams.set("stable_state", stableState);
    if (blockerRoute) url.searchParams.set("blocker_route", blockerRoute);
    if (reviewRoute) url.searchParams.set("review_route", reviewRoute);
    if (receiptKind) url.searchParams.set("receipt_kind", receiptKind);

    const response = await fetchWithTimeout(url.toString(), { method: "GET", signal: options.signal }, options.timeoutMs ?? 10_000);
    if (!response.ok) {
      throw new ReactorApiError(`Reactor events list request failed with HTTP ${response.status}`, {
        status: response.status,
        url: url.toString(),
      });
    }

    const raw = (await response.json()) as unknown;
    return parseReactorEventSnapshot(raw, {
      limit,
      status,
      trigger_source: triggerSource,
      stable_state: stableState,
      blocker_route: blockerRoute,
      review_route: reviewRoute,
      receipt_kind: receiptKind,
    });
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

export function parseReactorOperatorVisibilitySummary(
  raw: unknown,
  defaults: { limit?: number } = {},
): ReactorOperatorVisibilitySummary {
  const record = isRecord(raw) ? raw : {};
  const latestReviewItemsRaw = Array.isArray(record.latest_review_items) ? record.latest_review_items : [];
  const latestProposalReviewsRaw = Array.isArray(record.latest_proposal_reviews) ? record.latest_proposal_reviews : [];
  const readyExternalDeliveryProcessorItemsRaw = Array.isArray(record.ready_external_delivery_processor_items)
    ? record.ready_external_delivery_processor_items
    : [];
  const readyExternalDeliverySenderItemsRaw = Array.isArray(record.ready_external_delivery_sender_items)
    ? record.ready_external_delivery_sender_items
    : [];
  const blockedExternalDeliverySenderItemsRaw = Array.isArray(record.blocked_external_delivery_sender_items)
    ? record.blocked_external_delivery_sender_items
    : [];
  const error = safeString(record.error).trim();

  return {
    ok: typeof record.ok === "boolean" ? record.ok : error.length === 0,
    kind: optionalString(record.kind),
    status: optionalString(record.status),
    limit: Math.max(0, safeNumber(record.limit, boundedLimit(defaults.limit, 10))),
    next_step: optionalString(record.next_step),
    event_total: Math.max(0, safeNumber(record.event_total, 0)),
    review_queue_total: Math.max(0, safeNumber(record.review_queue_total, 0)),
    deadletter_total: Math.max(0, safeNumber(record.deadletter_total, 0)),
    retry_schedule_total: Math.max(0, safeNumber(record.retry_schedule_total, 0)),
    external_delivery_total: Math.max(0, safeNumber(record.external_delivery_total, 0)),
    external_delivery_sender_readiness_total: Math.max(
      0,
      safeNumber(record.external_delivery_sender_readiness_total, 0),
    ),
    external_delivery_sender_contract_status: optionalString(record.external_delivery_sender_contract_status),
    external_delivery_sender_contract_ready: optionalBoolean(record.external_delivery_sender_contract_ready),
    external_delivery_sender_contract_blocker: optionalString(record.external_delivery_sender_contract_blocker),
    supported_external_sender_adapters: optionalStringList(record.supported_external_sender_adapters) ?? [],
    supported_external_sender_adapter_total: Math.max(0, safeNumber(record.supported_external_sender_adapter_total, 0)),
    external_sender_required_fields: optionalStringList(record.external_sender_required_fields) ?? [],
    recovery_receipt_total: Math.max(0, safeNumber(record.recovery_receipt_total, 0)),
    proposal_review_history_total: Math.max(0, safeNumber(record.proposal_review_history_total, 0)),
    attention: parseCountMap(record.attention),
    counts: parseNestedCountMap(record.counts),
    readback_surfaces: parseStringMap(record.readback_surfaces),
    latest_review_items: latestReviewItemsRaw
      .map(parseReactorReviewQueueItem)
      .filter((item): item is ReactorReviewQueueItem => Boolean(item)),
    latest_proposal_reviews: latestProposalReviewsRaw
      .map(parseReactorProposalReviewHistoryItem)
      .filter((item): item is ReactorProposalReviewHistoryItem => Boolean(item)),
    ready_external_delivery_processor_items: readyExternalDeliveryProcessorItemsRaw
      .map(parseReactorExternalDeliveryProcessorItem)
      .filter((item): item is ReactorExternalDeliveryProcessorItem => Boolean(item)),
    ready_external_delivery_sender_items: readyExternalDeliverySenderItemsRaw
      .map(parseReactorExternalDeliverySenderItem)
      .filter((item): item is ReactorExternalDeliverySenderItem => Boolean(item)),
    blocked_external_delivery_sender_items: blockedExternalDeliverySenderItemsRaw
      .map(parseReactorExternalDeliverySenderItem)
      .filter((item): item is ReactorExternalDeliverySenderItem => Boolean(item)),
    external_delivery_sender_contract: parseReactorExternalDeliverySenderContract(
      record.external_delivery_sender_contract,
    ),
    governance: isRecord(record.governance) ? record.governance : undefined,
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

export function parseReactorEventSnapshot(
  raw: unknown,
  defaults: ReactorEventListParams = {},
): ReactorEventSnapshot {
  const record = isRecord(raw) ? raw : {};
  const rawItems = Array.isArray(record.items) ? record.items : [];
  const items = rawItems.map(parseReactorEventItem).filter((item): item is ReactorEventItem => Boolean(item));
  const limit = Math.max(0, safeNumber(record.limit, boundedLimit(defaults.limit, 20)));
  const total = Math.max(0, safeNumber(record.total, items.length));
  const error = safeString(record.error).trim();

  return {
    ok: typeof record.ok === "boolean" ? record.ok : error.length === 0,
    items,
    total,
    limit,
    status: optionalString(record.status) || optionalString(defaults.status),
    trigger_source: optionalString(record.trigger_source) || optionalString(defaults.trigger_source),
    stable_state: optionalString(record.stable_state) || optionalString(defaults.stable_state),
    blocker_route: optionalString(record.blocker_route) || optionalString(defaults.blocker_route),
    review_route: optionalString(record.review_route) || optionalString(defaults.review_route),
    receipt_kind: optionalString(record.receipt_kind) || optionalString(defaults.receipt_kind),
    error: error || undefined,
  };
}

export function parseReactorProposalReviewHistoryItem(raw: unknown): ReactorProposalReviewHistoryItem | null {
  const record = isRecord(raw) ? raw : null;
  if (!record) return null;
  const eventId = safeString(record.event_id).trim() || safeString(record.id).trim();
  if (!eventId) return null;

  return {
    event_id: eventId,
    status: optionalString(record.status),
    stable_state: optionalString(record.stable_state),
    summary: optionalString(record.summary),
    route: optionalString(record.route),
    outcome: optionalString(record.outcome),
    next_step: optionalString(record.next_step),
    proposal_id: optionalString(record.proposal_id),
    plugin_id: optionalString(record.plugin_id),
    proposal_status: optionalString(record.proposal_status),
    quality_ready: optionalBoolean(record.quality_ready),
    missing_requirements: optionalStringList(record.missing_requirements),
    review_status: optionalString(record.review_status),
    review_receipt_id: optionalString(record.review_receipt_id),
    validation_receipt_id: optionalString(record.validation_receipt_id),
    validation_receipt_path: optionalString(record.validation_receipt_path),
    readback_only: optionalBoolean(record.readback_only),
    proposal_decision_applied: optionalBoolean(record.proposal_decision_applied),
    promotion_applied: optionalBoolean(record.promotion_applied),
    execution_started: optionalBoolean(record.execution_started),
    dispatch_applied: optionalBoolean(record.dispatch_applied),
    memory_write: optionalBoolean(record.memory_write),
    verified: optionalBoolean(record.verified),
  };
}

export function parseReactorExternalDeliveryProcessorItem(raw: unknown): ReactorExternalDeliveryProcessorItem | null {
  const record = isRecord(raw) ? raw : null;
  if (!record) return null;
  const readinessId = safeString(record.readiness_id).trim() || safeString(record.id).trim();
  const deliveryId = safeString(record.delivery_id).trim();
  const deadletterId = safeString(record.deadletter_id).trim();
  const eventId = safeString(record.event_id).trim();
  if (!readinessId && !deliveryId && !deadletterId && !eventId) return null;

  return {
    readiness_id: readinessId || undefined,
    delivery_id: deliveryId || undefined,
    deadletter_id: deadletterId || undefined,
    event_id: eventId || undefined,
    status: optionalString(record.status),
    route: optionalString(record.route),
    delivery_status: optionalString(record.delivery_status),
    delivery_processor_status: optionalString(record.delivery_processor_status),
    delivery_processor_ready: optionalBoolean(record.delivery_processor_ready),
    delivery_processor_blockers: optionalStringList(record.delivery_processor_blockers),
    external_delivery_started: optionalBoolean(record.external_delivery_started),
    external_escalation_started: optionalBoolean(record.external_escalation_started),
    blockers: optionalStringList(record.blockers),
    next_step: optionalString(record.next_step),
  };
}

export function parseReactorExternalDeliverySenderItem(raw: unknown): ReactorExternalDeliverySenderItem | null {
  const record = isRecord(raw) ? raw : null;
  if (!record) return null;
  const readinessId = safeString(record.readiness_id).trim() || safeString(record.id).trim();
  const deliveryId = safeString(record.delivery_id).trim();
  const deadletterId = safeString(record.deadletter_id).trim();
  const eventId = safeString(record.event_id).trim();
  if (!readinessId && !deliveryId && !deadletterId && !eventId) return null;

  return {
    readiness_id: readinessId || undefined,
    delivery_id: deliveryId || undefined,
    deadletter_id: deadletterId || undefined,
    event_id: eventId || undefined,
    status: optionalString(record.status),
    route: optionalString(record.route),
    delivery_status: optionalString(record.delivery_status),
    external_delivery_sender_status: optionalString(record.external_delivery_sender_status),
    external_delivery_sender_ready: optionalBoolean(record.external_delivery_sender_ready),
    external_delivery_sender_blockers: optionalStringList(record.external_delivery_sender_blockers),
    external_delivery_sender_attempted: optionalBoolean(record.external_delivery_sender_attempted),
    external_sender_adapter: optionalString(record.external_sender_adapter),
    external_sender_status: optionalString(record.external_sender_status),
    external_sender_blocker: optionalString(record.external_sender_blocker),
    delivery_processor_completed: optionalBoolean(record.delivery_processor_completed),
    local_outbox_processor_completed: optionalBoolean(record.local_outbox_processor_completed),
    external_delivery_started: optionalBoolean(record.external_delivery_started),
    external_message_sent: optionalBoolean(record.external_message_sent),
    external_network_send: optionalBoolean(record.external_network_send),
    external_escalation_started: optionalBoolean(record.external_escalation_started),
    execution_started: optionalBoolean(record.execution_started),
    memory_write: optionalBoolean(record.memory_write),
    next_step: optionalString(record.next_step),
    governance: isRecord(record.governance) ? record.governance : undefined,
  };
}

export function parseReactorExternalDeliverySenderContract(raw: unknown): ReactorExternalDeliverySenderContract | undefined {
  const record = isRecord(raw) ? raw : null;
  if (!record) return undefined;
  const contract = {
    kind: optionalString(record.kind),
    status: optionalString(record.status),
    route: optionalString(record.route),
    gate: optionalString(record.gate),
    supported_external_sender_adapters: optionalStringList(record.supported_external_sender_adapters) ?? [],
    external_sender_required_fields: optionalStringList(record.external_sender_required_fields) ?? [],
    external_delivery_sender_ready: optionalBoolean(record.external_delivery_sender_ready),
    external_sender_contract_ready: optionalBoolean(record.external_sender_contract_ready),
    external_sender_contract_blocker: optionalString(record.external_sender_contract_blocker),
    missing_requirements: optionalStringList(record.missing_requirements),
    external_delivery_started: optionalBoolean(record.external_delivery_started),
    external_message_sent: optionalBoolean(record.external_message_sent),
    external_network_send: optionalBoolean(record.external_network_send),
    completion_claim_allowed: optionalBoolean(record.completion_claim_allowed),
    next_step: optionalString(record.next_step),
    governance: isRecord(record.governance) ? record.governance : undefined,
  };
  return hasAnyValue(contract) ? contract : undefined;
}

export function parseReactorEventItem(raw: unknown): ReactorEventItem | null {
  const record = isRecord(raw) ? raw : null;
  if (!record) return null;
  const eventId = safeString(record.event_id).trim() || safeString(record.id).trim();
  if (!eventId) return null;

  return {
    event_id: eventId,
    id: optionalString(record.id),
    status: optionalString(record.status),
    stable_state: optionalString(record.stable_state),
    created_ts: optionalNumber(record.created_ts),
    updated_ts: optionalNumber(record.updated_ts),
    trigger: parseTrigger(record.trigger),
    classification: parseClassification(record.classification),
    latest_dispatch_execution_receipt: parseReceipt(record.latest_dispatch_execution_receipt),
    latest_verification_receipt: parseReceipt(record.latest_verification_receipt),
    latest_stable_return: parseReceipt(record.latest_stable_return),
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
    escalation_acknowledged: optionalBoolean(record.escalation_acknowledged),
    escalation_handoff_recorded: optionalBoolean(record.escalation_handoff_recorded),
    external_escalation_started: optionalBoolean(record.external_escalation_started),
    recovery_requested: optionalBoolean(record.recovery_requested),
    recovery_dispatched: optionalBoolean(record.recovery_dispatched),
    recovery_started: optionalBoolean(record.recovery_started),
    execution_started: optionalBoolean(record.execution_started),
    retry_started: optionalBoolean(record.retry_started),
    escalation_started: optionalBoolean(record.escalation_started),
    created_ts: optionalNumber(record.created_ts),
    updated_ts: optionalNumber(record.updated_ts),
    latest_review_receipt: parseReceipt(record.latest_review_receipt),
    latest_resolution_receipt: parseReceipt(record.latest_resolution_receipt),
    latest_escalation_handoff_receipt: parseReceipt(record.latest_escalation_handoff_receipt),
    latest_escalation_acknowledgement_receipt: parseReceipt(record.latest_escalation_acknowledgement_receipt),
    latest_recovery_request_receipt: parseReceipt(record.latest_recovery_request_receipt),
    latest_recovery_dispatch_receipt: parseReceipt(record.latest_recovery_dispatch_receipt),
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
    proposal_id: optionalString(record.proposal_id),
    plugin_id: optionalString(record.plugin_id),
    status: optionalString(record.status),
    outcome: optionalString(record.outcome),
    route: optionalString(record.route),
    gate: optionalString(record.gate),
    stable_state: optionalString(record.stable_state),
    next_step: optionalString(record.next_step),
    proposal_status: optionalString(record.proposal_status),
    quality_ready: optionalBoolean(record.quality_ready),
    missing_requirements: optionalStringList(record.missing_requirements),
    review_status: optionalString(record.review_status),
    review_receipt_id: optionalString(record.review_receipt_id),
    validation_receipt_id: optionalString(record.validation_receipt_id),
    validation_receipt_path: optionalString(record.validation_receipt_path),
    review_decision: optionalString(record.review_decision),
    resolution_decision: optionalString(record.resolution_decision),
    deadletter_resolved: optionalBoolean(record.deadletter_resolved),
    escalation_recorded: optionalBoolean(record.escalation_recorded),
    escalation_acknowledged: optionalBoolean(record.escalation_acknowledged),
    escalation_handoff_recorded: optionalBoolean(record.escalation_handoff_recorded),
    external_escalation_started: optionalBoolean(record.external_escalation_started),
    recovery_requested: optionalBoolean(record.recovery_requested),
    recovery_dispatched: optionalBoolean(record.recovery_dispatched),
    recovery_event_id: optionalString(record.recovery_event_id),
    recovery_request_receipt_id: optionalString(record.recovery_request_receipt_id),
    recovery_started: optionalBoolean(record.recovery_started),
    readback_only: optionalBoolean(record.readback_only),
    proposal_decision_applied: optionalBoolean(record.proposal_decision_applied),
    promotion_applied: optionalBoolean(record.promotion_applied),
    verified: optionalBoolean(record.verified),
    completion_claim_allowed: optionalBoolean(record.completion_claim_allowed),
    dispatch_applied: optionalBoolean(record.dispatch_applied),
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
  const metadata = isRecord(record.metadata) ? record.metadata : {};
  const trigger: ReactorReviewTrigger = {
    source: optionalString(record.source),
    type: optionalString(record.type),
    summary: optionalString(record.summary),
    mission_id: optionalString(record.mission_id),
    operation_id: optionalString(record.operation_id),
    approval_id: optionalString(record.approval_id),
    proposal_id: optionalString(record.proposal_id) || optionalString(metadata.proposal_id) || optionalString(metadata.forge_proposal_id),
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

function parseNestedCountMap(raw: unknown): Record<string, Record<string, number>> {
  const record = isRecord(raw) ? raw : null;
  if (!record) return {};
  const counts: Record<string, Record<string, number>> = {};
  for (const [key, value] of Object.entries(record)) {
    const cleanKey = safeString(key).trim();
    if (!cleanKey) continue;
    counts[cleanKey] = parseCountMap(value);
  }
  return counts;
}

function parseStringMap(raw: unknown): Record<string, string> {
  const record = isRecord(raw) ? raw : null;
  if (!record) return {};
  const values: Record<string, string> = {};
  for (const [key, value] of Object.entries(record)) {
    const cleanKey = safeString(key).trim();
    const cleanValue = safeString(value).trim();
    if (!cleanKey || !cleanValue) continue;
    values[cleanKey] = cleanValue;
  }
  return values;
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

function optionalStringList(value: unknown): string[] | undefined {
  if (Array.isArray(value)) {
    const items = value.map((item) => safeString(item).trim()).filter(Boolean);
    return items.length > 0 ? items : undefined;
  }
  const item = safeString(value).trim();
  return item ? [item] : undefined;
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
