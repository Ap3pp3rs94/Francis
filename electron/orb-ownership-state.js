const ORB_OWNERSHIP_STATES = Object.freeze({
  PASS_THROUGH: "pass_through",
  INTERACTABLE_ORB: "interactable_orb",
  INTERACTABLE_LENS: "interactable_lens",
  RESTRICTED: "restricted",
});

const ORB_OWNERSHIP_GOVERNOR_STATES = Object.freeze({
  OBSERVE: "observe",
  ASSIST: "assist",
  ACT: "act",
  PAUSED: "paused",
  DEGRADED: "degraded",
  USER_OVERRIDE: "user_override",
});

const ORB_OWNERSHIP_USER_OVERRIDE_HOLD_MS = 1200;

function cleanText(value, fallback = "") {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text || fallback;
}

function buildDefaultOrbOwnershipGovernor() {
  return {
    userOverrideUntilMs: 0,
    userOverrideReason: "",
    lastChangedAtMs: 0,
  };
}

function normalizeOrbOwnershipGovernor(value = {}) {
  const current = {
    ...buildDefaultOrbOwnershipGovernor(),
    ...(value && typeof value === "object" ? value : {}),
  };
  current.userOverrideUntilMs = Math.max(0, Number(current.userOverrideUntilMs || 0));
  current.userOverrideReason = cleanText(current.userOverrideReason).toLowerCase();
  current.lastChangedAtMs = Math.max(0, Number(current.lastChangedAtMs || 0));
  return current;
}

function normalizeOrbOwnershipRequest(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (Object.values(ORB_OWNERSHIP_STATES).includes(normalized)) {
    return normalized;
  }
  return ORB_OWNERSHIP_STATES.PASS_THROUGH;
}

function isOrbOwnershipUserOverrideReason(reason = "") {
  const normalized = cleanText(reason).toLowerCase();
  return [
    "foreground_window_changed",
    "human_returned",
    "orb_blur",
    "desktop_user_override",
  ].includes(normalized);
}

function shouldClearOrbOwnershipUserOverrideForReason(reason = "") {
  const normalized = cleanText(reason).toLowerCase();
  return [
    "orb_surface_focus",
    "orb_surface_chat",
    "orb_surface_menu",
    "orb_surface_strip",
    "orb_shell",
  ].includes(normalized);
}

function isOrbOwnershipUserOverrideActive(governor = {}, nowMs = Date.now()) {
  const current = normalizeOrbOwnershipGovernor(governor);
  return current.userOverrideUntilMs > Math.max(0, Number(nowMs || Date.now()));
}

function armOrbOwnershipUserOverride(governor = {}, {
  reason = "",
  nowMs = Date.now(),
  holdMs = ORB_OWNERSHIP_USER_OVERRIDE_HOLD_MS,
} = {}) {
  const current = normalizeOrbOwnershipGovernor(governor);
  const normalizedReason = cleanText(reason).toLowerCase();
  if (!isOrbOwnershipUserOverrideReason(normalizedReason)) {
    return current;
  }
  return normalizeOrbOwnershipGovernor({
    ...current,
    userOverrideUntilMs: Math.max(current.userOverrideUntilMs, Math.max(0, Number(nowMs || Date.now())) + Math.max(250, Number(holdMs || ORB_OWNERSHIP_USER_OVERRIDE_HOLD_MS))),
    userOverrideReason: normalizedReason,
    lastChangedAtMs: Math.max(0, Number(nowMs || Date.now())),
  });
}

function clearOrbOwnershipUserOverride(governor = {}, {
  nowMs = Date.now(),
} = {}) {
  const current = normalizeOrbOwnershipGovernor(governor);
  if (!current.userOverrideUntilMs && !current.userOverrideReason) {
    return current;
  }
  return normalizeOrbOwnershipGovernor({
    ...current,
    userOverrideUntilMs: 0,
    userOverrideReason: "",
    lastChangedAtMs: Math.max(0, Number(nowMs || Date.now())),
  });
}

function isRestrictedRuntime({ authority = {}, runtimeHealth = {}, captureSuspended = false } = {}) {
  const runtimeStatus = String(runtimeHealth?.status || "nominal").trim().toLowerCase() || "nominal";
  return Boolean(
    captureSuspended
      || authority?.localStopped
      || authority?.pauseHeld
      || authority?.disconnected
      || runtimeStatus === "degraded"
      || runtimeStatus === "disconnected"
      || runtimeStatus === "recovering",
  );
}

