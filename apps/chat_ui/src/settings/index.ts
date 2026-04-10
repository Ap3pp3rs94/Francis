/**
 * Settings module (UI).
 *
 * This module is the browser-side "control plane" for:
 *  - Server introspection: health, runtime info, effective config snapshot
 *  - Feature flags (read by default; optionally mutable)
 *  - UI preferences (local, versioned, defensive storage)
 *
 * Design contract:
 *  1) Framework-agnostic core:
 *     - This file contains NO React imports.
 *     - Consumers (React components) should live alongside (e.g., SettingsPanel.tsx).
 *
 *  2) Defensive parsing:
 *     - Treat all JSON as untrusted.
 *     - Accept reasonable alias shapes for forward/back compatibility.
 *
 *  3) Safe-by-default mutations:
 *     - "Write" endpoints exist but are opt-in (mutationsEnabled=false by default).
 *     - Server should enforce approvals/policies for any mutation.
 *
 *  4) Forward-compatible endpoints:
 *     - Endpoints are configurable and can probe multiple candidate paths.
 *     - This lets backend routes evolve without breaking the UI immediately.
 */

export type UnixSeconds = number;

export type SystemInfo = {
  service?: string;
  instance_id?: string;
  version?: string;
  build?: string;
  git_sha?: string;

  env_profile?: string;
  run_mode?: string;

  started_ts?: UnixSeconds;
  uptime_s?: number;

  host?: string;
  pid?: number;

  python?: {
    version?: string;
    executable?: string;
    implementation?: string;
    platform?: string;
  };

  meta?: Record<string, unknown>;
};

export type HealthCheck = {
  name?: string;
  ok: boolean;
  detail?: string;
  latency_ms?: number;
  ts?: UnixSeconds;
  meta?: Record<string, unknown>;
};

export type SystemHealth = {
  ok: boolean;
  status?: string; // "ok" | "degraded" | "down" | ...
  ts?: UnixSeconds;
  checks?: HealthCheck[];
  meta?: Record<string, unknown>;
};

export type FeatureFlag = {
  key: string;
  enabled: boolean;

  description?: string;
  source?: string; // e.g., "env", "config", "runtime"
  ts?: UnixSeconds;

  meta?: Record<string, unknown>;
};

export type FeatureFlagsResponse = {
  items: FeatureFlag[];
};

export type EffectiveConfigSnapshot = {
  ts?: UnixSeconds;
  env_profile?: string;
  run_mode?: string;

  // The effective, merged config. Shape is intentionally open-ended.
  config: Record<string, unknown>;

  // Optional provenance hints (forward compatible)
  sources?: Record<string, string>;
  meta?: Record<string, unknown>;
};

/**
 * A controlled server mutation request.
 * The backend is expected to enforce approvals/policy; the UI just submits intent.
 */
export type ConfigMutationOp = "set" | "unset" | "merge" | "append" | "remove" | string;

export type ConfigMutationRequest = {
  op: ConfigMutationOp;

  /**
   * Path format is intentionally flexible:
   *  - dot.path.like.this
   *  - /json/pointer/style
   *
   * Backend decides what it supports; UI remains forward-compatible.
   */
  path: string;

  value?: unknown;

  // Strongly recommended: justification / governance context
  reason?: string;
  domain?: string;
  actor?: string;

  meta?: Record<string, unknown>;
};

export type ConfigMutationResponse = {
  ok: boolean;

  /**
   * If mutations are approval-gated, backend can return:
   *  - approval_id: created approval item
   *  - status: "pending" | "approved" | "rejected" | ...
   */
  approval_id?: string;
  status?: string;

  /**
   * If applied immediately (no approval required), backend can return:
   *  - applied: true
   *  - resulting_value or snapshot
   */
  applied?: boolean;
  resulting_value?: unknown;

  message?: string;
  meta?: Record<string, unknown>;
};

