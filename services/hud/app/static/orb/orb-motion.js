(function (globalScope, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  globalScope.FrancisOrbMotion = factory();
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  const ORB_BODY_STATES = Object.freeze({
    IDLE_ANCHORED: "idle_anchored",
    ATTENTIVE: "attentive",
    INVESTIGATE: "investigate",
    TARGET_LOCK: "target_lock",
    COMMIT_MOVE: "commit_move",
    HOVER_READY: "hover_ready",
    CLICK_ACT: "click_act",
    DRAG_ACT: "drag_act",
    TYPE_HOLD: "type_hold",
    WAITING_USER: "waiting_user",
    BLOCKED: "blocked",
    INTERRUPTED: "interrupted",
    DEGRADED: "degraded",
    PAUSED: "paused",
  });

  const LEGACY_BODY_STATE_ALIASES = Object.freeze({
    waiting_for_user: ORB_BODY_STATES.WAITING_USER,
    blocked_uncertain: ORB_BODY_STATES.BLOCKED,
    abort_interrupted: ORB_BODY_STATES.INTERRUPTED,
  });

  const COMMIT_STATES = new Set([
    ORB_BODY_STATES.COMMIT_MOVE,
    ORB_BODY_STATES.HOVER_READY,
    ORB_BODY_STATES.CLICK_ACT,
    ORB_BODY_STATES.DRAG_ACT,
    ORB_BODY_STATES.TYPE_HOLD,
    ORB_BODY_STATES.TARGET_LOCK,
  ]);
  const REST_STATES = new Set([
    ORB_BODY_STATES.IDLE_ANCHORED,
    ORB_BODY_STATES.ATTENTIVE,
    ORB_BODY_STATES.WAITING_USER,
    ORB_BODY_STATES.PAUSED,
    ORB_BODY_STATES.DEGRADED,
  ]);

  const ORB_STATE_DESCRIPTORS = Object.freeze({
    [ORB_BODY_STATES.IDLE_ANCHORED]: {
      anchorLabel: "resident perch",
      motionLabel: "anchored idle",
      summary: "Resting at an intentional perch.",
    },
    [ORB_BODY_STATES.ATTENTIVE]: {
      anchorLabel: "workspace edge",
      motionLabel: "attentive bias",
      summary: "Holding nearby and listening.",
    },
    [ORB_BODY_STATES.INVESTIGATE]: {
      anchorLabel: "candidate target",
      motionLabel: "investigation arc",
      summary: "Inspecting candidate UI regions.",
    },
    [ORB_BODY_STATES.TARGET_LOCK]: {
      anchorLabel: "target lock",
      motionLabel: "lock compression",
      summary: "Target confidence is high and motion is tightening.",
    },
    [ORB_BODY_STATES.COMMIT_MOVE]: {
      anchorLabel: "execution path",
      motionLabel: "commit move",
      summary: "Travelling directly to the execution point.",
    },
    [ORB_BODY_STATES.HOVER_READY]: {
      anchorLabel: "execution point",
      motionLabel: "hover dwell",
      summary: "Holding over the control before acting.",
    },
    [ORB_BODY_STATES.CLICK_ACT]: {
      anchorLabel: "click point",
      motionLabel: "click pulse",
      summary: "Committing a click with visible confirmation.",
    },
    [ORB_BODY_STATES.DRAG_ACT]: {
      anchorLabel: "drag path",
      motionLabel: "drag tension",
      summary: "Maintaining contact and tension during drag.",
    },
    [ORB_BODY_STATES.TYPE_HOLD]: {
      anchorLabel: "typing context",
      motionLabel: "type hold",
      summary: "Holding near the insertion context while typing.",
    },
    [ORB_BODY_STATES.WAITING_USER]: {
      anchorLabel: "respectful side anchor",
      motionLabel: "paused and attentive",
      summary: "Waiting for user confirmation without camping on the control.",
    },
    [ORB_BODY_STATES.BLOCKED]: {
      anchorLabel: "reassessment edge",
      motionLabel: "hesitate and recoil",
      summary: "Confidence dropped and the orb is reassessing.",
    },
    [ORB_BODY_STATES.INTERRUPTED]: {
      anchorLabel: "return path",
      motionLabel: "graceful retreat",
      summary: "Backing off cleanly after interruption or handback.",
    },
    [ORB_BODY_STATES.DEGRADED]: {
      anchorLabel: "guarded perch",
      motionLabel: "degraded hold",
      summary: "Holding a stable perch while runtime confidence is reduced.",
    },
    [ORB_BODY_STATES.PAUSED]: {
      anchorLabel: "pause hold",
      motionLabel: "paused hold",
      summary: "Paused locally and holding a respectful perch.",
    },
  });

  const ORB_ALLOWED_TRANSITIONS = Object.freeze({
    [ORB_BODY_STATES.IDLE_ANCHORED]: Object.freeze([
      ORB_BODY_STATES.ATTENTIVE,
      ORB_BODY_STATES.INVESTIGATE,
      ORB_BODY_STATES.TARGET_LOCK,
      ORB_BODY_STATES.COMMIT_MOVE,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
    ]),
    [ORB_BODY_STATES.ATTENTIVE]: Object.freeze([
      ORB_BODY_STATES.IDLE_ANCHORED,
      ORB_BODY_STATES.INVESTIGATE,
      ORB_BODY_STATES.TARGET_LOCK,
      ORB_BODY_STATES.COMMIT_MOVE,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
    ]),
    [ORB_BODY_STATES.INVESTIGATE]: Object.freeze([
      ORB_BODY_STATES.ATTENTIVE,
      ORB_BODY_STATES.TARGET_LOCK,
      ORB_BODY_STATES.COMMIT_MOVE,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
      ORB_BODY_STATES.IDLE_ANCHORED,
    ]),
    [ORB_BODY_STATES.TARGET_LOCK]: Object.freeze([
      ORB_BODY_STATES.INVESTIGATE,
      ORB_BODY_STATES.COMMIT_MOVE,
      ORB_BODY_STATES.HOVER_READY,
      ORB_BODY_STATES.CLICK_ACT,
      ORB_BODY_STATES.DRAG_ACT,
      ORB_BODY_STATES.TYPE_HOLD,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
    ]),
    [ORB_BODY_STATES.COMMIT_MOVE]: Object.freeze([
      ORB_BODY_STATES.TARGET_LOCK,
      ORB_BODY_STATES.HOVER_READY,
      ORB_BODY_STATES.CLICK_ACT,
      ORB_BODY_STATES.DRAG_ACT,
      ORB_BODY_STATES.TYPE_HOLD,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
      ORB_BODY_STATES.IDLE_ANCHORED,
    ]),
    [ORB_BODY_STATES.HOVER_READY]: Object.freeze([
      ORB_BODY_STATES.COMMIT_MOVE,
      ORB_BODY_STATES.CLICK_ACT,
      ORB_BODY_STATES.DRAG_ACT,
      ORB_BODY_STATES.TYPE_HOLD,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
    ]),
    [ORB_BODY_STATES.CLICK_ACT]: Object.freeze([
      ORB_BODY_STATES.IDLE_ANCHORED,
      ORB_BODY_STATES.ATTENTIVE,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
    ]),
    [ORB_BODY_STATES.DRAG_ACT]: Object.freeze([
      ORB_BODY_STATES.COMMIT_MOVE,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
      ORB_BODY_STATES.IDLE_ANCHORED,
    ]),
    [ORB_BODY_STATES.TYPE_HOLD]: Object.freeze([
      ORB_BODY_STATES.COMMIT_MOVE,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
      ORB_BODY_STATES.IDLE_ANCHORED,
    ]),
    [ORB_BODY_STATES.WAITING_USER]: Object.freeze([
      ORB_BODY_STATES.ATTENTIVE,
      ORB_BODY_STATES.INVESTIGATE,
      ORB_BODY_STATES.TARGET_LOCK,
      ORB_BODY_STATES.COMMIT_MOVE,
      ORB_BODY_STATES.BLOCKED,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
      ORB_BODY_STATES.IDLE_ANCHORED,
    ]),
    [ORB_BODY_STATES.BLOCKED]: Object.freeze([
      ORB_BODY_STATES.ATTENTIVE,
      ORB_BODY_STATES.INVESTIGATE,
      ORB_BODY_STATES.TARGET_LOCK,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.INTERRUPTED,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
      ORB_BODY_STATES.IDLE_ANCHORED,
    ]),
    [ORB_BODY_STATES.INTERRUPTED]: Object.freeze([
      ORB_BODY_STATES.IDLE_ANCHORED,
      ORB_BODY_STATES.ATTENTIVE,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.DEGRADED,
      ORB_BODY_STATES.PAUSED,
    ]),
    [ORB_BODY_STATES.DEGRADED]: Object.freeze([
      ORB_BODY_STATES.PAUSED,
      ORB_BODY_STATES.IDLE_ANCHORED,
      ORB_BODY_STATES.ATTENTIVE,
      ORB_BODY_STATES.INVESTIGATE,
      ORB_BODY_STATES.WAITING_USER,
    ]),
    [ORB_BODY_STATES.PAUSED]: Object.freeze([
      ORB_BODY_STATES.IDLE_ANCHORED,
      ORB_BODY_STATES.ATTENTIVE,
      ORB_BODY_STATES.INVESTIGATE,
      ORB_BODY_STATES.WAITING_USER,
      ORB_BODY_STATES.DEGRADED,
    ]),
  });

  function normalizeOrbBodyState(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (LEGACY_BODY_STATE_ALIASES[normalized]) {
      return LEGACY_BODY_STATE_ALIASES[normalized];
    }
    const knownState = Object.values(ORB_BODY_STATES).find((candidate) => candidate === normalized);
    return knownState || ORB_BODY_STATES.IDLE_ANCHORED;
  }

  function isOrbTransitionAllowed(previousState, nextState) {
    const from = normalizeOrbBodyState(previousState);
    const to = normalizeOrbBodyState(nextState);
    if (from === to) {
      return true;
    }
    const allowed = ORB_ALLOWED_TRANSITIONS[from] || [];
    return allowed.includes(to);
  }

  function resolveOrbTransitionState(previousState, nextState) {
    const from = normalizeOrbBodyState(previousState);
    const to = normalizeOrbBodyState(nextState);
    if (from === to || isOrbTransitionAllowed(from, to)) {
      return to;
    }
    if (
      to === ORB_BODY_STATES.WAITING_USER
      || to === ORB_BODY_STATES.BLOCKED
      || to === ORB_BODY_STATES.INTERRUPTED
      || to === ORB_BODY_STATES.DEGRADED
      || to === ORB_BODY_STATES.PAUSED
    ) {
      return to;
    }
    if (to === ORB_BODY_STATES.INVESTIGATE) {
      return from === ORB_BODY_STATES.IDLE_ANCHORED ? ORB_BODY_STATES.ATTENTIVE : ORB_BODY_STATES.INVESTIGATE;
    }
    if (to === ORB_BODY_STATES.TARGET_LOCK) {
      return (
        from === ORB_BODY_STATES.IDLE_ANCHORED
        || from === ORB_BODY_STATES.ATTENTIVE
        || from === ORB_BODY_STATES.WAITING_USER
        || from === ORB_BODY_STATES.BLOCKED
        || from === ORB_BODY_STATES.INTERRUPTED
      )
        ? ORB_BODY_STATES.INVESTIGATE
        : ORB_BODY_STATES.TARGET_LOCK;
    }
    if (to === ORB_BODY_STATES.COMMIT_MOVE) {
      if (from === ORB_BODY_STATES.IDLE_ANCHORED) {
        return ORB_BODY_STATES.ATTENTIVE;
      }
      if (
        from === ORB_BODY_STATES.ATTENTIVE
        || from === ORB_BODY_STATES.WAITING_USER
        || from === ORB_BODY_STATES.BLOCKED
        || from === ORB_BODY_STATES.INTERRUPTED
      ) {
        return ORB_BODY_STATES.INVESTIGATE;
      }
      return ORB_BODY_STATES.TARGET_LOCK;
    }
    if (to === ORB_BODY_STATES.HOVER_READY) {
      return ORB_BODY_STATES.HOVER_READY;
    }
    if (to === ORB_BODY_STATES.CLICK_ACT) {
      if (from === ORB_BODY_STATES.HOVER_READY) {
        return ORB_BODY_STATES.CLICK_ACT;
      }
      return from === ORB_BODY_STATES.TARGET_LOCK ? ORB_BODY_STATES.HOVER_READY : ORB_BODY_STATES.COMMIT_MOVE;
    }
    if (to === ORB_BODY_STATES.DRAG_ACT || to === ORB_BODY_STATES.TYPE_HOLD) {
      return to;
    }
    return to;
  }

  function clamp(value, lower, upper) {
    return Math.max(lower, Math.min(upper, value));
  }

  function roundNumber(value) {
    return Number.isFinite(value) ? Math.round(value) : 0;
  }

  function isFinitePoint(value) {
    return Boolean(
      value
      && Number.isFinite(Number(value.x))
      && Number.isFinite(Number(value.y)),
    );
  }

  function normalizePoint(value, fallback = null) {
    if (!isFinitePoint(value)) {
      return fallback;
    }
    return {
      x: roundNumber(Number(value.x)),
      y: roundNumber(Number(value.y)),
    };
  }

  function normalizeRect(value, fallback) {
    const source = value && typeof value === "object" ? value : {};
    return {
      x: roundNumber(Number(source.x ?? fallback.x)),
      y: roundNumber(Number(source.y ?? fallback.y)),
      width: Math.max(1, roundNumber(Number(source.width ?? fallback.width))),
      height: Math.max(1, roundNumber(Number(source.height ?? fallback.height))),
    };
  }

  function resolveFrame(input, viewportWidth, viewportHeight) {
    const defaultRect = {
      x: 0,
      y: 0,
      width: Math.max(1, roundNumber(Number(viewportWidth || 1))),
      height: Math.max(1, roundNumber(Number(viewportHeight || 1))),
    };
    const overlayBounds = normalizeRect(input?.overlayBounds, defaultRect);
    const bounds = normalizeRect(input?.displayBounds, overlayBounds);
    const workArea = normalizeRect(input?.displayWorkArea, bounds);
    const originX = Number(overlayBounds.x || 0);
    const originY = Number(overlayBounds.y || 0);
    return {
      overlayBounds,
      bounds: {
        x: bounds.x - originX,
        y: bounds.y - originY,
        width: bounds.width,
        height: bounds.height,
      },
      workArea: {
        x: workArea.x - originX,
        y: workArea.y - originY,
        width: workArea.width,
        height: workArea.height,
      },
    };
  }

  function resolveTaskbarEdge(bounds, workArea) {
    const insets = {
      top: Math.max(0, Number(workArea.y || 0) - Number(bounds.y || 0)),
      left: Math.max(0, Number(workArea.x || 0) - Number(bounds.x || 0)),
      right: Math.max(
        0,
        Number(bounds.x || 0) + Number(bounds.width || 0) - (Number(workArea.x || 0) + Number(workArea.width || 0)),
      ),
      bottom: Math.max(
        0,
        Number(bounds.y || 0) + Number(bounds.height || 0) - (Number(workArea.y || 0) + Number(workArea.height || 0)),
      ),
    };
    let edge = "bottom";
    let thickness = insets.bottom;
    for (const candidate of ["top", "left", "right", "bottom"]) {
      if (insets[candidate] > thickness) {
        edge = candidate;
        thickness = insets[candidate];
      }
    }
    return {
      edge,
      thickness: Math.max(0, thickness),
      insets,
    };
  }

  function pointInsideRect(point, rect) {
    return Boolean(
      isFinitePoint(point)
      && point.x >= rect.x
      && point.x <= rect.x + rect.width
      && point.y >= rect.y
      && point.y <= rect.y + rect.height
    );
  }

  function toOverlayPoint(rawPoint, overlayBounds) {
    const point = normalizePoint(rawPoint);
    if (!point) {
      return null;
    }
    return {
      x: point.x - Number(overlayBounds.x || 0),
      y: point.y - Number(overlayBounds.y || 0),
    };
  }

  function resolveCommandTargetPoint({
    authority,
    operator,
    input,
    overlayBounds,
    perception,
    targetCue,
    targetConfidence,
    targetStability,
    cursorAuthority,
    forceInvestigate = false,
    previousState = "",
  }) {
    const claimed = Array.isArray(authority?.claimed) && authority.claimed.length
      ? authority.claimed[0]
      : null;
    const executionTarget = resolveExecutionTarget(authority, overlayBounds);
    if (executionTarget) {
      return executionTarget;
    }
    const commandSources = [
      claimed,
      operator?.controls?.desktop_run_args ? {
        kind: operator?.controls?.desktop_run_kind,
        args: operator.controls.desktop_run_args,
      } : null,
      operator?.controls?.surface_action_command_args ? {
        kind: operator?.controls?.surface_action_command_kind,
        args: operator.controls.surface_action_command_args,
      } : null,
      operator?.controls?.run_args ? {
        kind: operator?.controls?.run_kind,
        args: operator.controls.run_args,
      } : null,
    ].filter(Boolean);

    for (const source of commandSources) {
      const args = source.args && typeof source.args === "object" ? source.args : {};
      if (!Number.isFinite(Number(args.x)) || !Number.isFinite(Number(args.y))) {
        continue;
      }
      const coordinateSpace = String(args.coordinate_space || args.coordinateSpace || "screen").trim().toLowerCase();
      if (coordinateSpace === "display") {
        const displayBounds = normalizeRect(input?.displayBounds, {
          x: 0,
          y: 0,
          width: overlayBounds.width || 1,
          height: overlayBounds.height || 1,
        });
        return {
          x: roundNumber(Number(displayBounds.x || 0) - Number(overlayBounds.x || 0) + Number(args.x)),
          y: roundNumber(Number(displayBounds.y || 0) - Number(overlayBounds.y || 0) + Number(args.y)),
        };
      }
      return toOverlayPoint({ x: args.x, y: args.y }, overlayBounds);
    }

    const shouldUsePerceptionCursor = Boolean(cursorAuthority)
      || Boolean(forceInvestigate)
      || Boolean(targetCue)
      || String(targetConfidence || "low") !== "low"
      || ["tracking", "settled"].includes(String(targetStability || "idle"));
    if (!shouldUsePerceptionCursor) {
      return null;
    }
    return normalizePoint(input?.cursorDisplay) || normalizePoint(perception?.cursor) || null;
  }

  function resolveActionKind({ authority, operator }) {
    const claimed = Array.isArray(authority?.claimed) && authority.claimed.length
      ? authority.claimed[0]
      : null;
    const recent = Array.isArray(authority?.recent) && authority.recent.length
      ? authority.recent[0]
      : null;
    const values = [
      authority?.activeCommandKind,
      authority?.execution?.kind,
      claimed?.execution?.kind,
      claimed?.kind,
      operator?.controls?.desktop_run_kind,
      operator?.controls?.surface_action_command_kind,
      operator?.controls?.run_kind,
      operator?.focus_kind,
      recent?.execution?.kind,
      recent?.kind,
    ];
    for (const value of values) {
      const normalized = String(value || "").trim().toLowerCase();
      if (normalized) {
        return normalized;
      }
    }
    return "";
  }

  function resolveExecutionPhase(authority = {}) {
    const claimed = Array.isArray(authority?.claimed) && authority.claimed.length
      ? authority.claimed[0]
      : null;
    const recent = Array.isArray(authority?.recent) && authority.recent.length
      ? authority.recent[0]
      : null;
    const values = [
      authority?.executionPhase,
      authority?.execution?.phase,
      claimed?.execution?.phase,
      recent?.execution?.phase,
    ];
    for (const value of values) {
      const normalized = String(value || "").trim().toLowerCase();
      if (normalized) {
        return normalizeOrbBodyState(normalized);
      }
    }
    return "";
  }

  function resolveExecutionTarget(authority = {}, overlayBounds = {}) {
    const claimed = Array.isArray(authority?.claimed) && authority.claimed.length
      ? authority.claimed[0]
      : null;
    const recent = Array.isArray(authority?.recent) && authority.recent.length
      ? authority.recent[0]
      : null;
    const values = [
      authority?.executionTarget,
      authority?.execution?.target,
      claimed?.execution?.target,
      recent?.execution?.target,
    ];
    for (const value of values) {
      const target = value && typeof value === "object" ? value : null;
      if (!target || !Number.isFinite(Number(target.x)) || !Number.isFinite(Number(target.y))) {
        continue;
      }
      const coordinateSpace = String(target.coordinate_space || target.coordinateSpace || "screen").trim().toLowerCase();
      if (coordinateSpace === "display") {
        return {
          x: roundNumber(Number(target.x)),
          y: roundNumber(Number(target.y)),
        };
      }
      return toOverlayPoint({ x: target.x, y: target.y }, overlayBounds);
    }
    return null;
  }

  function resolveTargetConfidence(targetCue, perception) {
    const cueConfidence = String(targetCue?.confidence || "").trim().toLowerCase();
    if (cueConfidence) {
      return cueConfidence;
    }
    return String(perception?.target?.confidence || "low").trim().toLowerCase() || "low";
  }

  function resolveTargetStability(targetCue, perception) {
    const cueValue = String(targetCue?.stability || "").trim().toLowerCase();
    if (cueValue) {
      return cueValue;
    }
    return String(perception?.target?.stability?.state || "idle").trim().toLowerCase() || "idle";
  }

  function resolveAttentionCueState(targetCue, perception) {
    const cueValue = String(targetCue?.attention_state || "").trim().toLowerCase();
    if (cueValue) {
      return cueValue;
    }
    return String(perception?.target?.attention?.state || "idle").trim().toLowerCase() || "idle";
  }

  function resolveAttentionStrength(targetCue, perception, targetConfidence = "low") {
    const cueValue = Number(targetCue?.attention_strength);
    if (Number.isFinite(cueValue)) {
      return clamp(cueValue, 0, 1);
    }
    const perceptionValue = Number(perception?.target?.attention?.strength);
    if (Number.isFinite(perceptionValue)) {
      return clamp(perceptionValue, 0, 1);
    }
    if (String(targetConfidence || "low") === "high" || String(targetConfidence || "low") === "likely") {
      return 0.88;
    }
    if (String(targetConfidence || "low") === "medium") {
      return 0.58;
    }
    return 0.24;
  }

  function resolveAttentionLockStrength(targetCue, perception, targetStability = "idle") {
    const cueValue = Number(targetCue?.lock_strength);
    if (Number.isFinite(cueValue)) {
      return clamp(cueValue, 0, 1);
    }
    const perceptionValue = Number(perception?.target?.attention?.lock_strength);
    if (Number.isFinite(perceptionValue)) {
      return clamp(perceptionValue, 0, 1);
    }
    if (String(targetStability || "idle") === "settled") {
      return 0.84;
    }
    if (String(targetStability || "idle") === "tracking") {
      return 0.46;
    }
    return 0.16;
  }

  function hasInvestigationPressure({
    forceInvestigate = false,
    targetCue = null,
    targetConfidence = "low",
    targetStability = "idle",
    attentionState = "idle",
    attentionStrength = 0,
    perception = null,
  }) {
    if (forceInvestigate) {
      return true;
    }
    if (String(attentionState || "idle") === "target_lock") {
      return true;
    }
    if (String(attentionState || "idle") === "investigate" && Number(attentionStrength || 0) >= 0.34) {
      return true;
    }
    const cueSummary = String(targetCue?.summary || targetCue?.label || targetCue?.reason || "").trim();
    if (cueSummary) {
      return true;
    }
    if (targetCue && typeof targetCue === "object" && String(targetConfidence || "low") !== "low") {
      return true;
    }
    const targetSummary = String(perception?.target?.summary || perception?.target?.label || "").trim();
    const stable = ["tracking", "settled"].includes(String(targetStability || "idle"));
    if (stable && String(targetConfidence || "low") === "high") {
      return true;
    }
    return stable && String(targetConfidence || "low") === "medium" && Boolean(targetSummary);
  }

  function buildMovementConfig(movement = {}) {
    return {
      anchorStrategy: String(movement.anchor_strategy || "edge_window_perch").trim().toLowerCase() || "edge_window_perch",
      safeMarginPx: clamp(Number(movement.safe_margin_px ?? 32), 16, 140),
      taskbarMarginPx: clamp(Number(movement.taskbar_margin_px ?? 18), 8, 72),
      idleAmplitudePx: clamp(Number(movement.idle_amplitude_px ?? 1.2), 0, 28),
      attentiveBias: clamp(Number(movement.attentive_bias ?? 0.08), 0.04, 0.38),
      investigateRadiusPx: clamp(Number(movement.investigate_radius_px ?? 14), 6, 88),
      lockRadiusPx: clamp(Number(movement.lock_radius_px ?? 8), 4, 52),
      windowPerchGapPx: clamp(Number(movement.window_perch_gap_px ?? 148), 40, 220),
      windowPerchVerticalBiasPx: clamp(Number(movement.window_perch_vertical_bias_px ?? 110), 18, 180),
      investigateStandoffPx: clamp(Number(movement.investigate_standoff_px ?? 140), 28, 220),
      lockStandoffPx: clamp(Number(movement.lock_standoff_px ?? 48), 10, 92),
      hoverRadiusPx: clamp(Number(movement.hover_radius_px ?? 16), 6, 48),
      hoverDwellMs: clamp(Number(movement.hover_dwell_ms ?? 140), 40, 520),
      clickPulseMs: clamp(Number(movement.click_pulse_ms ?? 160), 60, 420),
      blockedRecoilPx: clamp(Number(movement.blocked_recoil_px ?? 32), 12, 96),
      typeHoldOffsetXPx: clamp(Number(movement.type_hold_offset_x_px ?? 22), -64, 96),
      typeHoldOffsetYPx: clamp(Number(movement.type_hold_offset_y_px ?? -28), -96, 32),
      idleStiffness: clamp(Number(movement.idle_stiffness ?? 0.22), 0.06, 0.5),
      attentiveStiffness: clamp(Number(movement.attentive_stiffness ?? 0.24), 0.08, 0.52),
      investigateStiffness: clamp(Number(movement.investigate_stiffness ?? 0.24), 0.1, 0.6),
      lockStiffness: clamp(Number(movement.lock_stiffness ?? 0.34), 0.14, 0.72),
      commitStiffness: clamp(Number(movement.commit_stiffness ?? 0.48), 0.2, 0.92),
      hoverStiffness: clamp(Number(movement.hover_stiffness ?? 0.42), 0.16, 0.82),
      dragStiffness: clamp(Number(movement.drag_stiffness ?? 0.58), 0.2, 0.95),
      abortStiffness: clamp(Number(movement.abort_stiffness ?? 0.28), 0.1, 0.64),
      dampingIdle: clamp(Number(movement.damping_idle ?? 0.84), 0.55, 0.95),
      dampingCommit: clamp(Number(movement.damping_commit ?? 0.72), 0.45, 0.92),
      dampingHover: clamp(Number(movement.damping_hover ?? 0.8), 0.55, 0.96),
      clickPulseScale: clamp(Number(movement.click_pulse_scale ?? 0.9), 0.82, 1.02),
      lockScale: clamp(Number(movement.lock_scale ?? 0.942), 0.88, 1.02),
      hoverScale: clamp(Number(movement.hover_scale ?? 0.932), 0.86, 1.02),
      dragScale: clamp(Number(movement.drag_scale ?? 0.918), 0.82, 1.01),
      blockedScale: clamp(Number(movement.blocked_scale ?? 0.97), 0.88, 1.04),
      waitingScale: clamp(Number(movement.waiting_scale ?? 0.972), 0.9, 1.04),
      interruptedScale: clamp(Number(movement.interrupted_scale ?? 0.968), 0.9, 1.04),
      degradedScale: clamp(Number(movement.degraded_scale ?? 0.974), 0.9, 1.04),
      pausedScale: clamp(Number(movement.paused_scale ?? 0.978), 0.9, 1.04),
    };
  }

  function resolveWindowRect(perception, overlayBounds) {
    const bounds = perception?.window?.bounds;
    if (!bounds || typeof bounds !== "object" || Number(bounds.width || 0) <= 0 || Number(bounds.height || 0) <= 0) {
      return null;
    }
    return {
      x: roundNumber(Number(bounds.x || 0) - Number(overlayBounds.x || 0)),
      y: roundNumber(Number(bounds.y || 0) - Number(overlayBounds.y || 0)),
      width: Math.max(1, roundNumber(Number(bounds.width || 0))),
      height: Math.max(1, roundNumber(Number(bounds.height || 0))),
    };
  }

  function pointInsideRect(point, rect, padding = 0) {
    if (!isFinitePoint(point) || !rect) {
      return false;
    }
    const inset = Math.max(0, Number(padding || 0));
    return point.x >= Number(rect.x || 0) - inset
      && point.x <= Number(rect.x || 0) + Number(rect.width || 0) + inset
      && point.y >= Number(rect.y || 0) - inset
      && point.y <= Number(rect.y || 0) + Number(rect.height || 0) + inset;
  }

  function clampPointToWorkArea(point, frame, size, config) {
    const marginX = Math.max(config.safeMarginPx, size * 0.5 + 12);
    const marginY = Math.max(config.safeMarginPx + 8, size * 0.5 + 12);
    return {
      x: clamp(
        Number(point.x || 0),
        Number(frame.workArea.x || 0) + marginX,
        Number(frame.workArea.x || 0) + Number(frame.workArea.width || 0) - marginX,
      ),
      y: clamp(
        Number(point.y || 0),
        Number(frame.workArea.y || 0) + marginY,
        Number(frame.workArea.y || 0) + Number(frame.workArea.height || 0) - marginY,
      ),
    };
  }

  function clampPointToDesktopBounds(point, frame, size, config, { allowTaskbar = false } = {}) {
    const margin = allowTaskbar
      ? config.taskbarMarginPx
      : Math.max(config.safeMarginPx, size * 0.5 + 12);
    return {
      x: clamp(
        Number(point.x || 0),
        Number(frame.bounds.x || 0) + margin,
        Number(frame.bounds.x || 0) + Number(frame.bounds.width || 0) - margin,
      ),
      y: clamp(
        Number(point.y || 0),
        Number(frame.bounds.y || 0) + margin,
        Number(frame.bounds.y || 0) + Number(frame.bounds.height || 0) - margin,
      ),
    };
  }

  function resolvePerchPoint({
    frame,
    windowRect,
    targetPoint,
    previousPoint,
    latchedPerchPoint,
    preferLatchedPerch = false,
    size,
    config,
  }) {
    const latchedPoint = normalizePoint(latchedPerchPoint);
    if (preferLatchedPerch && latchedPoint) {
      return clampPointToWorkArea(latchedPoint, frame, size, config);
    }
    const taskbar = resolveTaskbarEdge(frame.bounds, frame.workArea);
    const margin = Math.max(config.safeMarginPx, size * 0.5 + 16);
    const workCenterX = Number(frame.workArea.x || 0) + Number(frame.workArea.width || 0) * 0.5;
    const workCenterY = Number(frame.workArea.y || 0) + Number(frame.workArea.height || 0) * 0.5;

    if (windowRect) {
      const windowCenterX = Number(windowRect.x || 0) + Number(windowRect.width || 0) * 0.5;
      const windowCenterY = Number(windowRect.y || 0) + Number(windowRect.height || 0) * 0.5;
      const targetBiasX = Number(targetPoint?.x ?? previousPoint?.x ?? windowCenterX);
      const targetBiasY = Number(targetPoint?.y ?? previousPoint?.y ?? (windowRect.y + windowRect.height * 0.5));
      const targetAttached = pointInsideRect(targetPoint, windowRect, 12);
      const side = targetAttached
        ? targetBiasX >= windowCenterX ? "left" : "right"
        : targetBiasX >= windowCenterX ? "right" : "left";
      const horizontalGap = Math.max(config.windowPerchGapPx, size * 0.78);
      const verticalBias = Math.max(config.windowPerchVerticalBiasPx, size * 0.42);
      const verticalDirection = targetAttached
        ? targetBiasY >= windowCenterY ? -1 : 1
        : targetBiasY >= windowCenterY ? 1 : -1;
      const verticalInset = Math.max(30, size * 0.34);
      const candidate = {
        x: side === "right"
          ? windowRect.x + windowRect.width + horizontalGap
          : windowRect.x - horizontalGap,
        y: clamp(
          targetBiasY + verticalDirection * verticalBias,
          windowRect.y + verticalInset,
          windowRect.y + windowRect.height - verticalInset,
        ),
      };
      return clampPointToWorkArea(candidate, frame, size, config);
    }

    let candidate = {
      x: workCenterX + Number(frame.workArea.width || 0) * 0.32,
      y: workCenterY + Number(frame.workArea.height || 0) * 0.26,
    };
    if (taskbar.edge === "bottom") {
      candidate.y = Number(frame.workArea.y || 0) + Number(frame.workArea.height || 0) - margin;
    } else if (taskbar.edge === "top") {
      candidate.y = Number(frame.workArea.y || 0) + margin;
    } else if (taskbar.edge === "left") {
      candidate.x = Number(frame.workArea.x || 0) + margin;
    } else if (taskbar.edge === "right") {
      candidate.x = Number(frame.workArea.x || 0) + Number(frame.workArea.width || 0) - margin;
    }
    return clampPointToWorkArea(candidate, frame, size, config);
  }

  function pointInTaskbar(point, frame) {
    if (!isFinitePoint(point)) {
      return false;
    }
    const taskbar = resolveTaskbarEdge(frame.bounds, frame.workArea);
    if (taskbar.thickness <= 0) {
      return false;
    }
    if (taskbar.edge === "bottom") {
      return point.y >= Number(frame.workArea.y || 0) + Number(frame.workArea.height || 0);
    }
    if (taskbar.edge === "top") {
      return point.y <= Number(frame.workArea.y || 0);
    }
    if (taskbar.edge === "left") {
      return point.x <= Number(frame.workArea.x || 0);
    }
    return point.x >= Number(frame.workArea.x || 0) + Number(frame.workArea.width || 0);
  }

  function buildStandoffPoint(targetPoint, perchPoint, standoffPx, lateralPx, phase, lateralAspect = 0.6) {
    if (!targetPoint) {
      return null;
    }
    const baseX = Number(perchPoint?.x ?? targetPoint.x - standoffPx);
    const baseY = Number(perchPoint?.y ?? targetPoint.y);
    const towardTargetX = targetPoint.x - baseX;
    const towardTargetY = targetPoint.y - baseY;
    const length = Math.max(1, Math.hypot(towardTargetX, towardTargetY));
    const unitX = towardTargetX / length;
    const unitY = towardTargetY / length;
    const perpendicularX = -unitY;
    const perpendicularY = unitX;
    return {
      x: targetPoint.x - unitX * standoffPx + perpendicularX * Math.cos(phase) * lateralPx,
      y: targetPoint.y - unitY * standoffPx + perpendicularY * Math.sin(phase * 0.92) * lateralPx * lateralAspect,
    };
  }

  function buildInvestigatePoint(targetPoint, perchPoint, timestamp, config) {
    if (!targetPoint) {
      return null;
    }
    return buildStandoffPoint(
      targetPoint,
      perchPoint,
      config.investigateStandoffPx,
      config.investigateRadiusPx,
      timestamp / 760,
      0.46,
    );
  }

  function buildLockPoint(targetPoint, perchPoint, timestamp, config) {
    if (!targetPoint) {
      return null;
    }
    return buildStandoffPoint(
      targetPoint,
      perchPoint,
      config.lockStandoffPx,
      Math.max(2, config.lockRadiusPx),
      timestamp / 320,
      0.28,
    );
  }

  function buildBlockedPoint(targetPoint, perchPoint, config) {
    if (!targetPoint) {
      return perchPoint;
    }
    const towardPerchX = Number(perchPoint?.x ?? targetPoint.x) - targetPoint.x;
    const towardPerchY = Number(perchPoint?.y ?? targetPoint.y) - targetPoint.y;
    const length = Math.max(1, Math.hypot(towardPerchX, towardPerchY));
    return {
      x: targetPoint.x + (towardPerchX / length) * config.blockedRecoilPx,
      y: targetPoint.y + (towardPerchY / length) * config.blockedRecoilPx,
    };
  }

  function buildTypeHoldPoint(targetPoint, config) {
    if (!targetPoint) {
      return null;
    }
    return {
      x: targetPoint.x + config.typeHoldOffsetXPx,
      y: targetPoint.y + config.typeHoldOffsetYPx,
    };
  }

  function deriveRequestedBodyState({
    cursorAuthority,
    pausedActive,
    interruptedActive,
    degradedActive,
    handbackActive,
    clickPulseActive,
    blockedActive,
    hoverReady,
    humanActive,
    waitingForUser,
    targetPoint,
    targetConfidence,
    targetStability,
    attentionState,
    attentionStrength,
    lockStrength,
    previousState,
    actionKind,
    executionPhase,
    investigationPressure,
  }) {
    if (pausedActive) {
      return ORB_BODY_STATES.PAUSED;
    }
    if (interruptedActive || handbackActive) {
      return ORB_BODY_STATES.INTERRUPTED;
    }
    if (degradedActive) {
      return ORB_BODY_STATES.DEGRADED;
    }
    if (clickPulseActive) {
      return ORB_BODY_STATES.CLICK_ACT;
    }
    if (blockedActive) {
      return ORB_BODY_STATES.BLOCKED;
    }
    if (waitingForUser) {
      return ORB_BODY_STATES.WAITING_USER;
    }
    if (cursorAuthority) {
      if (
        executionPhase === ORB_BODY_STATES.CLICK_ACT
        || executionPhase === ORB_BODY_STATES.DRAG_ACT
        || executionPhase === ORB_BODY_STATES.TYPE_HOLD
        || executionPhase === ORB_BODY_STATES.HOVER_READY
        || executionPhase === ORB_BODY_STATES.COMMIT_MOVE
        || executionPhase === ORB_BODY_STATES.TARGET_LOCK
      ) {
        return executionPhase;
      }
      if (actionKind.startsWith("keyboard.")) {
        return ORB_BODY_STATES.TYPE_HOLD;
      }
      if (actionKind.startsWith("mouse.drag")) {
        return ORB_BODY_STATES.DRAG_ACT;
      }
      if (hoverReady) {
        return ORB_BODY_STATES.HOVER_READY;
      }
      if (
        targetPoint
        && (
          String(attentionState || "") === "target_lock"
          || (targetStability === "settled" && targetConfidence !== "low" && Number(lockStrength || 0) >= 0.52)
        )
      ) {
        return ORB_BODY_STATES.TARGET_LOCK;
      }
      return ORB_BODY_STATES.COMMIT_MOVE;
    }
    if (
      String(attentionState || "") === "reassess"
      && targetPoint
      && (COMMIT_STATES.has(previousState) || previousState === ORB_BODY_STATES.INVESTIGATE || previousState === ORB_BODY_STATES.TARGET_LOCK)
    ) {
      return ORB_BODY_STATES.BLOCKED;
    }
    if (COMMIT_STATES.has(previousState) && targetPoint && (targetConfidence === "low" || targetStability === "transient")) {
      return ORB_BODY_STATES.BLOCKED;
    }
    if (targetPoint && investigationPressure) {
      if (
        String(attentionState || "") === "target_lock"
        || (targetStability === "settled" && targetConfidence !== "low" && Number(lockStrength || 0) >= 0.5)
      ) {
        return ORB_BODY_STATES.TARGET_LOCK;
      }
      if (String(attentionState || "") === "reassess") {
        return ORB_BODY_STATES.BLOCKED;
      }
      return ORB_BODY_STATES.INVESTIGATE;
    }
    if (String(attentionState || "") === "reassess" && Number(attentionStrength || 0) >= 0.22) {
      return ORB_BODY_STATES.BLOCKED;
    }
    if (humanActive) {
      return ORB_BODY_STATES.ATTENTIVE;
    }
    return ORB_BODY_STATES.IDLE_ANCHORED;
  }

  function deriveBodyState(context = {}) {
    const requestedState = deriveRequestedBodyState(context);
    return resolveOrbTransitionState(context.previousState, requestedState);
  }

  function describeState(state) {
    return ORB_STATE_DESCRIPTORS[normalizeOrbBodyState(state)] || ORB_STATE_DESCRIPTORS[ORB_BODY_STATES.IDLE_ANCHORED];
  }

  function deriveOrbBodyIntent(context = {}) {
    const viewportWidth = Number(context.viewportWidth || 0) || 1;
    const viewportHeight = Number(context.viewportHeight || 0) || 1;
    const frame = resolveFrame(context.input || {}, viewportWidth, viewportHeight);
    const size = Math.max(96, Number(context.size || 144));
    const config = buildMovementConfig(context.orb?.movement || {});
    const targetCue = context.operator?.target_cue || context.orb?.operator?.target_cue || null;
    const policyState = String(context.operator?.policy?.state || "").trim().toLowerCase();
    const policyBlockedActive = policyState === "policy_blocked";
    const targetConfidence = resolveTargetConfidence(targetCue, context.perception || context.orb?.perception || {});
    const targetStability = resolveTargetStability(targetCue, context.perception || context.orb?.perception || {});
    const attentionState = resolveAttentionCueState(targetCue, context.perception || context.orb?.perception || {});
    const attentionStrength = resolveAttentionStrength(targetCue, context.perception || context.orb?.perception || {}, targetConfidence);
    const lockStrength = resolveAttentionLockStrength(targetCue, context.perception || context.orb?.perception || {}, targetStability);
    const actionKind = resolveActionKind({ authority: context.authority, operator: context.operator });
    const executionPhase = resolveExecutionPhase(context.authority);
    const investigationPressure = hasInvestigationPressure({
      forceInvestigate: Boolean(context.forceInvestigate),
      targetCue,
      targetConfidence,
      targetStability,
      attentionState,
      attentionStrength,
      perception: context.perception || context.orb?.perception || {},
    });
    const targetPoint = resolveCommandTargetPoint({
      authority: context.authority,
      operator: context.operator,
      input: context.input || {},
      overlayBounds: frame.overlayBounds,
      perception: context.perception || context.orb?.perception || {},
      targetCue,
      targetConfidence,
      targetStability,
      cursorAuthority: Boolean(context.cursorAuthority),
      forceInvestigate: Boolean(context.forceInvestigate),
      previousState: String(context.previousState || ""),
    });
    const waitingForUser = Boolean(
      context.orb?.interjection?.state === "needed_decision"
      || context.orb?.interjection?.state === "immediate_intervention"
      || context.operator?.controls?.run_mode === "approve_and_run"
      || policyState === "approval_required"
      || (context.orb?.interjection_level ?? 0) >= 2 && !context.cursorAuthority,
    );
    const pausedActive = Boolean(context.pausedActive);
    const interruptedActive = Boolean(context.interruptedActive);
    const degradedActive = Boolean(context.degradedActive);
    const state = deriveBodyState({
      cursorAuthority: Boolean(context.cursorAuthority),
      pausedActive,
      interruptedActive,
      degradedActive,
      handbackActive: Boolean(context.handbackActive),
      clickPulseActive: Boolean(context.clickPulseActive),
      blockedActive: Boolean(context.blockedActive || policyBlockedActive),
      hoverReady: Boolean(context.hoverReady),
      humanActive: Boolean(context.humanActive),
      waitingForUser,
      targetPoint,
      targetConfidence,
      targetStability,
      attentionState,
      attentionStrength,
      lockStrength,
      previousState: String(context.previousState || ""),
      actionKind,
      executionPhase,
      investigationPressure,
    });
    const holdPerch = Boolean(context.holdPerch) && REST_STATES.has(state);
    const previousPoint = normalizePoint(context.currentPosition);
    const windowRect = resolveWindowRect(context.perception || context.orb?.perception || {}, frame.overlayBounds);
    const perchPoint = resolvePerchPoint({
      frame,
      windowRect,
      targetPoint,
      previousPoint,
      latchedPerchPoint: context.latchedPerchPoint,
      preferLatchedPerch: holdPerch,
      size,
      config,
    });
    const taskbarIntent = pointInTaskbar(targetPoint, frame);
    const descriptors = state === ORB_BODY_STATES.BLOCKED && policyBlockedActive
      ? {
          anchorLabel: "policy boundary",
          motionLabel: "policy hold",
          summary: "Holding at a governed boundary until scope or approval changes.",
        }
      : describeState(state);
    let desiredPoint = perchPoint;
    if (state === ORB_BODY_STATES.ATTENTIVE) {
      if (holdPerch) {
        desiredPoint = perchPoint;
      } else if (targetPoint) {
        desiredPoint = {
          x: perchPoint.x + (targetPoint.x - perchPoint.x) * config.attentiveBias,
          y: perchPoint.y + (targetPoint.y - perchPoint.y) * config.attentiveBias,
        };
      } else {
        desiredPoint = {
          x: perchPoint.x + Math.cos(Number(context.timestamp || 0) / 2600) * config.idleAmplitudePx * 0.28,
          y: perchPoint.y + Math.sin(Number(context.timestamp || 0) / 3000) * config.idleAmplitudePx * 0.18,
        };
      }
    } else if (state === ORB_BODY_STATES.INVESTIGATE) {
      desiredPoint = buildInvestigatePoint(targetPoint, perchPoint, Number(context.timestamp || 0), config) || perchPoint;
    } else if (state === ORB_BODY_STATES.TARGET_LOCK) {
      desiredPoint = buildLockPoint(targetPoint, perchPoint, Number(context.timestamp || 0), config) || perchPoint;
    } else if (
      state === ORB_BODY_STATES.COMMIT_MOVE
      || state === ORB_BODY_STATES.HOVER_READY
      || state === ORB_BODY_STATES.CLICK_ACT
      || state === ORB_BODY_STATES.DRAG_ACT
    ) {
      desiredPoint = targetPoint || perchPoint;
    } else if (state === ORB_BODY_STATES.TYPE_HOLD) {
      desiredPoint = buildTypeHoldPoint(targetPoint, config) || perchPoint;
    } else if (state === ORB_BODY_STATES.BLOCKED) {
      desiredPoint = policyBlockedActive ? perchPoint : buildBlockedPoint(targetPoint, perchPoint, config);
    } else if (
      state === ORB_BODY_STATES.INTERRUPTED
      || state === ORB_BODY_STATES.WAITING_USER
      || state === ORB_BODY_STATES.DEGRADED
      || state === ORB_BODY_STATES.PAUSED
    ) {
      desiredPoint = perchPoint;
    } else {
      desiredPoint = holdPerch
        ? perchPoint
        : {
          x: perchPoint.x + Math.cos(Number(context.timestamp || 0) / 1800) * config.idleAmplitudePx,
          y: perchPoint.y + Math.sin(Number(context.timestamp || 0) / 2200) * config.idleAmplitudePx * 0.58,
        };
    }
    desiredPoint = taskbarIntent && COMMIT_STATES.has(state)
      ? clampPointToDesktopBounds(desiredPoint, frame, size, config, { allowTaskbar: true })
      : clampPointToWorkArea(desiredPoint, frame, size, config);
    const stiffness = state === ORB_BODY_STATES.IDLE_ANCHORED
      ? config.idleStiffness
      : state === ORB_BODY_STATES.ATTENTIVE || state === ORB_BODY_STATES.WAITING_USER || (state === ORB_BODY_STATES.BLOCKED && !policyBlockedActive)
        ? config.attentiveStiffness
      : state === ORB_BODY_STATES.BLOCKED && policyBlockedActive
        ? config.hoverStiffness
      : state === ORB_BODY_STATES.INVESTIGATE
        ? config.investigateStiffness
      : state === ORB_BODY_STATES.TARGET_LOCK
        ? config.lockStiffness
      : state === ORB_BODY_STATES.HOVER_READY
        ? config.hoverStiffness
      : state === ORB_BODY_STATES.DRAG_ACT
        ? config.dragStiffness
        : state === ORB_BODY_STATES.INTERRUPTED
          ? config.abortStiffness
          : state === ORB_BODY_STATES.DEGRADED || state === ORB_BODY_STATES.PAUSED
            ? config.idleStiffness
                  : config.commitStiffness;
    const damping = state === ORB_BODY_STATES.HOVER_READY || state === ORB_BODY_STATES.TYPE_HOLD
      ? config.dampingHover
      : state === ORB_BODY_STATES.BLOCKED && policyBlockedActive
        ? config.dampingHover
      : COMMIT_STATES.has(state)
        ? config.dampingCommit
        : config.dampingIdle;
    const scale = state === ORB_BODY_STATES.CLICK_ACT
      ? config.clickPulseScale
      : state === ORB_BODY_STATES.DRAG_ACT
        ? config.dragScale
        : state === ORB_BODY_STATES.TARGET_LOCK
          ? config.lockScale
          : state === ORB_BODY_STATES.HOVER_READY || state === ORB_BODY_STATES.TYPE_HOLD
            ? config.hoverScale
            : state === ORB_BODY_STATES.BLOCKED
              ? policyBlockedActive ? config.waitingScale : config.blockedScale
              : state === ORB_BODY_STATES.WAITING_USER
                ? config.waitingScale
                : state === ORB_BODY_STATES.INTERRUPTED
                  ? config.interruptedScale
                  : state === ORB_BODY_STATES.DEGRADED
                    ? config.degradedScale
                    : state === ORB_BODY_STATES.PAUSED
                      ? config.pausedScale
                : 1;
    return {
      state,
      actionKind,
      targetPoint,
      perchPoint,
      desiredPoint,
      taskbarIntent,
      targetConfidence,
      targetStability,
      attentionState,
      attentionStrength,
      lockStrength,
      executionPhase,
      waitingForUser,
      windowRect,
      frame,
      config,
      stiffness,
      damping,
      scale,
      holdPerch,
      policyBlockedActive,
      summary: descriptors.summary,
      anchorLabel: descriptors.anchorLabel,
      motionLabel: descriptors.motionLabel,
    };
  }

  return {
    ORB_BODY_STATES,
    COMMIT_STATES,
    normalizeOrbBodyState,
    isOrbTransitionAllowed,
    resolveOrbTransitionState,
    resolveTaskbarEdge,
    deriveOrbBodyIntent,
  };
});
