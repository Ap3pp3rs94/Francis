const test = require("node:test");
const assert = require("node:assert/strict");

const { SUPPORT_BUNDLE_VERSION, buildSupportBundle } = require("./support-bundle");

test("support bundle captures lifecycle recovery and display posture", () => {
  const bundle = buildSupportBundle({
    generatedAt: "2026-03-12T12:00:00Z",
    hudUrl: "http://127.0.0.1:8767",
    overlay: {
      ignoreMouseEvents: true,
      alwaysOnTop: true,
      visible: false,
      bounds: { x: 10, y: 20, width: 1200, height: 800 },
      targetDisplayId: 2,
      activeDisplayId: 2,
      shortcuts: { toggleOverlay: "Ctrl+Shift+Alt+F" },
    },
    lifecycle: {
      buildIdentity: "0.1.0+abc1234",
      distribution: "installer",
      degradedMode: { mode: "reduced" },
      accessibility: { motionMode: "reduce", effectiveMotionMode: "reduce" },
      history: { count: 2, latestKind: "support.export" },
      provider: { severity: "medium", activeProviderLabel: "OpenAI", fallbackSummary: "none" },
      authority: { severity: "medium", supportConfigured: true, supportBound: false },
      signing: { severity: "medium", mode: "unsigned", ready: false },
      delivery: { severity: "medium", channel: "portable" },
      preflight: { blocked: 1, attention: 0 },
      migration: { blocked: 0, attention: 2 },
      update: { pendingNotice: true, currentBuild: "0.1.0+abc1234" },
      rollback: { count: 2 },
      decommission: { summary: "clean uninstall available" },
    },
    hud: { mode: "managed", ready: true },
    recovery: { needed: true, status: "attention" },
    display: { targetDisplayId: 2 },
  });

  assert.equal(bundle.version, SUPPORT_BUNDLE_VERSION);
  assert.equal(bundle.lifecycle.distribution, "installer");
  assert.equal(bundle.overlay.targetDisplayId, 2);
  assert.match(bundle.summary, /preflight/i);
  assert.match(bundle.summary, /update notice/i);
  assert.match(bundle.summary, /migration/i);
  assert.match(bundle.summary, /degraded mode/i);
  assert.match(bundle.summary, /provider/i);
  assert.match(bundle.summary, /authority/i);
  assert.match(bundle.summary, /signing/i);
  assert.match(bundle.summary, /delivery/i);
  assert.match(bundle.summary, /recovery/i);
  assert.match(bundle.summary, /rollback/i);
  assert.equal(bundle.lifecycle.decommission.summary, "clean uninstall available");
  assert.equal(bundle.lifecycle.migration.attention, 2);
  assert.equal(bundle.lifecycle.degradedMode.mode, "reduced");
  assert.equal(bundle.lifecycle.accessibility.motionMode, "reduce");
  assert.equal(bundle.lifecycle.history.latestKind, "support.export");
  assert.equal(bundle.lifecycle.provider.activeProviderLabel, "OpenAI");
  assert.equal(bundle.lifecycle.authority.supportConfigured, true);
  assert.equal(bundle.lifecycle.signing.mode, "unsigned");
  assert.equal(bundle.lifecycle.delivery.channel, "portable");
});
