const CAPTURE_PROCESS_NAMES = new Set([
  "screenclippinghost",
  "snippingtool",
]);

const CAPTURE_TITLE_FRAGMENTS = [
  "snipping tool",
  "screen snip",
  "screen clipping",
];

function normalizeCaptureProcessName(value) {
  return String(value || "").trim().toLowerCase().replace(/\.exe$/, "");
}

function isCaptureForegroundWindow(record) {
  const processName = normalizeCaptureProcessName(record?.process);
  const title = String(record?.title || "").trim().toLowerCase();
  if (CAPTURE_PROCESS_NAMES.has(processName)) {
    return true;
  }
  return CAPTURE_TITLE_FRAGMENTS.some((fragment) => title.includes(fragment));
}

module.exports = {
  CAPTURE_PROCESS_NAMES,
  isCaptureForegroundWindow,
  normalizeCaptureProcessName,
};
