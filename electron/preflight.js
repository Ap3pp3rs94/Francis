const fs = require("node:fs");
const path = require("node:path");

function pathWritable(targetPath) {
  try {
    fs.mkdirSync(targetPath, { recursive: true });
    fs.accessSync(targetPath, fs.constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

function fileParentWritable(targetPath) {
  try {
    const parent = path.dirname(targetPath);
    fs.mkdirSync(parent, { recursive: true });
    fs.accessSync(parent, fs.constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

function buildPreflightState({
  userDataPath = null,
  workspaceRoot = null,
  preferencesPath = null,
  sessionStatePath = null,
  updateStatePath = null,
  hudState = null,
  provider = null,
  authority = null,
  signing = null,
  launchAtLogin = null,
  buildIdentity = "unknown",
  distribution = "source",
} = {}) {
  const userDataWritable = userDataPath ? pathWritable(userDataPath) : false;
  const workspaceWritable = workspaceRoot ? pathWritable(workspaceRoot) : false;
  const preferencesWritable = preferencesPath ? fileParentWritable(preferencesPath) : false;
  const sessionWritable = sessionStatePath ? fileParentWritable(sessionStatePath) : false;
  const updateWritable = updateStatePath ? fileParentWritable(updateStatePath) : false;
  const runtimeReady = Boolean(hudState?.ready);
  const runtimeMode = String(hudState?.mode || "unavailable");
  const runtimeKind = String(hudState?.runtimeKind || "unknown");
  const startupSupport = Boolean(launchAtLogin?.available);

  const checks = [
    {
      id: "user_data",
      label: "User Data",
      status: userDataWritable ? "ok" : "blocked",
      detail: userDataPath || "unavailable",
    },
    {
      id: "workspace",
      label: "Workspace Root",
      status: workspaceWritable ? "ok" : "blocked",
      detail: workspaceRoot || "unavailable",
    },
    {
      id: "preferences",
      label: "Shell Preferences",
      status: preferencesWritable ? "ok" : "blocked",
      detail: preferencesPath || "unavailable",
    },
    {
      id: "continuity",
      label: "Continuity Ledgers",
      status: sessionWritable && updateWritable ? "ok" : "blocked",
      detail: sessionStatePath && updateStatePath
        ? `${sessionStatePath} | ${updateStatePath}`
        : "unavailable",
    },
    {
      id: "hud_runtime",
      label: "HUD Runtime",
      status: runtimeReady ? "ok" : runtimeMode === "crashed" ? "attention" : "blocked",
      detail: `${runtimeMode} | ${runtimeKind}`,
    },
    {
      id: "startup_support",
      label: "Startup Support",
      status: startupSupport ? "ok" : "attention",
      detail: startupSupport ? "launch-at-login available" : "launch-at-login unavailable",
    },
    {
      id: "build",
      label: "Build Identity",
      status: "ok",
      detail: `${distribution} | ${buildIdentity}`,
    },
  ];

  if (provider && typeof provider === "object") {
    checks.push({
      id: "provider",
      label: "Provider Posture",
      status:
        provider.severity === "high"
          ? "blocked"
          : provider.severity === "medium"
            ? "attention"
            : "ok",
      detail: String(provider.summary || "Provider posture unavailable"),
    });
  }

  if (authority && typeof authority === "object") {
    checks.push({
      id: "authority",
      label: "Authority Posture",
      status:
        authority.severity === "high"
          ? "blocked"
          : authority.severity === "medium"
            ? "attention"
            : "ok",
      detail: String(authority.summary || "Authority posture unavailable"),
    });
  }

  if (signing && typeof signing === "object") {
    checks.push({
      id: "signing",
      label: "Signing Posture",
      status:
        signing.severity === "high"
          ? "blocked"
          : signing.severity === "medium"
            ? "attention"
            : "ok",
      detail: String(signing.summary || "Signing posture unavailable"),
    });
  }

  const blocked = checks.filter((entry) => entry.status === "blocked").length;
  const attention = checks.filter((entry) => entry.status === "attention").length;
  const summary =
    blocked > 0
      ? `${blocked} preflight checks blocked. Inspect runtime and writable roots before trusting startup.`
      : attention > 0
        ? `${attention} preflight checks need attention. Startup is usable but not fully ideal.`
        : "Preflight checks are nominal.";

  return {
    summary,
    blocked,
    attention,
    checks,
  };
}

module.exports = {
  buildPreflightState,
};
