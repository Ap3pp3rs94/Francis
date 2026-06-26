import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { fetchLensMcpStatus, type LensMcpStatus } from "./lens/mcpStatus";
import {
  collaborationActionBoundarySummary,
  collaborationActionIntakeSummary,
  collaborationBuildDirectionGateSummary,
  collaborationImplementationReviewSummary,
  collaborationLearningGuardSummary,
  collaborationTranscriptAuditSummary,
  DEFAULT_SHOW_GUARD_RECEIPTS,
  fetchCollaborationAgentsStatus,
  fetchCollaborationLearning,
  fetchCollaborationReview,
  fetchCollaborationRuntimeHealth,
  fetchCollaborationSessions,
  fetchCollaborationSubstrateReadiness,
  fetchCollaborationTranscript,
  fetchFrancisBodyMap,
  fetchFrancisTrustLadder,
  collaborationReviewBadge,
  collaborationReviewNextAction,
  collaborationReviewTone,
  collaborationRuntimeRecurrenceSummary,
  collaborationSessionReviewGateSummary,
  collaborationRuntimeLocalModelResponseSummary,
  collaborationRuntimeLearningReceiptSummary,
  collaborationRuntimeLearningSignalSummary,
  collaborationRuntimeReviewReceiptSummary,
  collaborationSubstrateChecklistSummary,
  collaborationSessionTranscriptDisclosureSummary,
  filterCollaborationTranscriptItems,
  francisBodySurfaceExposureSummary,
  formatCollaborationRelayMessage,
  isCollaborationAuditReceipt,
  isCollaborationDriverPrompt,
  isCollaborationGuardReceipt,
  preserveCollaborationReadbackDuringWarming,
  setCollaborationAgentEnabled,
  type CollaborationAgent,
  type CollaborationAgentsStatus,
  type CollaborationAgentToggleReceipt,
  type CollaborationLearning,
  type CollaborationReview,
  type CollaborationRuntimeHealth,
  type CollaborationSessions,
  type CollaborationSubstrateReadiness,
  type CollaborationTranscript,
  type FrancisBodyMap,
  type FrancisTrustLadder,
} from "./chat/collaboration";
import {
  fetchCommandPaletteMonitorStatus,
  type CommandPaletteMonitorStatus,
} from "./lens/commandPaletteMonitor";
import { bodyStateReady, presentOrbGlyph, type OrbGlyphState } from "./lens/orbGlyph";
import { shouldOpenLensOrbOverlay } from "./lens";
import {
  FrancisVoiceClient,
  type FrancisVoiceIngressResponse,
  createVoiceTurnId,
  normalizeVoiceTranscript,
  shouldSpeakVoiceReplyWithBrowserTts,
  summarizeVoiceRecognitionErrorForOperator,
  summarizeVoiceSoundForOperator,
  summarizeVoiceTranscriptForOperator,
} from "./voice";

type SpeechRecognitionAlternative = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: ((event: { error?: string; message?: string }) => void) | null;
  onnomatch: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onsoundend: (() => void) | null;
  onsoundstart: (() => void) | null;
  onspeechstart: (() => void) | null;
  onstart: (() => void) | null;
  abort: () => void;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionAlternative;

type SpeechRecognitionResultLike = {
  isFinal: boolean;
  item?: (index: number) => { transcript?: string };
  [index: number]: { transcript?: string } | undefined;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: SpeechRecognitionResultLike;
  };
};

const BRIDGE_MONITOR_POLL_MS = 15000;
const COLLABORATION_PANEL_POLL_MS = 5000;
const LENS_MCP_STATUS_TIMEOUT_MS = 5000;
const COLLABORATION_READBACK_TIMEOUT_MS = 9000;
const COLLABORATION_TRANSCRIPT_LIMIT = 40;
const COLLABORATION_SESSION_ITEM_LIMIT = 50;
const COLLABORATION_REVIEW_LIMIT = 20;
const COLLABORATION_LEARNING_LIMIT = 4;
const FRANCIS_TRUST_LADDER_LIMIT = 8;
const COLLABORATION_SESSION_GAP_MS = 30 * 60 * 1000;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

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

type PolicyRelayReceiptView = {
  receiptId: string;
  decision: string;
  policyId: string;
  riskClass: string;
  toolName: string;
  requestedAuthority: string;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  remoteEgress: boolean;
};

type PolicyRelayView = {
  available: boolean;
  ok: boolean;
  status: string;
  safeReadback: boolean;
  receiptCount: number;
  returnedCount: number;
  latest: PolicyRelayReceiptView | null;
};

function recordValue(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {};
}

function recordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.map(recordValue) : [];
}

