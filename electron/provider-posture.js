const ACTIVE_PROVIDER_KEYS = ["FRANCIS_PROVIDER", "FRANCIS_LLM_PROVIDER", "FRANCIS_MODEL_PROVIDER"];
const FALLBACK_PROVIDER_KEYS = ["FRANCIS_PROVIDER_FALLBACKS", "FRANCIS_LLM_FALLBACKS", "FRANCIS_MODEL_FALLBACKS"];

const PROVIDER_DEFINITIONS = [
  {
    id: "ollama",
    label: "Ollama",
    kind: "local",
    aliases: ["local", "ollama"],
    endpointKeys: ["OLLAMA_HOST", "OLLAMA_BASE_URL", "FRANCIS_OLLAMA_HOST"],
    implicitEndpoint: "http://127.0.0.1:11434",
  },
  {
    id: "llamacpp",
    label: "llama.cpp",
    kind: "local",
    aliases: ["llama.cpp", "llama_cpp", "llamacpp"],
    endpointKeys: ["LLAMA_CPP_SERVER", "LLAMA_CPP_SERVER_URL", "LLAMACPP_SERVER_URL", "FRANCIS_LLAMACPP_URL"],
  },
  {
    id: "openai",
    label: "OpenAI",
    kind: "remote",
    aliases: ["openai", "gpt"],
    credentialKeys: ["OPENAI_API_KEY", "FRANCIS_OPENAI_API_KEY"],
    endpointKeys: ["OPENAI_BASE_URL", "FRANCIS_OPENAI_BASE_URL"],
  },
  {
    id: "anthropic",
    label: "Anthropic",
    kind: "remote",
    aliases: ["anthropic", "claude"],
    credentialKeys: ["ANTHROPIC_API_KEY", "FRANCIS_ANTHROPIC_API_KEY"],
    endpointKeys: ["ANTHROPIC_BASE_URL", "FRANCIS_ANTHROPIC_BASE_URL"],
  },
];

function readEnvValue(env, keys = []) {
  for (const key of keys) {
    const value = env && typeof env[key] === "string" ? env[key].trim() : "";
    if (value) {
      return value;
    }
  }
  return "";
}

function normalizeProviderId(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, "");
  if (!normalized) {
    return null;
  }

  for (const provider of PROVIDER_DEFINITIONS) {
    if (provider.id === normalized || provider.aliases.includes(normalized)) {
      return provider.id;
    }
  }
  return null;
}

function parseFallbackProviders(env) {
  const raw = readEnvValue(env, FALLBACK_PROVIDER_KEYS);
  if (!raw) {
    return [];
  }
  const seen = new Set();
  const values = [];
  for (const part of raw.split(",")) {
    const normalized = normalizeProviderId(part);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    values.push(normalized);
  }
  return values;
}

function buildProviderRecord(definition, env) {
  const credential = readEnvValue(env, definition.credentialKeys);
  const endpoint = readEnvValue(env, definition.endpointKeys);
  const hasImplicitLocalDefault = Boolean(definition.implicitEndpoint);
  const explicitConfig = Boolean(credential || endpoint);

  let configured = explicitConfig;
  let status = "blocked";
  let detail = "No provider path declared.";

  if (definition.kind === "local") {
    if (endpoint) {
      configured = true;
      status = "ok";
      detail = `Endpoint ${endpoint}`;
    } else if (hasImplicitLocalDefault) {
      detail = `Implicit local default ${definition.implicitEndpoint}`;
      status = "attention";
    }
  } else if (credential) {
    configured = true;
    status = "ok";
    detail = endpoint ? `Credential and endpoint configured (${endpoint})` : "Credential configured";
  } else if (endpoint) {
    configured = true;
    status = "attention";
    detail = `Endpoint configured without credential (${endpoint})`;
  }

  return {
    id: definition.id,
    label: definition.label,
    kind: definition.kind,
    configured,
    explicitConfig,
    credentialConfigured: Boolean(credential),
    endpointConfigured: Boolean(endpoint),
    implicitDefault: Boolean(definition.kind === "local" && hasImplicitLocalDefault && !endpoint),
    status,
    detail,
    endpoint: endpoint || definition.implicitEndpoint || null,
  };
}

function inferActiveProvider(records) {
  for (const candidate of ["ollama", "llamacpp", "openai", "anthropic"]) {
    const record = records.find((item) => item.id === candidate);
    if (record && record.explicitConfig) {
      return record.id;
    }
  }
  return null;
}

function describeDependency(activeRecord, fallbackRecords) {
  if (!activeRecord) {
    return "inspect_only";
  }
  if (activeRecord.kind === "local") {
    return fallbackRecords.some((entry) => entry.kind === "remote") ? "hybrid" : "local_first";
  }
  return fallbackRecords.some((entry) => entry.kind === "local") ? "remote_with_local_fallback" : "remote_primary";
}

