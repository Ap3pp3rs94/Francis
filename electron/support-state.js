const fs = require("node:fs");
const path = require("node:path");

const SUPPORT_STATE_FILE = "overlay-support.json";
const SUPPORT_STATE_VERSION = 1;

function getSupportStatePath(userDataPath) {
  return path.join(userDataPath, SUPPORT_STATE_FILE);
}

function buildDefaultSupportState() {
  return {
    version: SUPPORT_STATE_VERSION,
    lastBundleAt: null,
    lastBundlePath: null,
  };
}

function normalizeSupportState(raw) {
  const defaults = buildDefaultSupportState();
  if (!raw || typeof raw !== "object") {
    return defaults;
  }
  return {
    version: SUPPORT_STATE_VERSION,
    lastBundleAt: typeof raw.lastBundleAt === "string" ? raw.lastBundleAt : null,
    lastBundlePath: typeof raw.lastBundlePath === "string" ? raw.lastBundlePath : null,
  };
}

function loadSupportState(userDataPath) {
  const filePath = getSupportStatePath(userDataPath);
  try {
    return normalizeSupportState(JSON.parse(fs.readFileSync(filePath, "utf8")));
  } catch {
    return buildDefaultSupportState();
  }
}

function saveSupportState(userDataPath, state) {
  const filePath = getSupportStatePath(userDataPath);
  const normalized = normalizeSupportState(state);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(normalized, null, 2), "utf8");
  return normalized;
}

module.exports = {
  SUPPORT_STATE_FILE,
  SUPPORT_STATE_VERSION,
  buildDefaultSupportState,
  getSupportStatePath,
  loadSupportState,
  normalizeSupportState,
  saveSupportState,
};
