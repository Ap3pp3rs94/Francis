const DEFAULT_PLAN_STEP_DELAY_MS = 0;
const MAX_PLAN_STEP_DELAY_MS = 4000;
const ALLOWED_STEP_KINDS = new Set([
  "mouse.move",
  "mouse.click",
  "keyboard.type",
  "keyboard.key",
  "keyboard.shortcut",
]);

function clampNumber(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function sleep(delayMs) {
  return new Promise((resolve) => {
    setTimeout(resolve, Math.max(0, Number(delayMs || 0)));
  });
}

function normalizeCoordinateSpace(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "display") {
    return "display";
  }
  return "screen";
}

function normalizePoint(value, fallback = null) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.round(numeric);
}

function normalizeOrbPlanStep(row, index = 0) {
  if (!row || typeof row !== "object" || Array.isArray(row)) {
    throw new TypeError(`Orb plan step ${index + 1} must be an object.`);
  }
  const kind = String(row.kind || "").trim().toLowerCase();
  if (!ALLOWED_STEP_KINDS.has(kind)) {
    throw new Error(`Orb plan step ${index + 1} uses unsupported kind: ${kind || "unknown"}.`);
  }
  const args = row.args && typeof row.args === "object" && !Array.isArray(row.args) ? { ...row.args } : {};
  const reason = String(row.reason || "").trim() || `Carry out Orb plan step ${index + 1}.`;
  const interaction = String(row.interaction || "").trim().toLowerCase();
  const delayMs = clampNumber(
    Number(row.delay_ms ?? row.wait_ms ?? row.pause_ms ?? DEFAULT_PLAN_STEP_DELAY_MS) || 0,
    0,
    MAX_PLAN_STEP_DELAY_MS,
  );
  const normalized = {
    kind,
    args,
    reason,
    interaction,
    delay_ms: delayMs,
  };

  if (kind === "mouse.move") {
    const x = normalizePoint(args.x);
    const y = normalizePoint(args.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      throw new Error(`Orb plan step ${index + 1} requires numeric x and y coordinates.`);
    }
    normalized.args = {
      x,
      y,
      coordinate_space: normalizeCoordinateSpace(args.coordinate_space || args.coordinateSpace),
    };
    return normalized;
  }

  if (kind === "mouse.click") {
    const x = normalizePoint(args.x);
    const y = normalizePoint(args.y);
    const normalizedArgs = {
      button: String(args.button || "left").trim().toLowerCase() === "right" ? "right" : "left",
      double: Boolean(args.double),
    };
    if (Number.isFinite(x) && Number.isFinite(y)) {
      normalizedArgs.x = x;
      normalizedArgs.y = y;
      normalizedArgs.coordinate_space = normalizeCoordinateSpace(args.coordinate_space || args.coordinateSpace);
    }
    normalized.args = normalizedArgs;
    return normalized;
  }

  if (kind === "keyboard.type") {
    const text = String(args.text || "");
    if (!text.trim()) {
      throw new Error(`Orb plan step ${index + 1} requires text for keyboard.type.`);
    }
    normalized.args = { text };
    return normalized;
  }

  if (kind === "keyboard.key") {
    const key = String(args.key || "").trim().toLowerCase();
    if (!key) {
      throw new Error(`Orb plan step ${index + 1} requires a key for keyboard.key.`);
    }
    normalized.args = { key };
    return normalized;
  }

  const keys = Array.isArray(args.keys)
    ? args.keys
    : typeof args.keys === "string" && args.keys.trim()
      ? [args.keys]
      : [];
  const normalizedKeys = keys.map((value) => String(value || "").trim().toLowerCase()).filter(Boolean);
  if (!normalizedKeys.length) {
    throw new Error(`Orb plan step ${index + 1} requires keys for keyboard.shortcut.`);
  }
  normalized.args = { keys: normalizedKeys };
  return normalized;
}

function normalizeOrbDesktopPlan(plan) {
  if (!plan || typeof plan !== "object" || Array.isArray(plan)) {
    throw new TypeError("Orb desktop plan must be an object.");
  }
  const stepsSource = Array.isArray(plan.steps) ? plan.steps : [];
  if (!stepsSource.length) {
    throw new Error("Orb desktop plan requires at least one step.");
  }
  return {
    title: String(plan.title || "").trim() || "Orb desktop plan",
    summary: String(plan.summary || "").trim() || "Carry out the requested desktop action through the Orb shell.",
    mode_requirement: String(plan.mode_requirement || "pilot").trim().toLowerCase() || "pilot",
    reasoning: Array.isArray(plan.reasoning)
      ? plan.reasoning.map((value) => String(value || "").trim()).filter(Boolean).slice(0, 8)
      : [],
    auto_execute: Boolean(plan.auto_execute),
    steps: stepsSource.map((row, index) => normalizeOrbPlanStep(row, index)),
  };
}

