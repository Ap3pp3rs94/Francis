const fs = require("node:fs");
const path = require("node:path");

const { PREFERENCES_FILE } = require("./preferences");
const { SESSION_STATE_FILE } = require("./session-state");
const { UPDATE_STATE_FILE } = require("./update-state");
const { PORTABILITY_STATE_FILE } = require("./overlay-portability");
const { SUPPORT_STATE_FILE } = require("./support-state");

const SHELL_STATE_FILES = [
  {
    id: "preferences",
    label: "Overlay Preferences",
    fileName: PREFERENCES_FILE,
    removable: true,
    description: "Overlay bounds, target display, click-through, topmost, and startup profile.",
  },
  {
    id: "session",
    label: "Session Continuity",
    fileName: SESSION_STATE_FILE,
    removable: true,
    description: "Last launch/exit posture and HUD crash continuity.",
  },
  {
    id: "update",
    label: "Update Posture",
    fileName: UPDATE_STATE_FILE,
    removable: true,
    description: "Build identity, update notice, and schema compatibility posture.",
  },
  {
    id: "portability",
    label: "Shell Portability",
    fileName: PORTABILITY_STATE_FILE,
    removable: true,
    description: "Most recent shell export/import activity and limits.",
  },
  {
    id: "support",
    label: "Support Bundle Ledger",
    fileName: SUPPORT_STATE_FILE,
    removable: true,
    description: "Most recent governed support-bundle export activity.",
  },
];

function statIfPresent(targetPath) {
  try {
    return fs.statSync(targetPath);
  } catch {
    return null;
  }
}

function countDirectoryEntries(rootPath) {
  try {
    return fs.readdirSync(rootPath).length;
  } catch {
    return 0;
  }
}

function describeRetainedState({
  userDataPath,
  workspaceRoot = null,
  launchAtLogin = null,
} = {}) {
  const shellItems = SHELL_STATE_FILES.map((entry) => {
    const filePath = path.join(userDataPath, entry.fileName);
    const stat = statIfPresent(filePath);
    return {
      id: entry.id,
      label: entry.label,
      category: "shell_state",
      path: filePath,
      exists: Boolean(stat),
      sizeBytes: stat ? stat.size : 0,
      removable: entry.removable,
      description: entry.description,
    };
  });

  const workspaceStat = workspaceRoot ? statIfPresent(workspaceRoot) : null;
  const workspaceItem = {
    id: "workspace_root",
    label: "Workspace Continuity Root",
    category: "continuity_root",
    path: workspaceRoot,
    exists: Boolean(workspaceStat),
    sizeBytes: workspaceStat ? workspaceStat.size : 0,
    entryCount: workspaceStat && workspaceStat.isDirectory() ? countDirectoryEntries(workspaceRoot) : 0,
    removable: false,
    description: "Receipts, runs, missions, and other continuity artifacts remain separate from shell settings.",
  };

  const startupItem = {
    id: "launch_at_login",
    label: "Launch At Login",
    category: "startup_entry",
    path: null,
    exists: Boolean(launchAtLogin?.available),
    enabled: Boolean(launchAtLogin?.enabled),
    removable: Boolean(launchAtLogin?.available),
    description: launchAtLogin?.available
      ? "Windows login-item registration stays machine-local and must be reviewed explicitly."
      : "Launch-at-login is unavailable on this runtime.",
  };

  const items = [...shellItems, workspaceItem, startupItem];
  const removableCount = items.filter((item) => item.removable && (item.exists || item.enabled)).length;
  const retainedCount = items.filter((item) => item.exists).length;

  return {
    summary:
      retainedCount > 0
        ? `${retainedCount} retained surfaces detected; ${removableCount} can be cleared without touching workspace continuity.`
        : "No retained shell surfaces detected.",
    removableCount,
    retainedCount,
    items,
  };
}

module.exports = {
  SHELL_STATE_FILES,
  describeRetainedState,
};
