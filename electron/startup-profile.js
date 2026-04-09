const STARTUP_PROFILES = Object.freeze({
  operator: {
    id: "operator",
    label: "Operator Orb",
    description: "Show Francis immediately in orb-first interactive mode.",
    visible: true,
    ignoreMouseEvents: false,
  },
  quiet: {
    id: "quiet",
    label: "Quiet Orb",
    description: "Show only the orb immediately in click-through mode.",
    visible: true,
    ignoreMouseEvents: true,
  },
  core_only: {
    id: "core_only",
    label: "Core Services Only",
    description: "Start local runtime, but keep Francis hidden until summoned.",
    visible: false,
    ignoreMouseEvents: false,
  },
  recovery_safe: {
    id: "recovery_safe",
    label: "Recovery Safe",
    description: "Override startup posture after an unclean exit so Francis starts visible and interactive for inspection.",
    visible: true,
    ignoreMouseEvents: false,
    recoveryOnly: true,
  },
});

const DEFAULT_STARTUP_PROFILE = STARTUP_PROFILES.operator.id;

function normalizeStartupProfile(value, { allowRecoverySafe = false } = {}) {
  const requested = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (requested && STARTUP_PROFILES[requested]) {
    if (requested === STARTUP_PROFILES.recovery_safe.id && !allowRecoverySafe) {
      return DEFAULT_STARTUP_PROFILE;
    }
    return requested;
  }
  return DEFAULT_STARTUP_PROFILE;
}

function listStartupProfiles({ includeRecoverySafe = false } = {}) {
  return Object.values(STARTUP_PROFILES)
    .filter((profile) => includeRecoverySafe || !profile.recoveryOnly)
    .map((profile) => ({
      id: profile.id,
      label: profile.label,
      description: profile.description,
      visible: profile.visible,
      ignoreMouseEvents: profile.ignoreMouseEvents,
      recoveryOnly: Boolean(profile.recoveryOnly),
    }));
}

function resolveStartupProfile(preferences, { recoveryNeeded = false } = {}) {
  const requested = normalizeStartupProfile(preferences?.startupProfile);
  const effective = recoveryNeeded ? STARTUP_PROFILES.recovery_safe : STARTUP_PROFILES[requested];

  return {
    requested,
    effective: effective.id,
    label: effective.label,
    description: effective.description,
    visible: effective.visible,
    ignoreMouseEvents: effective.ignoreMouseEvents,
    recoveryLocked: effective.id === STARTUP_PROFILES.recovery_safe.id,
    options: listStartupProfiles(),
  };
}

module.exports = {
  DEFAULT_STARTUP_PROFILE,
  STARTUP_PROFILES,
  listStartupProfiles,
  normalizeStartupProfile,
  resolveStartupProfile,
};
