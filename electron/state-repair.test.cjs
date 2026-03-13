const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { PREFERENCES_FILE, PREFERENCES_VERSION } = require("./preferences");
const { SESSION_STATE_FILE, SESSION_STATE_VERSION } = require("./session-state");
const { SUPPORT_STATE_FILE, buildDefaultSupportState } = require("./support-state");
const { repairShellState } = require("./state-repair");

function makeTempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-repair-"));
}

function makeDisplays() {
  return [
    {
      id: 1,
      primary: true,
      workArea: { x: 0, y: 0, width: 1920, height: 1080 },
    },
  ];
}

test("repair shell state normalizes legacy files in place", () => {
  const root = makeTempRoot();
  fs.writeFileSync(
    path.join(root, SESSION_STATE_FILE),
    JSON.stringify({ version: 0, lastLaunchAt: "2026-03-13T10:00:00Z" }, null, 2),
    "utf8",
  );

  const result = repairShellState(root, {
    displays: makeDisplays(),
    primaryDisplayId: 1,
    buildIdentity: "0.1.0+abc1234",
  });

  const repaired = JSON.parse(fs.readFileSync(path.join(root, SESSION_STATE_FILE), "utf8"));
  assert.equal(result.normalizedCount, 1);
  assert.equal(repaired.version, SESSION_STATE_VERSION);
  assert.equal(repaired.lastLaunchAt, "2026-03-13T10:00:00Z");
});

test("repair shell state quarantines unreadable files and resets only the affected ledger", () => {
  const root = makeTempRoot();
  fs.writeFileSync(path.join(root, SUPPORT_STATE_FILE), "{not-json", "utf8");
  fs.writeFileSync(
    path.join(root, PREFERENCES_FILE),
    JSON.stringify(
      {
        version: PREFERENCES_VERSION,
        targetDisplayId: 1,
        alwaysOnTop: false,
        ignoreMouseEvents: true,
        startupProfile: "quiet",
        motionMode: "reduce",
        windowBounds: { x: 10, y: 10, width: 1280, height: 720 },
      },
      null,
      2,
    ),
    "utf8",
  );

  const result = repairShellState(root, {
    displays: makeDisplays(),
    primaryDisplayId: 1,
    buildIdentity: "0.1.0+abc1234",
  });

  const support = JSON.parse(fs.readFileSync(path.join(root, SUPPORT_STATE_FILE), "utf8"));
  const preferences = JSON.parse(fs.readFileSync(path.join(root, PREFERENCES_FILE), "utf8"));

  assert.equal(result.quarantinedCount, 1);
  assert.equal(support.version, buildDefaultSupportState().version);
  assert.equal(preferences.ignoreMouseEvents, true);
  assert.ok(result.actions.some((entry) => entry.targetId === "support" && entry.archivePath));
});
