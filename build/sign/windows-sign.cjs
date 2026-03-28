const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

const {
  resolveWindowsSigningConfig,
  validateWindowsSigningConfig,
} = require("./windows-sign.config.cjs");

let summaryState = null;
let exitHookRegistered = false;

function formatTargetPath(filePath) {
  try {
    return path.relative(path.resolve(__dirname, "..", ".."), filePath) || filePath;
  } catch {
    return filePath;
  }
}

function createSummaryState(config, metadata) {
  return {
    version: 1,
    generatedAt: new Date().toISOString(),
    toolPaths: {
      signtool: config.signToolPath,
      dlib: config.dlibPath,
      metadata: config.metadataPath,
    },
    timestampUrl: config.timestampUrl,
    metadata: metadata
      ? {
          endpoint: metadata.Endpoint || "",
          codeSigningAccountName: metadata.CodeSigningAccountName || "",
          certificateProfileName: metadata.CertificateProfileName || "",
        }
      : null,
    signed: [],
    skipped: [],
    failed: [],
  };
}

function writeSummary(summary, summaryPath) {
  fs.mkdirSync(path.dirname(summaryPath), { recursive: true });
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf8");
}

function ensureSummary(config, metadata) {
  if (!summaryState) {
    summaryState = createSummaryState(config, metadata);
    writeSummary(summaryState, config.summaryPath);
  }

  if (!exitHookRegistered) {
    process.once("exit", () => {
      if (!summaryState) {
        return;
      }
      console.log(formatWindowsSigningSummary(summaryState));
    });
    exitHookRegistered = true;
  }

  return summaryState;
}

function formatWindowsSigningSummary(summary) {
  return [
    "[francis-overlay] Windows signing summary",
    `  signed: ${summary.signed.length}`,
    `  skipped: ${summary.skipped.length}`,
    `  failed: ${summary.failed.length}`,
    `  signtool: ${summary.toolPaths.signtool}`,
    `  dlib: ${summary.toolPaths.dlib}`,
    `  metadata: ${summary.toolPaths.metadata}`,
    `  timestamp: ${summary.timestampUrl}`,
  ].join("\n");
}

function recordSummaryEntry(kind, entry, summaryPath) {
  summaryState[kind].push(entry);
  writeSummary(summaryState, summaryPath);
}

function buildSignToolArgs({ targetPath, config, isNest = false }) {
  const args = [
    "sign",
    "/v",
    "/debug",
    "/fd",
    "SHA256",
    "/td",
    "SHA256",
    "/tr",
    config.timestampUrl,
    "/dlib",
    config.dlibPath,
    "/dmdf",
    config.metadataPath,
  ];

  if (isNest) {
    args.push("/as");
  }

  args.push(targetPath);
  return args;
}

function runSigntool(signToolPath, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(signToolPath, args, {
      windowsHide: true,
      shell: false,
    });
    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      reject(error);
    });
    child.on("close", (code) => {
      resolve({
        code: code == null ? 1 : code,
        stdout,
        stderr,
      });
    });
  });
}

function dotnetHostIsAvailable() {
  const result = spawnSync("where.exe", ["dotnet"], {
    windowsHide: true,
    shell: false,
    encoding: "utf8",
  });
  return result.status === 0;
}

async function signWindows(configuration) {
  const config = resolveWindowsSigningConfig(process.env);
  const validation = validateWindowsSigningConfig(config);
  if (!validation.ok) {
    const details = validation.failures.map((entry) => `${entry.key}: ${entry.message}`).join("\n");
    throw new Error(`[francis-overlay] Windows signing env is not ready.\n${details}`);
  }

  const targetPath = path.resolve(String(configuration?.path || ""));
  if (!targetPath || !fs.existsSync(targetPath)) {
    throw new Error(`[francis-overlay] Electron Builder requested signing for a missing path: ${targetPath || "<empty>"}`);
  }

  const summary = ensureSummary(config, validation.metadata);
  const args = buildSignToolArgs({
    targetPath,
    config,
    isNest: Boolean(configuration?.isNest),
  });
  const relativeTargetPath = formatTargetPath(targetPath);

  console.log(`[francis-overlay] Windows sign hook target=${relativeTargetPath}`);
  console.log(`[francis-overlay] signtool=${config.signToolPath}`);
  console.log(`[francis-overlay] dlib=${config.dlibPath}`);
  console.log(`[francis-overlay] metadata=${config.metadataPath}`);
  console.log(`[francis-overlay] timestamp=${config.timestampUrl}`);

  const result = await runSigntool(config.signToolPath, args);
  if (result.stdout.trim()) {
    console.log(result.stdout.trim());
  }
  if (result.code !== 0) {
    if (result.stderr.trim()) {
      console.error(result.stderr.trim());
    }
    recordSummaryEntry(
      "failed",
      {
        path: targetPath,
        exitCode: result.code,
      },
      config.summaryPath,
    );
    throw new Error(
      `[francis-overlay] signtool exited with code ${result.code} while signing ${relativeTargetPath}.${dotnetHostIsAvailable() ? "" : " dotnet.exe is not available on PATH; Azure.CodeSigning.Dlib.dll requires the .NET 8 runtime host."}`,
    );
  }

  recordSummaryEntry(
    "signed",
    {
      path: targetPath,
      signedAt: new Date().toISOString(),
    },
    config.summaryPath,
  );
  return true;
}

function printSummaryFromDisk() {
  const config = resolveWindowsSigningConfig(process.env);
  if (!fs.existsSync(config.summaryPath)) {
    console.error(`[francis-overlay] No signing summary exists at ${config.summaryPath}.`);
    process.exit(1);
  }
  const summary = JSON.parse(fs.readFileSync(config.summaryPath, "utf8"));
  console.log(formatWindowsSigningSummary(summary));
}

module.exports = signWindows;
module.exports.default = signWindows;
module.exports.buildSignToolArgs = buildSignToolArgs;
module.exports.formatWindowsSigningSummary = formatWindowsSigningSummary;

if (require.main === module) {
  if (process.argv.includes("--print-summary")) {
    printSummaryFromDisk();
  } else {
    console.error("[francis-overlay] windows-sign.cjs is an Electron Builder sign hook. Use --print-summary to inspect the last summary.");
    process.exit(1);
  }
}
