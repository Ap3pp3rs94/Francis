const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  STAGED_RUNTIME_DIR,
  buildBundledRuntimeEnv,
  getBundledPythonExecutable,
  getVenvSitePackages,
  resolveBundledRuntimeRoot,
  resolvePythonHome,
  resolveStagedRuntimeRoot,
  shouldExcludeSitePackageEntry,
  shouldExcludeStdlibPath,
} = require("./python-runtime");

function withTempDir(callback) {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-runtime-"));
  try {
    return callback(tempRoot);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
}

test("resolvePythonHome prefers explicit env and falls back to .venv pyvenv.cfg", () => {
  withTempDir((sourceRoot) => {
    const venvRoot = path.join(sourceRoot, ".venv");
    fs.mkdirSync(venvRoot, { recursive: true });
    fs.writeFileSync(path.join(venvRoot, "pyvenv.cfg"), "home = C:\\Python313\n", "utf8");

    assert.equal(
      resolvePythonHome({
        sourceRoot,
        env: { FRANCIS_OVERLAY_PYTHON_HOME: "D:/CustomPython" },
      }),
      path.resolve("D:/CustomPython"),
    );

    assert.equal(resolvePythonHome({ sourceRoot, env: {} }), path.resolve("C:\\Python313"));
  });
});

test("bundled runtime roots resolve to staging in dev and resources in packaged mode", () => {
  const sourceRoot = path.resolve("D:/francis");
  assert.equal(resolveStagedRuntimeRoot(sourceRoot), path.join(sourceRoot, STAGED_RUNTIME_DIR));
  assert.equal(
    resolveBundledRuntimeRoot({
      sourceRoot,
      resourcesPath: "C:/Francis/resources",
      isPackaged: true,
    }),
    path.join("C:/Francis/resources", "python-runtime"),
  );
  assert.equal(
    resolveBundledRuntimeRoot({
      sourceRoot,
      resourcesPath: "C:/ignored",
      isPackaged: false,
    }),
    path.join(sourceRoot, STAGED_RUNTIME_DIR),
  );
});

test("site package and stdlib exclusion helpers only drop packaging hazards", () => {
  assert.equal(shouldExcludeStdlibPath("site-packages/fastapi"), true);
  assert.equal(shouldExcludeStdlibPath("test/test_asyncio.py"), true);
  assert.equal(shouldExcludeStdlibPath("venv/scripts/nt/venvlauncher.exe"), true);
  assert.equal(shouldExcludeStdlibPath("asyncio/base_events.py"), false);
  assert.equal(shouldExcludeSitePackageEntry("__editable__.francis-0.1.0.pth"), true);
  assert.equal(shouldExcludeSitePackageEntry("__editable___francis_0_1_0_finder.py"), true);
  assert.equal(shouldExcludeSitePackageEntry("pip"), true);
  assert.equal(shouldExcludeSitePackageEntry("setuptools-75.8.0.dist-info"), true);
  assert.equal(shouldExcludeSitePackageEntry("fastapi"), false);
});

test("bundled runtime env pins PYTHONHOME and prepends runtime and source paths", () => {
  const runtimeRoot = "C:/Francis/python-runtime";
  const sourceRoot = "D:/francis";
  const env = buildBundledRuntimeEnv({
    runtimeRoot,
    sourceRoot,
    env: {
      PATH: "C:/Windows/System32",
      PYTHONPATH: "C:/existing",
    },
  });

  assert.equal(env.PYTHONHOME, runtimeRoot);
  assert.equal(env.PYTHONNOUSERSITE, "1");
  assert.ok(env.PYTHONPATH.startsWith(`${sourceRoot}${path.delimiter}`));
  assert.ok(env.PATH.startsWith(`${runtimeRoot}${path.delimiter}${path.join(runtimeRoot, "DLLs")}`));
});

test("venv site-packages and bundled python executable helpers resolve expected paths", () => {
  withTempDir((sourceRoot) => {
    const sitePackages = path.join(sourceRoot, ".venv", "Lib", "site-packages");
    fs.mkdirSync(sitePackages, { recursive: true });

    assert.equal(getVenvSitePackages(sourceRoot), sitePackages);
    assert.equal(
      getBundledPythonExecutable("C:/Francis/python-runtime"),
      path.join("C:/Francis/python-runtime", "python.exe"),
    );
  });
});
