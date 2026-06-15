import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { fetchLensMcpStatus, type LensMcpStatus } from "./lens/mcpStatus";

function envString(key: string, fallback = ""): string {
  const env = (import.meta.env ?? {}) as Record<string, unknown>;
  const value = env[key];
  return typeof value === "string" ? value : fallback;
}

function apiBaseUrl(): string {
  return envString("VITE_FRANCIS_API_BASE_URL", envString("VITE_API_BASE_URL", "http://127.0.0.1:8000")).trim();
}

function statusText(value: unknown): string {
  return typeof value === "string" && value.trim() ? value.trim() : "unknown";
}

function boolText(value: boolean): string {
  return value ? "true" : "false";
}

function Pill(props: { label: string; value: string; tone?: "ready" | "blocked" | "neutral" }) {
  const border = props.tone === "ready" ? "#6ee7b7" : props.tone === "blocked" ? "#fca5a5" : "#cbd5e1";
  return (
    <span
      style={{
        border: `1px solid ${border}`,
        borderRadius: 999,
        display: "inline-flex",
        gap: 8,
        padding: "6px 10px",
        whiteSpace: "nowrap",
      }}
    >
      <strong>{props.label}</strong>
      <span>{props.value}</span>
    </span>
  );
}

function BodyStatePanel(props: { status: LensMcpStatus | null; loading: boolean; error: string; onRefresh: () => void }) {
  const status = props.status;
  const ready = status?.status === "ready" && status.mcp.missing_tools.length === 0 && status.blockers.length === 0;

  return (
    <section
      style={{
        border: "1px solid rgba(148, 163, 184, 0.35)",
        borderRadius: 18,
        padding: 24,
        background: "rgba(15, 23, 42, 0.86)",
        boxShadow: "0 24px 80px rgba(0,0,0,0.28)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div>
          <p style={{ color: "#93c5fd", margin: 0, textTransform: "uppercase", letterSpacing: 1.8 }}>
            Lens / Orb body-state
          </p>
          <h1 style={{ fontSize: 34, margin: "8px 0 8px" }}>Francis MCP Status</h1>
          <p style={{ color: "#cbd5e1", margin: 0, maxWidth: 760 }}>
            Read-only projection from the existing Lens surface into the MCP, screen, takeover, and input
            substrate. This does not grant resident or input authority.
          </p>
        </div>
        <button
          type="button"
          onClick={props.onRefresh}
          disabled={props.loading}
          style={{
            background: "#e2e8f0",
            border: 0,
            borderRadius: 12,
            color: "#0f172a",
            cursor: props.loading ? "wait" : "pointer",
            fontWeight: 700,
            padding: "10px 14px",
          }}
        >
          {props.loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {props.error ? (
        <div style={{ border: "1px solid #fca5a5", borderRadius: 12, color: "#fecaca", marginTop: 20, padding: 14 }}>
          {props.error}
        </div>
      ) : null}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 22 }}>
        <Pill label="status" value={statusText(status?.status)} tone={ready ? "ready" : "blocked"} />
        <Pill label="posture" value={statusText(status?.embodied_posture)} tone="neutral" />
        <Pill label="tools" value={String(status?.mcp.tool_count ?? 0)} tone="neutral" />
        <Pill label="missing" value={String(status?.mcp.missing_tools.length ?? 0)} tone={ready ? "ready" : "blocked"} />
        <Pill label="resident" value={boolText(status?.resident ?? false)} tone="neutral" />
        <Pill label="blockers" value={String(status?.blockers.length ?? 0)} tone={ready ? "ready" : "blocked"} />
      </div>

      <dl style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: 24 }}>
        <div>
          <dt style={{ color: "#94a3b8" }}>Route</dt>
          <dd style={{ margin: 0 }}>{status?.routes.mcp_status ?? "/lens/mcp/status"}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Execution authority</dt>
          <dd style={{ margin: 0 }}>{boolText(Boolean(status?.governance["grants_execution_authority"]))}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Mutation authority</dt>
          <dd style={{ margin: 0 }}>{boolText(Boolean(status?.governance["grants_mutation_authority"]))}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Read-only</dt>
          <dd style={{ margin: 0 }}>{boolText(Boolean(status?.governance["read_only"]))}</dd>
        </div>
      </dl>

      <pre
        style={{
          background: "rgba(2, 6, 23, 0.86)",
          borderRadius: 14,
          color: "#bfdbfe",
          marginTop: 24,
          maxHeight: 340,
          overflow: "auto",
          padding: 16,
        }}
      >
        {JSON.stringify(
          status
            ? {
                status: status.status,
                embodied_posture: status.embodied_posture,
                resident: status.resident,
                blockers: status.blockers,
                mcp: status.mcp,
                routes: status.routes,
              }
            : { status: props.loading ? "loading" : "not_loaded" },
          null,
          2,
        )}
      </pre>
    </section>
  );
}

export default function App() {
  const [status, setStatus] = useState<LensMcpStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const baseUrl = useMemo(() => apiBaseUrl(), []);

  const refresh = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");

    void fetchLensMcpStatus({ baseUrl, actor: "chat_ui.lens", signal: controller.signal })
      .then((nextStatus) => {
        setStatus(nextStatus);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Lens MCP status request failed.");
      })
      .finally(() => {
        setLoading(false);
      });

    return () => controller.abort();
  }, [baseUrl]);

  useEffect(() => refresh(), [refresh]);

  const shell: CSSProperties = {
    background: "radial-gradient(circle at top left, #1e3a8a 0, #020617 48%, #020617 100%)",
    color: "#f8fafc",
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    minHeight: "100vh",
    padding: 32,
  };

  return (
    <main style={shell}>
      <BodyStatePanel status={status} loading={loading} error={error} onRefresh={refresh} />
    </main>
  );
}
