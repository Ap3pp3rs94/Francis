const fs = require("node:fs");
const path = require("node:path");

const { PREFERENCES_FILE, PREFERENCES_VERSION } = require("./preferences");
const { SESSION_STATE_FILE, SESSION_STATE_VERSION } = require("./session-state");
const { UPDATE_STATE_FILE, UPDATE_STATE_VERSION } = require("./update-state");
const { PORTABILITY_STATE_FILE, PORTABILITY_STATE_VERSION } = require("./overlay-portability");
const { SUPPORT_STATE_FILE, SUPPORT_STATE_VERSION } = require("./support-state");

const SHELL_MIGRATION_SPECS = [
  {
    id: "preferences",
    label: "Overlay Preferences",
    fileName: PREFERENCES_FILE,
    currentVersion: PREFERENCES_VERSION,
  },
  {
    id: "session",
    label: "Session Continuity",
    fileName: SESSION_STATE_FILE,
    currentVersion: SESSION_STATE_VERSION,
  },
  {
    id: "update",
    label: "Update Posture",
    fileName: UPDATE_STATE_FILE,
    currentVersion: UPDATE_STATE_VERSION,
  },
  {
    id: "portability",
    label: "Shell Portability",
    fileName: PORTABILITY_STATE_FILE,
    currentVersion: PORTABILITY_STATE_VERSION,
  },
  {
    id: "support",
    label: "Support Bundle Ledger",
    fileName: SUPPORT_STATE_FILE,
    currentVersion: SUPPORT_STATE_VERSION,
  },
];

function readRawState(filePath) {
  try {
    return {
      exists: true,
      raw: JSON.parse(fs.readFileSync(filePath, "utf8")),
      error: null,
    };
  } catch (error) {
    if (error && error.code === "ENOENT") {
      return {
        exists: false,
        raw: null,
        error: null,
      };
    }
    return {
      exists: true,
      raw: null,
      error,
    };
  }
}

function getRecordedVersion(raw) {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const numericVersion = Number(raw.version);
  return Number.isFinite(numericVersion) ? numericVersion : null;
}

function assessMigrationItem(spec, userDataPath) {
  const filePath = path.join(userDataPath, spec.fileName);
  const record = readRawState(filePath);

  if (!record.exists) {
    return {
      id: spec.id,
      label: spec.label,
      path: filePath,
      expectedVersion: spec.currentVersion,
      recordedVersion: null,
      status: "missing",
      tone: "low",
      summary: "No persisted state file yet.",
    };
  }

  if (record.error) {
    return {
      id: spec.id,
      label: spec.label,
      path: filePath,
      expectedVersion: spec.currentVersion,
      recordedVersion: null,
      status: "invalid",
      tone: "high",
      summary: "Stored state is unreadable and needs repair.",
      error: record.error instanceof Error ? record.error.message : String(record.error),
    };
  }

  const recordedVersion = getRecordedVersion(record.raw);
  if (recordedVersion === null) {
    return {
      id: spec.id,
      label: spec.label,
      path: filePath,
      expectedVersion: spec.currentVersion,
      recordedVersion: null,
      status: "legacy",
      tone: "medium",
      summary: `Stored without a schema version; current shell expects v${spec.currentVersion}.`,
    };
  }

  if (recordedVersion > spec.currentVersion) {
    return {
      id: spec.id,
      label: spec.label,
      path: filePath,
      expectedVersion: spec.currentVersion,
      recordedVersion,
      status: "future",
      tone: "high",
      summary: `Stored as v${recordedVersion}; current shell only understands v${spec.currentVersion}.`,
    };
  }

  if (recordedVersion < spec.currentVersion) {
    return {
      id: spec.id,
      label: spec.label,
      path: filePath,
      expectedVersion: spec.currentVersion,
      recordedVersion,
      status: "legacy",
      tone: "medium",
      summary: `Stored as v${recordedVersion}; loader will normalize it toward v${spec.currentVersion} on the next write.`,
    };
  }

  return {
    id: spec.id,
    label: spec.label,
    path: filePath,
    expectedVersion: spec.currentVersion,
    recordedVersion,
    status: "current",
    tone: "low",
    summary: `Stored schema matches v${spec.currentVersion}.`,
  };
}

function buildShellMigrationPosture(userDataPath = null) {
  if (!userDataPath) {
    return {
      summary: "Shell migration posture is unavailable until the desktop shell is ready.",
      blocked: 0,
      attention: 0,
      current: 0,
      missing: SHELL_MIGRATION_SPECS.length,
      items: [],
      cards: [
        {
          label: "Migration",
          value: "unavailable",
          tone: "low",
        },
      ],
    };
  }

  const items = SHELL_MIGRATION_SPECS.map((spec) => assessMigrationItem(spec, userDataPath));
  const blocked = items.filter((item) => item.status === "invalid" || item.status === "future").length;
  const attention = items.filter((item) => item.status === "legacy").length;
  const current = items.filter((item) => item.status === "current").length;
  const missing = items.filter((item) => item.status === "missing").length;

  let summary = "Shell state schemas are current.";
  if (blocked > 0) {
    summary = `${blocked} retained shell state file${blocked === 1 ? "" : "s"} need repair before continuity is trusted.`;
  } else if (attention > 0) {
    summary = `${attention} retained shell state file${attention === 1 ? "" : "s"} need migration review before continuity is treated as settled.`;
  } else if (missing > 0 && current === 0) {
    summary = "No retained shell state files exist yet; migration posture is clean.";
  }

  return {
    summary,
    blocked,
    attention,
    current,
    missing,
    items,
    cards: [
      {
        label: "Summary",
        value: summary,
        tone: blocked > 0 ? "high" : attention > 0 ? "medium" : "low",
      },
      {
        label: "Blocked",
        value: String(blocked),
        tone: blocked > 0 ? "high" : "low",
      },
      {
        label: "Attention",
        value: String(attention),
        tone: attention > 0 ? "medium" : "low",
      },
      {
        label: "Current",
        value: String(current),
        tone: current > 0 ? "medium" : "low",
      },
      {
        label: "Missing",
        value: String(missing),
        tone: missing > 0 ? "low" : "medium",
      },
    ],
  };
}

module.exports = {
  SHELL_MIGRATION_SPECS,
  assessMigrationItem,
  buildShellMigrationPosture,
};
