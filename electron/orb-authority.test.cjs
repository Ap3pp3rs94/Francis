const test = require("node:test");
const assert = require("node:assert/strict");

const {
  canEngageOrbAuthority,
  detectHumanActivitySignal,
  detectHumanCursorReturn,
  detectHumanIdleRegression,
  detectHumanKeyboardReturn,
  inferOrbAuthorityState,
} = require("./orb-authority");

test("canEngageOrbAuthority requires eligibility and idle threshold", () => {
  assert.equal(canEngageOrbAuthority({ eligible: false, idleSeconds: 40, thresholdSeconds: 30 }), false);
  assert.equal(canEngageOrbAuthority({ eligible: true, idleSeconds: 29, thresholdSeconds: 30 }), false);
  assert.equal(canEngageOrbAuthority({ eligible: true, idleSeconds: 30, thresholdSeconds: 30 }), true);
});

test("inferOrbAuthorityState distinguishes human active idle armed authority and handback", () => {
  assert.equal(inferOrbAuthorityState({ eligible: false, idleSeconds: 0 }), "human_active");
  assert.equal(inferOrbAuthorityState({ eligible: true, idleSeconds: 8, thresholdSeconds: 30 }), "idle_armed");
  assert.equal(inferOrbAuthorityState({ eligible: true, live: true, idleSeconds: 30, thresholdSeconds: 30 }), "francis_authority");
  assert.equal(inferOrbAuthorityState({ handback: true }), "handback");
});

test("detectHumanCursorReturn ignores synthetic grace and catches cursor deviation", () => {
  assert.equal(
    detectHumanCursorReturn({
      live: true,
      currentCursor: { x: 200, y: 100 },
      syntheticCursor: { x: 204, y: 104 },
      lastSyntheticAtMs: 950,
      nowMs: 1000,
    }),
    false,
  );
  assert.equal(
    detectHumanCursorReturn({
      live: true,
      currentCursor: { x: 200, y: 100 },
      syntheticCursor: { x: 240, y: 140 },
      lastSyntheticAtMs: 500,
      nowMs: 1000,
    }),
    true,
  );
});

test("detectHumanKeyboardReturn waits out grace and idle reset", () => {
  assert.equal(detectHumanKeyboardReturn({ live: true, idleSeconds: 0, lastSyntheticAtMs: 900, nowMs: 1000 }), false);
  assert.equal(detectHumanKeyboardReturn({ live: true, idleSeconds: 0, lastSyntheticAtMs: 0, nowMs: 2500 }), true);
});

test("detectHumanIdleRegression catches real idle drops after synthetic grace", () => {
  assert.equal(
    detectHumanIdleRegression({
      live: true,
      idleSeconds: 5,
      lastObservedIdleSeconds: 21,
      lastSyntheticAtMs: 0,
      nowMs: 2500,
    }),
    true,
  );
  assert.equal(
    detectHumanIdleRegression({
      live: true,
      idleSeconds: 5,
      lastObservedIdleSeconds: 21,
      lastSyntheticAtMs: 2200,
      nowMs: 2500,
    }),
    false,
  );
});

test("detectHumanActivitySignal respects real activity after synthetic input", () => {
  assert.equal(
    detectHumanActivitySignal({
      live: true,
      lastHumanActivitySignalAtMs: 4200,
      lastSyntheticAtMs: 3900,
      nowMs: 4280,
    }),
    true,
  );
  assert.equal(
    detectHumanActivitySignal({
      live: true,
      lastHumanActivitySignalAtMs: 3900,
      lastSyntheticAtMs: 4200,
      nowMs: 4280,
    }),
    false,
  );
});
