/**
 * Digital Twin Center module (UI).
 *
 * Framework-agnostic client + types for interacting with Digital Twins metadata/state.
 *
 * Scope:
 *  - List available twins (metadata)
 *  - Read a twin snapshot (state summary)
 *  - Submit requests for simulation/validation/control as governed actions (optional)
 *
 * Non-goals:
 *  - No React imports
 *  - No long-lived background loops
 *  - No direct "control" from browser without governance (approval/policy)
 *
 * Endpoint philosophy:
 *  - Default endpoints are conventional and can be overridden via options.
 *  - Parsing is defensive: tolerate unknown fields and API evolution.
 */

export type TwinStatus =
  | "ready"
  | "building"
  | "simulating"
  | "degraded"
  | "offline"
  | "error"
  | string;

export type TwinKind =
  | "asset"
  | "process"
  | "facility"
  | "system"
  | "model"
  | string;

export type TwinMeta = {
  id: string;
  name: string;

  kind?: TwinKind;
  status?: TwinStatus;

  // Ownership/scope
  domain?: string;

  // Timestamps (unix seconds preferred; ms tolerated by consumers)
  created_ts?: number;
  updated_ts?: number;

  // Optional safety/ops hints
  risk?: string;
  requires_approval?: boolean;

  // Forward-compatible metadata
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type TwinSnapshot = {
  id: string;
  ts: number;

  status?: TwinStatus;
  summary?: string;

  // State is intentionally opaque to keep UI forward compatible.
  // UI components can render this as JSON or selected fields later.
  state?: Record<string, unknown>;

  // Optional health metrics
  health?: Record<string, unknown>;
};

export type TwinListResponse = { items: TwinMeta[] };

export type TwinAction =
  | "simulate"
  | "validate_safety"
  | "export"
  | "request_control"
  | string;

export type TwinActionRequest = {
  twin_id: string;
  action: TwinAction;

  // Operator justification (often required for approvals)
  reason?: string;

  // Optional action parameters (never secrets)
  params?: Record<string, unknown>;
};

export type TwinActionResponse = {
  ok: boolean;
  twin_id: string;
  action: TwinAction;

  // For governance integration
  approval_id?: string;

  // Backend request tracking
  request_id?: string;

  status?: string;
};

export class DigitalTwinApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "DigitalTwinApiError";
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

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
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
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");

    return await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new DigitalTwinApiError("Digital twin request aborted/timed out", { url, cause: err });
    }
    throw new DigitalTwinApiError("Digital twin request failed", { url, cause: err });
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
    throw new DigitalTwinApiError(`HTTP ${res.status} for digital twin request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  return await res.json();
}

function parseTwinMeta(raw: unknown): TwinMeta | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const name = safeString(raw.name, id);

  const t: TwinMeta = {
    id,
    name,
  };

  const kind = safeString(raw.kind, "");
  if (kind) t.kind = kind;

  const status = safeString(raw.status, "");
  if (status) t.status = status;

  const domain = safeString(raw.domain, "");
  if (domain) t.domain = domain;

  const created = safeNumber(raw.created_ts, 0);
  if (created > 0) t.created_ts = created;

  const updated = safeNumber(raw.updated_ts, 0);
  if (updated > 0) t.updated_ts = updated;

  const risk = safeString(raw.risk, "");
  if (risk) t.risk = risk;

  if (typeof raw.requires_approval === "boolean") t.requires_approval = raw.requires_approval;

  if (Array.isArray(raw.tags)) {
    const tags = (raw.tags as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (tags.length) t.tags = tags;
  }

  if (isRecord(raw.meta)) t.meta = raw.meta;

  return t;
}

function parseTwinSnapshot(raw: unknown): TwinSnapshot | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const ts = safeNumber(raw.ts, 0);

  const s: TwinSnapshot = {
    id,
    ts,
  };

  const status = safeString(raw.status, "");
  if (status) s.status = status;

  const summary = safeString(raw.summary, "");
  if (summary) s.summary = summary;

  if (isRecord(raw.state)) s.state = raw.state;
  if (isRecord(raw.health)) s.health = raw.health;

  return s;
}

export type DigitalTwinEndpoints = {
  list: () => string;
  get: (id: string) => string;
  snapshot: (id: string) => string;
  action: () => string;
};

export function defaultDigitalTwinEndpoints(): DigitalTwinEndpoints {
  return {
    list: () => "/industrial/digital_twins/list",
    get: (id) => `/industrial/digital_twins/get?id=${encodeURIComponent(id)}`,
    snapshot: (id) => `/industrial/digital_twins/snapshot?id=${encodeURIComponent(id)}`,
    action: () => "/industrial/digital_twins/action",
  };
}

export type DigitalTwinClientOptions = {
  endpoints?: DigitalTwinEndpoints;
  defaultTimeoutMs?: number;
};

export class DigitalTwinClient {
  readonly baseUrl: string;
  readonly endpoints: DigitalTwinEndpoints;
  readonly defaultTimeoutMs: number;

  constructor(baseUrl: string, opts?: DigitalTwinClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) {
      throw new Error("DigitalTwinClient requires a non-empty baseUrl");
    }

    this.endpoints = opts?.endpoints ?? defaultDigitalTwinEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  async list(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<TwinListResponse> {
    const url = this.url(this.endpoints.list());
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).twins)
        ? ((json as Record<string, unknown>).twins as unknown[])
        : [];

    const items = raw.map(parseTwinMeta).filter((x): x is TwinMeta => x !== null);
    return { items };
  }

  async get(id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<TwinMeta | null> {
    const safeId = (id || "").trim();
    if (!safeId) return null;

    const url = this.url(this.endpoints.get(safeId));
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (isRecord(json) && "item" in json) return parseTwinMeta((json as Record<string, unknown>).item);
    return parseTwinMeta(json);
  }

  async snapshot(id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<TwinSnapshot | null> {
    const safeId = (id || "").trim();
    if (!safeId) return null;

    const url = this.url(this.endpoints.snapshot(safeId));
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (isRecord(json) && "snapshot" in json) return parseTwinSnapshot((json as Record<string, unknown>).snapshot);
    return parseTwinSnapshot(json);
  }

  /**
   * Submit a governed action request.
   * Server decides whether to:
   *  - execute immediately
   *  - create an approval item and return approval_id
   *  - reject based on policy
   */
  async requestAction(
    req: TwinActionRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<TwinActionResponse> {
    const url = this.url(this.endpoints.action());
    const json = await fetchJson(url, {
      method: "POST",
      body: JSON.stringify(req),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) {
      return { ok: true, twin_id: req.twin_id, action: req.action };
    }

    const r = json as Record<string, unknown>;
    return {
      ok: Boolean(r.ok ?? true),
      twin_id: safeString(r.twin_id, req.twin_id),
      action: safeString(r.action, req.action),
      approval_id: safeString(r.approval_id, ""),
      request_id: safeString(r.request_id, ""),
      status: safeString(r.status, ""),
    };
  }
}
