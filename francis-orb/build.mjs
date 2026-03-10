import { build } from "esbuild";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const outputDir = path.resolve(rootDir, "../services/hud/app/static/orb");

await build({
  entryPoints: [path.resolve(rootDir, "index.ts")],
  outfile: path.resolve(outputDir, "francis-orb.js"),
  bundle: true,
  format: "iife",
  globalName: "FrancisOrb",
  platform: "browser",
  target: ["es2022"],
  sourcemap: false,
  minify: false,
  loader: {
    ".glsl": "text",
  },
  banner: {
    js: "/* Francis Orb bundle: generated from francis-orb/build.mjs */",
  },
});
