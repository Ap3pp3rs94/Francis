/**
 * Credential Manager module (UI).
 *
 * This module is a typed, defensive client for credential *metadata* operations.
 * It is intentionally designed to avoid secrets ever touching the browser.
 *
 * Design contract:
 *  1) NO SECRET MATERIAL:
 *     - Do not expose credential values, private keys, bearer tokens, etc.
 *     - Only handle metadata, references, and governed actions.
 *
 *  2) Framework-agnostic:
 *     - No React imports, no DOM dependencies.
 *
 *  3) Defensive parsing:
 *     - Treat all JSON as untrusted; parse carefully; tolerate API evolution.
 *
 *  4) Forward-compatible endpoints:
 *     - Endpoint mapping is configurable to match backend route changes without
 *       rewriting call sites.
 *
 * Suggested backend pattern (future-ready):
 *   - list:        GET  /credentials/list
 *   - scopes:      GET  /credentials/scopes
 *   - delegations: GET  /credentials/delegations
 *   - request:     POST /credentials/request   (creates an approval item)
 *   - revoke:      POST /credentials/revoke    (policy/approval gated)
 *
 * If your backend differs, override endpoints via CredentialManagerClientOptions.
 */

export type CredentialStatus = "active" | "revoked" | "expired" | "pending" | "error" | string;

export type CredentialType =
  | "api_key"
  | "oauth_token"
  | "jwt"
  | "ssh_key"
  | "db_password"
  | "service_account"
  | string;

export type CredentialScope = {
  id: string;
  name: string;
  description?: string;

  // Optional policy/governance hints
  requires_approval?: boolean;
  risk?: string;

  // Forward-compatible metadata
  meta?: Record<string, unknown>;
};

export type CredentialRef = {
  id: string; // credential identifier/reference
  type: CredentialType;
  status: CredentialStatus;

  // Ownership / linkage
  scope_id?: string;
  provider?: string; // e.g., "openai", "aws", "postgres", "github"
  domain?: string;
  actor?: string; // who created/owns it

  // Timestamps (unix seconds preferred; ms tolerated by consumers)
  created_ts?: number;
  last_used_ts?: number;
  expires_ts?: number;

  // Non-secret info
  label?: string; // user-friendly alias
  fingerprint?: string; // hash/fingerprint for keys
  hint?: string; // redacted display hint like "sk-...abcd"

  meta?: Record<string, unknown>;
};

export type Delegation = {
  id: string;
  ts: number;
  from?: string;
  to?: string;
  scope_id?: string;
  status?: string;
  reason?: string;
  meta?: Record<string, unknown>;
};

export type CredentialListResponse = { items: CredentialRef[] };
export type ScopeListResponse = { items: CredentialScope[] };
export type DelegationListResponse = { items: Delegation[] };

export type CredentialRequest = {
  scope_id: string;
  provider?: string;
  type?: CredentialType;
  label?: string;
  actor?: string;

  // Optional justification (often required for approvals)
  reason?: string;

  // Forward-compatible options bag (never include secret material)
  meta?: Record<string, unknown>;
};

export type CredentialRequestResponse = {
  ok: boolean;
  request_id?: string;
  approval_id?: string;
  status?: string;
};

export type CredentialRevokeRequest = {
  id: string;
  reason?: string;
  actor?: string;
};

export type CredentialRevokeResponse = {
  ok: boolean;
  id: string;
  status?: CredentialStatus;
};

const DEFAULT_CREDENTIAL_MUTATION_ACTOR = "chat_ui.credentials";

export class CredentialManagerApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "CredentialManagerApiError";
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

