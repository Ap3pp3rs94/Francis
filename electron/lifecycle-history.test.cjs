const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  LIFECYCLE_HISTORY_FILE,
  MAX_LIFECYCLE_HISTORY_ITEMS,
  buildLifecycleHistorySurface,
  getLifecycleHistoryPath,
  loadLifecycleHistoryState,
  recordLifecycleEvent,
} = require("./lifecycle-history");

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-history-"));
}

test("lifecycle history records newest events first", () => {
  const userDataPath = makeTempUserData();
  let state = loadLifecycleHistoryState(userDataPath);
  state = recordLifecycleEvent(userDataPath, state, {
    id: "one",
    at: "2026-03-13T01:00:00Z",
    kind: "update.acknowledged",
    summary: "Update notice acknowledged.",
    tone: "medium",
  });
  state = recordLifecycleEvent(userDataPath, state, {
    id: "two",
    at: "2026-03-13T02:00:00Z",
    kind: "rollback.restore",
    summary: "Latest rollback snapshot restored.",
    tone: "high",
  });

  const loaded = loadLifecycleHistoryState(userDataPath);
  const surface = buildLifecycleHistorySurface(loaded);

  assert.equal(path.basename(getLifecycleHistoryPath(userDataPath)), LIFECYCLE_HISTORY_FILE);
  assert.equal(loaded.items[0].kind, "rollback.restore");
  assert.equal(surface.latestKind, "rollback.restore");
  assert.match(surface.summary, /rollback snapshot restored/i);
});

test("lifecycle history trims to the configured maximum", () => {
  const userDataPath = makeTempUserData();
  let state = loadLifecycleHistoryState(userDataPath);

  for (let index = 0; index < MAX_LIFECYCLE_HISTORY_ITEMS + 4; index += 1) {
    state = recordLifecycleEvent(userDataPath, state, {
      id: `item-${index}`,
      at: `2026-03-13T0${index % 10}:00:00Z`,
      kind: "shell.event",
      summary: `Event ${index}`,
      tone: "low",
    });
  }

  const loaded = loadLifecycleHistoryState(userDataPath);
  assert.equal(loaded.items.length, MAX_LIFECYCLE_HISTORY_ITEMS);
  assert.equal(loaded.items[0].summary, `Event ${MAX_LIFECYCLE_HISTORY_ITEMS + 3}`);
});
