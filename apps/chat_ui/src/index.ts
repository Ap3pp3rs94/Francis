export type ApprovalStatus = "pending" | "approved" | "rejected" | "emergency" | string;

export type ApprovalPayloadSummary = {
  requested_action?: string;
  plugin_id?: string;
  scope_id?: string;
  provider?: string;
  credential_type?: string;
  label?: string;
  credential_id?: string;
  target_kind?: string;
  target_id?: string;
  twin_id?: string;
  url?: string;
  domain?: string;
  actor?: string;
  risk?: string;
  enabled?: boolean;
  dry_run?: boolean;
  risk_tier?: string;
  required_trust?: number;
  payload_keys?: string[];
  input_keys?: string[];
  meta_keys?: string[];
  params_keys?: string[];
};

export type ApprovalItem = {
  id: string;
  ts: number;
  action: string;
  reason?: string;
  payload?: unknown;
  status: ApprovalStatus;
  domain?: string;
  risk?: string;
  request_kind?: string;
  previous_approval_id?: string;
  previous_approval_status?: string;
  payload_summary?: ApprovalPayloadSummary;
};

export class ApprovalsApiError extends Error {
  readonly status?: number;
  readonly url?: string;

  constructor(message: string, opts?: { status?: number; url?: string }) {
    super(message);
    this.name = "ApprovalsApiError";
    this.status = opts?.status;
    this.url = opts?.url;
  }
}

type ListResult = {
  items: ApprovalItem[];
};

type DecideResult = {
  ok: boolean;
  status?: ApprovalStatus;
  item?: ApprovalItem;
  error?: string;
};

function safeString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function safeNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeString(item)).filter(Boolean);
}

function parseApprovalPayloadSummary(raw: Record<string, unknown>): ApprovalPayloadSummary {
  const summary: ApprovalPayloadSummary = {};
  const requestedAction = safeString(raw.requested_action);
  if (requestedAction) summary.requested_action = requestedAction;
  const pluginId = safeString(raw.plugin_id);
  if (pluginId) summary.plugin_id = pluginId;
  const scopeId = safeString(raw.scope_id);
  if (scopeId) summary.scope_id = scopeId;
  const provider = safeString(raw.provider);
  if (provider) summary.provider = provider;
  const credentialType = safeString(raw.credential_type);
  if (credentialType) summary.credential_type = credentialType;
  const label = safeString(raw.label);
  if (label) summary.label = label;
  const credentialId = safeString(raw.credential_id);
  if (credentialId) summary.credential_id = credentialId;
  const targetKind = safeString(raw.target_kind);
  if (targetKind) summary.target_kind = targetKind;
  const targetId = safeString(raw.target_id);
  if (targetId) summary.target_id = targetId;
  const twinId = safeString(raw.twin_id);
  if (twinId) summary.twin_id = twinId;
  const url = safeString(raw.url);
  if (url) summary.url = url;
  const domain = safeString(raw.domain);
  if (domain) summary.domain = domain;
  const actor = safeString(raw.actor);
  if (actor) summary.actor = actor;
  const risk = safeString(raw.risk);
  if (risk) summary.risk = risk;
  if (typeof raw.enabled === "boolean") summary.enabled = raw.enabled;
  if (typeof raw.dry_run === "boolean") summary.dry_run = raw.dry_run;
  const riskTier = safeString(raw.risk_tier);
  if (riskTier) summary.risk_tier = riskTier;
  if (typeof raw.required_trust === "number" && Number.isFinite(raw.required_trust)) {
    summary.required_trust = raw.required_trust;
  }
  const payloadKeys = safeStringList(raw.payload_keys);
  if (payloadKeys.length > 0) summary.payload_keys = payloadKeys;
  const inputKeys = safeStringList(raw.input_keys);
  if (inputKeys.length > 0) summary.input_keys = inputKeys;
  const metaKeys = safeStringList(raw.meta_keys);
  if (metaKeys.length > 0) summary.meta_keys = metaKeys;
  const paramsKeys = safeStringList(raw.params_keys);
  if (paramsKeys.length > 0) summary.params_keys = paramsKeys;
  return summary;
}

function parseApprovalItem(raw: unknown): ApprovalItem | null {
  if (!isRecord(raw)) return null;
  const id = safeString(raw.id);
  if (!id) return null;
  const item: ApprovalItem = {
    id,
    ts: safeNumber(raw.ts),
    action: safeString(raw.action),
    reason: safeString(raw.reason) || undefined,
    payload: raw.payload,
    status: (safeString(raw.status) || "pending") as ApprovalStatus,
    domain: safeString(raw.domain) || undefined,
    risk: safeString(raw.risk) || undefined,
    request_kind: safeString(raw.request_kind) || undefined,
    previous_approval_id: safeString(raw.previous_approval_id) || undefined,
    previous_approval_status: safeString(raw.previous_approval_status) || undefined,
  };
  if (isRecord(raw.payload_summary)) {
    item.payload_summary = parseApprovalPayloadSummary(raw.payload_summary);
  }
  return item;
}

export class ApprovalsClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = (baseUrl || "").replace(/\/+$/, "");
  }

  async list(opts: {
    status?: string;
    limit?: number;
    signal?: AbortSignal;
  }): Promise<ListResult> {
    const status = opts.status ?? "pending";
    const limit = typeof opts.limit === "number" ? opts.limit : 100;
    const url = `${this.baseUrl}/approvals/list?status=${encodeURIComponent(status)}&limit=${limit}`;

    const res = await fetch(url, { method: "GET", signal: opts.signal });
    if (!res.ok) {
      throw new ApprovalsApiError("Failed to list approvals.", { status: res.status, url });
    }

    const data = (await res.json()) as Partial<ListResult> | null;
    return { items: Array.isArray(data?.items) ? data.items.map(parseApprovalItem).filter((item): item is ApprovalItem => item !== null) : [] };
  }

  async decide(opts: { id: string; action: string; comment?: string }): Promise<DecideResult> {
    const url = `${this.baseUrl}/approvals/decision`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: opts.id, action: opts.action, comment: opts.comment }),
    });

    if (!res.ok) {
      throw new ApprovalsApiError("Decision failed.", { status: res.status, url });
    }

    const data = (await res.json()) as Partial<DecideResult> | null;
    return {
      ok: Boolean(data?.ok),
      status: data?.status,
      item: parseApprovalItem(data?.item) ?? undefined,
      error: data?.error,
    };
  }
}
