const test = require("node:test");
const assert = require("node:assert/strict");

const {
  ORB_WINDOW_MARGIN,
  ORB_WINDOW_SIZE,
  ORB_WINDOW_TOPMOST_LEVEL,
  buildOrbWindowBounds,
} = require("./orb-surface");

test("buildOrbWindowBounds anchors the orb window to the top-right work area", () => {
  const bounds = buildOrbWindowBounds({
    x: 100,
    y: 40,
    width: 1600,
    height: 900,
  });

  assert.equal(bounds.width, ORB_WINDOW_SIZE);
  assert.equal(bounds.height, ORB_WINDOW_SIZE);
  assert.equal(bounds.x, 100 + 1600 - ORB_WINDOW_SIZE - ORB_WINDOW_MARGIN);
  assert.equal(bounds.y, 40 + ORB_WINDOW_MARGIN);
});

test("buildOrbWindowBounds clamps undersized inputs to safe minimums", () => {
  const bounds = buildOrbWindowBounds(
    {
      x: 0,
      y: 0,
      width: 300,
      height: 200,
    },
    { size: 80, margin: 2 },
  );

  assert.equal(bounds.width, 160);
  assert.equal(bounds.height, 160);
  assert.equal(bounds.x, 128);
  assert.equal(bounds.y, 12);
});

test("orb window topmost level stays pinned to the desktop-presence layer", () => {
  assert.equal(ORB_WINDOW_TOPMOST_LEVEL, "screen-saver");
});