export class SettingsApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly requestId?: string;
  readonly bodySnippet?: string;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; requestId?: string; bodySnippet?: string; cause?: unknown },
  ) {
    super(message);
    this.name = "SettingsApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.requestId = opts?.requestId;
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

function safeBoolean(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function normalizeUnixSeconds(ts: unknown): UnixSeconds | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  // Heuristic: if it looks like milliseconds, normalize to seconds.
  if (ts > 10_000_000_000) return Math.floor(ts / 1000);
  return Math.floor(ts);
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function buildQuery(params: Record<string, unknown> | undefined): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      for (const item of v) sp.append(k, String(item));
    } else {
      sp.set(k, String(v));
    }
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function readTextSnippet(res: Response, maxChars = 4096): Promise<string> {
  try {
    const txt = await res.text();
    return txt.length > maxChars ? `${txt.slice(0, maxChars)}…` : txt;
  } catch {
    return "";
  }
}

type TimeoutFetchInit = RequestInit & {
  timeoutMs?: number;
  /**
   * Optional auth token (bearer). Intentionally not stored anywhere by this module.
   * Prefer cookies in production; tokens are acceptable for local/internal consoles.
   */
  bearerToken?: string | null;

  /**
   * Extra headers (merged with defaults).
   */
  headersExtra?: Record<string, string>;
};

async function fetchWithTimeout(url: string, init?: TimeoutFetchInit): Promise<Response> {
  const { timeoutMs = 20_000, signal: externalSignal, bearerToken, headersExtra, ...fetchInit } = init ?? {};

  const controller = new AbortController();
  let timeoutId: number | null = null;

  if (timeoutMs > 0) {
    timeoutId = window.setTimeout(() => {
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

    // Defaults: this module is JSON-centric.
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (fetchInit.method && fetchInit.method !== "GET" && fetchInit.method !== "HEAD") {
      if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    }

    if (bearerToken) {
      // NOTE: Token handling is caller-owned; do not persist in localStorage here.
      headers.set("Authorization", `Bearer ${bearerToken}`);
    }

    if (headersExtra) {
      for (const [k, v] of Object.entries(headersExtra)) headers.set(k, v);
    }

    return await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });
  } finally {
    if (timeoutId !== null) window.clearTimeout(timeoutId);
    if (externalSignal && !externalSignal.aborted) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

async function fetchJson(url: string, init?: TimeoutFetchInit): Promise<{ res: Response; json: unknown }> {
  const res = await fetchWithTimeout(url, init);

  if (!res.ok) {
    const snippet = await readTextSnippet(res);
    const requestId =
      res.headers.get("x-request-id") ??
      res.headers.get("x-correlation-id") ??
      res.headers.get("x-trace-id") ??
      undefined;

    throw new SettingsApiError(`HTTP ${res.status} for settings request`, {
      status: res.status,
      url,
      requestId,
      bodySnippet: snippet,
    });
  }

  const json = await res.json();
  return { res, json };
}

function parseSystemInfo(raw: unknown): SystemInfo {
  if (!isRecord(raw)) return {};

  // Accept alias shapes:
  //  - { service, version, env_profile, ... }
  //  - { info: { ... } }
  const obj = isRecord(raw.info) ? (raw.info as Record<string, unknown>) : raw;

  const info: SystemInfo = {
    service: safeString(obj.service, ""),
    instance_id: safeString(obj.instance_id, ""),
    version: safeString(obj.version, ""),
    build: safeString(obj.build, ""),
    git_sha: safeString(obj.git_sha, ""),

    env_profile: safeString(obj.env_profile, ""),
    run_mode: safeString(obj.run_mode, ""),

    started_ts: normalizeUnixSeconds(obj.started_ts),
    uptime_s: safeNumber(obj.uptime_s, 0),

    host: safeString(obj.host, ""),
    pid: safeNumber(obj.pid, 0),
  };

  // Clean up empties (keeps logs/UI tidy)
  if (!info.service) delete info.service;
  if (!info.instance_id) delete info.instance_id;
  if (!info.version) delete info.version;
  if (!info.build) delete info.build;
  if (!info.git_sha) delete info.git_sha;

  if (!info.env_profile) delete info.env_profile;
  if (!info.run_mode) delete info.run_mode;

  if (!info.started_ts) delete info.started_ts;
  if (!info.uptime_s) delete info.uptime_s;

  if (!info.host) delete info.host;
  if (!info.pid) delete info.pid;

  // Python info can appear as nested object or flattened fields.
  const py = isRecord(obj.python) ? (obj.python as Record<string, unknown>) : null;
  const pyInfo =
    py || isRecord(obj.py) ? ((obj.py as Record<string, unknown>) ?? {}) : (null as Record<string, unknown> | null);

  const pythonObj = pyInfo && isRecord(pyInfo) ? pyInfo : py;

  if (pythonObj && isRecord(pythonObj)) {
    const python: NonNullable<SystemInfo["python"]> = {};
    const v = safeString(pythonObj.version, "");
    const exe = safeString(pythonObj.executable, "");
    const impl = safeString(pythonObj.implementation, "");
    const plat = safeString(pythonObj.platform, "");

    if (v) python.version = v;
    if (exe) python.executable = exe;
    if (impl) python.implementation = impl;
    if (plat) python.platform = plat;

    if (Object.keys(python).length > 0) info.python = python;
  }

  if (isRecord(obj.meta)) info.meta = obj.meta as Record<string, unknown>;

  return info;
}

function parseHealthCheck(raw: unknown): HealthCheck | null {
  if (!isRecord(raw)) return null;

  const ok = safeBoolean(raw.ok, false);

  const hc: HealthCheck = {
    ok,
  };

  const name = safeString(raw.name, "");
  if (name) hc.name = name;

  const detail = safeString(raw.detail, "");
  if (detail) hc.detail = detail;

  const latency = safeNumber(raw.latency_ms, NaN);
  if (Number.isFinite(latency) && latency >= 0) hc.latency_ms = latency;

  const ts = normalizeUnixSeconds(raw.ts);
  if (ts) hc.ts = ts;

  if (isRecord(raw.meta)) hc.meta = raw.meta as Record<string, unknown>;

  return hc;
}

function parseSystemHealth(raw: unknown): SystemHealth {
  if (!isRecord(raw)) {
    // Some servers return a bare string "ok"
    if (typeof raw === "string") {
      const s = raw.toLowerCase();
      return { ok: s === "ok" || s === "healthy", status: raw };
    }
    return { ok: false };
  }

  // Accept aliases:
  //  - { ok, status, checks: [] }
  //  - { health: { ... } }
  const obj = isRecord(raw.health) ? (raw.health as Record<string, unknown>) : raw;

  const ok = safeBoolean(obj.ok, false);
  const health: SystemHealth = {
    ok,
    status: safeString(obj.status, ""),
    ts: normalizeUnixSeconds(obj.ts),
  };

  if (!health.status) delete health.status;
  if (!health.ts) delete health.ts;

  const checksRaw = Array.isArray(obj.checks) ? (obj.checks as unknown[]) : [];
  const checks = checksRaw.map(parseHealthCheck).filter((c): c is HealthCheck => c !== null);
  if (checks.length > 0) health.checks = checks;

  if (isRecord(obj.meta)) health.meta = obj.meta as Record<string, unknown>;

  return health;
}

function parseFeatureFlag(raw: unknown): FeatureFlag | null {
  if (!isRecord(raw)) return null;

  // Accept: { key, enabled } or { name, enabled } or { id, enabled }
  const key = safeString(raw.key, "") || safeString(raw.name, "") || safeString(raw.id, "");
  if (!key) return null;

  const enabled = safeBoolean(raw.enabled, false);

  const f: FeatureFlag = { key, enabled };

  const desc = safeString(raw.description, "");
  if (desc) f.description = desc;

  const source = safeString(raw.source, "");
  if (source) f.source = source;

  const ts = normalizeUnixSeconds(raw.ts);
  if (ts) f.ts = ts;

  if (isRecord(raw.meta)) f.meta = raw.meta as Record<string, unknown>;

  return f;
}

function parseFeatureFlagsResponse(raw: unknown): FeatureFlagsResponse {
  if (!isRecord(raw)) return { items: [] };

  // Accept: { items: [...] } or { flags: [...] }
  const arr = Array.isArray(raw.items)
    ? (raw.items as unknown[])
    : Array.isArray(raw.flags)
      ? (raw.flags as unknown[])
      : [];

  const items = arr.map(parseFeatureFlag).filter((x): x is FeatureFlag => x !== null);
  return { items };
}

function parseEffectiveConfigSnapshot(raw: unknown): EffectiveConfigSnapshot {
  if (!isRecord(raw)) return { config: {} };

  // Accept: { config: {...} } or { effective: {...} } or { settings: {...} }
  const cfg =
    (isRecord(raw.config) ? (raw.config as Record<string, unknown>) : null) ??
    (isRecord(raw.effective) ? (raw.effective as Record<string, unknown>) : null) ??
    (isRecord(raw.settings) ? (raw.settings as Record<string, unknown>) : null) ??
    {};

  const snap: EffectiveConfigSnapshot = {
    config: cfg,
    ts: normalizeUnixSeconds(raw.ts),
    env_profile: safeString(raw.env_profile, ""),
    run_mode: safeString(raw.run_mode, ""),
  };

  if (!snap.ts) delete snap.ts;
  if (!snap.env_profile) delete snap.env_profile;
  if (!snap.run_mode) delete snap.run_mode;

  if (isRecord(raw.sources)) snap.sources = raw.sources as Record<string, string>;
  if (isRecord(raw.meta)) snap.meta = raw.meta as Record<string, unknown>;

  return snap;
}

export type SettingsEndpoints = {
  /**
   * Each endpoint returns a *priority-ordered* list of candidate paths.
   * The client probes in order and tolerates 404/405 to allow route evolution.
   */
  info: () => string[];
  health: () => string[];
  featureFlags: () => string[];
  effectiveConfig: () => string[];

  /**
   * Mutations (opt-in).
   * If your backend doesn’t support mutations, leave defaults and keep mutationsDisabled.
   */
  mutateConfig: () => string[];
  setFeatureFlag: (key: string) => string[];
};

export function defaultSettingsEndpoints(): SettingsEndpoints {
  return {
    // Common candidates across FastAPI-style systems.
    info: () => ["/system/info", "/system/status", "/system", "/status"],
    health: () => ["/system/health", "/health", "/system/ping", "/ping"],
    featureFlags: () => ["/system/flags", "/system/feature_flags", "/system/features", "/flags"],
    effectiveConfig: () => ["/system/config/effective", "/system/effective_config", "/system/config", "/config/effective"],

    mutateConfig: () => ["/system/config/mutate", "/system/config/patch", "/system/settings/mutate", "/system/settings"],
    setFeatureFlag: (key: string) => [
      `/system/flags/${encodeURIComponent(key)}`,
      `/system/feature_flags/${encodeURIComponent(key)}`,
      "/system/flags/set",
      "/system/feature_flags/set",
    ],
  };
}

export type SettingsClientOptions = {
  endpoints?: SettingsEndpoints;

  /**
   * Default timeout applied when per-call timeoutMs is not provided.
   */
  defaultTimeoutMs?: number;

  /**
   * Enable mutation methods. Defaults to false for safety.
   * Backend still must enforce approvals/policies.
   */
  mutationsEnabled?: boolean;

  /**
   * Optional bearer token supplier (caller-owned).
   */
  bearerTokenProvider?: () => string | null;

  /**
   * Extra headers (caller-owned).
   */
  headersExtra?: Record<string, string>;
};

export class SettingsClient {
  readonly baseUrl: string;
  readonly endpoints: SettingsEndpoints;
  readonly defaultTimeoutMs: number;
  readonly mutationsEnabled: boolean;

  private readonly bearerTokenProvider?: () => string | null;
  private readonly headersExtra?: Record<string, string>;

  constructor(baseUrl: string, opts?: SettingsClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("SettingsClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultSettingsEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
    this.mutationsEnabled = Boolean(opts?.mutationsEnabled ?? false);

    this.bearerTokenProvider = opts?.bearerTokenProvider;
    this.headersExtra = opts?.headersExtra;
  }

  private url(path: string): string {
    if (!path.startsWith("/")) path = `/${path}`;
    return `${this.baseUrl}${path}`;
  }

  private init(opts?: { signal?: AbortSignal; timeoutMs?: number }): TimeoutFetchInit {
    return {
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
      bearerToken: this.bearerTokenProvider?.() ?? null,
      headersExtra: this.headersExtra,
    };
  }

  private async fetchFirstOk(
    paths: string[],
    init: TimeoutFetchInit,
  ): Promise<{ url: string; json: unknown; res: Response }> {
    let lastErr: unknown = null;

    for (const p of paths) {
      const url = this.url(p);
      try {
        const { res, json } = await fetchJson(url, init);
        return { url, json, res };
      } catch (err) {
        lastErr = err;

        // If the route isn't found (or method not allowed), try next candidate.
        if (err instanceof SettingsApiError) {
          if (err.status === 404 || err.status === 405) continue;
        }

        // Otherwise fail fast: auth errors, 500s, network errors should surface.
        throw err;
      }
    }

    // No candidates worked.
    if (lastErr instanceof Error) throw lastErr;
    throw new Error("No settings endpoints responded successfully");
  }

  async getSystemInfo(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<SystemInfo> {
    const { json } = await this.fetchFirstOk(this.endpoints.info(), this.init(opts));
    return parseSystemInfo(json);
  }

  async getHealth(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<SystemHealth> {
    const { json } = await this.fetchFirstOk(this.endpoints.health(), this.init(opts));
    return parseSystemHealth(json);
  }

  async listFeatureFlags(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<FeatureFlagsResponse> {
    const { json } = await this.fetchFirstOk(this.endpoints.featureFlags(), this.init(opts));
    return parseFeatureFlagsResponse(json);
  }

  async getEffectiveConfig(opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<EffectiveConfigSnapshot> {
    const { json } = await this.fetchFirstOk(this.endpoints.effectiveConfig(), this.init(opts));
    return parseEffectiveConfigSnapshot(json);
  }

  async mutateConfig(
    req: ConfigMutationRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<ConfigMutationResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("SettingsClient.mutateConfig is disabled (mutationsEnabled=false).");
    }

    const { json } = await this.fetchFirstOk(this.endpoints.mutateConfig(), {
      ...this.init(opts),
      method: "POST",
      body: JSON.stringify(req),
    });

    if (!isRecord(json)) return { ok: true };
    return {
      ok: safeBoolean(json.ok, true),
      approval_id: safeString(json.approval_id, ""),
      status: safeString(json.status, ""),
      applied: safeBoolean(json.applied, false),
      resulting_value: (json as Record<string, unknown>).resulting_value,
      message: safeString(json.message, ""),
      meta: isRecord(json.meta) ? (json.meta as Record<string, unknown>) : undefined,
    };
  }

  async setFeatureFlag(
    key: string,
    enabled: boolean,
    opts?: { reason?: string; signal?: AbortSignal; timeoutMs?: number },
  ): Promise<ConfigMutationResponse> {
    if (!this.mutationsEnabled) {
      throw new Error("SettingsClient.setFeatureFlag is disabled (mutationsEnabled=false).");
    }

    const cleanedKey = (key || "").trim();
    if (!cleanedKey) throw new Error("setFeatureFlag requires a non-empty key");

    // Strategy:
    //  - Try REST-ish endpoints first: POST /system/flags/<key> with body { enabled, reason }
    //  - Fall back to generic setter endpoints: POST /system/flags/set with body { key, enabled, reason }
    const candidates = this.endpoints.setFeatureFlag(cleanedKey);

    const primaryPayload = { enabled, reason: (opts?.reason || "").trim() || undefined };
    const fallbackPayload = { key: cleanedKey, enabled, reason: (opts?.reason || "").trim() || undefined };

    let lastErr: unknown = null;

    for (const path of candidates) {
      const isGenericSetter = path.endsWith("/set");
      const body = JSON.stringify(isGenericSetter ? fallbackPayload : primaryPayload);

      try {
        const { json } = await this.fetchFirstOk([path], {
          ...this.init(opts),
          method: "POST",
          body,
        });

        if (!isRecord(json)) return { ok: true };

        return {
          ok: safeBoolean(json.ok, true),
          approval_id: safeString(json.approval_id, ""),
          status: safeString(json.status, ""),
          applied: safeBoolean(json.applied, false),
          resulting_value: (json as Record<string, unknown>).resulting_value,
          message: safeString(json.message, ""),
          meta: isRecord(json.meta) ? (json.meta as Record<string, unknown>) : undefined,
        };
      } catch (err) {
        lastErr = err;

        // Route mismatch? try next.
        if (err instanceof SettingsApiError && (err.status === 404 || err.status === 405)) continue;

        throw err;
      }
    }

    if (lastErr instanceof Error) throw lastErr;
    throw new Error("No feature flag endpoints responded successfully");
  }
}

/* -------------------------------------------------------------------------------------------------
 * UI Preferences (local)
 * ------------------------------------------------------------------------------------------------- */

export type UiTheme = "system" | "dark" | "light";
export type UiDensity = "comfortable" | "compact";

export type UiPreferencesV1 = {
  version: 1;

  theme: UiTheme;
  density: UiDensity;

  /**
   * If true, the UI can show more "operator-grade" toggles and diagnostics.
   * This is a UI-only preference (NOT a permission model).
   */
  show_advanced: boolean;

  /**
   * Refresh cadence hints (UI-only). Modules can read and decide what to do.
   */
  refresh: {
    approvals_ms: number; // 0 disables auto-refresh
    ledger_ms: number; // 0 disables auto-refresh
    health_ms: number; // 0 disables auto-refresh
  };

  /**
   * Last update for local auditing/debug.
   */
  updated_ts?: UnixSeconds;

  /**
   * Forward-compatible metadata.
   */
  meta?: Record<string, unknown>;
};

export type UiPreferences = UiPreferencesV1;

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  version: 1,
  theme: "system",
  density: "comfortable",
  show_advanced: false,
  refresh: {
    approvals_ms: 0,
    ledger_ms: 0,
    health_ms: 10_000,
  },
  updated_ts: Math.floor(Date.now() / 1000),
};

function hasStorage(): boolean {
  try {
    return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
  } catch {
    return false;
  }
}

function parseUiPreferences(raw: unknown): UiPreferences {
  if (!isRecord(raw)) return { ...DEFAULT_UI_PREFERENCES };

  // Versioned parsing (future-ready)
  const version = safeNumber(raw.version, 0);

  if (version !== 1) {
    // Unknown version: fall back safely.
    return { ...DEFAULT_UI_PREFERENCES };
  }

  const themeRaw = safeString(raw.theme, DEFAULT_UI_PREFERENCES.theme);
  const theme: UiTheme = themeRaw === "dark" || themeRaw === "light" || themeRaw === "system" ? themeRaw : "system";

  const densityRaw = safeString(raw.density, DEFAULT_UI_PREFERENCES.density);
  const density: UiDensity = densityRaw === "compact" || densityRaw === "comfortable" ? densityRaw : "comfortable";

  const showAdvanced = safeBoolean(raw.show_advanced, DEFAULT_UI_PREFERENCES.show_advanced);

  const refreshRaw = isRecord(raw.refresh) ? (raw.refresh as Record<string, unknown>) : {};
  const approvalsMs = Math.max(0, safeNumber(refreshRaw.approvals_ms, DEFAULT_UI_PREFERENCES.refresh.approvals_ms));
  const ledgerMs = Math.max(0, safeNumber(refreshRaw.ledger_ms, DEFAULT_UI_PREFERENCES.refresh.ledger_ms));
  const healthMs = Math.max(0, safeNumber(refreshRaw.health_ms, DEFAULT_UI_PREFERENCES.refresh.health_ms));

  const prefs: UiPreferences = {
    version: 1,
    theme,
    density,
    show_advanced: showAdvanced,
    refresh: {
      approvals_ms: approvalsMs,
      ledger_ms: ledgerMs,
      health_ms: healthMs,
    },
    updated_ts: normalizeUnixSeconds(raw.updated_ts) ?? Math.floor(Date.now() / 1000),
  };

  if (isRecord(raw.meta)) prefs.meta = raw.meta as Record<string, unknown>;

  return prefs;
}

/**
 * Local UI preference store:
 *  - versioned schema
 *  - safe parse + defaults
 *  - optional cross-tab subscription via `storage` event
 */
export class UiPreferencesStore {
  readonly storageKey: string;

  constructor(storageKey = "francis.ui.preferences") {
    this.storageKey = storageKey;
  }

  read(): UiPreferences {
    if (!hasStorage()) return { ...DEFAULT_UI_PREFERENCES };

    try {
      const raw = window.localStorage.getItem(this.storageKey);
      if (!raw) return { ...DEFAULT_UI_PREFERENCES };

      const parsed = JSON.parse(raw) as unknown;
      return parseUiPreferences(parsed);
    } catch {
      return { ...DEFAULT_UI_PREFERENCES };
    }
  }

  write(prefs: UiPreferences): void {
    if (!hasStorage()) return;

    const normalized: UiPreferences = {
      ...prefs,
      version: 1,
      updated_ts: Math.floor(Date.now() / 1000),
    };

    try {
      window.localStorage.setItem(this.storageKey, JSON.stringify(normalized));
    } catch {
      // ignore (quota, privacy mode, etc.)
    }
  }

  patch(patch: Partial<UiPreferences>): UiPreferences {
    const current = this.read();

    // Shallow merge + nested refresh merge
    const next: UiPreferences = {
      ...current,
      ...patch,
      version: 1,
      refresh: {
        ...current.refresh,
        ...(isRecord(patch.refresh) ? (patch.refresh as UiPreferences["refresh"]) : {}),
      },
      updated_ts: Math.floor(Date.now() / 1000),
    };

    // Normalize through parser to enforce constraints.
    const normalized = parseUiPreferences(next);
    this.write(normalized);
    return normalized;
  }

  /**
   * Cross-tab synchronization (optional).
   * Returns an unsubscribe function.
   */
  subscribe(cb: (prefs: UiPreferences) => void): () => void {
    if (typeof window === "undefined") return () => {};
    if (!hasStorage()) return () => {};

    const handler = (e: StorageEvent) => {
      if (e.key !== this.storageKey) return;
      cb(this.read());
    };

    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }
}

/**
 * Convenience: safe duration clamp for UI controls.
 */
export function clampMs(ms: number, minMs: number, maxMs: number): number {
  if (!Number.isFinite(ms)) return minMs;
  return Math.max(minMs, Math.min(maxMs, ms));
}

/**
 * Convenience: format seconds/ms-ish timestamps to local time.
 */
export function toLocaleTime(tsSeconds?: number): string {
  if (!tsSeconds || !Number.isFinite(tsSeconds)) return "";
  const ms = tsSeconds > 10_000_000_000 ? tsSeconds : tsSeconds * 1000;
  return new Date(ms).toLocaleString();
}

/**
 * Convenience: derive a reasonable default API base URL when not provided.
 * This is intentionally conservative and suitable for local dev.
 */
export function defaultApiBaseUrl(): string {
  return "http://127.0.0.1:8000";
}
