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

function BridgeMonitorPanel(props: { baseUrl: string }) {
  const [status, setStatus] = useState<CommandPaletteMonitorStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const statusRequestInFlight = useRef(false);

  const loadStatus = useCallback(
    (signal?: AbortSignal, opts?: { showLoading?: boolean }) => {
      if (statusRequestInFlight.current) return;
      statusRequestInFlight.current = true;
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
          statusRequestInFlight.current = false;
          if (signal?.aborted) return;
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
  const orbOverlayIntent = useMemo(() => {
    if (typeof window === "undefined") return false;
    return shouldOpenLensOrbOverlay(window.location.search, window.location.hash);
  }, []);

  const loadStatus = useCallback(
    (signal?: AbortSignal) => {
      setLoading(true);
      setError("");

      void fetchLensMcpStatus({ baseUrl, actor: "chat_ui.lens", signal })
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
    const controller = new AbortController();
    loadStatus(controller.signal);
    return () => controller.abort();
  }, [loadStatus]);

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

  return (
    <main style={shell}>
      <BodyStatePanel status={status} loading={loading} error={error} onRefresh={() => loadStatus()} />
      <VoiceTranscriptionPanel baseUrl={baseUrl} />
      <BridgeMonitorPanel baseUrl={baseUrl} />
    </main>
  );
}
