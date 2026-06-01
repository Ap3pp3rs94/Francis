import React, { useCallback, useEffect, useMemo, useState } from "react";

import {
  FederationApiError,
  FederationClient,
  presentFederationSleepContinuityAction,
  type FederationSleepContinuityActionReadback,
  type FederationSleepContinuityPresentation,
  type FederationStage16Status,
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
  const ready = lower.includes("ready") || lower.includes("validated") || lower.includes("capture");
  const blocked = lower.includes("blocked") || lower.includes("false") || lower.includes("missing");
  return {
    display: "inline-flex",
    alignItems: "center",
    padding: "3px 7px",
    borderRadius: 999,
    border: `1px solid ${ready && !blocked ? "#2f5f46" : "#5a1a1a"}`,
    background: ready && !blocked ? "#102218" : "#2a0f0f",
    color: ready && !blocked ? "#9de2ad" : "#ffaaaa",
    fontSize: 11,
    lineHeight: 1.2,
  };
}

function errorText(err: unknown): string {
  if (err instanceof FederationApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Federation request failed.";
}

function yesNo(value: boolean): string {
  return value ? "true" : "false";
}

function codeValue(value: string | undefined, fallback = "none"): string {
  const text = (value ?? "").trim();
  return text || fallback;
}

export function FederationHubPanel(props: { baseUrl: string }) {
  const client = useMemo(() => new FederationClient(props.baseUrl), [props.baseUrl]);
  const [status, setStatus] = useState<FederationStage16Status | null>(null);
  const [action, setAction] = useState<FederationSleepContinuityActionReadback | null>(null);
  const [presentation, setPresentation] = useState<FederationSleepContinuityPresentation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextStatus, nextAction] = await Promise.all([
        client.getStatus({ timeoutMs: 10_000 }),
        client.getSleepContinuityAction({ timeoutMs: 10_000 }),
      ]);
      setStatus(nextStatus);
      setAction(nextAction);
      setPresentation(presentFederationSleepContinuityAction(nextAction));
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

  const blockers = presentation?.blockers.length ? presentation.blockers : status?.completion_review_blockers ?? [];
  const priorLiveReadbackBlockers = presentation?.prior_live_readback_blockers ?? [];
  const selectedAction = action?.selected_action;

  return (
    <section style={panelStyle}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Federation</div>
          <div style={{ fontSize: 12, color: MUTED, marginTop: 6 }}>
            Stage 16 / next{" "}
            <code>{codeValue(presentation?.next_smallest_truthful_gap ?? status?.next_smallest_truthful_gap)}</code>
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
          <div style={{ fontSize: 11, color: MUTED }}>Stage state</div>
          <div style={{ marginTop: 8 }}>
            <span style={badgeStyle(codeValue(status?.stage16_status, "unknown"))}>
              {codeValue(status?.stage16_status, "unknown")}
            </span>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>
            {status?.ready_count ?? 0}/{status?.required_count ?? 0} deliverables
          </div>
        </div>

        <div style={{ border: `1px solid ${PANEL_BORDER}`, borderRadius: 10, padding: 10, background: "#121212" }}>
          <div style={{ fontSize: 11, color: MUTED }}>Sleep action</div>
          <div style={{ marginTop: 8 }}>
            <span style={badgeStyle(codeValue(presentation?.state, "unknown"))}>
              {presentation?.status_label ?? codeValue(action?.status, "unknown")}
            </span>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>
            selected <code>{codeValue(presentation?.selected_step_id)}</code>
          </div>
        </div>

        <div style={{ border: `1px solid ${PANEL_BORDER}`, borderRadius: 10, padding: 10, background: "#121212" }}>
          <div style={{ fontSize: 11, color: MUTED }}>Evidence</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
            <span style={badgeStyle(`pre_sleep_${yesNo(Boolean(presentation?.pre_sleep_evidence_ready))}`)}>
              pre {yesNo(Boolean(presentation?.pre_sleep_evidence_ready))}
            </span>
            <span style={badgeStyle(`post_resume_${yesNo(Boolean(presentation?.post_resume_evidence_ready))}`)}>
              post {yesNo(Boolean(presentation?.post_resume_evidence_ready))}
            </span>
            <span style={badgeStyle(`continuity_${yesNo(Boolean(presentation?.sleep_continuity_ready))}`)}>
              continuity {yesNo(Boolean(presentation?.sleep_continuity_ready))}
            </span>
          </div>
        </div>
      </div>

      <div style={{ border: `1px solid ${PANEL_BORDER}`, borderRadius: 10, padding: 10, background: "#121212", marginTop: 12 }}>
        <div style={{ fontSize: 12, fontWeight: 600 }}>Selected readback</div>
        <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>
          scope <code>{codeValue(presentation?.required_scope)}</code>
          {" / "}route <code>{codeValue(presentation?.primary_route)}</code>
        </div>
        <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>
          readback <code>{codeValue(presentation?.readback_route)}</code>
          {" / "}runbook <code>{codeValue(presentation?.runbook_route)}</code>
          {" / "}closure <code>{codeValue(presentation?.closure_decision_route)}</code>
        </div>
        {presentation?.primary_command ? (
          <pre
            style={{
              margin: "8px 0 0",
              padding: 10,
              borderRadius: 10,
              border: `1px solid ${PANEL_BORDER}`,
              background: "#101010",
              color: TEXT,
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
              fontSize: 11,
            }}
          >
            {presentation.primary_command}
          </pre>
        ) : null}
        {selectedAction?.expected_output ? (
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>
            expected <code>{selectedAction.expected_output}</code>
          </div>
        ) : null}
        {presentation?.pre_sleep_evidence_path ? (
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>
            pre-sleep evidence <code>{presentation.pre_sleep_evidence_path}</code>
          </div>
        ) : null}
        {presentation?.post_resume_evidence_path ? (
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>
            post-resume evidence <code>{presentation.post_resume_evidence_path}</code>
          </div>
        ) : null}
        {presentation?.evidence_path ? (
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>
            evidence <code>{presentation.evidence_path}</code>
          </div>
        ) : null}
      </div>

      <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Blockers</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
            {blockers.length ? (
              blockers.map((blocker) => (
                <span key={`federation-blocker-${blocker}`} style={badgeStyle("blocked")}>
                  {blocker}
                </span>
              ))
            ) : (
              <span style={badgeStyle("ready")}>none</span>
            )}
          </div>
          {priorLiveReadbackBlockers.length ? (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, color: MUTED }}>Prior live readbacks</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {priorLiveReadbackBlockers.map((blocker) => (
                  <span key={`federation-prior-live-blocker-${blocker}`} style={badgeStyle("blocked")}>
                    {blocker}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Guards</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
            <span style={badgeStyle(presentation?.mutation_available_from_ui ? "blocked" : "ready")}>
              ui mutation {yesNo(Boolean(presentation?.mutation_available_from_ui))}
            </span>
            <span style={badgeStyle(action?.action_projection_only ? "ready" : "blocked")}>
              projection only {yesNo(Boolean(action?.action_projection_only))}
            </span>
            <span style={badgeStyle(action?.runs_shell ? "blocked" : "ready")}>
              shell {yesNo(Boolean(action?.runs_shell))}
            </span>
            <span style={badgeStyle(action?.runs_tools ? "blocked" : "ready")}>
              tools {yesNo(Boolean(action?.runs_tools))}
            </span>
            <span style={badgeStyle(action?.runs_git ? "blocked" : "ready")}>
              git {yesNo(Boolean(action?.runs_git))}
            </span>
            <span style={badgeStyle(action?.launches_browser ? "blocked" : "ready")}>
              browser {yesNo(Boolean(action?.launches_browser))}
            </span>
            <span style={badgeStyle(action?.captures_screen ? "blocked" : "ready")}>
              screen {yesNo(Boolean(action?.captures_screen))}
            </span>
            <span style={badgeStyle(action?.writes_receipts ? "blocked" : "ready")}>
              writes receipts {yesNo(Boolean(action?.writes_receipts))}
            </span>
            <span style={badgeStyle(action?.writes_registry ? "blocked" : "ready")}>
              registry {yesNo(Boolean(action?.writes_registry))}
            </span>
            <span style={badgeStyle(action?.writes_memory ? "blocked" : "ready")}>
              memory {yesNo(Boolean(action?.writes_memory))}
            </span>
            <span style={badgeStyle(action?.grants_mutation_authority ? "blocked" : "ready")}>
              authority {yesNo(Boolean(action?.grants_mutation_authority))}
            </span>
            <span style={badgeStyle(action?.marks_stage16_closed ? "blocked" : "ready")}>
              stage close {yesNo(Boolean(action?.marks_stage16_closed))}
            </span>
            <span style={badgeStyle(presentation?.operator_confirmation_required ? "blocked" : "ready")}>
              confirmation {yesNo(Boolean(presentation?.operator_confirmation_required))}
            </span>
            <span style={badgeStyle(presentation?.operator_action_required ? "blocked" : "ready")}>
              operator action {yesNo(Boolean(presentation?.operator_action_required))}
            </span>
            <span style={badgeStyle(presentation?.writes_evidence_when_run ? "blocked" : "ready")}>
              selected writes evidence {yesNo(Boolean(presentation?.writes_evidence_when_run))}
            </span>
            <span style={badgeStyle(presentation?.writes_receipts_when_run ? "blocked" : "ready")}>
              selected writes receipts {yesNo(Boolean(presentation?.writes_receipts_when_run))}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
