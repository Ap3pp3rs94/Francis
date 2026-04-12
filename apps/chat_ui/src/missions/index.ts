import type { OperationDetail, OperationRecord } from "../operations";
import { parseOperationDetail, parseOperationRecord } from "../operations";

export type MissionRecord = {
  id: string;
  status?: string;
  objective?: string;
  summary?: string;
  next_step?: string;
  requester_id?: string;
  priority?: number;
  risk_tier?: string;
  linked_task_ids?: string[];
  linked_task_count?: number;
  deadletter_reason?: string;
  created_at?: string;
  updated_at?: string;
  meta?: Record<string, unknown>;
};

export type MissionHistoryEntry = {
  ts?: string;
  mission_id?: string;
  event?: string;
  details?: Record<string, unknown>;
};

export type MissionDetail = {
  ok: boolean;
  mission?: MissionRecord;
  history?: MissionHistoryEntry[];
  linked_operations?: OperationDetail[];
  run_ledger?: OperationRecord[];
  error?: string;
};

export class MissionsApiError extends Error {
  readonly status?: number;
  readonly url?: string;
  readonly bodySnippet?: string;

  constructor(message: string, opts?: { status?: number; url?: string; bodySnippet?: string; cause?: unknown }) {
    super(message);
    this.name = "MissionsApiError";
    this.status = opts?.status;
    this.url = opts?.url;
    this.bodySnippet = opts?.bodySnippet;
    // @ts-expect-error Error.cause depends on TS lib target.
    this.cause = opts?.cause;
  }
}

type TimeoutFetchInit = RequestInit & {
  timeoutMs?: number;
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function safeBoolean(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function safeStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.map((item) => (typeof item === "string" ? item.trim() : "")).filter((item) => item.length > 0);
  return out.length ? out : undefined;
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

async function readTextSnippet(res: Response, maxChars = 1200): Promise<string> {
  try {
    const text = await res.text();
    return text.slice(0, maxChars);
  } catch {
    return "";
  }
}

async function fetchWithTimeout(url: string, init?: TimeoutFetchInit): Promise<Response> {
  const timeoutMs = Math.max(1000, Math.floor(init?.timeoutMs ?? 20_000));
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(new Error(`Mission request timed out after ${timeoutMs}ms`)), timeoutMs);

  try {
    const signal = init?.signal
      ? AbortSignal.any
        ? AbortSignal.any([init.signal, controller.signal])
        : controller.signal
      : controller.signal;
    const response = await fetch(url, {
      ...init,
      signal,
      headers: {
        Accept: "application/json, text/plain;q=0.9, */*;q=0.8",
        ...(init?.headers ?? {}),
      },
    });
    return response;
  } catch (err) {
    if (err instanceof MissionsApiError) throw err;
    throw new MissionsApiError("Mission request failed", { url, cause: err });
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchJson(url: string, init?: TimeoutFetchInit): Promise<unknown> {
  const res = await fetchWithTimeout(url, init);
  if (!res.ok) {
    const snippet = await readTextSnippet(res);
    throw new MissionsApiError(`HTTP ${res.status} for mission request`, {
      status: res.status,
      url,
      bodySnippet: snippet,
    });
  }

  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function parseMissionRecord(raw: unknown): MissionRecord | undefined {
  if (!isRecord(raw)) return undefined;

  const id = safeString(raw.id) || safeString(raw.mission_id);
  if (!id) return undefined;

  const record: MissionRecord = {
    id,
    status: safeString(raw.status, "") || undefined,
    objective: safeString(raw.objective, "") || undefined,
    summary: safeString(raw.summary, "") || undefined,
    next_step: safeString(raw.next_step, "") || undefined,
    requester_id: safeString(raw.requester_id, "") || undefined,
    priority: safeNumber(raw.priority, 0) || undefined,
    risk_tier: safeString(raw.risk_tier, "") || undefined,
    linked_task_ids: safeStringArray(raw.linked_task_ids),
    linked_task_count: safeNumber(raw.linked_task_count, 0) || undefined,
    deadletter_reason: safeString(raw.deadletter_reason, "") || undefined,
    created_at: safeString(raw.created_at, "") || undefined,
    updated_at: safeString(raw.updated_at, "") || undefined,
    meta: isRecord(raw.meta) ? raw.meta : undefined,
  };

  return record;
}

function parseMissionHistoryEntry(raw: unknown): MissionHistoryEntry | null {
  if (!isRecord(raw)) return null;
  return {
    ts: safeString(raw.ts, "") || undefined,
    mission_id: safeString(raw.mission_id, "") || undefined,
    event: safeString(raw.event, "") || undefined,
    details: isRecord(raw.details) ? raw.details : undefined,
  };
}

function parseMissionDetail(json: unknown, idHint = ""): MissionDetail {
  if (!isRecord(json)) {
    return {
      ok: false,
      mission: idHint ? { id: idHint } : undefined,
      history: [],
      linked_operations: [],
      run_ledger: [],
      error: typeof json === "string" ? json : "invalid_mission_payload",
    };
  }

  const mission = parseMissionRecord(json.mission) ?? parseMissionRecord(json) ?? (idHint ? { id: idHint } : undefined);
  const history = Array.isArray(json.history)
    ? json.history.map(parseMissionHistoryEntry).filter((item): item is MissionHistoryEntry => item !== null)
    : [];
  const linked_operations = Array.isArray(json.linked_operations)
    ? json.linked_operations
        .map((item) => parseOperationDetail(item, mission?.id ?? idHint))
        .filter((item): item is OperationDetail => item !== null)
    : [];
  const run_ledger = Array.isArray(json.run_ledger)
    ? json.run_ledger
        .map((item) => {
          const parsed = parseOperationRecord(item);
          if (!parsed || !isRecord(item)) return parsed;
          const mergedMeta: Record<string, unknown> = {
            ...(isRecord(parsed.meta) ? parsed.meta : {}),
          };
          if (safeString(item.operation_id)) mergedMeta.operation_id = safeString(item.operation_id);
          if (safeString(item.operation_name)) mergedMeta.operation_name = safeString(item.operation_name);
          if (safeString(item.operation_status)) mergedMeta.operation_status = safeString(item.operation_status);
          if (!Object.keys(mergedMeta).length) return parsed;
          return { ...parsed, meta: mergedMeta };
        })
        .filter((item): item is OperationRecord => item !== null)
    : [];

  return {
    ok: safeBoolean(json.ok, Boolean(mission)),
    mission,
    history,
    linked_operations,
    run_ledger,
    error: safeString(json.error, "") || undefined,
  };
}

export class MissionsClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
  }

  private missionUrl(missionId: string): string {
    const cleaned = (missionId || "").trim();
    if (!cleaned) throw new Error("Mission id is required");
    return `${this.baseUrl}/missions/${encodeURIComponent(cleaned)}`;
  }

  async get(missionId: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<MissionDetail> {
    const json = await fetchJson(this.missionUrl(missionId), {
      method: "GET",
      signal: opts?.signal,
      timeoutMs: opts?.timeoutMs,
    });
    return parseMissionDetail(json, missionId);
  }
}
