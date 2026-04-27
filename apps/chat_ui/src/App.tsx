import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArtifactInspectionPanel } from "./artifacts/ArtifactInspectionPanel";
import { parseChatSendResponse, type ChatMessage } from "./chat";

import type { ApprovalItem } from "./index";
import { ApprovalsApiError, ApprovalsClient } from "./index";
import {
  MissionsApiError,
  MissionsClient,
  missionCurrentOperation,
  missionCurrentTaskId,
  missionRecoveryTargetId,
  presentMissionQueue,
} from "./missions";
import type {
  MissionCurrentTask,
  MissionDetail,
  MissionGovernanceDecision,
  MissionLoopState,
  MissionQueueItem,
  MissionReceiptSummary,
} from "./missions";
import {
  buildMemoryEvidenceQueries,
  memoryEvidenceQueryKey,
  mergeMemoryEvidenceResponses,
} from "./memory_evidence";
import {
  buildExplanationEvidenceQueries,
  explanationEvidenceQueryKey,
  mergeExplanationEvidenceResponses,
} from "./explanation_evidence";
import { ExplanationApiError, ExplanationClient, type ExplanationRecord } from "./explanation_explorer";
import { MemoryTimelineApiError, MemoryTimelineClient } from "./memory_timeline";
import type { MemoryTimelineEvent } from "./memory_timeline";
import { OperationsApiError, OperationsClient } from "./operations";
import type { OperationDetail, OperationGovernanceDecision, OperationMemoryReceipt, OperationRecord } from "./operations";
import type {
  PluginForgeProposal,
  PluginForgeProposalDecisionAction,
  PluginForgeProposalReview,
  PluginPromotionReadinessItem,
  PluginRef,
  PluginRunResponse,
  PluginToolRef,
  PluginToolRunRequest,
} from "./plugin_browser";
import { PluginBrowserApiError, PluginBrowserClient } from "./plugin_browser";
import {
  SettingsApiError,
  SettingsClient,
  missionReadinessEvidenceLines,
  presentMissionDeadletterItems,
  presentMissionReadinessCriteria,
  presentMissionRecoveryItems,
  toLocaleTime,
} from "./settings";
import type {
  ContinuityBriefingSnapshot,
  ContinuityLedgerEntry,
  ContinuityLedgerSnapshot,
  MissionReadinessSummary,
  ObserverAnomalySummary,
  ObserverEventsSnapshot,
  ObserverScanReceiptSummary,
  OperatorControlModeId,
  OperatorModeSnapshot,
  OrbStatusSnapshot,
  SystemHealth,
  SystemInfo,
  WorldStateApprovalSummary,
  WorldStateIncidentSummary,
  WorldStateMissionSummary,
  WorldStateSnapshot,
} from "./settings";

const DEFAULT_API = "http://127.0.0.1:8000";

type TabKey = "approvals" | "plugins" | "system" | "operations" | "settings";
type SensingMode = "text_only" | "input_only" | "camera_mic";
type PaletteCommand = {
  id: string;
  label: string;
  description: string;
  group: string;
  keywords?: string;
  run: () => void | Promise<void>;
};

type UiSettings = {
  proactive: boolean;
  sensingMode: SensingMode;
  voiceEnabled: boolean;
  voiceAutoFemale: boolean;
  voiceUri: string;
  voiceRate: number;
  voicePitch: number;
};

type ChatSession = {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedTs: number;
};

type ChatMissionSurface = {
  missionId: string;
  operationId?: string;
  status?: string;
  activeStage?: string;
  nextStep?: string;
};

type MissionMemoryReceiptLike = {
  id?: string;
  source?: string;
  ts?: unknown;
  mission_id?: string;
  operation_id?: string;
  trace_id?: string;
  approval_id?: string;
  run_id?: string;
  artifact_dir?: string;
  operation_status?: string;
  operation_error?: string;
  result_message?: string;
  recovery_next_step?: string;
  active_stage?: string;
  handoff_stage?: string;
  handoff_action?: string;
  handoff_operation_id?: string;
  handoff_trace_id?: string;
  handoff_run_id?: string;
  handoff_artifact_dir?: string;
  handoff_next_step?: string;
  current_task_source?: string;
  current_task_operation_id?: string;
  current_task_operation_name?: string;
  current_task_operation_plane?: string;
  current_task_advance_action?: string;
  current_task_trace_id?: string;
  current_task_run_id?: string;
  current_task_artifact_dir?: string;
  current_task_next_step?: string;
  memory_receipt_count?: number;
  references?: {
    mission_id?: string;
    operation_id?: string;
    trace_id?: string;
    approval_id?: string;
    run_id?: string;
    artifact_dir?: string;
  };
};

type MissionOperationRecoveryFields = {
  operationError?: string;
  resultMessage?: string;
  recoveryNextStep?: string;
};

type MissionOperationRecoverySource = {
  operation_error?: unknown;
  result_message?: unknown;
  recovery_next_step?: unknown;
  memory_receipt?: unknown;
  latest_memory_receipt?: unknown;
};

const DEFAULT_SETTINGS: UiSettings = {
  proactive: true,
  sensingMode: "text_only",
  voiceEnabled: false,
  voiceAutoFemale: true,
  voiceUri: "",
  voiceRate: 1.0,
  voicePitch: 1.0,
};

const THEME = {
  bg: "#0a0a0a",
  panel: "#141414",
  panelBorder: "#242424",
  rail: "#0f0f0f",
  railBorder: "#1f1f1f",
  inputBg: "#1b1b1b",
  inputBorder: "#2e2e2e",
  text: "#f5f5f5",
  muted: "#bdbdbd",
  buttonBg: "#1f1f1f",
  buttonBorder: "#333333",
  buttonActive: "#2a2a2a",
  errorBg: "#2a0f0f",
  errorBorder: "#5a1a1a",
  userBubble: "#1f1f1f",
  assistantBubble: "#121212",
};

const panelStyle: React.CSSProperties = {
  border: `1px solid ${THEME.panelBorder}`,
  padding: 16,
  borderRadius: 14,
  background: THEME.panel,
};

const inputStyle: React.CSSProperties = {
  padding: 12,
  borderRadius: 12,
  border: `1px solid ${THEME.inputBorder}`,
  background: THEME.inputBg,
  color: THEME.text,
};

const buttonStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: 12,
  border: `1px solid ${THEME.buttonBorder}`,
  background: THEME.buttonBg,
  color: THEME.text,
};

function clamp01(n: number): number {
  return Math.min(2, Math.max(0.5, n));
}

function normalizeBaseUrl(url: string): string {
  return (url || "").trim().replace(/\/+$/, "");
}

function safeString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function missionGovernanceNotice(governance: MissionGovernanceDecision | undefined, fallback = ""): string {
  if (!governance) return fallback;
  const gate = safeString(governance.gate).trim();
  const reason = safeString(governance.reason).trim();
  const nextStep = safeString(governance.next_step).trim();
  const parts = [
    gate ? `gate=${gate}` : "",
    reason ? `reason=${reason}` : "",
    nextStep ? `next=${nextStep}` : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" / ") : fallback;
}

function operationGovernanceNotice(governance: OperationGovernanceDecision | undefined, fallback = ""): string {
  if (!governance) return fallback;
  const gate = safeString(governance.gate).trim();
  const reason = safeString(governance.reason).trim();
  const nextStep = safeString(governance.next_step).trim();
  const operatorHint = safeString(governance.operator_hint).trim();
  const parts = [
    gate ? `gate=${gate}` : "",
    reason ? `reason=${reason}` : "",
    nextStep ? `next=${nextStep}` : "",
    operatorHint ? `hint=${operatorHint}` : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" / ") : fallback;
}

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function missionOperationRecoveryFields(source: MissionOperationRecoverySource | null | undefined): MissionOperationRecoveryFields {
  const rawMemoryReceipt = source?.memory_receipt;
  const rawLatestMemoryReceipt = source?.latest_memory_receipt;
  const memoryReceipt = isRecord(rawMemoryReceipt) ? rawMemoryReceipt : {};
  const latestMemoryReceipt = isRecord(rawLatestMemoryReceipt) ? rawLatestMemoryReceipt : {};
  return {
    operationError:
      safeString(source?.operation_error).trim() ||
      safeString(memoryReceipt.operation_error).trim() ||
      safeString(latestMemoryReceipt.operation_error).trim() ||
      undefined,
    resultMessage:
      safeString(source?.result_message).trim() ||
      safeString(memoryReceipt.result_message).trim() ||
      safeString(latestMemoryReceipt.result_message).trim() ||
      undefined,
    recoveryNextStep:
      safeString(source?.recovery_next_step).trim() ||
      safeString(memoryReceipt.recovery_next_step).trim() ||
      safeString(latestMemoryReceipt.recovery_next_step).trim() ||
      undefined,
  };
}

function missionOperationRecoveryLine(fields: MissionOperationRecoveryFields | null | undefined): React.ReactNode {
  const items = [
    { label: "operation_error", value: safeString(fields?.operationError).trim() },
    { label: "result_message", value: safeString(fields?.resultMessage).trim() },
    { label: "recovery_next_step", value: safeString(fields?.recoveryNextStep).trim() },
  ].filter((item) => item.value);
  if (items.length === 0) return null;

  return (
    <div
      style={{
        fontSize: 11,
        color: fields?.operationError ? "#ffcf9d" : THEME.muted,
        marginTop: 4,
        overflowWrap: "anywhere",
      }}
    >
      {items.map((item, index) => (
        <React.Fragment key={item.label}>
          {index > 0 ? " / " : ""}
          {item.label}=<code>{item.value}</code>
        </React.Fragment>
      ))}
    </div>
  );
}

function chatMissionSurface(message: ChatMessage): ChatMissionSurface | null {
  const meta = isRecord(message.meta) ? message.meta : {};
  if (safeString(meta.mode).trim() !== "mission_ingress") return null;

  const mission = isRecord(meta.mission) ? meta.mission : {};
  const loopState = isRecord(meta.loop_state) ? meta.loop_state : {};
  const handoff = isRecord(loopState.handoff) ? loopState.handoff : {};
  const currentTask = isRecord(meta.current_task) ? meta.current_task : {};
  const queueItem = isRecord(meta.queue_item) ? meta.queue_item : {};
  const missionId = safeString(meta.mission_id).trim() || safeString(mission.id).trim();
  if (!missionId) return null;

  const surface: ChatMissionSurface = { missionId };
  const status = safeString(meta.status).trim();
  const activeStage = safeString(loopState.active_stage).trim();
  const operationId =
    safeString(meta.operation_id).trim() ||
    safeString(currentTask.operation_id).trim() ||
    safeString(handoff.operation_id).trim() ||
    safeString(queueItem.action_target_id).trim();
  const nextStep =
    safeString(currentTask.next_step).trim() ||
    safeString(handoff.next_step).trim() ||
    safeString(handoff.action).trim();
  if (status) surface.status = status;
  if (activeStage) surface.activeStage = activeStage;
  if (operationId) surface.operationId = operationId;
  if (nextStep) surface.nextStep = nextStep;
  return surface;
}

function operationMetaString(record: OperationRecord | null | undefined, key: string, fallback = ""): string {
  if (!record || !isRecord(record.meta)) return fallback;
  return safeString(record.meta[key], fallback);
}

function operationOutputRecord(record: OperationRecord | null | undefined): Record<string, unknown> {
  return isRecord(record?.output) ? record.output : {};
}

function operationGovernance(record: OperationRecord | null | undefined): Record<string, unknown> {
  const metaGovernance = record && isRecord(record.meta) && isRecord(record.meta.governance) ? record.meta.governance : null;
  if (metaGovernance) return metaGovernance;
  const output = operationOutputRecord(record);
  return isRecord(output.governance) ? output.governance : {};
}

function operationApprovalId(record: OperationRecord | null | undefined): string {
  return operationMetaString(record, "approval_id") || safeString(operationOutputRecord(record).approval_id);
}

function operationMissionId(record: OperationRecord | null | undefined): string {
  if (!record) return "";
  const input = isRecord(record.input) ? record.input : {};
  const inputMeta = isRecord(input.meta) ? input.meta : {};
  const output = operationOutputRecord(record);
  return (
    operationMetaString(record, "mission_id").trim() ||
    safeString(input.mission_id).trim() ||
    safeString(inputMeta.mission_id).trim() ||
    safeString(output.mission_id).trim()
  );
}

function operationGate(record: OperationRecord | null | undefined): string {
  return safeString(operationGovernance(record).gate).trim();
}

function operationNextStep(record: OperationRecord | null | undefined): string {
  return safeString(operationGovernance(record).next_step).trim();
}

function operationResultMessage(record: OperationRecord | null | undefined): string {
  return operationMetaString(record, "result_message") || safeString(operationOutputRecord(record).message).trim();
}

function operationTraceId(record: OperationRecord | null | undefined): string {
  return safeString(record?.trace_id).trim() || operationMetaString(record, "trace_id");
}

function operationRunId(record: OperationRecord | null | undefined): string {
  const output = operationOutputRecord(record);
  const receipt = isRecord(output.receipt) ? output.receipt : {};
  const sandbox = isRecord(output.sandbox) ? output.sandbox : isRecord(receipt.sandbox) ? receipt.sandbox : {};
  return (
    safeString(record?.run_id).trim() ||
    operationMetaString(record, "run_id") ||
    safeString(output.run_id).trim() ||
    safeString(output.runId).trim() ||
    safeString(receipt.run_id).trim() ||
    safeString(sandbox.run_id).trim()
  );
}

function operationArtifactDir(record: OperationRecord | null | undefined): string {
  const output = operationOutputRecord(record);
  const receipt = isRecord(output.receipt) ? output.receipt : {};
  const sandbox = isRecord(output.sandbox) ? output.sandbox : isRecord(receipt.sandbox) ? receipt.sandbox : {};
  return (
    safeString(record?.artifact_dir).trim() ||
    operationMetaString(record, "artifact_dir") ||
    safeString(output.artifact_dir).trim() ||
    safeString(output.artifact_path).trim() ||
    safeString(receipt.artifact_dir).trim() ||
    safeString(receipt.artifact_path).trim() ||
    safeString(sandbox.artifact_dir).trim() ||
    safeString(sandbox.artifact_path).trim()
  );
}

function memoryTimelineEventSummary(event: MemoryTimelineEvent): string {
  return safeString(event.title).trim() || safeString(event.message).trim() || safeString(event.kind).trim() || event.id;
}

function memoryTimelineEventReferenceLine(event: MemoryTimelineEvent): string {
  const refs = event.references;
  const loop = event.loop;
  const parts: string[] = [];
  if (refs?.mission_id) parts.push(`mission ${refs.mission_id}`);
  const operationId =
    refs?.operation_id || loop?.current_task_operation_id || loop?.handoff_operation_id;
  const traceId = refs?.trace_id || loop?.current_task_trace_id || loop?.handoff_trace_id;
  const approvalId = refs?.approval_id || loop?.current_task_approval_id || loop?.handoff_approval_id;
  const runId = refs?.run_id || loop?.current_task_run_id || loop?.handoff_run_id || loop?.run_id;
  const artifactDir =
    refs?.artifact_dir || loop?.current_task_artifact_dir || loop?.handoff_artifact_dir || loop?.artifact_dir;
  if (operationId) parts.push(`task ${operationId}`);
  if (traceId) parts.push(`trace ${traceId}`);
  if (approvalId) parts.push(`approval ${approvalId}`);
  if (runId) parts.push(`run ${runId}`);
  if (artifactDir) parts.push(`artifact ${artifactDir}`);
  return parts.join(" / ");
}

function explanationRecordSummary(record: ExplanationRecord): string {
  return safeString(record.title).trim() || safeString(record.summary).trim() || safeString(record.kind).trim() || record.id;
}

function explanationRecordReferenceLine(record: ExplanationRecord): string {
  const parts: string[] = [];
  if (record.mission_id) parts.push(`mission ${record.mission_id}`);
  if (record.operation_id) parts.push(`task ${record.operation_id}`);
  if (record.trace_id) parts.push(`trace ${record.trace_id}`);
  if (record.run_id) parts.push(`run ${record.run_id}`);
  if (record.artifact_dir) parts.push(`artifact ${record.artifact_dir}`);
  if (record.approval_id) parts.push(`approval ${record.approval_id}`);
  if (record.plugin_id) parts.push(`plugin ${record.plugin_id}`);
  if (record.domain) parts.push(`domain ${record.domain}`);
  return parts.join(" / ");
}

function missionMemoryReceiptLabel(receipt: MissionMemoryReceiptLike | null | undefined): string {
  return safeString(receipt?.id).trim() || safeString(receipt?.source).trim() || "receipt";
}

function missionMemoryReceiptReferenceLine(receipt: MissionMemoryReceiptLike | null | undefined): string {
  const refs = receipt?.references;
  const parts: string[] = [];
  const missionId = safeString(receipt?.mission_id).trim() || safeString(refs?.mission_id).trim();
  const operationId = safeString(receipt?.operation_id).trim() || safeString(refs?.operation_id).trim();
  const traceId = safeString(receipt?.trace_id).trim() || safeString(refs?.trace_id).trim();
  const approvalId = safeString(receipt?.approval_id).trim() || safeString(refs?.approval_id).trim();
  const runId = safeString(receipt?.run_id).trim() || safeString(refs?.run_id).trim();
  const artifactDir = safeString(receipt?.artifact_dir).trim() || safeString(refs?.artifact_dir).trim();
  if (missionId) parts.push(`mission ${missionId}`);
  if (operationId) parts.push(`task ${operationId}`);
  if (traceId) parts.push(`trace ${traceId}`);
  if (approvalId) parts.push(`approval ${approvalId}`);
  if (runId) parts.push(`run ${runId}`);
  if (artifactDir) parts.push(`artifact ${artifactDir}`);
  return parts.join(" / ");
}

function missionMemoryReceiptHandoffLine(receipt: MissionMemoryReceiptLike | null | undefined): string {
  const refs = receipt?.references;
  const parts: string[] = [];
  const activeStage = safeString(receipt?.active_stage).trim();
  const handoffStage = safeString(receipt?.handoff_stage).trim();
  const handoffAction = safeString(receipt?.handoff_action).trim();
  const nextStep =
    safeString(receipt?.current_task_next_step).trim() || safeString(receipt?.handoff_next_step).trim();
  const operationId =
    safeString(receipt?.current_task_operation_id).trim() || safeString(receipt?.handoff_operation_id).trim();
  const operationName = safeString(receipt?.current_task_operation_name).trim();
  const operationPlane = safeString(receipt?.current_task_operation_plane).trim();
  const advanceAction = safeString(receipt?.current_task_advance_action).trim();
  const traceId = safeString(receipt?.current_task_trace_id).trim() || safeString(receipt?.handoff_trace_id).trim();
  const runId = safeString(receipt?.current_task_run_id).trim() || safeString(receipt?.handoff_run_id).trim();
  const artifactDir =
    safeString(receipt?.current_task_artifact_dir).trim() || safeString(receipt?.handoff_artifact_dir).trim();
  const receiptCount =
    typeof receipt?.memory_receipt_count === "number" && Number.isFinite(receipt.memory_receipt_count)
      ? receipt.memory_receipt_count
      : undefined;
  const baseOperationId = safeString(receipt?.operation_id).trim() || safeString(refs?.operation_id).trim();
  const baseTraceId = safeString(receipt?.trace_id).trim() || safeString(refs?.trace_id).trim();
  const baseRunId = safeString(receipt?.run_id).trim() || safeString(refs?.run_id).trim();
  const baseArtifactDir = safeString(receipt?.artifact_dir).trim() || safeString(refs?.artifact_dir).trim();
  if (activeStage) parts.push(`active_stage ${activeStage}`);
  if (handoffStage && handoffStage !== activeStage) parts.push(`handoff_stage ${handoffStage}`);
  if (handoffAction) parts.push(`handoff ${handoffAction}`);
  if (nextStep) parts.push(`next ${nextStep}`);
  if (operationId && operationId !== baseOperationId) parts.push(`handoff_task ${operationId}`);
  if (operationName) parts.push(`task_name ${operationName}`);
  if (operationPlane) parts.push(`task_plane ${operationPlane}`);
  if (advanceAction && advanceAction !== handoffAction) parts.push(`advance ${advanceAction}`);
  if (traceId && traceId !== baseTraceId) parts.push(`handoff_trace ${traceId}`);
  if (runId && runId !== baseRunId) parts.push(`handoff_run ${runId}`);
  if (artifactDir && artifactDir !== baseArtifactDir) parts.push(`handoff_artifact ${artifactDir}`);
  if (receiptCount !== undefined) parts.push(`receipt_count ${String(receiptCount)}`);
  return parts.join(" / ");
}

function operationMemoryReceiptReferenceLine(receipt: OperationMemoryReceipt | null | undefined): string {
  const refs = receipt?.references;
  const parts: string[] = [];
  if (refs?.mission_id) parts.push(`mission ${refs.mission_id}`);
  if (refs?.operation_id) parts.push(`task ${refs.operation_id}`);
  if (refs?.trace_id) parts.push(`trace ${refs.trace_id}`);
  if (refs?.approval_id) parts.push(`approval ${refs.approval_id}`);
  if (refs?.run_id) parts.push(`run ${refs.run_id}`);
  if (refs?.artifact_dir) parts.push(`artifact ${refs.artifact_dir}`);
  return parts.join(" / ");
}

function operationMemoryReceiptCurrentTaskLine(receipt: OperationMemoryReceipt | null | undefined): string {
  const refs = receipt?.references;
  const parts: string[] = [];
  const source = safeString(receipt?.current_task_source).trim();
  const activeStage = safeString(receipt?.active_stage).trim();
  const handoffStage = safeString(receipt?.handoff_stage).trim();
  const handoffAction = safeString(receipt?.handoff_action).trim();
  const gate = safeString(receipt?.current_task_gate).trim() || safeString(receipt?.handoff_gate).trim();
  const approvalId =
    safeString(receipt?.current_task_approval_id).trim() || safeString(receipt?.handoff_approval_id).trim();
  const approvalStatus =
    safeString(receipt?.current_task_approval_status).trim() ||
    safeString(receipt?.handoff_approval_status).trim() ||
    safeString(receipt?.approval_status).trim();
  const operationId =
    safeString(receipt?.current_task_operation_id).trim() ||
    safeString(receipt?.handoff_operation_id).trim() ||
    safeString(refs?.operation_id).trim();
  const nextStep =
    safeString(receipt?.current_task_next_step).trim() || safeString(receipt?.handoff_next_step).trim();
  const traceId =
    safeString(receipt?.current_task_trace_id).trim() ||
    safeString(receipt?.handoff_trace_id).trim() ||
    safeString(refs?.trace_id).trim();
  const runId =
    safeString(receipt?.current_task_run_id).trim() ||
    safeString(receipt?.handoff_run_id).trim() ||
    safeString(refs?.run_id).trim();
  const artifactDir =
    safeString(receipt?.current_task_artifact_dir).trim() ||
    safeString(receipt?.handoff_artifact_dir).trim() ||
    safeString(refs?.artifact_dir).trim();
  const receiptCount =
    typeof receipt?.memory_receipt_count === "number" && Number.isFinite(receipt.memory_receipt_count)
      ? receipt.memory_receipt_count
      : undefined;

  if (source) parts.push(`source ${source}`);
  if (activeStage) parts.push(`active ${activeStage}`);
  if (handoffStage) parts.push(`handoff ${handoffStage}`);
  if (handoffAction) parts.push(`action ${handoffAction}`);
  if (gate) parts.push(`gate ${gate}`);
  if (approvalId) parts.push(`approval ${approvalId}`);
  if (approvalStatus) parts.push(`approval_status ${approvalStatus}`);
  if (operationId) parts.push(`task ${operationId}`);
  if (receipt?.current_task_operation_name) parts.push(`task_name ${receipt.current_task_operation_name}`);
  if (receipt?.current_task_operation_plane) parts.push(`task_plane ${receipt.current_task_operation_plane}`);
  if (receipt?.current_task_advance_action) parts.push(`advance ${receipt.current_task_advance_action}`);
  if (nextStep) parts.push(`next ${nextStep}`);
  if (traceId) parts.push(`trace ${traceId}`);
  if (runId) parts.push(`run ${runId}`);
  if (artifactDir) parts.push(`artifact ${artifactDir}`);
  if (receiptCount !== undefined) parts.push(`receipt_count ${String(receiptCount)}`);
  return parts.join(" / ");
}

function operationMemoryReceiptFromMeta(value: unknown): OperationMemoryReceipt | undefined {
  if (!isRecord(value)) return undefined;
  const rawMemoryReceiptCount = safeNumber(value.memory_receipt_count, Number.NaN);
  const referencesRaw = isRecord(value.references) ? value.references : {};
  const references = {
    mission_id: safeString(referencesRaw.mission_id).trim() || undefined,
    operation_id: safeString(referencesRaw.operation_id).trim() || undefined,
    trace_id: safeString(referencesRaw.trace_id).trim() || undefined,
    approval_id: safeString(referencesRaw.approval_id).trim() || undefined,
    run_id: safeString(referencesRaw.run_id).trim() || undefined,
    artifact_dir: safeString(referencesRaw.artifact_dir).trim() || undefined,
  };
  const receipt: OperationMemoryReceipt = {
    source: safeString(value.source).trim() || undefined,
    kind: safeString(value.kind).trim() || undefined,
    ts: safeNumber(value.ts, 0) || undefined,
    role: safeString(value.role).trim() || undefined,
    message: safeString(value.message).trim() || undefined,
    scope: safeString(value.scope).trim() || undefined,
    operation_status: safeString(value.operation_status).trim() || undefined,
    approval_status: safeString(value.approval_status).trim() || undefined,
    capability: safeString(value.capability).trim() || undefined,
    subsystem: safeString(value.subsystem).trim() || undefined,
    active_stage: safeString(value.active_stage).trim() || undefined,
    handoff_stage: safeString(value.handoff_stage).trim() || undefined,
    handoff_action: safeString(value.handoff_action).trim() || undefined,
    handoff_gate: safeString(value.handoff_gate).trim() || undefined,
    handoff_approval_id: safeString(value.handoff_approval_id).trim() || undefined,
    handoff_approval_status: safeString(value.handoff_approval_status).trim() || undefined,
    handoff_operation_id: safeString(value.handoff_operation_id).trim() || undefined,
    handoff_trace_id: safeString(value.handoff_trace_id).trim() || undefined,
    handoff_run_id: safeString(value.handoff_run_id).trim() || undefined,
    handoff_artifact_dir: safeString(value.handoff_artifact_dir).trim() || undefined,
    handoff_next_step: safeString(value.handoff_next_step).trim() || undefined,
    current_task_source: safeString(value.current_task_source).trim() || undefined,
    current_task_approval_id: safeString(value.current_task_approval_id).trim() || undefined,
    current_task_approval_status: safeString(value.current_task_approval_status).trim() || undefined,
    current_task_operation_id: safeString(value.current_task_operation_id).trim() || undefined,
    current_task_operation_name: safeString(value.current_task_operation_name).trim() || undefined,
    current_task_operation_plane: safeString(value.current_task_operation_plane).trim() || undefined,
    current_task_advance_action: safeString(value.current_task_advance_action).trim() || undefined,
    current_task_gate: safeString(value.current_task_gate).trim() || undefined,
    current_task_trace_id: safeString(value.current_task_trace_id).trim() || undefined,
    current_task_run_id: safeString(value.current_task_run_id).trim() || undefined,
    current_task_artifact_dir: safeString(value.current_task_artifact_dir).trim() || undefined,
    current_task_next_step: safeString(value.current_task_next_step).trim() || undefined,
    memory_receipt_count: Number.isFinite(rawMemoryReceiptCount)
      ? Math.max(0, Math.floor(rawMemoryReceiptCount))
      : undefined,
  };
  if (Object.values(references).some(Boolean)) receipt.references = references;
  return Object.values(receipt).some((item) => item !== undefined) ? receipt : undefined;
}

function missionLoopStagePlanReceiptLine(stage: MissionLoopState["plan"] | null | undefined): React.ReactNode {
  const planStatus = safeString(stage?.plan_status).trim();
  const currentStepId = safeString(stage?.plan_current_step_id).trim();
  const currentStepTitle = safeString(stage?.plan_current_step_title).trim();
  const stepCount =
    typeof stage?.plan_step_count === "number" && Number.isFinite(stage.plan_step_count)
      ? stage.plan_step_count
      : undefined;
  const checkpointCount =
    typeof stage?.plan_checkpoint_count === "number" && Number.isFinite(stage.plan_checkpoint_count)
      ? stage.plan_checkpoint_count
      : undefined;

  if (!planStatus && !currentStepId && !currentStepTitle && stepCount === undefined && checkpointCount === undefined) {
    return null;
  }

  const hasCheckpointPrefix = Boolean(planStatus || currentStepId || currentStepTitle || stepCount !== undefined);

  return (
    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6, overflowWrap: "anywhere" }}>
      {planStatus ? (
        <>
          plan_status <code>{planStatus}</code>
        </>
      ) : null}
      {(currentStepId || currentStepTitle) ? (
        <>
          {planStatus ? " / " : ""}current_step{" "}
          {currentStepId ? <code>{currentStepId}</code> : null}
          {currentStepId && currentStepTitle ? " / " : null}
          {currentStepTitle ? <code>{currentStepTitle}</code> : null}
        </>
      ) : null}
      {stepCount !== undefined ? (
        <>
          {(planStatus || currentStepId || currentStepTitle) ? " / " : ""}steps <code>{String(stepCount)}</code>
        </>
      ) : null}
      {checkpointCount !== undefined ? (
        <>
          {hasCheckpointPrefix ? " / " : ""}checkpoints <code>{String(checkpointCount)}</code>
        </>
      ) : null}
    </div>
  );
}

function operationRecoveryGuidance(record: OperationRecord | null | undefined): string {
  if (!record) return "";
  const output = operationOutputRecord(record);
  const governance = operationGovernance(record);
  const status = safeString(record.status).trim().toLowerCase();
  const gate =
    safeString(governance.gate).trim() ||
    operationMetaString(record, "gate") ||
    safeString(output.gate).trim();
  const nextStep =
    safeString(governance.next_step).trim() ||
    operationMetaString(record, "next_step") ||
    safeString(output.next_step).trim();
  const approvalId = operationApprovalId(record);
  const artifactDir = operationArtifactDir(record);
  const traceId = operationTraceId(record);
  const errorText = safeString(record.error).trim() || safeString(output.error).trim();

  if (nextStep) {
    return gate ? `Next step: ${nextStep} through ${gate}.` : `Next step: ${nextStep}.`;
  }
  if (approvalId) {
    return `Review approval ${approvalId} before rerunning this operation.`;
  }
  if (gate) {
    return `Resolve gate ${gate} before rerunning this operation.`;
  }
  if (artifactDir) {
    return `Inspect artifact ${artifactDir} for captured failure output before retrying.`;
  }
  if (traceId) {
    return `Inspect trace ${traceId} and the audit trail before retrying.`;
  }
  if (["blocked", "denied", "error", "failed"].includes(status) || errorText) {
    return "Inspect the audit trail and captured output, then retry only after the failure cause is resolved.";
  }
  return "";
}

function truncateText(value: string, maxChars = 180): string {
  const cleaned = safeString(value).trim();
  if (!cleaned) return "";
  if (cleaned.length <= maxChars) return cleaned;
  return `${cleaned.slice(0, maxChars).trimEnd()}…`;
}

function continuityLedgerMetaLabels(entry: ContinuityLedgerEntry): string[] {
  const meta = isRecord(entry.meta) ? entry.meta : {};
  const labels = [
    safeString(meta.subsystem).trim(),
    safeString(meta.session_id).trim(),
    safeString(meta.mission_id).trim(),
    safeString(meta.mode).trim() || safeString(meta.run_mode).trim(),
    safeString(meta.profile).trim(),
    safeString(meta.queue).trim() ? `queue ${safeString(meta.queue).trim()}` : "",
    safeString(meta.kind).trim(),
  ];
  return labels.filter((label) => label.length > 0).slice(0, 4);
}

function mixedLocaleTime(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return toLocaleTime(value);
  const text = safeString(value).trim();
  if (!text) return "";
  const parsedMs = Date.parse(text);
  if (Number.isNaN(parsedMs)) return "";
  return new Date(parsedMs).toLocaleString();
}

function latestActivitySummary(activity: Record<string, unknown> | null | undefined): {
  name: string;
  status: string;
  gate: string;
  observedAt: string;
} {
  if (!activity) {
    return { name: "", status: "", gate: "", observedAt: "" };
  }
  return {
    name: safeString(activity["name"]).trim(),
    status: safeString(activity["status"]).trim(),
    gate: safeString(activity["gate"]).trim(),
    observedAt: mixedLocaleTime(activity["ts"]),
  };
}

function incidentEvidenceSummary(incident: WorldStateIncidentSummary | null | undefined): string[] {
  const evidence = Array.isArray(incident?.evidence) ? incident.evidence : [];
  return evidence
    .map((item) => {
      const label =
        safeString(item?.label).trim() ||
        safeString(item?.id).trim() ||
        safeString(item?.kind).trim() ||
        "evidence";
      const status = safeString(item?.status).trim();
      const detail = safeString(item?.detail).trim();
      const path = safeString(item?.path).trim();
      const parts = [label];
      if (status) parts.push(status);
      if (detail) parts.push(detail);
      else if (path) parts.push(path);
      return parts.join(" / ");
    })
    .filter(Boolean)
    .slice(0, 2);
}

function observerScanFocusSummary(scan: ObserverScanReceiptSummary | null | undefined): string[] {
  const focus = Array.isArray(scan?.focus) ? scan.focus : [];
  return focus
    .map((item) => safeString(item?.title).trim() || safeString(item?.id).trim())
    .filter(Boolean)
    .slice(0, 2);
}

function observerAnomalyReasonSummary(anomaly: ObserverAnomalySummary | null | undefined): string {
  const reasons = Array.isArray(anomaly?.reasons) ? anomaly.reasons : [];
  return reasons.map((item) => safeString(item).trim()).filter(Boolean).slice(0, 3).join(" · ");
}

function renderObserverScanCard(scan: ObserverScanReceiptSummary, keyPrefix: string): React.ReactNode {
  const observedAt = mixedLocaleTime(scan.generated_at ?? scan.ts);
  const focusLines = observerScanFocusSummary(scan);
  const anomalySummary = observerAnomalyReasonSummary(scan.anomaly);

  return (
    <div
      key={`${keyPrefix}-${scan.receipt_id || scan.headline || observedAt}`}
      style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#0f0f0f" }}
    >
      {scan.anomaly ? (
        <div style={{ fontSize: 11, color: THEME.muted, marginBottom: 6 }}>
          <span style={badgeStyle(safeString(scan.anomaly.level).trim() || "clear")}>
            anomaly {safeNumber(scan.anomaly.score, 0)}/100
          </span>
          {anomalySummary ? <span style={{ marginLeft: 8 }}>{anomalySummary}</span> : null}
        </div>
      ) : null}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <div style={{ fontSize: 11, fontWeight: 600 }}>{scan.headline || "Observer scan recorded"}</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {scan.status ? <span style={badgeStyle(scan.status)}>{scan.status}</span> : null}
          {scan.decision ? <span style={badgeStyle(scan.decision)}>{scan.decision}</span> : null}
          {typeof scan.incident_count === "number" ? (
            <span style={badgeStyle(scan.incident_count > 0 ? "warning" : "clear")}>incidents {scan.incident_count}</span>
          ) : null}
        </div>
      </div>
      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
        receipt=<code>{scan.receipt_id || "unknown"}</code>
        {observedAt ? (
          <>
            {" / "}at=<code>{observedAt}</code>
          </>
        ) : null}
        {scan.trace_id ? (
          <>
            {" / "}trace=<code>{scan.trace_id}</code>
          </>
        ) : null}
        {scan.run_id ? (
          <>
            {" / "}run=<code>{scan.run_id}</code>
          </>
        ) : null}
        {scan.actor ? (
          <>
            {" / "}actor=<code>{scan.actor}</code>
          </>
        ) : null}
        {scan.reason ? (
          <>
            {" / "}reason=<code>{scan.reason}</code>
          </>
        ) : null}
      </div>
      {scan.probe_statuses?.length ? (
        <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
          {scan.probe_statuses.map((probe) => (
            <div
              key={`${keyPrefix}:${scan.receipt_id || scan.headline || "observer-scan"}:${probe.id || probe.headline}`}
              style={{
                border: `1px solid ${THEME.panelBorder}`,
                borderRadius: 8,
                padding: 8,
                background: "#121212",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                  flexWrap: "wrap",
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 600 }}>{probe.headline || probe.id || "Observer probe"}</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {probe.id ? <span style={badgeStyle(probe.id)}>{probe.id}</span> : null}
                  {probe.status ? <span style={badgeStyle(probe.status)}>{probe.status}</span> : null}
                  {probe.severity ? <span style={badgeStyle(probe.severity)}>{probe.severity}</span> : null}
                  {typeof probe.incident_count === "number" ? (
                    <span style={badgeStyle(probe.incident_count > 0 ? "warning" : "clear")}>
                      incidents {probe.incident_count}
                    </span>
                  ) : null}
                </div>
              </div>
              {probe.detail ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{probe.detail}</div> : null}
            </div>
          ))}
        </div>
      ) : null}
      {scan.probes?.length ? (
        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
          probes <code>{scan.probes.join(", ")}</code>
        </div>
      ) : null}
      {focusLines.length > 0 ? (
        <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
          {focusLines.map((line) => (
            <div key={`${keyPrefix}:${scan.receipt_id || scan.headline}:${line}`} style={{ fontSize: 11, color: THEME.muted }}>
              focus <code>{line}</code>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function executionBlockedReason(operatorMode: OperatorModeSnapshot | null, actionLabel: string): string {
  if (!operatorMode?.ok) {
    return "Execution controls remain disabled until operator posture is loaded.";
  }

  const controlModeId = safeString(operatorMode.control_mode?.id).trim().toLowerCase();
  const controlModeWrites = safeString(operatorMode.control_mode?.writes).trim().toLowerCase();
  const postureWrites = safeString(operatorMode.posture?.writes).trim().toLowerCase();

  if (controlModeId === "observe" || controlModeWrites === "blocked") {
    return `Observe mode keeps execution read-only. Switch posture before ${actionLabel}.`;
  }
  if (postureWrites === "blocked") {
    return `Current operator posture blocks writes. Adjust the environment before ${actionLabel}.`;
  }
  return "";
}

function statusBadgeColors(status: string): { bg: string; border: string; color: string } {
  const normalized = safeString(status).trim().toLowerCase();
  if (["ready", "ok", "approved", "completed", "succeeded", "healthy", "live", "recorded", "clear", "available"].includes(normalized)) {
    return { bg: "#102417", border: "#244d31", color: "#9de2ad" };
  }
  if (["running", "pending", "accepted", "queued", "needs_approval", "attention", "stale"].includes(normalized)) {
    return { bg: "#1f1a0b", border: "#5a4c18", color: "#f4d27a" };
  }
  if (
    [
      "blocked",
      "denied",
      "failed",
      "rejected",
      "cancelled",
      "canceled",
      "missing",
      "error",
      "degraded",
      "disabled",
      "unavailable",
    ].includes(
      normalized,
    )
  ) {
    return { bg: "#2a0f0f", border: "#5a1a1a", color: "#ffaaaa" };
  }
  return { bg: "#171717", border: "#333333", color: THEME.muted };
}

function badgeStyle(status: string): React.CSSProperties {
  const tone = statusBadgeColors(status);
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 11,
    padding: "4px 8px",
    borderRadius: 999,
    background: tone.bg,
    border: `1px solid ${tone.border}`,
    color: tone.color,
    whiteSpace: "nowrap",
  };
}

function MissionReadinessEvidencePanel(props: {
  title: string;
  readiness?: MissionReadinessSummary;
  keyPrefix: string;
  criterionLimit?: number;
  evidenceLimit?: number;
  showCriteriaBadges?: boolean;
  detailCards?: boolean;
  marginTop?: number;
}): React.ReactElement | null {
  const readiness = props.readiness;
  if (!readiness) return null;

  const presentation = presentMissionReadinessCriteria(readiness, props.criterionLimit ?? 3);
  const criteria = readiness.criteria ?? [];
  const evidenceLimit = props.evidenceLimit ?? 4;
  const blockedCriteriaIds = readiness.blocked_criteria_ids ?? [];
  const attentionCriteriaIds = readiness.attention_criteria_ids ?? [];
  const reviewCriteriaIds = readiness.review_criteria_ids ?? [];

  return (
    <div
      style={{
        border: `1px solid ${THEME.panelBorder}`,
        borderRadius: 10,
        padding: 10,
        background: "#121212",
        marginTop: props.marginTop ?? 10,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: props.detailCards ? "center" : "flex-start",
          justifyContent: "space-between",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>{props.title}</div>
          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
            {readiness.stage || "Stage 3 - Missions"}
            {typeof readiness.satisfied === "number" && typeof readiness.total === "number"
              ? ` / ${readiness.satisfied}/${readiness.total} criteria`
              : ""}
          </div>
        </div>
        {readiness.status ? <span style={badgeStyle(readiness.status)}>{readiness.status}</span> : null}
      </div>
      {readiness.next_action ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{readiness.next_action}</div> : null}
      {blockedCriteriaIds.length ? (
        <div style={{ fontSize: 10, color: "#cce7e2", marginTop: 6 }}>
          blockers=<code>{blockedCriteriaIds.join(", ")}</code>
          {attentionCriteriaIds.length ? (
            <>
              {" / "}attention=<code>{attentionCriteriaIds.join(", ")}</code>
            </>
          ) : null}
          {reviewCriteriaIds.length ? (
            <>
              {" / "}review=<code>{reviewCriteriaIds.join(", ")}</code>
            </>
          ) : null}
        </div>
      ) : null}
      {props.showCriteriaBadges && criteria.length ? (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
          {criteria.map((criterion, index) => (
            <span
              key={`${props.keyPrefix}-badge-${criterion.id || criterion.label || index}`}
              style={badgeStyle(criterion.status || "unknown")}
            >
              {criterion.label || criterion.id || "criterion"}: {criterion.status || "unknown"}
            </span>
          ))}
        </div>
      ) : null}
      {presentation.visible.length ? (
        <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
          {presentation.visible.map((criterion) => {
            const evidenceLines = missionReadinessEvidenceLines(criterion, evidenceLimit);
            const label = criterion.label || criterion.id || "criterion";
            const status = criterion.status || "unknown";
            const key = `${props.keyPrefix}-detail-${criterion.id || criterion.label}`;

            if (!props.detailCards) {
              return (
                <div key={key} style={{ fontSize: 11 }}>
                  <span style={badgeStyle(status)}>{status}</span> <span style={{ color: "#f1f1f1" }}>{label}</span>
                  {evidenceLines.length ? (
                    <div style={{ fontSize: 10, color: "#cce7e2", marginTop: 4 }}>
                      evidence: <code>{evidenceLines.join(" / ")}</code>
                    </div>
                  ) : null}
                </div>
              );
            }

            return (
              <div
                key={key}
                style={{
                  border: `1px solid ${THEME.panelBorder}`,
                  borderRadius: 8,
                  padding: 8,
                  background: "#0f0f0f",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                  <div style={{ fontSize: 11, fontWeight: 600 }}>{label}</div>
                  <span style={badgeStyle(status)}>{status}</span>
                </div>
                {criterion.detail ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 5 }}>{criterion.detail}</div> : null}
                {evidenceLines.length ? (
                  <div style={{ fontSize: 10, color: "#cce7e2", marginTop: 5 }}>
                    evidence: <code>{evidenceLines.join(" / ")}</code>
                  </div>
                ) : null}
              </div>
            );
          })}
          {presentation.hiddenTotal > 0 ? (
            <div style={{ fontSize: 10, color: THEME.muted }}>
              Hidden readiness criteria: <code>{String(presentation.hiddenTotal)}</code>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

type RecoveryFollowthroughLike = {
  replacement_mission_id?: string;
  replacement_status?: string;
  replacement_objective?: string;
  replacement_next_step?: string;
  replacement_last_task_id?: string;
  replacement_last_task_status?: string;
  replacement_updated_at?: string;
  replacement_terminal?: boolean;
  replacement_error?: string;
};

function MissionRecoveryFollowthroughCard(props: {
  recovery?: RecoveryFollowthroughLike | null;
  onOpenMission?: (missionId: string) => void;
}): React.ReactElement | null {
  const replacementId = safeString(props.recovery?.replacement_mission_id).trim();
  if (!replacementId) return null;

  const status = safeString(props.recovery?.replacement_status).trim();
  const objective = safeString(props.recovery?.replacement_objective).trim();
  const nextStep = safeString(props.recovery?.replacement_next_step).trim();
  const lastTaskId = safeString(props.recovery?.replacement_last_task_id).trim();
  const lastTaskStatus = safeString(props.recovery?.replacement_last_task_status).trim();
  const updatedAt = mixedLocaleTime(props.recovery?.replacement_updated_at);
  const error = safeString(props.recovery?.replacement_error).trim();

  return (
    <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#111819", marginTop: 8 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <div style={{ fontSize: 11, fontWeight: 600 }}>Replacement follow-through</div>
        {status ? <span style={badgeStyle(status)}>{status}</span> : null}
      </div>
      <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>
        replacement=<code>{replacementId}</code>
        {lastTaskId ? (
          <>
            {" / "}last_task=<code>{lastTaskId}</code>
          </>
        ) : null}
        {lastTaskStatus ? (
          <>
            {" / "}task_status=<code>{lastTaskStatus}</code>
          </>
        ) : null}
        {updatedAt ? (
          <>
            {" / "}updated=<code>{updatedAt}</code>
          </>
        ) : null}
        {props.recovery?.replacement_terminal ? (
          <>
            {" / "}terminal=<code>true</code>
          </>
        ) : null}
      </div>
      {objective ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{truncateText(objective, 180)}</div> : null}
      {error ? (
        <div style={{ fontSize: 11, color: "#ffb0b0", marginTop: 4 }}>
          replacement_error=<code>{error}</code>
        </div>
      ) : null}
      {nextStep ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{nextStep}</div> : null}
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
        <button style={buttonStyle} onClick={() => props.onOpenMission?.(replacementId)} disabled={!props.onOpenMission}>
          Open replacement
        </button>
      </div>
    </div>
  );
}

function summaryCardStyle(): React.CSSProperties {
  return {
    border: `1px solid ${THEME.panelBorder}`,
    borderRadius: 12,
    padding: 10,
    background: "#101010",
  };
}

function prettyData(value: unknown): string {
  if (value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

type ApprovalProjectionLike = ApprovalItem | WorldStateApprovalSummary;

function approvalProjectionTitle(item: ApprovalProjectionLike | null | undefined): string {
  const requestedAction = safeString(item?.payload_summary?.requested_action).trim();
  if (requestedAction) return requestedAction;
  const action = safeString(item?.action).trim();
  if (action) return action;
  const requestKind = safeString(item?.request_kind).trim();
  if (requestKind) return requestKind;
  return "Pending approval";
}

function approvalProjectionFactLine(item: ApprovalProjectionLike | null | undefined): string {
  const summary = item?.payload_summary;
  const facts: string[] = [];
  const requestKind = safeString(item?.request_kind).trim();
  if (requestKind) facts.push(requestKind);
  if (safeString(summary?.plugin_id).trim()) {
    facts.push(`plugin ${safeString(summary?.plugin_id).trim()}`);
  } else if (safeString(summary?.scope_id).trim()) {
    facts.push(`scope ${safeString(summary?.scope_id).trim()}`);
  } else if (safeString(summary?.target_id).trim()) {
    facts.push(`${safeString(summary?.target_kind).trim() || "target"} ${safeString(summary?.target_id).trim()}`);
  } else if (safeString(summary?.credential_id).trim()) {
    facts.push(`credential ${safeString(summary?.credential_id).trim()}`);
  } else if (safeString(summary?.url).trim()) {
    facts.push(safeString(summary?.url).trim());
  } else if (safeString(summary?.domain).trim()) {
    facts.push(safeString(summary?.domain).trim());
  }
  const risk = safeString(summary?.risk_tier).trim() || safeString(summary?.risk).trim();
  if (risk) facts.push(`risk ${risk}`);
  if (typeof summary?.required_trust === "number") facts.push(`trust ${summary.required_trust}`);
  return facts.filter(Boolean).slice(0, 4).join(" · ");
}

function approvalProjectionExactActionLine(item: ApprovalProjectionLike | null | undefined): string {
  const summary = item?.payload_summary;
  const details: string[] = [];
  if (Array.isArray(summary?.input_keys) && summary.input_keys.length > 0) {
    details.push(`input ${summary.input_keys.join(", ")}`);
  }
  if (Array.isArray(summary?.params_keys) && summary.params_keys.length > 0) {
    details.push(`params ${summary.params_keys.join(", ")}`);
  }
  if (typeof summary?.enabled === "boolean") {
    details.push(`enabled ${summary.enabled ? "on" : "off"}`);
  }
  if (typeof summary?.dry_run === "boolean") {
    details.push(`dry run ${summary.dry_run ? "yes" : "no"}`);
  }
  return details.slice(0, 4).join(" · ");
}

function approvalProjectionLineage(item: ApprovalProjectionLike | null | undefined): string {
  const previousApprovalId = safeString(item?.previous_approval_id).trim();
  if (!previousApprovalId) return "";
  const previousStatus = safeString(item?.previous_approval_status).trim();
  return previousStatus ? `refresh of ${previousApprovalId} (${previousStatus})` : `refresh of ${previousApprovalId}`;
}

function approvalProjectionReplacementLine(item: ApprovalProjectionLike | null | undefined): string {
  const kind = safeString(item?.replacement_kind).trim();
  const reason = safeString(item?.replacement_reason).trim();
  const changedKeys = Array.isArray(item?.replacement_changed_keys)
    ? item.replacement_changed_keys.map((key) => safeString(key).trim()).filter(Boolean)
    : [];
  if (!kind && !reason && changedKeys.length === 0) return "";
  const parts: string[] = [];
  if (kind) parts.push(`kind ${kind}`);
  if (reason) parts.push(reason);
  if (changedKeys.length > 0) parts.push(`changed ${changedKeys.join(", ")}`);
  return parts.join(" · ");
}

function approvalProjectionReplacementScopeLine(item: ApprovalProjectionLike | null | undefined): string {
  const expectedKeys = Array.isArray(item?.replacement_expected_payload_keys)
    ? item.replacement_expected_payload_keys.map((key) => safeString(key).trim()).filter(Boolean)
    : [];
  const previousKeys = Array.isArray(item?.replacement_previous_payload_keys)
    ? item.replacement_previous_payload_keys.map((key) => safeString(key).trim()).filter(Boolean)
    : [];
  if (expectedKeys.length === 0 && previousKeys.length === 0) return "";
  const parts: string[] = [];
  if (expectedKeys.length > 0) parts.push(`expected keys ${expectedKeys.join(", ")}`);
  if (previousKeys.length > 0) parts.push(`previous keys ${previousKeys.join(", ")}`);
  return parts.join(" · ");
}

function approvalProjectionLoopLine(item: ApprovalProjectionLike | null | undefined): string {
  const missionId = safeString(item?.mission_id).trim();
  const operationId = safeString(item?.operation_id).trim();
  const gate = safeString(item?.gate).trim();
  const nextStep = safeString(item?.next_step).trim();
  const operationStatus = safeString(item?.operation_status).trim();
  const resultStatus = safeString(item?.operation_result_status).trim();
  const traceId = safeString(item?.trace_id).trim();
  const runId = safeString(item?.run_id).trim();
  const parts: string[] = [];
  if (missionId) parts.push(`mission ${missionId}`);
  if (operationId) parts.push(`task ${operationId}`);
  if (gate) parts.push(`gate ${gate}`);
  if (nextStep) parts.push(`next ${nextStep}`);
  if (operationStatus || resultStatus) {
    parts.push(`status ${[operationStatus, resultStatus].filter(Boolean).join("/")}`);
  }
  if (traceId) parts.push(`trace ${traceId}`);
  if (runId) parts.push(`run ${runId}`);
  return parts.slice(0, 6).join(" · ");
}

function approvalProjectionPlanLine(item: ApprovalProjectionLike | null | undefined): string {
  const planStatus = safeString(item?.plan_status).trim();
  const currentStepId = safeString(item?.plan_current_step_id).trim();
  const currentStepTitle = safeString(item?.plan_current_step_title).trim();
  const stepCount =
    typeof item?.plan_step_count === "number" && Number.isFinite(item.plan_step_count)
      ? item.plan_step_count
      : undefined;
  const checkpointCount =
    typeof item?.plan_checkpoint_count === "number" && Number.isFinite(item.plan_checkpoint_count)
      ? item.plan_checkpoint_count
      : undefined;
  const parts: string[] = [];
  if (planStatus) parts.push(`status ${planStatus}`);
  if (currentStepId) parts.push(`step ${currentStepId}`);
  if (currentStepTitle) parts.push(`title ${currentStepTitle}`);
  if (stepCount !== undefined) parts.push(`steps ${stepCount}`);
  if (checkpointCount !== undefined) parts.push(`checkpoints ${checkpointCount}`);
  return parts.join(" · ");
}

function approvalProjectionDetail(item: ApprovalProjectionLike | null | undefined): string {
  const factLine = approvalProjectionFactLine(item);
  if (factLine) return factLine;
  const reason = safeString(item?.reason).trim();
  if (reason) return reason;
  return "A governed action is queued and waiting for operator review.";
}

function parseJsonObjectInput(value: string): { ok: true; parsed: Record<string, unknown> } | { ok: false; error: string } {
  const trimmed = safeString(value).trim();
  if (!trimmed) {
    return { ok: true, parsed: {} };
  }
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (!isRecord(parsed)) {
      return { ok: false, error: "Request input must be a JSON object." };
    }
    return { ok: true, parsed };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? `Request input is invalid JSON: ${err.message}` : "Request input is invalid JSON.",
    };
  }
}

function parseDelimitedIds(value: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of safeString(value).split(/[\n,]+/)) {
    const cleaned = item.trim();
    if (!cleaned || seen.has(cleaned)) continue;
    seen.add(cleaned);
    out.push(cleaned);
  }
  return out;
}

type ApprovalInspection = {
  domain: string;
  risk: string;
  scopeLabel: string;
  scopeItems: string[];
  evidenceItems: string[];
  approveEffect: string;
  denyEffect: string;
  missionRelation: string;
  missionId: string;
  operationId: string;
};

type ApprovalReturnContext = {
  missionId?: string;
  operationId?: string;
  source?: string;
  reviewKind?: string;
  reviewReason?: string;
  changedKeys?: string[];
};

function approvalPayload(item: ApprovalItem | null | undefined): Record<string, unknown> {
  return isRecord(item?.payload) ? item.payload : {};
}

function approvalTextField(payload: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = safeString(payload[key]).trim();
    if (value) return value;
  }
  return "";
}

function approvalActionField(payload: Record<string, unknown>, fallback: string): string {
  return approvalTextField(payload, "action", "name") || fallback;
}

function approvalContextField(item: ApprovalProjectionLike | null | undefined, ...keys: string[]): string {
  const payload = approvalPayload(item as ApprovalItem | null | undefined);
  const input = isRecord(payload.input) ? payload.input : {};
  const payloadMeta = isRecord(payload.meta) ? payload.meta : {};
  const inputMeta = isRecord(input.meta) ? input.meta : {};
  const itemFields = isRecord(item) ? item : {};
  const sources = [itemFields, payload, payloadMeta, input, inputMeta];
  for (const source of sources) {
    const value = approvalTextField(source, ...keys);
    if (value) return value;
  }
  return "";
}

function inspectApproval(item: ApprovalItem | null | undefined): ApprovalInspection {
  const payload = approvalPayload(item);
  const meta = isRecord(payload.meta) ? payload.meta : {};
  const summary = item?.payload_summary;
  const action = safeString(item?.action).trim().toLowerCase();
  const requestAction =
    safeString(summary?.requested_action).trim() ||
    approvalActionField(payload, safeString(item?.action).trim() || "requested action");
  const missionId = approvalContextField(item, "mission_id");
  const operationId = approvalContextField(item, "operation_id", "task_id");
  const risk =
    safeString(summary?.risk_tier).trim() ||
    safeString(summary?.risk).trim() ||
    approvalTextField(payload, "risk", "risk_tier") ||
    approvalTextField(meta, "risk", "risk_tier") ||
    safeString(item?.risk).trim() ||
    "unknown";
  const domain =
    safeString(summary?.domain).trim() ||
    safeString(summary?.provider).trim() ||
    approvalTextField(payload, "domain", "provider") ||
    safeString(item?.domain).trim() ||
    (action.includes(".") ? action.split(".", 1)[0] : action || "approval");

  const scopeItems: string[] = [];
  const pushScope = (label: string, value: string) => {
    const cleaned = value.trim();
    const entry = cleaned ? `${label}: ${cleaned}` : "";
    if (entry && !scopeItems.includes(entry)) scopeItems.push(entry);
  };

  pushScope("Plugin", safeString(summary?.plugin_id).trim() || approvalTextField(payload, "plugin_id"));
  pushScope("Scope", safeString(summary?.scope_id).trim() || approvalTextField(payload, "scope_id", "scope"));
  const targetKind = safeString(summary?.target_kind).trim() || approvalTextField(payload, "target_kind");
  const targetId =
    safeString(summary?.target_id).trim() ||
    safeString(summary?.twin_id).trim() ||
    approvalTextField(payload, "target_id", "twin_id", "validation_id");
  if (targetKind || targetId) {
    pushScope("Target", [targetKind, targetId].filter(Boolean).join(":"));
  }
  pushScope("Credential", safeString(summary?.credential_id).trim() || approvalTextField(payload, "credential_id", "id"));
  pushScope("Provider", safeString(summary?.provider).trim() || approvalTextField(payload, "provider"));
  pushScope("URL", safeString(summary?.url).trim() || approvalTextField(payload, "url"));
  pushScope("Domain", safeString(summary?.domain).trim() || approvalTextField(payload, "domain"));
  pushScope("Record", approvalTextField(payload, "record_id", "request_id"));
  pushScope("Mission", missionId);
  pushScope("Task", operationId);

  const scopeLabel = scopeItems[0] || `Domain: ${domain}`;

  const evidenceItems: string[] = [];
  const pushEvidence = (label: string, value: string) => {
    const cleaned = value.trim();
    const entry = cleaned ? `${label}: ${cleaned}` : "";
    if (entry && !evidenceItems.includes(entry)) evidenceItems.push(entry);
  };

  pushEvidence("Requested action", requestAction);
  pushEvidence("Request kind", safeString(item?.request_kind).trim());
  pushEvidence("Reason", safeString(item?.reason).trim());
  pushEvidence(
    "Required trust",
    typeof summary?.required_trust === "number" ? String(summary.required_trust) : approvalTextField(payload, "required_trust"),
  );
  pushEvidence("Credential type", safeString(summary?.credential_type).trim() || approvalTextField(payload, "type"));
  pushEvidence("Label", safeString(summary?.label).trim() || approvalTextField(payload, "label"));
  pushEvidence("Actor", safeString(summary?.actor).trim() || approvalTextField(payload, "actor"));
  pushEvidence(
    "Enabled change",
    typeof summary?.enabled === "boolean" ? String(summary.enabled) : typeof payload.enabled === "boolean" ? String(payload.enabled) : "",
  );
  pushEvidence("Dry run", typeof summary?.dry_run === "boolean" ? String(summary.dry_run) : "");
  pushEvidence("Idempotency key", approvalTextField(payload, "idempotency_key"));
  pushEvidence("Replacement reason", safeString(item?.replacement_reason).trim());
  if (Array.isArray(item?.replacement_expected_payload_keys) && item.replacement_expected_payload_keys.length > 0) {
    evidenceItems.push(`Expected payload keys: ${item.replacement_expected_payload_keys.join(", ")}`);
  }
  if (Array.isArray(item?.replacement_previous_payload_keys) && item.replacement_previous_payload_keys.length > 0) {
    evidenceItems.push(`Previous payload keys: ${item.replacement_previous_payload_keys.join(", ")}`);
  }
  if (Array.isArray(item?.replacement_changed_keys) && item.replacement_changed_keys.length > 0) {
    evidenceItems.push(`Changed payload keys: ${item.replacement_changed_keys.join(", ")}`);
  }
  if (Array.isArray(summary?.input_keys) && summary.input_keys.length > 0) {
    evidenceItems.push(`Input keys: ${summary.input_keys.join(", ")}`);
  }
  if (Array.isArray(summary?.params_keys) && summary.params_keys.length > 0) {
    evidenceItems.push(`Params keys: ${summary.params_keys.join(", ")}`);
  }
  if (isRecord(payload.params) && Object.keys(payload.params).length > 0) {
    evidenceItems.push(`Params: ${Object.keys(payload.params).length} recorded field(s)`);
  }
  if (Object.keys(meta).length > 0) {
    evidenceItems.push(`Meta: ${Object.keys(meta).length} recorded field(s)`);
  }

  let approveEffect = "Approving allows the recorded action to proceed within the payload that was submitted for review.";
  let denyEffect = "Rejecting keeps the action blocked and requires a narrower or replacement request.";
  let missionRelation = "This pending approval is one of the governed blockers surfaced in the ORB mission feed.";

  if (action === "plugin.run") {
    approveEffect = `Approving allows plugin ${approvalTextField(payload, "plugin_id") || "unknown"} to run action ${requestAction}.`;
    denyEffect = "Rejecting keeps the plugin action blocked until a new approval is requested or scope is narrowed.";
    missionRelation = "Plugin execution remains parked in continuity briefing until this decision is resolved.";
  } else if (action === "industrial.intervention.execute" || action === "industrial.intervention") {
    approveEffect = `Approving allows industrial action ${requestAction} against ${[targetKind, targetId].filter(Boolean).join(":") || "the recorded target"}.`;
    denyEffect = "Rejecting prevents the requested intervention from executing against the target.";
    missionRelation = "This approval gates a real-world intervention path, so it should stay reviewable and visible.";
  } else if (action === "industrial.safety.validate") {
    approveEffect = `Approving allows high-risk validation for ${[targetKind, targetId].filter(Boolean).join(":") || "the recorded target"}.`;
    denyEffect = "Rejecting keeps the high-risk validation from proceeding.";
    missionRelation = "This validation remains a mission blocker until the operator accepts or denies the request.";
  } else if (action === "industrial.digital_twin.action") {
    approveEffect = `Approving allows digital twin action ${requestAction} for ${approvalTextField(payload, "twin_id") || "the recorded twin"}.`;
    denyEffect = "Rejecting prevents the twin action from being applied.";
    missionRelation = "This approval controls a simulated action path, which should remain visible alongside mission progress.";
  } else if (action === "credential.request") {
    approveEffect = `Approving allows credential issuance for scope ${approvalTextField(payload, "scope_id") || "unknown"} and provider ${approvalTextField(payload, "provider") || "unknown"}.`;
    denyEffect = "Rejecting prevents the credential request from being fulfilled.";
    missionRelation = "Credential access remains a dependency blocker until the request is reviewed.";
  } else if (action === "credential.revoke") {
    approveEffect = `Approving allows revocation of credential ${approvalTextField(payload, "id") || "unknown"}.`;
    denyEffect = "Rejecting leaves the credential in place and clears the pending revocation path.";
    missionRelation = "This request changes trust posture, so the approval should remain tied to continuity state.";
  } else if (action === "web_learning.request") {
    approveEffect = `Approving allows web learning to fetch and ingest ${approvalTextField(payload, "url") || approvalTextField(payload, "domain") || "the recorded source"}.`;
    denyEffect = "Rejecting keeps the learn request from running until the source or policy scope changes.";
    missionRelation = "Learning remains paused in the mission feed until the operator resolves this request.";
  } else if (action === "web_learning.set_enabled") {
    approveEffect = `Approving applies the requested web learning enabled state (${String(payload.enabled)}).`;
    denyEffect = "Rejecting keeps web learning at its current enabled state.";
    missionRelation = "This governs a capability toggle, so it affects future mission continuity rather than a single task.";
  } else if (action === "web_learning.quarantine.delete") {
    approveEffect = `Approving allows deletion of quarantine item ${approvalTextField(payload, "id") || "unknown"}.`;
    denyEffect = "Rejecting keeps the quarantine item in place for continued review.";
    missionRelation = "The quarantined artifact remains visible as an incident/continuity item until resolved.";
  }

  return {
    domain,
    risk,
    scopeLabel,
    scopeItems,
    evidenceItems,
    approveEffect,
    denyEffect,
    missionRelation,
    missionId,
    operationId,
  };
}

function operationStatus(record: OperationRecord | null | undefined): string {
  return safeString(record?.status).trim().toLowerCase() || "unknown";
}

function operationLabel(record: OperationRecord | null | undefined): string {
  return operationMetaString(record, "objective") || safeString(record?.name).trim() || safeString(record?.id).trim() || "operation";
}

function operationAssignedTo(record: OperationRecord | null | undefined): string {
  return operationMetaString(record, "assigned_to", "unassigned");
}

function operationPlane(record: OperationRecord | null | undefined): string {
  return operationMetaString(record, "orb_plane");
}

function operationMessage(record: OperationRecord | null | undefined): string {
  return (
    safeString(record?.error).trim() ||
    operationMetaString(record, "result_message") ||
    operationMetaString(record, "note") ||
    ""
  );
}

type TelemetryPosture = {
  label: string;
  tone: string;
  scopeLabel: string;
  detail: string;
  voiceLabel: string;
  proactiveLabel: string;
};

type ContinuationPosture = {
  label: string;
  tone: string;
  detail: string;
};

function describeTelemetry(settings: UiSettings): TelemetryPosture {
  const voiceLabel = settings.voiceEnabled ? "Voice enabled" : "Voice silent";
  const proactiveLabel = settings.proactive ? "Proactive enabled" : "Proactive manual";

  if (settings.sensingMode === "camera_mic") {
    return {
      label: "Telemetry Armed",
      tone: "warning",
      scopeLabel: "Camera + mic",
      detail: "Camera and mic scope are configured in settings. This build shows approved posture here; it does not claim hidden live capture by itself.",
      voiceLabel,
      proactiveLabel,
    };
  }

  if (settings.sensingMode === "input_only") {
    return {
      label: "Telemetry Armed",
      tone: "ready",
      scopeLabel: "Keyboard + mouse",
      detail: "Input telemetry is configured for keyboard and mouse scope. This is a visible configuration surface, not a claim of unattended capture.",
      voiceLabel,
      proactiveLabel,
    };
  }

  return {
    label: "Telemetry Dormant",
    tone: "dormant",
    scopeLabel: "Text only",
    detail: "No ambient sensing is configured. Francis is operating through explicit text input only.",
    voiceLabel,
    proactiveLabel,
  };
}

function describeContinuation(mode: OperatorModeSnapshot | null): ContinuationPosture {
  const controlModeId = safeString(mode?.control_mode?.id).trim().toLowerCase();
  const backlog = mode?.backlog;
  const pendingApprovals = safeNumber(backlog?.pending_approvals, 0);
  const approvalPendingTasks = safeNumber(backlog?.approval_pending_tasks, 0);
  const blockedTasks = safeNumber(backlog?.blocked_tasks, 0);
  const queuedTasks = safeNumber(backlog?.queued_tasks, 0);
  const runningTasks = safeNumber(backlog?.running_tasks, 0);

  if (controlModeId === "pilot" && runningTasks > 0) {
    return {
      label: "Delegated Execution",
      tone: "running",
      detail: `${runningTasks} delegated ${runningTasks === 1 ? "task is" : "tasks are"} actively executing under Pilot posture.`,
    };
  }
  if (controlModeId === "pilot") {
    return {
      label: "Pilot Standing By",
      tone: "pilot_active",
      detail: "Pilot is declared and visible, but no live delegated run is currently recorded.",
    };
  }
  if (controlModeId === "away" && runningTasks + queuedTasks + blockedTasks + approvalPendingTasks + pendingApprovals > 0) {
    return {
      label: "Actively Continuing",
      tone: "away_active",
      detail: "Away continuation is active with governed work still running, queued, or waiting on review.",
    };
  }
  if (controlModeId === "away") {
    return {
      label: "Away Standby",
      tone: "away_active",
      detail: "Away is declared, but no active continuation work is currently moving.",
    };
  }
  if (pendingApprovals > 0 || approvalPendingTasks > 0) {
    const total = pendingApprovals + approvalPendingTasks;
    return {
      label: "Waiting For Input",
      tone: "needs_approval",
      detail: `${total} governed ${total === 1 ? "item is" : "items are"} waiting for operator review or approval.`,
    };
  }
  if (blockedTasks > 0 || controlModeId === "observe") {
    return {
      label: "Constrained By Mode",
      tone: "blocked",
      detail:
        controlModeId === "observe"
          ? "Observe keeps Francis read-only. The console is visible, but write authority remains blocked."
          : `${blockedTasks} ${blockedTasks === 1 ? "task is" : "tasks are"} blocked by current policy or trust constraints.`,
    };
  }
  if (runningTasks > 0) {
    return {
      label: "Active Execution",
      tone: "running",
      detail: `${runningTasks} ${runningTasks === 1 ? "task is" : "tasks are"} currently running through the execution plane.`,
    };
  }
  if (queuedTasks > 0) {
    return {
      label: "Ready Queue",
      tone: "queued",
      detail: `${queuedTasks} ${queuedTasks === 1 ? "task is" : "tasks are"} queued and ready for execution.`,
    };
  }
  return {
    label: "Ready",
    tone: "ready",
    detail: "No governed backlog is currently visible. Francis is ready for the next operator request.",
  };
}

type FeedFreshnessState = "live" | "stale" | "degraded" | "unavailable";

function nowUnixSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function formatAgeLabel(ageSeconds: number): string {
  const age = Math.max(0, Math.floor(ageSeconds));
  if (age < 60) return `${age}s old`;
  if (age < 3600) return `${Math.floor(age / 60)}m old`;
  if (age < 86_400) return `${Math.floor(age / 3600)}h old`;
  return `${Math.floor(age / 86_400)}d old`;
}

function deriveFeedFreshness(
  observedAt: number | null | undefined,
  nowTs: number,
  opts?: { error?: string | null; staleAfterSeconds?: number },
): { state: FeedFreshnessState; ageLabel: string } {
  if (!observedAt) {
    return {
      state: "unavailable",
      ageLabel: "No snapshot",
    };
  }

  const ageSeconds = Math.max(0, nowTs - observedAt);
  if (opts?.error) {
    return {
      state: "degraded",
      ageLabel: formatAgeLabel(ageSeconds),
    };
  }
  if (ageSeconds > safeNumber(opts?.staleAfterSeconds, 180)) {
    return {
      state: "stale",
      ageLabel: formatAgeLabel(ageSeconds),
    };
  }
  return {
    state: "live",
    ageLabel: formatAgeLabel(ageSeconds),
  };
}

function loadSettings(): UiSettings {
  try {
    const raw = localStorage.getItem("francis_ui_settings");
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<UiSettings>;
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function saveSettings(settings: UiSettings): void {
  try {
    localStorage.setItem("francis_ui_settings", JSON.stringify(settings));
  } catch {
    // ignore
  }
}

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem("francis_ui_sessions");
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatSession[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: ChatSession[]): void {
  try {
    localStorage.setItem("francis_ui_sessions", JSON.stringify(sessions));
  } catch {
    // ignore
  }
}

function createSession(): ChatSession {
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now());
  return { id, title: "New chat", messages: [], updatedTs: Date.now() };
}

function summarizeTitle(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "New chat";
  const short = trimmed.length > 48 ? `${trimmed.slice(0, 48)}.` : trimmed;
  return short.replace(/\s+/g, " ");
}

function pickAutoFemaleVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  if (!voices.length) return undefined;
  const preferred = voices.find((v) => /female|zira|susan|samantha|karen|victoria/i.test(v.name));
  return preferred ?? voices[0];
}

function useWindowWidth(): number {
  const [width, setWidth] = useState(() => window.innerWidth);
  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return width;
}
function ChatPanel(props: {
  baseUrl: string;
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  onSend: (text: string) => void;
  onOpenMission: (missionId: string) => void;
  onSpeak: (text: string) => void;
}) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const lastSpokenIdx = useRef(-1);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [props.messages]);

  useEffect(() => {
    const lastIdx = props.messages.length - 1;
    if (lastIdx <= lastSpokenIdx.current) return;
    const msg = props.messages[lastIdx];
    if (msg.role !== "assistant") return;
    lastSpokenIdx.current = lastIdx;
    props.onSpeak(msg.content);
  }, [props.messages, props.onSpeak]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "100%" }}>
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflow: "auto",
          padding: "8px 4px 8px 0",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {props.messages.length === 0 ? (
          <div style={{ color: THEME.muted, marginTop: 24 }}>
            Start a conversation. Francis will respond in the main window.
          </div>
        ) : null}
        {props.messages.map((m, idx) => {
          const isUser = m.role === "user";
          const missionSurface = isUser ? null : chatMissionSurface(m);
          return (
            <div
              key={`${m.role}-${idx}`}
              style={{
                alignSelf: isUser ? "flex-end" : "flex-start",
                maxWidth: "78%",
                background: isUser ? THEME.userBubble : THEME.assistantBubble,
                border: `1px solid ${THEME.panelBorder}`,
                borderRadius: 16,
                padding: "12px 14px",
                lineHeight: 1.45,
              }}
            >
              <div style={{ fontSize: 12, color: THEME.muted, marginBottom: 6 }}>
                {isUser ? "You" : "Francis"}
              </div>
              <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
              {missionSurface ? (
                <div
                  style={{
                    marginTop: 10,
                    paddingTop: 10,
                    borderTop: `1px solid ${THEME.panelBorder}`,
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <span style={badgeStyle(missionSurface.status || "mission")}>
                      {missionSurface.status || "mission"}
                    </span>
                    {missionSurface.activeStage ? (
                      <span style={badgeStyle(missionSurface.activeStage)}>{missionSurface.activeStage}</span>
                    ) : null}
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted }}>
                    Mission <code>{missionSurface.missionId}</code>
                    {missionSurface.operationId ? (
                      <>
                        {" / "}task <code>{missionSurface.operationId}</code>
                      </>
                    ) : null}
                    {missionSurface.nextStep ? ` / ${missionSurface.nextStep}` : ""}
                  </div>
                  <button
                    style={{ ...buttonStyle, alignSelf: "flex-start", fontSize: 11, padding: "6px 8px" }}
                    onClick={() => props.onOpenMission(missionSurface.missionId)}
                  >
                    Open mission flow
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      {props.error ? (
        <div
          style={{
            border: `1px solid ${THEME.errorBorder}`,
            background: THEME.errorBg,
            padding: 10,
            borderRadius: 10,
            color: "#ffaaaa",
            fontSize: 12,
          }}
        >
          <b>Error:</b> {props.error}
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              props.onSend(input);
              setInput("");
            }
          }}
          placeholder="Message Francis"
          style={{ ...inputStyle, flex: 1 }}
        />
        <button
          onClick={() => {
            props.onSend(input);
            setInput("");
          }}
          disabled={props.busy}
          style={buttonStyle}
        >
          {props.busy ? "Working." : "Send"}
        </button>
      </div>
      <div style={{ fontSize: 11, color: THEME.muted }}>
        API: <code>{props.baseUrl}</code>
      </div>
    </div>
  );
}

function SettingsPanel(props: { settings: UiSettings; onChange: (next: UiSettings) => void }) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    const load = () => setVoices(window.speechSynthesis.getVoices());
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);

  const hasVoices = voices.length > 0;

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Settings</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>Behavior, sensing, and voice.</div>

      <div style={{ display: "grid", gap: 12, marginTop: 16 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={props.settings.proactive}
            onChange={(e) => props.onChange({ ...props.settings, proactive: e.target.checked })}
          />
          Proactive mode (speak only when it adds value)
        </label>

        <div>
          <div style={{ fontSize: 12, marginBottom: 6, color: THEME.muted }}>Sensing mode</div>
          <select
            value={props.settings.sensingMode}
            onChange={(e) => props.onChange({ ...props.settings, sensingMode: e.target.value as SensingMode })}
            style={{
              padding: "6px 8px",
              borderRadius: 6,
              border: `1px solid ${THEME.inputBorder}`,
              background: THEME.inputBg,
              color: THEME.text,
            }}
          >
            <option value="text_only">Text only</option>
            <option value="input_only">Input only (keyboard/mouse)</option>
            <option value="camera_mic">Camera + mic</option>
          </select>
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={props.settings.voiceEnabled}
            onChange={(e) => props.onChange({ ...props.settings, voiceEnabled: e.target.checked })}
          />
          Voice enabled (assistant replies)
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={props.settings.voiceAutoFemale}
            onChange={(e) => props.onChange({ ...props.settings, voiceAutoFemale: e.target.checked })}
            disabled={!props.settings.voiceEnabled}
          />
          Auto-pick a soft female voice
        </label>

        <div>
          <div style={{ fontSize: 12, marginBottom: 6, color: THEME.muted }}>Voice</div>
          <select
            value={props.settings.voiceUri}
            onChange={(e) => props.onChange({ ...props.settings, voiceUri: e.target.value, voiceAutoFemale: false })}
            disabled={!props.settings.voiceEnabled || !hasVoices}
            style={{
              padding: "6px 8px",
              borderRadius: 6,
              border: `1px solid ${THEME.inputBorder}`,
              minWidth: 260,
              background: THEME.inputBg,
              color: THEME.text,
            }}
          >
            <option value="">Auto</option>
            {voices.map((v) => (
              <option key={v.voiceURI} value={v.voiceURI}>
                {v.name} ({v.lang})
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            Rate
            <input
              type="number"
              step="0.1"
              min="0.5"
              max="2"
              value={props.settings.voiceRate}
              onChange={(e) =>
                props.onChange({ ...props.settings, voiceRate: clamp01(parseFloat(e.target.value) || 1.0) })
              }
              style={{
                width: 80,
                padding: "4px 6px",
                borderRadius: 6,
                border: `1px solid ${THEME.inputBorder}`,
                background: THEME.inputBg,
                color: THEME.text,
              }}
              disabled={!props.settings.voiceEnabled}
            />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}
          >
            Pitch
            <input
              type="number"
              step="0.1"
              min="0.5"
              max="2"
              value={props.settings.voicePitch}
              onChange={(e) =>
                props.onChange({ ...props.settings, voicePitch: clamp01(parseFloat(e.target.value) || 1.0) })
              }
              style={{
                width: 80,
                padding: "4px 6px",
                borderRadius: 6,
                border: `1px solid ${THEME.inputBorder}`,
                background: THEME.inputBg,
                color: THEME.text,
              }}
              disabled={!props.settings.voiceEnabled}
            />
          </label>
        </div>
      </div>
    </section>
  );
}

function OperatorModeBanner(props: {
  mode: OperatorModeSnapshot | null;
  error: string | null;
  busy: boolean;
  onOpenApprovals: () => void;
  onOpenOperations: () => void;
  onOpenOrb: () => void;
  onSetControlMode: (modeId: OperatorControlModeId) => void;
}) {
  const environment = props.mode?.environment;
  const posture = props.mode?.posture;
  const controlMode = props.mode?.control_mode;
  const availableModes = props.mode?.available_modes ?? [];
  const focus = props.mode?.focus;
  const backlog = props.mode?.backlog;
  const notes = props.mode?.notes ?? [];

  const writes = safeString(posture?.writes);
  const environmentId = safeString(environment?.id).trim().toLowerCase();
  const tone =
    writes === "blocked"
      ? { bg: "#2a0f0f", border: "#5a1a1a", color: "#ffaaaa" }
      : environmentId === "airgapped"
        ? { bg: "#10212a", border: "#2b5a74", color: "#b7e9ff" }
        : writes === "restricted"
          ? { bg: "#1f1a0b", border: "#5a4c18", color: "#f4d27a" }
          : { bg: "#102417", border: "#244d31", color: "#9de2ad" };

  const pendingApprovals = safeNumber(backlog?.pending_approvals, 0);
  const approvalPendingTasks = safeNumber(backlog?.approval_pending_tasks, 0);
  const blockedTasks = safeNumber(backlog?.blocked_tasks, 0);
  const queuedTasks = safeNumber(backlog?.queued_tasks, 0);
  const runningTasks = safeNumber(backlog?.running_tasks, 0);

  let actionLabel = "Open ORB";
  let action = props.onOpenOrb;
  if (pendingApprovals > 0) {
    actionLabel = "Open approvals";
    action = props.onOpenApprovals;
  } else if (approvalPendingTasks > 0 || blockedTasks > 0 || queuedTasks > 0 || runningTasks > 0) {
    actionLabel = "Open operations";
    action = props.onOpenOperations;
  }

  return (
    <section
      style={{
        ...panelStyle,
        padding: 14,
        background: tone.bg,
        border: `1px solid ${tone.border}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "grid", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={badgeStyle(environment?.label || environment?.id || "mode")}>
              {environment?.label || environment?.id || "mode"}
            </span>
            {environment?.runtime_mode ? <span style={badgeStyle(environment.runtime_mode)}>{environment.runtime_mode}</span> : null}
            {focus?.label ? <span style={badgeStyle(focus.label)}>{focus.label}</span> : null}
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: tone.color }}>
            {safeString(environment?.banner_text) || `${environment?.name || "Francis"} operator mode`}
          </div>
          <div style={{ fontSize: 12, color: THEME.text }}>
            {safeString(focus?.reason) || "Loading operator posture."}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <button style={buttonStyle} onClick={action}>
            {actionLabel}
          </button>
          <button style={buttonStyle} onClick={props.onOpenOrb}>
            ORB
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
        {posture?.governance_mode ? <span style={badgeStyle(posture.governance_mode)}>{posture.governance_mode}</span> : null}
        {posture?.trust_posture ? <span style={badgeStyle(posture.trust_posture)}>{posture.trust_posture}</span> : null}
        <span style={badgeStyle(posture?.web_access || "unknown")}>web {posture?.web_access || "unknown"}</span>
        <span style={badgeStyle(posture?.writes || "unknown")}>writes {posture?.writes || "unknown"}</span>
        <span style={badgeStyle(posture?.network_egress || "unknown")}>egress {posture?.network_egress || "unknown"}</span>
        <span style={badgeStyle("trust")}>
          trust {String(posture?.trust_level ?? 0)}/{String(posture?.minimum_operational_trust ?? 0)}
        </span>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
        <span style={badgeStyle("approvals")}>approvals {pendingApprovals}</span>
        <span style={badgeStyle("queued")}>queued {queuedTasks}</span>
        <span style={badgeStyle("blocked")}>blocked {blockedTasks}</span>
        <span style={badgeStyle("needs_approval")}>awaiting approval {approvalPendingTasks}</span>
        <span style={badgeStyle("running")}>running {runningTasks}</span>
      </div>

      <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: THEME.muted }}>
            Control mode
          </span>
          {controlMode?.label ? <span style={badgeStyle(controlMode.label)}>{controlMode.label}</span> : null}
          {controlMode?.implementation_status ? (
            <span style={badgeStyle(controlMode.implementation_status)}>{controlMode.implementation_status}</span>
          ) : null}
          {props.busy ? <span style={badgeStyle("updating")}>updating</span> : null}
        </div>
        <div style={{ fontSize: 12, color: THEME.text }}>
          {safeString(controlMode?.summary) || "Control mode sets the visible legal posture for Francis."}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {availableModes.map((item) => {
            const isActive = item.id === controlMode?.id;
            return (
              <button
                key={item.id}
                onClick={() => props.onSetControlMode(item.id)}
                disabled={props.busy || isActive}
                style={{
                  ...buttonStyle,
                  padding: "6px 10px",
                  border: isActive ? `1px solid ${THEME.text}` : `1px solid ${THEME.buttonBorder}`,
                  background: isActive ? THEME.buttonActive : THEME.buttonBg,
                  opacity: props.busy || isActive ? 0.8 : 1,
                }}
                title={item.summary || item.label || item.id}
              >
                {item.label || item.id}
              </button>
            );
          })}
        </div>
      </div>

      {notes.length > 0 || props.error ? (
        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 10 }}>
          {notes[0] ? notes[0] : null}
          {notes[0] && props.error ? " / " : null}
          {props.error ? `status: ${props.error}` : null}
        </div>
      ) : null}
    </section>
  );
}

function CommandPalette(props: {
  open: boolean;
  query: string;
  commands: PaletteCommand[];
  onQueryChange: (value: string) => void;
  onClose: () => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filtered = useMemo(() => {
    const query = props.query.trim().toLowerCase();
    if (!query) return props.commands;
    return props.commands.filter((command) => {
      const haystack = [command.label, command.description, command.group, command.keywords || ""].join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }, [props.commands, props.query]);

  useEffect(() => {
    if (!props.open) return;
    setSelectedIndex(0);
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [props.open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [props.query]);

  if (!props.open) return null;

  const runCommand = (command: PaletteCommand | null | undefined) => {
    if (!command) return;
    props.onClose();
    props.onQueryChange("");
    const result = command.run();
    if (result && typeof (result as Promise<void>).then === "function") {
      void result;
    }
  };

  return (
    <div
      onClick={props.onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "rgba(4, 4, 4, 0.72)",
        backdropFilter: "blur(10px)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "10vh 20px 20px",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(760px, 100%)",
          borderRadius: 18,
          border: `1px solid ${THEME.panelBorder}`,
          background: "#0f0f0f",
          boxShadow: "0 24px 80px rgba(0, 0, 0, 0.45)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: 14, borderBottom: `1px solid ${THEME.panelBorder}` }}>
          <input
            ref={inputRef}
            value={props.query}
            onChange={(e) => props.onQueryChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedIndex((prev) => (filtered.length === 0 ? 0 : (prev + 1) % filtered.length));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedIndex((prev) => (filtered.length === 0 ? 0 : (prev - 1 + filtered.length) % filtered.length));
              } else if (e.key === "Enter") {
                e.preventDefault();
                runCommand(filtered[selectedIndex]);
              } else if (e.key === "Escape") {
                e.preventDefault();
                props.onClose();
              }
            }}
            placeholder="Jump to approvals, switch to pilot, open ORB..."
            style={{
              ...inputStyle,
              width: "100%",
              padding: "12px 14px",
              fontSize: 14,
              borderRadius: 14,
            }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: 8, fontSize: 11, color: THEME.muted }}>
            <span>Command palette</span>
            <span>Summon with Ctrl/Cmd K</span>
          </div>
        </div>

        <div style={{ maxHeight: 420, overflow: "auto", padding: 10, display: "grid", gap: 8 }}>
          {filtered.length === 0 ? (
            <div style={{ padding: 12, borderRadius: 12, background: "#121212", color: THEME.muted, fontSize: 12 }}>
              No commands match this query.
            </div>
          ) : (
            filtered.map((command, index) => {
              const active = index === selectedIndex;
              return (
                <button
                  key={command.id}
                  onMouseEnter={() => setSelectedIndex(index)}
                  onClick={() => runCommand(command)}
                  style={{
                    ...buttonStyle,
                    textAlign: "left",
                    padding: 12,
                    borderRadius: 14,
                    background: active ? "#1b1b1b" : "#121212",
                    border: active ? `1px solid ${THEME.text}` : `1px solid ${THEME.panelBorder}`,
                    display: "grid",
                    gap: 6,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{command.label}</div>
                    <span style={badgeStyle(command.group)}>{command.group}</span>
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted }}>{command.description}</div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

function ResidentHud(props: {
  mode: OperatorModeSnapshot | null;
  settings: UiSettings;
  panel: TabKey;
  paletteOpen: boolean;
  isNarrow: boolean;
  onTogglePalette: () => void;
  onOpenApprovals: () => void;
  onOpenOperations: () => void;
  onOpenOrb: () => void;
  onNewChat: () => void;
}) {
  const environment = props.mode?.environment;
  const controlMode = props.mode?.control_mode;
  const backlog = props.mode?.backlog;
  const pendingApprovals = safeNumber(backlog?.pending_approvals, 0);
  const blockedTasks = safeNumber(backlog?.blocked_tasks, 0);
  const runningTasks = safeNumber(backlog?.running_tasks, 0);
  const approvalPendingTasks = safeNumber(backlog?.approval_pending_tasks, 0);
  const controlModeId = safeString(controlMode?.id).trim().toLowerCase();
  const telemetry = describeTelemetry(props.settings);
  const continuation = describeContinuation(props.mode);
  const tone =
    controlModeId === "pilot"
      ? { bg: "rgba(36, 22, 10, 0.94)", border: "#7a541b", color: "#ffd38a" }
      : controlModeId === "away"
        ? { bg: "rgba(16, 33, 42, 0.94)", border: "#2b5a74", color: "#b7e9ff" }
        : controlModeId === "observe"
          ? { bg: "rgba(20, 20, 20, 0.94)", border: "#4c4c4c", color: "#d8d8d8" }
          : { bg: "rgba(16, 24, 18, 0.94)", border: "#244d31", color: "#9de2ad" };

  const shellStyle: React.CSSProperties = props.isNarrow
    ? {
        position: "fixed",
        left: 14,
        right: 14,
        bottom: 14,
        zIndex: 35,
      }
    : {
        position: "fixed",
        right: 18,
        bottom: 18,
        width: 300,
        zIndex: 35,
      };

  return (
    <aside
      style={{
        ...shellStyle,
        borderRadius: 18,
        border: `1px solid ${tone.border}`,
        background: tone.bg,
        boxShadow: "0 22px 60px rgba(0, 0, 0, 0.42)",
        backdropFilter: "blur(14px)",
        padding: 12,
        display: "grid",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "grid", gap: 4 }}>
          <div style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: THEME.muted }}>HUD</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: tone.color }}>
            {environment?.label || environment?.id || "Francis"} / {controlMode?.label || controlMode?.id || "mode"}
          </div>
        </div>
        <span style={badgeStyle(props.panel)}>{props.panel}</span>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span style={badgeStyle("approvals")}>approvals {pendingApprovals}</span>
        <span style={badgeStyle("blocked")}>blocked {blockedTasks}</span>
        <span style={badgeStyle("running")}>running {runningTasks}</span>
        <span style={badgeStyle("needs_approval")}>awaiting {approvalPendingTasks}</span>
      </div>

      <div style={{ fontSize: 11, color: THEME.muted }}>
        {controlMode?.summary || "Resident operator HUD active."}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span style={badgeStyle(telemetry.tone)}>{telemetry.label}</span>
        <span style={badgeStyle(continuation.tone)}>{continuation.label}</span>
      </div>

      <div style={{ fontSize: 11, color: THEME.muted }}>
        {telemetry.scopeLabel} / {telemetry.voiceLabel.toLowerCase()} / {telemetry.proactiveLabel.toLowerCase()}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: props.isNarrow ? "repeat(2, minmax(0, 1fr))" : "repeat(3, minmax(0, 1fr))",
          gap: 8,
        }}
      >
        <button style={buttonStyle} onClick={props.onTogglePalette}>
          {props.paletteOpen ? "Close" : "Summon"}
        </button>
        <button style={buttonStyle} onClick={props.onOpenApprovals}>
          Approvals
        </button>
        <button style={buttonStyle} onClick={props.onOpenOperations}>
          Ops
        </button>
        <button style={buttonStyle} onClick={props.onOpenOrb}>
          ORB
        </button>
        <button style={buttonStyle} onClick={props.onNewChat}>
          New chat
        </button>
      </div>
    </aside>
  );
}

export default function App() {
  const [settings, setSettings] = useState<UiSettings>(() => loadSettings());
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions());
  const [activeId, setActiveId] = useState<string>(() => (loadSessions()[0]?.id ?? createSession().id));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<TabKey>("approvals");
  const [focusedApprovalId, setFocusedApprovalId] = useState("");
  const [approvalReturnContext, setApprovalReturnContext] = useState<ApprovalReturnContext | null>(null);
  const [focusedOperationId, setFocusedOperationId] = useState("");
  const [focusedMissionId, setFocusedMissionId] = useState("");
  const [operatorMode, setOperatorMode] = useState<OperatorModeSnapshot | null>(null);
  const [operatorModeError, setOperatorModeError] = useState<string | null>(null);
  const [operatorModeBusy, setOperatorModeBusy] = useState(false);
  const [observerScanBusy, setObserverScanBusy] = useState(false);
  const [observerScanNotice, setObserverScanNotice] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [baseUrl, setBaseUrl] = useState(() => {
    const env = safeString(import.meta.env.VITE_FRANCIS_API_BASE_URL, DEFAULT_API);
    return normalizeBaseUrl(env);
  });
  const width = useWindowWidth();
  const modeClient = useMemo(() => {
    const normalized = normalizeBaseUrl(baseUrl);
    return normalized ? new SettingsClient(normalized, { mutationsEnabled: true }) : null;
  }, [baseUrl]);

  useEffect(() => {
    if (sessions.length === 0) {
      const s = createSession();
      setSessions([s]);
      setActiveId(s.id);
    }
  }, [sessions.length]);

  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  useEffect(() => {
    const load = () => setVoices(window.speechSynthesis.getVoices());
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (!settings.voiceEnabled) return;
      if (!text.trim()) return;
      const utterance = new SpeechSynthesisUtterance(text);
      const voice =
        settings.voiceAutoFemale && voices.length
          ? pickAutoFemaleVoice(voices)
          : voices.find((v) => v.voiceURI === settings.voiceUri);
      if (voice) utterance.voice = voice;
      utterance.rate = settings.voiceRate;
      utterance.pitch = settings.voicePitch;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    },
    [settings, voices],
  );

  const activeSession = sessions.find((s) => s.id === activeId) ?? sessions[0];

  const updateSession = useCallback(
    (id: string, updater: (s: ChatSession) => ChatSession) => {
      setSessions((prev) => prev.map((s) => (s.id === id ? updater(s) : s)));
    },
    [],
  );

  const onSend = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !activeSession || busy) return;
      setError(null);
      setBusy(true);

      updateSession(activeSession.id, (s) => {
        const next = { ...s };
        const title = s.title === "New chat" ? summarizeTitle(trimmed) : s.title;
        next.title = title;
        next.messages = [
          ...s.messages,
          { role: "user", content: trimmed, ts: Math.floor(Date.now() / 1000) },
        ];
        next.updatedTs = Date.now();
        return next;
      });

      try {
        const res = await fetch(`${baseUrl}/chat/send`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed, use_llm: true }),
        });
        if (!res.ok) {
          setError(`HTTP ${res.status}`);
          return;
        }
        const parsed = parseChatSendResponse(await res.json());
        const parsedMessage = parsed.message;
        if (parsed.error && !parsedMessage) {
          setError(parsed.error);
        }
        if (parsedMessage) {
          updateSession(activeSession.id, (s) => ({
            ...s,
            messages: [
              ...s.messages,
              { ...parsedMessage, ts: Math.floor(Date.now() / 1000) },
            ],
            updatedTs: Date.now(),
          }));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Chat request failed.");
      } finally {
        setBusy(false);
      }
    },
    [activeSession, baseUrl, busy, updateSession],
  );

  const createNewChat = useCallback(() => {
    const s = createSession();
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
  }, []);

  const openApprovalsPanel = useCallback((approvalId?: string, returnContext?: ApprovalReturnContext) => {
    setFocusedApprovalId(approvalId ? approvalId : "");
    setApprovalReturnContext(
      returnContext && (safeString(returnContext.missionId).trim() || safeString(returnContext.operationId).trim())
        ? {
            missionId: safeString(returnContext.missionId).trim() || undefined,
            operationId: safeString(returnContext.operationId).trim() || undefined,
            source: safeString(returnContext.source).trim() || undefined,
            reviewReason: safeString(returnContext.reviewReason).trim() || undefined,
            changedKeys: Array.isArray(returnContext.changedKeys)
              ? returnContext.changedKeys.map((key) => safeString(key).trim()).filter(Boolean)
              : undefined,
          }
        : null,
    );
    setPanel("approvals");
  }, []);

  const openOperationPanel = useCallback((operationId: string) => {
    setFocusedOperationId(operationId);
    setPanel("operations");
  }, []);

  const openOperationsPanel = useCallback(() => {
    setFocusedOperationId("");
    setPanel("operations");
  }, []);

  const openPluginsPanel = useCallback(() => {
    setPanel("plugins");
  }, []);

  const openSettingsPanel = useCallback(() => {
    setPanel("settings");
  }, []);

  const openOrbPanel = useCallback(() => {
    setPanel("system");
  }, []);

  const openContinuityLedger = useCallback(() => {
    setPanel("system");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById("francis-continuity-ledger")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }, []);

  const openMissionPanel = useCallback((missionId: string) => {
    const cleaned = missionId.trim();
    if (!cleaned) return;
    setFocusedMissionId(cleaned);
    setPanel("system");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const target =
          document.getElementById("francis-mission-feed") ?? document.getElementById("francis-shift-briefing");
        target?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }, []);

  const openMissionFeed = useCallback(() => {
    setPanel("system");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const target =
          document.getElementById("francis-shift-briefing") ?? document.getElementById("francis-mission-feed");
        target?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }, []);

  const openTakeoverFeed = useCallback(() => {
    setPanel("system");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById("francis-takeover-feed")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }, []);

  const openTelemetryStatus = useCallback(() => {
    setPanel("system");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById("francis-telemetry-status")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }, []);

  const togglePalette = useCallback(() => {
    setPaletteQuery("");
    setPaletteOpen((prev) => !prev);
  }, []);

  useEffect(() => {
    if (!modeClient) {
      setOperatorMode(null);
      setOperatorModeError("API base URL is required.");
      return;
    }

    let cancelled = false;

    const refreshOperatorMode = async () => {
      try {
        const next = await modeClient.getOperatorMode({ timeoutMs: 10_000 });
        if (cancelled) return;
        setOperatorMode(next);
        setOperatorModeError(null);
      } catch (err) {
        if (cancelled) return;
        const msg =
          err instanceof SettingsApiError
            ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
            : err instanceof Error
              ? err.message
              : "Operator mode request failed.";
        setOperatorModeError(msg);
      }
    };

    void refreshOperatorMode();
    const intervalId = window.setInterval(() => {
      void refreshOperatorMode();
    }, 30_000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [modeClient]);

  const setControlMode = useCallback(
    async (modeId: OperatorControlModeId) => {
      if (!modeClient) {
        setOperatorModeError("API base URL is required.");
        return;
      }
      const normalizedMode = safeString(modeId).trim().toLowerCase();
      if (!normalizedMode) return;
      if (normalizedMode === safeString(operatorMode?.control_mode?.id).trim().toLowerCase()) return;

      if (
        (normalizedMode === "pilot" || normalizedMode === "away") &&
        !window.confirm(
          `${
            normalizedMode === "pilot" ? "Pilot" : "Away"
          } mode is a visible legal posture. Approval gates still remain active in this build. Continue?`,
        )
      ) {
        return;
      }

      setOperatorModeBusy(true);
      try {
        const response = await modeClient.setOperatorMode(
          {
            mode: normalizedMode,
            reason: `console_mode_switch:${normalizedMode}`,
            actor: "chat_ui.banner",
          },
          { timeoutMs: 10_000 },
        );
        if (!response.ok) {
          throw new Error(response.message || "Control mode update failed.");
        }
        if (response.snapshot) {
          setOperatorMode(response.snapshot);
        }
        setOperatorModeError(null);
      } catch (err) {
        const msg =
          err instanceof SettingsApiError
            ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
            : err instanceof Error
              ? err.message
              : "Control mode update failed.";
        setOperatorModeError(msg);
      } finally {
        setOperatorModeBusy(false);
      }
    },
    [modeClient, operatorMode?.control_mode?.id],
  );

  const recordObserverScan = useCallback(async () => {
    if (!modeClient) {
      setObserverScanNotice({ tone: "error", text: "API base URL is required before observer scans can be recorded." });
      setOperatorModeError("API base URL is required before observer scans can be recorded.");
      return;
    }

    setObserverScanBusy(true);
    setObserverScanNotice(null);
    try {
      const response = await modeClient.recordObserverScan(
        {
          reason: "chat_ui.command_palette",
          actor: "chat_ui.command_palette",
        },
        { timeoutMs: 10_000 },
      );
      if (!response.ok) {
        throw new Error("Observer scan failed.");
      }
      const receiptId = safeString(response.receipt?.receipt_id).trim();
      const decision = safeString(response.decision).trim() || safeString(response.receipt?.decision).trim();
      setObserverScanNotice({
        tone: "info",
        text: receiptId
          ? `Observer scan recorded as ${receiptId}${decision ? ` (${decision})` : ""}.`
          : "Observer scan recorded.",
      });
      setPanel("system");
      setOperatorModeError(null);
    } catch (err) {
      const msg =
        err instanceof SettingsApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
          : err instanceof Error
            ? err.message
            : "Observer scan request failed.";
      setObserverScanNotice({ tone: "error", text: msg });
      setOperatorModeError(msg);
    } finally {
      setObserverScanBusy(false);
    }
  }, [modeClient]);

  const paletteCommands = useMemo<PaletteCommand[]>(() => {
    const pendingApprovals = safeNumber(operatorMode?.backlog?.pending_approvals, 0);
    return [
      {
        id: "nav.briefing",
        label: "Request Continuity Briefing",
        description: "Open the shift briefing and return-to-work recommendations.",
        group: "Navigation",
        keywords: "briefing continuity mission return to work handoff",
        run: () => openMissionFeed(),
      },
      {
        id: "nav.takeover",
        label: "Open Takeover Feed",
        description: "Inspect active Pilot scope, live execution, and hand-back guidance.",
        group: "Navigation",
        keywords: "takeover pilot delegated execution interrupt hand back",
        run: () => openTakeoverFeed(),
      },
      {
        id: "nav.telemetry",
        label: "Open Telemetry Status",
        description: "Inspect visible sensing posture and continuation state.",
        group: "Navigation",
        keywords: "telemetry away sensing continuation status posture",
        run: () => openTelemetryStatus(),
      },
      {
        id: "nav.approvals",
        label: pendingApprovals > 0 ? `Open Approvals (${pendingApprovals})` : "Open Approvals",
        description: "Review the approval queue and make governance decisions.",
        group: "Navigation",
        keywords: "approval review queue governance",
        run: () => openApprovalsPanel(),
      },
      {
        id: "nav.operations",
        label: "Open Operations",
        description: "Inspect queued, blocked, and running task activity.",
        group: "Navigation",
        keywords: "operations tasks backlog execution",
        run: () => openOperationsPanel(),
      },
      {
        id: "nav.orb",
        label: "Open ORB",
        description: "Inspect the canonical flow, incidents, and runtime posture.",
        group: "Navigation",
        keywords: "orb system incidents runtime",
        run: () => openOrbPanel(),
      },
      {
        id: "nav.continuity-ledger",
        label: "Open Continuity Ledger",
        description: "Inspect raw local continuity receipts without treating them as synthesized memory.",
        group: "Navigation",
        keywords: "continuity ledger receipts memory trace audit",
        run: () => openContinuityLedger(),
      },
      {
        id: "nav.plugins",
        label: "Open Plugins",
        description: "Inspect plugins, tools, and governance outcomes.",
        group: "Navigation",
        keywords: "plugins tools browser",
        run: () => openPluginsPanel(),
      },
      {
        id: "nav.settings",
        label: "Open Settings",
        description: "Adjust console preferences and voice settings.",
        group: "Navigation",
        keywords: "settings preferences voice",
        run: () => openSettingsPanel(),
      },
      {
        id: "chat.new",
        label: "Start New Chat",
        description: "Open a fresh Francis conversation.",
        group: "Chat",
        keywords: "new chat session",
        run: () => createNewChat(),
      },
      {
        id: "mode.observe",
        label: "Switch to Observe",
        description: "Declare read-only posture with no claimed write authority.",
        group: "Control",
        keywords: "observe readonly mode",
        run: () => setControlMode("observe"),
      },
      {
        id: "mode.assist",
        label: "Switch to Assist",
        description: "Return to collaborative operator posture.",
        group: "Control",
        keywords: "assist collaborative mode",
        run: () => setControlMode("assist"),
      },
      {
        id: "mode.pilot",
        label: "Switch to Pilot",
        description: "Declare takeover posture and light the pilot indicator.",
        group: "Control",
        keywords: "pilot takeover active indicator",
        run: () => setControlMode("pilot"),
      },
      {
        id: "mode.away",
        label: "Switch to Away",
        description: "Declare away posture for continuity while you step out.",
        group: "Control",
        keywords: "away night shift mode",
        run: () => setControlMode("away"),
      },
      {
        id: "observer.scan",
        label: "Record Observer Scan",
        description: "Trigger an explicit receipted observer scan and refresh the continuity surfaces.",
        group: "Control",
        keywords: "observer scan receipt continuity observability",
        run: () => recordObserverScan(),
      },
    ];
  }, [
    createNewChat,
    openApprovalsPanel,
    openContinuityLedger,
    openMissionFeed,
    openTakeoverFeed,
    openTelemetryStatus,
    openOperationsPanel,
    openOrbPanel,
    openPluginsPanel,
    openSettingsPanel,
    operatorMode?.backlog?.pending_approvals,
    recordObserverScan,
    setControlMode,
  ]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const normalizedKey = event.key.toLowerCase();
      if ((event.metaKey || event.ctrlKey) && normalizedKey === "k") {
        event.preventDefault();
        setPaletteQuery("");
        setPaletteOpen((prev) => !prev);
        return;
      }
      if (normalizedKey === "escape") {
        setPaletteOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const isNarrow = width < 1100;
  const controlModeId = safeString(operatorMode?.control_mode?.id).trim().toLowerCase();
  const telemetry = describeTelemetry(settings);
  const continuation = describeContinuation(operatorMode);
  const indicatorTone =
    controlModeId === "pilot"
      ? { bg: "#3a150d", border: "#8f5221", color: "#ffd38a" }
      : controlModeId === "away"
        ? { bg: "#10212a", border: "#2b5a74", color: "#b7e9ff" }
        : { bg: "#171717", border: "#333333", color: THEME.muted };

  return (
    <div
      style={{
        minHeight: "100vh",
        color: THEME.text,
        background: "radial-gradient(1200px 600px at 15% -10%, #1d1d1d 0%, #0a0a0a 55%, #070707 100%)",
        fontFamily: '"Space Grotesk", "Manrope", "Segoe UI", sans-serif',
      }}
    >
      <div style={{ display: "flex", minHeight: "100vh" }}>
        <aside
          style={{
            width: 280,
            background: THEME.rail,
            borderRight: `1px solid ${THEME.railBorder}`,
            padding: 18,
            display: isNarrow ? "none" : "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>Francis</div>
            <div style={{ fontSize: 12, color: THEME.muted }}>Operator console</div>
          </div>

          <button onClick={createNewChat} style={{ ...buttonStyle, width: "100%" }}>
            New chat
          </button>

          <div style={{ fontSize: 12, color: THEME.muted }}>History</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveId(s.id)}
                style={{
                  ...buttonStyle,
                  textAlign: "left",
                  border: s.id === activeId ? `1px solid ${THEME.text}` : `1px solid ${THEME.buttonBorder}`,
                  background: s.id === activeId ? THEME.buttonActive : THEME.buttonBg,
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 600 }}>{s.title}</div>
                <div style={{ fontSize: 11, color: THEME.muted }}>
                  {new Date(s.updatedTs).toLocaleDateString()}
                </div>
              </button>
            ))}
          </div>

          <div style={{ marginTop: "auto", fontSize: 11, color: THEME.muted }}>
            Connected to <code>{baseUrl}</code>
          </div>
        </aside>

        <main style={{ flex: 1, display: "flex", flexDirection: "column", padding: 24, gap: 18 }}>
          <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>Francis Console</div>
              <div style={{ fontSize: 12, color: THEME.muted }}>
                Chat, approvals, plugins, system checks, and operations.
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                <span style={badgeStyle(operatorMode?.control_mode?.label || operatorMode?.control_mode?.id || "mode")}>
                  {operatorMode?.control_mode?.label || operatorMode?.control_mode?.id || "mode"}
                </span>
                {controlModeId === "pilot" ? (
                  <span
                    style={{
                      ...badgeStyle("pilot_active"),
                      background: indicatorTone.bg,
                      border: `1px solid ${indicatorTone.border}`,
                      color: indicatorTone.color,
                    }}
                  >
                    Pilot Active
                  </span>
                ) : null}
                {controlModeId === "away" ? (
                  <span
                    style={{
                      ...badgeStyle("away_active"),
                      background: indicatorTone.bg,
                      border: `1px solid ${indicatorTone.border}`,
                      color: indicatorTone.color,
                    }}
                  >
                    Away Active
                  </span>
                ) : null}
                <span style={badgeStyle(telemetry.tone)}>
                  {telemetry.label} / {telemetry.scopeLabel}
                </span>
                <span style={badgeStyle(continuation.tone)}>{continuation.label}</span>
                <span style={{ fontSize: 11, color: THEME.muted }}>Summon with Ctrl/Cmd K</span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button style={buttonStyle} onClick={togglePalette}>
                Command
              </button>
              <span style={{ fontSize: 12, color: THEME.muted }}>API</span>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(normalizeBaseUrl(e.target.value))}
                style={{ ...inputStyle, padding: "8px 10px", minWidth: 220 }}
              />
            </div>
          </header>

          <OperatorModeBanner
            mode={operatorMode}
            error={operatorModeError}
            busy={operatorModeBusy}
            onOpenApprovals={() => openApprovalsPanel()}
            onOpenOperations={openOperationsPanel}
            onOpenOrb={openOrbPanel}
            onSetControlMode={setControlMode}
          />

          <div style={{ display: "flex", gap: 18, flex: 1, minHeight: 0 }}>
            <section style={{ ...panelStyle, flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
              {activeSession ? (
                <ChatPanel
                  baseUrl={baseUrl}
                  messages={activeSession.messages}
                  busy={busy}
                  error={error}
                  onSend={onSend}
                  onOpenMission={openMissionPanel}
                  onSpeak={speak}
                />
              ) : (
                <div style={{ color: THEME.muted }}>No active chat.</div>
              )}
            </section>

            {isNarrow ? null : (
              <aside style={{ width: 360, display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {(
                    [
                      ["approvals", "Approvals"],
                      ["plugins", "Plugins"],
                      ["system", "ORB"],
                      ["operations", "Operations"],
                      ["settings", "Settings"],
                    ] as Array<[TabKey, string]>
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      onClick={() => setPanel(key)}
                      style={{
                        ...buttonStyle,
                        border: panel === key ? `1px solid ${THEME.text}` : `1px solid ${THEME.buttonBorder}`,
                        background: panel === key ? THEME.buttonActive : THEME.buttonBg,
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {panel === "approvals" ? (
                  <ApprovalsPanel
                    baseUrl={baseUrl}
                    focusApprovalId={focusedApprovalId}
                    returnContext={approvalReturnContext}
                    onOpenMission={openMissionPanel}
                    onOpenOperation={openOperationPanel}
                  />
                ) : null}
                {panel === "plugins" ? <PluginsPanel baseUrl={baseUrl} onOpenApprovals={openApprovalsPanel} /> : null}
                {panel === "system" ? (
                  <SystemPanel
                    baseUrl={baseUrl}
                    settings={settings}
                    operatorMode={operatorMode}
                    focusMissionId={focusedMissionId}
                    onOpenApprovals={openApprovalsPanel}
                    onOpenOperation={openOperationPanel}
                    onOpenOperations={openOperationsPanel}
                  />
                ) : null}
                {panel === "operations" ? (
                  <OperationsPanel
                    baseUrl={baseUrl}
                    focusOperationId={focusedOperationId}
                    operatorMode={operatorMode}
                    onOpenApprovals={openApprovalsPanel}
                    onOpenMission={openMissionPanel}
                    onOpenContinuityLedger={openContinuityLedger}
                  />
                ) : null}
                {panel === "settings" ? <SettingsPanel settings={settings} onChange={setSettings} /> : null}
              </aside>
            )}
          </div>

          {isNarrow ? (
            <section style={{ ...panelStyle, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {(
                  [
                    ["approvals", "Approvals"],
                    ["plugins", "Plugins"],
                    ["system", "ORB"],
                    ["operations", "Operations"],
                    ["settings", "Settings"],
                  ] as Array<[TabKey, string]>
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setPanel(key)}
                    style={{
                      ...buttonStyle,
                      border: panel === key ? `1px solid ${THEME.text}` : `1px solid ${THEME.buttonBorder}`,
                      background: panel === key ? THEME.buttonActive : THEME.buttonBg,
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {panel === "approvals" ? (
                <ApprovalsPanel
                  baseUrl={baseUrl}
                  focusApprovalId={focusedApprovalId}
                  returnContext={approvalReturnContext}
                  onOpenMission={openMissionPanel}
                  onOpenOperation={openOperationPanel}
                />
              ) : null}
              {panel === "plugins" ? <PluginsPanel baseUrl={baseUrl} onOpenApprovals={openApprovalsPanel} /> : null}
              {panel === "system" ? (
                <SystemPanel
                  baseUrl={baseUrl}
                  settings={settings}
                  operatorMode={operatorMode}
                  focusMissionId={focusedMissionId}
                  onOpenApprovals={openApprovalsPanel}
                  onOpenOperation={openOperationPanel}
                  onOpenOperations={openOperationsPanel}
                />
              ) : null}
              {panel === "operations" ? (
                <OperationsPanel
                  baseUrl={baseUrl}
                  focusOperationId={focusedOperationId}
                  operatorMode={operatorMode}
                  onOpenApprovals={openApprovalsPanel}
                  onOpenMission={openMissionPanel}
                  onOpenContinuityLedger={openContinuityLedger}
                />
              ) : null}
              {panel === "settings" ? <SettingsPanel settings={settings} onChange={setSettings} /> : null}
            </section>
          ) : null}
        </main>
      </div>
      <CommandPalette
        open={paletteOpen}
        query={paletteQuery}
        commands={paletteCommands}
        onQueryChange={setPaletteQuery}
        onClose={() => setPaletteOpen(false)}
      />
      <ResidentHud
        mode={operatorMode}
        settings={settings}
        panel={panel}
        paletteOpen={paletteOpen}
        isNarrow={isNarrow}
        onTogglePalette={togglePalette}
        onOpenApprovals={() => openApprovalsPanel()}
        onOpenOperations={openOperationsPanel}
        onOpenOrb={openOrbPanel}
        onNewChat={createNewChat}
      />
    </div>
  );
}
function ApprovalsPanel(props: {
  baseUrl: string;
  focusApprovalId?: string;
  returnContext?: ApprovalReturnContext | null;
  onOpenMission?: (missionId: string) => void;
  onOpenOperation?: (operationId: string) => void;
}) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new ApprovalsClient(resolvedBaseUrl), [resolvedBaseUrl]);

  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [selectedApprovalId, setSelectedApprovalId] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [decisionBusy, setDecisionBusy] = useState<Record<string, boolean>>({});
  const [decisionError, setDecisionError] = useState<Record<string, string | null>>({});
  const [decisionResult, setDecisionResult] = useState<{
    approvalId: string;
    action: string;
    status: string;
    missionId?: string;
    operationId?: string;
  } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await client.list({ status: "pending", limit: 50 });
      const nextItems = res.items ?? [];
      setItems(nextItems);
      setSelectedApprovalId((prev) => {
        if (props.focusApprovalId && nextItems.some((item) => item.id === props.focusApprovalId)) {
          return props.focusApprovalId;
        }
        if (prev && nextItems.some((item) => item.id === prev)) return prev;
        return nextItems[0]?.id ?? "";
      });
    } catch (err) {
      if (err instanceof ApprovalsApiError) {
        const detail = err.status ? `HTTP ${err.status}` : "request failed";
        setLoadError(`${detail}${err.url ? ` (${err.url})` : ""}`);
      } else if (err instanceof Error) {
        setLoadError(err.message);
      } else {
        setLoadError("Failed to load approvals.");
      }
    } finally {
      setLoading(false);
    }
  }, [client, props.focusApprovalId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!props.focusApprovalId) return;
    setSelectedApprovalId(props.focusApprovalId);
  }, [props.focusApprovalId]);

  useEffect(() => {
    setDecisionResult(null);
  }, [props.focusApprovalId]);

  async function performDecision(id: string, action: string) {
    const currentItem = items.find((item) => item.id === id) ?? null;
    setDecisionError((prev) => ({ ...prev, [id]: null }));
    setDecisionBusy((prev) => ({ ...prev, [id]: true }));
    try {
      const response = await client.decide({ id, action });
      const decidedItem = response.item ?? currentItem;
      const inspection = inspectApproval(decidedItem);
      const fallbackContext =
        props.focusApprovalId && props.focusApprovalId === id && props.returnContext ? props.returnContext : null;
      setDecisionResult({
        approvalId: id,
        action,
        status: safeString(response.status, action).trim() || action,
        missionId: inspection.missionId || fallbackContext?.missionId,
        operationId: inspection.operationId || fallbackContext?.operationId,
      });
      await refresh();
    } catch (err) {
      const msg =
        err instanceof ApprovalsApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
          : err instanceof Error
            ? err.message
            : "Decision failed.";
      setDecisionError((prev) => ({ ...prev, [id]: msg }));
    } finally {
      setDecisionBusy((prev) => ({ ...prev, [id]: false }));
    }
  }

  const selectedApproval = items.find((item) => item.id === selectedApprovalId) ?? items[0] ?? null;
  const selectedInspection = inspectApproval(selectedApproval);
  const selectedApprovalPlanLine = approvalProjectionPlanLine(selectedApproval);
  const activeReturnContext =
    props.focusApprovalId && selectedApproval?.id === props.focusApprovalId ? props.returnContext : null;
  const returnSource = safeString(activeReturnContext?.source).trim();
  const returnReviewKind = safeString(activeReturnContext?.reviewKind).trim();
  const returnReviewReason = safeString(activeReturnContext?.reviewReason).trim();
  const returnChangedKeys = Array.isArray(activeReturnContext?.changedKeys)
    ? activeReturnContext.changedKeys.map((key) => safeString(key).trim()).filter(Boolean)
    : [];
  const approvalStats = {
    total: items.length,
    highRisk: items.filter((item) => ["high", "critical", "safety_critical"].includes(inspectApproval(item).risk.toLowerCase())).length,
    domains: new Set(items.map((item) => inspectApproval(item).domain.toLowerCase()).filter(Boolean)).size,
  };

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Approvals</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>
        status=pending / api=<code>{resolvedBaseUrl}</code>
      </div>

      {loadError ? (
        <div
          style={{
            marginTop: 12,
            padding: 10,
            borderRadius: 10,
            border: `1px solid ${THEME.errorBorder}`,
            background: THEME.errorBg,
            color: "#ffaaaa",
            fontSize: 12,
          }}
        >
          <b>Load error:</b> {loadError}
        </div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, marginTop: 12 }}>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Pending now</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{approvalStats.total}</div>
        </div>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>High-risk queue</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{approvalStats.highRisk}</div>
        </div>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Domains touched</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{approvalStats.domains}</div>
        </div>
      </div>

      {decisionResult ? (
        <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Latest Decision</div>
              <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>
                <code>{decisionResult.approvalId}</code> moved to <code>{decisionResult.status}</code> via{" "}
                <code>{decisionResult.action}</code>.
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {decisionResult.missionId && props.onOpenMission ? (
                <button style={buttonStyle} onClick={() => props.onOpenMission?.(decisionResult.missionId || "")}>
                  Open mission flow
                </button>
              ) : null}
              {decisionResult.operationId && props.onOpenOperation ? (
                <button style={buttonStyle} onClick={() => props.onOpenOperation?.(decisionResult.operationId || "")}>
                  Open linked task
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Selected Approval</div>
        {!selectedApproval ? (
          <div style={{ marginTop: 8, fontSize: 12, color: THEME.muted }}>No approval selected.</div>
        ) : (
          <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>{approvalProjectionTitle(selectedApproval)}</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span style={badgeStyle(selectedApproval.status || "pending")}>{selectedApproval.status || "pending"}</span>
                <span style={badgeStyle(selectedInspection.risk)}>{selectedInspection.risk}</span>
                <span style={badgeStyle(selectedInspection.domain)}>{selectedInspection.domain}</span>
                {selectedApproval.request_kind ? (
                  <span style={badgeStyle("queued")}>{selectedApproval.request_kind}</span>
                ) : null}
              </div>
            </div>
            <div style={{ fontSize: 11, color: THEME.muted }}>
              <code>{selectedApproval.id}</code>
            </div>
            <div style={{ fontSize: 12, color: THEME.muted }}>
              {approvalProjectionDetail(selectedApproval)}
            </div>
            {safeString(selectedApproval.reason).trim() && safeString(selectedApproval.reason).trim() !== approvalProjectionDetail(selectedApproval) ? (
              <div style={{ fontSize: 12, color: "#ffcf9d" }}>{selectedApproval.reason}</div>
            ) : null}
            {approvalProjectionExactActionLine(selectedApproval) ? (
              <div style={{ fontSize: 12, color: THEME.muted }}>Exact action: {approvalProjectionExactActionLine(selectedApproval)}</div>
            ) : null}
            {approvalProjectionLoopLine(selectedApproval) ? (
              <div style={{ fontSize: 12, color: THEME.muted }}>Loop: {approvalProjectionLoopLine(selectedApproval)}</div>
            ) : null}
            {selectedApprovalPlanLine ? (
              <div style={{ fontSize: 12, color: THEME.muted }}>Plan: {selectedApprovalPlanLine}</div>
            ) : null}
            {approvalProjectionLineage(selectedApproval) ? (
              <div style={{ fontSize: 12, color: THEME.muted }}>Lineage: {approvalProjectionLineage(selectedApproval)}</div>
            ) : null}
            {approvalProjectionReplacementLine(selectedApproval) ? (
              <div style={{ fontSize: 12, color: THEME.muted }}>
                Replacement: {approvalProjectionReplacementLine(selectedApproval)}
              </div>
            ) : null}
            {approvalProjectionReplacementScopeLine(selectedApproval) ? (
              <div style={{ fontSize: 12, color: THEME.muted }}>
                Mismatch scope: {approvalProjectionReplacementScopeLine(selectedApproval)}
              </div>
            ) : null}
            <div style={{ fontSize: 12 }}>
              Created: <code>{selectedApproval.ts ? toLocaleTime(selectedApproval.ts) : "unknown"}</code>
            </div>
            {activeReturnContext ? (
              <div style={{ fontSize: 12, color: THEME.muted }}>
                Opened from <code>{returnSource || "linked context"}</code>
                {returnReviewKind ? (
                  <>
                    {" / "}kind=<code>{returnReviewKind}</code>
                  </>
                ) : null}
                {returnReviewReason ? (
                  <>
                    {" / "}reason=<code>{returnReviewReason}</code>
                  </>
                ) : null}
                {returnChangedKeys.length > 0 ? (
                  <>
                    {" / "}changed_keys=<code>{returnChangedKeys.join(",")}</code>
                  </>
                ) : null}
              </div>
            ) : null}
            {selectedInspection.missionId || selectedInspection.operationId ? (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {selectedInspection.missionId && props.onOpenMission ? (
                  <button style={buttonStyle} onClick={() => props.onOpenMission?.(selectedInspection.missionId)}>
                    Open mission flow
                  </button>
                ) : null}
                {selectedInspection.operationId && props.onOpenOperation ? (
                  <button style={buttonStyle} onClick={() => props.onOpenOperation?.(selectedInspection.operationId)}>
                    Open linked task
                  </button>
                ) : null}
              </div>
            ) : null}
            <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Scope Touched</div>
              <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                {selectedInspection.scopeItems.length === 0 ? (
                  <div style={{ fontSize: 12, color: THEME.muted }}>No structured scope fields were recorded for this approval.</div>
                ) : (
                  selectedInspection.scopeItems.map((item) => (
                    <div key={item} style={{ fontSize: 12, color: THEME.muted }}>
                      {item}
                    </div>
                  ))
                )}
              </div>
            </div>
            <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Evidence</div>
              <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                {selectedInspection.evidenceItems.length === 0 ? (
                  <div style={{ fontSize: 12, color: THEME.muted }}>Only the raw payload is available for this approval.</div>
                ) : (
                  selectedInspection.evidenceItems.map((item) => (
                    <div key={item} style={{ fontSize: 12, color: THEME.muted }}>
                      {item}
                    </div>
                  ))
                )}
              </div>
            </div>
            <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Decision Consequences</div>
              <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                <div style={{ fontSize: 12, color: "#9de2ad" }}>Approve: {selectedInspection.approveEffect}</div>
                <div style={{ fontSize: 12, color: "#ffcf9d" }}>Reject: {selectedInspection.denyEffect}</div>
                <div style={{ fontSize: 12, color: THEME.muted }}>Mission state: {selectedInspection.missionRelation}</div>
              </div>
            </div>
            {selectedApproval.payload !== undefined ? (
              <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#0d0d0d" }}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Raw Payload</div>
                <pre
                  style={{
                    margin: 0,
                    whiteSpace: "pre-wrap",
                    fontSize: 11,
                    maxHeight: 220,
                    overflow: "auto",
                  }}
                >
{prettyData(selectedApproval.payload)}
                </pre>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10, maxHeight: 300, overflow: "auto" }}>
        {loading && items.length === 0 ? <i>Loading approvals.</i> : null}
        {!loading && items.length === 0 ? <i>No approvals found.</i> : null}
        {items.map((a) => {
          const inspection = inspectApproval(a);
          const busy = Boolean(decisionBusy[a.id]);
          const err = decisionError[a.id];
          const selected = a.id === selectedApproval?.id;
          const detail = approvalProjectionDetail(a);
          const exactAction = approvalProjectionExactActionLine(a);
          const loopLine = approvalProjectionLoopLine(a);
          const planLine = approvalProjectionPlanLine(a);
          const lineage = approvalProjectionLineage(a);
          const replacement = approvalProjectionReplacementLine(a);
          const replacementScope = approvalProjectionReplacementScopeLine(a);
          const reason = safeString(a.reason).trim();
          return (
            <div
              key={a.id}
              style={{
                border: selected ? `1px solid ${THEME.text}` : `1px solid ${THEME.panelBorder}`,
                borderRadius: 12,
                padding: 10,
                background: selected ? THEME.buttonActive : "transparent",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <div style={{ fontWeight: 600 }}>{approvalProjectionTitle(a)}</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span style={badgeStyle(a.status || "pending")}>{a.status || "pending"}</span>
                  <span style={badgeStyle(inspection.risk)}>{inspection.risk}</span>
                </div>
              </div>
              <div style={{ fontSize: 12, color: THEME.muted, marginTop: 4 }}>{detail}</div>
              {reason && reason !== detail ? <div style={{ fontSize: 12, color: "#ffcf9d", marginTop: 4 }}>{reason}</div> : null}
              <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>{inspection.scopeLabel}</div>
              {exactAction ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>exact action: {exactAction}</div> : null}
              {loopLine ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>loop: {loopLine}</div> : null}
              {planLine ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>plan: {planLine}</div> : null}
              {lineage ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>lineage: {lineage}</div> : null}
              {replacement ? (
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>replacement: {replacement}</div>
              ) : null}
              {replacementScope ? (
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>mismatch scope: {replacementScope}</div>
              ) : null}
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                <code>{a.id}</code> / domain=<code>{inspection.domain}</code>
              </div>
              {err ? (
                <div style={{ marginTop: 6, fontSize: 12, color: "#ffaaaa" }}>
                  <b>Decision error:</b> {err}
                </div>
              ) : null}
              <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                <button style={buttonStyle} onClick={() => setSelectedApprovalId(a.id)}>
                  Inspect
                </button>
                <button style={buttonStyle} disabled={busy} onClick={() => void performDecision(a.id, "approve")}>
                  Approve
                </button>
                <button style={buttonStyle} disabled={busy} onClick={() => void performDecision(a.id, "reject")}>
                  Reject
                </button>
                <button style={buttonStyle} disabled={busy} onClick={() => void performDecision(a.id, "emergency")}>
                  Emergency
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SystemPanel(props: {
  baseUrl: string;
  settings: UiSettings;
  operatorMode: OperatorModeSnapshot | null;
  focusMissionId?: string;
  onOpenApprovals: (approvalId?: string, returnContext?: ApprovalReturnContext) => void;
  onOpenOperation: (operationId: string) => void;
  onOpenOperations: () => void;
}) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new SettingsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const missionsClient = useMemo(() => new MissionsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const operationsClient = useMemo(() => new OperationsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [infoError, setInfoError] = useState<string | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [worldState, setWorldState] = useState<WorldStateSnapshot | null>(null);
  const [worldStateError, setWorldStateError] = useState<string | null>(null);
  const [continuityLedger, setContinuityLedger] = useState<ContinuityLedgerSnapshot | null>(null);
  const [continuityLedgerError, setContinuityLedgerError] = useState<string | null>(null);
  const [continuityBriefing, setContinuityBriefing] = useState<ContinuityBriefingSnapshot | null>(null);
  const [continuityBriefingError, setContinuityBriefingError] = useState<string | null>(null);
  const [observerEvents, setObserverEvents] = useState<ObserverEventsSnapshot | null>(null);
  const [observerEventsError, setObserverEventsError] = useState<string | null>(null);
  const [orbStatus, setOrbStatus] = useState<OrbStatusSnapshot | null>(null);
  const [orbStatusError, setOrbStatusError] = useState<string | null>(null);
  const [observerScanBusy, setObserverScanBusy] = useState(false);
  const [observerScanNotice, setObserverScanNotice] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [takeoverOperations, setTakeoverOperations] = useState<OperationRecord[]>([]);
  const [takeoverOperationsError, setTakeoverOperationsError] = useState<string | null>(null);
  const [takeoverOperationsLoadedAt, setTakeoverOperationsLoadedAt] = useState<number | null>(null);
  const [selectedMissionId, setSelectedMissionId] = useState("");
  const [missionDetail, setMissionDetail] = useState<MissionDetail | null>(null);
  const [missionDetailBusy, setMissionDetailBusy] = useState(false);
  const [missionDetailError, setMissionDetailError] = useState<string | null>(null);
  const [missionActionBusy, setMissionActionBusy] = useState<"" | "run" | "cancel" | "advance" | "replace">("");
  const [missionActionTargetId, setMissionActionTargetId] = useState("");
  const [missionActionNotice, setMissionActionNotice] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [missionActionResult, setMissionActionResult] = useState<{
    missionId?: string;
    operationId?: string;
    approvalId?: string;
    operationError?: string;
    resultMessage?: string;
    recoveryNextStep?: string;
  } | null>(null);
  const [missionQueueRunBusy, setMissionQueueRunBusy] = useState(false);
  const [missionQueueRunSummary, setMissionQueueRunSummary] = useState<{
    processed: number;
    applied: number;
    advanced: number;
    status?: string;
    error?: string;
    errorCount: number;
    counts: Record<string, number>;
    request?: {
      actor?: string;
      note?: string;
      limit?: number;
    };
    results: Array<{
      missionId?: string;
      operationId?: string;
      approvalId?: string;
      action?: string;
      activeStage?: string;
      status?: string;
      gate?: string;
      nextStep?: string;
      traceId?: string;
      runId?: string;
      artifactDir?: string;
      queueItem?: MissionQueueItem;
      currentTask?: MissionCurrentTask;
      receiptSummary?: MissionReceiptSummary;
      handoffAction?: string;
      handoffDetail?: string;
      historyCount?: number;
      linkedOperationCount?: number;
      runLedgerCount?: number;
      message?: string;
      operationError?: string;
      resultMessage?: string;
      recoveryNextStep?: string;
    }>;
    errors: Array<{
      missionId?: string;
      operationId?: string;
      approvalId?: string;
      action?: string;
      status?: string;
      gate?: string;
      nextStep?: string;
      traceId?: string;
      runId?: string;
      artifactDir?: string;
      error?: string;
      message?: string;
      operationError?: string;
      resultMessage?: string;
      recoveryNextStep?: string;
    }>;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshAttemptedAt, setLastRefreshAttemptedAt] = useState<number | null>(null);
  const [lastRefreshCompletedAt, setLastRefreshCompletedAt] = useState<number | null>(null);
  const [nowTs, setNowTs] = useState(() => nowUnixSeconds());
  const autoRefreshIntervalMs = 30_000;

  const settingsError = useCallback((err: unknown, fallback = "Request failed."): string => {
    if (err instanceof SettingsApiError) {
      return `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`;
    }
    if (err instanceof Error) return err.message;
    return fallback;
  }, []);

  const operationsError = useCallback((err: unknown): string => {
    if (err instanceof OperationsApiError) {
      return `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`;
    }
    if (err instanceof Error) return err.message;
    return "Operations request failed.";
  }, []);

  const scrollOrbSection = useCallback((sectionId: string) => {
    window.requestAnimationFrame(() => {
      document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, []);

  const missionError = useCallback((err: unknown): string => {
    if (err instanceof MissionsApiError) {
      return `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`;
    }
    if (err instanceof Error) return err.message;
    return "Mission request failed.";
  }, []);

  const refresh = useCallback(async () => {
    const refreshStartedAt = nowUnixSeconds();
    setLastRefreshAttemptedAt(refreshStartedAt);
    setBusy(true);
    setRefreshNotice(null);
    setError(null);
    try {
      const [
        nextInfo,
        nextHealth,
        nextWorldState,
        nextContinuityLedger,
        nextContinuityBriefing,
        nextObserverEvents,
        nextOrbStatus,
        nextOperations,
      ] =
        await Promise.allSettled([
        client.getSystemInfo(),
        client.getHealth(),
        client.getWorldState(),
        client.getContinuityLedger({ limit: 8 }),
        client.getContinuityBriefing(),
        client.getObserverEvents({ limit: 8 }),
        client.getOrbStatus(),
        operationsClient.list({ limit: 16 }).then((response) => response.items ?? []),
      ]);

      const degradedFeeds: string[] = [];

      if (nextInfo.status === "fulfilled") {
        setInfo(nextInfo.value);
        setInfoError(null);
      } else {
        setInfoError(settingsError(nextInfo.reason, "System info request failed."));
        degradedFeeds.push("system info");
      }

      if (nextHealth.status === "fulfilled") {
        setHealth(nextHealth.value);
        setHealthError(null);
      } else {
        setHealthError(settingsError(nextHealth.reason, "Health request failed."));
        degradedFeeds.push("health");
      }

      if (nextWorldState.status === "fulfilled") {
        setWorldState(nextWorldState.value);
        setWorldStateError(null);
      } else {
        setWorldStateError(settingsError(nextWorldState.reason, "World-state request failed."));
        degradedFeeds.push("world state");
      }

      if (nextContinuityLedger.status === "fulfilled") {
        setContinuityLedger(nextContinuityLedger.value);
        setContinuityLedgerError(null);
      } else {
        setContinuityLedgerError(settingsError(nextContinuityLedger.reason, "Continuity ledger request failed."));
        degradedFeeds.push("continuity ledger");
      }

      if (nextContinuityBriefing.status === "fulfilled") {
        setContinuityBriefing(nextContinuityBriefing.value);
        setContinuityBriefingError(null);
      } else {
        setContinuityBriefingError(settingsError(nextContinuityBriefing.reason, "Continuity briefing request failed."));
        degradedFeeds.push("continuity briefing");
      }

      if (nextObserverEvents.status === "fulfilled") {
        setObserverEvents(nextObserverEvents.value);
        setObserverEventsError(null);
      } else {
        setObserverEventsError(settingsError(nextObserverEvents.reason, "Observer audit request failed."));
        degradedFeeds.push("observer audit");
      }

      if (nextOrbStatus.status === "fulfilled") {
        setOrbStatus(nextOrbStatus.value);
        setOrbStatusError(null);
      } else {
        setOrbStatusError(settingsError(nextOrbStatus.reason, "ORB status request failed."));
        degradedFeeds.push("orb status");
      }

      if (nextOperations.status === "fulfilled") {
        setTakeoverOperations(nextOperations.value);
        setTakeoverOperationsError(null);
        setTakeoverOperationsLoadedAt(refreshStartedAt);
      } else {
        setTakeoverOperationsError(operationsError(nextOperations.reason));
        degradedFeeds.push("live operations");
      }

      if (degradedFeeds.length > 0) {
        setRefreshNotice(`Refresh completed with degraded feeds: ${degradedFeeds.join(", ")}.`);
      }
    } catch (err) {
      setError(settingsError(err));
    } finally {
      setLastRefreshCompletedAt(nowUnixSeconds());
      setBusy(false);
    }
  }, [client, operationsClient, operationsError, settingsError]);

  const recordObserverScan = useCallback(async () => {
    if (!modeClient) {
      setObserverScanNotice({ tone: "error", text: "API base URL is required before observer scans can be recorded." });
      return;
    }

    setObserverScanBusy(true);
    setObserverScanNotice(null);
    try {
      const response = await modeClient.recordObserverScan(
        {
          reason: "chat_ui.shift_briefing",
          actor: "chat_ui.shift_briefing",
        },
        { timeoutMs: 10_000 },
      );
      if (!response.ok) {
        throw new Error("Observer scan failed.");
      }
      const receiptId = safeString(response.receipt?.receipt_id).trim();
      const decision = safeString(response.decision).trim() || safeString(response.receipt?.decision).trim();
      setObserverScanNotice({
        tone: "info",
        text: receiptId
          ? `Observer scan recorded as ${receiptId}${decision ? ` (${decision})` : ""}.`
          : "Observer scan recorded.",
      });
      await refresh();
    } catch (err) {
      setObserverScanNotice({
        tone: "error",
        text: settingsError(err, "Observer scan request failed."),
      });
    } finally {
      setObserverScanBusy(false);
    }
  }, [modeClient, refresh, settingsError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setNowTs(nowUnixSeconds());
    }, 15_000);
    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      if (busy) return;
      if (document.visibilityState !== "visible") return;
      void refresh();
    }, autoRefreshIntervalMs);
    return () => window.clearInterval(intervalId);
  }, [autoRefreshIntervalMs, busy, refresh]);

  const loadMissionDetail = useCallback(
    async (missionId: string) => {
      const cleaned = missionId.trim();
      if (!cleaned) {
        setMissionDetail(null);
        setMissionDetailError(null);
        return null;
      }
      setMissionDetailBusy(true);
      setMissionDetailError(null);
      try {
        const nextDetail = await missionsClient.get(cleaned);
        setMissionDetail(nextDetail);
        if (!nextDetail.ok && nextDetail.error) {
          setMissionDetailError(nextDetail.error);
        }
        return nextDetail;
      } catch (err) {
        setMissionDetail(null);
        setMissionDetailError(missionError(err));
        return null;
      } finally {
        setMissionDetailBusy(false);
      }
    },
    [missionError, missionsClient],
  );

  const counts = worldState?.counts;
  const overview = worldState?.overview;
  const shiftBriefing = continuityBriefing?.briefing;
  const continuityOperatorSurface = continuityBriefing?.operator;
  const continuityOperatorMode = continuityOperatorSurface?.control_mode;
  const continuityOperatorModeId = safeString(continuityOperatorMode?.id).trim().toLowerCase();
  const continuityOperatorModeLabel =
    safeString(continuityOperatorMode?.label).trim() || continuityOperatorModeId || "operator";
  const continuityOperatorFocus =
    safeString(continuityOperatorSurface?.focus?.label).trim() ||
    safeString(continuityOperatorSurface?.focus?.plane_id).trim();
  const continuityOperatorWrites = safeString(continuityOperatorSurface?.posture?.writes).trim();
  const continuityOperatorTrustLevel = continuityOperatorSurface?.posture?.trust_level;
  const continuityOrbSurface = continuityBriefing?.orb;
  const continuityOrbState = isRecord(continuityOrbSurface?.state) ? continuityOrbSurface.state : null;
  const continuityOrbRenderState =
    safeString(continuityOrbState?.render_state).trim() || safeString(continuityOrbState?.current).trim();
  const continuityOrbHandbackState = isRecord(continuityOrbState?.handback_state)
    ? continuityOrbState.handback_state
    : null;
  const continuityOrbIncidentPressure = isRecord(continuityOrbState?.incident_pressure)
    ? continuityOrbState.incident_pressure
    : null;
  const continuityOrbPressureObserver = isRecord(continuityOrbIncidentPressure?.observer)
    ? continuityOrbIncidentPressure.observer
    : null;
  const continuityOrbHandbackStatus = safeString(continuityOrbHandbackState?.state).trim();
  const continuityOrbHandbackHeadline = safeString(continuityOrbHandbackState?.headline).trim();
  const continuityOrbPressureLevel = safeString(continuityOrbIncidentPressure?.level).trim();
  const continuityOrbPressureSource = safeString(continuityOrbIncidentPressure?.source).trim();
  const continuityOrbPressureHeadline =
    safeString(continuityOrbIncidentPressure?.headline).trim() || safeString(continuityOrbPressureObserver?.headline).trim();
  const continuityOrbPressureScore = safeNumber(continuityOrbPressureObserver?.score, 0);
  const continuityOrbPressureReasons = observerAnomalyReasonSummary(
    continuityOrbPressureObserver
      ? {
          score: continuityOrbPressureScore,
          level: safeString(continuityOrbPressureObserver?.level).trim(),
          reasons: Array.isArray(continuityOrbPressureObserver?.reasons)
            ? continuityOrbPressureObserver.reasons.map((item) => safeString(item).trim()).filter(Boolean)
            : [],
        }
      : null,
  );
  const shiftBriefingCounts = shiftBriefing?.counts ?? {};
  const shiftBriefingFocus = shiftBriefing?.focus ?? [];
  const shiftBriefingCompleted = shiftBriefing?.recently_completed ?? [];
  const shiftBriefingMemoryReceipts = shiftBriefing?.memory_receipts ?? [];
  const shiftBriefingFailed = shiftBriefing?.failed_preview ?? [];
  const shiftBriefingFailedPresentation = useMemo(
    () => presentMissionRecoveryItems(shiftBriefingFailed, 2),
    [shiftBriefingFailed],
  );
  const shiftBriefingDeadletter = shiftBriefing?.deadletter_preview ?? [];
  const shiftBriefingDeadletterPresentation = useMemo(
    () => presentMissionDeadletterItems(shiftBriefingDeadletter, 2),
    [shiftBriefingDeadletter],
  );
  const shiftBriefingReadiness = shiftBriefing?.readiness;
  const shiftBriefingObserver = shiftBriefing?.observer;
  const shiftBriefingObserverCounts = shiftBriefingObserver?.counts ?? {};
  const shiftBriefingObserverFocus = shiftBriefingObserver?.focus ?? [];
  const shiftBriefingObserverProbes = shiftBriefingObserver?.probes ?? [];
  const shiftBriefingObserverRecentScans = shiftBriefingObserver?.recent_scans ?? [];
  const shiftBriefingObserverAnomaly = shiftBriefingObserver?.anomaly;
  const shiftBriefingObserverReadiness = shiftBriefingObserver?.readiness;
  const shiftBriefingObserverReadinessCriteria = shiftBriefingObserverReadiness?.criteria ?? [];
  const shiftBriefingObserverHasAnomaly = Boolean(shiftBriefingObserverAnomaly);
  const shiftBriefingObserverActive = safeNumber(shiftBriefingObserverCounts["active"], shiftBriefingObserverFocus.length);
  const shiftBriefingObserverCritical = safeNumber(shiftBriefingObserverCounts["critical"], 0);
  const shiftBriefingObserverError = safeNumber(shiftBriefingObserverCounts["error"], 0);
  const shiftBriefingObserverWarning = safeNumber(shiftBriefingObserverCounts["warning"], 0);
  const shiftBriefingObserverAnomalyScore = safeNumber(shiftBriefingObserverAnomaly?.score, 0);
  const shiftBriefingObserverAnomalyLevel =
    safeString(shiftBriefingObserverAnomaly?.level).trim() || (shiftBriefingObserverActive > 0 ? "warning" : "clear");
  const shiftBriefingObserverAnomalyReasons = observerAnomalyReasonSummary(shiftBriefingObserverAnomaly);
  const continuityLedgerEntries = [...(continuityLedger?.entries ?? [])].slice(-6).reverse();
  const continuityLedgerCount = continuityLedger?.entries?.length ?? 0;
  const continuityLedgerRouteError = safeString(continuityLedger?.error).trim();
  const observerEventEntries = observerEvents?.items ?? [];
  const observerEventCount = observerEvents?.total ?? observerEventEntries.length;
  const observerEventsRouteError = safeString(observerEvents?.error).trim();
  const taskStatusCounts = overview?.task_status_counts ?? {};
  const missionStatusCounts = overview?.mission_status_counts ?? {};
  const overviewMissionReadiness = overview?.mission_briefing?.readiness ?? shiftBriefingReadiness;
  const recentTasks = overview?.recent_tasks ?? [];
  const recentMissions = overview?.recent_missions ?? [];
  const missionQueue = overview?.mission_queue ?? [];
  const missionQueuePresentation = useMemo(() => presentMissionQueue(missionQueue, 4), [missionQueue]);
  const failedPreview = overview?.failed_missions ?? [];
  const failedPreviewPresentation = useMemo(() => presentMissionRecoveryItems(failedPreview, 2), [failedPreview]);
  const deadletterPreview = overview?.deadletter_missions ?? [];
  const deadletterPreviewPresentation = useMemo(() => presentMissionDeadletterItems(deadletterPreview, 2), [deadletterPreview]);
  const incidents = overview?.incidents ?? [];
  const pendingApprovals = overview?.pending_approvals ?? [];
  const queuedTasks = safeNumber(counts?.queued_tasks, safeNumber(taskStatusCounts.pending, 0) + safeNumber(taskStatusCounts.accepted, 0));
  const approvalPendingTasks = safeNumber(counts?.approval_pending_tasks, safeNumber(taskStatusCounts.needs_approval, 0));
  const blockedTasks = safeNumber(counts?.blocked_tasks, safeNumber(taskStatusCounts.blocked, 0));
  const runningTasks = safeNumber(counts?.running_tasks, safeNumber(taskStatusCounts.running, 0));
  const queuedMissions = safeNumber(counts?.queued_missions, safeNumber(missionStatusCounts.queued, 0));
  const activeMissions = safeNumber(counts?.active_missions, safeNumber(missionStatusCounts.active, 0));
  const blockedMissions = safeNumber(counts?.blocked_missions, safeNumber(missionStatusCounts.blocked, 0));
  const failedMissions = safeNumber(counts?.failed_missions, safeNumber(missionStatusCounts.failed, 0));
  const deadletteredMissions = safeNumber(
    counts?.deadlettered_missions,
    safeNumber(missionStatusCounts.deadlettered, 0),
  );
  const declaredMissionCount = safeNumber(counts?.missions, recentMissions.length);
  const activeIncidents = safeNumber(counts?.active_incidents, incidents.length);
  const shiftBriefingBlocked = safeNumber(shiftBriefingCounts["blocked"], 0);
  const shiftBriefingQueued = safeNumber(shiftBriefingCounts["queued"], 0);
  const shiftBriefingFailedCount = safeNumber(shiftBriefingCounts["failed"], 0);
  const shiftBriefingCompletedCount = safeNumber(shiftBriefingCounts["completed"], 0);
  const shiftBriefingDeadletterCount = safeNumber(shiftBriefingCounts["deadlettered"], 0);
  const shiftBriefingMemoryReceiptCount = shiftBriefingMemoryReceipts.length;
  const servicesRaw =
    worldState?.services && typeof worldState.services === "object" && !Array.isArray(worldState.services)
      ? worldState.services
      : null;
  const serviceItems = Array.isArray(servicesRaw?.services)
    ? servicesRaw.services.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    : [];
  const orbModel = orbStatus?.model;
  const coreLoop = orbStatus?.core_loop ?? [];
  const gateStack = orbStatus?.gates ?? [];
  const forbiddenTransitions = orbStatus?.transitions?.forbidden ?? [];
  const runtimeState = health?.ok ? "healthy" : "attention";
  const controlMode = props.operatorMode?.control_mode;
  const controlModeId = safeString(controlMode?.id).trim().toLowerCase();
  const telemetry = describeTelemetry(props.settings);
  const continuation = describeContinuation(props.operatorMode);
  const controlTone =
    controlModeId === "pilot"
      ? { bg: "#24160a", border: "#7a541b", color: "#ffd38a" }
      : controlModeId === "away"
        ? { bg: "#10212a", border: "#2b5a74", color: "#b7e9ff" }
      : controlModeId === "observe"
        ? { bg: "#1a1a1a", border: "#4c4c4c", color: "#d8d8d8" }
        : { bg: "#102417", border: "#244d31", color: "#9de2ad" };
  const missionFeedDeclared = declaredMissionCount > 0 || recentMissions.length > 0;
  const queueLead = missionQueuePresentation.lead ?? null;
  const leadMission =
    recentMissions.find((mission) => ["failed", "deadlettered", "blocked"].includes(safeString(mission.status).trim().toLowerCase())) ??
    recentMissions.find((mission) => safeString(mission.status).trim().toLowerCase() === "active") ??
    recentMissions.find((mission) => safeString(mission.status).trim().toLowerCase() === "queued") ??
    recentMissions[0] ??
    null;
  const activeTask = recentTasks.find((task) => safeString(task.status).trim().toLowerCase() === "running");
  const blockedTask = recentTasks.find((task) => {
    const status = safeString(task.status).trim().toLowerCase();
    return status === "blocked" || status === "needs_approval";
  });
  const stalledTask = recentTasks.find((task) => {
    const status = safeString(task.status).trim().toLowerCase();
    return status === "pending" || status === "accepted";
  });
  const recentDeclaredMissions = recentMissions.slice(0, 4);
  const recentTaskProgress = recentTasks.slice(0, 4);
  const handoffTasks = recentTasks
    .filter((task) => {
      const assignedTo = safeString(task.assigned_to).trim().toLowerCase();
      return assignedTo !== "" && assignedTo !== "unassigned";
    })
    .slice(0, 3);
  const missionSummaryItems = [
    { label: "Active missions", value: activeMissions, tone: activeMissions > 0 ? "running" : "clear" },
    { label: "Queued missions", value: queuedMissions, tone: queuedMissions > 0 ? "pending" : "clear" },
    { label: "Blocked missions", value: blockedMissions, tone: blockedMissions > 0 ? "blocked" : "clear" },
    { label: "Failed missions", value: failedMissions, tone: failedMissions > 0 ? "failed" : "clear" },
    { label: "Deadlettered", value: deadletteredMissions, tone: deadletteredMissions > 0 ? "failed" : "clear" },
    {
      label: "Pending approvals",
      value: Math.max(pendingApprovals.length, approvalPendingTasks),
      tone: pendingApprovals.length > 0 || approvalPendingTasks > 0 ? "needs_approval" : "clear",
    },
  ];
  const returnToWorkItems: Array<{
    id: string;
    label: string;
    title: string;
    detail: string;
    tone: string;
    actionLabel?: string;
    onAction?: () => void;
  }> = [];

  if (queueLead) {
    const queueCurrentTask = queueLead.current_task;
    const queueTargetId = missionRecoveryTargetId(queueLead, queueLead, undefined, queueCurrentTask);
    const queueOperationTargetId = missionCurrentTaskId(queueLead, queueLead, undefined, queueCurrentTask);
    const queueApprovalId =
      safeString(queueCurrentTask?.approval_id).trim() || safeString(queueLead.last_task_approval_id).trim();
    const queueTargetIsMission = queueTargetId.startsWith("msn_");
    const queueTargetIsOperation = queueTargetId.startsWith("tsk_");
    returnToWorkItems.push({
      id: `queue:${queueLead.id}`,
      label: "Queue",
      title: queueLead.objective || queueLead.id,
      detail:
        safeString(queueLead.operator_hint).trim() ||
        safeString(queueLead.next_step).trim() ||
        "Mission queue item needs operator review.",
      tone: queueLead.status || "queued",
      actionLabel: queueApprovalId
        ? "Review approval"
        : queueTargetId && queueTargetIsMission
          ? "Open dependency mission"
          : queueTargetId && queueTargetIsOperation
            ? "Open linked task"
            : undefined,
      onAction: queueApprovalId
        ? () =>
            props.onOpenApprovals(queueApprovalId, {
              missionId: queueLead.id,
              operationId: queueTargetIsOperation ? queueTargetId : queueOperationTargetId || undefined,
            })
        : queueTargetId && queueTargetIsMission
          ? () => inspectMission(queueTargetId)
          : queueTargetId && queueTargetIsOperation
            ? () => props.onOpenOperation(queueTargetId)
            : undefined,
    });
  } else if (leadMission) {
    const leadMissionCurrentTask = leadMission.current_task;
    const linkedTaskId = missionCurrentTaskId(leadMission, undefined, undefined, leadMissionCurrentTask);
    const missionDetail =
      safeString(leadMissionCurrentTask?.next_step).trim() ||
      safeString(leadMission.last_task_next_step).trim() ||
      safeString(leadMission.next_step).trim() ||
      safeString(leadMissionCurrentTask?.reason).trim() ||
      safeString(leadMission.last_task_reason).trim() ||
      safeString(leadMission.summary).trim() ||
      safeString(leadMission.deadletter_reason).trim() ||
      "Mission continuity exists, but the next-step note is still blank.";
    returnToWorkItems.push({
      id: `mission:${leadMission.id}`,
      label: "Mission",
      title: leadMission.objective || leadMission.id,
      detail: missionDetail,
      tone: leadMission.status || "queued",
      actionLabel: linkedTaskId ? "Open linked task" : undefined,
      onAction: linkedTaskId ? () => props.onOpenOperation(linkedTaskId) : undefined,
    });
  }

  if (incidents.length > 0) {
    const incident = incidents[0];
    const approvalId = safeString(incident.approval_id);
    const taskId = safeString(incident.task_id);
    returnToWorkItems.push({
      id: `incident:${incident.id}`,
      label: "Incident",
      title: incident.title || incident.id,
      detail: incident.detail || "Local runtime drift needs operator review before additional action.",
      tone: incident.severity || "warning",
      actionLabel: approvalId ? "Review approval" : taskId ? "Open task" : undefined,
      onAction: approvalId
        ? () =>
            props.onOpenApprovals(approvalId, {
              operationId: taskId || undefined,
            })
        : taskId
          ? () => props.onOpenOperation(taskId)
          : undefined,
    });
  }

  if (pendingApprovals.length > 0) {
    const approval = pendingApprovals[0];
    returnToWorkItems.push({
      id: `approval:${approval.id}`,
      label: "Approval",
      title: approvalProjectionTitle(approval),
      detail: approvalProjectionDetail(approval),
      tone: approval.status || "needs_approval",
      actionLabel: "Open approvals",
      onAction: () => props.onOpenApprovals(approval.id),
    });
  }

  if (blockedTask) {
    returnToWorkItems.push({
      id: `blocked:${blockedTask.id}`,
      label: "Blocked",
      title: blockedTask.objective || blockedTask.capability || blockedTask.id,
      detail: blockedTask.status_reason || "This work unit cannot proceed until an operator clears the blocker.",
      tone: blockedTask.status || "blocked",
      actionLabel: "Open task",
      onAction: () => props.onOpenOperation(blockedTask.id),
    });
  } else if (activeTask) {
    returnToWorkItems.push({
      id: `active:${activeTask.id}`,
      label: "Active",
      title: activeTask.objective || activeTask.capability || activeTask.id,
      detail: activeTask.status_reason || "Execution is active; review progress before introducing new work.",
      tone: activeTask.status || "running",
      actionLabel: "Open task",
      onAction: () => props.onOpenOperation(activeTask.id),
    });
  } else if (stalledTask) {
    returnToWorkItems.push({
      id: `stalled:${stalledTask.id}`,
      label: "Stalled",
      title: stalledTask.objective || stalledTask.capability || stalledTask.id,
      detail: stalledTask.status_reason || "This work is queued but not advancing yet.",
      tone: stalledTask.status || "pending",
      actionLabel: "Open task",
      onAction: () => props.onOpenOperation(stalledTask.id),
    });
  }

  if (returnToWorkItems.length === 0) {
    returnToWorkItems.push({
      id: "clear",
      label: "Clear",
      title: "No immediate continuity blockers",
      detail: "Local task, approval, and incident state are clear. Use the palette to ask, inspect, or delegate.",
      tone: "clear",
    });
  }

  const controlModeGuidance =
    controlModeId === "observe"
      ? "Observe keeps Francis read-only. Review incidents and approvals before you deliberately change posture."
      : controlModeId === "pilot"
        ? "Pilot is visibly active. Review the mission feed before approving additional work."
        : controlModeId === "away"
          ? "Away keeps continuity visible while you step out. Prioritize handoffs and pending approvals."
          : "Assist keeps the operator in the loop while Francis surfaces the next governed step.";
  const focusPlaneId = safeString(props.operatorMode?.focus?.plane_id).trim();
  const focusLabel = safeString(props.operatorMode?.focus?.label).trim() || focusPlaneId || "No active scope";
  const focusReason = safeString(props.operatorMode?.focus?.reason).trim() || "No active operator focus has been recorded.";
  const pilotActive = controlModeId === "pilot";
  const activeTakeoverOperations = takeoverOperations.filter((operation) =>
    ["running", "queued", "blocked"].includes(operationStatus(operation)),
  );
  const currentTakeoverOperation = activeTakeoverOperations[0] ?? null;
  const completedTakeoverOperations = takeoverOperations
    .filter((operation) => ["succeeded", "failed", "canceled"].includes(operationStatus(operation)))
    .slice(0, 3);
  const interruptibleOperations = activeTakeoverOperations.slice(0, 3);
  const activePlanes = Array.from(
    new Set(activeTakeoverOperations.map((operation) => operationPlane(operation)).filter(Boolean)),
  ).slice(0, 3);
  const missionSelectionCandidates = useMemo(() => {
    const ordered: string[] = [];
    const push = (value: unknown) => {
      const cleaned = safeString(value).trim();
      if (!cleaned || ordered.includes(cleaned)) return;
      ordered.push(cleaned);
    };

    push(props.focusMissionId);
    shiftBriefingFocus.forEach((item) => push(item.id));
    missionQueuePresentation.ordered.forEach((item) => push(item.id));
    recentDeclaredMissions.forEach((mission) => push(mission.id));
    shiftBriefingCompleted.forEach((item) => push(item.id));
    shiftBriefingDeadletter.forEach((item) => push(item.id));
    if (leadMission) push(leadMission.id);
    return ordered;
  }, [leadMission, missionQueuePresentation.ordered, props.focusMissionId, recentDeclaredMissions, shiftBriefingCompleted, shiftBriefingDeadletter, shiftBriefingFocus]);
  const missionSelectionKey = missionSelectionCandidates.join("|");
  const selectedMission = missionDetail?.mission;
  const selectedMissionMeta = isRecord(selectedMission?.meta) ? selectedMission.meta : {};
  const selectedMissionReplacementForId =
    safeString(selectedMission?.replacement_for_mission_id).trim() ||
    safeString(selectedMissionMeta.replacement_for_mission_id).trim();
  const selectedMissionReplacementForStatus =
    safeString(selectedMission?.replacement_for_status).trim() ||
    safeString(selectedMissionMeta.replacement_for_status).trim();
  const selectedMissionReplacementSourceAction =
    safeString(selectedMission?.replacement_source_action).trim() ||
    safeString(selectedMissionMeta.replacement_source_action).trim();
  const selectedMissionReplacementSourceTargetId =
    safeString(selectedMission?.replacement_source_target_id).trim() ||
    safeString(selectedMissionMeta.replacement_source_target_id).trim();
  const selectedMissionReplacementReason =
    safeString(selectedMission?.replacement_reason).trim() ||
    safeString(selectedMissionMeta.replacement_reason).trim();
  const selectedMissionCurrentTask = missionDetail?.current_task;
  const selectedMissionCurrentTaskOperationName = safeString(selectedMissionCurrentTask?.operation_name).trim();
  const selectedMissionCurrentTaskOperationPlane = safeString(selectedMissionCurrentTask?.operation_plane).trim();
  const selectedMissionCurrentTaskAdvanceAction = safeString(selectedMissionCurrentTask?.advance_action).trim();
  const selectedMissionTaskStatus = safeString(selectedMissionCurrentTask?.task_status).trim();
  const selectedMissionLastTaskStatus =
    safeString(selectedMissionCurrentTask?.operation_status).trim() ||
    selectedMissionTaskStatus ||
    safeString(selectedMission?.last_task_status).trim() ||
    safeString(selectedMissionMeta.last_task_status).trim();
  const selectedMissionLastTaskResultStatus =
    safeString(selectedMissionCurrentTask?.result_status).trim() ||
    safeString(selectedMission?.last_task_result_status).trim() ||
    safeString(selectedMissionMeta.last_task_result_status).trim();
  const selectedMissionLastTaskGate =
    safeString(selectedMissionCurrentTask?.gate).trim() ||
    safeString(selectedMission?.last_task_gate).trim() ||
    safeString(selectedMissionMeta.last_task_gate).trim();
  const selectedMissionLastTaskReason =
    safeString(selectedMissionCurrentTask?.reason).trim() ||
    safeString(selectedMission?.last_task_reason).trim() ||
    safeString(selectedMissionMeta.last_task_reason).trim();
  const selectedMissionCurrentTaskReceiptEvent = safeString(selectedMissionCurrentTask?.latest_receipt_event).trim();
  const selectedMissionCurrentTaskReceiptStatus = safeString(selectedMissionCurrentTask?.latest_receipt_status).trim();
  const selectedMissionContextId = safeString(selectedMission?.id).trim() || selectedMissionId;
  const missionLinkedOperations = missionDetail?.linked_operations ?? [];
  const missionRunLedger = missionDetail?.run_ledger ?? [];
  const missionHistory = missionDetail?.history ?? [];
  const missionLoopState: MissionLoopState | undefined = missionDetail?.loop_state;
  const missionLoopHandoff = missionLoopState?.handoff;
  const selectedMissionQueueItem = missionDetail?.mission?.id === selectedMission?.id ? missionDetail.queue_item : undefined;
  const selectedMissionCurrentTaskId = missionCurrentTaskId(
    selectedMission,
    selectedMissionQueueItem,
    missionLoopHandoff,
    selectedMissionCurrentTask,
  );
  const missionReceiptSummary = missionDetail?.receipt_summary;
  const missionReceiptOperationId =
    safeString(missionReceiptSummary?.current_operation_id).trim() || selectedMissionCurrentTaskId;
  const missionReceiptOperationName = safeString(missionReceiptSummary?.current_operation_name).trim();
  const missionReceiptOperationPlane = safeString(missionReceiptSummary?.current_operation_plane).trim();
  const missionReceiptAdvanceAction = safeString(missionReceiptSummary?.current_advance_action).trim();
  const missionReceiptPlanStatus = safeString(missionReceiptSummary?.plan_status).trim();
  const missionReceiptPlanStepId = safeString(missionReceiptSummary?.plan_current_step_id).trim();
  const missionReceiptPlanStepTitle = safeString(missionReceiptSummary?.plan_current_step_title).trim();
  const missionReceiptPlanStepCount = missionReceiptSummary?.plan_step_count;
  const missionReceiptPlanCheckpointCount = missionReceiptSummary?.plan_checkpoint_count;
  const missionReceiptApprovalId =
    safeString(missionReceiptSummary?.current_approval_id).trim() || safeString(selectedMissionCurrentTask?.approval_id).trim();
  const missionReceiptTraceId =
    safeString(missionReceiptSummary?.current_trace_id).trim() || safeString(selectedMissionCurrentTask?.trace_id).trim();
  const missionReceiptRunId =
    safeString(missionReceiptSummary?.current_run_id).trim() || safeString(selectedMissionCurrentTask?.run_id).trim();
  const missionReceiptArtifactDir =
    safeString(missionReceiptSummary?.current_artifact_dir).trim() ||
    safeString(selectedMissionCurrentTask?.artifact_dir).trim();
  const missionReceiptLatestRunAt = mixedLocaleTime(missionReceiptSummary?.latest_run_ts);
  const missionReceiptLatestHistoryAt = mixedLocaleTime(missionReceiptSummary?.latest_history_ts);
  const missionMemoryReceiptCount =
    missionDetail?.memory_receipt_count ??
    missionReceiptSummary?.memory_receipt_count ??
    missionLoopState?.memory?.memory_receipt_count ??
    missionDetail?.memory_receipts?.length ??
    0;
  const missionLatestMemoryReceipt =
    missionDetail?.latest_memory_receipt ??
    missionReceiptSummary?.latest_memory_receipt ??
    missionLoopState?.memory?.latest_memory_receipt ??
    missionDetail?.memory_receipts?.[0];
  const missionLatestMemoryReceiptRefs = missionLatestMemoryReceipt
    ? missionMemoryReceiptReferenceLine(missionLatestMemoryReceipt)
    : "";
  const missionLatestMemoryReceiptHandoff = missionLatestMemoryReceipt
    ? missionMemoryReceiptHandoffLine(missionLatestMemoryReceipt)
    : "";
  const missionLatestMemoryReceiptAt = mixedLocaleTime(missionLatestMemoryReceipt?.ts);
  const missionLoopStages = missionLoopState
    ? ([
        { key: "plan", label: "Plan", stage: missionLoopState.plan },
        { key: "gate", label: "Gate", stage: missionLoopState.gate },
        { key: "execute", label: "Execute", stage: missionLoopState.execute },
        { key: "trace", label: "Trace", stage: missionLoopState.trace },
        { key: "memory", label: "Memory", stage: missionLoopState.memory },
        { key: "interface", label: "Interface", stage: missionLoopState.interface },
      ] as const).filter((item) => item.stage)
    : [];
  const primaryMissionOperation = missionCurrentOperation(missionLinkedOperations, selectedMissionCurrentTaskId);
  const primaryMissionOperationStatus = operationStatus(primaryMissionOperation);
  const primaryMissionOperationApprovalId =
    safeString(selectedMissionCurrentTask?.approval_id).trim() || operationApprovalId(primaryMissionOperation);
  const primaryMissionRecoverySummary =
    primaryMissionOperationStatus === "running"
      ? "Execution is live for this mission. You can monitor the linked task here or cancel it if the plan needs to stop."
      : primaryMissionOperationApprovalId
        ? "This mission is waiting on an explicit approval. Review the exact approval or retry after the blocker is resolved."
        : ["queued", "blocked"].includes(primaryMissionOperationStatus)
          ? "This mission has retryable work parked in the queue or governance path. You can retry it directly from the ORB panel."
          : primaryMissionOperationStatus === "failed"
            ? "The latest linked operation failed. Review the ledger and linked task before deciding whether to rerun or revise the plan."
            : "This mission is currently in a steady state. Review continuity and linked traces before changing course.";
  const selectedMissionRecommendedAction = safeString(selectedMissionQueueItem?.recommended_action).trim();
  const selectedMissionDependencyState = selectedMissionQueueItem?.dependency_state;
  const selectedMissionDependencyStatus = safeString(selectedMissionDependencyState?.status).trim();
  const selectedMissionDependencyAction = ["wait_for_dependency", "resolve_dependency_blocker"].includes(
    selectedMissionRecommendedAction,
  );
  const selectedMissionAdvanceEligible = selectedMissionQueueItem?.advance?.eligible === true;
  const selectedMissionAdvanceAction = safeString(selectedMissionQueueItem?.advance?.action).trim();
  const selectedMissionAdvanceReason = safeString(selectedMissionQueueItem?.advance?.reason).trim();
  const selectedMissionRecovery = selectedMissionQueueItem?.recovery;
  const selectedMissionRecoveryAction = safeString(selectedMissionRecovery?.action).trim();
  const selectedMissionRecoveryTargetId = safeString(selectedMissionRecovery?.target_id).trim();
  const selectedMissionRecoveryReason = safeString(selectedMissionRecovery?.reason).trim();
  const selectedMissionRecoveryNextStep = safeString(selectedMissionRecovery?.next_step).trim();
  const selectedMissionRecoverySourceStatus = safeString(selectedMissionRecovery?.source_status).trim().toLowerCase();
  const selectedMissionRecoveryReplacementId = safeString(selectedMissionRecovery?.replacement_mission_id).trim();
  const selectedMissionRecoveryReplacementStatus = safeString(selectedMissionRecovery?.replacement_status).trim();
  const selectedMissionRecoveryReplacementLastTaskId = safeString(selectedMissionRecovery?.replacement_last_task_id).trim();
  const selectedMissionRecoveryReplacementLastTaskStatus = safeString(selectedMissionRecovery?.replacement_last_task_status).trim();
  const selectedMissionRecoveryReplacementNextStep = safeString(selectedMissionRecovery?.replacement_next_step).trim();
  const selectedMissionRecoveryReplacementUpdatedAt = mixedLocaleTime(selectedMissionRecovery?.replacement_updated_at);
  const selectedMissionRecoveryReplacementError = safeString(selectedMissionRecovery?.replacement_error).trim();
  const selectedMissionReplacementEligible = ["failed", "deadlettered"].includes(selectedMissionRecoverySourceStatus);
  const selectedMissionAdvanceLabel =
    selectedMissionAdvanceAction === "create_first_operation" ? "Create operation" : "Advance mission once";
  const selectedMissionActionTargetId = missionRecoveryTargetId(
    selectedMission,
    selectedMissionQueueItem,
    missionLoopHandoff,
    selectedMissionCurrentTask,
  );
  const selectedMissionTargetIsMission = selectedMissionActionTargetId.startsWith("msn_");
  const selectedMissionTargetIsOperation = selectedMissionActionTargetId.startsWith("tsk_");
  const selectedMissionApprovalId =
    safeString(selectedMissionCurrentTask?.approval_id).trim() ||
    safeString(selectedMissionQueueItem?.last_task_approval_id).trim() ||
    safeString(missionLoopHandoff?.approval_id).trim();
  const selectedMissionApprovalStatus =
    safeString(selectedMissionCurrentTask?.approval_status).trim() ||
    safeString(missionLoopHandoff?.approval_status).trim() ||
    safeString(selectedMissionQueueItem?.last_task_approval_status).trim();
  const selectedMissionFirstDependencyId =
    safeString(selectedMissionDependencyState?.first_unresolved?.id).trim() ||
    selectedMission?.dependency_ids?.find((dependencyId) => safeString(dependencyId).trim().length > 0) ||
    "";
  const selectedMissionDependencyTotal = Math.max(
    0,
    Number(selectedMissionDependencyState?.total ?? selectedMission?.dependency_count ?? selectedMission?.dependency_ids?.length ?? 0),
  );
  const selectedMissionDependencyResolved = Math.max(0, Number(selectedMissionDependencyState?.resolved ?? 0));
  const selectedMissionLastAdvanceAction = safeString(selectedMissionQueueItem?.last_advance_action).trim();
  const selectedMissionLastAdvanceOutcome = safeString(selectedMissionQueueItem?.last_advance_outcome).trim();
  const selectedMissionLastAdvanceOperationId = safeString(selectedMissionQueueItem?.last_advance_operation_id).trim();
  const selectedMissionLastRecoveryAction = safeString(selectedMissionQueueItem?.last_recovery_action).trim();
  const selectedMissionLastRecoveryOutcome = safeString(selectedMissionQueueItem?.last_recovery_outcome).trim();
  const selectedMissionLastRecoveryTargetId = safeString(selectedMissionQueueItem?.last_recovery_target_id).trim();
  const selectedMissionLastRecoveryAt = mixedLocaleTime(selectedMissionQueueItem?.last_recovery_at);
  const missionAdvanceBlockedReason = executionBlockedReason(props.operatorMode, "advancing mission continuity");
  const canAdvanceMission = missionAdvanceBlockedReason.length === 0;
  const missionReplaceBlockedReason = executionBlockedReason(props.operatorMode, "declaring replacement mission");
  const canReplaceMission = missionReplaceBlockedReason.length === 0;
  const missionQueueRunBlockedReason = executionBlockedReason(props.operatorMode, "running the mission queue");
  const canRunMissionQueue = missionQueueRunBlockedReason.length === 0;
  const inspectMission = useCallback((missionId: string) => {
    const cleaned = missionId.trim();
    if (!cleaned) return;
    setSelectedMissionId(cleaned);
  }, []);

  useEffect(() => {
    const cleaned = safeString(props.focusMissionId).trim();
    if (!cleaned) return;
    setSelectedMissionId(cleaned);
  }, [props.focusMissionId]);

  useEffect(() => {
    setSelectedMissionId((prev) => {
      if (prev && missionSelectionCandidates.includes(prev)) return prev;
      return missionSelectionCandidates[0] ?? "";
    });
  }, [missionSelectionKey, missionSelectionCandidates]);

  useEffect(() => {
    void loadMissionDetail(selectedMissionId);
  }, [loadMissionDetail, selectedMissionId]);

  useEffect(() => {
    setMissionActionNotice(null);
    setMissionActionResult(null);
  }, [selectedMissionId]);

  const advanceMission = useCallback(
    async (missionId: string) => {
      const cleaned = missionId.trim();
      if (!cleaned || !canAdvanceMission) return;
      setMissionActionBusy("advance");
      setMissionActionTargetId(cleaned);
      setMissionActionNotice(null);
      setMissionActionResult(null);
      try {
        const response = await missionsClient.advance(cleaned, {
          actor: "chat_ui.orb",
          note: "advance_from_orb_panel",
          worker_id: "chat_ui.orb",
        });
        const nextDetail = await loadMissionDetail(cleaned);
        await refresh();
        const actionHandoff = response.loop_state?.handoff ?? nextDetail?.loop_state?.handoff;
        const responseCurrentTask = response.current_task ?? nextDetail?.current_task;
        const nextMissionCurrentTaskId = missionCurrentTaskId(
          nextDetail?.mission,
          nextDetail?.queue_item,
          actionHandoff,
          responseCurrentTask,
        );
        const resolvedOperation =
          response.operation ?? missionCurrentOperation(nextDetail?.linked_operations ?? [], nextMissionCurrentTaskId);
        const approvalId = safeString(responseCurrentTask?.approval_id).trim() || operationApprovalId(resolvedOperation);
        const nextStatus = safeString(response.status || nextDetail?.mission?.status || response.mission?.status, "unknown");
        const operationId =
          safeString(responseCurrentTask?.operation_id).trim() ||
          safeString(response.operation_id).trim() ||
          safeString(resolvedOperation?.id).trim();
        const recoveryFields = missionOperationRecoveryFields(response);
        setMissionActionResult({
          missionId: cleaned,
          operationId: operationId || undefined,
          approvalId: approvalId || undefined,
          ...recoveryFields,
        });
        if (!response.ok) {
          const governanceText = missionGovernanceNotice(response.governance);
          setMissionActionNotice({
            tone: "error",
            text:
              governanceText ||
              response.error ||
              response.message ||
              `Mission advance failed with status ${nextStatus}.`,
          });
          return;
        }

        const summary = response.applied
          ? `Mission advanced once. Status is now ${nextStatus}.`
          : `Mission remains ${nextStatus}.`;
        const message = safeString(response.message).trim();
        const handoffDetail = safeString(actionHandoff?.detail).trim();
        const approvalMessage = approvalId ? ` Review approval ${approvalId}.` : "";
        setMissionActionNotice({
          tone: "info",
          text: `${summary}${message ? ` ${message}` : ""}${handoffDetail ? ` ${handoffDetail}` : ""}${approvalMessage}`,
        });
      } catch (err) {
        setMissionActionNotice({ tone: "error", text: missionError(err) });
      } finally {
        setMissionActionBusy("");
        setMissionActionTargetId("");
      }
    },
    [canAdvanceMission, loadMissionDetail, missionError, missionsClient, refresh],
  );

  const replaceMission = useCallback(
    async (missionId: string) => {
      const cleaned = missionId.trim();
      if (!cleaned || !canReplaceMission) return;
      setMissionActionBusy("replace");
      setMissionActionTargetId(cleaned);
      setMissionActionNotice(null);
      setMissionActionResult(null);
      try {
        const response = await missionsClient.replace(cleaned, {
          actor: "chat_ui.orb",
          note: "declare_replacement_from_orb_panel",
        });
        await refresh();
        const replacementId = safeString(response.replacement_mission_id).trim() || safeString(response.mission?.id).trim();
        if (replacementId) {
          setSelectedMissionId(replacementId);
          await loadMissionDetail(replacementId);
        } else {
          await loadMissionDetail(cleaned);
        }
        if (!response.ok) {
          setMissionActionNotice({
            tone: "error",
            text: response.error || response.message || "Replacement mission declaration failed.",
          });
          return;
        }

        setMissionActionResult({
          missionId: replacementId || cleaned,
        });
        setMissionActionNotice({
          tone: "info",
          text: replacementId
            ? `Replacement mission ${replacementId} declared. Source mission remains failed/deadlettered.`
            : "Replacement mission declared. Source mission remains failed/deadlettered.",
        });
      } catch (err) {
        setMissionActionNotice({ tone: "error", text: missionError(err) });
      } finally {
        setMissionActionBusy("");
        setMissionActionTargetId("");
      }
    },
    [canReplaceMission, loadMissionDetail, missionError, missionsClient, refresh],
  );

  const runMissionQueueOnce = useCallback(async () => {
    if (!canRunMissionQueue) return;
    setMissionQueueRunBusy(true);
    setMissionActionNotice(null);
    setMissionActionResult(null);
    try {
      const response = await missionsClient.runOnce({
        actor: "chat_ui.orb",
        note: "run_queue_once_from_orb_panel",
        limit: 6,
      });
      await refresh();
      if (selectedMissionId) {
        await loadMissionDetail(selectedMissionId);
      }

      setMissionQueueRunSummary({
        processed: response.processed ?? 0,
        applied: response.applied ?? 0,
        advanced: response.advanced ?? 0,
        status: response.status,
        error: response.error,
        errorCount: response.errors?.length ?? 0,
        counts: response.counts ?? {},
        request: response.request,
        results: (response.results ?? []).slice(0, 4).map((item) => {
          const recoveryFields = missionOperationRecoveryFields(item);
          return {
            missionId: item.mission_id,
            operationId: item.operation_id,
            approvalId: item.approval_id,
            action: item.action,
            activeStage: item.loop_state?.active_stage,
            status: item.status,
            gate: item.gate,
            nextStep: item.next_step,
            traceId: item.trace_id,
            runId: item.run_id,
            artifactDir: item.artifact_dir,
            queueItem: item.queue_item,
            currentTask: item.current_task,
            receiptSummary: item.receipt_summary,
            handoffAction: item.handoff?.action ?? item.loop_state?.handoff?.action,
            handoffDetail: item.handoff?.detail ?? item.loop_state?.handoff?.detail,
            historyCount: item.history_count,
            linkedOperationCount: item.linked_operation_count,
            runLedgerCount: item.run_ledger_count,
            message: item.message,
            ...recoveryFields,
          };
        }),
        errors: (response.errors ?? []).slice(0, 4).map((item) => {
          const governance = isRecord(item.governance) ? item.governance : {};
          const governanceDecision: MissionGovernanceDecision = {
            gate: safeString(governance.gate).trim(),
            reason: safeString(governance.reason).trim(),
            next_step: safeString(governance.next_step).trim(),
          };
          const recoveryFields = missionOperationRecoveryFields(item);
          return {
            missionId: safeString(item.mission_id).trim(),
            operationId: safeString(item.operation_id).trim() || safeString(item.task_id).trim(),
            approvalId: safeString(item.approval_id).trim(),
            action: safeString(item.action).trim(),
            status: safeString(item.status).trim(),
            gate: safeString(item.gate).trim() || safeString(governanceDecision.gate).trim(),
            nextStep: safeString(item.next_step).trim() || safeString(governanceDecision.next_step).trim(),
            traceId: safeString(item.trace_id).trim() || safeString(item.traceId).trim(),
            runId: safeString(item.run_id).trim() || safeString(item.runId).trim(),
            artifactDir: safeString(item.artifact_dir).trim() || safeString(item.artifact_path).trim(),
            error: safeString(item.error).trim(),
            message:
              safeString(item.message).trim() ||
              missionGovernanceNotice(governanceDecision) ||
              missionGovernanceNotice(response.governance),
            ...recoveryFields,
          };
        }),
      });

      if (!response.ok) {
        const governanceText = missionGovernanceNotice(response.governance);
        const firstError = isRecord(response.errors?.[0]) ? safeString(response.errors?.[0]?.error).trim() : "";
        setMissionActionNotice({
          tone: "error",
          text: governanceText || response.error || firstError || "Mission queue run did not complete cleanly.",
        });
        return;
      }

      setMissionActionNotice({
        tone: "info",
        text: `Mission queue pass processed ${String(response.processed ?? 0)} missions and advanced ${String(
          response.advanced ?? 0,
        )}. Continuity and backlog state have been refreshed.`,
      });
    } catch (err) {
      setMissionActionNotice({ tone: "error", text: missionError(err) });
    } finally {
      setMissionQueueRunBusy(false);
    }
  }, [canRunMissionQueue, loadMissionDetail, missionError, missionsClient, refresh, selectedMissionId]);

  const runMissionOperation = useCallback(
    async (operationId: string) => {
      const cleaned = operationId.trim();
      if (!cleaned) return;
      setMissionActionBusy("run");
      setMissionActionTargetId(cleaned);
      setMissionActionNotice(null);
      try {
        const response = await operationsClient.run(cleaned, { worker_id: "chat_ui.orb" });
        await loadMissionDetail(selectedMissionId || safeString(selectedMission?.id));
        await refresh();
        const nextStatus = safeString(response.operation?.status || response.status, "unknown");
        if (!response.ok) {
          setMissionActionNotice({
            tone: "error",
            text: response.message ? `Retry failed: ${response.message}` : `Retry failed with status ${nextStatus}.`,
          });
          return;
        }
        setMissionActionNotice({
          tone: "info",
          text:
            response.message === "already_terminal"
              ? `Operation is already ${nextStatus}.`
              : `Operation status is now ${nextStatus}.`,
        });
      } catch (err) {
        setMissionActionNotice({ tone: "error", text: operationsError(err) });
      } finally {
        setMissionActionBusy("");
        setMissionActionTargetId("");
      }
    },
    [loadMissionDetail, operationsClient, operationsError, refresh, selectedMission?.id, selectedMissionId],
  );

  const cancelMissionOperation = useCallback(
    async (operationId: string) => {
      const cleaned = operationId.trim();
      if (!cleaned) return;
      setMissionActionBusy("cancel");
      setMissionActionTargetId(cleaned);
      setMissionActionNotice(null);
      try {
        const response = await operationsClient.cancel(cleaned, { reason: "cancelled_from_orb_panel" });
        await loadMissionDetail(selectedMissionId || safeString(selectedMission?.id));
        await refresh();
        const nextStatus = safeString(response.status, "unknown");
        if (!response.ok) {
          setMissionActionNotice({
            tone: "error",
            text: response.message ? `Cancel failed: ${response.message}` : `Cancel failed with status ${nextStatus}.`,
          });
          return;
        }
        setMissionActionNotice({
          tone: "info",
          text: `Operation status is now ${nextStatus}.`,
        });
      } catch (err) {
        setMissionActionNotice({ tone: "error", text: operationsError(err) });
      } finally {
        setMissionActionBusy("");
        setMissionActionTargetId("");
      }
    },
    [loadMissionDetail, operationsClient, operationsError, refresh, selectedMission?.id, selectedMissionId],
  );
  const remainingTakeoverItems = [
    { label: "Queued", value: queuedTasks, tone: queuedTasks > 0 ? "queued" : "clear" },
    { label: "Blocked", value: blockedTasks, tone: blockedTasks > 0 ? "blocked" : "clear" },
    {
      label: "Awaiting approval",
      value: Math.max(approvalPendingTasks, pendingApprovals.length),
      tone: approvalPendingTasks > 0 || pendingApprovals.length > 0 ? "needs_approval" : "clear",
    },
  ].filter((item) => item.value > 0);
  const takeoverLead =
    currentTakeoverOperation !== null
      ? operationMessage(currentTakeoverOperation) ||
        `Status ${operationStatus(currentTakeoverOperation)} on ${operationLabel(currentTakeoverOperation)}.`
      : pilotActive
        ? "Pilot is active, but no live delegated operation is currently recorded."
        : "Pilot is not active. This feed remains observational until delegated execution is declared.";
  const handBackGuidance =
    interruptibleOperations.length > 0
      ? "Open Operations to cancel or let live work finish, then return to Assist from the control banner once the active run is settled."
      : pendingApprovals.length > 0 || blockedTasks > 0 || approvalPendingTasks > 0
        ? "Pilot is clear of active execution, but governance backlog remains. Resolve approvals and blocked work before handing back."
        : pilotActive
          ? "No live run is active. Review recent outcomes, then return to Assist when you want Francis back in collaborative posture."
          : "Declare Pilot only when you want Francis in delegated execution. Until then, this surface stays advisory.";
  const freshnessItems = [
    {
      id: "health",
      label: "Health",
      observedAt: health?.ts,
      error: healthError,
      staleAfterSeconds: 90,
      actionLabel: undefined,
      onAction: undefined,
      detail: healthError
        ? `Runtime heartbeat is degraded: ${healthError}`
        : `Service reports ${safeString(health?.status, health?.ok ? "ok" : "attention") || "unknown"}.`,
    },
    {
      id: "world-state",
      label: "World State",
      observedAt: worldState?.generated_at,
      error: worldStateError,
      staleAfterSeconds: 180,
      actionLabel: "Inspect missions",
      onAction: () => scrollOrbSection("francis-mission-feed"),
      detail: worldStateError
        ? `Showing the last retained local snapshot while refresh is failing: ${worldStateError}`
        : `${counts?.tasks ?? 0} tasks and ${declaredMissionCount} missions are visible in the local state snapshot.`,
    },
    {
      id: "continuity",
      label: "Continuity",
      observedAt: continuityBriefing?.generated_at,
      error: continuityBriefingError,
      staleAfterSeconds: 240,
      actionLabel: "Inspect briefing",
      onAction: () => scrollOrbSection("francis-shift-briefing"),
      detail: continuityBriefingError
        ? `Continuity briefing refresh failed: ${continuityBriefingError}`
        : safeString(shiftBriefing?.headline).trim() || "Shift briefing is available for return-to-work continuity.",
    },
    {
      id: "orb-status",
      label: "ORB Model",
      observedAt: orbStatus?.generated_at,
      error: orbStatusError,
      staleAfterSeconds: 300,
      actionLabel: "Inspect takeover",
      onAction: () => scrollOrbSection("francis-takeover-feed"),
      detail: orbStatusError
        ? `ORB model status could not refresh: ${orbStatusError}`
        : `${coreLoop.length} core loop planes and ${gateStack.length} governance gates are exposed in this snapshot.`,
    },
    {
      id: "operations",
      label: "Live Operations",
      observedAt: takeoverOperationsLoadedAt,
      error: takeoverOperationsError,
      staleAfterSeconds: 120,
      actionLabel: "Open operations",
      onAction: () => props.onOpenOperations(),
      detail: takeoverOperationsError
        ? `Showing the last retained execution feed while refresh is failing: ${takeoverOperationsError}`
        : `${takeoverOperations.length} recent operation${takeoverOperations.length === 1 ? "" : "s"} are cached from the execution feed.`,
    },
  ].map((item) => ({
    ...item,
    ...deriveFeedFreshness(item.observedAt, nowTs, {
      error: item.error,
      staleAfterSeconds: item.staleAfterSeconds,
    }),
  }));
  const degradedFreshnessItems = freshnessItems.filter((item) => item.state !== "live");
  const freshnessGuidance =
    degradedFreshnessItems.length > 0
      ? "Refresh stale or degraded feeds before approving, rerouting, or judging continuity state."
      : "All ORB feeds are fresh enough for operator review.";

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>ORB</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>
        Canonical ORB flow, gate stack, runtime snapshot, pending approvals, and recent task activity.
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 10 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <span style={badgeStyle(runtimeState)}>{runtimeState}</span>
          {worldState?.subsystem ? <span style={badgeStyle(worldState.subsystem)}>{worldState.subsystem}</span> : null}
          {worldState?.generated_at ? (
            <span style={{ fontSize: 11, color: THEME.muted }}>Snapshot {toLocaleTime(worldState.generated_at)}</span>
          ) : null}
        </div>
        <button onClick={() => void refresh()} disabled={busy} style={buttonStyle}>
          {busy ? "Refreshing." : "Refresh"}
        </button>
      </div>

      {error ? (
        <div
          style={{
            marginTop: 10,
            padding: 10,
            borderRadius: 10,
            border: `1px solid ${THEME.errorBorder}`,
            background: THEME.errorBg,
            fontSize: 12,
            color: "#ffaaaa",
          }}
        >
          <b>Error:</b> {error}
        </div>
      ) : null}

      {refreshNotice ? (
        <div
          style={{
            marginTop: 10,
            padding: 10,
            borderRadius: 10,
            border: "1px solid #5a4c18",
            background: "#1f1a0b",
            fontSize: 12,
            color: "#f4d27a",
          }}
        >
          <b>Refresh:</b> {refreshNotice}
        </div>
      ) : null}

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Snapshot Freshness</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{freshnessGuidance}</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              Auto-refresh runs every {Math.floor(autoRefreshIntervalMs / 1000)}s while the ORB panel is open and visible.
            </div>
          </div>
          <div style={{ fontSize: 11, color: THEME.muted, textAlign: "right" }}>
            <div>{lastRefreshCompletedAt ? `Settled ${toLocaleTime(lastRefreshCompletedAt)}` : "Refresh not completed yet"}</div>
            <div>{lastRefreshAttemptedAt ? `Requested ${toLocaleTime(lastRefreshAttemptedAt)}` : "No refresh attempt recorded"}</div>
          </div>
        </div>

        {infoError ? (
          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
            System info is degraded: {infoError}
          </div>
        ) : null}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: 8,
            marginTop: 10,
          }}
        >
          {freshnessItems.map((item) => (
            <div key={item.id} style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <div style={{ fontSize: 12, fontWeight: 600 }}>{item.label}</div>
                <span style={badgeStyle(item.state)}>{item.state}</span>
              </div>
              <div style={{ fontSize: 12, marginTop: 8 }}>{item.ageLabel}</div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                {item.observedAt ? `Observed ${toLocaleTime(item.observedAt)}` : "No successful snapshot recorded yet."}
              </div>
              <div style={{ fontSize: 11, color: item.error ? "#ffcf9d" : THEME.muted, marginTop: 6 }}>{item.detail}</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                <button style={buttonStyle} disabled={busy} onClick={() => void refresh()}>
                  {busy ? "Refreshing." : item.state === "live" ? "Refresh now" : "Retry now"}
                </button>
                {item.onAction && item.actionLabel ? (
                  <button style={buttonStyle} onClick={item.onAction}>
                    {item.actionLabel}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8, marginTop: 12 }}>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Pending approvals</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{counts?.pending_approvals ?? 0}</div>
        </div>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Awaiting approval</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{approvalPendingTasks}</div>
        </div>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Blocked tasks</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{blockedTasks}</div>
        </div>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Queued tasks</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{queuedTasks}</div>
        </div>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Running now</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{runningTasks}</div>
        </div>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Active incidents</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{activeIncidents}</div>
        </div>
        <div
          style={{
            ...summaryCardStyle(),
            background: controlTone.bg,
            border: `1px solid ${controlTone.border}`,
          }}
        >
          <div style={{ fontSize: 11, color: THEME.muted }}>Control mode</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4, color: controlTone.color }}>
            {controlMode?.label || "Unknown"}
          </div>
        </div>
        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 11, color: THEME.muted }}>Total tasks</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{counts?.tasks ?? 0}</div>
        </div>
      </div>

      {controlMode ? (
        <div
          style={{
            ...summaryCardStyle(),
            marginTop: 12,
            background: controlTone.bg,
            border: `1px solid ${controlTone.border}`,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Control Posture</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <span style={badgeStyle(controlMode.label || controlMode.id || "mode")}>
                {controlMode.label || controlMode.id || "mode"}
              </span>
              {controlMode.implementation_status ? (
                <span style={badgeStyle(controlMode.implementation_status)}>{controlMode.implementation_status}</span>
              ) : null}
            </div>
          </div>
          <div style={{ fontSize: 12, color: controlTone.color, marginTop: 8 }}>
            {controlMode.summary || "Current legal control mode not available."}
          </div>
          {controlMode.reason ? (
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
              reason <code>{controlMode.reason}</code>
            </div>
          ) : null}
          {controlMode.changed_by || controlMode.changed_at ? (
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              {controlMode.changed_by ? `by ${controlMode.changed_by}` : "mode change recorded"}
              {controlMode.changed_at ? ` at ${toLocaleTime(controlMode.changed_at)}` : ""}
            </div>
          ) : null}
        </div>
      ) : null}

      <div id="francis-shift-briefing" style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Shift Briefing</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              {safeString(shiftBriefing?.headline).trim() || "Shift briefing is available once continuity state is recorded."}
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <span style={badgeStyle(shiftBriefingBlocked > 0 ? "blocked" : "clear")}>blocked {shiftBriefingBlocked}</span>
            <span style={badgeStyle(shiftBriefingQueued > 0 ? "queued" : "clear")}>queued {shiftBriefingQueued}</span>
            <span style={badgeStyle(shiftBriefingFailedCount > 0 ? "failed" : "clear")}>failed {shiftBriefingFailedCount}</span>
            <span style={badgeStyle(shiftBriefingCompletedCount > 0 ? "completed" : "clear")}>
              completed {shiftBriefingCompletedCount}
            </span>
            <span style={badgeStyle(shiftBriefingMemoryReceiptCount > 0 ? "memory" : "clear")}>
              memory receipts {shiftBriefingMemoryReceiptCount}
            </span>
            <span style={badgeStyle(shiftBriefingDeadletterCount > 0 ? "deadlettered" : "clear")}>
              deadlettered {shiftBriefingDeadletterCount}
            </span>
            {continuityBriefing?.generated_at ? (
              <span style={{ fontSize: 11, color: THEME.muted }}>Snapshot {toLocaleTime(continuityBriefing.generated_at)}</span>
            ) : null}
          </div>
        </div>

        {continuityBriefingError ? (
          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
            Briefing feed unavailable: {continuityBriefingError}
          </div>
        ) : null}

        <MissionReadinessEvidencePanel
          title="Mission readiness"
          readiness={shiftBriefingReadiness}
          keyPrefix="mission-readiness"
          criterionLimit={3}
          evidenceLimit={4}
          showCriteriaBadges
          detailCards
          marginTop={10}
        />

        {shiftBriefingMemoryReceipts.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>Memory Evidence</div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                  Completed mission operation receipts from continuity.
                </div>
              </div>
              <span style={badgeStyle("memory")}>receipts {shiftBriefingMemoryReceiptCount}</span>
            </div>
            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
              {shiftBriefingMemoryReceipts.slice(0, 3).map((receipt, receiptIndex) => {
                const receiptReferenceLine = missionMemoryReceiptReferenceLine(receipt);
                const receiptHandoffLine = missionMemoryReceiptHandoffLine(receipt);
                const receiptAt = mixedLocaleTime(receipt.ts);
                const receiptOperationId = safeString(receipt.operation_id).trim();
                const receiptMissionId = safeString(receipt.mission_id).trim();
                return (
                  <div
                    key={`shift-memory-receipt-${receipt.id || receiptMissionId || "unknown"}-${receiptOperationId || receiptIndex}`}
                    style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#101010" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <div style={{ fontSize: 11, fontWeight: 600 }}>{receipt.id || receiptOperationId || "memory receipt"}</div>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {receipt.operation_status ? <span style={badgeStyle(receipt.operation_status)}>{receipt.operation_status}</span> : null}
                        {receipt.source ? <span style={badgeStyle(receipt.source)}>{receipt.source}</span> : null}
                      </div>
                    </div>
                    {receiptReferenceLine ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{receiptReferenceLine}</div>
                    ) : null}
                    {receiptHandoffLine ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{receiptHandoffLine}</div>
                    ) : null}
                    {receipt.capability || receipt.domain || receipt.scope || receiptAt ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        {receipt.capability ? (
                          <>
                            capability=<code>{receipt.capability}</code>
                          </>
                        ) : null}
                        {receipt.domain ? (
                          <>
                            {receipt.capability ? " / " : ""}domain=<code>{receipt.domain}</code>
                          </>
                        ) : null}
                        {receipt.scope ? (
                          <>
                            {(receipt.capability || receipt.domain) ? " / " : ""}scope=<code>{receipt.scope}</code>
                          </>
                        ) : null}
                        {receiptAt ? (
                          <>
                            {(receipt.capability || receipt.domain || receipt.scope) ? " / " : ""}at=<code>{receiptAt}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      {receiptOperationId ? (
                        <button style={buttonStyle} onClick={() => props.onOpenOperation(receiptOperationId)}>
                          Open task
                        </button>
                      ) : null}
                      {receiptMissionId ? (
                        <button style={buttonStyle} onClick={() => inspectMission(receiptMissionId)}>
                          Inspect mission
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        {(continuityOperatorSurface || continuityOrbSurface) && !continuityBriefingError ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 8,
              marginTop: 12,
            }}
          >
            <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Embedded Operator Surface</div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                Continuity carries the last operator posture seen during the briefing snapshot.
              </div>
              {continuityOperatorSurface?.available ? (
                <>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                    <span style={badgeStyle(continuityOperatorModeLabel)}>{continuityOperatorModeLabel}</span>
                    {continuityOperatorWrites ? (
                      <span style={badgeStyle(continuityOperatorWrites)}>{continuityOperatorWrites}</span>
                    ) : null}
                    {continuityOperatorFocus ? <span style={badgeStyle(continuityOperatorFocus)}>{continuityOperatorFocus}</span> : null}
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                    {safeString(continuityOperatorMode?.summary).trim() ||
                      "Dedicated operator-mode polling can degrade; this briefing snapshot keeps the last declared posture visible."}
                  </div>
                  {typeof continuityOperatorTrustLevel === "number" && Number.isFinite(continuityOperatorTrustLevel) ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      trust <code>{continuityOperatorTrustLevel.toFixed(2)}</code>
                    </div>
                  ) : null}
                </>
              ) : (
                <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
                  {safeString(continuityOperatorSurface?.error).trim() ||
                    "Embedded operator posture is unavailable in this briefing snapshot."}
                </div>
              )}
            </div>

            <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Embedded Orb Surface</div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                Continuity also carries the last orb handback state so return-to-work context stays inspectable.
              </div>
              {continuityOrbSurface?.available ? (
                <>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                    {continuityOrbRenderState ? <span style={badgeStyle(continuityOrbRenderState)}>{continuityOrbRenderState}</span> : null}
                    {continuityOrbHandbackStatus ? (
                      <span style={badgeStyle(continuityOrbHandbackStatus)}>{continuityOrbHandbackStatus}</span>
                    ) : null}
                    {continuityOrbPressureLevel ? (
                      <span style={badgeStyle(continuityOrbPressureLevel)}>
                        pressure {continuityOrbPressureLevel}
                      </span>
                    ) : null}
                    {continuityOrbPressureSource ? (
                      <span style={badgeStyle(continuityOrbPressureSource)}>{continuityOrbPressureSource}</span>
                    ) : null}
                    {continuityOrbPressureSource === "observer" ? (
                      <span style={badgeStyle(safeString(continuityOrbPressureObserver?.level).trim() || "clear")}>
                        anomaly {continuityOrbPressureScore}/100
                      </span>
                    ) : null}
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                    {continuityOrbHandbackHeadline ||
                      "Dedicated ORB model polling can degrade; this briefing snapshot keeps the last handback state visible."}
                  </div>
                  {continuityOrbPressureSource === "observer" && continuityOrbPressureHeadline ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      Observer-backed pressure: {continuityOrbPressureHeadline}
                    </div>
                  ) : null}
                  {continuityOrbPressureSource === "observer" && continuityOrbPressureReasons ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{continuityOrbPressureReasons}</div>
                  ) : null}
                </>
              ) : (
                <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
                  {safeString(continuityOrbSurface?.error).trim() ||
                    "Embedded orb handback state is unavailable in this briefing snapshot."}
                </div>
              )}
            </div>
          </div>
        ) : null}

        {shiftBriefingObserver ? (
          <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212", marginTop: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>Embedded Observer Surface</div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                  {safeString(shiftBriefingObserver.headline).trim() || "Observer findings are embedded here when available."}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end", alignItems: "center" }}>
                <span style={badgeStyle(shiftBriefingObserverActive > 0 ? "warning" : "clear")}>
                  active {shiftBriefingObserverActive}
                </span>
                <span style={badgeStyle(shiftBriefingObserverCritical > 0 ? "critical" : "clear")}>
                  critical {shiftBriefingObserverCritical}
                </span>
                <span style={badgeStyle(shiftBriefingObserverError > 0 ? "error" : "clear")}>
                  error {shiftBriefingObserverError}
                </span>
                <span style={badgeStyle(shiftBriefingObserverWarning > 0 ? "warning" : "clear")}>
                  warning {shiftBriefingObserverWarning}
                </span>
                {shiftBriefingObserverHasAnomaly ? (
                  <span style={badgeStyle(shiftBriefingObserverAnomalyLevel)}>
                    anomaly {shiftBriefingObserverAnomalyScore}/100
                  </span>
                ) : null}
                {shiftBriefingObserver.observed_at ? (
                  <span style={{ fontSize: 11, color: THEME.muted }}>Observed {toLocaleTime(shiftBriefingObserver.observed_at)}</span>
                ) : null}
                <button style={buttonStyle} disabled={busy || observerScanBusy} onClick={() => void recordObserverScan()}>
                  {observerScanBusy ? "Scanning." : "Record observer scan"}
                </button>
              </div>
            </div>
            {safeString(shiftBriefingObserver.error).trim() ? (
              <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>{safeString(shiftBriefingObserver.error).trim()}</div>
            ) : null}
            {observerScanNotice ? (
              <div
                style={{
                  fontSize: 11,
                  marginTop: 8,
                  color: observerScanNotice.tone === "error" ? "#ffb0b0" : "#d7f0c8",
                }}
              >
                {observerScanNotice.text}
              </div>
            ) : null}
            {shiftBriefingObserverHasAnomaly ? (
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                Anomaly score {shiftBriefingObserverAnomalyScore}/100
                {shiftBriefingObserverAnomalyReasons ? `. ${shiftBriefingObserverAnomalyReasons}` : "."}
              </div>
            ) : null}
            {shiftBriefingObserverReadiness ? (
              <div style={{ marginTop: 10, border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#0f0f0f" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600 }}>Observer readiness</div>
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      {shiftBriefingObserverReadiness.stage || "Stage 2 - Observer"}
                      {typeof shiftBriefingObserverReadiness.satisfied === "number" &&
                      typeof shiftBriefingObserverReadiness.total === "number"
                        ? ` / ${shiftBriefingObserverReadiness.satisfied}/${shiftBriefingObserverReadiness.total} criteria`
                        : ""}
                    </div>
                  </div>
                  {shiftBriefingObserverReadiness.status ? (
                    <span style={badgeStyle(shiftBriefingObserverReadiness.status)}>
                      {shiftBriefingObserverReadiness.status}
                    </span>
                  ) : null}
                </div>
                {shiftBriefingObserverReadiness.next_action ? (
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                    {shiftBriefingObserverReadiness.next_action}
                  </div>
                ) : null}
                {shiftBriefingObserverReadinessCriteria.length ? (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                    {shiftBriefingObserverReadinessCriteria.map((criterion) => (
                      <span key={`observer-readiness-${criterion.id || criterion.label}`} style={badgeStyle(criterion.status || "unknown")}>
                        {criterion.label || criterion.id || "criterion"}: {criterion.status || "unknown"}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600 }}>Observer probes</div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                These are the bounded probe results behind the current observer summary.
              </div>
              <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                {shiftBriefingObserverProbes.length === 0 ? (
                  <div style={{ fontSize: 11, color: THEME.muted }}>No probe summaries are embedded in this snapshot yet.</div>
                ) : (
                  shiftBriefingObserverProbes.map((probe) => (
                    <div
                      key={`observer-probe-${probe.id || probe.headline}`}
                      style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#0f0f0f" }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                        <div style={{ fontSize: 11, fontWeight: 600 }}>{probe.headline || probe.id || "Observer probe"}</div>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {probe.id ? <span style={badgeStyle(probe.id)}>{probe.id}</span> : null}
                          {probe.status ? <span style={badgeStyle(probe.status)}>{probe.status}</span> : null}
                          {probe.severity ? <span style={badgeStyle(probe.severity)}>{probe.severity}</span> : null}
                          {typeof probe.incident_count === "number" ? (
                            <span style={badgeStyle(probe.incident_count > 0 ? "warning" : "clear")}>
                              incidents {probe.incident_count}
                            </span>
                          ) : null}
                        </div>
                      </div>
                      {probe.detail ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{probe.detail}</div>
                      ) : null}
                      {probe.observed_at ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          observed <code>{mixedLocaleTime(probe.observed_at)}</code>
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
            </div>
            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
              {shiftBriefingObserverFocus.length === 0 ? (
                <div style={{ fontSize: 11, color: THEME.muted }}>No active observer incidents are embedded in this snapshot.</div>
              ) : (
                shiftBriefingObserverFocus.slice(0, 2).map((incident) => {
                  const approvalId = safeString(incident.approval_id).trim();
                  const taskId = safeString(incident.task_id).trim();
                  const evidenceLines = incidentEvidenceSummary(incident);
                  const observedAt = mixedLocaleTime(incident.observed_at);
                  return (
                    <div
                      key={`observer-focus-${incident.id}`}
                      style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#0f0f0f" }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                        <div style={{ fontSize: 11, fontWeight: 600 }}>{incident.title || incident.id}</div>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {incident.severity ? <span style={badgeStyle(incident.severity)}>{incident.severity}</span> : null}
                          {incident.category ? <span style={badgeStyle(incident.category)}>{incident.category}</span> : null}
                        </div>
                      </div>
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                        {incident.detail || "Observer detail unavailable."}
                      </div>
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        source=<code>{incident.source || "unknown"}</code>
                        {incident.probe ? (
                          <>
                            {" / "}probe=<code>{incident.probe}</code>
                          </>
                        ) : null}
                        {typeof incident.count === "number" ? ` / count=${String(incident.count)}` : ""}
                        {observedAt ? (
                          <>
                            {" / "}at=<code>{observedAt}</code>
                          </>
                        ) : null}
                      </div>
                      {evidenceLines.length > 0 ? (
                        <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
                          {evidenceLines.map((line) => (
                            <div key={`${incident.id}:${line}`} style={{ fontSize: 11, color: THEME.muted }}>
                              evidence <code>{line}</code>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                        {approvalId ? (
                          <button
                            style={buttonStyle}
                            onClick={() =>
                              props.onOpenApprovals(approvalId, {
                                operationId: taskId || undefined,
                              })
                            }
                          >
                            Review approval
                          </button>
                        ) : null}
                        {taskId ? (
                          <button style={buttonStyle} onClick={() => props.onOpenOperation(taskId)}>
                            Open task
                          </button>
                        ) : null}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600 }}>Recent explicit observer scans</div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                This is the bounded decisions log for manual observer scans. Passive briefing reads do not create these receipts.
              </div>
              <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                {shiftBriefingObserverRecentScans.length === 0 ? (
                  <div style={{ fontSize: 11, color: THEME.muted }}>No explicit observer scan receipts are embedded in this snapshot yet.</div>
                ) : (
                  shiftBriefingObserverRecentScans.slice(0, 2).map((scan) => renderObserverScanCard(scan, "observer-scan"))
                )}
              </div>
            </div>
          </div>
        ) : null}

        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Focus Now</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {shiftBriefingFocus.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>
              No live continuity focus items are recorded yet. Francis is clear to accept the next governed objective.
            </div>
          ) : (
            shiftBriefingFocus.slice(0, 3).map((item) => {
              const currentTask = item.current_task;
              const targetId = missionRecoveryTargetId(item, item, undefined, currentTask);
              const targetOperationId = missionCurrentTaskId(item, item, undefined, currentTask);
              const targetIsMission = targetId.startsWith("msn_");
              const targetIsOperation = targetId.startsWith("tsk_");
              const currentTaskId = safeString(currentTask?.operation_id).trim();
              const currentTaskStatus =
                safeString(currentTask?.task_status).trim() || safeString(currentTask?.operation_status).trim();
              const currentTaskResult = safeString(currentTask?.result_status).trim();
              const currentTaskGate = safeString(currentTask?.gate).trim();
              const currentTaskSource = safeString(currentTask?.source).trim();
              const currentTaskReceiptEvent = safeString(currentTask?.latest_receipt_event).trim();
              const currentTaskReceiptStatus = safeString(currentTask?.latest_receipt_status).trim();
              const dependencyState = item.dependency_state;
              const dependencyStatus = safeString(dependencyState?.status).trim();
              const dependencyIds = Array.isArray(item.dependency_ids)
                ? item.dependency_ids.map((dependencyId) => safeString(dependencyId).trim()).filter(Boolean)
                : [];
              const dependencyTotal = Math.max(
                0,
                Number(dependencyState?.total ?? item.dependency_count ?? dependencyIds.length ?? 0),
              );
              const dependencyResolved = Math.max(0, Number(dependencyState?.resolved ?? 0));
              const firstDependency = dependencyState?.first_unresolved;
              const firstDependencyId = safeString(firstDependency?.id).trim() || dependencyIds[0] || "";
              const recommendedAction = safeString(item.recommended_action).trim();
              const dependencyAction = ["wait_for_dependency", "resolve_dependency_blocker"].includes(recommendedAction);
              const advanceAction = safeString(item.advance?.action).trim();
              const briefingAdvanceAction = item.advance?.eligible === true;
              const briefingAdvanceLabel =
                advanceAction === "create_first_operation" ? "Create operation" : "Advance once";
              const escalationPath = safeString(item.escalation_path).trim();
              const approvalId = safeString(currentTask?.approval_id).trim() || safeString(item.last_task_approval_id).trim();
              const approvalStatus =
                safeString(currentTask?.approval_status).trim() || safeString(item.last_task_approval_status).trim();
              const focusDetail =
                safeString(currentTask?.reason).trim() ||
                safeString(currentTask?.next_step).trim() ||
                safeString(item.operator_hint).trim() ||
                safeString(item.next_step).trim() ||
                safeString(item.last_advance_message).trim() ||
                escalationPath ||
                safeString(item.summary).trim() ||
                safeString(item.deadletter_reason).trim() ||
                "Mission continuity exists, but the next-step note is still blank.";
              const latestActivity = latestActivitySummary(item.latest_activity);
              const latestHistoryAt = mixedLocaleTime(item.latest_history_ts);
              const historyTail = Array.isArray(item.history_tail) ? item.history_tail.slice(-2) : [];
              return (
                <div
                  key={`shift-focus-${item.id}`}
                  style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>{item.objective || item.id}</div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span style={badgeStyle(item.status || "unknown")}>{item.status || "unknown"}</span>
                      {item.recommended_action ? (
                        <span style={badgeStyle(item.recommended_action)}>{item.recommended_action}</span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{focusDetail}</div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    priority=<code>{String(item.priority ?? 0)}</code>
                    {" / "}risk=<code>{item.risk_tier || "unknown"}</code>
                    {" / "}linked_tasks=<code>{String(item.linked_task_count ?? 0)}</code>
                  </div>
                  {dependencyTotal > 0 ? (
                    <div style={{ fontSize: 11, color: dependencyAction ? "#ffcf9d" : THEME.muted, marginTop: 4 }}>
                      dependencies=<code>{String(dependencyResolved)}/{String(dependencyTotal)}</code>
                      {" / "}state=<code>{dependencyStatus || "unknown"}</code>
                      {firstDependencyId ? (
                        <>
                          {" / "}next=<code>{firstDependencyId}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {escalationPath ? (
                    <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>
                      escalation <code>{escalationPath}</code>
                    </div>
                  ) : null}
                  {approvalId ? (
                    <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>
                      approval=<code>{approvalId}</code>
                      {approvalStatus ? (
                        <>
                          {" / "}approval_status=<code>{approvalStatus}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {currentTaskId || currentTaskStatus || currentTaskResult || currentTaskGate || currentTaskReceiptEvent || currentTaskReceiptStatus ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      {currentTaskId ? (
                        <>
                          current_task=<code>{currentTaskId}</code>
                        </>
                      ) : null}
                      {currentTaskStatus ? (
                        <>
                          {currentTaskId ? " / " : ""}task_status=<code>{currentTaskStatus}</code>
                        </>
                      ) : null}
                      {currentTaskResult ? (
                        <>
                          {(currentTaskId || currentTaskStatus) ? " / " : ""}result=<code>{currentTaskResult}</code>
                        </>
                      ) : null}
                      {currentTaskGate ? (
                        <>
                          {(currentTaskId || currentTaskStatus || currentTaskResult) ? " / " : ""}gate=<code>{currentTaskGate}</code>
                        </>
                      ) : null}
                      {currentTaskSource ? (
                        <>
                          {" / "}source=<code>{currentTaskSource}</code>
                        </>
                      ) : null}
                      {currentTaskReceiptEvent ? (
                        <>
                          {" / "}receipt=<code>{currentTaskReceiptEvent}</code>
                        </>
                      ) : null}
                      {currentTaskReceiptStatus ? (
                        <>
                          {" / "}receipt_status=<code>{currentTaskReceiptStatus}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {latestActivity.name || latestActivity.status || latestActivity.gate || latestActivity.observedAt ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      latest=
                      <code>{latestActivity.name || "activity"}</code>
                      {" / "}status=<code>{latestActivity.status || "unknown"}</code>
                      {latestActivity.gate ? (
                        <>
                          {" / "}gate=<code>{latestActivity.gate}</code>
                        </>
                      ) : null}
                      {latestActivity.observedAt ? (
                        <>
                          {" / "}at=<code>{latestActivity.observedAt}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {(item.history_count || item.latest_history_event || latestHistoryAt) ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      receipts=<code>{String(item.history_count || 0)}</code>
                      {item.latest_history_event ? (
                        <>
                          {" / "}latest_receipt=<code>{item.latest_history_event}</code>
                        </>
                      ) : null}
                      {latestHistoryAt ? (
                        <>
                          {" / "}receipt_at=<code>{latestHistoryAt}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {historyTail.length > 0 ? (
                    <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                      {historyTail.map((entry, historyIndex) => (
                        <div
                          key={`shift-focus-history-${item.id}-${entry.ts || "unknown"}-${entry.event || historyIndex}`}
                          style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#101010" }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                            <div style={{ fontSize: 11, fontWeight: 600 }}>{entry.event || "receipt"}</div>
                            <div style={{ fontSize: 11, color: THEME.muted }}>{mixedLocaleTime(entry.ts) || entry.ts || "unknown time"}</div>
                          </div>
                          {entry.details && Object.keys(entry.details).length > 0 ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{prettyData(entry.details)}</div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                    {approvalId ? (
                      <button
                        style={buttonStyle}
                        onClick={() =>
                          props.onOpenApprovals(approvalId, {
                            missionId: item.id,
                            operationId: targetIsOperation ? targetId : targetOperationId || undefined,
                          })
                        }
                      >
                        Review approval
                      </button>
                    ) : null}
                    {briefingAdvanceAction ? (
                      <button
                        style={buttonStyle}
                        onClick={() => void advanceMission(item.id)}
                        disabled={!canAdvanceMission || missionActionBusy !== "" || missionQueueRunBusy}
                      >
                        {missionActionBusy === "advance" && missionActionTargetId === item.id
                          ? "Advancing."
                          : briefingAdvanceLabel}
                      </button>
                    ) : null}
                    <button style={buttonStyle} onClick={() => inspectMission(item.id)}>
                      Inspect mission flow
                    </button>
                    {targetId && (targetIsMission || targetIsOperation) ? (
                      <button
                        style={buttonStyle}
                        onClick={() => (targetIsMission ? inspectMission(targetId) : props.onOpenOperation(targetId))}
                      >
                        {targetIsMission ? "Open dependency mission" : "Open linked task"}
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {shiftBriefingCompleted.length > 0 || shiftBriefingFailed.length > 0 || shiftBriefingDeadletter.length > 0 ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 8,
              marginTop: 12,
            }}
          >
            <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Recently Completed</div>
              <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                {shiftBriefingCompleted.length === 0 ? (
                  <div style={{ fontSize: 11, color: THEME.muted }}>No recent completions recorded.</div>
                ) : (
                  shiftBriefingCompleted.slice(0, 2).map((item) => {
                    const completedCurrentTask = item.current_task;
                    const completedOperationId =
                      safeString(completedCurrentTask?.operation_id).trim() || safeString(item.last_task_id).trim();
                    const completedTaskStatus =
                      safeString(completedCurrentTask?.task_status).trim() ||
                      safeString(completedCurrentTask?.operation_status).trim();
                    const completedTaskResult = safeString(completedCurrentTask?.result_status).trim();
                    const completedTaskHandoffAction = safeString(completedCurrentTask?.handoff_action).trim();
                    const completedTaskNextStep = safeString(completedCurrentTask?.next_step).trim();
                    const completedLatestHistoryAt = mixedLocaleTime(item.latest_history_ts);
                    const completedHistoryTail = Array.isArray(item.history_tail) ? item.history_tail.slice(-2) : [];
                    return (
                    <div key={`shift-complete-${item.id}`}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                        <div style={{ fontSize: 11, fontWeight: 600 }}>{item.objective || item.id}</div>
                        <span style={badgeStyle(item.last_advance_outcome || "completed")}>
                          {item.last_advance_outcome || "completed"}
                        </span>
                      </div>
                      {item.last_advance_action ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          action <code>{item.last_advance_action}</code>
                        </div>
                      ) : null}
                      {completedOperationId || completedTaskStatus || completedTaskResult ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          {completedOperationId ? (
                            <>
                              current_task=<code>{completedOperationId}</code>
                            </>
                          ) : null}
                          {completedTaskStatus ? (
                            <>
                              {completedOperationId ? " / " : ""}task_status=<code>{completedTaskStatus}</code>
                            </>
                          ) : null}
                          {completedTaskResult ? (
                            <>
                              {(completedOperationId || completedTaskStatus) ? " / " : ""}result=<code>{completedTaskResult}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {completedTaskHandoffAction || completedTaskNextStep ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          {completedTaskHandoffAction ? (
                            <>
                              handoff=<code>{completedTaskHandoffAction}</code>
                            </>
                          ) : null}
                          {completedTaskNextStep ? (
                            <>
                              {completedTaskHandoffAction ? " / " : ""}next=<code>{completedTaskNextStep}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {(item.history_count || item.latest_history_event || completedLatestHistoryAt) ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          receipts=<code>{String(item.history_count || 0)}</code>
                          {item.latest_history_event ? (
                            <>
                              {" / "}latest_receipt=<code>{item.latest_history_event}</code>
                            </>
                          ) : null}
                          {completedLatestHistoryAt ? (
                            <>
                              {" / "}receipt_at=<code>{completedLatestHistoryAt}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {completedHistoryTail.length > 0 ? (
                        <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                          {completedHistoryTail.map((entry, historyIndex) => (
                            <div
                              key={`shift-complete-history-${item.id}-${entry.ts || "unknown"}-${entry.event || historyIndex}`}
                              style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#101010" }}
                            >
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                                <div style={{ fontSize: 11, fontWeight: 600 }}>{entry.event || "receipt"}</div>
                                <div style={{ fontSize: 11, color: THEME.muted }}>{mixedLocaleTime(entry.ts) || entry.ts || "unknown time"}</div>
                              </div>
                              {entry.details && Object.keys(entry.details).length > 0 ? (
                                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{prettyData(entry.details)}</div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ) : null}
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                        {completedOperationId ? (
                          <button style={buttonStyle} onClick={() => props.onOpenOperation(completedOperationId)}>
                            Open current task
                          </button>
                        ) : null}
                        <button style={buttonStyle} onClick={() => inspectMission(item.id)}>
                          Inspect
                        </button>
                      </div>
                    </div>
                    );
                  })
                )}
              </div>
            </div>

            <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Failed Mission Recovery</div>
              <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                {shiftBriefingFailedPresentation.total === 0 ? (
                  <div style={{ fontSize: 11, color: THEME.muted }}>No failed missions waiting for recovery.</div>
                ) : (
                  shiftBriefingFailedPresentation.visible.map((item) => {
                    const failedCurrentTask = item.current_task;
                    const recovery = item.recovery;
                    const recoveryAction = safeString(recovery?.action).trim() || safeString(item.recommended_action).trim();
                    const recoveryTargetId =
                      safeString(recovery?.target_id).trim() ||
                      safeString(item.action_target_id).trim() ||
                      safeString(failedCurrentTask?.operation_id).trim() ||
                      safeString(item.last_task_id).trim();
                    const recoveryReason = safeString(recovery?.reason).trim() || safeString(item.reason).trim();
                    const recoveryNextStep = safeString(recovery?.next_step).trim();
                    const lastRecoveryAction =
                      safeString(item.last_recovery_action).trim() || safeString(recovery?.last_review_action).trim();
                    const lastRecoveryOutcome =
                      safeString(item.last_recovery_outcome).trim() || safeString(recovery?.last_review_outcome).trim();
                    const lastRecoveryAt = mixedLocaleTime(
                      safeString(item.last_recovery_at).trim() || safeString(recovery?.last_reviewed_at).trim(),
                    );
                    const failedTaskStatus =
                      safeString(failedCurrentTask?.task_status).trim() ||
                      safeString(failedCurrentTask?.operation_status).trim() ||
                      safeString(item.last_task_status).trim();
                    const failedTaskResult =
                      safeString(failedCurrentTask?.result_status).trim() ||
                      safeString(item.last_task_result_status).trim();
                    return (
                      <div key={`shift-failed-${item.id}`}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                          <div style={{ fontSize: 11, fontWeight: 600 }}>{item.objective || item.id}</div>
                          <span style={badgeStyle(item.status || "failed")}>{item.status || "failed"}</span>
                        </div>
                        <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>
                          recovery=<code>{recoveryAction || "retry_or_deadletter"}</code>
                          {recoveryTargetId ? (
                            <>
                              {" / "}target=<code>{recoveryTargetId}</code>
                            </>
                          ) : null}
                          {" / "}automatic_retry=<code>{recovery?.automatic_retry ? "true" : "false"}</code>
                        </div>
                        {recoveryReason ? (
                          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{recoveryReason}</div>
                        ) : null}
                        {recoveryNextStep ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{recoveryNextStep}</div>
                        ) : null}
                        <MissionRecoveryFollowthroughCard recovery={recovery} onOpenMission={inspectMission} />
                        {lastRecoveryAction ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            reviewed=<code>{lastRecoveryAction}</code>
                            {lastRecoveryOutcome ? (
                              <>
                                {" / "}outcome=<code>{lastRecoveryOutcome}</code>
                              </>
                            ) : null}
                            {lastRecoveryAt ? (
                              <>
                                {" / "}at=<code>{lastRecoveryAt}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {failedTaskStatus || failedTaskResult ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {failedTaskStatus ? (
                              <>
                                task_status=<code>{failedTaskStatus}</code>
                              </>
                            ) : null}
                            {failedTaskResult ? (
                              <>
                                {failedTaskStatus ? " / " : ""}result=<code>{failedTaskResult}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                          {recoveryTargetId.startsWith("tsk_") ? (
                            <button style={buttonStyle} onClick={() => props.onOpenOperation(recoveryTargetId)}>
                              Open failed task
                            </button>
                          ) : null}
                          <button style={buttonStyle} onClick={() => inspectMission(item.id)}>
                            Inspect
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
              {shiftBriefingFailedPresentation.hiddenTotal > 0 ? (
                <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
                  Hidden from this bounded view: <code>{String(shiftBriefingFailedPresentation.hiddenTotal)}</code>
                </div>
              ) : null}
            </div>

            <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Deadletter Review</div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                showing=<code>{String(shiftBriefingDeadletterPresentation.visible.length)}/{String(shiftBriefingDeadletterPresentation.total)}</code>
              </div>
              <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                {shiftBriefingDeadletterPresentation.total === 0 ? (
                  <div style={{ fontSize: 11, color: THEME.muted }}>No deadlettered missions waiting for review.</div>
                ) : (
                  shiftBriefingDeadletterPresentation.visible.map((item) => {
                    const deadletterCurrentTask = item.current_task;
                    const latestActivity = latestActivitySummary(item.latest_activity);
                    const updatedAt = mixedLocaleTime(item.updated_at);
                    const latestHistoryAt = mixedLocaleTime(item.latest_history_ts);
                    const historyTail = Array.isArray(item.history_tail) ? item.history_tail.slice(-2) : [];
                    const deadletterOperationId =
                      safeString(deadletterCurrentTask?.operation_id).trim() || safeString(item.last_task_id).trim();
                    const deadletterTaskStatus =
                      safeString(deadletterCurrentTask?.task_status).trim() ||
                      safeString(deadletterCurrentTask?.operation_status).trim() ||
                      safeString(item.last_task_status).trim();
                    const deadletterTaskResult =
                      safeString(deadletterCurrentTask?.result_status).trim() ||
                      safeString(item.last_task_result_status).trim();
                    const deadletterTaskGate =
                      safeString(deadletterCurrentTask?.gate).trim() || safeString(item.last_task_gate).trim();
                    const approvalId =
                      safeString(deadletterCurrentTask?.approval_id).trim() || safeString(item.last_task_approval_id).trim();
                    const previousApprovalId = safeString(item.last_task_previous_approval_id).trim();
                    const previousApprovalStatus = safeString(item.last_task_previous_approval_status).trim();
                    const approvalStatus =
                      safeString(deadletterCurrentTask?.approval_status).trim() ||
                      safeString(item.last_task_approval_status).trim();
                    const replacementKind = safeString(item.last_task_approval_replacement_kind).trim();
                    const replacementReason = safeString(item.last_task_approval_replacement_reason).trim();
                    const replacementChangedKeys = Array.isArray(item.last_task_approval_replacement_changed_keys)
                      ? item.last_task_approval_replacement_changed_keys.map((key) => safeString(key).trim()).filter(Boolean)
                      : [];
                    const recovery = item.recovery;
                    const recoveryAction = safeString(recovery?.action).trim();
                    const recoveryTargetId = safeString(recovery?.target_id).trim();
                    const recoveryReason = safeString(recovery?.reason).trim();
                    const recoveryNextStep = safeString(recovery?.next_step).trim();
                    const recoverySourceStatus = safeString(recovery?.source_status).trim();
                    const lastRecoveryAction =
                      safeString(item.last_recovery_action).trim() || safeString(recovery?.last_review_action).trim();
                    const lastRecoveryOutcome =
                      safeString(item.last_recovery_outcome).trim() || safeString(recovery?.last_review_outcome).trim();
                    const lastRecoveryAt = mixedLocaleTime(
                      safeString(item.last_recovery_at).trim() || safeString(recovery?.last_reviewed_at).trim(),
                    );
                    return (
                    <div key={`shift-deadletter-${item.id}`}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                        <div style={{ fontSize: 11, fontWeight: 600 }}>{item.objective || item.id}</div>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          <span style={badgeStyle("deadlettered")}>deadlettered</span>
                          <span style={badgeStyle(item.recommended_action || "review_deadletter")}>
                            {item.recommended_action || "review_deadletter"}
                          </span>
                        </div>
                      </div>
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        action=<code>{item.recommended_action || "review_deadletter"}</code>
                        {updatedAt ? (
                          <>
                            {" / "}updated=<code>{updatedAt}</code>
                          </>
                        ) : null}
                        {deadletterOperationId ? (
                          <>
                            {" / "}current_task=<code>{deadletterOperationId}</code>
                          </>
                        ) : null}
                        {deadletterTaskStatus ? (
                          <>
                            {" / "}task_status=<code>{deadletterTaskStatus}</code>
                          </>
                        ) : null}
                        {deadletterTaskResult ? (
                          <>
                            {" / "}result=<code>{deadletterTaskResult}</code>
                          </>
                        ) : null}
                        {deadletterTaskGate ? (
                          <>
                            {" / "}gate=<code>{deadletterTaskGate}</code>
                          </>
                        ) : null}
                        {approvalId ? (
                          <>
                            {" / "}approval=<code>{approvalId}</code>
                          </>
                        ) : null}
                        {approvalStatus ? (
                          <>
                            {" / "}approval_status=<code>{approvalStatus}</code>
                          </>
                        ) : null}
                        {previousApprovalId ? (
                          <>
                            {" / "}previous_approval=<code>{previousApprovalId}</code>
                          </>
                        ) : null}
                        {previousApprovalStatus ? (
                          <>
                            {" / "}previous_status=<code>{previousApprovalStatus}</code>
                          </>
                        ) : null}
                        {replacementKind ? (
                          <>
                            {" / "}replacement_kind=<code>{replacementKind}</code>
                          </>
                        ) : null}
                        {replacementReason ? (
                          <>
                            {" / "}replacement=<code>{replacementReason}</code>
                          </>
                        ) : null}
                        {replacementChangedKeys.length > 0 ? (
                          <>
                            {" / "}changed_keys=<code>{replacementChangedKeys.join(",")}</code>
                          </>
                        ) : null}
                      </div>
                      <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>
                        {item.reason || "Mission has been deadlettered and needs review."}
                      </div>
                      {recovery ? (
                        <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>
                          recovery=<code>{recoveryAction || item.recommended_action || "review_deadletter"}</code>
                          {recoverySourceStatus ? (
                            <>
                              {" / "}source=<code>{recoverySourceStatus}</code>
                            </>
                          ) : null}
                          {recoveryTargetId ? (
                            <>
                              {" / "}target=<code>{recoveryTargetId}</code>
                            </>
                          ) : null}
                          {" / "}operator_required=<code>{recovery.operator_required ? "true" : "false"}</code>
                          {" / "}automatic_retry=<code>{recovery.automatic_retry ? "true" : "false"}</code>
                          {recoveryReason ? (
                            <>
                              {" / "}reason=<code>{recoveryReason}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {recoveryNextStep ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{recoveryNextStep}</div>
                      ) : null}
                      <MissionRecoveryFollowthroughCard recovery={recovery} onOpenMission={inspectMission} />
                      {lastRecoveryAction ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          reviewed=<code>{lastRecoveryAction}</code>
                          {lastRecoveryOutcome ? (
                            <>
                              {" / "}outcome=<code>{lastRecoveryOutcome}</code>
                            </>
                          ) : null}
                          {lastRecoveryAt ? (
                            <>
                              {" / "}at=<code>{lastRecoveryAt}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {item.approval_summary ? (
                        <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>{item.approval_summary}</div>
                      ) : null}
                      {item.approval_replacement_summary ? (
                        <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>{item.approval_replacement_summary}</div>
                      ) : null}
                      {item.history_summary ? (
                        <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>{item.history_summary}</div>
                      ) : null}
                      {latestActivity.name || latestActivity.status || latestActivity.gate || latestActivity.observedAt ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          latest=<code>{latestActivity.name || "activity"}</code>
                          {" / "}status=<code>{latestActivity.status || "unknown"}</code>
                          {latestActivity.gate ? (
                            <>
                              {" / "}gate=<code>{latestActivity.gate}</code>
                            </>
                          ) : null}
                          {latestActivity.observedAt ? (
                            <>
                              {" / "}at=<code>{latestActivity.observedAt}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {(item.history_count || item.latest_history_event || latestHistoryAt) ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          receipts=<code>{String(item.history_count || 0)}</code>
                          {item.latest_history_event ? (
                            <>
                              {" / "}latest_receipt=<code>{item.latest_history_event}</code>
                            </>
                          ) : null}
                          {latestHistoryAt ? (
                            <>
                              {" / "}receipt_at=<code>{latestHistoryAt}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {historyTail.length > 0 ? (
                        <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                          {historyTail.map((entry, historyIndex) => (
                            <div
                              key={`shift-deadletter-history-${item.id}-${entry.ts || "unknown"}-${entry.event || historyIndex}`}
                              style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#101010" }}
                            >
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                                <div style={{ fontSize: 11, fontWeight: 600 }}>{entry.event || "receipt"}</div>
                                <div style={{ fontSize: 11, color: THEME.muted }}>{mixedLocaleTime(entry.ts) || entry.ts || "unknown time"}</div>
                              </div>
                              {entry.details && Object.keys(entry.details).length > 0 ? (
                                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{prettyData(entry.details)}</div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ) : null}
                      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                        {approvalId ? (
                          <button
                            style={buttonStyle}
                            onClick={() =>
                              props.onOpenApprovals(approvalId, {
                                missionId: item.id,
                                operationId: deadletterOperationId || undefined,
                                source: "deadletter",
                                reviewKind: replacementKind || undefined,
                                reviewReason: replacementReason || undefined,
                                changedKeys: replacementChangedKeys,
                              })
                            }
                          >
                            {item.approval_review_label || "Review approval"}
                          </button>
                        ) : null}
                        {previousApprovalId && previousApprovalId !== approvalId ? (
                          <button
                            style={buttonStyle}
                            onClick={() =>
                              props.onOpenApprovals(previousApprovalId, {
                                missionId: item.id,
                                operationId: deadletterOperationId || undefined,
                                source: "deadletter",
                                reviewKind: replacementKind || undefined,
                                reviewReason: replacementReason || undefined,
                                changedKeys: replacementChangedKeys,
                              })
                            }
                          >
                            {item.previous_approval_review_label || "Open previous approval"}
                          </button>
                        ) : null}
                        {deadletterOperationId ? (
                          <button style={buttonStyle} onClick={() => props.onOpenOperation(deadletterOperationId)}>
                            Open current task
                          </button>
                        ) : null}
                        <button style={buttonStyle} onClick={() => inspectMission(item.id)}>
                          Inspect
                        </button>
                      </div>
                    </div>
                    );
                  })
                )}
              </div>
              {shiftBriefingDeadletterPresentation.hiddenTotal > 0 ? (
                <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
                  Hidden from this bounded view: <code>{String(shiftBriefingDeadletterPresentation.hiddenTotal)}</code>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <div id="francis-continuity-ledger" style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Continuity Ledger Tail</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              Raw recent append records from the local continuity ledger. This is a receipt surface, not a synthesized memory claim.
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <span style={badgeStyle(continuityLedgerCount > 0 ? "live" : "clear")}>entries {continuityLedgerCount}</span>
            {continuityLedgerEntries[0]?.ts ? (
              <span style={{ fontSize: 11, color: THEME.muted }}>Latest {toLocaleTime(continuityLedgerEntries[0].ts)}</span>
            ) : null}
          </div>
        </div>

        {continuityLedgerError ? (
          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
            Ledger feed unavailable: {continuityLedgerError}
          </div>
        ) : null}

        {continuityLedgerRouteError && !continuityLedgerError ? (
          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
            Ledger route reported: {continuityLedgerRouteError}
          </div>
        ) : null}

        <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
          {continuityLedgerEntries.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>
              No continuity ledger entries are recorded yet. Once chat, daemon, or governed runtime activity appends receipts, they will appear here.
            </div>
          ) : (
            continuityLedgerEntries.map((entry, index) => {
              const metaLabels = continuityLedgerMetaLabels(entry);
              return (
                <div
                  key={`continuity-ledger-${entry.ts ?? "unknown"}-${entry.role}-${index}`}
                  style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span style={badgeStyle(entry.role || "unknown")}>{entry.role || "unknown"}</span>
                      {entry.ts ? <span style={{ fontSize: 11, color: THEME.muted }}>{toLocaleTime(entry.ts)}</span> : null}
                    </div>
                    {metaLabels.length > 0 ? (
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                        {metaLabels.map((label) => (
                          <span key={`${entry.role}-${label}`} style={badgeStyle(label)}>
                            {label}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div style={{ fontSize: 12, color: THEME.text, marginTop: 8 }}>
                    {truncateText(entry.content, 220) || "Ledger entry recorded without content."}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div id="francis-observer-audit" style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Observer Receipt Audit</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              Read-only bounded audit history from the explicit observer scan route. This extends the decisions log beyond the embedded shift briefing snapshot.
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <span style={badgeStyle(observerEventCount > 0 ? "live" : "clear")}>entries {observerEventCount}</span>
            {observerEventEntries[0]?.ts ? (
              <span style={{ fontSize: 11, color: THEME.muted }}>Latest {toLocaleTime(observerEventEntries[0].ts)}</span>
            ) : null}
          </div>
        </div>

        {observerEventsError ? (
          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
            Observer audit feed unavailable: {observerEventsError}
          </div>
        ) : null}

        {observerEventsRouteError && !observerEventsError ? (
          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
            Observer audit route reported: {observerEventsRouteError}
          </div>
        ) : null}

        <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
          {observerEventEntries.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>
              No explicit observer audit receipts are recorded yet. Trigger a governed observer scan to append a new receipt.
            </div>
          ) : (
            observerEventEntries.slice(0, 6).map((scan) => renderObserverScanCard(scan, "observer-audit"))
          )}
        </div>
      </div>

      <div id="francis-telemetry-status" style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Telemetry & Continuation</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              Visible sensing posture and continuity state. This surface reports configured scope and governed state without claiming hidden capture.
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span style={badgeStyle(telemetry.tone)}>{telemetry.label}</span>
            <span style={badgeStyle(continuation.tone)}>{continuation.label}</span>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: 8,
            marginTop: 10,
          }}
        >
          <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
            <div style={{ fontSize: 11, color: THEME.muted }}>Telemetry scope</div>
            <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>{telemetry.scopeLabel}</div>
          </div>
          <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
            <div style={{ fontSize: 11, color: THEME.muted }}>Voice posture</div>
            <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>{telemetry.voiceLabel}</div>
          </div>
          <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
            <div style={{ fontSize: 11, color: THEME.muted }}>Proactive mode</div>
            <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>{telemetry.proactiveLabel}</div>
          </div>
        </div>

        <div style={{ fontSize: 12, color: THEME.text, marginTop: 10 }}>{telemetry.detail}</div>
        <div style={{ fontSize: 12, color: continuation.tone === "blocked" ? "#ffcf9d" : THEME.muted, marginTop: 6 }}>
          {continuation.detail}
        </div>
      </div>

      <div
        id="francis-takeover-feed"
        style={{
          ...summaryCardStyle(),
          marginTop: 12,
          background: pilotActive ? controlTone.bg : "#101010",
          border: `1px solid ${pilotActive ? controlTone.border : THEME.panelBorder}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Takeover Feed</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              Live execution surface for delegated work, active scope, interruption options, and clean hand-back guidance.
            </div>
          </div>
          <span
            style={
              pilotActive
                ? {
                    ...badgeStyle("pilot_active"),
                    background: controlTone.bg,
                    border: `1px solid ${controlTone.border}`,
                    color: controlTone.color,
                  }
                : badgeStyle("standby")
            }
          >
            {pilotActive ? "Pilot Active" : "Pilot Standby"}
          </span>
        </div>

        {takeoverOperationsError ? (
          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
            Live operations unavailable: {takeoverOperationsError}
          </div>
        ) : null}

        <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
          <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Active Scope</div>
              {focusPlaneId ? <span style={badgeStyle(focusPlaneId)}>{focusPlaneId}</span> : null}
            </div>
            <div style={{ fontSize: 12, color: pilotActive ? controlTone.color : THEME.text, marginTop: 6 }}>{focusLabel}</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{focusReason}</div>
            {activePlanes.length > 0 ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                {activePlanes.map((plane) => (
                  <span key={plane} style={badgeStyle(plane)}>
                    {plane}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Current Run</div>
              {currentTakeoverOperation ? (
                <span style={badgeStyle(operationStatus(currentTakeoverOperation))}>{operationStatus(currentTakeoverOperation)}</span>
              ) : null}
            </div>
            {currentTakeoverOperation ? (
              <>
                <div style={{ fontSize: 12, color: THEME.text, marginTop: 6 }}>{operationLabel(currentTakeoverOperation)}</div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                  assigned_to=<code>{operationAssignedTo(currentTakeoverOperation)}</code>
                  {operationPlane(currentTakeoverOperation) ? (
                    <>
                      {" / "}plane=<code>{operationPlane(currentTakeoverOperation)}</code>
                    </>
                  ) : null}
                </div>
              </>
            ) : null}
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{takeoverLead}</div>
            {currentTakeoverOperation ? (
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                <button style={buttonStyle} onClick={() => props.onOpenOperation(currentTakeoverOperation.id)}>
                  Open live operation
                </button>
              </div>
            ) : null}
          </div>
        </div>

        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Actions Underway</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {activeTakeoverOperations.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>
              {pilotActive
                ? "No queued, blocked, or running delegated operations are currently visible."
                : "No live takeover work is visible because Pilot is not currently active."}
            </div>
          ) : (
            activeTakeoverOperations.slice(0, 4).map((operation) => (
              <div
                key={`takeover-live-${operation.id}`}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{operationLabel(operation)}</div>
                  <span style={badgeStyle(operationStatus(operation))}>{operationStatus(operation)}</span>
                </div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                  assigned_to=<code>{operationAssignedTo(operation)}</code>
                  {operationPlane(operation) ? (
                    <>
                      {" / "}plane=<code>{operationPlane(operation)}</code>
                    </>
                  ) : null}
                </div>
                {operationMessage(operation) ? (
                  <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{operationMessage(operation)}</div>
                ) : null}
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                  <button style={buttonStyle} onClick={() => props.onOpenOperation(operation.id)}>
                    Open task
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Recently Completed</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {completedTakeoverOperations.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No recent completed operations are available in the current feed window.</div>
          ) : (
            completedTakeoverOperations.map((operation) => (
              <div
                key={`takeover-complete-${operation.id}`}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{operationLabel(operation)}</div>
                  <span style={badgeStyle(operationStatus(operation))}>{operationStatus(operation)}</span>
                </div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                  actor=<code>{operation.actor || "unknown"}</code>
                  {" / "}assigned_to=<code>{operationAssignedTo(operation)}</code>
                </div>
                {operationMessage(operation) ? (
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{operationMessage(operation)}</div>
                ) : null}
              </div>
            ))
          )}
        </div>

        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>What Remains</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          {remainingTakeoverItems.length === 0 ? (
            <span style={{ fontSize: 12, color: THEME.muted }}>No remaining governed backlog is currently visible.</span>
          ) : (
            remainingTakeoverItems.map((item) => (
              <span key={`remaining-${item.label}`} style={badgeStyle(item.tone)}>
                {item.label} {item.value}
              </span>
            ))
          )}
        </div>

        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Interruptible Now</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {interruptibleOperations.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No live operation is currently in a cancelable state.</div>
          ) : (
            interruptibleOperations.map((operation) => (
              <div
                key={`interrupt-${operation.id}`}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{operationLabel(operation)}</div>
                  <span style={badgeStyle(operationStatus(operation))}>{operationStatus(operation)}</span>
                </div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                  Open the operation detail to run, cancel, or inspect governance state cleanly.
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                  <button style={buttonStyle} onClick={() => props.onOpenOperation(operation.id)}>
                    Open controls
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212", marginTop: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600 }}>Hand Back Cleanly</div>
          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{handBackGuidance}</div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
            {pendingApprovals.length > 0 ? (
              <button style={buttonStyle} onClick={() => props.onOpenApprovals()}>
                Review approvals
              </button>
            ) : null}
            <button
              style={buttonStyle}
              disabled={!currentTakeoverOperation}
              onClick={() => {
                if (currentTakeoverOperation) props.onOpenOperation(currentTakeoverOperation.id);
              }}
            >
              Open current run
            </button>
          </div>
        </div>
      </div>

      <div id="francis-mission-feed" style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Mission Feed</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              {missionFeedDeclared
                ? "Declared continuity from local mission records, linked tasks, approvals, and incidents."
                : "No declared mission records yet. Falling back to task, approval, and incident continuity in this build."}
            </div>
          </div>
          <span style={badgeStyle(returnToWorkItems[0]?.tone || "clear")}>{returnToWorkItems[0]?.label || "Clear"}</span>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
            gap: 8,
            marginTop: 10,
          }}
        >
          {missionSummaryItems.map((item) => {
            const tone = statusBadgeColors(item.tone);
            return (
              <div
                key={item.label}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
              >
                <div style={{ fontSize: 11, color: THEME.muted }}>{item.label}</div>
                <div style={{ fontSize: 21, fontWeight: 700, marginTop: 4, color: tone.color }}>{item.value}</div>
              </div>
            );
          })}
        </div>

        <div style={{ fontSize: 12, color: controlTone.color, marginTop: 10 }}>{controlModeGuidance}</div>

        <MissionReadinessEvidencePanel
          title="Mission Readiness Evidence"
          readiness={overviewMissionReadiness}
          keyPrefix="overview-readiness"
          criterionLimit={2}
          evidenceLimit={3}
          marginTop={12}
        />

        <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212", marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600 }}>Mission Flow Inspector</div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                Linked operations and ledger entries for the selected mission. This keeps continuity, governance, and execution reachable from the active ORB surface.
              </div>
            </div>
            {selectedMission ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                <span style={badgeStyle(selectedMission.status || "unknown")}>{selectedMission.status || "unknown"}</span>
                <span style={badgeStyle(selectedMission.risk_tier || "unknown")}>{selectedMission.risk_tier || "unknown"}</span>
              </div>
            ) : null}
          </div>

          {!selectedMissionId ? (
            <div style={{ fontSize: 12, color: THEME.muted, marginTop: 8 }}>
              No declared mission is selected yet. Use any mission card in the shift briefing or mission feed to inspect its governed flow.
            </div>
          ) : missionDetailBusy && !selectedMission ? (
            <div style={{ fontSize: 12, color: THEME.muted, marginTop: 8 }}>Loading mission detail.</div>
          ) : missionDetailError ? (
            <div
              style={{
                marginTop: 10,
                padding: 10,
                borderRadius: 10,
                border: `1px solid ${THEME.errorBorder}`,
                background: THEME.errorBg,
                fontSize: 12,
                color: "#ffaaaa",
              }}
            >
              <b>Error:</b> {missionDetailError}
            </div>
          ) : selectedMission ? (
            <>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{selectedMission.objective || selectedMission.id}</div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    <code>{selectedMission.id}</code>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <span style={badgeStyle(`priority-${String(selectedMission.priority ?? 0)}`)}>priority {selectedMission.priority ?? 0}</span>
                  <span style={badgeStyle(operationMetaString(primaryMissionOperation, "orb_plane") || "mission")}>
                    {operationMetaString(primaryMissionOperation, "orb_plane") || "mission"}
                  </span>
                </div>
              </div>

              {selectedMission.summary ? <div style={{ fontSize: 12, color: THEME.muted, marginTop: 8 }}>{selectedMission.summary}</div> : null}
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                next_step=<code>{safeString(selectedMissionCurrentTask?.next_step).trim() || selectedMission.next_step || "unset"}</code>
                {selectedMissionCurrentTaskId ? (
                  <>
                    {" / "}current_task=<code>{selectedMissionCurrentTaskId}</code>
                  </>
                ) : null}
                {selectedMissionCurrentTaskOperationName ? (
                  <>
                    {" / "}operation=<code>{selectedMissionCurrentTaskOperationName}</code>
                  </>
                ) : null}
                {selectedMissionCurrentTaskOperationPlane ? (
                  <>
                    {" / "}plane=<code>{selectedMissionCurrentTaskOperationPlane}</code>
                  </>
                ) : null}
                {selectedMissionCurrentTaskAdvanceAction ? (
                  <>
                    {" / "}advance=<code>{selectedMissionCurrentTaskAdvanceAction}</code>
                  </>
                ) : null}
                {selectedMissionLastTaskStatus ? (
                  <>
                    {" / "}latest_run=<code>{selectedMissionLastTaskStatus}</code>
                  </>
                ) : null}
                {selectedMissionCurrentTaskReceiptEvent ? (
                  <>
                    {" / "}receipt=<code>{selectedMissionCurrentTaskReceiptEvent}</code>
                  </>
                ) : null}
                {selectedMissionCurrentTaskReceiptStatus ? (
                  <>
                    {" / "}receipt_status=<code>{selectedMissionCurrentTaskReceiptStatus}</code>
                  </>
                ) : null}
                {selectedMissionTaskStatus && selectedMissionTaskStatus !== selectedMissionLastTaskStatus ? (
                  <>
                    {" / "}task_status=<code>{selectedMissionTaskStatus}</code>
                  </>
                ) : null}
                {selectedMissionLastTaskResultStatus ? (
                  <>
                    {" / "}result=<code>{selectedMissionLastTaskResultStatus}</code>
                  </>
                ) : null}
                {selectedMissionLastTaskGate ? (
                  <>
                    {" / "}gate=<code>{selectedMissionLastTaskGate}</code>
                  </>
                ) : null}
                {selectedMissionCurrentTask?.source ? (
                  <>
                    {" / "}source=<code>{selectedMissionCurrentTask.source}</code>
                  </>
                ) : null}
              </div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                owner=<code>{selectedMission.owner_id || selectedMission.requester_id || "unset"}</code>
                {" / "}dependencies=<code>{String(selectedMission.dependency_count ?? selectedMission.dependency_ids?.length ?? 0)}</code>
                {selectedMission.escalation_path ? (
                  <>
                    {" / "}escalation=<code>{selectedMission.escalation_path}</code>
                  </>
                ) : null}
              </div>
              {selectedMission.dependency_ids && selectedMission.dependency_ids.length > 0 ? (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                  {selectedMission.dependency_ids.slice(0, 4).map((dependencyId) => (
                    <span key={`mission-dependency-${selectedMission.id}-${dependencyId}`} style={badgeStyle("dependency")}>
                      dependency <code>{dependencyId}</code>
                    </span>
                  ))}
                </div>
              ) : null}
              {selectedMissionLastTaskReason ? (
                <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 6 }}>{selectedMissionLastTaskReason}</div>
              ) : null}
              {selectedMission.deadletter_reason ? (
                <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 6 }}>{selectedMission.deadletter_reason}</div>
              ) : null}
              {selectedMissionReplacementForId ? (
                <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#111819", marginTop: 8 }}>
                  <div style={{ fontSize: 11, color: "#cce7e2" }}>
                    replacement_for=<code>{selectedMissionReplacementForId}</code>
                    {selectedMissionReplacementForStatus ? (
                      <>
                        {" / "}source_status=<code>{selectedMissionReplacementForStatus}</code>
                      </>
                    ) : null}
                    {selectedMissionReplacementSourceAction ? (
                      <>
                        {" / "}source_action=<code>{selectedMissionReplacementSourceAction}</code>
                      </>
                    ) : null}
                    {selectedMissionReplacementSourceTargetId ? (
                      <>
                        {" / "}source_target=<code>{selectedMissionReplacementSourceTargetId}</code>
                      </>
                    ) : null}
                  </div>
                  {selectedMissionReplacementReason ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{selectedMissionReplacementReason}</div>
                  ) : null}
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                    <button style={buttonStyle} onClick={() => inspectMission(selectedMissionReplacementForId)}>
                      Open source mission
                    </button>
                    {selectedMissionReplacementSourceTargetId.startsWith("tsk_") ? (
                      <button style={buttonStyle} onClick={() => props.onOpenOperation(selectedMissionReplacementSourceTargetId)}>
                        Open source task
                      </button>
                    ) : null}
                  </div>
                </div>
              ) : null}
              <div
                style={{
                  marginTop: 10,
                  padding: 10,
                  borderRadius: 10,
                  border: `1px solid ${
                    primaryMissionOperationApprovalId
                      ? "#5a4c18"
                      : primaryMissionOperationStatus === "running"
                        ? "#244d31"
                        : ["queued", "blocked", "failed"].includes(primaryMissionOperationStatus)
                          ? THEME.panelBorder
                          : THEME.panelBorder
                  }`,
                  background:
                    primaryMissionOperationApprovalId
                      ? "#1f1a0b"
                      : primaryMissionOperationStatus === "running"
                        ? "#102417"
                        : ["queued", "blocked", "failed"].includes(primaryMissionOperationStatus)
                          ? "#111819"
                          : "#101010",
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600 }}>Recovery Posture</div>
                <div
                  style={{
                    fontSize: 11,
                    marginTop: 6,
                    color:
                      primaryMissionOperationApprovalId
                        ? "#f4d27a"
                        : primaryMissionOperationStatus === "running"
                          ? "#9de2ad"
                          : THEME.muted,
                  }}
                >
                  {primaryMissionRecoverySummary}
                </div>
              </div>

              {missionReceiptSummary ? (
                <div style={{ ...summaryCardStyle(), marginTop: 10 }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>Continuity Receipts</div>
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        Compact receipt posture for this mission from linked operations, run ledger, local mission history, and memory receipts.
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                      <span style={badgeStyle(missionReceiptSummary.current_operation_status || "mission")}>
                        {missionReceiptSummary.current_operation_status || "mission"}
                      </span>
                      {missionReceiptSummary.current_gate ? (
                        <span style={badgeStyle(missionReceiptSummary.current_gate)}>{missionReceiptSummary.current_gate}</span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                    linked_ops=<code>{String(missionReceiptSummary.linked_operation_count ?? missionLinkedOperations.length)}</code>
                    {" / "}run_receipts=<code>{String(missionReceiptSummary.run_ledger_count ?? missionRunLedger.length)}</code>
                    {" / "}history_receipts=<code>{String(missionReceiptSummary.history_count ?? missionHistory.length)}</code>
                    {" / "}memory_receipts=<code>{String(missionMemoryReceiptCount)}</code>
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                    {missionReceiptOperationId ? (
                      <>
                        current_task=<code>{missionReceiptOperationId}</code>
                      </>
                    ) : (
                      <>
                        current_task=<code>unset</code>
                      </>
                    )}
                    {missionReceiptApprovalId ? (
                      <>
                        {" / "}approval=<code>{missionReceiptApprovalId}</code>
                      </>
                    ) : null}
                    {missionReceiptTraceId ? (
                      <>
                        {" / "}trace=<code>{missionReceiptTraceId}</code>
                      </>
                    ) : null}
                    {missionReceiptRunId ? (
                      <>
                        {" / "}run=<code>{missionReceiptRunId}</code>
                      </>
                    ) : null}
                    {missionReceiptArtifactDir ? (
                      <>
                        {" / "}artifact=<code>{missionReceiptArtifactDir}</code>
                      </>
                    ) : null}
                  </div>
                  {missionReceiptOperationName || missionReceiptOperationPlane || missionReceiptAdvanceAction ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      {missionReceiptOperationName ? (
                        <>
                          task_name=<code>{missionReceiptOperationName}</code>
                        </>
                      ) : null}
                      {missionReceiptOperationPlane ? (
                        <>
                          {missionReceiptOperationName ? " / " : ""}plane=<code>{missionReceiptOperationPlane}</code>
                        </>
                      ) : null}
                      {missionReceiptAdvanceAction ? (
                        <>
                          {(missionReceiptOperationName || missionReceiptOperationPlane) ? " / " : ""}advance=
                          <code>{missionReceiptAdvanceAction}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {missionReceiptPlanStatus ||
                  missionReceiptPlanStepId ||
                  missionReceiptPlanStepTitle ||
                  typeof missionReceiptPlanStepCount === "number" ||
                  typeof missionReceiptPlanCheckpointCount === "number" ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      {missionReceiptPlanStatus ? (
                        <>
                          plan=<code>{missionReceiptPlanStatus}</code>
                        </>
                      ) : null}
                      {missionReceiptPlanStepId ? (
                        <>
                          {missionReceiptPlanStatus ? " / " : ""}step=<code>{missionReceiptPlanStepId}</code>
                        </>
                      ) : null}
                      {missionReceiptPlanStepTitle ? (
                        <>
                          {(missionReceiptPlanStatus || missionReceiptPlanStepId) ? " / " : ""}step_title=
                          <code>{missionReceiptPlanStepTitle}</code>
                        </>
                      ) : null}
                      {typeof missionReceiptPlanStepCount === "number" ? (
                        <>
                          {(missionReceiptPlanStatus || missionReceiptPlanStepId || missionReceiptPlanStepTitle) ? " / " : ""}
                          steps=<code>{String(missionReceiptPlanStepCount)}</code>
                        </>
                      ) : null}
                      {typeof missionReceiptPlanCheckpointCount === "number" ? (
                        <>
                          {(missionReceiptPlanStatus ||
                          missionReceiptPlanStepId ||
                          missionReceiptPlanStepTitle ||
                          typeof missionReceiptPlanStepCount === "number")
                            ? " / "
                            : ""}
                          checkpoints=<code>{String(missionReceiptPlanCheckpointCount)}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {(missionReceiptSummary.latest_run_event || missionReceiptLatestRunAt || missionReceiptSummary.latest_history_event || missionReceiptLatestHistoryAt) ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      {missionReceiptSummary.latest_run_event ? (
                        <>
                          latest_run=<code>{missionReceiptSummary.latest_run_event}</code>
                        </>
                      ) : null}
                      {missionReceiptSummary.latest_run_status ? (
                        <>
                          {missionReceiptSummary.latest_run_event ? " / " : ""}run_status=<code>{missionReceiptSummary.latest_run_status}</code>
                        </>
                      ) : null}
                      {missionReceiptLatestRunAt ? (
                        <>
                          {(missionReceiptSummary.latest_run_event || missionReceiptSummary.latest_run_status) ? " / " : ""}run_at=<code>{missionReceiptLatestRunAt}</code>
                        </>
                      ) : null}
                      {missionReceiptSummary.latest_history_event ? (
                        <>
                          {(missionReceiptSummary.latest_run_event || missionReceiptSummary.latest_run_status || missionReceiptLatestRunAt) ? " / " : ""}history=<code>{missionReceiptSummary.latest_history_event}</code>
                        </>
                      ) : null}
                      {missionReceiptLatestHistoryAt ? (
                        <>
                          {(missionReceiptSummary.latest_run_event ||
                          missionReceiptSummary.latest_run_status ||
                          missionReceiptLatestRunAt ||
                          missionReceiptSummary.latest_history_event)
                            ? " / "
                            : ""}
                          history_at=<code>{missionReceiptLatestHistoryAt}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {missionLatestMemoryReceipt ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      latest_memory=<code>{missionMemoryReceiptLabel(missionLatestMemoryReceipt)}</code>
                      {missionLatestMemoryReceipt.operation_status ? (
                        <>
                          {" / "}memory_status=<code>{missionLatestMemoryReceipt.operation_status}</code>
                        </>
                      ) : null}
                      {missionLatestMemoryReceiptAt ? (
                        <>
                          {" / "}memory_at=<code>{missionLatestMemoryReceiptAt}</code>
                        </>
                      ) : null}
                      {missionLatestMemoryReceiptRefs ? <>{" / "}{missionLatestMemoryReceiptRefs}</> : null}
                      {missionLatestMemoryReceiptHandoff ? <>{" / "}{missionLatestMemoryReceiptHandoff}</> : null}
                    </div>
                  ) : null}
                  {missionReceiptArtifactDir ? (
                    <div style={{ marginTop: 8 }}>
                      <ArtifactInspectionPanel
                        baseUrl={resolvedBaseUrl}
                        artifactDir={missionReceiptArtifactDir}
                        title="Receipt Artifact"
                        buttonLabel="Inspect receipt artifact"
                        buttonStyle={buttonStyle}
                        badgeStyle={badgeStyle}
                        borderColor={THEME.panelBorder}
                        mutedColor={THEME.muted}
                      />
                    </div>
                  ) : null}
                  {(missionReceiptApprovalId ||
                    missionReceiptOperationId ||
                    missionReceiptTraceId ||
                    missionReceiptRunId ||
                    missionReceiptArtifactDir ||
                    missionReceiptSummary.run_ledger_count ||
                    missionReceiptSummary.history_count ||
                    missionMemoryReceiptCount) ? (
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      {missionReceiptApprovalId ? (
                        <button
                          style={buttonStyle}
                          onClick={() =>
                            props.onOpenApprovals(missionReceiptApprovalId, {
                              missionId: selectedMission.id,
                              operationId: missionReceiptOperationId || undefined,
                            })
                          }
                        >
                          Review approval
                        </button>
                      ) : null}
                      {missionReceiptOperationId ? (
                        <button style={buttonStyle} onClick={() => props.onOpenOperation(missionReceiptOperationId)}>
                          Open receipt task
                        </button>
                      ) : null}
                      <button style={buttonStyle} onClick={() => scrollOrbSection("francis-continuity-ledger")}>
                        Open continuity ledger
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {missionLoopStages.length > 0 ? (
                <div style={{ ...summaryCardStyle(), marginTop: 10 }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>ORB Loop State</div>
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        {missionLoopState?.summary || "Current plan, gate, execution, trace, and continuity posture for this mission."}
                      </div>
                    </div>
                    {missionLoopState?.active_stage ? (
                      <span style={badgeStyle(missionLoopState.active_stage)}>active {missionLoopState.active_stage}</span>
                    ) : null}
                  </div>

                  {missionLoopHandoff ? (
                    <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#111819", marginTop: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                        <div style={{ fontSize: 11, fontWeight: 600 }}>Loop Handoff</div>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {missionLoopHandoff.stage ? <span style={badgeStyle(missionLoopHandoff.stage)}>{missionLoopHandoff.stage}</span> : null}
                          {missionLoopHandoff.action ? <span style={badgeStyle(missionLoopHandoff.action)}>{missionLoopHandoff.action}</span> : null}
                        </div>
                      </div>
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                        {missionLoopHandoff.detail || "No loop handoff has been projected for this mission yet."}
                      </div>
                      {(missionLoopHandoff.gate ||
                        missionLoopHandoff.approval_status ||
                        missionLoopHandoff.next_step ||
                        missionLoopHandoff.latest_event ||
                        missionLoopHandoff.latest_ts) ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                          {missionLoopHandoff.gate ? (
                            <>
                              gate <code>{missionLoopHandoff.gate}</code>
                            </>
                          ) : null}
                          {missionLoopHandoff.approval_status ? (
                            <>
                              {missionLoopHandoff.gate ? " / " : ""}approval_status <code>{missionLoopHandoff.approval_status}</code>
                            </>
                          ) : null}
                          {missionLoopHandoff.next_step ? (
                            <>
                              {(missionLoopHandoff.gate || missionLoopHandoff.approval_status) ? " / " : ""}next{" "}
                              <code>{missionLoopHandoff.next_step}</code>
                            </>
                          ) : null}
                          {missionLoopHandoff.latest_event ? (
                            <>
                              {(missionLoopHandoff.gate || missionLoopHandoff.approval_status || missionLoopHandoff.next_step) ? " / " : ""}
                              latest <code>{missionLoopHandoff.latest_event}</code>
                            </>
                          ) : null}
                          {missionLoopHandoff.latest_ts ? (
                            <>
                              {(missionLoopHandoff.gate ||
                              missionLoopHandoff.approval_status ||
                              missionLoopHandoff.next_step ||
                              missionLoopHandoff.latest_event)
                                ? " / "
                                : ""}
                              at <code>{toLocaleTime(missionLoopHandoff.latest_ts)}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {(missionLoopHandoff.approval_id ||
                        missionLoopHandoff.operation_id ||
                        missionLoopHandoff.trace_id ||
                        missionLoopHandoff.run_id ||
                        missionLoopHandoff.artifact_dir) ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6, overflowWrap: "anywhere" }}>
                          {missionLoopHandoff.approval_id ? (
                            <>
                              approval <code>{missionLoopHandoff.approval_id}</code>
                            </>
                          ) : null}
                          {missionLoopHandoff.operation_id ? (
                            <>
                              {missionLoopHandoff.approval_id ? " / " : ""}task <code>{missionLoopHandoff.operation_id}</code>
                            </>
                          ) : null}
                          {missionLoopHandoff.trace_id ? (
                            <>
                              {(missionLoopHandoff.approval_id || missionLoopHandoff.operation_id) ? " / " : ""}trace <code>{missionLoopHandoff.trace_id}</code>
                            </>
                          ) : null}
                          {missionLoopHandoff.run_id ? (
                            <>
                              {(missionLoopHandoff.approval_id || missionLoopHandoff.operation_id || missionLoopHandoff.trace_id)
                                ? " / "
                                : ""}
                              run <code>{missionLoopHandoff.run_id}</code>
                            </>
                          ) : null}
                          {missionLoopHandoff.artifact_dir ? (
                            <>
                              {(missionLoopHandoff.approval_id ||
                              missionLoopHandoff.operation_id ||
                              missionLoopHandoff.trace_id ||
                              missionLoopHandoff.run_id)
                                ? " / "
                                : ""}
                              artifact <code title={missionLoopHandoff.artifact_dir}>{truncateText(missionLoopHandoff.artifact_dir, 96)}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {(missionLoopHandoff.approval_id || missionLoopHandoff.operation_id) ? (
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                          {missionLoopHandoff.approval_id ? (
                            <button
                              style={buttonStyle}
                              onClick={() =>
                                props.onOpenApprovals(missionLoopHandoff.approval_id || "", {
                                  missionId: selectedMissionContextId || undefined,
                                  operationId: missionLoopHandoff.operation_id,
                                })
                              }
                            >
                              Review approval
                            </button>
                          ) : null}
                          {missionLoopHandoff.operation_id ? (
                            <button style={buttonStyle} onClick={() => props.onOpenOperation(missionLoopHandoff.operation_id || "")}>
                              Open linked task
                            </button>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8, marginTop: 8 }}>
                    {missionLoopStages.map((item) => {
                      const stageMemoryReceiptHandoff = missionMemoryReceiptHandoffLine(item.stage?.latest_memory_receipt);
                      return (
                        <div
                          key={`mission-loop-${item.key}`}
                          style={{
                            border: `1px solid ${missionLoopState?.active_stage === item.key ? "#3a5c67" : THEME.panelBorder}`,
                            borderRadius: 10,
                            padding: 10,
                            background: missionLoopState?.active_stage === item.key ? "#10181b" : "#121212",
                          }}
                        >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                          <div style={{ fontSize: 11, color: THEME.muted }}>{item.label}</div>
                          <span style={badgeStyle(item.stage?.status || "unknown")}>{item.stage?.status || "unknown"}</span>
                        </div>
                        <div style={{ fontSize: 11, color: THEME.text, marginTop: 8 }}>
                          {item.stage?.detail || "No receipt is recorded for this stage yet."}
                        </div>
                        {(item.stage?.count !== undefined ||
                          item.stage?.gate ||
                          item.stage?.approval_status ||
                          item.stage?.next_step ||
                          item.stage?.memory_receipt_count) ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                            {item.stage?.count !== undefined ? (
                              <>
                                count <code>{String(item.stage.count)}</code>
                              </>
                            ) : null}
                            {item.stage?.gate ? (
                              <>
                                {item.stage?.count !== undefined ? " / " : ""}gate <code>{item.stage.gate}</code>
                              </>
                            ) : null}
                            {item.stage?.approval_status ? (
                              <>
                                {(item.stage?.count !== undefined || item.stage?.gate) ? " / " : ""}approval_status{" "}
                                <code>{item.stage.approval_status}</code>
                              </>
                            ) : null}
                            {item.stage?.next_step ? (
                              <>
                                {(item.stage?.count !== undefined || item.stage?.gate || item.stage?.approval_status) ? " / " : ""}
                                next <code>{item.stage.next_step}</code>
                              </>
                            ) : null}
                            {item.stage?.memory_receipt_count ? (
                              <>
                                {(item.stage?.count !== undefined || item.stage?.gate || item.stage?.approval_status || item.stage?.next_step)
                                  ? " / "
                                  : ""}
                                memory_receipts <code>{String(item.stage.memory_receipt_count)}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {(item.stage?.approval_id ||
                          item.stage?.operation_id ||
                          item.stage?.trace_id ||
                          item.stage?.run_id ||
                          item.stage?.artifact_dir ||
                          item.stage?.latest_event ||
                          item.stage?.latest_receipt_status ||
                          item.stage?.latest_ts) ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8, overflowWrap: "anywhere" }}>
                            {item.stage?.approval_id ? (
                              <>
                                approval <code>{item.stage.approval_id}</code>
                              </>
                            ) : null}
                            {item.stage?.operation_id ? (
                              <>
                                {item.stage?.approval_id ? " / " : ""}task <code>{item.stage.operation_id}</code>
                              </>
                            ) : null}
                            {item.stage?.trace_id ? (
                              <>
                                {(item.stage?.approval_id || item.stage?.operation_id) ? " / " : ""}trace <code>{item.stage.trace_id}</code>
                              </>
                            ) : null}
                            {item.stage?.run_id ? (
                              <>
                                {(item.stage?.approval_id || item.stage?.operation_id || item.stage?.trace_id) ? " / " : ""}run{" "}
                                <code>{item.stage.run_id}</code>
                              </>
                            ) : null}
                            {item.stage?.artifact_dir ? (
                              <>
                                {(item.stage?.approval_id ||
                                item.stage?.operation_id ||
                                item.stage?.trace_id ||
                                item.stage?.run_id)
                                  ? " / "
                                  : ""}
                                artifact <code title={item.stage.artifact_dir}>{truncateText(item.stage.artifact_dir, 96)}</code>
                              </>
                            ) : null}
                            {item.stage?.latest_event ? (
                              <>
                                {(item.stage?.approval_id ||
                                item.stage?.operation_id ||
                                item.stage?.trace_id ||
                                item.stage?.run_id ||
                                item.stage?.artifact_dir)
                                  ? " / "
                                  : ""}
                                latest <code>{item.stage.latest_event}</code>
                              </>
                            ) : null}
                            {item.stage?.latest_receipt_status ? (
                              <>
                                {(item.stage?.approval_id ||
                                item.stage?.operation_id ||
                                item.stage?.trace_id ||
                                item.stage?.run_id ||
                                item.stage?.artifact_dir ||
                                item.stage?.latest_event)
                                  ? " / "
                                  : ""}
                                receipt_status <code>{item.stage.latest_receipt_status}</code>
                              </>
                            ) : null}
                            {item.stage?.latest_ts ? (
                              <>
                                {(item.stage?.approval_id ||
                                item.stage?.operation_id ||
                                item.stage?.trace_id ||
                                item.stage?.run_id ||
                                item.stage?.artifact_dir ||
                                item.stage?.latest_event ||
                                item.stage?.latest_receipt_status)
                                  ? " / "
                                  : ""}
                                at <code>{toLocaleTime(item.stage.latest_ts)}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {item.stage?.latest_memory_receipt ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                            latest_memory=<code>{missionMemoryReceiptLabel(item.stage.latest_memory_receipt)}</code>
                            {item.stage.latest_memory_receipt.operation_status ? (
                              <>
                                {" / "}memory_status=<code>{item.stage.latest_memory_receipt.operation_status}</code>
                              </>
                            ) : null}
                            {mixedLocaleTime(item.stage.latest_memory_receipt.ts) ? (
                              <>
                                {" / "}memory_at=<code>{mixedLocaleTime(item.stage.latest_memory_receipt.ts)}</code>
                              </>
                            ) : null}
                            {missionMemoryReceiptReferenceLine(item.stage.latest_memory_receipt) ? (
                              <>{" / "}{missionMemoryReceiptReferenceLine(item.stage.latest_memory_receipt)}</>
                            ) : null}
                            {stageMemoryReceiptHandoff ? <>{" / "}{stageMemoryReceiptHandoff}</> : null}
                          </div>
                        ) : null}
                        {missionLoopStagePlanReceiptLine(item.stage)}
                        {item.stage?.artifact_dir ? (
                          <div style={{ marginTop: 8 }}>
                            <ArtifactInspectionPanel
                              baseUrl={resolvedBaseUrl}
                              artifactDir={item.stage.artifact_dir}
                              title={`${item.label} Artifact`}
                              buttonLabel="Inspect stage artifact"
                              buttonStyle={buttonStyle}
                              badgeStyle={badgeStyle}
                              borderColor={THEME.panelBorder}
                              mutedColor={THEME.muted}
                              limit={25}
                              maxEntries={5}
                            />
                          </div>
                        ) : null}
                        {(item.stage?.approval_id || item.stage?.operation_id) ? (
                          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                            {item.stage?.approval_id ? (
                              <button
                                style={buttonStyle}
                                onClick={() =>
                                  props.onOpenApprovals(item.stage?.approval_id || "", {
                                    missionId: selectedMissionContextId || undefined,
                                    operationId: item.stage?.operation_id,
                                  })
                                }
                              >
                                Review approval
                              </button>
                            ) : null}
                            {item.stage?.operation_id ? (
                              <button style={buttonStyle} onClick={() => props.onOpenOperation(item.stage?.operation_id || "")}>
                                Open linked task
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {missionActionNotice ? (
                <div
                  style={{
                    marginTop: 10,
                    padding: 10,
                    borderRadius: 10,
                    border: `1px solid ${missionActionNotice.tone === "error" ? THEME.errorBorder : THEME.panelBorder}`,
                    background: missionActionNotice.tone === "error" ? THEME.errorBg : "#111819",
                    color: missionActionNotice.tone === "error" ? "#ffaaaa" : "#aee6df",
                    fontSize: 12,
                  }}
                >
                  {missionActionNotice.text}
                </div>
              ) : null}
              {missionActionResult ? (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 10 }}>
                  {missionActionResult.missionId ? (
                    <span style={badgeStyle("mission")}>mission <code>{missionActionResult.missionId}</code></span>
                  ) : null}
                  {missionActionResult.operationId ? (
                    <span style={badgeStyle("queued")}>task <code>{missionActionResult.operationId}</code></span>
                  ) : null}
                  {missionActionResult.approvalId ? (
                    <span style={badgeStyle("needs_approval")}>approval <code>{missionActionResult.approvalId}</code></span>
                  ) : null}
                  {missionActionResult.operationId ? (
                    <button style={buttonStyle} onClick={() => props.onOpenOperation(missionActionResult.operationId || "")}>
                      Open task
                    </button>
                  ) : null}
                  {missionActionResult.approvalId ? (
                    <button
                      style={buttonStyle}
                      onClick={() =>
                        props.onOpenApprovals(missionActionResult.approvalId, {
                          missionId: missionActionResult.missionId,
                          operationId: missionActionResult.operationId,
                        })
                      }
                    >
                      Review approval
                    </button>
                  ) : null}
                  {missionActionResult.operationError ||
                  missionActionResult.resultMessage ||
                  missionActionResult.recoveryNextStep ? (
                    <div style={{ flexBasis: "100%" }}>{missionOperationRecoveryLine(missionActionResult)}</div>
                  ) : null}
                </div>
              ) : null}
              {missionAdvanceBlockedReason ? (
                <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>{missionAdvanceBlockedReason}</div>
              ) : null}
              {selectedMissionQueueItem ? (
                <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#111819", marginTop: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <div style={{ fontSize: 11, fontWeight: 600 }}>Mission Actionability</div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span style={badgeStyle(selectedMissionRecommendedAction || "review_mission")}>
                        {selectedMissionRecommendedAction || "review_mission"}
                      </span>
                      <span style={badgeStyle(selectedMissionAdvanceEligible ? "eligible" : "review_required")}>
                        {selectedMissionAdvanceEligible ? "advance eligible" : "review required"}
                      </span>
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: selectedMissionAdvanceEligible ? THEME.muted : "#ffcf9d", marginTop: 6 }}>
                    {selectedMissionAdvanceReason ||
                      selectedMissionQueueItem.operator_hint ||
                      "Mission actionability is available, but no operator hint is recorded."}
                  </div>
                  {selectedMissionRecovery ? (
                    <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#101010", marginTop: 8 }}>
                      <div style={{ fontSize: 11, color: "#cce7e2" }}>
                        recovery=<code>{selectedMissionRecoveryAction || selectedMissionRecommendedAction || "review_mission"}</code>
                        {selectedMissionRecoverySourceStatus ? (
                          <>
                            {" / "}source=<code>{selectedMissionRecoverySourceStatus}</code>
                          </>
                        ) : null}
                        {selectedMissionRecoveryTargetId ? (
                          <>
                            {" / "}target=<code>{selectedMissionRecoveryTargetId}</code>
                          </>
                        ) : null}
                        {" / "}operator_required=<code>{selectedMissionRecovery.operator_required ? "true" : "false"}</code>
                        {" / "}automatic_retry=<code>{selectedMissionRecovery.automatic_retry ? "true" : "false"}</code>
                      </div>
                      {selectedMissionRecoveryReason ? (
                        <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{selectedMissionRecoveryReason}</div>
                      ) : null}
                      {selectedMissionRecoveryNextStep ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{selectedMissionRecoveryNextStep}</div>
                      ) : null}
                      {selectedMissionRecoveryReplacementId ? (
                        <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#111819", marginTop: 8 }}>
                          <div style={{ fontSize: 11, color: "#cce7e2" }}>
                            replacement=<code>{selectedMissionRecoveryReplacementId}</code>
                            {selectedMissionRecoveryReplacementStatus ? (
                              <>
                                {" / "}status=<code>{selectedMissionRecoveryReplacementStatus}</code>
                              </>
                            ) : null}
                            {selectedMissionRecoveryReplacementLastTaskId ? (
                              <>
                                {" / "}last_task=<code>{selectedMissionRecoveryReplacementLastTaskId}</code>
                              </>
                            ) : null}
                            {selectedMissionRecoveryReplacementLastTaskStatus ? (
                              <>
                                {" / "}task_status=<code>{selectedMissionRecoveryReplacementLastTaskStatus}</code>
                              </>
                            ) : null}
                            {selectedMissionRecoveryReplacementUpdatedAt ? (
                              <>
                                {" / "}updated=<code>{selectedMissionRecoveryReplacementUpdatedAt}</code>
                              </>
                            ) : null}
                          </div>
                          {selectedMissionRecoveryReplacementError ? (
                            <div style={{ fontSize: 11, color: "#ffb0b0", marginTop: 4 }}>
                              replacement_error=<code>{selectedMissionRecoveryReplacementError}</code>
                            </div>
                          ) : null}
                          {selectedMissionRecoveryReplacementNextStep ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                              {selectedMissionRecoveryReplacementNextStep}
                            </div>
                          ) : null}
                          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                            <button
                              style={buttonStyle}
                              onClick={() => inspectMission(selectedMissionRecoveryReplacementId)}
                              disabled={!selectedMissionRecoveryReplacementId}
                            >
                              Open replacement
                            </button>
                          </div>
                        </div>
                      ) : null}
                      {selectedMissionReplacementEligible ? (
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                          {missionReplaceBlockedReason ? (
                            <span style={{ fontSize: 11, color: "#ffcf9d", alignSelf: "center" }}>{missionReplaceBlockedReason}</span>
                          ) : null}
                          <button
                            style={buttonStyle}
                            onClick={() => void replaceMission(selectedMissionContextId)}
                            disabled={!canReplaceMission || missionActionBusy !== "" || missionQueueRunBusy}
                          >
                            {missionActionBusy === "replace" && missionActionTargetId === selectedMissionContextId
                              ? "Declaring replacement."
                              : "Declare replacement mission"}
                          </button>
                        </div>
                      ) : null}
                      {selectedMissionLastRecoveryAction ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                          reviewed=<code>{selectedMissionLastRecoveryAction}</code>
                          {selectedMissionLastRecoveryOutcome ? (
                            <>
                              {" / "}outcome=<code>{selectedMissionLastRecoveryOutcome}</code>
                            </>
                          ) : null}
                          {selectedMissionLastRecoveryTargetId ? (
                            <>
                              {" / "}target=<code>{selectedMissionLastRecoveryTargetId}</code>
                            </>
                          ) : null}
                          {selectedMissionLastRecoveryAt ? (
                            <>
                              {" / "}at=<code>{selectedMissionLastRecoveryAt}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {(selectedMissionApprovalId || selectedMissionDependencyTotal > 0 || selectedMissionLastAdvanceAction) ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      {selectedMissionApprovalId ? (
                        <>
                          approval <code>{selectedMissionApprovalId}</code>
                          {selectedMissionApprovalStatus ? (
                            <>
                              {" / "}status <code>{selectedMissionApprovalStatus}</code>
                            </>
                          ) : null}
                        </>
                      ) : null}
                      {selectedMissionDependencyTotal > 0 ? (
                        <>
                          {selectedMissionApprovalId ? " / " : ""}dependencies{" "}
                          <code>
                            {String(selectedMissionDependencyResolved)}/{String(selectedMissionDependencyTotal)}
                          </code>
                          {selectedMissionDependencyStatus ? (
                            <>
                              {" / "}state <code>{selectedMissionDependencyStatus}</code>
                            </>
                          ) : null}
                        </>
                      ) : null}
                      {selectedMissionLastAdvanceAction ? (
                        <>
                          {(selectedMissionApprovalId || selectedMissionDependencyTotal > 0) ? " / " : ""}last advance{" "}
                          <code>{selectedMissionLastAdvanceAction}</code>
                          {selectedMissionLastAdvanceOutcome ? (
                            <>
                              {" / "}outcome <code>{selectedMissionLastAdvanceOutcome}</code>
                            </>
                          ) : null}
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {(selectedMissionApprovalId ||
                    selectedMissionTargetIsMission ||
                    selectedMissionTargetIsOperation ||
                    selectedMissionFirstDependencyId ||
                    selectedMissionLastAdvanceOperationId) ? (
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      {selectedMissionApprovalId ? (
                        <button
                          style={buttonStyle}
                          onClick={() =>
                            props.onOpenApprovals(selectedMissionApprovalId, {
                              missionId: selectedMission.id,
                              operationId: selectedMissionTargetIsOperation
                                ? selectedMissionActionTargetId
                                : selectedMissionCurrentTaskId || selectedMissionQueueItem.last_task_id,
                            })
                          }
                        >
                          Review approval
                        </button>
                      ) : null}
                      {selectedMissionTargetIsMission ? (
                        <button style={buttonStyle} onClick={() => inspectMission(selectedMissionActionTargetId)}>
                          Open dependency mission
                        </button>
                      ) : null}
                      {selectedMissionTargetIsOperation ? (
                        <button style={buttonStyle} onClick={() => props.onOpenOperation(selectedMissionActionTargetId)}>
                          Open linked task
                        </button>
                      ) : null}
                      {selectedMissionFirstDependencyId &&
                      selectedMissionFirstDependencyId !== selectedMissionActionTargetId &&
                      selectedMissionFirstDependencyId.startsWith("msn_") ? (
                        <button style={buttonStyle} onClick={() => inspectMission(selectedMissionFirstDependencyId)}>
                          Open first dependency
                        </button>
                      ) : null}
                      {selectedMissionLastAdvanceOperationId &&
                      selectedMissionLastAdvanceOperationId !== selectedMissionActionTargetId ? (
                        <button style={buttonStyle} onClick={() => props.onOpenOperation(selectedMissionLastAdvanceOperationId)}>
                          Open last advanced task
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <button style={buttonStyle} onClick={() => void loadMissionDetail(selectedMission.id)} disabled={missionDetailBusy}>
                  {missionDetailBusy ? "Refreshing." : "Refresh mission flow"}
                </button>
                <button
                  style={buttonStyle}
                  onClick={() => void advanceMission(selectedMission.id)}
                  disabled={!canAdvanceMission || missionActionBusy !== "" || missionQueueRunBusy || !selectedMissionAdvanceEligible}
                >
                  {!selectedMissionAdvanceEligible && selectedMissionDependencyAction
                    ? selectedMissionDependencyStatus === "blocked"
                      ? "Dependency blocked"
                      : "Waiting on dependency"
                    : !selectedMissionAdvanceEligible
                      ? "Review required"
                      : missionActionBusy === "advance" && missionActionTargetId === selectedMission.id
                        ? "Advancing."
                        : selectedMissionAdvanceLabel}
                </button>
                {selectedMissionCurrentTaskId ? (
                  <button style={buttonStyle} onClick={() => props.onOpenOperation(selectedMissionCurrentTaskId)}>
                    Open current task
                  </button>
                ) : null}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 8, marginTop: 12 }}>
                <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#101010" }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>Linked Operations</div>
                  <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                    {missionLinkedOperations.length === 0 ? (
                      <div style={{ fontSize: 11, color: THEME.muted }}>No linked operations recorded for this mission yet.</div>
                    ) : (
                      missionLinkedOperations.slice(0, 4).map((detailItem) => {
                        const operation = detailItem.operation;
                        const approvalId = operationApprovalId(operation);
                        const gate = operationGate(operation);
                        const nextStep = operationNextStep(operation);
                        return (
                          <div
                            key={`mission-op-${operation.id}`}
                            style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                          >
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                              <div style={{ fontSize: 11, fontWeight: 600 }}>
                                {operationMetaString(operation, "objective") || operation.name || operation.id}
                              </div>
                              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                <span style={badgeStyle(operation.status || "unknown")}>{operation.status || "unknown"}</span>
                                {operationMetaString(operation, "orb_plane") ? (
                                  <span style={badgeStyle(operationMetaString(operation, "orb_plane"))}>
                                    {operationMetaString(operation, "orb_plane")}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                              <code>{operation.id}</code>
                            </div>
                            {operationResultMessage(operation) ? (
                              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{operationResultMessage(operation)}</div>
                            ) : null}
                            {operationTraceId(operation) ? (
                              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                                trace <code>{operationTraceId(operation)}</code>
                              </div>
                            ) : null}
                            {gate ? (
                              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                                gate <code>{gate}</code>
                                {nextStep ? (
                                  <>
                                    {" / "}next <code>{nextStep}</code>
                                  </>
                                ) : null}
                              </div>
                            ) : null}
                            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                              {approvalId ? (
                                <button
                                  style={buttonStyle}
                                  onClick={() =>
                                    props.onOpenApprovals(approvalId, {
                                      missionId: selectedMission.id,
                                      operationId: operation.id,
                                    })
                                  }
                                >
                                  Review approval
                                </button>
                              ) : null}
                              {["queued", "blocked"].includes(operationStatus(operation)) ? (
                                <button
                                  style={buttonStyle}
                                  onClick={() => void runMissionOperation(operation.id)}
                                  disabled={missionActionBusy !== "" && missionActionTargetId === operation.id}
                                >
                                  {missionActionBusy === "run" && missionActionTargetId === operation.id ? "Retrying." : "Retry now"}
                                </button>
                              ) : null}
                              {["queued", "running", "blocked"].includes(operationStatus(operation)) ? (
                                <button
                                  style={buttonStyle}
                                  onClick={() => void cancelMissionOperation(operation.id)}
                                  disabled={missionActionBusy !== "" && missionActionTargetId === operation.id}
                                >
                                  {missionActionBusy === "cancel" && missionActionTargetId === operation.id ? "Canceling." : "Cancel"}
                                </button>
                              ) : null}
                              <button style={buttonStyle} onClick={() => props.onOpenOperation(operation.id)}>
                                Open task
                              </button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#101010" }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>Run Ledger</div>
                  <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                    {missionRunLedger.length === 0 ? (
                      <div style={{ fontSize: 11, color: THEME.muted }}>No ledger entries are recorded for this mission yet.</div>
                    ) : (
                      missionRunLedger.slice(0, 6).map((entry) => (
                        <div
                          key={`mission-ledger-${entry.id}`}
                          style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                            <div style={{ fontSize: 11, fontWeight: 600 }}>{entry.name || entry.id}</div>
                            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                              {entry.status ? <span style={badgeStyle(entry.status)}>{entry.status}</span> : null}
                              <span style={{ fontSize: 11, color: THEME.muted }}>{toLocaleTime(entry.ts)}</span>
                            </div>
                          </div>
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            operation=<code>{operationMetaString(entry, "operation_name") || operationMetaString(entry, "operation_id") || "unknown"}</code>
                            {operationMetaString(entry, "operation_status") ? (
                              <>
                                {" / "}status=<code>{operationMetaString(entry, "operation_status")}</code>
                              </>
                            ) : null}
                          </div>
                          {operationGate(entry) ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                              gate <code>{operationGate(entry)}</code>
                              {operationNextStep(entry) ? (
                                <>
                                  {" / "}next <code>{operationNextStep(entry)}</code>
                                </>
                              ) : null}
                            </div>
                          ) : null}
                          {safeString(entry.message).trim() ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{safeString(entry.message).trim()}</div>
                          ) : null}
                          {operationTraceId(entry) ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                              trace <code>{operationTraceId(entry)}</code>
                            </div>
                          ) : null}
                          {operationMetaString(entry, "operation_id") ? (
                            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                              <button style={buttonStyle} onClick={() => props.onOpenOperation(operationMetaString(entry, "operation_id"))}>
                                Open task
                              </button>
                            </div>
                          ) : null}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {missionHistory.length > 0 ? (
                <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#101010", marginTop: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>Mission History</div>
                  <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                    {missionHistory.slice(0, 5).map((entry, index) => (
                      <div
                        key={`mission-history-${entry.ts || "unknown"}-${entry.event || index}`}
                        style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                          <div style={{ fontSize: 11, fontWeight: 600 }}>{entry.event || "event"}</div>
                          <div style={{ fontSize: 11, color: THEME.muted }}>{entry.ts || "unknown time"}</div>
                        </div>
                        {entry.details && Object.keys(entry.details).length > 0 ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{prettyData(entry.details)}</div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <div style={{ fontSize: 12, color: THEME.muted, marginTop: 8 }}>
              Mission detail is not available for the selected mission yet.
            </div>
          )}
        </div>

        {missionQueue.length > 0 ? (
          <>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>Mission Queue</div>
                <div style={{ fontSize: 11, color: missionQueueRunBlockedReason ? "#ffcf9d" : THEME.muted, marginTop: 4 }}>
                  {missionQueueRunBlockedReason ||
                    "Run one bounded queue pass to reconcile continuity and advance only missions that are already safe to move."}
                </div>
              </div>
              <button
                style={buttonStyle}
                onClick={() => void runMissionQueueOnce()}
                disabled={!canRunMissionQueue || missionQueueRunBusy || missionActionBusy !== ""}
              >
                {missionQueueRunBusy ? "Running queue." : "Run mission queue once"}
              </button>
            </div>
            {missionQueueRunSummary ? (
              <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#111819", marginTop: 8 }}>
                <div style={{ fontSize: 11, color: THEME.muted }}>
                  processed=<code>{String(missionQueueRunSummary.processed)}</code>
                  {" / "}applied=<code>{String(missionQueueRunSummary.applied)}</code>
                  {" / "}advanced=<code>{String(missionQueueRunSummary.advanced)}</code>
                  {" / "}errors=<code>{String(missionQueueRunSummary.errorCount)}</code>
                  {missionQueueRunSummary.status ? (
                    <>
                      {" / "}status=<code>{missionQueueRunSummary.status}</code>
                    </>
                  ) : null}
                </div>
                {Object.keys(missionQueueRunSummary.counts).length > 0 ? (
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    queued=<code>{String(missionQueueRunSummary.counts.queued ?? 0)}</code>
                    {" / "}active=<code>{String(missionQueueRunSummary.counts.active ?? 0)}</code>
                    {" / "}blocked=<code>{String(missionQueueRunSummary.counts.blocked ?? 0)}</code>
                    {" / "}failed=<code>{String(missionQueueRunSummary.counts.failed ?? 0)}</code>
                    {" / "}deadlettered=<code>{String(missionQueueRunSummary.counts.deadlettered ?? 0)}</code>
                  </div>
                ) : null}
                {missionQueueRunSummary.request ? (
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4, overflowWrap: "anywhere" }}>
                    actor=<code>{missionQueueRunSummary.request.actor || "unknown"}</code>
                    {typeof missionQueueRunSummary.request.limit === "number" ? (
                      <>
                        {" / "}limit=<code>{String(missionQueueRunSummary.request.limit)}</code>
                      </>
                    ) : null}
                    {missionQueueRunSummary.request.note ? (
                      <>
                        {" / "}note=<code>{missionQueueRunSummary.request.note}</code>
                      </>
                    ) : null}
                  </div>
                ) : null}
                {missionQueueRunSummary.error ? (
                  <div style={{ fontSize: 11, color: THEME.danger, marginTop: 4, overflowWrap: "anywhere" }}>
                    error=<code>{missionQueueRunSummary.error}</code>
                  </div>
                ) : null}
                {missionQueueRunSummary.results.length > 0 ? (
                  <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                    {missionQueueRunSummary.results.map((item, index) => {
                      const queueItem = item.queueItem;
                      const queueCurrentTask = item.currentTask ?? queueItem?.current_task;
                      const queueAction = safeString(queueItem?.recommended_action).trim();
                      const queueAdvanceEligible = queueItem?.advance?.eligible === true;
                      const queueAdvanceReason = safeString(queueItem?.advance?.reason).trim();
                      const queueTargetId = queueItem
                        ? missionRecoveryTargetId(queueItem, queueItem, undefined, queueCurrentTask) || item.operationId || ""
                        : item.operationId || "";
                      const queueOperationTargetId = queueItem
                        ? missionCurrentTaskId(queueItem, queueItem, undefined, queueCurrentTask) || item.operationId || ""
                        : item.operationId || "";
                      const queueTargetIsMission = queueTargetId.startsWith("msn_");
                      const queueTargetIsOperation = queueTargetId.startsWith("tsk_");
                      const queueApprovalId =
                        safeString(queueCurrentTask?.approval_id).trim() ||
                        safeString(queueItem?.last_task_approval_id).trim() ||
                        item.approvalId ||
                        "";
                      const queueApprovalStatus =
                        safeString(queueCurrentTask?.approval_status).trim() ||
                        safeString(queueItem?.last_task_approval_status).trim();
                      const queueCurrentTaskId = safeString(queueCurrentTask?.operation_id).trim();
                      const queueCurrentTaskStatus =
                        safeString(queueCurrentTask?.task_status).trim() ||
                        safeString(queueCurrentTask?.operation_status).trim();
                      const queueCurrentTaskResult = safeString(queueCurrentTask?.result_status).trim();
                      const queueCurrentTaskGate = safeString(queueCurrentTask?.gate).trim();
                      const queueCurrentTaskSource = safeString(queueCurrentTask?.source).trim();
                      const queueDependencyState = queueItem?.dependency_state;
                      const queueDependencyTotal = Math.max(0, Number(queueDependencyState?.total ?? queueItem?.dependency_count ?? 0));
                      const queueDependencyResolved = Math.max(0, Number(queueDependencyState?.resolved ?? 0));
                      const queueDependencyStatus = safeString(queueDependencyState?.status).trim();
                      const queueFirstDependencyId = safeString(queueDependencyState?.first_unresolved?.id).trim();
                      const queueLastAdvanceAction = safeString(queueItem?.last_advance_action).trim();
                      const queueLastAdvanceOutcome = safeString(queueItem?.last_advance_outcome).trim();
                      const queueLastAdvanceOperationId = safeString(queueItem?.last_advance_operation_id).trim();
                      const queueLatestHistoryEvent = safeString(queueItem?.latest_history_event).trim();
                      const queueLatestHistoryAt = mixedLocaleTime(queueItem?.latest_history_ts);
                      const queueHistoryTail = Array.isArray(queueItem?.history_tail) ? queueItem.history_tail.slice(-2) : [];
                      const queueReceiptSummary = item.receiptSummary;
                      const queueReceiptOperationId = safeString(queueReceiptSummary?.current_operation_id).trim();
                      const queueReceiptOperationStatus = safeString(queueReceiptSummary?.current_operation_status).trim();
                      const queueReceiptGate = safeString(queueReceiptSummary?.current_gate).trim();
                      const queueReceiptApprovalId = safeString(queueReceiptSummary?.current_approval_id).trim();
                      const queueReceiptTraceId = safeString(queueReceiptSummary?.current_trace_id).trim();
                      const queueReceiptRunId = safeString(queueReceiptSummary?.current_run_id).trim();
                      const queueReceiptArtifactDir = safeString(queueReceiptSummary?.current_artifact_dir).trim();
                      const queueResultTraceId = safeString(item.traceId).trim();
                      const queueResultRunId = safeString(item.runId).trim();
                      const queueResultArtifactDir = safeString(item.artifactDir).trim();
                      const queueCurrentTaskTraceId = safeString(queueCurrentTask?.trace_id).trim();
                      const queueCurrentTaskRunId = safeString(queueCurrentTask?.run_id).trim();
                      const queueCurrentTaskArtifactDir = safeString(queueCurrentTask?.artifact_dir).trim();
                      const queueVisibleTraceId = queueReceiptTraceId || queueResultTraceId || queueCurrentTaskTraceId;
                      const queueVisibleRunId = queueReceiptRunId || queueResultRunId || queueCurrentTaskRunId;
                      const queueVisibleArtifactDir =
                        queueReceiptArtifactDir || queueResultArtifactDir || queueCurrentTaskArtifactDir;
                      const queueReceiptLatestRunEvent = safeString(queueReceiptSummary?.latest_run_event).trim();
                      const queueReceiptLatestRunStatus = safeString(queueReceiptSummary?.latest_run_status).trim();
                      const queueReceiptLatestRunAt = mixedLocaleTime(queueReceiptSummary?.latest_run_ts);
                      return (
                      <div key={`mission-queue-summary-${item.missionId || item.operationId || index}`} style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                          <div style={{ fontSize: 11, fontWeight: 600 }}>{item.missionId || "mission"}</div>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {item.action ? <span style={badgeStyle(item.action)}>{item.action}</span> : null}
                            {item.status ? <span style={badgeStyle(item.status)}>{item.status}</span> : null}
                            {item.activeStage ? <span style={badgeStyle(item.activeStage)}>{item.activeStage}</span> : null}
                            {queueAction ? <span style={badgeStyle(queueAction)}>{queueAction}</span> : null}
                          </div>
                        </div>
                        {item.message ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{item.message}</div> : null}
                        {missionOperationRecoveryLine(item)}
                        {queueItem ? (
                          <div style={{ fontSize: 11, color: queueAdvanceEligible ? THEME.muted : "#ffcf9d", marginTop: 6 }}>
                            advance=<code>{queueAdvanceEligible ? "eligible" : "review_required"}</code>
                            {queueAdvanceReason ? (
                              <>
                                {" / "}{queueAdvanceReason}
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {(queueApprovalId || queueDependencyTotal > 0 || queueLastAdvanceAction) ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {queueApprovalId ? (
                              <>
                                approval=<code>{queueApprovalId}</code>
                                {queueApprovalStatus ? (
                                  <>
                                    {" / "}approval_status=<code>{queueApprovalStatus}</code>
                                  </>
                                ) : null}
                              </>
                            ) : null}
                            {queueDependencyTotal > 0 ? (
                              <>
                                {queueApprovalId ? " / " : ""}dependencies=
                                <code>
                                  {String(queueDependencyResolved)}/{String(queueDependencyTotal)}
                                </code>
                                {queueDependencyStatus ? (
                                  <>
                                    {" / "}state=<code>{queueDependencyStatus}</code>
                                  </>
                                ) : null}
                              </>
                            ) : null}
                            {queueLastAdvanceAction ? (
                              <>
                                {(queueApprovalId || queueDependencyTotal > 0) ? " / " : ""}last_advance=
                                <code>{queueLastAdvanceAction}</code>
                                {queueLastAdvanceOutcome ? (
                                  <>
                                    {" / "}outcome=<code>{queueLastAdvanceOutcome}</code>
                                  </>
                                ) : null}
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {queueCurrentTaskId || queueCurrentTaskStatus || queueCurrentTaskResult || queueCurrentTaskGate ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {queueCurrentTaskId ? (
                              <>
                                current_task=<code>{queueCurrentTaskId}</code>
                              </>
                            ) : null}
                            {queueCurrentTaskStatus ? (
                              <>
                                {queueCurrentTaskId ? " / " : ""}task_status=<code>{queueCurrentTaskStatus}</code>
                              </>
                            ) : null}
                            {queueCurrentTaskResult ? (
                              <>
                                {(queueCurrentTaskId || queueCurrentTaskStatus) ? " / " : ""}result=<code>{queueCurrentTaskResult}</code>
                              </>
                            ) : null}
                            {queueCurrentTaskGate ? (
                              <>
                                {(queueCurrentTaskId || queueCurrentTaskStatus || queueCurrentTaskResult) ? " / " : ""}gate=<code>{queueCurrentTaskGate}</code>
                              </>
                            ) : null}
                            {queueCurrentTaskSource ? (
                              <>
                                {" / "}source=<code>{queueCurrentTaskSource}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {queueReceiptOperationId ||
                        queueReceiptOperationStatus ||
                        queueReceiptGate ||
                        queueReceiptApprovalId ||
                        queueVisibleTraceId ||
                        queueVisibleRunId ||
                        queueVisibleArtifactDir ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {queueReceiptOperationId ? (
                              <>
                                receipt_task=<code>{queueReceiptOperationId}</code>
                              </>
                            ) : null}
                            {queueReceiptOperationStatus ? (
                              <>
                                {queueReceiptOperationId ? " / " : ""}receipt_status=<code>{queueReceiptOperationStatus}</code>
                              </>
                            ) : null}
                            {queueReceiptGate ? (
                              <>
                                {(queueReceiptOperationId || queueReceiptOperationStatus) ? " / " : ""}receipt_gate=
                                <code>{queueReceiptGate}</code>
                              </>
                            ) : null}
                            {queueReceiptApprovalId ? (
                              <>
                                {(queueReceiptOperationId || queueReceiptOperationStatus || queueReceiptGate) ? " / " : ""}
                                receipt_approval=<code>{queueReceiptApprovalId}</code>
                              </>
                            ) : null}
                            {queueVisibleTraceId ? (
                              <>
                                {(queueReceiptOperationId ||
                                queueReceiptOperationStatus ||
                                queueReceiptGate ||
                                queueReceiptApprovalId)
                                  ? " / "
                                  : ""}
                                trace=<code>{queueVisibleTraceId}</code>
                              </>
                            ) : null}
                            {queueVisibleRunId ? (
                              <>
                                {(queueReceiptOperationId ||
                                queueReceiptOperationStatus ||
                                queueReceiptGate ||
                                queueReceiptApprovalId ||
                                queueVisibleTraceId)
                                  ? " / "
                                  : ""}
                                run=<code>{queueVisibleRunId}</code>
                              </>
                            ) : null}
                            {queueVisibleArtifactDir ? (
                              <>
                                {(queueReceiptOperationId ||
                                queueReceiptOperationStatus ||
                                queueReceiptGate ||
                                queueReceiptApprovalId ||
                                queueVisibleTraceId ||
                                queueVisibleRunId)
                                  ? " / "
                                  : ""}
                                artifact=<code>{queueVisibleArtifactDir}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {queueReceiptLatestRunEvent || queueReceiptLatestRunStatus || queueReceiptLatestRunAt ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {queueReceiptLatestRunEvent ? (
                              <>
                                latest_run=<code>{queueReceiptLatestRunEvent}</code>
                              </>
                            ) : null}
                            {queueReceiptLatestRunStatus ? (
                              <>
                                {queueReceiptLatestRunEvent ? " / " : ""}run_status=<code>{queueReceiptLatestRunStatus}</code>
                              </>
                            ) : null}
                            {queueReceiptLatestRunAt ? (
                              <>
                                {(queueReceiptLatestRunEvent || queueReceiptLatestRunStatus) ? " / " : ""}run_at=
                                <code>{queueReceiptLatestRunAt}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {item.handoffDetail ? (
                          <div style={{ fontSize: 11, color: "#d6e8e8", marginTop: 6 }}>
                            Handoff{item.handoffAction ? ` (${item.handoffAction})` : ""}: {item.handoffDetail}
                          </div>
                        ) : null}
                        {item.gate || item.nextStep ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {item.gate ? (
                              <>
                                gate=<code>{item.gate}</code>
                              </>
                            ) : null}
                            {item.nextStep ? (
                              <>
                                {item.gate ? " / " : ""}next=<code>{item.nextStep}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {typeof item.historyCount === "number" ||
                        typeof item.linkedOperationCount === "number" ||
                        typeof item.runLedgerCount === "number" ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            history=<code>{String(item.historyCount ?? 0)}</code>
                            {" / "}linked=<code>{String(item.linkedOperationCount ?? 0)}</code>
                            {" / "}ledger=<code>{String(item.runLedgerCount ?? 0)}</code>
                          </div>
                        ) : null}
                        {queueLatestHistoryEvent || queueLatestHistoryAt ? (
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {queueLatestHistoryEvent ? (
                              <>
                                latest_receipt=<code>{queueLatestHistoryEvent}</code>
                              </>
                            ) : null}
                            {queueLatestHistoryAt ? (
                              <>
                                {queueLatestHistoryEvent ? " / " : ""}receipt_at=<code>{queueLatestHistoryAt}</code>
                              </>
                            ) : null}
                          </div>
                        ) : null}
                        {queueHistoryTail.length > 0 ? (
                          <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                            {queueHistoryTail.map((entry, historyIndex) => (
                              <div
                                key={[
                                  "mission-queue-summary-history",
                                  item.missionId || item.operationId || index,
                                  entry.ts || "unknown",
                                  entry.event || historyIndex,
                                ].join("-")}
                                style={{
                                  border: `1px solid ${THEME.panelBorder}`,
                                  borderRadius: 8,
                                  padding: 8,
                                  background: "#101010",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    gap: 8,
                                    flexWrap: "wrap",
                                  }}
                                >
                                  <div style={{ fontSize: 11, fontWeight: 600 }}>{entry.event || "receipt"}</div>
                                  <div style={{ fontSize: 11, color: THEME.muted }}>
                                    {mixedLocaleTime(entry.ts) || entry.ts || "unknown time"}
                                  </div>
                                </div>
                                {entry.details && Object.keys(entry.details).length > 0 ? (
                                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                                    {prettyData(entry.details)}
                                  </div>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                          {queueApprovalId ? (
                            <button
                              style={buttonStyle}
                              onClick={() =>
                                props.onOpenApprovals(queueApprovalId, {
                                  missionId: item.missionId,
                                  operationId: queueTargetIsOperation ? queueTargetId : queueOperationTargetId || undefined,
                                })
                              }
                            >
                              Review approval
                            </button>
                          ) : null}
                          {queueReceiptApprovalId && queueReceiptApprovalId !== queueApprovalId ? (
                            <button
                              style={buttonStyle}
                              onClick={() =>
                                props.onOpenApprovals(queueReceiptApprovalId, {
                                  missionId: item.missionId,
                                  operationId: queueReceiptOperationId || queueOperationTargetId || undefined,
                                })
                              }
                            >
                              Review receipt approval
                            </button>
                          ) : null}
                          {item.missionId ? (
                            <button style={buttonStyle} onClick={() => inspectMission(item.missionId || "")}>
                              Inspect mission flow
                            </button>
                          ) : null}
                          {item.operationId ? (
                            <button style={buttonStyle} onClick={() => props.onOpenOperation(item.operationId || "")}>
                              Open linked task
                            </button>
                          ) : null}
                          {queueTargetIsMission && queueTargetId !== item.missionId ? (
                            <button style={buttonStyle} onClick={() => inspectMission(queueTargetId)}>
                              Open dependency mission
                            </button>
                          ) : null}
                          {queueTargetIsOperation && queueTargetId !== item.operationId ? (
                            <button style={buttonStyle} onClick={() => props.onOpenOperation(queueTargetId)}>
                              Open action target
                            </button>
                          ) : null}
                          {queueFirstDependencyId && queueFirstDependencyId !== queueTargetId && queueFirstDependencyId.startsWith("msn_") ? (
                            <button style={buttonStyle} onClick={() => inspectMission(queueFirstDependencyId)}>
                              Open first dependency
                            </button>
                          ) : null}
                          {queueLastAdvanceOperationId &&
                          queueLastAdvanceOperationId !== item.operationId &&
                          queueLastAdvanceOperationId !== queueTargetId ? (
                            <button style={buttonStyle} onClick={() => props.onOpenOperation(queueLastAdvanceOperationId)}>
                              Open last advanced task
                            </button>
                          ) : null}
                          {queueReceiptOperationId &&
                          queueReceiptOperationId !== item.operationId &&
                          queueReceiptOperationId !== queueTargetId &&
                          queueReceiptOperationId !== queueLastAdvanceOperationId ? (
                            <button style={buttonStyle} onClick={() => props.onOpenOperation(queueReceiptOperationId)}>
                              Open receipt task
                            </button>
                          ) : null}
                        </div>
                      </div>
                      );
                    })}
                  </div>
                ) : null}
                {missionQueueRunSummary.errors.length > 0 ? (
                  <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                    {missionQueueRunSummary.errors.map((item, index) => {
                      const errorDetail = item.error || item.message || "No error detail was provided.";
                      return (
                        <div
                          key={`mission-queue-error-${item.missionId || item.operationId || index}`}
                          style={{
                            border: `1px solid ${THEME.panelBorder}`,
                            borderRadius: 10,
                            padding: 10,
                            background: "#1b1212",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              gap: 8,
                              flexWrap: "wrap",
                            }}
                          >
                            <div style={{ fontSize: 11, fontWeight: 600 }}>{item.missionId || "queue_run_error"}</div>
                            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                              <span style={badgeStyle("failed")}>queue_error</span>
                              {item.status ? <span style={badgeStyle(item.status)}>{item.status}</span> : null}
                              {item.action ? <span style={badgeStyle(item.action)}>{item.action}</span> : null}
                            </div>
                          </div>
                          <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 6 }}>{errorDetail}</div>
                          {missionOperationRecoveryLine(item)}
                          {item.operationId ||
                          item.approvalId ||
                          item.gate ||
                          item.nextStep ||
                          item.traceId ||
                          item.runId ||
                          item.artifactDir ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                              {item.operationId ? (
                                <>
                                  operation=<code>{item.operationId}</code>
                                </>
                              ) : null}
                              {item.approvalId ? (
                                <>
                                  {item.operationId ? " / " : ""}approval=<code>{item.approvalId}</code>
                                </>
                              ) : null}
                              {item.gate ? (
                                <>
                                  {(item.operationId || item.approvalId) ? " / " : ""}gate=<code>{item.gate}</code>
                                </>
                              ) : null}
                              {item.nextStep ? (
                                <>
                                  {(item.operationId || item.approvalId || item.gate) ? " / " : ""}next=
                                  <code>{item.nextStep}</code>
                                </>
                              ) : null}
                              {item.traceId ? (
                                <>
                                  {(item.operationId || item.approvalId || item.gate || item.nextStep) ? " / " : ""}
                                  trace=<code>{item.traceId}</code>
                                </>
                              ) : null}
                              {item.runId ? (
                                <>
                                  {(item.operationId || item.approvalId || item.gate || item.nextStep || item.traceId)
                                    ? " / "
                                    : ""}
                                  run=<code>{item.runId}</code>
                                </>
                              ) : null}
                              {item.artifactDir ? (
                                <>
                                  {(item.operationId ||
                                  item.approvalId ||
                                  item.gate ||
                                  item.nextStep ||
                                  item.traceId ||
                                  item.runId)
                                    ? " / "
                                    : ""}
                                  artifact=<code>{item.artifactDir}</code>
                                </>
                              ) : null}
                            </div>
                          ) : null}
                          {item.missionId || item.operationId || item.approvalId ? (
                            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                              {item.approvalId ? (
                                <button
                                  style={buttonStyle}
                                  onClick={() =>
                                    props.onOpenApprovals(item.approvalId || "", {
                                      missionId: item.missionId || undefined,
                                      operationId: item.operationId || undefined,
                                    })
                                  }
                                >
                                  Review approval
                                </button>
                              ) : null}
                              {item.missionId ? (
                                <button style={buttonStyle} onClick={() => inspectMission(item.missionId || "")}>
                                  Inspect mission flow
                                </button>
                              ) : null}
                              {item.operationId ? (
                                <button style={buttonStyle} onClick={() => props.onOpenOperation(item.operationId || "")}>
                                  Open task
                                </button>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
              showing=<code>{String(missionQueuePresentation.visible.length)}/{String(missionQueuePresentation.total)}</code>
              {" / "}review_required=<code>{String(missionQueuePresentation.reviewRequired)}</code>
              {" / "}eligible=<code>{String(missionQueuePresentation.eligible)}</code>
            </div>
            {missionQueuePresentation.hiddenTotal > 0 ? (
              <div
                style={{
                  fontSize: 11,
                  color: missionQueuePresentation.hiddenReviewRequired > 0 ? "#ffcf9d" : THEME.muted,
                  marginTop: 4,
                }}
              >
                Hidden from this bounded view: review_required=
                <code>{String(missionQueuePresentation.hiddenReviewRequired)}</code>
                {" / "}eligible=<code>{String(missionQueuePresentation.hiddenEligible)}</code>
              </div>
            ) : null}
            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
              {missionQueuePresentation.visible.map((item) => {
                const queueCurrentTask = item.current_task;
                const queueTargetId = missionRecoveryTargetId(item, item, undefined, queueCurrentTask);
                const queueOperationTargetId = missionCurrentTaskId(item, item, undefined, queueCurrentTask);
                const queueTargetIsMission = queueTargetId.startsWith("msn_");
                const queueTargetIsOperation = queueTargetId.startsWith("tsk_");
                const queueApprovalId =
                  safeString(queueCurrentTask?.approval_id).trim() || safeString(item.last_task_approval_id).trim();
                const queueApprovalStatus =
                  safeString(queueCurrentTask?.approval_status).trim() || safeString(item.last_task_approval_status).trim();
                const queueCurrentTaskId = safeString(queueCurrentTask?.operation_id).trim();
                const queueCurrentTaskStatus =
                  safeString(queueCurrentTask?.task_status).trim() || safeString(queueCurrentTask?.operation_status).trim();
                const queueCurrentTaskResult = safeString(queueCurrentTask?.result_status).trim();
                const queueCurrentTaskGate = safeString(queueCurrentTask?.gate).trim();
                const queueCurrentTaskSource = safeString(queueCurrentTask?.source).trim();
                const queueLoopState = item.loop_state;
                const queueLoopHandoff = item.handoff ?? queueLoopState?.handoff;
                const queueLoopActiveStage = safeString(queueLoopState?.active_stage).trim();
                const queueLoopHandoffAction = safeString(queueLoopHandoff?.action).trim();
                const queueLoopHandoffNextStep = safeString(queueLoopHandoff?.next_step).trim();
                const queueReceiptSummary = item.receipt_summary;
                const queueReceiptOperationId = safeString(queueReceiptSummary?.current_operation_id).trim();
                const queueReceiptOperationName = safeString(queueReceiptSummary?.current_operation_name).trim();
                const queueReceiptOperationPlane = safeString(queueReceiptSummary?.current_operation_plane).trim();
                const queueReceiptOperationStatus = safeString(queueReceiptSummary?.current_operation_status).trim();
                const queueReceiptAdvanceAction = safeString(queueReceiptSummary?.current_advance_action).trim();
                const queueReceiptGate = safeString(queueReceiptSummary?.current_gate).trim();
                const queueReceiptApprovalId = safeString(queueReceiptSummary?.current_approval_id).trim();
                const queueReceiptTraceId = safeString(queueReceiptSummary?.current_trace_id).trim();
                const queueReceiptRunId = safeString(queueReceiptSummary?.current_run_id).trim();
                const queueReceiptArtifactDir = safeString(queueReceiptSummary?.current_artifact_dir).trim();
                const queueReceiptRunCount = queueReceiptSummary?.run_ledger_count;
                const queueReceiptHistoryCount = queueReceiptSummary?.history_count;
                const queueReceiptMemoryCount = queueReceiptSummary?.memory_receipt_count;
                const queueReceiptPlanStatus = safeString(queueReceiptSummary?.plan_status).trim();
                const queueReceiptPlanStepId = safeString(queueReceiptSummary?.plan_current_step_id).trim();
                const queueReceiptPlanStepTitle = safeString(queueReceiptSummary?.plan_current_step_title).trim();
                const queueReceiptPlanStepCount = queueReceiptSummary?.plan_step_count;
                const queueReceiptPlanCheckpointCount = queueReceiptSummary?.plan_checkpoint_count;
                const latestActivity = latestActivitySummary(item.latest_activity);
                const latestHistoryAt = mixedLocaleTime(item.latest_history_ts);
                const historyTail = Array.isArray(item.history_tail) ? item.history_tail.slice(-2) : [];
                const dependencyState = item.dependency_state;
                const dependencyStatus = safeString(dependencyState?.status).trim();
                const firstDependency = dependencyState?.first_unresolved;
                const dependencyAction = ["wait_for_dependency", "resolve_dependency_blocker"].includes(
                  safeString(item.recommended_action).trim(),
                );
                const queueAdvanceEligible = item.advance?.eligible === true;
                const queueAdvanceAction = safeString(item.advance?.action).trim();
                const queueAdvanceReason = safeString(item.advance?.reason).trim();
                const queueAdvanceLabel = queueAdvanceAction === "create_first_operation" ? "Create operation" : "Advance once";
                return (
                  <div
                    key={`mission-queue-${item.id}`}
                    style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{item.objective || item.id}</div>
                      <span style={badgeStyle(item.status || "unknown")}>{item.status || "unknown"}</span>
                    </div>
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      action=<code>{item.recommended_action || "review_mission"}</code>
                      {" / "}advance=<code>{queueAdvanceEligible ? "eligible" : "review_required"}</code>
                    </div>
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      {item.operator_hint || item.next_step || "Mission queue item needs operator review."}
                    </div>
                    {!queueAdvanceEligible && queueAdvanceReason ? (
                      <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{queueAdvanceReason}</div>
                    ) : null}
                    {dependencyState && Number(dependencyState.total ?? 0) > 0 ? (
                      <div style={{ fontSize: 11, color: dependencyAction ? "#ffcf9d" : THEME.muted, marginTop: 4 }}>
                        dependencies=<code>{String(dependencyState.resolved ?? 0)}/{String(dependencyState.total ?? 0)}</code>
                        {" / "}state=<code>{dependencyStatus || "unknown"}</code>
                        {firstDependency?.id ? (
                          <>
                            {" / "}next=<code>{firstDependency.id}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      priority=<code>{String(item.priority ?? 0)}</code>
                      {" / "}risk=<code>{item.risk_tier || "unknown"}</code>
                    </div>
                    {queueApprovalId ? (
                      <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>
                        approval=<code>{queueApprovalId}</code>
                        {queueApprovalStatus ? (
                          <>
                            {" / "}approval_status=<code>{queueApprovalStatus}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {queueCurrentTaskId || queueCurrentTaskStatus || queueCurrentTaskResult || queueCurrentTaskGate ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        {queueCurrentTaskId ? (
                          <>
                            current_task=<code>{queueCurrentTaskId}</code>
                          </>
                        ) : null}
                        {queueCurrentTaskStatus ? (
                          <>
                            {queueCurrentTaskId ? " / " : ""}task_status=<code>{queueCurrentTaskStatus}</code>
                          </>
                        ) : null}
                        {queueCurrentTaskResult ? (
                          <>
                            {(queueCurrentTaskId || queueCurrentTaskStatus) ? " / " : ""}result=<code>{queueCurrentTaskResult}</code>
                          </>
                        ) : null}
                        {queueCurrentTaskGate ? (
                          <>
                            {(queueCurrentTaskId || queueCurrentTaskStatus || queueCurrentTaskResult) ? " / " : ""}gate=<code>{queueCurrentTaskGate}</code>
                          </>
                        ) : null}
                        {queueCurrentTaskSource ? (
                          <>
                            {" / "}source=<code>{queueCurrentTaskSource}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {queueLoopActiveStage || queueLoopHandoffAction || queueLoopHandoffNextStep ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        {queueLoopActiveStage ? (
                          <>
                            loop=<code>{queueLoopActiveStage}</code>
                          </>
                        ) : null}
                        {queueLoopHandoffAction ? (
                          <>
                            {queueLoopActiveStage ? " / " : ""}handoff=<code>{queueLoopHandoffAction}</code>
                          </>
                        ) : null}
                        {queueLoopHandoffNextStep ? (
                          <>
                            {(queueLoopActiveStage || queueLoopHandoffAction) ? " / " : ""}next=
                            <code>{queueLoopHandoffNextStep}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {queueReceiptOperationId ||
                    queueReceiptOperationName ||
                    queueReceiptOperationPlane ||
                    queueReceiptOperationStatus ||
                    queueReceiptAdvanceAction ||
                    queueReceiptGate ||
                    queueReceiptTraceId ||
                    queueReceiptRunId ||
                    queueReceiptArtifactDir ||
                    typeof queueReceiptRunCount === "number" ||
                    typeof queueReceiptHistoryCount === "number" ||
                    typeof queueReceiptMemoryCount === "number" ||
                    queueReceiptPlanStatus ||
                    queueReceiptPlanStepId ||
                    queueReceiptPlanStepTitle ||
                    typeof queueReceiptPlanStepCount === "number" ||
                    typeof queueReceiptPlanCheckpointCount === "number" ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        {queueReceiptOperationId ? (
                          <>
                            receipt_task=<code>{queueReceiptOperationId}</code>
                          </>
                        ) : null}
                        {queueReceiptOperationStatus ? (
                          <>
                            {queueReceiptOperationId ? " / " : ""}receipt_status=
                            <code>{queueReceiptOperationStatus}</code>
                          </>
                        ) : null}
                        {queueReceiptOperationName ? (
                          <>
                            {(queueReceiptOperationId || queueReceiptOperationStatus) ? " / " : ""}task_name=
                            <code>{queueReceiptOperationName}</code>
                          </>
                        ) : null}
                        {queueReceiptOperationPlane ? (
                          <>
                            {(queueReceiptOperationId || queueReceiptOperationStatus || queueReceiptOperationName) ? " / " : ""}
                            plane=<code>{queueReceiptOperationPlane}</code>
                          </>
                        ) : null}
                        {queueReceiptAdvanceAction ? (
                          <>
                            {(queueReceiptOperationId ||
                            queueReceiptOperationStatus ||
                            queueReceiptOperationName ||
                            queueReceiptOperationPlane)
                              ? " / "
                              : ""}
                            advance=<code>{queueReceiptAdvanceAction}</code>
                          </>
                        ) : null}
                        {queueReceiptGate ? (
                          <>
                            {(queueReceiptOperationId ||
                            queueReceiptOperationStatus ||
                            queueReceiptOperationName ||
                            queueReceiptOperationPlane ||
                            queueReceiptAdvanceAction)
                              ? " / "
                              : ""}
                            receipt_gate=
                            <code>{queueReceiptGate}</code>
                          </>
                        ) : null}
                        {queueReceiptApprovalId ? (
                          <>
                            {(queueReceiptOperationId || queueReceiptOperationStatus || queueReceiptGate) ? " / " : ""}
                            receipt_approval=<code>{queueReceiptApprovalId}</code>
                          </>
                        ) : null}
                        {queueReceiptTraceId ? (
                          <>
                            {(queueReceiptOperationId ||
                            queueReceiptOperationStatus ||
                            queueReceiptGate ||
                            queueReceiptApprovalId)
                              ? " / "
                              : ""}
                            trace=<code>{queueReceiptTraceId}</code>
                          </>
                        ) : null}
                        {queueReceiptRunId ? (
                          <>
                            {(queueReceiptOperationId ||
                            queueReceiptOperationStatus ||
                            queueReceiptGate ||
                            queueReceiptApprovalId ||
                            queueReceiptTraceId)
                              ? " / "
                              : ""}
                            run=<code>{queueReceiptRunId}</code>
                          </>
                        ) : null}
                        {queueReceiptArtifactDir ? (
                          <>
                            {(queueReceiptOperationId ||
                            queueReceiptOperationStatus ||
                            queueReceiptGate ||
                            queueReceiptApprovalId ||
                            queueReceiptTraceId ||
                            queueReceiptRunId)
                              ? " / "
                              : ""}
                            artifact=<code>{queueReceiptArtifactDir}</code>
                          </>
                        ) : null}
                        {typeof queueReceiptRunCount === "number" ? (
                          <>
                            {(queueReceiptOperationId ||
                            queueReceiptOperationStatus ||
                            queueReceiptGate ||
                            queueReceiptApprovalId ||
                            queueReceiptTraceId ||
                            queueReceiptRunId ||
                            queueReceiptArtifactDir)
                              ? " / "
                              : ""}
                            run_receipts=<code>{String(queueReceiptRunCount)}</code>
                          </>
                        ) : null}
                        {typeof queueReceiptHistoryCount === "number" ? (
                          <>
                            {" / "}history_receipts=<code>{String(queueReceiptHistoryCount)}</code>
                          </>
                        ) : null}
                        {typeof queueReceiptMemoryCount === "number" ? (
                          <>
                            {" / "}memory_receipts=<code>{String(queueReceiptMemoryCount)}</code>
                          </>
                        ) : null}
                        {queueReceiptPlanStatus ? (
                          <>
                            {" / "}plan=<code>{queueReceiptPlanStatus}</code>
                          </>
                        ) : null}
                        {queueReceiptPlanStepId ? (
                          <>
                            {" / "}step=<code>{queueReceiptPlanStepId}</code>
                          </>
                        ) : null}
                        {queueReceiptPlanStepTitle ? (
                          <>
                            {" / "}step_title=<code>{queueReceiptPlanStepTitle}</code>
                          </>
                        ) : null}
                        {typeof queueReceiptPlanStepCount === "number" ? (
                          <>
                            {" / "}steps=<code>{String(queueReceiptPlanStepCount)}</code>
                          </>
                        ) : null}
                        {typeof queueReceiptPlanCheckpointCount === "number" ? (
                          <>
                            {" / "}checkpoints=<code>{String(queueReceiptPlanCheckpointCount)}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {queueReceiptArtifactDir ? (
                      <div style={{ marginTop: 8 }}>
                        <ArtifactInspectionPanel
                          baseUrl={resolvedBaseUrl}
                          artifactDir={queueReceiptArtifactDir}
                          title="Queue Receipt Artifact"
                          buttonLabel="Inspect receipt artifact"
                          buttonStyle={buttonStyle}
                          badgeStyle={badgeStyle}
                          borderColor={THEME.panelBorder}
                          mutedColor={THEME.muted}
                        />
                      </div>
                    ) : null}
                    {latestActivity.name || latestActivity.status || latestActivity.gate || latestActivity.observedAt ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        latest=<code>{latestActivity.name || "activity"}</code>
                        {" / "}status=<code>{latestActivity.status || "unknown"}</code>
                        {latestActivity.gate ? (
                          <>
                            {" / "}gate=<code>{latestActivity.gate}</code>
                          </>
                        ) : null}
                        {latestActivity.observedAt ? (
                          <>
                            {" / "}at=<code>{latestActivity.observedAt}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {(item.history_count || item.latest_history_event || latestHistoryAt) ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        receipts=<code>{String(item.history_count || 0)}</code>
                        {item.latest_history_event ? (
                          <>
                            {" / "}latest_receipt=<code>{item.latest_history_event}</code>
                          </>
                        ) : null}
                        {latestHistoryAt ? (
                          <>
                            {" / "}receipt_at=<code>{latestHistoryAt}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {historyTail.length > 0 ? (
                      <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                        {historyTail.map((entry, historyIndex) => (
                          <div
                            key={`mission-queue-history-${item.id}-${entry.ts || "unknown"}-${entry.event || historyIndex}`}
                            style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#101010" }}
                          >
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                              <div style={{ fontSize: 11, fontWeight: 600 }}>{entry.event || "receipt"}</div>
                              <div style={{ fontSize: 11, color: THEME.muted }}>{mixedLocaleTime(entry.ts) || entry.ts || "unknown time"}</div>
                            </div>
                            {entry.details && Object.keys(entry.details).length > 0 ? (
                              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{prettyData(entry.details)}</div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      {queueApprovalId ? (
                        <button
                          style={buttonStyle}
                          onClick={() =>
                            props.onOpenApprovals(queueApprovalId, {
                              missionId: item.id,
                              operationId: queueTargetIsOperation ? queueTargetId : queueOperationTargetId || undefined,
                            })
                          }
                        >
                          Review approval
                        </button>
                      ) : null}
                      {queueReceiptApprovalId && queueReceiptApprovalId !== queueApprovalId ? (
                        <button
                          style={buttonStyle}
                          onClick={() =>
                            props.onOpenApprovals(queueReceiptApprovalId, {
                              missionId: item.id,
                              operationId: queueReceiptOperationId || queueOperationTargetId || undefined,
                            })
                          }
                        >
                          Review receipt approval
                        </button>
                      ) : null}
                      <button
                        style={buttonStyle}
                        onClick={() => void advanceMission(item.id)}
                        disabled={!canAdvanceMission || missionActionBusy !== "" || missionQueueRunBusy || !queueAdvanceEligible}
                      >
                        {!queueAdvanceEligible && dependencyAction
                          ? dependencyStatus === "blocked"
                            ? "Dependency blocked"
                            : "Waiting on dependency"
                          : !queueAdvanceEligible
                            ? "Review required"
                          : missionActionBusy === "advance" && missionActionTargetId === item.id
                            ? "Advancing."
                            : queueAdvanceLabel}
                      </button>
                      <button style={buttonStyle} onClick={() => inspectMission(item.id)}>
                        Inspect mission flow
                      </button>
                      {queueTargetId && (queueTargetIsMission || queueTargetIsOperation) ? (
                        <button
                          style={buttonStyle}
                          onClick={() =>
                            queueTargetIsMission ? inspectMission(queueTargetId) : props.onOpenOperation(queueTargetId)
                          }
                        >
                          {queueTargetIsMission ? "Open dependency mission" : "Open linked task"}
                        </button>
                      ) : null}
                      {queueReceiptOperationId &&
                      queueReceiptOperationId !== queueTargetId &&
                      queueReceiptOperationId !== queueOperationTargetId ? (
                        <button style={buttonStyle} onClick={() => props.onOpenOperation(queueReceiptOperationId)}>
                          Open receipt task
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : null}

        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Return-to-Work Recommendations</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {returnToWorkItems.map((item) => (
            <div
              key={item.id}
              style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 600 }}>{item.title}</div>
                <span style={badgeStyle(item.tone)}>{item.label}</span>
              </div>
              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{item.detail}</div>
              {item.onAction && item.actionLabel ? (
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                  <button style={buttonStyle} onClick={item.onAction}>
                    {item.actionLabel}
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>

        {handoffTasks.length > 0 ? (
          <>
            <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Handoffs</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
              {handoffTasks.map((task) => (
                <div
                  key={`handoff-${task.id}`}
                  style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 999, padding: "8px 10px", background: "#121212" }}
                >
                  <div style={{ fontSize: 11, fontWeight: 600 }}>{task.objective || task.capability || task.id}</div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    assigned_to=<code>{task.assigned_to || "unknown"}</code>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : null}

        {failedPreviewPresentation.total > 0 ? (
          <>
            <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Failed Mission Recovery</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              showing=<code>{String(failedPreviewPresentation.visible.length)}/{String(failedPreviewPresentation.total)}</code>
            </div>
            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
              {failedPreviewPresentation.visible.map((item) => {
                const failedCurrentTask = item.current_task;
                const recovery = item.recovery;
                const recoveryAction = safeString(recovery?.action).trim() || safeString(item.recommended_action).trim();
                const recoveryTargetId =
                  safeString(recovery?.target_id).trim() ||
                  safeString(item.action_target_id).trim() ||
                  safeString(failedCurrentTask?.operation_id).trim() ||
                  safeString(item.last_task_id).trim();
                const recoveryReason = safeString(recovery?.reason).trim() || safeString(item.operator_hint).trim();
                const recoveryNextStep = safeString(recovery?.next_step).trim();
                const lastRecoveryAction =
                  safeString(item.last_recovery_action).trim() || safeString(recovery?.last_review_action).trim();
                const lastRecoveryOutcome =
                  safeString(item.last_recovery_outcome).trim() || safeString(recovery?.last_review_outcome).trim();
                const lastRecoveryAt = mixedLocaleTime(
                  safeString(item.last_recovery_at).trim() || safeString(recovery?.last_reviewed_at).trim(),
                );
                const failedTaskStatus =
                  safeString(failedCurrentTask?.task_status).trim() ||
                  safeString(failedCurrentTask?.operation_status).trim() ||
                  safeString(item.last_task_status).trim();
                const failedTaskResult =
                  safeString(failedCurrentTask?.result_status).trim() ||
                  safeString(item.last_task_result_status).trim();
                return (
                  <div
                    key={`mission-failed-${item.id}`}
                    style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{item.objective || item.id}</div>
                      <span style={badgeStyle(item.status || "failed")}>{item.status || "failed"}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>
                      recovery=<code>{recoveryAction || "retry_or_deadletter"}</code>
                      {recoveryTargetId ? (
                        <>
                          {" / "}target=<code>{recoveryTargetId}</code>
                        </>
                      ) : null}
                      {" / "}automatic_retry=<code>{recovery?.automatic_retry ? "true" : "false"}</code>
                    </div>
                    {recoveryReason ? (
                      <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{recoveryReason}</div>
                    ) : null}
                    {recoveryNextStep ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{recoveryNextStep}</div>
                    ) : null}
                    <MissionRecoveryFollowthroughCard recovery={recovery} onOpenMission={inspectMission} />
                    {lastRecoveryAction ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        reviewed=<code>{lastRecoveryAction}</code>
                        {lastRecoveryOutcome ? (
                          <>
                            {" / "}outcome=<code>{lastRecoveryOutcome}</code>
                          </>
                        ) : null}
                        {lastRecoveryAt ? (
                          <>
                            {" / "}at=<code>{lastRecoveryAt}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {failedTaskStatus || failedTaskResult ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        {failedTaskStatus ? (
                          <>
                            task_status=<code>{failedTaskStatus}</code>
                          </>
                        ) : null}
                        {failedTaskResult ? (
                          <>
                            {failedTaskStatus ? " / " : ""}result=<code>{failedTaskResult}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      {recoveryTargetId.startsWith("tsk_") ? (
                        <button style={buttonStyle} onClick={() => props.onOpenOperation(recoveryTargetId)}>
                          Open failed task
                        </button>
                      ) : null}
                      <button style={buttonStyle} onClick={() => inspectMission(item.id)}>
                        Inspect
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
            {failedPreviewPresentation.hiddenTotal > 0 ? (
              <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
                Hidden from this bounded view: <code>{String(failedPreviewPresentation.hiddenTotal)}</code>
              </div>
            ) : null}
          </>
        ) : null}

        {deadletterPreviewPresentation.total > 0 ? (
          <>
            <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Deadletter</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              showing=<code>{String(deadletterPreviewPresentation.visible.length)}/{String(deadletterPreviewPresentation.total)}</code>
            </div>
            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
              {deadletterPreviewPresentation.visible.map((item) => {
                const deadletterCurrentTask = item.current_task;
                const latestActivity = latestActivitySummary(item.latest_activity);
                const updatedAt = mixedLocaleTime(item.updated_at);
                const latestHistoryAt = mixedLocaleTime(item.latest_history_ts);
                const historyTail = Array.isArray(item.history_tail) ? item.history_tail.slice(-2) : [];
                const deadletterOperationId =
                  safeString(deadletterCurrentTask?.operation_id).trim() || safeString(item.last_task_id).trim();
                const approvalId =
                  safeString(deadletterCurrentTask?.approval_id).trim() || safeString(item.last_task_approval_id).trim();
                const previousApprovalId = safeString(item.last_task_previous_approval_id).trim();
                const previousApprovalStatus = safeString(item.last_task_previous_approval_status).trim();
                const approvalStatus =
                  safeString(deadletterCurrentTask?.approval_status).trim() || safeString(item.last_task_approval_status).trim();
                const replacementKind = safeString(item.last_task_approval_replacement_kind).trim();
                const replacementReason = safeString(item.last_task_approval_replacement_reason).trim();
                const deadletterCurrentTaskStatus =
                  safeString(deadletterCurrentTask?.task_status).trim() ||
                  safeString(deadletterCurrentTask?.operation_status).trim();
                const deadletterCurrentTaskResult = safeString(deadletterCurrentTask?.result_status).trim();
                const deadletterCurrentTaskGate = safeString(deadletterCurrentTask?.gate).trim();
                const replacementChangedKeys = Array.isArray(item.last_task_approval_replacement_changed_keys)
                  ? item.last_task_approval_replacement_changed_keys.map((key) => safeString(key).trim()).filter(Boolean)
                  : [];
                const recovery = item.recovery;
                const recoveryAction = safeString(recovery?.action).trim();
                const recoveryTargetId = safeString(recovery?.target_id).trim();
                const recoveryReason = safeString(recovery?.reason).trim();
                const recoveryNextStep = safeString(recovery?.next_step).trim();
                const recoverySourceStatus = safeString(recovery?.source_status).trim();
                const lastRecoveryAction =
                  safeString(item.last_recovery_action).trim() || safeString(recovery?.last_review_action).trim();
                const lastRecoveryOutcome =
                  safeString(item.last_recovery_outcome).trim() || safeString(recovery?.last_review_outcome).trim();
                const lastRecoveryAt = mixedLocaleTime(
                  safeString(item.last_recovery_at).trim() || safeString(recovery?.last_reviewed_at).trim(),
                );
                return (
                  <div
                    key={`mission-deadletter-${item.id}`}
                    style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{item.objective || item.id}</div>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        <span style={badgeStyle(item.status || "deadlettered")}>{item.status || "deadlettered"}</span>
                        <span style={badgeStyle(item.recommended_action || "review_deadletter")}>
                          {item.recommended_action || "review_deadletter"}
                        </span>
                      </div>
                    </div>
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      action=<code>{item.recommended_action || "review_deadletter"}</code>
                      {updatedAt ? (
                        <>
                          {" / "}updated=<code>{updatedAt}</code>
                        </>
                      ) : null}
                      {approvalId ? (
                        <>
                          {" / "}approval=<code>{approvalId}</code>
                        </>
                      ) : null}
                      {approvalStatus ? (
                        <>
                          {" / "}approval_status=<code>{approvalStatus}</code>
                        </>
                      ) : null}
                      {previousApprovalId ? (
                        <>
                          {" / "}previous_approval=<code>{previousApprovalId}</code>
                        </>
                      ) : null}
                      {previousApprovalStatus ? (
                        <>
                          {" / "}previous_status=<code>{previousApprovalStatus}</code>
                        </>
                      ) : null}
                      {replacementKind ? (
                        <>
                          {" / "}replacement_kind=<code>{replacementKind}</code>
                        </>
                      ) : null}
                      {replacementReason ? (
                        <>
                          {" / "}replacement=<code>{replacementReason}</code>
                        </>
                      ) : null}
                      {replacementChangedKeys.length > 0 ? (
                        <>
                          {" / "}changed_keys=<code>{replacementChangedKeys.join(",")}</code>
                        </>
                      ) : null}
                    </div>
                    <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 6 }}>
                      {item.reason || "Mission has been deadlettered."}
                    </div>
                    {recovery ? (
                      <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>
                        recovery=<code>{recoveryAction || item.recommended_action || "review_deadletter"}</code>
                        {recoverySourceStatus ? (
                          <>
                            {" / "}source=<code>{recoverySourceStatus}</code>
                          </>
                        ) : null}
                        {recoveryTargetId ? (
                          <>
                            {" / "}target=<code>{recoveryTargetId}</code>
                          </>
                        ) : null}
                        {" / "}operator_required=<code>{recovery.operator_required ? "true" : "false"}</code>
                        {" / "}automatic_retry=<code>{recovery.automatic_retry ? "true" : "false"}</code>
                        {recoveryReason ? (
                          <>
                            {" / "}reason=<code>{recoveryReason}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {recoveryNextStep ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{recoveryNextStep}</div>
                    ) : null}
                    <MissionRecoveryFollowthroughCard recovery={recovery} onOpenMission={inspectMission} />
                    {lastRecoveryAction ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        reviewed=<code>{lastRecoveryAction}</code>
                        {lastRecoveryOutcome ? (
                          <>
                            {" / "}outcome=<code>{lastRecoveryOutcome}</code>
                          </>
                        ) : null}
                        {lastRecoveryAt ? (
                          <>
                            {" / "}at=<code>{lastRecoveryAt}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {item.approval_summary ? (
                      <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>{item.approval_summary}</div>
                    ) : null}
                    {item.approval_replacement_summary ? (
                      <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>{item.approval_replacement_summary}</div>
                    ) : null}
                    {item.history_summary ? (
                      <div style={{ fontSize: 11, color: "#cce7e2", marginTop: 4 }}>{item.history_summary}</div>
                    ) : null}
                    {deadletterOperationId || deadletterCurrentTaskStatus || deadletterCurrentTaskResult || deadletterCurrentTaskGate ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        {deadletterOperationId ? (
                          <>
                            current_task=<code>{deadletterOperationId}</code>
                          </>
                        ) : null}
                        {deadletterCurrentTaskStatus ? (
                          <>
                            {deadletterOperationId ? " / " : ""}task_status=<code>{deadletterCurrentTaskStatus}</code>
                          </>
                        ) : null}
                        {deadletterCurrentTaskResult ? (
                          <>
                            {(deadletterOperationId || deadletterCurrentTaskStatus) ? " / " : ""}result=<code>{deadletterCurrentTaskResult}</code>
                          </>
                        ) : null}
                        {deadletterCurrentTaskGate ? (
                          <>
                            {(deadletterOperationId || deadletterCurrentTaskStatus || deadletterCurrentTaskResult) ? " / " : ""}gate=<code>{deadletterCurrentTaskGate}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {latestActivity.name || latestActivity.status || latestActivity.gate || latestActivity.observedAt ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        latest=<code>{latestActivity.name || "activity"}</code>
                        {" / "}status=<code>{latestActivity.status || "unknown"}</code>
                        {latestActivity.gate ? (
                          <>
                            {" / "}gate=<code>{latestActivity.gate}</code>
                          </>
                        ) : null}
                        {latestActivity.observedAt ? (
                          <>
                            {" / "}at=<code>{latestActivity.observedAt}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {(item.history_count || item.latest_history_event || latestHistoryAt) ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        receipts=<code>{String(item.history_count || 0)}</code>
                        {item.latest_history_event ? (
                          <>
                            {" / "}latest_receipt=<code>{item.latest_history_event}</code>
                          </>
                        ) : null}
                        {latestHistoryAt ? (
                          <>
                            {" / "}receipt_at=<code>{latestHistoryAt}</code>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {historyTail.length > 0 ? (
                      <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                        {historyTail.map((entry, historyIndex) => (
                          <div
                            key={`overview-deadletter-history-${item.id}-${entry.ts || "unknown"}-${entry.event || historyIndex}`}
                            style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8, background: "#101010" }}
                          >
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                              <div style={{ fontSize: 11, fontWeight: 600 }}>{entry.event || "receipt"}</div>
                              <div style={{ fontSize: 11, color: THEME.muted }}>{mixedLocaleTime(entry.ts) || entry.ts || "unknown time"}</div>
                            </div>
                            {entry.details && Object.keys(entry.details).length > 0 ? (
                              <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{prettyData(entry.details)}</div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8, gap: 8, flexWrap: "wrap" }}>
                      {approvalId ? (
                        <button
                          style={buttonStyle}
                          onClick={() =>
                            props.onOpenApprovals(approvalId, {
                              missionId: item.id,
                              operationId: deadletterOperationId || undefined,
                              source: "deadletter",
                              reviewKind: replacementKind || undefined,
                              reviewReason: replacementReason || undefined,
                              changedKeys: replacementChangedKeys,
                            })
                          }
                        >
                          {item.approval_review_label || "Review approval"}
                        </button>
                      ) : null}
                      {previousApprovalId && previousApprovalId !== approvalId ? (
                        <button
                          style={buttonStyle}
                          onClick={() =>
                            props.onOpenApprovals(previousApprovalId, {
                              missionId: item.id,
                              operationId: deadletterOperationId || undefined,
                              source: "deadletter",
                              reviewKind: replacementKind || undefined,
                              reviewReason: replacementReason || undefined,
                              changedKeys: replacementChangedKeys,
                            })
                          }
                        >
                          {item.previous_approval_review_label || "Open previous approval"}
                        </button>
                      ) : null}
                      {deadletterOperationId ? (
                        <button style={buttonStyle} onClick={() => props.onOpenOperation(deadletterOperationId)}>
                          Open current task
                        </button>
                      ) : null}
                      <button style={buttonStyle} onClick={() => inspectMission(item.id)}>
                        Inspect mission flow
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
            {deadletterPreviewPresentation.hiddenTotal > 0 ? (
              <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 8 }}>
                Hidden from this bounded view: <code>{String(deadletterPreviewPresentation.hiddenTotal)}</code>
              </div>
            ) : null}
          </>
        ) : null}

        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Recent Mission Progress</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {missionFeedDeclared && recentDeclaredMissions.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No mission progress has been recorded yet.</div>
          ) : missionFeedDeclared ? (
            recentDeclaredMissions.map((mission) => {
              const missionCurrentTask = mission.current_task;
              const linkedTaskId = missionCurrentTaskId(mission, undefined, undefined, missionCurrentTask);
              const latestActivity = latestActivitySummary(mission.latest_activity);
              const currentTaskStatus =
                safeString(missionCurrentTask?.task_status).trim() || safeString(missionCurrentTask?.operation_status).trim();
              const currentTaskResult = safeString(missionCurrentTask?.result_status).trim();
              const currentTaskGate = safeString(missionCurrentTask?.gate).trim();
              const currentTaskNextStep = safeString(missionCurrentTask?.next_step).trim();
              const currentTaskReason = safeString(missionCurrentTask?.reason).trim();
              return (
                <div
                  key={`mission-progress-${mission.id}`}
                  style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>{mission.objective || mission.id}</div>
                    <span style={badgeStyle(mission.status || "unknown")}>{mission.status || "unknown"}</span>
                  </div>
                  {mission.summary ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{mission.summary}</div> : null}
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    next_step=<code>{currentTaskNextStep || mission.next_step || "unset"}</code>
                  </div>
                  {currentTaskStatus || currentTaskResult || mission.last_task_status || mission.last_task_result_status ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      latest_run=<code>{currentTaskStatus || mission.last_task_status || "unknown"}</code>
                      {currentTaskResult || mission.last_task_result_status ? (
                        <>
                          {" / "}result=<code>{currentTaskResult || mission.last_task_result_status}</code>
                        </>
                      ) : null}
                      {currentTaskGate || mission.last_task_gate ? (
                        <>
                          {" / "}gate=<code>{currentTaskGate || mission.last_task_gate}</code>
                        </>
                      ) : null}
                      {linkedTaskId ? (
                        <>
                          {" / "}current_task=<code>{linkedTaskId}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    linked_tasks=<code>{String(mission.linked_task_count ?? mission.linked_task_ids?.length ?? 0)}</code>
                    {" / "}risk=<code>{mission.risk_tier || "unknown"}</code>
                  </div>
                  {latestActivity.name || latestActivity.status || latestActivity.gate || latestActivity.observedAt ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      latest=<code>{latestActivity.name || "activity"}</code>
                      {" / "}status=<code>{latestActivity.status || "unknown"}</code>
                      {latestActivity.gate ? (
                        <>
                          {" / "}gate=<code>{latestActivity.gate}</code>
                        </>
                      ) : null}
                      {latestActivity.observedAt ? (
                        <>
                          {" / "}at=<code>{latestActivity.observedAt}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {currentTaskReason || mission.last_task_reason ? (
                    <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{currentTaskReason || mission.last_task_reason}</div>
                  ) : null}
                  {mission.deadletter_reason ? (
                    <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{mission.deadletter_reason}</div>
                  ) : null}
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                    <button style={buttonStyle} onClick={() => inspectMission(mission.id)}>
                      Inspect mission flow
                    </button>
                    {linkedTaskId ? (
                      <button style={buttonStyle} onClick={() => props.onOpenOperation(linkedTaskId)}>
                        Open linked task
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })
          ) : recentTaskProgress.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No mission progress has been recorded yet.</div>
          ) : (
            recentTaskProgress.map((task) => (
              <div
                key={`mission-progress-${task.id}`}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{task.objective || task.capability || task.id}</div>
                  <span style={badgeStyle(task.status || "unknown")}>{task.status || "unknown"}</span>
                </div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                  capability=<code>{task.capability || "unknown"}</code>
                </div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                  assigned_to=<code>{task.assigned_to || "unassigned"}</code>
                </div>
                {task.status_reason ? <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{task.status_reason}</div> : null}
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                  <button style={buttonStyle} onClick={() => props.onOpenOperation(task.id)}>
                    Open task
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Incident View</div>
          <span style={badgeStyle(activeIncidents > 0 ? "warning" : "clear")}>
            {activeIncidents > 0 ? `${activeIncidents} active` : "clear"}
          </span>
        </div>
        <div style={{ display: "grid", gap: 8, marginTop: 8, maxHeight: 220, overflow: "auto" }}>
          {incidents.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No active incidents derived from local runtime state.</div>
          ) : (
            incidents.map((incident) => {
              const approvalId = safeString(incident.approval_id);
              const taskId = safeString(incident.task_id);
              const evidenceLines = incidentEvidenceSummary(incident);
              const observedAt = mixedLocaleTime(incident.observed_at);
              return (
                <div
                  key={incident.id}
                  style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>{incident.title || incident.id}</div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {incident.severity ? <span style={badgeStyle(incident.severity)}>{incident.severity}</span> : null}
                      {incident.category ? <span style={badgeStyle(incident.category)}>{incident.category}</span> : null}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                    {incident.detail || "Incident detail unavailable."}
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    source=<code>{incident.source || "unknown"}</code>
                    {incident.probe ? (
                      <>
                        {" / "}probe=<code>{incident.probe}</code>
                      </>
                    ) : null}
                    {typeof incident.count === "number" ? ` / count=${String(incident.count)}` : ""}
                    {observedAt ? (
                      <>
                        {" / "}at=<code>{observedAt}</code>
                      </>
                    ) : null}
                  </div>
                  {evidenceLines.length > 0 ? (
                    <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
                      {evidenceLines.map((line) => (
                        <div key={`${incident.id}:${line}`} style={{ fontSize: 11, color: THEME.muted }}>
                          evidence <code>{line}</code>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
                    {approvalId ? (
                      <button
                        style={buttonStyle}
                        onClick={() =>
                          props.onOpenApprovals(approvalId, {
                            operationId: taskId || undefined,
                          })
                        }
                      >
                        Review approval
                      </button>
                    ) : null}
                    {taskId ? (
                      <button style={buttonStyle} onClick={() => props.onOpenOperation(taskId)}>
                        Open task
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Canonical Flow</div>
          <div style={{ fontSize: 11, color: THEME.muted }}>
            plane_map {orbModel?.plane_map_version ? `v${String(orbModel.plane_map_version)}` : "unknown"} / taxonomy{" "}
            {orbModel?.action_taxonomy_version ? `v${String(orbModel.action_taxonomy_version)}` : "unknown"}
          </div>
        </div>
        {coreLoop.length === 0 ? (
          <div style={{ fontSize: 12, color: THEME.muted, marginTop: 8 }}>ORB model data not loaded.</div>
        ) : (
          <>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
              {coreLoop.map((plane) => (
                <span key={plane.id} style={badgeStyle(plane.id)}>
                  {plane.name || plane.id}
                </span>
              ))}
            </div>
            <div style={{ display: "grid", gap: 8, marginTop: 10, maxHeight: 180, overflow: "auto" }}>
              {coreLoop.map((plane) => (
                <div
                  key={`plane-${plane.id}`}
                  style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>{plane.name || plane.id}</div>
                    <span style={badgeStyle(plane.default_risk_class || "unknown")}>
                      {plane.default_risk_class || "unknown"}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                    <code>{plane.id}</code> / {plane.category || "uncategorized"}
                  </div>
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    side effects <code>{plane.side_effects_allowed ? "allowed" : "blocked"}</code>
                  </div>
                  {plane.purpose ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{plane.purpose}</div>
                  ) : null}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Gate Stack</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {gateStack.length === 0 ? (
            <span style={{ fontSize: 12, color: THEME.muted }}>No gate metadata loaded.</span>
          ) : (
            gateStack.slice(0, 5).map((gate) => (
              <div
                key={gate.id}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: "8px 10px", background: "#121212" }}
              >
                <div style={{ fontSize: 11, fontWeight: 600 }}>{gate.id}</div>
                {gate.description ? (
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4, maxWidth: 220 }}>{gate.description}</div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Forbidden Shortcuts</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {forbiddenTransitions.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No forbidden transitions loaded.</div>
          ) : (
            forbiddenTransitions.slice(0, 4).map((transition) => (
              <div
                key={`${transition.from}-${transition.to}`}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
              >
                <div style={{ fontSize: 12, fontWeight: 600 }}>
                  <code>{transition.from}</code> to <code>{transition.to}</code>
                </div>
                {transition.reason ? (
                  <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 6 }}>{transition.reason}</div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Runtime</div>
        <div style={{ display: "grid", gap: 6, marginTop: 8, fontSize: 12 }}>
          <div>
            Environment: <code>{info?.env_profile || "unknown"}</code> / mode <code>{info?.run_mode || "unknown"}</code>
          </div>
          <div>
            Service: <code>{info?.service || "francis-api"}</code> / version <code>{info?.version || "unknown"}</code>
          </div>
          <div>
            Host: <code>{info?.host || "unknown"}</code> / pid <code>{String(info?.pid ?? "unknown")}</code>
          </div>
          <div>
            Repo: <code>{worldState?.repo_root || "unknown"}</code>
          </div>
          <div>
            Data: <code>{worldState?.data_dir || "unknown"}</code>
          </div>
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Services</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {serviceItems.length === 0 ? (
            <span style={{ fontSize: 12, color: THEME.muted }}>No service data loaded.</span>
          ) : (
            serviceItems.map((item, index) => {
              const name = safeString(item.name, `service-${index}`);
              const status = safeString(item.status, "unknown");
              return (
                <div key={`${name}-${index}`} style={{ ...badgeStyle(status), maxWidth: "100%" }}>
                  <span>{name}</span>
                  <span style={{ color: THEME.muted }}>{status}</span>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Pending Approvals</div>
          <button style={buttonStyle} onClick={() => props.onOpenApprovals()}>
            Open approvals
          </button>
        </div>
        <div style={{ display: "grid", gap: 8, marginTop: 8, maxHeight: 160, overflow: "auto" }}>
          {pendingApprovals.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No pending approvals.</div>
          ) : (
            pendingApprovals.map((item) => (
              (() => {
                const detail = approvalProjectionDetail(item);
                const exactAction = approvalProjectionExactActionLine(item);
                const loopLine = approvalProjectionLoopLine(item);
                const planLine = approvalProjectionPlanLine(item);
                const lineage = approvalProjectionLineage(item);
                const replacement = approvalProjectionReplacementLine(item);
                const reason = safeString(item.reason).trim();
                return (
                  <div
                    key={item.id}
                    style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{approvalProjectionTitle(item)}</div>
                      <span style={badgeStyle(item.status || "pending")}>{item.status || "pending"}</span>
                    </div>
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{detail}</div>
                    {reason && reason !== detail ? (
                      <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{reason}</div>
                    ) : null}
                    {exactAction ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>exact action: {exactAction}</div>
                    ) : null}
                    {loopLine ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>loop: {loopLine}</div>
                    ) : null}
                    {planLine ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>plan: {planLine}</div>
                    ) : null}
                    {lineage ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>lineage: {lineage}</div>
                    ) : null}
                    {replacement ? (
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>replacement: {replacement}</div>
                    ) : null}
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      <code>{item.id}</code>
                    </div>
                    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                      <button style={buttonStyle} onClick={() => props.onOpenApprovals(item.id)}>
                        Review
                      </button>
                    </div>
                  </div>
                );
              })()
            ))
          )}
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Recent Tasks</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8, maxHeight: 220, overflow: "auto" }}>
          {recentTasks.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No recent tasks found.</div>
          ) : (
            recentTasks.map((task) => (
              <div
                key={task.id}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{task.objective || task.capability || task.id}</div>
                  <span style={badgeStyle(task.status || "unknown")}>{task.status || "unknown"}</span>
                </div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                  capability=<code>{task.capability || "unknown"}</code>
                </div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                  assigned_to=<code>{task.assigned_to || "unassigned"}</code>
                </div>
                {task.status_reason ? (
                  <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{task.status_reason}</div>
                ) : null}
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                  updated {task.updated_at ? task.updated_at : task.created_at || "unknown"}
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                  <button style={buttonStyle} onClick={() => props.onOpenOperation(task.id)}>
                    Open task
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function PluginsPanel(props: { baseUrl: string; onOpenApprovals: (approvalId?: string) => void }) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new PluginBrowserClient(resolvedBaseUrl), [resolvedBaseUrl]);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [plugins, setPlugins] = useState<PluginRef[]>([]);
  const [tools, setTools] = useState<PluginToolRef[]>([]);
  const [promotionReadiness, setPromotionReadiness] = useState<PluginPromotionReadinessItem[]>([]);
  const [forgeProposals, setForgeProposals] = useState<PluginForgeProposal[]>([]);
  const [forgeProposalReviews, setForgeProposalReviews] = useState<PluginForgeProposalReview[]>([]);
  const [proposalDecisionReason, setProposalDecisionReason] = useState("operator reviewed Forge proposal");
  const [selectedPluginId, setSelectedPluginId] = useState("");
  const [selectedToolId, setSelectedToolId] = useState("");
  const [toolDetail, setToolDetail] = useState<PluginToolRef | null>(null);
  const [runInput, setRunInput] = useState("{\"input\": \"hello\"}");
  const [runReason, setRunReason] = useState("requested");
  const [approvalId, setApprovalId] = useState("");
  const [runResponse, setRunResponse] = useState<PluginRunResponse | null>(null);
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPlugin = useMemo(
    () => plugins.find((item) => item.id === selectedPluginId) ?? null,
    [plugins, selectedPluginId],
  );
  const selectedTool = useMemo(
    () => tools.find((item) => item.id === selectedToolId) ?? null,
    [tools, selectedToolId],
  );
  const selectedPromotionReadiness = useMemo(
    () => promotionReadiness.find((item) => item.plugin_id === selectedPluginId) ?? null,
    [promotionReadiness, selectedPluginId],
  );
  const promotionReadinessCounts = useMemo(() => {
    const ready = promotionReadiness.filter((item) => item.ready || item.status === "ready").length;
    const blocked = promotionReadiness.filter((item) => !item.ready && item.status !== "ready").length;
    return { total: promotionReadiness.length, ready, blocked };
  }, [promotionReadiness]);
  const selectedForgeProposal = useMemo(() => {
    const readinessProposalId = selectedPromotionReadiness?.proposal_id ?? "";
    if (readinessProposalId) {
      const linked = forgeProposals.find(
        (proposal) => proposal.proposal_id === readinessProposalId || proposal.id === readinessProposalId,
      );
      if (linked) return linked;
    }
    return forgeProposals.find((proposal) => proposal.plugin_id === selectedPluginId) ?? null;
  }, [forgeProposals, selectedPluginId, selectedPromotionReadiness?.proposal_id]);
  const selectedForgeProposalReviews = useMemo(() => {
    const proposalId = selectedForgeProposal?.proposal_id ?? selectedPromotionReadiness?.proposal_id ?? "";
    if (!proposalId) return [];
    return forgeProposalReviews
      .filter((review) => review.proposal_id === proposalId)
      .sort((a, b) => (b.decided_ts ?? 0) - (a.decided_ts ?? 0));
  }, [forgeProposalReviews, selectedForgeProposal?.proposal_id, selectedPromotionReadiness?.proposal_id]);
  const latestForgeProposalReview = selectedForgeProposalReviews[0] ?? null;
  const selectedForgeProposalStatus = safeString(selectedForgeProposal?.status).trim().toLowerCase();
  const selectedForgeValidationEvidence = useMemo(() => {
    const qualityEvidence = forgeRecord(selectedForgeProposal?.quality_analysis, "evidence");
    const proposalValidation = selectedForgeProposal?.validation;
    const receiptId =
      safeString(selectedPromotionReadiness?.evidence?.validation_receipt_id).trim() ||
      forgeRecordString(proposalValidation, "validation_receipt_id") ||
      forgeRecordString(qualityEvidence, "validation_receipt_id");
    const receiptPath =
      safeString(selectedPromotionReadiness?.evidence?.validation_receipt_path).trim() ||
      forgeRecordString(proposalValidation, "validation_receipt_path") ||
      forgeRecordString(qualityEvidence, "validation_receipt_path");
    return { receiptId, receiptPath };
  }, [selectedForgeProposal?.quality_analysis, selectedForgeProposal?.validation, selectedPromotionReadiness?.evidence]);

  function pluginErrorMessage(err: unknown): string {
    if (err instanceof PluginBrowserApiError) {
      const status = err.status ? `HTTP ${err.status}` : "request failed";
      return `${status}${err.url ? ` (${err.url})` : ""}`;
    }
    if (err instanceof Error) return err.message;
    return "Plugin request failed.";
  }

  function forgeRecordString(record: Record<string, unknown> | undefined, key: string): string {
    return safeString(record?.[key]).trim();
  }

  function forgeRecord(record: Record<string, unknown> | undefined, key: string): Record<string, unknown> | undefined {
    const value = record?.[key];
    return isRecord(value) ? value : undefined;
  }

  function forgeRecordCount(record: Record<string, unknown> | undefined, key: string): number {
    const value = record?.[key];
    if (Array.isArray(value)) return value.length;
    if (isRecord(value)) return Object.keys(value).length;
    return safeString(value).trim() ? 1 : 0;
  }

  const refreshPlugins = useCallback(async () => {
    setLoading(true);
    try {
      const [res, readiness, proposals, proposalReviews] = await Promise.all([
        client.list({ limit: 200 }),
        client.listPromotionReadiness({ limit: 200 }),
        client.listForgeProposals({ limit: 200 }),
        client.listForgeProposalReviews({ limit: 200 }),
      ]);
      const items = res.items ?? [];
      setPlugins(items);
      setPromotionReadiness(readiness.items ?? []);
      setForgeProposals(proposals.items ?? []);
      setForgeProposalReviews(proposalReviews.items ?? []);
      setSelectedPluginId((prev) => {
        if (prev && items.some((item) => item.id === prev)) return prev;
        return items[0]?.id ?? "";
      });
    } finally {
      setLoading(false);
    }
  }, [client]);

  const refreshTools = useCallback(
    async (pluginId: string) => {
      const resolvedPluginId = pluginId.trim();
      if (!resolvedPluginId) {
        setTools([]);
        setSelectedToolId("");
        setToolDetail(null);
        return;
      }
      const res = await client.listTools({ plugin_id: resolvedPluginId, limit: 500 });
      const items = res.items ?? [];
      setTools(items);
      setSelectedToolId((prev) => {
        if (prev && items.some((item) => item.id === prev)) return prev;
        return items[0]?.id ?? "";
      });
    },
    [client],
  );

  const loadToolDetail = useCallback(
    async (toolId: string) => {
      const resolvedToolId = toolId.trim();
      if (!resolvedToolId) {
        setToolDetail(null);
        return;
      }
      const detail = await client.getTool(resolvedToolId);
      setToolDetail(detail.item);
    },
    [client],
  );

  useEffect(() => {
    void (async () => {
      setError(null);
      try {
        await refreshPlugins();
      } catch (err) {
        setError(pluginErrorMessage(err));
      }
    })();
  }, [refreshPlugins]);

  useEffect(() => {
    void (async () => {
      setError(null);
      try {
        await refreshTools(selectedPluginId);
      } catch (err) {
        setError(pluginErrorMessage(err));
      }
    })();
  }, [selectedPluginId, refreshTools]);

  useEffect(() => {
    void (async () => {
      setError(null);
      try {
        await loadToolDetail(selectedToolId);
      } catch (err) {
        setError(pluginErrorMessage(err));
      }
    })();
  }, [selectedToolId, loadToolDetail]);

  useEffect(() => {
    setRunResponse(null);
    setResult("");
  }, [selectedPluginId, selectedToolId]);

  const governanceTone = useMemo(() => {
    const status = safeString(runResponse?.status).trim().toLowerCase();
    if (["blocked", "denied", "error", "failed", "disabled"].includes(status)) return "error";
    if (["pending", "needs_approval"].includes(status)) return "warn";
    return "info";
  }, [runResponse]);

  function parseRunInput(text: string): unknown {
    const trimmed = text.trim();
    if (!trimmed) return "";
    try {
      return JSON.parse(trimmed) as unknown;
    } catch {
      return trimmed;
    }
  }

  async function build() {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    setRunResponse(null);
    setResult("");

    try {
      const res = await fetch(`${resolvedBaseUrl}/plugins/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed, description: description.trim(), actor: "chat_ui.plugins" }),
      });
      if (!res.ok) {
        setError(`HTTP ${res.status}`);
        return;
      }
      const json = (await res.json()) as unknown;
      setResult(JSON.stringify(json, null, 2));
      await refreshPlugins();
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function reloadRegistry() {
    setBusy(true);
    setError(null);
    setRunResponse(null);
    try {
      const res = await client.reload();
      setResult(JSON.stringify(res, null, 2));
      await refreshPlugins();
      await refreshTools(selectedPluginId);
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function exportToolsCsv() {
    setBusy(true);
    setError(null);
    setRunResponse(null);
    try {
      const exportParams: { plugin_id?: string } = {};
      if (selectedPluginId) exportParams.plugin_id = selectedPluginId;
      const blob = await client.exportTools("csv", exportParams);
      const toolScope = selectedPluginId || "all";
      const fileName = `francis-plugin-tools-${toolScope}.csv`;
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(href);
      const preview = await blob.text();
      setResult(preview.slice(0, 4000));
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function runSelectedTool() {
    if (!selectedPluginId) {
      setError("Select a plugin.");
      return;
    }
    const tool = toolDetail ?? selectedTool;
    if (!tool) {
      setError("Select a tool action.");
      return;
    }

    setBusy(true);
    setError(null);
    setRunResponse(null);
    try {
      const req: PluginToolRunRequest = {
        id: tool.id,
        input: parseRunInput(runInput),
      };
      const reason = runReason.trim();
      if (reason) req.reason = reason;
      const approval = approvalId.trim();
      if (approval) req.approval_id = approval;

      const res = await client.runTool(req);
      if (res.approval_id) setApprovalId(res.approval_id);
      setRunResponse(res);
      setResult(JSON.stringify(res, null, 2));
      await refreshPlugins();
      await refreshTools(selectedPluginId);
      if (selectedToolId) await loadToolDetail(selectedToolId);
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function decideSelectedForgeProposal(action: PluginForgeProposalDecisionAction) {
    const proposalId = selectedForgeProposal?.proposal_id ?? selectedPromotionReadiness?.proposal_id ?? "";
    if (!proposalId) {
      setError("Select a Forge proposal.");
      return;
    }

    setBusy(true);
    setError(null);
    setRunResponse(null);
    try {
      const res = await client.decideForgeProposal({
        id: proposalId,
        action,
        reason: proposalDecisionReason.trim() || "operator reviewed Forge proposal",
      });
      setResult(JSON.stringify(res, null, 2));
      await refreshPlugins();
    } catch (err) {
      setError(pluginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Plugins</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>
        Build plugins, inspect tool actions, and run/export tool catalog.
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        <button onClick={() => void refreshPlugins()} disabled={busy || loading} style={buttonStyle}>
          {loading ? "Loading." : "Refresh"}
        </button>
        <button onClick={() => void reloadRegistry()} disabled={busy} style={buttonStyle}>
          {busy ? "Working." : "Reload registry"}
        </button>
        <button onClick={() => void exportToolsCsv()} disabled={busy} style={buttonStyle}>
          {busy ? "Working." : "Export tools CSV"}
        </button>
      </div>

      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Plugin name" style={inputStyle} />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          rows={3}
          style={inputStyle}
        />
        <button onClick={() => void build()} disabled={busy} style={buttonStyle}>
          {busy ? "Building." : "Build plugin"}
        </button>
      </div>

      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <select
          value={selectedPluginId}
          onChange={(e) => setSelectedPluginId(e.target.value)}
          style={{ ...inputStyle, padding: "8px 10px" }}
        >
          <option value="">Select plugin</option>
          {plugins.map((plugin) => (
            <option key={plugin.id} value={plugin.id}>
              {plugin.name} ({plugin.id})
            </option>
          ))}
        </select>

        <select
          value={selectedToolId}
          onChange={(e) => setSelectedToolId(e.target.value)}
          style={{ ...inputStyle, padding: "8px 10px" }}
          disabled={!selectedPluginId}
        >
          <option value="">Select tool action</option>
          {tools.map((tool) => (
            <option key={tool.id} value={tool.id}>
              {tool.action} [{tool.risk_tier || "normal"}]
            </option>
          ))}
        </select>
      </div>

      {selectedPlugin ? (
        <div style={{ marginTop: 10, fontSize: 12, color: THEME.muted }}>
          Plugin: <code>{selectedPlugin.id}</code> / status={selectedPlugin.status ?? "unknown"} / enabled=
          {String(selectedPlugin.enabled ?? false)}
        </div>
      ) : null}

      <div
        style={{
          marginTop: 10,
          border: `1px solid ${THEME.panelBorder}`,
          borderRadius: 8,
          padding: 10,
          background: "#111819",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Forge Promotion Readiness</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span style={badgeStyle("candidate")}>candidates {promotionReadinessCounts.total}</span>
            <span style={badgeStyle(promotionReadinessCounts.ready > 0 ? "ready" : "none")}>
              ready {promotionReadinessCounts.ready}
            </span>
            <span style={badgeStyle(promotionReadinessCounts.blocked > 0 ? "blocked" : "clear")}>
              blocked {promotionReadinessCounts.blocked}
            </span>
          </div>
        </div>

        {promotionReadinessCounts.total === 0 ? (
          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
            No staged Forge promotion candidates returned by the backend.
          </div>
        ) : selectedPromotionReadiness ? (
          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span style={badgeStyle(selectedPromotionReadiness.status)}>{selectedPromotionReadiness.status}</span>
              {selectedPromotionReadiness.proposal_id ? (
                <span style={badgeStyle("proposal")}>proposal {selectedPromotionReadiness.proposal_id}</span>
              ) : null}
              {selectedPromotionReadiness.evidence?.proposal_review_status ? (
                <span style={badgeStyle(selectedPromotionReadiness.evidence.proposal_review_status)}>
                  review {selectedPromotionReadiness.evidence.proposal_review_status}
                </span>
              ) : null}
            </div>
            {selectedPromotionReadiness.missing_requirements.length ? (
              <div style={{ marginTop: 6 }}>
                Missing: <code>{selectedPromotionReadiness.missing_requirements.join(", ")}</code>
              </div>
            ) : (
              <div style={{ marginTop: 6 }}>No missing readiness requirements reported.</div>
            )}
            {selectedPromotionReadiness.evidence?.proposal_review_receipt_id ? (
              <div style={{ marginTop: 4 }}>
                review receipt <code>{selectedPromotionReadiness.evidence.proposal_review_receipt_id}</code>
              </div>
            ) : null}
            {selectedPromotionReadiness.governance?.next_step ? (
              <div style={{ marginTop: 4 }}>
                next step <code>{selectedPromotionReadiness.governance.next_step}</code>
              </div>
            ) : null}
          </div>
        ) : (
          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
            Selected plugin has no staged Forge promotion-readiness record. Candidates:{" "}
            {promotionReadiness.slice(0, 5).map((item, index) => (
              <span key={item.plugin_id} style={badgeStyle(item.status)}>
                {index > 0 ? " " : ""}
                {item.plugin?.name || item.plugin_id}
              </span>
            ))}
          </div>
        )}

        {selectedForgeProposal ? (
          <div
            style={{
              marginTop: 10,
              borderTop: `1px solid ${THEME.panelBorder}`,
              paddingTop: 10,
              fontSize: 11,
              color: THEME.muted,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: THEME.text }}>Proposal Evidence</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <span style={badgeStyle(selectedForgeProposal.status || "proposal")}>
                  {selectedForgeProposal.status || "proposal"}
                </span>
                {forgeRecordString(selectedForgeProposal.quality_requirements, "risk_tier") ? (
                  <span style={badgeStyle(forgeRecordString(selectedForgeProposal.quality_requirements, "risk_tier"))}>
                    risk {forgeRecordString(selectedForgeProposal.quality_requirements, "risk_tier")}
                  </span>
                ) : null}
                {latestForgeProposalReview?.status ? (
                  <span style={badgeStyle(latestForgeProposalReview.status)}>review {latestForgeProposalReview.status}</span>
                ) : null}
                {selectedForgeValidationEvidence.receiptId ? (
                  <span style={badgeStyle("validation")}>validation receipt</span>
                ) : null}
              </div>
            </div>
            <div style={{ marginTop: 6 }}>
              proposal <code>{selectedForgeProposal.proposal_id}</code>
              {selectedForgeProposal.relative_path ? (
                <>
                  {" "}
                  / artifact <code>{selectedForgeProposal.relative_path}</code>
                </>
              ) : null}
            </div>
            {selectedForgeValidationEvidence.receiptId || selectedForgeValidationEvidence.receiptPath ? (
              <div style={{ marginTop: 4 }}>
                validation receipt{" "}
                {selectedForgeValidationEvidence.receiptId ? (
                  <code>{selectedForgeValidationEvidence.receiptId}</code>
                ) : (
                  <code>unreported</code>
                )}
                {selectedForgeValidationEvidence.receiptPath ? (
                  <>
                    {" "}
                    / artifact <code>{selectedForgeValidationEvidence.receiptPath}</code>
                  </>
                ) : null}
              </div>
            ) : (
              <div style={{ marginTop: 4 }}>No validation receipt returned for this proposal.</div>
            )}
            {forgeRecordString(selectedForgeProposal.friction, "summary") ? (
              <div style={{ marginTop: 4 }}>
                friction <code>{forgeRecordString(selectedForgeProposal.friction, "summary")}</code>
              </div>
            ) : null}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6 }}>
              <span style={badgeStyle("evidence")}>
                evidence {forgeRecordCount(selectedForgeProposal.friction, "evidence")}
              </span>
              <span style={badgeStyle("tests")}>
                tests {forgeRecordCount(selectedForgeProposal.quality_requirements, "tests")}
              </span>
              <span style={badgeStyle("docs")}>
                docs {forgeRecordCount(selectedForgeProposal.quality_requirements, "docs")}
              </span>
            </div>
            {latestForgeProposalReview ? (
              <div style={{ marginTop: 6 }}>
                latest review <code>{latestForgeProposalReview.receipt_id}</code>
                {latestForgeProposalReview.decision ? <> / decision <code>{latestForgeProposalReview.decision}</code></> : null}
                {latestForgeProposalReview.previous_status ? (
                  <> / from <code>{latestForgeProposalReview.previous_status}</code></>
                ) : null}
              </div>
            ) : (
              <div style={{ marginTop: 6 }}>No proposal review receipt returned for this proposal.</div>
            )}
            <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
              <input
                value={proposalDecisionReason}
                onChange={(e) => setProposalDecisionReason(e.target.value)}
                placeholder="Proposal decision reason"
                style={inputStyle}
              />
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  style={buttonStyle}
                  disabled={busy || selectedForgeProposalStatus === "approved"}
                  onClick={() => void decideSelectedForgeProposal("approve")}
                >
                  Approve proposal
                </button>
                <button
                  style={buttonStyle}
                  disabled={busy || selectedForgeProposalStatus === "needs_revision"}
                  onClick={() => void decideSelectedForgeProposal("request_changes")}
                >
                  Request changes
                </button>
                <button
                  style={buttonStyle}
                  disabled={busy || selectedForgeProposalStatus === "rejected"}
                  onClick={() => void decideSelectedForgeProposal("reject")}
                >
                  Reject proposal
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 10 }}>
            No linked Forge proposal artifact returned for the selected plugin.
          </div>
        )}
      </div>

      {toolDetail ? (
        <div style={{ marginTop: 8, fontSize: 12, color: THEME.muted }}>
          Tool: <code>{toolDetail.id}</code> / action=<code>{toolDetail.action}</code> / risk=
          {toolDetail.risk_tier ?? "normal"} / required_trust=
          {String(toolDetail.required_trust ?? 0)} / approvals_required=
          {String(toolDetail.approvals_required ?? false)}
        </div>
      ) : null}

      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <textarea
          value={runInput}
          onChange={(e) => setRunInput(e.target.value)}
          placeholder="Tool input JSON or plain text"
          rows={3}
          style={inputStyle}
        />
        <input
          value={runReason}
          onChange={(e) => setRunReason(e.target.value)}
          placeholder="Run reason (audit)"
          style={inputStyle}
        />
        <input
          value={approvalId}
          onChange={(e) => setApprovalId(e.target.value)}
          placeholder="Approval id (optional, for gated actions)"
          style={inputStyle}
        />
        <button onClick={() => void runSelectedTool()} disabled={busy || !selectedPluginId || !selectedToolId} style={buttonStyle}>
          {busy ? "Running." : "Run selected action"}
        </button>
      </div>

      {runResponse ? (
        <div
          style={{
            marginTop: 12,
            border: `1px solid ${governanceTone === "error" ? THEME.errorBorder : THEME.panelBorder}`,
            background: governanceTone === "error" ? THEME.errorBg : governanceTone === "warn" ? "#1f1a0b" : "#111819",
            color: governanceTone === "error" ? "#ffaaaa" : governanceTone === "warn" ? "#f4d27a" : "#aee6df",
            borderRadius: 12,
            padding: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Governance Outcome</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span style={badgeStyle(runResponse.status || (runResponse.ok ? "ok" : "error"))}>
                {runResponse.status || (runResponse.ok ? "ok" : "error")}
              </span>
              {runResponse.governance?.gate ? (
                <span style={badgeStyle(runResponse.governance.gate)}>{runResponse.governance.gate}</span>
              ) : null}
            </div>
          </div>
          {runResponse.message ? <div style={{ fontSize: 12, marginTop: 8 }}>{runResponse.message}</div> : null}
          {runResponse.governance?.operator_hint ? (
            <div style={{ fontSize: 12, marginTop: 8 }}>{runResponse.governance.operator_hint}</div>
          ) : null}
          {runResponse.governance?.next_step ? (
            <div style={{ fontSize: 11, marginTop: 8 }}>
              Next step: <code>{runResponse.governance.next_step}</code>
            </div>
          ) : null}
          {(runResponse.governance?.required_trust !== undefined || runResponse.governance?.current_trust !== undefined) ? (
            <div style={{ fontSize: 11, marginTop: 6 }}>
              trust <code>{String(runResponse.governance?.current_trust ?? "unknown")}</code> / required{" "}
              <code>{String(runResponse.governance?.required_trust ?? "unknown")}</code>
            </div>
          ) : null}
          {runResponse.approval_id ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              <div style={{ fontSize: 11 }}>
                approval <code>{runResponse.approval_id}</code>
              </div>
              <button
                style={buttonStyle}
                onClick={() => props.onOpenApprovals(runResponse.approval_id)}
              >
                Open approval
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <div style={{ marginTop: 10, fontSize: 12, color: "#ffaaaa" }}>
          <b>Error:</b> {error}
        </div>
      ) : null}

      {result ? <pre style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>{result}</pre> : null}
    </section>
  );
}

function OperationsPanel(props: {
  baseUrl: string;
  focusOperationId?: string;
  operatorMode: OperatorModeSnapshot | null;
  onOpenApprovals: (approvalId?: string, returnContext?: ApprovalReturnContext) => void;
  onOpenMission: (missionId: string) => void;
  onOpenContinuityLedger: () => void;
}) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new OperationsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const missionsClient = useMemo(() => new MissionsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const memoryTimelineClient = useMemo(() => new MemoryTimelineClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const explanationClient = useMemo(() => new ExplanationClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const [items, setItems] = useState<OperationRecord[]>([]);
  const [selectedOperationId, setSelectedOperationId] = useState("");
  const [detail, setDetail] = useState<OperationDetail | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState<"" | "run" | "cancel">("");
  const [actionNotice, setActionNotice] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [workerCycleBusy, setWorkerCycleBusy] = useState(false);
  const [workerCycleNotice, setWorkerCycleNotice] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [selectedMissionDetail, setSelectedMissionDetail] = useState<MissionDetail | null>(null);
  const [selectedMissionDetailBusy, setSelectedMissionDetailBusy] = useState(false);
  const [selectedMissionDetailError, setSelectedMissionDetailError] = useState<string | null>(null);
  const [selectedMemoryEvidence, setSelectedMemoryEvidence] = useState<MemoryTimelineEvent[]>([]);
  const [selectedMemoryEvidenceBusy, setSelectedMemoryEvidenceBusy] = useState(false);
  const [selectedMemoryEvidenceError, setSelectedMemoryEvidenceError] = useState<string | null>(null);
  const [selectedMemoryEvidenceLoadedAt, setSelectedMemoryEvidenceLoadedAt] = useState<number | null>(null);
  const [selectedExplanationEvidence, setSelectedExplanationEvidence] = useState<ExplanationRecord[]>([]);
  const [selectedExplanationEvidenceBusy, setSelectedExplanationEvidenceBusy] = useState(false);
  const [selectedExplanationEvidenceError, setSelectedExplanationEvidenceError] = useState<string | null>(null);
  const [selectedExplanationEvidenceLoadedAt, setSelectedExplanationEvidenceLoadedAt] = useState<number | null>(null);
  const [composerObjective, setComposerObjective] = useState("Create a governed plan for the current operator objective");
  const [composerReason, setComposerReason] = useState("operator_requested");
  const [composerAction, setComposerAction] = useState("plan.create");
  const [composerInputText, setComposerInputText] = useState('{\n  "goal": "Capture the next governed plan step"\n}');
  const [composerDomain, setComposerDomain] = useState("");
  const [composerMissionSummary, setComposerMissionSummary] = useState("Declared from the operations console so the ORB can carry the work across queue, governance, execution, and continuity.");
  const [composerMissionNextStep, setComposerMissionNextStep] = useState("Inspect the created task, satisfy any approval gate, and run the first bounded execution step.");
  const [composerMissionOwner, setComposerMissionOwner] = useState("chat_ui.operations");
  const [composerMissionDependencies, setComposerMissionDependencies] = useState("");
  const [composerMissionEscalation, setComposerMissionEscalation] = useState("Review in the ORB mission inspector, then deadletter or adjust scope if the blocker cannot be cleared.");
  const [composerCreateMission, setComposerCreateMission] = useState(true);
  const [composerPriority, setComposerPriority] = useState("5");
  const [composerRiskTier, setComposerRiskTier] = useState("medium");
  const [composerBusy, setComposerBusy] = useState<"" | "create" | "create_run">("");
  const [composerNotice, setComposerNotice] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [composerResult, setComposerResult] = useState<{ missionId?: string; operationId?: string; approvalId?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const operationsError = useCallback((err: unknown): string => {
    if (err instanceof OperationsApiError) {
      return `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`;
    }
    if (err instanceof Error) return err.message;
    return "Operations request failed.";
  }, []);

  const upsertOperation = useCallback((operation: OperationRecord) => {
    setItems((prev) => {
      const index = prev.findIndex((item) => item.id === operation.id);
      if (index === -1) return [operation, ...prev];
      const next = [...prev];
      next[index] = operation;
      return next;
    });
  }, []);

  const loadDetail = useCallback(
    async (operationId: string) => {
      if (!operationId) {
        setDetail(null);
        return null;
      }
      setDetailBusy(true);
      setError(null);
      try {
        const nextDetail = await client.get(operationId);
        setDetail(nextDetail);
        if (nextDetail?.operation) upsertOperation(nextDetail.operation);
        return nextDetail;
      } catch (err) {
        setDetail(null);
        setError(operationsError(err));
        return null;
      } finally {
        setDetailBusy(false);
      }
    },
    [client, operationsError, upsertOperation],
  );

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await client.list({
        limit: 50,
        status: statusFilter === "all" ? undefined : statusFilter,
      });
      const nextItems = response.items ?? [];
      setItems(nextItems);
      setSelectedOperationId((prev) => {
        if (props.focusOperationId) return props.focusOperationId;
        if (prev && nextItems.some((item) => item.id === prev)) return prev;
        return nextItems[0]?.id ?? "";
      });
    } catch (err) {
      setError(operationsError(err));
    } finally {
      setBusy(false);
    }
  }, [client, operationsError, props.focusOperationId, statusFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!props.focusOperationId) return;
    setSelectedOperationId(props.focusOperationId);
  }, [props.focusOperationId]);

  useEffect(() => {
    setActionNotice(null);
  }, [selectedOperationId]);

  const operatorEnvironment = props.operatorMode?.environment;
  const composerBlockedReason = executionBlockedReason(props.operatorMode, "declaring governed work");
  const canCreateComposedRequest = composerBlockedReason.length === 0;
  const runSelectedBlockedReason = executionBlockedReason(props.operatorMode, "running queued work");
  const workerProfile = safeString(operatorEnvironment?.id).trim();
  const workerRunMode = safeString(operatorEnvironment?.run_mode).trim();
  const workerCycleBlockedReason =
    executionBlockedReason(props.operatorMode, "running a worker cycle") ||
    (!workerProfile || !workerRunMode
      ? "Worker cycle remains disabled until operator environment posture is loaded."
      : "");
  const canRunWorkerCycle = workerCycleBlockedReason.length === 0;

  useEffect(() => {
    void loadDetail(selectedOperationId);
  }, [loadDetail, selectedOperationId]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const item of items) {
      const key = safeString(item.status, "unknown") || "unknown";
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  }, [items]);

  const selectedOperation =
    detail?.operation ?? items.find((item) => item.id === selectedOperationId) ?? null;
  const selectedStatus = safeString(selectedOperation?.status).trim().toLowerCase();
  const selectedMeta = isRecord(selectedOperation?.meta) ? selectedOperation.meta : {};
  const selectedOutput = isRecord(selectedOperation?.output) ? selectedOperation.output : {};
  const selectedPlanSummary = selectedOperation?.plan_summary;
  const selectedPlanStatus = safeString(selectedPlanSummary?.status).trim();
  const selectedPlanCurrentStepId = safeString(selectedPlanSummary?.current_step_id).trim();
  const selectedPlanCurrentStepTitle = safeString(selectedPlanSummary?.current_step_title).trim();
  const selectedPlanStepCount =
    typeof selectedPlanSummary?.step_count === "number" && Number.isFinite(selectedPlanSummary.step_count)
      ? selectedPlanSummary.step_count
      : undefined;
  const selectedPlanCheckpointCount =
    typeof selectedPlanSummary?.checkpoint_count === "number" && Number.isFinite(selectedPlanSummary.checkpoint_count)
      ? selectedPlanSummary.checkpoint_count
      : undefined;
  const selectedGovernance = isRecord(selectedMeta.governance) ? selectedMeta.governance : {};
  const selectedApprovalId =
    safeString(selectedMeta.approval_id) || safeString(selectedOutput.approval_id) || "";
  const selectedMissionId = operationMissionId(selectedOperation);
  const selectedOrbPlane = safeString(selectedMeta.orb_plane);
  const selectedResultMessage = safeString(selectedMeta.result_message);
  const selectedTraceId = operationTraceId(selectedOperation);
  const selectedRunId = operationRunId(selectedOperation);
  const selectedArtifactDir = operationArtifactDir(selectedOperation);
  const selectedErrorText =
    selectedOperation?.error !== undefined
      ? safeString(selectedOperation.error, JSON.stringify(selectedOperation.error))
      : "";
  const selectedRecoveryGuidance = operationRecoveryGuidance(selectedOperation);
  const showSelectedRecoveryGuidance =
    selectedRecoveryGuidance.length > 0 &&
    (selectedErrorText.length > 0 || ["blocked", "denied", "error", "failed"].includes(selectedStatus));
  const selectedMissionBridgeDetail =
    selectedMissionDetail?.mission?.id === selectedMissionId ? selectedMissionDetail : null;
  const selectedMissionLoopState = selectedMissionBridgeDetail?.loop_state;
  const selectedMissionLoopHandoff = selectedMissionLoopState?.handoff;
  const selectedMissionReceiptSummary = selectedMissionBridgeDetail?.receipt_summary;
  const selectedMissionCurrentTask = selectedMissionBridgeDetail?.current_task;
  const selectedMissionCurrentTaskId = safeString(selectedMissionCurrentTask?.operation_id).trim();
  const selectedMissionCurrentTaskOperationName = safeString(selectedMissionCurrentTask?.operation_name).trim();
  const selectedMissionCurrentTaskOperationPlane = safeString(selectedMissionCurrentTask?.operation_plane).trim();
  const selectedMissionCurrentTaskAdvanceAction = safeString(selectedMissionCurrentTask?.advance_action).trim();
  const selectedMissionCurrentTaskStatus = safeString(selectedMissionCurrentTask?.operation_status).trim();
  const selectedMissionCurrentTaskResultStatus = safeString(selectedMissionCurrentTask?.result_status).trim();
  const selectedMissionCurrentTaskGate = safeString(selectedMissionCurrentTask?.gate).trim();
  const selectedMissionCurrentTaskNextStep = safeString(selectedMissionCurrentTask?.next_step).trim();
  const selectedMissionCurrentTaskReceiptEvent = safeString(selectedMissionCurrentTask?.latest_receipt_event).trim();
  const selectedMissionCurrentTaskReceiptStatus = safeString(selectedMissionCurrentTask?.latest_receipt_status).trim();
  const selectedMissionCurrentTaskApprovalStatus =
    safeString(selectedMissionCurrentTask?.approval_status).trim() ||
    safeString(selectedMissionLoopHandoff?.approval_status).trim();
  const selectedMissionBridgeApprovalId =
    safeString(selectedMissionCurrentTask?.approval_id).trim() ||
    safeString(selectedMissionLoopHandoff?.approval_id).trim() ||
    safeString(selectedMissionReceiptSummary?.current_approval_id).trim();
  const selectedOperationMemoryReceipt =
    detail?.latest_memory_receipt ??
    operationMemoryReceiptFromMeta(selectedMeta.latest_memory_receipt) ??
    detail?.memory_receipts?.[0];
  const selectedOperationMemoryReceiptRefs = operationMemoryReceiptReferenceLine(selectedOperationMemoryReceipt);
  const selectedOperationMemoryReceiptTaskLine = operationMemoryReceiptCurrentTaskLine(selectedOperationMemoryReceipt);
  const selectedOperationMemoryReceiptAt = mixedLocaleTime(selectedOperationMemoryReceipt?.ts);
  const selectedOperationMemoryReceiptCount =
    detail?.memory_receipt_count ??
    (safeNumber(selectedMeta.memory_receipt_count, 0) ||
      detail?.memory_receipts?.length ||
      (selectedOperationMemoryReceipt ? 1 : 0));
  const selectedOperationReceiptOperationId =
    safeString(selectedOperationMemoryReceipt?.current_task_operation_id).trim() ||
    safeString(selectedOperationMemoryReceipt?.handoff_operation_id).trim() ||
    safeString(selectedOperationMemoryReceipt?.references?.operation_id).trim();
  const selectedOperationReceiptApprovalId =
    safeString(selectedOperationMemoryReceipt?.current_task_approval_id).trim() ||
    safeString(selectedOperationMemoryReceipt?.handoff_approval_id).trim() ||
    safeString(selectedOperationMemoryReceipt?.references?.approval_id).trim();
  const selectedOperationReceiptTraceId =
    safeString(selectedOperationMemoryReceipt?.current_task_trace_id).trim() ||
    safeString(selectedOperationMemoryReceipt?.handoff_trace_id).trim() ||
    safeString(selectedOperationMemoryReceipt?.references?.trace_id).trim();
  const selectedOperationReceiptRunId =
    safeString(selectedOperationMemoryReceipt?.current_task_run_id).trim() ||
    safeString(selectedOperationMemoryReceipt?.handoff_run_id).trim() ||
    safeString(selectedOperationMemoryReceipt?.references?.run_id).trim();
  const selectedOperationReceiptArtifactDir =
    safeString(selectedOperationMemoryReceipt?.current_task_artifact_dir).trim() ||
    safeString(selectedOperationMemoryReceipt?.handoff_artifact_dir).trim() ||
    safeString(selectedOperationMemoryReceipt?.references?.artifact_dir).trim();
  const selectedMissionBridgeTaskId =
    selectedMissionCurrentTaskId ||
    safeString(selectedMissionLoopHandoff?.operation_id).trim() ||
    safeString(selectedMissionReceiptSummary?.current_operation_id).trim();
  const selectedMissionEvidenceReceipt =
    selectedOperationMemoryReceipt ??
    selectedMissionBridgeDetail?.latest_memory_receipt ??
    selectedMissionReceiptSummary?.latest_memory_receipt ??
    selectedMissionLoopState?.memory?.latest_memory_receipt ??
    selectedMissionBridgeDetail?.memory_receipts?.[0];
  const selectedMemoryEvidenceOperationId = selectedOperationReceiptOperationId || selectedMissionBridgeTaskId;
  const selectedMissionMemoryTraceId =
    safeString(selectedMissionCurrentTask?.trace_id).trim() ||
    safeString(selectedMissionLoopHandoff?.trace_id).trim() ||
    safeString(selectedMissionReceiptSummary?.current_trace_id).trim() ||
    selectedOperationReceiptTraceId ||
    selectedTraceId;
  const selectedMemoryEvidenceQueries = useMemo(
    () =>
      buildMemoryEvidenceQueries({
        missionId: selectedMissionId,
        operationId: selectedMemoryEvidenceOperationId,
        approvalId: selectedMissionBridgeApprovalId || selectedOperationReceiptApprovalId || selectedApprovalId,
        fallbackOperationId: selectedOperation?.id,
        operationStatus: [
          selectedMissionCurrentTaskStatus,
          selectedMissionCurrentTaskResultStatus,
          selectedStatus,
        ],
        traceId: selectedMissionMemoryTraceId,
        runId: selectedOperationReceiptRunId || selectedRunId,
        artifactDir: selectedOperationReceiptArtifactDir || selectedArtifactDir,
        receipt: selectedMissionEvidenceReceipt,
      }),
    [
      selectedArtifactDir,
      selectedMissionId,
      selectedMissionCurrentTaskResultStatus,
      selectedMissionCurrentTaskStatus,
      selectedMissionEvidenceReceipt,
      selectedMissionBridgeApprovalId,
      selectedMemoryEvidenceOperationId,
      selectedMissionMemoryTraceId,
      selectedOperationReceiptApprovalId,
      selectedOperationReceiptArtifactDir,
      selectedOperationReceiptRunId,
      selectedOperation?.id,
      selectedApprovalId,
      selectedRunId,
      selectedStatus,
    ],
  );
  const selectedMemoryEvidenceQueryKey = memoryEvidenceQueryKey(selectedMemoryEvidenceQueries);
  const selectedExplanationEvidenceQueries = useMemo(
    () =>
      buildExplanationEvidenceQueries({
        missionId: selectedMissionId,
        operationId: selectedMemoryEvidenceOperationId,
        approvalId: selectedMissionBridgeApprovalId || selectedOperationReceiptApprovalId || selectedApprovalId,
        traceId: selectedMissionMemoryTraceId,
        runId: selectedOperationReceiptRunId || selectedRunId,
        artifactDir: selectedOperationReceiptArtifactDir || selectedArtifactDir,
        receipt: selectedMissionEvidenceReceipt,
      }),
    [
      selectedArtifactDir,
      selectedApprovalId,
      selectedMemoryEvidenceOperationId,
      selectedMissionEvidenceReceipt,
      selectedMissionBridgeApprovalId,
      selectedMissionId,
      selectedMissionMemoryTraceId,
      selectedOperationReceiptApprovalId,
      selectedOperationReceiptArtifactDir,
      selectedOperationReceiptRunId,
      selectedRunId,
    ],
  );
  const selectedExplanationEvidenceQueryKey = explanationEvidenceQueryKey(selectedExplanationEvidenceQueries);
  const selectedMissionLoopStages = [
    { key: "plan", label: "Plan", stage: selectedMissionLoopState?.plan },
    { key: "gate", label: "Gate", stage: selectedMissionLoopState?.gate },
    { key: "execute", label: "Execute", stage: selectedMissionLoopState?.execute },
    { key: "trace", label: "Trace", stage: selectedMissionLoopState?.trace },
    { key: "memory", label: "Memory", stage: selectedMissionLoopState?.memory },
    { key: "interface", label: "Interface", stage: selectedMissionLoopState?.interface },
  ].filter((item) => item.stage);
  const selectedMissionLatestRunAt = mixedLocaleTime(selectedMissionReceiptSummary?.latest_run_ts);
  const selectedMissionLatestHistoryAt = mixedLocaleTime(selectedMissionReceiptSummary?.latest_history_ts);
  const selectedMissionMemoryReceiptCount =
    selectedMissionBridgeDetail?.memory_receipt_count ??
    selectedMissionReceiptSummary?.memory_receipt_count ??
    selectedMissionLoopState?.memory?.memory_receipt_count ??
    selectedMissionBridgeDetail?.memory_receipts?.length ??
    0;
  const selectedMissionLatestMemoryReceipt = selectedMissionEvidenceReceipt;
  const selectedMissionLatestMemoryReceiptRefs = selectedMissionLatestMemoryReceipt
    ? missionMemoryReceiptReferenceLine(selectedMissionLatestMemoryReceipt)
    : "";
  const selectedMissionLatestMemoryReceiptHandoff = selectedMissionLatestMemoryReceipt
    ? missionMemoryReceiptHandoffLine(selectedMissionLatestMemoryReceipt)
    : "";
  const selectedMissionLatestMemoryReceiptAt = mixedLocaleTime(selectedMissionLatestMemoryReceipt?.ts);
  const selectedReceiptEvidenceAvailable = Boolean(
    selectedTraceId ||
      selectedRunId ||
      selectedArtifactDir ||
      selectedMissionLoopState ||
      selectedMissionReceiptSummary?.run_ledger_count ||
      selectedMissionReceiptSummary?.history_count ||
      selectedMissionMemoryReceiptCount,
  );
  const selectedLogs = Array.isArray(detail?.logs) ? detail.logs : [];
  const hasGovernance =
    Object.keys(selectedGovernance).length > 0 || Boolean(selectedApprovalId) || Boolean(selectedOrbPlane);
  const governanceTone =
    ["blocked", "denied", "failed", "error"].includes(selectedStatus)
      ? "error"
      : ["queued", "pending", "needs_approval"].includes(selectedStatus)
        ? "warn"
        : "info";
  const canRunSelected = (selectedStatus === "queued" || selectedStatus === "blocked") && runSelectedBlockedReason.length === 0;
  const canCancelSelected = selectedStatus === "queued" || selectedStatus === "running" || selectedStatus === "blocked";

  const loadSelectedMissionDetail = useCallback(
    async (missionId: string, opts?: { apply?: () => boolean; showBusy?: boolean }) => {
      const cleaned = safeString(missionId).trim();
      if (!cleaned) {
        setSelectedMissionDetail(null);
        setSelectedMissionDetailError(null);
        setSelectedMissionDetailBusy(false);
        return null;
      }
      const showBusy = opts?.showBusy !== false;
      if (showBusy) setSelectedMissionDetailBusy(true);
      setSelectedMissionDetailError(null);
      try {
        const nextDetail = await missionsClient.get(cleaned, { timeoutMs: 10_000 });
        if (opts?.apply && !opts.apply()) return nextDetail;
        setSelectedMissionDetail(nextDetail);
        setSelectedMissionDetailError(nextDetail.ok ? null : nextDetail.error || "Linked mission detail unavailable.");
        return nextDetail;
      } catch (err) {
        if (opts?.apply && !opts.apply()) return null;
        const msg =
          err instanceof MissionsApiError
            ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
            : err instanceof Error
              ? err.message
              : "Linked mission detail request failed.";
        setSelectedMissionDetail(null);
        setSelectedMissionDetailError(msg);
        return null;
      } finally {
        if (!opts?.apply || opts.apply()) {
          if (showBusy) setSelectedMissionDetailBusy(false);
        }
      }
    },
    [missionsClient],
  );

  useEffect(() => {
    if (!selectedMissionId) {
      setSelectedMissionDetail(null);
      setSelectedMissionDetailError(null);
      setSelectedMissionDetailBusy(false);
      return;
    }

    let cancelled = false;
    void loadSelectedMissionDetail(selectedMissionId, { apply: () => !cancelled });

    return () => {
      cancelled = true;
    };
  }, [loadSelectedMissionDetail, selectedMissionId]);

  useEffect(() => {
    setSelectedMemoryEvidence([]);
    setSelectedMemoryEvidenceError(null);
    setSelectedMemoryEvidenceLoadedAt(null);
  }, [selectedMemoryEvidenceQueryKey]);

  useEffect(() => {
    setSelectedExplanationEvidence([]);
    setSelectedExplanationEvidenceError(null);
    setSelectedExplanationEvidenceLoadedAt(null);
  }, [selectedExplanationEvidenceQueryKey]);

  const loadSelectedMemoryEvidence = useCallback(async () => {
    if (!selectedMemoryEvidenceQueries.length) {
      setSelectedMemoryEvidence([]);
      setSelectedMemoryEvidenceLoadedAt(null);
      setSelectedMemoryEvidenceError("No mission, task, or trace id is available for memory evidence.");
      return;
    }

    setSelectedMemoryEvidenceBusy(true);
    setSelectedMemoryEvidenceError(null);
    try {
      const responses = await Promise.all(
        selectedMemoryEvidenceQueries.map((query) =>
          memoryTimelineClient.list(query.filters, { timeoutMs: 10_000 }),
        ),
      );
      setSelectedMemoryEvidence(mergeMemoryEvidenceResponses(responses, 10));
      setSelectedMemoryEvidenceLoadedAt(nowUnixSeconds());
    } catch (err) {
      const msg =
        err instanceof MemoryTimelineApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
          : err instanceof Error
            ? err.message
            : "Memory timeline request failed.";
      setSelectedMemoryEvidence([]);
      setSelectedMemoryEvidenceLoadedAt(null);
      setSelectedMemoryEvidenceError(msg);
    } finally {
      setSelectedMemoryEvidenceBusy(false);
    }
  }, [memoryTimelineClient, selectedMemoryEvidenceQueries]);

  const loadSelectedExplanationEvidence = useCallback(async () => {
    if (!selectedExplanationEvidenceQueries.length) {
      setSelectedExplanationEvidence([]);
      setSelectedExplanationEvidenceLoadedAt(null);
      setSelectedExplanationEvidenceError("No mission, operation, trace, run, or artifact handle is available for explanation evidence.");
      return;
    }

    setSelectedExplanationEvidenceBusy(true);
    setSelectedExplanationEvidenceError(null);
    try {
      const responses = await Promise.all(
        selectedExplanationEvidenceQueries.map((query) =>
          explanationClient.list({ ...query.filters, timeoutMs: 10_000 }),
        ),
      );
      setSelectedExplanationEvidence(mergeExplanationEvidenceResponses(responses, 10));
      setSelectedExplanationEvidenceLoadedAt(nowUnixSeconds());
    } catch (err) {
      const msg =
        err instanceof ExplanationApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
          : err instanceof Error
            ? err.message
            : "Explanation evidence request failed.";
      setSelectedExplanationEvidence([]);
      setSelectedExplanationEvidenceLoadedAt(null);
      setSelectedExplanationEvidenceError(msg);
    } finally {
      setSelectedExplanationEvidenceBusy(false);
    }
  }, [explanationClient, selectedExplanationEvidenceQueries]);

  const refreshSelectedOperationView = useCallback(async () => {
    await refresh();
    if (!selectedOperationId) return;
    const nextDetail = await loadDetail(selectedOperationId);
    const bridgeMissionId = operationMissionId(nextDetail?.operation) || selectedMissionId;
    if (bridgeMissionId) {
      await loadSelectedMissionDetail(bridgeMissionId, { showBusy: false });
    }
  }, [loadDetail, loadSelectedMissionDetail, refresh, selectedMissionId, selectedOperationId]);

  const runWorkerCycle = useCallback(async () => {
    if (!canRunWorkerCycle) return;
    setWorkerCycleBusy(true);
    setWorkerCycleNotice(null);
    setActionNotice(null);
    setError(null);
    try {
      const response = await client.runOnce({
        queue: "default",
        kind: "default",
        concurrency: 1,
        heartbeat_s: 0.25,
        profile: workerProfile,
        run_mode: workerRunMode,
        log_level: "INFO",
      });
      await refresh();
      if (selectedOperationId) {
        const nextDetail = await loadDetail(selectedOperationId);
        const bridgeMissionId = operationMissionId(nextDetail?.operation) || selectedMissionId;
        if (bridgeMissionId) {
          await loadSelectedMissionDetail(bridgeMissionId, { showBusy: false });
        }
      }
      if (!response.ok) {
        setWorkerCycleNotice({
          tone: "error",
          text:
            operationGovernanceNotice(response.governance) ||
            response.message?.trim() ||
            response.error?.trim() ||
            `Worker cycle exited with code ${String(response.exit_code ?? "unknown")}.`,
        });
        return;
      }
      setWorkerCycleNotice({
        tone: "info",
        text: `Worker cycle completed with exit code ${String(response.exit_code ?? 0)} in ${workerProfile}/${workerRunMode}.`,
      });
    } catch (err) {
      setWorkerCycleNotice({ tone: "error", text: operationsError(err) });
    } finally {
      setWorkerCycleBusy(false);
    }
  }, [
    canRunWorkerCycle,
    client,
    loadDetail,
    loadSelectedMissionDetail,
    operationsError,
    refresh,
    selectedMissionId,
    selectedOperationId,
    workerProfile,
    workerRunMode,
  ]);

  const submitComposedRequest = useCallback(
    async (runImmediately: boolean) => {
      if (!canCreateComposedRequest) return;

      const objective = safeString(composerObjective).trim();
      const action = safeString(composerAction).trim();
      const reason = safeString(composerReason).trim() || "operator_requested";
      const parsedInput = parseJsonObjectInput(composerInputText);
      if (!action) {
        setComposerNotice({ tone: "error", text: "Action is required before Francis can queue governed work." });
        return;
      }
      if (!parsedInput.ok) {
        setComposerNotice({ tone: "error", text: parsedInput.error });
        return;
      }
      if (composerCreateMission && !objective) {
        setComposerNotice({ tone: "error", text: "Mission creation requires an objective so continuity has a truthful anchor." });
        return;
      }

      setComposerBusy(runImmediately ? "create_run" : "create");
      setComposerNotice(null);
      setComposerResult(null);
      setActionNotice(null);
      setWorkerCycleNotice(null);
      setError(null);

      let missionId = "";
      try {
        if (composerCreateMission) {
          const missionResponse = await missionsClient.create({
            objective,
            summary: safeString(composerMissionSummary).trim(),
            next_step: safeString(composerMissionNextStep).trim(),
            requester_id: "chat_ui.operations",
            owner_id: safeString(composerMissionOwner).trim() || "chat_ui.operations",
            priority: Math.max(1, Math.min(9, Number.parseInt(composerPriority, 10) || 5)),
            risk_tier: safeString(composerRiskTier).trim() || "medium",
            dependency_ids: parseDelimitedIds(composerMissionDependencies),
            escalation_path: safeString(composerMissionEscalation).trim(),
          });
          if (!missionResponse.ok || !safeString(missionResponse.mission_id).trim()) {
            setComposerNotice({
              tone: "error",
              text: missionResponse.error || "Mission creation failed before any governed operation was queued.",
            });
            return;
          }
          missionId = safeString(missionResponse.mission_id).trim();
        }

        const createResponse = await client.create({
          action,
          reason,
          domain: safeString(composerDomain).trim() || undefined,
          actor: "chat_ui.operations",
          mission_id: missionId || undefined,
          input: parsedInput.parsed,
          objective: objective || undefined,
          priority: Math.max(1, Math.min(9, Number.parseInt(composerPriority, 10) || 5)),
        });

        const createdOperationId = safeString(createResponse.operation_id).trim();
        if (!createResponse.ok || !createdOperationId) {
          setComposerResult(missionId ? { missionId } : null);
          setComposerNotice({
            tone: "error",
            text:
              operationGovernanceNotice(createResponse.governance) ||
              createResponse.message ||
              "Governed operation creation failed. Any declared mission was preserved and should be inspected before retrying.",
          });
          return;
        }

        let approvalId = safeString(createResponse.approval_id).trim();
        setSelectedOperationId(createdOperationId);
        await refresh();
        const createdDetail = await loadDetail(createdOperationId);
        const createdBridgeMissionId = missionId || operationMissionId(createdDetail?.operation);
        if (createdBridgeMissionId) {
          await loadSelectedMissionDetail(createdBridgeMissionId, { showBusy: false });
        }

        if (runImmediately) {
          const runResponse = await client.run(createdOperationId, { worker_id: "chat_ui.operations" });
          if (runResponse.operation) {
            upsertOperation(runResponse.operation);
          }
          await refresh();
          const nextDetail = await loadDetail(createdOperationId);
          const runBridgeMissionId = missionId || operationMissionId(nextDetail?.operation);
          if (runBridgeMissionId) {
            await loadSelectedMissionDetail(runBridgeMissionId, { showBusy: false });
          }
          const resolvedApprovalId =
            safeString(runResponse.operation?.meta?.approval_id) ||
            safeString(isRecord(runResponse.operation?.output) ? runResponse.operation?.output.approval_id : "") ||
            safeString(isRecord(nextDetail?.operation?.meta) ? nextDetail?.operation?.meta.approval_id : "") ||
            safeString(isRecord(nextDetail?.operation?.output) ? nextDetail?.operation?.output.approval_id : "") ||
            approvalId;
          setComposerResult({
            missionId: missionId || undefined,
            operationId: createdOperationId,
            approvalId: resolvedApprovalId || undefined,
          });
          setComposerNotice({
            tone: runResponse.ok ? "info" : "error",
            text: runResponse.ok
              ? `Governed request queued and advanced. Inspect the created task for execution, governance, trace, and continuity outcomes.`
              : operationGovernanceNotice(runResponse.governance) ||
                runResponse.message ||
                "The task was created, but the first execution step did not complete cleanly.",
          });
          return;
        }

        const resolvedApprovalId =
          safeString(isRecord(createdDetail?.operation?.meta) ? createdDetail?.operation?.meta.approval_id : "") ||
          safeString(isRecord(createdDetail?.operation?.output) ? createdDetail?.operation?.output.approval_id : "") ||
          approvalId;
        setComposerResult({
          missionId: missionId || undefined,
          operationId: createdOperationId,
          approvalId: resolvedApprovalId || undefined,
        });
        setComposerNotice({
          tone: "info",
          text: missionId
            ? "Mission and first governed task were created. Open the mission flow or task detail to continue through governance and execution."
            : "Governed task created. Open the task detail to continue through governance and execution.",
        });
      } catch (err) {
        setComposerResult(missionId ? { missionId } : null);
        setComposerNotice({ tone: "error", text: err instanceof Error ? err.message : "Request creation failed." });
      } finally {
        setComposerBusy("");
      }
    },
    [
      canCreateComposedRequest,
      client,
      composerAction,
      composerCreateMission,
      composerDomain,
      composerInputText,
      composerMissionDependencies,
      composerMissionEscalation,
      composerMissionNextStep,
      composerMissionOwner,
      composerMissionSummary,
      composerObjective,
      composerPriority,
      composerReason,
      composerRiskTier,
      loadDetail,
      loadSelectedMissionDetail,
      missionsClient,
      refresh,
      upsertOperation,
    ],
  );

  const runSelectedOperation = useCallback(async () => {
    if (!selectedOperationId || !canRunSelected) return;
    setActionBusy("run");
    setActionNotice(null);
    setWorkerCycleNotice(null);
    setError(null);
    try {
      const response = await client.run(selectedOperationId, { worker_id: "chat_ui.operations" });
      if (response.operation) upsertOperation(response.operation);
      const nextDetail = await loadDetail(selectedOperationId);
      const nextStatus = safeString(
        nextDetail?.operation.status ?? response.operation?.status ?? response.status,
        "unknown",
      );
      const bridgeMissionId = operationMissionId(nextDetail?.operation) || selectedMissionId;
      if (bridgeMissionId) {
        await loadSelectedMissionDetail(bridgeMissionId, { showBusy: false });
      }
      if (!response.ok) {
        setActionNotice({
          tone: "error",
          text: `Run failed: ${
            operationGovernanceNotice(response.governance) ||
            response.message ||
            `status ${nextStatus}`
          }.`,
        });
        return;
      }
      const memoryReceiptRefs = operationMemoryReceiptReferenceLine(response.memory_receipt);
      const memoryReceiptTaskLine = operationMemoryReceiptCurrentTaskLine(response.memory_receipt);
      const memoryReceiptLine = [memoryReceiptRefs, memoryReceiptTaskLine].filter(Boolean).join(" / ");
      const memoryReceiptText = memoryReceiptLine
        ? ` Memory receipt: ${memoryReceiptLine}.`
        : response.memory_receipt
          ? " Memory receipt recorded."
          : "";
      setActionNotice({
        tone: "info",
        text:
          response.message === "already_terminal"
            ? `Operation is already ${nextStatus}.`
            : `Operation status is now ${nextStatus}.${memoryReceiptText}`,
      });
    } catch (err) {
      setActionNotice({ tone: "error", text: operationsError(err) });
    } finally {
      setActionBusy("");
    }
  }, [
    canRunSelected,
    client,
    loadDetail,
    loadSelectedMissionDetail,
    operationsError,
    selectedMissionId,
    selectedOperationId,
    upsertOperation,
  ]);

  const cancelSelectedOperation = useCallback(async () => {
    if (!selectedOperationId || !canCancelSelected) return;
    setActionBusy("cancel");
    setActionNotice(null);
    setWorkerCycleNotice(null);
    setError(null);
    try {
      const response = await client.cancel(selectedOperationId, { reason: "cancelled_from_chat_ui" });
      const nextDetail = await loadDetail(selectedOperationId);
      const nextStatus = safeString(nextDetail?.operation.status ?? response.status, "unknown");
      const bridgeMissionId = operationMissionId(nextDetail?.operation) || selectedMissionId;
      if (bridgeMissionId) {
        await loadSelectedMissionDetail(bridgeMissionId, { showBusy: false });
      }
      if (!response.ok) {
        setActionNotice({
          tone: "error",
          text: `Cancel failed: ${
            operationGovernanceNotice(response.governance) ||
            response.message ||
            `status ${nextStatus}`
          }.`,
        });
        return;
      }
      setActionNotice({ tone: "info", text: `Operation status is now ${nextStatus}.` });
    } catch (err) {
      setActionNotice({ tone: "error", text: operationsError(err) });
    } finally {
      setActionBusy("");
    }
  }, [canCancelSelected, client, loadDetail, loadSelectedMissionDetail, operationsError, selectedMissionId, selectedOperationId]);

  return (
    <section style={panelStyle}>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Operations</div>
      <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>
        Queued task activity, lifecycle state, and operation detail.
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 10 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <span style={badgeStyle("queued")}>queued {statusCounts.queued ?? 0}</span>
          <span style={badgeStyle("blocked")}>blocked {statusCounts.blocked ?? 0}</span>
          <span style={badgeStyle("running")}>running {statusCounts.running ?? 0}</span>
          <span style={badgeStyle("succeeded")}>succeeded {statusCounts.succeeded ?? 0}</span>
          <span style={badgeStyle("failed")}>failed {statusCounts.failed ?? 0}</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ ...inputStyle, padding: "8px 10px", minWidth: 130 }}
          >
            <option value="all">All statuses</option>
            <option value="queued">Queued</option>
            <option value="blocked">Blocked</option>
            <option value="running">Running</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="canceled">Canceled</option>
          </select>
          <button onClick={() => void refreshSelectedOperationView()} disabled={busy || detailBusy || actionBusy !== "" || workerCycleBusy} style={buttonStyle}>
            {busy ? "Refreshing." : "Refresh"}
          </button>
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Governed Request Composer</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              Declare a mission if needed, queue the first governed operation, and optionally advance it immediately without leaving the operator console.
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span style={badgeStyle(composerCreateMission ? "mission-linked" : "task-only")}>
              {composerCreateMission ? "mission linked" : "task only"}
            </span>
            <span style={badgeStyle(composerAction || "action")}>{composerAction || "action"}</span>
          </div>
        </div>

        <div style={{ fontSize: 11, color: composerBlockedReason ? "#ffcf9d" : THEME.muted, marginTop: 8 }}>
          {composerBlockedReason || "This writes only explicit mission/task state. Governance, approvals, and trace surfaces remain visible after creation."}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8, marginTop: 10 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 11, color: THEME.muted }}>Objective</span>
            <input value={composerObjective} onChange={(e) => setComposerObjective(e.target.value)} style={inputStyle} />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 11, color: THEME.muted }}>Action</span>
            <input value={composerAction} onChange={(e) => setComposerAction(e.target.value)} style={inputStyle} />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 11, color: THEME.muted }}>Reason</span>
            <input value={composerReason} onChange={(e) => setComposerReason(e.target.value)} style={inputStyle} />
          </label>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 11, color: THEME.muted }}>Domain</span>
            <input value={composerDomain} onChange={(e) => setComposerDomain(e.target.value)} placeholder="optional domain scope" style={inputStyle} />
          </label>
        </div>

        <label style={{ display: "grid", gap: 6, marginTop: 8 }}>
          <span style={{ fontSize: 11, color: THEME.muted }}>Input JSON object</span>
          <textarea
            value={composerInputText}
            onChange={(e) => setComposerInputText(e.target.value)}
            rows={6}
            style={{ ...inputStyle, resize: "vertical", fontFamily: "Consolas, monospace", fontSize: 12 }}
          />
        </label>

        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            <input
              type="checkbox"
              checked={composerCreateMission}
              onChange={(e) => setComposerCreateMission(e.target.checked)}
            />
            Declare mission alongside task
          </label>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            Priority
            <input
              value={composerPriority}
              onChange={(e) => setComposerPriority(e.target.value)}
              inputMode="numeric"
              style={{ ...inputStyle, padding: "8px 10px", width: 72 }}
            />
          </label>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            Risk
            <input
              value={composerRiskTier}
              onChange={(e) => setComposerRiskTier(e.target.value)}
              style={{ ...inputStyle, padding: "8px 10px", width: 110 }}
            />
          </label>
        </div>

        {composerCreateMission ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 8, marginTop: 8 }}>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 11, color: THEME.muted }}>Mission summary</span>
              <textarea
                value={composerMissionSummary}
                onChange={(e) => setComposerMissionSummary(e.target.value)}
                rows={3}
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 11, color: THEME.muted }}>Mission next step</span>
              <textarea
                value={composerMissionNextStep}
                onChange={(e) => setComposerMissionNextStep(e.target.value)}
                rows={3}
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 11, color: THEME.muted }}>Owner</span>
              <input
                value={composerMissionOwner}
                onChange={(e) => setComposerMissionOwner(e.target.value)}
                placeholder="chat_ui.operations"
                style={inputStyle}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 11, color: THEME.muted }}>Dependencies</span>
              <textarea
                value={composerMissionDependencies}
                onChange={(e) => setComposerMissionDependencies(e.target.value)}
                rows={3}
                placeholder="one dependency id per line or comma-separated"
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 11, color: THEME.muted }}>Escalation path</span>
              <textarea
                value={composerMissionEscalation}
                onChange={(e) => setComposerMissionEscalation(e.target.value)}
                rows={3}
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </label>
          </div>
        ) : null}

        {composerNotice ? (
          <div
            style={{
              border: `1px solid ${composerNotice.tone === "error" ? THEME.errorBorder : THEME.panelBorder}`,
              background: composerNotice.tone === "error" ? THEME.errorBg : "#111819",
              color: composerNotice.tone === "error" ? "#ffaaaa" : "#aee6df",
              padding: 10,
              borderRadius: 10,
              fontSize: 12,
              marginTop: 10,
            }}
          >
            {composerNotice.text}
          </div>
        ) : null}

        {composerResult ? (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 10 }}>
            {composerResult.missionId ? <span style={badgeStyle("mission")}>mission <code>{composerResult.missionId}</code></span> : null}
            {composerResult.operationId ? <span style={badgeStyle("queued")}>task <code>{composerResult.operationId}</code></span> : null}
            {composerResult.approvalId ? <span style={badgeStyle("needs_approval")}>approval <code>{composerResult.approvalId}</code></span> : null}
            {composerResult.missionId ? (
              <button style={buttonStyle} onClick={() => props.onOpenMission(composerResult.missionId ?? "")}>
                Open mission flow
              </button>
            ) : null}
            {composerResult.operationId ? (
              <button style={buttonStyle} onClick={() => setSelectedOperationId(composerResult.operationId ?? "")}>
                Open task detail
              </button>
            ) : null}
            {composerResult.approvalId ? (
              <button
                style={buttonStyle}
                onClick={() =>
                  props.onOpenApprovals(composerResult.approvalId, {
                    missionId: composerResult.missionId,
                    operationId: composerResult.operationId,
                  })
                }
              >
                Review approval
              </button>
            ) : null}
          </div>
        ) : null}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
          <button
            onClick={() => void submitComposedRequest(false)}
            disabled={!canCreateComposedRequest || composerBusy !== "" || busy || actionBusy !== "" || workerCycleBusy}
            style={buttonStyle}
          >
            {composerBusy === "create" ? "Creating." : "Create request"}
          </button>
          <button
            onClick={() => void submitComposedRequest(true)}
            disabled={!canCreateComposedRequest || composerBusy !== "" || busy || actionBusy !== "" || workerCycleBusy}
            style={buttonStyle}
          >
            {composerBusy === "create_run" ? "Creating + running." : "Create + run now"}
          </button>
        </div>
      </div>

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Worker Cycle</div>
            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
              Run one bounded worker cycle through the existing queue. This preserves the current backend routing and keeps the action explicit in the operator console.
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {workerProfile ? <span style={badgeStyle(workerProfile)}>{workerProfile}</span> : null}
            {workerRunMode ? <span style={badgeStyle(workerRunMode)}>{workerRunMode}</span> : null}
            <span style={badgeStyle("default")}>queue default</span>
            <span style={badgeStyle("default")}>kind default</span>
          </div>
        </div>
        <div style={{ fontSize: 11, color: workerCycleBlockedReason ? "#ffcf9d" : THEME.muted, marginTop: 8 }}>
          {workerCycleBlockedReason || "This cycle uses concurrency 1 and heartbeat 0.25s so the queue advances in a narrow, reviewable step."}
        </div>
        {workerCycleNotice ? (
          <div
            style={{
              border: `1px solid ${workerCycleNotice.tone === "error" ? THEME.errorBorder : THEME.panelBorder}`,
              background: workerCycleNotice.tone === "error" ? THEME.errorBg : "#111819",
              color: workerCycleNotice.tone === "error" ? "#ffaaaa" : "#aee6df",
              padding: 10,
              borderRadius: 10,
              fontSize: 12,
              marginTop: 10,
            }}
          >
            {workerCycleNotice.text}
          </div>
        ) : null}
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}>
          <button
            onClick={() => void runWorkerCycle()}
            disabled={!canRunWorkerCycle || workerCycleBusy || busy || actionBusy !== ""}
            style={buttonStyle}
          >
            {workerCycleBusy ? "Running cycle." : "Run worker cycle"}
          </button>
        </div>
      </div>

      {error ? (
        <div
          style={{
            marginTop: 10,
            padding: 10,
            borderRadius: 10,
            border: `1px solid ${THEME.errorBorder}`,
            background: THEME.errorBg,
            fontSize: 12,
            color: "#ffaaaa",
          }}
        >
          <b>Error:</b> {error}
        </div>
      ) : null}

      <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
        <div style={{ ...summaryCardStyle(), maxHeight: 240, overflow: "auto" }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Recent Operations</div>
          <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
            {items.length === 0 ? (
              <div style={{ fontSize: 12, color: THEME.muted }}>
                {busy ? "Loading operations." : "No operations found."}
              </div>
            ) : (
              items.map((item) => {
                const selected = item.id === selectedOperationId;
                const objective = operationMetaString(item, "objective");
                const assignedTo = operationMetaString(item, "assigned_to");
                return (
                  <button
                    key={item.id}
                    onClick={() => setSelectedOperationId(item.id)}
                    style={{
                      ...buttonStyle,
                      textAlign: "left",
                      padding: 10,
                      border: selected ? `1px solid ${THEME.text}` : `1px solid ${THEME.panelBorder}`,
                      background: selected ? THEME.buttonActive : "#121212",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{objective || item.name || item.id}</div>
                      <span style={badgeStyle(item.status || "unknown")}>{item.status || "unknown"}</span>
                    </div>
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                      <code>{item.id}</code>
                    </div>
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      actor=<code>{item.actor || "unknown"}</code>
                      {" / "}
                      assigned_to=<code>{assignedTo || "unassigned"}</code>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        <div style={summaryCardStyle()}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Operation Detail</div>
          {!selectedOperation ? (
            <div style={{ marginTop: 8, fontSize: 12, color: THEME.muted }}>
              {detailBusy ? "Loading detail." : "Select an operation to inspect."}
            </div>
          ) : (
            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 600 }}>
                  {operationMetaString(selectedOperation, "objective") || selectedOperation.name || selectedOperation.id}
                </div>
                <span style={badgeStyle(selectedOperation.status || "unknown")}>
                  {selectedOperation.status || "unknown"}
                </span>
              </div>
              <div style={{ fontSize: 11, color: THEME.muted }}>
                <code>{selectedOperation.id}</code>
              </div>
              <div style={{ fontSize: 12 }}>
                Capability: <code>{selectedOperation.name || "unknown"}</code>
              </div>
              <div style={{ fontSize: 12 }}>
                Actor: <code>{selectedOperation.actor || "unknown"}</code>
              </div>
              <div style={{ fontSize: 12 }}>
                Updated: <code>{toLocaleTime(selectedOperation.ts)}</code>
              </div>
              <div style={{ fontSize: 12 }}>
                Assigned to: <code>{operationMetaString(selectedOperation, "assigned_to", "unassigned")}</code>
              </div>
              {selectedMissionId ? (
                <div style={{ fontSize: 12 }}>
                  Mission: <code>{selectedMissionId}</code>
                </div>
              ) : null}
              {selectedTraceId ? (
                <div style={{ fontSize: 12 }}>
                  Trace: <code>{selectedTraceId}</code>
                </div>
              ) : null}
              {selectedRunId ? (
                <div style={{ fontSize: 12 }}>
                  Run: <code>{selectedRunId}</code>
                </div>
              ) : null}
              {selectedArtifactDir ? (
                <div style={{ fontSize: 12 }}>
                  Artifact: <code>{selectedArtifactDir}</code>
                </div>
              ) : null}
              <div style={{ fontSize: 12 }}>
                Attempts: <code>{String(safeNumber(isRecord(selectedOperation.meta) ? selectedOperation.meta.attempts : 0, 0))}</code>
              </div>
              {(selectedOperationMemoryReceiptCount || selectedOperationMemoryReceipt) ? (
                <div style={{ fontSize: 12, overflowWrap: "anywhere" }}>
                  Operation memory receipts: <code>{String(selectedOperationMemoryReceiptCount)}</code>
                  {selectedOperationMemoryReceipt?.operation_status ? (
                    <>
                      {" / "}status <code>{selectedOperationMemoryReceipt.operation_status}</code>
                    </>
                  ) : null}
                  {selectedOperationMemoryReceiptAt ? (
                    <>
                      {" / "}at <code>{selectedOperationMemoryReceiptAt}</code>
                    </>
                  ) : null}
                  {selectedOperationMemoryReceiptRefs ? <>{" / "}{selectedOperationMemoryReceiptRefs}</> : null}
                  {selectedOperationMemoryReceiptTaskLine ? <>{" / "}{selectedOperationMemoryReceiptTaskLine}</> : null}
                </div>
              ) : null}
              {selectedPlanSummary ? (
                <div style={{ fontSize: 12, display: "grid", gap: 4, overflowWrap: "anywhere" }}>
                  <div style={{ fontWeight: 600 }}>Plan Receipt</div>
                  {selectedPlanStatus ? (
                    <div>
                      Status: <code>{selectedPlanStatus}</code>
                    </div>
                  ) : null}
                  {(selectedPlanCurrentStepId || selectedPlanCurrentStepTitle) ? (
                    <div>
                      Current step:{" "}
                      {selectedPlanCurrentStepId ? <code>{selectedPlanCurrentStepId}</code> : null}
                      {selectedPlanCurrentStepId && selectedPlanCurrentStepTitle ? " / " : null}
                      {selectedPlanCurrentStepTitle ? <code>{selectedPlanCurrentStepTitle}</code> : null}
                    </div>
                  ) : null}
                  {(selectedPlanStepCount !== undefined || selectedPlanCheckpointCount !== undefined) ? (
                    <div>
                      {selectedPlanStepCount !== undefined ? (
                        <>
                          Steps: <code>{String(selectedPlanStepCount)}</code>
                        </>
                      ) : null}
                      {selectedPlanStepCount !== undefined && selectedPlanCheckpointCount !== undefined ? " / " : null}
                      {selectedPlanCheckpointCount !== undefined ? (
                        <>
                          Checkpoints: <code>{String(selectedPlanCheckpointCount)}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {selectedArtifactDir ? (
                <ArtifactInspectionPanel
                  baseUrl={resolvedBaseUrl}
                  artifactDir={selectedArtifactDir}
                  buttonStyle={buttonStyle}
                  badgeStyle={badgeStyle}
                  borderColor={THEME.panelBorder}
                  mutedColor={THEME.muted}
                />
              ) : null}
              {selectedMissionId ? (
                <div style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#111819" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>Mission Loop Bridge</div>
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                        Read-only loop posture for the mission linked to this operation.
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                      <span style={badgeStyle(selectedMissionLoopState?.active_stage || "mission")}>
                        {selectedMissionLoopState?.active_stage ? `active ${selectedMissionLoopState.active_stage}` : "mission"}
                      </span>
                      {selectedMissionCurrentTaskStatus ? (
                        <span style={badgeStyle(selectedMissionCurrentTaskStatus)}>
                          {selectedMissionCurrentTaskStatus}
                        </span>
                      ) : null}
                      {selectedMissionCurrentTaskApprovalStatus ? (
                        <span style={badgeStyle(selectedMissionCurrentTaskApprovalStatus)}>
                          approval {selectedMissionCurrentTaskApprovalStatus}
                        </span>
                      ) : null}
                      {selectedMissionCurrentTaskResultStatus ? (
                        <span style={badgeStyle(selectedMissionCurrentTaskResultStatus)}>
                          result {selectedMissionCurrentTaskResultStatus}
                        </span>
                      ) : null}
                      <button
                        style={{ ...buttonStyle, padding: "4px 8px", fontSize: 11 }}
                        disabled={selectedMissionDetailBusy}
                        onClick={() => void loadSelectedMissionDetail(selectedMissionId)}
                      >
                        {selectedMissionDetailBusy ? "Refreshing." : "Refresh loop"}
                      </button>
                    </div>
                  </div>
                  {selectedMissionDetailBusy ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>Loading linked mission loop.</div>
                  ) : selectedMissionDetailError ? (
                    <div style={{ fontSize: 11, color: "#ffaaaa", marginTop: 8 }}>
                      Mission loop unavailable: {selectedMissionDetailError}
                    </div>
                  ) : selectedMissionBridgeDetail ? (
                    <>
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                        {selectedMissionLoopState?.summary || "Mission detail is loaded, but no loop summary has been projected yet."}
                      </div>
                      {(selectedMissionCurrentTaskId ||
                        selectedMissionCurrentTaskOperationName ||
                        selectedMissionCurrentTaskOperationPlane ||
                        selectedMissionCurrentTaskAdvanceAction ||
                        selectedMissionCurrentTaskStatus ||
                        selectedMissionCurrentTaskApprovalStatus ||
                        selectedMissionCurrentTaskResultStatus ||
                        selectedMissionCurrentTaskGate ||
                        selectedMissionCurrentTaskNextStep ||
                        selectedMissionCurrentTaskReceiptEvent ||
                        selectedMissionCurrentTaskReceiptStatus) ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                          {selectedMissionCurrentTaskId ? (
                            <>
                              current_task=<code>{selectedMissionCurrentTaskId}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskOperationName ? (
                            <>
                              {selectedMissionCurrentTaskId ? " / " : ""}operation=<code>{selectedMissionCurrentTaskOperationName}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskOperationPlane ? (
                            <>
                              {(selectedMissionCurrentTaskId || selectedMissionCurrentTaskOperationName) ? " / " : ""}
                              plane=<code>{selectedMissionCurrentTaskOperationPlane}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskAdvanceAction ? (
                            <>
                              {(selectedMissionCurrentTaskId ||
                              selectedMissionCurrentTaskOperationName ||
                              selectedMissionCurrentTaskOperationPlane)
                                ? " / "
                                : ""}
                              advance=<code>{selectedMissionCurrentTaskAdvanceAction}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskStatus ? (
                            <>
                              {(selectedMissionCurrentTaskId ||
                              selectedMissionCurrentTaskOperationName ||
                              selectedMissionCurrentTaskOperationPlane ||
                              selectedMissionCurrentTaskAdvanceAction)
                                ? " / "
                                : ""}
                              task_status=<code>{selectedMissionCurrentTaskStatus}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskApprovalStatus ? (
                            <>
                              {(selectedMissionCurrentTaskId ||
                              selectedMissionCurrentTaskOperationName ||
                              selectedMissionCurrentTaskOperationPlane ||
                              selectedMissionCurrentTaskAdvanceAction ||
                              selectedMissionCurrentTaskStatus)
                                ? " / "
                                : ""}
                              approval_status=<code>{selectedMissionCurrentTaskApprovalStatus}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskResultStatus ? (
                            <>
                              {(selectedMissionCurrentTaskId ||
                              selectedMissionCurrentTaskOperationName ||
                              selectedMissionCurrentTaskOperationPlane ||
                              selectedMissionCurrentTaskAdvanceAction ||
                              selectedMissionCurrentTaskStatus ||
                              selectedMissionCurrentTaskApprovalStatus)
                                ? " / "
                                : ""}
                              result=<code>{selectedMissionCurrentTaskResultStatus}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskGate ? (
                            <>
                              {(selectedMissionCurrentTaskId ||
                              selectedMissionCurrentTaskOperationName ||
                              selectedMissionCurrentTaskOperationPlane ||
                              selectedMissionCurrentTaskAdvanceAction ||
                              selectedMissionCurrentTaskStatus ||
                              selectedMissionCurrentTaskApprovalStatus ||
                              selectedMissionCurrentTaskResultStatus)
                                ? " / "
                                : ""}
                              gate=<code>{selectedMissionCurrentTaskGate}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskNextStep ? (
                            <>
                              {(selectedMissionCurrentTaskId ||
                              selectedMissionCurrentTaskOperationName ||
                              selectedMissionCurrentTaskOperationPlane ||
                              selectedMissionCurrentTaskAdvanceAction ||
                              selectedMissionCurrentTaskStatus ||
                              selectedMissionCurrentTaskApprovalStatus ||
                              selectedMissionCurrentTaskResultStatus ||
                              selectedMissionCurrentTaskGate)
                                ? " / "
                                : ""}
                              next=<code>{selectedMissionCurrentTaskNextStep}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskReceiptEvent ? (
                            <>
                              {(selectedMissionCurrentTaskId ||
                              selectedMissionCurrentTaskOperationName ||
                              selectedMissionCurrentTaskOperationPlane ||
                              selectedMissionCurrentTaskAdvanceAction ||
                              selectedMissionCurrentTaskStatus ||
                              selectedMissionCurrentTaskApprovalStatus ||
                              selectedMissionCurrentTaskResultStatus ||
                              selectedMissionCurrentTaskGate ||
                              selectedMissionCurrentTaskNextStep)
                                ? " / "
                                : ""}
                              receipt=<code>{selectedMissionCurrentTaskReceiptEvent}</code>
                            </>
                          ) : null}
                          {selectedMissionCurrentTaskReceiptStatus ? (
                            <>
                              {(selectedMissionCurrentTaskId ||
                              selectedMissionCurrentTaskOperationName ||
                              selectedMissionCurrentTaskOperationPlane ||
                              selectedMissionCurrentTaskAdvanceAction ||
                              selectedMissionCurrentTaskStatus ||
                              selectedMissionCurrentTaskApprovalStatus ||
                              selectedMissionCurrentTaskResultStatus ||
                              selectedMissionCurrentTaskGate ||
                              selectedMissionCurrentTaskNextStep ||
                              selectedMissionCurrentTaskReceiptEvent)
                                ? " / "
                                : ""}
                              receipt_status=<code>{selectedMissionCurrentTaskReceiptStatus}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {(selectedMissionLoopHandoff?.detail ||
                        selectedMissionLoopHandoff?.gate ||
                        selectedMissionLoopHandoff?.next_step ||
                        selectedMissionLoopHandoff?.approval_id ||
                        selectedMissionLoopHandoff?.operation_id ||
                        selectedMissionLoopHandoff?.trace_id ||
                        selectedMissionLoopHandoff?.run_id ||
                        selectedMissionLoopHandoff?.artifact_dir) ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6, overflowWrap: "anywhere" }}>
                          {selectedMissionLoopHandoff?.detail ? <span>{selectedMissionLoopHandoff.detail}</span> : null}
                          {selectedMissionLoopHandoff?.gate ? (
                            <>
                              {selectedMissionLoopHandoff.detail ? " / " : ""}gate <code>{selectedMissionLoopHandoff.gate}</code>
                            </>
                          ) : null}
                          {selectedMissionLoopHandoff?.next_step ? (
                            <>
                              {(selectedMissionLoopHandoff.detail || selectedMissionLoopHandoff.gate) ? " / " : ""}next{" "}
                              <code>{selectedMissionLoopHandoff.next_step}</code>
                            </>
                          ) : null}
                          {selectedMissionLoopHandoff?.approval_id ? (
                            <>
                              {(selectedMissionLoopHandoff.detail ||
                              selectedMissionLoopHandoff.gate ||
                              selectedMissionLoopHandoff.next_step)
                                ? " / "
                                : ""}
                              approval <code>{selectedMissionLoopHandoff.approval_id}</code>
                            </>
                          ) : null}
                          {selectedMissionLoopHandoff?.operation_id ? (
                            <>
                              {(selectedMissionLoopHandoff.detail ||
                              selectedMissionLoopHandoff.gate ||
                              selectedMissionLoopHandoff.next_step ||
                              selectedMissionLoopHandoff.approval_id)
                                ? " / "
                                : ""}
                              task <code>{selectedMissionLoopHandoff.operation_id}</code>
                            </>
                          ) : null}
                          {selectedMissionLoopHandoff?.trace_id ? (
                            <>
                              {(selectedMissionLoopHandoff.detail ||
                              selectedMissionLoopHandoff.gate ||
                              selectedMissionLoopHandoff.next_step ||
                              selectedMissionLoopHandoff.approval_id ||
                              selectedMissionLoopHandoff.operation_id)
                                ? " / "
                                : ""}
                              trace <code>{selectedMissionLoopHandoff.trace_id}</code>
                            </>
                          ) : null}
                          {selectedMissionLoopHandoff?.run_id ? (
                            <>
                              {(selectedMissionLoopHandoff.detail ||
                              selectedMissionLoopHandoff.gate ||
                              selectedMissionLoopHandoff.next_step ||
                              selectedMissionLoopHandoff.approval_id ||
                              selectedMissionLoopHandoff.operation_id ||
                              selectedMissionLoopHandoff.trace_id)
                                ? " / "
                                : ""}
                              run <code>{selectedMissionLoopHandoff.run_id}</code>
                            </>
                          ) : null}
                          {selectedMissionLoopHandoff?.artifact_dir ? (
                            <>
                              {(selectedMissionLoopHandoff.detail ||
                              selectedMissionLoopHandoff.gate ||
                              selectedMissionLoopHandoff.next_step ||
                              selectedMissionLoopHandoff.approval_id ||
                              selectedMissionLoopHandoff.operation_id ||
                              selectedMissionLoopHandoff.trace_id ||
                              selectedMissionLoopHandoff.run_id)
                                ? " / "
                                : ""}
                              artifact{" "}
                              <code title={selectedMissionLoopHandoff.artifact_dir}>
                                {truncateText(selectedMissionLoopHandoff.artifact_dir, 96)}
                              </code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {(selectedMissionBridgeApprovalId ||
                        selectedMissionBridgeTaskId ||
                        selectedMemoryEvidenceQueries.length > 0 ||
                        selectedExplanationEvidenceQueries.length > 0) ? (
                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                          {selectedMissionBridgeApprovalId ? (
                            <button
                              style={buttonStyle}
                              onClick={() =>
                                props.onOpenApprovals(selectedMissionBridgeApprovalId, {
                                  missionId: selectedMissionId,
                                  operationId: selectedMissionBridgeTaskId || undefined,
                                })
                              }
                            >
                              Review bridge approval
                            </button>
                          ) : null}
                          {selectedMissionBridgeTaskId ? (
                            <button style={buttonStyle} onClick={() => props.onOpenOperation(selectedMissionBridgeTaskId)}>
                              {selectedMissionBridgeTaskId === selectedOperation.id ? "Open selected task" : "Open bridge task"}
                            </button>
                          ) : null}
                          {selectedMemoryEvidenceQueries.length > 0 ? (
                            <button
                              style={buttonStyle}
                              disabled={selectedMemoryEvidenceBusy}
                              onClick={() => void loadSelectedMemoryEvidence()}
                            >
                              {selectedMemoryEvidenceBusy ? "Loading memory." : "Load memory evidence"}
                            </button>
                          ) : null}
                          {selectedExplanationEvidenceQueries.length > 0 ? (
                            <button
                              style={buttonStyle}
                              disabled={selectedExplanationEvidenceBusy}
                              onClick={() => void loadSelectedExplanationEvidence()}
                            >
                              {selectedExplanationEvidenceBusy ? "Loading audit." : "Load audit explanations"}
                            </button>
                          ) : null}
                          <button style={buttonStyle} onClick={() => props.onOpenMission(selectedMissionId)}>
                            Open mission flow
                          </button>
                        </div>
                      ) : null}
                      {selectedMissionLoopStages.length > 0 ? (
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8, marginTop: 8 }}>
                          {selectedMissionLoopStages.map((item) => {
                            const stage = item.stage;
                            const stageLatestAt = stage?.latest_ts ? toLocaleTime(stage.latest_ts) : "";
                            const stageMemoryReceipt = stage?.latest_memory_receipt;
                            const stageMemoryReceiptAt = mixedLocaleTime(stageMemoryReceipt?.ts);
                            const stageMemoryReceiptRefs = missionMemoryReceiptReferenceLine(stageMemoryReceipt);
                            const stageMemoryReceiptHandoff = missionMemoryReceiptHandoffLine(stageMemoryReceipt);
                            return (
                              <div
                                key={`selected-operation-loop-${selectedOperation.id}-${item.key}`}
                                style={{
                                  border: `1px solid ${selectedMissionLoopState?.active_stage === item.key ? "#3a5c67" : THEME.panelBorder}`,
                                  borderRadius: 10,
                                  padding: 8,
                                  background: selectedMissionLoopState?.active_stage === item.key ? "#10181b" : "#121212",
                                }}
                              >
                                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                                  <div style={{ fontSize: 11, color: THEME.muted }}>{item.label}</div>
                                  <span style={badgeStyle(stage?.status || "unknown")}>{stage?.status || "unknown"}</span>
                                </div>
                                <div style={{ fontSize: 11, color: THEME.text, marginTop: 6 }}>
                                  {stage?.detail || "No receipt is recorded for this stage yet."}
                                </div>
                                {(stage?.count !== undefined ||
                                  stage?.gate ||
                                  stage?.approval_status ||
                                  stage?.next_step ||
                                  stage?.memory_receipt_count) ? (
                                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                                    {stage?.count !== undefined ? (
                                      <>
                                        count <code>{String(stage.count)}</code>
                                      </>
                                    ) : null}
                                    {stage?.gate ? (
                                      <>
                                        {stage?.count !== undefined ? " / " : ""}gate <code>{stage.gate}</code>
                                      </>
                                    ) : null}
                                    {stage?.approval_status ? (
                                      <>
                                        {(stage?.count !== undefined || stage?.gate) ? " / " : ""}approval_status{" "}
                                        <code>{stage.approval_status}</code>
                                      </>
                                    ) : null}
                                    {stage?.next_step ? (
                                      <>
                                        {(stage?.count !== undefined || stage?.gate || stage?.approval_status) ? " / " : ""}next{" "}
                                        <code>{stage.next_step}</code>
                                      </>
                                    ) : null}
                                    {stage?.memory_receipt_count ? (
                                      <>
                                        {(stage?.count !== undefined || stage?.gate || stage?.approval_status || stage?.next_step)
                                          ? " / "
                                          : ""}
                                        memory_receipts <code>{String(stage.memory_receipt_count)}</code>
                                      </>
                                    ) : null}
                                  </div>
                                ) : null}
                                {(stage?.approval_id ||
                                  stage?.operation_id ||
                                  stage?.trace_id ||
                                  stage?.run_id ||
                                  stage?.artifact_dir ||
                                  stage?.latest_event ||
                                  stage?.latest_receipt_status ||
                                  stageLatestAt) ? (
                                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6, overflowWrap: "anywhere" }}>
                                    {stage?.approval_id ? (
                                      <>
                                        approval <code>{stage.approval_id}</code>
                                      </>
                                    ) : null}
                                    {stage?.operation_id ? (
                                      <>
                                        {stage?.approval_id ? " / " : ""}task <code>{stage.operation_id}</code>
                                      </>
                                    ) : null}
                                    {stage?.trace_id ? (
                                      <>
                                        {(stage?.approval_id || stage?.operation_id) ? " / " : ""}trace <code>{stage.trace_id}</code>
                                      </>
                                    ) : null}
                                    {stage?.run_id ? (
                                      <>
                                        {(stage?.approval_id || stage?.operation_id || stage?.trace_id) ? " / " : ""}run{" "}
                                        <code>{stage.run_id}</code>
                                      </>
                                    ) : null}
                                    {stage?.artifact_dir ? (
                                      <>
                                        {(stage?.approval_id || stage?.operation_id || stage?.trace_id || stage?.run_id)
                                          ? " / "
                                          : ""}
                                        artifact <code title={stage.artifact_dir}>{truncateText(stage.artifact_dir, 96)}</code>
                                      </>
                                    ) : null}
                                    {stage?.latest_event ? (
                                      <>
                                        {(stage?.approval_id ||
                                        stage?.operation_id ||
                                        stage?.trace_id ||
                                        stage?.run_id ||
                                        stage?.artifact_dir)
                                          ? " / "
                                          : ""}
                                        latest{" "}
                                        <code>{stage.latest_event}</code>
                                      </>
                                    ) : null}
                                    {stage?.latest_receipt_status ? (
                                      <>
                                        {(stage?.approval_id ||
                                        stage?.operation_id ||
                                        stage?.trace_id ||
                                        stage?.run_id ||
                                        stage?.artifact_dir ||
                                        stage?.latest_event)
                                          ? " / "
                                          : ""}
                                        receipt_status <code>{stage.latest_receipt_status}</code>
                                      </>
                                    ) : null}
                                    {stageLatestAt ? (
                                      <>
                                        {(stage?.approval_id ||
                                        stage?.operation_id ||
                                        stage?.trace_id ||
                                        stage?.run_id ||
                                        stage?.artifact_dir ||
                                        stage?.latest_event ||
                                        stage?.latest_receipt_status)
                                          ? " / "
                                          : ""}
                                        at{" "}
                                        <code>{stageLatestAt}</code>
                                      </>
                                    ) : null}
                                  </div>
                                ) : null}
                                {stageMemoryReceipt ? (
                                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                                    latest_memory=<code>{missionMemoryReceiptLabel(stageMemoryReceipt)}</code>
                                    {stageMemoryReceipt.operation_status ? (
                                      <>
                                        {" / "}memory_status=<code>{stageMemoryReceipt.operation_status}</code>
                                      </>
                                    ) : null}
                                    {stageMemoryReceiptAt ? (
                                      <>
                                        {" / "}memory_at=<code>{stageMemoryReceiptAt}</code>
                                      </>
                                    ) : null}
                                    {stageMemoryReceiptRefs ? <>{" / "}{stageMemoryReceiptRefs}</> : null}
                                    {stageMemoryReceiptHandoff ? <>{" / "}{stageMemoryReceiptHandoff}</> : null}
                                  </div>
                                ) : null}
                                {missionLoopStagePlanReceiptLine(stage)}
                                {stage?.artifact_dir ? (
                                  <div style={{ marginTop: 8 }}>
                                    <ArtifactInspectionPanel
                                      baseUrl={resolvedBaseUrl}
                                      artifactDir={stage.artifact_dir}
                                      title={`${item.label} Artifact`}
                                      buttonLabel="Inspect stage artifact"
                                      buttonStyle={buttonStyle}
                                      badgeStyle={badgeStyle}
                                      borderColor={THEME.panelBorder}
                                      mutedColor={THEME.muted}
                                      limit={25}
                                      maxEntries={5}
                                    />
                                  </div>
                                ) : null}
                                {(stage?.approval_id || stage?.operation_id) ? (
                                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                                    {stage?.approval_id ? (
                                      <button
                                        style={buttonStyle}
                                        onClick={() =>
                                          props.onOpenApprovals(stage.approval_id || "", {
                                            missionId: selectedMissionId,
                                            operationId: stage.operation_id || selectedMissionBridgeTaskId || undefined,
                                          })
                                        }
                                      >
                                        Review stage approval
                                      </button>
                                    ) : null}
                                    {stage?.operation_id ? (
                                      <button style={buttonStyle} onClick={() => props.onOpenOperation(stage.operation_id || "")}>
                                        {stage.operation_id === selectedOperation.id ? "Open selected task" : "Open stage task"}
                                      </button>
                                    ) : null}
                                  </div>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      ) : null}
                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                        linked_ops=<code>{String(selectedMissionReceiptSummary?.linked_operation_count ?? 0)}</code>
                        {" / "}run_receipts=<code>{String(selectedMissionReceiptSummary?.run_ledger_count ?? 0)}</code>
                        {" / "}history_receipts=<code>{String(selectedMissionReceiptSummary?.history_count ?? 0)}</code>
                        {" / "}memory_receipts=<code>{String(selectedMissionMemoryReceiptCount)}</code>
                      </div>
                      {(selectedMissionReceiptSummary?.latest_run_event ||
                        selectedMissionLatestRunAt ||
                        selectedMissionReceiptSummary?.latest_history_event ||
                        selectedMissionLatestHistoryAt) ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                          {selectedMissionReceiptSummary?.latest_run_event ? (
                            <>
                              latest_run=<code>{selectedMissionReceiptSummary.latest_run_event}</code>
                            </>
                          ) : null}
                          {selectedMissionLatestRunAt ? (
                            <>
                              {selectedMissionReceiptSummary?.latest_run_event ? " / " : ""}run_at=<code>{selectedMissionLatestRunAt}</code>
                            </>
                          ) : null}
                          {selectedMissionReceiptSummary?.latest_history_event ? (
                            <>
                              {(selectedMissionReceiptSummary?.latest_run_event || selectedMissionLatestRunAt) ? " / " : ""}
                              memory=<code>{selectedMissionReceiptSummary.latest_history_event}</code>
                            </>
                          ) : null}
                          {selectedMissionLatestHistoryAt ? (
                            <>
                              {(selectedMissionReceiptSummary?.latest_run_event ||
                              selectedMissionLatestRunAt ||
                              selectedMissionReceiptSummary?.latest_history_event)
                                ? " / "
                                : ""}
                              memory_at=<code>{selectedMissionLatestHistoryAt}</code>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      {selectedMissionLatestMemoryReceipt ? (
                        <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                          latest_memory=<code>{missionMemoryReceiptLabel(selectedMissionLatestMemoryReceipt)}</code>
                          {selectedMissionLatestMemoryReceipt.operation_status ? (
                            <>
                              {" / "}memory_status=<code>{selectedMissionLatestMemoryReceipt.operation_status}</code>
                            </>
                          ) : null}
                          {selectedMissionLatestMemoryReceiptAt ? (
                            <>
                              {" / "}memory_at=<code>{selectedMissionLatestMemoryReceiptAt}</code>
                            </>
                          ) : null}
                          {selectedMissionLatestMemoryReceiptRefs ? <>{" / "}{selectedMissionLatestMemoryReceiptRefs}</> : null}
                          {selectedMissionLatestMemoryReceiptHandoff ? <>{" / "}{selectedMissionLatestMemoryReceiptHandoff}</> : null}
                        </div>
                      ) : null}
                      {(selectedMemoryEvidenceBusy ||
                        selectedMemoryEvidenceError ||
                        selectedMemoryEvidenceLoadedAt !== null ||
                        selectedMemoryEvidence.length > 0) ? (
                        <div
                          style={{
                            border: `1px solid ${THEME.panelBorder}`,
                            borderRadius: 10,
                            padding: 10,
                            marginTop: 8,
                            background: "#101214",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                            <div style={{ fontSize: 12, fontWeight: 600 }}>Memory Evidence</div>
                            {selectedMemoryEvidenceLoadedAt !== null ? (
                              <div style={{ fontSize: 11, color: THEME.muted }}>
                                loaded <code>{toLocaleTime(selectedMemoryEvidenceLoadedAt)}</code>
                              </div>
                            ) : null}
                          </div>
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {selectedMemoryEvidenceQueries.map((query) => query.label).join(" / ")}
                          </div>
                          {selectedMemoryEvidenceBusy ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>Loading timeline events.</div>
                          ) : selectedMemoryEvidenceError ? (
                            <div style={{ fontSize: 11, color: "#ffaaaa", marginTop: 8 }}>
                              Memory timeline unavailable: {selectedMemoryEvidenceError}
                            </div>
                          ) : selectedMemoryEvidenceLoadedAt !== null && selectedMemoryEvidence.length === 0 ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                              No timeline events returned for the selected ids.
                            </div>
                          ) : selectedMemoryEvidence.length > 0 ? (
                            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                              {selectedMemoryEvidence.map((event) => {
                                const referenceLine = memoryTimelineEventReferenceLine(event);
                                return (
                                  <div key={event.id} style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8 }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                                      <div style={{ fontSize: 12, color: THEME.text }}>{memoryTimelineEventSummary(event)}</div>
                                      <span style={badgeStyle(event.kind || "memory")}>{event.kind || "memory"}</span>
                                    </div>
                                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                                      event <code>{event.id}</code> / at <code>{toLocaleTime(event.ts)}</code>
                                    </div>
                                    {referenceLine ? (
                                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{referenceLine}</div>
                                    ) : null}
                                  </div>
                                );
                              })}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      {(selectedExplanationEvidenceBusy ||
                        selectedExplanationEvidenceError ||
                        selectedExplanationEvidenceLoadedAt !== null ||
                        selectedExplanationEvidence.length > 0) ? (
                        <div
                          style={{
                            border: `1px solid ${THEME.panelBorder}`,
                            borderRadius: 10,
                            padding: 10,
                            marginTop: 8,
                            background: "#101214",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                            <div style={{ fontSize: 12, fontWeight: 600 }}>Audit Explanations</div>
                            {selectedExplanationEvidenceLoadedAt !== null ? (
                              <div style={{ fontSize: 11, color: THEME.muted }}>
                                loaded <code>{toLocaleTime(selectedExplanationEvidenceLoadedAt)}</code>
                              </div>
                            ) : null}
                          </div>
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            {selectedExplanationEvidenceQueries.map((query) => query.label).join(" / ")}
                          </div>
                          {selectedExplanationEvidenceBusy ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>Loading explanation records.</div>
                          ) : selectedExplanationEvidenceError ? (
                            <div style={{ fontSize: 11, color: "#ffaaaa", marginTop: 8 }}>
                              Explanation records unavailable: {selectedExplanationEvidenceError}
                            </div>
                          ) : selectedExplanationEvidenceLoadedAt !== null && selectedExplanationEvidence.length === 0 ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                              No explanation records returned for the selected receipt handles.
                            </div>
                          ) : selectedExplanationEvidence.length > 0 ? (
                            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                              {selectedExplanationEvidence.map((record) => {
                                const referenceLine = explanationRecordReferenceLine(record);
                                return (
                                  <div key={record.id} style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 8, padding: 8 }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                                      <div style={{ fontSize: 12, color: THEME.text }}>{explanationRecordSummary(record)}</div>
                                      <span style={badgeStyle(record.kind || "audit")}>{record.kind || "audit"}</span>
                                    </div>
                                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                                      record <code>{record.id}</code> / at <code>{toLocaleTime(record.ts)}</code>
                                    </div>
                                    {referenceLine ? (
                                      <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>{referenceLine}</div>
                                    ) : null}
                                  </div>
                                );
                              })}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 8 }}>
                      Open mission flow to inspect loop receipts when the mission detail route is available.
                    </div>
                  )}
                </div>
              ) : null}
              {runSelectedBlockedReason && (selectedStatus === "queued" || selectedStatus === "blocked") ? (
                <div style={{ fontSize: 11, color: "#ffcf9d" }}>{runSelectedBlockedReason}</div>
              ) : null}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  onClick={() => void runSelectedOperation()}
                  disabled={!canRunSelected || actionBusy !== "" || workerCycleBusy}
                  style={buttonStyle}
                >
                  {actionBusy === "run" ? "Running." : "Run now"}
                </button>
                <button
                  onClick={() => void cancelSelectedOperation()}
                  disabled={!canCancelSelected || actionBusy !== "" || workerCycleBusy}
                  style={buttonStyle}
                >
                  {actionBusy === "cancel" ? "Canceling." : "Cancel"}
                </button>
                {selectedMissionId ? (
                  <button style={buttonStyle} onClick={() => props.onOpenMission(selectedMissionId)}>
                    Open mission flow
                  </button>
                ) : null}
                {selectedReceiptEvidenceAvailable ? (
                  <button style={buttonStyle} onClick={props.onOpenContinuityLedger}>
                    Open ORB ledger
                  </button>
                ) : null}
              </div>
              {actionNotice ? (
                <div
                  style={{
                    border: `1px solid ${actionNotice.tone === "error" ? THEME.errorBorder : THEME.panelBorder}`,
                    background: actionNotice.tone === "error" ? THEME.errorBg : "#111819",
                    color: actionNotice.tone === "error" ? "#ffaaaa" : "#aee6df",
                    padding: 10,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                >
                  {actionNotice.text}
                </div>
              ) : null}
              {hasGovernance ? (
                <div
                  style={{
                    border: `1px solid ${governanceTone === "error" ? THEME.errorBorder : THEME.panelBorder}`,
                    background:
                      governanceTone === "error" ? THEME.errorBg : governanceTone === "warn" ? "#1f1a0b" : "#111819",
                    color: governanceTone === "error" ? "#ffaaaa" : governanceTone === "warn" ? "#f4d27a" : "#aee6df",
                    padding: 12,
                    borderRadius: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>Governance Outcome</div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <span style={badgeStyle(selectedOperation.status || "unknown")}>
                        {selectedOperation.status || "unknown"}
                      </span>
                      {safeString(selectedGovernance.gate) ? (
                        <span style={badgeStyle(safeString(selectedGovernance.gate))}>
                          {safeString(selectedGovernance.gate)}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  {selectedResultMessage ? <div style={{ fontSize: 12, marginTop: 8 }}>{selectedResultMessage}</div> : null}
                  {safeString(selectedGovernance.operator_hint) ? (
                    <div style={{ fontSize: 12, marginTop: 8 }}>{safeString(selectedGovernance.operator_hint)}</div>
                  ) : null}
                  {safeString(selectedGovernance.next_step) ? (
                    <div style={{ fontSize: 11, marginTop: 8 }}>
                      Next step: <code>{safeString(selectedGovernance.next_step)}</code>
                    </div>
                  ) : null}
                  {(selectedGovernance.required_trust !== undefined || selectedGovernance.current_trust !== undefined) ? (
                    <div style={{ fontSize: 11, marginTop: 6 }}>
                      trust <code>{String(selectedGovernance.current_trust ?? "unknown")}</code> / required{" "}
                      <code>{String(selectedGovernance.required_trust ?? "unknown")}</code>
                    </div>
                  ) : null}
                  {selectedOrbPlane ? (
                    <div style={{ fontSize: 11, marginTop: 6 }}>
                      ORB plane <code>{selectedOrbPlane}</code>
                    </div>
                  ) : null}
                  {selectedMissionId ? (
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      <div style={{ fontSize: 11 }}>
                        mission <code>{selectedMissionId}</code>
                      </div>
                      <button style={buttonStyle} onClick={() => props.onOpenMission(selectedMissionId)}>
                        Open mission flow
                      </button>
                    </div>
                  ) : null}
                  {selectedApprovalId ? (
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      <div style={{ fontSize: 11 }}>
                        approval <code>{selectedApprovalId}</code>
                      </div>
                      <button
                        style={buttonStyle}
                        onClick={() =>
                          props.onOpenApprovals(selectedApprovalId, {
                            missionId: selectedMissionId || undefined,
                            operationId: selectedOperation.id,
                          })
                        }
                      >
                        Open approval
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {selectedErrorText ? (
                <div
                  style={{
                    border: `1px solid ${THEME.errorBorder}`,
                    background: THEME.errorBg,
                    color: "#ffaaaa",
                    padding: 10,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                >
                  <div>
                    <b>Error:</b> {selectedErrorText}
                  </div>
                  {selectedRecoveryGuidance ? (
                    <div style={{ marginTop: 8 }}>
                      <b>Recovery:</b> {selectedRecoveryGuidance}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {!selectedErrorText && showSelectedRecoveryGuidance ? (
                <div
                  style={{
                    border: `1px solid ${THEME.errorBorder}`,
                    background: THEME.errorBg,
                    color: "#ffaaaa",
                    padding: 10,
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                >
                  <b>Recovery:</b> {selectedRecoveryGuidance}
                </div>
              ) : null}
              {selectedLogs.length > 0 ? (
                <div
                  style={{
                    border: `1px solid ${THEME.panelBorder}`,
                    background: "#101010",
                    padding: 10,
                    borderRadius: 10,
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600 }}>Audit Trail</div>
                  <div style={{ display: "grid", gap: 8, marginTop: 8, maxHeight: 220, overflow: "auto" }}>
                    {selectedLogs.map((entry) => {
                      const entryMeta = isRecord(entry.meta) ? entry.meta : {};
                      const reason = safeString(entryMeta.reason);
                      const gate = safeString(entryMeta.gate);
                      const nextStep = safeString(entryMeta.next_step);
                      const taskId = safeString(entryMeta.task_id).trim() || selectedOperation.id;
                      const entryOrbPlane = safeString(entryMeta.orb_plane).trim();
                      return (
                        <div
                          key={entry.id}
                          style={{
                            border: `1px solid ${THEME.panelBorder}`,
                            borderRadius: 10,
                            padding: 10,
                            background: "#121212",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                            <div style={{ fontSize: 12, fontWeight: 600 }}>{entry.name || entry.id}</div>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                              {entry.status && entry.status !== "unknown" ? (
                                <span style={badgeStyle(entry.status)}>{entry.status}</span>
                              ) : null}
                              <span style={{ fontSize: 11, color: THEME.muted }}>
                                {toLocaleTime(entry.ts)}
                              </span>
                            </div>
                          </div>
                          {reason ? <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{reason}</div> : null}
                          {gate ? (
                            <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                              gate <code>{gate}</code>
                              {nextStep ? (
                                <>
                                  {" / "}next <code>{nextStep}</code>
                                </>
                              ) : null}
                            </div>
                          ) : null}
                          <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                            task <code>{taskId}</code>
                            {selectedMissionId ? (
                              <>
                                {" / "}mission <code>{selectedMissionId}</code>
                              </>
                            ) : null}
                            {entryOrbPlane ? (
                              <>
                                {" / "}plane <code>{entryOrbPlane}</code>
                              </>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              {(selectedOperation.output !== undefined || selectedOperation.input !== undefined) ? (
                <pre
                  style={{
                    margin: 0,
                    padding: 10,
                    borderRadius: 10,
                    border: `1px solid ${THEME.panelBorder}`,
                    background: "#101010",
                    whiteSpace: "pre-wrap",
                    fontSize: 11,
                    maxHeight: 220,
                    overflow: "auto",
                  }}
                >
{JSON.stringify(
  {
    input: selectedOperation.input,
    output: selectedOperation.output,
  },
  null,
  2,
)}
                </pre>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
