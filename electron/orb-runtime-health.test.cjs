const test = require("node:test");
const assert = require("node:assert/strict");

const {
  FAILURE_CIRCUIT_THRESHOLD,
  escalateOrbRuntimeFailure,
  getOrbRuntimeRetryDelayMs,
  isOrbRuntimeProbeDeferred,
  recordOrbRuntimeHealthy,
} = require("./orb-runtime-health");

test("runtime failure escalation applies bounded retry backoff before reopening probes", () => {
  const state = escalateOrbRuntimeFailure({}, {
    reason: "fetch failed",
    source: "authority",
    nowMs: 1000,
  });
  assert.equal(state.status, "degraded");
  assert.ok(state.nextProbeAtMs > 1000);
  assert.equal(isOrbRuntimeProbeDeferred(state, 1001), true);
  assert.match(state.detail, /degraded local posture/i);
});

test("runtime failure escalation opens a circuit after repeated failures", () => {
  let state = {};
  for (let index = 0; index < FAILURE_CIRCUIT_THRESHOLD; index += 1) {
    state = escalateOrbRuntimeFailure(state, {
      reason: "Orb authority sync failed: fetch failed",
      source: "authority",
      nowMs: 1000 + index,
    });
  }
  assert.equal(state.status, "disconnected");
  assert.ok(state.circuitOpenUntilMs > state.nextProbeAtMs - getOrbRuntimeRetryDelayMs(state.failureCount));
  assert.equal(isOrbRuntimeProbeDeferred(state, state.circuitOpenUntilMs - 1), true);
});

test("runtime healthy proofs clear retry backoff and circuit state once recovery settles", () => {
  let state = {};
  for (let index = 0; index < FAILURE_CIRCUIT_THRESHOLD; index += 1) {
    state = escalateOrbRuntimeFailure(state, {
      reason: "fetch failed",
      source: "hud",
      nowMs: 1000 + index,
    });
  }
  state = recordOrbRuntimeHealthy(state, {
    reason: "Fresh healthy proofs are back.",
    source: "hud",
    nowMs: 3000,
  });
  assert.equal(state.status, "recovering");
  state = recordOrbRuntimeHealthy(state, {
    reason: "Fresh healthy proofs are back.",
    source: "hud",
    nowMs: 4000,
  });
  assert.equal(state.status, "nominal");
  assert.equal(state.nextProbeAtMs, 0);
  assert.equal(state.circuitOpenUntilMs, 0);
});
