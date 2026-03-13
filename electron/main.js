const path = require("node:path");
const fs = require("node:fs");
const { app, BrowserWindow, Menu, Tray, dialog, globalShortcut, ipcMain, nativeImage, screen, shell } = require("electron");
const { createHudRuntimeManager } = require("./hud-runtime");
const {
  buildDefaultPreferences,
  PREFERENCES_VERSION,
  getPreferencesPath,
  loadPreferences,
  normalizeBounds,
  resolveTargetDisplay,
  savePreferences,
} = require("./preferences");
const {
  SESSION_STATE_VERSION,
  buildDefaultSessionState,
  getSessionStatePath,
  loadSessionState,
  saveSessionState,
} = require("./session-state");
const { getLaunchAtLoginState, setLaunchAtLogin } = require("./login-item");
const { normalizeStartupProfile, resolveStartupProfile } = require("./startup-profile");
const { resolveBuildIdentity } = require("./build-info");
const {
  loadUpdateState,
  saveUpdateState,
  acknowledgeUpdateNotice,
  buildUpdatePosture,
  getUpdateStatePath,
  reconcileUpdateState,
} = require("./update-state");
const {
  assessPortablePayloadCompatibility,
  buildDefaultPortabilityState,
  buildOverlayExportPayload,
  extractPortablePreferences,
  loadPortabilityState,
  savePortabilityState,
} = require("./overlay-portability");
const {
  buildDefaultSupportState,
  getSupportStatePath,
  loadSupportState,
  saveSupportState,
} = require("./support-state");
const { buildRuntimeProvenance, loadGeneratedProvenance } = require("./build-provenance");
const { describeRetainedState } = require("./retained-state");
const { buildPreflightState } = require("./preflight");
const { createShellBackup, restoreShellBackup, summarizeBackups } = require("./backup-state");
const { buildDecommissionPlan } = require("./decommission-plan");
const { buildSupportBundle } = require("./support-bundle");

const HUD_URL = process.env.FRANCIS_HUD_URL || "http://127.0.0.1:8767";
const OVERLAY_TOGGLE_SHORTCUT = "Control+Shift+Alt+F";
const CLICK_THROUGH_TOGGLE_SHORTCUT = "Control+Shift+Alt+C";

let mainWindow = null;
let tray = null;
let ipcRegistered = false;
let overlayPreferences = null;
let sessionState = null;
let updateState = null;
let buildInfo = null;
let portabilityState = null;
let backupState = null;
let supportState = null;
let buildProvenance = null;
let preferenceSaveTimer = null;
let hudRuntime = null;
let hudRecoveryTimer = null;
let hudRecoveryAttempts = 0;
let quitAfterHudShutdown = false;
let overlayState = {
  ignoreMouseEvents: false,
  alwaysOnTop: true,
};
let overlayRecovery = {
  needed: false,
  status: "nominal",
  message: "",
  lastExitReason: "",
};

function log(message, extra) {
  if (extra === undefined) {
    console.log(`[francis-overlay] ${message}`);
    return;
  }
  console.log(`[francis-overlay] ${message}`, extra);
}

function setOverlayRecovery(next = {}) {
  overlayRecovery = {
    needed: Boolean(next.needed),
    status: String(next.status || (next.needed ? "attention" : "nominal")),
    message: String(next.message || ""),
    lastExitReason: String(next.lastExitReason || ""),
  };
}

function markSessionLaunch() {
  sessionState = saveSessionState(app.getPath("userData"), {
    ...(sessionState || buildDefaultSessionState()),
    lastLaunchAt: new Date().toISOString(),
    lastExitClean: false,
    lastExitReason: "running",
  });
}

function markSessionExit(reason, { clean = true } = {}) {
  if (!app.isReady()) {
    return;
  }
  sessionState = saveSessionState(app.getPath("userData"), {
    ...(sessionState || buildDefaultSessionState()),
    lastExitAt: new Date().toISOString(),
    lastExitClean: clean,
    lastExitReason: String(reason || (clean ? "clean-exit" : "unclean-exit")),
    hudCrashCount: hudRuntime ? Number(hudRuntime.getPublicState().crashCount || 0) : Number(sessionState?.hudCrashCount || 0),
    hudLastError: hudRuntime ? hudRuntime.getPublicState().lastError || null : sessionState?.hudLastError || null,
  });
}

function getHudState() {
  return hudRuntime ? hudRuntime.getPublicState() : null;
}

function getSortedDisplays() {
  return [...screen.getAllDisplays()].sort((left, right) => {
    if (left.bounds.x !== right.bounds.x) {
      return left.bounds.x - right.bounds.x;
    }
    if (left.bounds.y !== right.bounds.y) {
      return left.bounds.y - right.bounds.y;
    }
    return left.id - right.id;
  });
}

function serializeDisplay(display, index) {
  return {
    id: display.id,
    ordinal: index + 1,
    label: display.primary ? "Primary Display" : `Display ${index + 1}`,
    primary: Boolean(display.primary),
    scaleFactor: display.scaleFactor,
    bounds: display.bounds,
    workArea: display.workArea,
    workAreaSize: display.workAreaSize,
  };
}

function listDisplays() {
  return getSortedDisplays().map((display, index) => serializeDisplay(display, index));
}

function getDisplayContext() {
  const displays = getSortedDisplays();
  if (!displays.length) {
    throw new Error("No displays are available for the overlay shell");
  }
  return {
    displays,
    primaryDisplayId: screen.getPrimaryDisplay().id,
  };
}

function getResolvedTargetDisplay(targetDisplayId = overlayPreferences?.targetDisplayId ?? null) {
  const { displays, primaryDisplayId } = getDisplayContext();
  return resolveTargetDisplay(displays, targetDisplayId, primaryDisplayId);
}

function getWindowOrPreferenceBounds(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  return safeWindow ? safeWindow.getBounds() : overlayPreferences?.windowBounds || null;
}

function getActiveDisplay(win = mainWindow) {
  const bounds = getWindowOrPreferenceBounds(win);
  if (bounds && Number.isFinite(bounds.x) && Number.isFinite(bounds.y)) {
    return screen.getDisplayMatching(bounds);
  }
  return getResolvedTargetDisplay();
}

function getDisplayInfo(win = mainWindow) {
  const displays = listDisplays();
  const primaryDisplay = displays.find((display) => display.primary) || displays[0];
  const targetDisplay = displays.find((display) => display.id === overlayPreferences?.targetDisplayId) || primaryDisplay;
  const activeDisplay = displays.find((display) => display.id === getActiveDisplay(win).id) || targetDisplay;

  return {
    primaryDisplayId: primaryDisplay.id,
    targetDisplayId: targetDisplay.id,
    activeDisplayId: activeDisplay.id,
    targetDisplay,
    activeDisplay,
    displays,
  };
}

