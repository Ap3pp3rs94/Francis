function normalizeConfiguredEnvValue(value = "") {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "";
  }
  if (/<[^>]+>/.test(normalized)) {
    return "";
  }
  return normalized;
}

function readConfiguredEnvValue(env, keys = []) {
  for (const key of keys) {
    const value = normalizeConfiguredEnvValue(env && env[key]);
    if (value) {
      return value;
    }
  }
  return "";
}

function readConfiguredEnvBoolean(env, keys = []) {
  const value = readConfiguredEnvValue(env, keys).toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

module.exports = {
  normalizeConfiguredEnvValue,
  readConfiguredEnvBoolean,
  readConfiguredEnvValue,
};
