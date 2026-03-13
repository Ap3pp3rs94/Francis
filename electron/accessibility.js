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

const CONTRAST_MODES = Object.freeze({
  system: {
    id: "system",
    label: "System Contrast",
    description: "Follow the operating system high-contrast preference when available.",
  },
  standard: {
    id: "standard",
    label: "Standard Contrast",
    description: "Use the default Francis contrast posture.",
  },
  high: {
    id: "high",
    label: "High Contrast",
    description: "Increase contrast and border clarity for longer or higher-stress sessions.",
  },
});

const DENSITY_MODES = Object.freeze({
  comfortable: {
    id: "comfortable",
    label: "Comfortable Density",
    description: "Keep Francis spaced for longer reading sessions.",
  },
  compact: {
    id: "compact",
    label: "Compact Density",
    description: "Tighten spacing to fit more operator state without changing scope.",
  },
});

const DEFAULT_MOTION_MODE = MOTION_MODES.system.id;
const DEFAULT_CONTRAST_MODE = CONTRAST_MODES.system.id;
const DEFAULT_DENSITY_MODE = DENSITY_MODES.comfortable.id;

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

function normalizeContrastMode(value) {
  const requested = typeof value === "string" ? value.trim().toLowerCase() : "";
  return CONTRAST_MODES[requested] ? requested : DEFAULT_CONTRAST_MODE;
}

function listContrastModes() {
  return Object.values(CONTRAST_MODES).map((mode) => ({
    id: mode.id,
    label: mode.label,
    description: mode.description,
  }));
}

function resolveContrastMode(mode, { systemHighContrast = false } = {}) {
  const requested = normalizeContrastMode(mode);
  const high = requested === CONTRAST_MODES.high.id || (requested === CONTRAST_MODES.system.id && Boolean(systemHighContrast));
  return {
    requested,
    effective: high ? CONTRAST_MODES.high.id : CONTRAST_MODES.standard.id,
    high,
    systemHighContrast: Boolean(systemHighContrast),
    options: listContrastModes(),
  };
}

function normalizeDensityMode(value) {
  const requested = typeof value === "string" ? value.trim().toLowerCase() : "";
  return DENSITY_MODES[requested] ? requested : DEFAULT_DENSITY_MODE;
}

function listDensityModes() {
  return Object.values(DENSITY_MODES).map((mode) => ({
    id: mode.id,
    label: mode.label,
    description: mode.description,
  }));
}

