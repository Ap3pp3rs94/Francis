const path = require("node:path");
const http = require("node:http");
const https = require("node:https");
const { spawn } = require("node:child_process");
const {
  buildBundledRuntimeEnv,
  getBundledPythonExecutable,
  pathExists,
  resolveBundledRuntimeRoot,
} = require("./python-runtime");

const DEFAULT_HUD_URL = process.env.FRANCIS_HUD_URL || "http://127.0.0.1:8767";
const DEFAULT_BOOT_TIMEOUT_MS = 25000;
const DEFAULT_POLL_MS = 350;
const DEFAULT_MAX_POLL_MS = 1500;

function normalizeHudUrl(raw = DEFAULT_HUD_URL) {
  const url = new URL(String(raw || DEFAULT_HUD_URL));
  url.pathname = "/";
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/$/, "");
}

function buildHudHealthUrl(hudUrl) {
  return new URL("/health", `${normalizeHudUrl(hudUrl)}/`).toString();
}

function classifyHudReachabilityFailure(error = null, statusCode = 0) {
  if (Number.isFinite(Number(statusCode)) && Number(statusCode) >= 400) {
    return {
      kind: "non_200",
      message: `${Number(statusCode)}`,
      statusCode: Number(statusCode),
    };
  }
  const safeError = error instanceof Error ? error : new Error(String(error || "unknown failure"));
  const code = String(safeError?.cause?.code || safeError?.code || "").trim().toUpperCase();
  const message = String(safeError.message || safeError || "").trim();
  if (safeError.name === "AbortError" || code === "ABORT_ERR") {
    return {
      kind: "aborted",
      message: message || "Request aborted.",
      statusCode: 0,
    };
  }
  if (code === "ECONNREFUSED") {
    return {
      kind: "connection_refused",
      message: message || "Connection refused.",
      statusCode: 0,
    };
  }
  if (code === "ECONNRESET") {
    return {
      kind: "connection_reset",
      message: message || "Connection reset.",
      statusCode: 0,
    };
  }
  if (message.toLowerCase().includes("timed out")) {
    return {
      kind: "timeout",
      message,
      statusCode: 0,
    };
  }
  return {
    kind: "network_error",
    message: message || "Unknown network error.",
    statusCode: 0,
  };
}

function buildHudWorkspaceRoot({ sourceRoot, userDataPath, isPackaged }) {
  return isPackaged ? path.join(userDataPath, "workspace") : path.join(sourceRoot, "workspace");
}

function resolveHudSourceRoot({ appDir, resourcesPath, isPackaged }) {
  return isPackaged ? path.join(resourcesPath, "python-src") : path.resolve(appDir, "..");
}

function buildHudLaunchCandidates({
  sourceRoot,
  resourcesPath,
  hudUrl,
  env,
  userDataPath,
  isPackaged = false,
}) {
  const normalizedUrl = new URL(`${normalizeHudUrl(hudUrl)}/`);
  const host = normalizedUrl.hostname;
  const port = Number(normalizedUrl.port || (normalizedUrl.protocol === "https:" ? "443" : "80"));
  const bundledRuntimeRoot = resolveBundledRuntimeRoot({
    sourceRoot,
    resourcesPath,
    isPackaged,
  });
  const bundledPython = getBundledPythonExecutable(bundledRuntimeRoot);
  const pythonCandidates = [
    ...(isPackaged && pathExists(bundledPython)
      ? [
          {
            command: bundledPython,
            runtimeKind: "bundled",
            runtimePath: bundledPython,
            env: buildBundledRuntimeEnv({
              runtimeRoot: bundledRuntimeRoot,
              sourceRoot,
              env,
            }),
          },
        ]
      : []),
    ...(env.FRANCIS_HUD_PYTHONS || "")
      .split(path.delimiter)
      .map((value) => value.trim())
      .filter(Boolean),
    env.FRANCIS_HUD_PYTHON,
    path.join(sourceRoot, ".venv", "Scripts", "python.exe"),
    path.join(sourceRoot, ".venv", "bin", "python"),
    "python",
    "py",
  ]
    .filter(Boolean)
    .map((candidate) =>
      typeof candidate === "string"
        ? {
            command: candidate,
            runtimeKind: "external",
            runtimePath: candidate,
          }
        : candidate,
    );

  const seen = new Set();
  const deduped = pythonCandidates.filter((candidate) => {
    const key = String(candidate.command || "").toLowerCase();
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });

  const workspaceRoot = buildHudWorkspaceRoot({
    sourceRoot,
    userDataPath,
    isPackaged,
  });
  const sharedEnv = {
    ...env,
    FRANCIS_HUD_URL: normalizeHudUrl(hudUrl),
    FRANCIS_WORKSPACE_ROOT: workspaceRoot,
    PYTHONNOUSERSITE: "1",
    PYTHONUNBUFFERED: "1",
  };

  return deduped.map((candidate) => ({
    command: candidate.command,
    args: [
      "-m",
      "services.hud.app.run_hud",
      "--host",
      host,
      "--port",
      String(port),
    ],
    cwd: sourceRoot,
    env: candidate.env || {
      ...sharedEnv,
      PYTHONPATH: appendEnvPath(env.PYTHONPATH, sourceRoot),
    },
    runtimeKind: candidate.runtimeKind || "external",
    runtimePath: candidate.runtimePath || candidate.command,
  }));
}