function getLifecycleState() {
  const currentBuild = buildInfo || resolveBuildIdentity(app, __dirname);
  const login = getLaunchAtLoginState(app);
  const hudState = getHudState();
  const startupProfile = resolveStartupProfile(overlayPreferences, { recoveryNeeded: overlayRecovery.needed });
  const workspaceRoot = app.isReady() ? path.join(app.getPath("userData"), "workspace") : null;
  const session = {
    ...(sessionState || buildDefaultSessionState()),
    hudCrashCount: hudState ? Number(hudState.crashCount || 0) : Number(sessionState?.hudCrashCount || 0),
    hudLastError: hudState?.lastError || sessionState?.hudLastError || null,
  };
  return {
    packaged: currentBuild.packaged,
    distribution: currentBuild.distribution,
    version: currentBuild.version,
    revision: currentBuild.revision,
    buildIdentity: currentBuild.identity,
    launchAtLogin: login,
    startupProfile,
    update: buildUpdatePosture(
      updateState ||
        reconcileUpdateState(app.getPath("userData"), {
          buildIdentity: currentBuild.identity,
          preferencesSchemaVersion: PREFERENCES_VERSION,
          sessionSchemaVersion: SESSION_STATE_VERSION,
        }),
    ),
    portability: portabilityState || buildDefaultPortabilityState(),
    support: supportState || buildDefaultSupportState(),
    provenance: buildProvenance || {
      summary: "Build provenance is unavailable.",
      version: 1,
      buildIdentity: currentBuild.identity,
      distribution: currentBuild.distribution,
    },
    retainedState: app.isReady()
      ? describeRetainedState({
          userDataPath: app.getPath("userData"),
          workspaceRoot,
          launchAtLogin: login,
        })
      : describeRetainedState({
          userDataPath: ".",
          workspaceRoot: null,
          launchAtLogin: login,
        }),
    preflight: app.isReady()
      ? buildPreflightState({
          userDataPath: app.getPath("userData"),
          workspaceRoot,
          preferencesPath: getPreferencesPath(app.getPath("userData")),
          sessionStatePath: getSessionStatePath(app.getPath("userData")),
          updateStatePath: getUpdateStatePath(app.getPath("userData")),
          hudState,
          launchAtLogin: login,
          buildIdentity: currentBuild.identity,
          distribution: currentBuild.distribution,
        })
      : buildPreflightState({
          userDataPath: null,
          workspaceRoot: null,
          preferencesPath: null,
          sessionStatePath: null,
          updateStatePath: null,
          hudState,
          launchAtLogin: login,
          buildIdentity: currentBuild.identity,
          distribution: currentBuild.distribution,
        }),
    rollback: app.isReady()
      ? (backupState || summarizeBackups(app.getPath("userData")))
      : { count: 0, latest: null, summary: "Rollback snapshots unavailable until the shell is ready.", items: [] },
    decommission: buildDecommissionPlan({
      buildIdentity: currentBuild.identity,
      distribution: currentBuild.distribution,
      installRoot: app.isReady()
        ? (currentBuild.packaged ? path.dirname(process.execPath) : app.getAppPath())
        : null,
      execPath: app.isReady() ? process.execPath : null,
      userDataPath: app.isReady() ? app.getPath("userData") : null,
      workspaceRoot,
      retainedState: app.isReady()
        ? describeRetainedState({
            userDataPath: app.getPath("userData"),
            workspaceRoot,
            launchAtLogin: login,
          })
        : describeRetainedState({
            userDataPath: ".",
            workspaceRoot: null,
            launchAtLogin: login,
          }),
      rollbackState: app.isReady()
        ? (backupState || summarizeBackups(app.getPath("userData")))
        : { count: 0, latest: null, summary: "Rollback snapshots unavailable until the shell is ready.", items: [] },
      portabilityState: portabilityState || buildDefaultPortabilityState(),
      launchAtLogin: login,
    }),
    userDataPath: app.isReady() ? app.getPath("userData") : null,
    preferencesPath: app.isReady() ? getPreferencesPath(app.getPath("userData")) : null,
    sessionStatePath: app.isReady() ? getSessionStatePath(app.getPath("userData")) : null,
    updateStatePath: app.isReady() ? getUpdateStatePath(app.getPath("userData")) : null,
    supportStatePath: app.isReady() ? getSupportStatePath(app.getPath("userData")) : null,
    session,
  };
}

function getOverlayState(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  const bounds = getWindowOrPreferenceBounds(safeWindow);
  const displayInfo = app.isReady() ? getDisplayInfo(safeWindow) : null;
  const lifecycle = getLifecycleState();

  return {
    ignoreMouseEvents: overlayState.ignoreMouseEvents,
    alwaysOnTop: safeWindow ? safeWindow.isAlwaysOnTop() : overlayState.alwaysOnTop,
    visible: safeWindow ? safeWindow.isVisible() : false,
    hudUrl: HUD_URL,
    bounds,
    targetDisplayId: displayInfo?.targetDisplayId ?? overlayPreferences?.targetDisplayId ?? null,
    activeDisplayId: displayInfo?.activeDisplayId ?? null,
    preferencesPath: lifecycle.preferencesPath,
    launchOnStartup: lifecycle.launchAtLogin.enabled,
    recovery: overlayRecovery,
    hud: getHudState(),
    lifecycle,
    shortcuts: {
      toggleOverlay: OVERLAY_TOGGLE_SHORTCUT,
      toggleClickThrough: CLICK_THROUGH_TOGGLE_SHORTCUT,
    },
  };
}

function setLaunchAtLoginEnabled(enabled) {
  const nextState = setLaunchAtLogin(app, enabled);
  const safeWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
  if (app.isReady()) {
    overlayPreferences = persistOverlayPreferences(safeWindow, {
      launchOnStartup: nextState.enabled,
    });
  }
  log("Updated launch-at-login state", nextState);
  notifyOverlayState(safeWindow);
  return nextState;
}

function setStartupProfile(profileId) {
  const normalized = normalizeStartupProfile(profileId);
  const safeWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
  if (app.isReady()) {
    overlayPreferences = persistOverlayPreferences(safeWindow, {
      startupProfile: normalized,
    });
  }
  log("Updated startup profile", {
    requested: profileId,
    startupProfile: normalized,
  });
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function dismissUpdateNotice() {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }
  updateState = acknowledgeUpdateNotice(app.getPath("userData"), updateState || {}, new Date().toISOString());
  log("Acknowledged update notice", {
    build: updateState.currentBuild,
    notice: updateState.notice,
  });
  notifyOverlayState(mainWindow);
  return getOverlayState(mainWindow);
}

function refreshBackupState() {
  if (!app.isReady()) {
    backupState = { count: 0, latest: null, summary: "Rollback snapshots unavailable until the shell is ready.", items: [] };
    return backupState;
  }
  backupState = summarizeBackups(app.getPath("userData"));
  return backupState;
}

