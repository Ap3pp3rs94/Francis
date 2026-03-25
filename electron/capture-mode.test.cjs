const test = require("node:test");
const assert = require("node:assert/strict");

const { isCaptureForegroundWindow, normalizeCaptureProcessName } = require("./capture-mode");

test("normalizeCaptureProcessName trims case and exe suffix", () => {
  assert.equal(normalizeCaptureProcessName("SnippingTool.exe"), "snippingtool");
  assert.equal(normalizeCaptureProcessName(" ScreenClippingHost "), "screenclippinghost");
});

test("isCaptureForegroundWindow matches known capture processes and titles", () => {
  assert.equal(isCaptureForegroundWindow({ process: "SnippingTool.exe", title: "" }), true);
  assert.equal(isCaptureForegroundWindow({ process: "ScreenClippingHost", title: "" }), true);
  assert.equal(isCaptureForegroundWindow({ process: "ApplicationFrameHost", title: "Screen snip" }), true);
  assert.equal(isCaptureForegroundWindow({ process: "Code", title: "Visual Studio Code" }), false);
});
