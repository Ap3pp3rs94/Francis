import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  WebLearningApiError,
  WebLearningClient,
  formatBytes,
  formatMs,
  toLocaleTime,
  type WebLearningEvent,
  type WebLearningExportFormat,
  type WebLearningPolicy,
  type WebLearningQuarantineItem,
  type WebLearningRecord,
  type WebLearningStatus,
} from "./index";

/**
 * WebLearningMonitorPanel
 *
 * Operator goals:
 *  - Observe web learning state + drift quickly.
 *  - Inspect recent records/events/quarantine.
 *  - Provide governed actions (request learn, quarantine decisions, enable/disable)
 *    without assuming backend policy.
 *
 * Non-goals:
 *  - No chart libraries, no heavy UI frameworks, no global state.
 */

export type WebLearningMonitorPanelProps = {
  apiBaseUrl?: string;

  allowMutations?: boolean;
  bearerToken?: string | null;

  title?: string;

  autoRefreshMs?: number;

  recordsLimit?: number;
  eventsLimit?: number;
  quarantineLimit?: number;

  defaultWindowHours?: number;
};

function envString(key: string, fallback = ""): string {
  try {
    const v = (import.meta as unknown as { env?: Record<string, unknown> }).env?.[key];
    return typeof v === "string" ? v : fallback;
  } catch {
    return fallback;
  }
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function safeInt(v: unknown, fallback: number): number {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return fallback;
  return Math.floor(n);
}

function nowUnix(): number {
  return Math.floor(Date.now() / 1000);
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noreferrer";
    a.click();
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

function summarizeStatus(s: WebLearningStatus | null): string {
  if (!s) return "unknown";
  if (!s.enabled) return "disabled";
  if (s.last_error && s.last_error_ts && (nowUnix() - s.last_error_ts) < 60 * 10) return "degraded";
  return "enabled";
}

function badgeStyle(kind: "good" | "warn" | "bad" | "muted"): React.CSSProperties {
  if (kind === "good") return { background: "#e9fbe9", border: "1px solid #bfe9bf", color: "#155d15" };
  if (kind === "warn") return { background: "#fff7db", border: "1px solid #f2dd8c", color: "#6a4b00" };
  if (kind === "bad") return { background: "#ffe9e9", border: "1px solid #f0b6b6", color: "#7a1717" };
  return { background: "#f6f6f6", border: "1px solid #ddd", color: "#333" };
}

function recordStatusKind(status: string): "good" | "warn" | "bad" | "muted" {
  const s = (status || "").toLowerCase();
  if (s === "ingested" || s === "parsed" || s === "fetched") return "good";
  if (s === "quarantined" || s === "blocked" || s === "pending") return "warn";
  if (s === "failed" || s === "error") return "bad";
  return "muted";
}

function eventLine(e: WebLearningEvent): string {
  const k = (e.kind || "event").toLowerCase();
  const msg = e.message ? ` — ${e.message}` : "";
  const url = e.url ? ` (${e.url})` : "";
  return `${k}${msg}${url}`;
}

export default function WebLearningMonitorPanel(props: WebLearningMonitorPanelProps) {
  const apiBaseUrl = useMemo(() => {
    const fromProps = (props.apiBaseUrl || "").trim();
    if (fromProps) return fromProps.replace(/\/+$/, "");
    const fromEnv = envString("VITE_FRANCIS_API_BASE_URL", "").trim();
    return (fromEnv || "http://127.0.0.1:8000").replace(/\/+$/, "");
  }, [props.apiBaseUrl]);

  const allowMutations = Boolean(props.allowMutations ?? false);

  const client = useMemo(() => {
    return new WebLearningClient(apiBaseUrl, {
      mutationsEnabled: allowMutations,
      bearerTokenProvider: () => props.bearerToken ?? null,
      retry: { retries: 1 },
    });
  }, [apiBaseUrl, allowMutations, props.bearerToken]);

  const recordsLimit = clamp(safeInt(props.recordsLimit, 100), 10, 2000);
  const eventsLimit = clamp(safeInt(props.eventsLimit, 200), 10, 2000);
  const quarantineLimit = clamp(safeInt(props.quarantineLimit, 100), 10, 2000);

  const defaultWindowHours = clamp(safeInt(props.defaultWindowHours, 24), 0, 24 * 365);

  const [status, setStatus] = useState<WebLearningStatus | null>(null);
  const [policy, setPolicy] = useState<WebLearningPolicy | null>(null);

  const [records, setRecords] = useState<WebLearningRecord[]>([]);
  const [events, setEvents] = useState<WebLearningEvent[]>([]);
  const [quarantine, setQuarantine] = useState<WebLearningQuarantineItem[]>([]);

  const [loading, setLoading] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  // Filters
  const [windowHours, setWindowHours] = useState<number>(defaultWindowHours);
  const [search, setSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [domainFilter, setDomainFilter] = useState<string>("");

  // Mutations: request learn
  const [learnUrl, setLearnUrl] = useState<string>("");
  const [learnReason, setLearnReason] = useState<string>("");
  const [learnBusy, setLearnBusy] = useState(false);
  const [learnResult, setLearnResult] = useState<string | null>(null);

  // Mutations: enable/disable
  const [toggleBusy, setToggleBusy] = useState(false);

  // Quarantine decisions per item
  const [qBusy, setQBusy] = useState<Record<string, boolean>>({});
  const [qError, setQError] = useState<Record<string, string | null>>({});

  // Export
  const [exportBusy, setExportBusy] = useState(false);
  const [exportProgress, setExportProgress] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  function computeTimeWindow(): { start_ts?: number; end_ts?: number } {
    if (!windowHours || windowHours <= 0) return {};
    const end = nowUnix();
    const start = end - windowHours * 3600;
    return { start_ts: start, end_ts: end };
  }

  async function refreshAll() {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setLoading(true);
    setLastError(null);

    const w = computeTimeWindow();

    try {
      const [s, p, r, e, q] = await Promise.allSettled([
        client.getStatus({ signal: ac.signal }),
        client.getPolicy({ signal: ac.signal }),
        client.listRecords(
          {
            ...w,
            limit: recordsLimit,
            search: search.trim() || undefined,
            status: statusFilter.trim() || undefined,
            domain: domainFilter.trim() || undefined,
          },
          { signal: ac.signal },
        ),
        client.listEvents(
          {
            ...w,
            limit: eventsLimit,
            search: search.trim() || undefined,
            status: statusFilter.trim() || undefined,
            domain: domainFilter.trim() || undefined,
          },
          { signal: ac.signal },
        ),
        client.listQuarantine(
          {
            ...w,
            limit: quarantineLimit,
            search: search.trim() || undefined,
            status: statusFilter.trim() || undefined,
            domain: domainFilter.trim() || undefined,
          },
          { signal: ac.signal },
        ),
      ]);

      if (s.status === "fulfilled") setStatus(s.value);
      if (p.status === "fulfilled") setPolicy(p.value);

      if (r.status === "fulfilled") setRecords(r.value.items);
      if (e.status === "fulfilled") setEvents(e.value.items);
      if (q.status === "fulfilled") setQuarantine(q.value.items);

      // If everything failed, surface one meaningful error.
      const failures = [s, p, r, e, q].filter((x) => x.status === "rejected") as PromiseRejectedResult[];
      if (failures.length === 5) throw failures[0].reason;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;

      const msg =
        err instanceof WebLearningApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}${err.requestId ? ` [req=${err.requestId}]` : ""}`
          : err instanceof Error
            ? err.message
            : "Web learning refresh failed.";

      setLastError(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, windowHours, recordsLimit, eventsLimit, quarantineLimit, search, statusFilter, domainFilter]);

  useEffect(() => {
    const ms = clamp(safeInt(props.autoRefreshMs, 10_000), 0, 120_000);
    if (!ms) return;

    // Jitter to avoid multi-tab thump.
    const jitter = Math.floor(Math.random() * clamp(ms * 0.1, 50, 500));
    const intervalMs = ms + jitter;

    const t = window.setInterval(() => void refreshAll(), intervalMs);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.autoRefreshMs, client, windowHours, search, statusFilter, domainFilter]);

  async function submitLearnRequest() {
    if (!allowMutations) {
      setLearnResult("Mutations disabled (allowMutations=false).");
      return;
    }

    const url = learnUrl.trim();
    if (!url) {
      setLearnResult("Enter a URL.");
      return;
    }

    setLearnBusy(true);
    setLearnResult(null);

    try {
      const res = await client.requestLearn({
        url,
        reason: learnReason.trim() || undefined,
      });

      if (!res.ok) {
        setLearnResult(res.message || "Request failed.");
      } else if (res.approval_id) {
        setLearnResult(`Submitted for approval: ${res.approval_id} (${res.status || "pending"})`);
      } else if (res.record_id) {
        setLearnResult(`Accepted. record_id=${res.record_id}`);
      } else {
        setLearnResult("Submitted.");
      }

      window.setTimeout(() => void refreshAll(), 250);
    } catch (err) {
      const msg =
        err instanceof WebLearningApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}${err.requestId ? ` [req=${err.requestId}]` : ""}`
          : err instanceof Error
            ? err.message
            : "Request failed.";
      setLearnResult(msg);
    } finally {
      setLearnBusy(false);
    }
  }

  async function toggleEnabled() {
    if (!allowMutations) return;
    if (!status) return;

    const next = !status.enabled;

    const reason = window.prompt(`Reason to ${next ? "enable" : "disable"} web learning (recommended)`, "") ?? "";
    if (reason === null) return;

    setToggleBusy(true);
    setLastError(null);

    try {
      const res = await client.setEnabled({ enabled: next, reason: reason.trim() || undefined });
      if (!res.ok) {
        setLastError(res.message || "Toggle failed.");
      } else if (res.approval_id) {
        setLastError(`Submitted for approval: ${res.approval_id} (${res.status || "pending"})`);
        window.setTimeout(() => setLastError(null), 2500);
      }
      window.setTimeout(() => void refreshAll(), 250);
    } catch (err) {
      const msg =
        err instanceof WebLearningApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}${err.requestId ? ` [req=${err.requestId}]` : ""}`
          : err instanceof Error
            ? err.message
            : "Toggle failed.";
      setLastError(msg);
    } finally {
      setToggleBusy(false);
    }
  }

  async function decideQuarantine(id: string, action: "release" | "delete") {
    if (!allowMutations) return;

    const ok =
      action === "delete"
        ? window.confirm(`Delete quarantine item ${id}? This may be irreversible.`)
        : true;

    if (!ok) return;

    let reason: string | undefined;
    if (action !== "release") {
      const r = window.prompt(`Reason for "${action}" (recommended)`, "");
      if (r !== null) reason = r.trim() || undefined;
    }

    setQBusy((prev) => ({ ...prev, [id]: true }));
    setQError((prev) => ({ ...prev, [id]: null }));
    setLastError(null);

    try {
      const res = await client.decideQuarantine({ id, action, reason });
      if (!res.ok) {
        setQError((prev) => ({ ...prev, [id]: res.message || "Decision failed." }));
      } else if (res.approval_id) {
        setQError((prev) => ({ ...prev, [id]: `Submitted for approval: ${res.approval_id} (${res.status || "pending"})` }));
      }

      window.setTimeout(() => void refreshAll(), 250);
    } catch (err) {
      const msg =
        err instanceof WebLearningApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}${err.requestId ? ` [req=${err.requestId}]` : ""}`
          : err instanceof Error
            ? err.message
            : "Decision failed.";
      setQError((prev) => ({ ...prev, [id]: msg }));
    } finally {
      setQBusy((prev) => ({ ...prev, [id]: false }));
    }
  }

  async function doExport(kind: "records" | "events" | "quarantine", format: WebLearningExportFormat) {
    setExportBusy(true);
    setExportProgress(null);
    setLastError(null);

    try {
      const w = computeTimeWindow();
      const res = await client.export(
        {
          kind,
          format,
          ...w,
          status: statusFilter.trim() || undefined,
          domain: domainFilter.trim() || undefined,
          search: search.trim() || undefined,
          reason: "UI export",
        },
        {
          onProgress: (p) => {
            const total = p.totalBytes && Number.isFinite(p.totalBytes) ? ` / ${formatBytes(p.totalBytes)}` : "";
            setExportProgress(`${formatBytes(p.loadedBytes)}${total}`);
          },
        },
      );

      downloadBlob(res.filename, res.blob);
      setExportProgress(null);
    } catch (err) {
      const msg =
        err instanceof WebLearningApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}${err.requestId ? ` [req=${err.requestId}]` : ""}`
          : err instanceof Error
            ? err.message
            : "Export failed.";
      setLastError(msg);
    } finally {
      setExportBusy(false);
      window.setTimeout(() => setExportProgress(null), 1000);
    }
  }

  const st = summarizeStatus(status);
  const stKind = st === "enabled" ? "good" : st === "degraded" ? "warn" : st === "disabled" ? "muted" : "muted";

  return (
    <div style={{ border: "1px solid #ddd", padding: 12, borderRadius: 10 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <h3 style={{ margin: 0 }}>{props.title || "Web Learning Monitor"}</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => void refreshAll()} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
          <button onClick={() => void doExport("records", "json")} disabled={exportBusy}>
            Export Records (json)
          </button>
          <button onClick={() => void doExport("events", "csv")} disabled={exportBusy}>
            Export Events (csv)
          </button>
        </div>
      </div>

      <div style={{ marginTop: 8, fontSize: 12, opacity: 0.85 }}>
        API: <code>{apiBaseUrl}</code>
      </div>

      {lastError ? (
        <div style={{ marginTop: 10, padding: 10, borderRadius: 8, border: "1px solid #f0c36d", background: "#fff7db" }}>
          <b>Notice:</b> {lastError}
        </div>
      ) : null}

      {exportProgress ? (
        <div style={{ marginTop: 10, fontSize: 12, opacity: 0.8 }}>
          Export progress: <code>{exportProgress}</code>
        </div>
      ) : null}

      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 12 }}>
        <section style={{ border: "1px solid #eee", borderRadius: 10, padding: 10 }}>
          <h4 style={{ marginTop: 0 }}>Status</h4>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ padding: "2px 8px", borderRadius: 999, fontSize: 12, ...badgeStyle(stKind) }}>
                {st}
              </span>

              <div style={{ fontSize: 12, opacity: 0.75 }}>
                {status?.ts ? <span>updated {toLocaleTime(status.ts)}</span> : <span>no status endpoint</span>}
              </div>
            </div>

            {allowMutations ? (
              <button onClick={() => void toggleEnabled()} disabled={toggleBusy || !status}>
                {toggleBusy ? "…" : status?.enabled ? "Disable" : "Enable"}
              </button>
            ) : (
              <div style={{ fontSize: 12, opacity: 0.7 }}>mutations disabled</div>
            )}
          </div>

          <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "160px 1fr", gap: 6, fontSize: 13 }}>
            <div>Enabled</div>
            <div><code>{status ? (status.enabled ? "true" : "false") : "—"}</code></div>

            <div>Approvals required</div>
            <div><code>{status?.approvals_required !== undefined ? String(status.approvals_required) : "—"}</code></div>

            <div>Queue depth</div>
            <div><code>{status?.queue_depth !== undefined ? String(status.queue_depth) : "—"}</code></div>

            <div>In flight</div>
            <div><code>{status?.in_flight !== undefined ? String(status.in_flight) : "—"}</code></div>

            <div>Concurrency</div>
            <div><code>{status?.concurrency !== undefined ? String(status.concurrency) : "—"}</code></div>

            <div>Last success</div>
            <div><code>{status?.last_success_ts ? toLocaleTime(status.last_success_ts) : "—"}</code></div>

            <div>Last error</div>
            <div style={{ color: status?.last_error ? "#7a1717" : undefined }}>
              {status?.last_error ? (
                <>
                  <code>{toLocaleTime(status.last_error_ts)}</code> — {status.last_error}
                </>
              ) : (
                <code>—</code>
              )}
            </div>
          </div>

          {policy ? (
            <details style={{ marginTop: 10 }}>
              <summary style={{ cursor: "pointer" }}>Policy</summary>
              {policy.summary ? <div style={{ marginTop: 8, fontSize: 13 }}><b>summary:</b> {policy.summary}</div> : null}
              <pre style={{ marginTop: 8, fontSize: 12, maxHeight: 220, overflow: "auto", background: "#0b0f1a", color: "#e8e8e8", padding: 10, borderRadius: 8 }}>
                {JSON.stringify(policy, null, 2)}
              </pre>
            </details>
          ) : (
            <div style={{ marginTop: 10, fontSize: 12, opacity: 0.7 }}>
              <i>No policy endpoint available.</i>
            </div>
          )}
        </section>

        <section style={{ border: "1px solid #eee", borderRadius: 10, padding: 10 }}>
          <h4 style={{ marginTop: 0 }}>Operator Controls</h4>

          <div style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 8, alignItems: "center" }}>
            <div>Time window (hours)</div>
            <input
              type="number"
              min={0}
              max={24 * 365}
              step={1}
              value={windowHours}
              onChange={(e) => setWindowHours(clamp(Number(e.target.value), 0, 24 * 365))}
            />

            <div>Search</div>
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="url/title/error contains…" />

            <div>Status filter</div>
            <input value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} placeholder="e.g. failed, quarantined" />

            <div>Domain filter</div>
            <input value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)} placeholder="e.g. example.com" />
          </div>

          <div style={{ marginTop: 14, borderTop: "1px dashed #eee", paddingTop: 12 }}>
            <h4 style={{ marginTop: 0 }}>Request Learn</h4>

            <div style={{ display: "grid", gridTemplateColumns: "110px 1fr", gap: 8, alignItems: "center" }}>
              <div>URL</div>
              <input value={learnUrl} onChange={(e) => setLearnUrl(e.target.value)} placeholder="https://…" disabled={!allowMutations || learnBusy} />

              <div>Reason</div>
              <input value={learnReason} onChange={(e) => setLearnReason(e.target.value)} placeholder="optional (recommended)" disabled={!allowMutations || learnBusy} />
            </div>

            <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
              <button onClick={() => void submitLearnRequest()} disabled={!allowMutations || learnBusy || learnUrl.trim().length === 0}>
                {learnBusy ? "Submitting…" : "Submit"}
              </button>
              <button onClick={() => { setLearnUrl(""); setLearnReason(""); setLearnResult(null); }} disabled={learnBusy}>
                Reset
              </button>
            </div>

            {learnResult ? (
              <div style={{ marginTop: 10, padding: 8, borderRadius: 8, border: "1px solid #f1f1f1", background: "#fafafa" }}>
                <div style={{ fontSize: 12, opacity: 0.75 }}>result</div>
                <div style={{ marginTop: 4, fontSize: 13 }}>{learnResult}</div>
              </div>
            ) : null}

            {!allowMutations ? (
              <div style={{ marginTop: 8, fontSize: 12, opacity: 0.7 }}>
                Mutations disabled. Set <code>allowMutations</code> to true to enable request + quarantine actions (backend still enforces approvals/policy).
              </div>
            ) : null}
          </div>
        </section>
      </div>

      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <section style={{ border: "1px solid #eee", borderRadius: 10, padding: 10 }}>
          <h4 style={{ marginTop: 0 }}>Recent Records</h4>

          {records.length === 0 ? (
            <i style={{ opacity: 0.75 }}>No records (or endpoint unavailable).</i>
          ) : (
            <div style={{ maxHeight: 360, overflow: "auto", border: "1px solid #f1f1f1", borderRadius: 8, padding: 8 }}>
              {records.map((r) => (
                <div key={r.id} style={{ padding: "6px 0", borderBottom: "1px dashed #eee" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ padding: "2px 8px", borderRadius: 999, fontSize: 12, ...badgeStyle(recordStatusKind(r.status)) }}>
                          {r.status}
                        </span>

                        <a href={r.url} target="_blank" rel="noreferrer" style={{ fontSize: 13, wordBreak: "break-all" }}>
                          {r.url}
                        </a>
                      </div>

                      {r.title ? <div style={{ marginTop: 4, fontSize: 12, opacity: 0.85 }}>{r.title}</div> : null}
                      {r.error ? <div style={{ marginTop: 4, fontSize: 12, color: "#7a1717" }}>{r.error}</div> : null}

                      <div style={{ marginTop: 4, fontSize: 11, opacity: 0.75 }}>
                        {r.domain ? <span>domain: <code>{r.domain}</code></span> : null}
                        {r.http_status ? <span>{r.domain ? " · " : ""}http: <code>{r.http_status}</code></span> : null}
                        {r.content_type ? <span>{(r.domain || r.http_status) ? " · " : ""}type: <code>{r.content_type}</code></span> : null}
                        {r.approval_id ? <span>{(r.domain || r.http_status || r.content_type) ? " · " : ""}approval: <code>{r.approval_id}</code></span> : null}
                        {r.quarantine_id ? <span>{(r.domain || r.http_status || r.content_type || r.approval_id) ? " · " : ""}quarantine: <code>{r.quarantine_id}</code></span> : null}
                      </div>
                    </div>

                    <div style={{ textAlign: "right", fontSize: 11, opacity: 0.8, minWidth: 140 }}>
                      <div><code>{toLocaleTime(r.ts)}</code></div>
                      <div>{formatBytes(r.bytes)} · {formatMs(r.duration_ms)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section style={{ border: "1px solid #eee", borderRadius: 10, padding: 10 }}>
          <h4 style={{ marginTop: 0 }}>Recent Events</h4>

          {events.length === 0 ? (
            <i style={{ opacity: 0.75 }}>No events (or endpoint unavailable).</i>
          ) : (
            <div style={{ maxHeight: 360, overflow: "auto", border: "1px solid #f1f1f1", borderRadius: 8, padding: 8 }}>
              {events.map((e) => (
                <div key={e.id} style={{ padding: "6px 0", borderBottom: "1px dashed #eee" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                    <div style={{ minWidth: 0 }}>
                      <b style={{ fontSize: 13 }}>{(e.kind || "event").toLowerCase()}</b>
                      <div style={{ fontSize: 12, opacity: 0.85, wordBreak: "break-word" }}>{eventLine(e)}</div>

                      <div style={{ marginTop: 4, fontSize: 11, opacity: 0.75 }}>
                        {e.domain ? <span>domain: <code>{e.domain}</code></span> : null}
                        {e.http_status ? <span>{e.domain ? " · " : ""}http: <code>{e.http_status}</code></span> : null}
                        {typeof e.bytes === "number" && e.bytes > 0 ? <span>{(e.domain || e.http_status) ? " · " : ""}bytes: <code>{formatBytes(e.bytes)}</code></span> : null}
                        {e.approval_id ? <span>{(e.domain || e.http_status || e.bytes) ? " · " : ""}approval: <code>{e.approval_id}</code></span> : null}
                        {e.quarantine_id ? <span>{(e.domain || e.http_status || e.bytes || e.approval_id) ? " · " : ""}quarantine: <code>{e.quarantine_id}</code></span> : null}
                      </div>
                    </div>

                    <div style={{ textAlign: "right", fontSize: 11, opacity: 0.8, minWidth: 140 }}>
                      <div><code>{toLocaleTime(e.ts)}</code></div>
                      <div>{formatMs(e.duration_ms)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <div style={{ marginTop: 12 }}>
        <section style={{ border: "1px solid #eee", borderRadius: 10, padding: 10 }}>
          <h4 style={{ marginTop: 0 }}>Quarantine</h4>

          {quarantine.length === 0 ? (
            <i style={{ opacity: 0.75 }}>No quarantine items (or endpoint unavailable).</i>
          ) : (
            <div style={{ maxHeight: 360, overflow: "auto", border: "1px solid #f1f1f1", borderRadius: 8, padding: 8 }}>
              {quarantine.map((q) => {
                const busy = Boolean(qBusy[q.id]);
                const err = qError[q.id];

                return (
                  <div key={q.id} style={{ padding: "8px 0", borderBottom: "1px dashed #eee" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start" }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                          <span style={{ padding: "2px 8px", borderRadius: 999, fontSize: 12, ...badgeStyle("warn") }}>
                            {q.status || "quarantine"}
                          </span>

                          <a href={q.url} target="_blank" rel="noreferrer" style={{ fontSize: 13, wordBreak: "break-all" }}>
                            {q.url}
                          </a>
                        </div>

                        {q.reason ? <div style={{ marginTop: 4, fontSize: 12, opacity: 0.85 }}>{q.reason}</div> : null}
                        {q.evidence ? <div style={{ marginTop: 4, fontSize: 12, opacity: 0.8 }}>{q.evidence}</div> : null}

                        <div style={{ marginTop: 4, fontSize: 11, opacity: 0.75 }}>
                          {q.domain ? <span>domain: <code>{q.domain}</code></span> : null}
                          {q.record_id ? <span>{q.domain ? " · " : ""}record: <code>{q.record_id}</code></span> : null}
                          {q.approval_id ? <span>{(q.domain || q.record_id) ? " · " : ""}approval: <code>{q.approval_id}</code></span> : null}
                        </div>

                        {err ? (
                          <div style={{ marginTop: 6, fontSize: 12, color: "#7a1717" }}>
                            {err}
                          </div>
                        ) : null}
                      </div>

                      <div style={{ textAlign: "right", minWidth: 180 }}>
                        <div style={{ fontSize: 11, opacity: 0.8 }}>
                          <code>{toLocaleTime(q.ts)}</code>
                        </div>

                        {allowMutations ? (
                          <div style={{ marginTop: 8, display: "flex", gap: 8, justifyContent: "flex-end" }}>
                            <button disabled={busy} onClick={() => void decideQuarantine(q.id, "release")}>
                              {busy ? "…" : "Release"}
                            </button>
                            <button disabled={busy} onClick={() => void decideQuarantine(q.id, "delete")}>
                              {busy ? "…" : "Delete"}
                            </button>
                          </div>
                        ) : (
                          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.7 }}>mutations disabled</div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.7 }}>
            Tip: Use filters above to isolate <code>quarantined</code> or <code>failed</code> flows and export audit trails.
          </div>
        </section>
      </div>
    </div>
  );
}
