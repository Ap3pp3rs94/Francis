/**
 * Artifacts module (UI).
 *
 * Framework-agnostic client for backend artifact inspection.
 *
 * Contract:
 * - transports metadata-only artifact projections from `/artifacts/inspect`
 * - preserves failure state without fabricating availability
 * - never carries artifact file contents into UI state
 */

export type ArtifactEntryKind = "directory" | "file" | "external_link" | "unavailable" | string;

export type ArtifactEntry = {
  name: string;
  relative_path?: string;
  kind: ArtifactEntryKind;
  bytes?: number;
  modified_ts?: number | null;
};

export type ArtifactInspectResponse = {
  ok: boolean;
  error?: string;
  recovery_hint?: string;
  next_step?: string;
  retryable?: boolean;
  artifact_root?: string;
  artifact_dir?: string;
  relative_path?: string;
  exists?: boolean;
  kind?: ArtifactEntryKind;
  bytes?: number;
  modified_ts?: number | null;
  entries: ArtifactEntry[];
  entry_count?: number;
  truncated?: boolean;
};

export type ArtifactInspectQuery = {
  artifact_dir: string;
  limit?: number;
};

export type ArtifactsEndpoints = {
  inspect: (query: ArtifactInspectQuery) => string;
};

export type ArtifactsClientOptions = {
  endpoints?: ArtifactsEndpoints;
  defaultTimeoutMs?: number;
  defaultLimit?: number;
};

