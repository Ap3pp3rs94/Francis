function cleanMessage(value, fallback = "") {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text || fallback;
}

function buildPanicStopResult({
  queueCleared = true,
  authorityReleased = true,
  localError = null,
  remoteResponse = null,
  remoteError = null,
} = {}) {
  const localStopped = Boolean(authorityReleased) && !cleanMessage(localError);
  const remoteSynced = Boolean(queueCleared) && !cleanMessage(remoteError);
  const status = localStopped
    ? remoteSynced
      ? "stopped"
      : "local_only"
    : "degraded";
  const summary = localStopped
    ? remoteSynced
      ? "Panic stop engaged. Local authority dropped."
      : "Panic stop engaged locally. Remote sync is pending."
    : "Panic stop degraded. Local authority may still need inspection.";
  const detail = localStopped
    ? remoteSynced
      ? "Queued actions were cleared and cursor authority was returned to the user."
      : "Cursor authority was returned locally. Francis is holding the stop posture until upstream confirmation catches up."
    : "Local stop work did not complete cleanly. Inspect diagnostics before assuming the surface is safe.";
  return {
    ok: localStopped,
    status,
    localStopped,
    remoteSynced,
    summary,
    detail,
    remoteResponse: remoteResponse && typeof remoteResponse === "object" ? remoteResponse : null,
    diagnostics: {
      localError: cleanMessage(localError),
      remoteError: cleanMessage(remoteError),
    },
  };
}

module.exports = {
  buildPanicStopResult,
};
