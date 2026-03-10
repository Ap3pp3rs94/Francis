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

const WORK_AREA = { x: 0, y: 0, width: 1536, height: 912 };

function tempUserDataPath() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-"));
}

test("normalizeBounds clamps invalid geometry into the work area", () => {
  const bounds = normalizeBounds({ x: -400, y: -200, width: 4000, height: 120 }, WORK_AREA);

  assert.equal(bounds.x, 0);
  assert.equal(bounds.y, 0);
  assert.equal(bounds.width, 1536);
  assert.equal(bounds.height, 360);
});

test("loadPreferences falls back cleanly when no file exists", () => {
  const userDataPath = tempUserDataPath();
  const prefs = loadPreferences(userDataPath, WORK_AREA);

  assert.deepEqual(prefs, buildDefaultPreferences(WORK_AREA));
});

test("savePreferences persists normalized bounds and booleans", () => {
  const userDataPath = tempUserDataPath();
  const saved = savePreferences(
    userDataPath,
    {
      alwaysOnTop: false,
      ignoreMouseEvents: true,
      windowBounds: { x: 1440, y: 800, width: 900, height: 900 },
    },
    WORK_AREA,
  );

  const loaded = loadPreferences(userDataPath, WORK_AREA);

  assert.equal(saved.alwaysOnTop, false);
  assert.equal(saved.ignoreMouseEvents, true);
  assert.deepEqual(saved, loaded);
  assert.equal(saved.windowBounds.x, 636);
  assert.equal(saved.windowBounds.y, 12);
});

test("loadPreferences ignores malformed json and returns defaults", () => {
  const userDataPath = tempUserDataPath();
  fs.writeFileSync(getPreferencesPath(userDataPath), "{broken", "utf8");

  const prefs = loadPreferences(userDataPath, WORK_AREA);

  assert.deepEqual(prefs, buildDefaultPreferences(WORK_AREA));
});
