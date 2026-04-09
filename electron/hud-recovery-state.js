function buildDefaultHudRecoveryState() {
  return {
    generation: 0,
    currentPid: null,
    previousPid: null,
    childAlive: false,
    lastReadyAtMs: 0,
    lastHealthOkAtMs: 0,
    lastPerceptionOkAtMs: 0,
    lastAuthorityStateOkAtMs: 0,
    lastFailure: null,
    recovery: {
      id: 0,
      attempt: 0,
      reason: "",
      generation: 0,
      timerActive: false,
      inFlight: false,
      scheduledAtMs: 0,
      startedAtMs: 0,
      completedAtMs: 0,
    },
  };
}

function normalizeHudRecoveryState(state = {}) {
  const base = buildDefaultHudRecoveryState();
  const next = {
    ...base,
    ...(state && typeof state === "object" ? state : {}),
    recovery: {
      ...base.recovery,
      ...(state?.recovery && typeof state.recovery === "object" ? state.recovery : {}),
    },
  };
  next.generation = Math.max(0, Number(next.generation || 0));
  next.currentPid =
    next.currentPid === null || next.currentPid === undefined || next.currentPid === ""
      ? null
      : Number.isFinite(Number(next.currentPid))
        ? Number(next.currentPid)
        : null;
  next.previousPid =
    next.previousPid === null || next.previousPid === undefined || next.previousPid === ""
      ? null
      : Number.isFinite(Number(next.previousPid))
        ? Number(next.previousPid)
        : null;
  next.childAlive = Boolean(next.childAlive);
  next.lastReadyAtMs = Math.max(0, Number(next.lastReadyAtMs || 0));
  next.lastHealthOkAtMs = Math.max(0, Number(next.lastHealthOkAtMs || 0));
  next.lastPerceptionOkAtMs = Math.max(0, Number(next.lastPerceptionOkAtMs || 0));
  next.lastAuthorityStateOkAtMs = Math.max(0, Number(next.lastAuthorityStateOkAtMs || 0));
  next.lastFailure = next.lastFailure && typeof next.lastFailure === "object" ? { ...next.lastFailure } : null;
  next.recovery.id = Math.max(0, Number(next.recovery.id || 0));
  next.recovery.attempt = Math.max(0, Number(next.recovery.attempt || 0));
  next.recovery.reason = String(next.recovery.reason || "");
  next.recovery.generation = Math.max(0, Number(next.recovery.generation || 0));
  next.recovery.timerActive = Boolean(next.recovery.timerActive);
  next.recovery.inFlight = Boolean(next.recovery.inFlight);
  next.recovery.scheduledAtMs = Math.max(0, Number(next.recovery.scheduledAtMs || 0));
  next.recovery.startedAtMs = Math.max(0, Number(next.recovery.startedAtMs || 0));
  next.recovery.completedAtMs = Math.max(0, Number(next.recovery.completedAtMs || 0));
  return next;
}

function noteHudGenerationReady(state = {}, { pid = null, nowMs = Date.now() } = {}) {
  const current = normalizeHudRecoveryState(state);
  const nextPid = Number.isFinite(Number(pid)) ? Number(pid) : null;
  const samePid = current.generation > 0 && current.currentPid === nextPid;
  const nextGeneration = samePid ? current.generation : current.generation + 1;
  return normalizeHudRecoveryState({
    ...current,
    generation: nextGeneration,
    previousPid: samePid ? current.previousPid : current.currentPid,
    currentPid: nextPid,
    childAlive: nextPid !== null,
    lastReadyAtMs: nowMs,
  });
}

function noteHudProcessState(state = {}, { pid = null, alive = false } = {}) {
  const current = normalizeHudRecoveryState(state);
  const nextPid = Number.isFinite(Number(pid)) ? Number(pid) : current.currentPid;
  return normalizeHudRecoveryState({
    ...current,
    currentPid: nextPid,
    childAlive: Boolean(alive && nextPid !== null),
  });
}

