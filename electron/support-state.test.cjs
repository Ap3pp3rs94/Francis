const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  buildDefaultSupportState,
  getSupportStatePath,
  loadSupportState,
  saveSupportState,
} = require("./support-state");

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-support-"));
}

test("support state persists last exported bundle", () => {
  const userDataPath = makeTempUserData();
  const saved = saveSupportState(userDataPath, {
    lastBundleAt: "2026-03-12T12:00:00Z",
    lastBundlePath: "C:\\Temp\\francis-support.json",
  });

  assert.equal(saved.lastBundleAt, "2026-03-12T12:00:00Z");
  assert.equal(saved.lastBundlePath, "C:\\Temp\\francis-support.json");
  assert.equal(loadSupportState(userDataPath).lastBundlePath, "C:\\Temp\\francis-support.json");
  assert.equal(getSupportStatePath(userDataPath).endsWith("overlay-support.json"), true);
});

test("support state falls back cleanly when no file exists", () => {
  const userDataPath = makeTempUserData();
  assert.deepEqual(loadSupportState(userDataPath), buildDefaultSupportState());
});
