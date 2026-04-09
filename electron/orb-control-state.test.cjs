const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildOrbControlState,
  buildPauseAuthorityResult,
} = require("./orb-control-state");

test("orb control state keeps local stop authoritative when remote sync fails", () => {
  const state = buildOrbControlState({
    authorityState: {
      state: "francis_authority",
      eligible: true,
      live: true,
      idleSeconds: 42,
      thresholdSeconds: 30,
    },
    hudState: { ready: true },
    recovery: { needed: false },
    inputState: { humanActive: false },
    ignoreMouseEvents: true,
    safetyState: {
      localStopped: true,
      remoteSyncStatus: "failed",
      summary: "Local stop confirmed. Remote sync failed.",
      detail: "Francis dropped local authority immediately, but remote confirmation failed.",
      remoteError: "fetch failed",
    },
  });

  assert.equal(state.localStopped, true);
  assert.equal(state.cursorLive, false);
  assert.equal(state.authorityLabel, "Local stop");
  assert.equal(state.remoteSyncStatus, "failed");
  assert.equal(state.canPause, false);
  assert.equal(state.diagnostics.remoteError, "fetch failed");
});

test("orb control state degrades safely when HUD is disconnected", () => {
  const state = buildOrbControlState({
    authorityState: {
      state: "idle_armed",
      eligible: true,
      live: false,
      idleSeconds: 12,
      thresholdSeconds: 30,
    },
    hudState: { ready: false },
    recovery: { needed: true },
    inputState: { humanActive: true },
    ignoreMouseEvents: true,
    safetyState: {
      disconnected: true,
      remoteSyncStatus: "pending",
      detail: "HUD disconnected. Human control remains primary.",
    },
  });

  assert.equal(state.disconnected, true);
  assert.equal(state.cursorArmed, false);
  assert.equal(state.authorityLabel, "Disconnected");
  assert.equal(state.inputOwnership, "pass_through");
});

test("pause authority result stays honest during live commits", () => {
  const result = buildPauseAuthorityResult({ activeLive: true });
  assert.equal(result.ok, false);
  assert.equal(result.status, "use_stop");
  assert.match(result.summary, /use stop/i);
});

test("orb control state preserves local stop and pause semantics during recovery", () => {
  const paused = buildOrbControlState({
    authorityState: {
      state: "idle_armed",
      eligible: true,
      live: false,
      idleSeconds: 18,
      thresholdSeconds: 30,
    },
    hudState: { ready: true },
    recovery: { needed: true },
    inputState: { humanActive: false },
    ignoreMouseEvents: true,
    safetyState: {
      pauseHeld: true,
      remoteSyncStatus: "pending",
      summary: "Paused locally.",
      detail: "Waiting for the remote clear to catch up.",
    },
  });

  assert.equal(paused.pauseHeld, true);
  assert.equal(paused.canPause, true);
  assert.equal(paused.authorityLabel, "Paused locally");
  assert.equal(paused.cursorLive, false);
});

test("orb control state keeps degraded user-facing detail calm while diagnostics hold transport failures", () => {
  const state = buildOrbControlState({
    authorityState: {
      state: "idle_armed",
      eligible: true,
      live: false,
      idleSeconds: 18,
      thresholdSeconds: 30,
    },
    hudState: { ready: true },
    recovery: { needed: false },
    inputState: { humanActive: false },
    ignoreMouseEvents: true,
    safetyState: {
      degraded: true,
      remoteSyncStatus: "failed",
      summary: "Orb authority degraded. Human control remains primary.",
      detail: "Francis released local authority because the authority sync could not be confirmed.",
      remoteError: "fetch failed",
    },
  });

  assert.equal(state.detail, "Francis released local authority because the authority sync could not be confirmed.");
  assert.equal(state.diagnostics.remoteError, "fetch failed");
});

test("orb control state preserves canonical execution truth for the compact orb surface", () => {
  const state = buildOrbControlState({
    authorityState: {
      state: "francis_authority",
      eligible: true,
      live: true,
      idleSeconds: 34,
      thresholdSeconds: 30,
      activeCommandKind: "mouse.drag",
      executionPhase: "drag_act",
      executionSummary: "Anchored drag control is live.",
      executionDetail: "Francis is maintaining anchored contact and tension across the drag path.",
      executionTarget: { x: 640, y: 420, coordinate_space: "screen" },
    },
    hudState: { ready: true },
    recovery: { needed: false },
    inputState: { humanActive: false },
    ignoreMouseEvents: false,
    safetyState: {},
  });

  assert.equal(state.activeCommandKind, "mouse.drag");
  assert.equal(state.executionPhase, "drag_act");
  assert.equal(state.executionSummary, "Anchored drag control is live.");
  assert.equal(state.executionDetail, "Francis is maintaining anchored contact and tension across the drag path.");
  assert.deepEqual(state.executionTarget, { x: 640, y: 420, coordinate_space: "screen" });
});
