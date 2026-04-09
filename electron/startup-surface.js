const { resolveStartupProfile } = require("./startup-profile");

function resolveStartupSurface(preferences, { recoveryNeeded = false } = {}) {
  const startupProfile = resolveStartupProfile(preferences, { recoveryNeeded });

  return {
    startupProfile,
    bootOrbWindow: true,
    showOrbWindowOnBoot: Boolean(startupProfile.visible),
    constructLensWindowOnBoot: false,
    bootLensWindow: false,
    showLensWindowOnBoot: false,
    lensBootstrap: "explicit",
    visibleStartupBody: startupProfile.visible ? "orb" : "none",
    orbFirst: true,
  };
}

function resolveOrbFirstAppActivation({
  orbVisible = false,
  lensVisible = false,
} = {}) {
  const hasVisibleSurface = Boolean(orbVisible) || Boolean(lensVisible);
  return {
    ensureOrbWindow: true,
    showOrbWindow: !hasVisibleSurface,
    reason: hasVisibleSurface ? "activate_noop" : "activate_show_orb",
  };
}

function resolveOrbFirstSecondInstance({
  orbVisible = false,
  lensVisible = false,
} = {}) {
  return {
    ensureOrbWindow: true,
    showOrbWindow: true,
    preserveLensWindow: Boolean(lensVisible),
    reason: Boolean(orbVisible) ? "second_instance_focus_orb" : "second_instance_show_orb",
  };
}

module.exports = {
  resolveOrbFirstAppActivation,
  resolveOrbFirstSecondInstance,
  resolveStartupSurface,
};
