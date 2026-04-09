const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
const { app, BrowserWindow, Menu, Tray, desktopCapturer, dialog, globalShortcut, ipcMain, nativeImage, nativeTheme, powerMonitor, screen, shell, systemPreferences } = require("electron");
const {
  classifyHudReachabilityFailure,
  createHudRuntimeManager,
  isHudReachable,
  probeHudReachability,
} = require("./hud-runtime");
const { createOllamaRuntimeManager, isOllamaReachable, normalizeOllamaUrl, DEFAULT_OLLAMA_URL } = require("./ollama-runtime");
const { isCaptureForegroundWindow } = require("./capture-mode");
const { getScheduledHudRecoveryReason } = require("./hud-recovery");
const { guardStandardStreams, patchConsoleForDetachedPipes, writeConsole } = require("./safe-log");
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
const {
  resolveOrbFirstAppActivation,
  resolveOrbFirstSecondInstance,
  resolveStartupSurface,
} = require("./startup-surface");
const {
  normalizeOrbBehaviorMode,
  normalizePersistedOrbBehaviorMode,
  resolveOrbBehaviorMode,
} = require("./orb-behavior");
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
const { inspectAuthenticodeSignature } = require("./signature-state");
const {
  ORB_WINDOW_REINFORCE_INTERVAL_MS,
  ORB_WINDOW_TOPMOST_LEVEL,
  ORB_WINDOW_TOPMOST_PRIORITY,
  buildDesktopAuthoritySnapshot,
  buildOrbDisplayTopology,
  buildOrbWindowBounds,
} = require("./orb-surface");
const {
  EMPTY_ORB_ACCESSIBILITY,
  buildOrbEnvironmentGrounding,
  buildOrbFocusCropRect,
  buildOrbTargetStability,
  getOrbFocusedAccessibilitySnapshot,
} = require("./orb-perception");
const {
  canEngageOrbAuthority,
  describeOrbClickTargetLockFailure,
  detectHumanActivitySignal,
  detectHumanCursorReturn,
  detectHumanIdleRegression,
  detectHumanKeyboardReturn,
  inferOrbAuthorityState,
  isOrbClickTargetLocked,
} = require("./orb-authority");
const {
  buildOrbControlState,
  buildPauseAuthorityResult,
  normalizeRemoteSyncStatus,
} = require("./orb-control-state");
const {
  ORB_OWNERSHIP_STATES,
  armOrbOwnershipUserOverride,
  buildOrbOwnershipState,
  buildDefaultOrbOwnershipGovernor,
  clearOrbOwnershipUserOverride,
  isOrbOwnershipUserOverrideReason,
  normalizeOrbOwnershipRequest,
  shouldClearOrbOwnershipUserOverrideForReason,
  shouldResetOrbOwnershipForForeground,
} = require("./orb-ownership-state");
const {
  buildDefaultOrbRuntimeHealth,
  escalateOrbRuntimeFailure,
  getOrbRuntimeRetryDelayMs,
  isOrbRuntimeProbeDeferred,
  recordOrbRuntimeHealthy,
  startOrbRuntimeRecovery,
} = require("./orb-runtime-health");
const {
  beginHudRecoveryAttempt,
  buildDefaultHudRecoveryState,
  finishHudRecoveryAttempt,
  isStaleHudGeneration,
  noteHudEndpointFailure,
  noteHudEndpointSuccess,
  noteHudGenerationReady,
  noteHudProcessState,
  scheduleHudRecovery: planHudRecovery,
} = require("./hud-recovery-state");
const { getForegroundWindowInfo } = require("./foreground-window");
const { buildWindowsDesktopCapabilityProfile, executeWindowsInputCommand } = require("./windows-input");
const { executeOrbDesktopPlan } = require("./orb-plan");
const { buildPanicStopResult } = require("./orb-panic");
const { buildOrbExecutionSemantics } = require("./orb-execution");
const {
  buildDefaultLifecycleHistoryState,
  buildLifecycleHistorySurface,
  getLifecycleHistoryPath,
  loadLifecycleHistoryState,
  recordLifecycleEvent,
} = require("./lifecycle-history");

const HUD_URL = process.env.FRANCIS_HUD_URL || "http://127.0.0.1:8767";
const OLLAMA_URL = normalizeOllamaUrl(process.env.FRANCIS_OLLAMA_HOST || process.env.OLLAMA_HOST || DEFAULT_OLLAMA_URL);
const ORB_VERIFICATION_CAPTURE_ENABLED = (() => {
  const switchValue = app.commandLine.hasSwitch("francis-orb-capture-on-start")
    ? app.commandLine.getSwitchValue("francis-orb-capture-on-start") || "1"
    : "";
  const envValue = String(process.env.FRANCIS_ORB_CAPTURE_ON_START || "").trim();
  return /^(1|true|yes|on)$/i.test(String(switchValue || envValue).trim());
})();
const ORB_VERIFICATION_CAPTURE_DIR = (() => {
  const switchValue = app.commandLine.hasSwitch("francis-orb-capture-dir")
    ? app.commandLine.getSwitchValue("francis-orb-capture-dir")
    : "";
  const rawValue = String(switchValue || process.env.FRANCIS_ORB_CAPTURE_DIR || "").trim();
  return path.resolve(rawValue || os.tmpdir());
})();

guardStandardStreams(process.stdout, process.stderr);
patchConsoleForDetachedPipes(console);
const OVERLAY_TOGGLE_SHORTCUT = "Control+Shift+Alt+F";
const CLICK_THROUGH_TOGGLE_SHORTCUT = "Control+Shift+Alt+C";
const HUD_HEALTH_RECONCILE_INTERVAL_MS = 4000;
const HUD_HEALTH_TIMEOUT_MS = 8000;
const HUD_HEALTH_FAILURES_BEFORE_RECOVERY = 3;
const HUD_MAX_RECOVERY_ATTEMPTS = 3;
const HUD_RECOVERY_BASE_DELAY_MS = 1500;
const HUD_RECOVERY_MAX_DELAY_MS = 12000;
const OLLAMA_HEALTH_RECONCILE_INTERVAL_MS = 7000;
const OLLAMA_MAX_RECOVERY_ATTEMPTS = 3;
const ORB_PERCEPTION_SYNC_INTERVAL_MS = 1000;
const ORB_AUTHORITY_SYNC_INTERVAL_MS = 350;
const ORB_FOREGROUND_WINDOW_CACHE_MS = 2000;
const ORB_ACCESSIBILITY_CACHE_MS = 800;
const ORB_LOCAL_STOP_LATCH_MS = 5000;
const ORB_CLICK_ACTUATION_LOCK_TIMEOUT_MS = 1400;
const ORB_CLICK_ACTUATION_LOCK_POLL_MS = 90;
const TRAY_QUIT_ARM_WINDOW_MS = 8000;
const REVIEW_HUD_WINDOW_ENABLED = false;

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
let executableSignature = null;
let preferenceSaveTimer = null;
let hudRuntime = null;
let ollamaRuntime = null;
let hudRecoveryTimer = null;
let hudRecoveryAttempts = 0;
let hudHealthTimer = null;
let hudHealthCheckPending = false;
let hudHealthFailureCount = 0;
let ollamaRecoveryTimer = null;
let ollamaRecoveryAttempts = 0;
let ollamaHealthTimer = null;
let ollamaHealthCheckPending = false;
let captureRecoveryTimer = null;
let captureCheckPending = false;
let orbPerceptionTimer = null;
let orbPerceptionSyncPending = false;
let orbPerceptionErrorLogged = false;
let orbAuthorityTimer = null;
let orbSurfaceAuthorityTimer = null;
let orbAuthorityCommandPending = false;
let orbAuthorityPublishPending = false;
let orbAuthorityLastPublishedKey = "";
let orbAuthorityFailureLogged = false;
let orbAuthorityExecutionClearTimer = null;
let orbForegroundWindow = {
  title: "",
  process: "",
  pid: null,
  elevated: false,
  bounds: {
    x: null,
    y: null,
    width: 0,
    height: 0,
  },
  updatedAt: 0,
};
let orbFocusedAccessibility = {
  ...EMPTY_ORB_ACCESSIBILITY,
  updatedAt: 0,
};
let orbCursorStabilitySamples = [];
let orbPerceptionEnvironmentSamples = [];
let orbAuthorityState = {
  state: "human_active",
  eligible: false,
  live: false,
  idleSeconds: 0,
  lastObservedIdleSeconds: 0,
  thresholdSeconds: 30,
  claimedCommandId: "",
  activeCommandKind: "",
  executionPhase: "",
  executionSummary: "",
  executionDetail: "",
  executionTarget: null,
  syntheticCursor: null,
  lastSyntheticAtMs: 0,
  lastHumanActivitySignalAtMs: 0,
  lastHumanActivitySignalSource: "",
  lastReleaseReason: "",
  lastHumanReturnReason: "",
};
let orbSafetyState = {
  localStopLatchedUntilMs: 0,
  localStopActive: false,
  pauseHeld: false,
  remoteSyncStatus: "current",
  summary: "",
  detail: "",
  degraded: false,
  disconnected: false,
  localError: "",
  remoteError: "",
  lastAction: "",
  lastReason: "",
  lastChangedAtMs: 0,
};
let orbPanicStopPending = null;
let orbPauseAuthorityPending = null;
let orbRuntimeHealth = buildDefaultOrbRuntimeHealth();
let hudRecoveryState = buildDefaultHudRecoveryState();
let hudRestartPromise = null;
let hudLastRecoverySuppressionKey = "";
let orbOwnershipSuppressionLogKey = "";
let trayQuitArmedUntilMs = 0;
let trayQuitArmTimer = null;
let quitAfterHudShutdown = false;
let overlayState = {
  ignoreMouseEvents: false,
  alwaysOnTop: true,
};
let orbInputState = {
  ignoreMouseEvents: true,
};
let orbOwnershipRequest = {
  mode: ORB_OWNERSHIP_STATES.PASS_THROUGH,
  reason: "startup",
  updatedAtMs: 0,
};
let orbOwnershipGovernor = buildDefaultOrbOwnershipGovernor();
let overlayRecovery = {
  needed: false,
  status: "nominal",
  message: "",
  lastExitReason: "",
};
let captureSuspensionState = {
  active: false,
  reason: "",
  lensVisible: false,
  orbVisible: false,
  overlayIgnoreMouseEvents: false,
  orbIgnoreMouseEvents: true,
  overlayAlwaysOnTop: true,
};
let lensInteractionRestoreIgnoreMouseEvents = null;

function log(message, extra) {
  const prefix = `[francis-overlay] ${message}`;
  appendMainLogLine(prefix, extra);
  if (extra === undefined) {
    writeConsole(console.log, prefix);
    return;
  }
  writeConsole(console.log, prefix, extra);
}

function requestAppQuit(reason, details = {}) {
  const stack = new Error().stack
    ?.split("\n")
    .slice(2, 8)
    .map((line) => line.trim())
    .join(" | ");
  log("Quit requested", {
    reason: String(reason || "unknown"),
    ...details,
    stack: stack || "",
  });
  app.quit();
}

function confirmTrayQuit() {
  const choice = dialog.showMessageBoxSync({
    type: "question",
    buttons: ["Cancel", "Quit Francis"],
    defaultId: 0,
    cancelId: 0,
    noLink: true,
    title: "Quit Francis Overlay",
    message: "Quit Francis Overlay?",
    detail: "Francis will shut down the overlay windows and the managed HUD runtime.",
  });
  return choice === 1;
}

function isTrayQuitArmed() {
  return trayQuitArmedUntilMs > Date.now();
}

function armTrayQuit() {
  if (trayQuitArmTimer !== null) {
    clearTimeout(trayQuitArmTimer);
    trayQuitArmTimer = null;
  }
  trayQuitArmedUntilMs = Date.now() + TRAY_QUIT_ARM_WINDOW_MS;
  trayQuitArmTimer = setTimeout(() => {
    trayQuitArmTimer = null;
    clearTrayQuitArm();
  }, TRAY_QUIT_ARM_WINDOW_MS);
  log("Tray quit armed", {
    expiresInMs: TRAY_QUIT_ARM_WINDOW_MS,
  });
  updateTray();
}

function clearTrayQuitArm() {
  if (trayQuitArmTimer !== null) {
    clearTimeout(trayQuitArmTimer);
    trayQuitArmTimer = null;
  }
  if (!trayQuitArmedUntilMs) {
    return;
  }
  trayQuitArmedUntilMs = 0;
  updateTray();
}

function handleTrayQuitRequest() {
  if (!isTrayQuitArmed()) {
    armTrayQuit();
    return;
  }
  clearTrayQuitArm();
  if (!confirmTrayQuit()) {
    log("Tray quit request canceled");
    return;
  }
  requestAppQuit("tray-menu");
}

function appendMainLogLine(message, extra) {
  try {
    const logPath = resolveMainLogPath();
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    const suffix =
      extra === undefined
        ? ""
        : ` ${typeof extra === "string" ? extra : JSON.stringify(extra)}`;
    fs.appendFileSync(logPath, `${new Date().toISOString()} ${message}${suffix}\n`, "utf8");
  } catch {
    // Logging must never crash the main process.
  }
}