function summarizeRestrictedReason({ authority = {}, runtimeHealth = {}, captureSuspended = false } = {}) {
  if (captureSuspended) {
    return {
      reason: "capture_suspended",
      summary: "Pointer ownership is suspended while protected capture mode is active.",
    };
  }
  if (authority?.localStopped) {
    return {
      reason: "local_stop",
      summary: "Local stop is engaged. Human control remains primary.",
    };
  }
  if (authority?.pauseHeld) {
    return {
      reason: "pause_held",
      summary: "Pause is holding local authority clear. Human control remains primary.",
    };
  }
  const runtimeStatus = String(runtimeHealth?.status || "nominal").trim().toLowerCase() || "nominal";
  if (runtimeStatus === "disconnected" || authority?.disconnected) {
    return {
      reason: "runtime_disconnected",
      summary: "The local operator runtime is disconnected. Francis will not claim orb input.",
    };
  }
  if (runtimeStatus === "recovering") {
    return {
      reason: "runtime_recovering",
      summary: "The local operator runtime is recovering. Francis is holding safe pass-through.",
    };
  }
  if (runtimeStatus === "degraded" || authority?.degraded) {
    return {
      reason: "runtime_degraded",
      summary: "The local operator runtime is degraded. Francis is holding safe pass-through.",
    };
  }
  return {
    reason: "safe_fallback",
    summary: "Francis is holding safe pass-through.",
  };
}

function deriveOwnershipModeLabel(authority = {}) {
  if (cleanText(authority?.modeLabel)) {
    return cleanText(authority.modeLabel);
  }
  if (authority?.localStopped) {
    return "Stopped";
  }
  if (authority?.pauseHeld) {
    return "Paused";
  }
  if (authority?.cursorLive) {
    return "Act";
  }
  if (authority?.cursorArmed) {
    return "Assist";
  }
  return "Observe";
}

function deriveOwnershipGovernorState({
  authority = {},
  restricted = false,
  userOverrideActive = false,
} = {}) {
  if (restricted) {
    if (authority?.pauseHeld) {
      return ORB_OWNERSHIP_GOVERNOR_STATES.PAUSED;
    }
    return ORB_OWNERSHIP_GOVERNOR_STATES.DEGRADED;
  }
  if (userOverrideActive) {
    return ORB_OWNERSHIP_GOVERNOR_STATES.USER_OVERRIDE;
  }
  if (authority?.cursorLive) {
    return ORB_OWNERSHIP_GOVERNOR_STATES.ACT;
  }
  if (authority?.cursorArmed) {
    return ORB_OWNERSHIP_GOVERNOR_STATES.ASSIST;
  }
  return ORB_OWNERSHIP_GOVERNOR_STATES.OBSERVE;
}

