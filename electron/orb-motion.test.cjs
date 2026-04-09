const test = require("node:test");
const assert = require("node:assert/strict");

const {
  ORB_BODY_STATES,
  deriveOrbBodyIntent,
  isOrbTransitionAllowed,
  normalizeOrbBodyState,
  resolveTaskbarEdge,
  resolveOrbTransitionState,
} = require("../services/hud/app/static/orb/orb-motion.js");

function buildBaseContext(overrides = {}) {
  return {
    timestamp: 1000,
    size: 144,
    viewportWidth: 1920,
    viewportHeight: 1080,
    currentPosition: { x: 1400, y: 860 },
    orb: {
      movement: {},
      interjection_level: 0,
      operator: {},
      authority: {},
      perception: {},
      interjection: {},
    },
    operator: {
      controls: {},
      target_cue: null,
    },
    authority: {
      claimed: [],
      recent: [],
    },
    perception: {
      window: {
        bounds: { x: 320, y: 180, width: 1040, height: 720 },
      },
      target: {
        confidence: "low",
        stability: { state: "idle" },
      },
    },
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
      cursorDisplay: { x: 1360, y: 640 },
    },
    previousState: ORB_BODY_STATES.IDLE_ANCHORED,
    cursorAuthority: false,
    handbackActive: false,
    humanActive: false,
    hoverReady: false,
    clickPulseActive: false,
    blockedActive: false,
    ...overrides,
  };
}

test("taskbar edge detection respects work-area insets", () => {
  const edge = resolveTaskbarEdge(
    { x: 0, y: 0, width: 1920, height: 1080 },
    { x: 0, y: 0, width: 1920, height: 1040 },
  );
  assert.equal(edge.edge, "bottom");
  assert.equal(edge.thickness, 40);
});

test("idle anchored resolves to a deliberate perch near the active work area edge", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext());
  assert.equal(intent.state, ORB_BODY_STATES.IDLE_ANCHORED);
  assert.ok(intent.perchPoint.x > 1460, `expected wider right-side perch, got ${intent.perchPoint.x}`);
  assert.ok(intent.perchPoint.y > 780, `expected lower perch, got ${intent.perchPoint.y}`);
  assert.equal(intent.taskbarIntent, false);
  assert.ok(Math.abs(intent.desiredPoint.x - intent.perchPoint.x) <= 3, `expected restrained idle x drift, got ${intent.desiredPoint.x - intent.perchPoint.x}`);
  assert.ok(Math.abs(intent.desiredPoint.y - intent.perchPoint.y) <= 2, `expected restrained idle y drift, got ${intent.desiredPoint.y - intent.perchPoint.y}`);
});

test("grounded target pressure is required before non-authority investigation begins", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    operator: {
      controls: {},
      target_cue: null,
    },
    perception: {
      window: {
        bounds: { x: 320, y: 180, width: 1040, height: 720 },
      },
      target: {
        confidence: "medium",
        stability: { state: "tracking" },
      },
      cursor: { x: 1260, y: 540 },
    },
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
      cursorDisplay: { x: 1260, y: 540 },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.IDLE_ANCHORED);
});

test("explicit investigate intent can still scout deliberately without authority", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    forceInvestigate: true,
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
      cursorDisplay: { x: 1260, y: 540 },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.INVESTIGATE);
  assert.notDeepEqual(intent.desiredPoint, intent.perchPoint);
  assert.ok(intent.perchPoint.x < intent.windowRect.x, `expected investigate perch to stay off the target side, got ${intent.perchPoint.x}`);
  assert.ok(
    Math.hypot(intent.desiredPoint.x - intent.targetPoint.x, intent.desiredPoint.y - intent.targetPoint.y) >= intent.config.investigateStandoffPx * 0.78,
    `expected investigate standoff, got ${Math.hypot(intent.desiredPoint.x - intent.targetPoint.x, intent.desiredPoint.y - intent.targetPoint.y)}`,
  );
});

