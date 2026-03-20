const path = require("node:path");
const fs = require("node:fs");
const { app, BrowserWindow, Menu, Tray, desktopCapturer, dialog, globalShortcut, ipcMain, nativeImage, nativeTheme, powerMonitor, screen, shell, systemPreferences } = require("electron");
const { createHudRuntimeManager, isHudReachable } = require("./hud-runtime");
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
  buildAccessibilityState,
  normalizeContrastMode,
  normalizeDensityMode,
  normalizeMotionMode,
} = require("./accessibility");
const {
  SESSION_STATE_VERSION,
  buildDefaultSessionState,
  getSessionStatePath,
  loadSessionState,
  saveSessionState,
} = require("./session-state");
const { getLaunchAtLoginState, setLaunchAtLogin } = require("./login-item");
const { normalizeStartupProfile, resolveStartupProfile } = require("./startup-profile");
const { normalizeOrbBehaviorMode, resolveOrbBehaviorMode } = require("./orb-behavior");
const { resolveBuildIdentity } = require("./build-info");
const {
  buildDefaultUpdateState,
  loadUpdateState,
  saveUpdateState,
  acknowledgeUpdateNotice,
  buildUpdatePosture,
  getUpdateStatePath,
  reconcileUpdateState,
} = require("./update-state");
const {
  PORTABILITY_STATE_VERSION,
  assessPortablePayloadCompatibility,
  buildDefaultPortabilityState,
  buildOverlayExportPayload,
  extractPortablePreferences,
  loadPortabilityState,
  savePortabilityState,
} = require("./overlay-portability");
const {
  SUPPORT_STATE_VERSION,
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
const { buildRepairPlan } = require("./update-repair");
const { buildUpdateDeliveryPosture } = require("./update-delivery");
const { buildShellMigrationPosture } = require("./state-migrations");
const { repairShellState } = require("./state-repair");
const { buildDegradedModePosture } = require("./degraded-mode");
const { buildProviderPosture } = require("./provider-posture");
const { buildAuthorityPosture } = require("./authority-posture");
const { buildSigningPosture } = require("./signing-posture");
const { ORB_WINDOW_TOPMOST_LEVEL, buildOrbWindowBounds } = require("./orb-surface");
const { buildOrbFocusCropRect, buildOrbTargetStability } = require("./orb-perception");
const {
  canEngageOrbAuthority,
  detectHumanActivitySignal,
  detectHumanCursorReturn,
  detectHumanIdleRegression,
  detectHumanKeyboardReturn,
  inferOrbAuthorityState,
} = require("./orb-authority");
const { getForegroundWindowInfo } = require("./foreground-window");
const { executeWindowsInputCommand } = require("./windows-input");
const { executeOrbDesktopPlan } = require("./orb-plan");
const {
  buildDefaultLifecycleHistoryState,
  buildLifecycleHistorySurface,
  getLifecycleHistoryPath,
  loadLifecycleHistoryState,
  recordLifecycleEvent,
} = require("./lifecycle-history");

const HUD_URL = process.env.FRANCIS_HUD_URL || "http://127.0.0.1:8767";
const OVERLAY_TOGGLE_SHORTCUT = "Control+Shift+Alt+F";
const CLICK_THROUGH_TOGGLE_SHORTCUT = "Control+Shift+Alt+C";
const HUD_HEALTH_RECONCILE_INTERVAL_MS = 4000;
const HUD_MAX_RECOVERY_ATTEMPTS = 3;
const ORB_PERCEPTION_SYNC_INTERVAL_MS = 1000;
const ORB_AUTHORITY_SYNC_INTERVAL_MS = 350;
const ORB_FOREGROUND_WINDOW_CACHE_MS = 2000;

let mainWindow = null;
let orbWindow = null;
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
let lifecycleHistoryState = null;
let preferenceSaveTimer = null;
let hudRuntime = null;
let hudRecoveryTimer = null;
let hudRecoveryAttempts = 0;
let hudHealthTimer = null;
let hudHealthCheckPending = false;
let orbPerceptionTimer = null;
let orbPerceptionSyncPending = false;
let orbPerceptionErrorLogged = false;
let orbAuthorityTimer = null;
let orbAuthorityCommandPending = false;
let orbAuthorityPublishPending = false;
let orbAuthorityLastPublishedKey = "";
let orbForegroundWindow = {
  title: "",
  process: "",
  pid: null,
  updatedAt: 0,
};
let orbCursorStabilitySamples = [];
let orbAuthorityState = {
  state: "human_active",
  eligible: false,
  live: false,
  idleSeconds: 0,
  lastObservedIdleSeconds: 0,
  thresholdSeconds: 30,
  claimedCommandId: "",
  syntheticCursor: null,
  lastSyntheticAtMs: 0,
  lastHumanActivitySignalAtMs: 0,
  lastHumanActivitySignalSource: "",
  lastReleaseReason: "",
  lastHumanReturnReason: "",
};
let quitAfterHudShutdown = false;
let overlayState = {
  ignoreMouseEvents: false,
  alwaysOnTop: true,
};
let orbInputState = {
  ignoreMouseEvents: true,
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

function readSystemReducedMotionPreference() {
  try {
    if (typeof systemPreferences?.getAnimationSettings === "function") {
      const settings = systemPreferences.getAnimationSettings();
      if (typeof settings?.prefersReducedMotion === "boolean") {
        return settings.prefersReducedMotion;
      }
      if (typeof settings?.shouldRenderRichAnimation === "boolean") {
        return !settings.shouldRenderRichAnimation;
      }
    }
  } catch (error) {
    log("Could not read system reduced-motion preference", error instanceof Error ? error.message : String(error));
  }
  return false;
}

function readSystemHighContrastPreference() {
  try {
    if (typeof nativeTheme?.shouldUseHighContrastColors === "boolean") {
      return nativeTheme.shouldUseHighContrastColors;
    }
  } catch (error) {
    log("Could not read system high-contrast preference", error instanceof Error ? error.message : String(error));
  }
  return false;
}

function setOverlayRecovery(next = {}) {
  overlayRecovery = {
    needed: Boolean(next.needed),
    status: String(next.status || (next.needed ? "attention" : "nominal")),
    message: String(next.message || ""),
    lastExitReason: String(next.lastExitReason || ""),
  };
}

function recordLifecycleHistory(kind, summary, { tone = "low", detail = {} } = {}) {
  if (!app.isReady()) {
    return null;
  }
  lifecycleHistoryState = recordLifecycleEvent(
    app.getPath("userData"),
    lifecycleHistoryState || buildDefaultLifecycleHistoryState(),
    {
      id: `${Date.now()}-${String(kind || "event")}`,
      at: new Date().toISOString(),
      kind: String(kind || "shell.event"),
      summary: String(summary || "Lifecycle event recorded."),
      tone: String(tone || "low"),
      detail: detail && typeof detail === "object" ? detail : {},
    },
  );
  return lifecycleHistoryState;
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

function getShellWindows() {
  return [mainWindow, orbWindow].filter((win) => win && !win.isDestroyed());
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

function getOrbSurfaceBounds() {
  return buildOrbWindowBounds(getSortedDisplays());
}

function getOrbTargetStability(cursorScreen) {
  const nowMs = Date.now();
  if (cursorScreen && Number.isFinite(cursorScreen.x) && Number.isFinite(cursorScreen.y)) {
    const nextSample = {
      x: Math.round(Number(cursorScreen.x)),
      y: Math.round(Number(cursorScreen.y)),
      at: nowMs,
    };
    const lastSample = orbCursorStabilitySamples[orbCursorStabilitySamples.length - 1] || null;
    if (
      !lastSample
      || lastSample.x !== nextSample.x
      || lastSample.y !== nextSample.y
      || nowMs - lastSample.at >= 40
    ) {
      orbCursorStabilitySamples.push(nextSample);
    } else {
      lastSample.at = nowMs;
    }
  }

  orbCursorStabilitySamples = orbCursorStabilitySamples
    .filter((sample) => sample && Number.isFinite(sample.at) && nowMs - sample.at <= 1000)
    .slice(-16);

  return buildOrbTargetStability({
    samples: orbCursorStabilitySamples,
    nowMs,
  });
}

function getOverlayInputState() {
  const cursorScreen = screen.getCursorScreenPoint();
  const activeDisplay = screen.getDisplayNearestPoint(cursorScreen);
  const workArea = getOrbSurfaceBounds();
  const cursorDisplay = {
    x: cursorScreen.x - Number(workArea.x || 0),
    y: cursorScreen.y - Number(workArea.y || 0),
  };
  const idleSeconds = Number(powerMonitor?.getSystemIdleTime?.() || 0);
  const targetStability = getOrbTargetStability(cursorScreen);
  return {
    displayId: activeDisplay.id,
    cursorScreen,
    cursorDisplay,
    workArea,
    idleSeconds,
    idleThresholdSeconds: 30,
    humanActive: idleSeconds < 30,
    targetStability,
  };
}

function getOrbAuthoritySnapshot() {
  return {
    state: orbAuthorityState.state,
    eligible: Boolean(orbAuthorityState.eligible),
    live: Boolean(orbAuthorityState.live),
    idleSeconds: Number(orbAuthorityState.idleSeconds || 0),
    lastObservedIdleSeconds: Number(orbAuthorityState.lastObservedIdleSeconds || 0),
    thresholdSeconds: Number(orbAuthorityState.thresholdSeconds || 30),
    claimedCommandId: String(orbAuthorityState.claimedCommandId || ""),
    lastHumanActivitySignalAtMs: Number(orbAuthorityState.lastHumanActivitySignalAtMs || 0),
    lastHumanActivitySignalSource: String(orbAuthorityState.lastHumanActivitySignalSource || ""),
    lastReleaseReason: String(orbAuthorityState.lastReleaseReason || ""),
    lastHumanReturnReason: String(orbAuthorityState.lastHumanReturnReason || ""),
  };
}

async function capturePerceptionFrame() {
  const cursorPoint = screen.getCursorScreenPoint();
  const activeDisplay = screen.getDisplayNearestPoint(cursorPoint);
  const targetDisplayId = activeDisplay?.id ?? null;
  if (!desktopCapturer || typeof desktopCapturer.getSources !== "function") {
    throw new Error("desktopCapturer is unavailable in the main process");
  }
  const sources = await desktopCapturer.getSources({
    types: ["screen"],
    thumbnailSize: { width: 720, height: 405 },
    fetchWindowIcons: false,
  });
  const selected =
    sources.find((source) => String(source.display_id || "") === String(targetDisplayId || "")) ||
    sources[0] ||
    null;
  if (!selected) {
    throw new Error("No display capture source is available");
  }
  const size = selected.thumbnail.getSize();
  const focusRect = buildOrbFocusCropRect({
    sourceWidth: Number(size.width || 0),
    sourceHeight: Number(size.height || 0),
    displayBounds: activeDisplay?.bounds || null,
    cursorScreen: cursorPoint,
  });
  const focusImage =
    focusRect && typeof selected.thumbnail.crop === "function"
      ? selected.thumbnail.crop(focusRect)
      : null;
  return {
    sourceId: selected.id,
    displayId: Number(selected.display_id || targetDisplayId || 0),
    displayWidth: Number(activeDisplay?.bounds?.width || 0),
    displayHeight: Number(activeDisplay?.bounds?.height || 0),
    width: Number(size.width || 0),
    height: Number(size.height || 0),
    capturedAt: new Date().toISOString(),
    dataUrl: `data:image/jpeg;base64,${selected.thumbnail.toJPEG(78).toString("base64")}`,
    focusWidth: Number(focusRect?.width || 0),
    focusHeight: Number(focusRect?.height || 0),
    focusDataUrl:
      focusImage && !focusImage.isEmpty()
        ? `data:image/jpeg;base64,${focusImage.toJPEG(82).toString("base64")}`
        : "",
  };
}

async function getCachedForegroundWindowInfo() {
  const now = Date.now();
  if (now - Number(orbForegroundWindow.updatedAt || 0) < ORB_FOREGROUND_WINDOW_CACHE_MS) {
    return orbForegroundWindow;
  }
  const nextInfo = await getForegroundWindowInfo();
  orbForegroundWindow = {
    ...nextInfo,
    updatedAt: now,
  };
  return orbForegroundWindow;
}

async function publishOrbAuthorityState(reason = "") {
  const publishPayload = {
    state: orbAuthorityState.state,
    eligible: Boolean(orbAuthorityState.eligible),
    live: Boolean(orbAuthorityState.live),
    idle_seconds: Number(orbAuthorityState.idleSeconds || 0),
    threshold_seconds: Number(orbAuthorityState.thresholdSeconds || 30),
    claimed_command_id: String(orbAuthorityState.claimedCommandId || ""),
    reason: String(reason || orbAuthorityState.lastReleaseReason || ""),
    actor: "electron.orb",
  };
  const nextKey = JSON.stringify(publishPayload);
  if (nextKey === orbAuthorityLastPublishedKey) {
    return null;
  }
  if (orbAuthorityPublishPending) {
    return null;
  }
  const hudState = getHudState();
  if (!hudState?.ready) {
    return null;
  }
  orbAuthorityPublishPending = true;
  try {
    const payload = await fetchHudJson("/api/orb/authority/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(publishPayload),
    });
    orbAuthorityLastPublishedKey = nextKey;
    return payload;
  } catch (error) {
    log("Orb authority state publish failed", error instanceof Error ? error.message : String(error));
    return null;
  } finally {
    orbAuthorityPublishPending = false;
  }
}

async function cancelOrbAuthorityQueue(reason) {
  const hudState = getHudState();
  if (!hudState?.ready) {
    return null;
  }
  try {
    return await fetchHudJson("/api/orb/authority/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reason: String(reason || "Orb authority queue canceled."),
        actor: "electron.orb",
      }),
    });
  } catch (error) {
    log("Orb authority cancel failed", error instanceof Error ? error.message : String(error));
    return null;
  }
}

