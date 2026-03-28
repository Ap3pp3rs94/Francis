const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildSignToolArgs,
  formatWindowsSigningSummary,
} = require("./windows-sign.cjs");

test("buildSignToolArgs emits the direct signtool Azure signing invocation", () => {
  const args = buildSignToolArgs({
    targetPath: "D:\\francis\\dist\\overlay\\win-unpacked\\Francis Overlay.exe",
    config: {
      dlibPath: "C:\\tools\\Azure.CodeSigning.Dlib.dll",
      metadataPath: "C:\\tools\\metadata.json",
      timestampUrl: "http://timestamp.acs.microsoft.com",
    },
  });

  assert.deepEqual(args, [
    "sign",
    "/v",
    "/debug",
    "/fd",
    "SHA256",
    "/td",
    "SHA256",
    "/tr",
    "http://timestamp.acs.microsoft.com",
    "/dlib",
    "C:\\tools\\Azure.CodeSigning.Dlib.dll",
    "/dmdf",
    "C:\\tools\\metadata.json",
    "D:\\francis\\dist\\overlay\\win-unpacked\\Francis Overlay.exe",
  ]);
});

test("formatWindowsSigningSummary reports signed totals and tool paths", () => {
  const summary = formatWindowsSigningSummary({
    signed: [{ path: "one.exe" }, { path: "two.exe" }],
    skipped: [],
    failed: [],
    toolPaths: {
      signtool: "C:\\tools\\signtool.exe",
      dlib: "C:\\tools\\Azure.CodeSigning.Dlib.dll",
      metadata: "C:\\tools\\metadata.json",
    },
    timestampUrl: "http://timestamp.acs.microsoft.com",
  });

  assert.match(summary, /signed: 2/);
  assert.match(summary, /failed: 0/);
  assert.match(summary, /signtool: C:\\tools\\signtool\.exe/);
});