test("attention cue lock semantics can tighten posture before full command authority arrives", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    operator: {
      controls: {},
      target_cue: {
        attention_state: "target_lock",
        attention_strength: 0.82,
        lock_strength: 0.78,
        confidence: "medium",
        stability: "tracking",
        summary: "Concrete target line is converging.",
      },
    },
    perception: {
      window: {
        bounds: { x: 320, y: 180, width: 1040, height: 720 },
      },
      target: {
        confidence: "medium",
        stability: { state: "tracking" },
        attention: { state: "target_lock", strength: 0.82, lock_strength: 0.78 },
      },
      cursor: { x: 1240, y: 548 },
    },
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
      cursorDisplay: { x: 1240, y: 548 },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.TARGET_LOCK);
  assert.equal(intent.attentionState, "target_lock");
  const lockDistance = Math.hypot(intent.desiredPoint.x - intent.targetPoint.x, intent.desiredPoint.y - intent.targetPoint.y);
  assert.ok(lockDistance >= intent.config.lockStandoffPx * 0.72, `expected lock standoff, got ${lockDistance}`);
  assert.ok(lockDistance < intent.config.investigateStandoffPx * 0.72, `expected lock to be tighter than investigate, got ${lockDistance}`);
});

test("approval-ready posture returns to a respectful waiting anchor", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    humanActive: true,
    operator: {
      controls: {
        run_mode: "approve_and_run",
      },
      target_cue: {
        confidence: "likely",
        stability: "settled",
      },
    },
    orb: {
      movement: {},
      interjection_level: 2,
      interjection: { state: "needed_decision" },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.WAITING_USER);
  assert.deepEqual(intent.desiredPoint, intent.perchPoint);
});

test("claimed authority click resolves to a direct commit target in display coordinates", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    cursorAuthority: true,
    authority: {
      claimed: [
        {
          kind: "mouse.click",
          args: { x: 120, y: 1062, coordinate_space: "display" },
        },
      ],
      recent: [],
    },
    operator: {
      controls: {
        desktop_run_kind: "mouse.click",
      },
    },
    perception: {
      window: {
        bounds: { x: 0, y: 0, width: 1920, height: 1080 },
      },
      target: {
        confidence: "medium",
        stability: { state: "tracking" },
      },
    },
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
      cursorDisplay: { x: 400, y: 400 },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.COMMIT_MOVE);
  assert.deepEqual(intent.targetPoint, { x: 120, y: 1062 });
  assert.equal(intent.taskbarIntent, true);
  assert.ok(intent.desiredPoint.y >= 1040, `expected taskbar-aligned body point, got ${intent.desiredPoint.y}`);
});

test("hover ready and typing states stay precise once authority is live", () => {
  const hoverIntent = deriveOrbBodyIntent(buildBaseContext({
    cursorAuthority: true,
    hoverReady: true,
    authority: {
      claimed: [
        {
          kind: "mouse.move",
          args: { x: 1440, y: 640, coordinate_space: "screen" },
        },
      ],
      recent: [],
    },
    operator: {
      controls: {
        desktop_run_kind: "mouse.move",
      },
      target_cue: {
        confidence: "high",
        stability: "settled",
      },
    },
    perception: {
      window: {
        bounds: { x: 960, y: 160, width: 760, height: 720 },
      },
      target: {
        confidence: "high",
        stability: { state: "settled" },
      },
    },
  }));
  assert.equal(hoverIntent.state, ORB_BODY_STATES.HOVER_READY);
  assert.deepEqual(hoverIntent.desiredPoint, hoverIntent.targetPoint);

  const typeIntent = deriveOrbBodyIntent(buildBaseContext({
    cursorAuthority: true,
    authority: {
      claimed: [
        {
          kind: "keyboard.type",
          args: { text: "hello" },
        },
      ],
      recent: [],
    },
    operator: {
      controls: {
        desktop_run_kind: "keyboard.type",
      },
      target_cue: {
        confidence: "high",
        stability: "settled",
      },
    },
    perception: {
      window: {
        bounds: { x: 920, y: 180, width: 820, height: 700 },
      },
      target: {
        confidence: "high",
        stability: { state: "settled" },
      },
      cursor: { x: 1180, y: 610 },
    },
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
      cursorDisplay: { x: 1180, y: 610 },
    },
  }));
  assert.equal(typeIntent.state, ORB_BODY_STATES.TYPE_HOLD);
  assert.equal(typeIntent.desiredPoint.x, typeIntent.targetPoint.x + typeIntent.config.typeHoldOffsetXPx);
  assert.equal(typeIntent.desiredPoint.y, typeIntent.targetPoint.y + typeIntent.config.typeHoldOffsetYPx);
});

