const SUPPORT_BUNDLE_VERSION = 1;

function buildSupportSummary(lifecycle = {}, hud = null, recovery = null) {
  const preflight = lifecycle?.preflight || {};
  const update = lifecycle?.update || {};
  const rollback = lifecycle?.rollback || {};
  const parts = [];

  if (preflight.blocked > 0) {
    parts.push(`${preflight.blocked} preflight checks blocked`);
  } else if (preflight.attention > 0) {
    parts.push(`${preflight.attention} preflight checks need attention`);
  } else {
    parts.push("preflight nominal");
  }

  if (update.pendingNotice) {
    parts.push(`update notice ${String(update.currentBuild || "pending")}`);
  }

  if (recovery?.needed) {
    parts.push(`recovery ${String(recovery.status || "attention")}`);
  }

  if (hud?.mode) {
    parts.push(`HUD ${String(hud.mode)}`);
  }

  if (rollback.count > 0) {
    parts.push(`${rollback.count} rollback snapshots`);
  }

  return parts.join(" | ");
}

function buildSupportBundle({
  generatedAt = new Date().toISOString(),
  hudUrl = "unknown",
  overlay = {},
  lifecycle = {},
  hud = null,
  recovery = null,
  display = null,
} = {}) {
  return {
    version: SUPPORT_BUNDLE_VERSION,
    generatedAt,
    summary: buildSupportSummary(lifecycle, hud, recovery),
    hudUrl,
    overlay: {
      ignoreMouseEvents: Boolean(overlay?.ignoreMouseEvents),
      alwaysOnTop: Boolean(overlay?.alwaysOnTop),
      visible: Boolean(overlay?.visible),
      bounds: overlay?.bounds || null,
      targetDisplayId: overlay?.targetDisplayId ?? null,
      activeDisplayId: overlay?.activeDisplayId ?? null,
      shortcuts: overlay?.shortcuts || {},
    },
    lifecycle: {
      buildIdentity: lifecycle?.buildIdentity || "unknown",
      distribution: lifecycle?.distribution || "source",
      version: lifecycle?.version || "unknown",
      revision: lifecycle?.revision || null,
      startupProfile: lifecycle?.startupProfile || null,
      launchAtLogin: lifecycle?.launchAtLogin || null,
      update: lifecycle?.update || null,
      portability: lifecycle?.portability || null,
      retainedState: lifecycle?.retainedState || null,
      preflight: lifecycle?.preflight || null,
      rollback: lifecycle?.rollback || null,
      decommission: lifecycle?.decommission || null,
      provenance: lifecycle?.provenance || null,
      session: lifecycle?.session || null,
    },
    hud,
    recovery,
    display,
  };
}

module.exports = {
  SUPPORT_BUNDLE_VERSION,
  buildSupportBundle,
};
