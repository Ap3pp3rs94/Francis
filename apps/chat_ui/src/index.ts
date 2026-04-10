export type ApprovalStatus = "pending" | "approved" | "rejected" | "emergency" | string;

export type ApprovalItem = {
  id: string;
  ts: number;
  action: string;
  reason?: string;
  payload?: unknown;
  status: ApprovalStatus;
  domain?: string;
  risk?: string;
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
    return { items: Array.isArray(data?.items) ? (data?.items as ApprovalItem[]) : [] };
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
      item: data?.item,
      error: data?.error,
    };
  }
}