function createRollbackSnapshot(reason = "manual", note = "") {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }
  const manifest = createShellBackup(app.getPath("userData"), {
    reason,
    buildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    note,
  });
  refreshBackupState();
  log("Created rollback snapshot", {
    backupId: manifest.backupId,
    reason: manifest.reason,
  });
  notifyOverlayState(mainWindow);
  return getOverlayState(mainWindow);
}

function restoreLatestRollbackSnapshot(win = mainWindow) {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }

  const safeWindow = win && !win.isDestroyed() ? win : null;
  const latest = refreshBackupState().latest;
  if (!latest?.backupId) {
    throw new Error("No rollback snapshot is available");
  }

  createShellBackup(app.getPath("userData"), {
    reason: "pre_restore",
    buildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    note: `Before restoring rollback snapshot ${latest.backupId}`,
  });
  const manifest = restoreShellBackup(app.getPath("userData"), latest.backupId);
  overlayPreferences = loadPreferences(app.getPath("userData"), getDisplayContext().displays, getDisplayContext().primaryDisplayId);
  sessionState = loadSessionState(app.getPath("userData"));
  updateState = loadUpdateState(app.getPath("userData"), {
    buildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    preferencesSchemaVersion: PREFERENCES_VERSION,
    sessionSchemaVersion: SESSION_STATE_VERSION,
  });
  portabilityState = loadPortabilityState(app.getPath("userData"));
  supportState = loadSupportState(app.getPath("userData"));
  refreshBackupState();

  if (safeWindow) {
    safeWindow.setBounds(overlayPreferences.windowBounds);
    applyAlwaysOnTop(safeWindow, overlayPreferences.alwaysOnTop);
    applyIgnoreMouseEvents(safeWindow, overlayPreferences.ignoreMouseEvents);
  }

  log("Restored rollback snapshot", {
    backupId: manifest.backupId,
    reason: manifest.reason,
  });
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

async function exportShellState(win = mainWindow) {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }

  const safeWindow = win && !win.isDestroyed() ? win : null;
  const defaultName = `francis-overlay-state-${new Date().toISOString().slice(0, 10)}.json`;
  const selected = await dialog.showSaveDialog(safeWindow || undefined, {
    title: "Export Francis Overlay Shell State",
    defaultPath: path.join(app.getPath("documents"), defaultName),
    filters: [{ name: "JSON", extensions: ["json"] }],
  });

  if (selected.canceled || !selected.filePath) {
    return getOverlayState(safeWindow);
  }

  const payload = buildOverlayExportPayload({
    buildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    version: (buildInfo || resolveBuildIdentity(app, __dirname)).version,
    exportedAt: new Date().toISOString(),
    preferences: {
      ...(overlayPreferences || {}),
      windowBounds: getWindowOrPreferenceBounds(safeWindow),
      ignoreMouseEvents: overlayState.ignoreMouseEvents,
      alwaysOnTop: safeWindow ? safeWindow.isAlwaysOnTop() : overlayState.alwaysOnTop,
    },
  });

  fs.writeFileSync(selected.filePath, JSON.stringify(payload, null, 2), "utf8");
  portabilityState = savePortabilityState(app.getPath("userData"), {
    ...(portabilityState || buildDefaultPortabilityState()),
    lastExportAt: payload.exportedAt,
    lastExportPath: selected.filePath,
  });
  log("Exported overlay shell state", {
    filePath: selected.filePath,
    startupProfile: payload.shell.startupProfile,
  });
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

async function importShellState(win = mainWindow) {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }

  const safeWindow = win && !win.isDestroyed() ? win : null;
  const selected = await dialog.showOpenDialog(safeWindow || undefined, {
    title: "Import Francis Overlay Shell State",
    properties: ["openFile"],
    filters: [{ name: "JSON", extensions: ["json"] }],
  });

  if (selected.canceled || !Array.isArray(selected.filePaths) || !selected.filePaths[0]) {
    return getOverlayState(safeWindow);
  }

  const filePath = selected.filePaths[0];
  createShellBackup(app.getPath("userData"), {
    reason: "pre_import",
    buildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    note: `Before importing shell state from ${filePath}`,
  });
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const compatibility = assessPortablePayloadCompatibility(raw, {
    currentBuildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    currentVersion: (buildInfo || resolveBuildIdentity(app, __dirname)).version,
  });
  if (!compatibility.compatible) {
    portabilityState = savePortabilityState(app.getPath("userData"), {
      ...(portabilityState || buildDefaultPortabilityState()),
      lastImportAt: new Date().toISOString(),
      lastImportPath: filePath,
      lastImportStatus: compatibility.status,
      lastImportMessage: compatibility.summary,
    });
    log("Blocked overlay shell import", {
      filePath,
      summary: compatibility.summary,
    });
    notifyOverlayState(safeWindow);
    throw new Error(compatibility.summary);
  }
  const imported = extractPortablePreferences(raw, {
    currentBuildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    currentVersion: (buildInfo || resolveBuildIdentity(app, __dirname)).version,
  });
  overlayPreferences = persistOverlayPreferences(safeWindow, imported);

  if (safeWindow) {
    safeWindow.setBounds(overlayPreferences.windowBounds);
    applyAlwaysOnTop(safeWindow, overlayPreferences.alwaysOnTop);
    applyIgnoreMouseEvents(safeWindow, overlayPreferences.ignoreMouseEvents);
  }

  portabilityState = savePortabilityState(app.getPath("userData"), {
    ...(portabilityState || buildDefaultPortabilityState()),
    lastImportAt: new Date().toISOString(),
    lastImportPath: filePath,
    lastImportStatus: "applied",
    lastImportMessage: `${compatibility.summary} Imported safe shell preferences only. Launch-at-login and authority state remain local.`,
  });
  log("Imported overlay shell state", {
    filePath,
    startupProfile: overlayPreferences.startupProfile,
  });
  refreshBackupState();
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function resetRetainedShellState(win = mainWindow) {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }

  const safeWindow = win && !win.isDestroyed() ? win : null;
  const targetDisplay = getResolvedTargetDisplay(screen.getPrimaryDisplay().id);
  createShellBackup(app.getPath("userData"), {
    reason: "pre_reset",
    buildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    note: "Before resetting retained shell state",
  });

  try {
    setLaunchAtLogin(app, false);
  } catch (error) {
    log("Reset shell state could not clear launch-at-login", error instanceof Error ? error.message : String(error));
  }

  overlayPreferences = savePreferences(
    app.getPath("userData"),
    buildDefaultPreferences(targetDisplay),
    getDisplayContext().displays,
    getDisplayContext().primaryDisplayId,
  );
  sessionState = saveSessionState(app.getPath("userData"), buildDefaultSessionState());
  updateState = reconcileUpdateState(app.getPath("userData"), {
    buildIdentity: (buildInfo || resolveBuildIdentity(app, __dirname)).identity,
    preferencesSchemaVersion: PREFERENCES_VERSION,
    sessionSchemaVersion: SESSION_STATE_VERSION,
  });
  portabilityState = savePortabilityState(app.getPath("userData"), buildDefaultPortabilityState());
  supportState = saveSupportState(app.getPath("userData"), buildDefaultSupportState());
  refreshBackupState();
  setOverlayRecovery({ needed: false, status: "nominal", message: "", lastExitReason: "" });

  if (safeWindow) {
    safeWindow.setBounds(overlayPreferences.windowBounds);
    applyAlwaysOnTop(safeWindow, overlayPreferences.alwaysOnTop);
    applyIgnoreMouseEvents(safeWindow, overlayPreferences.ignoreMouseEvents);
  }

  log("Reset retained shell state", {
    targetDisplayId: overlayPreferences.targetDisplayId,
  });
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

