const test = require("node:test");
const assert = require("node:assert/strict");

const { buildRepairPlan } = require("./update-repair");

test("repair plan escalates when blocked checks and rollback are present", () => {
  const plan = buildRepairPlan({
    update: {
      pendingNotice: true,
    },
    preflight: {
      blocked: 2,
      attention: 1,
    },
    migration: {
      blocked: 1,
      attention: 1,
    },
    recovery: {
      needed: true,
    },
    rollback: {
      count: 3,
    },
    portability: {
      lastImportStatus: "blocked",
      lastImportMessage: "Payload channel mismatch.",
    },
    support: {
      lastBundleAt: null,
    },
    hud: {
      mode: "managed",
    },
    decommission: {
      userDataPath: "C:\\Users\\Alice\\AppData\\Roaming\\Francis Overlay",
    },
  });

  assert.equal(plan.severity, "high");
  assert.equal(plan.actions.reset_shell_state.enabled, true);
  assert.equal(plan.actions.restore_snapshot.enabled, true);
  assert.equal(plan.actions.export_support_bundle.enabled, true);
  assert.equal(plan.actions.open_user_data.enabled, true);
  assert.match(plan.summary, /blocked/i);
  assert.equal(plan.steps.some((step) => /support bundle/i.test(step)), true);
});

test("repair plan stays nominal when no repair signals are active", () => {
  const plan = buildRepairPlan({
    update: {
      pendingNotice: false,
    },
    preflight: {
      blocked: 0,
      attention: 0,
    },
    migration: {
      blocked: 0,
      attention: 0,
    },
    recovery: {
      needed: false,
    },
    rollback: {
      count: 0,
    },
    portability: {
      lastImportStatus: "idle",
    },
    support: {
      lastBundleAt: "2026-03-12T12:00:00Z",
    },
    hud: {
      mode: "external",
    },
  });

  assert.equal(plan.severity, "low");
  assert.equal(plan.actions.acknowledge_update.enabled, false);
  assert.equal(plan.actions.reset_shell_state.enabled, false);
  assert.equal(plan.actions.restore_snapshot.enabled, false);
  assert.equal(plan.steps[0], "No repair actions are required right now.");
});
