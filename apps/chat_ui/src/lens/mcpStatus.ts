export type LensMcpStatusComponent = {
  authority: string;
  data: Record<string, unknown>;
  error: string;
  label: string;
  ok: boolean;
  safe_readback: boolean;
  status: string;
  tool: string;
};

export type LensMcpToolState = {
  expected_tool_count: number;
  tool_count: number;
  missing_tools: string[];
  missing_required_tools: string[];
};

export type LensMcpStatus = {
  ok: boolean;
  kind: string;
  status: string;
  embodied_posture: string;
  resident: boolean;
  blockers: string[];
  mcp: LensMcpToolState;
  routes: {
    mcp_status: string;
    orb_mcp_status: string;
  };
  governance: Record<string, unknown>;
  components: Record<string, LensMcpStatusComponent>;
  error?: string;
};

export class LensMcpStatusError extends Error {
  readonly status?: number;
  readonly url?: string;

  constructor(message: string, opts?: { status?: number; url?: string; cause?: unknown }) {
    super(message);
    this.name = "LensMcpStatusError";
    this.status = opts?.status;
    this.url = opts?.url;
    if (opts?.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = opts.cause;
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function safeString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function safeBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function safeNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function safeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => safeString(item).trim()).filter(Boolean) : [];
}

function normalizeBaseUrl(value: string | undefined): string {
  return (value ?? "").trim().replace(/\/+$/, "");
}

function parseComponent(value: unknown): LensMcpStatusComponent {
  const raw = safeRecord(value);
  return {
    authority: safeString(raw["authority"]).trim(),
    data: safeRecord(raw["data"]),
    error: safeString(raw["error"]).trim(),
    label: safeString(raw["label"]).trim(),
    ok: safeBoolean(raw["ok"], false),
    safe_readback: safeBoolean(raw["safe_readback"], false),
    status: safeString(raw["status"]).trim(),
    tool: safeString(raw["tool"]).trim(),
  };
}

function parseComponents(value: unknown): Record<string, LensMcpStatusComponent> {
  const raw = safeRecord(value);
  const out: Record<string, LensMcpStatusComponent> = {};
  for (const [key, component] of Object.entries(raw)) {
    out[key] = parseComponent(component);
  }
  return out;
}

export function parseLensMcpStatus(value: unknown): LensMcpStatus {
  const raw = safeRecord(value);
  const mcp = safeRecord(raw["mcp"]);
  const routes = safeRecord(raw["routes"]);
  const missingRequiredTools = safeStringList(mcp["missing_required_tools"]);
  const missingTools = safeStringList(mcp["missing_tools"]);
  const expectedToolCount = safeNumber(
    mcp["expected_tool_count"],
    safeNumber(mcp["expected_min_tool_count"], 0),
  );

  return {
    ok: safeBoolean(raw["ok"], false),
    kind: safeString(raw["kind"]).trim(),
    status: safeString(raw["status"]).trim(),
    embodied_posture: safeString(raw["embodied_posture"]).trim(),
    resident: safeBoolean(raw["resident"], false),
    blockers: safeStringList(raw["blockers"]),
    mcp: {
      expected_tool_count: expectedToolCount,
      tool_count: safeNumber(mcp["tool_count"], 0),
      missing_tools: missingTools.length ? missingTools : missingRequiredTools,
      missing_required_tools: missingRequiredTools.length ? missingRequiredTools : missingTools,
    },
    routes: {
      mcp_status: safeString(routes["mcp_status"]).trim(),
      orb_mcp_status: safeString(routes["orb_mcp_status"]).trim(),
    },
    governance: safeRecord(raw["governance"]),
    components: parseComponents(raw["components"]),
    error: safeString(raw["error"]).trim() || undefined,
  };
}

export async function fetchLensMcpStatus(opts?: {
  baseUrl?: string;
  actor?: string;
  signal?: AbortSignal;
}): Promise<LensMcpStatus> {
  const baseUrl = normalizeBaseUrl(opts?.baseUrl);
  const actor = encodeURIComponent(opts?.actor?.trim() || "chat_ui.lens");
  const url = `${baseUrl}/lens/mcp/status?actor=${actor}`;
  const res = await fetch(url, { method: "GET", signal: opts?.signal });
  const text = await res.text();

  let json: unknown = {};
  if (text.trim()) {
    try {
      json = JSON.parse(text);
    } catch (err) {
      throw new LensMcpStatusError("Lens MCP status response was not valid JSON.", {
        status: res.status,
        url,
        cause: err,
      });
    }
  }

  if (!res.ok) {
    throw new LensMcpStatusError(`Lens MCP status request failed with HTTP ${res.status}.`, {
      status: res.status,
      url,
    });
  }

  return parseLensMcpStatus(json);
}
