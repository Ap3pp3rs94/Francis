const { contextBridge, ipcRenderer } = require("electron");

function assertBoolean(name, value) {
  if (typeof value !== "boolean") {
    throw new TypeError(`${name} must be a boolean`);
  }
  return value;
}

function assertFunction(name, value) {
  if (typeof value !== "function") {
    throw new TypeError(`${name} must be a function`);
  }
  return value;
}

function assertFiniteNumber(name, value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`${name} must be a finite number`);
  }
  return value;
}

function assertString(name, value) {
  if (typeof value !== "string" || !value.trim()) {
    throw new TypeError(`${name} must be a non-empty string`);
  }
  return value;
}

contextBridge.exposeInMainWorld("FrancisDesktop", {
  setIgnoreMouseEvents(ignore) {
    return ipcRenderer.invoke("overlay:set-ignore-mouse-events", assertBoolean("ignore", ignore));
  },
  setAlwaysOnTop(value) {
    return ipcRenderer.invoke("overlay:set-always-on-top", assertBoolean("value", value));
  },
  setLaunchAtLogin(value) {
    return ipcRenderer.invoke("overlay:set-launch-at-login", assertBoolean("value", value));
  },
  setLaunchOnStartup(value) {
    return ipcRenderer.invoke("overlay:set-launch-on-startup", assertBoolean("value", value));
  },
  setStartupProfile(profileId) {
    return ipcRenderer.invoke("overlay:set-startup-profile", assertString("profileId", profileId));
  },
  setMotionMode(modeId) {
    return ipcRenderer.invoke("overlay:set-motion-mode", assertString("modeId", modeId));
  },
  acknowledgeUpdateNotice() {
    return ipcRenderer.invoke("overlay:acknowledge-update-notice");
  },
  exportShellState() {
    return ipcRenderer.invoke("overlay:export-shell-state");
  },
  exportSupportBundle() {
    return ipcRenderer.invoke("overlay:export-support-bundle");
  },
  importShellState() {
    return ipcRenderer.invoke("overlay:import-shell-state");
  },
  resetShellState() {
    return ipcRenderer.invoke("overlay:reset-shell-state");
  },
  createRollbackSnapshot() {
    return ipcRenderer.invoke("overlay:create-rollback-snapshot");
  },
  restoreLatestRollback() {
    return ipcRenderer.invoke("overlay:restore-latest-rollback");
  },
  openPath(target) {
    return ipcRenderer.invoke("overlay:open-path", assertString("target", target));
  },
  setTargetDisplay(displayId) {
    return ipcRenderer.invoke("overlay:set-target-display", assertFiniteNumber("displayId", displayId));
  },
  restartHud() {
    return ipcRenderer.invoke("overlay:restart-hud");
  },
  resetLayout() {
    return ipcRenderer.invoke("overlay:reset-layout");
  },
  getState() {
    return ipcRenderer.invoke("overlay:get-state");
  },
  getDisplayInfo() {
    return ipcRenderer.invoke("overlay:get-display-info");
  },
  minimize() {
    return ipcRenderer.invoke("overlay:minimize");
  },
  hide() {
    return ipcRenderer.invoke("overlay:hide");
  },
  show() {
    return ipcRenderer.invoke("overlay:show");
  },
  toggleDevTools() {
    return ipcRenderer.invoke("overlay:toggle-devtools");
  },
  onStateChanged(callback) {
    const safeCallback = assertFunction("callback", callback);
    ipcRenderer.removeAllListeners("overlay:state-changed");
    ipcRenderer.on("overlay:state-changed", (_event, value) => {
      safeCallback(value);
    });
    return true;
  },
});
