const ORB_BEHAVIOR_MODES = Object.freeze({
  explore: {
    id: "explore",
    label: "Explore",
    description: "Bias the Orb toward deliberate investigation arcs when the desktop opens up, while it still returns to a purposeful perch.",
  },
  trace: {
    id: "trace",
    label: "Trace",
    description: "Bias the Orb toward tighter workspace following without collapsing into a decorative cursor skin.",
  },
  autonomous: {
    id: "autonomous",
    label: "Autonomous",
    description: "Let the Orb choose between anchored rest, attentive following, and deliberate investigation based on live desktop context.",
  },
});

const DEFAULT_ORB_BEHAVIOR_MODE = ORB_BEHAVIOR_MODES.autonomous.id;

function normalizeOrbBehaviorMode(value) {
  const requested = typeof value === "string" ? value.trim().toLowerCase() : "";
  return ORB_BEHAVIOR_MODES[requested] ? requested : DEFAULT_ORB_BEHAVIOR_MODE;
}

function normalizePersistedOrbBehaviorMode(value) {
  const requested = normalizeOrbBehaviorMode(value);
  return requested === ORB_BEHAVIOR_MODES.explore.id ? DEFAULT_ORB_BEHAVIOR_MODE : requested;
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
    investigationPressure = false,
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
      summary: "Trace bias is active. The Orb stays close to your current work region while the mouse remains fully yours.",
      options: listOrbBehaviorModes(),
    };
  }
  if (requested === ORB_BEHAVIOR_MODES.explore.id) {
    return {
      requested,
      effective: ORB_BEHAVIOR_MODES.explore.id,
      trace: false,
      explore: true,
      summary: "Explore bias is active. The Orb uses deliberate scouting motion when the desktop opens up while keeping a disciplined perch.",
      options: listOrbBehaviorModes(),
    };
  }
  return {
    requested,
    effective: humanActive ? ORB_BEHAVIOR_MODES.trace.id : investigationPressure ? "investigate" : ORB_BEHAVIOR_MODES.autonomous.id,
    trace: Boolean(humanActive),
    explore: Boolean(!humanActive && investigationPressure),
    summary: humanActive
      ? "Autonomous bias is active. The Orb stays attentive to your current work region while you are active."
      : investigationPressure
        ? "Autonomous bias is active. Grounded target pressure is present, so the Orb investigates deliberately."
        : "Autonomous bias is active. The Orb stays perched and quiet until grounded target pressure justifies movement.",
    options: listOrbBehaviorModes(),
  };
}

module.exports = {
  DEFAULT_ORB_BEHAVIOR_MODE,
  ORB_BEHAVIOR_MODES,
  listOrbBehaviorModes,
  normalizeOrbBehaviorMode,
  normalizePersistedOrbBehaviorMode,
  resolveOrbBehaviorMode,
};