function resolveMainLogPath() {
  if (app?.isReady()) {
    try {
      return path.join(app.getPath("userData"), "logs", "electron-main.log");
    } catch {
      // Fall back to a temp path when userData is unavailable.
    }
  }
  return path.join(os.tmpdir(), "francis-electron-main.log");
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

function getOrbRuntimeHealthSnapshot() {
  return {
    ...orbRuntimeHealth,
  };
}

function getCurrentHudGeneration() {
  return Math.max(
    0,
    Number(getHudState()?.generation || hudRecoveryState?.generation || 0),
  );
}

function markHudGenerationReady(hudState, { nowMs = Date.now() } = {}) {
  hudRecoveryState = noteHudGenerationReady(hudRecoveryState, {
    pid: hudState?.pid ?? null,
    nowMs,
  });
  return hudRecoveryState;
}

function markHudEndpointSuccess(channel, { generation = getCurrentHudGeneration(), nowMs = Date.now() } = {}) {
  const result = noteHudEndpointSuccess(hudRecoveryState, {
    channel,
    generation,
    nowMs,
  });
  hudRecoveryState = result.state;
  return result;
}

function markHudEndpointFailure(channel, {
  generation = getCurrentHudGeneration(),
  kind = "unknown",
  message = "",
  statusCode = 0,
  nowMs = Date.now(),
} = {}) {
  const result = noteHudEndpointFailure(hudRecoveryState, {
    channel,
    generation,
    kind,
    message,
    statusCode,
    nowMs,
  });
  hudRecoveryState = result.state;
  return result;
}

function classifyHudFetchFailure(error, statusCode = 0) {
  return classifyHudReachabilityFailure(error, statusCode);
}

function buildHudRecoveryDiagnostics(extra = {}) {
  const hudState = getHudState();
  const nowMs = Date.now();
  return {
    generation: getCurrentHudGeneration(),
    managed: Boolean(hudState?.managed),
    mode: hudState?.mode || null,
    pid: hudState?.pid || null,
    previousPid: hudRecoveryState?.previousPid || null,
    childAlive: Boolean(hudState?.childAlive ?? hudRecoveryState?.childAlive),
    healthUrl: hudState?.healthUrl || null,
    recoveryAttempt: Number(hudRecoveryState?.recovery?.attempt || 0),
    recoveryTimerActive: Boolean(hudRecoveryTimer),
    recoveryInFlight: Boolean(hudRecoveryState?.recovery?.inFlight || hudRestartPromise),
    recoveryId: Number(hudRecoveryState?.recovery?.id || 0),
    hudReadyFromState: Boolean(hudState?.ready),
    staleReadyWindow: Boolean(hudState?.ready && hudHealthFailureCount > 0),
    lastHealthOkAtMs: Number(hudRecoveryState?.lastHealthOkAtMs || 0),
    lastHealthOkAgoMs: hudRecoveryState?.lastHealthOkAtMs ? Math.max(0, nowMs - hudRecoveryState.lastHealthOkAtMs) : null,
    lastPerceptionOkAtMs: Number(hudRecoveryState?.lastPerceptionOkAtMs || 0),
    lastPerceptionOkAgoMs: hudRecoveryState?.lastPerceptionOkAtMs ? Math.max(0, nowMs - hudRecoveryState.lastPerceptionOkAtMs) : null,
    lastAuthorityStateOkAtMs: Number(hudRecoveryState?.lastAuthorityStateOkAtMs || 0),
    lastAuthorityStateOkAgoMs: hudRecoveryState?.lastAuthorityStateOkAtMs ? Math.max(0, nowMs - hudRecoveryState.lastAuthorityStateOkAtMs) : null,
    orbPerceptionInFlight: Boolean(orbPerceptionSyncPending),
    orbAuthorityCommandInFlight: Boolean(orbAuthorityCommandPending),
    orbAuthorityPublishInFlight: Boolean(orbAuthorityPublishPending),
    ...extra,
  };
}

function isStaleHudGenerationError(error) {
  return Boolean(error && typeof error === "object" && error.name === "HudGenerationStaleError");
}

function createStaleHudGenerationError(route, requestGeneration, currentGeneration) {
  const error = new Error(
    `Ignored stale HUD response for ${String(route || "/")} from generation ${requestGeneration}; current generation is ${currentGeneration}.`,
  );
  error.name = "HudGenerationStaleError";
  error.route = String(route || "/");
  error.requestGeneration = Number(requestGeneration || 0);
  error.currentGeneration = Number(currentGeneration || 0);
  return error;
}

function setOrbRuntimeHealth(nextState, { notify = true } = {}) {
  orbRuntimeHealth = {
    ...buildDefaultOrbRuntimeHealth(),
    ...(nextState && typeof nextState === "object" ? nextState : {}),
  };
  reconcileOrbOwnership("runtime_health_changed", { notify });
  if (notify) {
    notifyOverlayState(mainWindow);
  }
  return getOrbRuntimeHealthSnapshot();
}

function recordOrbRuntimeFailure(reason, {
  source = "hud",
  nowMs = Date.now(),
  notify = true,
} = {}) {
  return setOrbRuntimeHealth(
    escalateOrbRuntimeFailure(orbRuntimeHealth, {
      reason,
      source,
      nowMs,
    }),
    { notify },
  );
}

function markOrbRuntimeRecovering(reason, {
  source = "hud",
  nowMs = Date.now(),
  notify = true,
} = {}) {
  return setOrbRuntimeHealth(
    startOrbRuntimeRecovery(orbRuntimeHealth, {
      reason,
      source,
      nowMs,
    }),
    { notify },
  );
}

function recordOrbRuntimeHealthyProof(reason, {
  source = "hud",
  nowMs = Date.now(),
  notify = true,
} = {}) {
  return setOrbRuntimeHealth(
    recordOrbRuntimeHealthy(orbRuntimeHealth, {
      reason,
      source,
      nowMs,
    }),
    { notify },
  );
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

function getOllamaState() {
  return ollamaRuntime ? ollamaRuntime.getPublicState() : null;
}

function buildManagedHudEnv() {
  return {
    ...process.env,
    FRANCIS_OLLAMA_HOST: String(getOllamaState()?.serviceUrl || OLLAMA_URL),
  };
}

function getShellWindows() {
  return [mainWindow, orbWindow].filter((win) => win && !win.isDestroyed());
}

function getLiveMainWindow() {
  return mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
}

function getLiveOrbWindow() {
  return orbWindow && !orbWindow.isDestroyed() ? orbWindow : null;
}

function getShellControlWindow({ preferOrb = true } = {}) {
  const liveMainWindow = getLiveMainWindow();
  const liveOrbWindow = getLiveOrbWindow();
  return preferOrb ? liveOrbWindow || liveMainWindow : liveMainWindow || liveOrbWindow;
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

function getDisplayTopology(displays = getSortedDisplays(), {
  targetDisplayId = overlayPreferences?.targetDisplayId ?? null,
  activeDisplayId = null,
} = {}) {
  return buildOrbDisplayTopology(displays, {
    targetDisplayId,
    activeDisplayId,
  });
}

function listDisplays() {
  return getDisplayTopology().displays;
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
  const activeDisplayId = getActiveDisplay(win)?.id ?? null;
  const topology = getDisplayTopology(getSortedDisplays(), {
    activeDisplayId,
  });
  const desktopAuthority = buildDesktopAuthoritySnapshot({
    displays: topology.displays,
    targetDisplayId: topology.targetDisplayId,
    activeDisplayId: topology.activeDisplayId,
    foregroundWindow: orbForegroundWindow,
    capabilityProfile: buildWindowsDesktopCapabilityProfile({
      platform: process.platform,
      foregroundWindow: orbForegroundWindow,
    }),
    orbVisible: Boolean(orbWindow && !orbWindow.isDestroyed() && orbWindow.isVisible()),
    lensVisible: Boolean(mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()),
    alwaysOnTop: orbWindow && !orbWindow.isDestroyed() ? orbWindow.isAlwaysOnTop() : true,
    overlayIgnoreMouseEvents: overlayState.ignoreMouseEvents,
    orbIgnoreMouseEvents: orbInputState.ignoreMouseEvents,
    captureSuspended: captureSuspensionState.active,
  });

  return {
    primaryDisplayId: topology.primaryDisplayId,
    targetDisplayId: topology.targetDisplayId,
    activeDisplayId: topology.activeDisplayId,
    targetDisplay: topology.targetDisplay,
    activeDisplay: topology.activeDisplay,
    displays: topology.displays,
    virtualBounds: topology.virtualBounds,
    desktopAuthority,
  };
}

function getReceiptForegroundWindowSnapshot() {
  const bounds = orbForegroundWindow?.bounds && typeof orbForegroundWindow.bounds === "object"
    ? {
        x: Number.isFinite(Number(orbForegroundWindow.bounds.x)) ? Math.round(Number(orbForegroundWindow.bounds.x)) : null,
        y: Number.isFinite(Number(orbForegroundWindow.bounds.y)) ? Math.round(Number(orbForegroundWindow.bounds.y)) : null,
        width: Math.max(0, Math.round(Number(orbForegroundWindow.bounds.width || 0))),
        height: Math.max(0, Math.round(Number(orbForegroundWindow.bounds.height || 0))),
      }
    : null;
  return {
    title: String(orbForegroundWindow?.title || "").trim(),
    process: String(orbForegroundWindow?.process || "").trim(),
    pid: Number(orbForegroundWindow?.pid || 0) || null,
    elevated: Boolean(orbForegroundWindow?.elevated),
    fullscreenLike: Boolean(orbForegroundWindow?.fullscreenLike),
    hostDisplayLabel: String(orbForegroundWindow?.hostDisplayLabel || "").trim(),
    bounds,
  };
}

function buildOrbReceiptContext(inputState = null) {
  const safeInput = inputState && typeof inputState === "object" ? inputState : getOverlayInputState();
  const displayInfo = app.isReady() ? getDisplayInfo(mainWindow) : null;
  return {
    authority: getOrbAuthoritySnapshot(safeInput),
    ownership: getOrbOwnershipSnapshot({ input: safeInput, foregroundWindow: orbForegroundWindow }),
    desktop_authority: displayInfo?.desktopAuthority || null,
    foreground_window: getReceiptForegroundWindowSnapshot(),
    display: displayInfo
      ? {
          targetDisplayId: displayInfo.targetDisplayId ?? null,
          activeDisplayId: displayInfo.activeDisplayId ?? null,
          summary: String(displayInfo.summary || "").trim(),
        }
      : null,
  };
}

function getOrbSurfaceBounds(displays = getSortedDisplays()) {
  return buildOrbWindowBounds(displays);
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
  const workArea = getDisplayTopology(getSortedDisplays(), {
    activeDisplayId: activeDisplay?.id ?? null,
  }).virtualBounds;
  const cursorDisplay = {
    x: cursorScreen.x - Number(workArea.x || 0),
    y: cursorScreen.y - Number(workArea.y || 0),
  };
  const idleSeconds = Number(powerMonitor?.getSystemIdleTime?.() || 0);
  const targetStability = getOrbTargetStability(cursorScreen);
  return {
    displayId: activeDisplay.id,
    displayBounds: activeDisplay?.bounds || null,
    displayWorkArea: activeDisplay?.workArea || null,
    cursorScreen,
    cursorDisplay,
    workArea,
    idleSeconds,
    idleThresholdSeconds: 30,
    humanActive: idleSeconds < 30,
    targetStability,
  };
}

function getOrbSafetySnapshot(nowMs = Date.now()) {
  const latchedUntilMs = Number(orbSafetyState.localStopLatchedUntilMs || 0);
  return {
    ...orbSafetyState,
    remoteSyncStatus: normalizeRemoteSyncStatus(orbSafetyState.remoteSyncStatus),
    localStopActive: Boolean(orbSafetyState.localStopActive),
    localError: cleanSafetyDiagnostic(orbSafetyState.localError),
    remoteError: cleanSafetyDiagnostic(orbSafetyState.remoteError),
    localStopped: Boolean(orbSafetyState.localStopActive) || latchedUntilMs > Number(nowMs || Date.now()),
  };
}

function cleanSafetyText(value, fallback = "") {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text || fallback;
}

function cleanSafetyDiagnostic(value, fallback = "") {
  return cleanSafetyText(value, fallback);
}

function setOrbSafetyState(patch = {}, { notify = true } = {}) {
  const nextPatch = patch && typeof patch === "object" ? patch : {};
  orbSafetyState = {
    ...orbSafetyState,
    ...nextPatch,
    localStopLatchedUntilMs: Object.prototype.hasOwnProperty.call(nextPatch, "localStopLatchedUntilMs")
      ? Math.max(0, Number(nextPatch.localStopLatchedUntilMs || 0))
      : Math.max(0, Number(orbSafetyState.localStopLatchedUntilMs || 0)),
    localStopActive: Object.prototype.hasOwnProperty.call(nextPatch, "localStopActive")
      ? Boolean(nextPatch.localStopActive)
      : Boolean(orbSafetyState.localStopActive),
    pauseHeld: Object.prototype.hasOwnProperty.call(nextPatch, "pauseHeld")
      ? Boolean(nextPatch.pauseHeld)
      : Boolean(orbSafetyState.pauseHeld),
    disconnected: Object.prototype.hasOwnProperty.call(nextPatch, "disconnected")
      ? Boolean(nextPatch.disconnected)
      : Boolean(orbSafetyState.disconnected),
    degraded: Object.prototype.hasOwnProperty.call(nextPatch, "degraded")
      ? Boolean(nextPatch.degraded)
      : Boolean(orbSafetyState.degraded),
    remoteSyncStatus: normalizeRemoteSyncStatus(
      Object.prototype.hasOwnProperty.call(nextPatch, "remoteSyncStatus")
        ? nextPatch.remoteSyncStatus
        : orbSafetyState.remoteSyncStatus,
    ),
    summary: Object.prototype.hasOwnProperty.call(nextPatch, "summary")
      ? cleanSafetyText(nextPatch.summary)
      : cleanSafetyText(orbSafetyState.summary),
    detail: Object.prototype.hasOwnProperty.call(nextPatch, "detail")
      ? cleanSafetyText(nextPatch.detail)
      : cleanSafetyText(orbSafetyState.detail),
    lastAction: Object.prototype.hasOwnProperty.call(nextPatch, "lastAction")
      ? cleanSafetyText(nextPatch.lastAction)
      : cleanSafetyText(orbSafetyState.lastAction),
    lastReason: Object.prototype.hasOwnProperty.call(nextPatch, "lastReason")
      ? cleanSafetyText(nextPatch.lastReason)
      : cleanSafetyText(orbSafetyState.lastReason),
    localError: Object.prototype.hasOwnProperty.call(nextPatch, "localError")
      ? cleanSafetyDiagnostic(nextPatch.localError)
      : cleanSafetyDiagnostic(orbSafetyState.localError),
    remoteError: Object.prototype.hasOwnProperty.call(nextPatch, "remoteError")
      ? cleanSafetyDiagnostic(nextPatch.remoteError)
      : cleanSafetyDiagnostic(orbSafetyState.remoteError),
    lastChangedAtMs: Date.now(),
  };
  if (notify) {
    notifyOverlayState(mainWindow);
  }
  return getOrbSafetySnapshot();
}

function setOrbAuthorityExecutionState(nextExecution = {}, { notify = true } = {}) {
  if (orbAuthorityExecutionClearTimer !== null) {
    clearTimeout(orbAuthorityExecutionClearTimer);
    orbAuthorityExecutionClearTimer = null;
  }
  const target =
    nextExecution.target && typeof nextExecution.target === "object"
      ? {
          x: Number.isFinite(Number(nextExecution.target.x)) ? Math.round(Number(nextExecution.target.x)) : null,
          y: Number.isFinite(Number(nextExecution.target.y)) ? Math.round(Number(nextExecution.target.y)) : null,
          coordinate_space: String(nextExecution.target.coordinate_space || nextExecution.target.coordinateSpace || "screen").trim().toLowerCase() || "screen",
        }
      : null;
  orbAuthorityState = {
    ...orbAuthorityState,
    activeCommandKind: String(nextExecution.kind || orbAuthorityState.activeCommandKind || "").trim().toLowerCase(),
    executionPhase: String(nextExecution.phase || orbAuthorityState.executionPhase || "").trim().toLowerCase(),
    executionSummary: cleanSafetyText(nextExecution.summary || orbAuthorityState.executionSummary || ""),
    executionDetail: cleanSafetyText(nextExecution.detail || orbAuthorityState.executionDetail || ""),
    executionTarget:
      target && Number.isFinite(Number(target.x)) && Number.isFinite(Number(target.y))
        ? target
        : null,
  };
  if (notify) {
    notifyOverlayState(mainWindow);
  }
  return getOrbAuthoritySnapshot();
}

function clearOrbAuthorityExecutionState({ notify = true } = {}) {
  if (orbAuthorityExecutionClearTimer !== null) {
    clearTimeout(orbAuthorityExecutionClearTimer);
    orbAuthorityExecutionClearTimer = null;
  }
  orbAuthorityState = {
    ...orbAuthorityState,
    activeCommandKind: "",
    executionPhase: "",
    executionSummary: "",
    executionDetail: "",
    executionTarget: null,
  };
  if (notify) {
    notifyOverlayState(mainWindow);
  }
  return getOrbAuthoritySnapshot();
}

function scheduleOrbAuthorityExecutionClear(phase = "") {
  if (orbAuthorityExecutionClearTimer !== null) {
    clearTimeout(orbAuthorityExecutionClearTimer);
    orbAuthorityExecutionClearTimer = null;
  }
  const normalizedPhase = String(phase || "").trim().toLowerCase();
  const holdMs = normalizedPhase === "click_act"
    ? 220
    : normalizedPhase === "drag_act"
      ? 280
      : normalizedPhase === "type_hold"
        ? 260
        : normalizedPhase === "hover_ready"
          ? 140
          : normalizedPhase === "blocked" || normalizedPhase === "interrupted"
            ? 260
            : 160;
  orbAuthorityExecutionClearTimer = setTimeout(() => {
    orbAuthorityExecutionClearTimer = null;
    if (!orbAuthorityState.live && !orbAuthorityState.claimedCommandId) {
      clearOrbAuthorityExecutionState();
    }
  }, holdMs);
}

function stabilizeOrbAuthorityLocally(reason, {
  localStop = false,
  localStopActive = null,
  pauseHold = null,
  disconnected = null,
  degraded = null,
  remoteSyncStatus = null,
  summary = "",
  detail = "",
  localError = "",
  remoteError = "",
  humanReturned = false,
  notify = true,
} = {}) {
  const resolvedDetail = cleanSafetyText(detail || reason || "Human control remains primary.", "Human control remains primary.");
  const resolvedSummary = cleanSafetyText(summary || orbSafetyState.summary || resolvedDetail, "Human control remains primary.");
  const nextLocalStopActive =
    localStopActive === null || localStopActive === undefined
      ? localStop
        ? true
        : pauseHold === true
          ? false
          : orbSafetyState.localStopActive
      : Boolean(localStopActive);
  orbAuthorityState = {
    ...orbAuthorityState,
    state: humanReturned ? "handback" : "human_active",
    live: false,
    claimedCommandId: "",
    activeCommandKind: "",
    executionPhase: "",
    executionSummary: "",
    executionDetail: "",
    executionTarget: null,
    syntheticCursor: null,
    lastSyntheticAtMs: 0,
    lastReleaseReason: resolvedDetail,
    lastHumanReturnReason: humanReturned ? resolvedDetail : orbAuthorityState.lastHumanReturnReason,
  };
  resetOrbOwnershipToSafeFallback(localStop ? "panic_stop" : pauseHold ? "pause_authority" : "authority_local_fallback");
  applyOrbIgnoreMouseEvents(true);
  return setOrbSafetyState({
    localStopLatchedUntilMs: localStop
      ? Date.now() + ORB_LOCAL_STOP_LATCH_MS
      : pauseHold === true
        ? 0
        : orbSafetyState.localStopLatchedUntilMs,
    localStopActive: nextLocalStopActive,
    pauseHeld: pauseHold === null || pauseHold === undefined ? orbSafetyState.pauseHeld : Boolean(pauseHold),
    disconnected: disconnected === null || disconnected === undefined ? orbSafetyState.disconnected : Boolean(disconnected),
    degraded: degraded === null || degraded === undefined ? orbSafetyState.degraded : Boolean(degraded),
    remoteSyncStatus: remoteSyncStatus === null || remoteSyncStatus === undefined ? orbSafetyState.remoteSyncStatus : remoteSyncStatus,
    summary: resolvedSummary,
    detail: resolvedDetail,
    localError,
    remoteError,
    lastAction: localStop ? "panic_stop" : pauseHold ? "pause_authority" : orbSafetyState.lastAction,
    lastReason: resolvedDetail,
  }, { notify });
}

function getOrbAuthoritySnapshot(inputState = null) {
  const safeInput = inputState && typeof inputState === "object" ? inputState : getOverlayInputState();
  const snapshot = buildOrbControlState({
    authorityState: orbAuthorityState,
    hudState: getHudState(),
    recovery: overlayRecovery,
    inputState: safeInput,
    ignoreMouseEvents: orbInputState.ignoreMouseEvents,
    safetyState: getOrbSafetySnapshot(),
  });
  return {
    ...snapshot,
    rawState: {
      state: orbAuthorityState.state,
      eligible: Boolean(orbAuthorityState.eligible),
      live: Boolean(orbAuthorityState.live),
      idleSeconds: Number(orbAuthorityState.idleSeconds || 0),
      lastObservedIdleSeconds: Number(orbAuthorityState.lastObservedIdleSeconds || 0),
      thresholdSeconds: Number(orbAuthorityState.thresholdSeconds || 30),
      claimedCommandId: String(orbAuthorityState.claimedCommandId || ""),
      activeCommandKind: String(orbAuthorityState.activeCommandKind || ""),
      executionPhase: String(orbAuthorityState.executionPhase || ""),
      executionSummary: String(orbAuthorityState.executionSummary || ""),
      executionDetail: String(orbAuthorityState.executionDetail || ""),
      executionTarget:
        orbAuthorityState.executionTarget && typeof orbAuthorityState.executionTarget === "object"
          ? orbAuthorityState.executionTarget
          : null,
    },
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

async function getCachedFocusedAccessibilityInfo() {
  const now = Date.now();
  if (now - Number(orbFocusedAccessibility.updatedAt || 0) < ORB_ACCESSIBILITY_CACHE_MS) {
    return orbFocusedAccessibility;
  }
  const nextInfo = await getOrbFocusedAccessibilitySnapshot();
  orbFocusedAccessibility = {
    ...EMPTY_ORB_ACCESSIBILITY,
    ...(nextInfo && typeof nextInfo === "object" ? nextInfo : {}),
    updatedAt: now,
  };
  return orbFocusedAccessibility;
}

function appendOrbPerceptionEnvironmentSample(sample = null, nowMs = Date.now()) {
  const maxAgeMs = 4200;
  const normalizedSample = sample && typeof sample === "object"
    ? {
        key: String(sample.key || "").trim(),
        at: Number.isFinite(Number(sample.at)) ? Number(sample.at) : Number(nowMs || Date.now()),
      }
    : null;
  orbPerceptionEnvironmentSamples = orbPerceptionEnvironmentSamples
    .filter((entry) => entry && Number.isFinite(Number(entry.at)) && nowMs - Number(entry.at) <= maxAgeMs)
    .slice(-8);
  if (normalizedSample && normalizedSample.key) {
    orbPerceptionEnvironmentSamples.push(normalizedSample);
    orbPerceptionEnvironmentSamples = orbPerceptionEnvironmentSamples.slice(-8);
  }
  return orbPerceptionEnvironmentSamples;
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
    }, {
      generation: getCurrentHudGeneration(),
      channel: "authority_state",
    });
    orbAuthorityLastPublishedKey = nextKey;
    if (orbSafetyState.disconnected || (orbSafetyState.degraded && orbSafetyState.remoteSyncStatus === "pending" && !orbSafetyState.pauseHeld)) {
      setOrbSafetyState({
        disconnected: false,
        degraded: Boolean(
          overlayRecovery.needed
          || orbSafetyState.pauseHeld
          || orbSafetyState.localStopActive
          || orbSafetyState.remoteSyncStatus !== "current"
        ),
        localError:
          orbSafetyState.pauseHeld || orbSafetyState.localStopActive || orbSafetyState.remoteSyncStatus !== "current"
            ? orbSafetyState.localError
            : "",
        remoteError:
          orbSafetyState.pauseHeld || orbSafetyState.localStopActive || orbSafetyState.remoteSyncStatus !== "current"
            ? orbSafetyState.remoteError
            : "",
      }, { notify: false });
    }
    return payload;
  } catch (error) {
    if (isStaleHudGenerationError(error)) {
      return null;
    }
    log("Orb authority state publish failed", error instanceof Error ? error.message : String(error));
    return null;
  } finally {
    orbAuthorityPublishPending = false;
  }
}

async function cancelOrbAuthorityQueue(reason) {
  const hudState = getHudState();
  if (!hudState?.ready) {
    return {
      ok: false,
      payload: null,
      error: "HUD is not ready.",
    };
  }
  try {
    const payload = await fetchHudJson("/api/orb/authority/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reason: String(reason || "Orb authority queue canceled."),
        actor: "electron.orb",
      }),
    });
    return {
      ok: true,
      payload,
      error: "",
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    log("Orb authority cancel failed", message);
    return {
      ok: false,
      payload: null,
      error: message,
    };
  }
}