function noteHudEndpointSuccess(state = {}, { channel = "", generation = 0, nowMs = Date.now() } = {}) {
  const current = normalizeHudRecoveryState(state);
  if (Number(generation || 0) !== current.generation) {
    return {
      state: current,
      ignored: true,
    };
  }
  const patch = {
    ...current,
  };
  if (channel === "health") {
    patch.lastHealthOkAtMs = nowMs;
  } else if (channel === "perception") {
    patch.lastPerceptionOkAtMs = nowMs;
  } else if (channel === "authority_state") {
    patch.lastAuthorityStateOkAtMs = nowMs;
  }
  return {
    state: normalizeHudRecoveryState(patch),
    ignored: false,
  };
}

function noteHudEndpointFailure(state = {}, {
  channel = "",
  generation = 0,
  nowMs = Date.now(),
  kind = "unknown",
  message = "",
  statusCode = 0,
} = {}) {
  const current = normalizeHudRecoveryState(state);
  if (Number(generation || 0) !== current.generation) {
    return {
      state: current,
      ignored: true,
    };
  }
  return {
    state: normalizeHudRecoveryState({
      ...current,
      lastFailure: {
        channel: String(channel || ""),
        generation: current.generation,
        kind: String(kind || "unknown"),
        message: String(message || ""),
        statusCode: Number.isFinite(Number(statusCode)) ? Number(statusCode) : 0,
        atMs: nowMs,
      },
    }),
    ignored: false,
  };
}

function scheduleHudRecovery(state = {}, { reason = "", nowMs = Date.now(), maxAttempts = 3 } = {}) {
  const current = normalizeHudRecoveryState(state);
  if (current.recovery.timerActive || current.recovery.inFlight) {
    return {
      state: current,
      scheduled: false,
      duplicate: true,
      exhausted: false,
      recoveryId: current.recovery.id,
    };
  }
  if (current.recovery.attempt >= Math.max(1, Number(maxAttempts || 1))) {
    return {
      state: current,
      scheduled: false,
      duplicate: false,
      exhausted: true,
      recoveryId: current.recovery.id,
    };
  }
  const nextId = current.recovery.id + 1;
  return {
    state: normalizeHudRecoveryState({
      ...current,
      recovery: {
        ...current.recovery,
        id: nextId,
        attempt: current.recovery.attempt + 1,
        reason: String(reason || ""),
        generation: current.generation,
        timerActive: true,
        inFlight: false,
        scheduledAtMs: nowMs,
      },
    }),
    scheduled: true,
    duplicate: false,
    exhausted: false,
    recoveryId: nextId,
  };
}

function beginHudRecoveryAttempt(state = {}, { recoveryId = 0, nowMs = Date.now() } = {}) {
  const current = normalizeHudRecoveryState(state);
  if (Number(recoveryId || 0) !== current.recovery.id || !current.recovery.timerActive) {
    return {
      state: current,
      started: false,
    };
  }
  return {
    state: normalizeHudRecoveryState({
      ...current,
      recovery: {
        ...current.recovery,
        timerActive: false,
        inFlight: true,
        startedAtMs: nowMs,
      },
    }),
    started: true,
  };
}

function finishHudRecoveryAttempt(state = {}, { recoveryId = 0, success = false, nowMs = Date.now() } = {}) {
  const current = normalizeHudRecoveryState(state);
  if (Number(recoveryId || 0) !== current.recovery.id) {
    return current;
  }
  return normalizeHudRecoveryState({
    ...current,
    recovery: {
      ...current.recovery,
      timerActive: false,
      inFlight: false,
      completedAtMs: nowMs,
      attempt: success ? 0 : current.recovery.attempt,
      reason: success ? "" : current.recovery.reason,
    },
  });
}

function isStaleHudGeneration(state = {}, generation = 0) {
  return Number(generation || 0) !== normalizeHudRecoveryState(state).generation;
}

module.exports = {
  beginHudRecoveryAttempt,
  buildDefaultHudRecoveryState,
  finishHudRecoveryAttempt,
  isStaleHudGeneration,
  normalizeHudRecoveryState,
  noteHudEndpointFailure,
  noteHudEndpointSuccess,
  noteHudGenerationReady,
  noteHudProcessState,
  scheduleHudRecovery,
};
