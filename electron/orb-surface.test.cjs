const test = require("node:test");
const assert = require("node:assert/strict");

const {
  ORB_WINDOW_TOPMOST_LEVEL,
  buildOrbWindowBounds,
} = require("./orb-surface");

test("buildOrbWindowBounds spans the full target bounds for free orb motion", () => {
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

test("buildOrbWindowBounds spans the full virtual desktop across displays", () => {
  const bounds = buildOrbWindowBounds([
    {
      bounds: {
        x: -1920,
        y: 0,
        width: 1920,
        height: 1080,
      },
    },
    {
      bounds: {
        x: 0,
        y: 0,
        width: 1600,
        height: 900,
      },
    },
  ]);

  assert.deepEqual(bounds, {
    x: -1920,
    y: 0,
    width: 3520,
    height: 1080,
  });
});

test("buildOrbWindowBounds prefers display bounds when work areas exclude the taskbar", () => {
  const bounds = buildOrbWindowBounds([
    {
      bounds: {
        x: 0,
        y: 0,
        width: 1920,
        height: 1080,
      },
      workArea: {
        x: 0,
        y: 0,
        width: 1920,
        height: 1032,
      },
    },
  ]);

  assert.deepEqual(bounds, {
    x: 0,
    y: 0,
    width: 1920,
    height: 1080,
  });
});

test("buildOrbWindowBounds clamps invalid bounds to safe fullscreen minimums", () => {
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