function safeBool(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function credentialMutationErrorMessage(json: Record<string, unknown>, fallback: string): string {
  return safeString(json.error, "") || safeString(json.message, "") || fallback;
}

function assertCredentialMutationAllowed(json: unknown, fallback: string): void {
  if (!isRecord(json)) return;
  if (safeBool(json.ok, true) === false) {
    throw new CredentialManagerApiError(credentialMutationErrorMessage(json, fallback));
  }
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
    if (externalSignal.aborted) {
      onExternalAbort();
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }

  try {
    const headers = new Headers(fetchInit.headers ?? undefined);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");

    const res = await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });

    // If fetch throws AbortError, we detect timeout via timedOut in caller
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _timedOut = timedOut;

    return res;
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
    throw new CredentialManagerApiError(`HTTP ${res.status} for credential manager request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  return await res.json();
}

function parseScope(raw: unknown): CredentialScope | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const name = safeString(raw.name, id);
  const s: CredentialScope = {
    id,
    name,
  };

  const desc = safeString(raw.description, "");
  if (desc) s.description = desc;

  if (typeof raw.requires_approval === "boolean") s.requires_approval = raw.requires_approval;

  const risk = safeString(raw.risk, "");
  if (risk) s.risk = risk;

  if (isRecord(raw.meta)) s.meta = raw.meta;

  return s;
}

function parseCredentialRef(raw: unknown): CredentialRef | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const ref: CredentialRef = {
    id,
    type: safeString(raw.type, "api_key"),
    status: safeString(raw.status, "active"),
  };

  const scopeId = safeString(raw.scope_id, "");
  if (scopeId) ref.scope_id = scopeId;

  const provider = safeString(raw.provider, "");
  if (provider) ref.provider = provider;

  const domain = safeString(raw.domain, "");
  if (domain) ref.domain = domain;

  const actor = safeString(raw.actor, "");
  if (actor) ref.actor = actor;

  const created = safeNumber(raw.created_ts, 0);
  if (created > 0) ref.created_ts = created;

  const lastUsed = safeNumber(raw.last_used_ts, 0);
  if (lastUsed > 0) ref.last_used_ts = lastUsed;

  const expires = safeNumber(raw.expires_ts, 0);
  if (expires > 0) ref.expires_ts = expires;

  const label = safeString(raw.label, "");
  if (label) ref.label = label;

  const fingerprint = safeString(raw.fingerprint, "");
  if (fingerprint) ref.fingerprint = fingerprint;

  const hint = safeString(raw.hint, "");
  if (hint) ref.hint = hint;

  if (isRecord(raw.meta)) ref.meta = raw.meta;

  return ref;
}

function parseDelegation(raw: unknown): Delegation | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id);
  if (!id) return null;

  const d: Delegation = {
    id,
    ts: safeNumber(raw.ts, 0),
  };

  const from = safeString(raw.from, "");
  if (from) d.from = from;

  const to = safeString(raw.to, "");
  if (to) d.to = to;

  const scopeId = safeString(raw.scope_id, "");
  if (scopeId) d.scope_id = scopeId;

  const status = safeString(raw.status, "");
  if (status) d.status = status;

  const reason = safeString(raw.reason, "");
  if (reason) d.reason = reason;

  if (isRecord(raw.meta)) d.meta = raw.meta;

  return d;
}

export type CredentialManagerEndpoints = {
  listCredentials: () => string;
  listScopes: () => string;
  listDelegations: () => string;
  requestCredential: () => string;
  revokeCredential: () => string;
};

export function defaultCredentialManagerEndpoints(): CredentialManagerEndpoints {
  return {
    listCredentials: () => "/credentials/list",
    listScopes: () => "/credentials/scopes",
    listDelegations: () => "/credentials/delegations",
    requestCredential: () => "/credentials/request",
    revokeCredential: () => "/credentials/revoke",
  };
}

export type CredentialManagerClientOptions = {
  endpoints?: CredentialManagerEndpoints;
  defaultTimeoutMs?: number;
};

export class CredentialManagerClient {
  readonly baseUrl: string;
  readonly endpoints: CredentialManagerEndpoints;
  readonly defaultTimeoutMs: number;

  constructor(baseUrl: string, opts?: CredentialManagerClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) {
      throw new Error("CredentialManagerClient requires a non-empty baseUrl");
    }

    this.endpoints = opts?.endpoints ?? defaultCredentialManagerEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  async listCredentials(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<CredentialListResponse> {
    const url = this.url(this.endpoints.listCredentials());
    const json = await fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).credentials)
        ? ((json as Record<string, unknown>).credentials as unknown[])
        : [];

    const items = raw.map(parseCredentialRef).filter((x): x is CredentialRef => x !== null);
    return { items };
  }

  async listScopes(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<ScopeListResponse> {
    const url = this.url(this.endpoints.listScopes());
    const json = await fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).scopes)
        ? ((json as Record<string, unknown>).scopes as unknown[])
        : [];

    const items = raw.map(parseScope).filter((x): x is CredentialScope => x !== null);
    return { items };
  }

  async listDelegations(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<DelegationListResponse> {
    const url = this.url(this.endpoints.listDelegations());
    const json = await fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs });

    if (!isRecord(json)) return { items: [] };

    const raw = Array.isArray((json as Record<string, unknown>).items)
      ? ((json as Record<string, unknown>).items as unknown[])
      : Array.isArray((json as Record<string, unknown>).delegations)
        ? ((json as Record<string, unknown>).delegations as unknown[])
        : [];

    const items = raw.map(parseDelegation).filter((x): x is Delegation => x !== null);
    return { items };
  }

  /**
   * Request a credential.
   * This should be approval/policy gated on the server side.
   * This client never sends secret material.
   */
  async requestCredential(
    req: CredentialRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<CredentialRequestResponse> {
    const url = this.url(this.endpoints.requestCredential());
    const body = { ...req, actor: req.actor?.trim() || DEFAULT_CREDENTIAL_MUTATION_ACTOR };
    const json = await fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true };
    assertCredentialMutationAllowed(json, "Credential request failed.");

    return {
      ok: safeBool((json as Record<string, unknown>).ok, true),
      request_id: safeString((json as Record<string, unknown>).request_id, ""),
      approval_id: safeString((json as Record<string, unknown>).approval_id, ""),
      status: safeString((json as Record<string, unknown>).status, ""),
    };
  }

  /**
   * Revoke a credential by reference id.
   * This should be approval/policy gated on the server side.
   */
  async revokeCredential(
    req: CredentialRevokeRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<CredentialRevokeResponse> {
    const url = this.url(this.endpoints.revokeCredential());
    const body = { ...req, actor: req.actor?.trim() || DEFAULT_CREDENTIAL_MUTATION_ACTOR };
    const json = await fetchJson(url, {
      method: "POST",
      body: JSON.stringify(body),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    if (!isRecord(json)) return { ok: true, id: req.id };
    assertCredentialMutationAllowed(json, "Credential revocation failed.");

    return {
      ok: safeBool((json as Record<string, unknown>).ok, true),
      id: safeString((json as Record<string, unknown>).id, req.id),
      status: safeString((json as Record<string, unknown>).status, ""),
    };
  }
}
