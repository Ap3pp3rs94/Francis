import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { fetchLensMcpStatus, type LensMcpStatus } from "./lens/mcpStatus";
import { bodyStateReady, presentOrbGlyph, type OrbGlyphState } from "./lens/orbGlyph";

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
  Array.from({ length: 60 }, (_unused, i) => ({
    rx: 14 + orbRand(i + 5) * 42,
    ry: 6 + orbRand(i + 13) * 24,
    rot: (i * 360) / 60 + (orbRand(i) - 0.5) * 46,
    o: 0.03 + orbRand(i + 23) * 0.12,
    dx: (orbRand(i + 41) - 0.5) * 14,
    dy: (orbRand(i + 59) - 0.5) * 14,
  }));

// A few crisper, slightly offset strands give the field definition over the smoke.
const ORB_ACCENTS: ReadonlyArray<{ rx: number; ry: number; rot: number; dx: number; dy: number }> = [
  { rx: 46, ry: 17, rot: 18, dx: -3, dy: 2 },
  { rx: 49, ry: 26, rot: 84, dx: 4, dy: -2 },
  { rx: 38, ry: 12, rot: 143, dx: 2, dy: 3 },
  { rx: 30, ry: 28, rot: 52, dx: -2, dy: -3 },
  { rx: 53, ry: 21, rot: 110, dx: 3, dy: 1 },
  { rx: 34, ry: 18, rot: 7, dx: -1, dy: -2 },
];

function OrbGlyph(props: { state: OrbGlyphState }) {
  const s = props.state;
  // Rings stay white/silver; state only subtly brightens them.
  const ringBoost = 0.6 + 0.5 * s.intensity;
  return (
    <svg
      width={104}
      height={104}
      viewBox="0 0 120 120"
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
          <stop offset="0%" stopColor="#0a1018" stopOpacity={0.6} />
          <stop offset="62%" stopColor="#070b12" stopOpacity={0.3} />
          <stop offset="100%" stopColor="#070b12" stopOpacity={0} />
        </radialGradient>
        {/* Luminous white/silver halo. */}
        <radialGradient id="francisOrbGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={s.glowColor} stopOpacity={0.85 * s.intensity} />
          <stop offset="32%" stopColor={s.glowColor} stopOpacity={0.26 * s.intensity} />
          <stop offset="70%" stopColor={s.glowColor} stopOpacity={0.05 * s.intensity} />
          <stop offset="100%" stopColor={s.glowColor} stopOpacity={0} />
        </radialGradient>
        {/* Graphite core whose edge dissolves into the field — a dark dense body
            with light emerging from inside, not a hard marble. */}
        <radialGradient id="francisOrbCore" cx="48%" cy="44%" r="60%">
          <stop offset="0%" stopColor="#dfe9f8" stopOpacity={0.85} />
          <stop offset="22%" stopColor="#7f93ad" stopOpacity={0.45} />
          <stop offset="46%" stopColor="#26354a" stopOpacity={0.92} />
          <stop offset="74%" stopColor="#101824" stopOpacity={0.8} />
          <stop offset="100%" stopColor={s.coreColor} stopOpacity={0} />
        </radialGradient>
        {/* Soft white luminous bloom — bright center bleeding past the core. */}
        <radialGradient id="francisOrbCenter" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity={0.95 * s.intensity} />
          <stop offset="22%" stopColor="#ffffff" stopOpacity={0.4 * s.intensity} />
          <stop offset="55%" stopColor="#ffffff" stopOpacity={0.1 * s.intensity} />
          <stop offset="100%" stopColor="#ffffff" stopOpacity={0} />
        </radialGradient>
        {/* Smoky softening for the dense trail field. */}
        <filter id="francisOrbSmoke" x="-25%" y="-25%" width="150%" height="150%">
          <feGaussianBlur stdDeviation="0.5" />
        </filter>
      </defs>
      <circle cx={60} cy={60} r={58} fill="url(#francisOrbField)" />
      <circle cx={60} cy={60} r={56} fill="url(#francisOrbGlow)" />
      {/* Dense smoky trail field */}
      <g fill="none" stroke={s.ringColor} strokeWidth={0.5} filter="url(#francisOrbSmoke)">
        {ORB_TRAILS.map((t, i) => (
          <ellipse
            key={`trail-${i}`}
            cx={60 + t.dx}
            cy={60 + t.dy}
            rx={t.rx}
            ry={t.ry}
            opacity={Math.min(0.4, t.o * ringBoost)}
            transform={`rotate(${t.rot.toFixed(2)} ${(60 + t.dx).toFixed(2)} ${(60 + t.dy).toFixed(2)})`}
          />
        ))}
      </g>
      {/* Defining strands */}
      <g fill="none" stroke={s.ringColor} strokeWidth={0.65}>
        {ORB_ACCENTS.map((b, i) => (
          <ellipse
            key={`accent-${i}`}
            cx={60 + b.dx}
            cy={60 + b.dy}
            rx={b.rx}
            ry={b.ry}
            opacity={Math.min(0.4, 0.12 * ringBoost)}
            transform={`rotate(${b.rot} ${60 + b.dx} ${60 + b.dy})`}
          />
        ))}
      </g>
      <circle cx={60} cy={60} r={26} fill="url(#francisOrbCore)" />
      <circle cx={60} cy={60} r={32} fill="url(#francisOrbCenter)" />
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

export default function App() {
  const [status, setStatus] = useState<LensMcpStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const baseUrl = useMemo(() => apiBaseUrl(), []);

  const loadStatus = useCallback(
    (signal?: AbortSignal) => {
      setLoading(true);
      setError("");

      void fetchLensMcpStatus({ baseUrl, actor: "chat_ui.lens", signal })
        .then((nextStatus) => {
          setStatus(nextStatus);
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Lens MCP status request failed.");
        })
        .finally(() => {
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

  return (
    <main style={shell}>
      <BodyStatePanel status={status} loading={loading} error={error} onRefresh={() => loadStatus()} />
    </main>
  );
}