async function completeOrbAuthorityCommand(commandId, status, detail, result = {}, { humanReturned = false } = {}) {
  if (!commandId) {
    return null;
  }
  try {
    const receiptContext = buildOrbReceiptContext();
    const normalizedResult = result && typeof result === "object"
      ? {
          ...receiptContext,
          ...result,
          desktop_authority: result.desktop_authority || receiptContext.desktop_authority,
          foreground_window: result.foreground_window || receiptContext.foreground_window,
          authority: result.authority || receiptContext.authority,
          ownership: result.ownership || receiptContext.ownership,
          display: result.display || receiptContext.display,
        }
      : receiptContext;
    return await fetchHudJson("/api/orb/authority/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command_id: String(commandId),
        status: String(status),
        detail: String(detail || ""),
        result: normalizedResult,
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
    activeCommandKind: "",
    executionPhase: "",
    executionSummary: "",
    executionDetail: "",
    executionTarget: null,
    lastReleaseReason: detail,
    lastHumanReturnReason: humanReturned ? detail : orbAuthorityState.lastHumanReturnReason,
  };
  await publishOrbAuthorityState(detail);
  notifyOverlayState(mainWindow);
}

async function pauseOrbAuthorityLocally() {
  if (orbPauseAuthorityPending) {
    return orbPauseAuthorityPending;
  }
  orbPauseAuthorityPending = (async () => {
    if (orbAuthorityState.live) {
      const result = buildPauseAuthorityResult({ activeLive: true });
      setOrbSafetyState({
        summary: result.summary,
        detail: result.detail,
        lastAction: "pause_authority",
        lastReason: result.detail,
      });
      return result;
    }

    stabilizeOrbAuthorityLocally(
      "Pause cleared local authority immediately. Human control remains primary.",
      {
        pauseHold: true,
        localStopActive: false,
        remoteSyncStatus: "pending",
        disconnected: !getHudState()?.ready,
        degraded: true,
        summary: "Paused locally. Clearing queued authority work.",
        detail: "Human control remains primary while Francis confirms queued authority work is cleared.",
        localError: "",
        remoteError: "",
      },
    );
    resetOrbOwnershipToSafeFallback("pause_authority");

    const remoteResult = await cancelOrbAuthorityQueue("Pause cleared queued Orb authority commands.");
    const remoteSynced = Boolean(remoteResult?.ok);
    const remoteSyncStatus = remoteSynced ? "current" : getHudState()?.ready ? "failed" : "pending";
    const result = buildPauseAuthorityResult({
      remoteSynced,
      remoteSyncStatus,
      summary: remoteSynced
        ? "Paused. Queued work cleared; human control remains primary."
        : remoteSyncStatus === "failed"
          ? "Paused locally. Remote queue clear failed."
          : "Paused locally. Remote queue clear pending.",
      detail: remoteSynced
        ? "Queued authority work was cleared locally and remotely."
        : remoteSyncStatus === "failed"
          ? "Human control remains primary, but the queued remote clear did not confirm."
          : "Human control remains primary while the queued remote clear remains pending.",
    });

    setOrbSafetyState({
      localStopLatchedUntilMs: 0,
      localStopActive: false,
      pauseHeld: !remoteSynced,
      disconnected: remoteSyncStatus === "pending" && !getHudState()?.ready,
      degraded: !remoteSynced || Boolean(overlayRecovery.needed),
      remoteSyncStatus,
      summary: result.summary,
      detail: result.detail,
      localError: "",
      remoteError: remoteSynced
        ? ""
        : cleanSafetyDiagnostic(remoteResult?.error || "Orb authority queue clear did not confirm."),
      lastAction: "pause_authority",
      lastReason: result.detail,
    });
    resetOrbOwnershipToSafeFallback("pause_authority");

    return result;
  })();
  try {
    return await orbPauseAuthorityPending;
  } finally {
    orbPauseAuthorityPending = null;
  }
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

async function waitForOrbClickTargetLock({
  timeoutMs = ORB_CLICK_ACTUATION_LOCK_TIMEOUT_MS,
  pollMs = ORB_CLICK_ACTUATION_LOCK_POLL_MS,
} = {}) {
  const deadline = Date.now() + Math.max(120, Number(timeoutMs || ORB_CLICK_ACTUATION_LOCK_TIMEOUT_MS));
  let lastCue = null;
  while (Date.now() <= deadline) {
    const safetySnapshot = getOrbSafetySnapshot();
    if (safetySnapshot.localStopped || safetySnapshot.pauseHeld || safetySnapshot.disconnected) {
      return {
        ready: false,
        reason: "safety_hold",
        cue: lastCue,
      };
    }
    try {
      const orbSurface = await fetchHudJson("/api/orb", {}, {
        generation: getCurrentHudGeneration(),
      });
      const cue = orbSurface?.operator?.target_cue;
      if (cue && typeof cue === "object") {
        lastCue = cue;
      }
      if (isOrbClickTargetLocked(orbSurface)) {
        return {
          ready: true,
          reason: "target_lock",
          cue: lastCue,
        };
      }
    } catch (error) {
      if (!isStaleHudGenerationError(error)) {
        return {
          ready: false,
          reason: "surface_unavailable",
          cue: lastCue,
        };
      }
    }
    await delayMs(pollMs);
  }
  return {
    ready: false,
    reason: "target_lock_timeout",
    cue: lastCue,
  };
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
  const setExecution = (status, {
    explicitPhase = "",
    executionArgs = args,
    target = null,
    notify = true,
  } = {}) => {
    const execution = buildOrbExecutionSemantics({
      kind,
      args: executionArgs,
      status,
      explicitPhase,
      target,
    });
    setOrbAuthorityExecutionState(execution, { notify });
    return execution;
  };

  try {
    if (kind === "mouse.move") {
      const targetPoint = resolveScreenPoint(args.x, args.y);
      setExecution("claimed", {
        executionArgs: {
          ...args,
          x: targetPoint.x,
          y: targetPoint.y,
          coordinate_space: "screen",
        },
        target: targetPoint,
      });
      const executionResult = await executeWindowsInputCommand(
        {
          kind,
          args: targetPoint,
        },
        { platform: process.platform },
      );
      orbAuthorityState.syntheticCursor = { x: targetPoint.x, y: targetPoint.y };
      orbAuthorityState.lastSyntheticAtMs = Date.now();
      const execution = executionResult?.execution && typeof executionResult.execution === "object"
        ? executionResult.execution
        : setExecution("completed", {
            executionArgs: {
              ...args,
              x: targetPoint.x,
              y: targetPoint.y,
              coordinate_space: "screen",
            },
            target: targetPoint,
            notify: false,
          });
      setOrbAuthorityExecutionState(execution, { notify: true });
      await completeOrbAuthorityCommand(commandId, "completed", "Cursor movement executed through Orb authority.", {
        cursor: { x: targetPoint.x, y: targetPoint.y },
        coordinate_space: coordinateSpace,
        execution,
      });
      scheduleOrbAuthorityExecutionClear(execution?.phase);
    } else if (kind === "mouse.click") {
      const hasExplicitTarget = Number.isFinite(Number(args.x)) && Number.isFinite(Number(args.y));
      if (!hasExplicitTarget) {
        throw new Error("Orb click requires explicit target coordinates from the Orb target lock.");
      }
      const targetPoint = resolveScreenPoint(args.x, args.y);
      const preserveHumanCursor = Boolean(
        args.preserve_human_cursor !== false
        && args.preserveHumanCursor !== false,
      );
      const clickArgs = {
        ...args,
        x: targetPoint.x,
        y: targetPoint.y,
        coordinate_space: "screen",
        preserve_human_cursor: preserveHumanCursor,
      };
      setExecution("claimed", {
        explicitPhase: "target_lock",
        executionArgs: clickArgs,
        target: targetPoint,
      });
      const targetLock = await waitForOrbClickTargetLock();
      if (!targetLock.ready) {
        throw new Error(describeOrbClickTargetLockFailure(targetLock));
      }
      setExecution("claimed", {
        executionArgs: clickArgs,
        target: targetPoint,
      });
      if (!preserveHumanCursor) {
        await executeWindowsInputCommand(
          {
            kind: "mouse.move",
            args: targetPoint,
          },
          { platform: process.platform },
        );
        orbAuthorityState.syntheticCursor = { x: targetPoint.x, y: targetPoint.y };
        orbAuthorityState.lastSyntheticAtMs = Date.now();
        setExecution("hover_ready", {
          explicitPhase: "hover_ready",
          executionArgs: clickArgs,
          target: targetPoint,
        });
      }
      setExecution("claimed", {
        explicitPhase: "click_act",
        executionArgs: clickArgs,
        target: targetPoint,
      });
      const executionResult = await executeWindowsInputCommand(
        {
          kind,
          args: clickArgs,
        },
        { platform: process.platform },
      );
      if (
        preserveHumanCursor
        && Number.isFinite(Number(cursorScreen?.x))
        && Number.isFinite(Number(cursorScreen?.y))
      ) {
        orbAuthorityState.syntheticCursor = {
          x: Math.round(Number(cursorScreen.x)),
          y: Math.round(Number(cursorScreen.y)),
        };
      } else {
        orbAuthorityState.syntheticCursor = { x: targetPoint.x, y: targetPoint.y };
      }
      orbAuthorityState.lastSyntheticAtMs = Date.now();
      const execution = executionResult?.execution && typeof executionResult.execution === "object"
        ? executionResult.execution
        : setExecution("completed", {
            executionArgs: clickArgs,
            target: targetPoint,
            notify: false,
          });
      setOrbAuthorityExecutionState(execution, { notify: true });
      await completeOrbAuthorityCommand(commandId, "completed", "Mouse click executed through Orb authority.", {
        button: String(args.button || "left"),
        double: Boolean(args.double),
        coordinate_space: coordinateSpace,
        cursor: { x: targetPoint.x, y: targetPoint.y },
        preserve_human_cursor: preserveHumanCursor,
        target_lock: {
          ready: true,
          reason: targetLock.reason,
          attention_state: String(targetLock?.cue?.attention_state || "").trim().toLowerCase(),
          control_ready: Boolean(targetLock?.cue?.control_ready),
        },
        execution,
      });
      scheduleOrbAuthorityExecutionClear(execution?.phase);
    } else if (kind === "mouse.drag") {
      const targetPoint = resolveScreenPoint(args.x, args.y);
      const startPoint =
        Number.isFinite(Number(args.start_x)) && Number.isFinite(Number(args.start_y))
          ? resolveScreenPoint(args.start_x, args.start_y)
          : null;
      const dragArgs = {
        ...args,
        x: targetPoint.x,
        y: targetPoint.y,
        coordinate_space: "screen",
        ...(startPoint ? {
          start_x: startPoint.x,
          start_y: startPoint.y,
        } : {}),
      };
      setExecution("claimed", {
        executionArgs: dragArgs,
        target: targetPoint,
      });
      const executionResult = await executeWindowsInputCommand(
        {
          kind,
          args: dragArgs,
        },
        { platform: process.platform },
      );
      orbAuthorityState.syntheticCursor = { x: targetPoint.x, y: targetPoint.y };
      orbAuthorityState.lastSyntheticAtMs = Date.now();
      const execution = executionResult?.execution && typeof executionResult.execution === "object"
        ? executionResult.execution
        : setExecution("completed", {
            executionArgs: dragArgs,
            target: targetPoint,
            notify: false,
          });
      setOrbAuthorityExecutionState(execution, { notify: true });
      await completeOrbAuthorityCommand(commandId, "completed", "Mouse drag executed through Orb authority.", {
        button: String(args.button || "left"),
        coordinate_space: coordinateSpace,
        cursor: { x: targetPoint.x, y: targetPoint.y },
        execution,
      });
      scheduleOrbAuthorityExecutionClear(execution?.phase);
    } else {
      setExecution("claimed");
      const executionResult = await executeWindowsInputCommand(
        {
          kind,
          args,
        },
        { platform: process.platform },
      );
      orbAuthorityState.lastSyntheticAtMs = Date.now();
      const execution = executionResult?.execution && typeof executionResult.execution === "object"
        ? executionResult.execution
        : setExecution("completed", { notify: false });
      setOrbAuthorityExecutionState(execution, { notify: true });
      await completeOrbAuthorityCommand(commandId, "completed", `${kind} executed through Orb authority.`, {
        kind,
        execution,
      });
      scheduleOrbAuthorityExecutionClear(execution?.phase);
    }
  } catch (error) {
    const failedExecution = buildOrbExecutionSemantics({
      kind,
      args,
      status: "failed",
    });
    setOrbAuthorityExecutionState(failedExecution, { notify: true });
    await completeOrbAuthorityCommand(
      commandId,
      "failed",
      `Orb authority command failed: ${error instanceof Error ? error.message : String(error)}`,
      {
        execution: failedExecution,
      },
    );
    scheduleOrbAuthorityExecutionClear(failedExecution?.phase);
  } finally {
    orbAuthorityState.claimedCommandId = "";
    orbAuthorityState.activeCommandKind = "";
  }
}

async function tickOrbAuthorityLoop() {
  if (orbAuthorityCommandPending) {
    return;
  }
  const nowMs = Date.now();
  if (isOrbRuntimeProbeDeferred(orbRuntimeHealth, nowMs)) {
    return;
  }
  let observedIdleSeconds = Number(orbAuthorityState.lastObservedIdleSeconds || 0);
  const hudState = getHudState();
  if (!hudState?.ready || !orbWindow || orbWindow.isDestroyed()) {
    const failureHealth = recordOrbRuntimeFailure("Orb authority lost HUD readiness.", {
      source: "authority",
      notify: false,
      nowMs,
    });
    if (orbAuthorityState.live || orbAuthorityState.claimedCommandId || !getOrbSafetySnapshot().disconnected) {
      stabilizeOrbAuthorityLocally(
        "HUD disconnected. Human control remains primary.",
        {
          disconnected: true,
          degraded: true,
          pauseHold: getOrbSafetySnapshot().pauseHeld,
          remoteSyncStatus: "pending",
          summary: "HUD disconnected. Human control remains primary.",
          detail: "Francis dropped local authority because the local operator stack is unavailable.",
        },
      );
    }
    resetOrbOwnershipToSafeFallback("authority_unavailable");
    if (!orbAuthorityFailureLogged) {
      orbAuthorityFailureLogged = true;
      log("Orb authority loop degraded", {
        status: failureHealth.status,
        source: failureHealth.source,
        nextProbeAtMs: failureHealth.nextProbeAtMs,
        circuitOpenUntilMs: failureHealth.circuitOpenUntilMs,
      });
    }
    notifyOverlayState(mainWindow);
    return;
  }

  orbAuthorityCommandPending = true;
  try {
    const [inputState, orbSurface] = await Promise.all([
      Promise.resolve(getOverlayInputState()),
      fetchHudJson("/api/orb", {}, {
        generation: getCurrentHudGeneration(),
      }),
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
    recordOrbRuntimeHealthyProof("Orb authority sync is healthy.", {
      source: "authority",
      notify: false,
    });
    orbAuthorityFailureLogged = false;
    if (orbSafetyState.disconnected || orbSafetyState.degraded) {
      setOrbSafetyState({
        disconnected: false,
        degraded: Boolean(
          overlayRecovery.needed
          || orbSafetyState.pauseHeld
          || orbSafetyState.localStopActive
          || orbSafetyState.remoteSyncStatus !== "current"
        ),
        localError:
          orbSafetyState.pauseHeld || orbSafetyState.localStopActive || orbSafetyState.remoteSyncStatus !== "current"
            ? orbSafetyState.localError
            : "",
        remoteError:
          orbSafetyState.pauseHeld || orbSafetyState.localStopActive || orbSafetyState.remoteSyncStatus !== "current"
            ? orbSafetyState.remoteError
            : "",
      }, { notify: false });
    }

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
      resetOrbOwnershipToSafeFallback("human_returned");
      return;
    }

    const safetySnapshot = getOrbSafetySnapshot();
    if (safetySnapshot.localStopped || safetySnapshot.pauseHeld) {
      resetOrbOwnershipToSafeFallback("safety_hold");
      notifyOverlayState(mainWindow);
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
      resetOrbOwnershipToSafeFallback("authority_idle");
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
    setOrbAuthorityExecutionState(
      claim.command.execution && typeof claim.command.execution === "object"
        ? claim.command.execution
        : buildOrbExecutionSemantics({
            kind: claim.command.kind,
            args: claim.command.args,
            status: "claimed",
          }),
      { notify: false },
    );
    await publishOrbAuthorityState("Francis is executing a queued Orb authority command.");
    await executeOrbAuthorityCommand(claim.command, inputState);
    notifyOverlayState(mainWindow);
  } catch (error) {
    if (isStaleHudGenerationError(error)) {
      return;
    }
    const failureHealth = recordOrbRuntimeFailure(`Orb authority sync failed: ${error instanceof Error ? error.message : String(error)}`, {
      source: "authority",
      notify: false,
      nowMs: Date.now(),
    });
    stabilizeOrbAuthorityLocally(
      "Orb authority degraded. Human control remains primary.",
      {
        disconnected: !getHudState()?.ready,
        degraded: true,
        pauseHold: getOrbSafetySnapshot().pauseHeld,
        remoteSyncStatus: getHudState()?.ready ? "failed" : "pending",
        summary: "Orb authority degraded. Human control remains primary.",
        detail: "Francis released local authority because the authority sync could not be confirmed.",
        localError: "",
        remoteError: error instanceof Error ? error.message : String(error),
      },
    );
    resetOrbOwnershipToSafeFallback("authority_failed");
    if (!orbAuthorityFailureLogged) {
      orbAuthorityFailureLogged = true;
      log("Orb authority loop degraded", {
        status: failureHealth.status,
        source: failureHealth.source,
        nextProbeAtMs: failureHealth.nextProbeAtMs,
        circuitOpenUntilMs: failureHealth.circuitOpenUntilMs,
      });
    }
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
    ollamaState: getOllamaState(),
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
    verifiedExecutable: executableSignature,
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
    runtimeHealth: getOrbRuntimeHealthSnapshot(),
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
  const authority = getOrbAuthoritySnapshot(input);
  const ownership = getOrbOwnershipSnapshot({ input, foregroundWindow: orbForegroundWindow });
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
    runtimeHealth: getOrbRuntimeHealthSnapshot(),
    hud: getHudState(),
    ollama: getOllamaState(),
    ownership,
    lifecycle,
      shortcuts: {
        toggleOverlay: OVERLAY_TOGGLE_SHORTCUT,
        toggleClickThrough: CLICK_THROUGH_TOGGLE_SHORTCUT,
      },
      input,
      authority,
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
  const trayQuitArmed = isTrayQuitArmed();
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
        click: () => applyAlwaysOnTop(getLiveMainWindow(), !overlayState.alwaysOnTop),
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
          restartHudAndRefreshWindow(getLiveMainWindow()).catch((error) => {
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
            executeRetainedStateRepair(getLiveMainWindow());
          } catch (error) {
            log("Tray shell repair failed", error instanceof Error ? error.message : String(error));
          }
        },
      },
      {
        label: "Export Shell State",
        click: () => {
          exportShellState(getLiveMainWindow()).catch((error) => {
            log("Tray shell export failed", error instanceof Error ? error.message : String(error));
          });
        },
      },
      {
        label: "Export Support Bundle",
        click: () => {
          exportSupportBundle(getLiveMainWindow()).catch((error) => {
            log("Tray support bundle export failed", error instanceof Error ? error.message : String(error));
          });
        },
      },
      {
        label: "Import Shell State",
        click: () => {
          importShellState(getLiveMainWindow()).catch((error) => {
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
            restoreLatestRollbackSnapshot(getLiveMainWindow());
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
        label: trayQuitArmed ? "Confirm Quit Francis Overlay" : "Arm Quit Francis Overlay",
        click: () => handleTrayQuitRequest(),
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
  const requestedOrbBehaviorMode = normalizeOrbBehaviorMode(
    overrides.orbBehaviorMode ?? overlayPreferences?.orbBehaviorMode,
  );

  const persistedPreferences = savePreferences(
    app.getPath("userData"),
    {
      ...(overlayPreferences || buildDefaultPreferences(fallbackDisplay)),
      ...overrides,
      targetDisplayId: overrides.targetDisplayId ?? activeDisplay.id ?? fallbackDisplay.id,
      alwaysOnTop: overrides.alwaysOnTop ?? (safeWindow ? safeWindow.isAlwaysOnTop() : overlayState.alwaysOnTop),
      ignoreMouseEvents: overrides.ignoreMouseEvents ?? overlayState.ignoreMouseEvents,
      launchOnStartup: overrides.launchOnStartup ?? launchAtLogin.enabled,
      startupProfile: overrides.startupProfile ?? overlayPreferences?.startupProfile,
      // Persist a calm boot posture, but keep explicit Explore active for the current session.
      orbBehaviorMode: normalizePersistedOrbBehaviorMode(requestedOrbBehaviorMode),
      windowBounds: bounds,
    },
    displays,
    primaryDisplayId,
  );

  overlayPreferences = {
    ...persistedPreferences,
    orbBehaviorMode: requestedOrbBehaviorMode,
  };

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
  const primaryDisplay = getResolvedTargetDisplay(screen.getPrimaryDisplay().id);
  overlayPreferences = buildDefaultPreferences(primaryDisplay);
  if (safeWindow) {
    safeWindow.setBounds(overlayPreferences.windowBounds);
  }
  if (orbWindow && !orbWindow.isDestroyed()) {
    orbWindow.setBounds(getOrbSurfaceBounds());
    reinforceOrbWindowPresence(orbWindow, { reason: "reset_overlay_preferences" });
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
  const targetDisplay = getResolvedTargetDisplay(displayId);
  const nextBounds = buildCenteredBoundsForDisplay(
    getWindowOrPreferenceBounds(safeWindow) || overlayPreferences?.windowBounds || buildDefaultPreferences(targetDisplay).windowBounds,
    targetDisplay,
  );

  if (safeWindow) {
    safeWindow.setBounds(nextBounds);
  }
  if (orbWindow && !orbWindow.isDestroyed()) {
    orbWindow.setBounds(getOrbSurfaceBounds());
    reinforceOrbWindowPresence(orbWindow, { reason: "move_overlay_to_display" });
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
      reinforceOrbWindowPresence(orbWindow, { reason });
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
      <h1>Francis review HUD is not reachable.</h1>
      <p>The desktop overlay shell started correctly, and the Orb can remain resident, but the review HUD at <code>${escapedTarget}</code> did not respond.</p>
      <p>Managed HUD state: <code>${escapedHudMode}</code></p>
      <p>If this shell owns the review runtime, you can retry startup directly from here.</p>
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
          status.textContent = 'Managed review HUD restart completed. Reloading overlay...';
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
  const safeWindow = win && !win.isDestroyed() ? win : null;
  const safeWindows = getShellWindows();
  if (!safeWindows.length && !safeWindow) {
    return overlayState.alwaysOnTop;
  }
  // The Lens shell follows the operator topmost preference, but the Orb stays pinned as a desktop presence object.
  for (const shellWindow of safeWindows) {
    const isOrbShell = shellWindow === orbWindow;
    const nextEnabled = isOrbShell ? true : Boolean(enabled);
    const nextLevel = nextEnabled ? ORB_WINDOW_TOPMOST_LEVEL : "normal";
    shellWindow.setAlwaysOnTop(nextEnabled, nextLevel, isOrbShell && nextEnabled ? ORB_WINDOW_TOPMOST_PRIORITY : 0);
  }
  overlayState.alwaysOnTop = Boolean(enabled);
  overlayPreferences = persistOverlayPreferences(safeWindow, {
    alwaysOnTop: overlayState.alwaysOnTop,
  });
  notifyOverlayState(safeWindow);
  return overlayState.alwaysOnTop;
}

function reinforceOrbWindowPresence(targetWindow = orbWindow, { reason = "" } = {}) {
  if (!targetWindow || targetWindow.isDestroyed()) {
    return;
  }
  const nextBounds = getOrbSurfaceBounds();
  if (!sameBounds(targetWindow.getBounds(), nextBounds)) {
    targetWindow.setBounds(nextBounds);
  }
  targetWindow.setAlwaysOnTop(true, ORB_WINDOW_TOPMOST_LEVEL, ORB_WINDOW_TOPMOST_PRIORITY);
  if (typeof targetWindow.setVisibleOnAllWorkspaces === "function") {
    targetWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  }
  if (typeof targetWindow.setSkipTaskbar === "function") {
    targetWindow.setSkipTaskbar(true);
  }
  if (typeof targetWindow.setFocusable === "function") {
    targetWindow.setFocusable(!orbInputState.ignoreMouseEvents);
  }
  if (typeof targetWindow.moveTop === "function") {
    try {
      targetWindow.moveTop();
    } catch {
      // Older Electron/Windows builds may not expose moveTop reliably.
    }
  }
  if (reason && !targetWindow.isVisible()) {
    log("Reinforced orb desktop authority while hidden", { reason, bounds: nextBounds });
  }
}

function stopOrbSurfaceAuthorityLoop() {
  if (orbSurfaceAuthorityTimer) {
    clearInterval(orbSurfaceAuthorityTimer);
    orbSurfaceAuthorityTimer = null;
  }
}

function ensureOrbSurfaceAuthorityLoop() {
  stopOrbSurfaceAuthorityLoop();
  orbSurfaceAuthorityTimer = setInterval(() => {
    if (!orbWindow || orbWindow.isDestroyed() || !orbWindow.isVisible()) {
      return;
    }
    reinforceOrbWindowPresence(orbWindow, { reason: "interval_reassert" });
  }, ORB_WINDOW_REINFORCE_INTERVAL_MS);
  if (typeof orbSurfaceAuthorityTimer?.unref === "function") {
    orbSurfaceAuthorityTimer.unref();
  }
}

function applyIgnoreMouseEvents(win, ignore) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  overlayState.ignoreMouseEvents = Boolean(ignore);
  // Forward mouse-move events while click-through is enabled so the overlay can still react visually.
  if (safeWindow) {
    safeWindow.setIgnoreMouseEvents(
      overlayState.ignoreMouseEvents,
      overlayState.ignoreMouseEvents ? { forward: true } : undefined,
    );
  }
  overlayPreferences = persistOverlayPreferences(safeWindow, {
    ignoreMouseEvents: overlayState.ignoreMouseEvents,
  });
  notifyOverlayState(safeWindow);
  return overlayState.ignoreMouseEvents;
}

function applyOrbIgnoreMouseEvents(ignore) {
  orbInputState.ignoreMouseEvents = Boolean(ignore);
  if (!orbWindow || orbWindow.isDestroyed()) {
    return orbInputState.ignoreMouseEvents;
  }
  if (typeof orbWindow.setFocusable === "function") {
    orbWindow.setFocusable(!orbInputState.ignoreMouseEvents);
  }
  orbWindow.setIgnoreMouseEvents(
    orbInputState.ignoreMouseEvents,
    orbInputState.ignoreMouseEvents ? { forward: true } : undefined,
  );
  reinforceOrbWindowPresence(orbWindow);
  if (orbInputState.ignoreMouseEvents && typeof orbWindow.blur === "function") {
    orbWindow.blur();
  }
  notifyOverlayState(mainWindow);
  return orbInputState.ignoreMouseEvents;
}

function getOrbOwnershipSnapshot({ input = null, foregroundWindow = null } = {}) {
  return buildOrbOwnershipState({
    requested: orbOwnershipRequest.mode,
    authority: getOrbAuthoritySnapshot(input),
    runtimeHealth: getOrbRuntimeHealthSnapshot(),
    governor: orbOwnershipGovernor,
    captureSuspended: Boolean(captureSuspensionState.active),
    lensVisible: Boolean(mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()),
    overlayIgnoreMouseEvents: overlayState.ignoreMouseEvents,
    orbIgnoreMouseEvents: orbInputState.ignoreMouseEvents,
    foregroundWindow,
    shellPid: process.pid,
  });
}

function reconcileOrbOwnership(reason = "", { notify = true } = {}) {
  const snapshot = getOrbOwnershipSnapshot();
  const nextIgnoreMouseEvents = Boolean(snapshot.shouldIgnoreOrbMouseEvents);
  if (orbInputState.ignoreMouseEvents !== nextIgnoreMouseEvents) {
    applyOrbIgnoreMouseEvents(nextIgnoreMouseEvents);
  } else if (notify) {
    notifyOverlayState(mainWindow);
  }
  return {
    ...snapshot,
    requestedReason: String(reason || orbOwnershipRequest.reason || "").trim(),
  };
}

function setOrbOwnershipMode(mode, reason = "", { notify = true } = {}) {
  const normalizedMode = normalizeOrbOwnershipRequest(mode);
  const normalizedReason = String(reason || "").trim();
  let overrideCleared = false;
  if (
    normalizedMode === ORB_OWNERSHIP_STATES.INTERACTABLE_ORB
    && shouldClearOrbOwnershipUserOverrideForReason(normalizedReason)
  ) {
    const nextGovernor = clearOrbOwnershipUserOverride(orbOwnershipGovernor, { nowMs: Date.now() });
    overrideCleared =
      nextGovernor.userOverrideUntilMs !== orbOwnershipGovernor.userOverrideUntilMs
      || nextGovernor.userOverrideReason !== orbOwnershipGovernor.userOverrideReason;
    orbOwnershipGovernor = nextGovernor;
  }
  const unchanged =
    orbOwnershipRequest.mode === normalizedMode
    && orbOwnershipRequest.reason === normalizedReason;
  if (!unchanged) {
    orbOwnershipRequest = {
      mode: normalizedMode,
      reason: normalizedReason,
      updatedAtMs: Date.now(),
    };
  }
  const snapshot = reconcileOrbOwnership(normalizedReason, { notify: notify && (!unchanged || overrideCleared) });
  return {
    ...snapshot,
    requestUnchanged: unchanged,
  };
}

function resetOrbOwnershipToSafeFallback(reason = "", { notify = true } = {}) {
  let overrideArmed = false;
  if (isOrbOwnershipUserOverrideReason(reason)) {
    const nextGovernor = armOrbOwnershipUserOverride(orbOwnershipGovernor, {
      reason,
      nowMs: Date.now(),
    });
    overrideArmed =
      nextGovernor.userOverrideUntilMs !== orbOwnershipGovernor.userOverrideUntilMs
      || nextGovernor.userOverrideReason !== orbOwnershipGovernor.userOverrideReason;
    orbOwnershipGovernor = nextGovernor;
  }
  const snapshot = setOrbOwnershipMode(ORB_OWNERSHIP_STATES.PASS_THROUGH, reason || "safe_fallback", { notify });
  if (notify && overrideArmed && snapshot.requestUnchanged) {
    notifyOverlayState(mainWindow);
  }
  return snapshot;
}

async function fetchHudJson(route, init = {}, {
  generation = getCurrentHudGeneration(),
  channel = "",
  ignoreStaleGeneration = true,
} = {}) {
  const target = new URL(String(route || "/"), HUD_URL).toString();
  try {
    const response = await fetch(target, init);
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    const currentGeneration = getCurrentHudGeneration();
    if (ignoreStaleGeneration && isStaleHudGeneration(hudRecoveryState, generation)) {
      const staleError = createStaleHudGenerationError(route, generation, currentGeneration);
      log("Ignored stale HUD response", {
        route: String(route || "/"),
        requestGeneration: generation,
        currentGeneration,
      });
      throw staleError;
    }
    if (!response.ok) {
      const classified = classifyHudFetchFailure(null, response.status);
      if (channel) {
        markHudEndpointFailure(channel, {
          generation,
          kind: classified.kind,
          message: String(payload?.detail || payload?.error || `${response.status} ${response.statusText}`),
          statusCode: Number(response.status || 0),
        });
      }
      throw new Error(String(payload?.detail || payload?.error || `${response.status} ${response.statusText}`));
    }
    if (channel) {
      markHudEndpointSuccess(channel, { generation });
    }
    return payload;
  } catch (error) {
    if (!isStaleHudGenerationError(error) && channel) {
      const classified = classifyHudFetchFailure(error, 0);
      markHudEndpointFailure(channel, {
        generation,
        kind: classified.kind,
        message: classified.message,
        statusCode: classified.statusCode,
      });
    }
    throw error;
  }
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
    const [frame, input, foregroundWindow, accessibility] = await Promise.all([
      capturePerceptionFrame(),
      Promise.resolve(getOverlayInputState()),
      getCachedForegroundWindowInfo(),
      getCachedFocusedAccessibilityInfo(),
    ]);
    const environment = buildOrbEnvironmentGrounding({
      cursorScreen: input?.cursorScreen || null,
      displayBounds: input?.displayBounds || null,
      foregroundWindow,
      accessibility,
      targetStability: input?.targetStability || null,
      focusAttached: Boolean(frame?.focusDataUrl),
      frameAttached: Boolean(frame?.dataUrl),
      samples: orbPerceptionEnvironmentSamples,
    });
    appendOrbPerceptionEnvironmentSample(environment?.sample || null);
    if (
      shouldResetOrbOwnershipForForeground({
        ownership: getOrbOwnershipSnapshot({ input, foregroundWindow }),
        foregroundWindow,
        shellPid: process.pid,
      })
    ) {
      resetOrbOwnershipToSafeFallback("foreground_window_changed");
    }
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
        accessibility: {
          available: Boolean(accessibility?.available),
          attached: Boolean(accessibility?.attached),
          status: String(accessibility?.status || "").trim().toLowerCase() || "unavailable",
          label: String(accessibility?.label || accessibility?.name || "").trim(),
          name: String(accessibility?.name || "").trim(),
          automation_id: String(accessibility?.automationId || "").trim(),
          control_type: String(accessibility?.controlType || "").trim().toLowerCase(),
          localized_control_type: String(accessibility?.localizedControlType || "").trim(),
          class_name: String(accessibility?.className || "").trim(),
          process_id: Number(accessibility?.processId || 0) || null,
          has_keyboard_focus: Boolean(accessibility?.hasKeyboardFocus),
          enabled: Boolean(accessibility?.enabled),
          offscreen: Boolean(accessibility?.offscreen),
          bounds: {
            x: Number.isFinite(accessibility?.bounds?.x) ? Math.round(accessibility.bounds.x) : null,
            y: Number.isFinite(accessibility?.bounds?.y) ? Math.round(accessibility.bounds.y) : null,
            width: Number(accessibility?.bounds?.width || 0),
            height: Number(accessibility?.bounds?.height || 0),
          },
        },
        environment: {
          source_priority: Array.isArray(environment?.sourcePriority) ? environment.sourcePriority : [],
          primary_source: String(environment?.primarySource || "").trim(),
          sources: environment?.sources && typeof environment.sources === "object" ? environment.sources : {},
          grounding: environment?.grounding && typeof environment.grounding === "object" ? environment.grounding : {},
        },
      }),
    }, {
      generation: getCurrentHudGeneration(),
      channel: "perception",
    });
    orbPerceptionErrorLogged = false;
    return payload;
  } catch (error) {
    if (isStaleHudGenerationError(error)) {
      return null;
    }
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

function stopCaptureRecoveryLoop() {
  if (captureRecoveryTimer !== null) {
    clearInterval(captureRecoveryTimer);
    captureRecoveryTimer = null;
  }
}

function ensureCaptureRecoveryLoop() {
  if (captureRecoveryTimer !== null) {
    return;
  }
  captureRecoveryTimer = setInterval(() => {
    void reconcileCaptureRecovery();
  }, 350);
}

function suspendOverlayForCapture(foregroundWindow) {
  if (captureSuspensionState.active) {
    return;
  }
  const lensVisible = Boolean(mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible());
  const orbVisible = Boolean(orbWindow && !orbWindow.isDestroyed() && orbWindow.isVisible());
  if (!lensVisible && !orbVisible) {
    return;
  }

  captureSuspensionState = {
    active: true,
    reason: String(foregroundWindow?.process || foregroundWindow?.title || "capture-mode"),
    lensVisible,
    orbVisible,
    overlayIgnoreMouseEvents: overlayState.ignoreMouseEvents,
    orbIgnoreMouseEvents: orbInputState.ignoreMouseEvents,
    overlayAlwaysOnTop: overlayState.alwaysOnTop,
  };

  resetOrbOwnershipToSafeFallback("capture_mode");
  if (mainWindow && !mainWindow.isDestroyed()) {
    applyIgnoreMouseEvents(mainWindow, true);
    mainWindow.hide();
  }
  applyOrbIgnoreMouseEvents(true);
  if (orbWindow && !orbWindow.isDestroyed()) {
    orbWindow.hide();
  }
  log("Suspended overlay for capture mode", {
    process: foregroundWindow?.process || "",
    title: foregroundWindow?.title || "",
  });
  ensureCaptureRecoveryLoop();
}

function restoreOverlayAfterCapture() {
  if (!captureSuspensionState.active) {
    return;
  }
  const restore = { ...captureSuspensionState };
  captureSuspensionState = {
    active: false,
    reason: "",
    lensVisible: false,
    orbVisible: false,
    overlayIgnoreMouseEvents: false,
    orbIgnoreMouseEvents: true,
    overlayAlwaysOnTop: true,
  };
  stopCaptureRecoveryLoop();

  if (mainWindow && !mainWindow.isDestroyed()) {
    applyAlwaysOnTop(mainWindow, restore.overlayAlwaysOnTop);
    applyIgnoreMouseEvents(mainWindow, restore.overlayIgnoreMouseEvents);
    if (restore.lensVisible) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.showInactive();
    }
  }

  applyOrbIgnoreMouseEvents(restore.orbIgnoreMouseEvents);
  orbOwnershipRequest = {
    mode: restore.orbIgnoreMouseEvents ? ORB_OWNERSHIP_STATES.PASS_THROUGH : ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
    reason: "capture_restore",
    updatedAtMs: Date.now(),
  };
  if (restore.orbVisible && orbWindow && !orbWindow.isDestroyed()) {
    if (orbWindow.isMinimized()) {
      orbWindow.restore();
    }
    orbWindow.showInactive();
    reinforceOrbWindowPresence(orbWindow);
  }
  log("Restored overlay after capture mode");
  reconcileOrbOwnership("capture_restore");
  notifyOverlayState(mainWindow);
}

async function checkForCaptureActivation() {
  if (captureCheckPending || captureSuspensionState.active) {
    return;
  }
  const shellVisible = Boolean(
    (mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()) ||
    (orbWindow && !orbWindow.isDestroyed() && orbWindow.isVisible()),
  );
  if (!shellVisible) {
    return;
  }
  captureCheckPending = true;
  try {
    const foregroundWindow = await getForegroundWindowInfo({ timeoutMs: 700 });
    if (isCaptureForegroundWindow(foregroundWindow)) {
      suspendOverlayForCapture(foregroundWindow);
    }
  } finally {
    captureCheckPending = false;
  }
}

async function reconcileCaptureRecovery() {
  if (!captureSuspensionState.active || captureCheckPending) {
    return;
  }
  captureCheckPending = true;
  try {
    const foregroundWindow = await getForegroundWindowInfo({ timeoutMs: 700 });
    if (!isCaptureForegroundWindow(foregroundWindow)) {
      restoreOverlayAfterCapture();
    }
  } finally {
    captureCheckPending = false;
  }
}

function showLensWindow() {
  if (!REVIEW_HUD_WINDOW_ENABLED) {
    const existing = getLiveMainWindow();
    if (existing) {
      existing.hide();
    }
    lensInteractionRestoreIgnoreMouseEvents = null;
    resetOrbOwnershipToSafeFallback("review_window_disabled");
    notifyOverlayState(existing);
    return getOverlayState(existing);
  }
  const hadWindow = Boolean(mainWindow && !mainWindow.isDestroyed());
  const win = hadWindow ? mainWindow : createMainWindow({ showOnReady: true });
  if (lensInteractionRestoreIgnoreMouseEvents === null) {
    lensInteractionRestoreIgnoreMouseEvents = Boolean(overlayState.ignoreMouseEvents);
  }
  if (overlayState.ignoreMouseEvents) {
    applyIgnoreMouseEvents(win, false);
  }
  resetOrbOwnershipToSafeFallback("lens_open");
  if (!hadWindow) {
    mainWindow = win;
    notifyOverlayState(win);
    return getOverlayState(win);
  }
  if (win.isMinimized()) {
    win.restore();
  }
  win.showInactive();
  notifyOverlayState(win);
  return getOverlayState(win);
}

function hideLensWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return getOverlayState(mainWindow);
  }
  const win = mainWindow;
  win.hide();
  if (lensInteractionRestoreIgnoreMouseEvents !== null) {
    applyIgnoreMouseEvents(win, Boolean(lensInteractionRestoreIgnoreMouseEvents));
    lensInteractionRestoreIgnoreMouseEvents = null;
  }
  resetOrbOwnershipToSafeFallback("lens_hidden");
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
  reinforceOrbWindowPresence(orbWindow);
  notifyOverlayState(mainWindow);
  return getOverlayState(mainWindow);
}

function shouldAllowWindowClose() {
  return Boolean(quitAfterHudShutdown);
}

function hideAllWindows() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
  }
  if (orbWindow && !orbWindow.isDestroyed()) {
    orbWindow.hide();
  }
  lensInteractionRestoreIgnoreMouseEvents = null;
  resetOrbOwnershipToSafeFallback("hide_all_windows");
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
  hudRecoveryState = finishHudRecoveryAttempt(hudRecoveryState, {
    recoveryId: hudRecoveryState?.recovery?.id || 0,
    success: true,
  });
  setOverlayRecovery({ needed: false, status: "nominal", message: "", lastExitReason: "" });
  recordOrbRuntimeHealthyProof("HUD recovery completed. Waiting for stable health proofs.", {
    source: "hud",
    notify: false,
  });
}

function scheduleHudRecovery(reason) {
  if (!hudRuntime || quitAfterHudShutdown) {
    return;
  }
  const plan = planHudRecovery(hudRecoveryState, {
    reason,
    maxAttempts: HUD_MAX_RECOVERY_ATTEMPTS,
  });
  hudRecoveryState = plan.state;
  if (!plan.scheduled) {
    const suppressionKey = `${reason}|${plan.recoveryId}|${plan.duplicate ? "duplicate" : plan.exhausted ? "exhausted" : "suppressed"}`;
    if (hudLastRecoverySuppressionKey !== suppressionKey) {
      hudLastRecoverySuppressionKey = suppressionKey;
      log("Suppressed duplicate managed HUD recovery scheduling", buildHudRecoveryDiagnostics({
        reason,
        duplicate: Boolean(plan.duplicate),
        exhausted: Boolean(plan.exhausted),
      }));
    }
    return;
  }
  hudRecoveryAttempts += 1;
  const recoveryDelayMs = getOrbRuntimeRetryDelayMs(hudRecoveryAttempts, {
    baseMs: HUD_RECOVERY_BASE_DELAY_MS,
    maxMs: HUD_RECOVERY_MAX_DELAY_MS,
  });
  log("Scheduling managed HUD recovery", {
    ...buildHudRecoveryDiagnostics({
      reason,
      attempt: hudRecoveryAttempts,
      maxAttempts: HUD_MAX_RECOVERY_ATTEMPTS,
      previousHudPidAliveAtSchedule: Boolean(hudRecoveryState?.childAlive),
      recoveryDelayMs,
    }),
  });
  setOverlayRecovery({
    needed: true,
    status: "recovering",
    message: "Managed HUD exited unexpectedly. Restarting the local runtime.",
    lastExitReason: reason,
  });
  markOrbRuntimeRecovering("Managed HUD recovery is in progress. Waiting for stable health proofs.", {
    source: "hud",
    notify: false,
  });
  stabilizeOrbAuthorityLocally(
    "Managed HUD recovery is in progress. Human control remains primary.",
    {
      disconnected: true,
      degraded: true,
      pauseHold: getOrbSafetySnapshot().pauseHeld,
      remoteSyncStatus: "pending",
      summary: "HUD disconnected. Human control remains primary.",
      detail: "Francis dropped local authority while the managed HUD runtime recovers.",
      notify: false,
    },
  );
  notifyOverlayState(mainWindow);
  hudRecoveryTimer = setTimeout(async () => {
    hudRecoveryTimer = null;
    const recoveryId = plan.recoveryId;
    const started = beginHudRecoveryAttempt(hudRecoveryState, { recoveryId });
    hudRecoveryState = started.state;
    if (!started.started) {
      log("Ignored stale managed HUD recovery timer", buildHudRecoveryDiagnostics({
        reason,
        recoveryId,
      }));
      return;
    }
    try {
      await restartHudAndRefreshWindow(mainWindow, { recoveryId, reason });
      clearHudRecovery();
      notifyOverlayState(mainWindow);
    } catch (error) {
      hudRecoveryState = finishHudRecoveryAttempt(hudRecoveryState, {
        recoveryId,
        success: false,
      });
      log("Managed HUD recovery failed", error instanceof Error ? error.message : String(error));
      setOverlayRecovery({
        needed: true,
        status: "failed",
        message: error instanceof Error ? error.message : String(error),
        lastExitReason: reason,
      });
      notifyOverlayState(mainWindow);
    }
  }, recoveryDelayMs);
}

async function reconcileHudHealth() {
  if (hudHealthCheckPending || !hudRuntime || quitAfterHudShutdown) {
    return;
  }

  const hudState = getHudState();
  const recoveryReason = getScheduledHudRecoveryReason(hudState);
  if (recoveryReason) {
    scheduleHudRecovery(recoveryReason);
    return;
  }

  if (!hudState?.ready) {
    return;
  }

  hudHealthCheckPending = true;
  try {
    const generation = getCurrentHudGeneration();
    const probe = await probeHudReachability(HUD_URL, HUD_HEALTH_TIMEOUT_MS);
    if (probe.ok) {
      hudHealthFailureCount = 0;
      markHudEndpointSuccess("health", { generation });
      recordOrbRuntimeHealthyProof("HUD health probe passed. Waiting for consecutive healthy proofs.", {
        source: "hud",
        notify: false,
      });
      if (orbRuntimeHealth.status === "nominal" && overlayRecovery.needed) {
        clearHudRecovery();
      } else {
        notifyOverlayState(mainWindow);
      }
      return;
    }

    hudHealthFailureCount += 1;
    markHudEndpointFailure("health", {
      generation,
      kind: probe.error?.kind || "unknown",
      message: probe.error?.message || "HUD health probe failed.",
      statusCode: Number(probe.statusCode || 0),
    });
    const failureHealth = recordOrbRuntimeFailure("HUD health probe failed.", {
      source: "hud",
      notify: false,
    });
    if (hudHealthFailureCount < HUD_HEALTH_FAILURES_BEFORE_RECOVERY) {
      if (failureHealth.status === "degraded") {
        setOverlayRecovery({
          needed: true,
          status: "degraded",
          message: "The local operator runtime is missing recent healthy HUD proofs.",
          lastExitReason: "hud-health-missed",
        });
      }
      log("HUD probe missed while the shell still considered it ready", {
        ...buildHudRecoveryDiagnostics({
          timeoutMs: HUD_HEALTH_TIMEOUT_MS,
          failureCount: hudHealthFailureCount,
          failureThreshold: HUD_HEALTH_FAILURES_BEFORE_RECOVERY,
          probe,
        }),
      });
      notifyOverlayState(mainWindow);
      return;
    }

    log("HUD runtime became unreachable while the shell still considered it ready", {
      ...buildHudRecoveryDiagnostics({
        timeoutMs: HUD_HEALTH_TIMEOUT_MS,
        failureCount: hudHealthFailureCount,
        failureThreshold: HUD_HEALTH_FAILURES_BEFORE_RECOVERY,
        probe,
      }),
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
    stabilizeOrbAuthorityLocally(
      "The HUD is unreachable. Human control remains primary.",
      {
        disconnected: true,
        degraded: true,
        pauseHold: getOrbSafetySnapshot().pauseHeld,
        remoteSyncStatus: "pending",
        summary: "HUD disconnected. Human control remains primary.",
        detail: "Francis dropped local authority because the HUD is unreachable.",
        notify: false,
      },
    );
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
  hudHealthFailureCount = 0;
}

function clearOllamaRecovery() {
  if (ollamaRecoveryTimer) {
    clearTimeout(ollamaRecoveryTimer);
    ollamaRecoveryTimer = null;
  }
  ollamaRecoveryAttempts = 0;
}

function scheduleOllamaRecovery(reason) {
  if (!ollamaRuntime || quitAfterHudShutdown) {
    return;
  }
  if (ollamaRecoveryTimer || ollamaRecoveryAttempts >= OLLAMA_MAX_RECOVERY_ATTEMPTS) {
    return;
  }
  ollamaRecoveryAttempts += 1;
  log("Scheduling Ollama runtime recovery", {
    reason,
    attempt: ollamaRecoveryAttempts,
    maxAttempts: OLLAMA_MAX_RECOVERY_ATTEMPTS,
  });
  notifyOverlayState(mainWindow);
  ollamaRecoveryTimer = setTimeout(async () => {
    ollamaRecoveryTimer = null;
    try {
      await ollamaRuntime.restart();
      clearOllamaRecovery();
      notifyOverlayState(mainWindow);
    } catch (error) {
      log("Ollama runtime recovery failed", error instanceof Error ? error.message : String(error));
      notifyOverlayState(mainWindow);
    }
  }, 1500);
}

async function reconcileOllamaHealth() {
  if (ollamaHealthCheckPending || !ollamaRuntime || quitAfterHudShutdown) {
    return;
  }

  const ollamaState = getOllamaState();
  if (ollamaState?.restartSuggested) {
    scheduleOllamaRecovery(`ollama-${ollamaState.mode || "crashed"}`);
    return;
  }

  if (!ollamaState?.ready) {
    return;
  }

  ollamaHealthCheckPending = true;
  try {
    const reachable = await isOllamaReachable(ollamaState.serviceUrl || OLLAMA_URL, 1500);
    if (reachable !== null) {
      return;
    }

    log("Ollama runtime became unreachable while the shell still considered it ready", {
      managed: Boolean(ollamaState?.managed),
      mode: ollamaState?.mode || null,
      pid: ollamaState?.pid || null,
      healthUrl: ollamaState?.healthUrl || null,
    });
    scheduleOllamaRecovery("ollama-unreachable");
  } finally {
    ollamaHealthCheckPending = false;
  }
}

function ensureOllamaHealthMonitor() {
  if (ollamaHealthTimer !== null) {
    return;
  }
  ollamaHealthTimer = setInterval(() => {
    void reconcileOllamaHealth();
  }, OLLAMA_HEALTH_RECONCILE_INTERVAL_MS);
  void reconcileOllamaHealth();
}

function stopOllamaHealthMonitor() {
  if (ollamaHealthTimer !== null) {
    clearInterval(ollamaHealthTimer);
    ollamaHealthTimer = null;
  }
  ollamaHealthCheckPending = false;
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

function delayMs(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, Math.max(0, Number(ms) || 0));
  });
}

async function readOrbVerificationState(win) {
  if (!win || win.isDestroyed()) {
    return null;
  }
  try {
    return await win.webContents.executeJavaScript(
      `(() => {
        const root = document.getElementById("orb-render-root");
        const overlay = document.getElementById("orb-overlay");
        const rect = root ? root.getBoundingClientRect() : null;
        return {
          locationHref: String(window.location.href || ""),
          bodyBoot: String(document.body?.dataset?.boot || ""),
          bodyOrbSurface: String(document.body?.dataset?.orbSurface || ""),
          rendererDataset: root?.dataset ? { ...root.dataset } : null,
          overlayDataset: overlay?.dataset ? { ...overlay.dataset } : null,
          rect: rect ? { x: rect.x, y: rect.y, width: rect.width, height: rect.height } : null,
          transform: root?.style?.transform || "",
          opacity: root?.style?.opacity || "",
          className: root?.className || "",
          title: String(document.title || ""),
          hasOpenOrbCommandMenu: typeof openOrbCommandMenu === "function",
          hasSetMenuOpen: typeof setMenuOpen === "function",
          hasCurrentOrb: typeof currentOrb === "object" && Boolean(currentOrb),
          hasBodyPresence: typeof orbBodyPresence === "object" && Boolean(orbBodyPresence),
          animationFrameActive: typeof orbAnimationFrame === "number",
        };
      })()`,
      true,
    );
  } catch {
    return null;
  }
}

async function waitForOrbVerificationReady(win, timeoutMs = 30000) {
  const deadline = Date.now() + Math.max(2000, Number(timeoutMs) || 18000);
  while (Date.now() < deadline) {
    if (!win || win.isDestroyed()) {
      return false;
    }
    try {
      const ready = await win.webContents.executeJavaScript(
        `(() => {
          const root = document.getElementById("orb-render-root");
          if (!root || typeof renderOverlayDock !== "function" || typeof renderOrbPresentation !== "function") {
            return false;
          }
          const boot = String(document.body?.dataset?.boot || "");
          const renderer = String(root.dataset?.renderer || "");
          const rect = root.getBoundingClientRect();
          const hasSignals =
            typeof currentOrb === "object"
            && currentOrb
            && typeof orbBodyPresence === "object"
            && orbBodyPresence
            && typeof orbAnimationFrame === "number";
          const visibleRect =
            Number.isFinite(rect.width)
            && Number.isFinite(rect.height)
            && rect.width >= 48
            && rect.height >= 48
            && rect.x > -900
            && rect.y > -900;
          return boot === "ready" && renderer === "live" && visibleRect && hasSignals;
        })()`,
        true,
      );
      if (ready) {
        return true;
      }
    } catch {}
    await delayMs(180);
  }
  return false;
}

async function writeOrbVerificationCapture(win, label) {
  if (!win || win.isDestroyed()) {
    return "";
  }
  fs.mkdirSync(ORB_VERIFICATION_CAPTURE_DIR, { recursive: true });
  const image = await win.webContents.capturePage();
  const filePath = path.join(
    ORB_VERIFICATION_CAPTURE_DIR,
    `francis-orb-${String(label || "capture").trim().toLowerCase().replace(/[^a-z0-9._-]+/g, "-")}.png`,
  );
  fs.writeFileSync(filePath, image.toPNG());
  log("Captured orb verification snapshot", { label, filePath });
  return filePath;
}

async function captureOrbShellVerificationSnapshots(win) {
  await win.webContents.executeJavaScript(
    `(() => {
      document.documentElement.style.background = "#000000";
      document.body.style.background = "#000000";
      document.body.dataset.menuOpen = "false";
      if (typeof setMenuOpen === "function") {
        setMenuOpen(false);
      }
      return Boolean(orbApi && orbApi.orb);
    })()`,
    true,
  );
  await delayMs(260);
  await writeOrbVerificationCapture(win, "idle");

  await win.webContents.executeJavaScript(
    `(() => {
      if (orbApi?.orb && typeof orbApi.orb.setSignals === "function") {
        orbApi.orb.setSignals({ state: "attentive", speakingAmplitude: 0.08, confidence: 0.58 });
      }
      return true;
    })()`,
    true,
  );
  await delayMs(220);
  await writeOrbVerificationCapture(win, "attentive");

  await win.webContents.executeJavaScript(
    `(() => {
      if (orbApi?.orb && typeof orbApi.orb.setSignals === "function") {
        orbApi.orb.setSignals({ state: "investigate", confidence: 0.76 });
      }
      return true;
    })()`,
    true,
  );
  await delayMs(220);
  await writeOrbVerificationCapture(win, "investigate");

  await win.webContents.executeJavaScript(
    `(() => {
      if (orbApi?.orb && typeof orbApi.orb.setSignals === "function") {
        orbApi.orb.setSignals({ state: "target_lock", confidence: 0.9, actionStrength: 0.56 });
      }
      return true;
    })()`,
    true,
  );
  await delayMs(220);
  await writeOrbVerificationCapture(win, "lock");

  await win.webContents.executeJavaScript(
    `(() => {
      if (orbApi?.orb && typeof orbApi.orb.setSignals === "function") {
        orbApi.orb.setSignals({ state: "paused", confidence: 0.22 });
      }
      return true;
    })()`,
    true,
  );
  await delayMs(220);
  await writeOrbVerificationCapture(win, "paused");

  await win.webContents.executeJavaScript(
    `(() => {
      if (orbApi?.orb && typeof orbApi.orb.setSignals === "function") {
        orbApi.orb.setSignals({ state: "interrupted", confidence: 0.18 });
      }
      return true;
    })()`,
    true,
  );
  await delayMs(220);
  await writeOrbVerificationCapture(win, "yield");

  await win.webContents.executeJavaScript(
    `(() => {
      document.documentElement.style.background = "transparent";
      document.body.style.background = "transparent";
      if (typeof setMenuOpen === "function") {
        setMenuOpen(false);
      }
      if (typeof syncOrb === "function") {
        syncOrb().catch(() => {});
      }
      return true;
    })()`,
    true,
  );
}

async function maybeCaptureOrbVerificationSnapshots(win) {
  if (!ORB_VERIFICATION_CAPTURE_ENABLED || !win || win.isDestroyed()) {
    return;
  }
  try {
    const ready = await waitForOrbVerificationReady(win);
    fs.mkdirSync(ORB_VERIFICATION_CAPTURE_DIR, { recursive: true });
    if (!ready) {
      const proofState = await readOrbVerificationState(win);
      if (proofState) {
        fs.writeFileSync(
          path.join(ORB_VERIFICATION_CAPTURE_DIR, "proof-state.json"),
          `${JSON.stringify(proofState, null, 2)}\n`,
          "utf8",
        );
      }
      log("Skipped orb verification snapshots because the orb window never reported ready state");
      fs.writeFileSync(
        path.join(ORB_VERIFICATION_CAPTURE_DIR, "capture-skipped.txt"),
        "Orb verification snapshots skipped because the orb window never reached ready state.\n",
        "utf8",
      );
      return;
    }
    const proofState = await readOrbVerificationState(win);
    if (proofState) {
      fs.writeFileSync(
        path.join(ORB_VERIFICATION_CAPTURE_DIR, "proof-state.json"),
        `${JSON.stringify(proofState, null, 2)}\n`,
        "utf8",
      );
    }
    const shellCaptureMode = await win.webContents.executeJavaScript(
      `(() => Boolean(typeof setMenuOpen === "function" && typeof syncOrb === "function" && typeof openOrbCommandMenu !== "function"))()`,
      true,
    ).catch(() => false);
    if (shellCaptureMode) {
      await captureOrbShellVerificationSnapshots(win);
      return;
    }
    await win.webContents.executeJavaScript(
      `(() => {
        document.documentElement.style.background = "#000000";
        document.body.style.background = "#000000";
        if (typeof closeOrbCommandMenu === "function") {
          closeOrbCommandMenu();
        }
        if (typeof orbHoverInteraction === "object" && orbHoverInteraction) {
          orbHoverInteraction.inside = false;
        }
        if (typeof orbCommandMenu === "object" && orbCommandMenu) {
          orbCommandMenu.open = false;
        }
        document.body.dataset.orbMenu = "closed";
        return true;
      })()`,
      true,
    );
    await delayMs(260);

    await win.webContents.executeJavaScript(
      `(() => {
        const root = document.getElementById("orb-render-root");
        const size = Number(root?.clientWidth || 160);
        const fallback = typeof getOrbResidentHomeTarget === "function"
          ? getOrbResidentHomeTarget(size)
          : { x: window.innerWidth - 150, y: window.innerHeight - 150 };
        if (typeof ORB_BODY_STATES !== "object" || !ORB_BODY_STATES || typeof renderOrbPresentation !== "function") {
          return false;
        }
        orbBodyPresence = {
          ...(orbBodyPresence || {}),
          state: ORB_BODY_STATES.IDLE_ANCHORED,
          desiredPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          perchPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          targetPoint: null,
          anchorLabel: "resident perch",
          motionLabel: "quiet anchor",
          summary: "Quiet, compact, and resting in place.",
          scale: 0.98,
          stiffness: 0.16,
          damping: 0.84,
          holdPerch: true,
          taskbarIntent: false,
        };
        if (typeof orbMotion === "object" && orbMotion) {
          orbMotion.x = Number(fallback.x);
          orbMotion.y = Number(fallback.y);
          orbMotion.targetX = Number(fallback.x);
          orbMotion.targetY = Number(fallback.y);
          orbMotion.vx = 0;
          orbMotion.vy = 0;
        }
        if (root) {
          root.style.width = \`\${size}px\`;
          root.style.height = \`\${size}px\`;
          root.dataset.bodyState = ORB_BODY_STATES.IDLE_ANCHORED;
        }
        renderOrbPresentation();
        if (typeof applyOrbSignals === "function") {
          applyOrbSignals();
        }
        return true;
      })()`,
      true,
    );
    await delayMs(220);
    await writeOrbVerificationCapture(win, "idle");

    await win.webContents.executeJavaScript(
      `(() => {
        const root = document.getElementById("orb-render-root");
        const size = Number(root?.clientWidth || 160);
        const fallback = typeof getOrbResidentHomeTarget === "function"
          ? getOrbResidentHomeTarget(size)
          : { x: window.innerWidth - 150, y: window.innerHeight - 150 };
        if (typeof ORB_BODY_STATES !== "object" || !ORB_BODY_STATES || typeof renderOrbPresentation !== "function") {
          return false;
        }
        orbBodyPresence = {
          ...(orbBodyPresence || {}),
          state: ORB_BODY_STATES.ATTENTIVE,
          desiredPoint: { x: Number(fallback.x) - 8, y: Number(fallback.y) - 4 },
          perchPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          targetPoint: { x: Number(fallback.x) + 48, y: Number(fallback.y) - 18 },
          anchorLabel: "resident perch",
          motionLabel: "quiet wake",
          summary: "Waking slightly without committing to action.",
          scale: 0.99,
          stiffness: 0.18,
          damping: 0.82,
          holdPerch: false,
          taskbarIntent: false,
        };
        if (typeof orbMotion === "object" && orbMotion) {
          orbMotion.x = Number(fallback.x) - 8;
          orbMotion.y = Number(fallback.y) - 4;
          orbMotion.targetX = Number(fallback.x) - 8;
          orbMotion.targetY = Number(fallback.y) - 4;
          orbMotion.vx = 0;
          orbMotion.vy = 0;
        }
        if (root) {
          root.style.width = \`\${size}px\`;
          root.style.height = \`\${size}px\`;
          root.dataset.bodyState = ORB_BODY_STATES.ATTENTIVE;
        }
        renderOrbPresentation();
        if (typeof applyOrbSignals === "function") {
          applyOrbSignals();
        }
        return true;
      })()`,
      true,
    );
    await delayMs(220);
    await writeOrbVerificationCapture(win, "attentive");

    await win.webContents.executeJavaScript(
      `(() => {
        const root = document.getElementById("orb-render-root");
        const size = Number(root?.clientWidth || 160);
        const targetX = Math.max(220, window.innerWidth - 320);
        const targetY = Math.max(220, window.innerHeight - 260);
        if (typeof ORB_BODY_STATES !== "object" || !ORB_BODY_STATES || typeof renderOrbPresentation !== "function") {
          return false;
        }
        orbBodyPresence = {
          ...(orbBodyPresence || {}),
          state: ORB_BODY_STATES.INVESTIGATE,
          desiredPoint: { x: targetX - 116, y: targetY + 26 },
          perchPoint: { x: targetX - 160, y: targetY + 58 },
          targetPoint: { x: targetX, y: targetY },
          anchorLabel: "verification target",
          motionLabel: "curious standoff",
          summary: "Investigating from a respectful side-biased standoff.",
          scale: 1,
          stiffness: 0.18,
          damping: 0.82,
          holdPerch: false,
          taskbarIntent: false,
        };
        if (typeof orbMotion === "object" && orbMotion) {
          orbMotion.x = targetX - 116;
          orbMotion.y = targetY + 26;
          orbMotion.targetX = targetX - 116;
          orbMotion.targetY = targetY + 26;
          orbMotion.vx = 0;
          orbMotion.vy = 0;
        }
        if (root) {
          root.style.width = \`\${size}px\`;
          root.style.height = \`\${size}px\`;
          root.dataset.bodyState = ORB_BODY_STATES.INVESTIGATE;
        }
        renderOrbPresentation();
        if (typeof applyOrbSignals === "function") {
          applyOrbSignals();
        }
        return true;
      })()`,
      true,
    );
    await delayMs(220);
    await writeOrbVerificationCapture(win, "investigate");

    await win.webContents.executeJavaScript(
      `(() => {
        const root = document.getElementById("orb-render-root");
        const size = Number(root?.clientWidth || 160);
        const targetX = Math.max(240, window.innerWidth - 300);
        const targetY = Math.max(220, window.innerHeight - 244);
        if (typeof ORB_BODY_STATES !== "object" || !ORB_BODY_STATES || typeof renderOrbPresentation !== "function") {
          return false;
        }
        orbBodyPresence = {
          ...(orbBodyPresence || {}),
          state: ORB_BODY_STATES.TARGET_LOCK,
          desiredPoint: { x: targetX - 72, y: targetY + 8 },
          perchPoint: { x: targetX - 104, y: targetY + 20 },
          targetPoint: { x: targetX, y: targetY },
          anchorLabel: "verification target",
          motionLabel: "stable lock",
          summary: "Holding a tighter, steadier target lock.",
          scale: 0.98,
          stiffness: 0.26,
          damping: 0.8,
          holdPerch: false,
          taskbarIntent: false,
        };
        if (typeof orbMotion === "object" && orbMotion) {
          orbMotion.x = targetX - 72;
          orbMotion.y = targetY + 8;
          orbMotion.targetX = targetX - 72;
          orbMotion.targetY = targetY + 8;
          orbMotion.vx = 0;
          orbMotion.vy = 0;
        }
        if (root) {
          root.style.width = \`\${size}px\`;
          root.style.height = \`\${size}px\`;
          root.dataset.bodyState = ORB_BODY_STATES.TARGET_LOCK;
        }
        renderOrbPresentation();
        if (typeof applyOrbSignals === "function") {
          applyOrbSignals();
        }
        return true;
      })()`,
      true,
    );
    await delayMs(220);
    await writeOrbVerificationCapture(win, "lock");

    await win.webContents.executeJavaScript(
      `(() => {
        const root = document.getElementById("orb-render-root");
        const size = Number(root?.clientWidth || 160);
        const fallback = typeof getOrbResidentHomeTarget === "function"
          ? getOrbResidentHomeTarget(size)
          : { x: window.innerWidth - 150, y: window.innerHeight - 150 };
        if (typeof ORB_BODY_STATES !== "object" || !ORB_BODY_STATES || typeof renderOrbPresentation !== "function") {
          return false;
        }
        orbBodyPresence = {
          ...(orbBodyPresence || {}),
          state: ORB_BODY_STATES.DEGRADED,
          desiredPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          perchPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          targetPoint: null,
          anchorLabel: "guarded perch",
          motionLabel: "reduced authority",
          summary: "Holding a weaker, flatter degraded posture.",
          scale: 0.97,
          stiffness: 0.14,
          damping: 0.86,
          holdPerch: true,
          taskbarIntent: false,
        };
        if (typeof orbMotion === "object" && orbMotion) {
          orbMotion.x = Number(fallback.x);
          orbMotion.y = Number(fallback.y);
          orbMotion.targetX = Number(fallback.x);
          orbMotion.targetY = Number(fallback.y);
          orbMotion.vx = 0;
          orbMotion.vy = 0;
        }
        if (root) {
          root.style.width = \`\${size}px\`;
          root.style.height = \`\${size}px\`;
          root.dataset.bodyState = ORB_BODY_STATES.DEGRADED;
        }
        renderOrbPresentation();
        if (typeof applyOrbSignals === "function") {
          applyOrbSignals();
        }
        return true;
      })()`,
      true,
    );
    await delayMs(220);
    await writeOrbVerificationCapture(win, "degraded");

    await win.webContents.executeJavaScript(
      `(() => {
        const root = document.getElementById("orb-render-root");
        const size = Number(root?.clientWidth || 160);
        const fallback = typeof getOrbResidentHomeTarget === "function"
          ? getOrbResidentHomeTarget(size)
          : { x: window.innerWidth - 150, y: window.innerHeight - 150 };
        if (typeof ORB_BODY_STATES !== "object" || !ORB_BODY_STATES || typeof renderOrbPresentation !== "function") {
          return false;
        }
        orbBodyPresence = {
          ...(orbBodyPresence || {}),
          state: ORB_BODY_STATES.PAUSED,
          desiredPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          perchPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          targetPoint: null,
          anchorLabel: "resident perch",
          motionLabel: "intentional stillness",
          summary: "Paused deliberately and holding still.",
          scale: 0.97,
          stiffness: 0.12,
          damping: 0.88,
          holdPerch: true,
          taskbarIntent: false,
        };
        if (typeof orbMotion === "object" && orbMotion) {
          orbMotion.x = Number(fallback.x);
          orbMotion.y = Number(fallback.y);
          orbMotion.targetX = Number(fallback.x);
          orbMotion.targetY = Number(fallback.y);
          orbMotion.vx = 0;
          orbMotion.vy = 0;
        }
        if (root) {
          root.style.width = \`\${size}px\`;
          root.style.height = \`\${size}px\`;
          root.dataset.bodyState = ORB_BODY_STATES.PAUSED;
        }
        renderOrbPresentation();
        if (typeof applyOrbSignals === "function") {
          applyOrbSignals();
        }
        return true;
      })()`,
      true,
    );
    await delayMs(220);
    await writeOrbVerificationCapture(win, "paused");

    await win.webContents.executeJavaScript(
      `(() => {
        const root = document.getElementById("orb-render-root");
        const size = Number(root?.clientWidth || 160);
        const fallback = typeof getOrbResidentHomeTarget === "function"
          ? getOrbResidentHomeTarget(size)
          : { x: window.innerWidth - 150, y: window.innerHeight - 150 };
        if (typeof ORB_BODY_STATES !== "object" || !ORB_BODY_STATES || typeof renderOrbPresentation !== "function") {
          return false;
        }
        orbBodyPresence = {
          ...(orbBodyPresence || {}),
          state: ORB_BODY_STATES.INTERRUPTED,
          desiredPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          perchPoint: { x: Number(fallback.x), y: Number(fallback.y) },
          targetPoint: null,
          anchorLabel: "resident perch",
          motionLabel: "graceful retreat",
          summary: "Backing off cleanly and returning to a safe anchor.",
          scale: 0.98,
          stiffness: 0.16,
          damping: 0.84,
          holdPerch: true,
          taskbarIntent: false,
        };
        if (typeof orbMotion === "object" && orbMotion) {
          orbMotion.x = Number(fallback.x);
          orbMotion.y = Number(fallback.y);
          orbMotion.targetX = Number(fallback.x);
          orbMotion.targetY = Number(fallback.y);
          orbMotion.vx = 0;
          orbMotion.vy = 0;
        }
        if (root) {
          root.style.width = \`\${size}px\`;
          root.style.height = \`\${size}px\`;
          root.dataset.bodyState = ORB_BODY_STATES.INTERRUPTED;
        }
        renderOrbPresentation();
        if (typeof applyOrbSignals === "function") {
          applyOrbSignals();
        }
        return true;
      })()`,
      true,
    );
    await delayMs(220);
    await writeOrbVerificationCapture(win, "yield");
    await win.webContents.executeJavaScript(
      `(() => {
        document.documentElement.style.background = "transparent";
        document.body.style.background = "transparent";
        return true;
      })()`,
      true,
    );
  } catch (error) {
    log("Orb verification snapshot capture failed", error instanceof Error ? error.message : String(error));
    try {
      fs.mkdirSync(ORB_VERIFICATION_CAPTURE_DIR, { recursive: true });
      fs.writeFileSync(
        path.join(ORB_VERIFICATION_CAPTURE_DIR, "capture-error.txt"),
        `${error instanceof Error ? error.stack || error.message : String(error)}\n`,
        "utf8",
      );
    } catch {}
  }
}

function createOrbWindow(options = {}) {
  const { displays, primaryDisplayId } = getDisplayContext();
  overlayPreferences = loadPreferences(app.getPath("userData"), displays, primaryDisplayId);
  const preloadPath = path.join(__dirname, "preload.js");
  const targetDisplay = resolveTargetDisplay(displays, overlayPreferences.targetDisplayId, primaryDisplayId);
  const startupProfile = resolveStartupProfile(overlayPreferences, { recoveryNeeded: overlayRecovery.needed });
  const showOnReady = options.showOnReady;
  const shouldShowOnReady = showOnReady === true ? true : showOnReady === false ? false : startupProfile.visible;
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
    focusable: false,
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
  if (typeof win.setFocusable === "function") {
    win.setFocusable(false);
  }
  applyAlwaysOnTop(win, overlayPreferences.alwaysOnTop);
  orbInputState.ignoreMouseEvents = true;
  win.setIgnoreMouseEvents(true, { forward: true });
  win.removeMenu();
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  if (typeof win.webContents.setBackgroundThrottling === "function") {
    win.webContents.setBackgroundThrottling(false);
  }
  reinforceOrbWindowPresence(win, { reason: "create_orb_window" });
  ensureOrbSurfaceAuthorityLoop();
  win.webContents.once("did-finish-load", () => {
    log("Orb HUD loaded", win.webContents.getURL());
    void maybeCaptureOrbVerificationSnapshots(win);
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
  win.webContents.on("render-process-gone", (_event, details) => {
    const reason = `orb-renderer-${details.reason || "gone"}`;
    log("Orb renderer process exited", details);
    setOverlayRecovery({
      needed: true,
      status: "renderer_crash",
      message: `Orb renderer exited: ${details.reason || "unknown"}. Rebuilding the orb surface.`,
      lastExitReason: reason,
    });
    notifyOverlayState(mainWindow);
  });
  win.on("unresponsive", () => {
    log("Orb window became unresponsive");
    setOverlayRecovery({
      needed: true,
      status: "unresponsive",
      message: "Orb renderer became unresponsive. Francis will attempt to restore the orb surface.",
      lastExitReason: "orb-renderer-unresponsive",
    });
    notifyOverlayState(mainWindow);
  });
  const orbUrl = getOrbHudUrl();
  log("Loading orb HUD", orbUrl);
  win.loadURL(orbUrl).catch((error) => {
    log("Unexpected orb HUD load error", error instanceof Error ? error.message : String(error));
  });
  ensureOrbPerceptionLoop();
  ensureOrbAuthorityLoop();

  win.once("ready-to-show", () => {
    if (shouldShowOnReady) {
      log("Orb ready; showing window", {
        startupProfile: startupProfile.effective,
      });
      win.showInactive();
      reinforceOrbWindowPresence(win, { reason: "orb_ready_show" });
      notifyOverlayState(mainWindow);
      return;
    }
    log("Orb ready; startup profile keeps the shell hidden until summoned", {
      startupProfile: startupProfile.effective,
    });
    notifyOverlayState(mainWindow);
  });

  win.on("show", () => {
    reinforceOrbWindowPresence(win, { reason: "orb_show" });
    notifyOverlayState(mainWindow);
  });
  win.on("blur", () => {
    resetOrbOwnershipToSafeFallback("orb_blur");
    void checkForCaptureActivation();
  });
  win.on("close", (event) => {
    if (shouldAllowWindowClose()) {
      return;
    }
    event.preventDefault();
    resetOrbOwnershipToSafeFallback("orb_window_hidden");
    win.hide();
    notifyOverlayState(mainWindow);
  });
  win.on("hide", () => notifyOverlayState(mainWindow));
  win.on("closed", () => {
    log("Orb window closed");
    if (orbWindow === win) {
      orbWindow = null;
      stopOrbSurfaceAuthorityLoop();
      stopOrbPerceptionLoop();
      stopOrbAuthorityLoop();
    }
    if (!shouldAllowWindowClose()) {
      setTimeout(() => {
        if (quitAfterHudShutdown) {
          return;
        }
        if (orbWindow && !orbWindow.isDestroyed()) {
          return;
        }
        log("Recreating orb window after unexpected close");
        orbWindow = createOrbWindow();
      }, 150);
    }
  });

  return win;
}

function createMainWindow(options = {}) {
  const showOnReady = options.showOnReady === true;
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
    title: "Francis Review HUD",
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
  if (typeof win.setOpacity === "function") {
    win.setOpacity(0);
  }

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
    if (showOnReady) {
      if (typeof win.setOpacity === "function") {
        win.setOpacity(1);
      }
      win.showInactive();
      log("Lens ready from explicit open request", {
        startupProfile: startupProfile.effective,
      });
    } else {
      if (typeof win.setOpacity === "function") {
        win.setOpacity(0);
      }
      win.hide();
      log("Lens ready; keeping the HUD hidden until the Orb opens it", {
        startupProfile: startupProfile.effective,
      });
    }
    notifyOverlayState(win);
  });

  win.on("move", () => schedulePreferenceSave(win));
  win.on("resize", () => schedulePreferenceSave(win));
  win.on("show", () => {
    if (typeof win.setOpacity === "function") {
      win.setOpacity(1);
    }
    notifyOverlayState(win);
  });
  win.on("blur", () => {
    void checkForCaptureActivation();
  });
  win.on("hide", () => {
    if (typeof win.setOpacity === "function") {
      win.setOpacity(0);
    }
    notifyOverlayState(win);
  });
  win.on("minimize", () => notifyOverlayState(win));
  win.on("restore", () => notifyOverlayState(win));
  win.on("close", (event) => {
    if (shouldAllowWindowClose()) {
      return;
    }
    event.preventDefault();
    win.hide();
    lensInteractionRestoreIgnoreMouseEvents = null;
    resetOrbOwnershipToSafeFallback("overlay_window_hidden");
    notifyOverlayState(win);
  });

  win.on("closed", () => {
    schedulePreferenceSave(win, { immediate: true });
    log("Overlay window closed");
    if (mainWindow === win) {
      mainWindow = null;
      lensInteractionRestoreIgnoreMouseEvents = null;
    }
  });

  loadHud(win).catch((error) => {
    log("Unexpected HUD load error", error instanceof Error ? error.message : String(error));
  });

  return win;
}

function requireWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = createMainWindow({ showOnReady: false });
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

async function restartHudAndRefreshWindow(win = mainWindow, { recoveryId = 0, reason = "" } = {}) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  if (!hudRuntime) {
    throw new Error("HUD runtime is not available");
  }
  if (hudRestartPromise) {
    log("Reused in-flight managed HUD restart", buildHudRecoveryDiagnostics({
      reason: reason || "restart_reused",
      recoveryId,
    }));
    return hudRestartPromise;
  }

  hudRestartPromise = (async () => {
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
  })();
  try {
    return await hudRestartPromise;
  } finally {
    hudRestartPromise = null;
  }
}

function registerIpc() {
  if (ipcRegistered) {
    return;
  }
  ipcRegistered = true;

  ipcMain.handle("overlay:set-ignore-mouse-events", (_event, ignore) => {
    const win = getLiveMainWindow();
    const value = applyIgnoreMouseEvents(win, ignore);
    log("Updated click-through state", value);
    return value;
  });
  ipcMain.handle("overlay:set-orb-ignore-mouse-events", (_event, ignore) => {
    const snapshot = setOrbOwnershipMode(
      ignore ? ORB_OWNERSHIP_STATES.PASS_THROUGH : ORB_OWNERSHIP_STATES.INTERACTABLE_ORB,
      "legacy_orb_mouse_events",
    );
    if (!snapshot.requestUnchanged && (snapshot.restricted || snapshot.state === ORB_OWNERSHIP_STATES.INTERACTABLE_LENS)) {
      log("Updated orb ownership state", snapshot);
    }
    return snapshot;
  });
  ipcMain.handle("overlay:set-orb-ownership-mode", (_event, mode, reason = "") => {
    const snapshot = setOrbOwnershipMode(mode, reason || "renderer_ownership");
    const runtimeHealth = getOrbRuntimeHealthSnapshot();
    const suppressionKey = [
      snapshot.requestedMode,
      snapshot.state,
      snapshot.reason,
      runtimeHealth.status,
      runtimeHealth.source,
    ].join("|");
    const loggableReason = !["orb_surface", "legacy_orb_mouse_events", "renderer_interaction", "orb_shell"].includes(
      String(reason || "").trim(),
    );
    if (!snapshot.requestUnchanged && loggableReason) {
      log("Updated orb ownership state", snapshot);
    } else if ((snapshot.restricted || !snapshot.canClaimOrbInteraction) && orbOwnershipSuppressionLogKey !== suppressionKey) {
      orbOwnershipSuppressionLogKey = suppressionKey;
      log("Suppressed repeated orb ownership request", {
        ...snapshot,
        runtimeHealth,
      });
    }
    return snapshot;
  });

  ipcMain.handle("overlay:set-always-on-top", (_event, enabled) => {
    const win = getLiveMainWindow();
    const value = applyAlwaysOnTop(win, enabled);
    log("Updated always-on-top state", value);
    return value;
  });

  ipcMain.handle("overlay:set-launch-at-login", (_event, enabled) => setLaunchAtLoginEnabled(enabled));
  ipcMain.handle("overlay:set-launch-on-startup", (_event, enabled) => setLaunchAtLoginEnabled(enabled));
  ipcMain.handle("overlay:set-startup-profile", (_event, profileId) => setStartupProfile(profileId));
  ipcMain.handle("overlay:set-orb-behavior-mode", (event, modeId) => {
    const senderId = event?.sender?.id;
    const orbWindowSender = Boolean(
      orbWindow
      && !orbWindow.isDestroyed()
      && orbWindow.webContents
      && orbWindow.webContents.id === senderId,
    );
    if (orbWindowSender) {
      log("Ignored orb behavior mode request from orb window", {
        requested: modeId,
      });
      return getOverlayState(mainWindow && !mainWindow.isDestroyed() ? mainWindow : null);
    }
    return setOrbBehaviorMode(modeId);
  });
  ipcMain.handle("overlay:set-motion-mode", (_event, modeId) => setMotionMode(modeId));
  ipcMain.handle("overlay:set-contrast-mode", (_event, modeId) => setContrastMode(modeId));
  ipcMain.handle("overlay:set-density-mode", (_event, modeId) => setDensityMode(modeId));
  ipcMain.handle("overlay:acknowledge-update-notice", () => dismissUpdateNotice());
  ipcMain.handle("overlay:export-shell-state", () => exportShellState(getLiveMainWindow()));
  ipcMain.handle("overlay:import-shell-state", () => importShellState(getLiveMainWindow()));
  ipcMain.handle("overlay:reset-shell-state", () => resetRetainedShellState(getLiveMainWindow()));
  ipcMain.handle("overlay:repair-shell-state", () => executeRetainedStateRepair(getLiveMainWindow()));
  ipcMain.handle("overlay:create-rollback-snapshot", () => createRollbackSnapshot("manual", "Created from the desktop shell."));
  ipcMain.handle("overlay:restore-latest-rollback", () => restoreLatestRollbackSnapshot(getLiveMainWindow()));
  ipcMain.handle("overlay:export-support-bundle", () => exportSupportBundle(getLiveMainWindow()));
  ipcMain.handle("overlay:set-target-display", (_event, displayId) => moveOverlayToDisplay(displayId, getLiveMainWindow()));
  ipcMain.handle("overlay:reset-layout", () => resetOverlayPreferences(getLiveMainWindow()));
  ipcMain.handle("overlay:get-state", () => getOverlayState(mainWindow));
  ipcMain.handle("overlay:get-input-state", () => getOverlayInputState());
  ipcMain.handle("overlay:capture-perception-frame", () => capturePerceptionFrame());
  ipcMain.handle("overlay:get-display-info", () => getDisplayInfo(mainWindow));
  ipcMain.handle("overlay:restart-hud", () => restartHudAndRefreshWindow(mainWindow));
  ipcMain.handle("overlay:pause-authority", () => pauseOrbAuthorityLocally());
  ipcMain.handle("overlay:open-path", (_event, target) => openLifecyclePath(target));
  ipcMain.handle("overlay:get-orb-surface", () => fetchHudJson("/api/orb"));
  ipcMain.handle("overlay:execute-orb-desktop-plan", async (_event, plan) => {
    const inputState = getOverlayInputState();
    const result = await executeOrbDesktopPlan(plan, {
      inputState,
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
    const enrichedResult = {
      ...buildOrbReceiptContext(inputState),
      ...(result && typeof result === "object" ? result : {}),
    };
    recordLifecycleHistory(
      "orb.desktop_plan",
      String(enrichedResult?.status || "").trim().toLowerCase() === "failed"
        ? `Orb desktop plan failed: ${String(enrichedResult.title || "Orb desktop plan")}.`
        : `Orb desktop plan executed: ${String(enrichedResult.title || "Orb desktop plan")}.`,
      {
        tone: String(enrichedResult?.status || "").trim().toLowerCase() === "failed" ? "high" : "medium",
        detail: enrichedResult && typeof enrichedResult === "object" ? enrichedResult : {},
      },
    );
    return enrichedResult;
  });
  ipcMain.handle("overlay:panic-stop", async () => {
    if (orbPanicStopPending) {
      return orbPanicStopPending;
    }
    orbPanicStopPending = (async () => {
      let remoteResponse = null;
      let remoteError = null;
      let localError = null;
      let queueError = "";
      const localDetail = "Panic stop released local authority immediately. Human control remains primary.";
      try {
        stabilizeOrbAuthorityLocally(
          localDetail,
          {
            localStop: true,
            localStopActive: true,
            pauseHold: false,
            disconnected: !getHudState()?.ready,
            degraded: true,
            remoteSyncStatus: "pending",
            summary: "Local stop confirmed. Remote sync pending.",
            detail: "Francis dropped local authority immediately and is holding a local stop posture while upstream confirmation catches up.",
            notify: false,
            localError: "",
            remoteError: "",
          },
        );
        notifyOverlayState(mainWindow);
      } catch (error) {
        localError = error instanceof Error ? error.message : String(error);
        log("Panic stop local release failed", localError);
      }

      const queueResult = await cancelOrbAuthorityQueue("Panic stop canceled queued Orb authority commands.");
      const queueSynced = Boolean(queueResult?.ok);
      queueError = cleanSafetyDiagnostic(queueResult?.error || "");
      try {
        remoteResponse = await fetchHudJson("/api/actions/execute", {
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
      } catch (error) {
        remoteError = error instanceof Error ? error.message : String(error);
        log("Panic stop remote sync failed", remoteError);
      }

      const remoteSynced = queueSynced && !remoteError;
      const remoteSyncStatus = remoteSynced ? "current" : getHudState()?.ready ? "failed" : "pending";
      const result = buildPanicStopResult({
        queueCleared: queueSynced,
        authorityReleased: !localError,
        localError,
        remoteResponse: remoteSynced ? remoteResponse : null,
        remoteError: remoteSynced
          ? null
          : remoteError || queueError || "Orb authority queue clear did not confirm.",
      });

      setOrbSafetyState({
        localStopLatchedUntilMs: result.localStopped ? Date.now() + ORB_LOCAL_STOP_LATCH_MS : 0,
        localStopActive: Boolean(result.localStopped) && !remoteSynced,
        pauseHeld: false,
        disconnected: remoteSyncStatus === "pending" && !getHudState()?.ready,
        degraded: !remoteSynced || Boolean(overlayRecovery.needed),
        remoteSyncStatus,
        summary: String(result.summary || "").trim(),
        detail: String(result.detail || localDetail).trim(),
        localError: result.diagnostics?.localError || "",
        remoteError: result.diagnostics?.remoteError || "",
        lastAction: "panic_stop",
        lastReason: String(result.detail || localDetail).trim(),
      });

      return result;
    })();
    try {
      return await orbPanicStopPending;
    } finally {
      orbPanicStopPending = null;
    }
  });
  ipcMain.handle("overlay:show-lens", () => showLensWindow());
  ipcMain.handle("overlay:hide-lens", () => hideLensWindow());

  ipcMain.handle("overlay:minimize", () => {
    const win = getShellControlWindow();
    if (!win) {
      return false;
    }
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

  ipcMain.handle("overlay:quit", (event) => {
    requestAppQuit("renderer-bridge", {
      senderUrl: event?.senderFrame?.url || event?.sender?.getURL?.() || "",
    });
    return true;
  });

  ipcMain.handle("overlay:toggle-devtools", () => {
    const win = getShellControlWindow();
    if (!win) {
      return false;
    }
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
    log("No live overlay windows were available; recreating orb window");
    showOrbWindow();
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
  const nextValue = !overlayState.ignoreMouseEvents;
  const applied = applyIgnoreMouseEvents(getLiveMainWindow(), nextValue);
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
    env: buildManagedHudEnv(),
    log,
    onStateChanged: (publicState) => {
      const previousGeneration = Number(hudRecoveryState?.generation || 0);
      hudRecoveryState = noteHudProcessState(hudRecoveryState, {
        pid: publicState?.pid ?? null,
        alive: Boolean(publicState?.childAlive),
      });
      if (publicState?.restartSuggested) {
        recordOrbRuntimeFailure("Managed HUD requested recovery.", {
          source: "hud",
          notify: false,
        });
        scheduleHudRecovery(`hud-${publicState.mode || "crashed"}`);
      } else if (publicState?.ready) {
        markHudGenerationReady(publicState);
        if (Number(hudRecoveryState?.generation || 0) !== previousGeneration) {
          log("Managed HUD generation became ready", buildHudRecoveryDiagnostics({
            generation: hudRecoveryState.generation,
            previousGeneration,
          }));
        }
        recordOrbRuntimeHealthyProof("Managed HUD reported ready. Waiting for stable health proofs.", {
          source: "hud",
          notify: false,
        });
        if (orbRuntimeHealth.status === "nominal") {
          clearHudRecovery();
        }
      }
      notifyOverlayState(mainWindow);
    },
  });

  try {
    const hudState = await hudRuntime.ensureReady();
    markHudGenerationReady(hudState);
    recordOrbRuntimeHealthyProof("Managed HUD booted and reported ready.", {
      source: "hud",
      notify: false,
    });
    log("HUD runtime ready", hudState);
  } catch (error) {
    recordOrbRuntimeFailure(error instanceof Error ? error.message : String(error), {
      source: "hud",
      notify: false,
    });
    log("HUD runtime initialization did not produce a ready server", error instanceof Error ? error.message : String(error));
    const recoveryReason = getScheduledHudRecoveryReason(hudRuntime.getPublicState());
    if (recoveryReason) {
      scheduleHudRecovery(recoveryReason);
    }
  }
}

async function initializeOllamaRuntime() {
  ollamaRuntime = createOllamaRuntimeManager({
    appDir: __dirname,
    ollamaUrl: OLLAMA_URL,
    env: process.env,
    log,
    onStateChanged: (publicState) => {
      if (publicState?.restartSuggested) {
        scheduleOllamaRecovery(`ollama-${publicState.mode || "crashed"}`);
      } else if (publicState?.ready) {
        clearOllamaRecovery();
      }
      notifyOverlayState(mainWindow);
    },
  });

  try {
    const ollamaState = await ollamaRuntime.ensureReady();
    log("Ollama runtime ready", ollamaState);
  } catch (error) {
    log("Ollama runtime initialization did not produce a ready server", error instanceof Error ? error.message : String(error));
  }
}

if (!app.requestSingleInstanceLock()) {
  requestAppQuit("single-instance-lock");
} else {
  app.whenReady().then(async () => {
    buildInfo = resolveBuildIdentity(app, __dirname);
    executableSignature = app.isPackaged ? inspectAuthenticodeSignature(app.getPath("exe")) : null;
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
    await initializeOllamaRuntime();
    ensureOllamaHealthMonitor();
    await initializeHudRuntime();
    ensureHudHealthMonitor();
    overlayPreferences = loadPreferences(
      app.getPath("userData"),
      getDisplayContext().displays,
      getDisplayContext().primaryDisplayId,
    );
    const startupSurface = resolveStartupSurface(overlayPreferences, { recoveryNeeded: overlayRecovery.needed });
    if (startupSurface.constructLensWindowOnBoot) {
      mainWindow = createMainWindow({ showOnReady: startupSurface.showLensWindowOnBoot === true });
    }
    orbWindow = createOrbWindow({ showOnReady: startupSurface.showOrbWindowOnBoot === true });
    createTray();
    registerShortcuts();
  });

  app.on("second-instance", () => {
    const startupSurface = resolveOrbFirstSecondInstance({
      orbVisible: Boolean(orbWindow && !orbWindow.isDestroyed() && orbWindow.isVisible()),
      lensVisible: Boolean(mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()),
    });
    if (startupSurface.ensureOrbWindow && (!orbWindow || orbWindow.isDestroyed())) {
      orbWindow = createOrbWindow();
    }
    if (startupSurface.showOrbWindow) {
      showOrbWindow();
      return;
    }
    notifyOverlayState(mainWindow);
  });
}

app.on("activate", () => {
  const startupSurface = resolveOrbFirstAppActivation({
    orbVisible: Boolean(orbWindow && !orbWindow.isDestroyed() && orbWindow.isVisible()),
    lensVisible: Boolean(mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()),
  });
  if (startupSurface.ensureOrbWindow && (!orbWindow || orbWindow.isDestroyed())) {
    orbWindow = createOrbWindow();
  }
  if (startupSurface.showOrbWindow) {
    showOrbWindow();
    return;
  }
  notifyOverlayState(mainWindow);
});

app.on("before-quit", (event) => {
  log("Electron before-quit received", {
    quitAfterHudShutdown,
    hudManaged: Boolean(hudRuntime && getHudState()?.managed),
    ollamaManaged: Boolean(ollamaRuntime && getOllamaState()?.managed),
  });
  if (quitAfterHudShutdown) {
    return;
  }
  markSessionExit("clean-exit", { clean: true });
  const shouldShutdownHud = Boolean(hudRuntime && getHudState()?.managed);
  const shouldShutdownOllama = Boolean(ollamaRuntime && getOllamaState()?.managed);
  if (!shouldShutdownHud && !shouldShutdownOllama) {
    return;
  }
  event.preventDefault();
  quitAfterHudShutdown = true;
  Promise.all([
    shouldShutdownHud
      ? hudRuntime.shutdown({ force: true }).catch((error) => {
          log("Managed HUD shutdown failed", error instanceof Error ? error.message : String(error));
        })
      : Promise.resolve(),
    shouldShutdownOllama
      ? ollamaRuntime.shutdown({ force: true }).catch((error) => {
          log("Managed Ollama shutdown failed", error instanceof Error ? error.message : String(error));
        })
      : Promise.resolve(),
  ])
    .finally(() => {
      requestAppQuit("managed-runtime-shutdown");
    });
});

app.on("window-all-closed", () => {
  log("Electron window-all-closed received", {
    quitAfterHudShutdown,
    mainWindowAlive: Boolean(mainWindow && !mainWindow.isDestroyed()),
    orbWindowAlive: Boolean(orbWindow && !orbWindow.isDestroyed()),
  });
  if (shouldAllowWindowClose()) {
    if (process.platform !== "darwin") {
      requestAppQuit("window-all-closed");
    }
    return;
  }
  log("All overlay windows closed; keeping Francis resident for tray and shortcut recovery");
});

app.on("will-quit", () => {
  log("Electron will-quit received", {
    quitAfterHudShutdown,
    mainWindowAlive: Boolean(mainWindow && !mainWindow.isDestroyed()),
    orbWindowAlive: Boolean(orbWindow && !orbWindow.isDestroyed()),
  });
  if (preferenceSaveTimer) {
    clearTimeout(preferenceSaveTimer);
    preferenceSaveTimer = null;
  }
  if (hudRecoveryTimer) {
    clearTimeout(hudRecoveryTimer);
    hudRecoveryTimer = null;
  }
  if (ollamaRecoveryTimer) {
    clearTimeout(ollamaRecoveryTimer);
    ollamaRecoveryTimer = null;
  }
  stopHudHealthMonitor();
  stopOllamaHealthMonitor();
  stopCaptureRecoveryLoop();
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