export class ArtifactsApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;
  readonly timedOut?: boolean;

  constructor(
    message: string,
    opts?: { status?: number; url?: string; bodySnippet?: string; timedOut?: boolean; cause?: unknown },
  ) {
    super(message);
    this.name = "ArtifactsApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.bodySnippet = opts?.bodySnippet;
    this.timedOut = opts?.timedOut;
    // @ts-expect-error - Error.cause may not exist depending on TS lib target
    this.cause = opts?.cause;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function safeBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function safeNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function safeNullableNumber(value: unknown): number | null | undefined {
  if (value === null) return null;
  return safeNumber(value);
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function buildQuery(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    const text = typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value).trim() : "";
    if (text) searchParams.set(key, text);
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function readHeaderRequestId(headers: Headers): string | undefined {
  for (const key of ["x-request-id", "x-correlation-id", "x-trace-id", "request-id"]) {
    const value = headers.get(key);
    if (value?.trim()) return value.trim();
  }
  return undefined;
}

async function readTextSnippet(response: Response, maxChars = 2048): Promise<string> {
  try {
    const text = await response.text();
    return text.length > maxChars ? `${text.slice(0, maxChars)}...` : text;
  } catch {
    return "";
  }
}

type TimeoutFetchInit = RequestInit & { timeoutMs?: number };

async function fetchWithTimeout(url: string, init?: TimeoutFetchInit): Promise<Response> {
  const { timeoutMs = 20_000, signal: externalSignal, ...fetchInit } = init ?? {};
  const controller = new AbortController();
  let timedOut = false;

  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null;
  if (timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => {
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

    return await fetch(url, {
      ...fetchInit,
      headers,
      signal: controller.signal,
    });
  } catch (error) {
    if (timedOut) {
      throw new ArtifactsApiError(`Timeout after ${timeoutMs}ms`, { url, timedOut: true, cause: error });
    }
    throw error;
  } finally {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
    if (externalSignal && !externalSignal.aborted) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

async function fetchJson(url: string, init?: TimeoutFetchInit): Promise<unknown> {
  const response = await fetchWithTimeout(url, init);
  const requestId = readHeaderRequestId(response.headers);

  if (!response.ok) {
    const snippet = await readTextSnippet(response);
    throw new ArtifactsApiError(`HTTP ${response.status} for artifact inspection request`, {
      status: response.status,
      url,
      bodySnippet: snippet,
    });
  }

  const body = await readTextSnippet(response, 1_000_000);
  try {
    return JSON.parse(body) as unknown;
  } catch (error) {
    throw new ArtifactsApiError("Failed to parse artifact inspection JSON response", {
      status: response.status,
      url,
      bodySnippet: body.slice(0, 2048),
      cause: { error, requestId },
    });
  }
}

function parseEntry(raw: unknown): ArtifactEntry | null {
  if (!isRecord(raw)) return null;

  const name = safeString(raw.name).trim();
  const kind = safeString(raw.kind).trim();
  if (!name || !kind) return null;

  const entry: ArtifactEntry = { name, kind };

  const relativePath = safeString(raw.relative_path).trim();
  if (relativePath) entry.relative_path = relativePath;

  const bytes = safeNumber(raw.bytes);
  if (bytes !== undefined) entry.bytes = bytes;

  const modifiedTs = safeNullableNumber(raw.modified_ts);
  if (modifiedTs !== undefined) entry.modified_ts = modifiedTs;

  return entry;
}

export function parseArtifactInspectResponse(raw: unknown): ArtifactInspectResponse {
  if (!isRecord(raw)) {
    return { ok: false, error: "artifact_response_invalid", entries: [] };
  }

  const response: ArtifactInspectResponse = {
    ok: raw.ok === true,
    entries: Array.isArray(raw.entries)
      ? raw.entries.map(parseEntry).filter((entry): entry is ArtifactEntry => entry !== null)
      : [],
  };

  const error = safeString(raw.error).trim();
  if (error) response.error = error;

  const recoveryHint = safeString(raw.recovery_hint).trim();
  if (recoveryHint) response.recovery_hint = recoveryHint;

  const nextStep = safeString(raw.next_step).trim();
  if (nextStep) response.next_step = nextStep;

  const retryable = safeBoolean(raw.retryable);
  if (retryable !== undefined) response.retryable = retryable;

  const artifactRoot = safeString(raw.artifact_root).trim();
  if (artifactRoot) response.artifact_root = artifactRoot;

  const artifactDir = safeString(raw.artifact_dir).trim();
  if (artifactDir) response.artifact_dir = artifactDir;

  const relativePath = safeString(raw.relative_path).trim();
  if (relativePath) response.relative_path = relativePath;

  const exists = safeBoolean(raw.exists);
  if (exists !== undefined) response.exists = exists;

  const kind = safeString(raw.kind).trim();
  if (kind) response.kind = kind;

  const bytes = safeNumber(raw.bytes);
  if (bytes !== undefined) response.bytes = bytes;

  const modifiedTs = safeNullableNumber(raw.modified_ts);
  if (modifiedTs !== undefined) response.modified_ts = modifiedTs;

  const entryCount = safeNumber(raw.entry_count);
  if (entryCount !== undefined) response.entry_count = entryCount;

  const truncated = safeBoolean(raw.truncated);
  if (truncated !== undefined) response.truncated = truncated;

  return response;
}

export function defaultArtifactsEndpoints(): ArtifactsEndpoints {
  return {
    inspect: (query) =>
      `/artifacts/inspect${buildQuery({
        artifact_dir: query.artifact_dir,
        limit: query.limit,
      })}`,
  };
}

export class ArtifactsClient {
  readonly baseUrl: string;
  readonly endpoints: ArtifactsEndpoints;
  readonly defaultTimeoutMs: number;
  readonly defaultLimit: number;

  constructor(baseUrl: string, opts?: ArtifactsClientOptions) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    if (!this.baseUrl) throw new Error("ArtifactsClient requires a non-empty baseUrl");

    this.endpoints = opts?.endpoints ?? defaultArtifactsEndpoints();
    this.defaultTimeoutMs = typeof opts?.defaultTimeoutMs === "number" ? opts.defaultTimeoutMs : 20_000;
    this.defaultLimit = clamp(Math.floor(typeof opts?.defaultLimit === "number" ? opts.defaultLimit : 50), 1, 200);
  }

  private url(path: string): string {
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    return `${this.baseUrl}${cleanPath}`;
  }

  async inspect(
    artifactDir: string,
    opts?: { limit?: number; signal?: AbortSignal; timeoutMs?: number },
  ): Promise<ArtifactInspectResponse> {
    const cleanedArtifactDir = (artifactDir || "").trim();
    if (!cleanedArtifactDir) throw new Error("ArtifactsClient.inspect requires a non-empty artifactDir");

    const limit = clamp(Math.floor(typeof opts?.limit === "number" ? opts.limit : this.defaultLimit), 1, 200);
    const url = this.url(this.endpoints.inspect({ artifact_dir: cleanedArtifactDir, limit }));
    const json = await fetchJson(url, {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs ?? this.defaultTimeoutMs,
    });

    return parseArtifactInspectResponse(json);
  }
}
