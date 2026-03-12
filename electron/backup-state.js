const fs = require("node:fs");
const path = require("node:path");

const { PREFERENCES_FILE } = require("./preferences");
const { SESSION_STATE_FILE } = require("./session-state");
const { UPDATE_STATE_FILE } = require("./update-state");
const { PORTABILITY_STATE_FILE } = require("./overlay-portability");
const { SUPPORT_STATE_FILE } = require("./support-state");

const BACKUP_ROOT_DIR = "overlay-backups";
const MANIFEST_FILE = "manifest.json";
const TRACKED_FILES = [PREFERENCES_FILE, SESSION_STATE_FILE, UPDATE_STATE_FILE, PORTABILITY_STATE_FILE, SUPPORT_STATE_FILE];

function getBackupRoot(userDataPath) {
  return path.join(userDataPath, BACKUP_ROOT_DIR);
}

function buildBackupId(now = new Date()) {
  return String(now.toISOString()).replaceAll(":", "-").replaceAll(".", "-");
}

function getBackupManifestPath(userDataPath, backupId) {
  return path.join(getBackupRoot(userDataPath), backupId, MANIFEST_FILE);
}

function listShellBackups(userDataPath) {
  const root = getBackupRoot(userDataPath);
  try {
    return fs.readdirSync(root, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => {
        const manifestPath = path.join(root, entry.name, MANIFEST_FILE);
        try {
          return JSON.parse(fs.readFileSync(manifestPath, "utf8"));
        } catch {
          return null;
        }
      })
      .filter(Boolean)
      .sort((left, right) => String(right.createdAt || "").localeCompare(String(left.createdAt || "")));
  } catch {
    return [];
  }
}

function summarizeBackups(userDataPath) {
  const items = listShellBackups(userDataPath);
  const latest = items[0] || null;
  return {
    count: items.length,
    latest,
    summary: latest
      ? `${items.length} rollback snapshot${items.length === 1 ? "" : "s"} | latest ${latest.reason} at ${latest.createdAt}`
      : "No rollback snapshots captured yet.",
    items,
  };
}

function createShellBackup(userDataPath, { reason = "manual", buildIdentity = "unknown", note = "" } = {}) {
  const now = new Date();
  const createdAt = now.toISOString();
  const backupId = buildBackupId(now);
  const root = getBackupRoot(userDataPath);
  const targetDir = path.join(root, backupId);
  fs.mkdirSync(targetDir, { recursive: true });

  const files = TRACKED_FILES.map((fileName) => {
    const sourcePath = path.join(userDataPath, fileName);
    const targetPath = path.join(targetDir, fileName);
    const exists = fs.existsSync(sourcePath);
    if (exists) {
      fs.copyFileSync(sourcePath, targetPath);
    }
    return {
      fileName,
      exists,
      sourcePath,
      backupPath: exists ? targetPath : null,
    };
  });

  const manifest = {
    version: 1,
    backupId,
    createdAt,
    reason: String(reason || "manual"),
    buildIdentity: String(buildIdentity || "unknown"),
    note: String(note || ""),
    files,
  };
  fs.writeFileSync(path.join(targetDir, MANIFEST_FILE), JSON.stringify(manifest, null, 2), "utf8");
  return manifest;
}

function restoreShellBackup(userDataPath, backupId) {
  const manifestPath = getBackupManifestPath(userDataPath, backupId);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

  for (const entry of Array.isArray(manifest.files) ? manifest.files : []) {
    const sourcePath = entry.backupPath;
    const targetPath = path.join(userDataPath, entry.fileName);
    if (entry.exists && sourcePath && fs.existsSync(sourcePath)) {
      fs.mkdirSync(path.dirname(targetPath), { recursive: true });
      fs.copyFileSync(sourcePath, targetPath);
    }
  }

  return manifest;
}

module.exports = {
  BACKUP_ROOT_DIR,
  MANIFEST_FILE,
  TRACKED_FILES,
  createShellBackup,
  getBackupManifestPath,
  getBackupRoot,
  listShellBackups,
  restoreShellBackup,
  summarizeBackups,
};
