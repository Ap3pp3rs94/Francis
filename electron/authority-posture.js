const NODE_ID_KEYS = ["FRANCIS_NODE_ID", "COMPUTERNAME", "HOSTNAME"];
const SERVICE_ID_KEYS = ["FRANCIS_SERVICE_ID"];
const SUPPORT_OPERATOR_KEYS = ["FRANCIS_SUPPORT_OPERATOR", "FRANCIS_SUPPORT_IDENTITY"];
const TENANT_BINDING_KEYS = ["FRANCIS_TENANT_ID", "FRANCIS_MANAGED_COPY_ID", "FRANCIS_COPY_ID"];

const CONNECTOR_CREDENTIAL_CLASSES = [
  {
    id: "model_remote",
    label: "Remote model providers",
    keys: ["OPENAI_API_KEY", "FRANCIS_OPENAI_API_KEY", "ANTHROPIC_API_KEY", "FRANCIS_ANTHROPIC_API_KEY"],
  },
  {
    id: "github",
    label: "GitHub",
    keys: ["GITHUB_TOKEN", "GH_TOKEN"],
  },
  {
    id: "observability",
    label: "Observability",
    keys: ["SENTRY_AUTH_TOKEN"],
  },
  {
    id: "deployment",
    label: "Deployment",
    keys: ["NETLIFY_AUTH_TOKEN", "VERCEL_TOKEN"],
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

function hasEnvValue(env, key) {
  return Boolean(env && typeof env[key] === "string" && env[key].trim());
}

function detectConnectorCredentialClasses(env) {
  const configured = [];
  for (const entry of CONNECTOR_CREDENTIAL_CLASSES) {
    if (entry.keys.some((key) => hasEnvValue(env, key))) {
      configured.push(entry.label);
    }
  }

  const customConnectorKeys = Object.keys(env || {}).filter((key) => /^FRANCIS_CONNECTOR_.+(_TOKEN|_KEY|_SECRET)$/.test(key));
  if (customConnectorKeys.length) {
    configured.push(`Custom connectors (${customConnectorKeys.length})`);
  }

  return configured;
}

function buildAuthorityPosture({ env = process.env, portability = null, provider = null } = {}) {
  const nodeId = readEnvValue(env, NODE_ID_KEYS) || "local-node";
  const nodeExplicit = hasEnvValue(env, "FRANCIS_NODE_ID");
  const serviceId = readEnvValue(env, SERVICE_ID_KEYS) || "overlay-shell";
  const serviceExplicit = hasEnvValue(env, "FRANCIS_SERVICE_ID");
  const supportIdentity = readEnvValue(env, SUPPORT_OPERATOR_KEYS);
  const tenantBinding = readEnvValue(env, TENANT_BINDING_KEYS);
  const connectorClasses = detectConnectorCredentialClasses(env);
  const supportConfigured = Boolean(supportIdentity);
  const supportBound = Boolean(supportIdentity && tenantBinding);
  const portabilitySummary = portability?.lastImportStatus === "blocked"
    ? String(portability?.lastImportMessage || "Portable shell import blocked")
    : "Shell portability excludes live authority and credentials.";

  let severity = "low";
  let summary = "Authority posture is explicit and local-first.";

  if (supportConfigured && !supportBound) {
    severity = "high";
    summary = "Support authority is configured without a tenant or managed-copy binding. Keep support-level actions review-first until authority is bound explicitly.";
  } else if ((connectorClasses.length > 0 || supportConfigured) && (!nodeExplicit || !serviceExplicit)) {
    severity = "medium";
    summary = "Connector or support authority is configured while node or service identity remains implicit. Make identity explicit before treating connector-backed execution as fully settled.";
  } else if (connectorClasses.length > 0) {
    severity = "medium";
    summary = "Connector credential classes are configured. Authority separation is visible, but connector-backed actions should stay reviewable.";
  } else if (provider?.severity === "high" || provider?.severity === "medium") {
    severity = "medium";
    summary = "Authority posture is local-first, but provider dependency still narrows model-backed authority until routing is settled.";
  }

  const items = [
    {
      id: "user",
      label: "User authority",
      tone: "low",
      summary: "Current OS operator remains sovereign. Shell startup, recovery, portability, and rollback do not restore live Pilot or Away authority.",
    },
    {
      id: "node",
      label: "Node identity",
      tone: nodeExplicit ? "low" : "medium",
      summary: `${nodeExplicit ? "explicit" : "implicit"} | ${nodeId}`,
    },
    {
      id: "service",
      label: "Service identity",
      tone: serviceExplicit ? "low" : "medium",
      summary: `${serviceExplicit ? "explicit" : "default"} | ${serviceId}`,
    },
    {
      id: "connectors",
      label: "Connector authority",
      tone: connectorClasses.length ? "medium" : "low",
      summary: connectorClasses.length
        ? `${connectorClasses.length} credential class${connectorClasses.length === 1 ? "" : "es"} configured | ${connectorClasses.join(", ")}`
        : "No connector credential classes detected in shell environment.",
    },
    {
      id: "support",
      label: "Support authority",
      tone: supportConfigured ? (supportBound ? "medium" : "high") : "low",
      summary: supportConfigured
        ? supportBound
          ? `configured | bound to ${tenantBinding}`
          : "configured | missing tenant or managed-copy binding"
        : "none | local operator only",
    },
    {
      id: "redaction",
      label: "Secret exposure",
      tone: "low",
      summary: "Shell surfaces expose credential class and authority posture only; secret values are withheld from HUD, support bundles, and shell portability.",
    },
  ];

  return {
    severity,
    summary,
    nodeId,
    nodeExplicit,
    serviceId,
    serviceExplicit,
    connectorCredentialClasses: connectorClasses,
    supportConfigured,
    supportBound,
    portabilitySummary,
    cards: [
      {
        label: "Summary",
        value: summary,
        tone: severity,
      },
      {
        label: "User",
        value: "Current OS operator",
        tone: "low",
      },
      {
        label: "Node",
        value: nodeExplicit ? nodeId : `${nodeId} (implicit)`,
        tone: nodeExplicit ? "low" : "medium",
      },
      {
        label: "Service",
        value: serviceExplicit ? serviceId : `${serviceId} (default)`,
        tone: serviceExplicit ? "low" : "medium",
      },
      {
        label: "Connectors",
        value: connectorClasses.length ? connectorClasses.join(", ") : "none",
        tone: connectorClasses.length ? "medium" : "low",
      },
      {
        label: "Support",
        value: supportConfigured ? (supportBound ? "bound" : "ambiguous") : "local-only",
        tone: supportConfigured ? (supportBound ? "medium" : "high") : "low",
      },
      {
        label: "Secrets",
        value: "class-only visibility",
        tone: "low",
      },
      {
        label: "Portability",
        value: portabilitySummary,
        tone: portability?.lastImportStatus === "blocked" ? "high" : "low",
      },
    ],
    items,
  };
}

module.exports = {
  buildAuthorityPosture,
};
