const fs = require("node:fs");
const path = require("node:path");

const UPDATE_STATE_FILE = "overlay-update-state.json";
const UPDATE_STATE_VERSION = 2;

function getUpdateStatePath(userDataPath) {
  return path.join(userDataPath, UPDATE_STATE_FILE);
}

function buildDefaultUpdateState({
  buildIdentity = "unknown",
  now = null,
  preferencesSchemaVersion = null,
  sessionSchemaVersion = null,
  portabilitySchemaVersion = null,
  supportSchemaVersion = null,
} = {}) {
  return {
    version: UPDATE_STATE_VERSION,
    firstSeenAt: now,
    currentBuild: buildIdentity,
    previousBuild: null,
    lastUpdatedAt: null,
    pendingNotice: false,
    notice: "fresh_install",
    acknowledgedAt: null,
    preferencesSchemaVersion,
    sessionSchemaVersion,
    portabilitySchemaVersion,
    supportSchemaVersion,
    lastSchemaSyncAt: now,
  };
}

function normalizeUpdateState(raw, defaults = buildDefaultUpdateState()) {
  if (!raw || typeof raw !== "object") {
    return defaults;
  }

  return {
    version: UPDATE_STATE_VERSION,
    firstSeenAt: typeof raw.firstSeenAt === "string" ? raw.firstSeenAt : defaults.firstSeenAt,
    currentBuild: typeof raw.currentBuild === "string" ? raw.currentBuild : defaults.currentBuild,
    previousBuild: typeof raw.previousBuild === "string" ? raw.previousBuild : null,
    lastUpdatedAt: typeof raw.lastUpdatedAt === "string" ? raw.lastUpdatedAt : null,
    pendingNotice: Boolean(raw.pendingNotice),
    notice: typeof raw.notice === "string" ? raw.notice : defaults.notice,
    acknowledgedAt: typeof raw.acknowledgedAt === "string" ? raw.acknowledgedAt : null,
    preferencesSchemaVersion: Number.isFinite(Number(raw.preferencesSchemaVersion))
      ? Number(raw.preferencesSchemaVersion)
      : defaults.preferencesSchemaVersion,
    sessionSchemaVersion: Number.isFinite(Number(raw.sessionSchemaVersion))
      ? Number(raw.sessionSchemaVersion)
      : defaults.sessionSchemaVersion,
    portabilitySchemaVersion: Number.isFinite(Number(raw.portabilitySchemaVersion))
      ? Number(raw.portabilitySchemaVersion)
      : defaults.portabilitySchemaVersion,
    supportSchemaVersion: Number.isFinite(Number(raw.supportSchemaVersion))
      ? Number(raw.supportSchemaVersion)
      : defaults.supportSchemaVersion,
    lastSchemaSyncAt: typeof raw.lastSchemaSyncAt === "string" ? raw.lastSchemaSyncAt : defaults.lastSchemaSyncAt,
  };
}

function loadUpdateState(userDataPath, options = {}) {
  const filePath = getUpdateStatePath(userDataPath);
  const defaults = buildDefaultUpdateState(options);
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    return normalizeUpdateState(JSON.parse(raw), defaults);
  } catch {
    return defaults;
  }
}

function saveUpdateState(userDataPath, state, options = {}) {
  const filePath = getUpdateStatePath(userDataPath);
  const defaults = buildDefaultUpdateState(options);
  const normalized = normalizeUpdateState(state, defaults);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(normalized, null, 2), "utf8");
  return normalized;
}

function reconcileUpdateState(
  userDataPath,
  {
    buildIdentity = "unknown",
    now = new Date().toISOString(),
    preferencesSchemaVersion = null,
    sessionSchemaVersion = null,
    portabilitySchemaVersion = null,
    supportSchemaVersion = null,
  } = {},
) {
  const filePath = getUpdateStatePath(userDataPath);
  const defaults = buildDefaultUpdateState({
    buildIdentity,
    now,
    preferencesSchemaVersion,
    sessionSchemaVersion,
    portabilitySchemaVersion,
    supportSchemaVersion,
  });

  let prior = null;
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    prior = normalizeUpdateState(JSON.parse(raw), defaults);
  } catch {
    prior = null;
  }

  if (!prior) {
    return saveUpdateState(userDataPath, defaults, defaults);
  }

  const buildChanged = prior.currentBuild !== buildIdentity;
  const schemaChanged =
    prior.preferencesSchemaVersion !== preferencesSchemaVersion ||
    prior.sessionSchemaVersion !== sessionSchemaVersion ||
    prior.portabilitySchemaVersion !== portabilitySchemaVersion ||
    prior.supportSchemaVersion !== supportSchemaVersion;

  const next = {
    ...prior,
    currentBuild: buildIdentity,
    preferencesSchemaVersion,
    sessionSchemaVersion,
    portabilitySchemaVersion,
    supportSchemaVersion,
    lastSchemaSyncAt: now,
  };

  if (buildChanged) {
    next.previousBuild = prior.currentBuild || prior.previousBuild || null;
    next.lastUpdatedAt = now;
    next.pendingNotice = true;
    next.notice = "updated";
    next.acknowledgedAt = null;
  } else if (schemaChanged) {
    next.pendingNotice = true;
    next.notice = "schema_reconciled";
    next.acknowledgedAt = null;
  } else if (!next.pendingNotice) {
    next.notice = "current";
  }

  return saveUpdateState(userDataPath, next, defaults);
}

function acknowledgeUpdateNotice(userDataPath, state, now = new Date().toISOString()) {
  return saveUpdateState(
    userDataPath,
    {
      ...state,
      pendingNotice: false,
      acknowledgedAt: now,
      notice: state?.pendingNotice ? "acknowledged" : state?.notice || "current",
    },
    state,
  );
}

function buildUpdatePosture(state) {
  const compatibility = state.pendingNotice
    ? "attention"
    : state.notice === "current" || state.notice === "acknowledged" || state.notice === "fresh_install"
      ? "current"
      : "review";
  let summary = `Running build ${state.currentBuild}.`;
  if (state.notice === "updated" && state.previousBuild) {
    summary = `Updated from ${state.previousBuild} to ${state.currentBuild}.`;
  } else if (state.notice === "schema_reconciled") {
    summary = `Lifecycle schemas reconciled for build ${state.currentBuild}.`;
  } else if (state.notice === "fresh_install") {
    summary = `Fresh lifecycle state created for build ${state.currentBuild}.`;
  }

  return {
    ...state,
    compatibility,
    summary,
    schemaSummary: [
      `prefs v${String(state.preferencesSchemaVersion ?? "unknown")}`,
      `session v${String(state.sessionSchemaVersion ?? "unknown")}`,
      `portability v${String(state.portabilitySchemaVersion ?? "unknown")}`,
      `support v${String(state.supportSchemaVersion ?? "unknown")}`,
    ].join(" | "),
  };
}

module.exports = {
  UPDATE_STATE_FILE,
  UPDATE_STATE_VERSION,
  acknowledgeUpdateNotice,
  buildDefaultUpdateState,
  buildUpdatePosture,
  getUpdateStatePath,
  loadUpdateState,
  normalizeUpdateState,
  reconcileUpdateState,
  saveUpdateState,
};
