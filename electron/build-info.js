const path = require("node:path");
const { execFileSync } = require("node:child_process");

function buildIdentity({ version, packaged, revision = null }) {
  const safeVersion = typeof version === "string" && version.trim() ? version.trim() : "unknown";
  const safeRevision = typeof revision === "string" && revision.trim() ? revision.trim() : null;
  const distribution = packaged ? "portable" : "source";

  return {
    packaged: Boolean(packaged),
    distribution,
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
  return buildIdentity({ version, packaged, revision });
}

module.exports = {
  buildIdentity,
  readGitRevision,
  resolveBuildIdentity,
};
