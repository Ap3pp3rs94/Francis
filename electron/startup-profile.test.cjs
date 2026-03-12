const test = require("node:test");
const assert = require("node:assert/strict");

const {
  DEFAULT_STARTUP_PROFILE,
  listStartupProfiles,
  normalizeStartupProfile,
  resolveStartupProfile,
} = require("./startup-profile");

test("startup profiles normalize unknown values to operator", () => {
  assert.equal(normalizeStartupProfile("quiet"), "quiet");
  assert.equal(normalizeStartupProfile("recovery_safe"), DEFAULT_STARTUP_PROFILE);
  assert.equal(normalizeStartupProfile("unknown"), DEFAULT_STARTUP_PROFILE);
});

test("startup profile options expose only operator-facing choices by default", () => {
  const options = listStartupProfiles();

  assert.deepEqual(
    options.map((entry) => entry.id),
    ["operator", "quiet", "core_only"],
  );
});

test("startup profile resolves quiet startup without changing law", () => {
  const state = resolveStartupProfile({ startupProfile: "quiet" });

  assert.equal(state.requested, "quiet");
  assert.equal(state.effective, "quiet");
  assert.equal(state.visible, true);
  assert.equal(state.ignoreMouseEvents, true);
  assert.equal(state.recoveryLocked, false);
});

test("startup profile forces recovery-safe inspection after an unclean exit", () => {
  const state = resolveStartupProfile({ startupProfile: "core_only" }, { recoveryNeeded: true });

  assert.equal(state.requested, "core_only");
  assert.equal(state.effective, "recovery_safe");
  assert.equal(state.visible, true);
  assert.equal(state.ignoreMouseEvents, false);
  assert.equal(state.recoveryLocked, true);
});
