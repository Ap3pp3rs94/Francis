function buildDefaultLoginItemState() {
  return {
    available: false,
    enabled: false,
    openAsHidden: false,
    openedAtLogin: false,
    openedAsHidden: false,
  };
}

function isLoginItemSupported(appLike) {
  return Boolean(
    appLike
      && typeof appLike.getLoginItemSettings === "function"
      && typeof appLike.setLoginItemSettings === "function",
  );
}

function normalizeLoginItemState(raw) {
  const defaults = buildDefaultLoginItemState();
  if (!raw || typeof raw !== "object") {
    return defaults;
  }
  return {
    available: true,
    enabled: Boolean(raw.openAtLogin),
    openAsHidden: Boolean(raw.openAsHidden),
    openedAtLogin: Boolean(raw.wasOpenedAtLogin),
    openedAsHidden: Boolean(raw.wasOpenedAsHidden),
  };
}

function getLaunchAtLoginState(appLike) {
  if (!isLoginItemSupported(appLike)) {
    return buildDefaultLoginItemState();
  }
  return normalizeLoginItemState(appLike.getLoginItemSettings());
}

function setLaunchAtLogin(appLike, enabled) {
  if (!isLoginItemSupported(appLike)) {
    throw new Error("Launch-at-login controls are unavailable in this Electron runtime.");
  }
  const nextValue = Boolean(enabled);
  appLike.setLoginItemSettings({
    openAtLogin: nextValue,
    openAsHidden: nextValue,
  });
  return getLaunchAtLoginState(appLike);
}

module.exports = {
  buildDefaultLoginItemState,
  getLaunchAtLoginState,
  isLoginItemSupported,
  normalizeLoginItemState,
  setLaunchAtLogin,
};
