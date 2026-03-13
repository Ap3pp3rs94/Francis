const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

function resolvePackagedDistribution(execPath) {
  if (typeof execPath !== "string" || !execPath.trim()) {
    return "portable";
  }
  const installRoot = path.dirname(execPath);
  const uninstallPath = path.join(installRoot, "Uninstall Francis Overlay.exe");
  return fs.existsSync(uninstallPath) ? "installer" : "portable";
}

function buildIdentity({ version, packaged, revision = null, distribution = null }) {
  const safeVersion = typeof version === "string" && version.trim() ? version.trim() : "unknown";
  const safeRevision = typeof revision === "string" && revision.trim() ? revision.trim() : null;
  const safeDistribution = packaged
    ? (typeof distribution === "string" && distribution.trim() ? distribution.trim() : "portable")
    : "source";

  return {
    packaged: Boolean(packaged),
    distribution: safeDistribution,
    version: safeVersion,
    revision: safeRevision,
    identity: !packaged && safeRevision ? `${safeVersion}+${safeRevision}` : safeVersion,
  };
}

function readGitRevision(repoRoot) {
  try {
    return execFileSync("git", ["rev-parse", "--short", "HEAD"], {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

function resolveBuildIdentity(appLike, appDir) {
  const packaged = Boolean(appLike?.isPackaged);
  const version = typeof appLike?.getVersion === "function" ? appLike.getVersion() : "unknown";
  const repoRoot = path.resolve(appDir, "..");
  const revision = packaged ? null : readGitRevision(repoRoot);
  const distribution = packaged ? resolvePackagedDistribution(process.execPath) : "source";
  return buildIdentity({ version, packaged, revision, distribution });
}

module.exports = {
  buildIdentity,
  readGitRevision,
  resolveBuildIdentity,
  resolvePackagedDistribution,
};
