const fs = require("node:fs");
const path = require("node:path");

const PREFERENCES_FILE = "overlay-preferences.json";
const PREFERENCES_VERSION = 3;
const MIN_WIDTH = 640;
const MIN_HEIGHT = 360;
const { DEFAULT_STARTUP_PROFILE, normalizeStartupProfile } = require("./startup-profile");

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function getPreferencesPath(userDataPath) {
  return path.join(userDataPath, PREFERENCES_FILE);
}

function resolvePrimaryDisplay(displays, primaryDisplayId = null) {
  const safeDisplays = Array.isArray(displays) ? displays.filter(Boolean) : [];
  if (!safeDisplays.length) {
    throw new Error("At least one display is required");
  }
  return (
    safeDisplays.find((display) => display.id === primaryDisplayId) ||
    safeDisplays.find((display) => Boolean(display.primary)) ||
    safeDisplays[0]
  );
}

function resolveTargetDisplay(displays, targetDisplayId, primaryDisplayId = null) {
  const primaryDisplay = resolvePrimaryDisplay(displays, primaryDisplayId);
  return safeDisplayMatch(displays, targetDisplayId) || primaryDisplay;
}

function safeDisplayMatch(displays, targetDisplayId) {
  return (Array.isArray(displays) ? displays : []).find(
    (display) => display && display.id === targetDisplayId,
  );
}

function normalizeBounds(rawBounds, workArea) {
  const fallback = {
    x: workArea.x,
    y: workArea.y,
    width: workArea.width,
    height: workArea.height,
  };

  if (!rawBounds || typeof rawBounds !== "object") {
    return fallback;
  }

  const width = clamp(
    Number(rawBounds.width) || fallback.width,
    MIN_WIDTH,
    Math.max(MIN_WIDTH, workArea.width),
  );
  const height = clamp(
    Number(rawBounds.height) || fallback.height,
    MIN_HEIGHT,
    Math.max(MIN_HEIGHT, workArea.height),
  );
  const maxX = workArea.x + Math.max(0, workArea.width - width);
  const maxY = workArea.y + Math.max(0, workArea.height - height);

  return {
    x: clamp(Number(rawBounds.x) || fallback.x, workArea.x, maxX),
    y: clamp(Number(rawBounds.y) || fallback.y, workArea.y, maxY),
    width,
    height,
  };
}

function buildDefaultPreferences(display) {
  return {
    version: PREFERENCES_VERSION,
    targetDisplayId: display.id,
    alwaysOnTop: true,
    ignoreMouseEvents: false,
    startupProfile: DEFAULT_STARTUP_PROFILE,
    windowBounds: normalizeBounds(null, display.workArea),
  };
}

function normalizePreferences(raw, displays, primaryDisplayId = null) {
  const targetDisplay = resolveTargetDisplay(displays, raw?.targetDisplayId, primaryDisplayId);
  const defaults = buildDefaultPreferences(targetDisplay);
  if (!raw || typeof raw !== "object") {
    return defaults;
  }

  return {
    version: PREFERENCES_VERSION,
    targetDisplayId: targetDisplay.id,
    alwaysOnTop: raw.alwaysOnTop !== false,
    ignoreMouseEvents: Boolean(raw.ignoreMouseEvents),
    startupProfile: normalizeStartupProfile(raw.startupProfile),
    windowBounds: normalizeBounds(raw.windowBounds, targetDisplay.workArea),
  };
}

function loadPreferences(userDataPath, displays, primaryDisplayId = null) {
  const filePath = getPreferencesPath(userDataPath);
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    return normalizePreferences(JSON.parse(raw), displays, primaryDisplayId);
  } catch {
    return buildDefaultPreferences(resolvePrimaryDisplay(displays, primaryDisplayId));
  }
}

function savePreferences(userDataPath, preferences, displays, primaryDisplayId = null) {
  const filePath = getPreferencesPath(userDataPath);
  const normalized = normalizePreferences(preferences, displays, primaryDisplayId);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(normalized, null, 2), "utf8");
  return normalized;
}

module.exports = {
  PREFERENCES_FILE,
  PREFERENCES_VERSION,
  buildDefaultPreferences,
  getPreferencesPath,
  loadPreferences,
  normalizeBounds,
  normalizePreferences,
  resolvePrimaryDisplay,
  resolveTargetDisplay,
  savePreferences,
};
