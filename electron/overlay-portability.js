const fs = require("node:fs");
const path = require("node:path");

const { normalizeStartupProfile } = require("./startup-profile");

const PORTABILITY_STATE_FILE = "overlay-portability.json";
const PORTABILITY_STATE_VERSION = 1;

function getPortabilityStatePath(userDataPath) {
  return path.join(userDataPath, PORTABILITY_STATE_FILE);
}

function buildDefaultPortabilityState() {
  return {
    version: PORTABILITY_STATE_VERSION,
    lastExportAt: null,
    lastExportPath: null,
    lastImportAt: null,
    lastImportPath: null,
    lastImportStatus: "idle",
    lastImportMessage: null,
  };
}

function normalizePortabilityState(raw) {
  const defaults = buildDefaultPortabilityState();
  if (!raw || typeof raw !== "object") {
    return defaults;
  }
  return {
    version: PORTABILITY_STATE_VERSION,
    lastExportAt: typeof raw.lastExportAt === "string" ? raw.lastExportAt : null,
    lastExportPath: typeof raw.lastExportPath === "string" ? raw.lastExportPath : null,
    lastImportAt: typeof raw.lastImportAt === "string" ? raw.lastImportAt : null,
    lastImportPath: typeof raw.lastImportPath === "string" ? raw.lastImportPath : null,
    lastImportStatus: typeof raw.lastImportStatus === "string" ? raw.lastImportStatus : defaults.lastImportStatus,
    lastImportMessage: typeof raw.lastImportMessage === "string" ? raw.lastImportMessage : null,
  };
}

function loadPortabilityState(userDataPath) {
  const filePath = getPortabilityStatePath(userDataPath);
  try {
    return normalizePortabilityState(JSON.parse(fs.readFileSync(filePath, "utf8")));
  } catch {
    return buildDefaultPortabilityState();
  }
}

function savePortabilityState(userDataPath, state) {
  const filePath = getPortabilityStatePath(userDataPath);
  const normalized = normalizePortabilityState(state);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(normalized, null, 2), "utf8");
  return normalized;
}

function buildOverlayExportPayload({
  buildIdentity = "unknown",
  exportedAt = new Date().toISOString(),
  preferences = {},
} = {}) {
  return {
    version: 1,
    exportedAt,
    buildIdentity,
    shell: {
      startupProfile: normalizeStartupProfile(preferences.startupProfile),
      alwaysOnTop: preferences.alwaysOnTop !== false,
      ignoreMouseEvents: Boolean(preferences.ignoreMouseEvents),
      targetDisplayId: Number.isFinite(Number(preferences.targetDisplayId))
        ? Number(preferences.targetDisplayId)
        : null,
      windowBounds:
        preferences.windowBounds && typeof preferences.windowBounds === "object"
          ? {
              x: Number(preferences.windowBounds.x) || 0,
              y: Number(preferences.windowBounds.y) || 0,
              width: Number(preferences.windowBounds.width) || 0,
              height: Number(preferences.windowBounds.height) || 0,
            }
          : null,
    },
    limits: {
      launchAtLogin: "Not imported automatically. Review locally after migration.",
      sessionContinuity: "Crash recovery and last-run continuity are not imported as live state.",
      approvals: "Approvals and authority do not transfer through shell portability.",
    },
  };
}

function extractPortablePreferences(raw) {
  if (!raw || typeof raw !== "object" || !raw.shell || typeof raw.shell !== "object") {
    throw new Error("Portable shell payload is missing the shell block");
  }

  return {
    startupProfile: normalizeStartupProfile(raw.shell.startupProfile),
    alwaysOnTop: raw.shell.alwaysOnTop !== false,
    ignoreMouseEvents: Boolean(raw.shell.ignoreMouseEvents),
    targetDisplayId: Number.isFinite(Number(raw.shell.targetDisplayId))
      ? Number(raw.shell.targetDisplayId)
      : null,
    windowBounds:
      raw.shell.windowBounds && typeof raw.shell.windowBounds === "object"
        ? {
            x: Number(raw.shell.windowBounds.x) || 0,
            y: Number(raw.shell.windowBounds.y) || 0,
            width: Number(raw.shell.windowBounds.width) || 0,
            height: Number(raw.shell.windowBounds.height) || 0,
          }
        : null,
  };
}

module.exports = {
  PORTABILITY_STATE_FILE,
  PORTABILITY_STATE_VERSION,
  buildDefaultPortabilityState,
  buildOverlayExportPayload,
  extractPortablePreferences,
  getPortabilityStatePath,
  loadPortabilityState,
  normalizePortabilityState,
  savePortabilityState,
};
