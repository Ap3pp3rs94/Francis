const test = require("node:test");
const assert = require("node:assert/strict");

const {
  ORB_WINDOW_TOPMOST_LEVEL,
  buildOrbWindowBounds,
} = require("./orb-surface");

test("buildOrbWindowBounds spans the full target work area for free orb motion", () => {
  const bounds = buildOrbWindowBounds({
    x: 100,
    y: 40,
    width: 1600,
    height: 900,
  });

  assert.deepEqual(bounds, {
    x: 100,
    y: 40,
    width: 1600,
    height: 900,
  });
});

test("buildOrbWindowBounds clamps invalid work areas to safe fullscreen minimums", () => {
  const bounds = buildOrbWindowBounds({
    x: 0,
    y: 0,
    width: 120,
    height: 80,
  });

  assert.deepEqual(bounds, {
    x: 0,
    y: 0,
    width: 320,
    height: 240,
  });
});

test("orb window topmost level stays pinned to the desktop-presence layer", () => {
  assert.equal(ORB_WINDOW_TOPMOST_LEVEL, "screen-saver");
});
