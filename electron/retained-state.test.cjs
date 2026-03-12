const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { PREFERENCES_FILE } = require("./preferences");
const { describeRetainedState } = require("./retained-state");

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-retained-"));
}

test("retained-state describes shell files, continuity root, and startup entry", () => {
  const userDataPath = makeTempUserData();
  const workspaceRoot = path.join(userDataPath, "workspace");
  fs.mkdirSync(workspaceRoot, { recursive: true });
  fs.writeFileSync(path.join(userDataPath, PREFERENCES_FILE), JSON.stringify({ alwaysOnTop: true }), "utf8");

  const state = describeRetainedState({
    userDataPath,
    workspaceRoot,
    launchAtLogin: {
      available: true,
      enabled: true,
    },
  });

  assert.equal(state.removableCount, 2);
  assert.equal(state.retainedCount, 3);

  const preferences = state.items.find((item) => item.id === "preferences");
  const workspace = state.items.find((item) => item.id === "workspace_root");
  const login = state.items.find((item) => item.id === "launch_at_login");

  assert.equal(preferences.exists, true);
  assert.equal(workspace.exists, true);
  assert.equal(workspace.removable, false);
  assert.equal(login.enabled, true);
});
