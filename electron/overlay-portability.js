const fs = require("node:fs");
const path = require("node:path");

const { normalizeStartupProfile } = require("./startup-profile");
const {
  normalizeContrastMode,
  normalizeDensityMode,
  normalizeMotionMode,
} = require("./accessibility");

const PORTABILITY_STATE_FILE = "overlay-portability.json";
const PORTABILITY_STATE_VERSION = 1;
const PORTABILITY_EXPORT_VERSION = 1;

function extractVersionCore(version) {
  return String(version || "").trim().split("+")[0] || "unknown";
}

function buildCompatibilityChannel(version) {
  const core = extractVersionCore(version);
  const match = core.match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!match) {
    return "unknown";
  }
  const major = Number(match[1]);
  const minor = Number(match[2]);
  return major === 0 ? `0.${minor}` : String(major);
}

function buildPortabilityCompatibility({
  buildIdentity = "unknown",
  version = null,
} = {}) {
  const safeVersion = extractVersionCore(version || buildIdentity);
  return {
    exportVersion: PORTABILITY_EXPORT_VERSION,
    buildIdentity: String(buildIdentity || "unknown"),
    version: safeVersion,
    channel: buildCompatibilityChannel(safeVersion),
    portabilityStateVersion: PORTABILITY_STATE_VERSION,
  };
}

function assessPortablePayloadCompatibility(raw, { currentBuildIdentity = "unknown", currentVersion = "unknown" } = {}) {
  if (!raw || typeof raw !== "object") {
    return {
      compatible: false,
      status: "blocked",
      summary: "Portable shell payload is unreadable.",
    };
  }

  const compatibility = raw.compatibility && typeof raw.compatibility === "object"
    ? raw.compatibility
    : buildPortabilityCompatibility({
        buildIdentity: typeof raw.buildIdentity === "string" ? raw.buildIdentity : "unknown",
        version: typeof raw.version === "string" ? raw.version : currentVersion,
      });

  const current = buildPortabilityCompatibility({
    buildIdentity: currentBuildIdentity,
    version: currentVersion,
  });

  if (Number(compatibility.exportVersion || 0) !== PORTABILITY_EXPORT_VERSION) {
    return {
      compatible: false,
      status: "blocked",
      summary: `Portable shell payload export version ${String(compatibility.exportVersion || "unknown")} is not supported by this shell.`,
      exportedBuildIdentity: compatibility.buildIdentity || "unknown",
      exportedChannel: compatibility.channel || "unknown",
    };
  }

  if (String(compatibility.channel || "unknown") !== String(current.channel || "unknown")) {
    return {
      compatible: false,
      status: "blocked",
      summary: `Portable shell payload channel ${String(compatibility.channel || "unknown")} does not match current channel ${String(current.channel || "unknown")}.`,
      exportedBuildIdentity: compatibility.buildIdentity || "unknown",
      exportedChannel: compatibility.channel || "unknown",
    };
  }

  return {
    compatible: true,
    status: compatibility.buildIdentity === current.buildIdentity ? "current" : "compatible",
    summary:
      compatibility.buildIdentity === current.buildIdentity
        ? `Portable shell payload matches current build ${current.buildIdentity}.`
        : `Portable shell payload from ${String(compatibility.buildIdentity || "unknown")} is compatible with current channel ${current.channel}.`,
    exportedBuildIdentity: compatibility.buildIdentity || "unknown",
    exportedChannel: compatibility.channel || "unknown",
  };
}

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
  version = null,
  exportedAt = new Date().toISOString(),
  preferences = {},
} = {}) {
  return {
    version: PORTABILITY_EXPORT_VERSION,
    exportedAt,
    buildIdentity,
    compatibility: buildPortabilityCompatibility({
      buildIdentity,
      version,
    }),
    shell: {
      startupProfile: normalizeStartupProfile(preferences.startupProfile),
      motionMode: normalizeMotionMode(preferences.motionMode),
      contrastMode: normalizeContrastMode(preferences.contrastMode),
      densityMode: normalizeDensityMode(preferences.densityMode),
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

function extractPortablePreferences(raw, options = {}) {
  if (!raw || typeof raw !== "object" || !raw.shell || typeof raw.shell !== "object") {
    throw new Error("Portable shell payload is missing the shell block");
  }

  const compatibility = assessPortablePayloadCompatibility(raw, options);
  if (!compatibility.compatible) {
    throw new Error(compatibility.summary);
  }

  return {
    startupProfile: normalizeStartupProfile(raw.shell.startupProfile),
    motionMode: normalizeMotionMode(raw.shell.motionMode),
    contrastMode: normalizeContrastMode(raw.shell.contrastMode),
    densityMode: normalizeDensityMode(raw.shell.densityMode),
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
  PORTABILITY_EXPORT_VERSION,
  PORTABILITY_STATE_FILE,
  PORTABILITY_STATE_VERSION,
  assessPortablePayloadCompatibility,
  buildCompatibilityChannel,
  buildDefaultPortabilityState,
  buildPortabilityCompatibility,
  buildOverlayExportPayload,
  extractPortablePreferences,
  getPortabilityStatePath,
  loadPortabilityState,
  normalizePortabilityState,
  savePortabilityState,
};
