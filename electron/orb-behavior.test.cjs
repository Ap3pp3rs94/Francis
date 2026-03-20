const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_ORB_BEHAVIOR_MODE,
  listOrbBehaviorModes,
  normalizeOrbBehaviorMode,
  resolveOrbBehaviorMode,
} = require("./orb-behavior");

test("orb behavior normalizes unknown values to autonomous", () => {
  assert.equal(normalizeOrbBehaviorMode("trace"), "trace");
  assert.equal(normalizeOrbBehaviorMode("unknown"), DEFAULT_ORB_BEHAVIOR_MODE);
});

test("orb behavior exposes the three operator-facing modes", () => {
  assert.deepEqual(
    listOrbBehaviorModes().map((entry) => entry.id),
    ["explore", "trace", "autonomous"],
  );
});

test("orb behavior resolves trace explore autonomous authority and handback", () => {
  assert.equal(resolveOrbBehaviorMode("trace").effective, "trace");
  assert.equal(resolveOrbBehaviorMode("explore").effective, "explore");
  assert.equal(resolveOrbBehaviorMode("autonomous", { humanActive: true }).effective, "trace");
  assert.equal(resolveOrbBehaviorMode("autonomous", { humanActive: false }).effective, "explore");
  assert.equal(resolveOrbBehaviorMode("autonomous", { authorityLive: true }).effective, "authority");
  assert.equal(resolveOrbBehaviorMode("autonomous", { handback: true }).effective, "handback");
});