test("canonical authority execution phases drive visible execution posture directly", () => {
  const clickIntent = deriveOrbBodyIntent(buildBaseContext({
    previousState: ORB_BODY_STATES.HOVER_READY,
    cursorAuthority: true,
    authority: {
      activeCommandKind: "mouse.click",
      executionPhase: "click_act",
      executionTarget: { x: 1420, y: 662, coordinate_space: "screen" },
      claimed: [],
      recent: [],
    },
  }));
  assert.equal(clickIntent.state, ORB_BODY_STATES.CLICK_ACT);
  assert.deepEqual(clickIntent.targetPoint, { x: 1420, y: 662 });

  const dragIntent = deriveOrbBodyIntent(buildBaseContext({
    previousState: ORB_BODY_STATES.COMMIT_MOVE,
    cursorAuthority: true,
    authority: {
      activeCommandKind: "mouse.drag",
      executionPhase: "drag_act",
      executionTarget: { x: 1360, y: 700, coordinate_space: "screen" },
      claimed: [],
      recent: [],
    },
  }));
  assert.equal(dragIntent.state, ORB_BODY_STATES.DRAG_ACT);
  assert.deepEqual(dragIntent.targetPoint, { x: 1360, y: 700 });

  const typeIntent = deriveOrbBodyIntent(buildBaseContext({
    previousState: ORB_BODY_STATES.COMMIT_MOVE,
    cursorAuthority: true,
    authority: {
      activeCommandKind: "keyboard.type",
      executionPhase: "type_hold",
      executionTarget: { x: 1180, y: 610, coordinate_space: "screen" },
      claimed: [],
      recent: [],
    },
  }));
  assert.equal(typeIntent.state, ORB_BODY_STATES.TYPE_HOLD);
});

test("lost confidence during a commit path produces blocked posture", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    previousState: ORB_BODY_STATES.COMMIT_MOVE,
    cursorAuthority: false,
    operator: {
      target_cue: {
        confidence: "low",
        stability: "transient",
      },
    },
    perception: {
      window: {
        bounds: { x: 240, y: 160, width: 960, height: 720 },
      },
      target: {
        confidence: "low",
        stability: { state: "transient" },
      },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.BLOCKED);
});

test("reassess attention semantics hold the orb in a visible blocked posture", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    previousState: ORB_BODY_STATES.TARGET_LOCK,
    operator: {
      target_cue: {
        attention_state: "reassess",
        attention_strength: 0.36,
        lock_strength: 0.18,
        confidence: "medium",
        stability: "tracking",
      },
    },
    perception: {
      window: {
        bounds: { x: 240, y: 160, width: 960, height: 720 },
      },
      target: {
        confidence: "medium",
        stability: { state: "tracking" },
        attention: { state: "reassess", strength: 0.36, uncertainty: 0.74 },
      },
      cursor: { x: 1060, y: 540 },
    },
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
      cursorDisplay: { x: 1060, y: 540 },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.BLOCKED);
  assert.equal(intent.attentionState, "reassess");
});

test("policy blocked posture holds at the boundary instead of recoiling like uncertainty", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    previousState: ORB_BODY_STATES.TARGET_LOCK,
    operator: {
      controls: {},
      policy: {
        state: "policy_blocked",
      },
      target_cue: {
        attention_state: "target_lock",
        attention_strength: 0.74,
        lock_strength: 0.68,
        confidence: "high",
        stability: "settled",
      },
    },
    perception: {
      window: {
        bounds: { x: 240, y: 160, width: 960, height: 720 },
      },
      target: {
        confidence: "high",
        stability: { state: "settled" },
        attention: { state: "target_lock", strength: 0.74, lock_strength: 0.68 },
      },
      cursor: { x: 1060, y: 540 },
    },
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
      cursorDisplay: { x: 1060, y: 540 },
    },
  }));

  assert.equal(intent.state, ORB_BODY_STATES.BLOCKED);
  assert.equal(intent.policyBlockedActive, true);
  assert.deepEqual(intent.desiredPoint, intent.perchPoint);
  assert.equal(intent.motionLabel, "policy hold");
});

test("canonical body-state aliases normalize to the Section 4 vocabulary", () => {
  assert.equal(normalizeOrbBodyState("waiting_for_user"), ORB_BODY_STATES.WAITING_USER);
  assert.equal(normalizeOrbBodyState("blocked_uncertain"), ORB_BODY_STATES.BLOCKED);
  assert.equal(normalizeOrbBodyState("abort_interrupted"), ORB_BODY_STATES.INTERRUPTED);
});

