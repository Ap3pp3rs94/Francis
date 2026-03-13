const MOTION_MODES = Object.freeze({
  system: {
    id: "system",
    label: "System Motion",
    description: "Follow the operating system reduced-motion preference when available.",
  },
  reduce: {
    id: "reduce",
    label: "Reduced Motion",
    description: "Calm animation, lower Orb drift, and reduced interface motion.",
  },
  full: {
    id: "full",
    label: "Full Motion",
    description: "Allow the full Orb and HUD motion model.",
  },
});

const DEFAULT_MOTION_MODE = MOTION_MODES.system.id;

function normalizeMotionMode(value) {
  const requested = typeof value === "string" ? value.trim().toLowerCase() : "";
  return MOTION_MODES[requested] ? requested : DEFAULT_MOTION_MODE;
}

function listMotionModes() {
  return Object.values(MOTION_MODES).map((mode) => ({
    id: mode.id,
    label: mode.label,
    description: mode.description,
  }));
}

function resolveMotionMode(mode, { systemReducedMotion = false } = {}) {
  const requested = normalizeMotionMode(mode);
  const reduced = requested === MOTION_MODES.reduce.id || (requested === MOTION_MODES.system.id && Boolean(systemReducedMotion));
  return {
    requested,
    effective: reduced ? MOTION_MODES.reduce.id : MOTION_MODES.full.id,
    reduced,
    systemReducedMotion: Boolean(systemReducedMotion),
    options: listMotionModes(),
  };
}

function buildAccessibilityState({ motionMode = DEFAULT_MOTION_MODE, systemReducedMotion = false } = {}) {
  const resolvedMotion = resolveMotionMode(motionMode, { systemReducedMotion });

  return {
    summary: resolvedMotion.reduced
      ? "Reduced-motion accessibility mode is active."
      : resolvedMotion.requested === DEFAULT_MOTION_MODE
        ? "Accessibility motion follows the system preference."
        : "Full-motion accessibility mode is active.",
    motionMode: resolvedMotion.requested,
    effectiveMotionMode: resolvedMotion.effective,
    reducedMotion: resolvedMotion.reduced,
    systemReducedMotion: resolvedMotion.systemReducedMotion,
    options: resolvedMotion.options,
    cards: [
      {
        label: "Summary",
        value: resolvedMotion.reduced
          ? "Reduced-motion posture is active."
          : resolvedMotion.requested === DEFAULT_MOTION_MODE
            ? "Motion follows the system preference."
            : "Full-motion posture is active.",
        tone: resolvedMotion.reduced ? "medium" : "low",
      },
      {
        label: "Requested",
        value: resolvedMotion.requested,
        tone: "low",
      },
      {
        label: "Effective",
        value: resolvedMotion.effective,
        tone: resolvedMotion.reduced ? "medium" : "low",
      },
      {
        label: "System Preference",
        value: resolvedMotion.systemReducedMotion ? "reduce" : "full",
        tone: resolvedMotion.systemReducedMotion ? "medium" : "low",
      },
    ],
  };
}

module.exports = {
  DEFAULT_MOTION_MODE,
  MOTION_MODES,
  buildAccessibilityState,
  listMotionModes,
  normalizeMotionMode,
  resolveMotionMode,
};
