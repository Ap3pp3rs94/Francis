const ORB_EXECUTION_PHASES = Object.freeze({
  IDLE_ANCHORED: "idle_anchored",
  TARGET_LOCK: "target_lock",
  COMMIT_MOVE: "commit_move",
  HOVER_READY: "hover_ready",
  CLICK_ACT: "click_act",
  DRAG_ACT: "drag_act",
  TYPE_HOLD: "type_hold",
  BLOCKED: "blocked",
  INTERRUPTED: "interrupted",
});

const ACTIVE_PHASE_BY_KIND = Object.freeze({
  "mouse.move": ORB_EXECUTION_PHASES.COMMIT_MOVE,
  "mouse.click": ORB_EXECUTION_PHASES.COMMIT_MOVE,
  "mouse.drag": ORB_EXECUTION_PHASES.COMMIT_MOVE,
  "keyboard.type": ORB_EXECUTION_PHASES.TYPE_HOLD,
  "keyboard.key": ORB_EXECUTION_PHASES.TYPE_HOLD,
  "keyboard.shortcut": ORB_EXECUTION_PHASES.TYPE_HOLD,
});

const FINAL_PHASE_BY_KIND = Object.freeze({
  "mouse.move": ORB_EXECUTION_PHASES.COMMIT_MOVE,
  "mouse.click": ORB_EXECUTION_PHASES.CLICK_ACT,
  "mouse.drag": ORB_EXECUTION_PHASES.DRAG_ACT,
  "keyboard.type": ORB_EXECUTION_PHASES.TYPE_HOLD,
  "keyboard.key": ORB_EXECUTION_PHASES.TYPE_HOLD,
  "keyboard.shortcut": ORB_EXECUTION_PHASES.TYPE_HOLD,
});

function cleanText(value, fallback = "") {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text || fallback;
}

function normalizeCommandKind(value) {
  return cleanText(value).toLowerCase();
}

function normalizeExecutionPhase(value, fallback = ORB_EXECUTION_PHASES.IDLE_ANCHORED) {
  const normalized = cleanText(value).toLowerCase();
  if (Object.values(ORB_EXECUTION_PHASES).includes(normalized)) {
    return normalized;
  }
  return fallback;
}

function normalizeCoordinateSpace(value, fallback = "screen") {
  const normalized = cleanText(value).toLowerCase();
  return normalized === "display" ? "display" : fallback;
}

function buildExecutionTarget(args = {}, fallback = null, coordinateSpace = "screen") {
  if (fallback && Number.isFinite(Number(fallback.x)) && Number.isFinite(Number(fallback.y))) {
    return {
      x: Math.round(Number(fallback.x)),
      y: Math.round(Number(fallback.y)),
      coordinate_space: normalizeCoordinateSpace(fallback.coordinate_space || fallback.coordinateSpace, coordinateSpace),
    };
  }
  if (!Number.isFinite(Number(args.x)) || !Number.isFinite(Number(args.y))) {
    return null;
  }
  return {
    x: Math.round(Number(args.x)),
    y: Math.round(Number(args.y)),
    coordinate_space: normalizeCoordinateSpace(args.coordinate_space || args.coordinateSpace, coordinateSpace),
  };
}

function deriveExecutionPhase(kind, {
  status = "claimed",
  explicitPhase = "",
  humanReturned = false,
} = {}) {
  const normalizedKind = normalizeCommandKind(kind);
  const normalizedStatus = cleanText(status, "claimed").toLowerCase();
  const phaseHint = normalizeExecutionPhase(explicitPhase, "");
  if (phaseHint) {
    return phaseHint;
  }
  if (humanReturned || normalizedStatus === "released" || normalizedStatus === "canceled") {
    return ORB_EXECUTION_PHASES.INTERRUPTED;
  }
  if (normalizedStatus === "failed") {
    return ORB_EXECUTION_PHASES.BLOCKED;
  }
  if (normalizedStatus === "hover_ready") {
    return ORB_EXECUTION_PHASES.HOVER_READY;
  }
  if (normalizedStatus === "completed") {
    return FINAL_PHASE_BY_KIND[normalizedKind] || ACTIVE_PHASE_BY_KIND[normalizedKind] || ORB_EXECUTION_PHASES.TARGET_LOCK;
  }
  return ACTIVE_PHASE_BY_KIND[normalizedKind] || ORB_EXECUTION_PHASES.TARGET_LOCK;
}

