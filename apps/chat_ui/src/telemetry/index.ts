export type TelemetrySourceStatus = {
  id: string;
  label: string;
  description: string;
  status: string;
  active: boolean;
  visible_indicator: boolean;
  hidden_sensing: boolean;
  scope: {
    status: string;
    allowed_paths: string[];
    allowed_processes: string[];
    denied_by_default: boolean;
  };
  redaction: Record<string, unknown>;
  retention: Record<string, unknown>;
  signals: unknown[];
  expected_signals: string[];
  blocked_by: string[];
  authority: Record<string, boolean>;
  latest_event?: TelemetryTerminalEventSummary | null;
  latest_snapshot?: TelemetryGitSnapshotSummary | null;
  latest_diagnostic?: TelemetryIdeDiagnosticSummary | null;
  routes: Record<string, string>;
};

export type TelemetryTerminalEventSummary = {
  event_id: string;
  recorded_ts?: number;
  exit_code?: number | null;
  cwd: string;
  command: string;
  operation_id: string;
  approval_id: string;
  trace_id: string;
  run_id: string;
  artifact_dir: string;
};

export type TelemetryGitSnapshotSummary = {
  branch: string;
  head: string;
  upstream: string;
  ahead: number;
  behind: number;
  dirty: boolean;
  changed_count: number;
  changed_paths: Array<{ status: string; path: string }>;
  ts?: number;
};

export type TelemetryIdeDiagnosticSummary = {
  event_id: string;
  recorded_ts?: number;
  source: string;
  workspace: string;
  file: string;
  diagnostic_count: number;
  highest_severity: string;
  operation_id: string;
  approval_id: string;
  trace_id: string;
  run_id: string;
};

export type TelemetryStatusSnapshot = {
  ok: boolean;
  kind: string;
  stage: string;
  status: string;
  active: boolean;
  claim: string;
  ts?: number;
  source_total: number;
  active_source_total: number;
  sources: TelemetrySourceStatus[];
  redaction: Record<string, unknown>;
  retention: Record<string, unknown>;
  sensing: Record<string, unknown>;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackReview = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  capture_mode: string;
  reviewed_event_count: number;
  total: number;
  limit: number;
  truncated: boolean;
  rating_counts: Record<string, number>;
  source_counts: Record<string, number>;
  tag_counts: Record<string, number>;
  quality_signals: string[];
  latest_feedback: {
    feedback_id: string;
    context_id: string;
    surface: string;
    rating: string;
    source_ids: string[];
    tags: string[];
    recorded_ts?: number;
  } | null;
  redacted: boolean;
  hidden_sensing: boolean;
  stores_prompt_body: boolean;
  stores_model_response: boolean;
  trains_model: boolean;
  writes_memory: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryQualityRecord = {
  ok: boolean;
  kind: string;
  status: string;
  source_id: string;
  memory_event_id: string;
  writes_memory: boolean;
  quality: Record<string, unknown>;
  memory_event: Record<string, unknown> | null;
  governance: Record<string, unknown>;
};

export type TelemetryContextFeedbackMemoryRetrievalEvent = {
  id: string;
  kind: string;
  action_type: string;
  classification: string;
  confidence?: number;
  retention: Record<string, unknown>;
  payload: Record<string, unknown>;
};

export type TelemetryContextFeedbackMemoryRetrievalReadback = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  count: number;
  total: number;
  skipped_count: number;
  items: TelemetryContextFeedbackMemoryRetrievalEvent[];
  reads_memory: boolean;
  writes_memory: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export type TelemetryContextFeedbackMemoryAssistancePolicy = {
  ok: boolean;
  kind: string;
  stage: string;
  source_id: string;
  status: string;
  policy_id: string;
  memory_readback_route: string;
  memory_policy_route: string;
  allowed_memory_event_kinds: string[];
  allowed_action_types: string[];
  allowed_classifications: string[];
  allowed_influence: string[];
  forbidden_influence: string[];
  assistance_guards: Record<string, unknown>;
  reads_memory: boolean;
  writes_memory: boolean;
  trains_model: boolean;
  grants_execution_authority: boolean;
  grants_mutation_authority: boolean;
  governance: Record<string, unknown>;
  next_smallest_truthful_gap: string;
};

export class TelemetryApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(message: string, opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown }) {
    super(message);
    this.name = "TelemetryApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.bodySnippet = opts?.bodySnippet;
    if (opts?.cause !== undefined) this.cause = opts.cause;
  }
}

