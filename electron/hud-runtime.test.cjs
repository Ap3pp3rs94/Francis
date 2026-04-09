const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const {
  appendEnvPath,
  buildManagedExitUpdate,
  buildHudHealthUrl,
  buildHudLaunchCandidates,
  buildHudWorkspaceRoot,
  classifyHudReachabilityFailure,
  getHudProbeDelayMs,
  isHudReachable,
  normalizeHudUrl,
  probeHudReachability,
  resolveManagedHudExitUpdate,
  resolveHudSourceRoot,
  waitForHudReady,
} = require("./hud-runtime");

function makeTempRoot() {
  return path.join(os.tmpdir(), "francis-overlay-test-root");
}

test("normalizeHudUrl trims path state and builds a health url", () => {
  const hudUrl = normalizeHudUrl("http://127.0.0.1:8767/api/bootstrap?x=1");
  assert.equal(hudUrl, "http://127.0.0.1:8767");
  assert.equal(buildHudHealthUrl(hudUrl), "http://127.0.0.1:8767/health");
});

test("appendEnvPath prepends new values without losing existing entries", () => {
  const merged = appendEnvPath(`C:${path.delimiter}tools`, "D:/francis");
  assert.ok(merged.startsWith(`D:/francis${path.delimiter}`));
  assert.ok(merged.endsWith(`C:${path.delimiter}tools`));
});

test("resolveHudSourceRoot chooses repo root in dev and python-src in packaged mode", () => {
  const appDir = "D:/francis/electron";
  assert.equal(
    resolveHudSourceRoot({ appDir, resourcesPath: "C:/ignored", isPackaged: false }),
    path.resolve("D:/francis"),
  );
  assert.equal(
    resolveHudSourceRoot({ appDir, resourcesPath: "C:/Francis/resources", isPackaged: true }),
    path.join("C:/Francis/resources", "python-src"),
  );
});

test("buildHudLaunchCandidates wires host, port, source root, and workspace root", () => {
  const sourceRoot = path.resolve("D:/francis");
  const userDataPath = path.join(makeTempRoot(), "userdata");
  const candidates = buildHudLaunchCandidates({
    sourceRoot,
    resourcesPath: "C:/ignored",
    hudUrl: "http://127.0.0.1:9009",
    env: { PATH: "X", PYTHONPATH: "Y", FRANCIS_HUD_PYTHONS: "python" },
    userDataPath,
    isPackaged: false,
  });

  assert.ok(candidates.length >= 1);
  assert.equal(candidates[0].command, "python");
  assert.equal(candidates[0].runtimeKind, "external");
  assert.deepEqual(candidates[0].args, [
    "-m",
    "services.hud.app.run_hud",
    "--host",
    "127.0.0.1",
    "--port",
    "9009",
  ]);
  assert.equal(candidates[0].cwd, sourceRoot);
  assert.equal(
    candidates[0].env.FRANCIS_WORKSPACE_ROOT,
    buildHudWorkspaceRoot({ sourceRoot, userDataPath, isPackaged: false }),
  );
  assert.ok(candidates[0].env.PYTHONPATH.startsWith(sourceRoot));
});

test("buildHudLaunchCandidates prefers a bundled packaged runtime when available", () => {
  const sourceRoot = path.resolve("D:/francis");
  const userDataPath = path.join(makeTempRoot(), "userdata");
  const resourcesPath = path.join(makeTempRoot(), "resources");
  const bundledRuntime = path.join(resourcesPath, "python-runtime");
  fs.mkdirSync(bundledRuntime, { recursive: true });
  fs.writeFileSync(path.join(bundledRuntime, "python.exe"), "", "utf8");

  const candidates = buildHudLaunchCandidates({
    sourceRoot,
    resourcesPath,
    hudUrl: "http://127.0.0.1:9010",
    env: { PATH: "X", PYTHONPATH: "Y", FRANCIS_HUD_PYTHONS: "python" },
    userDataPath,
    isPackaged: true,
  });

  assert.ok(candidates.length >= 2);
  assert.equal(candidates[0].command, path.join(bundledRuntime, "python.exe"));
  assert.equal(candidates[0].runtimeKind, "bundled");
  assert.equal(candidates[0].env.PYTHONHOME, bundledRuntime);
  assert.ok(candidates[0].env.PATH.startsWith(bundledRuntime));
});