function buildAccessibilityState({
  motionMode = DEFAULT_MOTION_MODE,
  systemReducedMotion = false,
  contrastMode = DEFAULT_CONTRAST_MODE,
  systemHighContrast = false,
  densityMode = DEFAULT_DENSITY_MODE,
  shortcuts = {},
} = {}) {
  const resolvedMotion = resolveMotionMode(motionMode, { systemReducedMotion });
  const resolvedContrast = resolveContrastMode(contrastMode, { systemHighContrast });
  const normalizedDensity = normalizeDensityMode(densityMode);
  const overlayShortcut = typeof shortcuts.toggleOverlay === "string" ? shortcuts.toggleOverlay.trim() : "";
  const clickThroughShortcut = typeof shortcuts.toggleClickThrough === "string" ? shortcuts.toggleClickThrough.trim() : "";
  const keyboardReady = Boolean(overlayShortcut && clickThroughShortcut);
  const stressControlSummary = keyboardReady
    ? `Use ${clickThroughShortcut} to recover pointer control and ${overlayShortcut} to summon or re-show Francis.`
    : "Keyboard recovery posture appears once the desktop shell bridge is attached.";
  const summaryParts = [];
  if (resolvedMotion.reduced) {
    summaryParts.push("Reduced motion is active");
  } else if (resolvedMotion.requested === DEFAULT_MOTION_MODE) {
    summaryParts.push("motion follows the system preference");
  } else {
    summaryParts.push("full motion is active");
  }
  if (resolvedContrast.high) {
    summaryParts.push("high contrast is active");
  }
  if (normalizedDensity === DENSITY_MODES.compact.id) {
    summaryParts.push("compact density is active");
  }
  if (keyboardReady) {
    summaryParts.push("critical shell flows are keyboard-reachable");
  }

  return {
    summary: `${summaryParts.join("; ")}.`.replace(/^./, (value) => value.toUpperCase()),
    motionMode: resolvedMotion.requested,
    effectiveMotionMode: resolvedMotion.effective,
    reducedMotion: resolvedMotion.reduced,
    systemReducedMotion: resolvedMotion.systemReducedMotion,
    contrastMode: resolvedContrast.requested,
    effectiveContrastMode: resolvedContrast.effective,
    highContrast: resolvedContrast.high,
    systemHighContrast: resolvedContrast.systemHighContrast,
    densityMode: normalizedDensity,
    keyboardFirst: keyboardReady,
    focusVisibility: "strong",
    screenReaderPosture: "HUD panels use semantic headings, buttons, lists, and summarized proof layers.",
    stressControls: stressControlSummary,
    options: resolvedMotion.options,
    contrastOptions: resolvedContrast.options,
    densityOptions: listDensityModes(),
    cards: [
      {
        label: "Summary",
        value: `${summaryParts.join("; ")}.`.replace(/^./, (value) => value.toUpperCase()),
        tone: resolvedMotion.reduced || resolvedContrast.high ? "medium" : "low",
      },
      {
        label: "Requested",
        value: resolvedMotion.requested,
        tone: "low",
      },
      {
        label: "Motion",
        value: resolvedMotion.effective,
        tone: resolvedMotion.reduced ? "medium" : "low",
      },
      {
        label: "Contrast",
        value: resolvedContrast.effective,
        tone: resolvedContrast.high ? "medium" : "low",
      },
      {
        label: "Density",
        value: normalizedDensity,
        tone: normalizedDensity === DENSITY_MODES.compact.id ? "medium" : "low",
      },
      {
        label: "Keyboard",
        value: keyboardReady ? `${overlayShortcut} | ${clickThroughShortcut}` : "bridge unavailable",
        tone: keyboardReady ? "low" : "medium",
      },
      {
        label: "Focus",
        value: "strong focus-visible outlines",
        tone: "low",
      },
      {
        label: "System Motion",
        value: resolvedMotion.systemReducedMotion ? "reduce" : "full",
        tone: resolvedMotion.systemReducedMotion ? "medium" : "low",
      },
      {
        label: "System Contrast",
        value: resolvedContrast.systemHighContrast ? "high" : "standard",
        tone: resolvedContrast.systemHighContrast ? "medium" : "low",
      },
    ],
    items: [
      {
        id: "keyboard",
        label: "Keyboard Control",
        summary: keyboardReady
          ? `Critical shell flows remain reachable from the keyboard through ${overlayShortcut} and ${clickThroughShortcut}.`
          : "Keyboard control posture will appear once the desktop shell bridge is attached.",
      },
      {
        id: "stress_controls",
        label: "Stress Controls",
        summary: stressControlSummary,
      },
      {
        id: "screen_reader",
        label: "Screen Reader",
        summary: "Semantic panel headings, buttons, lists, and compact audits preserve readable structure where Chromium accessibility tooling is available.",
      },
    ],
  };
}

module.exports = {
  CONTRAST_MODES,
  DEFAULT_CONTRAST_MODE,
  DEFAULT_DENSITY_MODE,
  DEFAULT_MOTION_MODE,
  DENSITY_MODES,
  MOTION_MODES,
  buildAccessibilityState,
  listContrastModes,
  listDensityModes,
  listMotionModes,
  normalizeContrastMode,
  normalizeDensityMode,
  normalizeMotionMode,
  resolveContrastMode,
  resolveMotionMode,
};