async function exportSupportBundle(win = mainWindow) {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }

  const safeWindow = win && !win.isDestroyed() ? win : null;
  const timestamp = new Date().toISOString().replaceAll(":", "-");
  const selected = await dialog.showSaveDialog(safeWindow || undefined, {
    title: "Export Francis Overlay Support Bundle",
    defaultPath: path.join(app.getPath("documents"), `francis-overlay-support-${timestamp}.json`),
    filters: [{ name: "JSON", extensions: ["json"] }],
  });

  if (selected.canceled || !selected.filePath) {
    return getOverlayState(safeWindow);
  }

  const overlaySnapshot = getOverlayState(safeWindow);
  const payload = buildSupportBundle({
    generatedAt: new Date().toISOString(),
    hudUrl: HUD_URL,
    overlay: overlaySnapshot,
    lifecycle: overlaySnapshot.lifecycle,
    hud: overlaySnapshot.hud,
    recovery: overlaySnapshot.recovery,
    display: overlaySnapshot.displayInfo,
  });

  fs.writeFileSync(selected.filePath, JSON.stringify(payload, null, 2), "utf8");
  supportState = saveSupportState(app.getPath("userData"), {
    ...(supportState || buildDefaultSupportState()),
    lastBundleAt: payload.generatedAt,
    lastBundlePath: selected.filePath,
  });
  log("Exported support bundle", {
    filePath: selected.filePath,
    summary: payload.summary,
  });
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function notifyOverlayState(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  if (safeWindow) {
    safeWindow.webContents.send("overlay:state-changed", getOverlayState(safeWindow));
  }
  updateTray();
}

function buildTrayIcon() {
  const iconPath = path.join(__dirname, "assets", "francis-overlay.png");
  return nativeImage.createFromPath(iconPath);
}

function trayLabelForState() {
  const inputMode = overlayState.ignoreMouseEvents ? "click-through" : "interactive";
  const hudMode = getHudState()?.mode || "offline";
  return `Francis Overlay | ${inputMode} | HUD ${hudMode}`;
}

function updateTray() {
  if (!tray) {
    return;
  }
  const visible = mainWindow && !mainWindow.isDestroyed() ? mainWindow.isVisible() : false;
  const overlaySnapshot = getOverlayState(mainWindow);
  const loginState = overlaySnapshot.lifecycle?.launchAtLogin || getLaunchAtLoginState(app);
  tray.setToolTip(trayLabelForState());
  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: visible ? "Hide Overlay" : "Show Overlay",
        click: () => toggleOverlayVisibility(),
      },
      {
        label: overlayState.ignoreMouseEvents ? "Switch To Interactive" : "Enable Click-through",
        click: () => toggleClickThrough(),
      },
      {
        label: overlayState.alwaysOnTop ? "Release Topmost" : "Pin Topmost",
        click: () => applyAlwaysOnTop(requireWindow(), !overlayState.alwaysOnTop),
      },
      {
        label: loginState?.enabled ? "Disable Start At Login" : "Enable Start At Login",
        enabled: Boolean(loginState?.available),
        click: () => {
          try {
            setLaunchAtLoginEnabled(!Boolean(loginState?.enabled));
          } catch (error) {
            log("Tray launch-at-login update failed", error instanceof Error ? error.message : String(error));
          }
        },
      },
      {
        label: "Startup Profile",
        submenu: getOverlayState(mainWindow).lifecycle.startupProfile.options.map((profile) => ({
          label: profile.label,
          type: "radio",
          checked: overlayPreferences?.startupProfile === profile.id,
          click: () => {
            try {
              setStartupProfile(profile.id);
            } catch (error) {
              log("Tray startup profile update failed", error instanceof Error ? error.message : String(error));
            }
          },
        })),
      },
      {
        label: overlaySnapshot.lifecycle?.update?.pendingNotice
          ? `Acknowledge Update (${overlaySnapshot.lifecycle.update.currentBuild})`
          : `Build ${overlaySnapshot.lifecycle?.update?.currentBuild || overlaySnapshot.lifecycle?.buildIdentity || "unknown"}`,
        enabled: Boolean(overlaySnapshot.lifecycle?.update?.pendingNotice),
        click: () => {
          try {
            dismissUpdateNotice();
          } catch (error) {
            log("Tray update notice acknowledge failed", error instanceof Error ? error.message : String(error));
          }
        },
      },
      { type: "separator" },
      {
        label: "Restart HUD",
        click: () => {
          restartHudAndRefreshWindow(requireWindow()).catch((error) => {
            log("Tray HUD restart failed", error instanceof Error ? error.message : String(error));
          });
        },
      },
      {
        label: "Export Shell State",
        click: () => {
          exportShellState(requireWindow()).catch((error) => {
            log("Tray shell export failed", error instanceof Error ? error.message : String(error));
          });
        },
      },
      {
        label: "Export Support Bundle",
        click: () => {
          exportSupportBundle(requireWindow()).catch((error) => {
            log("Tray support bundle export failed", error instanceof Error ? error.message : String(error));
          });
        },
      },
      {
        label: "Import Shell State",
        click: () => {
          importShellState(requireWindow()).catch((error) => {
            log("Tray shell import failed", error instanceof Error ? error.message : String(error));
          });
        },
      },
      {
        label: "Create Rollback Snapshot",
        click: () => {
          try {
            createRollbackSnapshot("manual", "Created from tray control surface.");
          } catch (error) {
            log("Tray rollback snapshot failed", error instanceof Error ? error.message : String(error));
          }
        },
      },
      {
        label: "Restore Latest Snapshot",
        enabled: Boolean(overlaySnapshot.lifecycle?.rollback?.latest?.backupId),
        click: () => {
          try {
            restoreLatestRollbackSnapshot(requireWindow());
          } catch (error) {
            log("Tray rollback restore failed", error instanceof Error ? error.message : String(error));
          }
        },
      },
      { type: "separator" },
      {
        label: overlaySnapshot.recovery?.needed ? `Recovery: ${overlaySnapshot.recovery.status}` : "Recovery Nominal",
        enabled: false,
      },
      {
        label: `HUD: ${overlaySnapshot.hud?.mode || "offline"}`,
        enabled: false,
      },
      { type: "separator" },
      {
        label: "Quit Francis Overlay",
        click: () => app.quit(),
      },
    ]),
  );
}

