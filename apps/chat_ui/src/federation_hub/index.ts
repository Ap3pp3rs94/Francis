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

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeTs(ts: number): number {
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : ts;
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

export type FederationEndpoints = {
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