async function completeOrbAuthorityCommand(commandId, status, detail, result = {}, { humanReturned = false } = {}) {
  if (!commandId) {
    return null;
  }
  try {
    return await fetchHudJson("/api/orb/authority/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command_id: String(commandId),
        status: String(status),
        detail: String(detail || ""),
        result,
        actor: "electron.orb",
        human_returned: Boolean(humanReturned),
      }),
    });
  } catch (error) {
    log("Orb authority completion failed", error instanceof Error ? error.message : String(error));
    return null;
  }
}

async function releaseOrbAuthority(reason, { humanReturned = false } = {}) {
  const detail = String(reason || "Orb authority released.").trim() || "Orb authority released.";
  const claimedCommandId = String(orbAuthorityState.claimedCommandId || "");
  if (claimedCommandId) {
    await completeOrbAuthorityCommand(
      claimedCommandId,
      humanReturned ? "released" : "canceled",
      detail,
      {},
      { humanReturned },
    );
  }
  orbAuthorityState = {
    ...orbAuthorityState,
    state: humanReturned ? "handback" : "human_active",
    live: false,
    claimedCommandId: "",
    lastReleaseReason: detail,
    lastHumanReturnReason: humanReturned ? detail : orbAuthorityState.lastHumanReturnReason,
  };
  await publishOrbAuthorityState(detail);
  notifyOverlayState(mainWindow);
}