export function parseTelemetryStatus(value: unknown): TelemetryStatusSnapshot {
  const raw = isRecord(value) ? value : {};
  const sources = Array.isArray(raw.sources)
    ? raw.sources.map(parseTelemetrySource).filter((item): item is TelemetrySourceStatus => item !== null)
    : [];

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    status: safeString(raw.status, "unknown"),
    active: safeBoolean(raw.active, false),
    claim: safeString(raw.claim, ""),
    ts: safeNumberOrUndefined(raw.ts),
    source_total: safeNumber(raw.source_total, sources.length),
    active_source_total: safeNumber(raw.active_source_total, sources.filter((source) => source.active).length),
    sources,
    redaction: recordOrEmpty(raw.redaction),
    retention: recordOrEmpty(raw.retention),
    sensing: recordOrEmpty(raw.sensing),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackReview(value: unknown): TelemetryContextFeedbackReview {
  const raw = isRecord(value) ? value : {};
  const latest = parseTelemetryContextFeedbackReviewItem(raw.latest_feedback);

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    capture_mode: safeString(raw.capture_mode, ""),
    reviewed_event_count: safeNumber(raw.reviewed_event_count, 0),
    total: safeNumber(raw.total, 0),
    limit: safeNumber(raw.limit, 0),
    truncated: safeBoolean(raw.truncated, false),
    rating_counts: numberRecord(raw.rating_counts),
    source_counts: numberRecord(raw.source_counts),
    tag_counts: numberRecord(raw.tag_counts),
    quality_signals: safeStringArray(raw.quality_signals),
    latest_feedback: latest,
    redacted: safeBoolean(raw.redacted, false),
    hidden_sensing: safeBoolean(raw.hidden_sensing, false),
    stores_prompt_body: safeBoolean(raw.stores_prompt_body, true),
    stores_model_response: safeBoolean(raw.stores_model_response, true),
    trains_model: safeBoolean(raw.trains_model, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryQualityRecord(
  value: unknown,
): TelemetryContextFeedbackMemoryQualityRecord {
  const raw = isRecord(value) ? value : {};
  const memoryEvent = recordOrEmpty(raw.memory_event);

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    status: safeString(raw.status, "unknown"),
    source_id: safeString(raw.source_id, ""),
    memory_event_id: safeString(raw.memory_event_id, ""),
    writes_memory: safeBoolean(raw.writes_memory, false),
    quality: recordOrEmpty(raw.quality),
    memory_event: Object.keys(memoryEvent).length > 0 ? memoryEvent : null,
    governance: recordOrEmpty(raw.governance),
  };
}

export function parseTelemetryContextFeedbackMemoryRetrievalReadback(
  value: unknown,
): TelemetryContextFeedbackMemoryRetrievalReadback {
  const raw = isRecord(value) ? value : {};
  const items = Array.isArray(raw.items)
    ? raw.items
        .map(parseTelemetryContextFeedbackMemoryRetrievalEvent)
        .filter((item): item is TelemetryContextFeedbackMemoryRetrievalEvent => item !== null)
    : [];

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    count: safeNumber(raw.count, items.length),
    total: safeNumber(raw.total, items.length),
    skipped_count: safeNumber(raw.skipped_count, 0),
    items,
    reads_memory: safeBoolean(raw.reads_memory, false),
    writes_memory: safeBoolean(raw.writes_memory, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export function parseTelemetryContextFeedbackMemoryAssistancePolicy(
  value: unknown,
): TelemetryContextFeedbackMemoryAssistancePolicy {
  const raw = isRecord(value) ? value : {};

  return {
    ok: safeBoolean(raw.ok, false),
    kind: safeString(raw.kind, ""),
    stage: safeString(raw.stage, ""),
    source_id: safeString(raw.source_id, ""),
    status: safeString(raw.status, "unknown"),
    policy_id: safeString(raw.policy_id, ""),
    memory_readback_route: safeString(raw.memory_readback_route, ""),
    memory_policy_route: safeString(raw.memory_policy_route, ""),
    allowed_memory_event_kinds: safeStringArray(raw.allowed_memory_event_kinds),
    allowed_action_types: safeStringArray(raw.allowed_action_types),
    allowed_classifications: safeStringArray(raw.allowed_classifications),
    allowed_influence: safeStringArray(raw.allowed_influence),
    forbidden_influence: safeStringArray(raw.forbidden_influence),
    assistance_guards: recordOrEmpty(raw.assistance_guards),
    reads_memory: safeBoolean(raw.reads_memory, true),
    writes_memory: safeBoolean(raw.writes_memory, true),
    trains_model: safeBoolean(raw.trains_model, true),
    grants_execution_authority: safeBoolean(raw.grants_execution_authority, true),
    grants_mutation_authority: safeBoolean(raw.grants_mutation_authority, true),
    governance: recordOrEmpty(raw.governance),
    next_smallest_truthful_gap: safeString(raw.next_smallest_truthful_gap, ""),
  };
}

export class TelemetryClient {
  readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  async getStatus(opts?: { signal?: AbortSignal }): Promise<TelemetryStatusSnapshot> {
    const url = this.url("/telemetry/status");
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry status request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry status request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryStatus(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry status response was not valid JSON.", { url, cause: err });
    }
  }

  async getContextFeedbackReview(opts?: { limit?: number; signal?: AbortSignal }): Promise<TelemetryContextFeedbackReview> {
    const limit = clampLimit(opts?.limit, 100);
    const url = this.url(`/telemetry/context/feedback/review?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback review request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback review request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackReview(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback review response was not valid JSON.", { url, cause: err });
    }
  }

  async recordContextFeedbackMemoryQuality(opts: {
    actor: string;
    reason: string;
    limit?: number;
    event_id?: string;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryQualityRecord> {
    const url = this.url("/telemetry/context/feedback/memory-quality");
    const body: Record<string, unknown> = {
      actor: opts.actor,
      reason: opts.reason,
      limit: clampLimit(opts.limit, 25),
    };
    const eventId = opts.event_id?.trim();
    if (eventId) body.event_id = eventId;

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: opts.signal,
      });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory-quality record request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback memory-quality record request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryQualityRecord(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory-quality record response was not valid JSON.", { url, cause: err });
    }
  }

  async getContextFeedbackMemoryRetrievalReadback(opts?: {
    limit?: number;
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryRetrievalReadback> {
    const limit = clampLimit(opts?.limit, 20);
    const url = this.url(`/telemetry/context/feedback/memory-retrieval-readback?limit=${limit}`);
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory retrieval readback request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback memory retrieval readback request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryRetrievalReadback(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory retrieval readback response was not valid JSON.", { url, cause: err });
    }
  }

  async getContextFeedbackMemoryAssistancePolicy(opts?: {
    signal?: AbortSignal;
  }): Promise<TelemetryContextFeedbackMemoryAssistancePolicy> {
    const url = this.url("/telemetry/context/feedback/memory-assistance-policy");
    let response: Response;
    try {
      response = await fetch(url, { method: "GET", signal: opts?.signal });
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory assistance policy request failed.", { url, cause: err });
    }

    const text = await response.text();
    if (!response.ok) {
      throw new TelemetryApiError(`HTTP ${response.status} for telemetry context feedback memory assistance policy request`, {
        status: response.status,
        url,
        bodySnippet: text.slice(0, 500),
      });
    }

    try {
      return parseTelemetryContextFeedbackMemoryAssistancePolicy(text ? JSON.parse(text) : {});
    } catch (err) {
      throw new TelemetryApiError("Telemetry context feedback memory assistance policy response was not valid JSON.", {
        url,
        cause: err,
      });
    }
  }

  private url(path: string): string {
    return `${this.baseUrl}${path}`;
  }
}

function parseTelemetrySource(value: unknown): TelemetrySourceStatus | null {
  if (!isRecord(value)) return null;
  const scope = recordOrEmpty(value.scope);

  return {
    id: safeString(value.id, ""),
    label: safeString(value.label, ""),
    description: safeString(value.description, ""),
    status: safeString(value.status, "unknown"),
    active: safeBoolean(value.active, false),
    visible_indicator: safeBoolean(value.visible_indicator, false),
    hidden_sensing: safeBoolean(value.hidden_sensing, false),
    scope: {
      status: safeString(scope.status, "unknown"),
      allowed_paths: safeStringArray(scope.allowed_paths),
      allowed_processes: safeStringArray(scope.allowed_processes),
      denied_by_default: safeBoolean(scope.denied_by_default, false),
    },
    redaction: recordOrEmpty(value.redaction),
    retention: recordOrEmpty(value.retention),
    signals: Array.isArray(value.signals) ? value.signals : [],
    expected_signals: safeStringArray(value.expected_signals),
    blocked_by: safeStringArray(value.blocked_by),
    authority: booleanRecord(value.authority),
    latest_event: parseTerminalEventSummary(value.latest_event),
    latest_snapshot: parseGitSnapshotSummary(value.latest_snapshot),
    latest_diagnostic: parseIdeDiagnosticSummary(value.latest_diagnostic),
    routes: stringRecord(value.routes),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function recordOrEmpty(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function booleanRecord(value: unknown): Record<string, boolean> {
  if (!isRecord(value)) return {};
  const out: Record<string, boolean> = {};
  for (const [key, raw] of Object.entries(value)) {
    out[key] = safeBoolean(raw, false);
  }
  return out;
}

function numberRecord(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {};
  const out: Record<string, number> = {};
  for (const [key, raw] of Object.entries(value)) {
    out[key] = safeNumber(raw, 0);
  }
  return out;
}

function stringRecord(value: unknown): Record<string, string> {
  if (!isRecord(value)) return {};
  const out: Record<string, string> = {};
  for (const [key, raw] of Object.entries(value)) {
    const text = safeString(raw, "").trim();
    if (text) out[key] = text;
  }
  return out;
}

function parseTelemetryContextFeedbackReviewItem(
  value: unknown,
): TelemetryContextFeedbackReview["latest_feedback"] {
  if (!isRecord(value)) return null;
  const item = {
    feedback_id: safeString(value.feedback_id, ""),
    context_id: safeString(value.context_id, ""),
    surface: safeString(value.surface, ""),
    rating: safeString(value.rating, ""),
    source_ids: safeStringArray(value.source_ids),
    tags: safeStringArray(value.tags),
    recorded_ts: safeNumberOrUndefined(value.recorded_ts),
  };
  if (!item.feedback_id && !item.context_id && !item.surface && !item.rating && item.source_ids.length === 0 && item.tags.length === 0) {
    return null;
  }
  return item;
}

function parseTelemetryContextFeedbackMemoryRetrievalEvent(
  value: unknown,
): TelemetryContextFeedbackMemoryRetrievalEvent | null {
  if (!isRecord(value)) return null;
  const id = safeString(value.id, "").trim();
  const kind = safeString(value.kind, "").trim();
  if (!id && !kind) return null;
  return {
    id,
    kind,
    action_type: safeString(value.action_type, ""),
    classification: safeString(value.classification, ""),
    confidence: safeNumberOrUndefined(value.confidence),
    retention: recordOrEmpty(value.retention),
    payload: recordOrEmpty(value.payload),
  };
}

function parseTerminalEventSummary(value: unknown): TelemetryTerminalEventSummary | null {
  if (!isRecord(value)) return null;
  return {
    event_id: safeString(value.event_id, ""),
    recorded_ts: safeNumberOrUndefined(value.recorded_ts),
    exit_code: value.exit_code === null ? null : safeNumberOrUndefined(value.exit_code),
    cwd: safeString(value.cwd, ""),
    command: safeString(value.command, ""),
    operation_id: safeString(value.operation_id, ""),
    approval_id: safeString(value.approval_id, ""),
    trace_id: safeString(value.trace_id, ""),
    run_id: safeString(value.run_id, ""),
    artifact_dir: safeString(value.artifact_dir, ""),
  };
}

function parseGitSnapshotSummary(value: unknown): TelemetryGitSnapshotSummary | null {
  if (!isRecord(value)) return null;
  return {
    branch: safeString(value.branch, ""),
    head: safeString(value.head, ""),
    upstream: safeString(value.upstream, ""),
    ahead: safeNumber(value.ahead, 0),
    behind: safeNumber(value.behind, 0),
    dirty: safeBoolean(value.dirty, false),
    changed_count: safeNumber(value.changed_count, 0),
    changed_paths: Array.isArray(value.changed_paths)
      ? value.changed_paths.map(parseGitChangedPath).filter((item): item is { status: string; path: string } => item !== null)
      : [],
    ts: safeNumberOrUndefined(value.ts),
  };
}

function parseGitChangedPath(value: unknown): { status: string; path: string } | null {
  if (!isRecord(value)) return null;
  return {
    status: safeString(value.status, ""),
    path: safeString(value.path, ""),
  };
}

function parseIdeDiagnosticSummary(value: unknown): TelemetryIdeDiagnosticSummary | null {
  if (!isRecord(value)) return null;
  return {
    event_id: safeString(value.event_id, ""),
    recorded_ts: safeNumberOrUndefined(value.recorded_ts),
    source: safeString(value.source, ""),
    workspace: safeString(value.workspace, ""),
    file: safeString(value.file, ""),
    diagnostic_count: safeNumber(value.diagnostic_count, 0),
    highest_severity: safeString(value.highest_severity, ""),
    operation_id: safeString(value.operation_id, ""),
    approval_id: safeString(value.approval_id, ""),
    trace_id: safeString(value.trace_id, ""),
    run_id: safeString(value.run_id, ""),
  };
}

function safeString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function safeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeString(item, "").trim()).filter(Boolean);
}

function safeBoolean(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true") return true;
    if (normalized === "false") return false;
  }
  return fallback;
}

function safeNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function safeNumberOrUndefined(value: unknown): number | undefined {
  const parsed = safeNumber(value, Number.NaN);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function clampLimit(value: unknown, fallback: number): number {
  const parsed = safeNumber(value, fallback);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(Math.max(Math.trunc(parsed), 1), 500);
}
