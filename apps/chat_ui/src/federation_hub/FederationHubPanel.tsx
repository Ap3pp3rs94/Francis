import React, { useCallback, useEffect, useMemo, useState } from "react";

import {
  DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR,
  FederationApiError,
  FederationClient,
  federationSleepContinuityVisibleOperatorCommands,
  federationSleepResumeConfirmationActorReadinessVisibleCommands,
  federationSleepResumeConfirmationVisibleCommands,
  federationSleepResumeReceiptBackedSequenceVisibleCommands,
  federationSleepResumeReceiptRecordReadiness,
  isFederationSleepResumeConfirmationActorReadinessCurrent,
  presentFederationSleepContinuityAction,
  shouldAutoCheckFederationSleepResumeConfirmationActorReadiness,
  type FederationSleepContinuityActionReadback,
  type FederationSleepContinuityPresentation,
  type FederationSleepContinuityRunbook,
  type FederationSleepResumeConfirmationActorReadiness,
  type FederationSleepResumeOperatorChecklist,
  type FederationSleepResumeReceiptBackedSequenceReadiness,
  type FederationSleepResumeConfirmationRecordResponse,
  type FederationSleepResumeConfirmations,
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

function recordBoolean(value: Record<string, unknown> | undefined, key: string): boolean {
  return Boolean(value?.[key]);
}

function recordString(value: Record<string, unknown> | undefined, key: string): string | undefined {
  const raw = value?.[key];
  return typeof raw === "string" ? raw : undefined;
}

export function FederationHubPanel(props: { baseUrl: string }) {
  const client = useMemo(() => new FederationClient(props.baseUrl), [props.baseUrl]);
  const [status, setStatus] = useState<FederationStage16Status | null>(null);
  const [runbook, setRunbook] = useState<FederationSleepContinuityRunbook | null>(null);
  const [action, setAction] = useState<FederationSleepContinuityActionReadback | null>(null);
  const [confirmations, setConfirmations] = useState<FederationSleepResumeConfirmations | null>(null);
  const [operatorChecklist, setOperatorChecklist] = useState<FederationSleepResumeOperatorChecklist | null>(null);
  const [sequenceReadiness, setSequenceReadiness] =
    useState<FederationSleepResumeReceiptBackedSequenceReadiness | null>(null);
  const [actorReadiness, setActorReadiness] = useState<FederationSleepResumeConfirmationActorReadiness | null>(null);
  const [actorPreflightActor, setActorPreflightActor] = useState(DEFAULT_FEDERATION_SLEEP_RESUME_CONFIRMATION_ACTOR);
  const [actorReadinessAutoCheckedActor, setActorReadinessAutoCheckedActor] = useState("");
  const [actorReadinessLoading, setActorReadinessLoading] = useState(false);
  const [sleepResumeAcknowledged, setSleepResumeAcknowledged] = useState(false);
  const [receiptMutationLoading, setReceiptMutationLoading] = useState(false);
  const [receiptMutationResult, setReceiptMutationResult] =
    useState<FederationSleepResumeConfirmationRecordResponse | null>(null);
  const [presentation, setPresentation] = useState<FederationSleepContinuityPresentation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        nextStatus,
        nextRunbook,
        nextAction,
        nextConfirmations,
        nextOperatorChecklist,
        nextSequenceReadiness,
      ] = await Promise.all([
        client.getStatus({ actor: actorPreflightActor, timeoutMs: 10_000 }),
        client.getSleepContinuityRunbook({ timeoutMs: 10_000 }),
        client.getSleepContinuityAction({ actor: actorPreflightActor, timeoutMs: 10_000 }),
        client.getSleepResumeConfirmations({
          limit: 5,
          actor: actorPreflightActor,
          timeoutMs: 10_000,
        }),
        client.getSleepResumeConfirmationOperatorChecklist({
          actor: actorPreflightActor,
          timeoutMs: 10_000,
        }),
        client.getSleepResumeReceiptBackedSequenceReadiness({
          actor: actorPreflightActor,
          timeoutMs: 10_000,
        }),
      ]);
      setStatus(nextStatus);
      setRunbook(nextRunbook);
      setAction(nextAction);
      setConfirmations(nextConfirmations);
      setOperatorChecklist(nextOperatorChecklist);
      setSequenceReadiness(nextSequenceReadiness);
      setPresentation(presentFederationSleepContinuityAction(nextAction));
      setLoadedAt(Date.now());
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [actorPreflightActor, client]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const checkActorReadiness = useCallback(async () => {
    setActorReadinessLoading(true);
    setError(null);
    try {
      const nextReadiness = await client.getSleepResumeConfirmationActorReadiness({
        actor: actorPreflightActor,
        timeoutMs: 10_000,
      });
      setActorReadiness(nextReadiness);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setActorReadinessLoading(false);
    }
  }, [actorPreflightActor, client]);

  useEffect(() => {
    const trimmedActor = actorPreflightActor.trim();
    if (actorReadinessLoading || actorReadinessAutoCheckedActor === trimmedActor) return;
    if (
      !shouldAutoCheckFederationSleepResumeConfirmationActorReadiness({
        confirmations,
        actor: actorPreflightActor,
        readiness: actorReadiness,
      })
    ) {
      return;
    }
    setActorReadinessAutoCheckedActor(trimmedActor);
    void checkActorReadiness();
  }, [
    actorPreflightActor,
    actorReadiness,
    actorReadinessAutoCheckedActor,
    actorReadinessLoading,
    checkActorReadiness,
    confirmations,
  ]);

  const blockers = presentation?.blockers.length ? presentation.blockers : status?.completion_review_blockers ?? [];
  const priorLiveReadbackBlockers = presentation?.prior_live_readback_blockers ?? [];
  const governance = action?.governance;
  const latestPreSleepEvidence = status?.latest_pre_sleep_evidence;
  const latestPostResumeEvidence = status?.latest_post_resume_evidence;
  const postResumeEvidenceConflict =
    Boolean(presentation?.post_resume_evidence_conflict) ||
    recordBoolean(latestPostResumeEvidence, "conflict_detected");
  const selectedActionReadiness = presentation?.selected_action_readiness;
  const operatorTerminalInvocation = presentation?.operator_terminal_invocation;
  const operatorSleepResumeGate = presentation?.operator_sleep_resume_gate;
  const operatorConfirmationHandoff = presentation?.operator_confirmation_handoff;
  const afterManualExecutionReadback = presentation?.after_manual_execution_readback;
  const runbookSelectedActionSummary = runbook?.selected_action_summary;
  const confirmationReceiptBlockers = confirmations?.receipt_backed_sequence_blockers ?? [];
  const sequenceReadinessBlockers = sequenceReadiness?.receipt_backed_sequence_blockers ?? [];
  const confirmationReceiptOperatorSteps = confirmations?.confirmation_receipt_operator_steps ?? [];
  const visibleConfirmationCommands = federationSleepResumeConfirmationVisibleCommands(confirmations);
  const visibleSequenceReadinessCommands =
    federationSleepResumeReceiptBackedSequenceVisibleCommands(sequenceReadiness);
  const visibleActorReadiness = isFederationSleepResumeConfirmationActorReadinessCurrent(
    actorReadiness,
    actorPreflightActor,
  )
    ? actorReadiness
    : null;
  const visibleActorReadinessCommands =
    federationSleepResumeConfirmationActorReadinessVisibleCommands(visibleActorReadiness);
  const visibleOperatorCommands = federationSleepContinuityVisibleOperatorCommands(presentation);
  const visiblePrimaryCommand = visibleOperatorCommands.primary_command;
  const visibleOperatorTerminalCommand = visibleOperatorCommands.operator_terminal_copyable_command;
  const visiblePostResumeCaptureCommand = visibleOperatorCommands.post_resume_capture_copyable_command;
  const visiblePostResumeSequenceCommand = visibleOperatorCommands.post_resume_sequence_copyable_command;
  const visiblePostResumeReceiptBackedSequenceCommand =
    visibleOperatorCommands.post_resume_receipt_backed_sequence_copyable_command;
  const visiblePreSleepRecaptureCommand = visibleOperatorCommands.pre_sleep_recapture_copyable_command;
  const visibleConfirmationReceiptBackedSequenceCommand =
    visibleSequenceReadinessCommands.receipt_backed_sequence_copyable_command;
  const receiptRecordReadiness = federationSleepResumeReceiptRecordReadiness({
    status,
    confirmations,
    operatorAcknowledged: sleepResumeAcknowledged,
  });
  const currentPreSleepEvidencePath = receiptRecordReadiness.current_pre_sleep_evidence_path ?? "";
  const receiptRecordDisabled = receiptMutationLoading || receiptRecordReadiness.disabled;

  const recordSleepResumeConfirmation = useCallback(async () => {
    if (receiptRecordDisabled) return;
    setReceiptMutationLoading(true);
    setError(null);
    try {
      const result = await client.recordSleepResumeConfirmation({
        actor: actorPreflightActor,
        reason: "operator_confirmed_physical_sleep_resume_from_federation_hub",
        preSleepEvidencePath: currentPreSleepEvidencePath,
        operatorConfirmedSleepResume: true,
        timeoutMs: 10_000,
      });
      setReceiptMutationResult(result);
      setSleepResumeAcknowledged(false);
      await refresh();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setReceiptMutationLoading(false);
    }
  }, [actorPreflightActor, client, currentPreSleepEvidencePath, receiptRecordDisabled, refresh]);

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
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            title <code>{codeValue(presentation?.selected_step_title)}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            status <code>{codeValue(status?.sleep_continuity_status)}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            action <code>{codeValue(status?.sleep_continuity_selected_action_id)}</code>
            {" / "}current ready <code>{yesNo(Boolean(status?.sleep_continuity_action_current_ready_to_run))}</code>
            {" / "}confirmation pending{" "}
            <code>{yesNo(Boolean(status?.sleep_continuity_operator_confirmation_pending))}</code>
            {" / "}command visible <code>{yesNo(Boolean(visiblePrimaryCommand))}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            next <code>{codeValue(status?.sleep_continuity_next_step)}</code>
          </div>
          {runbookSelectedActionSummary ? (
            <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
              runbook action <code>{codeValue(runbookSelectedActionSummary.selected_action_id)}</code>
              {" / "}ready <code>{yesNo(runbookSelectedActionSummary.current_ready_to_run)}</code>
              {" / "}confirmation pending <code>{yesNo(runbookSelectedActionSummary.operator_confirmation_pending)}</code>
            </div>
          ) : null}
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
            <span style={badgeStyle(`post_resume_conflict_${yesNo(postResumeEvidenceConflict)}`)}>
              conflict {yesNo(postResumeEvidenceConflict)}
            </span>
            <span style={badgeStyle(`continuity_${yesNo(Boolean(presentation?.sleep_continuity_ready))}`)}>
              continuity {yesNo(Boolean(presentation?.sleep_continuity_ready))}
            </span>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            pre status <code>{codeValue(recordString(latestPreSleepEvidence, "status"))}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            pre id <code>{codeValue(recordString(latestPreSleepEvidence, "continuity_record_id"))}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            pre trace <code>{codeValue(recordString(latestPreSleepEvidence, "trace_id"))}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            post status <code>{codeValue(recordString(latestPostResumeEvidence, "status"))}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
            post linked <code>{yesNo(recordBoolean(latestPostResumeEvidence, "linked_to_latest_pre_sleep"))}</code>
          </div>
          {postResumeEvidenceConflict ? (
            <>
              <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
                expected pre <code>{codeValue(recordString(latestPostResumeEvidence, "expected_pre_sleep_evidence_path"))}</code>
              </div>
              <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
                candidate pre <code>{codeValue(recordString(latestPostResumeEvidence, "candidate_pre_sleep_evidence_path"))}</code>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {confirmations ? (
        <div style={{ border: `1px solid ${PANEL_BORDER}`, borderRadius: 10, padding: 10, background: "#121212", marginTop: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Sleep confirmation receipts</div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
            status <code>{codeValue(confirmations.status)}</code>
            {" / "}readback <code>{yesNo(confirmations.receipt_readback_ready)}</code>
            {" / "}current pre <code>{yesNo(confirmations.current_pre_sleep_evidence_present)}</code>
            {" / "}sequence ready <code>{yesNo(confirmations.receipt_backed_sequence_ready)}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
            latest receipt <code>{codeValue(confirmations.latest_receipt_id)}</code>
            {" / "}decision <code>{codeValue(confirmations.latest_decision)}</code>
            {" / "}matches current pre <code>{yesNo(confirmations.latest_receipt_matches_current_pre_sleep)}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
            remedy command <code>{yesNo(confirmations.confirmation_receipt_command_ready)}</code>
            {" / "}records receipt <code>{yesNo(confirmations.confirmation_receipt_command_records_receipt)}</code>
            {" / "}writes evidence <code>{yesNo(confirmations.confirmation_receipt_command_writes_evidence)}</code>
            {" / "}marks closed <code>{yesNo(confirmations.confirmation_receipt_command_marks_stage16_closed)}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
            status actor <code>{codeValue(status?.sleep_continuity_confirmation_receipt_actor)}</code>
            {" / "}accepted{" "}
            <code>{yesNo(Boolean(status?.sleep_continuity_confirmation_receipt_requested_actor_ready))}</code>
            {" / "}bound <code>{yesNo(Boolean(status?.sleep_continuity_confirmation_receipt_actor_bound))}</code>
            {" / "}substitution{" "}
            <code>{yesNo(Boolean(status?.sleep_continuity_confirmation_receipt_command_requires_actor_substitution))}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
            status receipt <code>{yesNo(Boolean(status?.sleep_continuity_confirmation_receipt_readback_ready))}</code>
            {" / "}status sequence{" "}
            <code>{yesNo(Boolean(status?.sleep_continuity_receipt_backed_sequence_ready))}</code>
            {" / "}matches current pre{" "}
            <code>{yesNo(Boolean(status?.sleep_continuity_confirmation_receipt_latest_matches_current_pre_sleep))}</code>
            {" / "}latest <code>{codeValue(status?.sleep_continuity_confirmation_receipt_latest_receipt_id)}</code>
          </div>
          {sequenceReadiness ? (
            <>
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                sequence readback <code>{codeValue(sequenceReadiness.status)}</code>
                {" / "}ready <code>{yesNo(sequenceReadiness.receipt_backed_sequence_ready)}</code>
                {" / "}visible <code>{yesNo(sequenceReadiness.receipt_backed_sequence_command_visible)}</code>
                {" / "}writes evidence <code>{yesNo(sequenceReadiness.writes_evidence_when_run)}</code>
                {" / "}writes receipts <code>{yesNo(sequenceReadiness.writes_receipts_when_run)}</code>
                {" / "}marks closed <code>{yesNo(sequenceReadiness.marks_stage16_closed_when_run)}</code>
              </div>
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                sequence pre age <code>{sequenceReadiness.current_pre_sleep_age_seconds}s</code>
                {" / "}freshness <code>{codeValue(sequenceReadiness.current_pre_sleep_freshness_state)}</code>
                {" / "}guidance <code>{codeValue(sequenceReadiness.current_pre_sleep_age_guidance)}</code>
                {" / "}recapture <code>{yesNo(sequenceReadiness.current_pre_sleep_recapture_recommended)}</code>
              </div>
            </>
          ) : null}
          <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
            requested actor <code>{codeValue(confirmations.confirmation_receipt_requested_actor)}</code>
            {" / "}accepted{" "}
            <code>{yesNo(confirmations.confirmation_receipt_requested_actor_ready)}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
            actor bound <code>{yesNo(confirmations.confirmation_receipt_actor_bound)}</code>
            {" / "}actor <code>{codeValue(confirmations.confirmation_receipt_actor)}</code>
            {" / "}placeholder <code>{codeValue(confirmations.confirmation_receipt_actor_placeholder)}</code>
          </div>
          <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
            actor substitution <code>{yesNo(confirmations.confirmation_receipt_command_requires_actor_substitution)}</code>
            {" / "}actor scope <code>{codeValue(confirmations.confirmation_receipt_command_actor_scope)}</code>
            {" / "}actor preflight <code>{codeValue(confirmations.confirmation_receipt_actor_readiness_route)}</code>
            {" / "}next readback <code>{codeValue(confirmations.confirmation_receipt_command_next_readback_route)}</code>
            {" / "}receipt field{" "}
            <code>{codeValue(confirmations.confirmation_receipt_command_receipt_id_readback_field)}</code>
          </div>
          {confirmationReceiptOperatorSteps.length ? (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
              {confirmationReceiptOperatorSteps.map((step) => (
                <span key={`federation-confirmation-operator-step-${step.order}-${step.id}`} style={badgeStyle(step.status ?? "")}>
                  {step.order}. {codeValue(step.id)}: {codeValue(step.status)}
                </span>
              ))}
            </div>
          ) : null}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
            <input
              value={actorPreflightActor}
              onChange={(event) => {
                setActorPreflightActor(event.target.value);
                setActorReadiness(null);
                setActorReadinessAutoCheckedActor("");
              }}
              placeholder="actor id"
              style={{
                minWidth: 220,
                flex: "1 1 220px",
                borderRadius: 10,
                border: `1px solid ${PANEL_BORDER}`,
                background: "#101010",
                color: TEXT,
                padding: "8px 10px",
                fontSize: 12,
              }}
            />
            <button style={buttonStyle} onClick={() => void checkActorReadiness()} disabled={actorReadinessLoading}>
              {actorReadinessLoading ? "Checking" : "Check Actor"}
            </button>
          </div>
          {visibleActorReadiness ? (
            <>
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                actor status <code>{codeValue(visibleActorReadiness.status)}</code>
                {" / "}ready <code>{yesNo(visibleActorReadiness.confirmation_receipt_actor_ready)}</code>
                {" / "}safe command <code>{yesNo(visibleActorReadiness.safe_to_use_in_confirmation_command)}</code>
                {" / "}writes receipt <code>{yesNo(visibleActorReadiness.writes_receipt)}</code>
                {" / "}marks closed <code>{yesNo(visibleActorReadiness.marks_stage16_closed)}</code>
              </div>
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                next <code>{codeValue(visibleActorReadiness.next_step)}</code>
                {" / "}bound actor <code>{codeValue(visibleActorReadiness.confirmation_receipt_actor)}</code>
                {" / "}substitution{" "}
                <code>{yesNo(visibleActorReadiness.confirmation_receipt_command_requires_actor_substitution)}</code>
              </div>
              {visibleActorReadiness.scope_remediation_required ? (
                <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                  scope remediation <code>{yesNo(visibleActorReadiness.scope_remediation_required)}</code>
                  {" / "}env <code>{codeValue(visibleActorReadiness.scope_remediation_env_var)}</code>
                  {" / "}scope <code>{codeValue(visibleActorReadiness.scope_remediation_required_scope)}</code>
                  {" / "}writes receipt <code>{yesNo(visibleActorReadiness.scope_remediation_writes_receipts)}</code>
                  {" / "}marks closed <code>{yesNo(visibleActorReadiness.scope_remediation_marks_stage16_closed)}</code>
                </div>
              ) : null}
              {visibleActorReadinessCommands.scope_remediation_copyable_command ? (
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
                  {visibleActorReadinessCommands.scope_remediation_copyable_command}
                </pre>
              ) : null}
              {visibleActorReadinessCommands.confirmation_receipt_copyable_command ? (
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
                  {visibleActorReadinessCommands.confirmation_receipt_copyable_command}
                </pre>
              ) : null}
            </>
          ) : null}
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: MUTED, marginBottom: 6, overflowWrap: "anywhere" }}>
              record ready <code>{yesNo(receiptRecordReadiness.ready)}</code>
              {" / "}actor <code>{codeValue(receiptRecordReadiness.actor)}</code>
              {" / "}pre path <code>{codeValue(receiptRecordReadiness.current_pre_sleep_evidence_path)}</code>
              {" / "}writes receipt <code>{yesNo(receiptRecordReadiness.records_receipt)}</code>
              {" / "}writes evidence <code>{yesNo(receiptRecordReadiness.writes_evidence)}</code>
              {" / "}marks closed <code>{yesNo(receiptRecordReadiness.marks_stage16_closed)}</code>
            </div>
            {operatorChecklist ? (
              <>
                <div style={{ fontSize: 11, color: MUTED, marginBottom: 6, overflowWrap: "anywhere" }}>
                  checklist <code>{codeValue(operatorChecklist.status)}</code>
                  {" / "}preconditions <code>{yesNo(operatorChecklist.preconditions_ready)}</code>
                  {" / "}after physical confirmation{" "}
                  <code>{yesNo(operatorChecklist.ready_to_record_after_operator_confirmation)}</code>
                  {" / "}physical recorded <code>{yesNo(operatorChecklist.operator_physical_confirmation_recorded)}</code>
                  {" / "}receipt <code>{codeValue(operatorChecklist.latest_confirmation_receipt_id)}</code>
                </div>
                <div style={{ fontSize: 11, color: MUTED, marginBottom: 6, overflowWrap: "anywhere" }}>
                  checklist pre age <code>{operatorChecklist.current_pre_sleep_age_seconds}s</code>
                  {" / "}freshness <code>{codeValue(operatorChecklist.current_pre_sleep_freshness_state)}</code>
                  {" / "}guidance <code>{codeValue(operatorChecklist.current_pre_sleep_age_guidance)}</code>
                  {" / "}recapture <code>{yesNo(operatorChecklist.current_pre_sleep_recapture_recommended)}</code>
                </div>
                {operatorChecklist.checklist.length ? (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
                    {operatorChecklist.checklist.map((item) => (
                      <span
                        key={`federation-sleep-operator-checklist-${item.id}`}
                        style={badgeStyle(item.passed ? "ready" : "blocked")}
                      >
                        {codeValue(item.id)} {yesNo(item.passed)}
                      </span>
                    ))}
                  </div>
                ) : null}
                {operatorChecklist.operator_actions_remaining.length ? (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
                    {operatorChecklist.operator_actions_remaining.map((item) => (
                      <span key={`federation-sleep-operator-action-${item}`} style={badgeStyle("blocked")}>
                        {item}
                      </span>
                    ))}
                  </div>
                ) : null}
              </>
            ) : null}
            <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 11, color: MUTED }}>
              <input
                type="checkbox"
                checked={sleepResumeAcknowledged}
                onChange={(event) => setSleepResumeAcknowledged(event.target.checked)}
                disabled={receiptMutationLoading || !receiptRecordReadiness.command_ready}
              />
              <span>
                I confirm this workstation slept or suspended after the current pre-sleep marker and resumed before
                continuing.
              </span>
            </label>
            <button
              style={{ ...buttonStyle, marginTop: 8 }}
              onClick={() => void recordSleepResumeConfirmation()}
              disabled={receiptRecordDisabled}
            >
              {receiptMutationLoading ? "Recording" : "Record Confirmation Receipt"}
            </button>
            {receiptMutationResult ? (
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                recorded receipt <code>{codeValue(receiptMutationResult.receipt_id)}</code>
                {" / "}status <code>{codeValue(receiptMutationResult.status)}</code>
                {" / "}writes evidence <code>{yesNo(receiptMutationResult.writes_evidence)}</code>
                {" / "}marks closed <code>{yesNo(receiptMutationResult.marks_stage16_closed)}</code>
              </div>
            ) : null}
            {receiptRecordReadiness.blockers.length ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {receiptRecordReadiness.blockers.map((blocker) => (
                  <span key={`federation-receipt-record-blocker-${blocker}`} style={badgeStyle("blocked")}>
                    {blocker}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
          {confirmations.current_pre_sleep_evidence_path ? (
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
              current pre path <code>{confirmations.current_pre_sleep_evidence_path}</code>
            </div>
          ) : null}
          {confirmationReceiptBlockers.length ? (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
              {confirmationReceiptBlockers.map((blocker) => (
                <span key={`federation-confirmation-readback-blocker-${blocker}`} style={badgeStyle("blocked")}>
                  {blocker}
                </span>
              ))}
            </div>
          ) : null}
          {status?.sleep_continuity_receipt_backed_sequence_blockers.length ? (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
              {status.sleep_continuity_receipt_backed_sequence_blockers.map((blocker) => (
                <span key={`federation-status-receipt-sequence-blocker-${blocker}`} style={badgeStyle("blocked")}>
                  status {blocker}
                </span>
              ))}
            </div>
          ) : null}
          {sequenceReadinessBlockers.length ? (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
              {sequenceReadinessBlockers.map((blocker) => (
                <span key={`federation-sequence-readiness-blocker-${blocker}`} style={badgeStyle("blocked")}>
                  sequence {blocker}
                </span>
              ))}
            </div>
          ) : null}
          {visibleConfirmationCommands.confirmation_receipt_copyable_command ? (
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
              {visibleConfirmationCommands.confirmation_receipt_copyable_command}
            </pre>
          ) : null}
          {visibleConfirmationReceiptBackedSequenceCommand ? (
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
              {visibleConfirmationReceiptBackedSequenceCommand}
            </pre>
          ) : null}
        </div>
      ) : null}

      <div style={{ border: `1px solid ${PANEL_BORDER}`, borderRadius: 10, padding: 10, background: "#121212", marginTop: 12 }}>
        <div style={{ fontSize: 12, fontWeight: 600 }}>Selected readback</div>
        <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>
          scope <code>{codeValue(presentation?.required_scope)}</code>
          {" / "}route <code>{codeValue(presentation?.primary_route)}</code>
          {" / "}current ready <code>{yesNo(Boolean(presentation?.current_ready_to_run))}</code>
          {" / "}confirmation pending <code>{yesNo(Boolean(presentation?.operator_confirmation_pending))}</code>
        </div>
        <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>
          readback <code>{codeValue(presentation?.readback_route)}</code>
          {" / "}runbook <code>{codeValue(presentation?.runbook_route)}</code>
          {" / "}closure <code>{codeValue(presentation?.closure_decision_route)}</code>
        </div>
        <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
          pre recapture <code>{yesNo(Boolean(presentation?.pre_sleep_recapture_recommended))}</code>
          {" / "}visible <code>{yesNo(Boolean(visiblePreSleepRecaptureCommand))}</code>
          {" / "}writes evidence <code>{yesNo(Boolean(action?.pre_sleep_recapture_writes_evidence_when_run))}</code>
          {" / "}marks closed{" "}
          <code>{yesNo(Boolean(action?.pre_sleep_recapture_marks_stage16_closed_when_run))}</code>
        </div>
        {visiblePreSleepRecaptureCommand ? (
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
            {visiblePreSleepRecaptureCommand}
          </pre>
        ) : null}
        {visiblePrimaryCommand ? (
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
            {visiblePrimaryCommand}
          </pre>
        ) : null}
        {operatorTerminalInvocation ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: MUTED }}>
              terminal invocation <code>{codeValue(operatorTerminalInvocation.status)}</code>
              {" / "}shell <code>{codeValue(operatorTerminalInvocation.shell)}</code>
              {" / "}projected <code>{yesNo(operatorTerminalInvocation.operator_terminal_command_ready)}</code>
              {" / "}visible <code>{yesNo(Boolean(visibleOperatorTerminalCommand))}</code>
              {" / "}confirmation pending <code>{yesNo(operatorTerminalInvocation.operator_confirmation_pending)}</code>
            </div>
            {operatorTerminalInvocation.working_directory ? (
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                cwd <code>{operatorTerminalInvocation.working_directory}</code>
              </div>
            ) : null}
            {visibleOperatorTerminalCommand ? (
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
                {visibleOperatorTerminalCommand}
              </pre>
            ) : null}
            {operatorTerminalInvocation.preconditions.length ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {operatorTerminalInvocation.preconditions.map((precondition) => (
                  <span key={`federation-terminal-precondition-${precondition}`} style={badgeStyle("blocked")}>
                    {precondition}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {operatorConfirmationHandoff ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: MUTED }}>
              confirmation handoff <code>{codeValue(operatorConfirmationHandoff.status)}</code>
              {" / "}pending <code>{yesNo(operatorConfirmationHandoff.operator_confirmation_pending)}</code>
              {" / "}after confirmation{" "}
              <code>{yesNo(operatorConfirmationHandoff.post_resume_capture_command_ready_after_confirmation)}</code>
              {" / "}no shell{" "}
              <code>{yesNo(recordBoolean(operatorConfirmationHandoff.proof_boundary, "does_not_run_shell"))}</code>
            </div>
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>
              post-confirmation sequence{" "}
              <code>{yesNo(operatorConfirmationHandoff.post_resume_sequence_available_after_confirmation)}</code>
              {" / "}writes evidence{" "}
              <code>{yesNo(operatorConfirmationHandoff.post_resume_sequence_writes_evidence_when_run)}</code>
              {" / "}writes receipts{" "}
              <code>{yesNo(operatorConfirmationHandoff.post_resume_sequence_writes_receipts_when_run)}</code>
            </div>
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
              receipt-backed projected{" "}
              <code>{yesNo(Boolean(operatorConfirmationHandoff.post_resume_receipt_backed_sequence_command))}</code>
              {" / "}visible{" "}
              <code>{yesNo(Boolean(visiblePostResumeReceiptBackedSequenceCommand))}</code>
              {" / "}requires receipt{" "}
              <code>
                {yesNo(operatorConfirmationHandoff.post_resume_receipt_backed_sequence_requires_confirmation_receipt)}
              </code>
              {" / "}receipt id{" "}
              <code>
                {codeValue(operatorConfirmationHandoff.post_resume_receipt_backed_sequence_confirmation_receipt_id_placeholder)}
              </code>
            </div>
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
              receipt route <code>{codeValue(operatorConfirmationHandoff.confirmation_receipt_route)}</code>
              {" / "}readback <code>{codeValue(operatorConfirmationHandoff.confirmation_receipt_readback_route)}</code>
            </div>
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
              receipt scope <code>{codeValue(operatorConfirmationHandoff.confirmation_receipt_required_scope)}</code>
              {" / "}writes evidence{" "}
              <code>{yesNo(operatorConfirmationHandoff.confirmation_receipt_writes_evidence)}</code>
              {" / "}marks closed{" "}
              <code>{yesNo(operatorConfirmationHandoff.confirmation_receipt_marks_stage16_closed)}</code>
            </div>
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
              receipt command <code>{yesNo(operatorConfirmationHandoff.confirmation_receipt_command_ready)}</code>
              {" / "}visible{" "}
              <code>{yesNo(Boolean(visibleOperatorCommands.confirmation_receipt_copyable_command))}</code>
              {" / "}records receipt{" "}
              <code>{yesNo(operatorConfirmationHandoff.confirmation_receipt_command_records_receipt)}</code>
              {" / "}projection{" "}
              <code>{yesNo(operatorConfirmationHandoff.confirmation_receipt_command_projection_only)}</code>
            </div>
            {operatorConfirmationHandoff.operator_confirmation_source_required ? (
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                source <code>{operatorConfirmationHandoff.operator_confirmation_source_required}</code>
              </div>
            ) : null}
            {operatorConfirmationHandoff.pre_sleep_evidence_path ? (
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                pre evidence <code>{operatorConfirmationHandoff.pre_sleep_evidence_path}</code>
              </div>
            ) : null}
            {operatorConfirmationHandoff.confirmation_receipt_copyable_command ? (
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
                {operatorConfirmationHandoff.confirmation_receipt_copyable_command}
              </pre>
            ) : null}
            {visiblePostResumeCaptureCommand ? (
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
                {visiblePostResumeCaptureCommand}
              </pre>
            ) : null}
            {visiblePostResumeSequenceCommand ? (
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
                {visiblePostResumeSequenceCommand}
              </pre>
            ) : null}
            {visiblePostResumeReceiptBackedSequenceCommand ? (
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
                {visiblePostResumeReceiptBackedSequenceCommand}
              </pre>
            ) : null}
            {operatorConfirmationHandoff.required_confirmation_requirements.length ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {operatorConfirmationHandoff.required_confirmation_requirements.map((requirement) => (
                  <span key={`federation-confirmation-handoff-requirement-${requirement}`} style={badgeStyle("blocked")}>
                    {requirement}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {afterManualExecutionReadback ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: MUTED }}>
              after manual run <code>{codeValue(afterManualExecutionReadback.status)}</code>
              {" / "}next action <code>{codeValue(afterManualExecutionReadback.expected_action_status_after_success)}</code>
              {" / "}confirmation pending <code>{yesNo(afterManualExecutionReadback.operator_confirmation_pending)}</code>
            </div>
            {afterManualExecutionReadback.run_blockers.length ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {afterManualExecutionReadback.run_blockers.map((blocker) => (
                  <span key={`federation-after-manual-blocker-${blocker}`} style={badgeStyle("blocked")}>
                    {blocker}
                  </span>
                ))}
              </div>
            ) : null}
            {afterManualExecutionReadback.expected_artifact_root ? (
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                artifact root <code>{afterManualExecutionReadback.expected_artifact_root}</code>
              </div>
            ) : null}
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
              artifact <code>{codeValue(afterManualExecutionReadback.expected_artifact_prefix)}</code>
              {" / "}kind <code>{codeValue(afterManualExecutionReadback.expected_artifact_kind)}</code>
            </div>
            {afterManualExecutionReadback.expected_next_step_after_success ? (
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                expected next step <code>{afterManualExecutionReadback.expected_next_step_after_success}</code>
              </div>
            ) : null}
          </div>
        ) : null}
        {operatorSleepResumeGate ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: MUTED }}>
              sleep/resume gate <code>{codeValue(operatorSleepResumeGate.status)}</code>
              {" / "}current ready <code>{yesNo(operatorSleepResumeGate.current_ready_to_run)}</code>
              {" / "}confirmation pending <code>{yesNo(operatorSleepResumeGate.operator_confirmation_pending)}</code>
              {" / "}after confirmation <code>{yesNo(operatorSleepResumeGate.ready_after_operator_confirmation)}</code>
              {" / "}no inference <code>{yesNo(operatorSleepResumeGate.does_not_infer_sleep_from_delay)}</code>
            </div>
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
              pre marker <code>{codeValue(operatorSleepResumeGate.pre_sleep_file_name)}</code>
              {" / "}age <code>{operatorSleepResumeGate.pre_sleep_age_seconds}s</code>
              {" / "}freshness <code>{codeValue(operatorSleepResumeGate.pre_sleep_freshness_state)}</code>
            </div>
            {operatorSleepResumeGate.pre_sleep_evidence_path ? (
              <div style={{ fontSize: 11, color: MUTED, marginTop: 6, overflowWrap: "anywhere" }}>
                pre path <code>{operatorSleepResumeGate.pre_sleep_evidence_path}</code>
              </div>
            ) : null}
            <div style={{ fontSize: 11, color: MUTED, marginTop: 6 }}>
              post evidence <code>{yesNo(operatorSleepResumeGate.post_resume_evidence_present)}</code>
              {" / "}status <code>{codeValue(operatorSleepResumeGate.post_resume_evidence_status)}</code>
            </div>
            {operatorSleepResumeGate.required_confirmation_requirements.length ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {operatorSleepResumeGate.required_confirmation_requirements.map((requirement) => (
                  <span key={`federation-sleep-gate-requirement-${requirement}`} style={badgeStyle("blocked")}>
                    {requirement}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {presentation?.expected_output ? (
          <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>
            expected <code>{presentation.expected_output}</code>
          </div>
        ) : null}
        {presentation?.operator_confirmation_requirements.length ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: MUTED }}>confirmation requirements</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
              {presentation.operator_confirmation_requirements.map((requirement) => (
                <span key={`federation-confirmation-requirement-${requirement}`} style={badgeStyle("blocked")}>
                  {requirement}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {selectedActionReadiness ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: MUTED }}>
              readiness <code>{codeValue(selectedActionReadiness.status)}</code>
              {" / "}ready <code>{yesNo(selectedActionReadiness.ready_to_run)}</code>
              {" / "}terminal projected <code>{yesNo(selectedActionReadiness.operator_terminal_command_ready)}</code>
              {" / "}terminal visible <code>{yesNo(Boolean(visibleOperatorTerminalCommand))}</code>
            </div>
            {selectedActionReadiness.run_blockers.length ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {selectedActionReadiness.run_blockers.map((blocker) => (
                  <span key={`federation-readiness-blocker-${blocker}`} style={badgeStyle("blocked")}>
                    {blocker}
                  </span>
                ))}
              </div>
            ) : null}
            {selectedActionReadiness.remaining_evidence_gates.length ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {selectedActionReadiness.remaining_evidence_gates.map((gate) => (
                  <span key={`federation-evidence-gate-${gate}`} style={badgeStyle("blocked")}>
                    {gate}
                  </span>
                ))}
              </div>
            ) : null}
            {selectedActionReadiness.met_conditions.length ? (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 11, color: MUTED }}>met conditions</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                  {selectedActionReadiness.met_conditions.map((condition) => (
                    <span key={`federation-met-condition-${condition}`} style={badgeStyle("ready")}>
                      {condition}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
            {selectedActionReadiness.command_validation.length ? (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 11, color: MUTED }}>command validation</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                  {selectedActionReadiness.command_validation.map((check) => (
                    <span key={`federation-command-validation-${check}`} style={badgeStyle("ready")}>
                      {check}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
            {selectedActionReadiness.command_validation_blockers.length ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {selectedActionReadiness.command_validation_blockers.map((blocker) => (
                  <span key={`federation-command-validation-blocker-${blocker}`} style={badgeStyle("blocked")}>
                    {blocker}
                  </span>
                ))}
              </div>
            ) : null}
            {selectedActionReadiness.next_operator_step ? (
              <div style={{ fontSize: 11, color: MUTED, marginTop: 8, overflowWrap: "anywhere" }}>
                next operator step <code>{selectedActionReadiness.next_operator_step}</code>
              </div>
            ) : null}
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
            <span style={badgeStyle(recordBoolean(governance, "read_only") ? "ready" : "blocked")}>
              read-only {yesNo(recordBoolean(governance, "read_only"))}
            </span>
            <span style={badgeStyle(recordBoolean(governance, "does_not_infer_sleep_from_delay") ? "ready" : "blocked")}>
              no sleep inference {yesNo(recordBoolean(governance, "does_not_infer_sleep_from_delay"))}
            </span>
            <span style={badgeStyle(recordBoolean(governance, "does_not_run_selected_command") ? "ready" : "blocked")}>
              no selected command {yesNo(recordBoolean(governance, "does_not_run_selected_command"))}
            </span>
            <span style={badgeStyle(recordBoolean(governance, "does_not_post_selected_route") ? "ready" : "blocked")}>
              no selected route {yesNo(recordBoolean(governance, "does_not_post_selected_route"))}
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
