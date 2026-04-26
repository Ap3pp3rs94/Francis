import React, { useCallback, useEffect, useMemo, useState } from "react";

import { artifactOriginTraceId, ArtifactsApiError, ArtifactsClient } from "./index";
import type { ArtifactInspectResponse } from "./index";

type ArtifactInspectionPanelProps = {
  baseUrl: string;
  artifactDir: string;
  title?: string;
  description?: string;
  buttonLabel?: string;
  busyLabel?: string;
  limit?: number;
  maxEntries?: number;
  buttonStyle: React.CSSProperties;
  badgeStyle: (tone: string) => React.CSSProperties;
  borderColor: string;
  mutedColor: string;
  errorColor?: string;
  warningColor?: string;
  background?: string;
};

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function nowUnixSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function formatTime(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    const ms = value > 10_000_000_000 ? value : value * 1000;
    return new Date(ms).toLocaleString();
  }
  if (typeof value !== "string") return "";
  const text = value.trim();
  if (!text) return "";
  const parsedMs = Date.parse(text);
  if (Number.isNaN(parsedMs)) return "";
  return new Date(parsedMs).toLocaleString();
}

export function ArtifactInspectionPanel(props: ArtifactInspectionPanelProps) {
  const {
    artifactDir,
    badgeStyle,
    borderColor,
    buttonStyle,
    mutedColor,
    title = "Artifact Inspection",
    description,
    buttonLabel = "Inspect artifact",
    busyLabel = "Inspecting.",
    limit = 50,
    maxEntries = 8,
    errorColor = "#ffaaaa",
    warningColor = "#ffcf9d",
    background = "#101214",
  } = props;
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const artifactsClient = useMemo(() => new ArtifactsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const [inspection, setInspection] = useState<ArtifactInspectResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);

  useEffect(() => {
    setInspection(null);
    setError(null);
    setLoadedAt(null);
  }, [artifactDir]);

  const inspectArtifact = useCallback(async () => {
    if (!artifactDir) {
      setInspection(null);
      setLoadedAt(null);
      setError("No artifact directory is available for inspection.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const response = await artifactsClient.inspect(artifactDir, { limit, timeoutMs: 10_000 });
      setInspection(response);
      setLoadedAt(nowUnixSeconds());
    } catch (err) {
      const msg =
        err instanceof ArtifactsApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
          : err instanceof Error
            ? err.message
            : "Artifact inspection request failed.";
      setInspection(null);
      setLoadedAt(null);
      setError(msg);
    } finally {
      setBusy(false);
    }
  }, [artifactDir, artifactsClient, limit]);

  const hasRecoveryGuidance =
    inspection &&
    (inspection.recovery_hint || inspection.next_step || inspection.retryable !== undefined);
  const originTraceId = artifactOriginTraceId(inspection?.originating_receipt);

  if (!artifactDir) return null;

  return (
    <div style={{ border: `1px solid ${borderColor}`, borderRadius: 10, padding: 10, background }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>{title}</div>
          <div style={{ fontSize: 11, color: mutedColor, marginTop: 4 }}>
            artifact=<code>{artifactDir}</code>
          </div>
          {description ? <div style={{ fontSize: 11, color: mutedColor, marginTop: 4 }}>{description}</div> : null}
        </div>
        <button
          style={{ ...buttonStyle, padding: "4px 8px", fontSize: 11 }}
          disabled={busy}
          onClick={() => void inspectArtifact()}
        >
          {busy ? busyLabel : buttonLabel}
        </button>
      </div>

      {busy ? (
        <div style={{ fontSize: 11, color: mutedColor, marginTop: 8 }}>Loading artifact metadata.</div>
      ) : error ? (
        <div style={{ fontSize: 11, color: errorColor, marginTop: 8 }}>Artifact inspection unavailable: {error}</div>
      ) : inspection ? (
        <>
          <div style={{ fontSize: 11, color: inspection.ok ? mutedColor : warningColor, marginTop: 8 }}>
            status=<code>{inspection.ok ? "available" : inspection.error || "unavailable"}</code>
            {inspection.exists !== undefined ? (
              <>
                {" / "}exists=<code>{String(inspection.exists)}</code>
              </>
            ) : null}
            {inspection.kind ? (
              <>
                {" / "}kind=<code>{inspection.kind}</code>
              </>
            ) : null}
            {inspection.bytes !== undefined ? (
              <>
                {" / "}bytes=<code>{String(inspection.bytes)}</code>
              </>
            ) : null}
            {inspection.entry_count !== undefined ? (
              <>
                {" / "}entries=<code>{String(inspection.entry_count)}</code>
              </>
            ) : null}
            {inspection.truncated !== undefined ? (
              <>
                {" / "}truncated=<code>{String(inspection.truncated)}</code>
              </>
            ) : null}
          </div>
          {hasRecoveryGuidance ? (
            <div style={{ fontSize: 11, color: inspection.ok ? mutedColor : warningColor, marginTop: 4 }}>
              {inspection.recovery_hint ? <span>{inspection.recovery_hint}</span> : null}
              {inspection.next_step ? (
                <>
                  {inspection.recovery_hint ? " / " : ""}next=<code>{inspection.next_step}</code>
                </>
              ) : null}
              {inspection.retryable !== undefined ? (
                <>
                  {(inspection.recovery_hint || inspection.next_step) ? " / " : ""}
                  retryable=<code>{String(inspection.retryable)}</code>
                </>
              ) : null}
            </div>
          ) : null}
          {inspection.originating_receipt ? (
            <div style={{ fontSize: 11, color: mutedColor, marginTop: 4, overflowWrap: "anywhere" }}>
              origin=<code>{inspection.originating_receipt.source || "receipt"}</code>
              {inspection.originating_receipt.mission_id ? (
                <>
                  {" / "}mission=<code>{inspection.originating_receipt.mission_id}</code>
                </>
              ) : null}
              {inspection.originating_receipt.operation_id ? (
                <>
                  {" / "}operation=<code>{inspection.originating_receipt.operation_id}</code>
                </>
              ) : null}
              {inspection.originating_receipt.approval_id ||
              inspection.originating_receipt.current_task_approval_id ||
              inspection.originating_receipt.handoff_approval_id ? (
                <>
                  {" / "}approval=
                  <code>
                    {inspection.originating_receipt.current_task_approval_id ||
                      inspection.originating_receipt.handoff_approval_id ||
                      inspection.originating_receipt.approval_id}
                  </code>
                </>
              ) : null}
              {inspection.originating_receipt.current_task_approval_status ||
              inspection.originating_receipt.handoff_approval_status ? (
                <>
                  {" / "}approval_status=
                  <code>
                    {inspection.originating_receipt.current_task_approval_status ||
                      inspection.originating_receipt.handoff_approval_status}
                  </code>
                </>
              ) : null}
              {inspection.originating_receipt.current_task_gate || inspection.originating_receipt.handoff_gate ? (
                <>
                  {" / "}gate=
                  <code>{inspection.originating_receipt.current_task_gate || inspection.originating_receipt.handoff_gate}</code>
                </>
              ) : null}
              {inspection.originating_receipt.active_stage || inspection.originating_receipt.handoff_stage ? (
                <>
                  {" / "}stage=
                  <code>
                    {inspection.originating_receipt.active_stage || inspection.originating_receipt.handoff_stage}
                  </code>
                </>
              ) : null}
              {inspection.originating_receipt.handoff_action ? (
                <>
                  {" / "}handoff=<code>{inspection.originating_receipt.handoff_action}</code>
                </>
              ) : null}
              {inspection.originating_receipt.current_task_operation_id ||
              inspection.originating_receipt.handoff_operation_id ? (
                <>
                  {" / "}task=
                  <code>
                    {inspection.originating_receipt.current_task_operation_id ||
                      inspection.originating_receipt.handoff_operation_id}
                  </code>
                </>
              ) : null}
              {inspection.originating_receipt.current_task_operation_name ? (
                <>
                  {" / "}task_name=<code>{inspection.originating_receipt.current_task_operation_name}</code>
                </>
              ) : null}
              {inspection.originating_receipt.current_task_advance_action ? (
                <>
                  {" / "}advance=<code>{inspection.originating_receipt.current_task_advance_action}</code>
                </>
              ) : null}
              {originTraceId ? (
                <>
                  {" / "}trace=<code>{originTraceId}</code>
                </>
              ) : null}
              {inspection.originating_receipt.current_task_run_id || inspection.originating_receipt.handoff_run_id ? (
                <>
                  {" / "}run=
                  <code>
                    {inspection.originating_receipt.current_task_run_id ||
                      inspection.originating_receipt.handoff_run_id}
                  </code>
                </>
              ) : null}
              {inspection.originating_receipt.current_task_artifact_dir ||
              inspection.originating_receipt.handoff_artifact_dir ? (
                <>
                  {" / "}artifact=
                  <code>
                    {inspection.originating_receipt.current_task_artifact_dir ||
                      inspection.originating_receipt.handoff_artifact_dir}
                  </code>
                </>
              ) : null}
              {inspection.originating_receipt.operation_status ? (
                <>
                  {" / "}status=<code>{inspection.originating_receipt.operation_status}</code>
                </>
              ) : null}
              {inspection.originating_receipt.current_task_next_step ||
              inspection.originating_receipt.recovery_next_step ? (
                <>
                  {" / "}recovery=
                  <code>
                    {inspection.originating_receipt.current_task_next_step ||
                      inspection.originating_receipt.recovery_next_step}
                  </code>
                </>
              ) : null}
            </div>
          ) : null}
          {loadedAt !== null ? (
            <div style={{ fontSize: 11, color: mutedColor, marginTop: 4 }}>
              inspected_at=<code>{formatTime(loadedAt)}</code>
              {inspection.relative_path ? (
                <>
                  {" / "}relative_path=<code>{inspection.relative_path}</code>
                </>
              ) : null}
            </div>
          ) : null}
          {inspection.entries.length > 0 ? (
            <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
              {inspection.entries.slice(0, maxEntries).map((entry) => {
                const modifiedAt =
                  entry.modified_ts !== undefined && entry.modified_ts !== null ? formatTime(entry.modified_ts) : "";
                return (
                  <div
                    key={`${entry.relative_path || entry.name}:${entry.kind}`}
                    style={{ border: `1px solid ${borderColor}`, borderRadius: 8, padding: 8, fontSize: 11 }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <code>{entry.name}</code>
                      <span style={badgeStyle(entry.kind)}>{entry.kind}</span>
                    </div>
                    <div style={{ color: mutedColor, marginTop: 4 }}>
                      {entry.relative_path ? (
                        <>
                          path=<code>{entry.relative_path}</code>
                        </>
                      ) : null}
                      {entry.bytes !== undefined ? (
                        <>
                          {entry.relative_path ? " / " : ""}bytes=<code>{String(entry.bytes)}</code>
                        </>
                      ) : null}
                      {modifiedAt ? (
                        <>
                          {(entry.relative_path || entry.bytes !== undefined) ? " / " : ""}modified=<code>{modifiedAt}</code>
                        </>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : loadedAt !== null && inspection.ok ? (
            <div style={{ fontSize: 11, color: mutedColor, marginTop: 8 }}>
              No child artifact entries returned for this handle.
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
