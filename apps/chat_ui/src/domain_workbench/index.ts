/**
 * Domain Workbench module (UI).
 *
 * Framework-agnostic client + types for domain-scoped operations.
 *
 * Domain philosophy:
 *  - Domains are the unit of isolation for: memory, trust, plugins, governance.
 *  - UI must always make domain context explicit and never “guess” implicitly.
 *
 * This module supports:
 *  - List domains (registry) with pagination + filtering
 *  - Get domain metadata
 *  - Create domain (governed; may generate approval_id)
 *  - Update domain (governed; may generate approval_id)
 *  - Delete domain (governed; may generate approval_id)
 *  - Domain-scoped resource summary (metadata only)
 *
 * Non-goals:
 *  - No React imports
 *  - No direct mutation of sensitive resources from the browser
 *  - No assumption that domain schema is stable (defensive parsing)
 *
 * Endpoints:
 *  - Defaults are conventional. Override with options to match backend contracts.
 */

export type DomainStatus = "active" | "archived" | "disabled" | "error" | string;

export type DomainMeta = {
  id: string;
  name: string;

  status?: DomainStatus;

  // timestamps (unix seconds preferred; ms tolerated)
  created_ts?: number;
  updated_ts?: number;

  // governance hints
  risk?: string;
  requires_approval?: boolean;

  // forward-compatible metadata
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type DomainRegistryResponse = {
  items: DomainMeta[];
};

export type DomainCreateRequest = {
  id?: string; // optional explicit id; backend may generate
  name: string;
  description?: string;
  tags?: string[];

  // justification for governed creation
  reason?: string;

  // forward-compatible non-secret options
  meta?: Record<string, unknown>;
};

export type DomainCreateResponse = {
  ok: boolean;
  id?: string;
  status?: DomainStatus;

  // governance integration
  approval_id?: string;

  // backend request tracking
  request_id?: string;

  message?: string;
};

export type DomainUpdateRequest = {
  domain_id: string;

  // Only metadata-level updates (no secrets)
  updates: Partial<Pick<DomainMeta, "name" | "status" | "tags" | "meta">>;

  // governance justification
  reason?: string;
};

export type DomainUpdateResponse = {
  ok: boolean;
  id: string;
  status?: DomainStatus;

  approval_id?: string;
  request_id?: string;
  message?: string;
};

export type DomainDeleteRequest = {
  domain_id: string;
  reason?: string;
};

export type DomainDeleteResponse = {
  ok: boolean;
  id: string;

  approval_id?: string;
  request_id?: string;
  message?: string;
};

export type DomainResourceSummary = {
  domain_id: string;

  // high-level summaries only (no secrets)
  trust_level?: number;
  memory_items?: number;
  plugin_count?: number;

  // forward-compatible
  meta?: Record<string, unknown>;
};

export class DomainWorkbenchApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "DomainWorkbenchApiError";
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

function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (typeof v === "string" && v.trim() === "") continue;

    if (Array.isArray(v)) {
      // Encode arrays as comma-separated list (conventional, server-friendly).
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
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");

    return await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new DomainWorkbenchApiError("Domain workbench request aborted/timed out", { url, cause: err });
    }
    throw new DomainWorkbenchApiError("Domain workbench request failed", { url, cause: err });
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
    throw new DomainWorkbenchApiError(`HTTP ${res.status} for domain workbench request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  return await res.json();
}

function parseDomainMeta(raw: unknown): DomainMeta | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const name = safeString(raw.name, id);

  const d: DomainMeta = { id, name };

  const status = safeString(raw.status, "");
  if (status) d.status = status;

  const created = safeNumber(raw.created_ts, 0);
  if (created > 0) d.created_ts = created;

  const updated = safeNumber(raw.updated_ts, 0);
  if (updated > 0) d.updated_ts = updated;

  const risk = safeString(raw.risk, "");
  if (risk) d.risk = risk;

  if (typeof raw.requires_approval === "boolean") d.requires_approval = raw.requires_approval;

  if (Array.isArray(raw.tags)) {
    const tags = (raw.tags as unknown[]).map((x) => safeString(x)).filter((x) => x.length > 0);
    if (tags.length) d.tags = tags;
  }

  if (isRecord(raw.meta)) d.meta = raw.meta;

  return d;
}

function parseResourceSummary(raw: unknown): DomainResourceSummary | null {
  if (!isRecord(raw)) return null;

  const domainId = safeString(raw.domain_id, safeString(raw.id, ""));
  if (!domainId) return null;

  const s: DomainResourceSummary = { domain_id: domainId };

  const trust = safeNumber(raw.trust_level, NaN);
  if (Number.isFinite(trust)) s.trust_level = trust;

  const mem = safeNumber(raw.memory_items, NaN);
  if (Number.isFinite(mem)) s.memory_items = mem;

  const plugins = safeNumber(raw.plugin_count, NaN);
  if (Number.isFinite(plugins)) s.plugin_count = plugins;

  if (isRecord(raw.meta)) s.meta = raw.meta;

  return s;
}

export type DomainWorkbenchEndpoints = {
  list: (q?: { limit?: number; offset?: number; status?: string; tags?: string[] }) => string;
  get: (domain_id: string) => string;
  create: () => string;
  update: () => string;
  delete: () => string;
  summary: (domain_id: string) => string;
};

export function defaultDomainWorkbenchEndpoints(): DomainWorkbenchEndpoints {
  return {
    list: (q) =>
      `/domains/list${buildQuery({
        limit: q?.limit,
        offset: q?.offset,
        status: q?.status,
        tags: q?.tags,
      })}`,
    get: (domain_id) => `/domains/get${buildQuery({ domain_id })}`,
    create: () => "/domains/create",
    update: () => "/domains/update",
    delete: () => "/domains/delete",
    summary: (domain_id) => `/domains/summary${buildQuery({ domain_id })}`,
  };
}

export type DomainWorkbenchClientOptions = {
  endpoints?: DomainWorkbenchEndpoints;
  defaultTimeoutMs?: number;
};

export class DomainWorkbenchClient {
  readonly baseUrl: string;
  readonly endpoints: DomainWorkbenchEndpoints;
  readonly defaultTimeoutMs: number;

  constructor(baseUrl: string, opts?: DomainWorkbenchClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) {
      throw new Error("DomainWorkbenchClient requires a non-empty baseUrl");
    }

    this.endpoints = opts?.endpoints ?? defaultDomainWorkbenchEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  async list(opts?: {
    limit?: number;
    offset?: number;
    status?: DomainStatus;
    tags?: string[];
    signal?: AbortSignal;
    timeoutMs?: number;
  }): Promise<DomainRegistryResponse> {
    const url = this.url(
      this.endpoints.list({
        limit: opts?.limit,
        offset: opts?.offset,
        status: opts?.status as string | undefined,
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
      : Array.isArray((json as Record<string, unknown>).domains)
        ? ((json as Record<string, unknown>).domains as unknown[])
        : [];

    const items = raw.map(parseDomainMeta).filter((x): x is DomainMeta => x !== null);
    return { items };
  }

  async get(domain_id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<DomainMeta | null> {
    const safeId = (domain_id || "").trim();
    if (!safeId) return null;

    const url = this.url(this.endpoints.get(safeId));
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (isRecord(json) && "item" in json) return parseDomainMeta((json as Record<string, unknown>).item);
    return parseDomainMeta(json);
  }

  async create(req: DomainCreateRequest, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<DomainCreateResponse> {
    const url = this.url(this.endpoints.create());
    const json = await fetchJson(url, {
      method: "POST",
      body: JSON.stringify(req),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true, message: "created" };

    const r = json as Record<string, unknown>;
    return {
      ok: Boolean(r.ok ?? true),
      id: safeString(r.id, safeString(r.domain_id, "")),
      status: safeString(r.status, ""),
      approval_id: safeString(r.approval_id, ""),
      request_id: safeString(r.request_id, ""),
      message: safeString(r.message, ""),
    };
  }

  async update(req: DomainUpdateRequest, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<DomainUpdateResponse> {
    const safeId = (req.domain_id || "").trim();
    if (!safeId) {
      throw new Error("update requires domain_id");
    }

    const url = this.url(this.endpoints.update());
    const json = await fetchJson(url, {
      method: "PATCH",
      body: JSON.stringify({
        domain_id: safeId,
        updates: req.updates,
        reason: req.reason,
      }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true, id: safeId };

    const r = json as Record<string, unknown>;
    return {
      ok: Boolean(r.ok ?? true),
      id: safeString(r.id, safeString(r.domain_id, safeId)),
      status: safeString(r.status, ""),
      approval_id: safeString(r.approval_id, ""),
      request_id: safeString(r.request_id, ""),
      message: safeString(r.message, ""),
    };
  }

  async delete(req: DomainDeleteRequest, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<DomainDeleteResponse> {
    const safeId = (req.domain_id || "").trim();
    if (!safeId) {
      throw new Error("delete requires domain_id");
    }

    const url = this.url(this.endpoints.delete());
    const json = await fetchJson(url, {
      method: "POST",
      body: JSON.stringify({
        domain_id: safeId,
        reason: req.reason,
      }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true, id: safeId };

    const r = json as Record<string, unknown>;
    return {
      ok: Boolean(r.ok ?? true),
      id: safeString(r.id, safeString(r.domain_id, safeId)),
      approval_id: safeString(r.approval_id, ""),
      request_id: safeString(r.request_id, ""),
      message: safeString(r.message, ""),
    };
  }

  async summary(domain_id: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<DomainResourceSummary | null> {
    const safeId = (domain_id || "").trim();
    if (!safeId) return null;

    const url = this.url(this.endpoints.summary(safeId));
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (isRecord(json) && "summary" in json) return parseResourceSummary((json as Record<string, unknown>).summary);
    return parseResourceSummary(json);
  }
}