function appendEnvPath(existingValue, nextValue) {
  const normalizedNext = String(nextValue || "").trim();
  if (!normalizedNext) {
    return existingValue || "";
  }
  return existingValue ? `${normalizedNext}${path.delimiter}${existingValue}` : normalizedNext;
}

async function probeHudReachability(hudUrl, timeoutMs = 1500) {
  const startedAtMs = Date.now();
  try {
    const target = new URL(buildHudHealthUrl(hudUrl));
    const transport = target.protocol === "https:" ? https : http;
    const statusCode = await new Promise((resolve, reject) => {
      const request = transport.request(target, {
        method: "GET",
        headers: {
          accept: "application/json",
        },
      }, (response) => {
        response.resume();
        response.once("end", () => resolve(Number(response.statusCode || 0)));
      });
      request.setTimeout(timeoutMs, () => {
        request.destroy(new Error(`Request timed out after ${timeoutMs}ms`));
      });
      request.once("error", reject);
      request.end();
    });
    const ok = statusCode >= 200 && statusCode < 300;
    return {
      ok,
      statusCode,
      elapsedMs: Date.now() - startedAtMs,
      error: ok ? null : classifyHudReachabilityFailure(null, statusCode),
    };
  } catch (error) {
    return {
      ok: false,
      statusCode: 0,
      elapsedMs: Date.now() - startedAtMs,
      error: classifyHudReachabilityFailure(error, 0),
    };
  }
}

async function isHudReachable(hudUrl, timeoutMs = 1500) {
  const probe = await probeHudReachability(hudUrl, timeoutMs);
  return Boolean(probe.ok);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getHudProbeDelayMs(attempt, {
  baseMs = DEFAULT_POLL_MS,
  maxMs = DEFAULT_MAX_POLL_MS,
} = {}) {
  const safeAttempt = Math.max(0, Number(attempt || 0));
  const safeBase = Math.max(100, Number(baseMs || DEFAULT_POLL_MS));
  const safeMax = Math.max(safeBase, Number(maxMs || DEFAULT_MAX_POLL_MS));
  return Math.min(safeMax, safeBase * Math.max(1, 2 ** Math.min(safeAttempt, 3)));
}

async function waitForHudReady(hudUrl, child, { timeoutMs = DEFAULT_BOOT_TIMEOUT_MS, pollMs = DEFAULT_POLL_MS } = {}) {
  const deadline = Date.now() + timeoutMs;
  let attempts = 0;

  while (Date.now() < deadline) {
    const probe = await probeHudReachability(hudUrl, Math.min(1200, pollMs * 3));
    if (probe.ok) {
      return true;
    }

    if (child && child.exitCode !== null) {
      throw new Error(`Managed HUD process exited with code ${child.exitCode}`);
    }

    await sleep(getHudProbeDelayMs(attempts, { baseMs: pollMs }));
    attempts += 1;
  }

  throw new Error(`Managed HUD did not become healthy within ${timeoutMs}ms`);
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
    lastError:
      code === 0 && !unexpected
        ? safeState.lastError
        : `Managed HUD exited with code ${code}${signal ? ` signal ${signal}` : ""}`,
    lastExitCode: code,
    lastExitSignal: signal,
    crashCount: unexpected ? intOrZero(safeState.crashCount) + 1 : intOrZero(safeState.crashCount),
    restartSuggested: unexpected,
  };
}

