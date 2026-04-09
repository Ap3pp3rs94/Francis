const test = require("node:test");
const assert = require("node:assert/strict");

const {
  resolveOrbFirstAppActivation,
  resolveOrbFirstSecondInstance,
  resolveStartupSurface,
} = require("./startup-surface");

test("startup surface keeps the orb as the only boot window for operator startup", () => {
  const state = resolveStartupSurface({ startupProfile: "operator" });

  assert.equal(state.startupProfile.effective, "operator");
  assert.equal(state.bootOrbWindow, true);
  assert.equal(state.showOrbWindowOnBoot, true);
  assert.equal(state.constructLensWindowOnBoot, false);
  assert.equal(state.bootLensWindow, false);
  assert.equal(state.showLensWindowOnBoot, false);
  assert.equal(state.lensBootstrap, "explicit");
  assert.equal(state.visibleStartupBody, "orb");
  assert.equal(state.orbFirst, true);
});

test("startup surface keeps the Lens lazy even when recovery-safe inspection is active", () => {
  const state = resolveStartupSurface({ startupProfile: "core_only" }, { recoveryNeeded: true });

  assert.equal(state.startupProfile.effective, "recovery_safe");
  assert.equal(state.bootOrbWindow, true);
  assert.equal(state.showOrbWindowOnBoot, true);
  assert.equal(state.constructLensWindowOnBoot, false);
  assert.equal(state.bootLensWindow, false);
  assert.equal(state.showLensWindowOnBoot, false);
  assert.equal(state.lensBootstrap, "explicit");
  assert.equal(state.visibleStartupBody, "orb");
});

test("startup surface keeps core-only explicit and non-visible without constructing Lens", () => {
  const state = resolveStartupSurface({ startupProfile: "core_only" });

  assert.equal(state.startupProfile.effective, "core_only");
  assert.equal(state.bootOrbWindow, true);
  assert.equal(state.showOrbWindowOnBoot, false);
  assert.equal(state.constructLensWindowOnBoot, false);
  assert.equal(state.bootLensWindow, false);
  assert.equal(state.showLensWindowOnBoot, false);
  assert.equal(state.visibleStartupBody, "none");
  assert.equal(state.orbFirst, true);
});

test("app activation restores the orb only when no Francis surface is visible", () => {
  assert.deepEqual(
    resolveOrbFirstAppActivation({ orbVisible: false, lensVisible: false }),
    {
      ensureOrbWindow: true,
      showOrbWindow: true,
      reason: "activate_show_orb",
    },
  );

  assert.deepEqual(
    resolveOrbFirstAppActivation({ orbVisible: true, lensVisible: false }),
    {
      ensureOrbWindow: true,
      showOrbWindow: false,
      reason: "activate_noop",
    },
  );
});

test("second-instance flow always re-centers the orb instead of toggling the whole overlay", () => {
  assert.deepEqual(
    resolveOrbFirstSecondInstance({ orbVisible: false, lensVisible: false }),
    {
      ensureOrbWindow: true,
      showOrbWindow: true,
      preserveLensWindow: false,
      reason: "second_instance_show_orb",
    },
  );

  assert.deepEqual(
    resolveOrbFirstSecondInstance({ orbVisible: true, lensVisible: true }),
    {
      ensureOrbWindow: true,
      showOrbWindow: true,
      preserveLensWindow: true,
      reason: "second_instance_focus_orb",
    },
  );
});
