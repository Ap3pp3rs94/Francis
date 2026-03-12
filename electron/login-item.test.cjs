const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildDefaultLoginItemState,
  getLaunchAtLoginState,
  isLoginItemSupported,
  setLaunchAtLogin,
} = require("./login-item");

function makeFakeApp(initial = {}) {
  const state = {
    openAtLogin: Boolean(initial.openAtLogin),
    openAsHidden: Boolean(initial.openAsHidden),
    wasOpenedAtLogin: Boolean(initial.wasOpenedAtLogin),
    wasOpenedAsHidden: Boolean(initial.wasOpenedAsHidden),
  };
  return {
    getLoginItemSettings() {
      return { ...state };
    },
    setLoginItemSettings(next) {
      state.openAtLogin = Boolean(next.openAtLogin);
      state.openAsHidden = Boolean(next.openAsHidden);
    },
  };
}

test("login-item defaults to unavailable when Electron runtime support is missing", () => {
  assert.equal(isLoginItemSupported({}), false);
  assert.deepEqual(getLaunchAtLoginState({}), buildDefaultLoginItemState());
});

test("login-item reflects current Electron login settings", () => {
  const fakeApp = makeFakeApp({
    openAtLogin: true,
    openAsHidden: true,
    wasOpenedAtLogin: true,
    wasOpenedAsHidden: false,
  });

  assert.equal(isLoginItemSupported(fakeApp), true);
  assert.deepEqual(getLaunchAtLoginState(fakeApp), {
    available: true,
    enabled: true,
    openAsHidden: true,
    openedAtLogin: true,
    openedAsHidden: false,
  });
});

test("login-item can toggle launch-at-login on and off", () => {
  const fakeApp = makeFakeApp();

  const enabled = setLaunchAtLogin(fakeApp, true);
  assert.equal(enabled.enabled, true);
  assert.equal(enabled.openAsHidden, true);

  const disabled = setLaunchAtLogin(fakeApp, false);
  assert.equal(disabled.enabled, false);
  assert.equal(disabled.openAsHidden, false);
});
