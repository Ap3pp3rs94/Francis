const { contextBridge, ipcRenderer } = require("electron");

function assertBoolean(name, value) {
  if (typeof value !== "boolean") {
    throw new TypeError(`${name} must be a boolean`);
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
});
