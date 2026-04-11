import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChatMessage } from "./chat";

import type { ApprovalItem } from "./index";
import { ApprovalsApiError, ApprovalsClient } from "./index";
import { OperationsApiError, OperationsClient } from "./operations";
import type { OperationDetail, OperationRecord } from "./operations";
import type { PluginRef, PluginRunResponse, PluginToolRef, PluginToolRunRequest } from "./plugin_browser";
import { PluginBrowserApiError, PluginBrowserClient } from "./plugin_browser";
import { SettingsApiError, SettingsClient, toLocaleTime } from "./settings";
import type {
  OperatorControlModeId,
  OperatorModeSnapshot,
  OrbStatusSnapshot,
  SystemHealth,
  SystemInfo,
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

function safeNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function firstLinkedTaskId(mission: WorldStateMissionSummary | null | undefined): string {
  if (!mission || !Array.isArray(mission.linked_task_ids)) return "";
  for (const taskId of mission.linked_task_ids) {
    const cleaned = safeString(taskId).trim();
    if (cleaned) return cleaned;
  }
  return "";
}

function operationMetaString(record: OperationRecord | null | undefined, key: string, fallback = ""): string {
  if (!record || !isRecord(record.meta)) return fallback;
  return safeString(record.meta[key], fallback);
}

function statusBadgeColors(status: string): { bg: string; border: string; color: string } {
  const normalized = safeString(status).trim().toLowerCase();
  if (["ready", "ok", "approved", "completed", "succeeded"].includes(normalized)) {
    return { bg: "#102417", border: "#244d31", color: "#9de2ad" };
  }
  if (["running", "pending", "accepted", "queued", "needs_approval"].includes(normalized)) {
    return { bg: "#1f1a0b", border: "#5a4c18", color: "#f4d27a" };
  }
  if (
    ["blocked", "denied", "failed", "rejected", "cancelled", "canceled", "missing", "error", "degraded", "disabled"].includes(
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

type ApprovalInspection = {
  domain: string;
  risk: string;
  scopeLabel: string;
  scopeItems: string[];
  evidenceItems: string[];
  approveEffect: string;
  denyEffect: string;
  missionRelation: string;
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

function inspectApproval(item: ApprovalItem | null | undefined): ApprovalInspection {
  const payload = approvalPayload(item);
  const meta = isRecord(payload.meta) ? payload.meta : {};
  const action = safeString(item?.action).trim().toLowerCase();
  const requestAction = approvalActionField(payload, safeString(item?.action).trim() || "requested action");
  const risk =
    approvalTextField(payload, "risk", "risk_tier") ||
    approvalTextField(meta, "risk", "risk_tier") ||
    safeString(item?.risk).trim() ||
    "unknown";
  const domain =
    approvalTextField(payload, "domain", "provider") ||
    safeString(item?.domain).trim() ||
    (action.includes(".") ? action.split(".", 1)[0] : action || "approval");

  const scopeItems: string[] = [];
  const pushScope = (label: string, value: string) => {
    const cleaned = value.trim();
    if (cleaned) scopeItems.push(`${label}: ${cleaned}`);
  };

  pushScope("Plugin", approvalTextField(payload, "plugin_id"));
  pushScope("Scope", approvalTextField(payload, "scope_id", "scope"));
  const targetKind = approvalTextField(payload, "target_kind");
  const targetId = approvalTextField(payload, "target_id", "twin_id", "validation_id");
  if (targetKind || targetId) {
    pushScope("Target", [targetKind, targetId].filter(Boolean).join(":"));
  }
  pushScope("Credential", approvalTextField(payload, "id"));
  pushScope("Provider", approvalTextField(payload, "provider"));
  pushScope("URL", approvalTextField(payload, "url"));
  pushScope("Domain", approvalTextField(payload, "domain"));
  pushScope("Record", approvalTextField(payload, "record_id", "request_id"));

  const scopeLabel = scopeItems[0] || `Domain: ${domain}`;

  const evidenceItems: string[] = [];
  const pushEvidence = (label: string, value: string) => {
    const cleaned = value.trim();
    if (cleaned) evidenceItems.push(`${label}: ${cleaned}`);
  };

  pushEvidence("Requested action", requestAction);
  pushEvidence("Reason", safeString(item?.reason).trim());
  pushEvidence("Required trust", approvalTextField(payload, "required_trust"));
  pushEvidence("Credential type", approvalTextField(payload, "type"));
  pushEvidence("Label", approvalTextField(payload, "label"));
  pushEvidence("Actor", approvalTextField(payload, "actor"));
  pushEvidence("Enabled change", typeof payload.enabled === "boolean" ? String(payload.enabled) : "");
  pushEvidence("Idempotency key", approvalTextField(payload, "idempotency_key"));
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
  const [focusedOperationId, setFocusedOperationId] = useState("");
  const [operatorMode, setOperatorMode] = useState<OperatorModeSnapshot | null>(null);
  const [operatorModeError, setOperatorModeError] = useState<string | null>(null);
  const [operatorModeBusy, setOperatorModeBusy] = useState(false);
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
        const json = (await res.json()) as { reply?: string };
        const reply = (json.reply ?? "").trim();
        if (reply) {
          updateSession(activeSession.id, (s) => ({
            ...s,
            messages: [
              ...s.messages,
              { role: "assistant", content: reply, ts: Math.floor(Date.now() / 1000) },
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

  const openApprovalsPanel = useCallback((approvalId?: string) => {
    setFocusedApprovalId(approvalId ? approvalId : "");
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

  const openMissionFeed = useCallback(() => {
    setPanel("system");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById("francis-mission-feed")?.scrollIntoView({ behavior: "smooth", block: "start" });
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

  const paletteCommands = useMemo<PaletteCommand[]>(() => {
    const pendingApprovals = safeNumber(operatorMode?.backlog?.pending_approvals, 0);
    return [
      {
        id: "nav.briefing",
        label: "Request Continuity Briefing",
        description: "Open the mission feed and return-to-work recommendations.",
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
    ];
  }, [
    createNewChat,
    openApprovalsPanel,
    openMissionFeed,
    openTakeoverFeed,
    openTelemetryStatus,
    openOperationsPanel,
    openOrbPanel,
    openPluginsPanel,
    openSettingsPanel,
    operatorMode?.backlog?.pending_approvals,
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

                {panel === "approvals" ? <ApprovalsPanel baseUrl={baseUrl} focusApprovalId={focusedApprovalId} /> : null}
                {panel === "plugins" ? <PluginsPanel baseUrl={baseUrl} onOpenApprovals={openApprovalsPanel} /> : null}
                {panel === "system" ? (
                <SystemPanel
                  baseUrl={baseUrl}
                  settings={settings}
                  operatorMode={operatorMode}
                  onOpenApprovals={openApprovalsPanel}
                  onOpenOperation={openOperationPanel}
                />
                ) : null}
                {panel === "operations" ? (
                  <OperationsPanel
                    baseUrl={baseUrl}
                    focusOperationId={focusedOperationId}
                    onOpenApprovals={openApprovalsPanel}
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

              {panel === "approvals" ? <ApprovalsPanel baseUrl={baseUrl} focusApprovalId={focusedApprovalId} /> : null}
              {panel === "plugins" ? <PluginsPanel baseUrl={baseUrl} onOpenApprovals={openApprovalsPanel} /> : null}
              {panel === "system" ? (
                <SystemPanel
                  baseUrl={baseUrl}
                  settings={settings}
                  operatorMode={operatorMode}
                  onOpenApprovals={openApprovalsPanel}
                  onOpenOperation={openOperationPanel}
                />
              ) : null}
              {panel === "operations" ? (
                <OperationsPanel
                  baseUrl={baseUrl}
                  focusOperationId={focusedOperationId}
                  onOpenApprovals={openApprovalsPanel}
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
function ApprovalsPanel(props: { baseUrl: string; focusApprovalId?: string }) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new ApprovalsClient(resolvedBaseUrl), [resolvedBaseUrl]);

  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [selectedApprovalId, setSelectedApprovalId] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [decisionBusy, setDecisionBusy] = useState<Record<string, boolean>>({});
  const [decisionError, setDecisionError] = useState<Record<string, string | null>>({});

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

  async function performDecision(id: string, action: string) {
    setDecisionError((prev) => ({ ...prev, [id]: null }));
    setDecisionBusy((prev) => ({ ...prev, [id]: true }));
    try {
      await client.decide({ id, action });
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

      <div style={{ ...summaryCardStyle(), marginTop: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Selected Approval</div>
        {!selectedApproval ? (
          <div style={{ marginTop: 8, fontSize: 12, color: THEME.muted }}>No approval selected.</div>
        ) : (
          <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>{selectedApproval.action || "(unknown action)"}</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span style={badgeStyle(selectedApproval.status || "pending")}>{selectedApproval.status || "pending"}</span>
                <span style={badgeStyle(selectedInspection.risk)}>{selectedInspection.risk}</span>
                <span style={badgeStyle(selectedInspection.domain)}>{selectedInspection.domain}</span>
              </div>
            </div>
            <div style={{ fontSize: 11, color: THEME.muted }}>
              <code>{selectedApproval.id}</code>
            </div>
            <div style={{ fontSize: 12, color: THEME.muted }}>
              {selectedApproval.reason || "No reason provided."}
            </div>
            <div style={{ fontSize: 12 }}>
              Created: <code>{selectedApproval.ts ? toLocaleTime(selectedApproval.ts) : "unknown"}</code>
            </div>
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
                <div style={{ fontWeight: 600 }}>{a.action || "(unknown action)"}</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span style={badgeStyle(a.status || "pending")}>{a.status || "pending"}</span>
                  <span style={badgeStyle(inspection.risk)}>{inspection.risk}</span>
                </div>
              </div>
              <div style={{ fontSize: 12, color: THEME.muted, marginTop: 4 }}>{a.reason || "No reason provided."}</div>
              <div style={{ fontSize: 12, color: THEME.muted, marginTop: 6 }}>{inspection.scopeLabel}</div>
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
  onOpenApprovals: (approvalId?: string) => void;
  onOpenOperation: (operationId: string) => void;
}) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new SettingsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const operationsClient = useMemo(() => new OperationsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [worldState, setWorldState] = useState<WorldStateSnapshot | null>(null);
  const [orbStatus, setOrbStatus] = useState<OrbStatusSnapshot | null>(null);
  const [takeoverOperations, setTakeoverOperations] = useState<OperationRecord[]>([]);
  const [takeoverOperationsError, setTakeoverOperationsError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setTakeoverOperationsError(null);
      const [nextInfo, nextHealth, nextWorldState, nextOrbStatus] = await Promise.all([
        client.getSystemInfo(),
        client.getHealth(),
        client.getWorldState(),
        client.getOrbStatus(),
      ]);
      const nextOperations = await operationsClient
        .list({ limit: 16 })
        .then((response) => response.items ?? [])
        .catch((err) => {
          const msg =
            err instanceof OperationsApiError
              ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
              : err instanceof Error
                ? err.message
                : "Operations request failed.";
          setTakeoverOperationsError(msg);
          return [] as OperationRecord[];
        });
      setInfo(nextInfo);
      setHealth(nextHealth);
      setWorldState(nextWorldState);
      setOrbStatus(nextOrbStatus);
      setTakeoverOperations(nextOperations);
    } catch (err) {
      const msg =
        err instanceof SettingsApiError
          ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
          : err instanceof Error
            ? err.message
            : "Request failed.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }, [client, operationsClient]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const counts = worldState?.counts;
  const overview = worldState?.overview;
  const taskStatusCounts = overview?.task_status_counts ?? {};
  const missionStatusCounts = overview?.mission_status_counts ?? {};
  const recentTasks = overview?.recent_tasks ?? [];
  const recentMissions = overview?.recent_missions ?? [];
  const incidents = overview?.incidents ?? [];
  const pendingApprovals = overview?.pending_approvals ?? [];
  const queuedTasks = safeNumber(counts?.queued_tasks, safeNumber(taskStatusCounts.pending, 0) + safeNumber(taskStatusCounts.accepted, 0));
  const approvalPendingTasks = safeNumber(counts?.approval_pending_tasks, safeNumber(taskStatusCounts.needs_approval, 0));
  const blockedTasks = safeNumber(counts?.blocked_tasks, safeNumber(taskStatusCounts.blocked, 0));
  const runningTasks = safeNumber(counts?.running_tasks, safeNumber(taskStatusCounts.running, 0));
  const queuedMissions = safeNumber(counts?.queued_missions, safeNumber(missionStatusCounts.queued, 0));
  const activeMissions = safeNumber(counts?.active_missions, safeNumber(missionStatusCounts.active, 0));
  const blockedMissions = safeNumber(counts?.blocked_missions, safeNumber(missionStatusCounts.blocked, 0));
  const deadletteredMissions = safeNumber(
    counts?.deadlettered_missions,
    safeNumber(missionStatusCounts.deadlettered, 0),
  );
  const declaredMissionCount = safeNumber(counts?.missions, recentMissions.length);
  const activeIncidents = safeNumber(counts?.active_incidents, incidents.length);
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
  const leadMission =
    recentMissions.find((mission) => ["deadlettered", "blocked"].includes(safeString(mission.status).trim().toLowerCase())) ??
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

  if (leadMission) {
    const linkedTaskId = firstLinkedTaskId(leadMission);
    const missionDetail =
      safeString(leadMission.last_task_next_step).trim() ||
      safeString(leadMission.next_step).trim() ||
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
      onAction: approvalId ? () => props.onOpenApprovals(approvalId) : taskId ? () => props.onOpenOperation(taskId) : undefined,
    });
  }

  if (pendingApprovals.length > 0) {
    const approval = pendingApprovals[0];
    returnToWorkItems.push({
      id: `approval:${approval.id}`,
      label: "Approval",
      title: approval.action || "Pending approval",
      detail: approval.reason || "A governed action is queued and waiting for operator review.",
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

        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12 }}>Recent Mission Progress</div>
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {missionFeedDeclared && recentDeclaredMissions.length === 0 ? (
            <div style={{ fontSize: 12, color: THEME.muted }}>No mission progress has been recorded yet.</div>
          ) : missionFeedDeclared ? (
            recentDeclaredMissions.map((mission) => {
              const linkedTaskId = firstLinkedTaskId(mission);
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
                    next_step=<code>{mission.next_step || "unset"}</code>
                  </div>
                  {mission.last_task_status || mission.last_task_result_status ? (
                    <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                      latest_run=<code>{mission.last_task_status || "unknown"}</code>
                      {mission.last_task_result_status ? (
                        <>
                          {" / "}result=<code>{mission.last_task_result_status}</code>
                        </>
                      ) : null}
                      {mission.last_task_gate ? (
                        <>
                          {" / "}gate=<code>{mission.last_task_gate}</code>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  <div style={{ fontSize: 11, color: THEME.muted, marginTop: 4 }}>
                    linked_tasks=<code>{String(mission.linked_task_count ?? mission.linked_task_ids?.length ?? 0)}</code>
                    {" / "}risk=<code>{mission.risk_tier || "unknown"}</code>
                  </div>
                  {mission.last_task_reason ? (
                    <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{mission.last_task_reason}</div>
                  ) : null}
                  {mission.deadletter_reason ? (
                    <div style={{ fontSize: 11, color: "#ffcf9d", marginTop: 4 }}>{mission.deadletter_reason}</div>
                  ) : null}
                  {linkedTaskId ? (
                    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                      <button style={buttonStyle} onClick={() => props.onOpenOperation(linkedTaskId)}>
                        Open linked task
                      </button>
                    </div>
                  ) : null}
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
                    {typeof incident.count === "number" ? ` / count=${String(incident.count)}` : ""}
                  </div>
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
                    {approvalId ? (
                      <button style={buttonStyle} onClick={() => props.onOpenApprovals(approvalId)}>
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
              <div
                key={item.id}
                style={{ border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 10, background: "#121212" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{item.action || "unknown_action"}</div>
                  <span style={badgeStyle(item.status || "pending")}>{item.status || "pending"}</span>
                </div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>{item.reason || "No reason recorded."}</div>
                <div style={{ fontSize: 11, color: THEME.muted, marginTop: 6 }}>
                  <code>{item.id}</code>
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                  <button style={buttonStyle} onClick={() => props.onOpenApprovals(item.id)}>
                    Review
                  </button>
                </div>
              </div>
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

  function pluginErrorMessage(err: unknown): string {
    if (err instanceof PluginBrowserApiError) {
      const status = err.status ? `HTTP ${err.status}` : "request failed";
      return `${status}${err.url ? ` (${err.url})` : ""}`;
    }
    if (err instanceof Error) return err.message;
    return "Plugin request failed.";
  }

  const refreshPlugins = useCallback(async () => {
    setLoading(true);
    try {
      const res = await client.list({ limit: 200 });
      const items = res.items ?? [];
      setPlugins(items);
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
        body: JSON.stringify({ name: trimmed, description: description.trim() }),
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
              <button style={buttonStyle} onClick={() => props.onOpenApprovals(runResponse.approval_id)}>
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

function OperationsPanel(props: { baseUrl: string; focusOperationId?: string; onOpenApprovals: (approvalId?: string) => void }) {
  const resolvedBaseUrl = useMemo(() => normalizeBaseUrl(props.baseUrl), [props.baseUrl]);
  const client = useMemo(() => new OperationsClient(resolvedBaseUrl), [resolvedBaseUrl]);
  const [items, setItems] = useState<OperationRecord[]>([]);
  const [selectedOperationId, setSelectedOperationId] = useState("");
  const [detail, setDetail] = useState<OperationDetail | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState<"" | "run" | "cancel">("");
  const [actionNotice, setActionNotice] = useState<{ tone: "info" | "error"; text: string } | null>(null);
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
  const selectedGovernance = isRecord(selectedMeta.governance) ? selectedMeta.governance : {};
  const selectedApprovalId =
    safeString(selectedMeta.approval_id) || safeString(selectedOutput.approval_id) || "";
  const selectedOrbPlane = safeString(selectedMeta.orb_plane);
  const selectedResultMessage = safeString(selectedMeta.result_message);
  const selectedLogs = Array.isArray(detail?.logs) ? detail.logs : [];
  const hasGovernance =
    Object.keys(selectedGovernance).length > 0 || Boolean(selectedApprovalId) || Boolean(selectedOrbPlane);
  const governanceTone =
    ["blocked", "denied", "failed", "error"].includes(selectedStatus)
      ? "error"
      : ["queued", "pending", "needs_approval"].includes(selectedStatus)
        ? "warn"
        : "info";
  const canRunSelected = selectedStatus === "queued" || selectedStatus === "blocked";
  const canCancelSelected = selectedStatus === "queued" || selectedStatus === "running" || selectedStatus === "blocked";

  const runSelectedOperation = useCallback(async () => {
    if (!selectedOperationId || !canRunSelected) return;
    setActionBusy("run");
    setActionNotice(null);
    setError(null);
    try {
      const response = await client.run(selectedOperationId, { worker_id: "chat_ui.operations" });
      if (response.operation) upsertOperation(response.operation);
      const nextDetail = await loadDetail(selectedOperationId);
      const nextStatus = safeString(
        nextDetail?.operation.status ?? response.operation?.status ?? response.status,
        "unknown",
      );
      if (!response.ok) {
        setActionNotice({
          tone: "error",
          text: response.message ? `Run failed: ${response.message}` : `Run failed with status ${nextStatus}.`,
        });
        return;
      }
      setActionNotice({
        tone: "info",
        text:
          response.message === "already_terminal"
            ? `Operation is already ${nextStatus}.`
            : `Operation status is now ${nextStatus}.`,
      });
    } catch (err) {
      setActionNotice({ tone: "error", text: operationsError(err) });
    } finally {
      setActionBusy("");
    }
  }, [canRunSelected, client, loadDetail, operationsError, selectedOperationId, upsertOperation]);

  const cancelSelectedOperation = useCallback(async () => {
    if (!selectedOperationId || !canCancelSelected) return;
    setActionBusy("cancel");
    setActionNotice(null);
    setError(null);
    try {
      const response = await client.cancel(selectedOperationId, { reason: "cancelled_from_chat_ui" });
      const nextDetail = await loadDetail(selectedOperationId);
      const nextStatus = safeString(nextDetail?.operation.status ?? response.status, "unknown");
      if (!response.ok) {
        setActionNotice({
          tone: "error",
          text: response.message ? `Cancel failed: ${response.message}` : `Cancel failed with status ${nextStatus}.`,
        });
        return;
      }
      setActionNotice({ tone: "info", text: `Operation status is now ${nextStatus}.` });
    } catch (err) {
      setActionNotice({ tone: "error", text: operationsError(err) });
    } finally {
      setActionBusy("");
    }
  }, [canCancelSelected, client, loadDetail, operationsError, selectedOperationId]);

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
          <button onClick={() => void refresh()} disabled={busy || actionBusy !== ""} style={buttonStyle}>
            {busy ? "Refreshing." : "Refresh"}
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
              <div style={{ fontSize: 12 }}>
                Attempts: <code>{String(safeNumber(isRecord(selectedOperation.meta) ? selectedOperation.meta.attempts : 0, 0))}</code>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  onClick={() => void runSelectedOperation()}
                  disabled={!canRunSelected || actionBusy !== ""}
                  style={buttonStyle}
                >
                  {actionBusy === "run" ? "Running." : "Run now"}
                </button>
                <button
                  onClick={() => void cancelSelectedOperation()}
                  disabled={!canCancelSelected || actionBusy !== ""}
                  style={buttonStyle}
                >
                  {actionBusy === "cancel" ? "Canceling." : "Cancel"}
                </button>
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
                  {selectedApprovalId ? (
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      <div style={{ fontSize: 11 }}>
                        approval <code>{selectedApprovalId}</code>
                      </div>
                      <button style={buttonStyle} onClick={() => props.onOpenApprovals(selectedApprovalId)}>
                        Open approval
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {selectedOperation.error ? (
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
                  <b>Error:</b> {safeString(selectedOperation.error, JSON.stringify(selectedOperation.error))}
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
