const path = require("node:path");

const {
  buildArtifactSigningReport,
  resolveOverlayArtifactPaths,
  validateSigningReport,
  writeGeneratedSigningReport,
} = require("./signature-state");
const { normalizeConfiguredEnvValue } = require("./signing-env");

function main() {
  const sourceRoot = path.resolve(__dirname, "..");
  const requireSigned =
    process.argv.includes("--require-signed") ||
    /^(1|true|yes|on)$/i.test(String(process.env.FRANCIS_REQUIRE_SIGNED_OVERLAY || ""));
  const requirePublisherEnv = process.argv.includes("--require-publisher-env");
  const requireChainHintEnv = process.argv.includes("--require-chain-hint-env");
  const explicitPublisherNameArg = process.argv.find((entry) => entry.startsWith("--require-publisher-name="));
  const explicitChainHintArg = process.argv.find((entry) => entry.startsWith("--require-chain-hint="));
  const requirePublisherName = requirePublisherEnv
    ? normalizeConfiguredEnvValue(process.env.FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME)
    : explicitPublisherNameArg
      ? normalizeConfiguredEnvValue(explicitPublisherNameArg.slice("--require-publisher-name=".length))
      : "";
  const requireChainHint = requireChainHintEnv
    ? normalizeConfiguredEnvValue(process.env.FRANCIS_WINDOWS_SIGNING_CHAIN_HINT)
    : explicitChainHintArg
      ? normalizeConfiguredEnvValue(explicitChainHintArg.slice("--require-chain-hint=".length))
      : "";
  const rejectSelfIssued =
    process.argv.includes("--reject-self-issued") ||
    /^(1|true|yes|on)$/i.test(String(process.env.FRANCIS_REQUIRE_PUBLIC_TRUST_OVERLAY || ""));

  if (requirePublisherEnv && !requirePublisherName) {
    console.error(
      "[francis-overlay] Signing verification failed: FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME is required for publisher-gated verification.",
    );
    process.exit(1);
  }

  if (requireChainHintEnv && !requireChainHint) {
    console.error(
      "[francis-overlay] Signing verification failed: FRANCIS_WINDOWS_SIGNING_CHAIN_HINT is required for public chain-gated verification.",
    );
    process.exit(1);
  }

  const artifactPaths = resolveOverlayArtifactPaths(sourceRoot);
  const report = buildArtifactSigningReport({ artifactPaths });
  const reportPath = writeGeneratedSigningReport(sourceRoot, report);
  const validation = validateSigningReport(report, {
    requireSigned,
    requirePublisherName,
    requireChainHint,
    rejectSelfIssued,
  });

  console.log(
    JSON.stringify(
      {
        summary: report.summary,
        reportPath,
        requireSigned,
        requirePublisherName,
        requireChainHint,
        rejectSelfIssued,
        counts: report.counts,
        artifacts: report.artifacts.map((artifact) => ({
          path: artifact.path,
          state: artifact.state,
          status: artifact.status,
          subject: artifact.subject,
          issuer: artifact.issuer,
          rootSubject: artifact.rootSubject,
          rootIssuer: artifact.rootIssuer,
          chainSubjects: artifact.chainSubjects,
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
        .map((entry) => `${path.basename(entry.path)}=${entry.reason || entry.state}`)
        .join(", ")}`,
    );
    process.exit(1);
  }
}

main();
