/**
 * Plugin Browser module (UI).
 *
 * A typed, defensive, framework-agnostic client for Francis plugin inventory and lifecycle actions.
 *
 * Design contract
 * ---------------
 *  1) Framework-agnostic:
 *     - No React imports, no UI state, no DOM dependencies.
 *
 *  2) Defensive parsing:
 *     - Treat JSON as untrusted.
 *     - Accept backend drift by supporting common alias fields and response shapes.
 *
 *  3) Observability-first:
 *     - Rich error type includes HTTP status, URL, request id, and body snippet.
 *     - Optional hooks for request/response tracing (no dependencies).
 *
 *  4) Forward-compatible endpoints:
 *     - Endpoints are builder functions (overrideable) so API routes can evolve.
 *
 *  5) Governance-friendly:
 *     - Mutations accept optional "reason" and may return approval_id.
 *
 * Expected backend (typical; override with endpoints):
 *  - GET    /plugins/list
 *  - GET    /plugins/get?id=...
 *  - POST   /plugins/enable
 *  - POST   /plugins/disable
 *  - POST   /plugins/install
 *  - POST   /plugins/uninstall
 *  - POST   /plugins/run
 *  - POST   /plugins/reload
 *
 * Notes
 * -----
 * - This client never handles secret material. If a plugin requires credentials,
 *   that should be handled by the credential manager + approvals system.
 * - "run" is intentionally generic: the plugin runtime contract may evolve.
 */

/* -------------------------------------------------------------------------------------------------
 * Types
 * ------------------------------------------------------------------------------------------------- */

export type PluginStatus =
  | "enabled"
  | "disabled"
  | "error"
  | "installing"
  | "uninstalling"
  | "updating"
  | "unknown"
  | string;

export type PluginSourceKind =
  | "registry"
  | "git"
  | "url"
  | "path"
  | "local_archive"
  | "builtin"
  | string;

export type PluginCapabilityKind =
  | "tool"
  | "command"
  | "event_handler"
  | "memory_provider"
  | "vector_backend"
  | "ui_extension"
  | "transport"
  | string;

/**
 * Minimal capability descriptor. Backends may emit richer shapes; we keep it tolerant.
 */
export type PluginCapability = {
  id?: string;
  kind: PluginCapabilityKind;
  name: string;

  description?: string;

  // Optional I/O schema hints (opaque to UI unless rendered)
  input_schema?: unknown;
  output_schema?: unknown;

  meta?: Record<string, unknown>;
};

export type PluginRef = {
  id: string;

  name: string;
  version?: string;

  status?: PluginStatus;
  enabled?: boolean;

  description?: string;

  author?: string;
  homepage?: string;
  license?: string;

  source_kind?: PluginSourceKind;
  source_ref?: string;

  installed_ts?: number; // unix seconds
  updated_ts?: number;

  tags?: string[];

  /**
   * Optional trust / verification hints (backend-defined):
   *  - signed: plugin package has signature
   *  - verified: signature validated by system trust root
   */
  signed?: boolean;
  verified?: boolean;

  capabilities?: PluginCapability[];

  meta?: Record<string, unknown>;
};

export type PluginDetail = PluginRef & {
  /**
   * Opaque manifest (backend-defined).
   * UI may render selectively (safe viewing only).
   */
  manifest?: Record<string, unknown>;

  /**
   * Optional config schema (JSON Schema-like or backend-defined).
   */
  config_schema?: unknown;

  /**
   * Optional README / docs.
   */
  readme?: string;

  /**
   * Optional file inventory (paths only, no file contents).
   */
  files?: string[];

  /**
   * Optional runtime info (backend-defined).
   */
  runtime?: Record<string, unknown>;
};

export type PluginListParams = {
  // Pagination
  limit?: number;
  offset?: number;
  cursor?: string;

  // Filtering
  status?: string;
  enabled?: boolean;
  source_kind?: string;
  tag?: string;
  tags?: string[];
  kind?: string; // capability kind, backend-dependent

  // Identity / scoping
  domain?: string;
  actor?: string;

  // Search
  search?: string;

  // Optional payload flags (backend-dependent)
  include_capabilities?: boolean;
  include_manifest?: boolean;
};

export type PluginListResponse = {
  items: PluginRef[];
  total?: number;
  next_cursor?: string;
};

export type PluginGetResponse = {
  item: PluginDetail | null;
};

export type PluginToggleRequest = {
  id: string;
  reason?: string;
  meta?: Record<string, unknown>;
};

export type PluginToggleResponse = {
  ok: boolean;
  id?: string;
  status?: PluginStatus;
  enabled?: boolean;

  approval_id?: string; // if action is approval-gated
  message?: string;
};

