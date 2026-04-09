function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function buildDiagnostics(safetyState = {}) {
  return {
    localError: cleanText(safetyState.localError || ""),
    remoteError: cleanText(safetyState.remoteError || ""),
  };
}

function normalizeRemoteSyncStatus(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "pending" || normalized === "failed") {
    return normalized;
  }
  return "current";
}

function buildOrbControlState({
  authorityState = {},
  hudState = {},
  recovery = {},
  inputState = {},
  ignoreMouseEvents = true,
  safetyState = {},
} = {}) {
  const diagnostics = buildDiagnostics(safetyState);
  const localStopped = Boolean(safetyState.localStopped);
  const pauseHeld = Boolean(safetyState.pauseHeld);
  const remoteSyncStatus = normalizeRemoteSyncStatus(safetyState.remoteSyncStatus);
  const disconnected = Boolean(safetyState.disconnected || !hudState?.ready);
  const degraded = Boolean(
    localStopped
      || pauseHeld
      || disconnected
      || recovery?.needed
      || safetyState.degraded
      || remoteSyncStatus !== "current",
  );
  const eligible = Boolean(authorityState.eligible) && !localStopped && !pauseHeld && !disconnected;
  const cursorLive = Boolean(authorityState.live) && !localStopped && !pauseHeld && !disconnected;
  const cursorArmed = eligible && !cursorLive;
  const humanActive = Boolean(inputState?.humanActive ?? true);
  const state = localStopped
    ? "local_stopped"
    : pauseHeld
      ? "paused"
      : disconnected
        ? "disconnected"
        : degraded
          ? "degraded"
          : cursorLive
            ? "francis_authority"
            : cursorArmed
              ? "idle_armed"
              : String(authorityState.state || (humanActive ? "human_active" : "ambient")).trim().toLowerCase() || "human_active";
  const modeLabel = localStopped
    ? "Stopped"
    : cursorLive
      ? "Act"
      : cursorArmed || pauseHeld
        ? "Assist"
        : "Observe";
  const authorityLabel = localStopped
    ? "Local stop"
    : disconnected
      ? "Disconnected"
      : pauseHeld
        ? remoteSyncStatus === "failed"
          ? "Queue clear failed"
          : "Paused locally"
        : cursorLive
          ? "Cursor live"
          : cursorArmed
            ? "Cursor armed"
            : "Observe only";
  const summary = localStopped
    ? remoteSyncStatus === "failed"
      ? "Local stop confirmed. Remote sync failed."
      : remoteSyncStatus === "pending"
        ? "Local stop confirmed. Remote sync pending."
        : "Local stop confirmed."
    : pauseHeld
      ? remoteSyncStatus === "failed"
        ? "Paused locally. Remote queue clear failed."
        : "Paused locally while remote queue clear is pending."
      : disconnected
        ? "HUD disconnected. Human control remains primary."
        : degraded
          ? cleanText(safetyState.summary || "Orb control is degraded. Human control remains primary.")
          : cursorLive
            ? "Away cursor authority is live."
            : cursorArmed
              ? "Away cursor authority is armed and waiting."
              : "Human control remains primary.";
  const detail = localStopped
    ? cleanText(safetyState.detail || summary || "Local authority dropped immediately.")
    : pauseHeld
      ? cleanText(
          safetyState.detail
            || (remoteSyncStatus === "failed"
              ? "Francis released local authority, but the queued remote clear did not confirm."
              : "Francis released local authority and is holding the cursor locally until queue clear confirms."),
        )
      : disconnected
        ? cleanText(safetyState.detail || recovery?.message || "The local operator stack is unreachable.")
        : degraded
          ? cleanText(safetyState.detail || recovery?.message || "Human control remains primary while Francis holds a degraded local posture.")
          : cleanText(safetyState.detail || authorityState.lastReleaseReason || summary);

  return {
    state,
    eligible,
    live: cursorLive,
    cursorLive,
    cursorArmed,
    idleSeconds: Number(authorityState.idleSeconds || 0),
    lastObservedIdleSeconds: Number(authorityState.lastObservedIdleSeconds || 0),
    thresholdSeconds: Number(authorityState.thresholdSeconds || 30),
    claimedCommandId: String(authorityState.claimedCommandId || ""),
    activeCommandKind: cleanText(authorityState.activeCommandKind || "").toLowerCase(),
    executionPhase: cleanText(authorityState.executionPhase || "").toLowerCase(),
    executionSummary: cleanText(authorityState.executionSummary || ""),
    executionDetail: cleanText(authorityState.executionDetail || ""),
    executionTarget:
      authorityState.executionTarget && typeof authorityState.executionTarget === "object"
        ? authorityState.executionTarget
        : null,
    lastHumanActivitySignalAtMs: Number(authorityState.lastHumanActivitySignalAtMs || 0),
    lastHumanActivitySignalSource: String(authorityState.lastHumanActivitySignalSource || ""),
    lastReleaseReason: String(authorityState.lastReleaseReason || ""),
    lastHumanReturnReason: String(authorityState.lastHumanReturnReason || ""),
    localStopped,
    pauseHeld,
    remoteSyncStatus,
    disconnected,
    degraded,
    passThrough: Boolean(ignoreMouseEvents),
    inputOwnership: Boolean(ignoreMouseEvents) ? "pass_through" : "interactive",
    canStop: !localStopped && (cursorLive || cursorArmed || pauseHeld || degraded || disconnected),
    canPause: !localStopped && !cursorLive && !disconnected,
    modeLabel,
    authorityLabel,
    summary,
    detail,
    safetySummary: cleanText(safetyState.summary || ""),
    safetyDetail: cleanText(safetyState.detail || ""),
    diagnostics,
  };
}

function buildPauseAuthorityResult({
  activeLive = false,
  remoteSynced = false,
  remoteSyncStatus = "current",
  summary = "",
  detail = "",
} = {}) {
  if (activeLive) {
    return {
      ok: false,
      status: "use_stop",
      localPaused: false,
      remoteSynced: true,
      summary: "Francis is actively acting. Use Stop to interrupt the live commit.",
      detail: "Pause only clears queued authority work. It does not interrupt an active live commit.",
    };
  }
  const normalizedRemote = normalizeRemoteSyncStatus(remoteSyncStatus);
  return {
    ok: true,
    status: remoteSynced ? "paused" : "local_only",
    localPaused: true,
    remoteSynced: Boolean(remoteSynced),
    summary: cleanText(summary || (remoteSynced ? "Paused. Queued work cleared locally and remotely." : "Paused locally. Remote queue clear is still pending.")),
    detail: cleanText(detail || (normalizedRemote === "failed"
      ? "Human control remains primary, but the queued remote clear did not confirm."
      : "Human control remains primary while the queued remote clear catches up.")),
  };
}

module.exports = {
  buildOrbControlState,
  buildPauseAuthorityResult,
  normalizeRemoteSyncStatus,
};