function buildOrbOwnershipState({
  requested = ORB_OWNERSHIP_STATES.PASS_THROUGH,
  authority = {},
  runtimeHealth = {},
  governor = {},
  captureSuspended = false,
  lensVisible = false,
  overlayIgnoreMouseEvents = false,
  orbIgnoreMouseEvents = true,
  foregroundWindow = null,
  shellPid = null,
  nowMs = Date.now(),
} = {}) {
  const requestedMode = normalizeOrbOwnershipRequest(requested);
  const normalizedGovernor = normalizeOrbOwnershipGovernor(governor);
  const restricted = isRestrictedRuntime({ authority, runtimeHealth, captureSuspended });
  const lensInteractive = Boolean(lensVisible) && !Boolean(overlayIgnoreMouseEvents);
  const userOverrideActive =
    !restricted
    && !lensInteractive
    && isOrbOwnershipUserOverrideActive(normalizedGovernor, nowMs);
  const sameProcessForeground =
    Number.isFinite(Number(shellPid)) && Number.isFinite(Number(foregroundWindow?.pid))
      ? Number(foregroundWindow.pid) === Number(shellPid)
      : null;
  const modeLabel = deriveOwnershipModeLabel(authority);

  let state = ORB_OWNERSHIP_STATES.PASS_THROUGH;
  let reason = "pass_through";
  let summary = "Orb input is passing through to the desktop.";
  let authorityLabel = "Pass-through";

  if (lensInteractive) {
    const restrictedDetail = summarizeRestrictedReason({ authority, runtimeHealth, captureSuspended });
    state = ORB_OWNERSHIP_STATES.INTERACTABLE_LENS;
    reason = restricted ? "lens_only_safe_fallback" : "lens_visible";
    summary = restricted
      ? `Lens remains interactive while the Orb stays in safe fallback. ${restrictedDetail.summary}`
      : "Lens is the active interactive surface.";
    authorityLabel = "Lens active";
  } else if (userOverrideActive) {
    state = ORB_OWNERSHIP_STATES.PASS_THROUGH;
    reason = "user_override";
    summary = "User override is active. Francis yielded orb input.";
    authorityLabel = "User override";
  } else if (!restricted && requestedMode === ORB_OWNERSHIP_STATES.INTERACTABLE_ORB) {
    state = ORB_OWNERSHIP_STATES.INTERACTABLE_ORB;
    reason = "orb_claimed";
    summary = authority?.cursorLive
      ? "Orb controls are active while Francis holds live cursor authority."
      : "Orb controls are the active interactive surface.";
    authorityLabel = authority?.cursorLive ? "Cursor live" : "Orb engaged";
  } else if (restricted) {
    const restrictedDetail = summarizeRestrictedReason({ authority, runtimeHealth, captureSuspended });
    state = ORB_OWNERSHIP_STATES.RESTRICTED;
    reason = restrictedDetail.reason;
    summary = restrictedDetail.summary;
    authorityLabel = authority?.localStopped
      ? "Local stop"
      : authority?.pauseHeld
        ? "Paused locally"
        : String(runtimeHealth?.status || "").trim().toLowerCase() === "disconnected" || authority?.disconnected
          ? "Disconnected"
          : String(runtimeHealth?.status || "").trim().toLowerCase() === "recovering"
            ? "Recovery hold"
            : captureSuspended
              ? "Capture hold"
              : "Degraded";
  }

  const governorState = deriveOwnershipGovernorState({
    authority,
    restricted,
    userOverrideActive,
  });
  const engaged = state === ORB_OWNERSHIP_STATES.INTERACTABLE_ORB || state === ORB_OWNERSHIP_STATES.INTERACTABLE_LENS;

  return {
    requestedMode,
    state,
    reason,
    summary,
    modeLabel,
    authorityLabel,
    governorState,
    passThrough: state === ORB_OWNERSHIP_STATES.PASS_THROUGH || state === ORB_OWNERSHIP_STATES.RESTRICTED,
    engaged,
    nonPassThrough: engaged,
    orbInteractive: state === ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    lensInteractive,
    safeFallback: restricted,
    restricted,
    canClaimOrbInteraction: !restricted && !lensInteractive && !userOverrideActive,
    shouldIgnoreOrbMouseEvents: state !== ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    foregroundMatchesShell: sameProcessForeground,
    userOverrideActive,
    overrideExpiresAtMs: userOverrideActive ? normalizedGovernor.userOverrideUntilMs : 0,
    overrideReason: userOverrideActive ? normalizedGovernor.userOverrideReason : "",
  };
}

function shouldResetOrbOwnershipForForeground({
  ownership = {},
  foregroundWindow = null,
  shellPid = null,
} = {}) {
  if (String(ownership?.state || "") !== ORB_OWNERSHIP_STATES.INTERACTABLE_ORB) {
    return false;
  }
  if (!Number.isFinite(Number(shellPid)) || !Number.isFinite(Number(foregroundWindow?.pid))) {
    return false;
  }
  return Number(foregroundWindow.pid) !== Number(shellPid);
}

module.exports = {
  ORB_OWNERSHIP_STATES,
  ORB_OWNERSHIP_GOVERNOR_STATES,
  ORB_OWNERSHIP_USER_OVERRIDE_HOLD_MS,
  armOrbOwnershipUserOverride,
  buildOrbOwnershipState,
  buildDefaultOrbOwnershipGovernor,
  clearOrbOwnershipUserOverride,
  isOrbOwnershipUserOverrideActive,
  isOrbOwnershipUserOverrideReason,
  normalizeOrbOwnershipRequest,
  normalizeOrbOwnershipGovernor,
  shouldClearOrbOwnershipUserOverrideForReason,
  shouldResetOrbOwnershipForForeground,
};