function numberValue(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function booleanValue(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function policyRelayView(status: LensMcpStatus | null): PolicyRelayView {
  const readback = status?.optional_readbacks["francis.policy.receipts"];
  const data = recordValue(readback?.data);
  const latestRaw = recordList(data["items"])[0];
  const latest = latestRaw
    ? {
        receiptId: stringValue(latestRaw["receipt_id"], "none"),
        decision: stringValue(latestRaw["decision"], "none"),
        policyId: stringValue(latestRaw["policy_id"], "none"),
        riskClass: stringValue(latestRaw["risk_class"], "none"),
        toolName: stringValue(latestRaw["tool_name"], "none"),
        requestedAuthority: stringValue(latestRaw["requested_authority"], "none"),
        grantsExecutionAuthority: booleanValue(latestRaw["grants_execution_authority"]),
        grantsMutationAuthority: booleanValue(latestRaw["grants_mutation_authority"]),
        remoteEgress: booleanValue(latestRaw["remote_egress"]),
      }
    : null;

  return {
    available: Boolean(readback),
    ok: Boolean(readback?.ok),
    status: statusText(readback?.status),
    safeReadback: Boolean(readback?.safe_readback),
    receiptCount: numberValue(data["receipt_count"]),
    returnedCount: numberValue(data["returned_count"]),
    latest,
  };
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === "AbortError";
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

// Deterministic pseudo-random in [0,1) so the smoky trail field is stable across
// renders (no Math.random — keeps SSR/markup deterministic).
function orbRand(n: number): number {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

// Many fine, lightly-blurred orbital trails approximate the reference's smoky
// filament density. Generated once; deliberately irregular — varied size, tilt,
// opacity, and small center offsets so the field is chaotic, not a clean "atom".
const ORB_TRAILS: ReadonlyArray<{ rx: number; ry: number; rot: number; o: number; dx: number; dy: number }> =
  Array.from({ length: 112 }, (_unused, i) => ({
    rx: 18 + orbRand(i + 5) * 62,
    ry: 7 + orbRand(i + 13) * 35,
    rot: (i * 360) / 112 + (orbRand(i) - 0.5) * 76,
    o: 0.035 + orbRand(i + 23) * 0.18,
    dx: (orbRand(i + 41) - 0.5) * 22,
    dy: (orbRand(i + 59) - 0.5) * 22,
  }));

// A few crisper, slightly offset strands give the field definition over the smoke.
const ORB_ACCENTS: ReadonlyArray<{ rx: number; ry: number; rot: number; dx: number; dy: number }> = [
  { rx: 68, ry: 22, rot: 18, dx: -4, dy: 3 },
  { rx: 72, ry: 34, rot: 84, dx: 6, dy: -3 },
  { rx: 58, ry: 18, rot: 143, dx: 3, dy: 4 },
  { rx: 46, ry: 42, rot: 52, dx: -3, dy: -4 },
  { rx: 78, ry: 28, rot: 110, dx: 4, dy: 1 },
  { rx: 52, ry: 24, rot: 7, dx: -2, dy: -3 },
  { rx: 64, ry: 38, rot: 156, dx: 2, dy: -1 },
  { rx: 44, ry: 17, rot: 219, dx: -5, dy: 2 },
];

function OrbGlyph(props: { state: OrbGlyphState }) {
  const s = props.state;
  // Rings stay white/silver; state only subtly brightens them.
  const ringBoost = 0.6 + 0.5 * s.intensity;
  return (
    <svg
      width={118}
      height={118}
      viewBox="0 0 160 160"
      role="img"
      aria-label={s.label}
      data-orb-glyph="true"
      data-orb-tone={s.tone}
      data-orb-posture={s.posture}
      data-orb-read-only={String(s.readOnly)}
      style={{ flexShrink: 0 }}
    >
      <title>{s.label}</title>
      <defs>
        {/* Soft dark field — a gentle vignette, not a hard black badge. */}
        <radialGradient id="francisOrbField" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#0a1018" stopOpacity={0.78} />
          <stop offset="48%" stopColor="#05080d" stopOpacity={0.36} />
          <stop offset="100%" stopColor="#020306" stopOpacity={0} />
        </radialGradient>
        {/* Luminous white/silver halo. */}
        <radialGradient id="francisOrbGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={s.glowColor} stopOpacity={0.95 * s.intensity} />
          <stop offset="23%" stopColor={s.glowColor} stopOpacity={0.34 * s.intensity} />
          <stop offset="62%" stopColor={s.glowColor} stopOpacity={0.08 * s.intensity} />
          <stop offset="100%" stopColor={s.glowColor} stopOpacity={0} />
        </radialGradient>
        {/* Graphite core whose edge dissolves into the field — a dark dense body
            with light emerging from inside, not a hard marble. */}
        <radialGradient id="francisOrbCore" cx="48%" cy="44%" r="60%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity={0.98} />
          <stop offset="20%" stopColor="#eef6ff" stopOpacity={0.9} />
          <stop offset="42%" stopColor="#8298b5" stopOpacity={0.64} />
          <stop offset="70%" stopColor="#172231" stopOpacity={0.76} />
          <stop offset="100%" stopColor={s.coreColor} stopOpacity={0} />
        </radialGradient>
        {/* Soft white luminous bloom — bright center bleeding past the core. */}
        <radialGradient id="francisOrbCenter" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity={1 * s.intensity} />
          <stop offset="28%" stopColor="#ffffff" stopOpacity={0.68 * s.intensity} />
          <stop offset="62%" stopColor="#eaf2ff" stopOpacity={0.16 * s.intensity} />
          <stop offset="100%" stopColor="#ffffff" stopOpacity={0} />
        </radialGradient>
        {/* Smoky softening for the dense trail field. */}
        <filter id="francisOrbSmoke" x="-25%" y="-25%" width="150%" height="150%">
          <feGaussianBlur stdDeviation="0.42" />
        </filter>
      </defs>
      <circle cx={80} cy={80} r={78} fill="url(#francisOrbField)" />
      <circle cx={80} cy={80} r={73} fill="url(#francisOrbGlow)" />
      {/* Dense smoky trail field */}
      <g fill="none" stroke={s.ringColor} strokeWidth={0.58} filter="url(#francisOrbSmoke)">
        {ORB_TRAILS.map((t, i) => (
          <ellipse
            key={`trail-${i}`}
            cx={80 + t.dx}
            cy={80 + t.dy}
            rx={t.rx}
            ry={t.ry}
            opacity={Math.min(0.52, t.o * ringBoost)}
            transform={`rotate(${t.rot.toFixed(2)} ${(80 + t.dx).toFixed(2)} ${(80 + t.dy).toFixed(2)})`}
          />
        ))}
      </g>
      {/* Defining strands */}
      <g fill="none" stroke={s.ringColor} strokeWidth={0.78}>
        {ORB_ACCENTS.map((b, i) => (
          <ellipse
            key={`accent-${i}`}
            cx={80 + b.dx}
            cy={80 + b.dy}
            rx={b.rx}
            ry={b.ry}
            opacity={Math.min(0.5, 0.18 * ringBoost)}
            transform={`rotate(${b.rot} ${80 + b.dx} ${80 + b.dy})`}
          />
        ))}
      </g>
      <circle cx={80} cy={80} r={34} fill="url(#francisOrbCore)" />
      <circle cx={80} cy={80} r={43} fill="url(#francisOrbCenter)" />
    </svg>
  );
}

function BodyStatePanel(props: { status: LensMcpStatus | null; loading: boolean; error: string; onRefresh: () => void }) {
  const status = props.status;
  const ready = bodyStateReady(status);
  const orb = presentOrbGlyph(status, props.loading);
  const policyRelay = policyRelayView(status);
  const policyRelayReady = policyRelay.available && policyRelay.ok && policyRelay.safeReadback;

  return (
    <section
      style={{
        border: "1px solid rgba(148, 163, 184, 0.35)",
        borderRadius: 18,
        padding: 24,
        background: "rgba(8, 11, 17, 0.92)",
        boxShadow: "0 24px 80px rgba(0,0,0,0.45)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", flexWrap: "wrap", justifyContent: "space-between", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", flexWrap: "wrap", gap: 18, minWidth: 0 }}>
          <OrbGlyph state={orb} />
          <div style={{ minWidth: 0 }}>
          <p style={{ color: "#93c5fd", margin: 0, textTransform: "uppercase", letterSpacing: 1.8 }}>
            Lens / Orb body-state
          </p>
          <h1 style={{ fontSize: 34, margin: "8px 0 8px" }}>Francis MCP Status</h1>
          <p style={{ color: "#cbd5e1", margin: 0, maxWidth: 760 }}>
            Read-only projection from the existing Lens surface into the MCP, screen, takeover, and input
            substrate. This does not grant resident or input authority.
          </p>
          </div>
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
            maxWidth: "100%",
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
        <Pill label="policy relay" value={policyRelay.status} tone={policyRelayReady ? "ready" : "blocked"} />
        <Pill label="policy receipts" value={String(policyRelay.receiptCount)} tone="neutral" />
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

      <section
        style={{
          borderTop: "1px solid rgba(148, 163, 184, 0.26)",
          marginTop: 18,
          paddingTop: 14,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", flexWrap: "wrap", justifyContent: "space-between", gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <p style={{ color: "#93c5fd", fontSize: 12, margin: 0, textTransform: "uppercase" }}>Tool policy relay</p>
            <h2 style={{ fontSize: 18, margin: "4px 0 0" }}>{policyRelay.latest?.decision ?? "no receipts"}</h2>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <Pill label="readback" value={policyRelay.safeReadback ? "safe" : "missing"} tone={policyRelayReady ? "ready" : "blocked"} />
            <Pill label="execution" value={boolText(Boolean(policyRelay.latest?.grantsExecutionAuthority))} tone="neutral" />
            <Pill label="mutation" value={boolText(Boolean(policyRelay.latest?.grantsMutationAuthority))} tone="neutral" />
            <Pill label="egress" value={boolText(Boolean(policyRelay.latest?.remoteEgress))} tone="neutral" />
          </div>
        </div>
        <dl
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            margin: "14px 0 0",
          }}
        >
          <div>
            <dt style={{ color: "#94a3b8" }}>Latest receipt</dt>
            <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{policyRelay.latest?.receiptId ?? "none"}</dd>
          </div>
          <div>
            <dt style={{ color: "#94a3b8" }}>Policy</dt>
            <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{policyRelay.latest?.policyId ?? "none"}</dd>
          </div>
          <div>
            <dt style={{ color: "#94a3b8" }}>Risk</dt>
            <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{policyRelay.latest?.riskClass ?? "none"}</dd>
          </div>
          <div>
            <dt style={{ color: "#94a3b8" }}>Tool</dt>
            <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{policyRelay.latest?.toolName ?? "none"}</dd>
          </div>
          <div>
            <dt style={{ color: "#94a3b8" }}>Authority requested</dt>
            <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{policyRelay.latest?.requestedAuthority ?? "none"}</dd>
          </div>
          <div>
            <dt style={{ color: "#94a3b8" }}>Returned</dt>
            <dd style={{ margin: 0 }}>{policyRelay.returnedCount}</dd>
          </div>
        </dl>
      </section>

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
                policy_relay: policyRelay,
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

const ORB_OVERLAY_SIZE = 128;
const ORB_OVERLAY_DOCK_MARGIN = 24;

function clampOrbOverlayPosition(left: number, top: number): { left: number; top: number } {
  if (typeof window === "undefined") return { left, top };

  const maxLeft = Math.max(0, window.innerWidth - ORB_OVERLAY_SIZE);
  const maxTop = Math.max(0, window.innerHeight - ORB_OVERLAY_SIZE);
  return {
    left: Math.min(Math.max(0, left), maxLeft),
    top: Math.min(Math.max(0, top), maxTop),
  };
}

function dockedOrbOverlayPosition(): { left: number; top: number } {
  if (typeof window === "undefined") {
    return { left: ORB_OVERLAY_DOCK_MARGIN, top: ORB_OVERLAY_DOCK_MARGIN };
  }

  return clampOrbOverlayPosition(
    window.innerWidth - ORB_OVERLAY_SIZE - ORB_OVERLAY_DOCK_MARGIN,
    window.innerHeight - ORB_OVERLAY_SIZE - ORB_OVERLAY_DOCK_MARGIN,
  );
}

function getQueryParam(name: string): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get(name)?.trim() ?? "";
}

type VoiceLogEntry = {
  id: string;
  role: "operator" | "francis" | "system";
  text: string;
  tone: "wake" | "passive" | "noise" | "error";
  awareness?: string;
  forwardToChat?: boolean;
  responseExpected?: boolean;
  summary?: string;
  ts: number;
};

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

function resultTranscript(result: SpeechRecognitionResultLike): string {
  const first = result[0] ?? (typeof result.item === "function" ? result.item(0) : undefined);
  return normalizeVoiceTranscript(first?.transcript ?? "");
}

function browserTtsOptInEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const value = new URLSearchParams(window.location.search).get("francis_browser_tts")?.trim().toLowerCase() ?? "";
  return value === "1" || value === "true" || value === "yes";
}

function speakBrowserText(text: string, onDone: () => void): boolean {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  const clean = normalizeVoiceTranscript(text);
  if (!clean) return false;
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate = 0.94;
  utterance.pitch = 1;
  utterance.volume = 1;
  utterance.onend = onDone;
  utterance.onerror = onDone;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
  return true;
}

function VoiceTranscriptionPanel(props: { baseUrl: string }) {
  const client = useMemo(() => new FrancisVoiceClient(props.baseUrl), [props.baseUrl]);
  const browserTtsEnabled = useMemo(() => browserTtsOptInEnabled(), []);
  const recognitionRef = useRef<SpeechRecognitionAlternative | null>(null);
  const shouldListenRef = useRef(false);
  const soundHadSpeechRef = useRef(false);
  const soundHadTranscriptRef = useRef(false);
  const speakingRef = useRef(false);
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [awareness, setAwareness] = useState("idle");
  const [error, setError] = useState("");
  const [log, setLog] = useState<VoiceLogEntry[]>([]);

  const appendLog = useCallback((entry: Omit<VoiceLogEntry, "id" | "ts"> & { id?: string }) => {
    setLog((current) => [
      {
        id: entry.id || createVoiceTurnId("voice_log"),
        role: entry.role,
        text: entry.text,
        tone: entry.tone,
        awareness: entry.awareness,
        forwardToChat: entry.forwardToChat,
        responseExpected: entry.responseExpected,
        summary: entry.summary,
        ts: Math.floor(Date.now() / 1000),
      },
      ...current,
    ].slice(0, 18));
  }, []);

  useEffect(() => {
    if (!browserTtsEnabled && typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }, [browserTtsEnabled]);

  const speakReply = useCallback(
    (text: string, response: FrancisVoiceIngressResponse): boolean => {
      if (!shouldSpeakVoiceReplyWithBrowserTts(response, { browserTtsEnabled })) {
        if (typeof window !== "undefined" && "speechSynthesis" in window) {
          window.speechSynthesis.cancel();
        }
        speakingRef.current = false;
        setSpeaking(false);
        return false;
      }
      speakingRef.current = true;
      setSpeaking(true);
      const started = speakBrowserText(text, () => {
        speakingRef.current = false;
        setSpeaking(false);
      });
      if (!started) {
        speakingRef.current = false;
        setSpeaking(false);
      }
      return started;
    },
    [browserTtsEnabled],
  );

  const handleFinalTranscript = useCallback(
    async (rawTranscript: string) => {
      const transcript = normalizeVoiceTranscript(rawTranscript);
      if (!transcript) return;
      soundHadTranscriptRef.current = true;
      if (speakingRef.current) {
        const summary = summarizeVoiceTranscriptForOperator(transcript, { speaking: true });
        const turnId = createVoiceTurnId("chat_ui_voice_guard");
        setInterimTranscript("");
        appendLog({
          id: turnId,
          role: "operator",
          text: transcript,
          tone: summary.kind === "wake" ? "wake" : "passive",
          awareness: summary.awareness_state,
          forwardToChat: summary.forward_to_chat,
          responseExpected: summary.response_expected,
          summary: summary.summary,
        });
        if (summary.summary === "interrupt_only") {
          if (typeof window !== "undefined" && "speechSynthesis" in window) {
            window.speechSynthesis.cancel();
          }
          speakingRef.current = false;
          setSpeaking(false);
          setAwareness(summary.awareness_state);
          appendLog({
            role: "system",
            text: "Francis stop heard. Speech cancelled and the interrupted reply context was scrubbed.",
            tone: "wake",
            awareness: summary.awareness_state,
            forwardToChat: false,
            responseExpected: false,
            summary: "interrupt_only",
          });
          return;
        }
        setAwareness(summary.awareness_state);
        appendLog({
          role: "system",
          text: "Transcript held while Francis was speaking. Say Francis stop to interrupt.",
          tone: "noise",
          awareness: summary.awareness_state,
          forwardToChat: false,
          responseExpected: false,
          summary: "suppressed_while_speaking",
        });
        return;
      }
      const classification = summarizeVoiceTranscriptForOperator(transcript);
      const turnId = createVoiceTurnId("chat_ui_voice");
      setInterimTranscript("");
      setAwareness(classification.awareness_state);
      appendLog({
        id: turnId,
        role: "operator",
        text: transcript,
        tone: classification.kind === "wake" ? "wake" : "passive",
        awareness: classification.awareness_state,
        forwardToChat: classification.forward_to_chat,
        responseExpected: classification.response_expected,
        summary: classification.summary,
      });

      setBusy(true);
      try {
        const response = await client.recordTranscript({
          transcript,
          turn_id: turnId,
          forward_to_chat: classification.forward_to_chat,
          use_llm: classification.use_llm,
        });
        if (!classification.forward_to_chat) {
          setAwareness(response.ok ? "passive_transcript_recorded" : "passive_transcript_denied");
          return;
        }

        const reply = normalizeVoiceTranscript(response.reply || response.error || "Francis did not return a speakable reply.");
        const browserSpeechStarted = response.ok ? speakReply(reply, response) : false;
        appendLog({
          role: "francis",
          text: reply,
          tone: response.ok ? "wake" : "error",
          awareness: response.ok ? "reply_ready" : "reply_blocked",
          forwardToChat: false,
          responseExpected: false,
          summary: response.ok
            ? browserSpeechStarted
              ? "reply_spoken_browser_tts_opt_in"
              : "reply_text_ready_browser_tts_suppressed"
            : "reply_blocked",
        });
        setAwareness(response.ok ? "reply_ready" : "reply_blocked");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Voice bridge request failed.";
        setError(message);
        setAwareness("voice_bridge_error");
        appendLog({
          role: "system",
          text: message,
          tone: "error",
          awareness: "voice_bridge_error",
          forwardToChat: false,
          responseExpected: false,
          summary: "bridge_error",
        });
      } finally {
        setBusy(false);
      }
    },
    [appendLog, client, speakReply],
  );

  const stopListening = useCallback(() => {
    shouldListenRef.current = false;
    setListening(false);
    setInterimTranscript("");
    recognitionRef.current?.stop();
  }, []);

  const startListening = useCallback(() => {
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) {
      setError("Browser speech recognition is unavailable.");
      setAwareness("speech_recognition_unavailable");
      return;
    }

    setError("");
    shouldListenRef.current = true;
    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onstart = () => {
      setListening(true);
      setAwareness("listening");
    };
    recognition.onsoundstart = () => {
      soundHadSpeechRef.current = false;
      soundHadTranscriptRef.current = false;
      setAwareness("sound_observed");
    };
    recognition.onspeechstart = () => {
      soundHadSpeechRef.current = true;
      setAwareness("speech_observed");
    };
    recognition.onsoundend = () => {
      const sound = summarizeVoiceSoundForOperator({
        soundObserved: true,
        speechObserved: soundHadSpeechRef.current,
        transcript: soundHadTranscriptRef.current ? "speech" : "",
      });
      if (sound.kind === "noise") {
        setAwareness(sound.awareness_state);
        appendLog({
          role: "system",
          text: "Ambient sound observed.",
          tone: "noise",
          awareness: sound.awareness_state,
          forwardToChat: sound.forward_to_chat,
          responseExpected: sound.response_expected,
          summary: sound.summary,
        });
      }
    };
    recognition.onnomatch = () => {
      setAwareness("speech_not_matched");
    };
    recognition.onerror = (event) => {
      const summary = summarizeVoiceRecognitionErrorForOperator(event.error || event.message || "Speech recognition error.");
      setError(summary.is_error ? summary.operator_text : "");
      setAwareness(summary.awareness_state);
      appendLog({
        role: "system",
        text: summary.operator_text,
        tone: summary.tone,
        awareness: summary.awareness_state,
        forwardToChat: summary.forward_to_chat,
        responseExpected: summary.response_expected,
        summary: summary.summary,
      });
    };
    recognition.onresult = (event) => {
      let interim = "";
      const finals: string[] = [];
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = resultTranscript(result);
        if (!transcript) continue;
        soundHadTranscriptRef.current = true;
        if (result.isFinal) {
          finals.push(transcript);
        } else {
          interim = normalizeVoiceTranscript(`${interim} ${transcript}`);
        }
      }
      setInterimTranscript(interim);
      for (const transcript of finals) {
        void handleFinalTranscript(transcript);
      }
    };
    recognition.onend = () => {
      if (!shouldListenRef.current) {
        setListening(false);
        return;
      }
      try {
        recognition.start();
      } catch {
        setListening(false);
      }
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch (err) {
      shouldListenRef.current = false;
      setListening(false);
      setError(err instanceof Error ? err.message : "Speech recognition could not start.");
    }
  }, [appendLog, handleFinalTranscript]);

  useEffect(() => {
    return () => {
      shouldListenRef.current = false;
      recognitionRef.current?.abort();
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      speakingRef.current = false;
    };
  }, []);

  const statusTone = error ? "blocked" : listening ? "ready" : "neutral";

  return (
    <section
      style={{
        background: "rgba(9, 13, 20, 0.92)",
        border: "1px solid rgba(148, 163, 184, 0.32)",
        borderRadius: 18,
        marginTop: 22,
        padding: 22,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", flexWrap: "wrap", justifyContent: "space-between", gap: 16 }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ color: "#86efac", margin: 0, textTransform: "uppercase", letterSpacing: 1.4 }}>
            Voice / transcription
          </p>
          <h2 style={{ fontSize: 24, margin: "8px 0 8px" }}>Passive Listen Console</h2>
        </div>
        <button
          type="button"
          onClick={listening ? stopListening : startListening}
          style={{
            background: listening ? "#fecaca" : "#bbf7d0",
            border: 0,
            borderRadius: 12,
            color: "#0f172a",
            cursor: "pointer",
            fontWeight: 800,
            maxWidth: "100%",
            minWidth: 112,
            padding: "10px 14px",
          }}
        >
          {listening ? "Stop" : "Listen"}
        </button>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 16 }}>
        <Pill label="listen" value={listening ? "on" : "off"} tone={statusTone} />
        <Pill label="state" value={awareness} tone={statusTone} />
        <Pill label="bridge" value={busy ? "recording" : "ready"} tone={busy ? "neutral" : "ready"} />
        <Pill label="speech" value={speaking ? "speaking" : "idle"} tone={speaking ? "neutral" : "ready"} />
      </div>

      {error ? (
        <div style={{ border: "1px solid #fca5a5", borderRadius: 12, color: "#fecaca", marginTop: 16, padding: 12 }}>
          {error}
        </div>
      ) : null}

      <div
        style={{
          background: "rgba(2, 6, 23, 0.72)",
          border: "1px solid rgba(148, 163, 184, 0.24)",
          borderRadius: 12,
          color: interimTranscript ? "#e0f2fe" : "#94a3b8",
          marginTop: 16,
          minHeight: 56,
          padding: 14,
        }}
      >
        {interimTranscript || "No active transcript."}
      </div>

      <div style={{ display: "grid", gap: 10, marginTop: 16 }}>
        {log.length === 0 ? (
          <div style={{ color: "#94a3b8" }}>No voice turns recorded in this panel.</div>
        ) : (
          log.map((entry) => {
            const border =
              entry.tone === "wake"
                ? "#67e8f9"
                : entry.tone === "noise"
                  ? "#fde68a"
                  : entry.tone === "error"
                    ? "#fca5a5"
                    : "#64748b";
            return (
              <article
                key={entry.id}
                style={{
                  border: `1px solid ${border}`,
                  borderRadius: 12,
                  padding: "10px 12px",
                }}
              >
                <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>
                  {entry.role} / {entry.tone}
                </div>
                <div style={{ marginTop: 4 }}>{entry.text}</div>
                {entry.awareness || entry.summary ? (
                  <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 6 }}>
                    {entry.awareness ? <span>state {entry.awareness}</span> : null}
                    {entry.summary ? <span>route {entry.summary}</span> : null}
                    {entry.forwardToChat !== undefined ? <span>chat {entry.forwardToChat ? "yes" : "no"}</span> : null}
                    {entry.responseExpected !== undefined ? <span>reply {entry.responseExpected ? "yes" : "no"}</span> : null}
                  </div>
                ) : null}
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}

function joinStatusList(values: string[], fallback = "none"): string {
  return values.length ? values.join(", ") : fallback;
}

type CollaborationTranscriptEntry = CollaborationTranscript["items"][number];
type CollaborationReviewEntry = CollaborationReview["items"][number];
type CollaborationLearningEntry = CollaborationLearning["items"][number];
type CollaborationReadbackResult<T> = { ok: true; value: T } | { ok: false; message: string };

type CollaborationUiSession = {
  id: string;
  label: string;
  startedAt: string;
  endedAt: string;
  items: CollaborationTranscriptEntry[];
};

function collaborationCacheLabel(cache?: { status: string; ageMs: number | null }): string {
  if (!cache?.status || cache.status === "not_reported") return "";
  const age = typeof cache.ageMs === "number" ? ` ${Math.max(0, Math.round(cache.ageMs / 1000))}s` : "";
  return ` / cache ${cache.status}${age}`;
}

function collaborationShortId(value: string): string {
  if (!value) return "unknown";
  return value.length > 30 ? `${value.slice(0, 18)}...${value.slice(-8)}` : value;
}

function collaborationDirectionText(item: CollaborationTranscriptEntry): string {
  return (item.direction || `${item.sourceAgent}->${item.targetAgent}`).replace("->", " -> ");
}

function collaborationRelayToneText(display: ReturnType<typeof formatCollaborationRelayMessage>): string {
  if (display.tone === "driver") return "codex turn";
  if (display.tone === "guard") return "guard rewrite";
  if (display.tone === "audit") return "audit";
  return "conversation";
}

function collaborationConversationLayerText(display: ReturnType<typeof formatCollaborationRelayMessage>): string {
  if (display.tone === "driver") return "Codex Turn";
  if (display.tone === "guard") return "Conversation Guard";
  return "Conversation";
}

function collaborationTimeText(item: CollaborationTranscriptEntry): string {
  if (!item.createdAt) return "unknown time";
  const timePart = item.createdAt.includes("T") ? item.createdAt.split("T")[1] : item.createdAt;
  return timePart.split(".")[0] || item.createdAt;
}

function collaborationTimestamp(item: CollaborationTranscriptEntry): number {
  const parsed = Date.parse(item.createdAt);
  return Number.isFinite(parsed) ? parsed : 0;
}

function collaborationLearningTermText(item: CollaborationLearningEntry): string {
  return item.repeatedTerms.length ? item.repeatedTerms.join(", ") : "unclassified";
}

function collaborationLearningLatestTurnText(item: CollaborationLearningEntry): string {
  if (item.latestTurn && item.latestTurn !== item.turn) return `latest turn ${item.latestTurn}`;
  return `turn ${item.turn || "?"}`;
}

function collaborationReadbackErrorMessage(label: string, err: unknown): string {
  if (isAbortError(err)) return `${label} readback timed out. Showing last known data.`;
  return err instanceof Error ? `${label} readback failed: ${err.message}` : `${label} readback failed.`;
}

async function fetchCollaborationReadbackWithTimeout<T>(
  label: string,
  parentSignal: AbortSignal | undefined,
  fetcher: (signal: AbortSignal) => Promise<T>,
): Promise<CollaborationReadbackResult<T>> {
  const controller = new AbortController();
  const abortFromParent = () => controller.abort();
  if (parentSignal?.aborted) {
    controller.abort();
  } else {
    parentSignal?.addEventListener("abort", abortFromParent, { once: true });
  }
  const timeoutId = window.setTimeout(() => controller.abort(), COLLABORATION_READBACK_TIMEOUT_MS);
  try {
    return { ok: true, value: await fetcher(controller.signal) };
  } catch (err) {
    return { ok: false, message: collaborationReadbackErrorMessage(label, err) };
  } finally {
    window.clearTimeout(timeoutId);
    parentSignal?.removeEventListener("abort", abortFromParent);
  }
}

function collaborationSessionLabel(item: CollaborationTranscriptEntry): string {
  const parsed = Date.parse(item.createdAt);
  if (!Number.isFinite(parsed)) return item.createdAt || "session";
  const date = new Date(parsed);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function collaborationDirectionCountsText(counts: Record<string, number>): string {
  const parts = Object.entries(counts)
    .filter(([, count]) => count > 0)
    .map(([direction, count]) => `${direction} ${count}`);
  return parts.length ? parts.join(" / ") : "unknown";
}

function latestToggleReceiptForAgent(
  receipts: CollaborationAgentToggleReceipt[],
  agentId: string,
): CollaborationAgentToggleReceipt | null {
  for (let index = receipts.length - 1; index >= 0; index -= 1) {
    const receipt = receipts[index];
    if (receipt?.agent === agentId) return receipt;
  }
  return null;
}

function buildCollaborationSessions(items: CollaborationTranscriptEntry[]): CollaborationUiSession[] {
  const chronological = [...items]
    .sort((left, right) => collaborationTimestamp(left) - collaborationTimestamp(right));
  const sessions: CollaborationUiSession[] = [];
  for (const item of chronological) {
    const previous = sessions[sessions.length - 1];
    const itemTime = collaborationTimestamp(item);
    const previousTime = previous?.items.length ? collaborationTimestamp(previous.items[previous.items.length - 1]!) : 0;
    if (!previous || (itemTime && previousTime && itemTime - previousTime > COLLABORATION_SESSION_GAP_MS)) {
      sessions.push({
        id: `session-${item.createdAt || item.id}`,
        label: collaborationSessionLabel(item),
        startedAt: item.createdAt,
        endedAt: item.createdAt,
        items: [item],
      });
    } else {
      previous.items.push(item);
      previous.endedAt = item.createdAt;
    }
  }
  return sessions.reverse();
}

function CollaborationAgentsPanel(props: { baseUrl: string }) {
  const [status, setStatus] = useState<CollaborationAgentsStatus | null>(null);
  const [transcript, setTranscript] = useState<CollaborationTranscript | null>(null);
  const [sessionReadback, setSessionReadback] = useState<CollaborationSessions | null>(null);
  const [review, setReview] = useState<CollaborationReview | null>(null);
  const [learning, setLearning] = useState<CollaborationLearning | null>(null);
  const [runtimeHealth, setRuntimeHealth] = useState<CollaborationRuntimeHealth | null>(null);
  const [substrateReadiness, setSubstrateReadiness] = useState<CollaborationSubstrateReadiness | null>(null);
  const [bodyMap, setBodyMap] = useState<FrancisBodyMap | null>(null);
  const [trustLadder, setTrustLadder] = useState<FrancisTrustLadder | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyAgent, setBusyAgent] = useState("");
  const [error, setError] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [followLatest, setFollowLatest] = useState(true);
  const [showAuditReceipts, setShowAuditReceipts] = useState(false);
  const [showRelayPrompts, setShowRelayPrompts] = useState(false);
  const [showGuardReceipts, setShowGuardReceipts] = useState(DEFAULT_SHOW_GUARD_RECEIPTS);
  const requestInFlight = useRef<{ signal?: AbortSignal } | null>(null);
  const liveTranscriptScrollRef = useRef<HTMLDivElement | null>(null);
  const transcriptScrollRef = useRef<HTMLDivElement | null>(null);

  const loadStatus = useCallback(
    (signal?: AbortSignal, opts: { showLoading?: boolean } = {}) => {
      if (requestInFlight.current && !requestInFlight.current.signal?.aborted) return;
      const request = { signal };
      requestInFlight.current = request;
      if (opts.showLoading !== false) setLoading(true);
      setError("");
      void (async () => {
        const readbackWarnings: string[] = [];
        const nextStatus = await fetchCollaborationAgentsStatus({ baseUrl: props.baseUrl, signal });
        if (!signal?.aborted) {
          setStatus(nextStatus);
        }
        const [
          nextBodyMap,
          nextTrustLadder,
          nextTranscript,
          nextSessions,
          nextReview,
          nextLearning,
          nextRuntime,
          nextSubstrateReadiness,
        ] = await Promise.all([
          fetchCollaborationReadbackWithTimeout("Body map", signal, (readbackSignal) =>
            fetchFrancisBodyMap({ baseUrl: props.baseUrl, signal: readbackSignal }),
          ),
          fetchCollaborationReadbackWithTimeout("Trust ladder", signal, (readbackSignal) =>
            fetchFrancisTrustLadder({ baseUrl: props.baseUrl, limit: FRANCIS_TRUST_LADDER_LIMIT, signal: readbackSignal }),
          ),
          fetchCollaborationReadbackWithTimeout("Transcript", signal, (readbackSignal) =>
            fetchCollaborationTranscript({ baseUrl: props.baseUrl, limit: COLLABORATION_TRANSCRIPT_LIMIT, signal: readbackSignal }),
          ),
          fetchCollaborationReadbackWithTimeout("Session", signal, (readbackSignal) =>
            fetchCollaborationSessions({
              baseUrl: props.baseUrl,
              limit: 5,
              itemLimit: COLLABORATION_SESSION_ITEM_LIMIT,
              signal: readbackSignal,
            }),
          ),
          fetchCollaborationReadbackWithTimeout("Review", signal, (readbackSignal) =>
            fetchCollaborationReview({ baseUrl: props.baseUrl, limit: COLLABORATION_REVIEW_LIMIT, signal: readbackSignal }),
          ),
          fetchCollaborationReadbackWithTimeout("Learning", signal, (readbackSignal) =>
            fetchCollaborationLearning({ baseUrl: props.baseUrl, limit: COLLABORATION_LEARNING_LIMIT, signal: readbackSignal }),
          ),
          fetchCollaborationReadbackWithTimeout("Runtime", signal, (readbackSignal) =>
            fetchCollaborationRuntimeHealth({ baseUrl: props.baseUrl, signal: readbackSignal }),
          ),
          fetchCollaborationReadbackWithTimeout("Substrate readiness", signal, (readbackSignal) =>
            fetchCollaborationSubstrateReadiness({ baseUrl: props.baseUrl, signal: readbackSignal }),
          ),
        ]);
        if (!signal?.aborted) {
          if (nextBodyMap.ok) {
            setBodyMap(nextBodyMap.value);
          } else {
            readbackWarnings.push(nextBodyMap.message);
          }
          if (nextTrustLadder.ok) {
            setTrustLadder(nextTrustLadder.value);
          } else {
            readbackWarnings.push(nextTrustLadder.message);
          }
          if (nextTranscript.ok) {
            setTranscript((previous) => preserveCollaborationReadbackDuringWarming(previous, nextTranscript.value));
          } else {
            readbackWarnings.push(nextTranscript.message);
          }
          if (nextSessions.ok) {
            setSessionReadback((previous) => preserveCollaborationReadbackDuringWarming(previous, nextSessions.value));
          } else {
            readbackWarnings.push(nextSessions.message);
          }
          if (nextReview.ok) {
            setReview((previous) => preserveCollaborationReadbackDuringWarming(previous, nextReview.value));
          } else {
            readbackWarnings.push(nextReview.message);
          }
          if (nextLearning.ok) {
            setLearning((previous) => preserveCollaborationReadbackDuringWarming(previous, nextLearning.value));
          } else {
            readbackWarnings.push(nextLearning.message);
          }
          if (nextRuntime.ok) {
            setRuntimeHealth(nextRuntime.value);
          } else {
            readbackWarnings.push(nextRuntime.message);
          }
        }
        if (!signal?.aborted) {
          if (nextSubstrateReadiness.ok) {
            setSubstrateReadiness(nextSubstrateReadiness.value);
          } else {
            readbackWarnings.push(nextSubstrateReadiness.message);
          }
        }
        return readbackWarnings;
      })()
        .then((readbackWarnings) => {
          if (signal?.aborted) return;
          setError(readbackWarnings.join(" "));
        })
        .catch((err: unknown) => {
          if (signal?.aborted || isAbortError(err)) return;
          setError(err instanceof Error ? err.message : "Collaboration relay request failed.");
        })
        .finally(() => {
          if (requestInFlight.current !== request) return;
          requestInFlight.current = null;
          setLoading(false);
        });
    },
    [props.baseUrl],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadStatus(controller.signal);
    const pollWhenVisible = () => {
      if (document.hidden) return;
      loadStatus(controller.signal, { showLoading: false });
    };
    const refreshWhenVisible = () => {
      if (!document.hidden) loadStatus(controller.signal, { showLoading: false });
    };
    const pollId = window.setInterval(() => {
      pollWhenVisible();
    }, COLLABORATION_PANEL_POLL_MS);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      controller.abort();
      window.clearInterval(pollId);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [loadStatus]);

  const toggleAgent = useCallback(
    (agent: CollaborationAgent, enabled: boolean) => {
      const controller = new AbortController();
      setBusyAgent(agent.agent);
      setError("");
      void setCollaborationAgentEnabled({
        baseUrl: props.baseUrl,
        agent: agent.agent,
        enabled,
        actor: "chat_ui.system",
        reason: "operator toggled collaboration participant in Chat UI",
        signal: controller.signal,
      })
        .then((nextStatus) => setStatus(nextStatus))
        .catch((err: unknown) => {
          if (controller.signal.aborted || isAbortError(err)) return;
          setError(err instanceof Error ? err.message : "Collaboration agent toggle failed.");
        })
        .finally(() => setBusyAgent(""));
      return () => controller.abort();
    },
    [props.baseUrl],
  );

  const agents = status?.agents ?? [];
  const activeCount = agents.filter((agent) => agent.enabled).length;
  const operatorConsole = status?.operatorConsole;
  const toggleReceipts = status?.receipts ?? [];
  const latestToggleReceipts = [...toggleReceipts].slice(-4).reverse();
  const transcriptItems = transcript?.items ?? [];
  const transcriptAuditSummary = useMemo(() => collaborationTranscriptAuditSummary(transcriptItems), [transcriptItems]);
  const transcriptFilterText = `${transcriptAuditSummary.substantiveTurnCount} substantive / ${transcriptAuditSummary.driverPromptCount} Codex turns ${
    showRelayPrompts ? "shown" : "hidden"
  }`;
  const transcriptAuditText = transcriptAuditSummary.auditReceiptCount
    ? ` / ${transcriptAuditSummary.auditReceiptCount} audit ${showAuditReceipts ? "shown" : "hidden"}`
    : "";
  const transcriptGuardText = transcriptAuditSummary.guardReceiptCount
    ? ` / ${transcriptAuditSummary.guardReceiptCount} guard ${showGuardReceipts ? "shown" : "hidden"}`
    : "";
  const transcriptVisibility = useMemo(
    () =>
      filterCollaborationTranscriptItems(transcriptItems, {
        showAuditReceipts,
        showDriverPrompts: showRelayPrompts,
        showGuardReceipts,
      }),
    [showAuditReceipts, showGuardReceipts, showRelayPrompts, transcriptItems],
  );
  const sessionSourceItems = transcriptVisibility.items;
  const hiddenMechanicText = transcriptVisibility.hiddenMechanicCount
    ? ` / ${transcriptVisibility.hiddenMechanicCount} mechanics hidden`
    : "";
  const sessions = useMemo(() => buildCollaborationSessions(sessionSourceItems), [sessionSourceItems]);
  const sessionSummaries = sessionReadback?.items ?? [];
  const reviewItems = review?.items ?? [];
  const blockedReviewItems = reviewItems.filter((item) => item.buildDirectionGate.blocksBuildDirection);
  const latestBuildDirectionReview = reviewItems[0] ?? null;
  const latestBuildDirectionGate = latestBuildDirectionReview
    ? collaborationBuildDirectionGateSummary(latestBuildDirectionReview)
    : null;
  const latestImplementationReview = reviewItems[0] ? collaborationImplementationReviewSummary(reviewItems[0]) : null;
  const actionIntakeReviews = reviewItems
    .map((item) => ({ item, summary: collaborationActionIntakeSummary(item) }))
    .filter(({ summary }) => summary.applies);
  const latestActionIntakeReview = actionIntakeReviews[0]?.item ?? null;
  const latestActionIntakeProof = actionIntakeReviews[0]?.summary ?? null;
  const learningItems = learning?.items ?? [];
  const recurrenceProof = collaborationRuntimeRecurrenceSummary(runtimeHealth);
  const localModelResponseProof = collaborationRuntimeLocalModelResponseSummary(runtimeHealth);
  const reviewReceiptProof = collaborationRuntimeReviewReceiptSummary(runtimeHealth);
  const learningReceiptProof = collaborationRuntimeLearningReceiptSummary(runtimeHealth);
  const learningSignalProof = collaborationRuntimeLearningSignalSummary(runtimeHealth);
  const learningGuardProof = collaborationLearningGuardSummary(learning, runtimeHealth);
  const runtimeEffectiveWorkers = runtimeHealth?.helpers.reduce((sum, helper) => sum + helper.effectiveWorkerCount, 0) ?? 0;
  const runtimeProcessCount = runtimeHealth?.helpers.reduce((sum, helper) => sum + helper.processCount, 0) ?? 0;
  const runtimeProcessModels = Array.from(new Set((runtimeHealth?.helpers ?? []).map((helper) => helper.processModel).filter(Boolean)));
  const runtimeProcessModelLabel =
    runtimeProcessModels.length === 1 ? runtimeProcessModels[0] : runtimeProcessModels.length > 1 ? runtimeProcessModels.join(", ") : "unknown";
  const substrateSummary = substrateReadiness?.summary;
  const substrateChecklistItems = substrateReadiness?.checklist ?? [];
  const substrateChecklistProof = collaborationSubstrateChecklistSummary(substrateReadiness);
  const substrateBlockedItems = substrateReadiness?.checklist.filter((item) => item.blocksMainBuildPrompt && item.status !== "passed") ?? [];
  const substrateOpenOrbGaps = substrateReadiness?.openOrbGaps ?? [];
  const roadmapAlignment = substrateReadiness?.roadmapAlignment;
  const roadmapAlignmentBlocked = Boolean(roadmapAlignment?.blocksMainBuildPrompt || roadmapAlignment?.candidateOnlyUntilReview);
  const bodyMapSurfaces = bodyMap?.surfaces ?? [];
  const bodyMapQuest = bodyMap?.quest;
  const bodyCoverageReview = bodyMap?.coverageReview;
  const bodyMapUnsafeAuthority =
    bodyMapSurfaces.some(
      (surface) =>
        surface.grantsExecutionAuthority ||
        surface.grantsMutationAuthority ||
        surface.grantsApprovalAuthority ||
        surface.grantsMemoryWriteAuthority ||
        surface.grantsTrainingAuthority ||
        surface.capabilityExposure.grantsCapabilityAuthority,
    ) || Boolean(bodyMap?.summary.fullBodyAuthorityGranted);
  const trustLadderItems = trustLadder?.items ?? [];
  const trustLadderUnsafeAuthority =
    Boolean(trustLadder?.summary.grantsAnyAuthority) ||
    trustLadderItems.some(
      (item) =>
        item.actionBoundary.conversationCanExecuteAction ||
        item.actionBoundary.conversationCanApproveAction ||
        Boolean(item.governance.grants_execution_authority) ||
        Boolean(item.governance.grants_mutation_authority) ||
        Boolean(item.governance.grants_memory_write_authority) ||
        Boolean(item.governance.grants_training_authority),
    );
  const selectedSession = sessions.find((session) => session.id === selectedSessionId) ?? sessions[0] ?? null;
  const visibleTranscriptItems = selectedSession?.items ?? [];
  const liveTranscriptItems = visibleTranscriptItems;
  const latestSessionId = sessions[0]?.id ?? "";
  const selectedSessionReadback =
    sessionSummaries.find((session) => session.id === selectedSession?.id) ??
    (followLatest ? sessionSummaries[0] ?? null : null);
  const selectedSessionReviewGateSummary =
    selectedSessionReadback?.latestReviewGate.observed
      ? collaborationSessionReviewGateSummary(selectedSessionReadback.latestReviewGate)
      : null;
  const selectedSessionDisclosureSummary = selectedSessionReadback
    ? collaborationSessionTranscriptDisclosureSummary(selectedSessionReadback.transcriptDisclosure)
    : null;
  const latestLiveMessageId = liveTranscriptItems[liveTranscriptItems.length - 1]?.id ?? "";
  const latestMessageId = visibleTranscriptItems[visibleTranscriptItems.length - 1]?.id ?? "";

  useEffect(() => {
    if (!sessions.length) {
      if (selectedSessionId) setSelectedSessionId("");
      return;
    }
    if (followLatest || !selectedSessionId || !sessions.some((session) => session.id === selectedSessionId)) {
      setSelectedSessionId(sessions[0].id);
    }
  }, [followLatest, selectedSessionId, sessions]);

  useEffect(() => {
    const scroller = transcriptScrollRef.current;
    if (!scroller) return;
    scroller.scrollTop = scroller.scrollHeight;
  }, [latestMessageId, selectedSessionId, visibleTranscriptItems.length]);

  useEffect(() => {
    const scroller = liveTranscriptScrollRef.current;
    if (!scroller) return;
    scroller.scrollTop = scroller.scrollHeight;
  }, [latestLiveMessageId, selectedSessionId, liveTranscriptItems.length]);

  return (
    <section
      style={{
        background: "rgba(9, 13, 20, 0.92)",
        border: "1px solid rgba(148, 163, 184, 0.32)",
        borderRadius: 18,
        marginTop: 18,
        padding: 24,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", flexWrap: "wrap", justifyContent: "space-between", gap: 14 }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ color: "#67e8f9", margin: 0, textTransform: "uppercase", letterSpacing: 1.4 }}>
            Collaboration intelligence
          </p>
          <h2 style={{ fontSize: 24, margin: "8px 0 8px" }}>Agent Relay Controls</h2>
          <p style={{ color: "#cbd5e1", margin: 0, maxWidth: 820 }}>
            Operator-visible control for Codex, Claude, and local Ollama on the existing Francis relay.
          </p>
        </div>
        <button
          type="button"
          onClick={() => loadStatus(undefined)}
          disabled={loading}
          style={{
            background: "#e2e8f0",
            border: 0,
            borderRadius: 12,
            color: "#0f172a",
            cursor: loading ? "wait" : "pointer",
            fontWeight: 700,
            padding: "10px 14px",
          }}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {error ? (
        <div style={{ border: "1px solid #fca5a5", borderRadius: 12, color: "#fecaca", marginTop: 16, padding: 12 }}>
          {error}
        </div>
      ) : null}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 18 }}>
        <Pill label="active" value={`${activeCount}/${agents.length || 3}`} tone={activeCount > 0 ? "ready" : "blocked"} />
        <Pill label="relay" value={status?.relay || "unknown"} tone="neutral" />
        <Pill label="client operator" value={boolText(Boolean(operatorConsole?.clientCanBeOperatorConsole))} tone="neutral" />
        <Pill
          label="body map"
          value={bodyMap?.summary.fullBodyVisible ? "visible" : "unknown"}
          tone={bodyMap?.summary.fullBodyVisible ? "ready" : "neutral"}
        />
        <Pill
          label="trust ladder"
          value={bodyMap?.summary.trustLadderEnforced ? "enforced" : "pending"}
          tone={bodyMap?.summary.trustLadderEnforced ? "ready" : "neutral"}
        />
        <Pill
          label="coverage"
          value={bodyCoverageReview?.status || "unknown"}
          tone={bodyMap?.summary.coverageReviewed ? "ready" : "neutral"}
        />
        <Pill
          label="substrate"
          value={substrateReadiness?.status || "unknown"}
          tone={substrateSummary?.mainBuildPromptAllowed ? "ready" : substrateBlockedItems.length ? "blocked" : "neutral"}
        />
        <Pill
          label="client authority"
          value={boolText(Boolean(operatorConsole?.clientIsAutomaticExecutionAuthority))}
          tone={operatorConsole?.clientIsAutomaticExecutionAuthority ? "blocked" : "ready"}
        />
      </div>

      <div
        style={{
          background:
            learningGuardProof.tone === "blocked" ? "rgba(69, 10, 10, 0.26)" : "rgba(8, 47, 73, 0.28)",
          border: `1px solid ${
            learningGuardProof.tone === "blocked" ? "rgba(252, 165, 165, 0.58)" : "rgba(125, 211, 252, 0.4)"
          }`,
          borderRadius: 14,
          marginTop: 18,
          padding: 16,
        }}
      >
        <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between" }}>
          <div style={{ minWidth: 0 }}>
            <h3 style={{ fontSize: 20, margin: 0 }}>Current Learning Guard</h3>
            <p style={{ color: "#e2e8f0", margin: "8px 0 0", overflowWrap: "anywhere" }}>
              {learningGuardProof.promptPolicy}
            </p>
          </div>
          <span
            style={{
              border: `1px solid ${learningGuardProof.tone === "blocked" ? "#fca5a5" : "#67e8f9"}`,
              borderRadius: 999,
              color: learningGuardProof.tone === "blocked" ? "#fecaca" : "#cffafe",
              fontSize: 12,
              fontWeight: 700,
              padding: "4px 8px",
            }}
          >
            {learningGuardProof.badge}
          </span>
        </div>
        <div style={{ color: "#93c5fd", display: "flex", flexWrap: "wrap", fontSize: 13, gap: 10, marginTop: 10 }}>
          <span>failure {learningGuardProof.failureType}</span>
          <span>latest turn {learningGuardProof.latestTurn || "unknown"}</span>
          <span>topic {runtimeHealth?.collaborationLoop.latestTurn.topic || "unknown"}</span>
        </div>
        <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 10 }}>
          {learningGuardProof.detail.map((line) => (
            <span
              key={line}
              style={{
                background: "rgba(15, 23, 42, 0.62)",
                border: "1px solid rgba(148, 163, 184, 0.2)",
                borderRadius: 999,
                maxWidth: "100%",
                overflowWrap: "anywhere",
                padding: "4px 8px",
              }}
            >
              {line}
            </span>
          ))}
        </div>
      </div>

      <div
        style={{
          background: "rgba(8, 15, 26, 0.76)",
          border: `1px solid ${
            substrateSummary?.mainBuildPromptAllowed
              ? "rgba(110, 231, 183, 0.45)"
              : substrateBlockedItems.length
                ? "rgba(252, 165, 165, 0.5)"
                : "rgba(148, 163, 184, 0.28)"
          }`,
          borderRadius: 14,
          marginTop: 18,
          padding: 16,
        }}
      >
        <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between" }}>
          <h3 style={{ fontSize: 20, margin: 0 }}>Substrate Readiness</h3>
          <span style={{ color: substrateSummary?.mainBuildPromptAllowed ? "#6ee7b7" : "#fca5a5", fontSize: 13 }}>
            main build prompt {boolText(Boolean(substrateSummary?.mainBuildPromptAllowed))}
            {collaborationCacheLabel(substrateReadiness?.readbackCache)}
          </span>
        </div>
        <div
          style={{
            color: "#cbd5e1",
            display: "grid",
            gap: 12,
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            marginTop: 12,
          }}
        >
          <div>
            <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Wiring Only</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>
              {substrateSummary?.boundedWiringPercentComplete ?? 0}% / {boolText(Boolean(substrateSummary?.collaborationSubstrateWired))}
            </div>
          </div>
          <div>
            <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Gate</div>
            <div style={{ overflowWrap: "anywhere" }}>{substrateSummary?.mainBuildPromptGate || "unknown"}</div>
          </div>
          <div>
            <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Open Gaps</div>
            <div>{substrateSummary?.coverageOpenGapCount ?? 0}</div>
          </div>
          <div>
            <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>No Authority Granted</div>
            <div>{boolText(Boolean(substrateSummary?.noAuthorityGranted))}</div>
          </div>
        </div>
        <p style={{ color: "#e2e8f0", margin: "12px 0 0", overflowWrap: "anywhere" }}>
          {substrateReadiness?.nextAction || "Readiness readback is still loading."}
        </p>
        {roadmapAlignment ? (
          <div
            style={{
              borderTop: "1px solid rgba(148, 163, 184, 0.18)",
              marginTop: 14,
              paddingTop: 12,
            }}
          >
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between" }}>
              <span style={{ color: "#dbeafe", fontSize: 15, fontWeight: 700 }}>Roadmap Alignment</span>
              <span
                style={{
                  border: `1px solid ${roadmapAlignmentBlocked ? "#fca5a5" : "#6ee7b7"}`,
                  borderRadius: 999,
                  color: roadmapAlignmentBlocked ? "#fecaca" : "#d1fae5",
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 8px",
                }}
              >
                {roadmapAlignment.status || "unknown"}
              </span>
            </div>
            <div
              style={{
                color: "#cbd5e1",
                display: "grid",
                gap: 12,
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                marginTop: 10,
              }}
            >
              <div>
                <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Source Order</div>
                <div style={{ overflowWrap: "anywhere" }}>{roadmapAlignment.sourceOrder.join(" -> ") || "unknown"}</div>
              </div>
              <div>
                <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Prompt Gate</div>
                <div style={{ overflowWrap: "anywhere" }}>{roadmapAlignment.mainBuildPromptGate || "requires_alignment_review"}</div>
              </div>
              <div>
                <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Blocking Items</div>
                <div style={{ overflowWrap: "anywhere" }}>{roadmapAlignment.blockingItems.join(", ") || "none"}</div>
              </div>
            </div>
            <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 10 }}>
              <span>ledger first {boolText(roadmapAlignment.ledgerFirst)}</span>
              <span>ledger {boolText(roadmapAlignment.ledgerObserved)}</span>
              <span>manifest {boolText(roadmapAlignment.manifestObserved)}</span>
              <span>candidate only {boolText(roadmapAlignment.candidateOnlyUntilReview)}</span>
              <span>main build prompt {boolText(roadmapAlignment.mainBuildPromptAllowed)}</span>
              <span>execute {boolText(roadmapAlignment.grantsExecutionAuthority)}</span>
              <span>approve {boolText(roadmapAlignment.grantsApprovalAuthority)}</span>
              <span>memory write {boolText(roadmapAlignment.grantsMemoryWriteAuthority)}</span>
            </div>
            <div style={{ color: "#93c5fd", fontSize: 13, marginTop: 8, overflowWrap: "anywhere" }}>
              next {roadmapAlignment.nextCheck || substrateReadiness?.nextAction || "Read ledger and manifest before main build prompting."}
            </div>
          </div>
        ) : null}
        {substrateOpenOrbGaps.length ? (
          <div
            style={{
              borderTop: "1px solid rgba(148, 163, 184, 0.18)",
              marginTop: 14,
              paddingTop: 12,
            }}
          >
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between" }}>
              <span style={{ color: "#dbeafe", fontSize: 15, fontWeight: 700 }}>Open ORB Gaps</span>
              <span style={{ color: "#fecaca", fontSize: 13 }}>
                {substrateOpenOrbGaps.length} shown / gate {substrateSummary?.mainBuildPromptGate || "unknown"}
              </span>
            </div>
            <div
              style={{
                display: "grid",
                gap: 0,
                marginTop: 10,
                maxHeight: 280,
                overflowY: "auto",
              }}
            >
              {substrateOpenOrbGaps.map((gap) => (
                <div
                  key={`${gap.planeId}-${gap.bodySurfaceId}`}
                  style={{
                    borderBottom: "1px solid rgba(148, 163, 184, 0.16)",
                    display: "grid",
                    gap: 6,
                    padding: "10px 0",
                  }}
                >
                  <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
                    <span style={{ color: "#e2e8f0", fontWeight: 700, overflowWrap: "anywhere" }}>
                      {gap.planeId} {gap.planeName || gap.bodySurfaceId}
                    </span>
                    <span
                      style={{
                        background: gap.riskLevel === "high" ? "rgba(127, 29, 29, 0.24)" : "rgba(71, 85, 105, 0.28)",
                        border: `1px solid ${gap.riskLevel === "high" ? "rgba(252, 165, 165, 0.42)" : "rgba(148, 163, 184, 0.3)"}`,
                        borderRadius: 999,
                        color: gap.riskLevel === "high" ? "#fecaca" : "#cbd5e1",
                        fontSize: 12,
                        padding: "3px 8px",
                      }}
                    >
                      {gap.riskLevel || "risk"}
                    </span>
                  </div>
                  <div style={{ color: "#cbd5e1", fontSize: 13, overflowWrap: "anywhere" }}>{gap.riskStatement || "No risk statement."}</div>
                  <ul style={{ color: "#e2e8f0", display: "grid", gap: 4, listStyle: "none", margin: 0, padding: 0 }}>
                    {(gap.remainingGaps.length ? gap.remainingGaps : ["No remaining gap text."]).map((item) => (
                      <li key={item} style={{ fontSize: 13, overflowWrap: "anywhere" }}>
                        {item}
                      </li>
                    ))}
                  </ul>
                  <div style={{ color: "#93c5fd", fontSize: 12, overflowWrap: "anywhere" }}>
                    review {gap.nextReviewArtifact || "unknown"} / next {gap.recommendedNextAction || "review required"}
                  </div>
                  <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8 }}>
                    <span>blocks main build {boolText(gap.blocksMainBuildPrompt)}</span>
                    <span>execute {boolText(gap.grantsExecutionAuthority)}</span>
                    <span>approve {boolText(gap.grantsApprovalAuthority)}</span>
                    <span>memory write {boolText(gap.grantsMemoryWriteAuthority)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between", marginTop: 14 }}>
          <span style={{ color: "#dbeafe", fontSize: 15, fontWeight: 700 }}>Substrate Checklist</span>
          <span
            style={{
              border: `1px solid ${
                substrateChecklistProof.tone === "ready" ? "#6ee7b7" : substrateChecklistProof.tone === "blocked" ? "#fca5a5" : "#cbd5e1"
              }`,
              borderRadius: 999,
              color: substrateChecklistProof.tone === "blocked" ? "#fecaca" : "#d1fae5",
              fontSize: 12,
              fontWeight: 700,
              padding: "4px 8px",
            }}
          >
            {substrateChecklistProof.badge}
          </span>
        </div>
        <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 10 }}>
          {substrateChecklistProof.detail.map((item) => (
            <span
              key={item}
              style={{
                background: "rgba(15, 23, 42, 0.7)",
                border: "1px solid rgba(148, 163, 184, 0.2)",
                borderRadius: 999,
                maxWidth: "100%",
                overflowWrap: "anywhere",
                padding: "4px 8px",
              }}
            >
              {item}
            </span>
          ))}
        </div>
        <div
          style={{
            borderTop: "1px solid rgba(148, 163, 184, 0.18)",
            display: "grid",
            gap: 0,
            marginTop: 10,
            maxHeight: 260,
            overflowY: "auto",
          }}
        >
          {(substrateChecklistItems.length ? substrateChecklistItems : []).map((item) => (
            <div
              key={item.id || item.label}
              style={{
                borderBottom: "1px solid rgba(148, 163, 184, 0.16)",
                display: "grid",
                gap: 6,
                padding: "10px 0",
              }}
            >
              <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
                <span style={{ color: "#e2e8f0", fontWeight: 700, overflowWrap: "anywhere" }}>{item.label}</span>
                <span
                  style={{
                    background: item.status === "passed" ? "rgba(20, 83, 45, 0.28)" : "rgba(127, 29, 29, 0.24)",
                    border: `1px solid ${item.status === "passed" ? "rgba(110, 231, 183, 0.42)" : "rgba(252, 165, 165, 0.42)"}`,
                    borderRadius: 999,
                    color: item.status === "passed" ? "#d1fae5" : "#fecaca",
                    fontSize: 12,
                    padding: "3px 8px",
                  }}
                >
                  {item.status}
                </span>
              </div>
              <div style={{ color: "#cbd5e1", fontSize: 13, overflowWrap: "anywhere" }}>{item.detail}</div>
              <div style={{ color: "#93c5fd", fontSize: 12, overflowWrap: "anywhere" }}>evidence {item.evidence}</div>
              {item.blocksMainBuildPrompt ? (
                <div style={{ color: "#fecaca", fontSize: 12 }}>blocks main build prompt</div>
              ) : null}
            </div>
          ))}
        </div>
        <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
          <span>runtime {boolText(Boolean(substrateSummary?.runtimeHealthy))}</span>
          <span>trust {boolText(Boolean(substrateSummary?.trustLadderEnforced))}</span>
          <span>learning {boolText(Boolean(substrateSummary?.learningReceiptsBounded))}</span>
          <span>blocks {substrateBlockedItems.length}</span>
          <span>sources {(substrateReadiness?.requiredAlignmentSources ?? []).join(", ") || "unknown"}</span>
        </div>
      </div>

      {latestActionIntakeReview && latestActionIntakeProof ? (
        <div
          style={{
            background: "rgba(8, 15, 26, 0.76)",
            border: `1px solid ${latestActionIntakeProof.tone === "blocked" ? "rgba(252, 165, 165, 0.5)" : "rgba(110, 231, 183, 0.42)"}`,
            borderRadius: 14,
            marginTop: 22,
            padding: 16,
          }}
        >
          <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between" }}>
            <h3 style={{ fontSize: 20, margin: 0 }}>Action Intake Boundary</h3>
            <span
              style={{
                border: `1px solid ${latestActionIntakeProof.tone === "blocked" ? "#fca5a5" : "#6ee7b7"}`,
                borderRadius: 999,
                color: latestActionIntakeProof.tone === "blocked" ? "#fecaca" : "#d1fae5",
                fontSize: 12,
                fontWeight: 700,
                padding: "4px 8px",
              }}
            >
              {latestActionIntakeProof.badge}
            </span>
          </div>
          <p style={{ color: "#e2e8f0", margin: "12px 0 0", overflowWrap: "anywhere" }}>
            {latestActionIntakeReview.buildIssue?.statement ||
              "Typed or spoken operator direction enters Francis as a reviewed action candidate, not direct execution."}
          </p>
          <div
            style={{
              color: "#cbd5e1",
              display: "grid",
              gap: 12,
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              marginTop: 12,
            }}
          >
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Surface</div>
              <div style={{ overflowWrap: "anywhere" }}>{latestActionIntakeReview.concreteRepoSurface || "unknown"}</div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Review Artifact</div>
              <div style={{ overflowWrap: "anywhere" }}>{latestActionIntakeReview.reviewArtifact || "unknown"}</div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Gate</div>
              <div>{latestActionIntakeReview.buildDirectionGate.state || "advisory_review_required"}</div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Candidate Creation</div>
              <div>{latestActionIntakeProof.candidateLine}</div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>No Direct Authority</div>
              <div>{latestActionIntakeProof.directAuthorityLine}</div>
            </div>
          </div>
          <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 12 }}>
            {latestActionIntakeProof.detail.map((line) => (
              <span
                key={line}
                style={{
                  background: "rgba(15, 23, 42, 0.7)",
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  borderRadius: 999,
                  maxWidth: "100%",
                  overflowWrap: "anywhere",
                  padding: "4px 8px",
                }}
              >
                {line}
              </span>
            ))}
          </div>
          <div style={{ color: "#93c5fd", fontSize: 13, marginTop: 10, overflowWrap: "anywhere" }}>
            evidence {latestActionIntakeReview.surfaceVerification?.evidence || "mission ingress review evidence unavailable"}
          </div>
          <div style={{ color: "#cbd5e1", fontSize: 13, marginTop: 8, overflowWrap: "anywhere" }}>
            next {latestActionIntakeReview.reviewRecommendation?.nextCodexAction || "Inspect mission ingress before changing action-intake behavior."}
          </div>
        </div>
      ) : null}

      {latestBuildDirectionGate && latestBuildDirectionReview ? (
        <div
          style={{
            background:
              latestBuildDirectionGate.tone === "blocked" ? "rgba(69, 10, 10, 0.26)" : "rgba(8, 47, 73, 0.28)",
            border: `1px solid ${
              latestBuildDirectionGate.tone === "blocked" ? "rgba(252, 165, 165, 0.62)" : "rgba(103, 232, 249, 0.42)"
            }`,
            borderRadius: 14,
            marginTop: 22,
            padding: 16,
          }}
        >
          <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between" }}>
            <h3 style={{ fontSize: 20, margin: 0 }}>Latest Build Direction Gate</h3>
            <span
              style={{
                border: `1px solid ${latestBuildDirectionGate.tone === "blocked" ? "#fca5a5" : "#67e8f9"}`,
                borderRadius: 999,
                color: latestBuildDirectionGate.tone === "blocked" ? "#fecaca" : "#cffafe",
                fontSize: 12,
                fontWeight: 700,
                padding: "4px 8px",
              }}
            >
              {latestBuildDirectionGate.badge}
            </span>
          </div>
          <div style={{ color: "#93c5fd", display: "flex", flexWrap: "wrap", fontSize: 13, gap: 10, marginTop: 10 }}>
            <span>turn {latestBuildDirectionReview.turn || "?"}</span>
            <span>{collaborationShortId(latestBuildDirectionReview.insightId)}</span>
            <span>{latestBuildDirectionReview.reviewRecommendation.decision || "review pending"}</span>
          </div>
          <p style={{ color: "#e2e8f0", margin: "10px 0 0", overflowWrap: "anywhere" }}>{latestBuildDirectionGate.reason}</p>
          <dl
            style={{
              color: "#cbd5e1",
              display: "grid",
              gap: 12,
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              margin: "12px 0 0",
            }}
          >
            <div>
              <dt style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Review Artifact</dt>
              <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{latestBuildDirectionGate.artifact}</dd>
            </div>
            <div>
              <dt style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Surface</dt>
              <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{latestBuildDirectionGate.surface}</dd>
            </div>
            <div>
              <dt style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Source Receipts</dt>
              <dd style={{ margin: 0 }}>
                <ul style={{ display: "grid", gap: 4, listStyle: "none", margin: 0, padding: 0 }}>
                  {latestBuildDirectionGate.conflictingSourceLines.map((line) => (
                    <li key={line} style={{ overflowWrap: "anywhere" }}>
                      {line}
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          </dl>
          <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 12 }}>
            {latestBuildDirectionGate.detail.map((line) => (
              <span
                key={line}
                style={{
                  background: "rgba(15, 23, 42, 0.7)",
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  borderRadius: 999,
                  maxWidth: "100%",
                  overflowWrap: "anywhere",
                  padding: "4px 8px",
                }}
              >
                {line}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {latestImplementationReview ? (
        <div
          style={{
            background: "rgba(8, 15, 26, 0.76)",
            border: `1px solid ${latestImplementationReview.tone === "blocked" ? "rgba(252, 165, 165, 0.58)" : "rgba(110, 231, 183, 0.42)"}`,
            borderRadius: 14,
            marginTop: 22,
            padding: 16,
          }}
        >
          <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between" }}>
            <h3 style={{ fontSize: 20, margin: 0 }}>Codex Implementation Preflight</h3>
            <span
              style={{
                border: `1px solid ${latestImplementationReview.tone === "blocked" ? "#fca5a5" : "#6ee7b7"}`,
                borderRadius: 999,
                color: latestImplementationReview.tone === "blocked" ? "#fecaca" : "#d1fae5",
                fontSize: 12,
                fontWeight: 700,
                padding: "4px 8px",
              }}
            >
              {latestImplementationReview.badge}
            </span>
          </div>
          <p style={{ color: "#e2e8f0", margin: "10px 0 0", overflowWrap: "anywhere" }}>
            Read this typed review receipt before editing collaboration code; it remains advisory until Codex or the operator checks repo truth.
          </p>
          <div
            style={{
              color: "#cbd5e1",
              display: "grid",
              gap: 12,
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              marginTop: 12,
            }}
          >
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Preflight Receipt</div>
              <div style={{ overflowWrap: "anywhere" }}>{latestImplementationReview.artifact}</div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Review Item</div>
              <div style={{ overflowWrap: "anywhere" }}>
                {latestImplementationReview.preflight.reviewItemId || "unknown"}
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Review Route</div>
              <div style={{ overflowWrap: "anywhere" }}>
                {latestImplementationReview.preflight.reviewRoute || "/developer-bridge/collaboration-review?limit=1"}
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Surface</div>
              <div style={{ overflowWrap: "anywhere" }}>{latestImplementationReview.surface}</div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Next Codex Action</div>
              <div style={{ overflowWrap: "anywhere" }}>{latestImplementationReview.nextAction}</div>
            </div>
            {latestImplementationReview.conflictingSourceLines.length ? (
              <div>
                <div style={{ color: "#94a3b8", fontSize: 12, textTransform: "uppercase" }}>Blocking Source Receipts</div>
                <ul style={{ display: "grid", gap: 4, listStyle: "none", margin: 0, padding: 0 }}>
                  {latestImplementationReview.conflictingSourceLines.map((line) => (
                    <li key={line} style={{ overflowWrap: "anywhere" }}>
                      {line}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
          <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 12 }}>
            {latestImplementationReview.detail.map((line) => (
              <span
                key={line}
                style={{
                  background: "rgba(15, 23, 42, 0.7)",
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  borderRadius: 999,
                  maxWidth: "100%",
                  overflowWrap: "anywhere",
                  padding: "4px 8px",
                }}
              >
                {line}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div
        style={{
          background: "rgba(8, 15, 26, 0.76)",
          border: "1px solid rgba(125, 211, 252, 0.42)",
          borderRadius: 14,
          marginTop: 22,
          padding: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 20, margin: 0 }}>Live Conversation</h3>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>
            {liveTranscriptItems.length} shown / {transcriptFilterText}
            {transcriptAuditText}
            {transcriptGuardText}
            {hiddenMechanicText}
            {collaborationCacheLabel(transcript?.readbackCache)}
          </span>
        </div>
        {sessions.length || transcriptItems.length ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
            <button
              type="button"
              onClick={() => {
                setFollowLatest(true);
                if (latestSessionId) setSelectedSessionId(latestSessionId);
              }}
              style={{
                background: followLatest ? "#bfdbfe" : "rgba(15, 23, 42, 0.62)",
                border: "1px solid rgba(147, 197, 253, 0.42)",
                borderRadius: 10,
                color: followLatest ? "#0f172a" : "#dbeafe",
                cursor: "pointer",
                fontWeight: 700,
                padding: "7px 10px",
              }}
            >
              Live
            </button>
            {transcriptAuditSummary.auditReceiptCount ? (
              <button
                type="button"
                onClick={() => setShowAuditReceipts((current) => !current)}
                style={{
                  background: showAuditReceipts ? "rgba(251, 191, 36, 0.26)" : "rgba(15, 23, 42, 0.62)",
                  border: "1px solid rgba(251, 191, 36, 0.38)",
                  borderRadius: 10,
                  color: showAuditReceipts ? "#fde68a" : "#cbd5e1",
                  cursor: "pointer",
                  fontWeight: 700,
                  padding: "7px 10px",
                }}
              >
                Audit ({transcriptAuditSummary.auditReceiptCount})
              </button>
            ) : null}
            {transcriptAuditSummary.driverPromptCount ? (
              <button
                type="button"
                onClick={() => setShowRelayPrompts((current) => !current)}
                style={{
                  background: showRelayPrompts ? "rgba(103, 232, 249, 0.24)" : "rgba(15, 23, 42, 0.62)",
                  border: "1px solid rgba(103, 232, 249, 0.36)",
                  borderRadius: 10,
                  color: showRelayPrompts ? "#cffafe" : "#cbd5e1",
                  cursor: "pointer",
                  fontWeight: 700,
                  padding: "7px 10px",
                }}
              >
                Codex turns ({transcriptAuditSummary.driverPromptCount})
              </button>
            ) : null}
            {transcriptAuditSummary.guardReceiptCount ? (
              <button
                type="button"
                onClick={() => setShowGuardReceipts((current) => !current)}
                style={{
                  background: showGuardReceipts ? "rgba(251, 191, 36, 0.24)" : "rgba(15, 23, 42, 0.62)",
                  border: "1px solid rgba(251, 191, 36, 0.36)",
                  borderRadius: 10,
                  color: showGuardReceipts ? "#fde68a" : "#cbd5e1",
                  cursor: "pointer",
                  fontWeight: 700,
                  padding: "7px 10px",
                }}
              >
                Guard ({transcriptAuditSummary.guardReceiptCount})
              </button>
            ) : null}
            {sessions.map((session) => (
              <button
                key={`live-${session.id}`}
                type="button"
                onClick={() => {
                  setSelectedSessionId(session.id);
                  setFollowLatest(session.id === latestSessionId);
                }}
                style={{
                  background: selectedSession?.id === session.id ? "rgba(14, 165, 233, 0.26)" : "rgba(15, 23, 42, 0.62)",
                  border: "1px solid rgba(148, 163, 184, 0.28)",
                  borderRadius: 10,
                  color: "#e2e8f0",
                  cursor: "pointer",
                  padding: "7px 10px",
                }}
              >
                {session.label} ({session.items.length})
              </button>
            ))}
          </div>
        ) : null}
        {selectedSessionReadback ? (
          <div
            style={{
              background: "rgba(15, 23, 42, 0.48)",
              border: "1px solid rgba(125, 211, 252, 0.26)",
              borderRadius: 12,
              marginTop: 12,
              padding: "10px 12px",
            }}
          >
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 10 }}>
              <span style={{ color: "#a7f3d0", fontSize: 12, fontWeight: 700, textTransform: "uppercase" }}>Session</span>
              <span style={{ color: "#93c5fd", fontSize: 13 }}>{selectedSessionReadback.messageCount} messages</span>
              <span style={{ color: "#93c5fd", fontSize: 13 }}>{selectedSessionReadback.latestDirection || "unknown direction"}</span>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>
                {selectedSessionReadback.endedAt
                  ? collaborationTimeText({ createdAt: selectedSessionReadback.endedAt } as CollaborationTranscriptEntry)
                  : "unknown time"}
              </span>
            </div>
            <p style={{ color: "#e2e8f0", margin: "8px 0 0", overflowWrap: "anywhere" }}>
              {selectedSessionReadback.latestObjective || "No session objective."}
            </p>
            {selectedSessionReadback.latestPreview ? (
              <p style={{ color: "#cbd5e1", margin: "6px 0 0", overflowWrap: "anywhere" }}>{selectedSessionReadback.latestPreview}</p>
            ) : null}
            {selectedSessionDisclosureSummary ? (
              <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                <span
                  style={{
                    border: `1px solid ${selectedSessionDisclosureSummary.tone === "blocked" ? "#fca5a5" : "#6ee7b7"}`,
                    borderRadius: 999,
                    color: selectedSessionDisclosureSummary.tone === "blocked" ? "#fecaca" : "#bbf7d0",
                    fontSize: 12,
                    fontWeight: 700,
                    padding: "3px 8px",
                  }}
                >
                  {selectedSessionDisclosureSummary.badge}
                </span>
                {selectedSessionDisclosureSummary.detail.slice(0, 4).map((line) => (
                  <span key={`live-disclosure-${line}`} style={{ color: "#94a3b8", fontSize: 12 }}>
                    {line}
                  </span>
                ))}
              </div>
            ) : null}
            {selectedSessionReviewGateSummary ? (
              <div
                style={{
                  borderTop: "1px solid rgba(148, 163, 184, 0.18)",
                  marginTop: 10,
                  paddingTop: 10,
                }}
              >
                <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 }}>
                  <span
                    style={{
                      border: `1px solid ${selectedSessionReviewGateSummary.tone === "blocked" ? "#fca5a5" : "#67e8f9"}`,
                      borderRadius: 999,
                      color: selectedSessionReviewGateSummary.tone === "blocked" ? "#fecaca" : "#cffafe",
                      fontSize: 12,
                      fontWeight: 700,
                      padding: "3px 8px",
                    }}
                  >
                    {selectedSessionReviewGateSummary.badge}
                  </span>
                  <span style={{ color: "#93c5fd", fontSize: 12 }}>turn {selectedSessionReadback.latestReviewGate.turn || "?"}</span>
                  <span style={{ color: "#94a3b8", fontSize: 12 }}>
                    {selectedSessionReadback.latestReviewGate.buildIssueCode || "review gate"}
                  </span>
                </div>
                <dl style={{ color: "#cbd5e1", display: "grid", gap: 6, margin: "8px 0 0" }}>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Review Artifact</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{selectedSessionReviewGateSummary.artifact}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Surface</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{selectedSessionReviewGateSummary.surface}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Next Codex Action</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{selectedSessionReviewGateSummary.nextAction}</dd>
                  </div>
                </dl>
                <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 8 }}>
                  {selectedSessionReviewGateSummary.detail.map((line) => (
                    <span key={line}>{line}</span>
                  ))}
                </div>
              </div>
            ) : null}
            <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 8 }}>
              <span>participants {selectedSessionReadback.participants.join(", ") || "unknown"}</span>
              <span>directions {collaborationDirectionCountsText(selectedSessionReadback.directionCounts)}</span>
              <span>latest {collaborationShortId(selectedSessionReadback.latestItemId)}</span>
            </div>
          </div>
        ) : null}
        <div
          ref={liveTranscriptScrollRef}
          style={{
            display: "grid",
            gap: 10,
            marginTop: 12,
            maxHeight: 520,
            minHeight: liveTranscriptItems.length ? 260 : 0,
            overflowY: "auto",
            paddingRight: 4,
          }}
        >
          {liveTranscriptItems.length ? (
            liveTranscriptItems.map((item) => {
              const display = formatCollaborationRelayMessage(item);
              return (
                <article
                  key={`live-message-${item.id}`}
                  style={{
                    background: "rgba(15, 23, 42, 0.58)",
                    border: "1px solid rgba(148, 163, 184, 0.22)",
                    borderRadius: 12,
                    padding: "12px 14px",
                  }}
                >
                  <div style={{ color: "#93c5fd", display: "flex", flexWrap: "wrap", fontSize: 13, gap: 10 }}>
                    <span>{collaborationDirectionText(item)}</span>
                    <span>{collaborationTimeText(item)}</span>
                    <span>{collaborationRelayToneText(display)}</span>
                    {isCollaborationAuditReceipt(item) ? <span>audit ack</span> : null}
                    {display.compacted ? <span>compact receipt</span> : null}
                  </div>
                  <div
                    style={{
                      borderLeft: `3px solid ${
                        display.tone === "guard"
                          ? "#fbbf24"
                          : display.tone === "audit"
                            ? "#94a3b8"
                            : display.tone === "driver"
                              ? "#67e8f9"
                              : "#6ee7b7"
                      }`,
                      marginTop: 10,
                      paddingLeft: 10,
                    }}
                  >
                    <div style={{ color: "#a7f3d0", fontSize: 12, fontWeight: 700, textTransform: "uppercase" }}>
                      {collaborationConversationLayerText(display)}
                    </div>
                    <p style={{ color: "#e2e8f0", margin: "5px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>
                      {display.conversationText || display.summary}
                    </p>
                  </div>
                  {display.technicalText ? (
                    <details style={{ color: "#94a3b8", fontSize: 13, marginTop: 10 }}>
                      <summary style={{ cursor: "pointer" }}>Technical receipt</summary>
                      <p style={{ color: "#94a3b8", margin: "8px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>
                        {display.technicalText}
                      </p>
                    </details>
                  ) : null}
                </article>
              );
            })
          ) : (
            <div style={{ border: "1px solid rgba(148, 163, 184, 0.22)", borderRadius: 12, color: "#94a3b8", padding: 14 }}>
              {transcriptItems.length && transcriptVisibility.hiddenMechanicCount
                ? `No conversation entries visible. ${transcriptVisibility.hiddenMechanicCount} relay mechanics hidden by display metadata.`
                : "No relay transcript entries returned."}
            </div>
          )}
        </div>
      </div>

      <details
        style={{
          border: "1px solid rgba(148, 163, 184, 0.24)",
          borderRadius: 14,
          marginTop: 18,
          padding: "12px 14px",
        }}
      >
        <summary style={{ color: "#dbeafe", cursor: "pointer", fontSize: 16, fontWeight: 700 }}>
          Francis body map and trust ladder evidence
        </summary>
        <div style={{ display: "grid", gap: 22, marginTop: 14 }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 18, margin: 0 }}>Francis Body Map</h3>
          <span style={{ color: bodyMapUnsafeAuthority ? "#fca5a5" : "#6ee7b7", fontSize: 13 }}>
            quest {bodyMapQuest?.percentComplete ?? 0}%
            {collaborationCacheLabel(bodyMap?.readbackCache)}
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            marginTop: 12,
            maxHeight: 420,
            overflowY: "auto",
            paddingRight: 4,
          }}
        >
          <article
            style={{
              background: "rgba(15, 23, 42, 0.58)",
              border: "1px solid rgba(148, 163, 184, 0.22)",
              borderRadius: 12,
              padding: "12px 14px",
            }}
          >
            <dl style={{ color: "#cbd5e1", display: "grid", gap: 8, margin: 0 }}>
              <div>
                <dt style={{ color: "#94a3b8" }}>Identity</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                  {bodyMap?.identity.localIdentity || "francis1"} via {bodyMap?.identity.providerLane || "unknown"}
                </dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Phase</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                  {bodyMap?.phase.current || "unknown"} / {bodyMap?.phase.priority || "unknown"}
                </dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Latest Ledger</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{bodyMap?.evidence.latestLedgerEntry || "No ledger readback."}</dd>
              </div>
            </dl>
            <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
              <span>surfaces {bodyMap?.summary.surfaceCount ?? 0}</span>
              <span>connected {bodyMap?.summary.connectedOrPartialCount ?? 0}</span>
              <span>candidate {bodyMap?.summary.candidateCount ?? 0}</span>
              <span>runtime observed {boolText(Boolean(bodyMap?.summary.runtimeRestartObserved))}</span>
              <span>
                planes {bodyMap?.summary.canonicalPlaneCoveredCount ?? 0}/{bodyMap?.summary.canonicalPlaneCount ?? 0}
              </span>
              <span>gaps {bodyMap?.summary.coverageOpenGapCount ?? 0}</span>
              <span>visible {bodyMap?.exposureSummary.visibleSurfaceCount ?? bodyMap?.summary.surfaceCount ?? 0}</span>
              <span>exposed {bodyMap?.exposureSummary.connectedToLocalModelCount ?? 0}</span>
              <span>not exposed {bodyMap?.exposureSummary.notExposedSurfaceCount ?? 0}</span>
              <span>review required {bodyMap?.exposureSummary.reviewRequiredSurfaceCount ?? 0}</span>
              <span>metadata only {boolText(Boolean(bodyMap?.informationSafety.validatedReadback))}</span>
              <span>sensitive {bodyMap?.informationSafety.sensitiveSurfaceCount ?? 0}</span>
              <span>active grants {bodyMap?.summary.activeCapabilityGrantCount ?? 0}</span>
              <span>denied/revoked {bodyMap?.summary.deniedOrRevokedCapabilityCount ?? 0}</span>
              <span>authority {boolText(Boolean(bodyMap?.summary.fullBodyAuthorityGranted))}</span>
              <span>unsafe {boolText(bodyMapUnsafeAuthority)}</span>
            </div>
          </article>
          <article
            style={{
              background: "rgba(15, 23, 42, 0.58)",
              border: "1px solid rgba(148, 163, 184, 0.22)",
              borderRadius: 12,
              padding: "12px 14px",
            }}
          >
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>Quest</span>
              <span
                style={{
                  border: "1px solid #93c5fd",
                  borderRadius: 999,
                  color: "#bfdbfe",
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 8px",
                }}
              >
                {bodyMapQuest?.completedSteps ?? 0}/{bodyMapQuest?.totalSteps ?? 0}
              </span>
            </div>
            <p style={{ color: "#e2e8f0", margin: "8px 0 0", overflowWrap: "anywhere" }}>
              {bodyMapQuest?.title || "Whole-body awareness quest not loaded."}
            </p>
            <p style={{ color: "#94a3b8", margin: "8px 0 0", overflowWrap: "anywhere" }}>
              {bodyMapQuest?.estimatedTimeline || "No timeline reported."}
            </p>
            <div style={{ color: "#cbd5e1", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              {(bodyMapQuest?.steps ?? []).slice(0, 6).map((step) => (
                <span
                  key={step.id || step.label}
                  style={{
                    background: step.status === "completed" ? "rgba(20, 83, 45, 0.32)" : "rgba(71, 85, 105, 0.28)",
                    border: `1px solid ${step.status === "completed" ? "rgba(110, 231, 183, 0.5)" : "rgba(148, 163, 184, 0.28)"}`,
                    borderRadius: 999,
                    fontSize: 12,
                    maxWidth: "100%",
                    overflowWrap: "anywhere",
                    padding: "4px 8px",
                  }}
                >
                  {step.label} / {step.status}
                </span>
              ))}
            </div>
          </article>
          <article
            style={{
              background: "rgba(15, 23, 42, 0.58)",
              border: "1px solid rgba(148, 163, 184, 0.22)",
              borderRadius: 12,
              padding: "12px 14px",
            }}
          >
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>Coverage</span>
              <span
                style={{
                  border: "1px solid #67e8f9",
                  borderRadius: 999,
                  color: "#a5f3fc",
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 8px",
                }}
              >
                {bodyCoverageReview?.coveredPlaneCount ?? 0}/{bodyCoverageReview?.planeCount ?? 0}
              </span>
            </div>
            <p style={{ color: "#e2e8f0", margin: "8px 0 0", overflowWrap: "anywhere" }}>
              {bodyCoverageReview?.status || "Coverage review not loaded."}
            </p>
            <p style={{ color: "#94a3b8", margin: "8px 0 0", overflowWrap: "anywhere" }}>
              {bodyCoverageReview?.canonicalSource || "No canonical source reported."}
            </p>
            <div style={{ color: "#cbd5e1", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              <span>open gaps {bodyCoverageReview?.openGapCount ?? 0}</span>
              <span>capability complete {boolText(Boolean(bodyCoverageReview?.capabilityComplete))}</span>
              <span>execute {boolText(Boolean(bodyCoverageReview?.grantsExecutionAuthority))}</span>
              <span>missing {(bodyCoverageReview?.missingPlaneIds ?? []).join(", ") || "none"}</span>
            </div>
            <div
              style={{
                color: "#94a3b8",
                display: "grid",
                gap: 8,
                marginTop: 10,
                maxHeight: 210,
                overflowY: "auto",
              }}
            >
              {(bodyCoverageReview?.items ?? []).map((item) => (
                <div
                  key={item.planeId}
                  style={{
                    background: "rgba(15, 23, 42, 0.6)",
                    border: "1px solid rgba(148, 163, 184, 0.22)",
                    borderRadius: 8,
                    maxWidth: "100%",
                    overflowWrap: "anywhere",
                    padding: "8px 10px",
                  }}
                >
                  <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
                    <strong style={{ color: "#e2e8f0" }}>
                      {item.planeId} / {item.currentPosture}
                    </strong>
                    <span style={{ color: item.riskLevel === "high" ? "#fecaca" : "#fde68a", fontSize: 12 }}>
                      risk {item.riskLevel || "unknown"}
                    </span>
                  </div>
                  <p style={{ color: "#cbd5e1", margin: "6px 0 0" }}>{item.riskStatement || item.remainingGaps[0] || "No risk statement."}</p>
                  <p style={{ color: "#94a3b8", fontSize: 12, margin: "6px 0 0" }}>
                    artifact {item.nextReviewArtifact || item.bodySurfaceId || "unknown"}
                  </p>
                </div>
              ))}
            </div>
          </article>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            marginTop: 12,
            maxHeight: 260,
            overflowY: "auto",
          }}
        >
          {bodyMapSurfaces.length ? (
            bodyMapSurfaces.map((surface) => {
              const surfaceExposure = francisBodySurfaceExposureSummary(surface);
              return (
              <article
                key={surface.id}
                style={{
                  background: "rgba(15, 23, 42, 0.48)",
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  borderRadius: 12,
                  padding: "10px 12px",
                }}
              >
                <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
                  <strong style={{ color: "#e2e8f0" }}>{surface.label}</strong>
                  <span style={{ color: surfaceExposure.tone === "blocked" ? "#fecaca" : "#93c5fd", fontSize: 12 }}>
                    {surfaceExposure.badge}
                  </span>
                </div>
                <p style={{ color: "#cbd5e1", margin: "8px 0 0", overflowWrap: "anywhere" }}>{surface.description}</p>
                <dl style={{ color: "#cbd5e1", display: "grid", gap: 6, margin: "8px 0 0" }}>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Boundary</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{surfaceExposure.boundary}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Evidence</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{surfaceExposure.evidenceLine}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Authority</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{surfaceExposure.authorityLine}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Capability Exposure</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{surfaceExposure.capabilityLine}</dd>
                  </div>
                </dl>
                <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 8 }}>
                  {surfaceExposure.detail.map((line) => (
                    <span key={line}>{line}</span>
                  ))}
                </div>
              </article>
              );
            })
          ) : (
            <div style={{ border: "1px solid rgba(148, 163, 184, 0.22)", borderRadius: 12, color: "#94a3b8", padding: 14 }}>
              No body-map surfaces returned.
            </div>
          )}
        </div>
      </div>

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 18, margin: 0 }}>Francis Trust Ladder</h3>
          <span style={{ color: trustLadderUnsafeAuthority ? "#fca5a5" : "#6ee7b7", fontSize: 13 }}>
            {trustLadderItems.length} needs{collaborationCacheLabel(trustLadder?.readbackCache)}
          </span>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
          {(trustLadder?.summary.allowedDecisions ?? ["wire_existing", "build_missing", "tune_prompt_guard", "reject_as_drift"]).map(
            (decision) => (
              <span
                key={decision}
                style={{
                  background: "rgba(15, 23, 42, 0.58)",
                  border: "1px solid rgba(148, 163, 184, 0.24)",
                  borderRadius: 999,
                  color: "#cbd5e1",
                  fontSize: 12,
                  padding: "4px 8px",
                }}
              >
                {decision} {trustLadder?.summary.decisionCounts[decision] ?? 0}
              </span>
            ),
          )}
          <span
            style={{
              background: trustLadderUnsafeAuthority ? "rgba(127, 29, 29, 0.28)" : "rgba(20, 83, 45, 0.24)",
              border: `1px solid ${trustLadderUnsafeAuthority ? "rgba(252, 165, 165, 0.5)" : "rgba(110, 231, 183, 0.45)"}`,
              borderRadius: 999,
              color: trustLadderUnsafeAuthority ? "#fecaca" : "#d1fae5",
              fontSize: 12,
              padding: "4px 8px",
            }}
          >
            no authority {boolText(!trustLadderUnsafeAuthority)}
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            marginTop: 12,
            maxHeight: 320,
            overflowY: "auto",
          }}
        >
          {trustLadderItems.length ? (
            trustLadderItems.map((item) => (
              <article
                key={item.id || item.sourceReviewItemId}
                style={{
                  background: "rgba(15, 23, 42, 0.5)",
                  border: "1px solid rgba(148, 163, 184, 0.22)",
                  borderRadius: 12,
                  padding: "10px 12px",
                }}
              >
                <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
                  <strong style={{ color: "#e2e8f0", overflowWrap: "anywhere" }}>{item.decision || "unclassified"}</strong>
                  <span style={{ color: "#93c5fd", fontSize: 12 }}>{item.currentAccessMode} {"->"} {item.requestedAccessMode}</span>
                </div>
                <p style={{ color: "#cbd5e1", margin: "8px 0 0", overflowWrap: "anywhere" }}>{item.needStatement || item.topic}</p>
                <dl style={{ color: "#94a3b8", display: "grid", gap: 6, margin: "8px 0 0" }}>
                  <div>
                    <dt>Surface</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{item.requestedSurface || "unknown"}</dd>
                  </div>
                  <div>
                    <dt>Trust Gate</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{item.nextTrustGate || "review required"}</dd>
                  </div>
                  <div>
                    <dt>Codex Action</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{item.recommendedNextAction || "Inspect the typed receipt."}</dd>
                  </div>
                </dl>
                <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 8 }}>
                  <span>surface {item.surfaceVerification.status || "unknown"}</span>
                  <span>execute {boolText(item.actionBoundary.conversationCanExecuteAction)}</span>
                  <span>approve {boolText(item.actionBoundary.conversationCanApproveAction)}</span>
                </div>
              </article>
            ))
          ) : (
            <div style={{ border: "1px solid rgba(148, 163, 184, 0.22)", borderRadius: 12, color: "#94a3b8", padding: 14 }}>
              No trust-ladder needs returned.
            </div>
          )}
        </div>
      </div>
        </div>
      </details>

      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", marginTop: 18 }}>
        {agents.map((agent) => {
          const busy = busyAgent === agent.agent;
          const latestToggle = latestToggleReceiptForAgent(toggleReceipts, agent.agent);
          const currentToggleProof = agent.currentToggleProof;
          const toggleProof = latestToggle?.operatorToggleProof ?? currentToggleProof;
          return (
            <article
              key={agent.agent}
              style={{
                border: "1px solid rgba(148, 163, 184, 0.28)",
                borderRadius: 14,
                padding: 14,
                background: agent.enabled ? "rgba(20, 83, 45, 0.18)" : "rgba(71, 85, 105, 0.16)",
              }}
            >
              <label style={{ alignItems: "center", display: "flex", gap: 10, justifyContent: "space-between" }}>
                <span>
                  <strong>{agent.label}</strong>
                  <span style={{ color: "#94a3b8", display: "block", fontSize: 13 }}>{agent.participantKind}</span>
                </span>
                <input
                  type="checkbox"
                  checked={agent.enabled}
                  disabled={busy}
                  onChange={(event) => toggleAgent(agent, event.currentTarget.checked)}
                  aria-label={`${agent.label} collaboration enabled`}
                  style={{ height: 20, width: 20 }}
                />
              </label>
              <dl style={{ color: "#cbd5e1", display: "grid", gap: 6, margin: "12px 0 0" }}>
                <div>
                  <dt style={{ color: "#94a3b8" }}>Authority</dt>
                  <dd style={{ margin: 0 }}>{agent.authority || "relay_only"}</dd>
                </div>
                <div>
                  <dt style={{ color: "#94a3b8" }}>Runner</dt>
                  <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{agent.localRunner || "external client"}</dd>
                </div>
                {latestToggle ? (
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Last Toggle</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                      {boolText(latestToggle.previousEnabled)} {"->"} {boolText(latestToggle.enabled)} by{" "}
                      {latestToggle.actor || "unknown"} ({collaborationShortId(latestToggle.receiptId)})
                    </dd>
                  </div>
                ) : null}
                {toggleProof ? (
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Current Toggle Proof</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                      {currentToggleProof.proofStatus}: {currentToggleProof.source || "unknown"}{" "}
                      {currentToggleProof.receiptId ? `(${collaborationShortId(currentToggleProof.receiptId)})` : ""}
                      {" / "}actor {boolText(currentToggleProof.actorRecorded)} / reason{" "}
                      {boolText(currentToggleProof.reasonRecorded)} / state {boolText(currentToggleProof.previousEnabled)} {"->"}{" "}
                      {boolText(currentToggleProof.currentEnabled)}
                    </dd>
                  </div>
                ) : null}
              </dl>
              <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 10 }}>
                <span>execute {boolText(Boolean(latestToggle?.governance.executes_prompt) || currentToggleProof.grantsExecutionAuthority)}</span>
                <span>model {boolText(Boolean(latestToggle?.governance.calls_model))}</span>
                <span>operator console {boolText(Boolean(toggleProof?.operatorConsoleActor))}</span>
                <span>legacy projection {boolText(currentToggleProof.legacyProjection)}</span>
                <span>capability authority {boolText(Boolean(toggleProof?.provesCapabilityAuthority))}</span>
                <span>approval {boolText(Boolean(toggleProof?.grantsApprovalAuthority))}</span>
                <span>
                  memory write{" "}
                  {boolText(Boolean(latestToggle?.governance.grants_memory_write_authority) || currentToggleProof.grantsMemoryWriteAuthority)}
                </span>
              </div>
            </article>
          );
        })}
      </div>

      <details
        style={{
          border: "1px solid rgba(148, 163, 184, 0.24)",
          borderRadius: 14,
          marginTop: 18,
          padding: "12px 14px",
        }}
      >
        <summary style={{ color: "#dbeafe", cursor: "pointer", fontSize: 16, fontWeight: 700 }}>
          Technical receipts and review history
        </summary>
        <div style={{ display: "grid", gap: 22, marginTop: 14 }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 18, margin: 0 }}>Toggle Receipts</h3>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>{latestToggleReceipts.length} latest / read only</span>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            marginTop: 12,
          }}
        >
          {latestToggleReceipts.length ? (
            latestToggleReceipts.map((receipt) => (
              <article
                key={receipt.receiptId || `${receipt.agent}-${receipt.createdAt}`}
                style={{
                  background: "rgba(15, 23, 42, 0.58)",
                  border: "1px solid rgba(148, 163, 184, 0.22)",
                  borderRadius: 12,
                  padding: "12px 14px",
                }}
              >
                <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 }}>
                  <span
                    style={{
                      border: `1px solid ${receipt.enabled ? "#6ee7b7" : "#fca5a5"}`,
                      borderRadius: 999,
                      color: receipt.enabled ? "#d1fae5" : "#fecaca",
                      fontSize: 12,
                      fontWeight: 700,
                      padding: "3px 8px",
                    }}
                  >
                    {receipt.agent} {boolText(receipt.previousEnabled)} {"->"} {boolText(receipt.enabled)}
                  </span>
                  <span style={{ color: "#93c5fd", fontSize: 12 }}>{collaborationShortId(receipt.receiptId)}</span>
                </div>
                <dl style={{ color: "#cbd5e1", display: "grid", gap: 6, margin: "10px 0 0" }}>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Actor</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{receipt.actor || "unknown"}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Reason</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{receipt.reason || "No reason recorded."}</dd>
                  </div>
                </dl>
                <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
                  <span>execute {boolText(Boolean(receipt.governance.executes_prompt))}</span>
                  <span>model {boolText(Boolean(receipt.governance.calls_model))}</span>
                  <span>memory write {boolText(Boolean(receipt.governance.grants_memory_write_authority))}</span>
                </div>
              </article>
            ))
          ) : (
            <div style={{ color: "#94a3b8" }}>No participant toggle receipts recorded yet.</div>
          )}
        </div>
      </div>

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 18, margin: 0 }}>Runtime Health</h3>
          <span style={{ color: runtimeHealth?.status === "healthy" ? "#6ee7b7" : "#fca5a5", fontSize: 13 }}>
            {runtimeHealth?.status || "unknown"}
            {collaborationCacheLabel(runtimeHealth?.readbackCache)}
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            marginTop: 12,
          }}
        >
          <article
            style={{
              background: "rgba(15, 23, 42, 0.58)",
              border: "1px solid rgba(148, 163, 184, 0.22)",
              borderRadius: 12,
              padding: "12px 14px",
            }}
          >
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>Recurrence Proof</span>
              <span
                style={{
                  border: `1px solid ${
                    recurrenceProof.tone === "ready" ? "#6ee7b7" : recurrenceProof.tone === "blocked" ? "#fca5a5" : "#cbd5e1"
                  }`,
                  borderRadius: 999,
                  color: recurrenceProof.tone === "blocked" ? "#fecaca" : "#d1fae5",
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 8px",
                }}
              >
                {recurrenceProof.badge}
              </span>
            </div>
            <div style={{ color: "#cbd5e1", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              {recurrenceProof.detail.map((item) => (
                <span
                  key={item}
                  style={{
                    background: "rgba(15, 23, 42, 0.7)",
                    border: "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: 999,
                    fontSize: 12,
                    padding: "4px 8px",
                  }}
                >
                  {item}
                </span>
              ))}
            </div>
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between", marginTop: 14 }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>Latest Model Response</span>
              <span
                style={{
                  border: `1px solid ${
                    localModelResponseProof.tone === "ready"
                      ? "#6ee7b7"
                      : localModelResponseProof.tone === "blocked"
                        ? "#fca5a5"
                        : "#cbd5e1"
                  }`,
                  borderRadius: 999,
                  color: localModelResponseProof.tone === "blocked" ? "#fecaca" : "#d1fae5",
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 8px",
                }}
              >
                {localModelResponseProof.badge}
              </span>
            </div>
            <div style={{ color: "#cbd5e1", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              {localModelResponseProof.detail.map((item) => (
                <span
                  key={item}
                  style={{
                    background: "rgba(15, 23, 42, 0.7)",
                    border: "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: 999,
                    fontSize: 12,
                    maxWidth: "100%",
                    overflowWrap: "anywhere",
                    padding: "4px 8px",
                  }}
                >
                  {item}
                </span>
              ))}
            </div>
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between", marginTop: 14 }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>Review Receipt</span>
              <span
                style={{
                  border: `1px solid ${
                    reviewReceiptProof.tone === "ready" ? "#6ee7b7" : reviewReceiptProof.tone === "blocked" ? "#fca5a5" : "#cbd5e1"
                  }`,
                  borderRadius: 999,
                  color: reviewReceiptProof.tone === "blocked" ? "#fecaca" : "#d1fae5",
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 8px",
                }}
              >
                {reviewReceiptProof.badge}
              </span>
            </div>
            <div style={{ color: "#cbd5e1", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              {reviewReceiptProof.detail.map((item) => (
                <span
                  key={item}
                  style={{
                    background: "rgba(15, 23, 42, 0.7)",
                    border: "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: 999,
                    fontSize: 12,
                    maxWidth: "100%",
                    overflowWrap: "anywhere",
                    padding: "4px 8px",
                  }}
                >
                  {item}
                </span>
              ))}
            </div>
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between", marginTop: 14 }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>Learning Receipt</span>
              <span
                style={{
                  border: `1px solid ${
                    learningReceiptProof.tone === "ready" ? "#6ee7b7" : learningReceiptProof.tone === "blocked" ? "#fca5a5" : "#cbd5e1"
                  }`,
                  borderRadius: 999,
                  color: learningReceiptProof.tone === "blocked" ? "#fecaca" : "#d1fae5",
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 8px",
                }}
              >
                {learningReceiptProof.badge}
              </span>
            </div>
            <div style={{ color: "#cbd5e1", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              {learningReceiptProof.detail.map((item) => (
                <span
                  key={item}
                  style={{
                    background: "rgba(15, 23, 42, 0.7)",
                    border: "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: 999,
                    fontSize: 12,
                    maxWidth: "100%",
                    overflowWrap: "anywhere",
                    padding: "4px 8px",
                  }}
                >
                  {item}
                </span>
              ))}
            </div>
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between", marginTop: 14 }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>Learning Signal</span>
              <span
                style={{
                  border: `1px solid ${
                    learningSignalProof.tone === "ready" ? "#6ee7b7" : learningSignalProof.tone === "blocked" ? "#fca5a5" : "#cbd5e1"
                  }`,
                  borderRadius: 999,
                  color: learningSignalProof.tone === "blocked" ? "#fecaca" : "#d1fae5",
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 8px",
                }}
              >
                {learningSignalProof.badge}
              </span>
            </div>
            <div style={{ color: "#cbd5e1", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
              {learningSignalProof.detail.map((item) => (
                <span
                  key={item}
                  style={{
                    background: "rgba(15, 23, 42, 0.7)",
                    border: "1px solid rgba(148, 163, 184, 0.2)",
                    borderRadius: 999,
                    fontSize: 12,
                    maxWidth: "100%",
                    overflowWrap: "anywhere",
                    padding: "4px 8px",
                  }}
                >
                  {item}
                </span>
              ))}
            </div>
            <dl style={{ color: "#cbd5e1", display: "grid", gap: 8, margin: "12px 0 0" }}>
              <div>
                <dt style={{ color: "#94a3b8" }}>Recurrence</dt>
                <dd style={{ margin: 0 }}>{runtimeHealth?.collaborationLoop.recurrenceState || "unknown"}</dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Turn</dt>
                <dd style={{ margin: 0 }}>{runtimeHealth?.collaborationLoop.turnCount || 0}</dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Topic</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                  {runtimeHealth?.collaborationLoop.latestTurn.topic || "No runtime topic reported."}
                </dd>
              </div>
            </dl>
          </article>
          <article
            style={{
              background: "rgba(15, 23, 42, 0.58)",
              border: "1px solid rgba(148, 163, 184, 0.22)",
              borderRadius: 12,
              padding: "12px 14px",
            }}
          >
            <dl style={{ color: "#cbd5e1", display: "grid", gap: 8, margin: 0 }}>
              <div>
                <dt style={{ color: "#94a3b8" }}>Last Prompt</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                  {collaborationShortId(runtimeHealth?.collaborationLoop.lastCodexPromptId || "")}
                </dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Last Reply</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                  {collaborationShortId(runtimeHealth?.collaborationLoop.lastOllamaPromptId || "")}
                </dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Turn Gap</dt>
                <dd style={{ margin: 0 }}>{runtimeHealth?.collaborationLoop.turnGapRemainingSeconds ?? 0}s</dd>
              </div>
            </dl>
          </article>
          <article
            style={{
              background: "rgba(15, 23, 42, 0.58)",
              border: "1px solid rgba(148, 163, 184, 0.22)",
              borderRadius: 12,
              padding: "12px 14px",
            }}
          >
            <div style={{ color: "#94a3b8", fontSize: 13, marginBottom: 8 }}>
              helpers {runtimeHealth?.helpers.filter((helper) => helper.running).length || 0}/{runtimeHealth?.desiredCount || 0}
              {" / "}workers {runtimeEffectiveWorkers}/{runtimeHealth?.desiredCount || 0}
            </div>
            <div style={{ color: "#cbd5e1", display: "flex", flexWrap: "wrap", gap: 8 }}>
              {(runtimeHealth?.helpers ?? []).map((helper) => (
                <span
                  key={helper.name}
                  style={{
                    border: `1px solid ${helper.running ? "#6ee7b7" : "#fca5a5"}`,
                    borderRadius: 999,
                    color: helper.running ? "#d1fae5" : "#fecaca",
                    fontSize: 12,
                    padding: "4px 8px",
                  }}
                >
                  {helper.name.replace("codex_ollama_", "").replace("ollama_codex_", "")} {helper.effectiveWorkerCount}/{helper.processCount}
                </span>
              ))}
            </div>
            <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
              <span>participants {runtimeHealth?.participants.enabledCount || 0}/{runtimeHealth?.participants.totalCount || 0}</span>
              <span>processes {runtimeProcessCount}</span>
              <span>model {runtimeProcessModelLabel}</span>
              <span>execute {boolText(Boolean(runtimeHealth?.governance.grants_model_execution_authority))}</span>
              <span>memory write {boolText(Boolean(runtimeHealth?.governance.grants_memory_write_authority))}</span>
            </div>
          </article>
        </div>
      </div>

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 18, margin: 0 }}>Session Readback</h3>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>
            {sessionSummaries.length} sessions{sessionReadback?.truncated ? " / truncated" : ""}
            {collaborationCacheLabel(sessionReadback?.readbackCache)}
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            marginTop: 12,
          }}
        >
          {sessionSummaries.length ? (
            sessionSummaries.map((session) => {
              const sessionGateSummary = session.latestReviewGate.observed
                ? collaborationSessionReviewGateSummary(session.latestReviewGate)
                : null;
              const sessionDisclosureSummary = collaborationSessionTranscriptDisclosureSummary(session.transcriptDisclosure);
              return (
              <article
                key={session.id}
                style={{
                  background: "rgba(15, 23, 42, 0.58)",
                  border: "1px solid rgba(148, 163, 184, 0.22)",
                  borderRadius: 12,
                  padding: "12px 14px",
                }}
              >
                <div style={{ color: "#93c5fd", display: "flex", flexWrap: "wrap", fontSize: 13, gap: 10 }}>
                  <span>{session.messageCount} messages</span>
                  <span>{session.latestDirection || "unknown direction"}</span>
                  <span>{session.endedAt ? collaborationTimeText({ createdAt: session.endedAt } as CollaborationTranscriptEntry) : "unknown time"}</span>
                </div>
                <p style={{ color: "#e2e8f0", margin: "8px 0 0", overflowWrap: "anywhere" }}>
                  {session.latestObjective || "No session objective."}
                </p>
                {session.latestPreview ? (
                  <p style={{ color: "#cbd5e1", margin: "8px 0 0", overflowWrap: "anywhere" }}>{session.latestPreview}</p>
                ) : null}
                <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                  <span
                    style={{
                      border: `1px solid ${sessionDisclosureSummary.tone === "blocked" ? "#fca5a5" : "#6ee7b7"}`,
                      borderRadius: 999,
                      color: sessionDisclosureSummary.tone === "blocked" ? "#fecaca" : "#bbf7d0",
                      fontSize: 12,
                      fontWeight: 700,
                      padding: "3px 8px",
                    }}
                  >
                    {sessionDisclosureSummary.badge}
                  </span>
                  {sessionDisclosureSummary.detail.slice(1, 4).map((line) => (
                    <span key={`${session.id}-${line}`} style={{ color: "#94a3b8", fontSize: 12 }}>
                      {line}
                    </span>
                  ))}
                </div>
                {sessionGateSummary ? (
                  <div
                    style={{
                      borderTop: "1px solid rgba(148, 163, 184, 0.18)",
                      marginTop: 10,
                      paddingTop: 10,
                    }}
                  >
                    <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 }}>
                      <span
                        style={{
                          border: `1px solid ${sessionGateSummary.tone === "blocked" ? "#fca5a5" : "#67e8f9"}`,
                          borderRadius: 999,
                          color: sessionGateSummary.tone === "blocked" ? "#fecaca" : "#cffafe",
                          fontSize: 12,
                          fontWeight: 700,
                          padding: "3px 8px",
                        }}
                      >
                        {sessionGateSummary.badge}
                      </span>
                      <span style={{ color: "#93c5fd", fontSize: 12 }}>turn {session.latestReviewGate.turn || "?"}</span>
                      <span style={{ color: "#94a3b8", fontSize: 12 }}>{session.latestReviewGate.buildIssueCode || "review gate"}</span>
                    </div>
                    <dl style={{ color: "#cbd5e1", display: "grid", gap: 6, margin: "8px 0 0" }}>
                      <div>
                        <dt style={{ color: "#94a3b8" }}>Review Artifact</dt>
                        <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{sessionGateSummary.artifact}</dd>
                      </div>
                      <div>
                        <dt style={{ color: "#94a3b8" }}>Surface</dt>
                        <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{sessionGateSummary.surface}</dd>
                      </div>
                      <div>
                        <dt style={{ color: "#94a3b8" }}>Next Codex Action</dt>
                        <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{sessionGateSummary.nextAction}</dd>
                      </div>
                    </dl>
                    <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 8, marginTop: 8 }}>
                      {sessionGateSummary.detail.map((line) => (
                        <span key={line}>{line}</span>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
                  <span>participants {session.participants.join(", ") || "unknown"}</span>
                  <span>latest {collaborationShortId(session.latestItemId)}</span>
                </div>
              </article>
              );
            })
          ) : (
            <div style={{ border: "1px solid rgba(148, 163, 184, 0.22)", borderRadius: 12, color: "#94a3b8", padding: 14 }}>
              No collaboration session summaries returned.
            </div>
          )}
        </div>
      </div>

      {blockedReviewItems.length ? (
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <h3 style={{ fontSize: 18, margin: 0 }}>Build Direction Gates</h3>
            <span style={{ color: "#fca5a5", fontSize: 13 }}>{blockedReviewItems.length} blocked</span>
          </div>
          <div
            style={{
              display: "grid",
              gap: 10,
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              marginTop: 12,
              maxHeight: 220,
              overflowY: "auto",
              paddingRight: 4,
            }}
          >
            {blockedReviewItems.map((item) => {
              const gateSummary = collaborationBuildDirectionGateSummary(item);
              return (
                <article
                  key={`gate-${item.id || item.insightId}`}
                  style={{
                    background: "rgba(69, 10, 10, 0.28)",
                    border: "1px solid rgba(252, 165, 165, 0.62)",
                    borderRadius: 12,
                    padding: "12px 14px",
                  }}
                >
                  <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 }}>
                    <span
                      style={{
                        border: "1px solid rgba(252, 165, 165, 0.68)",
                        borderRadius: 999,
                        color: "#fecaca",
                        fontSize: 12,
                        fontWeight: 700,
                        padding: "4px 8px",
                      }}
                    >
                      {gateSummary.badge}
                    </span>
                    <span style={{ color: "#93c5fd", fontSize: 13 }}>turn {item.turn || "?"}</span>
                    <span style={{ color: "#94a3b8", fontSize: 13 }}>{collaborationShortId(item.insightId)}</span>
                  </div>
                  <p style={{ color: "#e2e8f0", margin: "10px 0 0", overflowWrap: "anywhere" }}>{gateSummary.reason}</p>
                  <dl style={{ color: "#cbd5e1", display: "grid", gap: 6, margin: "10px 0 0" }}>
                    <div>
                      <dt style={{ color: "#94a3b8" }}>Review Artifact</dt>
                      <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{gateSummary.artifact}</dd>
                    </div>
                    <div>
                      <dt style={{ color: "#94a3b8" }}>Conflicting Sources</dt>
                      <dd style={{ margin: 0 }}>
                        <ul style={{ display: "grid", gap: 4, listStyle: "none", margin: 0, padding: 0 }}>
                          {gateSummary.conflictingSourceLines.map((line) => (
                            <li key={line} style={{ overflowWrap: "anywhere" }}>
                              {line}
                            </li>
                          ))}
                        </ul>
                      </dd>
                    </div>
                  </dl>
                  <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
                    <span>surface {gateSummary.surface}</span>
                    {gateSummary.detail.map((line) => (
                      <span key={line}>{line}</span>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      ) : null}

      {latestImplementationReview ? (
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <h3 style={{ fontSize: 18, margin: 0 }}>Implementation Review Gate</h3>
            <span
              style={{
                border: `1px solid ${latestImplementationReview.tone === "blocked" ? "#fca5a5" : "#6ee7b7"}`,
                borderRadius: 999,
                color: latestImplementationReview.tone === "blocked" ? "#fecaca" : "#d1fae5",
                fontSize: 12,
                fontWeight: 700,
                padding: "4px 8px",
              }}
            >
              {latestImplementationReview.badge}
            </span>
          </div>
          <article
            style={{
              background:
                latestImplementationReview.tone === "blocked" ? "rgba(69, 10, 10, 0.26)" : "rgba(20, 83, 45, 0.18)",
              border: `1px solid ${latestImplementationReview.tone === "blocked" ? "rgba(252, 165, 165, 0.62)" : "rgba(110, 231, 183, 0.45)"}`,
              borderRadius: 12,
              marginTop: 12,
              padding: "12px 14px",
            }}
          >
            <dl style={{ color: "#cbd5e1", display: "grid", gap: 8, margin: 0 }}>
              <div>
                <dt style={{ color: "#94a3b8" }}>Review Artifact</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{latestImplementationReview.artifact}</dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Review Item</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                  {latestImplementationReview.preflight.reviewItemId || "unknown"}
                </dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Review Route</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                  {latestImplementationReview.preflight.reviewRoute || "/developer-bridge/collaboration-review?limit=1"}
                </dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Surface</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{latestImplementationReview.surface}</dd>
              </div>
              <div>
                <dt style={{ color: "#94a3b8" }}>Next Codex Action</dt>
                <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{latestImplementationReview.nextAction}</dd>
              </div>
            </dl>
            <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
              {latestImplementationReview.detail.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 18, margin: 0 }}>Review Candidates</h3>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>
            {reviewItems.length} candidates{review?.mode ? ` / ${review.mode}` : ""}
            {collaborationCacheLabel(review?.readbackCache)}
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            marginTop: 12,
            maxHeight: 360,
            overflowY: "auto",
            paddingRight: 4,
          }}
        >
          {reviewItems.length ? (
            reviewItems.map((item) => {
              const tone = collaborationReviewTone(item);
              const border = tone === "ready" ? "#6ee7b7" : tone === "blocked" ? "#fca5a5" : "#cbd5e1";
              const actionBoundary = collaborationActionBoundarySummary(item);
              const actionBoundaryBorder =
                actionBoundary.tone === "ready" ? "#6ee7b7" : actionBoundary.tone === "blocked" ? "#fca5a5" : "#cbd5e1";
              const actionIntake = collaborationActionIntakeSummary(item);
              const actionIntakeBorder =
                actionIntake.tone === "ready" ? "#6ee7b7" : actionIntake.tone === "blocked" ? "#fca5a5" : "#cbd5e1";
              const roadmapProof = item.roadmapAlignmentProof;
              const hasRoadmapProof = Boolean(
                roadmapProof.latestLedgerEntry || roadmapProof.currentPhase || roadmapProof.mainBuildPromptGate,
              );
              return (
                <article
                  key={item.id || item.insightId}
                  style={{
                    background: "rgba(15, 23, 42, 0.58)",
                    border: `1px solid ${border}`,
                    borderRadius: 12,
                    padding: "12px 14px",
                  }}
                >
                  <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 }}>
                    <span
                      style={{
                        background: tone === "ready" ? "rgba(20, 83, 45, 0.35)" : "rgba(71, 85, 105, 0.28)",
                        border: `1px solid ${border}`,
                        borderRadius: 999,
                        color: "#e2e8f0",
                        fontSize: 12,
                        fontWeight: 700,
                        padding: "4px 8px",
                      }}
                    >
                      {collaborationReviewBadge(item)}
                    </span>
                    <span style={{ color: "#93c5fd", fontSize: 13 }}>turn {item.turn || "?"}</span>
                    <span style={{ color: "#94a3b8", fontSize: 13 }}>{collaborationShortId(item.insightId)}</span>
                  </div>
                  <dl style={{ color: "#cbd5e1", display: "grid", gap: 8, margin: "10px 0 0" }}>
                    <div>
                      <dt style={{ color: "#94a3b8" }}>Surface</dt>
                      <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{item.concreteRepoSurface || "unknown"}</dd>
                    </div>
                    <div>
                      <dt style={{ color: "#94a3b8" }}>Surface Status</dt>
                      <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                        {item.surfaceVerification.status || "unknown"}
                        {item.surfaceVerification.surfaceKind ? ` / ${item.surfaceVerification.surfaceKind}` : ""}
                      </dd>
                    </div>
                    <div>
                      <dt style={{ color: "#94a3b8" }}>Artifact</dt>
                      <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{item.reviewArtifact || "unknown"}</dd>
                    </div>
                    <div>
                      <dt style={{ color: "#94a3b8" }}>Action Boundary</dt>
                      <dd style={{ margin: 0 }}>
                        <span
                          style={{
                            border: `1px solid ${actionBoundaryBorder}`,
                            borderRadius: 999,
                            color: actionBoundary.tone === "blocked" ? "#fecaca" : "#d1fae5",
                            display: "inline-flex",
                            fontSize: 12,
                            fontWeight: 700,
                            marginBottom: 6,
                            padding: "3px 8px",
                          }}
                        >
                          {actionBoundary.badge}
                        </span>
                        <span style={{ color: "#94a3b8", display: "block", fontSize: 12, overflowWrap: "anywhere" }}>
                          {actionBoundary.detail.join(" / ")}
                        </span>
                      </dd>
                    </div>
                    {actionIntake.applies ? (
                      <div>
                        <dt style={{ color: "#94a3b8" }}>Action Intake</dt>
                        <dd style={{ margin: 0 }}>
                          <span
                            style={{
                              border: `1px solid ${actionIntakeBorder}`,
                              borderRadius: 999,
                              color: actionIntake.tone === "blocked" ? "#fecaca" : "#d1fae5",
                              display: "inline-flex",
                              fontSize: 12,
                              fontWeight: 700,
                              marginBottom: 6,
                              padding: "3px 8px",
                            }}
                          >
                            {actionIntake.badge}
                          </span>
                          <span style={{ color: "#94a3b8", display: "block", fontSize: 12, overflowWrap: "anywhere" }}>
                            {actionIntake.detail.join(" / ")}
                          </span>
                        </dd>
                      </div>
                    ) : null}
                    {item.buildDirectionGate.blocksBuildDirection ? (
                      <div>
                        <dt style={{ color: "#fca5a5" }}>Build Direction Gate</dt>
                        <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                          {item.buildDirectionGate.state || "blocked"}
                          {item.buildDirectionGate.reason ? `: ${item.buildDirectionGate.reason}` : ""}
                        </dd>
                      </div>
                    ) : null}
                    {hasRoadmapProof ? (
                      <div>
                        <dt style={{ color: "#93c5fd" }}>Roadmap Proof</dt>
                        <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                          {roadmapProof.currentPhase || "phase unknown"}
                          {roadmapProof.currentPhasePosture ? ` / ${roadmapProof.currentPhasePosture}` : ""} / gate{" "}
                          {roadmapProof.mainBuildPromptGate || "requires_alignment_review"} / ledger{" "}
                          {roadmapProof.latestLedgerEntry || "unknown"}
                        </dd>
                        <dd style={{ color: "#94a3b8", margin: "4px 0 0", overflowWrap: "anywhere" }}>
                          sources {roadmapProof.sourceOrder.join(" -> ") || "unknown"} / open gaps {roadmapProof.coverageOpenGapCount} /
                          candidate only {boolText(roadmapProof.mainBuildPromptCandidateOnly)} / override{" "}
                          {boolText(roadmapProof.conversationCanOverrideRoadmap)} / execute {boolText(roadmapProof.grantsExecutionAuthority)}
                        </dd>
                      </div>
                    ) : null}
                    <div>
                      <dt style={{ color: "#94a3b8" }}>Finding</dt>
                      <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{item.finding || "No finding text."}</dd>
                    </div>
                    <div>
                      <dt style={{ color: "#94a3b8" }}>Next Codex Action</dt>
                      <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{collaborationReviewNextAction(item)}</dd>
                    </div>
                  </dl>
                  <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
                    <span>decision {item.reviewRecommendation.decision || "unknown"}</span>
                    <span>model drift {boolText(item.qualityFlags.loopLanguagePresent)}</span>
                    <span>repo review {boolText(item.qualityFlags.needsRepoTruthReview)}</span>
                    <span>existing surface {boolText(item.surfaceVerification.existingSurfaceFound)}</span>
                    <span>wiring review {boolText(item.surfaceVerification.requiresBuildOrWiringReview)}</span>
                    <span>build blocked {boolText(item.buildDirectionGate.blocksBuildDirection)}</span>
                    <span>execute {boolText(item.actionBoundary.conversationCanExecuteAction)}</span>
                    <span>approve {boolText(item.actionBoundary.conversationCanApproveAction)}</span>
                  </div>
                </article>
              );
            })
          ) : (
            <div style={{ border: "1px solid rgba(148, 163, 184, 0.22)", borderRadius: 12, color: "#94a3b8", padding: 14 }}>
              No collaboration review candidates returned.
            </div>
          )}
        </div>
      </div>

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 18, margin: 0 }}>Learning Receipts</h3>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>
            {learningItems.length} receipts{learning?.truncated ? " / truncated" : ""}
            {collaborationCacheLabel(learning?.readbackCache)}
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            marginTop: 12,
            maxHeight: 280,
            overflowY: "auto",
            paddingRight: 4,
          }}
        >
          {learningItems.length ? (
            learningItems.map((item) => (
              <article
                key={item.id}
                style={{
                  background: "rgba(20, 24, 39, 0.72)",
                  border: "1px solid rgba(125, 211, 252, 0.42)",
                  borderRadius: 12,
                  padding: "12px 14px",
                }}
              >
                <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 }}>
                  <span
                    style={{
                      border: "1px solid rgba(125, 211, 252, 0.62)",
                      borderRadius: 999,
                      color: "#e0f2fe",
                      fontSize: 12,
                      fontWeight: 700,
                      padding: "4px 8px",
                    }}
                  >
                    {item.failureType || "learning"}
                  </span>
                  <span style={{ color: "#93c5fd", fontSize: 13 }}>{collaborationLearningLatestTurnText(item)}</span>
                  {item.latestTurn && item.latestTurn !== item.turn ? (
                    <span style={{ color: "#94a3b8", fontSize: 13 }}>first turn {item.turn || "?"}</span>
                  ) : null}
                  {item.currentSignalObserved ? <span style={{ color: "#6ee7b7", fontSize: 13 }}>current signal</span> : null}
                  <span style={{ color: "#94a3b8", fontSize: 13 }}>{collaborationShortId(item.id)}</span>
                </div>
                <dl style={{ color: "#cbd5e1", display: "grid", gap: 8, margin: "10px 0 0" }}>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Repeated Terms</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{collaborationLearningTermText(item)}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Observation</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{item.observation || "No observation text."}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8" }}>Next Prompt Policy</dt>
                    <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
                      {item.learning.nextPromptPolicy || "No prompt policy recorded."}
                    </dd>
                  </div>
                </dl>
                <div style={{ color: "#94a3b8", display: "flex", flexWrap: "wrap", fontSize: 12, gap: 10, marginTop: 10 }}>
                  <span>recent turns {item.recentTurnCount}</span>
                  <span>current signal turns {item.currentSignalRecentTurnCount || item.recentTurnCount}</span>
                  <span>
                    latest observed{" "}
                    {item.latestObservedAt ? collaborationTimeText({ createdAt: item.latestObservedAt } as CollaborationTranscriptEntry) : "unknown"}
                  </span>
                  <span>full transcript {boolText(Boolean(item.writerGovernance.stores_full_transcript))}</span>
                  <span>execute {boolText(Boolean(item.writerGovernance.grants_execution_authority))}</span>
                  <span>memory write {boolText(Boolean(item.writerGovernance.grants_memory_write_authority))}</span>
                </div>
              </article>
            ))
          ) : (
            <div style={{ border: "1px solid rgba(148, 163, 184, 0.22)", borderRadius: 12, color: "#94a3b8", padding: 14 }}>
              No collaboration learning receipts returned.
            </div>
          )}
        </div>
      </div>

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <h3 style={{ fontSize: 18, margin: 0 }}>Relay Transcript Archive</h3>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>
            {visibleTranscriptItems.length} messages / {transcriptFilterText}
            {transcript?.truncated ? " / truncated" : ""}
            {transcriptAuditText}
            {transcriptGuardText}
            {hiddenMechanicText}
            {collaborationCacheLabel(transcript?.readbackCache)}
          </span>
        </div>
        {sessions.length || transcriptItems.length ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
            <button
              type="button"
              onClick={() => {
                setFollowLatest(true);
                if (latestSessionId) setSelectedSessionId(latestSessionId);
              }}
              style={{
                background: followLatest ? "#bfdbfe" : "rgba(15, 23, 42, 0.62)",
                border: "1px solid rgba(147, 197, 253, 0.42)",
                borderRadius: 10,
                color: followLatest ? "#0f172a" : "#dbeafe",
                cursor: "pointer",
                fontWeight: 700,
                padding: "7px 10px",
              }}
            >
              Live
            </button>
            {transcriptAuditSummary.auditReceiptCount ? (
              <button
                type="button"
                onClick={() => setShowAuditReceipts((current) => !current)}
                style={{
                  background: showAuditReceipts ? "rgba(251, 191, 36, 0.26)" : "rgba(15, 23, 42, 0.62)",
                  border: "1px solid rgba(251, 191, 36, 0.38)",
                  borderRadius: 10,
                  color: showAuditReceipts ? "#fde68a" : "#cbd5e1",
                  cursor: "pointer",
                  fontWeight: 700,
                  padding: "7px 10px",
                }}
              >
                Audit ({transcriptAuditSummary.auditReceiptCount})
              </button>
            ) : null}
            {transcriptAuditSummary.driverPromptCount ? (
              <button
                type="button"
                onClick={() => setShowRelayPrompts((current) => !current)}
                style={{
                  background: showRelayPrompts ? "rgba(103, 232, 249, 0.24)" : "rgba(15, 23, 42, 0.62)",
                  border: "1px solid rgba(103, 232, 249, 0.36)",
                  borderRadius: 10,
                  color: showRelayPrompts ? "#cffafe" : "#cbd5e1",
                  cursor: "pointer",
                  fontWeight: 700,
                  padding: "7px 10px",
                }}
              >
                Codex turns ({transcriptAuditSummary.driverPromptCount})
              </button>
            ) : null}
            {transcriptAuditSummary.guardReceiptCount ? (
              <button
                type="button"
                onClick={() => setShowGuardReceipts((current) => !current)}
                style={{
                  background: showGuardReceipts ? "rgba(251, 191, 36, 0.24)" : "rgba(15, 23, 42, 0.62)",
                  border: "1px solid rgba(251, 191, 36, 0.36)",
                  borderRadius: 10,
                  color: showGuardReceipts ? "#fde68a" : "#cbd5e1",
                  cursor: "pointer",
                  fontWeight: 700,
                  padding: "7px 10px",
                }}
              >
                Guard ({transcriptAuditSummary.guardReceiptCount})
              </button>
            ) : null}
            {sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => {
                  setSelectedSessionId(session.id);
                  setFollowLatest(session.id === latestSessionId);
                }}
                style={{
                  background: selectedSession?.id === session.id ? "rgba(14, 165, 233, 0.26)" : "rgba(15, 23, 42, 0.62)",
                  border: "1px solid rgba(148, 163, 184, 0.28)",
                  borderRadius: 10,
                  color: "#e2e8f0",
                  cursor: "pointer",
                  padding: "7px 10px",
                }}
              >
                {session.label} ({session.items.length})
              </button>
            ))}
          </div>
        ) : null}
        <div
          ref={transcriptScrollRef}
          style={{
            display: "grid",
            gap: 10,
            marginTop: 12,
            maxHeight: 420,
            overflowY: "auto",
            paddingRight: 4,
          }}
        >
          {visibleTranscriptItems.length ? (
            visibleTranscriptItems.map((item) => {
              const display = formatCollaborationRelayMessage(item);
              return (
                <article
                  key={item.id}
                  style={{
                    background: "rgba(15, 23, 42, 0.58)",
                    border: "1px solid rgba(148, 163, 184, 0.22)",
                    borderRadius: 12,
                    padding: "12px 14px",
                  }}
                >
                  <div style={{ color: "#93c5fd", display: "flex", flexWrap: "wrap", fontSize: 13, gap: 10 }}>
                    <span>{collaborationDirectionText(item)}</span>
                    <span>{collaborationTimeText(item)}</span>
                    <span>{collaborationRelayToneText(display)}</span>
                    {isCollaborationAuditReceipt(item) ? <span>audit ack</span> : null}
                    {display.compacted ? <span>compact receipt</span> : null}
                  </div>
                  <div
                    style={{
                      borderLeft: `3px solid ${
                        display.tone === "guard"
                          ? "#fbbf24"
                          : display.tone === "audit"
                            ? "#94a3b8"
                            : display.tone === "driver"
                              ? "#67e8f9"
                              : "#6ee7b7"
                      }`,
                      marginTop: 10,
                      paddingLeft: 10,
                    }}
                  >
                    <div style={{ color: "#a7f3d0", fontSize: 12, fontWeight: 700, textTransform: "uppercase" }}>
                      {collaborationConversationLayerText(display)}
                    </div>
                    <p style={{ color: "#e2e8f0", margin: "5px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>
                      {display.conversationText || display.summary}
                    </p>
                  </div>
                  {display.technicalText ? (
                    <details style={{ color: "#94a3b8", fontSize: 13, marginTop: 10 }}>
                      <summary style={{ cursor: "pointer" }}>Technical receipt</summary>
                      <p style={{ color: "#94a3b8", margin: "8px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>
                        {display.technicalText}
                      </p>
                    </details>
                  ) : null}
                  {display.compacted || display.technicalText ? (
                    <details style={{ color: "#94a3b8", fontSize: 13, marginTop: 10 }}>
                      <summary style={{ cursor: "pointer" }}>Raw receipt</summary>
                      <p style={{ margin: "8px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{display.raw}</p>
                      {item.context ? (
                        <p style={{ margin: "8px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{item.context}</p>
                      ) : null}
                    </details>
                  ) : null}
                </article>
              );
            })
          ) : (
            <div style={{ border: "1px solid rgba(148, 163, 184, 0.22)", borderRadius: 12, color: "#94a3b8", padding: 14 }}>
              {transcriptItems.length && transcriptVisibility.hiddenMechanicCount
                ? `No conversation entries visible. ${transcriptVisibility.hiddenMechanicCount} relay mechanics hidden by display metadata.`
                : "No relay transcript entries returned."}
            </div>
          )}
        </div>
      </div>
        </div>
      </details>
    </section>
  );
}

function BridgeMonitorPanel(props: { baseUrl: string }) {
  const [status, setStatus] = useState<CommandPaletteMonitorStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const statusRequestInFlight = useRef<{ signal?: AbortSignal } | null>(null);

  const loadStatus = useCallback(
    (signal?: AbortSignal, opts?: { showLoading?: boolean }) => {
      if (statusRequestInFlight.current && !statusRequestInFlight.current.signal?.aborted) return;
      const request = { signal };
      statusRequestInFlight.current = request;
      const showLoading = opts?.showLoading !== false;
      if (showLoading) setLoading(true);
      setError("");

      void fetchCommandPaletteMonitorStatus({ baseUrl: props.baseUrl, signal })
        .then((nextStatus) => {
          setStatus(nextStatus);
        })
        .catch((err: unknown) => {
          if (signal?.aborted || isAbortError(err)) return;
          setError(err instanceof Error ? err.message : "Command-palette monitor request failed.");
        })
        .finally(() => {
          if (statusRequestInFlight.current !== request) return;
          statusRequestInFlight.current = null;
          if (showLoading) setLoading(false);
        });
    },
    [props.baseUrl],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadStatus(controller.signal);
    const pollId = window.setInterval(() => {
      loadStatus(controller.signal, { showLoading: false });
    }, BRIDGE_MONITOR_POLL_MS);
    return () => {
      controller.abort();
      window.clearInterval(pollId);
    };
  }, [loadStatus]);

  const voice = status?.voice_monitor;
  const proof = voice?.chatgpt_mcp_proof;
  const connector = status?.chatgpt_connector_monitor;
  const ingress = status?.chatgpt_persistent_ingress_plan_monitor;
  const ingressHandoff = ingress?.operator_handoff;
  const ingressProviders = ingress?.providers;
  const transcriptProofReady = Boolean(proof?.proof_observed);
  const connectionProofReady = Boolean(proof?.mcp_connection_proof_observed);
  const monitorReady = Boolean(status?.monitor_process_alive || status?.monitor_heartbeat_fresh);
  const passiveListenReady = voice?.passive_listen_contract === "passive_transcript_awareness_only_until_wake_phrase";
  const micGateReady =
    voice?.microphone_gate_while_speaking === "francis_stop_only" && !voice.conversation_forwarding_while_speaking;
  const voiceInputObserved = Boolean(voice?.voice_input_ready || voice?.wake_listening);
  const statusTone = error || status?.status === "anomaly" || status?.status === "missing" ? "blocked" : "ready";
  const connectionProofTone = connectionProofReady ? "ready" : "blocked";
  const transcriptProofTone = transcriptProofReady ? "ready" : "blocked";
  const connectorTone = connector?.connector_usable_for_chatgpt ? "ready" : "blocked";
  const ingressTone = connector?.persistent_candidate ? "ready" : "blocked";
  const cloudflareLoginStatus = ingressProviders?.cloudflared_login_status || "";
  const cloudflareLoginProcess =
    ingressProviders?.cloudflared_login_process_id && ingressProviders.cloudflared_login_process_id > 0
      ? `pid ${ingressProviders.cloudflared_login_process_id} ${
          ingressProviders.cloudflared_login_process_alive ? "alive" : "not alive"
        }`
      : "no login process";
  const cloudflareLoginReceipt = cloudflareLoginStatus
    ? `${statusText(cloudflareLoginStatus)} / ${cloudflareLoginProcess}`
    : ingressProviders?.cloudflared_named_tunnel_login_required
      ? "required / no login process"
      : "ready / no login process";

  return (
    <section
      style={{
        background: "rgba(9, 13, 20, 0.92)",
        border: "1px solid rgba(148, 163, 184, 0.32)",
        borderRadius: 18,
        marginTop: 22,
        padding: 22,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", flexWrap: "wrap", justifyContent: "space-between", gap: 16 }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ color: "#67e8f9", margin: 0, textTransform: "uppercase", letterSpacing: 1.4 }}>
            ChatGPT / MCP bridge
          </p>
          <h2 style={{ fontSize: 24, margin: "8px 0 8px" }}>Bridge Monitor</h2>
        </div>
        <button
          type="button"
          onClick={() => loadStatus()}
          disabled={loading}
          style={{
            background: "#e2e8f0",
            border: 0,
            borderRadius: 12,
            color: "#0f172a",
            cursor: loading ? "wait" : "pointer",
            fontWeight: 800,
            maxWidth: "100%",
            minWidth: 112,
            padding: "10px 14px",
          }}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 16 }}>
        <Pill label="monitor" value={statusText(status?.status)} tone={statusTone} />
        <Pill label="process" value={monitorReady ? "alive" : "not confirmed"} tone={monitorReady ? "ready" : "blocked"} />
        <Pill label="poll" value={`${Math.round(BRIDGE_MONITOR_POLL_MS / 1000)}s`} tone="ready" />
        <Pill
          label="mcp link"
          value={connectionProofReady ? "observed" : statusText(proof?.mcp_connection_proof_status)}
          tone={connectionProofTone}
        />
        <Pill
          label="transcript"
          value={transcriptProofReady ? "observed" : statusText(proof?.status)}
          tone={transcriptProofTone}
        />
        <Pill label="connector" value={statusText(connector?.status)} tone={connectorTone} />
        <Pill label="ingress" value={statusText(connector?.persistent_ingress_status)} tone={ingressTone} />
        <Pill label="listen" value={passiveListenReady ? "passive" : "unconfirmed"} tone={passiveListenReady ? "ready" : "blocked"} />
        <Pill label="wake" value={voice?.wake_listening ? "armed" : "off"} tone={voice?.wake_listening ? "ready" : "blocked"} />
        <Pill label="mic gate" value={micGateReady ? "guarded" : "open"} tone={micGateReady ? "ready" : "blocked"} />
        <Pill
          label="overlay"
          value={voice?.overlay_ready ? statusText(voice.overlay_status || "visible") : statusText(voice?.overlay_status || "missing")}
          tone={voice?.overlay_ready ? "ready" : "blocked"}
        />
      </div>

      {error ? (
        <div style={{ border: "1px solid #fca5a5", borderRadius: 12, color: "#fecaca", marginTop: 16, padding: 12 }}>
          {error}
        </div>
      ) : null}

      <dl
        style={{
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          marginTop: 18,
        }}
      >
        <div>
          <dt style={{ color: "#94a3b8" }}>Checked at</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{status?.checked_at || "none"}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Latest receipt</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{voice?.latest_receipt_id || "none"}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Latest origin</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {voice?.latest_receipt_actor || "none"} / {voice?.latest_receipt_source || "none"} /{" "}
            {voice?.latest_receipt_ingress_transport || "none"}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Proof rejection</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {voice?.latest_receipt_proof_rejection_reason || "none"}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Voice input</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {voice?.voice_input_status || (voiceInputObserved ? "wake_listening" : "none")}
            {voice?.voice_input_blocker ? ` / ${voice.voice_input_blocker}` : ""}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Wake phrase</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{voice?.wake_phrase || "none"}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Listen contract</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {voice?.passive_listen_contract || "none"}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Speaking gate</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {voice?.microphone_gate_while_speaking || "none"} / forwarding {boolText(Boolean(voice?.conversation_forwarding_while_speaking))}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>MCP link receipt</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {proof?.latest_mcp_connection_proof_receipt_id || "none"}
            {proof?.latest_mcp_connection_proof_tool ? ` / ${proof.latest_mcp_connection_proof_tool}` : ""}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Transcript receipt</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {proof?.latest_fresh_usable_mcp_server_receipt_id || proof?.latest_mcp_server_receipt_id || "none"}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Any MCP receipt</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {proof?.latest_any_mcp_server_receipt_id || "none"}
            {proof?.latest_any_mcp_server_receipt_source ? ` / ${proof.latest_any_mcp_server_receipt_source}` : ""}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Connector host</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{connector?.connector_url_host || "none"}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Persistent blockers</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {joinStatusList(connector?.blockers ?? ingress?.blockers ?? [])}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Next bridge step</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{proof?.next_operator_step || "none"}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Next ingress step</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{joinStatusList(ingress?.next_operator_steps ?? [])}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Preferred ingress</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{ingressHandoff?.preferred_provider || "none"}</dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Stable URL</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {ingressHandoff?.stable_url_placeholder || "none"}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Cloudflared</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {ingressProviders?.cloudflared_named_tunnel_available ? "available" : "missing"}
            {ingressProviders?.cloudflared_named_tunnel_path
              ? ` / ${ingressProviders.cloudflared_named_tunnel_path}`
              : ""}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Cloudflare login</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {ingressProviders?.cloudflared_named_tunnel_login_required ? "required" : "ready"}
            {" / origin cert "}
            {boolText(Boolean(ingressProviders?.cloudflared_named_tunnel_origin_cert_present))}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Cloudflare login receipt</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {cloudflareLoginReceipt}
            {ingressProviders?.cloudflared_login_provider_started ? " / provider browser opened" : ""}
            {ingressProviders?.cloudflared_login_public_tunnel_started ? " / public tunnel started" : ""}
            {ingressProviders?.cloudflared_login_connector_url_recorded ? " / connector URL recorded" : ""}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Named tunnel</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {ingressProviders?.cloudflared_named_tunnel_requested
              ? `${ingressProviders.cloudflared_named_tunnel_requested_name || "unnamed"} / ${
                  ingressProviders.cloudflared_named_tunnel_requested_hostname || "host missing"
                }`
              : "not requested"}
            {" / exists "}
            {boolText(Boolean(ingressProviders?.cloudflared_named_tunnel_exists))}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Provider next step</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {ingressProviders?.cloudflared_named_tunnel_next_operator_step || "none"}
          </dd>
        </div>
        <div>
          <dt style={{ color: "#94a3b8" }}>Provider setup</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>
            {joinStatusList(ingressProviders?.cloudflared_named_tunnel_operator_provider_setup_commands ?? [])}
          </dd>
        </div>
      </dl>

      <pre
        style={{
          background: "rgba(2, 6, 23, 0.72)",
          border: "1px solid rgba(148, 163, 184, 0.24)",
          borderRadius: 12,
          color: "#bfdbfe",
          marginTop: 18,
          maxHeight: 260,
          overflow: "auto",
          padding: 14,
        }}
      >
        {JSON.stringify(
          status
            ? {
                status: status.status,
                anomaly_count: status.anomaly_count,
                voice: {
                  selected_voice: voice?.selected_voice,
                  passive_listen_contract: voice?.passive_listen_contract,
                  wake_listening: voice?.wake_listening,
                  wake_phrase: voice?.wake_phrase,
                  microphone_gate_while_speaking: voice?.microphone_gate_while_speaking,
                  conversation_forwarding_while_speaking: voice?.conversation_forwarding_while_speaking,
                  voice_input_status: voice?.voice_input_status,
                  latest_receipt_actor: voice?.latest_receipt_actor,
                  latest_receipt_ingress_transport: voice?.latest_receipt_ingress_transport,
                  latest_receipt_counts_as_chatgpt_mcp_proof: voice?.latest_receipt_counts_as_chatgpt_mcp_proof,
                },
                chatgpt_mcp_proof: proof,
                connector: {
                  status: connector?.status,
                  connector_url_host: connector?.connector_url_host,
                  connector_usable_for_chatgpt: connector?.connector_usable_for_chatgpt,
                  persistent_ingress_status: connector?.persistent_ingress_status,
                  blockers: connector?.blockers,
                },
                ingress_handoff: {
                  preferred_provider: ingressHandoff?.preferred_provider,
                  stable_url_placeholder: ingressHandoff?.stable_url_placeholder,
                  read_only_plan: ingressHandoff?.read_only_plan,
                  installs_provider: ingressHandoff?.installs_provider,
                  opens_tunnel: ingressHandoff?.opens_tunnel,
                  record_url: ingressHandoff?.governed_handoff_commands.record_url,
                  start_persistent_mcp: ingressHandoff?.governed_handoff_commands.start_persistent_mcp,
                  start_cloudflared_named: ingressHandoff?.governed_handoff_commands.start_cloudflared_named,
                },
                ingress_providers: ingressProviders,
              }
            : { status: loading ? "loading" : "not_loaded" },
          null,
          2,
        )}
      </pre>
    </section>
  );
}

function OrbOverlaySurface(props: { status: LensMcpStatus | null; loading: boolean }) {
  const orb = presentOrbGlyph(props.status, props.loading);
  const dragState = useRef<{ pointerId: number; offsetX: number; offsetY: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [position, setPosition] = useState(dockedOrbOverlayPosition);
  const snapshotMode = getQueryParam("lens_orb_snapshot") === "1";
  const manualDragEnabled = getQueryParam("lens_orb_unlock") === "1";
  const keyColor = getQueryParam("lens_overlay_key");
  const background = /^#?[0-9a-fA-F]{6}$/.test(keyColor)
    ? `#${keyColor.replace(/^#/, "")}`
    : "transparent";

  const moveToPointer = useCallback((clientX: number, clientY: number) => {
    const drag = dragState.current;
    if (!drag) return;
    setPosition(clampOrbOverlayPosition(clientX - drag.offsetX, clientY - drag.offsetY));
  }, []);

  const onPointerDown = useCallback((event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!manualDragEnabled || snapshotMode) return;
    if (event.button !== 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    dragState.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  }, [manualDragEnabled, snapshotMode]);

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (dragState.current?.pointerId !== event.pointerId) return;
      moveToPointer(event.clientX, event.clientY);
    },
    [moveToPointer],
  );

  const releasePointer = useCallback((event: ReactPointerEvent<HTMLButtonElement>) => {
    if (dragState.current?.pointerId !== event.pointerId) return;
    dragState.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragging(false);
  }, []);

  return (
    <main
      data-francis-lens-surface="orb_overlay"
      data-orb-dock="bottom-right"
      data-orb-drag-mode={manualDragEnabled ? "manual_debug" : "locked"}
      style={{
        background,
        minHeight: "100vh",
        overflow: "hidden",
        pointerEvents: "none",
        width: snapshotMode ? ORB_OVERLAY_SIZE : undefined,
      }}
    >
      <button
        type="button"
        aria-label={orb.label}
        data-orb-overlay="true"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={releasePointer}
        onPointerCancel={releasePointer}
        disabled={snapshotMode}
        style={{
          alignItems: "center",
          background: "transparent",
          border: 0,
          boxSizing: "border-box",
          bottom: snapshotMode || manualDragEnabled ? undefined : ORB_OVERLAY_DOCK_MARGIN,
          cursor: snapshotMode ? "default" : manualDragEnabled ? (dragging ? "grabbing" : "grab") : "default",
          display: "flex",
          height: ORB_OVERLAY_SIZE,
          justifyContent: "center",
          left: snapshotMode ? 0 : manualDragEnabled ? position.left : undefined,
          padding: 4,
          pointerEvents: "auto",
          position: "fixed",
          right: snapshotMode || manualDragEnabled ? undefined : ORB_OVERLAY_DOCK_MARGIN,
          top: snapshotMode ? 0 : manualDragEnabled ? position.top : undefined,
          touchAction: manualDragEnabled ? "none" : "auto",
          width: ORB_OVERLAY_SIZE,
        }}
      >
        <OrbGlyph state={orb} />
      </button>
    </main>
  );
}

export default function App() {
  const [status, setStatus] = useState<LensMcpStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const baseUrl = useMemo(() => apiBaseUrl(), []);
  const surfacePath = useMemo(() => {
    if (typeof window === "undefined") return "/";
    return window.location.pathname.replace(/\/+$/, "") || "/";
  }, []);
  const diagnosticsOnly = surfacePath === "/diagnostics";
  const communicationOnly = !diagnosticsOnly;
  const orbOverlayIntent = useMemo(() => {
    if (typeof window === "undefined") return false;
    return shouldOpenLensOrbOverlay(window.location.search, window.location.hash);
  }, []);

  const loadStatus = useCallback(
    (signal?: AbortSignal) => {
      setLoading(true);
      setError("");

      void fetchLensMcpStatus({ baseUrl, actor: "chat_ui.lens", signal, timeoutMs: LENS_MCP_STATUS_TIMEOUT_MS })
        .then((nextStatus) => {
          setStatus(nextStatus);
        })
        .catch((err: unknown) => {
          if (signal?.aborted || isAbortError(err)) return;
          setError(err instanceof Error ? err.message : "Lens MCP status request failed.");
        })
        .finally(() => {
          if (signal?.aborted) return;
          setLoading(false);
        });
    },
    [baseUrl],
  );

  useEffect(() => {
    if (communicationOnly) return;
    const controller = new AbortController();
    loadStatus(controller.signal);
    return () => controller.abort();
  }, [communicationOnly, loadStatus]);

  const shell: CSSProperties = {
    background: "radial-gradient(circle at 32% 18%, #070a10 0, #04060a 55%, #030407 100%)",
    color: "#f8fafc",
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    minHeight: "100vh",
    padding: 32,
  };

  if (orbOverlayIntent) {
    return <OrbOverlaySurface status={status} loading={loading} />;
  }

  if (communicationOnly) {
    return (
      <main style={shell}>
        <CollaborationAgentsPanel baseUrl={baseUrl} />
      </main>
    );
  }

  return (
    <main style={shell}>
      <BodyStatePanel status={status} loading={loading} error={error} onRefresh={() => loadStatus()} />
      <VoiceTranscriptionPanel baseUrl={baseUrl} />
      <CollaborationAgentsPanel baseUrl={baseUrl} />
      <BridgeMonitorPanel baseUrl={baseUrl} />
    </main>
  );
}
