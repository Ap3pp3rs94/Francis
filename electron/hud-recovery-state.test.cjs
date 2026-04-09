const test = require("node:test");
const assert = require("node:assert/strict");

const {
  beginHudRecoveryAttempt,
  buildDefaultHudRecoveryState,
  finishHudRecoveryAttempt,
  isStaleHudGeneration,
  noteHudEndpointFailure,
  noteHudEndpointSuccess,
  noteHudGenerationReady,
  noteHudProcessState,
  scheduleHudRecovery,
} = require("./hud-recovery-state");

test("scheduleHudRecovery dedupes duplicate timers and enforces max attempts", () => {
  let state = buildDefaultHudRecoveryState();
  state = noteHudGenerationReady(state, { pid: 4100, nowMs: 100 });

  const first = scheduleHudRecovery(state, { reason: "hud-unreachable", nowMs: 200, maxAttempts: 2 });
  assert.equal(first.scheduled, true);
  assert.equal(first.duplicate, false);
  assert.equal(first.state.recovery.attempt, 1);

  const duplicate = scheduleHudRecovery(first.state, { reason: "hud-unreachable", nowMs: 220, maxAttempts: 2 });
  assert.equal(duplicate.scheduled, false);
  assert.equal(duplicate.duplicate, true);

  const started = beginHudRecoveryAttempt(first.state, { recoveryId: first.recoveryId, nowMs: 250 });
  assert.equal(started.started, true);

  const whileInFlight = scheduleHudRecovery(started.state, { reason: "hud-unreachable", nowMs: 260, maxAttempts: 2 });
  assert.equal(whileInFlight.scheduled, false);
  assert.equal(whileInFlight.duplicate, true);

  state = finishHudRecoveryAttempt(started.state, { recoveryId: first.recoveryId, success: false, nowMs: 300 });
  const second = scheduleHudRecovery(state, { reason: "hud-unreachable", nowMs: 320, maxAttempts: 2 });
  assert.equal(second.scheduled, true);
  assert.equal(second.state.recovery.attempt, 2);
  const secondStarted = beginHudRecoveryAttempt(second.state, { recoveryId: second.recoveryId, nowMs: 330 });
  const secondFinished = finishHudRecoveryAttempt(secondStarted.state, { recoveryId: second.recoveryId, success: false, nowMs: 340 });
  const exhausted = scheduleHudRecovery(secondFinished, { reason: "hud-unreachable", nowMs: 360, maxAttempts: 2 });
  assert.equal(exhausted.scheduled, false);
  assert.equal(exhausted.exhausted, true);
});

test("noteHudGenerationReady rotates generations and tracks previous pid", () => {
  let state = buildDefaultHudRecoveryState();
  state = noteHudGenerationReady(state, { pid: 5000, nowMs: 100 });
  assert.equal(state.generation, 1);
  assert.equal(state.currentPid, 5000);
  assert.equal(state.previousPid, null);

  const same = noteHudGenerationReady(state, { pid: 5000, nowMs: 110 });
  assert.equal(same.generation, 1);

  const next = noteHudGenerationReady(same, { pid: 5001, nowMs: 120 });
  assert.equal(next.generation, 2);
  assert.equal(next.currentPid, 5001);
  assert.equal(next.previousPid, 5000);
});

test("stale generation successes and failures are ignored", () => {
  let state = buildDefaultHudRecoveryState();
  state = noteHudGenerationReady(state, { pid: 6100, nowMs: 100 });

  let result = noteHudEndpointSuccess(state, { channel: "health", generation: 1, nowMs: 120 });
  assert.equal(result.ignored, false);
  assert.equal(result.state.lastHealthOkAtMs, 120);

  result = noteHudEndpointSuccess(result.state, { channel: "perception", generation: 0, nowMs: 140 });
  assert.equal(result.ignored, true);
  assert.equal(result.state.lastPerceptionOkAtMs, 0);

  const failure = noteHudEndpointFailure(state, {
    channel: "authority_state",
    generation: 0,
    nowMs: 150,
    kind: "connection_refused",
    message: "connect ECONNREFUSED",
  });
  assert.equal(failure.ignored, true);
  assert.equal(failure.state.lastFailure, null);
});

test("finishHudRecoveryAttempt clears in-flight state and noteHudProcessState tracks liveness", () => {
  let state = buildDefaultHudRecoveryState();
  state = noteHudGenerationReady(state, { pid: 7100, nowMs: 100 });
  const scheduled = scheduleHudRecovery(state, { reason: "hud-crashed", nowMs: 200, maxAttempts: 3 });
  const started = beginHudRecoveryAttempt(scheduled.state, { recoveryId: scheduled.recoveryId, nowMs: 250 });
  assert.equal(started.state.recovery.inFlight, true);

  state = noteHudProcessState(started.state, { pid: 7100, alive: false });
  assert.equal(state.childAlive, false);

  state = finishHudRecoveryAttempt(state, { recoveryId: scheduled.recoveryId, success: true, nowMs: 300 });
  assert.equal(state.recovery.inFlight, false);
  assert.equal(state.recovery.timerActive, false);
  assert.equal(state.recovery.attempt, 0);
  assert.equal(isStaleHudGeneration(state, 1), false);
  assert.equal(isStaleHudGeneration(state, 0), true);
});
