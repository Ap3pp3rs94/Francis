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
    authority: {
      severity: "high",
      summary: "Support authority is configured without a tenant or managed-copy binding.",
    },
    signing: {
      severity: "medium",
      summary: "Packaged Windows builds are currently unsigned.",
    },
    decommission: {
      userDataPath: "C:\\Users\\Alice\\AppData\\Roaming\\Francis Overlay",
    },
  });

  assert.equal(plan.severity, "high");
  assert.equal(plan.actions.repair_shell_state.enabled, true);
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
    authority: {
      severity: "low",
    },
    signing: {
      severity: "low",
    },
  });

  assert.equal(plan.severity, "low");
  assert.equal(plan.actions.acknowledge_update.enabled, false);
  assert.equal(plan.actions.reset_shell_state.enabled, false);
  assert.equal(plan.actions.restore_snapshot.enabled, false);
  assert.equal(plan.steps[0], "No repair actions are required right now.");
});

test("repair plan surfaces provider posture when model execution is narrowed", () => {
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
      count: 1,
    },
    portability: {
      lastImportStatus: "idle",
    },
    support: {
      lastBundleAt: "2026-03-12T12:00:00Z",
    },
    hud: {
      mode: "managed",
    },
    provider: {
      severity: "medium",
      activeProviderLabel: "OpenAI",
      summary: "OpenAI is the only active provider. Provider failure will narrow model-backed work immediately.",
    },
    authority: {
      severity: "low",
    },
    signing: {
      severity: "low",
    },
  });

  assert.equal(plan.severity, "medium");
  assert.ok(plan.steps.some((step) => /provider posture/i.test(step)));
  assert.ok(plan.cards.some((entry) => entry.label === "Provider"));
});

test("repair plan surfaces authority posture when support or connector identity is ambiguous", () => {
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
      count: 1,
    },
    portability: {
      lastImportStatus: "idle",
    },
    support: {
      lastBundleAt: "2026-03-12T12:00:00Z",
    },
    hud: {
      mode: "managed",
    },
    provider: {
      severity: "low",
    },
    authority: {
      severity: "medium",
      summary: "Connector or support authority is configured while node or service identity remains implicit.",
    },
    signing: {
      severity: "low",
    },
  });

  assert.equal(plan.severity, "medium");
  assert.ok(plan.steps.some((step) => /authority posture/i.test(step)));
  assert.ok(plan.cards.some((entry) => entry.label === "Authority"));
});

test("repair plan surfaces signing posture when packaged trust is unsigned", () => {
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
      count: 1,
    },
    portability: {
      lastImportStatus: "idle",
    },
    support: {
      lastBundleAt: "2026-03-12T12:00:00Z",
    },
    hud: {
      mode: "managed",
    },
    provider: {
      severity: "low",
    },
    authority: {
      severity: "low",
    },
    signing: {
      severity: "medium",
      summary: "Packaged Windows builds are currently unsigned. Installer trust remains blocked on certificate material.",
    },
  });

  assert.equal(plan.severity, "medium");
  assert.ok(plan.steps.some((step) => /Windows signing posture/i.test(step)));
  assert.ok(plan.cards.some((entry) => entry.label === "Signing"));
});
