const path = require("node:path");
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

async function isHudReachable(hudUrl, timeoutMs = 1500) {
  try {
    const response = await fetch(buildHudHealthUrl(hudUrl), {
      signal: AbortSignal.timeout(timeoutMs),
      headers: {
        accept: "application/json",
      },
    });
    return response.ok;
  } catch {
    return false;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForHudReady(hudUrl, child, { timeoutMs = DEFAULT_BOOT_TIMEOUT_MS, pollMs = DEFAULT_POLL_MS } = {}) {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    if (await isHudReachable(hudUrl, Math.min(1200, pollMs * 3))) {
      return true;
    }

    if (child && child.exitCode !== null) {
      throw new Error(`Managed HUD process exited with code ${child.exitCode}`);
    }

    await sleep(pollMs);
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
      setState({ pid: child.pid });

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
        });
        return getPublicState();
      } catch (error) {
        lastError = error;
        log(`Managed HUD did not become ready: ${error instanceof Error ? error.message : String(error)}`);
        await terminateProcessTree(child, { force: true });
        child = null;
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
  DEFAULT_HUD_URL,
  DEFAULT_POLL_MS,
  appendEnvPath,
  buildManagedExitUpdate,
  buildHudHealthUrl,
  buildHudLaunchCandidates,
  buildHudWorkspaceRoot,
  createHudRuntimeManager,
  isHudReachable,
  normalizeHudUrl,
  resolveHudSourceRoot,
  waitForHudReady,
};
