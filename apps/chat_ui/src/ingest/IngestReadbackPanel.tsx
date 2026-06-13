import React, { useCallback, useEffect, useMemo, useState } from "react";

import {
  IngestApiError,
  IngestReadbackClient,
  type IngestReadbackResponse,
  presentIngestReadback,
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
  borderRadius: 8,
  background: PANEL,
};

const buttonStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: 8,
  border: `1px solid ${BUTTON_BORDER}`,
  background: BUTTON_BG,
  color: TEXT,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: 8,
  border: `1px solid ${BUTTON_BORDER}`,
  background: "#0f0f0f",
  color: TEXT,
};

const rowStyle: React.CSSProperties = {
  border: `1px solid ${PANEL_BORDER}`,
  borderRadius: 8,
  padding: 10,
  background: "#121212",
};

function badgeStyle(value: string): React.CSSProperties {
  const lower = value.toLowerCase();
  const blocked = lower.includes("blocked") || lower.includes("denied") || lower.includes("failed") || lower.includes("high");
  const warn = lower.includes("medium") || lower.includes("discovered") || lower.includes("permission");
  return {
    display: "inline-flex",
    alignItems: "center",
    padding: "3px 7px",
    borderRadius: 999,
    border: `1px solid ${blocked ? "#6b2424" : warn ? "#63512a" : "#2f5f46"}`,
    background: blocked ? "#2a0f0f" : warn ? "#261f10" : "#102218",
    color: blocked ? "#ffaaaa" : warn ? "#f2d082" : "#9de2ad",
    fontSize: 11,
    lineHeight: 1.2,
  };
}

