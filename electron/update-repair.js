function buildRepairPlan({
  update = null,
  preflight = null,
  migration = null,
  recovery = null,
  rollback = null,
  portability = null,
  support = null,
  hud = null,
  provider = null,
  decommission = null,
} = {}) {
  const blocked = Number(preflight?.blocked || 0);
  const attention = Number(preflight?.attention || 0);
  const migrationBlocked = Number(migration?.blocked || 0);
  const migrationAttention = Number(migration?.attention || 0);
  const rollbackCount = Number(rollback?.count || 0);
  const updatePending = Boolean(update?.pendingNotice);
  const recoveryNeeded = Boolean(recovery?.needed);
  const hudMode = String(hud?.mode || "unknown");
  const portabilityBlocked = String(portability?.lastImportStatus || "idle") === "blocked";
  const supportExported = Boolean(support?.lastBundleAt);
  const providerSeverity = String(provider?.severity || "low");

  let severity = "low";
  let summary = "Repair posture is nominal.";
  if (blocked > 0 || migrationBlocked > 0) {
    severity = "high";
    summary =
      migrationBlocked > 0
        ? `${migrationBlocked} retained state migration check${migrationBlocked === 1 ? " is" : "s are"} blocked. Repair before trusting continuity.`
        : `${blocked} startup or continuity checks are blocked. Repair before trusting the updated shell.`;
  } else if (recoveryNeeded || updatePending || attention > 0 || migrationAttention > 0 || portabilityBlocked || hudMode === "crashed" || providerSeverity === "high" || providerSeverity === "medium") {
    severity = "medium";
    summary = updatePending
      ? "A new build or schema change needs inspection before continuity is treated as settled."
      : migrationAttention > 0
        ? `${migrationAttention} retained state migration check${migrationAttention === 1 ? "" : "s"} need review before continuity is treated as settled.`
      : recoveryNeeded
        ? "Recovery needs inspection before the shell is treated as fully normal."
        : providerSeverity === "high" || providerSeverity === "medium"
          ? String(provider?.summary || "Provider posture needs inspection before model-backed execution is trusted.")
        : portabilityBlocked
          ? "A shell import was blocked and needs operator repair."
          : `${attention} checks still need attention.`;
  }

  const steps = [];
  if (updatePending) {
    steps.push("Review update posture, previous build, and schema state before acknowledging the update.");
  }
  if (migrationBlocked > 0 || migrationAttention > 0) {
    steps.push("Review retained shell state versions and decide whether to normalize in place, reset local shell state, or restore a rollback snapshot.");
  }
  if (providerSeverity === "high" || providerSeverity === "medium") {
    steps.push("Inspect provider posture, declare the active provider path explicitly, and verify fallback behavior before trusting model-backed execution.");
  }
  if (blocked > 0 || recoveryNeeded || hudMode === "crashed") {
    steps.push("Restart the managed HUD and confirm preflight returns to nominal or attention instead of blocked.");
  }
  if (rollbackCount > 0 && (blocked > 0 || migrationBlocked > 0 || recoveryNeeded || portabilityBlocked)) {
    steps.push("Restore the latest rollback snapshot if the new posture cannot be stabilized cleanly.");
  }
  if (!supportExported && (blocked > 0 || migrationBlocked > 0 || migrationAttention > 0 || recoveryNeeded || portabilityBlocked || updatePending)) {
    steps.push("Export a support bundle before invasive repair so lifecycle and runtime posture leave evidence.");
  }
  if (decommission?.userDataPath && (blocked > 0 || migrationBlocked > 0 || migrationAttention > 0 || portabilityBlocked)) {
    steps.push("Inspect the user-data root directly if retained shell state or imported posture looks inconsistent.");
  }
  if (!steps.length) {
    steps.push("No repair actions are required right now.");
  }

  const actions = {
    acknowledge_update: {
      enabled: updatePending,
      label: "Acknowledge Update",
    },
    restart_hud: {
      enabled: hudMode !== "external",
      label: "Restart HUD",
    },
    reset_shell_state: {
      enabled: migrationBlocked > 0 || migrationAttention > 0,
      label: "Reset Shell State",
    },
    restore_snapshot: {
      enabled: rollbackCount > 0,
      label: "Restore Latest Snapshot",
    },
    export_support_bundle: {
      enabled: true,
      label: "Export Support Bundle",
    },
    open_user_data: {
      enabled: Boolean(decommission?.userDataPath),
      label: "Open User Data",
    },
  };

  const cards = [
    {
      label: "Summary",
      value: summary,
      tone: severity,
    },
    {
      label: "Blocked Checks",
      value: String(blocked),
      tone: blocked > 0 ? "high" : "low",
    },
    {
      label: "Attention Checks",
      value: String(attention),
      tone: attention > 0 ? "medium" : "low",
    },
    {
      label: "Migration",
      value:
        migrationBlocked > 0
          ? `${migrationBlocked} blocked`
          : migrationAttention > 0
            ? `${migrationAttention} need review`
            : "current",
      tone: migrationBlocked > 0 ? "high" : migrationAttention > 0 ? "medium" : "low",
    },
    {
      label: "Rollback",
      value: rollbackCount > 0 ? `${rollbackCount} snapshot${rollbackCount === 1 ? "" : "s"} available` : "No rollback snapshot available",
      tone: rollbackCount > 0 ? "medium" : "low",
    },
    {
      label: "Support Export",
      value: supportExported ? String(support.lastBundleAt) : "No support bundle exported",
      tone: supportExported ? "medium" : "low",
    },
    {
      label: "Portability",
      value: portabilityBlocked
        ? String(portability?.lastImportMessage || "Portable shell import blocked")
        : String(portability?.lastImportStatus || "idle"),
      tone: portabilityBlocked ? "high" : "low",
    },
    {
      label: "Provider",
      value: String(provider?.activeProviderLabel || "none"),
      tone: providerSeverity,
    },
  ];

  return {
    severity,
    summary,
    steps,
    cards,
    actions,
  };
}

module.exports = {
  buildRepairPlan,
};
