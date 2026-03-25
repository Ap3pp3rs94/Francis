const path = require("node:path");
const http = require("node:http");
const https = require("node:https");
const { spawn } = require("node:child_process");

const DEFAULT_OLLAMA_URL = process.env.FRANCIS_OLLAMA_HOST || process.env.OLLAMA_HOST || "http://127.0.0.1:11434";
const DEFAULT_BOOT_TIMEOUT_MS = 45000;
const DEFAULT_POLL_MS = 350;

function normalizeOllamaUrl(raw = DEFAULT_OLLAMA_URL) {
  let value = String(raw || DEFAULT_OLLAMA_URL).trim() || DEFAULT_OLLAMA_URL;
  if (!/^[a-z]+:\/\//i.test(value)) {
    value = `http://${value}`;
  }
  const url = new URL(value);
  url.pathname = "/";
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/$/, "");
}

function buildOllamaHealthUrl(ollamaUrl) {
  return new URL("/api/version", `${normalizeOllamaUrl(ollamaUrl)}/`).toString();
}

function buildOllamaCatalogUrl(ollamaUrl) {
  return new URL("/api/tags", `${normalizeOllamaUrl(ollamaUrl)}/`).toString();
}

function buildOllamaListenAddress(ollamaUrl) {
  const url = new URL(`${normalizeOllamaUrl(ollamaUrl)}/`);
  const port = Number(url.port || (url.protocol === "https:" ? "443" : "80"));
  return `${url.hostname}:${port}`;
}

function resolveOllamaSourceRoot({ appDir }) {
  return path.resolve(appDir, "..");
}

function parseOllamaModelCatalog(payload) {
  return Array.isArray(payload?.models)
    ? payload.models
        .map((entry) => String(entry?.model || entry?.name || "").trim())
        .filter(Boolean)
    : [];
}

function requestUrl(targetUrl, { timeoutMs = 1500, headers = {} } = {}) {
  const target = new URL(targetUrl);
  const transport = target.protocol === "https:" ? https : http;

  return new Promise((resolve, reject) => {
    const request = transport.request(
      target,
      {
        method: "GET",
        headers,
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
        response.on("end", () => {
          resolve({
            statusCode: Number(response.statusCode || 0),
            body: Buffer.concat(chunks).toString("utf8"),
          });
        });
      },
    );

    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`Request timed out after ${timeoutMs}ms`));
    });
    request.once("error", reject);
    request.end();
  });
}

async function requestJson(targetUrl, { timeoutMs = 1500, headers = {} } = {}) {
  const response = await requestUrl(targetUrl, { timeoutMs, headers });
  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(`Ollama probe returned HTTP ${response.statusCode}`);
  }
  return response.body.trim() ? JSON.parse(response.body) : {};
}

async function probeOllamaHealth(ollamaUrl, timeoutMs = 1500) {
  const response = await requestUrl(buildOllamaHealthUrl(ollamaUrl), {
    timeoutMs,
    headers: {
      accept: "application/json, text/plain",
    },
  });
  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(`Ollama health probe returned HTTP ${response.statusCode}`);
  }
}

async function fetchOllamaCatalog(ollamaUrl, timeoutMs = 1500) {
  return requestJson(buildOllamaCatalogUrl(ollamaUrl), {
    timeoutMs,
    headers: {
      accept: "application/json",
    },
  });
}

async function isOllamaReachable(ollamaUrl, timeoutMs = 1500) {
  try {
    await probeOllamaHealth(ollamaUrl, timeoutMs);
    try {
      const payload = await fetchOllamaCatalog(ollamaUrl, timeoutMs);
      return parseOllamaModelCatalog(payload);
    } catch {
      return [];
    }
  } catch {
    return null;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForOllamaReady(ollamaUrl, child, { timeoutMs = DEFAULT_BOOT_TIMEOUT_MS, pollMs = DEFAULT_POLL_MS } = {}) {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const availableModels = await isOllamaReachable(ollamaUrl, Math.min(1200, pollMs * 3));
    if (availableModels !== null) {
      return availableModels;
    }

    if (child && child.exitCode !== null) {
      throw new Error(`Managed Ollama process exited with code ${child.exitCode}`);
    }

    await sleep(pollMs);
  }

  throw new Error(`Managed Ollama did not become healthy within ${timeoutMs}ms`);
}

function onceProcessExit(child) {
  return new Promise((resolve) => {
    if (!child) {
      resolve({ code: null, signal: null });
      return;
    }
    child.once("exit", (code, signal) => {
      resolve({ code, signal });
    });
  });
}

function intOrZero(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.trunc(parsed)) : 0;
}