export type PluginInstallRequest = {
  /**
   * Where to install from.
   * This is intentionally generic and backend-defined.
   */
  source_kind: PluginSourceKind;

  /**
   * A backend-understood reference:
   *  - registry: "org/name" (+ optional version)
   *  - git: repo URL (+ optional ref)
   *  - url: https://.../plugin.zip
   *  - path: local path on server
   */
  source_ref: string;

  version?: string;
  ref?: string; // git ref / tag / commit
  sha256?: string; // integrity hint (optional)

  /**
   * Human justification (audit + approvals).
   */
  reason?: string;

  /**
   * If true, backend may validate/fetch but not activate/install.
   */
  dry_run?: boolean;

  /**
   * If true, backend may overwrite/update existing install (policy-dependent).
   */
  force?: boolean;

  meta?: Record<string, unknown>;
};

export type PluginInstallResponse = {
  ok: boolean;

  plugin_id?: string;
  status?: PluginStatus;
  message?: string;

  approval_id?: string; // if install is approval-gated
  operation_id?: string; // if install is queued async
};

export type PluginUninstallRequest = {
  id: string;
  reason?: string;
  force?: boolean;
  meta?: Record<string, unknown>;
};

export type PluginUninstallResponse = {
  ok: boolean;
  id?: string;
  status?: PluginStatus;
  message?: string;

  approval_id?: string;
  operation_id?: string;
};

export type PluginRunRequest = {
  id: string;

  /**
   * Action identifier (backend/plugin-defined):
   *  - could be a tool name, command name, or capability id
   */
  action: string;

  /**
   * Optional payload input (untrusted/opaque to transport layer).
   */
  input?: unknown;

  /**
   * Optional governance justification (if run requires approval).
   */
  reason?: string;

  /**
   * Optional idempotency hint.
   */
  idempotency_key?: string;
  approval_id?: string;

  meta?: Record<string, unknown>;
};

export type PluginGovernanceResult = {
  plane?: string;
  gate?: string;
  next_step?: string;
  operator_hint?: string;
  action?: string;
  risk_tier?: string;
  required_trust?: number;
  current_trust?: number;
  approval_status?: string;
};

export type PluginRunResponse = {
  ok: boolean;

  /**
   * If backend executes immediately:
   */
  output?: unknown;

  /**
   * If backend queues work:
   */
  operation_id?: string;

  /**
   * If backend gates via approvals:
   */
  approval_id?: string;

  /**
   * Optional status/error fields.
   */
  status?: string;
  error?: string;
  message?: string;
  tool_id?: string;
  governance?: PluginGovernanceResult;

  meta?: Record<string, unknown>;
};

export type PluginReloadResponse = {
  ok: boolean;
  message?: string;
};

export type PluginToolRef = {
  id: string;
  plugin_id: string;
  plugin_name?: string;
  name: string;
  action: string;
  kind?: PluginCapabilityKind;
  description?: string;
  enabled?: boolean;
  status?: PluginStatus;
  source_kind?: PluginSourceKind;
  risk_tier?: string;
  required_trust?: number;
  approvals_required?: boolean;
  input_schema?: unknown;
  output_schema?: unknown;
  tags?: string[];
  meta?: Record<string, unknown>;
};

export type PluginToolListParams = {
  limit?: number;
  offset?: number;
  plugin_id?: string;
  enabled?: boolean;
  kind?: string;
  tag?: string;
  tags?: string[];
  search?: string;
};

export type PluginToolListResponse = {
  items: PluginToolRef[];
  total?: number;
  offset?: number;
  limit?: number;
};

export type PluginToolGetResponse = {
  item: PluginToolRef | null;
};

export type PluginToolRunRequest = {
  id: string;
  input?: unknown;
  reason?: string;
  idempotency_key?: string;
  approval_id?: string;
  meta?: Record<string, unknown>;
};

export type PluginToolsExportFormat = "json" | "jsonl" | "csv";

/* -------------------------------------------------------------------------------------------------
 * Errors
 * ------------------------------------------------------------------------------------------------- */

export class PluginBrowserApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly requestId?: string;
  readonly bodySnippet?: string;
  readonly timedOut?: boolean;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; requestId?: string; bodySnippet?: string; timedOut?: boolean; cause?: unknown },
  ) {
    super(message);
    this.name = "PluginBrowserApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.requestId = opts?.requestId;
    this.bodySnippet = opts?.bodySnippet;
    this.timedOut = opts?.timedOut;
    // @ts-expect-error - Error.cause not always in TS lib target
    this.cause = opts?.cause;
  }
}

/* -------------------------------------------------------------------------------------------------
 * Utilities (tiny, dependency-free)
 * ------------------------------------------------------------------------------------------------- */

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

function safeStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.map((x) => (typeof x === "string" ? x : "")).filter((s) => s.length > 0);
  return out.length ? out : undefined;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function normalizeUnixSeconds(ts: unknown): number | undefined {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return undefined;
  return ts > 10_000_000_000 ? Math.floor(ts / 1000) : Math.floor(ts);
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

/**
 * Deterministic lightweight hash for synthesizing ids if backend omits them.
 * Not cryptographic; used only for stable UI keys.
 */
function fnv1a32(input: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h >>> 0;
}

function synthId(parts: Array<string | number | undefined>): string {
  const seed = parts.map((p) => (p === undefined ? "" : String(p))).join("|");
  return `pl_${fnv1a32(seed).toString(36)}`;
}

function headerRequestId(headers: Headers): string | undefined {
  const keys = ["x-request-id", "x-correlation-id", "x-trace-id", "request-id"];
  for (const k of keys) {
    const v = headers.get(k);
    if (v && v.trim()) return v.trim();
  }
  return undefined;
}

function encodeQuery(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();

  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;

    if (Array.isArray(v)) {
      for (const item of v) {
        if (item === undefined || item === null) continue;
        const s = String(item).trim();
        if (s) sp.append(k, s);
      }
      continue;
    }

    if (typeof v === "boolean") {
      sp.set(k, v ? "1" : "0");
      continue;
    }

    const s = String(v).trim();
    if (s) sp.set(k, s);
  }

  const qs = sp.toString();
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

function backoffMs(attempt: number, base = 250, cap = 5_000): number {
  const pow = 2 ** clamp(attempt, 0, 10);
  const raw = clamp(base * pow, base, cap);
  const jitter = Math.floor(Math.random() * clamp(raw * 0.2, 25, 500));
  return raw + jitter;
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;
  await new Promise<void>((resolve, reject) => {
    const t = window.setTimeout(() => {
      cleanup();
      resolve();
    }, ms);

    const onAbort = () => {
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };

    const cleanup = () => {
      window.clearTimeout(t);
      if (signal) signal.removeEventListener("abort", onAbort);
    };

    if (signal) {
      if (signal.aborted) {
        cleanup();
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

/* -------------------------------------------------------------------------------------------------
 * Parsing (defensive + alias tolerant)
 * ------------------------------------------------------------------------------------------------- */

function parseCapability(raw: unknown): PluginCapability | null {
  if (!isRecord(raw)) return null;

  const kind = safeString(raw.kind, safeString(raw.type, ""));
  const name = safeString(raw.name, safeString(raw.id, ""));
  if (!kind || !name) return null;

  const c: PluginCapability = {
    kind,
    name,
  };

  const id = safeString(raw.id, "");
  if (id) c.id = id;

  const desc = safeString(raw.description, "");
  if (desc) c.description = desc;

  if ("input_schema" in raw) c.input_schema = raw.input_schema;
  else if ("inputSchema" in raw) c.input_schema = (raw as Record<string, unknown>).inputSchema;

  if ("output_schema" in raw) c.output_schema = raw.output_schema;
  else if ("outputSchema" in raw) c.output_schema = (raw as Record<string, unknown>).outputSchema;

  if (isRecord(raw.meta)) c.meta = raw.meta;

  return c;
}

function statusFromBooleans(raw: Record<string, unknown>): { status?: PluginStatus; enabled?: boolean } {
  const enabled =
    typeof raw.enabled === "boolean"
      ? raw.enabled
      : typeof raw.is_enabled === "boolean"
        ? raw.is_enabled
        : typeof raw.isEnabled === "boolean"
          ? raw.isEnabled
          : undefined;

  if (enabled === undefined) return {};

  return {
    enabled,
    status: enabled ? "enabled" : "disabled",
  };
}

function parsePluginRef(raw: unknown): PluginRef | null {
  if (!isRecord(raw)) return null;

  const id =
    safeString(raw.id) ||
    safeString(raw.plugin_id) ||
    safeString(raw.pluginId) ||
    safeString(raw.slug) ||
    safeString(raw.name) ||
    "";

  const name = safeString(raw.name, safeString(raw.title, id));
  if (!id || !name) return null;

  const status = safeString(raw.status, safeString(raw.state, ""));
  const boolStatus = statusFromBooleans(raw);

  const installedTs =
    normalizeUnixSeconds(raw.installed_ts) ??
    normalizeUnixSeconds(raw.installedAt) ??
    normalizeUnixSeconds(raw.created_ts) ??
    undefined;

  const updatedTs =
    normalizeUnixSeconds(raw.updated_ts) ??
    normalizeUnixSeconds(raw.updatedAt) ??
    normalizeUnixSeconds(raw.modified_ts) ??
    undefined;

  const ref: PluginRef = {
    id: id || synthId([name, installedTs, status]),
    name,
  };

  const version = safeString(raw.version, "");
  if (version) ref.version = version;

  const effectiveStatus = status || boolStatus.status;
  if (effectiveStatus) ref.status = effectiveStatus;

  if (typeof boolStatus.enabled === "boolean") ref.enabled = boolStatus.enabled;
  else if (typeof raw.enabled === "boolean") ref.enabled = raw.enabled;

  const desc = safeString(raw.description, safeString(raw.summary, ""));
  if (desc) ref.description = desc;

  const author = safeString(raw.author, "");
  if (author) ref.author = author;

  const homepage = safeString(raw.homepage, safeString(raw.url, ""));
  if (homepage) ref.homepage = homepage;

  const license = safeString(raw.license, "");
  if (license) ref.license = license;

  const sourceKind = safeString(raw.source_kind, safeString(raw.sourceKind, safeString(raw.source, "")));
  if (sourceKind) ref.source_kind = sourceKind;

  const sourceRef = safeString(raw.source_ref, safeString(raw.sourceRef, safeString(raw.ref, "")));
  if (sourceRef) ref.source_ref = sourceRef;

  if (installedTs !== undefined) ref.installed_ts = installedTs;
  if (updatedTs !== undefined) ref.updated_ts = updatedTs;

  const tags = safeStringArray(raw.tags);
  if (tags) ref.tags = tags;

  const signed = typeof raw.signed === "boolean" ? raw.signed : undefined;
  if (signed !== undefined) ref.signed = signed;

  const verified = typeof raw.verified === "boolean" ? raw.verified : undefined;
  if (verified !== undefined) ref.verified = verified;

  const capsRaw =
    Array.isArray(raw.capabilities) ? raw.capabilities :
    Array.isArray(raw.tools) ? raw.tools :
    Array.isArray(raw.commands) ? raw.commands :
    undefined;

  if (capsRaw) {
    const caps = capsRaw.map(parseCapability).filter((x): x is PluginCapability => x !== null);
    if (caps.length) ref.capabilities = caps;
  }

  if (isRecord(raw.meta)) ref.meta = raw.meta;

  return ref;
}

function parsePluginDetail(raw: unknown): PluginDetail | null {
  const base = parsePluginRef(raw);
  if (!base) return null;

  const r = raw as Record<string, unknown>;
  const detail: PluginDetail = { ...base };

  // Optional manifest
  const manifest =
    isRecord(r.manifest) ? (r.manifest as Record<string, unknown>) :
    isRecord(r.plugin_manifest) ? (r.plugin_manifest as Record<string, unknown>) :
    isRecord(r.pluginManifest) ? (r.pluginManifest as Record<string, unknown>) :
    undefined;

  if (manifest) detail.manifest = manifest;

  // Optional config schema
  if ("config_schema" in r) detail.config_schema = r.config_schema;
  else if ("configSchema" in r) detail.config_schema = r.configSchema;

  // Optional readme
  const readme = safeString(r.readme, safeString(r.README, ""));
  if (readme) detail.readme = readme;

  // Optional files list
  const filesRaw = Array.isArray(r.files) ? r.files : Array.isArray(r.file_paths) ? r.file_paths : undefined;
  if (filesRaw) {
    const files = filesRaw.map((x) => (typeof x === "string" ? x : "")).filter((s) => s.length > 0);
    if (files.length) detail.files = files;
  }

  // Optional runtime info
  if (isRecord(r.runtime)) detail.runtime = r.runtime;

  return detail;
}

function parsePluginTool(raw: unknown): PluginToolRef | null {
  if (!isRecord(raw)) return null;

  const id = safeString(raw.id, "");
  const pluginId = safeString(raw.plugin_id, safeString(raw.pluginId, ""));
  const name = safeString(raw.name, safeString(raw.title, ""));
  const action = safeString(raw.action, safeString(raw.command, name));
  if (!id || !pluginId || !name || !action) return null;

  const out: PluginToolRef = {
    id,
    plugin_id: pluginId,
    name,
    action,
  };

  const pluginName = safeString(raw.plugin_name, safeString(raw.pluginName, ""));
  if (pluginName) out.plugin_name = pluginName;

  const kind = safeString(raw.kind, safeString(raw.type, ""));
  if (kind) out.kind = kind;

  const description = safeString(raw.description, "");
  if (description) out.description = description;

  if (typeof raw.enabled === "boolean") out.enabled = raw.enabled;

  const status = safeString(raw.status, "");
  if (status) out.status = status;

  const sourceKind = safeString(raw.source_kind, safeString(raw.sourceKind, ""));
  if (sourceKind) out.source_kind = sourceKind;

  const riskTier = safeString(raw.risk_tier, safeString(raw.riskTier, ""));
  if (riskTier) out.risk_tier = riskTier;
  if (typeof raw.required_trust === "number" && Number.isFinite(raw.required_trust)) {
    out.required_trust = raw.required_trust;
  }
  if (typeof raw.approvals_required === "boolean") out.approvals_required = raw.approvals_required;

  if ("input_schema" in raw) out.input_schema = raw.input_schema;
  else if ("inputSchema" in raw) out.input_schema = (raw as Record<string, unknown>).inputSchema;

  if ("output_schema" in raw) out.output_schema = raw.output_schema;
  else if ("outputSchema" in raw) out.output_schema = (raw as Record<string, unknown>).outputSchema;

  const tags = safeStringArray(raw.tags);
  if (tags) out.tags = tags;

  if (isRecord(raw.meta)) out.meta = raw.meta;

  return out;
}

/* -------------------------------------------------------------------------------------------------
 * Endpoints (overrideable)
 * ------------------------------------------------------------------------------------------------- */

export type PluginBrowserEndpoints = {
  list: (q?: PluginListParams) => string;
  get: (id: string) => string;
  toolsList: (q?: PluginToolListParams) => string;
  toolsGet: (id: string) => string;
  toolsExport: (format: PluginToolsExportFormat, q?: PluginToolListParams) => string;
  toolsRun: () => string;

  enable: () => string;
  disable: () => string;

  install: () => string;
  uninstall: () => string;

  run: () => string;

  reload?: () => string;
};

export function defaultPluginBrowserEndpoints(): PluginBrowserEndpoints {
  return {
    list: (q) =>
      `/plugins/list${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        cursor: q?.cursor,
        status: q?.status,
        enabled: q?.enabled,
        source_kind: q?.source_kind,
        tag: q?.tag,
        tags: q?.tags,
        kind: q?.kind,
        domain: q?.domain,
        actor: q?.actor,
        search: q?.search,
        include_capabilities: q?.include_capabilities ? true : undefined,
        include_manifest: q?.include_manifest ? true : undefined,
      })}`,

    get: (id: string) => `/plugins/get${encodeQuery({ id })}`,
    toolsList: (q) =>
      `/plugins/tools/list${encodeQuery({
        limit: q?.limit,
        offset: q?.offset,
        plugin_id: q?.plugin_id,
        enabled: q?.enabled,
        kind: q?.kind,
        tag: q?.tag,
        tags: q?.tags,
        search: q?.search,
      })}`,
    toolsGet: (id: string) => `/plugins/tools/get${encodeQuery({ id })}`,
    toolsExport: (format: PluginToolsExportFormat, q) =>
      `/plugins/tools/export${encodeQuery({
        format,
        plugin_id: q?.plugin_id,
        enabled: q?.enabled,
        kind: q?.kind,
        tag: q?.tag,
        tags: q?.tags,
        search: q?.search,
      })}`,
    toolsRun: () => "/plugins/tools/run",

    enable: () => "/plugins/enable",
    disable: () => "/plugins/disable",

    install: () => "/plugins/install",
    uninstall: () => "/plugins/uninstall",

    run: () => "/plugins/run",

    reload: () => "/plugins/reload",
  };
}

/* -------------------------------------------------------------------------------------------------
 * Client
 * ------------------------------------------------------------------------------------------------- */

export type PluginBrowserClientHooks = {
  onRequest?: (info: { url: string; method: string; attempt: number; timeoutMs: number }) => void;
  onResponse?: (info: { url: string; method: string; status: number; elapsedMs: number; requestId?: string; attempt: number }) => void;
};

export type RetryPolicy = {
  retries?: number; // default 0
  retryMethods?: string[]; // default ["GET", "HEAD"]
  retryStatusCodes?: number[]; // default [429, 502, 503, 504]
};

export type PluginBrowserClientOptions = {
  endpoints?: PluginBrowserEndpoints;
  defaultTimeoutMs?: number;
  hooks?: PluginBrowserClientHooks;
  retry?: RetryPolicy;
};

type TimeoutMergedFetchInit = RequestInit & { timeoutMs?: number };

export class PluginBrowserClient {
  readonly baseUrl: string;
  readonly endpoints: PluginBrowserEndpoints;
  readonly defaultTimeoutMs: number;
  readonly hooks?: PluginBrowserClientHooks;
  readonly retry: Required<RetryPolicy>;

  constructor(baseUrl: string, opts?: PluginBrowserClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("PluginBrowserClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultPluginBrowserEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;

    const r = opts?.retry ?? {};
    this.retry = {
      retries: typeof r.retries === "number" ? r.retries : 0,
      retryMethods: Array.isArray(r.retryMethods) && r.retryMethods.length ? r.retryMethods : ["GET", "HEAD"],
      retryStatusCodes: Array.isArray(r.retryStatusCodes) && r.retryStatusCodes.length ? r.retryStatusCodes : [429, 502, 503, 504],
    };

    this.hooks = opts?.hooks;
  }

  private url(path: string): string {
    const p = path.startsWith("/") ? path : `/${path}`;
    return `${this.baseUrl}${p}`;
  }

  private async fetchWithTimeout(url: string, init?: TimeoutMergedFetchInit): Promise<{ res: Response; elapsedMs: number }> {
    const timeoutMs = init?.timeoutMs ?? this.defaultTimeoutMs;
    const { signal: externalSignal, ...fetchInit } = init ?? {};

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
      if (externalSignal.aborted) onExternalAbort();
      else externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }

    const start = performance.now();

    try {
      const headers = new Headers(fetchInit.headers ?? undefined);
      if (!headers.has("Accept")) headers.set("Accept", "application/json");

      const method = safeString(fetchInit.method, "GET").toUpperCase();
      const hasBody = "body" in fetchInit && fetchInit.body !== undefined && fetchInit.body !== null;
      if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

      const res = await fetch(url, { ...fetchInit, headers, signal: controller.signal });
      const elapsedMs = Math.max(0, Math.round(performance.now() - start));
      return { res, elapsedMs };
    } catch (err) {
      if (timedOut) {
        throw new PluginBrowserApiError(`Request timed out after ${timeoutMs}ms`, { url, timedOut: true, cause: err });
      }
      throw err;
    } finally {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      if (externalSignal && !externalSignal.aborted) externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }

  private async fetchJson(url: string, init?: TimeoutMergedFetchInit): Promise<unknown> {
    const method = safeString(init?.method, "GET").toUpperCase();
    const retries = this.retry.retries;
    const canRetry = this.retry.retryMethods.map((m) => m.toUpperCase()).includes(method);

    let lastErr: unknown;

    for (let attempt = 0; attempt <= retries; attempt++) {
      this.hooks?.onRequest?.({ url, method, attempt, timeoutMs: init?.timeoutMs ?? this.defaultTimeoutMs });

      try {
        const { res, elapsedMs } = await this.fetchWithTimeout(url, init);
        const reqId = headerRequestId(res.headers);

        this.hooks?.onResponse?.({ url, method, status: res.status, elapsedMs, requestId: reqId, attempt });

        if (!res.ok) {
          const snippet = await readTextSnippet(res);
          const apiErr = new PluginBrowserApiError(`HTTP ${res.status} for plugin browser request`, {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
          });

          const shouldRetry = this.retry.retryStatusCodes.includes(res.status);
          if (attempt < retries && canRetry && shouldRetry) {
            lastErr = apiErr;
            await sleep(backoffMs(attempt), init?.signal);
            continue;
          }

          throw apiErr;
        }

        try {
          return await res.json();
        } catch (err) {
          const snippet = await readTextSnippet(res);
          throw new PluginBrowserApiError("Failed to parse JSON response", {
            status: res.status,
            url,
            requestId: reqId,
            bodySnippet: snippet,
            cause: err,
          });
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") throw err;
        if (err instanceof PluginBrowserApiError && err.timedOut) throw err;

        lastErr = err;

        if (attempt < retries && canRetry) {
          await sleep(backoffMs(attempt), init?.signal);
          continue;
        }

        throw err;
      }
    }

    throw lastErr instanceof Error ? lastErr : new Error("Plugin browser request failed");
  }

  private async fetchBlob(url: string, init?: TimeoutMergedFetchInit): Promise<Blob> {
    const method = safeString(init?.method, "GET").toUpperCase();
    this.hooks?.onRequest?.({ url, method, attempt: 0, timeoutMs: init?.timeoutMs ?? this.defaultTimeoutMs });

    const { res, elapsedMs } = await this.fetchWithTimeout(url, init);
    const reqId = headerRequestId(res.headers);
    this.hooks?.onResponse?.({ url, method, status: res.status, elapsedMs, requestId: reqId, attempt: 0 });

    if (!res.ok) {
      const snippet = await readTextSnippet(res);
      throw new PluginBrowserApiError(`HTTP ${res.status} for plugin browser request`, {
        status: res.status,
        url,
        requestId: reqId,
        bodySnippet: snippet,
      });
    }
    return await res.blob();
  }

  private parseRunResponse(json: unknown): PluginRunResponse {
    if (!isRecord(json)) {
      return {
        ok: true,
        output: json,
        status: "ok",
      };
    }
    const record = json as Record<string, unknown>;
    const governanceRaw = isRecord(record.governance) ? (record.governance as Record<string, unknown>) : null;
    const governance =
      governanceRaw
        ? {
            plane: safeString(governanceRaw.plane, "") || undefined,
            gate: safeString(governanceRaw.gate, "") || undefined,
            next_step: safeString(governanceRaw.next_step, "") || undefined,
            operator_hint: safeString(governanceRaw.operator_hint, "") || undefined,
            action: safeString(governanceRaw.action, "") || undefined,
            risk_tier: safeString(governanceRaw.risk_tier, "") || undefined,
            required_trust: safeNumber(governanceRaw.required_trust, NaN),
            current_trust: safeNumber(governanceRaw.current_trust, NaN),
            approval_status: safeString(governanceRaw.approval_status, "") || undefined,
          }
        : undefined;

    return {
      ok: Boolean(record.ok ?? true),
      output: record.output,
      operation_id: safeString(record.operation_id, "") || undefined,
      approval_id: safeString(record.approval_id, "") || undefined,
      tool_id: safeString(record.tool_id, "") || undefined,
      status: safeString(record.status, "") || undefined,
      error: safeString(record.error, "") || undefined,
      message: safeString(record.message, "") || undefined,
      governance: governance
        ? {
            ...governance,
            required_trust:
              typeof governance.required_trust === "number" && Number.isFinite(governance.required_trust)
                ? governance.required_trust
                : undefined,
            current_trust:
              typeof governance.current_trust === "number" && Number.isFinite(governance.current_trust)
                ? governance.current_trust
                : undefined,
          }
        : undefined,
      meta: isRecord(record.meta) ? (record.meta as Record<string, unknown>) : undefined,
    };
  }

  /**
   * List plugins with filters/pagination.
   */
  async list(
    params?: PluginListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginListResponse> {
    const url = this.url(this.endpoints.list(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).plugins)
          ? ((json as Record<string, unknown>).plugins as unknown[])
          : Array.isArray((json as Record<string, unknown>).entries)
            ? ((json as Record<string, unknown>).entries as unknown[])
            : [];

    const items = raw.map(parsePluginRef).filter((x): x is PluginRef => x !== null);

    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const nextCursor = safeString(
      (json as Record<string, unknown>).next_cursor,
      safeString((json as Record<string, unknown>).cursor, ""),
    );

    return {
      items,
      total: total > 0 ? total : undefined,
      next_cursor: nextCursor || undefined,
    };
  }

  /**
   * Get a single plugin detail by id.
   */
  async get(
    id: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginGetResponse> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("PluginBrowserClient.get requires a non-empty id");

    const url = this.url(this.endpoints.get(clean));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    // Accept { item }, { plugin }, or direct object
    const raw =
      isRecord(json) && (json as Record<string, unknown>).item !== undefined
        ? (json as Record<string, unknown>).item
        : isRecord(json) && (json as Record<string, unknown>).plugin !== undefined
          ? (json as Record<string, unknown>).plugin
          : json;

    return { item: parsePluginDetail(raw) };
  }

  /**
   * List plugin tools/actions with filtering/pagination.
   */
  async listTools(
    params?: PluginToolListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginToolListResponse> {
    const url = this.url(this.endpoints.toolsList(params));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
    if (!isRecord(json)) return { items: [] };

    const raw =
      Array.isArray((json as Record<string, unknown>).items)
        ? ((json as Record<string, unknown>).items as unknown[])
        : Array.isArray((json as Record<string, unknown>).tools)
          ? ((json as Record<string, unknown>).tools as unknown[])
          : [];

    const items = raw.map(parsePluginTool).filter((x): x is PluginToolRef => x !== null);
    const total = safeNumber((json as Record<string, unknown>).total, 0);
    const offset = safeNumber((json as Record<string, unknown>).offset, 0);
    const limit = safeNumber((json as Record<string, unknown>).limit, 0);

    return {
      items,
      total: total > 0 ? total : undefined,
      offset: offset >= 0 ? offset : undefined,
      limit: limit > 0 ? limit : undefined,
    };
  }

  /**
   * Get a single plugin tool/action detail by id.
   */
  async getTool(
    id: string,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginToolGetResponse> {
    const clean = (id || "").trim();
    if (!clean) throw new Error("PluginBrowserClient.getTool requires a non-empty id");

    const url = this.url(this.endpoints.toolsGet(clean));
    const json = await this.fetchJson(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    const raw =
      isRecord(json) && (json as Record<string, unknown>).item !== undefined
        ? (json as Record<string, unknown>).item
        : isRecord(json) && (json as Record<string, unknown>).tool !== undefined
          ? (json as Record<string, unknown>).tool
          : json;

    return { item: parsePluginTool(raw) };
  }

  /**
   * Export plugin tools catalog as a blob.
   */
  async exportTools(
    format: PluginToolsExportFormat,
    params?: PluginToolListParams,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<Blob> {
    const url = this.url(this.endpoints.toolsExport(format, params));
    return await this.fetchBlob(url, { method: "GET", signal: opts?.signal, timeoutMs: opts?.timeoutMs });
  }

  /**
   * Run a plugin tool/action by tool id.
   */
  async runTool(
    req: PluginToolRunRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginRunResponse> {
    const id = (req?.id || "").trim();
    if (!id) throw new Error("PluginBrowserClient.runTool requires req.id");

    const url = this.url(this.endpoints.toolsRun());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ ...req, id }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    return this.parseRunResponse(json);
  }

  /**
   * Batch get (dedupe + bounded concurrency; preserves input order; drops nulls).
   */
  async getMany(
    ids: string[],
    opts?: { signal?: AbortSignal; timeoutMs?: number; concurrency?: number; tolerateFailures?: boolean },
  ): Promise<PluginDetail[]> {
    const original = (ids ?? []).map((s) => (s || "").trim()).filter((s) => s.length > 0);
    if (!original.length) return [];

    const unique: string[] = [];
    const seen = new Set<string>();
    for (const id of original) {
      if (!seen.has(id)) {
        seen.add(id);
        unique.push(id);
      }
    }

    const concurrency = clamp(Math.floor(opts?.concurrency ?? 6), 1, 16);
    const tolerateFailures = opts?.tolerateFailures ?? true;

    const map = new Map<string, PluginDetail | null>();
    for (const id of unique) map.set(id, null);

    let cursor = 0;
    const worker = async (): Promise<void> => {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const i = cursor++;
        if (i >= unique.length) return;
        const id = unique[i];

        try {
          const r = await this.get(id, { signal: opts?.signal, timeoutMs: opts?.timeoutMs });
          map.set(id, r.item);
        } catch (err) {
          if (!tolerateFailures) throw err;
          map.set(id, null);
        }
      }
    };

    await Promise.all(Array.from({ length: Math.min(concurrency, unique.length) }, () => worker()));

    const out: PluginDetail[] = [];
    for (const id of original) {
      const v = map.get(id) ?? null;
      if (v) out.push(v);
    }
    return out;
  }

  /**
   * Enable a plugin (may be policy/approval gated).
   */
  async enable(
    req: PluginToggleRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginToggleResponse> {
    const id = (req?.id || "").trim();
    if (!id) throw new Error("PluginBrowserClient.enable requires req.id");

    const url = this.url(this.endpoints.enable());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ ...req, id }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    if (!isRecord(json)) return { ok: true, id, enabled: true, status: "enabled" };

    const enabled = safeBool((json as Record<string, unknown>).enabled, true);
    const status = safeString((json as Record<string, unknown>).status, enabled ? "enabled" : "disabled");

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, id),
      enabled,
      status,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
    };
  }

  /**
   * Disable a plugin (may be policy/approval gated).
   */
  async disable(
    req: PluginToggleRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginToggleResponse> {
    const id = (req?.id || "").trim();
    if (!id) throw new Error("PluginBrowserClient.disable requires req.id");

    const url = this.url(this.endpoints.disable());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ ...req, id }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    if (!isRecord(json)) return { ok: true, id, enabled: false, status: "disabled" };

    const enabled = safeBool((json as Record<string, unknown>).enabled, false);
    const status = safeString((json as Record<string, unknown>).status, enabled ? "enabled" : "disabled");

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, id),
      enabled,
      status,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
    };
  }

  /**
   * Install a plugin (approval-gated / queued installs supported).
   */
  async install(
    req: PluginInstallRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginInstallResponse> {
    const kind = (req?.source_kind || "").trim();
    const ref = (req?.source_ref || "").trim();
    if (!kind || !ref) throw new Error("PluginBrowserClient.install requires source_kind and source_ref");

    const url = this.url(this.endpoints.install());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ ...req, source_kind: kind, source_ref: ref }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    if (!isRecord(json)) return { ok: true };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      plugin_id:
        safeString((json as Record<string, unknown>).plugin_id, "") ||
        safeString((json as Record<string, unknown>).id, "") ||
        undefined,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      operation_id: safeString((json as Record<string, unknown>).operation_id, "") || undefined,
    };
  }

  /**
   * Uninstall a plugin.
   */
  async uninstall(
    req: PluginUninstallRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginUninstallResponse> {
    const id = (req?.id || "").trim();
    if (!id) throw new Error("PluginBrowserClient.uninstall requires req.id");

    const url = this.url(this.endpoints.uninstall());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ ...req, id }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });

    if (!isRecord(json)) return { ok: true, id, status: "uninstalling" };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      id: safeString((json as Record<string, unknown>).id, id) || id,
      status: safeString((json as Record<string, unknown>).status, "") || undefined,
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
      approval_id: safeString((json as Record<string, unknown>).approval_id, "") || undefined,
      operation_id: safeString((json as Record<string, unknown>).operation_id, "") || undefined,
    };
  }

  /**
   * Run a plugin action (generic).
   *
   * This is intentionally loose:
   * - Some backends may run synchronously and return output immediately.
   * - Others may enqueue work and return an operation_id.
   * - Some may require approvals and return approval_id.
   */
  async run(
    req: PluginRunRequest,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginRunResponse> {
    const id = (req?.id || "").trim();
    const action = (req?.action || "").trim();
    if (!id || !action) throw new Error("PluginBrowserClient.run requires req.id and req.action");

    const url = this.url(this.endpoints.run());
    const json = await this.fetchJson(url, {
      method: "POST",
      body: JSON.stringify({ ...req, id, action }),
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    return this.parseRunResponse(json);
  }

  /**
   * Reload plugin registry / re-scan (optional endpoint).
   */
  async reload(
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<PluginReloadResponse> {
    const ep = this.endpoints.reload;
    if (!ep) {
      throw new Error("PluginBrowserClient.reload is not configured (endpoints.reload missing)");
    }

    const url = this.url(ep());
    const json = await this.fetchJson(url, { method: "POST", signal: opts?.signal, timeoutMs: opts?.timeoutMs });

    if (!isRecord(json)) return { ok: true };

    return {
      ok: Boolean((json as Record<string, unknown>).ok ?? true),
      message: safeString((json as Record<string, unknown>).message, "") || undefined,
    };
  }
}
