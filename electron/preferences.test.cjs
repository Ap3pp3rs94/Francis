const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  buildDefaultPreferences,
  getPreferencesPath,
  loadPreferences,
  normalizeBounds,
  savePreferences,
} = require("./preferences");

const DISPLAYS = [
  {
    id: 101,
    primary: true,
    workArea: { x: 0, y: 0, width: 1536, height: 912 },
  },
  {
    id: 202,
    primary: false,
    workArea: { x: 1536, y: 0, width: 1280, height: 1024 },
  },
];

function tempUserDataPath() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-"));
}

test("normalizeBounds clamps invalid geometry into the work area", () => {
  const bounds = normalizeBounds({ x: -400, y: -200, width: 4000, height: 120 }, DISPLAYS[0].workArea);

  assert.equal(bounds.x, 0);
  assert.equal(bounds.y, 0);
  assert.equal(bounds.width, 1536);
  assert.equal(bounds.height, 360);
});

test("loadPreferences falls back cleanly when no file exists", () => {
  const userDataPath = tempUserDataPath();
  const prefs = loadPreferences(userDataPath, DISPLAYS, 101);

  assert.deepEqual(prefs, buildDefaultPreferences(DISPLAYS[0]));
});

test("savePreferences persists normalized bounds and booleans on the target display", () => {
  const userDataPath = tempUserDataPath();
  const saved = savePreferences(
    userDataPath,
    {
      targetDisplayId: 202,
      alwaysOnTop: false,
      ignoreMouseEvents: true,
      startupProfile: "quiet",
      windowBounds: { x: 1900, y: 800, width: 1400, height: 1100 },
    },
    DISPLAYS,
    101,
  );

  const loaded = loadPreferences(userDataPath, DISPLAYS, 101);

  assert.equal(saved.targetDisplayId, 202);
  assert.equal(saved.alwaysOnTop, false);
  assert.equal(saved.ignoreMouseEvents, true);
  assert.equal(saved.startupProfile, "quiet");
  assert.deepEqual(saved, loaded);
  assert.equal(saved.windowBounds.x, 1536);
  assert.equal(saved.windowBounds.y, 0);
  assert.equal(saved.windowBounds.width, 1280);
  assert.equal(saved.windowBounds.height, 1024);
});

test("invalid target display falls back to the primary display", () => {
  const userDataPath = tempUserDataPath();
  const saved = savePreferences(
    userDataPath,
    {
      targetDisplayId: 999,
      alwaysOnTop: true,
      ignoreMouseEvents: false,
      windowBounds: { x: 1900, y: 100, width: 900, height: 800 },
    },
    DISPLAYS,
    101,
  );

  assert.equal(saved.targetDisplayId, 101);
  assert.deepEqual(saved.windowBounds, {
    x: 636,
    y: 100,
    width: 900,
    height: 800,
  });
});

test("preferences normalize unknown startup profiles back to operator", () => {
  const userDataPath = tempUserDataPath();
  const saved = savePreferences(
    userDataPath,
    {
      targetDisplayId: 101,
      startupProfile: "bad-profile",
      windowBounds: { x: 32, y: 48, width: 900, height: 720 },
    },
    DISPLAYS,
    101,
  );

  assert.equal(saved.startupProfile, "operator");
});

test("loadPreferences ignores malformed json and returns defaults", () => {
  const userDataPath = tempUserDataPath();
  fs.writeFileSync(getPreferencesPath(userDataPath), "{broken", "utf8");

  const prefs = loadPreferences(userDataPath, DISPLAYS, 101);

  assert.deepEqual(prefs, buildDefaultPreferences(DISPLAYS[0]));
});
