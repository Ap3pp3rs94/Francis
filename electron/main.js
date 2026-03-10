const path = require("node:path");
const { app, BrowserWindow, globalShortcut, ipcMain, screen } = require("electron");
const {
  buildDefaultPreferences,
  getPreferencesPath,
  loadPreferences,
  savePreferences,
} = require("./preferences");

const HUD_URL = process.env.FRANCIS_HUD_URL || "http://127.0.0.1:8767";
const OVERLAY_TOGGLE_SHORTCUT = "Control+Shift+Alt+F";
const CLICK_THROUGH_TOGGLE_SHORTCUT = "Control+Shift+Alt+C";

let mainWindow = null;
let ipcRegistered = false;
let overlayPreferences = null;
let preferenceSaveTimer = null;
let overlayState = {
  ignoreMouseEvents: false,
  alwaysOnTop: true,
};

function log(message, extra) {
  if (extra === undefined) {
    console.log(`[francis-overlay] ${message}`);
    return;
  }
  console.log(`[francis-overlay] ${message}`, extra);
}

function getDisplayInfo() {
  const display = screen.getPrimaryDisplay();
  return {
    id: display.id,
    scaleFactor: display.scaleFactor,
    bounds: display.bounds,
    workArea: display.workArea,
    workAreaSize: display.workAreaSize,
  };
}

function getWorkAreaForBounds(bounds) {
  if (bounds && Number.isFinite(bounds.x) && Number.isFinite(bounds.y)) {
    return screen.getDisplayMatching(bounds).workArea;
  }
  return getDisplayInfo().workArea;
}

function getOverlayState(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  const bounds = safeWindow ? safeWindow.getBounds() : overlayPreferences?.windowBounds || null;
  return {
    ignoreMouseEvents: overlayState.ignoreMouseEvents,
    alwaysOnTop: safeWindow ? safeWindow.isAlwaysOnTop() : overlayState.alwaysOnTop,
    visible: safeWindow ? safeWindow.isVisible() : false,
    hudUrl: HUD_URL,
    bounds,
    preferencesPath: app.isReady() ? getPreferencesPath(app.getPath("userData")) : null,
    shortcuts: {
      toggleOverlay: OVERLAY_TOGGLE_SHORTCUT,
      toggleClickThrough: CLICK_THROUGH_TOGGLE_SHORTCUT,
    },
  };
}

function notifyOverlayState(win = mainWindow) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  if (!safeWindow) {
    return;
  }
  safeWindow.webContents.send("overlay:state-changed", getOverlayState(safeWindow));
}

function schedulePreferenceSave(win = mainWindow, { immediate = false } = {}) {
  const safeWindow = win && !win.isDestroyed() ? win : null;
  if (!safeWindow || safeWindow.isMinimized()) {
    return;
  }

  const persist = () => {
    const bounds = safeWindow.getBounds();
    const workArea = getWorkAreaForBounds(bounds);
    overlayPreferences = savePreferences(
      app.getPath("userData"),
      {
        ...(overlayPreferences || buildDefaultPreferences(workArea)),
        alwaysOnTop: safeWindow.isAlwaysOnTop(),
        ignoreMouseEvents: overlayState.ignoreMouseEvents,
        windowBounds: bounds,
      },
      workArea,
    );
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
  const workArea = getDisplayInfo().workArea;
  overlayPreferences = buildDefaultPreferences(workArea);
  safeWindow.setBounds(overlayPreferences.windowBounds);
  applyAlwaysOnTop(safeWindow, overlayPreferences.alwaysOnTop);
  applyIgnoreMouseEvents(safeWindow, overlayPreferences.ignoreMouseEvents);
  overlayPreferences = savePreferences(app.getPath("userData"), overlayPreferences, workArea);
  log("Reset overlay preferences", overlayPreferences);
  notifyOverlayState(safeWindow);
  return getOverlayState(safeWindow);
}

function buildFallbackHtml(errorText) {
  const escapedMessage = String(errorText || "Unknown load failure")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  const escapedTarget = HUD_URL.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
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
    </style>
  </head>
  <body>
    <main>
      <h1>Francis HUD server is not reachable.</h1>
      <p>The desktop overlay shell started correctly, but the HUD at <code>${escapedTarget}</code> did not respond.</p>
      <p>Start the HUD server first, then relaunch the overlay.</p>
      <pre>${escapedMessage}</pre>
    </main>
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
  const { workArea } = getDisplayInfo();
  overlayPreferences = loadPreferences(app.getPath("userData"), workArea);
  const preloadPath = path.join(__dirname, "preload.js");

  log("Creating overlay window", { hudUrl: HUD_URL, workArea, preferences: overlayPreferences });

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

  ipcMain.handle("overlay:reset-layout", () => resetOverlayPreferences(requireWindow()));
  ipcMain.handle("overlay:get-state", () => getOverlayState(requireWindow()));
  ipcMain.handle("overlay:get-display-info", () => getDisplayInfo());

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

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.whenReady().then(() => {
    registerIpc();
    mainWindow = createMainWindow();
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
  if (mainWindow && !mainWindow.isDestroyed()) {
    schedulePreferenceSave(mainWindow, { immediate: true });
  }
  log("Unregistering global shortcuts");
  globalShortcut.unregisterAll();
});