function errorText(err: unknown): string {
  if (err instanceof IngestApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Ingest readback request failed.";
}

function permissionText(permissions: {
  read: boolean;
  execute: boolean;
  network: boolean;
  write: boolean;
  destructive: boolean;
}): string {
  const enabled = [
    permissions.read ? "read" : "",
    permissions.execute ? "execute" : "",
    permissions.network ? "network" : "",
    permissions.write ? "write" : "",
    permissions.destructive ? "destructive" : "",
  ].filter(Boolean);
  return enabled.length ? enabled.join(", ") : "none";
}

export function IngestReadbackPanel(props: { baseUrl: string }) {
  const client = useMemo(() => new IngestReadbackClient(props.baseUrl), [props.baseUrl]);
  const [sourceFilter, setSourceFilter] = useState("");
  const [readback, setReadback] = useState<IngestReadbackResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await client.getReadback({ sourceId: sourceFilter.trim(), limit: 100 });
      setReadback(next);
      setLoadedAt(Date.now());
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [client, sourceFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const model = presentIngestReadback(readback);

  return (
    <section style={panelStyle}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Code Ingest</div>
          <div style={{ fontSize: 12, color: MUTED, marginTop: 6 }}>
            sources <code>{model.sourceCount}</code> / repo maps <code>{model.repoMapCount}</code> / candidates{" "}
            <code>{model.candidateCount}</code>
          </div>
        </div>
        <button style={buttonStyle} onClick={() => void refresh()} disabled={loading}>
          {loading ? "Loading" : "Refresh"}
        </button>
      </div>

      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <input
          value={sourceFilter}
          onChange={(event) => setSourceFilter(event.target.value)}
          placeholder="source id filter"
          style={inputStyle}
        />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span style={badgeStyle(model.status)}>{model.status}</span>
          <span style={badgeStyle("preflights")}>preflights {model.labPreflightCount}</span>
          <span style={badgeStyle("approval_consumptions")}>
            approval consumptions {model.approvalConsumptionCount}
          </span>
          <span style={badgeStyle("noop_runner_envelopes")}>
            no-op runner envelopes {model.noopRunnerEnvelopeCount}
          </span>
          <span style={badgeStyle("noop_runner_transcripts")}>
            no-op runner transcripts {model.noopRunnerTranscriptCount}
          </span>
          <span style={badgeStyle("noop_runner_identity_bindings")}>
            no-op runner identities {model.noopRunnerIdentityBindingCount}
          </span>
          <span style={badgeStyle("source_mount_readiness")}>
            source mount readiness {model.sourceMountReadinessCount}
          </span>
          <span style={badgeStyle("source_mount_contracts")}>
            source mount contracts {model.sourceMountContractCount}
          </span>
          <span style={badgeStyle("approval_handoffs")}>
            approval handoffs {model.approvalConsumptionHandoffCount}
          </span>
          <span style={badgeStyle("receipt_sink_reservations")}>
            receipt reservations {model.executionReceiptSinkReservationCount}
          </span>
          <span style={badgeStyle("receipt_write_readiness")}>
            receipt write readiness {model.executionReceiptWriteReadinessCount}
          </span>
          <span style={badgeStyle("receipt_prewrite_binding")}>
            receipt prewrite bindings {model.executionReceiptPrewriteBindingCount}
          </span>
          <span style={badgeStyle("receipt_writer_preflight")}>
            receipt writer preflights {model.executionReceiptWriterPreflightCount}
          </span>
          <span style={badgeStyle("run_boundary_preflights")}>
            run boundaries {model.runBoundaryPreflightCount}
          </span>
          <span style={badgeStyle("sandbox_provider_contracts")}>
            sandbox providers {model.sandboxProviderContractCount}
          </span>
          <span style={badgeStyle("sandbox_provider_bindings")}>
            provider bindings {model.sandboxProviderBindingCount}
          </span>
          <span style={badgeStyle("sandbox_provider_selections")}>
            provider selections {model.sandboxProviderSelectionCount}
          </span>
          <span style={badgeStyle("sandbox_provider_verifiers")}>
            provider verifiers {model.sandboxProviderVerifierCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probes")}>
            provider probes {model.sandboxProviderRuntimeProbeCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_harnesses")}>
            probe harnesses {model.sandboxProviderRuntimeProbeHarnessCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_runner_readiness")}>
            probe runners {model.sandboxProviderRuntimeProbeRunnerReadinessCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_runner_bindings")}>
            probe runner bindings {model.sandboxProviderRuntimeProbeRunnerBindingCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_runner_enforcements")}>
            probe runner enforcement {model.sandboxProviderRuntimeProbeRunnerEnforcementCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_execution_boundaries")}>
            probe boundaries {model.sandboxProviderRuntimeProbeExecutionBoundaryCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_refusals")}>
            probe refusals {model.sandboxProviderRuntimeProbeRefusalCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_approval_requests")}>
            probe approvals {model.sandboxProviderRuntimeProbeApprovalRequestCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_approval_consumptions")}>
            probe approval consumption {model.sandboxProviderRuntimeProbeApprovalConsumptionCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_invocation_boundaries")}>
            probe invocation boundaries {model.sandboxProviderRuntimeProbeInvocationBoundaryCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_runner_pre_execution_boundaries")}>
            probe runner pre-exec {model.sandboxProviderRuntimeProbeRunnerPreExecutionBoundaryCount}
          </span>
          <span style={badgeStyle("sandbox_provider_runtime_probe_runner_control_bindings")}>
            probe control bindings {model.sandboxProviderRuntimeProbeRunnerControlBindingCount}
          </span>
          <span style={badgeStyle("sandboxed_rebuild_run_test_boundaries")}>
            sandbox run boundaries {model.sandboxedRebuildRunTestBoundaryCount}
          </span>
          <span style={badgeStyle("sandboxed_rebuild_run_test_approval_requests")}>
            sandbox approvals {model.sandboxedRebuildRunTestApprovalRequestCount}
          </span>
          <span style={badgeStyle("sandboxed_rebuild_run_test_approval_consumptions")}>
            sandbox approval use {model.sandboxedRebuildRunTestApprovalConsumptionCount}
          </span>
          <span style={badgeStyle("sandboxed_rebuild_run_test_runner_bindings")}>
            sandbox runner bindings {model.sandboxedRebuildRunTestRunnerBindingCount}
          </span>
          <span style={badgeStyle("sandboxed_rebuild_run_test_sandbox_policies")}>
            sandbox policies {model.sandboxedRebuildRunTestSandboxPolicyCount}
          </span>
          <span style={badgeStyle("execution_receipts")}>execution receipts {model.executionReceiptCount}</span>
          <span style={badgeStyle("command_allowlists")}>
            command allowlists {model.runnerCommandAllowlistCount}
          </span>
          <span style={badgeStyle("command_allowlist_declarations")}>
            command declarations {model.runnerCommandAllowlistDeclarationCount}
          </span>
          <span style={badgeStyle("command_allowlist_enforcement")}>
            command enforcement {model.runnerCommandAllowlistEnforcementCount}
          </span>
          <span style={badgeStyle("sandbox_readiness")}>
            sandbox readiness {model.runnerSandboxReadinessCount}
          </span>
          <span style={badgeStyle("runner_contracts")}>runner contracts {model.runnerContractCount}</span>
          <span style={badgeStyle("runner_readiness")}>runner readiness {model.runnerReadinessCount}</span>
          <span style={badgeStyle("runner_binding")}>runner bindings {model.runnerBindingCount}</span>
          <span style={badgeStyle("runner_enforcement")}>runner enforcement {model.runnerEnforcementCount}</span>
          <span style={badgeStyle(model.sensitiveFileCount > 0 ? "medium" : "low")}>
            sensitive markers {model.sensitiveFileCount}
          </span>
        </div>
      </div>

      {error ? <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 10 }}>{error}</div> : null}
      {readback?.governance?.reason ? (
        <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 10 }}>
          governance: <code>{readback.governance.reason}</code>
        </div>
      ) : null}
      {loadedAt ? <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>Loaded {new Date(loadedAt).toLocaleTimeString()}</div> : null}

      <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
        <div style={rowStyle}>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Execution Guards</div>
          <div style={{ display: "grid", gap: 4, marginTop: 8 }}>
            {model.guardLines.map((item) => (
              <div key={`ingest-guard-${item}`} style={{ fontSize: 12, color: TEXT }}>
                {item}
              </div>
            ))}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Sources</div>
          <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
            {model.sources.length === 0 ? (
              <div style={{ fontSize: 12, color: MUTED }}>No source records returned.</div>
            ) : (
              model.sources.map((source) => (
                <div key={`ingest-source-${source.id}`} style={rowStyle}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <code style={{ fontSize: 12 }}>{source.id}</code>
                    <span style={badgeStyle(source.type)}>{source.type}</span>
                    <span style={badgeStyle(source.status)}>{source.status}</span>
                  </div>
                  <div style={{ fontSize: 11, color: MUTED, marginTop: 6, wordBreak: "break-word" }}>
                    {source.canonical_path || source.original_path || "path unavailable"}
                  </div>
                  <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>
                    permissions: <code>{permissionText(source.permissions)}</code>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Capability Candidates</div>
          <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
            {model.candidates.length === 0 ? (
              <div style={{ fontSize: 12, color: MUTED }}>No capability candidates returned.</div>
            ) : (
              model.candidates.map((candidate) => (
                <div key={`ingest-candidate-${candidate.id}`} style={rowStyle}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{candidate.name}</span>
                    <span style={badgeStyle(candidate.status)}>{candidate.status}</span>
                    <span style={badgeStyle(candidate.risk_level)}>{candidate.risk_level}</span>
                  </div>
                  <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>{candidate.description || candidate.id}</div>
                  <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>
                    permissions: <code>{permissionText(candidate.permissions_required)}</code>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Risk Signals</div>
          <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
            {model.riskSignals.length === 0 ? (
              <div style={{ fontSize: 12, color: MUTED }}>No risk signals returned.</div>
            ) : (
              model.riskSignals.map((signal, index) => (
                <div key={`ingest-risk-${signal.id}-${index}`} style={rowStyle}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <code style={{ fontSize: 12 }}>{signal.id}</code>
                    <span style={badgeStyle(signal.severity)}>{signal.severity}</span>
                  </div>
                  <div style={{ fontSize: 11, color: MUTED, marginTop: 6, wordBreak: "break-word" }}>
                    {signal.path || signal.detail || "no path detail"}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {model.blockers.length > 0 ? (
          <div>
            <div style={{ fontSize: 12, fontWeight: 600 }}>Lab Blockers</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
              {model.blockers.map((item) => (
                <span key={`ingest-blocker-${item}`} style={badgeStyle("blocked")}>
                  {item}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {model.latestArtifactPaths.length > 0 ? (
          <div>
            <div style={{ fontSize: 12, fontWeight: 600 }}>Readback Artifacts</div>
            <div style={{ display: "grid", gap: 4, marginTop: 8 }}>
              {model.latestArtifactPaths.map((path) => (
                <code key={`ingest-artifact-${path}`} style={{ fontSize: 11, color: MUTED, wordBreak: "break-word" }}>
                  {path}
                </code>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
