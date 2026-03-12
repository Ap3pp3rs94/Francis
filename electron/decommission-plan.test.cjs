const test = require("node:test");
const assert = require("node:assert/strict");

const { buildDecommissionPlan, buildRemovalCommand } = require("./decommission-plan");

test("decommission plan separates shell residue from workspace continuity", () => {
  const plan = buildDecommissionPlan({
    buildIdentity: "0.1.0+abc1234",
    distribution: "installer",
    installRoot: "C:\\Program Files\\Francis Overlay",
    execPath: "C:\\Program Files\\Francis Overlay\\Francis Overlay.exe",
    userDataPath: "C:\\Users\\Alice\\AppData\\Roaming\\Francis Overlay",
    workspaceRoot: "C:\\Users\\Alice\\AppData\\Roaming\\Francis Overlay\\workspace",
    retainedState: {
      items: [
        {
          id: "preferences",
          removable: true,
          exists: true,
          path: "C:\\Users\\Alice\\AppData\\Roaming\\Francis Overlay\\overlay-preferences.json",
        },
        {
          id: "workspace_root",
          removable: false,
          exists: true,
          path: "C:\\Users\\Alice\\AppData\\Roaming\\Francis Overlay\\workspace",
        },
        {
          id: "launch_at_login",
          removable: true,
          enabled: true,
          path: null,
        },
      ],
    },
    rollbackState: {
      count: 2,
    },
    portabilityState: {
      lastExportAt: "2026-03-12T10:00:00Z",
    },
    launchAtLogin: {
      available: true,
      enabled: true,
    },
  });

  assert.equal(plan.exportRecommended, true);
  assert.match(plan.summary, /shell residue/i);
  assert.equal(plan.shellResiduePaths.some((entry) => entry.endsWith("overlay-preferences.json")), true);
  assert.equal(plan.shellResiduePaths.some((entry) => entry.endsWith("overlay-backups")), true);
  assert.equal(plan.shellResiduePaths.includes("C:\\Users\\Alice\\AppData\\Roaming\\Francis Overlay\\workspace"), false);
  assert.match(plan.shellResidueCommand, /Remove-Item/);
  assert.match(plan.continuityCommand, /workspace/);
  assert.equal(plan.cards.some((card) => card.label === "Startup Entry" && /enabled/i.test(card.value)), true);
});

test("decommission removal command returns null when no paths remain", () => {
  assert.equal(buildRemovalCommand([]), null);
});
