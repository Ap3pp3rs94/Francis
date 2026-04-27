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

export type ArtifactOriginatingReceipt = {
  source?: string;
  matched_artifact_field?: string;
  mission_id?: string;
  operation_id?: string;
  approval_id?: string;
  trace_id?: string;
  run_id?: string;
  artifact_dir?: string;
  operation_status?: string;
  operation_error?: string;
  result_message?: string;
  recovery_next_step?: string;
  plan_status?: string;
  plan_current_step_id?: string;
  plan_current_step_title?: string;
  plan_step_count?: number;
  plan_checkpoint_count?: number;
  active_stage?: string;
  handoff_stage?: string;
  handoff_action?: string;
  handoff_gate?: string;
  handoff_mission_id?: string;
  handoff_approval_id?: string;
  handoff_approval_status?: string;
  handoff_operation_id?: string;
  handoff_trace_id?: string;
  handoff_run_id?: string;
  handoff_artifact_dir?: string;
  current_task_source?: string;
  current_task_gate?: string;
  current_task_mission_id?: string;
  current_task_approval_id?: string;
  current_task_approval_status?: string;
  current_task_previous_approval_id?: string;
  current_task_previous_approval_status?: string;
  current_task_operation_id?: string;
  current_task_operation_name?: string;
  current_task_operation_plane?: string;
  current_task_advance_action?: string;
  current_task_trace_id?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  current_task_next_step?: string;
  references?: {
    mission_id?: string;
    operation_id?: string;
    approval_id?: string;
    trace_id?: string;
    run_id?: string;
    artifact_dir?: string;
  };
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
  originating_receipt?: ArtifactOriginatingReceipt;
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

function firstString(...values: Array<string | undefined>): string {
  for (const value of values) {
    const text = safeString(value).trim();
    if (text) return text;
  }
  return "";
}

export function artifactOriginTraceId(receipt: ArtifactOriginatingReceipt | undefined): string {
  return firstString(
    receipt?.current_task_trace_id,
    receipt?.handoff_trace_id,
    receipt?.trace_id,
    receipt?.references?.trace_id,
  );
}

function safeBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function safeNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function safeOptionalNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value !== "string") return undefined;

  const parsed = Number(value.trim());
  return Number.isFinite(parsed) ? Math.trunc(parsed) : undefined;
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

function parseOriginatingReceipt(raw: unknown): ArtifactOriginatingReceipt | undefined {
  if (!isRecord(raw)) return undefined;

  const receipt: ArtifactOriginatingReceipt = {};
  for (const key of [
    "source",
    "matched_artifact_field",
    "mission_id",
    "operation_id",
    "approval_id",
    "trace_id",
    "run_id",
    "artifact_dir",
    "operation_status",
    "operation_error",
    "result_message",
    "recovery_next_step",
    "plan_status",
    "plan_current_step_id",
    "plan_current_step_title",
    "active_stage",
    "handoff_stage",
    "handoff_action",
    "handoff_gate",
    "handoff_mission_id",
    "handoff_approval_id",
    "handoff_approval_status",
    "handoff_operation_id",
    "handoff_trace_id",
    "handoff_run_id",
    "handoff_artifact_dir",
    "current_task_source",
    "current_task_gate",
    "current_task_mission_id",
    "current_task_approval_id",
    "current_task_approval_status",
    "current_task_previous_approval_id",
    "current_task_previous_approval_status",
    "current_task_operation_id",
    "current_task_operation_name",
    "current_task_operation_plane",
    "current_task_advance_action",
    "current_task_trace_id",
    "current_task_run_id",
    "current_task_artifact_dir",
    "current_task_next_step",
  ] as const) {
    const value = safeString(raw[key]).trim();
    if (value) receipt[key] = value;
  }

  for (const key of ["plan_step_count", "plan_checkpoint_count"] as const) {
    const value = safeOptionalNumber(raw[key]);
    if (value !== undefined) receipt[key] = Math.max(0, value);
  }

  if (isRecord(raw.references)) {
    const references: NonNullable<ArtifactOriginatingReceipt["references"]> = {};
    for (const key of ["mission_id", "operation_id", "approval_id", "trace_id", "run_id", "artifact_dir"] as const) {
      const value = safeString(raw.references[key]).trim();
      if (value) references[key] = value;
    }
    if (Object.keys(references).length > 0) receipt.references = references;
  }

  return Object.keys(receipt).length > 0 ? receipt : undefined;
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

  const originatingReceipt = parseOriginatingReceipt(raw.originating_receipt);
  if (originatingReceipt) response.originating_receipt = originatingReceipt;

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
