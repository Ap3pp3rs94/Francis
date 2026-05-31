import React, { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApprenticeshipApiError,
  ApprenticeshipClient,
  type ApprenticeshipLiveTeachingSessionUx,
  type ApprenticeshipStatusSnapshot,
  presentApprenticeshipPanel,
} from "./index";

const PANEL = "#141414";
const PANEL_BORDER = "#242424";
const TEXT = "#f5f5f5";
const MUTED = "#bdbdbd";
const BUTTON_BG = "#1f1f1f";
const BUTTON_BORDER = "#333333";

const panelStyle: React.CSSProperties = {
  border: `1px solid ${PANEL_BORDER}`,
  padding: 16,
  borderRadius: 14,
  background: PANEL,
};

const buttonStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: 12,
  border: `1px solid ${BUTTON_BORDER}`,
  background: BUTTON_BG,
  color: TEXT,
};

function badgeStyle(value: string): React.CSSProperties {
  const lower = value.toLowerCase();
  const ready = lower.includes("ready") || lower.includes("blocked") === false;
  return {
    display: "inline-flex",
    alignItems: "center",
    padding: "3px 7px",
    borderRadius: 999,
    border: `1px solid ${ready ? "#2f5f46" : "#5a1a1a"}`,
    background: ready ? "#102218" : "#2a0f0f",
    color: ready ? "#9de2ad" : "#ffaaaa",
    fontSize: 11,
    lineHeight: 1.2,
  };
}

function errorText(err: unknown): string {
  if (err instanceof ApprenticeshipApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Apprenticeship request failed.";
}

export function ApprenticeshipPanel(props: { baseUrl: string }) {
  const client = useMemo(() => new ApprenticeshipClient(props.baseUrl), [props.baseUrl]);
  const [status, setStatus] = useState<ApprenticeshipStatusSnapshot | null>(null);
  const [ux, setUx] = useState<ApprenticeshipLiveTeachingSessionUx | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextStatus, nextUx] = await Promise.all([client.getStatus(), client.getLiveTeachingSessionUx()]);
      setStatus(nextStatus);
      setUx(nextUx);
      setLoadedAt(Date.now());
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const model = presentApprenticeshipPanel(status, ux);

  return (
    <section style={panelStyle}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Apprenticeship</div>
          <div style={{ fontSize: 12, color: MUTED, marginTop: 6 }}>
            {model.readyCount}/{model.requiredCount} deliverables / next <code>{model.nextGap}</code>
          </div>
        </div>
        <button style={buttonStyle} onClick={() => void refresh()} disabled={loading}>
          {loading ? "Loading" : "Refresh"}
        </button>
      </div>

      {error ? <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 10 }}>{error}</div> : null}
      {loadedAt ? <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>Loaded {new Date(loadedAt).toLocaleTimeString()}</div> : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8, marginTop: 12 }}>
        <div style={{ border: `1px solid ${PANEL_BORDER}`, borderRadius: 10, padding: 10, background: "#121212" }}>
          <div style={{ fontSize: 11, color: MUTED }}>Stage</div>
          <div style={{ fontSize: 15, fontWeight: 700, marginTop: 4 }}>{model.stage}</div>
          <div style={{ marginTop: 8 }}>
            <span style={badgeStyle(model.status)}>{model.status}</span>
          </div>
        </div>
        <div style={{ border: `1px solid ${PANEL_BORDER}`, borderRadius: 10, padding: 10, background: "#121212" }}>
          <div style={{ fontSize: 11, color: MUTED }}>Ready deliverables</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
            {model.readyDeliverables.map((item) => (
              <span key={`apprenticeship-ready-${item}`} style={badgeStyle("ready")}>
                {item}
              </span>
            ))}
          </div>
        </div>
        <div style={{ border: `1px solid ${PANEL_BORDER}`, borderRadius: 10, padding: 10, background: "#121212" }}>
          <div style={{ fontSize: 11, color: MUTED }}>Guards</div>
          <div style={{ display: "grid", gap: 4, marginTop: 8 }}>
            {model.guardLines.map((item) => (
              <div key={`apprenticeship-guard-${item}`} style={{ fontSize: 12, color: TEXT }}>
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Visible surfaces</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
            {model.visibleSections.map((item) => (
              <span key={`apprenticeship-section-${item}`} style={badgeStyle("visible")}>
                {item}
              </span>
            ))}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Disabled actions</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
            {model.disabledActions.map((item) => (
              <span key={`apprenticeship-disabled-${item}`} style={badgeStyle("blocked")}>
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