function signalOrbHumanActivity(source = "system_active") {
  orbAuthorityState.lastHumanActivitySignalAtMs = Date.now();
  orbAuthorityState.lastHumanActivitySignalSource = String(source || "system_active");
  if (!orbAuthorityState.live) {
    return;
  }
  void releaseOrbAuthority(
    `Human input resumed via ${orbAuthorityState.lastHumanActivitySignalSource}. Francis handed control back immediately.`,
    { humanReturned: true },
  );
}

async function executeOrbAuthorityCommand(command, inputState) {
  const payload = command && typeof command === "object" ? command : {};
  const commandId = String(payload.id || "").trim();
  const kind = String(payload.kind || "").trim().toLowerCase();
  const args = payload.args && typeof payload.args === "object" ? payload.args : {};
  const cursorScreen = inputState?.cursorScreen && typeof inputState.cursorScreen === "object" ? inputState.cursorScreen : null;
  const workArea = inputState?.workArea && typeof inputState.workArea === "object" ? inputState.workArea : { x: 0, y: 0 };
  const coordinateSpace = String(args.coordinate_space || args.coordinateSpace || "screen").trim().toLowerCase();
  const resolveScreenPoint = (x, y) => {
    const pointX = Number.isFinite(Number(x)) ? Math.round(Number(x)) : Number(cursorScreen?.x || 0);
    const pointY = Number.isFinite(Number(y)) ? Math.round(Number(y)) : Number(cursorScreen?.y || 0);
    if (coordinateSpace === "display") {
      return {
        x: Number(workArea.x || 0) + pointX,
        y: Number(workArea.y || 0) + pointY,
      };
    }
    return { x: pointX, y: pointY };
  };

  try {
    if (kind === "mouse.move") {
      const targetPoint = resolveScreenPoint(args.x, args.y);
      await executeWindowsInputCommand(
        {
          kind,
          args: targetPoint,
        },
        { platform: process.platform },
      );
      orbAuthorityState.syntheticCursor = { x: targetPoint.x, y: targetPoint.y };
      orbAuthorityState.lastSyntheticAtMs = Date.now();
      await completeOrbAuthorityCommand(commandId, "completed", "Cursor movement executed through Orb authority.", {
        cursor: { x: targetPoint.x, y: targetPoint.y },
        coordinate_space: coordinateSpace,
      });
    } else if (kind === "mouse.click") {
      const targetPoint =
        Number.isFinite(Number(args.x)) && Number.isFinite(Number(args.y))
          ? resolveScreenPoint(args.x, args.y)
          : null;
      if (targetPoint !== null) {
        await executeWindowsInputCommand(
          {
            kind: "mouse.move",
            args: targetPoint,
          },
          { platform: process.platform },
        );
        orbAuthorityState.syntheticCursor = { x: targetPoint.x, y: targetPoint.y };
        orbAuthorityState.lastSyntheticAtMs = Date.now();
      }
      await executeWindowsInputCommand(
        {
          kind,
          args,
        },
        { platform: process.platform },
      );
      orbAuthorityState.lastSyntheticAtMs = Date.now();
      await completeOrbAuthorityCommand(commandId, "completed", "Mouse click executed through Orb authority.", {
        button: String(args.button || "left"),
        double: Boolean(args.double),
        coordinate_space: coordinateSpace,
      });
    } else {
      await executeWindowsInputCommand(
        {
          kind,
          args,
        },
        { platform: process.platform },
      );
      orbAuthorityState.lastSyntheticAtMs = Date.now();
      await completeOrbAuthorityCommand(commandId, "completed", `${kind} executed through Orb authority.`, {
        kind,
      });
    }
  } catch (error) {
    await completeOrbAuthorityCommand(
      commandId,
      "failed",
      `Orb authority command failed: ${error instanceof Error ? error.message : String(error)}`,
      {},
    );
  } finally {
    orbAuthorityState.claimedCommandId = "";
  }
}

async function tickOrbAuthorityLoop() {
  if (orbAuthorityCommandPending) {
    return;
  }
  let observedIdleSeconds = Number(orbAuthorityState.lastObservedIdleSeconds || 0);
  const hudState = getHudState();
  if (!hudState?.ready || !orbWindow || orbWindow.isDestroyed()) {
    return;
  }

  orbAuthorityCommandPending = true;
  try {
    const [inputState, orbSurface] = await Promise.all([
      Promise.resolve(getOverlayInputState()),
      fetchHudJson("/api/orb"),
    ]);
    const thresholdSeconds = Math.max(
      1,
      Number(orbSurface?.cursor_policy?.threshold_ms || 30000) / 1000,
    );
    const eligible = Boolean(orbSurface?.operator_cursor_eligible);
    const now = Date.now();
    observedIdleSeconds = Number(inputState?.idleSeconds || 0);

    orbAuthorityState.eligible = eligible;
    orbAuthorityState.idleSeconds = observedIdleSeconds;
    orbAuthorityState.thresholdSeconds = thresholdSeconds;

    if (
      detectHumanActivitySignal({
        live: orbAuthorityState.live,
        lastHumanActivitySignalAtMs: orbAuthorityState.lastHumanActivitySignalAtMs,
        lastSyntheticAtMs: orbAuthorityState.lastSyntheticAtMs,
        nowMs: now,
      }) ||
      detectHumanCursorReturn({
        live: orbAuthorityState.live,
        currentCursor: inputState?.cursorScreen,
        syntheticCursor: orbAuthorityState.syntheticCursor,
        lastSyntheticAtMs: orbAuthorityState.lastSyntheticAtMs,
        nowMs: now,
      }) ||
      detectHumanKeyboardReturn({
        live: orbAuthorityState.live,
        idleSeconds: inputState?.idleSeconds,
        lastSyntheticAtMs: orbAuthorityState.lastSyntheticAtMs,
        nowMs: now,
      }) ||
      detectHumanIdleRegression({
        live: orbAuthorityState.live,
        idleSeconds: observedIdleSeconds,
        lastObservedIdleSeconds: orbAuthorityState.lastObservedIdleSeconds,
        lastSyntheticAtMs: orbAuthorityState.lastSyntheticAtMs,
        nowMs: now,
      })
    ) {
      await releaseOrbAuthority("Human input resumed. Francis handed control back immediately.", { humanReturned: true });
      return;
    }

    const authorityLive = canEngageOrbAuthority({
      eligible,
      idleSeconds: inputState?.idleSeconds,
      thresholdSeconds,
    });
    orbAuthorityState.live = authorityLive;
    orbAuthorityState.state = inferOrbAuthorityState({
      eligible,
      live: authorityLive,
      idleSeconds: inputState?.idleSeconds,
      thresholdSeconds,
    });
    await publishOrbAuthorityState(
      authorityLive
        ? "Francis authority is live in Away mode."
        : eligible
          ? "Away authority is armed while the idle threshold accumulates."
          : "Orb authority is not eligible in the current mode and run state.",
    );
    if (!authorityLive) {
      notifyOverlayState(mainWindow);
      return;
    }

    const claim = await fetchHudJson("/api/orb/authority/claim-next", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        authority_live: true,
        idle_seconds: Number(inputState?.idleSeconds || 0),
        threshold_seconds: thresholdSeconds,
        actor: "electron.orb",
      }),
    });
    if (!claim?.command || typeof claim.command !== "object") {
      notifyOverlayState(mainWindow);
      return;
    }
    orbAuthorityState.claimedCommandId = String(claim.command.id || "");
    orbAuthorityState.state = "francis_authority";
    await publishOrbAuthorityState("Francis is executing a queued Orb authority command.");
    await executeOrbAuthorityCommand(claim.command, inputState);
    notifyOverlayState(mainWindow);
  } catch (error) {
    log("Orb authority loop failed", error instanceof Error ? error.message : String(error));
  } finally {
    orbAuthorityState.lastObservedIdleSeconds = observedIdleSeconds;
    orbAuthorityCommandPending = false;
  }
}