function resolveScreenPoint(args, inputState = {}) {
  const cursorScreen = inputState.cursorScreen && typeof inputState.cursorScreen === "object" ? inputState.cursorScreen : null;
  const workArea = inputState.workArea && typeof inputState.workArea === "object" ? inputState.workArea : { x: 0, y: 0 };
  const coordinateSpace = normalizeCoordinateSpace(args.coordinate_space || args.coordinateSpace);
  const pointX = normalizePoint(args.x, normalizePoint(cursorScreen?.x, 0));
  const pointY = normalizePoint(args.y, normalizePoint(cursorScreen?.y, 0));
  if (coordinateSpace === "display") {
    return {
      x: Number(workArea.x || 0) + Number(pointX || 0),
      y: Number(workArea.y || 0) + Number(pointY || 0),
    };
  }
  return {
    x: Number(pointX || 0),
    y: Number(pointY || 0),
  };
}

async function executeOrbDesktopPlan(plan, options = {}) {
  const normalizedPlan = normalizeOrbDesktopPlan(plan);
  const executeCommand = typeof options.executeCommand === "function" ? options.executeCommand : null;
  if (!executeCommand) {
    throw new TypeError("executeCommand must be provided to execute an Orb desktop plan.");
  }
  const delay = typeof options.sleep === "function" ? options.sleep : sleep;
  const inputState = options.inputState && typeof options.inputState === "object" ? options.inputState : {};
  const stepResults = [];
  const startedAt = new Date().toISOString();

  try {
    for (let index = 0; index < normalizedPlan.steps.length; index += 1) {
      const step = normalizedPlan.steps[index];
      const stepStartedAt = new Date().toISOString();
      if (typeof options.onStepStart === "function") {
        await options.onStepStart(step, index);
      }
      if (step.kind === "mouse.move") {
        const targetPoint = resolveScreenPoint(step.args, inputState);
        await executeCommand({
          kind: "mouse.move",
          args: targetPoint,
        });
        if (typeof options.onSyntheticCursor === "function") {
          options.onSyntheticCursor(targetPoint);
        }
        stepResults.push({
          index,
          kind: step.kind,
          status: "ok",
          started_at: stepStartedAt,
          finished_at: new Date().toISOString(),
          reason: step.reason,
          interaction: step.interaction,
          args: {
            ...step.args,
            x: targetPoint.x,
            y: targetPoint.y,
            coordinate_space: "screen",
          },
        });
      } else if (step.kind === "mouse.click") {
        let targetPoint = null;
        if (Number.isFinite(Number(step.args.x)) && Number.isFinite(Number(step.args.y))) {
          targetPoint = resolveScreenPoint(step.args, inputState);
          await executeCommand({
            kind: "mouse.move",
            args: targetPoint,
          });
          if (typeof options.onSyntheticCursor === "function") {
            options.onSyntheticCursor(targetPoint);
          }
        }
        await executeCommand({
          kind: "mouse.click",
          args: {
            button: step.args.button,
            double: Boolean(step.args.double),
          },
        });
        if (typeof options.onSyntheticInput === "function") {
          options.onSyntheticInput(step.kind);
        }
        stepResults.push({
          index,
          kind: step.kind,
          status: "ok",
          started_at: stepStartedAt,
          finished_at: new Date().toISOString(),
          reason: step.reason,
          interaction: step.interaction,
          args: targetPoint
            ? {
                ...step.args,
                x: targetPoint.x,
                y: targetPoint.y,
                coordinate_space: "screen",
              }
            : { ...step.args },
        });
      } else {
        await executeCommand({
          kind: step.kind,
          args: step.args,
        });
        if (typeof options.onSyntheticInput === "function") {
          options.onSyntheticInput(step.kind);
        }
        stepResults.push({
          index,
          kind: step.kind,
          status: "ok",
          started_at: stepStartedAt,
          finished_at: new Date().toISOString(),
          reason: step.reason,
          interaction: step.interaction,
          args: { ...step.args },
        });
      }
      if (step.delay_ms > 0) {
        await delay(step.delay_ms);
      }
      if (typeof options.onStepComplete === "function") {
        await options.onStepComplete(step, index, stepResults[stepResults.length - 1]);
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      status: "failed",
      title: normalizedPlan.title,
      summary: `${normalizedPlan.title} failed through the Orb shell.`,
      error: message,
      mode_requirement: normalizedPlan.mode_requirement,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      step_count: normalizedPlan.steps.length,
      completed_steps: stepResults.length,
      steps: stepResults,
    };
  }

  return {
    status: "ok",
    title: normalizedPlan.title,
    summary: `${normalizedPlan.title} completed through the Orb shell.`,
    mode_requirement: normalizedPlan.mode_requirement,
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    step_count: normalizedPlan.steps.length,
    completed_steps: stepResults.length,
    steps: stepResults,
  };
}

module.exports = {
  ALLOWED_STEP_KINDS,
  DEFAULT_PLAN_STEP_DELAY_MS,
  executeOrbDesktopPlan,
  normalizeOrbDesktopPlan,
  normalizeOrbPlanStep,
  resolveScreenPoint,
};