test("transition resolver steps through abrupt jumps but preserves grounded direct locks", () => {
  assert.equal(
    isOrbTransitionAllowed(ORB_BODY_STATES.IDLE_ANCHORED, ORB_BODY_STATES.CLICK_ACT),
    false,
  );
  assert.equal(
    resolveOrbTransitionState(ORB_BODY_STATES.IDLE_ANCHORED, ORB_BODY_STATES.CLICK_ACT),
    ORB_BODY_STATES.COMMIT_MOVE,
  );
  assert.equal(
    resolveOrbTransitionState(ORB_BODY_STATES.ATTENTIVE, ORB_BODY_STATES.TARGET_LOCK),
    ORB_BODY_STATES.TARGET_LOCK,
  );
});

test("paused and degraded posture override action intent without inventing motion", () => {
  const interruptedIntent = deriveOrbBodyIntent(buildBaseContext({
    cursorAuthority: true,
    interruptedActive: true,
    authority: {
      claimed: [{ kind: "mouse.click", args: { x: 1440, y: 640, coordinate_space: "screen" } }],
      recent: [],
    },
  }));
  assert.equal(interruptedIntent.state, ORB_BODY_STATES.INTERRUPTED);
  assert.deepEqual(interruptedIntent.desiredPoint, interruptedIntent.perchPoint);
  assert.ok(
    interruptedIntent.perchPoint.x > interruptedIntent.windowRect.x + interruptedIntent.windowRect.width
      || interruptedIntent.perchPoint.x < interruptedIntent.windowRect.x,
    `expected interrupted retreat to leave the active window zone, got ${JSON.stringify(interruptedIntent.perchPoint)}`,
  );

  const pausedIntent = deriveOrbBodyIntent(buildBaseContext({
    cursorAuthority: true,
    pausedActive: true,
    authority: {
      claimed: [{ kind: "mouse.click", args: { x: 1440, y: 640, coordinate_space: "screen" } }],
      recent: [],
    },
  }));
  assert.equal(pausedIntent.state, ORB_BODY_STATES.PAUSED);
  assert.deepEqual(pausedIntent.desiredPoint, pausedIntent.perchPoint);

  const degradedIntent = deriveOrbBodyIntent(buildBaseContext({
    cursorAuthority: true,
    degradedActive: true,
    authority: {
      claimed: [{ kind: "mouse.click", args: { x: 1440, y: 640, coordinate_space: "screen" } }],
      recent: [],
    },
  }));
  assert.equal(degradedIntent.state, ORB_BODY_STATES.DEGRADED);
  assert.deepEqual(degradedIntent.desiredPoint, degradedIntent.perchPoint);
});

test("completed commit does not synthesize a fresh target or investigate again", () => {
  const intent = deriveOrbBodyIntent(buildBaseContext({
    previousState: ORB_BODY_STATES.CLICK_ACT,
    operator: {
      controls: {
        desktop_run_kind: "mouse.click",
      },
      target_cue: null,
    },
    authority: {
      claimed: [],
      recent: [
        {
          kind: "mouse.click",
          status: "completed",
        },
      ],
    },
    perception: {
      window: {
        bounds: { x: 320, y: 180, width: 1040, height: 720 },
      },
      target: {
        confidence: "low",
        stability: { state: "idle" },
      },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.IDLE_ANCHORED);
  assert.equal(intent.targetPoint, null);
});

test("rest states hold a latched perch immediately after commit settle", () => {
  const latchedPerchPoint = { x: 1184, y: 804 };
  const intent = deriveOrbBodyIntent(buildBaseContext({
    previousState: ORB_BODY_STATES.CLICK_ACT,
    holdPerch: true,
    latchedPerchPoint,
    currentPosition: { ...latchedPerchPoint },
    input: {
      overlayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1040 },
    },
    perception: {
      window: {
        bounds: { x: 320, y: 180, width: 1040, height: 720 },
      },
      target: {
        confidence: "low",
        stability: { state: "idle" },
      },
    },
  }));
  assert.equal(intent.state, ORB_BODY_STATES.IDLE_ANCHORED);
  assert.equal(intent.holdPerch, true);
  assert.deepEqual(intent.perchPoint, latchedPerchPoint);
  assert.deepEqual(intent.desiredPoint, latchedPerchPoint);
});
