const test = require("node:test");
const assert = require("node:assert/strict");

const {
  ORB_WINDOW_REINFORCE_INTERVAL_MS,
  ORB_WINDOW_TOPMOST_LEVEL,
  ORB_WINDOW_TOPMOST_PRIORITY,
  buildDesktopAuthoritySnapshot,
  buildOrbDisplayTopology,
  buildOrbWindowBounds,
  resolveTaskbarEdge,
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
  assert.equal(ORB_WINDOW_TOPMOST_PRIORITY, 1);
  assert.equal(ORB_WINDOW_REINFORCE_INTERVAL_MS, 2400);
});

test("resolveTaskbarEdge identifies bottom taskbars from work-area insets", () => {
  const taskbar = resolveTaskbarEdge(
    { x: 0, y: 0, width: 1920, height: 1080 },
    { x: 0, y: 0, width: 1920, height: 1032 },
  );

  assert.equal(taskbar.edge, "bottom");
  assert.equal(taskbar.inset, 48);
});

test("buildOrbDisplayTopology centralizes display and taskbar posture", () => {
  const topology = buildOrbDisplayTopology(
    [
      {
        id: 1,
        primary: true,
        bounds: { x: 0, y: 0, width: 1920, height: 1080 },
        workArea: { x: 0, y: 0, width: 1920, height: 1032 },
      },
      {
        id: 2,
        primary: false,
        bounds: { x: 1920, y: 0, width: 2560, height: 1440 },
        workArea: { x: 1920, y: 40, width: 2560, height: 1400 },
      },
    ],
    {
      targetDisplayId: 2,
      activeDisplayId: 1,
    },
  );

  assert.equal(topology.displayCount, 2);
  assert.equal(topology.targetDisplay.id, 2);
  assert.equal(topology.activeDisplay.id, 1);
  assert.equal(topology.displays[0].taskbarEdge, "bottom");
  assert.equal(topology.displays[1].taskbarEdge, "top");
  assert.deepEqual(topology.virtualBounds, {
    x: 0,
    y: 0,
    width: 4480,
    height: 1440,
  });
});

test("buildDesktopAuthoritySnapshot reports active elevated fullscreen limits honestly", () => {
  const snapshot = buildDesktopAuthoritySnapshot({
    displays: [
      {
        id: 7,
        primary: true,
        bounds: { x: 0, y: 0, width: 1920, height: 1080 },
        workArea: { x: 0, y: 0, width: 1920, height: 1032 },
      },
    ],
    targetDisplayId: 7,
    activeDisplayId: 7,
    foregroundWindow: {
      process: "admin-tool",
      title: "Administrator Terminal",
      pid: 404,
      elevated: true,
      bounds: { x: 0, y: 0, width: 1920, height: 1080 },
    },
    capabilityProfile: {
      matrix: [],
      activeLimitations: [],
    },
    orbVisible: true,
    alwaysOnTop: true,
  });

  assert.equal(snapshot.mode, "desktop_authority_bounded");
  assert.equal(snapshot.activeLimitations[0].key, "elevated_foreground");
  assert.equal(snapshot.fallbackPosture.mode, "resident_reinforced_hold");
  assert.match(snapshot.summary, /elevated/i);
});
