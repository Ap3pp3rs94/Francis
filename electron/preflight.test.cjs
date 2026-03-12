const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { buildPreflightState } = require("./preflight");

function makeTempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-preflight-"));
}

test("preflight reports nominal posture when writable roots and HUD runtime are healthy", () => {
  const root = makeTempRoot();
  const userDataPath = path.join(root, "user-data");
  const workspaceRoot = path.join(root, "workspace");
  const preferencesPath = path.join(userDataPath, "overlay-preferences.json");
  const sessionStatePath = path.join(userDataPath, "overlay-session.json");
  const updateStatePath = path.join(userDataPath, "overlay-update-state.json");

  const state = buildPreflightState({
    userDataPath,
    workspaceRoot,
    preferencesPath,
    sessionStatePath,
    updateStatePath,
    hudState: { ready: true, mode: "managed", runtimeKind: "bundled" },
    launchAtLogin: { available: true, enabled: false },
    buildIdentity: "0.1.0+abc1234",
    distribution: "source",
  });

  assert.equal(state.blocked, 0);
  assert.equal(state.attention, 0);
  assert.match(state.summary, /nominal/i);
});

test("preflight reports blocked posture when writable roots or runtime are unavailable", () => {
  const state = buildPreflightState({
    userDataPath: "?:\\bad\\path",
    workspaceRoot: "?:\\bad\\workspace",
    preferencesPath: "?:\\bad\\overlay-preferences.json",
    sessionStatePath: "?:\\bad\\overlay-session.json",
    updateStatePath: "?:\\bad\\overlay-update-state.json",
    hudState: { ready: false, mode: "crashed", runtimeKind: null },
    launchAtLogin: { available: false, enabled: false },
    buildIdentity: "0.1.0",
    distribution: "portable",
  });

  assert.ok(state.blocked >= 1);
  assert.ok(state.attention >= 1);
});
