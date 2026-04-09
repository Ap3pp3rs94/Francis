const test = require("node:test");
const assert = require("node:assert/strict");

const {
  armOrbOwnershipUserOverride,
  ORB_OWNERSHIP_STATES,
  ORB_OWNERSHIP_USER_OVERRIDE_HOLD_MS,
  buildOrbOwnershipState,
  buildDefaultOrbOwnershipGovernor,
  isOrbOwnershipUserOverrideActive,
  isOrbOwnershipUserOverrideReason,
  shouldClearOrbOwnershipUserOverrideForReason,
  shouldResetOrbOwnershipForForeground,
} = require("./orb-ownership-state");

test("local stop forces restricted safe fallback ownership", () => {
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    authority: {
      localStopped: true,
    },
    runtimeHealth: {
      status: "nominal",
    },
    orbIgnoreMouseEvents: true,
  });

  assert.equal(ownership.state, ORB_OWNERSHIP_STATES.RESTRICTED);
  assert.equal(ownership.safeFallback, true);
  assert.equal(ownership.orbInteractive, false);
  assert.equal(ownership.shouldIgnoreOrbMouseEvents, true);
});

test("pause hold forces restricted safe fallback ownership", () => {
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    authority: {
      pauseHeld: true,
    },
    runtimeHealth: {
      status: "nominal",
    },
    orbIgnoreMouseEvents: true,
  });

  assert.equal(ownership.state, ORB_OWNERSHIP_STATES.RESTRICTED);
  assert.equal(ownership.reason, "pause_held");
});

test("lens handoff keeps Lens interactive while orb remains in safe fallback", () => {
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.PASS_THROUGH,
    authority: {
      disconnected: true,
    },
    runtimeHealth: {
      status: "disconnected",
    },
    lensVisible: true,
    overlayIgnoreMouseEvents: false,
    orbIgnoreMouseEvents: true,
  });

  assert.equal(ownership.state, ORB_OWNERSHIP_STATES.INTERACTABLE_LENS);
  assert.equal(ownership.lensInteractive, true);
  assert.equal(ownership.safeFallback, true);
  assert.equal(ownership.orbInteractive, false);
});

test("recovering runtime does not silently restore orb interactivity", () => {
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    authority: {
      localStopped: false,
      pauseHeld: false,
      disconnected: false,
    },
    runtimeHealth: {
      status: "recovering",
    },
    orbIgnoreMouseEvents: false,
  });

  assert.equal(ownership.state, ORB_OWNERSHIP_STATES.RESTRICTED);
  assert.equal(ownership.canClaimOrbInteraction, false);
  assert.equal(ownership.orbInteractive, false);
});

test("foreground handoff resets interactive orb ownership when another app takes foreground", () => {
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    authority: {},
    runtimeHealth: { status: "nominal" },
    orbIgnoreMouseEvents: false,
    shellPid: 4000,
    foregroundWindow: { pid: 4000 },
  });

  assert.equal(
    shouldResetOrbOwnershipForForeground({
      ownership,
      foregroundWindow: { pid: 5120 },
      shellPid: 4000,
    }),
    true,
  );
});

test("orb can claim interactivity from pass-through when runtime and authority are healthy", () => {
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    authority: {},
    runtimeHealth: { status: "nominal" },
    orbIgnoreMouseEvents: true,
  });

  assert.equal(ownership.state, ORB_OWNERSHIP_STATES.INTERACTABLE_ORB);
  assert.equal(ownership.orbInteractive, true);
  assert.equal(ownership.shouldIgnoreOrbMouseEvents, false);
});

test("user override hold keeps the orb in pass-through after human reclaim", () => {
  const governor = armOrbOwnershipUserOverride(buildDefaultOrbOwnershipGovernor(), {
    reason: "foreground_window_changed",
    nowMs: 1000,
  });
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    authority: {
      cursorArmed: true,
      modeLabel: "Assist",
    },
    runtimeHealth: { status: "nominal" },
    governor,
    orbIgnoreMouseEvents: true,
    nowMs: 1000 + Math.floor(ORB_OWNERSHIP_USER_OVERRIDE_HOLD_MS / 2),
  });

  assert.equal(ownership.state, ORB_OWNERSHIP_STATES.PASS_THROUGH);
  assert.equal(ownership.userOverrideActive, true);
  assert.equal(ownership.reason, "user_override");
  assert.equal(ownership.modeLabel, "Assist");
  assert.equal(ownership.authorityLabel, "User override");
  assert.equal(ownership.canClaimOrbInteraction, false);
});

test("healthy pass-through keeps assist truth visible without claiming interaction", () => {
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.PASS_THROUGH,
    authority: {
      cursorArmed: true,
      modeLabel: "Assist",
    },
    runtimeHealth: { status: "nominal" },
    orbIgnoreMouseEvents: true,
  });

  assert.equal(ownership.state, ORB_OWNERSHIP_STATES.PASS_THROUGH);
  assert.equal(ownership.modeLabel, "Assist");
  assert.equal(ownership.authorityLabel, "Pass-through");
  assert.equal(ownership.engaged, false);
});

test("orb engagement keeps act truth aligned with interactive ownership", () => {
  const ownership = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    authority: {
      cursorLive: true,
      modeLabel: "Act",
    },
    runtimeHealth: { status: "nominal" },
    orbIgnoreMouseEvents: false,
  });

  assert.equal(ownership.state, ORB_OWNERSHIP_STATES.INTERACTABLE_ORB);
  assert.equal(ownership.modeLabel, "Act");
  assert.equal(ownership.authorityLabel, "Cursor live");
  assert.equal(ownership.engaged, true);
});

test("ownership governor helpers distinguish override hold reasons from explicit reclaim reasons", () => {
  const governor = armOrbOwnershipUserOverride(buildDefaultOrbOwnershipGovernor(), {
    reason: "human_returned",
    nowMs: 1000,
  });

  assert.equal(isOrbOwnershipUserOverrideReason("human_returned"), true);
  assert.equal(shouldClearOrbOwnershipUserOverrideForReason("orb_surface_focus"), true);
  assert.equal(isOrbOwnershipUserOverrideActive(governor, 1001), true);
  assert.equal(isOrbOwnershipUserOverrideActive(governor, 1000 + ORB_OWNERSHIP_USER_OVERRIDE_HOLD_MS + 1), false);
});

test("safe pass-through reset is idempotent", () => {
  const first = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.PASS_THROUGH,
    authority: {},
    runtimeHealth: { status: "nominal" },
    orbIgnoreMouseEvents: true,
  });
  const second = buildOrbOwnershipState({
    requested: ORB_OWNERSHIP_STATES.PASS_THROUGH,
    authority: {},
    runtimeHealth: { status: "nominal" },
    orbIgnoreMouseEvents: true,
  });

  assert.deepEqual(second, first);
});