test("buildHudWorkspaceRoot switches to user data in packaged mode", () => {
  const sourceRoot = path.resolve("D:/francis");
  const userDataPath = path.join(makeTempRoot(), "userdata");

  assert.equal(
    buildHudWorkspaceRoot({ sourceRoot, userDataPath, isPackaged: false }),
    path.join(sourceRoot, "workspace"),
  );
  assert.equal(
    buildHudWorkspaceRoot({ sourceRoot, userDataPath, isPackaged: true }),
    path.join(userDataPath, "workspace"),
  );
});

test("isHudReachable and waitForHudReady observe a live local health endpoint", async () => {
  const server = http.createServer((request, response) => {
    if (request.url === "/health") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end('{"status":"ok"}');
      return;
    }
    response.writeHead(404);
    response.end();
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const hudUrl = `http://127.0.0.1:${address.port}`;

  assert.equal(await isHudReachable(hudUrl, 1000), true);
  await waitForHudReady(hudUrl, { exitCode: null }, { timeoutMs: 1500, pollMs: 100 });

  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
});

test("probeHudReachability classifies non-200 responses", async () => {
  const server = http.createServer((request, response) => {
    if (request.url === "/health") {
      response.writeHead(503, { "content-type": "application/json" });
      response.end('{"detail":"unavailable"}');
      return;
    }
    response.writeHead(404);
    response.end();
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const probe = await probeHudReachability(`http://127.0.0.1:${address.port}`, 1000);
  assert.equal(probe.ok, false);
  assert.equal(probe.error.kind, "non_200");
  assert.equal(probe.statusCode, 503);

  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
});

test("getHudProbeDelayMs applies bounded retry backoff for managed HUD probes", () => {
  assert.equal(getHudProbeDelayMs(0, { baseMs: 200 }), 200);
  assert.equal(getHudProbeDelayMs(1, { baseMs: 200 }), 400);
  assert.equal(getHudProbeDelayMs(2, { baseMs: 200 }), 800);
  assert.equal(getHudProbeDelayMs(5, { baseMs: 200, maxMs: 900 }), 900);
});

test("classifyHudReachabilityFailure distinguishes timeout and connection refusal", () => {
  assert.equal(
    classifyHudReachabilityFailure(new Error("Request timed out after 8000ms")).kind,
    "timeout",
  );
  const refused = new Error("connect ECONNREFUSED 127.0.0.1:8767");
  refused.cause = { code: "ECONNREFUSED" };
  assert.equal(classifyHudReachabilityFailure(refused).kind, "connection_refused");
});

test("buildManagedExitUpdate marks unexpected managed exits as recoverable crashes", () => {
  const update = buildManagedExitUpdate({
    previousState: { mode: "managed", crashCount: 1, lastError: null },
    code: 1,
    signal: null,
    shutdownRequested: false,
  });

  assert.equal(update.mode, "crashed");
  assert.equal(update.restartSuggested, true);
  assert.equal(update.crashCount, 2);
  assert.match(update.lastError, /Managed HUD exited with code 1/);
});

test("buildManagedExitUpdate leaves intentional shutdowns in stopped mode", () => {
  const update = buildManagedExitUpdate({
    previousState: { mode: "managed", crashCount: 2, lastError: null },
    code: 0,
    signal: null,
    shutdownRequested: true,
  });

  assert.equal(update.mode, "stopped");
  assert.equal(update.restartSuggested, false);
  assert.equal(update.crashCount, 2);
});

test("resolveManagedHudExitUpdate keeps a healthy detached HUD alive", async () => {
  const server = http.createServer((request, response) => {
    if (request.url === "/health") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end('{"status":"ok"}');
      return;
    }
    response.writeHead(404);
    response.end();
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const hudUrl = `http://127.0.0.1:${address.port}`;
  const update = await resolveManagedHudExitUpdate({
    previousState: {
      ready: true,
      mode: "managed",
      managed: true,
      attemptedAutoStart: true,
      runtimeKind: "external",
      runtimePath: "D:/francis/.venv/Scripts/python.exe",
      crashCount: 1,
      lastError: null,
    },
    code: 0,
    signal: null,
    shutdownRequested: false,
    hudUrl,
    timeoutMs: 1000,
  });

  assert.equal(update.ready, true);
  assert.equal(update.mode, "external");
  assert.equal(update.managed, false);
  assert.equal(update.restartSuggested, false);
  assert.equal(update.lastError, null);

  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
});