function stopOrbAuthorityLoop() {
  if (orbAuthorityTimer !== null) {
    clearInterval(orbAuthorityTimer);
    orbAuthorityTimer = null;
  }
  orbAuthorityCommandPending = false;
  orbAuthorityLastPublishedKey = "";
}

function ensureOrbAuthorityLoop() {
  if (orbAuthorityTimer !== null) {
    return;
  }
  orbAuthorityTimer = setInterval(() => {
    void tickOrbAuthorityLoop();
  }, ORB_AUTHORITY_SYNC_INTERVAL_MS);
  void tickOrbAuthorityLoop();
}

function getOrbBehaviorState(inputState = null) {
  return resolveOrbBehaviorMode(overlayPreferences?.orbBehaviorMode, {
    humanActive: Boolean(inputState?.humanActive),
    authorityLive: Boolean(orbAuthorityState.live),
    handback: orbAuthorityState.state === "handback",
  });
}

function getLifecycleState(inputState = null) {
  const currentBuild = buildInfo || resolveBuildIdentity(app, __dirname);
  const login = getLaunchAtLoginState(app);
  const hudState = getHudState();
  const startupProfile = resolveStartupProfile(overlayPreferences, { recoveryNeeded: overlayRecovery.needed });
  const orbBehavior = getOrbBehaviorState(inputState);
  const accessibility = buildAccessibilityState({
    motionMode: overlayPreferences?.motionMode,
    systemReducedMotion: readSystemReducedMotionPreference(),
    contrastMode: overlayPreferences?.contrastMode,
    systemHighContrast: readSystemHighContrastPreference(),
    densityMode: overlayPreferences?.densityMode,
    shortcuts: {
      toggleOverlay: OVERLAY_TOGGLE_SHORTCUT,
      toggleClickThrough: CLICK_THROUGH_TOGGLE_SHORTCUT,
    },
  });
  const ready = app.isReady();
  const userDataPath = ready ? app.getPath("userData") : null;
  const workspaceRoot = ready ? path.join(userDataPath, "workspace") : null;
  const session = {
    ...(sessionState || buildDefaultSessionState()),
    hudCrashCount: hudState ? Number(hudState.crashCount || 0) : Number(sessionState?.hudCrashCount || 0),
    hudLastError: hudState?.lastError || sessionState?.hudLastError || null,
  };
  const portability = portabilityState || buildDefaultPortabilityState();
  const support = supportState || buildDefaultSupportState();
  const retainedState = ready
    ? describeRetainedState({
        userDataPath,
        workspaceRoot,
        launchAtLogin: login,
      })
    : describeRetainedState({
        userDataPath: ".",
        workspaceRoot: null,
        launchAtLogin: login,
      });
  const update = buildUpdatePosture(
    updateState ||
      (ready
        ? reconcileUpdateState(userDataPath, {
            buildIdentity: currentBuild.identity,
            preferencesSchemaVersion: PREFERENCES_VERSION,
            sessionSchemaVersion: SESSION_STATE_VERSION,
            portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
            supportSchemaVersion: SUPPORT_STATE_VERSION,
          })
        : buildDefaultUpdateState({
            buildIdentity: currentBuild.identity,
            preferencesSchemaVersion: PREFERENCES_VERSION,
            sessionSchemaVersion: SESSION_STATE_VERSION,
            portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
            supportSchemaVersion: SUPPORT_STATE_VERSION,
          })),
  );
  const provider = buildProviderPosture({
    env: process.env,
    hudState,
  });
  const authority = buildAuthorityPosture({
    env: process.env,
    portability,
    provider,
  });
  const signing = buildSigningPosture({
    env: process.env,
    distribution: currentBuild.distribution,
    packaged: currentBuild.packaged,
  });
  const preflight = ready
    ? buildPreflightState({
        userDataPath,
        workspaceRoot,
        preferencesPath: getPreferencesPath(userDataPath),
        sessionStatePath: getSessionStatePath(userDataPath),
        updateStatePath: getUpdateStatePath(userDataPath),
        hudState,
        provider,
        authority,
        signing,
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
        provider,
        authority,
        signing,
        launchAtLogin: login,
        buildIdentity: currentBuild.identity,
        distribution: currentBuild.distribution,
      });
  const migration = ready ? buildShellMigrationPosture(userDataPath) : buildShellMigrationPosture(null);
  const degradedMode = buildDegradedModePosture({
    preflight,
    migration,
    update,
    recovery: overlayRecovery,
    hud: hudState,
    provider,
    authority,
    signing,
    startupProfile,
  });
  const rollback = ready
    ? (backupState || summarizeBackups(userDataPath))
    : { count: 0, latest: null, summary: "Rollback snapshots unavailable until the shell is ready.", items: [] };
  const installRoot = ready
    ? (currentBuild.packaged ? path.dirname(process.execPath) : app.getAppPath())
    : null;
  const decommission = buildDecommissionPlan({
    buildIdentity: currentBuild.identity,
    distribution: currentBuild.distribution,
    installRoot,
    execPath: ready ? process.execPath : null,
    userDataPath,
    workspaceRoot,
    retainedState,
    rollbackState: rollback,
    portabilityState: portability,
    launchAtLogin: login,
  });
  const delivery = buildUpdateDeliveryPosture({
    distribution: currentBuild.distribution,
    buildIdentity: currentBuild.identity,
    update,
    rollback,
    signing,
    installRoot,
  });
  const repair = buildRepairPlan({
    update,
    preflight,
    migration,
    recovery: overlayRecovery,
    rollback,
    portability,
    support,
    hud: hudState,
    provider,
    authority,
    signing,
    decommission,
  });
  const history = buildLifecycleHistorySurface(lifecycleHistoryState || buildDefaultLifecycleHistoryState());
  return {
    packaged: currentBuild.packaged,
    distribution: currentBuild.distribution,
    version: currentBuild.version,
    revision: currentBuild.revision,
    buildIdentity: currentBuild.identity,
    launchAtLogin: login,
    startupProfile,
    orbBehavior,
    accessibility,
    update,
    delivery,
    portability,
    support,
    history,
    provider,
    authority,
    signing,
    degradedMode,
    provenance: buildProvenance || {
      summary: "Build provenance is unavailable.",
      version: 1,
      buildIdentity: currentBuild.identity,
      distribution: currentBuild.distribution,
    },
    retainedState,
    preflight,
    migration,
    degradedMode,
    rollback,
    decommission,
    repair,
    userDataPath,
    preferencesPath: userDataPath ? getPreferencesPath(userDataPath) : null,
    sessionStatePath: userDataPath ? getSessionStatePath(userDataPath) : null,
    updateStatePath: userDataPath ? getUpdateStatePath(userDataPath) : null,
    supportStatePath: userDataPath ? getSupportStatePath(userDataPath) : null,
    historyStatePath: userDataPath ? getLifecycleHistoryPath(userDataPath) : null,
    session,
  };
}

