const test = require("node:test");
const assert = require("node:assert/strict");

const {
  executeOrbDesktopPlan,
  inferTaskbarPlacement,
  normalizeOrbDesktopPlan,
  resolveDesktopAnchor,
  resolveScreenPoint,
} = require("./orb-plan");

test("normalizeOrbDesktopPlan accepts delay_ms wait_ms and pause_ms", () => {
  const plan = normalizeOrbDesktopPlan({
    title: "Open Notepad",
    steps: [
      { kind: "keyboard.shortcut", args: { keys: ["ctrl", "esc"] }, wait_ms: 120 },
      { kind: "keyboard.type", args: { text: "notepad" }, pause_ms: 180 },
      { kind: "keyboard.key", args: { key: "enter" }, delay_ms: 220 },
    ],
  });

  assert.deepEqual(
    plan.steps.map((step) => step.delay_ms),
    [120, 180, 220],
  );
});

test("resolveScreenPoint translates display-relative coordinates through the work area", () => {
  const point = resolveScreenPoint(
    { x: 140, y: 88, coordinate_space: "display" },
    { workArea: { x: 100, y: 40 } },
  );

  assert.deepEqual(point, { x: 240, y: 128 });
});

test("resolveDesktopAnchor infers the Start button from display bounds and work area", () => {
  const placement = inferTaskbarPlacement(
    { x: 0, y: 0, width: 1920, height: 1080 },
    { x: 0, y: 0, width: 1920, height: 1032 },
  );
  assert.deepEqual(placement, { edge: "bottom", thickness: 48 });

  const point = resolveDesktopAnchor("start_button", {
    displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
    displayWorkArea: { x: 0, y: 0, width: 1920, height: 1032 },
  });
  assert.deepEqual(point, { x: 58, y: 1056 });
});

test("resolveScreenPoint accepts named desktop anchors", () => {
  const point = resolveScreenPoint(
    { anchor: "start_button" },
    {
      displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
      displayWorkArea: { x: 0, y: 0, width: 1920, height: 1032 },
      cursorScreen: { x: 480, y: 720 },
    },
  );

  assert.deepEqual(point, { x: 58, y: 1056 });
});

test("resolveDesktopAnchor infers the show-desktop button from taskbar bounds", () => {
  const point = resolveDesktopAnchor("show_desktop_button", {
    displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
    displayWorkArea: { x: 0, y: 0, width: 1920, height: 1032 },
  });

  assert.deepEqual(point, { x: 1906, y: 1056 });
});

test("executeOrbDesktopPlan moves before a positioned click and returns a shell summary", async () => {
  const commands = [];
  const sleeps = [];
  const synthetic = [];
  const result = await executeOrbDesktopPlan(
    {
      title: "Open Context Menu",
      steps: [
        {
          kind: "mouse.click",
          args: { x: 40, y: 60, button: "right", coordinate_space: "display" },
          reason: "Open the context menu at the current target.",
          delay_ms: 180,
        },
      ],
    },
    {
      inputState: { workArea: { x: 10, y: 20 } },
      executeCommand: async (command) => {
        commands.push(command);
        return { status: "ok" };
      },
      sleep: async (delayMs) => {
        sleeps.push(delayMs);
      },
      onSyntheticCursor: (point) => {
        synthetic.push(point);
      },
    },
  );

  assert.equal(result.status, "ok");
  assert.equal(result.summary, "Open Context Menu completed through the Orb shell.");
  assert.equal(result.steps[0].execution.phase, "click_act");
  assert.equal(result.steps[0].execution.summary, "Right click committed cleanly.");
  assert.deepEqual(commands, [
    { kind: "mouse.move", args: { x: 50, y: 80 } },
    { kind: "mouse.click", args: { button: "right", double: false } },
  ]);
  assert.deepEqual(synthetic, [{ x: 50, y: 80 }]);
  assert.deepEqual(sleeps, [180]);
});

test("executeOrbDesktopPlan supports mouse.drag and records anchored execution semantics", async () => {
  const commands = [];
  const synthetic = [];
  const result = await executeOrbDesktopPlan(
    {
      title: "Drag Francis Lens",
      steps: [
        {
          kind: "mouse.drag",
          args: {
            start_anchor: "start_button",
            x: 260,
            y: 180,
            coordinate_space: "display",
            button: "left",
            duration_ms: 320,
            steps: 10,
          },
          reason: "Drag the target into place.",
        },
      ],
    },
    {
      inputState: {
        workArea: { x: 10, y: 20 },
        displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
        displayWorkArea: { x: 0, y: 0, width: 1920, height: 1032 },
      },
      executeCommand: async (command) => {
        commands.push(command);
        return { status: "ok" };
      },
      onSyntheticCursor: (point) => {
        synthetic.push(point);
      },
    },
  );

  assert.equal(result.status, "ok");
  assert.deepEqual(commands, [
    {
      kind: "mouse.drag",
      args: {
        button: "left",
        duration_ms: 320,
        steps: 10,
        x: 270,
        y: 200,
        coordinate_space: "screen",
        start_x: 58,
        start_y: 1056,
      },
    },
  ]);
  assert.deepEqual(synthetic, [{ x: 270, y: 200 }]);
  assert.equal(result.steps[0].execution.phase, "drag_act");
  assert.equal(result.steps[0].execution.sustained_contact, true);
});

test("executeOrbDesktopPlan returns a failed result instead of throwing when command execution fails", async () => {
  const result = await executeOrbDesktopPlan(
    {
      title: "Open Notepad",
      steps: [
        { kind: "keyboard.shortcut", args: { keys: ["ctrl", "esc"] } },
      ],
    },
    {
      executeCommand: async () => {
        throw new Error("SendKeys failed");
      },
    },
  );

  assert.equal(result.status, "failed");
  assert.match(result.error, /SendKeys failed/);
  assert.equal(result.completed_steps, 0);
});

test("executeOrbDesktopPlan moves to named anchors before clicking", async () => {
  const commands = [];
  const result = await executeOrbDesktopPlan(
    {
      title: "Open Start",
      steps: [
        {
          kind: "mouse.click",
          args: { button: "left", anchor: "start_button" },
          reason: "Open Start with a left click.",
          delay_ms: 120,
        },
      ],
    },
    {
      inputState: {
        displayBounds: { x: 0, y: 0, width: 1920, height: 1080 },
        displayWorkArea: { x: 0, y: 0, width: 1920, height: 1032 },
      },
      executeCommand: async (command) => {
        commands.push(command);
        return { status: "ok" };
      },
      sleep: async () => {},
    },
  );

  assert.equal(result.status, "ok");
  assert.deepEqual(commands, [
    { kind: "mouse.move", args: { x: 58, y: 1056 } },
    { kind: "mouse.click", args: { button: "left", double: false } },
  ]);
});
