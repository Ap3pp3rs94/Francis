import type { LensMcpStatus } from "./mcpStatus.ts";

// First visible state-driven Orb glyph (Chat UI only).
//
// Visual target (per operator reference): a calm, premium "atom-like" presence
// on a dark field — smoky white/silver orbital bands around a black-chrome core
// with a soft luminous glow. The orbit rings stay silver/white; the operational
// state cue is carried by glow color and overall intensity, not by recoloring
// the rings. This is a first approximation, not the final Orb.
//
// This module is a pure presenter: it turns the already-fetched read-only
// Lens-Orb MCP body-state (/lens/mcp/status) into a small descriptor that
// App.tsx renders as an inline SVG glyph. It performs no network I/O, claims
// no resident autonomy, and grants no input, takeover, capture, or mutation
// authority. Governance flags below are surfaced truthfully from the backend
// projection; the glyph never sets them.

export type OrbGlyphTone = "idle" | "ready" | "attention" | "active";

export type OrbGlyphState = {
  tone: OrbGlyphTone;
  posture: string;
  status: string;
  ready: boolean;
  resident: boolean;
  readOnly: boolean;
  grantsExecutionAuthority: boolean;
  grantsMutationAuthority: boolean;
  coreColor: string;
  ringColor: string;
  glowColor: string;
  intensity: number;
  label: string;
};

// Black-chrome core base and smoky white/silver orbit bands are constant; only
// the glow color and intensity carry the state cue.
const CORE_COLOR = "#0b1220";
const RING_COLOR = "#dbe4f0";

// Identity is primarily a graphite core + white/silver rings; the operational
// state only subtly shifts the center glow (cool silver -> bright white, with a
// gentle warm-white for attention) and the overall intensity. No neon accents.
const TONE: Record<OrbGlyphTone, { glow: string; intensity: number }> = {
  idle: { glow: "#cbd5e1", intensity: 0.55 },
  ready: { glow: "#eaf2ff", intensity: 0.85 },
  attention: { glow: "#fbe9cf", intensity: 0.8 },
  active: { glow: "#ffffff", intensity: 1 },
};

function textOrUnknown(value: string | undefined): string {
  return typeof value === "string" && value.trim() ? value.trim() : "unknown";
}

// Single source of truth for readiness, shared with the BodyStatePanel pills so
// the orb cue can never contradict the textual status it sits beside.
export function bodyStateReady(status: LensMcpStatus | null): boolean {
  return Boolean(
    status &&
      status.status === "ready" &&
      status.mcp.missing_tools.length === 0 &&
      status.blockers.length === 0,
  );
}

function deriveTone(status: LensMcpStatus | null, loading: boolean, ready: boolean, posture: string): OrbGlyphTone {
  if (loading || !status) return "idle";
  if (!ready || posture === "degraded") return "attention";
  if (posture === "takeover_active") return "active";
  return "ready";
}

export function presentOrbGlyph(status: LensMcpStatus | null, loading = false): OrbGlyphState {
  const posture = textOrUnknown(status?.embodied_posture);
  const statusText = textOrUnknown(status?.status);
  const ready = bodyStateReady(status);
  const tone = deriveTone(status, loading, ready, posture);
  const cue = TONE[tone];

  // The chat-UI body-state surface is read-only by contract; reflect the
  // backend governance flag when present and default to read-only otherwise.
  const readOnly = status ? Boolean(status.governance["read_only"]) : true;
  const grantsExecutionAuthority = Boolean(status?.governance["grants_execution_authority"]);
  const grantsMutationAuthority = Boolean(status?.governance["grants_mutation_authority"]);

  const label = `Francis Orb — posture: ${posture}, status: ${statusText}${readOnly ? " (read-only)" : ""}`;

  return {
    tone,
    posture,
    status: statusText,
    ready,
    resident: Boolean(status?.resident),
    readOnly,
    grantsExecutionAuthority,
    grantsMutationAuthority,
    coreColor: CORE_COLOR,
    ringColor: RING_COLOR,
    glowColor: cue.glow,
    intensity: cue.intensity,
    label,
  };
}
