const test = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const {
  buildManagedExitUpdate,
  buildManagedOllamaEnv,
  buildOllamaCatalogUrl,
  buildOllamaHealthUrl,
  buildOllamaLaunchCandidates,
  buildOllamaListenAddress,
  formatManagedLaunchError,
  isLaunchCandidateAvailable,
  isOllamaReachable,
  normalizeOllamaUrl,
  parseOllamaModelCatalog,
  probeOllamaHealth,
  raceChildError,
  resolveOllamaSourceRoot,
  waitForOllamaReady,
} = require("./ollama-runtime");

function makeTempRoot() {
  return path.join(os.tmpdir(), "francis-overlay-ollama-test-root");
}

test("normalizeOllamaUrl trims path state and builds the tags health url", () => {
  const ollamaUrl = normalizeOllamaUrl("127.0.0.1:11434/api/tags?x=1");
  assert.equal(ollamaUrl, "http://127.0.0.1:11434");
  assert.equal(buildOllamaHealthUrl(ollamaUrl), "http://127.0.0.1:11434/api/version");
  assert.equal(buildOllamaCatalogUrl(ollamaUrl), "http://127.0.0.1:11434/api/tags");
  assert.equal(buildOllamaListenAddress(ollamaUrl), "127.0.0.1:11434");
});

test("resolveOllamaSourceRoot chooses the repo root from the Electron app dir", () => {
  assert.equal(
    resolveOllamaSourceRoot({ appDir: "D:/francis/electron" }),
    path.resolve("D:/francis"),
  );
});

test("parseOllamaModelCatalog tolerates model and name payload keys", () => {
  assert.deepEqual(
    parseOllamaModelCatalog({
      models: [
        { model: "llama3.1:8b" },
        { name: "phi4:14b" },
        {},
      ],
    }),
    ["llama3.1:8b", "phi4:14b"],
  );
});

test("buildOllamaLaunchCandidates wires a host-bound managed serve command", () => {
  const appDir = path.resolve("D:/francis/electron");
  const userLocal = path.join(makeTempRoot(), "LocalAppData");
  const programFiles = path.join(makeTempRoot(), "ProgramFiles");
  const candidates = buildOllamaLaunchCandidates({
    appDir,
    ollamaUrl: "http://127.0.0.1:11434",
    env: {
      LOCALAPPDATA: userLocal,
      ProgramFiles: programFiles,
      FRANCIS_OLLAMA_BINS: "ollama",
    },
  });

  assert.ok(candidates.length >= 1);
  assert.equal(candidates[0].command, "ollama");
  assert.deepEqual(candidates[0].args, ["serve"]);
  assert.equal(candidates[0].env.OLLAMA_HOST, "127.0.0.1:11434");
  assert.equal(candidates[0].serviceUrl, "http://127.0.0.1:11434");
});

test("absolute launch candidates are rejected when the launcher path is missing", () => {
  assert.equal(
    isLaunchCandidateAvailable({
      command: "C:\\Program Files\\Ollama\\ollama.exe",
    }),
    false,
  );
  assert.equal(
    isLaunchCandidateAvailable({
      command: "ollama",
    }),
    true,
  );
});

test("buildManagedOllamaEnv strips scheme-bearing inherited host values", () => {
  const env = buildManagedOllamaEnv(
    {
      FRANCIS_OLLAMA_HOST: "http://127.0.0.1:11434",
      OLLAMA_HOST: "http://127.0.0.1:11434",
      Path: "C:\\Windows\\System32",
    },
    "127.0.0.1:11434",
  );

  assert.equal(env.OLLAMA_HOST, "127.0.0.1:11434");
  assert.equal(env.FRANCIS_OLLAMA_HOST, undefined);
  assert.equal(env.Path, "C:\\Windows\\System32");
});

test("isOllamaReachable and waitForOllamaReady observe a live local tags endpoint", async () => {
  const server = http.createServer((request, response) => {
    if (request.url === "/api/version") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ version: "0.18.0" }));
      return;
    }
    if (request.url === "/api/tags") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ models: [{ model: "llama3.1:8b" }, { model: "phi4:14b" }] }));
      return;
    }
    response.writeHead(404);
    response.end();
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const ollamaUrl = `http://127.0.0.1:${address.port}`;

  await probeOllamaHealth(ollamaUrl, 1000);
  assert.deepEqual(await isOllamaReachable(ollamaUrl, 1000), ["llama3.1:8b", "phi4:14b"]);
  assert.deepEqual(
    await waitForOllamaReady(ollamaUrl, { exitCode: null }, { timeoutMs: 1500, pollMs: 100 }),
    ["llama3.1:8b", "phi4:14b"],
  );

  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
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
  assert.match(update.lastError, /Managed Ollama exited with code 1/);
});

test("raceChildError rejects when the child emits an async spawn failure", async () => {
  const child = new EventEmitter();
  child.exitCode = null;

  const guarded = raceChildError(
    child,
    new Promise((resolve) => setTimeout(resolve, 1000)),
  );

  setImmediate(() => {
    const error = new Error("spawn C:\\Program Files\\Ollama\\ollama.exe ENOENT");
    error.code = "ENOENT";
    child.emit("error", error);
  });

  await assert.rejects(guarded, /ENOENT/);
});

test("formatManagedLaunchError rewrites missing launcher failures into a calm runtime message", () => {
  const error = new Error("spawn C:\\Program Files\\Ollama\\ollama.exe ENOENT");
  error.code = "ENOENT";

  const formatted = formatManagedLaunchError(error, {
    command: "C:\\Program Files\\Ollama\\ollama.exe",
    runtimePath: "C:\\Program Files\\Ollama\\ollama.exe",
  });

  assert.match(formatted.message, /Managed Ollama launcher not found/i);
  assert.match(formatted.message, /C:\\Program Files\\Ollama\\ollama\.exe/i);
});
