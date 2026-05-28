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
