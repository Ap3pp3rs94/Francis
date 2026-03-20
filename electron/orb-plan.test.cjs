const test = require("node:test");
const assert = require("node:assert/strict");

const {
  executeOrbDesktopPlan,
  normalizeOrbDesktopPlan,
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
  assert.deepEqual(commands, [
    { kind: "mouse.move", args: { x: 50, y: 80 } },
    { kind: "mouse.click", args: { button: "right", double: false } },
  ]);
  assert.deepEqual(synthetic, [{ x: 50, y: 80 }]);
  assert.deepEqual(sleeps, [180]);
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
