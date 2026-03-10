const fs = require("node:fs");
const path = require("node:path");

const PREFERENCES_FILE = "overlay-preferences.json";
const MIN_WIDTH = 640;
const MIN_HEIGHT = 360;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function getPreferencesPath(userDataPath) {
  return path.join(userDataPath, PREFERENCES_FILE);
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

function buildDefaultPreferences(workArea) {
  return {
    version: 1,
    alwaysOnTop: true,
    ignoreMouseEvents: false,
    windowBounds: normalizeBounds(null, workArea),
  };
}

function normalizePreferences(raw, workArea) {
  const defaults = buildDefaultPreferences(workArea);
  if (!raw || typeof raw !== "object") {
    return defaults;
  }

  return {
    version: 1,
    alwaysOnTop: raw.alwaysOnTop !== false,
    ignoreMouseEvents: Boolean(raw.ignoreMouseEvents),
    windowBounds: normalizeBounds(raw.windowBounds, workArea),
  };
}

function loadPreferences(userDataPath, workArea) {
  const filePath = getPreferencesPath(userDataPath);
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    return normalizePreferences(JSON.parse(raw), workArea);
  } catch {
    return buildDefaultPreferences(workArea);
  }
}

function savePreferences(userDataPath, preferences, workArea) {
  const filePath = getPreferencesPath(userDataPath);
  const normalized = normalizePreferences(preferences, workArea);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(normalized, null, 2), "utf8");
  return normalized;
}

module.exports = {
  PREFERENCES_FILE,
  buildDefaultPreferences,
  getPreferencesPath,
  loadPreferences,
  normalizeBounds,
  normalizePreferences,
  savePreferences,
};