function deriveExecutionSummary(kind, phase, { args = {}, status = "claimed" } = {}) {
  const normalizedKind = normalizeCommandKind(kind);
  const normalizedPhase = normalizeExecutionPhase(phase);
  const normalizedStatus = cleanText(status, "claimed").toLowerCase();
  const button = cleanText(args.button, "left").toLowerCase() === "right" ? "Right click" : "Click";
  if (normalizedPhase === ORB_EXECUTION_PHASES.INTERRUPTED) {
    return "Yielding cleanly.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.BLOCKED) {
    return normalizedStatus === "failed" ? "Execution blocked." : "Backing off to reassess.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.HOVER_READY) {
    return normalizedKind === "mouse.click"
      ? "Holding poised contact before click."
      : "Holding poised contact.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.CLICK_ACT) {
    return normalizedStatus === "completed"
      ? `${button} committed cleanly.`
      : `${button} is committing now.`;
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.DRAG_ACT) {
    return normalizedStatus === "completed"
      ? "Drag completed cleanly."
      : "Anchored drag control is live.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.TYPE_HOLD) {
    if (normalizedKind === "keyboard.shortcut") {
      return normalizedStatus === "completed" ? "Shortcut committed cleanly." : "Holding the active shortcut lane.";
    }
    if (normalizedKind === "keyboard.key") {
      return normalizedStatus === "completed" ? "Key committed cleanly." : "Holding the active key lane.";
    }
    return normalizedStatus === "completed" ? "Typing completed cleanly." : "Holding the active typing lane.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.COMMIT_MOVE) {
    if (normalizedKind === "mouse.move") {
      return normalizedStatus === "completed" ? "Move completed cleanly." : "Travelling directly to the grounded point.";
    }
    if (normalizedKind === "mouse.drag") {
      return "Committing to the drag path.";
    }
    if (normalizedKind === "mouse.click") {
      return "Committed to the grounded click point.";
    }
    return "Committing to the execution path.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.TARGET_LOCK) {
    return "Execution target is locked.";
  }
  return "Execution is ready.";
}

function deriveExecutionDetail(kind, phase, { args = {}, status = "claimed" } = {}) {
  const normalizedKind = normalizeCommandKind(kind);
  const normalizedPhase = normalizeExecutionPhase(phase);
  const normalizedStatus = cleanText(status, "claimed").toLowerCase();
  if (normalizedPhase === ORB_EXECUTION_PHASES.INTERRUPTED) {
    return "Francis released execution posture deliberately and yielded control.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.BLOCKED) {
    return normalizedStatus === "failed"
      ? "The command could not complete cleanly, so Francis is holding a blocked execution posture."
      : "Francis backed off the action path and is reassessing before recommitting.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.HOVER_READY) {
    return "Francis is holding directly over the target so contact reads as intentional before actuation.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.CLICK_ACT) {
    return "Francis is pulsing a short, controlled click directly through the grounded target.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.DRAG_ACT) {
    return "Francis is maintaining anchored contact and tension across the drag path.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.TYPE_HOLD) {
    if (normalizedKind === "keyboard.shortcut") {
      return "Francis is holding a stable execution posture while the shortcut commits through the active context.";
    }
    if (normalizedKind === "keyboard.key") {
      return "Francis is holding a stable execution posture while the key commits through the active context.";
    }
    return "Francis is holding a stable execution posture while typing through the active context.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.COMMIT_MOVE) {
    if (normalizedKind === "mouse.drag") {
      return "Francis is advancing with resolve into the drag path before sustained contact takes over.";
    }
    if (normalizedKind === "mouse.click") {
      return "Francis is advancing with resolve toward the grounded click point.";
    }
    if (normalizedKind === "mouse.move") {
      return "Francis is physically travelling to the grounded execution point.";
    }
    return "Francis is advancing directly into the execution path.";
  }
  if (normalizedPhase === ORB_EXECUTION_PHASES.TARGET_LOCK) {
    return "Francis has stabilized the target and is holding a pre-commit execution lock.";
  }
  return cleanText(args.reason, "Execution posture is stable.");
}

function buildOrbExecutionSemantics({
  kind,
  args = {},
  status = "claimed",
  explicitPhase = "",
  target = null,
  humanReturned = false,
} = {}) {
  const normalizedKind = normalizeCommandKind(kind);
  if (!normalizedKind) {
    return null;
  }
  const phase = deriveExecutionPhase(normalizedKind, {
    status,
    explicitPhase,
    humanReturned,
  });
  return {
    kind: normalizedKind,
    phase,
    body_state_hint: phase,
    summary: deriveExecutionSummary(normalizedKind, phase, { args, status }),
    detail: deriveExecutionDetail(normalizedKind, phase, { args, status }),
    target: buildExecutionTarget(args, target),
    hover_ready_capable: normalizedKind === "mouse.click",
    click_pulse: phase === ORB_EXECUTION_PHASES.CLICK_ACT,
    sustained_contact: phase === ORB_EXECUTION_PHASES.DRAG_ACT || phase === ORB_EXECUTION_PHASES.TYPE_HOLD,
  };
}

module.exports = {
  ORB_EXECUTION_PHASES,
  buildExecutionTarget,
  buildOrbExecutionSemantics,
  cleanText,
  deriveExecutionPhase,
  deriveExecutionSummary,
  normalizeCommandKind,
  normalizeExecutionPhase,
};
