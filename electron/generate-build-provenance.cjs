const fs = require("node:fs");
const path = require("node:path");

const { buildRuntimeProvenance, writeGeneratedProvenance } = require("./build-provenance");

function log(message, extra) {
  if (extra === undefined) {
    console.log(`[francis-overlay] ${message}`);
    return;
  }
  console.log(`[francis-overlay] ${message}`, extra);
}

function main() {
  const sourceRoot = path.resolve(__dirname, "..");
  const appLike = {
    isPackaged: false,
    getVersion() {
      const packageJsonPath = path.join(sourceRoot, "package.json");
      return JSON.parse(fs.readFileSync(packageJsonPath, "utf8")).version || "unknown";
    },
  };

  const manifest = buildRuntimeProvenance({
    appLike,
    appDir: __dirname,
  });
  const filePath = writeGeneratedProvenance(sourceRoot, manifest);
  log("Generated build provenance manifest", {
    filePath,
    buildIdentity: manifest.buildIdentity,
    targets: manifest.targets,
  });
}

try {
  main();
} catch (error) {
  console.error(
    `[francis-overlay] Failed to generate build provenance: ${
      error instanceof Error ? error.stack || error.message : String(error)
    }`,
  );
  process.exit(1);
}
