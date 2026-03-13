const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { buildShellMigrationPosture } = require("./state-migrations");

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-migrations-"));
}

test("migration posture stays nominal when no retained shell state exists", () => {
  const userDataPath = makeTempUserData();
  const posture = buildShellMigrationPosture(userDataPath);

  assert.equal(posture.blocked, 0);
  assert.equal(posture.attention, 0);
  assert.match(posture.summary, /clean|current/i);
});

test("migration posture flags legacy and unreadable state files", () => {
  const userDataPath = makeTempUserData();

  fs.writeFileSync(
    path.join(userDataPath, "overlay-preferences.json"),
    JSON.stringify({ version: 1, alwaysOnTop: true }, null, 2),
    "utf8",
  );
  fs.writeFileSync(
    path.join(userDataPath, "overlay-portability.json"),
    "{not-json",
    "utf8",
  );

  const posture = buildShellMigrationPosture(userDataPath);
  const preferences = posture.items.find((item) => item.id === "preferences");
  const portability = posture.items.find((item) => item.id === "portability");

  assert.equal(posture.blocked, 1);
  assert.equal(posture.attention, 1);
  assert.equal(preferences?.status, "legacy");
  assert.equal(portability?.status, "invalid");
  assert.match(posture.summary, /need repair/i);
});

test("migration posture blocks future-version state", () => {
  const userDataPath = makeTempUserData();

  fs.writeFileSync(
    path.join(userDataPath, "overlay-update-state.json"),
    JSON.stringify({ version: 99, currentBuild: "future" }, null, 2),
    "utf8",
  );

  const posture = buildShellMigrationPosture(userDataPath);
  const update = posture.items.find((item) => item.id === "update");

  assert.equal(posture.blocked, 1);
  assert.equal(update?.status, "future");
  assert.match(update?.summary || "", /only understands/i);
});