function createTray() {
  if (tray) {
    return tray;
  }
  tray = new Tray(buildTrayIcon());
  tray.on("double-click", () => toggleOverlayVisibility());
  updateTray();
  return tray;
}

function buildCenteredBoundsForDisplay(bounds, display) {
  const normalized = normalizeBounds(bounds, display.workArea);
  return {
    x: Math.round(display.workArea.x + Math.max(0, display.workArea.width - normalized.width) / 2),
    y: Math.round(display.workArea.y + Math.max(0, display.workArea.height - normalized.height) / 2),
    width: normalized.width,
    height: normalized.height,
  };
}

function persistOverlayPreferences(win = mainWindow, overrides = {}) {
  const { displays, primaryDisplayId } = getDisplayContext();
  const fallbackDisplay = resolveTargetDisplay(
    displays,
    overrides.targetDisplayId ?? overlayPreferences?.targetDisplayId,
    primaryDisplayId,
  );
  const launchAtLogin = getLaunchAtLoginState(app);
  const safeWindow = win && !win.isDestroyed() ? win : null;
  const bounds =
    overrides.windowBounds ||
    getWindowOrPreferenceBounds(safeWindow) ||
    buildDefaultPreferences(fallbackDisplay).windowBounds;
  const activeDisplay = screen.getDisplayMatching(bounds);

  overlayPreferences = savePreferences(
    app.getPath("userData"),
    {
      ...(overlayPreferences || buildDefaultPreferences(fallbackDisplay)),
      ...overrides,
      targetDisplayId: overrides.targetDisplayId ?? activeDisplay.id ?? fallbackDisplay.id,
      alwaysOnTop: overrides.alwaysOnTop ?? (safeWindow ? safeWindow.isAlwaysOnTop() : overlayState.alwaysOnTop),
      ignoreMouseEvents: overrides.ignoreMouseEvents ?? overlayState.ignoreMouseEvents,
      launchOnStartup: overrides.launchOnStartup ?? launchAtLogin.enabled,
      startupProfile: overrides.startupProfile ?? overlayPreferences?.startupProfile,
      windowBounds: bounds,
    },
    displays,
    primaryDisplayId,
  );

  return overlayPreferences;
}

function schedulePreferenceSave(win = mainWindow, { immediate = false } = {}) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  if (!safeWindow || safeWindow.isMinimized()) {
    return;
  }

  const persist = () => {
    overlayPreferences = persistOverlayPreferences(safeWindow);
    log("Saved overlay preferences", overlayPreferences);
    notifyOverlayState(safeWindow);
  };

  if (preferenceSaveTimer) {
    clearTimeout(preferenceSaveTimer);
    preferenceSaveTimer = null;
  }

  if (immediate) {
    persist();
    return;
  }

  preferenceSaveTimer = setTimeout(() => {
    preferenceSaveTimer = null;
    persist();
  }, 180);
}