async function resolveManagedHudExitUpdate({
  previousState,
  code,
  signal,
  shutdownRequested,
  hudUrl,
  timeoutMs = 2000,
}) {
  const safeState = previousState && typeof previousState === "object" ? previousState : {};
  const unexpectedManagedExit = !shutdownRequested && safeState.mode === "managed";
  if (unexpectedManagedExit && await isHudReachable(hudUrl, timeoutMs)) {
    return {
      ...safeState,
      ready: true,
      mode: "external",
      managed: false,
      pid: null,
      lastError: null,
      lastExitCode: code,
      lastExitSignal: signal,
      restartSuggested: false,
    };
  }
  return buildManagedExitUpdate({
    previousState: safeState,
    code,
    signal,
    shutdownRequested,
  });
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

function createHudRuntimeManager({
  appDir,
  resourcesPath,
  userDataPath,
  isPackaged,
  hudUrl = DEFAULT_HUD_URL,
  env = process.env,
  log = () => {},
  onStateChanged = () => {},
} = {}) {
  const normalizedHudUrl = normalizeHudUrl(hudUrl);
  const sourceRoot = resolveHudSourceRoot({ appDir, resourcesPath, isPackaged });
  const bundledRuntimeRoot = resolveBundledRuntimeRoot({
    sourceRoot,
    resourcesPath,
    isPackaged,
  });
  const bundledRuntimePath = getBundledPythonExecutable(bundledRuntimeRoot);
  const bundledRuntimeAvailable = isPackaged && pathExists(bundledRuntimePath);
  const allowManagedStart = !["0", "false", "no"].includes(String(env.FRANCIS_OVERLAY_MANAGE_HUD || "1").toLowerCase());
  const state = {
    ready: false,
    mode: "idle",
    managed: false,
    attemptedAutoStart: false,
    healthUrl: buildHudHealthUrl(normalizedHudUrl),
    hudUrl: normalizedHudUrl,
    sourceRoot,
    workspaceRoot: buildHudWorkspaceRoot({ sourceRoot, userDataPath, isPackaged }),
    bundledRuntimeAvailable,
    bundledRuntimePath: bundledRuntimeAvailable ? bundledRuntimePath : null,
    launcher: null,
    runtimeKind: null,
    runtimePath: null,
    pid: null,
    lastError: null,
    lastExitCode: null,
    lastExitSignal: null,
    crashCount: 0,
    restartSuggested: false,
    generation: 0,
    previousPid: null,
    childAlive: false,
    launchInFlight: false,
    lastStartedAtMs: 0,
    lastReadyAtMs: 0,
    lastExitedAtMs: 0,
  };

  let child = null;
  let shutdownRequested = false;
  let ensureReadyPromise = null;
  let restartPromise = null;

  function setState(next) {
    Object.assign(state, next);
    onStateChanged(getPublicState());
  }

  function attachManagedLogs(processRef) {
    if (!processRef?.stdout || !processRef?.stderr) {
      return;
    }
    processRef.stdout.on("data", (chunk) => {
      log(`HUD stdout: ${String(chunk).trimEnd()}`);
    });
    processRef.stderr.on("data", (chunk) => {
      log(`HUD stderr: ${String(chunk).trimEnd()}`);
    });
    processRef.on("exit", (code, signal) => {
      const exitedManaged = child && processRef.pid === child.pid;
      if (!exitedManaged) {
        return;
      }
      child = null;
      setState({
        childAlive: false,
        previousPid: processRef.pid || state.previousPid || null,
        lastExitedAtMs: Date.now(),
      });
      void resolveManagedHudExitUpdate({
          previousState: state,
          code,
          signal,
          shutdownRequested,
          hudUrl: normalizedHudUrl,
        }).then((nextState) => {
          setState(nextState);
          shutdownRequested = false;
        });
    });
  }

  async function ensureReady() {
    if (ensureReadyPromise) {
      return ensureReadyPromise;
    }
    ensureReadyPromise = (async () => {
    if (await isHudReachable(normalizedHudUrl)) {
      setState({
        ready: true,
        mode: "external",
        managed: false,
        attemptedAutoStart: false,
        launcher: null,
        runtimeKind: null,
        runtimePath: null,
        pid: null,
        lastError: null,
        lastExitCode: null,
        lastExitSignal: null,
        restartSuggested: false,
        childAlive: false,
        launchInFlight: false,
        lastReadyAtMs: Date.now(),
      });
      return getPublicState();
    }

    if (!allowManagedStart) {
      const message = "Managed HUD startup is disabled by FRANCIS_OVERLAY_MANAGE_HUD";
      setState({
        ready: false,
        mode: "disabled",
        managed: false,
        attemptedAutoStart: false,
        runtimeKind: null,
        runtimePath: null,
        lastError: message,
        restartSuggested: false,
      });
      throw new Error(message);
    }

    const candidates = buildHudLaunchCandidates({
      sourceRoot,
      resourcesPath,
      hudUrl: normalizedHudUrl,
      env,
      userDataPath,
      isPackaged,
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
        lastError: null,
        lastExitCode: null,
        lastExitSignal: null,
        restartSuggested: false,
        launchInFlight: true,
        lastStartedAtMs: Date.now(),
      });
      log(`Starting managed HUD: ${describeLaunchCandidate(candidate)}`);

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
        log(`Managed HUD launch failed: ${error instanceof Error ? error.message : String(error)}`);
        continue;
      }

      attachManagedLogs(child);
      setState({
        generation: Number(state.generation || 0) + 1,
        previousPid: state.pid || state.previousPid || null,
        pid: child.pid,
        childAlive: true,
      });

      try {
        await waitForHudReady(normalizedHudUrl, child);
        setState({
          ready: true,
          mode: "managed",
          managed: true,
          runtimeKind: candidate.runtimeKind || null,
          runtimePath: candidate.runtimePath || null,
          pid: child.pid,
          lastError: null,
          lastExitCode: null,
          lastExitSignal: null,
          restartSuggested: false,
          childAlive: true,
          launchInFlight: false,
          lastReadyAtMs: Date.now(),
        });
        return getPublicState();
      } catch (error) {
        lastError = error;
        log(`Managed HUD did not become ready: ${error instanceof Error ? error.message : String(error)}`);
        await terminateProcessTree(child, { force: true });
        child = null;
        setState({
          childAlive: false,
          launchInFlight: false,
          lastExitedAtMs: Date.now(),
        });
      }
    }

    const message = lastError instanceof Error ? lastError.message : "Managed HUD startup failed";
    setState({
      ready: false,
      mode: "error",
      managed: false,
      runtimeKind: null,
      runtimePath: null,
      pid: null,
      lastError: message,
      restartSuggested: false,
      childAlive: false,
      launchInFlight: false,
    });
    throw new Error(message);
    })();
    try {
      return await ensureReadyPromise;
    } finally {
      ensureReadyPromise = null;
    }
  }

  async function restart() {
    if (restartPromise) {
      return restartPromise;
    }
    restartPromise = (async () => {
      await shutdown({ force: true });
      return ensureReady();
    })();
    try {
      return await restartPromise;
    } finally {
      restartPromise = null;
    }
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
      restartSuggested: false,
      childAlive: false,
      launchInFlight: false,
      lastExitedAtMs: Date.now(),
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
  DEFAULT_HUD_URL,
  DEFAULT_POLL_MS,
  appendEnvPath,
  buildManagedExitUpdate,
  buildHudHealthUrl,
  buildHudLaunchCandidates,
  buildHudWorkspaceRoot,
  classifyHudReachabilityFailure,
  createHudRuntimeManager,
  isHudReachable,
  normalizeHudUrl,
  probeHudReachability,
  resolveManagedHudExitUpdate,
  resolveHudSourceRoot,
  waitForHudReady,
  getHudProbeDelayMs,
};
