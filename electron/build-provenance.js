const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const { resolveBuildIdentity } = require("./build-info");
const { pathExists, resolveStagedRuntimeRoot } = require("./python-runtime");

const GENERATED_PROVENANCE_DIR = path.join("electron", "generated");
const GENERATED_PROVENANCE_FILE = "build-provenance.json";

function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

function safeStat(targetPath) {
  try {
    return fs.statSync(targetPath);
  } catch {
    return null;
  }
}

function describeFile(targetPath) {
  const stat = safeStat(targetPath);
  if (!stat || !stat.isFile()) {
    return {
      path: targetPath,
      exists: false,
      sizeBytes: 0,
      sha256: null,
    };
  }
  return {
    path: targetPath,
    exists: true,
    sizeBytes: stat.size,
    sha256: sha256File(targetPath),
  };
}

function countEntries(rootPath) {
  try {
    return fs.readdirSync(rootPath, { recursive: true }).length;
  } catch {
    return 0;
  }
}

function resolveGeneratedProvenancePath(sourceRoot) {
  return path.join(sourceRoot, GENERATED_PROVENANCE_DIR, GENERATED_PROVENANCE_FILE);
}

function normalizeBuildTargets(buildConfig = {}) {
  const targets = Array.isArray(buildConfig?.win?.target) ? buildConfig.win.target : [];
  const normalized = [];
  for (const entry of targets) {
    if (typeof entry === "string") {
      normalized.push(entry);
      continue;
    }
    if (entry && typeof entry === "object" && typeof entry.target === "string") {
      normalized.push(entry.target);
    }
  }
  return [...new Set(normalized)];
}

function buildProvenanceManifest({
  sourceRoot,
  buildIdentity,
  packageJson,
  packageJsonPath,
  packageLockPath,
  pyprojectPath,
  runtimeRoot,
  generatedAt = new Date().toISOString(),
} = {}) {
  const buildTargets = normalizeBuildTargets(packageJson?.build || {});
  const runtimeStat = runtimeRoot ? safeStat(runtimeRoot) : null;
  const packageVersion = packageJson?.version || "unknown";
  const runtimeEntryCount = runtimeStat && runtimeStat.isDirectory() ? countEntries(runtimeRoot) : 0;
  const targetsSummary = buildTargets.length ? buildTargets.join(", ") : "source-only";

  return {
    version: 1,
    generatedAt,
    summary: `Build ${buildIdentity} | targets ${targetsSummary} | runtime entries ${runtimeEntryCount}`,
    buildIdentity,
    packageVersion,
    productName: packageJson?.build?.productName || packageJson?.name || "Francis Overlay",
    appId: packageJson?.build?.appId || null,
    targets: buildTargets,
    packageManager: {
      electron: packageJson?.devDependencies?.electron || null,
      electronBuilder: packageJson?.devDependencies?.["electron-builder"] || null,
    },
    inputs: {
      packageJson: describeFile(packageJsonPath),
      packageLock: describeFile(packageLockPath),
      pyproject: describeFile(pyprojectPath),
    },
    runtime: {
      root: runtimeRoot,
      exists: Boolean(runtimeStat),
      entryCount: runtimeEntryCount,
      pythonExecutable: runtimeRoot ? path.join(runtimeRoot, "python.exe") : null,
      pythonExecutableExists: runtimeRoot ? pathExists(path.join(runtimeRoot, "python.exe")) : false,
    },
    sourceRoot,
  };
}

function loadGeneratedProvenance(sourceRoot) {
  const filePath = resolveGeneratedProvenancePath(sourceRoot);
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function writeGeneratedProvenance(sourceRoot, manifest) {
  const filePath = resolveGeneratedProvenancePath(sourceRoot);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(manifest, null, 2), "utf8");
  return filePath;
}

function buildRuntimeProvenance({ appLike, appDir, runtimeRoot = null } = {}) {
  const sourceRoot = path.resolve(appDir, "..");
  const packageJsonPath = path.join(sourceRoot, "package.json");
  const packageLockPath = path.join(sourceRoot, "package-lock.json");
  const pyprojectPath = path.join(sourceRoot, "pyproject.toml");
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
  const resolvedRuntimeRoot = runtimeRoot || resolveStagedRuntimeRoot(sourceRoot);
  const buildIdentity = resolveBuildIdentity(appLike, appDir).identity;
  return buildProvenanceManifest({
    sourceRoot,
    buildIdentity,
    packageJson,
    packageJsonPath,
    packageLockPath,
    pyprojectPath,
    runtimeRoot: resolvedRuntimeRoot,
  });
}

module.exports = {
  GENERATED_PROVENANCE_DIR,
  GENERATED_PROVENANCE_FILE,
  buildProvenanceManifest,
  buildRuntimeProvenance,
  loadGeneratedProvenance,
  normalizeBuildTargets,
  resolveGeneratedProvenancePath,
  writeGeneratedProvenance,
};
