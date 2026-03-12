const path = require("node:path");
const { app, BrowserWindow, Menu, Tray, globalShortcut, ipcMain, nativeImage, screen } = require("electron");
const { createHudRuntimeManager } = require("./hud-runtime");
const {
  buildDefaultPreferences,
  getPreferencesPath,
  loadPreferences,
  normalizeBounds,
  resolveTargetDisplay,
  savePreferences,
} = require("./preferences");
const {
  buildDefaultSessionState,
  loadSessionState,
  saveSessionState,
} = require("./session-state");

const HUD_URL = process.env.FRANCIS_HUD_URL || "http://127.0.0.1:8767";
const OVERLAY_TOGGLE_SHORTCUT = "Control+Shift+Alt+F";
const CLICK_THROUGH_TOGGLE_SHORTCUT = "Control+Shift+Alt+C";

let mainWindow = null;
let tray = null;
let ipcRegistered = false;
let overlayPreferences = null;
let sessionState = null;
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

function getOverlayState(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  const bounds = getWindowOrPreferenceBounds(safeWindow);
  const displayInfo = app.isReady() ? getDisplayInfo(safeWindow) : null;

  return {
    ignoreMouseEvents: overlayState.ignoreMouseEvents,
    alwaysOnTop: safeWindow ? safeWindow.isAlwaysOnTop() : overlayState.alwaysOnTop,
    visible: safeWindow ? safeWindow.isVisible() : false,
    hudUrl: HUD_URL,
    bounds,
    targetDisplayId: displayInfo?.targetDisplayId ?? overlayPreferences?.targetDisplayId ?? null,
    activeDisplayId: displayInfo?.activeDisplayId ?? null,
    preferencesPath: app.isReady() ? getPreferencesPath(app.getPath("userData")) : null,
    recovery: overlayRecovery,
    hud: getHudState(),
    shortcuts: {
      toggleOverlay: OVERLAY_TOGGLE_SHORTCUT,
      toggleClickThrough: CLICK_THROUGH_TOGGLE_SHORTCUT,
    },
  };
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
      { type: "separator" },
      {
        label: "Restart HUD",
        click: () => {
          restartHudAndRefreshWindow(requireWindow()).catch((error) => {
            log("Tray HUD restart failed", error instanceof Error ? error.message : String(error));
          });
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

  log("Creating overlay window", {
    hudUrl: HUD_URL,
    targetDisplayId: targetDisplay.id,
    bounds: overlayPreferences.windowBounds,
    preferences: overlayPreferences,
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
  applyIgnoreMouseEvents(win, overlayPreferences.ignoreMouseEvents);

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
    log("Overlay ready; showing window");
    win.showInactive();
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

  ipcMain.handle("overlay:set-target-display", (_event, displayId) => moveOverlayToDisplay(displayId, requireWindow()));
  ipcMain.handle("overlay:reset-layout", () => resetOverlayPreferences(requireWindow()));
  ipcMain.handle("overlay:get-state", () => getOverlayState(requireWindow()));
  ipcMain.handle("overlay:get-display-info", () => getDisplayInfo(requireWindow()));
  ipcMain.handle("overlay:restart-hud", () => restartHudAndRefreshWindow(requireWindow()));

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
    sessionState = loadSessionState(app.getPath("userData"));
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
