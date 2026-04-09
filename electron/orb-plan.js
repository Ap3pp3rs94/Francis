const {
  buildOrbExecutionSemantics,
} = require("./orb-execution");

const DEFAULT_PLAN_STEP_DELAY_MS = 0;
const MAX_PLAN_STEP_DELAY_MS = 4000;
const MAX_DRAG_DURATION_MS = 1800;
const MAX_DRAG_STEPS = 48;
const ALLOWED_STEP_KINDS = new Set([
  "mouse.move",
  "mouse.click",
  "mouse.drag",
  "keyboard.type",
  "keyboard.key",
  "keyboard.shortcut",
]);
const ALLOWED_DESKTOP_ANCHORS = new Set([
  "start_button",
  "show_desktop_button",
  "current_cursor",
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

function normalizeDesktopAnchor(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "";
  }
  if (normalized === "cursor") {
    return "current_cursor";
  }
  if (normalized === "start" || normalized === "start_menu" || normalized === "start-menu") {
    return "start_button";
  }
  if (normalized === "show_desktop" || normalized === "desktop_button" || normalized === "show-desktop") {
    return "show_desktop_button";
  }
  return ALLOWED_DESKTOP_ANCHORS.has(normalized) ? normalized : "";
}

function normalizeOptionalPoint(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
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
    const anchor = normalizeDesktopAnchor(args.anchor || args.target || args.named_target);
    const x = normalizePoint(args.x);
    const y = normalizePoint(args.y);
    if (!anchor && (!Number.isFinite(x) || !Number.isFinite(y))) {
      throw new Error(`Orb plan step ${index + 1} requires numeric x/y coordinates or a named desktop anchor.`);
    }
    normalized.args = {
      coordinate_space: normalizeCoordinateSpace(args.coordinate_space || args.coordinateSpace),
    };
    if (anchor) {
      normalized.args.anchor = anchor;
    } else {
      normalized.args.x = x;
      normalized.args.y = y;
    }
    return normalized;
  }

  if (kind === "mouse.click") {
    const anchor = normalizeDesktopAnchor(args.anchor || args.target || args.named_target);
    const x = normalizePoint(args.x);
    const y = normalizePoint(args.y);
    const normalizedArgs = {
      button: String(args.button || "left").trim().toLowerCase() === "right" ? "right" : "left",
      double: Boolean(args.double),
    };
    if (anchor) {
      normalizedArgs.anchor = anchor;
    } else if (Number.isFinite(x) && Number.isFinite(y)) {
      normalizedArgs.x = x;
      normalizedArgs.y = y;
      normalizedArgs.coordinate_space = normalizeCoordinateSpace(args.coordinate_space || args.coordinateSpace);
    }
    normalized.args = normalizedArgs;
    return normalized;
  }

  if (kind === "mouse.drag") {
    const anchor = normalizeDesktopAnchor(args.anchor || args.target || args.named_target);
    const x = normalizePoint(args.x);
    const y = normalizePoint(args.y);
    const startAnchor = normalizeDesktopAnchor(args.start_anchor || args.start_target || args.start_named_target);
    const startX = normalizeOptionalPoint(args.start_x);
    const startY = normalizeOptionalPoint(args.start_y);
    if (!anchor && (!Number.isFinite(x) || !Number.isFinite(y))) {
      throw new Error(`Orb plan step ${index + 1} requires numeric x/y coordinates or a named desktop anchor for mouse.drag.`);
    }
    const normalizedArgs = {
      button: String(args.button || "left").trim().toLowerCase() === "right" ? "right" : "left",
      duration_ms: clampNumber(Number(args.duration_ms ?? args.durationMs ?? 220) || 220, 60, MAX_DRAG_DURATION_MS),
      steps: clampNumber(Number(args.steps ?? 12) || 12, 4, MAX_DRAG_STEPS),
      coordinate_space: normalizeCoordinateSpace(args.coordinate_space || args.coordinateSpace),
    };
    if (anchor) {
      normalizedArgs.anchor = anchor;
    } else {
      normalizedArgs.x = x;
      normalizedArgs.y = y;
    }
    if (startAnchor) {
      normalizedArgs.start_anchor = startAnchor;
    } else if (Number.isFinite(startX) && Number.isFinite(startY)) {
      normalizedArgs.start_x = startX;
      normalizedArgs.start_y = startY;
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

function inferTaskbarPlacement(bounds, workArea) {
  const safeBounds = bounds && typeof bounds === "object" ? bounds : { x: 0, y: 0, width: 0, height: 0 };
  const safeWorkArea = workArea && typeof workArea === "object" ? workArea : safeBounds;
  const leftInset = Number(safeWorkArea.x || 0) - Number(safeBounds.x || 0);
  const topInset = Number(safeWorkArea.y || 0) - Number(safeBounds.y || 0);
  const rightInset = (Number(safeBounds.x || 0) + Number(safeBounds.width || 0))
    - (Number(safeWorkArea.x || 0) + Number(safeWorkArea.width || 0));
  const bottomInset = (Number(safeBounds.y || 0) + Number(safeBounds.height || 0))
    - (Number(safeWorkArea.y || 0) + Number(safeWorkArea.height || 0));

  if (leftInset > 0 && leftInset >= rightInset) {
    return { edge: "left", thickness: leftInset };
  }
  if (rightInset > 0) {
    return { edge: "right", thickness: rightInset };
  }
  if (topInset > 0 && topInset >= bottomInset) {
    return { edge: "top", thickness: topInset };
  }
  if (bottomInset > 0) {
    return { edge: "bottom", thickness: bottomInset };
  }
  return { edge: "bottom", thickness: Math.max(48, Math.round((Number(safeBounds.height || 0) || 1080) * 0.045)) };
}

function resolveDesktopAnchor(anchor, inputState = {}) {
  const normalized = normalizeDesktopAnchor(anchor);
  const cursorScreen = inputState.cursorScreen && typeof inputState.cursorScreen === "object" ? inputState.cursorScreen : null;
  if (normalized === "current_cursor") {
    return {
      x: normalizePoint(cursorScreen?.x, 0),
      y: normalizePoint(cursorScreen?.y, 0),
    };
  }
  const displayBounds = inputState.displayBounds && typeof inputState.displayBounds === "object"
    ? inputState.displayBounds
    : inputState.workArea && typeof inputState.workArea === "object"
      ? inputState.workArea
      : { x: 0, y: 0, width: 1920, height: 1080 };
  const displayWorkArea = inputState.displayWorkArea && typeof inputState.displayWorkArea === "object"
    ? inputState.displayWorkArea
    : displayBounds;

  if (normalized === "start_button") {
    const placement = inferTaskbarPlacement(displayBounds, displayWorkArea);
    const boundsX = Number(displayBounds.x || 0);
    const boundsY = Number(displayBounds.y || 0);
    const boundsWidth = Number(displayBounds.width || 0);
    const boundsHeight = Number(displayBounds.height || 0);
    const thickness = Math.max(36, Number(placement.thickness || 48));
    if (placement.edge === "left") {
      return {
        x: Math.round(boundsX + thickness * 0.5),
        y: Math.round(boundsY + Math.min(56, Math.max(36, thickness * 1.15))),
      };
    }
    if (placement.edge === "right") {
      return {
        x: Math.round(boundsX + boundsWidth - thickness * 0.5),
        y: Math.round(boundsY + Math.min(56, Math.max(36, thickness * 1.15))),
      };
    }
    if (placement.edge === "top") {
      return {
        x: Math.round(boundsX + Math.min(64, Math.max(38, thickness * 1.2))),
        y: Math.round(boundsY + thickness * 0.5),
      };
    }
    return {
      x: Math.round(boundsX + Math.min(64, Math.max(38, thickness * 1.2))),
      y: Math.round(boundsY + boundsHeight - thickness * 0.5),
    };
  }
  if (normalized === "show_desktop_button") {
    const placement = inferTaskbarPlacement(displayBounds, displayWorkArea);
    const boundsX = Number(displayBounds.x || 0);
    const boundsY = Number(displayBounds.y || 0);
    const boundsWidth = Number(displayBounds.width || 0);
    const boundsHeight = Number(displayBounds.height || 0);
    const thickness = Math.max(24, Number(placement.thickness || 48));
    const sliver = Math.max(8, Math.min(18, Math.round(thickness * 0.3)));
    if (placement.edge === "left") {
      return {
        x: Math.round(boundsX + sliver * 0.5),
        y: Math.round(boundsY + boundsHeight - Math.min(56, Math.max(36, thickness * 1.2))),
      };
    }
    if (placement.edge === "right") {
      return {
        x: Math.round(boundsX + boundsWidth - sliver * 0.5),
        y: Math.round(boundsY + boundsHeight - Math.min(56, Math.max(36, thickness * 1.2))),
      };
    }
    if (placement.edge === "top") {
      return {
        x: Math.round(boundsX + boundsWidth - Math.max(6, sliver)),
        y: Math.round(boundsY + thickness * 0.5),
      };
    }
    return {
      x: Math.round(boundsX + boundsWidth - Math.max(6, sliver)),
      y: Math.round(boundsY + boundsHeight - thickness * 0.5),
    };
  }
  return {
    x: normalizePoint(cursorScreen?.x, 0),
    y: normalizePoint(cursorScreen?.y, 0),
  };
}

function resolveScreenPoint(args, inputState = {}) {
  const anchor = normalizeDesktopAnchor(args.anchor || args.target || args.named_target);
  if (anchor) {
    return resolveDesktopAnchor(anchor, inputState);
  }
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
        const commandResult = await executeCommand({
          kind: "mouse.move",
          args: targetPoint,
        });
        if (typeof options.onSyntheticCursor === "function") {
          options.onSyntheticCursor(targetPoint);
        }
        const execution = commandResult?.execution && typeof commandResult.execution === "object"
          ? commandResult.execution
          : buildOrbExecutionSemantics({
              kind: step.kind,
              args: targetPoint,
              status: "completed",
              target: targetPoint,
            });
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
          execution,
        });
      } else if (step.kind === "mouse.click") {
        let targetPoint = null;
        if (
          step.args.anchor
          || (Number.isFinite(Number(step.args.x)) && Number.isFinite(Number(step.args.y)))
        ) {
          targetPoint = resolveScreenPoint(step.args, inputState);
          await executeCommand({
            kind: "mouse.move",
            args: targetPoint,
          });
          if (typeof options.onSyntheticCursor === "function") {
            options.onSyntheticCursor(targetPoint);
          }
        }
        const commandResult = await executeCommand({
          kind: "mouse.click",
          args: {
            button: step.args.button,
            double: Boolean(step.args.double),
          },
        });
        if (typeof options.onSyntheticInput === "function") {
          options.onSyntheticInput(step.kind);
        }
        const execution = commandResult?.execution && typeof commandResult.execution === "object"
          ? commandResult.execution
          : buildOrbExecutionSemantics({
              kind: step.kind,
              args: {
                ...step.args,
                ...(targetPoint ? targetPoint : {}),
              },
              status: "completed",
              target: targetPoint,
            });
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
          execution,
        });
      } else if (step.kind === "mouse.drag") {
        const endTarget = resolveScreenPoint(step.args, inputState);
        const startTarget = step.args.start_anchor
          || (Number.isFinite(Number(step.args.start_x)) && Number.isFinite(Number(step.args.start_y)))
          ? resolveScreenPoint({
              anchor: step.args.start_anchor,
              x: step.args.start_x,
              y: step.args.start_y,
              coordinate_space: step.args.coordinate_space,
            }, inputState)
          : null;
        const commandArgs = {
          button: step.args.button,
          duration_ms: step.args.duration_ms,
          steps: step.args.steps,
          x: endTarget.x,
          y: endTarget.y,
          coordinate_space: "screen",
          ...(startTarget ? {
            start_x: startTarget.x,
            start_y: startTarget.y,
          } : {}),
        };
        const commandResult = await executeCommand({
          kind: "mouse.drag",
          args: commandArgs,
        });
        if (typeof options.onSyntheticCursor === "function") {
          options.onSyntheticCursor(endTarget);
        }
        if (typeof options.onSyntheticInput === "function") {
          options.onSyntheticInput(step.kind);
        }
        const execution = commandResult?.execution && typeof commandResult.execution === "object"
          ? commandResult.execution
          : buildOrbExecutionSemantics({
              kind: step.kind,
              args: commandArgs,
              status: "completed",
              target: endTarget,
            });
        stepResults.push({
          index,
          kind: step.kind,
          status: "ok",
          started_at: stepStartedAt,
          finished_at: new Date().toISOString(),
          reason: step.reason,
          interaction: step.interaction,
          args: commandArgs,
          execution,
        });
      } else {
        const commandResult = await executeCommand({
          kind: step.kind,
          args: step.args,
        });
        if (typeof options.onSyntheticInput === "function") {
          options.onSyntheticInput(step.kind);
        }
        const execution = commandResult?.execution && typeof commandResult.execution === "object"
          ? commandResult.execution
          : buildOrbExecutionSemantics({
              kind: step.kind,
              args: step.args,
              status: "completed",
            });
        stepResults.push({
          index,
          kind: step.kind,
          status: "ok",
          started_at: stepStartedAt,
          finished_at: new Date().toISOString(),
          reason: step.reason,
          interaction: step.interaction,
          args: { ...step.args },
          execution,
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
  inferTaskbarPlacement,
  normalizeDesktopAnchor,
  normalizeOrbDesktopPlan,
  normalizeOrbPlanStep,
  resolveDesktopAnchor,
  resolveScreenPoint,
};
