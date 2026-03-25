function getScheduledHudRecoveryReason(hudState) {
  const safeState = hudState && typeof hudState === "object" ? hudState : null;
  if (!safeState) {
    return "";
  }
  if (safeState.ready) {
    return "";
  }
  if (!safeState.allowManagedStart) {
    return "";
  }
  const mode = String(safeState.mode || "idle").trim().toLowerCase();
  if (!mode || mode === "starting" || mode === "disabled") {
    return "";
  }
  return `hud-not-ready:${mode}`;
}

module.exports = {
  getScheduledHudRecoveryReason,
};