function buildManagedExitUpdate({ previousState, code, signal, shutdownRequested }) {
  const safeState = previousState && typeof previousState === "object" ? previousState : {};
  const unexpected = !shutdownRequested && safeState.mode === "managed";
  return {
    ready: false,
    mode: unexpected ? "crashed" : safeState.mode === "managed" ? "stopped" : safeState.mode,
    managed: false,
    runtimeKind: null,
    runtimePath: null,
    pid: null,
    availableModels: [],
    lastError:
      code === 0 && !unexpected
        ? safeState.lastError
        : `Managed Ollama exited with code ${code}${signal ? ` signal ${signal}` : ""}`,
    lastExitCode: code,
    lastExitSignal: signal,
    crashCount: unexpected ? intOrZero(safeState.crashCount) + 1 : intOrZero(safeState.crashCount),
    restartSuggested: unexpected,
  };
}

async function terminateProcessTree(child, { force = false } = {}) {
  if (!child || child.exitCode !== null) {
    return { code: child?.exitCode ?? null, signal: null };
  }

  if (process.platform === "win32") {
    const args = ["/pid", String(child.pid), "/t"];
    if (force) {
      args.push("/f");
    }
    await new Promise((resolve) => {
      const killer = spawn("taskkill", args, { windowsHide: true, stdio: "ignore" });
      killer.once("exit", () => resolve());
      killer.once("error", () => resolve());
    });
    return onceProcessExit(child);
  }

  child.kill(force ? "SIGKILL" : "SIGTERM");
  return onceProcessExit(child);
}

function describeLaunchCandidate(candidate) {
  return [candidate.command, ...candidate.args].join(" ");
}

function buildManagedOllamaEnv(env = process.env, listenAddress) {
  const nextEnv = {
    ...env,
  };
  for (const key of Object.keys(nextEnv)) {
    const normalized = String(key || "").trim().toUpperCase();
    if (normalized === "OLLAMA_HOST" || normalized === "FRANCIS_OLLAMA_HOST") {
      delete nextEnv[key];
    }
  }
  nextEnv.OLLAMA_HOST = String(listenAddress || "");
  return nextEnv;
}

