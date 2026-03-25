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

function patchConsoleForDetachedPipes(consoleObject = console) {
  if (!consoleObject || consoleObject.__francisDetachedPipeSafe) {
    return consoleObject;
  }
  const originalLog = typeof consoleObject.log === "function" ? consoleObject.log.bind(consoleObject) : null;
  const originalWarn = typeof consoleObject.warn === "function" ? consoleObject.warn.bind(consoleObject) : null;
  const originalError = typeof consoleObject.error === "function" ? consoleObject.error.bind(consoleObject) : null;

  if (originalLog) {
    consoleObject.log = (...args) => writeConsole(originalLog, ...args);
  }
  if (originalWarn) {
    consoleObject.warn = (...args) => writeConsole(originalWarn, ...args);
  }
  if (originalError) {
    consoleObject.error = (...args) => writeConsole(originalError, ...args);
  }

  Object.defineProperty(consoleObject, "__francisDetachedPipeSafe", {
    value: true,
    enumerable: false,
    configurable: false,
    writable: false,
  });
  return consoleObject;
}

module.exports = {
  isDetachedConsoleError,
  patchConsoleForDetachedPipes,
  writeConsole,
};
