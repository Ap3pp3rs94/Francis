function isDetachedConsoleError(error) {
  if (!error || typeof error !== "object") {
    return false;
  }
  const code = String(error.code || "").trim().toUpperCase();
  const message = String(error.message || "").toLowerCase();
  return code === "EPIPE" || code === "ERR_STREAM_DESTROYED" || message.includes("broken pipe");
}

function writeConsole(writer, ...args) {
  try {
    writer(...args);
    return true;
  } catch (error) {
    if (isDetachedConsoleError(error)) {
      return false;
    }
    throw error;
  }
}

module.exports = {
  isDetachedConsoleError,
  writeConsole,
};
