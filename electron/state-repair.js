const fs = require("node:fs");
const path = require("node:path");

const { SHELL_MIGRATION_SPECS, assessMigrationItem } = require("./state-migrations");
const {
  PREFERENCES_FILE,
  PREFERENCES_VERSION,
  buildDefaultPreferences,
  loadPreferences,
  resolvePrimaryDisplay,
  savePreferences,
} = require("./preferences");
const {
  SESSION_STATE_FILE,
  SESSION_STATE_VERSION,
  buildDefaultSessionState,
  loadSessionState,
  saveSessionState,
} = require("./session-state");
const {
  UPDATE_STATE_FILE,
  buildDefaultUpdateState,
  loadUpdateState,
  saveUpdateState,
} = require("./update-state");
const {
  PORTABILITY_STATE_FILE,
  PORTABILITY_STATE_VERSION,
  buildDefaultPortabilityState,
  loadPortabilityState,
  savePortabilityState,
} = require("./overlay-portability");
const {
  SUPPORT_STATE_FILE,
  SUPPORT_STATE_VERSION,
  buildDefaultSupportState,
  loadSupportState,
  saveSupportState,
} = require("./support-state");

const REPAIR_ARCHIVE_DIR = "overlay-repair-archive";

function getRepairArchiveRoot(userDataPath) {
  return path.join(userDataPath, REPAIR_ARCHIVE_DIR);
}

function getRepairSpec(targetId) {
  return SHELL_MIGRATION_SPECS.find((entry) => entry.id === targetId) || null;
}

function getSchemaOptions(context = {}) {
  return {
    buildIdentity: context.buildIdentity || "unknown",
    preferencesSchemaVersion: context.preferencesSchemaVersion ?? PREFERENCES_VERSION,
    sessionSchemaVersion: context.sessionSchemaVersion ?? SESSION_STATE_VERSION,
    portabilitySchemaVersion: context.portabilitySchemaVersion ?? PORTABILITY_STATE_VERSION,
    supportSchemaVersion: context.supportSchemaVersion ?? SUPPORT_STATE_VERSION,
    now: context.now || new Date().toISOString(),
  };
}

function getDisplayOptions(context = {}) {
  const displays = Array.isArray(context.displays) ? context.displays.filter(Boolean) : [];
  if (!displays.length) {
    throw new Error("Display context is required to repair overlay preferences.");
  }
  return {
    displays,
    primaryDisplayId: context.primaryDisplayId ?? displays.find((entry) => entry.primary)?.id ?? displays[0].id,
  };
}

function normalizeStateFile(userDataPath, targetId, context = {}) {
  switch (targetId) {
    case "preferences": {
      const { displays, primaryDisplayId } = getDisplayOptions(context);
      const normalized = loadPreferences(userDataPath, displays, primaryDisplayId);
      savePreferences(userDataPath, normalized, displays, primaryDisplayId);
      return {
        targetId,
        action: "normalized",
        summary: "Overlay preferences normalized in place.",
      };
    }
    case "session":
      saveSessionState(userDataPath, loadSessionState(userDataPath));
      return {
        targetId,
        action: "normalized",
        summary: "Session continuity normalized in place.",
      };
    case "update": {
      const options = getSchemaOptions(context);
      saveUpdateState(userDataPath, loadUpdateState(userDataPath, options), options);
      return {
        targetId,
        action: "normalized",
        summary: "Update posture normalized in place.",
      };
    }
    case "portability":
      savePortabilityState(userDataPath, loadPortabilityState(userDataPath));
      return {
        targetId,
        action: "normalized",
        summary: "Shell portability ledger normalized in place.",
      };
    case "support":
      saveSupportState(userDataPath, loadSupportState(userDataPath));
      return {
        targetId,
        action: "normalized",
        summary: "Support bundle ledger normalized in place.",
      };
    default:
      throw new Error(`Unsupported repair target: ${targetId}`);
  }
}

function resetStateFile(userDataPath, targetId, context = {}) {
  switch (targetId) {
    case "preferences": {
      const { displays, primaryDisplayId } = getDisplayOptions(context);
      const primaryDisplay = resolvePrimaryDisplay(displays, primaryDisplayId);
      savePreferences(userDataPath, buildDefaultPreferences(primaryDisplay), displays, primaryDisplayId);
      return {
        targetId,
        action: "reset",
        summary: "Overlay preferences reset to defaults.",
      };
    }
    case "session":
      saveSessionState(userDataPath, buildDefaultSessionState());
      return {
        targetId,
        action: "reset",
        summary: "Session continuity reset to defaults.",
      };
    case "update": {
      const options = getSchemaOptions(context);
      saveUpdateState(userDataPath, buildDefaultUpdateState(options), options);
      return {
        targetId,
        action: "reset",
        summary: "Update posture reset to defaults.",
      };
    }
    case "portability":
      savePortabilityState(userDataPath, buildDefaultPortabilityState());
      return {
        targetId,
        action: "reset",
        summary: "Shell portability ledger reset to defaults.",
      };
    case "support":
      saveSupportState(userDataPath, buildDefaultSupportState());
      return {
        targetId,
        action: "reset",
        summary: "Support bundle ledger reset to defaults.",
      };
    default:
      throw new Error(`Unsupported repair target: ${targetId}`);
  }
}

function quarantineStateFile(userDataPath, targetId) {
  const spec = getRepairSpec(targetId);
  if (!spec) {
    throw new Error(`Unsupported repair target: ${targetId}`);
  }

  const sourcePath = path.join(userDataPath, spec.fileName);
  if (!fs.existsSync(sourcePath)) {
    return null;
  }

  const archiveRoot = getRepairArchiveRoot(userDataPath);
  fs.mkdirSync(archiveRoot, { recursive: true });
  const archivePath = path.join(archiveRoot, `${new Date().toISOString().replaceAll(":", "-").replaceAll(".", "-")}-${spec.fileName}`);
  fs.renameSync(sourcePath, archivePath);
  return archivePath;
}

function repairShellState(userDataPath, context = {}) {
  const items = SHELL_MIGRATION_SPECS.map((spec) => assessMigrationItem(spec, userDataPath));
  const actions = [];

  for (const item of items) {
    if (item.status === "legacy") {
      actions.push({
        ...normalizeStateFile(userDataPath, item.id, context),
        tone: "medium",
        item,
      });
      continue;
    }

    if (item.status === "invalid" || item.status === "future") {
      const archivePath = quarantineStateFile(userDataPath, item.id);
      const reset = resetStateFile(userDataPath, item.id, context);
      actions.push({
        ...reset,
        action: "quarantined_and_reset",
        archivePath,
        tone: "high",
        item,
        summary: archivePath
          ? `${item.label} quarantined to ${archivePath} and reset to defaults.`
          : `${item.label} reset to defaults.`,
      });
    }
  }

  const normalizedCount = actions.filter((entry) => entry.action === "normalized").length;
  const quarantinedCount = actions.filter((entry) => entry.action === "quarantined_and_reset").length;

  return {
    repairedCount: actions.length,
    normalizedCount,
    quarantinedCount,
    archiveRoot: quarantinedCount > 0 ? getRepairArchiveRoot(userDataPath) : null,
    actions,
    summary: actions.length
      ? `${actions.length} retained state file${actions.length === 1 ? "" : "s"} repaired | ${normalizedCount} normalized | ${quarantinedCount} quarantined and reset`
      : "No retained state repair actions were required.",
  };
}

module.exports = {
  REPAIR_ARCHIVE_DIR,
  getRepairArchiveRoot,
  normalizeStateFile,
  quarantineStateFile,
  repairShellState,
  resetStateFile,
};
