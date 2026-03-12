const path = require("node:path");

const { BACKUP_ROOT_DIR } = require("./backup-state");

function quotePowerShellLiteral(value) {
  return `'${String(value || "").replaceAll("'", "''")}'`;
}

function uniquePaths(paths) {
  return [...new Set((paths || []).filter((entry) => typeof entry === "string" && entry.trim()))];
}

function buildRemovalCommand(paths) {
  const targets = uniquePaths(paths);
  if (!targets.length) {
    return null;
  }
  return targets
    .map(
      (targetPath) =>
        `if (Test-Path -LiteralPath ${quotePowerShellLiteral(targetPath)}) { Remove-Item -LiteralPath ${quotePowerShellLiteral(targetPath)} -Recurse -Force }`,
    )
    .join("; ");
}

function buildDecommissionPlan({
  buildIdentity = "unknown",
  distribution = "source",
  installRoot = null,
  execPath = null,
  userDataPath = null,
  workspaceRoot = null,
  retainedState = null,
  rollbackState = null,
  portabilityState = null,
  launchAtLogin = null,
} = {}) {
  const retainedItems = Array.isArray(retainedState?.items) ? retainedState.items : [];
  const removableItems = retainedItems.filter((item) => item?.removable && (item?.exists || item?.enabled));
  const workspaceItem = retainedItems.find((item) => item?.id === "workspace_root") || null;
  const rollbackCount = Number(rollbackState?.count || 0);
  const rollbackRoot = userDataPath ? path.join(userDataPath, BACKUP_ROOT_DIR) : null;
  const shellResiduePaths = uniquePaths([
    ...removableItems.map((item) => item.path).filter(Boolean),
    rollbackCount > 0 ? rollbackRoot : null,
  ]);
  const shellResidueCommand = buildRemovalCommand(shellResiduePaths);
  const continuityCommand = workspaceItem?.exists ? buildRemovalCommand([workspaceItem.path]) : null;
  const exportRecommended = Boolean(removableItems.length || rollbackCount > 0);
  const lastExportAt = typeof portabilityState?.lastExportAt === "string" ? portabilityState.lastExportAt : null;
  const startupEnabled = Boolean(launchAtLogin?.available && launchAtLogin?.enabled);
  const summary =
    shellResiduePaths.length > 0 || startupEnabled
      ? "Francis can be removed cleanly, but shell residue and startup entry should be reviewed before uninstall."
      : "No retained shell residue is currently blocking a clean uninstall posture.";

  const steps = [
    exportRecommended
      ? "Export shell posture first if you want the overlay layout, startup profile, or display targeting on another machine."
      : "No shell posture export is currently necessary unless you want a copy before removal.",
    "Quit Francis Overlay before deleting shell residue or uninstalling the app.",
    distribution === "portable"
      ? "Delete the portable overlay directory after the shell is closed."
      : "Run the NSIS uninstaller or remove Francis Overlay from Windows Apps after the shell is closed.",
    shellResidueCommand
      ? "Run the generated PowerShell cleanup command if you want reinstall to start without leftover shell residue."
      : "No shell-residue cleanup command is needed right now.",
    workspaceItem?.exists
      ? "Decide separately whether to keep or purge workspace continuity. Receipts, runs, and mission history live there and are not removed by default."
      : "No workspace continuity root is currently present.",
  ];

  const cards = [
    {
      label: "Summary",
      value: summary,
      tone: shellResiduePaths.length > 0 || startupEnabled ? "medium" : "low",
    },
    {
      label: "Shell Residue",
      value: shellResiduePaths.length > 0 ? `${shellResiduePaths.length} removable paths remain.` : "No removable shell paths remain.",
      tone: shellResiduePaths.length > 0 ? "medium" : "low",
    },
    {
      label: "Rollback Backups",
      value: rollbackCount > 0 ? `${rollbackCount} rollback snapshot${rollbackCount === 1 ? "" : "s"} remain under user data.` : "No rollback snapshots remain.",
      tone: rollbackCount > 0 ? "medium" : "low",
    },
    {
      label: "Workspace Continuity",
      value: workspaceItem?.exists
        ? `${workspaceItem.path} stays separate from shell cleanup by default.`
        : "No continuity root is present.",
      tone: workspaceItem?.exists ? "medium" : "low",
    },
    {
      label: "Startup Entry",
      value: startupEnabled ? "Launch At Login is still enabled and should be disabled before uninstall." : "No active startup entry remains.",
      tone: startupEnabled ? "high" : "low",
    },
    {
      label: "Last Export",
      value: lastExportAt || "No shell export recorded.",
      tone: lastExportAt ? "medium" : "low",
    },
  ];

  return {
    summary,
    buildIdentity,
    distribution,
    exportRecommended,
    installRoot,
    execPath,
    userDataPath,
    workspaceRoot: workspaceItem?.path || workspaceRoot || null,
    shellResiduePaths,
    shellResidueCommand,
    continuityCommand,
    steps,
    cards,
  };
}

module.exports = {
  buildDecommissionPlan,
  buildRemovalCommand,
};