function resetOverlayPreferences(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  if (!safeWindow) {
    throw new Error("Overlay window is not available");
  }

  const primaryDisplay = getResolvedTargetDisplay(screen.getPrimaryDisplay().id);
  overlayPreferences = buildDefaultPreferences(primaryDisplay);
  safeWindow.setBounds(overlayPreferences.windowBounds);
  applyAlwaysOnTop(safeWindow, overlayPreferences.alwaysOnTop);
  applyIgnoreMouseEvents(safeWindow, overlayPreferences.ignoreMouseEvents);
  overlayPreferences = persistOverlayPreferences(safeWindow, overlayPreferences);
  log("Reset overlay preferences", overlayPreferences);
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function moveOverlayToDisplay(displayId, win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  if (!safeWindow) {
    throw new Error("Overlay window is not available");
  }

  const targetDisplay = getResolvedTargetDisplay(displayId);
  const nextBounds = buildCenteredBoundsForDisplay(getWindowOrPreferenceBounds(safeWindow), targetDisplay);

  safeWindow.setBounds(nextBounds);
  overlayPreferences = persistOverlayPreferences(safeWindow, {
    targetDisplayId: targetDisplay.id,
    windowBounds: nextBounds,
  });
  log("Moved overlay to target display", {
    targetDisplayId: targetDisplay.id,
    bounds: nextBounds,
  });
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function sameBounds(left, right) {
  if (!left || !right) {
    return false;
  }
  return left.x === right.x && left.y === right.y && left.width === right.width && left.height === right.height;
}

function reconcileDisplayTopology(reason) {
  if (!app.isReady()) {
    return;
  }

  try {
    const safeWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
    overlayPreferences = persistOverlayPreferences(safeWindow, {
      windowBounds: getWindowOrPreferenceBounds(safeWindow),
    });

    if (safeWindow && !sameBounds(safeWindow.getBounds(), overlayPreferences.windowBounds)) {
      safeWindow.setBounds(overlayPreferences.windowBounds);
    }

    log("Reconciled display topology", {
      reason,
      targetDisplayId: overlayPreferences.targetDisplayId,
      bounds: overlayPreferences.windowBounds,
    });
    notifyOverlayState(safeWindow);
  } catch (error) {
    log("Display topology reconciliation failed", error instanceof Error ? error.message : String(error));
  }
}

function buildFallbackHtml(errorText) {
  const hudState = getHudState();
  const escapedMessage = String(errorText || "Unknown load failure")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  const escapedTarget = HUD_URL.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  const escapedHudMode = String(hudState?.mode || "unknown")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  const escapedHudError = String(hudState?.lastError || "No managed HUD error captured.")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Francis Overlay Unavailable</title>
    <style>
      :root {
        color-scheme: dark;
        font-family: "Segoe UI", system-ui, sans-serif;
      }
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background:
          radial-gradient(circle at top, rgba(88, 127, 166, 0.35), transparent 48%),
          rgba(4, 12, 24, 0.92);
        color: #e6eef8;
      }
      main {
        width: min(680px, calc(100vw - 48px));
        padding: 28px 32px;
        border-radius: 20px;
        background: rgba(6, 17, 34, 0.82);
        border: 1px solid rgba(152, 188, 221, 0.24);
        box-shadow: 0 28px 80px rgba(0, 0, 0, 0.42);
      }
      h1 {
        margin: 0 0 12px;
        font-size: 30px;
      }
      p {
        margin: 0 0 12px;
        line-height: 1.6;
        color: rgba(230, 238, 248, 0.84);
      }
      code {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 999px;
        background: rgba(152, 188, 221, 0.14);
        color: #b9d9ff;
      }
      pre {
        margin: 18px 0 0;
        padding: 16px;
        border-radius: 14px;
        background: rgba(0, 0, 0, 0.24);
        color: #ffd8c2;
        white-space: pre-wrap;
      }
      button {
        margin-top: 16px;
        padding: 10px 14px;
        border: 0;
        border-radius: 999px;
        background: #9ed2ff;
        color: #06111f;
        font: inherit;
        cursor: pointer;
      }
      small {
        display: block;
        margin-top: 10px;
        color: rgba(230, 238, 248, 0.7);
      }
    </style>
  </head>
  <body>
    <main>
      <h1>Francis HUD server is not reachable.</h1>
      <p>The desktop overlay shell started correctly, but the HUD at <code>${escapedTarget}</code> did not respond.</p>
      <p>Managed HUD state: <code>${escapedHudMode}</code></p>
      <p>If this shell owns the HUD runtime, you can retry startup directly from here.</p>
      <button type="button" onclick="retryHudStart()">Retry Managed HUD Startup</button>
      <small id="retry-status">No retry attempted yet.</small>
      <pre>${escapedMessage}\n\n${escapedHudError}</pre>
    </main>
    <script>
      async function retryHudStart() {
        const status = document.getElementById('retry-status');
        status.textContent = 'Retrying HUD startup...';
        try {
          if (!window.FrancisDesktop || typeof window.FrancisDesktop.restartHud !== 'function') {
            throw new Error('Desktop bridge is unavailable in this fallback view.');
          }
          await window.FrancisDesktop.restartHud();
          status.textContent = 'Managed HUD restart completed. Reloading overlay...';
          window.location.reload();
        } catch (error) {
          status.textContent = error && error.message ? error.message : String(error);
        }
      }
    </script>
  </body>
</html>`;
}

function fallbackUrl(errorText) {
  return `data:text/html;charset=utf-8,${encodeURIComponent(buildFallbackHtml(errorText))}`;
}

function applyAlwaysOnTop(win, enabled) {
  if (!win || win.isDestroyed()) {
    return overlayState.alwaysOnTop;
  }
  // Use a high always-on-top level so the overlay behaves like an operator layer, not a normal app window.
  win.setAlwaysOnTop(Boolean(enabled), enabled ? "screen-saver" : "normal");
  overlayState.alwaysOnTop = win.isAlwaysOnTop();
  schedulePreferenceSave(win);
  notifyOverlayState(win);
  return overlayState.alwaysOnTop;
}

function applyIgnoreMouseEvents(win, ignore) {
  if (!win || win.isDestroyed()) {
    return overlayState.ignoreMouseEvents;
  }
  overlayState.ignoreMouseEvents = Boolean(ignore);
  // Forward mouse-move events while click-through is enabled so the overlay can still react visually.
  win.setIgnoreMouseEvents(overlayState.ignoreMouseEvents, overlayState.ignoreMouseEvents ? { forward: true } : undefined);
  schedulePreferenceSave(win);
  notifyOverlayState(win);
  return overlayState.ignoreMouseEvents;
}

async function showFallbackPage(win, errorText) {
  if (!win || win.isDestroyed()) {
    return;
  }
  log("Loading fallback error page", errorText);
  await win.loadURL(fallbackUrl(errorText));
}

function clearHudRecovery() {
  if (hudRecoveryTimer) {
    clearTimeout(hudRecoveryTimer);
    hudRecoveryTimer = null;
  }
  hudRecoveryAttempts = 0;
  setOverlayRecovery({ needed: false, status: "nominal", message: "", lastExitReason: "" });
}

function scheduleHudRecovery(reason) {
  if (!hudRuntime || quitAfterHudShutdown) {
    return;
  }
  if (hudRecoveryTimer || hudRecoveryAttempts >= 1) {
    return;
  }
  hudRecoveryAttempts += 1;
  setOverlayRecovery({
    needed: true,
    status: "recovering",
    message: "Managed HUD exited unexpectedly. Restarting the local runtime.",
    lastExitReason: reason,
  });
  notifyOverlayState(mainWindow);
  hudRecoveryTimer = setTimeout(async () => {
    hudRecoveryTimer = null;
    try {
      await restartHudAndRefreshWindow(mainWindow);
      clearHudRecovery();
      notifyOverlayState(mainWindow);
    } catch (error) {
      setOverlayRecovery({
        needed: true,
        status: "failed",
        message: error instanceof Error ? error.message : String(error),
        lastExitReason: reason,
      });
      notifyOverlayState(mainWindow);
    }
  }, 1500);
}

async function loadHud(win) {
  if (!win || win.isDestroyed()) {
    return;
  }

  let handledFailure = false;

  const handleLoadFailure = async (_event, code, description, validatedUrl, isMainFrame) => {
    if (!isMainFrame || handledFailure) {
      return;
    }
    if (!String(validatedUrl || "").startsWith(HUD_URL)) {
      return;
    }
    handledFailure = true;
    await showFallbackPage(win, `${description} (${code})`);
  };

  win.webContents.once("did-fail-load", handleLoadFailure);
  win.webContents.once("did-finish-load", () => {
    const currentUrl = win.webContents.getURL();
    if (currentUrl.startsWith("data:text/html")) {
      log("Overlay loaded fallback content");
      notifyOverlayState(win);
      return;
    }
    clearHudRecovery();
    log("Overlay loaded HUD", currentUrl);
    notifyOverlayState(win);
  });

  try {
    log("Loading HUD", HUD_URL);
    await win.loadURL(HUD_URL);
  } catch (error) {
    if (!handledFailure) {
      handledFailure = true;
      await showFallbackPage(win, error instanceof Error ? error.message : String(error));
    }
  }
}

function createMainWindow() {
  const { displays, primaryDisplayId } = getDisplayContext();
  overlayPreferences = loadPreferences(app.getPath("userData"), displays, primaryDisplayId);
  const preloadPath = path.join(__dirname, "preload.js");
  const targetDisplay = resolveTargetDisplay(displays, overlayPreferences.targetDisplayId, primaryDisplayId);
  const startupProfile = resolveStartupProfile(overlayPreferences, { recoveryNeeded: overlayRecovery.needed });

  log("Creating overlay window", {
    hudUrl: HUD_URL,
    targetDisplayId: targetDisplay.id,
    bounds: overlayPreferences.windowBounds,
    preferences: overlayPreferences,
    startupProfile,
    hud: getHudState(),
  });

  const win = new BrowserWindow({
    x: overlayPreferences.windowBounds.x,
    y: overlayPreferences.windowBounds.y,
    width: overlayPreferences.windowBounds.width,
    height: overlayPreferences.windowBounds.height,
    show: false,
    frame: false, // Remove native chrome so the window reads as an overlay instead of a desktop app.
    transparent: true, // Let the HUD alpha blend with the Windows desktop.
    backgroundColor: "#00000000", // Explicit zero-alpha background keeps transparency stable on Windows.
    alwaysOnTop: true, // The overlay must stay above work surfaces to remain visible as an operator layer.
    resizable: true, // Keep manual sizing available while the shell is still being tuned.
    fullscreenable: false, // The overlay should size to the desktop work area, not enter exclusive fullscreen.
    skipTaskbar: true, // Hide taskbar presence so the overlay behaves like a layer, not a launched app destination.
    hasShadow: false, // Native shadows create visible edges around transparent windows.
    autoHideMenuBar: true,
    title: "Francis Overlay",
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true, // Keep the page isolated and expose only the preload bridge.
      nodeIntegration: false, // The HUD is loaded from localhost and should not get Node access.
      spellcheck: false,
    },
  });

  win.setMenuBarVisibility(false);
  applyAlwaysOnTop(win, overlayPreferences.alwaysOnTop);
  applyIgnoreMouseEvents(win, startupProfile.ignoreMouseEvents);

  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event, targetUrl) => {
    if (!String(targetUrl || "").startsWith(HUD_URL)) {
      log("Blocked navigation away from HUD origin", targetUrl);
      event.preventDefault();
    }
  });
  win.webContents.on("render-process-gone", (_event, details) => {
    const reason = `renderer-${details.reason || "gone"}`;
    log("Overlay renderer process exited", details);
    setOverlayRecovery({
      needed: true,
      status: "renderer_crash",
      message: `Overlay renderer exited: ${details.reason || "unknown"}. Reloading the HUD shell.`,
      lastExitReason: reason,
    });
    markSessionExit(reason, { clean: false });
    loadHud(win).catch((error) => {
      log("Renderer recovery load failed", error instanceof Error ? error.message : String(error));
    });
    notifyOverlayState(win);
  });
  win.on("unresponsive", () => {
    setOverlayRecovery({
      needed: true,
      status: "unresponsive",
      message: "Overlay renderer became unresponsive. Reload the HUD if this persists.",
      lastExitReason: "renderer-unresponsive",
    });
    notifyOverlayState(win);
  });

  win.once("ready-to-show", () => {
    if (startupProfile.visible) {
      log("Overlay ready; showing window", {
        startupProfile: startupProfile.effective,
      });
      win.showInactive();
      return;
    }
    log("Overlay ready; startup profile keeps the window hidden until summoned", {
      startupProfile: startupProfile.effective,
    });
    notifyOverlayState(win);
  });

  win.on("move", () => schedulePreferenceSave(win));
  win.on("resize", () => schedulePreferenceSave(win));
  win.on("show", () => notifyOverlayState(win));
  win.on("hide", () => notifyOverlayState(win));
  win.on("minimize", () => notifyOverlayState(win));
  win.on("restore", () => notifyOverlayState(win));

  win.on("closed", () => {
    schedulePreferenceSave(win, { immediate: true });
    log("Overlay window closed");
    if (mainWindow === win) {
      mainWindow = null;
    }
  });

  loadHud(win).catch((error) => {
    log("Unexpected HUD load error", error instanceof Error ? error.message : String(error));
  });

  return win;
}

function requireWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    throw new Error("Overlay window is not available");
  }
  return mainWindow;
}

async function openLifecyclePath(target) {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }

  const lifecycle = getLifecycleState();
  const pathMap = {
    install_root: lifecycle.decommission?.installRoot || null,
    user_data: lifecycle.decommission?.userDataPath || null,
    workspace_root: lifecycle.decommission?.workspaceRoot || null,
  };
  const targetPath = pathMap[String(target || "")] || null;
  if (!targetPath) {
    throw new Error("Requested lifecycle path is unavailable");
  }

  const result = await shell.openPath(targetPath);
  if (result) {
    throw new Error(result);
  }

  log("Opened lifecycle path", {
    target,
    path: targetPath,
  });
  return {
    target: String(target),
    path: targetPath,
  };
}

async function restartHudAndRefreshWindow(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  if (!hudRuntime) {
    throw new Error("HUD runtime is not available");
  }

  await hudRuntime.restart();
  if (safeWindow) {
    await loadHud(safeWindow);
    notifyOverlayState(safeWindow);
  }
  return getOverlayState(safeWindow);
}

function registerIpc() {
  if (ipcRegistered) {
    return;
  }
  ipcRegistered = true;

  ipcMain.handle("overlay:set-ignore-mouse-events", (_event, ignore) => {
    const win = requireWindow();
    const value = applyIgnoreMouseEvents(win, ignore);
    log("Updated click-through state", value);
    return value;
  });

  ipcMain.handle("overlay:set-always-on-top", (_event, enabled) => {
    const win = requireWindow();
    const value = applyAlwaysOnTop(win, enabled);
    log("Updated always-on-top state", value);
    return value;
  });

  ipcMain.handle("overlay:set-launch-at-login", (_event, enabled) => setLaunchAtLoginEnabled(enabled));
  ipcMain.handle("overlay:set-launch-on-startup", (_event, enabled) => setLaunchAtLoginEnabled(enabled));
  ipcMain.handle("overlay:set-startup-profile", (_event, profileId) => setStartupProfile(profileId));
  ipcMain.handle("overlay:acknowledge-update-notice", () => dismissUpdateNotice());
  ipcMain.handle("overlay:export-shell-state", () => exportShellState(requireWindow()));
  ipcMain.handle("overlay:import-shell-state", () => importShellState(requireWindow()));
  ipcMain.handle("overlay:reset-shell-state", () => resetRetainedShellState(requireWindow()));
  ipcMain.handle("overlay:create-rollback-snapshot", () => createRollbackSnapshot("manual", "Created from the desktop shell."));
  ipcMain.handle("overlay:restore-latest-rollback", () => restoreLatestRollbackSnapshot(requireWindow()));
  ipcMain.handle("overlay:export-support-bundle", () => exportSupportBundle(requireWindow()));
  ipcMain.handle("overlay:set-target-display", (_event, displayId) => moveOverlayToDisplay(displayId, requireWindow()));
  ipcMain.handle("overlay:reset-layout", () => resetOverlayPreferences(requireWindow()));
  ipcMain.handle("overlay:get-state", () => getOverlayState(requireWindow()));
  ipcMain.handle("overlay:get-display-info", () => getDisplayInfo(requireWindow()));
  ipcMain.handle("overlay:restart-hud", () => restartHudAndRefreshWindow(requireWindow()));
  ipcMain.handle("overlay:open-path", (_event, target) => openLifecyclePath(target));

  ipcMain.handle("overlay:minimize", () => {
    const win = requireWindow();
    win.minimize();
    notifyOverlayState(win);
    return true;
  });

  ipcMain.handle("overlay:hide", () => {
    const win = requireWindow();
    win.hide();
    notifyOverlayState(win);
    return true;
  });

  ipcMain.handle("overlay:show", () => {
    const win = requireWindow();
    if (win.isMinimized()) {
      win.restore();
    }
    win.showInactive();
    notifyOverlayState(win);
    return true;
  });

  ipcMain.handle("overlay:toggle-devtools", () => {
    const win = requireWindow();
    if (win.webContents.isDevToolsOpened()) {
      win.webContents.closeDevTools();
      return false;
    }
    win.webContents.openDevTools({ mode: "detach" });
    return true;
  });
}

function toggleOverlayVisibility() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }
  if (mainWindow.isVisible()) {
    log("Hiding overlay via global shortcut");
    mainWindow.hide();
    notifyOverlayState(mainWindow);
    return;
  }
  log("Showing overlay via global shortcut");
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  mainWindow.showInactive();
  notifyOverlayState(mainWindow);
}

function toggleClickThrough() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }
  const nextValue = !overlayState.ignoreMouseEvents;
  const applied = applyIgnoreMouseEvents(mainWindow, nextValue);
  log("Toggled click-through via global shortcut", applied);
}

function registerShortcuts() {
  const overlayRegistered = globalShortcut.register(OVERLAY_TOGGLE_SHORTCUT, toggleOverlayVisibility);
  if (!overlayRegistered) {
    log(`Failed to register global shortcut: ${OVERLAY_TOGGLE_SHORTCUT}`);
  } else {
    log(`Registered global shortcut: ${OVERLAY_TOGGLE_SHORTCUT}`);
  }

  const clickThroughRegistered = globalShortcut.register(CLICK_THROUGH_TOGGLE_SHORTCUT, toggleClickThrough);
  if (!clickThroughRegistered) {
    log(`Failed to register global shortcut: ${CLICK_THROUGH_TOGGLE_SHORTCUT}`);
    return;
  }
  log(`Registered global shortcut: ${CLICK_THROUGH_TOGGLE_SHORTCUT}`);
}

function registerDisplayListeners() {
  screen.on("display-added", (_event, display) => {
    reconcileDisplayTopology(`display-added:${display.id}`);
  });
  screen.on("display-removed", (_event, display) => {
    reconcileDisplayTopology(`display-removed:${display.id}`);
  });
  screen.on("display-metrics-changed", (_event, display, changedMetrics) => {
    reconcileDisplayTopology(`display-metrics-changed:${display.id}:${changedMetrics.join(",")}`);
  });
}

async function initializeHudRuntime() {
  hudRuntime = createHudRuntimeManager({
    appDir: __dirname,
    resourcesPath: process.resourcesPath,
    userDataPath: app.getPath("userData"),
    isPackaged: app.isPackaged,
    hudUrl: HUD_URL,
    log,
    onStateChanged: (publicState) => {
      if (publicState?.restartSuggested) {
        scheduleHudRecovery(`hud-${publicState.mode || "crashed"}`);
      } else if (publicState?.ready) {
        clearHudRecovery();
      }
      notifyOverlayState(mainWindow);
    },
  });

  try {
    const hudState = await hudRuntime.ensureReady();
    log("HUD runtime ready", hudState);
  } catch (error) {
    log("HUD runtime initialization did not produce a ready server", error instanceof Error ? error.message : String(error));
  }
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.whenReady().then(async () => {
    buildInfo = resolveBuildIdentity(app, __dirname);
    buildProvenance =
      loadGeneratedProvenance(path.resolve(__dirname, "..")) ||
      buildRuntimeProvenance({
        appLike: app,
        appDir: __dirname,
      });
    sessionState = loadSessionState(app.getPath("userData"));
    portabilityState = loadPortabilityState(app.getPath("userData"));
    supportState = loadSupportState(app.getPath("userData"));
    const priorUpdateState = loadUpdateState(app.getPath("userData"), {
      buildIdentity: buildInfo.identity,
      preferencesSchemaVersion: PREFERENCES_VERSION,
      sessionSchemaVersion: SESSION_STATE_VERSION,
    });
    if (priorUpdateState.currentBuild && priorUpdateState.currentBuild !== buildInfo.identity) {
      const manifest = createShellBackup(app.getPath("userData"), {
        reason: "pre_update",
        buildIdentity: priorUpdateState.currentBuild,
        note: `Before loading build ${buildInfo.identity}`,
      });
      priorUpdateState.lastBackupId = manifest.backupId;
      priorUpdateState.lastBackupAt = manifest.createdAt;
      saveUpdateState(app.getPath("userData"), priorUpdateState, {
        buildIdentity: buildInfo.identity,
        preferencesSchemaVersion: PREFERENCES_VERSION,
        sessionSchemaVersion: SESSION_STATE_VERSION,
      });
    }
    updateState = reconcileUpdateState(app.getPath("userData"), {
      buildIdentity: buildInfo.identity,
      preferencesSchemaVersion: PREFERENCES_VERSION,
      sessionSchemaVersion: SESSION_STATE_VERSION,
    });
    refreshBackupState();
    if (sessionState.lastExitClean === false) {
      setOverlayRecovery({
        needed: true,
        status: "unclean_exit",
        message: "The previous overlay session did not exit cleanly. Francis restored the shell state and is reloading continuity.",
        lastExitReason: sessionState.lastExitReason || "unclean-exit",
      });
    }
    markSessionLaunch();
    registerIpc();
    registerDisplayListeners();
    await initializeHudRuntime();
    mainWindow = createMainWindow();
    createTray();
    registerShortcuts();
  });

  app.on("second-instance", () => {
    if (!mainWindow || mainWindow.isDestroyed()) {
      mainWindow = createMainWindow();
      return;
    }
    toggleOverlayVisibility();
  });
}

app.on("activate", () => {
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = createMainWindow();
    return;
  }
  if (!mainWindow.isVisible()) {
    mainWindow.showInactive();
  }
});

app.on("before-quit", (event) => {
  if (quitAfterHudShutdown) {
    return;
  }
  markSessionExit("clean-exit", { clean: true });
  if (!hudRuntime || !getHudState()?.managed) {
    return;
  }
  event.preventDefault();
  quitAfterHudShutdown = true;
  hudRuntime
    .shutdown({ force: true })
    .catch((error) => {
      log("Managed HUD shutdown failed", error instanceof Error ? error.message : String(error));
    })
    .finally(() => {
      app.quit();
    });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("will-quit", () => {
  if (preferenceSaveTimer) {
    clearTimeout(preferenceSaveTimer);
    preferenceSaveTimer = null;
  }
  if (hudRecoveryTimer) {
    clearTimeout(hudRecoveryTimer);
    hudRecoveryTimer = null;
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    schedulePreferenceSave(mainWindow, { immediate: true });
  }
  if (tray) {
    tray.destroy();
    tray = null;
  }
  log("Unregistering global shortcuts");
  globalShortcut.unregisterAll();
});
