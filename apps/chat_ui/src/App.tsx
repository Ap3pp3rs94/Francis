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
import { bodyStateReady, presentOrbGlyph, type OrbGlyphState } from "./lens/orbGlyph";
import { shouldOpenLensOrbOverlay } from "./lens";

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
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 18 }}>
          <OrbGlyph state={orb} />
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

const ORB_OVERLAY_SIZE = 128;

function clampOrbOverlayPosition(left: number, top: number): { left: number; top: number } {
  if (typeof window === "undefined") return { left, top };

  const maxLeft = Math.max(0, window.innerWidth - ORB_OVERLAY_SIZE);
  const maxTop = Math.max(0, window.innerHeight - ORB_OVERLAY_SIZE);
  return {
    left: Math.min(Math.max(0, left), maxLeft),
    top: Math.min(Math.max(0, top), maxTop),
  };
}

function getQueryParam(name: string): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get(name)?.trim() ?? "";
}

function OrbOverlaySurface(props: { status: LensMcpStatus | null; loading: boolean }) {
  const orb = presentOrbGlyph(props.status, props.loading);
  const dragState = useRef<{ pointerId: number; offsetX: number; offsetY: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [position, setPosition] = useState(() => ({ left: 24, top: 24 }));
  const snapshotMode = getQueryParam("lens_orb_snapshot") === "1";
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
    if (event.button !== 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    dragState.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  }, []);

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
      style={{
        background,
        minHeight: "100vh",
        overflow: "hidden",
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
          cursor: snapshotMode ? "default" : dragging ? "grabbing" : "grab",
          display: "flex",
          height: ORB_OVERLAY_SIZE,
          justifyContent: "center",
          left: snapshotMode ? 0 : position.left,
          padding: 4,
          position: "fixed",
          top: snapshotMode ? 0 : position.top,
          touchAction: "none",
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
    </main>
  );
}