function getOverlayState(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  const bounds = getWindowOrPreferenceBounds(safeWindow);
  const displayInfo = app.isReady() ? getDisplayInfo(safeWindow) : null;
  const input = app.isReady() ? getOverlayInputState() : null;
  const lifecycle = getLifecycleState(input);
  const lensVisible = Boolean(mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible());
  const orbVisible = Boolean(orbWindow && !orbWindow.isDestroyed() && orbWindow.isVisible());

  return {
    ignoreMouseEvents: overlayState.ignoreMouseEvents,
    orbIgnoreMouseEvents: orbInputState.ignoreMouseEvents,
    alwaysOnTop: safeWindow ? safeWindow.isAlwaysOnTop() : overlayState.alwaysOnTop,
    visible: lensVisible || orbVisible,
    lensVisible,
    orbVisible,
    hudUrl: HUD_URL,
    bounds,
    targetDisplayId: displayInfo?.targetDisplayId ?? overlayPreferences?.targetDisplayId ?? null,
    activeDisplayId: displayInfo?.activeDisplayId ?? null,
    orbBehavior: lifecycle.orbBehavior,
    preferencesPath: lifecycle.preferencesPath,
    launchOnStartup: lifecycle.launchAtLogin.enabled,
    recovery: overlayRecovery,
    hud: getHudState(),
    lifecycle,
      shortcuts: {
        toggleOverlay: OVERLAY_TOGGLE_SHORTCUT,
        toggleClickThrough: CLICK_THROUGH_TOGGLE_SHORTCUT,
      },
      input,
      authority: getOrbAuthoritySnapshot(),
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
  recordLifecycleHistory(
    "shell.launch_at_login",
    nextState.enabled ? "Launch at login enabled." : "Launch at login disabled.",
    {
      tone: nextState.enabled ? "medium" : "low",
      detail: nextState,
    },
  );
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
  recordLifecycleHistory(
    "shell.startup_profile",
    `Startup profile set to ${normalized}.`,
    {
      tone: "low",
      detail: { requested: profileId, startupProfile: normalized },
    },
  );
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function setOrbBehaviorMode(modeId) {
  const normalized = normalizeOrbBehaviorMode(modeId);
  const safeWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
  if (app.isReady()) {
    overlayPreferences = persistOverlayPreferences(safeWindow, {
      orbBehaviorMode: normalized,
    });
  }
  log("Updated orb behavior mode", {
    requested: modeId,
    orbBehaviorMode: normalized,
  });
  recordLifecycleHistory(
    "shell.orb_behavior",
    `Orb behavior mode set to ${normalized}.`,
    {
      tone: normalized === "trace" ? "medium" : "low",
      detail: { requested: modeId, orbBehaviorMode: normalized },
    },
  );
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function setMotionMode(modeId) {
  const normalized = normalizeMotionMode(modeId);
  const safeWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
  if (app.isReady()) {
    overlayPreferences = persistOverlayPreferences(safeWindow, {
      motionMode: normalized,
    });
  }
  log("Updated motion mode", {
    requested: modeId,
    motionMode: normalized,
  });
  recordLifecycleHistory(
    "shell.motion_mode",
    `Motion mode set to ${normalized}.`,
    {
      tone: normalized === "reduce" ? "medium" : "low",
      detail: { requested: modeId, motionMode: normalized },
    },
  );
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function setContrastMode(modeId) {
  const normalized = normalizeContrastMode(modeId);
  const safeWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
  if (app.isReady()) {
    overlayPreferences = persistOverlayPreferences(safeWindow, {
      contrastMode: normalized,
    });
  }
  log("Updated contrast mode", {
    requested: modeId,
    contrastMode: normalized,
  });
  recordLifecycleHistory(
    "shell.contrast_mode",
    `Contrast mode set to ${normalized}.`,
    {
      tone: normalized === "high" ? "medium" : "low",
      detail: { requested: modeId, contrastMode: normalized },
    },
  );
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function setDensityMode(modeId) {
  const normalized = normalizeDensityMode(modeId);
  const safeWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
  if (app.isReady()) {
    overlayPreferences = persistOverlayPreferences(safeWindow, {
      densityMode: normalized,
    });
  }
  log("Updated density mode", {
    requested: modeId,
    densityMode: normalized,
  });
  recordLifecycleHistory(
    "shell.density_mode",
    `Density mode set to ${normalized}.`,
    {
      tone: normalized === "compact" ? "medium" : "low",
      detail: { requested: modeId, densityMode: normalized },
    },
  );
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
  recordLifecycleHistory(
    "update.acknowledged",
    `Update notice acknowledged for ${String(updateState.currentBuild || "unknown build")}.`,
    {
      tone: "medium",
      detail: { build: updateState.currentBuild, notice: updateState.notice },
    },
  );
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
  recordLifecycleHistory("rollback.snapshot", `Rollback snapshot ${manifest.backupId} created.`, {
    tone: "medium",
    detail: manifest,
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
    portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
    supportSchemaVersion: SUPPORT_STATE_VERSION,
  });
  portabilityState = loadPortabilityState(app.getPath("userData"));
  supportState = loadSupportState(app.getPath("userData"));
  lifecycleHistoryState = loadLifecycleHistoryState(app.getPath("userData"));
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
  recordLifecycleHistory("rollback.restore", `Rollback snapshot ${manifest.backupId} restored.`, {
    tone: "high",
    detail: manifest,
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
  recordLifecycleHistory("portability.export", `Shell state exported to ${selected.filePath}.`, {
    tone: "low",
    detail: {
      filePath: selected.filePath,
      startupProfile: payload.shell.startupProfile,
      motionMode: payload.shell.motionMode,
    },
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
    recordLifecycleHistory("portability.import_blocked", compatibility.summary, {
      tone: "high",
      detail: {
        filePath,
        compatibility,
      },
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
  recordLifecycleHistory("portability.import", `Shell state imported from ${filePath}.`, {
    tone: "medium",
    detail: {
      filePath,
      startupProfile: overlayPreferences.startupProfile,
      motionMode: overlayPreferences.motionMode,
      compatibility,
    },
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
    portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
    supportSchemaVersion: SUPPORT_STATE_VERSION,
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
  recordLifecycleHistory("shell.reset", "Retained shell state reset to defaults.", {
    tone: "medium",
    detail: { targetDisplayId: overlayPreferences.targetDisplayId },
  });
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function executeRetainedStateRepair(win = mainWindow) {
  if (!app.isReady()) {
    throw new Error("Application is not ready");
  }

  const safeWindow = win && !win.isDestroyed() ? win : null;
  const currentBuild = buildInfo || resolveBuildIdentity(app, __dirname);
  createShellBackup(app.getPath("userData"), {
    reason: "pre_repair",
    buildIdentity: currentBuild.identity,
    note: "Before repairing retained shell state",
  });
  const repairResult = repairShellState(app.getPath("userData"), {
    displays: getDisplayContext().displays,
    primaryDisplayId: getDisplayContext().primaryDisplayId,
    buildIdentity: currentBuild.identity,
    preferencesSchemaVersion: PREFERENCES_VERSION,
    sessionSchemaVersion: SESSION_STATE_VERSION,
    portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
    supportSchemaVersion: SUPPORT_STATE_VERSION,
  });

  overlayPreferences = loadPreferences(
    app.getPath("userData"),
    getDisplayContext().displays,
    getDisplayContext().primaryDisplayId,
  );
  sessionState = loadSessionState(app.getPath("userData"));
  updateState = loadUpdateState(app.getPath("userData"), {
    buildIdentity: currentBuild.identity,
    preferencesSchemaVersion: PREFERENCES_VERSION,
    sessionSchemaVersion: SESSION_STATE_VERSION,
    portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
    supportSchemaVersion: SUPPORT_STATE_VERSION,
  });
  portabilityState = loadPortabilityState(app.getPath("userData"));
  supportState = loadSupportState(app.getPath("userData"));
  refreshBackupState();

  if (safeWindow) {
    safeWindow.setBounds(overlayPreferences.windowBounds);
    applyAlwaysOnTop(safeWindow, overlayPreferences.alwaysOnTop);
    applyIgnoreMouseEvents(safeWindow, overlayPreferences.ignoreMouseEvents);
  }

  log("Executed retained state repair", repairResult);
  recordLifecycleHistory("shell.repair", repairResult.summary, {
    tone: repairResult.quarantinedCount > 0 ? "high" : repairResult.repairedCount > 0 ? "medium" : "low",
    detail: repairResult,
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
  recordLifecycleHistory("support.export", `Support bundle exported to ${selected.filePath}.`, {
    tone: "medium",
    detail: { filePath: selected.filePath, summary: payload.summary },
  });
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function notifyOverlayState(win = mainWindow) {
  const payload = getOverlayState(win);
  for (const shellWindow of getShellWindows()) {
    shellWindow.webContents.send("overlay:state-changed", payload);
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
  const visible = Boolean(
    (mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()) ||
    (orbWindow && !orbWindow.isDestroyed() && orbWindow.isVisible()),
  );
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
        label: "Motion Mode",
        submenu: (overlaySnapshot.lifecycle?.accessibility?.options || []).map((option) => ({
          label: option.label,
          type: "radio",
          checked: overlayPreferences?.motionMode === option.id,
          click: () => {
            try {
              setMotionMode(option.id);
            } catch (error) {
              log("Tray motion mode update failed", error instanceof Error ? error.message : String(error));
            }
          },
        })),
      },
      {
        label: "Contrast Mode",
        submenu: (overlaySnapshot.lifecycle?.accessibility?.contrastOptions || []).map((option) => ({
          label: option.label,
          type: "radio",
          checked: overlayPreferences?.contrastMode === option.id,
          click: () => {
            try {
              setContrastMode(option.id);
            } catch (error) {
              log("Tray contrast mode update failed", error instanceof Error ? error.message : String(error));
            }
          },
        })),
      },
      {
        label: "Density Mode",
        submenu: (overlaySnapshot.lifecycle?.accessibility?.densityOptions || []).map((option) => ({
          label: option.label,
          type: "radio",
          checked: overlayPreferences?.densityMode === option.id,
          click: () => {
            try {
              setDensityMode(option.id);
            } catch (error) {
              log("Tray density mode update failed", error instanceof Error ? error.message : String(error));
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
        label: "Repair Retained State",
        enabled: Boolean(
          (overlaySnapshot.lifecycle?.migration?.blocked || 0) > 0 ||
          (overlaySnapshot.lifecycle?.migration?.attention || 0) > 0,
        ),
        click: () => {
          try {
            executeRetainedStateRepair(requireWindow());
          } catch (error) {
            log("Tray shell repair failed", error instanceof Error ? error.message : String(error));
          }
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
      orbBehaviorMode: overrides.orbBehaviorMode ?? overlayPreferences?.orbBehaviorMode,
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
  if (orbWindow && !orbWindow.isDestroyed()) {
    orbWindow.setBounds(getOrbSurfaceBounds());
  }
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
  if (orbWindow && !orbWindow.isDestroyed()) {
    orbWindow.setBounds(getOrbSurfaceBounds());
  }
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
    if (orbWindow && !orbWindow.isDestroyed()) {
      const nextOrbBounds = getOrbSurfaceBounds();
      if (!sameBounds(orbWindow.getBounds(), nextOrbBounds)) {
        orbWindow.setBounds(nextOrbBounds);
      }
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
  const safeWindows = getShellWindows();
  if (!safeWindows.length && (!win || win.isDestroyed())) {
    return overlayState.alwaysOnTop;
  }
  // The Lens shell follows the operator topmost preference, but the Orb stays pinned as a desktop presence object.
  for (const shellWindow of safeWindows) {
    const isOrbShell = shellWindow === orbWindow;
    const nextEnabled = isOrbShell ? true : Boolean(enabled);
    const nextLevel = nextEnabled ? ORB_WINDOW_TOPMOST_LEVEL : "normal";
    shellWindow.setAlwaysOnTop(nextEnabled, nextLevel);
  }
  overlayState.alwaysOnTop = Boolean(enabled);
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

function applyOrbIgnoreMouseEvents(ignore) {
  orbInputState.ignoreMouseEvents = Boolean(ignore);
  if (!orbWindow || orbWindow.isDestroyed()) {
    return orbInputState.ignoreMouseEvents;
  }
  orbWindow.setIgnoreMouseEvents(
    orbInputState.ignoreMouseEvents,
    orbInputState.ignoreMouseEvents ? { forward: true } : undefined,
  );
  notifyOverlayState(mainWindow);
  return orbInputState.ignoreMouseEvents;
}

async function fetchHudJson(route, init = {}) {
  const target = new URL(String(route || "/"), HUD_URL).toString();
  const response = await fetch(target, init);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(String(payload?.detail || payload?.error || `${response.status} ${response.statusText}`));
  }
  return payload;
}

async function pushOrbPerceptionFrame() {
  if (orbPerceptionSyncPending) {
    return null;
  }
  if (!orbWindow || orbWindow.isDestroyed()) {
    return null;
  }
  const hudState = getHudState();
  if (!hudState?.ready) {
    return null;
  }

  orbPerceptionSyncPending = true;
  try {
    const [frame, input, foregroundWindow] = await Promise.all([
      capturePerceptionFrame(),
      Promise.resolve(getOverlayInputState()),
      getCachedForegroundWindowInfo(),
    ]);
    const payload = await fetchHudJson("/api/orb/perception", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        captured_at: frame?.capturedAt || "",
        display_id: frame?.displayId ?? null,
        display_width: Number(frame?.displayWidth || 0),
        display_height: Number(frame?.displayHeight || 0),
        idle_seconds: Number(input?.idleSeconds || 0),
        cursor_x: Number.isFinite(input?.cursorDisplay?.x) ? Math.round(input.cursorDisplay.x) : null,
        cursor_y: Number.isFinite(input?.cursorDisplay?.y) ? Math.round(input.cursorDisplay.y) : null,
        frame_width: Number(frame?.width || 0),
        frame_height: Number(frame?.height || 0),
        frame_data_url: String(frame?.dataUrl || ""),
        focus_width: Number(frame?.focusWidth || 0),
        focus_height: Number(frame?.focusHeight || 0),
        focus_data_url: String(frame?.focusDataUrl || ""),
        window_title: String(foregroundWindow?.title || ""),
        process_name: String(foregroundWindow?.process || ""),
        window_pid: Number(foregroundWindow?.pid || 0) || null,
        window_x: Number.isFinite(foregroundWindow?.bounds?.x) ? Math.round(foregroundWindow.bounds.x) : null,
        window_y: Number.isFinite(foregroundWindow?.bounds?.y) ? Math.round(foregroundWindow.bounds.y) : null,
        window_width: Number(foregroundWindow?.bounds?.width || 0),
        window_height: Number(foregroundWindow?.bounds?.height || 0),
        target_stability_state: String(input?.targetStability?.state || "idle"),
        target_stability_dwell_ms: Number(input?.targetStability?.dwellMs || 0),
        target_stability_travel_px: Number(input?.targetStability?.travelPx || 0),
        target_stability_sample_count: Number(input?.targetStability?.sampleCount || 0),
      }),
    });
    orbPerceptionErrorLogged = false;
    return payload;
  } catch (error) {
    if (!orbPerceptionErrorLogged) {
      orbPerceptionErrorLogged = true;
      log("Orb perception sync failed", error instanceof Error ? error.message : String(error));
    }
    return null;
  } finally {
    orbPerceptionSyncPending = false;
  }
}

function stopOrbPerceptionLoop() {
  if (orbPerceptionTimer !== null) {
    clearInterval(orbPerceptionTimer);
    orbPerceptionTimer = null;
  }
  orbPerceptionSyncPending = false;
}

function ensureOrbPerceptionLoop() {
  if (orbPerceptionTimer !== null) {
    return;
  }
  orbPerceptionTimer = setInterval(() => {
    void pushOrbPerceptionFrame();
  }, ORB_PERCEPTION_SYNC_INTERVAL_MS);
  void pushOrbPerceptionFrame();
}

function showLensWindow() {
  const win = requireWindow();
  if (win.isMinimized()) {
    win.restore();
  }
  win.showInactive();
  notifyOverlayState(win);
  return getOverlayState(win);
}

function hideLensWindow() {
  const win = requireWindow();
  win.hide();
  notifyOverlayState(win);
  return getOverlayState(win);
}

function showOrbWindow() {
  if (!orbWindow || orbWindow.isDestroyed()) {
    orbWindow = createOrbWindow();
    return getOverlayState(mainWindow);
  }
  if (orbWindow.isMinimized()) {
    orbWindow.restore();
  }
  orbWindow.showInactive();
  notifyOverlayState(mainWindow);
  return getOverlayState(mainWindow);
}

function hideAllWindows() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
  }
  if (orbWindow && !orbWindow.isDestroyed()) {
    orbWindow.hide();
  }
  notifyOverlayState(mainWindow);
  return true;
}

async function showFallbackPage(win, errorText) {
  if (!win || win.isDestroyed()) {
    return;
  }
  log("Loading fallback error page", errorText);
  await win.loadURL(fallbackUrl(errorText));
}

function getLensHudUrl() {
  const target = new URL(HUD_URL);
  target.searchParams.set("orb", "external");
  return target.toString();
}

function getOrbHudUrl() {
  const target = new URL(HUD_URL);
  target.searchParams.set("orb", "window");
  target.searchParams.set("view", "orb_only");
  return target.toString();
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
  if (hudRecoveryTimer || hudRecoveryAttempts >= HUD_MAX_RECOVERY_ATTEMPTS) {
    return;
  }
  hudRecoveryAttempts += 1;
  log("Scheduling managed HUD recovery", {
    reason,
    attempt: hudRecoveryAttempts,
    maxAttempts: HUD_MAX_RECOVERY_ATTEMPTS,
  });
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
      log("Managed HUD recovery failed", error instanceof Error ? error.message : String(error));
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

async function reconcileHudHealth() {
  if (hudHealthCheckPending || !hudRuntime || quitAfterHudShutdown) {
    return;
  }

  const hudState = getHudState();
  if (!hudState?.ready) {
    return;
  }

  hudHealthCheckPending = true;
  try {
    const reachable = await isHudReachable(HUD_URL, 1500);
    if (reachable) {
      return;
    }

    log("HUD runtime became unreachable while the shell still considered it ready", {
      managed: Boolean(hudState?.managed),
      mode: hudState?.mode || null,
      pid: hudState?.pid || null,
      healthUrl: hudState?.healthUrl || null,
    });

    if (hudState?.managed) {
      scheduleHudRecovery("hud-unreachable");
      return;
    }

    setOverlayRecovery({
      needed: true,
      status: "failed",
      message: "The HUD is unreachable. Restart the local runtime or bring the external HUD back online.",
      lastExitReason: "hud-unreachable",
    });
    notifyOverlayState(mainWindow);
  } finally {
    hudHealthCheckPending = false;
  }
}

function ensureHudHealthMonitor() {
  if (hudHealthTimer !== null) {
    return;
  }
  hudHealthTimer = setInterval(() => {
    void reconcileHudHealth();
  }, HUD_HEALTH_RECONCILE_INTERVAL_MS);
  void reconcileHudHealth();
}

function stopHudHealthMonitor() {
  if (hudHealthTimer !== null) {
    clearInterval(hudHealthTimer);
    hudHealthTimer = null;
  }
  hudHealthCheckPending = false;
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
    const lensUrl = getLensHudUrl();
    log("Loading HUD", lensUrl);
    await win.loadURL(lensUrl);
  } catch (error) {
    if (!handledFailure) {
      handledFailure = true;
      await showFallbackPage(win, error instanceof Error ? error.message : String(error));
    }
  }
}

function createOrbWindow() {
  const { displays, primaryDisplayId } = getDisplayContext();
  overlayPreferences = loadPreferences(app.getPath("userData"), displays, primaryDisplayId);
  const preloadPath = path.join(__dirname, "preload.js");
  const targetDisplay = resolveTargetDisplay(displays, overlayPreferences.targetDisplayId, primaryDisplayId);
  const startupProfile = resolveStartupProfile(overlayPreferences, { recoveryNeeded: overlayRecovery.needed });
  const orbBounds = buildOrbWindowBounds(displays);

  log("Creating orb window", {
    targetDisplayId: targetDisplay.id,
    bounds: orbBounds,
  });

  const win = new BrowserWindow({
    x: orbBounds.x,
    y: orbBounds.y,
    width: orbBounds.width,
    height: orbBounds.height,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    alwaysOnTop: true,
    resizable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    hasShadow: false,
    autoHideMenuBar: true,
    title: "Francis Orb",
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  });

  win.setMenuBarVisibility(false);
  applyAlwaysOnTop(win, overlayPreferences.alwaysOnTop);
  orbInputState.ignoreMouseEvents = true;
  win.setIgnoreMouseEvents(true, { forward: true });
  win.removeMenu();
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.setAlwaysOnTop(true, ORB_WINDOW_TOPMOST_LEVEL);
  win.webContents.once("did-finish-load", () => {
    log("Orb HUD loaded", win.webContents.getURL());
  });
  win.webContents.once("did-fail-load", (_event, code, description, validatedUrl, isMainFrame) => {
    if (!isMainFrame) {
      return;
    }
    log("Orb HUD failed to load", {
      code,
      description,
      validatedUrl,
    });
  });
  win.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    log("Orb HUD console", {
      level,
      message,
      line,
      sourceId,
    });
  });
  const orbUrl = getOrbHudUrl();
  log("Loading orb HUD", orbUrl);
  win.loadURL(orbUrl).catch((error) => {
    log("Unexpected orb HUD load error", error instanceof Error ? error.message : String(error));
  });
  ensureOrbPerceptionLoop();
  ensureOrbAuthorityLoop();

  win.once("ready-to-show", () => {
    if (startupProfile.visible) {
      log("Orb ready; showing window", {
        startupProfile: startupProfile.effective,
      });
      win.showInactive();
      notifyOverlayState(mainWindow);
      return;
    }
    log("Orb ready; startup profile keeps the shell hidden until summoned", {
      startupProfile: startupProfile.effective,
    });
    notifyOverlayState(mainWindow);
  });

  win.on("show", () => notifyOverlayState(mainWindow));
  win.on("hide", () => notifyOverlayState(mainWindow));
  win.on("closed", () => {
    log("Orb window closed");
    if (orbWindow === win) {
      orbWindow = null;
      stopOrbPerceptionLoop();
      stopOrbAuthorityLoop();
    }
  });

  return win;
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
    log("Lens ready; keeping the HUD hidden until the Orb opens it", {
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
  recordLifecycleHistory("hud.restart", "Managed HUD restarted from the overlay shell.", {
    tone: "medium",
    detail: getHudState() || {},
  });
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
  ipcMain.handle("overlay:set-orb-ignore-mouse-events", (_event, ignore) => {
    const value = applyOrbIgnoreMouseEvents(ignore);
    log("Updated orb pass-through state", value);
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
  ipcMain.handle("overlay:set-orb-behavior-mode", (_event, modeId) => setOrbBehaviorMode(modeId));
  ipcMain.handle("overlay:set-motion-mode", (_event, modeId) => setMotionMode(modeId));
  ipcMain.handle("overlay:set-contrast-mode", (_event, modeId) => setContrastMode(modeId));
  ipcMain.handle("overlay:set-density-mode", (_event, modeId) => setDensityMode(modeId));
  ipcMain.handle("overlay:acknowledge-update-notice", () => dismissUpdateNotice());
  ipcMain.handle("overlay:export-shell-state", () => exportShellState(requireWindow()));
  ipcMain.handle("overlay:import-shell-state", () => importShellState(requireWindow()));
  ipcMain.handle("overlay:reset-shell-state", () => resetRetainedShellState(requireWindow()));
  ipcMain.handle("overlay:repair-shell-state", () => executeRetainedStateRepair(requireWindow()));
  ipcMain.handle("overlay:create-rollback-snapshot", () => createRollbackSnapshot("manual", "Created from the desktop shell."));
  ipcMain.handle("overlay:restore-latest-rollback", () => restoreLatestRollbackSnapshot(requireWindow()));
  ipcMain.handle("overlay:export-support-bundle", () => exportSupportBundle(requireWindow()));
  ipcMain.handle("overlay:set-target-display", (_event, displayId) => moveOverlayToDisplay(displayId, requireWindow()));
  ipcMain.handle("overlay:reset-layout", () => resetOverlayPreferences(requireWindow()));
  ipcMain.handle("overlay:get-state", () => getOverlayState(requireWindow()));
  ipcMain.handle("overlay:get-input-state", () => getOverlayInputState());
  ipcMain.handle("overlay:capture-perception-frame", () => capturePerceptionFrame());
  ipcMain.handle("overlay:get-display-info", () => getDisplayInfo(requireWindow()));
  ipcMain.handle("overlay:restart-hud", () => restartHudAndRefreshWindow(requireWindow()));
  ipcMain.handle("overlay:open-path", (_event, target) => openLifecyclePath(target));
  ipcMain.handle("overlay:get-orb-surface", () => fetchHudJson("/api/orb"));
  ipcMain.handle("overlay:execute-orb-desktop-plan", async (_event, plan) => {
    const result = await executeOrbDesktopPlan(plan, {
      inputState: getOverlayInputState(),
      executeCommand: (command) => executeWindowsInputCommand(command, { platform: process.platform }),
      onSyntheticCursor: (point) => {
        if (!point || !Number.isFinite(Number(point.x)) || !Number.isFinite(Number(point.y))) {
          return;
        }
        orbAuthorityState.syntheticCursor = {
          x: Math.round(Number(point.x)),
          y: Math.round(Number(point.y)),
        };
        orbAuthorityState.lastSyntheticAtMs = Date.now();
      },
      onSyntheticInput: () => {
        orbAuthorityState.lastSyntheticAtMs = Date.now();
      },
    });
    recordLifecycleHistory(
      "orb.desktop_plan",
      String(result?.status || "").trim().toLowerCase() === "failed"
        ? `Orb desktop plan failed: ${String(result.title || "Orb desktop plan")}.`
        : `Orb desktop plan executed: ${String(result.title || "Orb desktop plan")}.`,
      {
        tone: String(result?.status || "").trim().toLowerCase() === "failed" ? "high" : "medium",
        detail: result && typeof result === "object" ? result : {},
      },
    );
    return result;
  });
  ipcMain.handle("overlay:panic-stop", async () => {
    const response = await fetchHudJson("/api/actions/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "control.panic",
        args: {},
        dry_run: false,
        role: "architect",
        user: "electron.orb",
      }),
    });
    await cancelOrbAuthorityQueue("Panic stop canceled queued Orb authority commands.");
    await releaseOrbAuthority("Panic stop released Orb authority immediately.");
    return response;
  });
  ipcMain.handle("overlay:show-lens", () => showLensWindow());
  ipcMain.handle("overlay:hide-lens", () => hideLensWindow());

  ipcMain.handle("overlay:minimize", () => {
    const win = requireWindow();
    win.minimize();
    notifyOverlayState(win);
    return true;
  });

  ipcMain.handle("overlay:hide", () => {
    hideAllWindows();
    return true;
  });

  ipcMain.handle("overlay:show", () => {
    showOrbWindow();
    return true;
  });

  ipcMain.handle("overlay:quit", () => {
    log("Quitting overlay from renderer control");
    app.quit();
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
  if ((!mainWindow || mainWindow.isDestroyed()) && (!orbWindow || orbWindow.isDestroyed())) {
    return;
  }
  const visible = Boolean(
    (mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()) ||
    (orbWindow && !orbWindow.isDestroyed() && orbWindow.isVisible()),
  );
  if (visible) {
    log("Hiding overlay via global shortcut");
    hideAllWindows();
    return;
  }
  log("Showing overlay via global shortcut");
  showOrbWindow();
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

function registerPowerMonitorListeners() {
  if (!powerMonitor || typeof powerMonitor.on !== "function") {
    return;
  }
  powerMonitor.on("user-did-become-active", () => {
    signalOrbHumanActivity("power_monitor");
  });
  powerMonitor.on("unlock-screen", () => {
    signalOrbHumanActivity("unlock_screen");
  });
  powerMonitor.on("resume", () => {
    signalOrbHumanActivity("system_resume");
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
    lifecycleHistoryState = loadLifecycleHistoryState(app.getPath("userData"));
    const priorUpdateState = loadUpdateState(app.getPath("userData"), {
      buildIdentity: buildInfo.identity,
      preferencesSchemaVersion: PREFERENCES_VERSION,
      sessionSchemaVersion: SESSION_STATE_VERSION,
      portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
      supportSchemaVersion: SUPPORT_STATE_VERSION,
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
        portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
        supportSchemaVersion: SUPPORT_STATE_VERSION,
      });
    }
    updateState = reconcileUpdateState(app.getPath("userData"), {
      buildIdentity: buildInfo.identity,
      preferencesSchemaVersion: PREFERENCES_VERSION,
      sessionSchemaVersion: SESSION_STATE_VERSION,
      portabilitySchemaVersion: PORTABILITY_STATE_VERSION,
      supportSchemaVersion: SUPPORT_STATE_VERSION,
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
    registerPowerMonitorListeners();
    await initializeHudRuntime();
    ensureHudHealthMonitor();
    mainWindow = createMainWindow();
    orbWindow = createOrbWindow();
    createTray();
    registerShortcuts();
  });

  app.on("second-instance", () => {
    if (!mainWindow || mainWindow.isDestroyed()) {
      mainWindow = createMainWindow();
    }
    if (!orbWindow || orbWindow.isDestroyed()) {
      orbWindow = createOrbWindow();
    }
    toggleOverlayVisibility();
  });
}

app.on("activate", () => {
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = createMainWindow();
  }
  if (!orbWindow || orbWindow.isDestroyed()) {
    orbWindow = createOrbWindow();
  }
  if (!orbWindow.isVisible()) {
    orbWindow.showInactive();
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
  stopHudHealthMonitor();
  stopOrbPerceptionLoop();
  stopOrbAuthorityLoop();
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