function buildOllamaLaunchCandidates({ appDir, ollamaUrl = DEFAULT_OLLAMA_URL, env = process.env } = {}) {
  const sourceRoot = resolveOllamaSourceRoot({ appDir });
  const normalizedUrl = normalizeOllamaUrl(ollamaUrl);
  const listenAddress = buildOllamaListenAddress(normalizedUrl);
  const candidates = [
    ...(env.FRANCIS_OLLAMA_BINS || "")
      .split(path.delimiter)
      .map((value) => value.trim())
      .filter(Boolean),
    env.FRANCIS_OLLAMA_BIN,
    env.LOCALAPPDATA ? path.join(env.LOCALAPPDATA, "Programs", "Ollama", "ollama.exe") : "",
    env.ProgramFiles ? path.join(env.ProgramFiles, "Ollama", "ollama.exe") : "",
    "ollama",
  ].filter(Boolean);

  const seen = new Set();
  return candidates
    .filter((candidate) => {
      const key = String(candidate || "").trim().toLowerCase();
      if (!key || seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .map((candidate) => ({
      command: candidate,
      args: ["serve"],
      cwd: sourceRoot,
      env: buildManagedOllamaEnv(env, listenAddress),
      runtimeKind: path.isAbsolute(candidate) ? "installed" : "path",
      runtimePath: candidate,
      serviceUrl: normalizedUrl,
    }));
}

function createOllamaRuntimeManager({
  appDir,
  ollamaUrl = DEFAULT_OLLAMA_URL,
  env = process.env,
  log = () => {},
  onStateChanged = () => {},
} = {}) {
  const normalizedOllamaUrl = normalizeOllamaUrl(ollamaUrl);
  const allowManagedStart = !["0", "false", "no"].includes(String(env.FRANCIS_OVERLAY_MANAGE_OLLAMA || "1").toLowerCase());
  const state = {
    ready: false,
    mode: "idle",
    managed: false,
    attemptedAutoStart: false,
    serviceUrl: normalizedOllamaUrl,
    healthUrl: buildOllamaHealthUrl(normalizedOllamaUrl),
    launcher: null,
    runtimeKind: null,
    runtimePath: null,
    pid: null,
    availableModels: [],
    lastError: null,
    lastExitCode: null,
    lastExitSignal: null,
    crashCount: 0,
    restartSuggested: false,
  };

  let child = null;
  let shutdownRequested = false;

  function setState(next) {
    Object.assign(state, next);
    onStateChanged(getPublicState());
  }

  function attachManagedLogs(processRef) {
    if (!processRef?.stdout || !processRef?.stderr) {
      return;
    }
    processRef.stdout.on("data", (chunk) => {
      log(`Ollama stdout: ${String(chunk).trimEnd()}`);
    });
    processRef.stderr.on("data", (chunk) => {
      log(`Ollama stderr: ${String(chunk).trimEnd()}`);
    });
    processRef.on("exit", (code, signal) => {
      const exitedManaged = child && processRef.pid === child.pid;
      if (!exitedManaged) {
        return;
      }
      child = null;
      setState(
        buildManagedExitUpdate({
          previousState: state,
          code,
          signal,
          shutdownRequested,
        }),
      );
      shutdownRequested = false;
    });
  }

  async function ensureReady() {
    const externalModels = await isOllamaReachable(normalizedOllamaUrl);
    if (externalModels !== null) {
      setState({
        ready: true,
        mode: "external",
        managed: false,
        attemptedAutoStart: false,
        launcher: null,
        runtimeKind: null,
        runtimePath: null,
        pid: null,
        availableModels: externalModels,
        lastError: null,
        lastExitCode: null,
        lastExitSignal: null,
        restartSuggested: false,
      });
      return getPublicState();
    }

    if (!allowManagedStart) {
      const message = "Managed Ollama startup is disabled by FRANCIS_OVERLAY_MANAGE_OLLAMA";
      setState({
        ready: false,
        mode: "disabled",
        managed: false,
        attemptedAutoStart: false,
        runtimeKind: null,
        runtimePath: null,
        availableModels: [],
        lastError: message,
        restartSuggested: false,
      });
      throw new Error(message);
    }

    const candidates = buildOllamaLaunchCandidates({
      appDir,
      ollamaUrl: normalizedOllamaUrl,
      env,
    });

    let lastError = null;

    for (const candidate of candidates) {
      setState({
        ready: false,
        mode: "starting",
        managed: false,
        attemptedAutoStart: true,
        launcher: describeLaunchCandidate(candidate),
        runtimeKind: candidate.runtimeKind || null,
        runtimePath: candidate.runtimePath || null,
        pid: null,
        availableModels: [],
        lastError: null,
        lastExitCode: null,
        lastExitSignal: null,
        restartSuggested: false,
      });
      log(`Starting managed Ollama: ${describeLaunchCandidate(candidate)}`, {
        bindAddress: candidate.env.OLLAMA_HOST,
      });

      try {
        shutdownRequested = false;
        child = spawn(candidate.command, candidate.args, {
          cwd: candidate.cwd,
          env: candidate.env,
          stdio: ["ignore", "pipe", "pipe"],
          windowsHide: true,
        });
      } catch (error) {
        lastError = error;
        log(`Managed Ollama launch failed: ${error instanceof Error ? error.message : String(error)}`);
        continue;
      }

      attachManagedLogs(child);
      setState({ pid: child.pid });

      try {
        const availableModels = await waitForOllamaReady(normalizedOllamaUrl, child);
        setState({
          ready: true,
          mode: "managed",
          managed: true,
          runtimeKind: candidate.runtimeKind || null,
          runtimePath: candidate.runtimePath || null,
          pid: child.pid,
          availableModels,
          lastError: null,
          lastExitCode: null,
          lastExitSignal: null,
          restartSuggested: false,
        });
        return getPublicState();
      } catch (error) {
        lastError = error;
        log(`Managed Ollama did not become ready: ${error instanceof Error ? error.message : String(error)}`);
        await terminateProcessTree(child, { force: true });
        child = null;
      }
    }

    const message = lastError instanceof Error ? lastError.message : "Managed Ollama startup failed";
    setState({
      ready: false,
      mode: "error",
      managed: false,
      runtimeKind: null,
      runtimePath: null,
      pid: null,
      availableModels: [],
      lastError: message,
      restartSuggested: false,
    });
    throw new Error(message);
  }

  async function restart() {
    await shutdown({ force: true });
    return ensureReady();
  }

  async function shutdown({ force = true } = {}) {
    if (!child || child.exitCode !== null) {
      return getPublicState();
    }

    shutdownRequested = true;
    await terminateProcessTree(child, { force });
    child = null;
    setState({
      ready: false,
      mode: "stopped",
      managed: false,
      runtimeKind: null,
      runtimePath: null,
      pid: null,
      availableModels: [],
      restartSuggested: false,
    });
    return getPublicState();
  }

  function getPublicState() {
    return {
      ...state,
      allowManagedStart,
    };
  }

  return {
    ensureReady,
    restart,
    shutdown,
    getPublicState,
  };
}

module.exports = {
  DEFAULT_BOOT_TIMEOUT_MS,
  DEFAULT_OLLAMA_URL,
  DEFAULT_POLL_MS,
  buildManagedExitUpdate,
  buildManagedOllamaEnv,
  buildOllamaCatalogUrl,
  buildOllamaHealthUrl,
  buildOllamaLaunchCandidates,
  buildOllamaListenAddress,
  createOllamaRuntimeManager,
  fetchOllamaCatalog,
  isOllamaReachable,
  normalizeOllamaUrl,
  parseOllamaModelCatalog,
  probeOllamaHealth,
  resolveOllamaSourceRoot,
  waitForOllamaReady,
};
