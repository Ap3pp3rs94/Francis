const SUPPORT_BUNDLE_VERSION = 1;

function buildSupportSummary(lifecycle = {}, hud = null, recovery = null) {
  const preflight = lifecycle?.preflight || {};
  const degradedMode = lifecycle?.degradedMode || {};
  const update = lifecycle?.update || {};
  const delivery = lifecycle?.delivery || {};
  const migration = lifecycle?.migration || {};
  const rollback = lifecycle?.rollback || {};
  const provider = lifecycle?.provider || {};
  const authority = lifecycle?.authority || {};
  const signing = lifecycle?.signing || {};
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

  if (delivery.severity === "high" || delivery.severity === "medium") {
    parts.push(`delivery ${String(delivery.channel || "unknown")} ${String(delivery.severity)}`);
  }

  if (migration.blocked > 0) {
    parts.push(`${migration.blocked} migration checks blocked`);
  } else if (migration.attention > 0) {
    parts.push(`${migration.attention} migration checks need review`);
  }

  if (degradedMode.mode && degradedMode.mode !== "nominal") {
    parts.push(`degraded mode ${String(degradedMode.mode)}`);
  }

  if (provider.severity === "high" || provider.severity === "medium") {
    parts.push(`provider ${String(provider.activeProviderLabel || "unconfigured")} ${String(provider.severity)}`);
  }

  if (authority.severity === "high" || authority.severity === "medium") {
    parts.push(`authority ${String(authority.severity)}`);
  }

  if (signing.severity === "high" || signing.severity === "medium") {
    parts.push(`signing ${String(signing.mode || signing.severity)}`);
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
      accessibility: lifecycle?.accessibility || null,
      history: lifecycle?.history || null,
      provider: lifecycle?.provider || null,
      authority: lifecycle?.authority || null,
      signing: lifecycle?.signing || null,
      launchAtLogin: lifecycle?.launchAtLogin || null,
      degradedMode: lifecycle?.degradedMode || null,
      update: lifecycle?.update || null,
      delivery: lifecycle?.delivery || null,
      portability: lifecycle?.portability || null,
      retainedState: lifecycle?.retainedState || null,
      preflight: lifecycle?.preflight || null,
      migration: lifecycle?.migration || null,
      rollback: lifecycle?.rollback || null,
      decommission: lifecycle?.decommission || null,
      provenance: lifecycle?.provenance || null,
      repair: lifecycle?.repair || null,
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
