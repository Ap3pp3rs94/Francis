function canEngageOrbAuthority({ eligible = false, idleSeconds = 0, thresholdSeconds = 30 } = {}) {
  return Boolean(eligible) && Number(idleSeconds || 0) >= Number(thresholdSeconds || 30);
}

function inferOrbAuthorityState({ eligible = false, live = false, idleSeconds = 0, thresholdSeconds = 30, handback = false } = {}) {
  if (handback) {
    return "handback";
  }
  if (Boolean(live)) {
    return "francis_authority";
  }
  if (Boolean(eligible) && Number(idleSeconds || 0) > 0 && Number(idleSeconds || 0) < Number(thresholdSeconds || 30)) {
    return "idle_armed";
  }
  return "human_active";
}

function detectHumanCursorReturn({
  live = false,
  currentCursor = null,
  syntheticCursor = null,
  lastSyntheticAtMs = 0,
  nowMs = Date.now(),
  tolerancePx = 12,
  syntheticGraceMs = 220,
} = {}) {
  if (!live || !currentCursor || !syntheticCursor) {
    return false;
  }
  if (Number(nowMs || 0) - Number(lastSyntheticAtMs || 0) <= Number(syntheticGraceMs || 220)) {
    return false;
  }
  const dx = Number(currentCursor.x || 0) - Number(syntheticCursor.x || 0);
  const dy = Number(currentCursor.y || 0) - Number(syntheticCursor.y || 0);
  return Math.hypot(dx, dy) > Number(tolerancePx || 12);
}

function detectHumanKeyboardReturn({ live = false, idleSeconds = 0, lastSyntheticAtMs = 0, nowMs = Date.now(), syntheticGraceMs = 1500 } = {}) {
  if (!live) {
    return false;
  }
  if (Number(nowMs || 0) - Number(lastSyntheticAtMs || 0) <= Number(syntheticGraceMs || 1500)) {
    return false;
  }
  return Number(idleSeconds || 0) === 0;
}

function detectHumanActivitySignal({
  live = false,
  lastHumanActivitySignalAtMs = 0,
  lastSyntheticAtMs = 0,
  nowMs = Date.now(),
  signalGraceMs = 160,
} = {}) {
  if (!live) {
    return false;
  }
  const signalAt = Number(lastHumanActivitySignalAtMs || 0);
  if (signalAt <= 0) {
    return false;
  }
  if (signalAt <= Number(lastSyntheticAtMs || 0)) {
    return false;
  }
  return Number(nowMs || 0) - signalAt <= Number(signalGraceMs || 160);
}

module.exports = {
  canEngageOrbAuthority,
  detectHumanActivitySignal,
  detectHumanCursorReturn,
  detectHumanKeyboardReturn,
  inferOrbAuthorityState,
};
