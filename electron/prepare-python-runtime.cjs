const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const {
  buildBundledRuntimeEnv,
  getBundledPythonExecutable,
  getVenvSitePackages,
  pathExists,
  resolvePythonHome,
  resolveStagedRuntimeRoot,
  shouldExcludeSitePackageEntry,
  shouldExcludeStdlibPath,
} = require("./python-runtime");

const RUNTIME_ROOT_FILES = [
  "LICENSE.txt",
  "python.exe",
  "pythonw.exe",
  "python3.dll",
  "python313.dll",
  "vcruntime140.dll",
  "vcruntime140_1.dll",
];

function log(message, extra) {
  if (extra === undefined) {
    console.log(`[francis-overlay] ${message}`);
    return;
  }
  console.log(`[francis-overlay] ${message}`, extra);
}

function ensureExists(targetPath, label) {
  if (!pathExists(targetPath)) {
    throw new Error(`${label} was not found at ${targetPath}`);
  }
}

function copyFileIfPresent(sourceRoot, targetRoot, fileName) {
  const sourcePath = path.join(sourceRoot, fileName);
  if (!pathExists(sourcePath)) {
    return false;
  }
  fs.copyFileSync(sourcePath, path.join(targetRoot, fileName));
  return true;
}

function copyDirectoryFiltered(sourcePath, targetPath, shouldExclude) {
  fs.cpSync(sourcePath, targetPath, {
    recursive: true,
    force: true,
    filter: (entryPath) => {
      const relative = path.relative(sourcePath, entryPath);
      if (!relative) {
        return true;
      }
      return !shouldExclude(relative);
    },
  });
}

function copyRuntimeRootFiles(pythonHome, runtimeRoot) {
  for (const fileName of RUNTIME_ROOT_FILES) {
    const copied = copyFileIfPresent(pythonHome, runtimeRoot, fileName);
    if (!copied && fileName !== "LICENSE.txt") {
      throw new Error(`Required Python runtime file is missing: ${fileName}`);
    }
  }
}

function copyStdlib(pythonHome, runtimeRoot) {
  const sourceLib = path.join(pythonHome, "Lib");
  ensureExists(sourceLib, "Python Lib directory");
  copyDirectoryFiltered(sourceLib, path.join(runtimeRoot, "Lib"), shouldExcludeStdlibPath);
}

function copyDlls(pythonHome, runtimeRoot) {
  const sourceDlls = path.join(pythonHome, "DLLs");
  if (!pathExists(sourceDlls)) {
    return;
  }
  copyDirectoryFiltered(sourceDlls, path.join(runtimeRoot, "DLLs"), shouldExcludeStdlibPath);
}

function copySitePackages(venvSitePackages, runtimeRoot) {
  ensureExists(venvSitePackages, "Virtualenv site-packages");
  const targetSitePackages = path.join(runtimeRoot, "Lib", "site-packages");
  fs.mkdirSync(targetSitePackages, { recursive: true });

  for (const entry of fs.readdirSync(venvSitePackages, { withFileTypes: true })) {
    if (shouldExcludeSitePackageEntry(entry.name)) {
      continue;
    }
    const sourcePath = path.join(venvSitePackages, entry.name);
    const targetPath = path.join(targetSitePackages, entry.name);
    fs.cpSync(sourcePath, targetPath, { recursive: true, force: true });
  }
}

function verifyBundledRuntime(runtimeRoot, sourceRoot) {
  const pythonExecutable = getBundledPythonExecutable(runtimeRoot);
  ensureExists(pythonExecutable, "Bundled python executable");

  const verification = spawnSync(
    pythonExecutable,
    [
      "-c",
      [
        "import fastapi, uvicorn",
        "from uvicorn.importer import import_from_string",
        "import_from_string('services.hud.app.main:app')",
        "print('runtime ok')",
      ].join("; "),
    ],
    {
      cwd: sourceRoot,
      env: buildBundledRuntimeEnv({ runtimeRoot, sourceRoot }),
      encoding: "utf8",
      windowsHide: true,
    },
  );

  if (verification.status !== 0) {
    throw new Error(
      [
        "Bundled runtime smoke test failed.",
        verification.stdout?.trim(),
        verification.stderr?.trim(),
      ]
        .filter(Boolean)
        .join("\n"),
    );
  }

  log(verification.stdout.trim());
}

function main() {
  const sourceRoot = path.resolve(__dirname, "..");
  const runtimeRoot = resolveStagedRuntimeRoot(sourceRoot);
  const pythonHome = resolvePythonHome({ sourceRoot, env: process.env });
  const venvSitePackages = getVenvSitePackages(sourceRoot);

  if (!pythonHome) {
    throw new Error(
      "Unable to resolve the base Python home. Set FRANCIS_OVERLAY_PYTHON_HOME or ensure .venv/pyvenv.cfg exists.",
    );
  }
  if (!venvSitePackages) {
    throw new Error("Unable to resolve the Francis virtualenv site-packages directory.");
  }

  log("Preparing bundled Python runtime", {
    pythonHome,
    venvSitePackages,
    runtimeRoot,
  });

  fs.rmSync(runtimeRoot, { recursive: true, force: true });
  fs.mkdirSync(runtimeRoot, { recursive: true });

  copyRuntimeRootFiles(pythonHome, runtimeRoot);
  copyStdlib(pythonHome, runtimeRoot);
  copyDlls(pythonHome, runtimeRoot);
  copySitePackages(venvSitePackages, runtimeRoot);
  verifyBundledRuntime(runtimeRoot, sourceRoot);

  log("Bundled Python runtime is ready", {
    runtimeRoot,
    pythonExecutable: getBundledPythonExecutable(runtimeRoot),
  });
}

try {
  main();
} catch (error) {
  console.error(
    `[francis-overlay] Failed to prepare bundled Python runtime: ${
      error instanceof Error ? error.stack || error.message : String(error)
    }`,
  );
  process.exit(1);
}
