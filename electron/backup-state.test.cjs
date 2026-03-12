const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  BACKUP_ROOT_DIR,
  createShellBackup,
  listShellBackups,
  restoreShellBackup,
  summarizeBackups,
} = require("./backup-state");
const { PREFERENCES_FILE } = require("./preferences");

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-backup-"));
}

test("shell backups capture tracked files and summarize latest snapshot", () => {
  const userDataPath = makeTempUserData();
  fs.writeFileSync(path.join(userDataPath, PREFERENCES_FILE), JSON.stringify({ alwaysOnTop: true }), "utf8");

  const manifest = createShellBackup(userDataPath, {
    reason: "manual",
    buildIdentity: "0.1.0+abc1234",
    note: "before risky change",
  });
  const summary = summarizeBackups(userDataPath);

  assert.equal(path.basename(path.dirname(summary.latest.files[0].backupPath)), manifest.backupId);
  assert.equal(path.basename(path.dirname(path.dirname(summary.latest.files[0].backupPath))), BACKUP_ROOT_DIR);
  assert.equal(summary.count, 1);
  assert.equal(summary.latest.reason, "manual");
});

test("restoring a shell backup rewrites tracked files", () => {
  const userDataPath = makeTempUserData();
  const preferencesPath = path.join(userDataPath, PREFERENCES_FILE);
  fs.writeFileSync(preferencesPath, JSON.stringify({ alwaysOnTop: true }), "utf8");

  const manifest = createShellBackup(userDataPath, {
    reason: "pre_import",
    buildIdentity: "0.1.0+abc1234",
  });

  fs.writeFileSync(preferencesPath, JSON.stringify({ alwaysOnTop: false }), "utf8");
  restoreShellBackup(userDataPath, manifest.backupId);

  const restored = JSON.parse(fs.readFileSync(preferencesPath, "utf8"));
  assert.equal(restored.alwaysOnTop, true);
  assert.equal(listShellBackups(userDataPath).length, 1);
});
