const ORB_BEHAVIOR_MODES = Object.freeze({
  explore: {
    id: "explore",
    label: "Explore",
    description: "Let the Orb move on its own while it stays local-first and out of the mouse path.",
  },
  trace: {
    id: "trace",
    label: "Trace",
    description: "Keep the Orb tracing the live cursor path while the mouse remains fully yours.",
  },
  autonomous: {
    id: "autonomous",
    label: "Autonomous",
    description: "Trace while you are active, then let the Orb explore on its own when you stop driving it.",
  },
});

const DEFAULT_ORB_BEHAVIOR_MODE = ORB_BEHAVIOR_MODES.autonomous.id;

function normalizeOrbBehaviorMode(value) {
  const requested = typeof value === "string" ? value.trim().toLowerCase() : "";
  return ORB_BEHAVIOR_MODES[requested] ? requested : DEFAULT_ORB_BEHAVIOR_MODE;
}

function listOrbBehaviorModes() {
  return Object.values(ORB_BEHAVIOR_MODES).map((mode) => ({
    id: mode.id,
    label: mode.label,
    description: mode.description,
  }));
}

function resolveOrbBehaviorMode(
  mode,
  {
    humanActive = false,
    authorityLive = false,
    handback = false,
  } = {},
) {
  const requested = normalizeOrbBehaviorMode(mode);
  if (handback) {
    return {
      requested,
      effective: "handback",
      trace: false,
      explore: false,
      summary: "Handback is active. Human sovereignty outranks Orb movement immediately.",
      options: listOrbBehaviorModes(),
    };
  }
  if (authorityLive) {
    return {
      requested,
      effective: "authority",
      trace: false,
      explore: false,
      summary: "Francis authority is live. Orb motion is now governed by the current desktop execution path.",
      options: listOrbBehaviorModes(),
    };
  }
  if (requested === ORB_BEHAVIOR_MODES.trace.id) {
    return {
      requested,
      effective: ORB_BEHAVIOR_MODES.trace.id,
      trace: true,
      explore: false,
      summary: "Trace is active. The Orb follows the cursor path with a short visual lag while the mouse remains yours.",
      options: listOrbBehaviorModes(),
    };
  }
  if (requested === ORB_BEHAVIOR_MODES.explore.id) {
    return {
      requested,
      effective: ORB_BEHAVIOR_MODES.explore.id,
      trace: false,
      explore: true,
      summary: "Explore is active. The Orb moves on its own while still learning human motion locally.",
      options: listOrbBehaviorModes(),
    };
  }
  return {
    requested,
    effective: humanActive ? ORB_BEHAVIOR_MODES.trace.id : ORB_BEHAVIOR_MODES.explore.id,
    trace: Boolean(humanActive),
    explore: !humanActive,
    summary: humanActive
      ? "Autonomous is active. The Orb is tracing the live cursor path while you are active."
      : "Autonomous is active. The Orb is exploring on its own using learned local motion.",
    options: listOrbBehaviorModes(),
  };
}

module.exports = {
  DEFAULT_ORB_BEHAVIOR_MODE,
  ORB_BEHAVIOR_MODES,
  listOrbBehaviorModes,
  normalizeOrbBehaviorMode,
  resolveOrbBehaviorMode,
};
