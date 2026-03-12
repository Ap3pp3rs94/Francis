const fs = require("node:fs");
const path = require("node:path");

const SESSION_STATE_FILE = "overlay-session.json";

function getSessionStatePath(userDataPath) {
  return path.join(userDataPath, SESSION_STATE_FILE);
}

function buildDefaultSessionState() {
  return {
    version: 1,
    lastLaunchAt: null,
    lastExitAt: null,
    lastExitClean: true,
    lastExitReason: "fresh",
    hudCrashCount: 0,
    hudLastError: null,
  };
}

function normalizeSessionState(raw) {
  const defaults = buildDefaultSessionState();
  if (!raw || typeof raw !== "object") {
    return defaults;
  }
  return {
    version: 1,
    lastLaunchAt: raw.lastLaunchAt || null,
    lastExitAt: raw.lastExitAt || null,
    lastExitClean: raw.lastExitClean !== false,
    lastExitReason: typeof raw.lastExitReason === "string" ? raw.lastExitReason : defaults.lastExitReason,
    hudCrashCount: Number.isFinite(Number(raw.hudCrashCount)) ? Math.max(0, Math.trunc(Number(raw.hudCrashCount))) : 0,
    hudLastError: typeof raw.hudLastError === "string" ? raw.hudLastError : null,
  };
}

function loadSessionState(userDataPath) {
  const filePath = getSessionStatePath(userDataPath);
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    return normalizeSessionState(JSON.parse(raw));
  } catch {
    return buildDefaultSessionState();
  }
}

function saveSessionState(userDataPath, state) {
  const filePath = getSessionStatePath(userDataPath);
  const normalized = normalizeSessionState(state);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(normalized, null, 2), "utf8");
  return normalized;
}

module.exports = {
  SESSION_STATE_FILE,
  buildDefaultSessionState,
  getSessionStatePath,
  loadSessionState,
  normalizeSessionState,
  saveSessionState,
};
