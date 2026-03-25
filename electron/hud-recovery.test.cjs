const test = require("node:test");
const assert = require("node:assert/strict");

const { getScheduledHudRecoveryReason } = require("./hud-recovery");

test("returns a recovery reason for managed startup states that are not ready", () => {
  assert.equal(
    getScheduledHudRecoveryReason({
      ready: false,
      allowManagedStart: true,
      mode: "error",
    }),
    "hud-not-ready:error",
  );
  assert.equal(
    getScheduledHudRecoveryReason({
      ready: false,
      allowManagedStart: true,
      mode: "crashed",
    }),
    "hud-not-ready:crashed",
  );
  assert.equal(
    getScheduledHudRecoveryReason({
      ready: false,
      allowManagedStart: true,
      mode: "idle",
    }),
    "hud-not-ready:idle",
  );
});

test("skips recovery when the hud is already ready or deliberately unmanaged", () => {
  assert.equal(
    getScheduledHudRecoveryReason({
      ready: true,
      allowManagedStart: true,
      mode: "managed",
    }),
    "",
  );
  assert.equal(
    getScheduledHudRecoveryReason({
      ready: false,
      allowManagedStart: false,
      mode: "error",
    }),
    "",
  );
  assert.equal(
    getScheduledHudRecoveryReason({
      ready: false,
      allowManagedStart: true,
      mode: "starting",
    }),
    "",
  );
  assert.equal(
    getScheduledHudRecoveryReason({
      ready: false,
      allowManagedStart: true,
      mode: "disabled",
    }),
    "",
  );
});