function describePrivacyPosture(dependency) {
  switch (dependency) {
    case "local_first":
      return "Local-first";
    case "hybrid":
      return "Local-first with governed remote fallback";
    case "remote_with_local_fallback":
      return "Remote primary with local fallback";
    case "remote_primary":
      return "Remote-dependent";
    default:
      return "Inspect-only";
  }
}

function buildProviderPosture({ env = process.env, hudState = null } = {}) {
  const requestedRaw = readEnvValue(env, ACTIVE_PROVIDER_KEYS);
  const requestedId = normalizeProviderId(requestedRaw);
  const fallbackIds = parseFallbackProviders(env);
  const records = PROVIDER_DEFINITIONS.map((definition) => buildProviderRecord(definition, env));
  const activeProviderId = requestedId || inferActiveProvider(records);
  const activeRecord = records.find((record) => record.id === activeProviderId) || null;
  const fallbackRecords = fallbackIds
    .filter((providerId) => providerId !== activeProviderId)
    .map((providerId) => records.find((record) => record.id === providerId))
    .filter(Boolean);
  const configuredCount = records.filter((record) => record.configured || record.implicitDefault).length;
  const dependency = describeDependency(activeRecord, fallbackRecords);
  const privacyPosture = describePrivacyPosture(dependency);

  let severity = "low";
  let summary = "Provider posture is governed.";

  if (requestedRaw && !requestedId) {
    severity = "high";
    summary = `Requested provider ${requestedRaw} is not recognized. Keep model-backed work inspect-first until provider routing is corrected.`;
  } else if (!activeRecord) {
    severity = "high";
    summary = "No model provider is configured. Keep model-backed work inspect-first until a provider path is declared.";
  } else if (activeRecord.status === "blocked") {
    severity = "high";
    summary = `${activeRecord.label} is selected but not configured. Declare a valid provider path before trusting model-backed execution.`;
  } else if (dependency === "remote_primary" && !fallbackRecords.length) {
    severity = "medium";
    summary = `${activeRecord.label} is the only active provider. Provider failure will narrow model-backed work immediately.`;
  } else if (activeRecord.status === "attention") {
    severity = "medium";
    summary = `${activeRecord.label} is active through an implicit or partial configuration. Verify the provider path before trusting fallback behavior.`;
  } else if (dependency === "hybrid") {
    summary = `${activeRecord.label} is primary with governed remote fallback. Provider dependency is visible and bounded.`;
  } else if (dependency === "local_first") {
    summary = `${activeRecord.label} is the active local provider. Model-backed work stays local unless the strategy changes.`;
  } else if (dependency === "remote_with_local_fallback") {
    summary = `${activeRecord.label} is primary with a local fallback path available for narrowed continuity.`;
  } else {
    summary = `${activeRecord.label} is the active provider and provider posture is visible.`;
  }

  const runtime = hudState
    ? `${String(hudState.mode || "unknown")} | ${String(hudState.runtimeKind || "unknown")}`
    : "unknown | unknown";
  const fallbackSummary = fallbackRecords.length ? fallbackRecords.map((record) => record.label).join(", ") : "none";
  const items = records.map((record) => {
    const roleParts = [];
    if (activeRecord && record.id === activeRecord.id) {
      roleParts.push("active");
    }
    if (fallbackRecords.some((fallback) => fallback.id === record.id)) {
      roleParts.push("fallback");
    }
    if (!roleParts.length) {
      roleParts.push("available");
    }
    return {
      id: record.id,
      label: record.label,
      tone:
        activeRecord && record.id === activeRecord.id
          ? severity
          : record.status === "blocked"
            ? "low"
            : record.status === "attention"
              ? "medium"
              : "low",
      summary: `${roleParts.join(" + ")} | ${record.kind} | ${record.detail}`,
    };
  });

  return {
    severity,
    summary,
    activeProviderId: activeRecord ? activeRecord.id : null,
    activeProviderLabel: activeRecord ? activeRecord.label : "none",
    requestedProvider: requestedId || requestedRaw || null,
    fallbackProviderIds: fallbackRecords.map((record) => record.id),
    fallbackSummary,
    dependency,
    privacyPosture,
    configuredCount,
    runtime,
    items,
    cards: [
      {
        label: "Summary",
        value: summary,
        tone: severity,
      },
      {
        label: "Active",
        value: activeRecord ? activeRecord.label : "none",
        tone: severity,
      },
      {
        label: "Fallback",
        value: fallbackSummary,
        tone: fallbackRecords.length ? "medium" : "low",
      },
      {
        label: "Dependency",
        value: dependency,
        tone: dependency === "remote_primary" ? "medium" : severity,
      },
      {
        label: "Privacy",
        value: privacyPosture,
        tone: dependency === "remote_primary" ? "medium" : "low",
      },
      {
        label: "Runtime",
        value: runtime,
        tone: hudState?.ready === false ? "medium" : "low",
      },
      {
        label: "Configured",
        value: String(configuredCount),
        tone: configuredCount === 0 ? "high" : configuredCount === 1 ? "medium" : "low",
      },
    ],
  };
}

module.exports = {
  buildProviderPosture,
  normalizeProviderId,
};
