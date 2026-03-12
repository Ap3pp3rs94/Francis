const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  SESSION_STATE_FILE,
  buildDefaultSessionState,
  getSessionStatePath,
  loadSessionState,
  saveSessionState,
} = require("./session-state");

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-session-"));
}

test("session state defaults to a clean fresh launch record", () => {
  const defaults = buildDefaultSessionState();
  assert.equal(defaults.lastExitClean, true);
  assert.equal(defaults.lastExitReason, "fresh");
  assert.equal(defaults.hudCrashCount, 0);
});

test("session state persists normalized values under the expected file name", () => {
  const userDataPath = makeTempUserData();
  const saved = saveSessionState(userDataPath, {
    lastLaunchAt: "2026-03-12T12:00:00+00:00",
    lastExitAt: "2026-03-12T12:30:00+00:00",
    lastExitClean: false,
    lastExitReason: "renderer-gone",
    hudCrashCount: 3,
    hudLastError: "Managed HUD exited with code 1",
  });

  assert.equal(path.basename(getSessionStatePath(userDataPath)), SESSION_STATE_FILE);
  assert.equal(saved.lastExitClean, false);
  assert.equal(saved.hudCrashCount, 3);

  const loaded = loadSessionState(userDataPath);
  assert.deepEqual(loaded, saved);
});
