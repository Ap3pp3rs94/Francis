const fs = require("node:fs");
const path = require("node:path");

const STAGED_RUNTIME_DIR = path.join("dist", "python-runtime-staging");
const PACKAGED_RUNTIME_DIR = "python-runtime";
const WINDOWS_PYTHON_EXECUTABLE = "python.exe";

function pathExists(targetPath) {
  try {
    fs.accessSync(targetPath);
    return true;
  } catch {
    return false;
  }
}

function resolveStagedRuntimeRoot(sourceRoot) {
  return path.join(sourceRoot, STAGED_RUNTIME_DIR);
}

function resolveBundledRuntimeRoot({ sourceRoot, resourcesPath, isPackaged }) {
  return isPackaged
    ? path.join(resourcesPath, PACKAGED_RUNTIME_DIR)
    : resolveStagedRuntimeRoot(sourceRoot);
}

function getBundledPythonExecutable(runtimeRoot) {
  return path.join(runtimeRoot, WINDOWS_PYTHON_EXECUTABLE);
}

function resolvePythonHome({ sourceRoot, env = process.env }) {
  const explicitHome = String(env.FRANCIS_OVERLAY_PYTHON_HOME || "").trim();
  if (explicitHome) {
    return path.resolve(explicitHome);
  }

  const pyvenvPath = path.join(sourceRoot, ".venv", "pyvenv.cfg");
  if (!pathExists(pyvenvPath)) {
    return null;
  }

  const contents = fs.readFileSync(pyvenvPath, "utf8");
  const match = contents.match(/^home\s*=\s*(.+)$/im);
  return match ? path.resolve(match[1].trim()) : null;
}

function getVenvSitePackages(sourceRoot) {
  const windowsPath = path.join(sourceRoot, ".venv", "Lib", "site-packages");
  if (pathExists(windowsPath)) {
    return windowsPath;
  }

  const libRoot = path.join(sourceRoot, ".venv", "lib");
  if (!pathExists(libRoot)) {
    return null;
  }

  for (const entry of fs.readdirSync(libRoot, { withFileTypes: true })) {
    if (!entry.isDirectory()) {
      continue;
    }
    const candidate = path.join(libRoot, entry.name, "site-packages");
    if (pathExists(candidate)) {
      return candidate;
    }
  }

  return null;
}

function shouldExcludeStdlibPath(relativePath) {
  const normalized = String(relativePath || "")
    .replace(/\\/g, "/")
    .replace(/^\/+/, "")
    .toLowerCase();

  if (!normalized) {
    return false;
  }

  if (normalized === "site-packages" || normalized.startsWith("site-packages/")) {
    return true;
  }

  if (
    normalized === "__pycache__" ||
    normalized.endsWith("/__pycache__") ||
    normalized.includes("/__pycache__/")
  ) {
    return true;
  }

  return [
    "ensurepip",
    "idlelib",
    "test",
    "tests",
    "tkinter",
    "turtledemo",
    "venv",
  ].some((segment) => normalized === segment || normalized.startsWith(`${segment}/`));
}

function shouldExcludeSitePackageEntry(name) {
  const normalized = String(name || "").trim().toLowerCase();
  return (
    !normalized ||
    normalized === "__pycache__" ||
    normalized.startsWith("__editable__") ||
    normalized === "pip" ||
    normalized === "setuptools" ||
    normalized === "wheel" ||
    /^pip-[\w.+-]+\.dist-info$/.test(normalized) ||
    /^setuptools-[\w.+-]+\.dist-info$/.test(normalized) ||
    /^wheel-[\w.+-]+\.dist-info$/.test(normalized) ||
    normalized.endsWith(".egg-link") ||
    normalized.endsWith(".pyc")
  );
}

function prependPathEntry(existingValue, nextValue) {
  const normalizedNext = String(nextValue || "").trim();
  if (!normalizedNext) {
    return existingValue || "";
  }
  return existingValue ? `${normalizedNext}${path.delimiter}${existingValue}` : normalizedNext;
}

function buildBundledRuntimeEnv({ runtimeRoot, sourceRoot, env = process.env }) {
  const dllPath = path.join(runtimeRoot, "DLLs");
  return {
    ...env,
    PATH: prependPathEntry(prependPathEntry(env.PATH, dllPath), runtimeRoot),
    PYTHONHOME: runtimeRoot,
    PYTHONNOUSERSITE: "1",
    PYTHONPATH: prependPathEntry(env.PYTHONPATH, sourceRoot),
    PYTHONUNBUFFERED: "1",
  };
}

module.exports = {
  PACKAGED_RUNTIME_DIR,
  STAGED_RUNTIME_DIR,
  buildBundledRuntimeEnv,
  getBundledPythonExecutable,
  getVenvSitePackages,
  pathExists,
  prependPathEntry,
  resolveBundledRuntimeRoot,
  resolvePythonHome,
  resolveStagedRuntimeRoot,
  shouldExcludeSitePackageEntry,
  shouldExcludeStdlibPath,
};
