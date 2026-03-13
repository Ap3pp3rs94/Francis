function buildDegradedModePosture({
  preflight = null,
  migration = null,
  update = null,
  recovery = null,
  hud = null,
  startupProfile = null,
} = {}) {
  const blockedChecks = Number(preflight?.blocked || 0);
  const attentionChecks = Number(preflight?.attention || 0);
  const blockedMigrations = Number(migration?.blocked || 0);
  const attentionMigrations = Number(migration?.attention || 0);
  const hudMode = String(hud?.mode || "unknown");
  const hudReady = hud?.ready !== false;
  const updatePending = Boolean(update?.pendingNotice);
  const recoveryNeeded = Boolean(recovery?.needed);

  let mode = "nominal";
  let summary = "Shell posture is nominal.";

  if (blockedChecks > 0 || blockedMigrations > 0 || hudMode === "crashed") {
    mode = "restricted";
    summary =
      blockedMigrations > 0
        ? `${blockedMigrations} migration check${blockedMigrations === 1 ? " is" : "s are"} blocked. Treat continuity as unsafe until repaired.`
        : hudMode === "crashed"
          ? "The managed HUD crashed. Treat the overlay as restricted until runtime health is restored."
          : `${blockedChecks} preflight check${blockedChecks === 1 ? " is" : "s are"} blocked. Treat the shell as restricted until repaired.`;
  } else if (attentionChecks > 0 || attentionMigrations > 0 || updatePending || recoveryNeeded || !hudReady) {
    mode = "reduced";
    summary = updatePending
      ? "A new build or schema change is pending review. Continuity is visible, but not fully settled."
      : attentionMigrations > 0
        ? `${attentionMigrations} migration check${attentionMigrations === 1 ? "" : "s"} need review before continuity is treated as current.`
        : recoveryNeeded
          ? "Recovery needs inspection before the shell is treated as fully normal."
          : !hudReady
            ? "The managed HUD is not fully ready. Keep work inspection-first until runtime health returns."
            : `${attentionChecks} shell checks need attention. Operate in reduced mode until they clear.`;
  }

  const continuityTrust = mode === "restricted" ? "unsafe" : mode === "reduced" ? "review" : "current";
  const pointerPosture = mode === "restricted" ? "interactive_only" : "flexible";
  const recommendedStartupProfile =
    mode === "restricted"
      ? "core_only"
      : recoveryNeeded
        ? "recovery_safe"
        : String(startupProfile?.requested || "operator");

  const restrictions = [];
  if (mode === "restricted") {
    restrictions.push("Keep the overlay interactive; do not rely on click-through while repair is still active.");
    restrictions.push("Treat retained continuity as inspection-only until blocked checks or migrations are cleared.");
  } else if (mode === "reduced") {
    restrictions.push("Treat continuity as review-first until update, migration, or recovery posture returns to current.");
  } else {
    restrictions.push("No degraded-mode restrictions are active.");
  }

  return {
    mode,
    summary,
    continuityTrust,
    pointerPosture,
    recommendedStartupProfile,
    restrictions,
    cards: [
      {
        label: "Summary",
        value: summary,
        tone: mode === "restricted" ? "high" : mode === "reduced" ? "medium" : "low",
      },
      {
        label: "Mode",
        value: mode,
        tone: mode === "restricted" ? "high" : mode === "reduced" ? "medium" : "low",
      },
      {
        label: "Continuity",
        value: continuityTrust,
        tone: continuityTrust === "unsafe" ? "high" : continuityTrust === "review" ? "medium" : "low",
      },
      {
        label: "Pointer",
        value: pointerPosture,
        tone: pointerPosture === "interactive_only" ? "medium" : "low",
      },
      {
        label: "Recommended Startup",
        value: recommendedStartupProfile,
        tone: recommendedStartupProfile === "core_only" ? "medium" : "low",
      },
      {
        label: "HUD Runtime",
        value: hudMode,
        tone: hudMode === "crashed" ? "high" : hudMode === "managed" ? "medium" : "low",
      },
    ],
  };
}

module.exports = {
  buildDegradedModePosture,
};
