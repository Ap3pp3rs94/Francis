const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  UPDATE_STATE_FILE,
  acknowledgeUpdateNotice,
  buildUpdatePosture,
  getUpdateStatePath,
  reconcileUpdateState,
} = require("./update-state");

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-update-"));
}

test("update state creates a first-run record without a pending notice", () => {
  const userDataPath = makeTempUserData();
  const state = reconcileUpdateState(userDataPath, {
    buildIdentity: "0.1.0+abc1234",
    now: "2026-03-12T08:00:00Z",
    preferencesSchemaVersion: 3,
    sessionSchemaVersion: 1,
    portabilitySchemaVersion: 1,
    supportSchemaVersion: 1,
  });

  assert.equal(path.basename(getUpdateStatePath(userDataPath)), UPDATE_STATE_FILE);
  assert.equal(state.notice, "fresh_install");
  assert.equal(state.pendingNotice, false);
});

test("update state raises a pending notice when the build identity changes", () => {
  const userDataPath = makeTempUserData();
  reconcileUpdateState(userDataPath, {
    buildIdentity: "0.1.0+abc1234",
    now: "2026-03-12T08:00:00Z",
    preferencesSchemaVersion: 3,
    sessionSchemaVersion: 1,
    portabilitySchemaVersion: 1,
    supportSchemaVersion: 1,
  });

  const updated = reconcileUpdateState(userDataPath, {
    buildIdentity: "0.1.0+def5678",
    now: "2026-03-12T09:00:00Z",
    preferencesSchemaVersion: 3,
    sessionSchemaVersion: 1,
    portabilitySchemaVersion: 1,
    supportSchemaVersion: 1,
  });

  assert.equal(updated.notice, "updated");
  assert.equal(updated.pendingNotice, true);
  assert.equal(updated.previousBuild, "0.1.0+abc1234");
  assert.equal(updated.lastUpdatedAt, "2026-03-12T09:00:00Z");
});

test("acknowledging an update notice clears the pending state", () => {
  const userDataPath = makeTempUserData();
  reconcileUpdateState(userDataPath, {
    buildIdentity: "0.1.0+abc1234",
    now: "2026-03-12T08:00:00Z",
    preferencesSchemaVersion: 3,
    sessionSchemaVersion: 1,
    portabilitySchemaVersion: 1,
    supportSchemaVersion: 1,
  });

  const updated = reconcileUpdateState(userDataPath, {
    buildIdentity: "0.1.0+def5678",
    now: "2026-03-12T09:00:00Z",
    preferencesSchemaVersion: 3,
    sessionSchemaVersion: 1,
    portabilitySchemaVersion: 1,
    supportSchemaVersion: 1,
  });

  const acknowledged = acknowledgeUpdateNotice(userDataPath, updated, "2026-03-12T09:10:00Z");
  const posture = buildUpdatePosture(acknowledged);

  assert.equal(acknowledged.pendingNotice, false);
  assert.equal(acknowledged.notice, "acknowledged");
  assert.equal(posture.compatibility, "current");
  assert.match(posture.summary, /Running build/);
  assert.match(posture.schemaSummary, /portability v1/);
});
