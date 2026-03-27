const path = require("node:path");

const {
  buildArtifactSigningReport,
  resolveOverlayArtifactPaths,
  validateSigningReport,
  writeGeneratedSigningReport,
} = require("./signature-state");

function main() {
  const sourceRoot = path.resolve(__dirname, "..");
  const requireSigned =
    process.argv.includes("--require-signed") ||
    /^(1|true|yes|on)$/i.test(String(process.env.FRANCIS_REQUIRE_SIGNED_OVERLAY || ""));

  const artifactPaths = resolveOverlayArtifactPaths(sourceRoot);
  const report = buildArtifactSigningReport({ artifactPaths });
  const reportPath = writeGeneratedSigningReport(sourceRoot, report);
  const validation = validateSigningReport(report, { requireSigned });

  console.log(
    JSON.stringify(
      {
        summary: report.summary,
        reportPath,
        requireSigned,
        counts: report.counts,
        artifacts: report.artifacts.map((artifact) => ({
          path: artifact.path,
          state: artifact.state,
          status: artifact.status,
          summary: artifact.summary,
        })),
      },
      null,
      2,
    ),
  );

  if (!validation.ok) {
    console.error(
      `[francis-overlay] Signing verification failed: ${validation.failures
        .map((entry) => `${path.basename(entry.path)}=${entry.state}`)
        .join(", ")}`,
    );
    process.exit(1);
  }
}

main();
