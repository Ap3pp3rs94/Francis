/**
 * Francis Chat UI — Runtime entrypoint.
 *
 * Design contract
 * ---------------
 *  1) Keep this file "bootstrap-only":
 *     - No business logic
 *     - No API calling for features
 *     - No secrets
 *
 *  2) Observability-first:
 *     - Global error hooks (window error + unhandledrejection)
 *     - Top-level React error boundary fallback
 *     - Optional error reporting endpoint (opt-in via env)
 *
 *  3) Deterministic mounting:
 *     - Single mount root (idempotent across HMR-ish scenarios)
 *     - Clear failure mode if #root is missing
 *
 * Notes
 * -----
 * - This app is NOT SSR by default. We intentionally avoid hydrateRoot.
 *   Your index.html includes a loading placeholder inside #root; hydrateRoot
 *   would treat that as SSR markup and cause mismatches.
 * - React.StrictMode only adds extra checks in development; production behavior
 *   is unchanged. WebSocket-heavy apps may see double-invoked effects in dev.
 */

import React from "react";
import { createRoot, type Root } from "react-dom/client";
import App from "./App";

/* -------------------------------------------------------------------------------------------------
 * Global typing surface (safe debug visibility only)
 * ------------------------------------------------------------------------------------------------- */

type UiRuntimeConfig = {
  mode: string;
  dev: boolean;
  prod: boolean;

  baseUrl: string; // Vite base URL (NOT API base URL)
  origin: string; // window.location.origin

  // Optional build metadata (safe, non-secret)
  buildSha?: string;
  buildTime?: string;

  // Optional error reporting endpoint (opt-in)
  errorReportingUrl?: string;
};

declare global {
  interface Window {
    __FRANCIS_UI__?: {
      bootTs: number;
      config: UiRuntimeConfig;
      root?: Root;
      lastFatal?: {
        ts: number;
        fingerprint: string;
      };
    };
  }
}

/* -------------------------------------------------------------------------------------------------
 * Env helpers — avoid hard dependency on vite-env.d.ts custom typings
 * ------------------------------------------------------------------------------------------------- */

function envRecord(): Record<string, unknown> {
  // Vite provides import.meta.env at runtime; we cast defensively.
  return (import.meta.env ?? {}) as unknown as Record<string, unknown>;
}

function envString(key: string, fallback = ""): string {
  const v = envRecord()[key];
  return typeof v === "string" ? v : fallback;
}

function envBool(key: string, fallback = false): boolean {
  const v = envRecord()[key];
  if (typeof v === "boolean") return v;
  if (typeof v === "string") {
    const s = v.trim().toLowerCase();
    if (s === "1" || s === "true" || s === "yes" || s === "on") return true;
    if (s === "0" || s === "false" || s === "no" || s === "off") return false;
  }
  return fallback;
}

/* -------------------------------------------------------------------------------------------------
 * Boot config — safe debug data only (no secrets)
 * ------------------------------------------------------------------------------------------------- */

function buildRuntimeConfig(): UiRuntimeConfig {
  // Vite standard fields
  const mode = String((import.meta as unknown as { env?: { MODE?: unknown } }).env?.MODE ?? "unknown");
  const dev = Boolean((import.meta as unknown as { env?: { DEV?: unknown } }).env?.DEV ?? false);
  const prod = Boolean((import.meta as unknown as { env?: { PROD?: unknown } }).env?.PROD ?? false);
  const baseUrl = String((import.meta as unknown as { env?: { BASE_URL?: unknown } }).env?.BASE_URL ?? "/");

  // Optional metadata (safe)
  const buildSha = envString("VITE_FRANCIS_BUILD_SHA", "").trim() || undefined;
  const buildTime = envString("VITE_FRANCIS_BUILD_TIME", "").trim() || undefined;

  // Optional error reporting endpoint (opt-in)
  // IMPORTANT: If unset, we only log locally.
  const errorReportingUrl = envString("VITE_FRANCIS_UI_ERROR_REPORTING_URL", "").trim() || undefined;

  return {
    mode,
    dev,
    prod,
    baseUrl,
    origin: window.location.origin,
    buildSha,
    buildTime,
    errorReportingUrl,
  };
}

function initGlobalDebugState(config: UiRuntimeConfig): void {
  if (!window.__FRANCIS_UI__) {
    window.__FRANCIS_UI__ = {
      bootTs: Date.now(),
      config,
    };
  } else {
    // Keep earliest boot timestamp, update config (useful in HMR/dev reloads).
    window.__FRANCIS_UI__.config = config;
  }
}

/* -------------------------------------------------------------------------------------------------
 * Logging — structured, quiet by default, helpful when needed
 * ------------------------------------------------------------------------------------------------- */

function bootLog(config: UiRuntimeConfig): void {
  // Keep output helpful but not noisy. Use a collapsed group.
  const title = `Francis UI boot (${config.mode})`;
  // eslint-disable-next-line no-console
  console.groupCollapsed(title);
  try {
    // eslint-disable-next-line no-console
    console.info("origin:", config.origin);
    // eslint-disable-next-line no-console
    console.info("baseUrl:", config.baseUrl);
    if (config.buildSha) {
      // eslint-disable-next-line no-console
      console.info("buildSha:", config.buildSha);
    }
    if (config.buildTime) {
      // eslint-disable-next-line no-console
      console.info("buildTime:", config.buildTime);
    }
    if (config.errorReportingUrl) {
      // eslint-disable-next-line no-console
      console.info("errorReportingUrl:", config.errorReportingUrl);
    }
  } finally {
    // eslint-disable-next-line no-console
    console.groupEnd();
  }
}

/* -------------------------------------------------------------------------------------------------
 * Error reporting — safe-by-default, opt-in transport
 * ------------------------------------------------------------------------------------------------- */

type ErrorEnvelope = {
  ts: number;
  kind: "window_error" | "unhandledrejection" | "react_error_boundary";
  message: string;
  stack?: string;

  url: string;
  userAgent: string;

  // Optional context
  componentStack?: string;

  // Optional request correlation (UI-side only)
  fingerprint: string;

  // Safe build metadata
  mode: string;
  buildSha?: string;
  buildTime?: string;
};

function fingerprintError(kind: string, message: string, stack?: string): string {
  // Cheap stable-ish fingerprint (no crypto dependency).
  // Keep it deterministic, small, and safe.
  const base = `${kind}|${message}|${stack ?? ""}`;
  let h = 2166136261; // FNV-1a style
  for (let i = 0; i < base.length; i++) {
    h ^= base.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return `ui_${(h >>> 0).toString(16)}`;
}

function shouldRateLimit(fingerprint: string): boolean {
  const now = Date.now();
  const last = window.__FRANCIS_UI__?.lastFatal;
  if (!last) return false;

  // Drop identical fingerprints seen very recently (prevents infinite loops).
  if (last.fingerprint === fingerprint && now - last.ts < 1500) return true;
  return false;
}

function recordLastFatal(fingerprint: string): void {
  if (!window.__FRANCIS_UI__) return;
  window.__FRANCIS_UI__.lastFatal = { ts: Date.now(), fingerprint };
}

async function postJson(url: string, body: unknown, timeoutMs = 5_000): Promise<void> {
  const controller = new AbortController();
  const t = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
      // credentials: "omit" by default
    });
  } catch {
    // Intentionally swallow: reporting must never crash the UI.
  } finally {
    window.clearTimeout(t);
  }
}

function reportError(envelope: ErrorEnvelope, config: UiRuntimeConfig): void {
  if (shouldRateLimit(envelope.fingerprint)) return;
  recordLastFatal(envelope.fingerprint);

  // Always log locally.
  // eslint-disable-next-line no-console
  console.error("[Francis UI] fatal:", envelope);

  // Optional: ship to backend if configured.
  if (config.errorReportingUrl) {
    void postJson(config.errorReportingUrl, envelope);
  }
}

function installGlobalErrorHandlers(config: UiRuntimeConfig): void {
  window.addEventListener("error", (ev) => {
    const message = ev.error instanceof Error ? ev.error.message : String(ev.message ?? "window error");
    const stack = ev.error instanceof Error ? ev.error.stack : undefined;

    const fp = fingerprintError("window_error", message, stack);

    reportError(
      {
        ts: Math.floor(Date.now() / 1000),
        kind: "window_error",
        message,
        stack,
        url: window.location.href,
        userAgent: navigator.userAgent,
        fingerprint: fp,
        mode: config.mode,
        buildSha: config.buildSha,
        buildTime: config.buildTime,
      },
      config,
    );
  });

  window.addEventListener("unhandledrejection", (ev) => {
    const reason = ev.reason;
    const message =
      reason instanceof Error
        ? reason.message
        : typeof reason === "string"
          ? reason
          : "Unhandled promise rejection";

    const stack = reason instanceof Error ? reason.stack : undefined;
    const fp = fingerprintError("unhandledrejection", message, stack);

    reportError(
      {
        ts: Math.floor(Date.now() / 1000),
        kind: "unhandledrejection",
        message,
        stack,
        url: window.location.href,
        userAgent: navigator.userAgent,
        fingerprint: fp,
        mode: config.mode,
        buildSha: config.buildSha,
        buildTime: config.buildTime,
      },
      config,
    );
  });
}

/* -------------------------------------------------------------------------------------------------
 * React error boundary — stops white-screen failures
 * ------------------------------------------------------------------------------------------------- */

type RootErrorBoundaryProps = {
  config: UiRuntimeConfig;
  children: React.ReactNode;
};

type RootErrorBoundaryState = {
  hasError: boolean;
  errorMessage?: string;
  stack?: string;
  componentStack?: string;
  fingerprint?: string;
};

class RootErrorBoundary extends React.PureComponent<RootErrorBoundaryProps, RootErrorBoundaryState> {
  state: RootErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(err: unknown): RootErrorBoundaryState {
    const message = err instanceof Error ? err.message : "Unknown UI error";
    const stack = err instanceof Error ? err.stack : undefined;
    const fp = fingerprintError("react_error_boundary", message, stack);
    return { hasError: true, errorMessage: message, stack, fingerprint: fp };
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo): void {
    const message = error instanceof Error ? error.message : "Unknown UI error";
    const stack = error instanceof Error ? error.stack : undefined;
    const fp = fingerprintError("react_error_boundary", message, stack);

    reportError(
      {
        ts: Math.floor(Date.now() / 1000),
        kind: "react_error_boundary",
        message,
        stack,
        componentStack: info.componentStack,
        url: window.location.href,
        userAgent: navigator.userAgent,
        fingerprint: fp,
        mode: this.props.config.mode,
        buildSha: this.props.config.buildSha,
        buildTime: this.props.config.buildTime,
      },
      this.props.config,
    );

    this.setState({ componentStack: info.componentStack, fingerprint: fp });
  }

  private copyDiagnostics = async (): Promise<void> => {
    const payload = {
      message: this.state.errorMessage,
      fingerprint: this.state.fingerprint,
      stack: this.state.stack,
      componentStack: this.state.componentStack,
      href: window.location.href,
      config: this.props.config,
    };

    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      // eslint-disable-next-line no-console
      console.info("[Francis UI] copied diagnostics to clipboard");
    } catch {
      // ignore
    }
  };

  render(): React.ReactNode {
    if (!this.state.hasError) return this.props.children;

    const msg = this.state.errorMessage ?? "A fatal UI error occurred.";
    const fp = this.state.fingerprint ?? "unknown";

    // Minimal inline styling: no CSS dependencies.
    return (
      <div style={{ fontFamily: "system-ui, sans-serif", padding: 16, maxWidth: 980, margin: "0 auto" }}>
        <h2 style={{ marginTop: 0 }}>Francis UI encountered a fatal error</h2>
        <p style={{ opacity: 0.9 }}>
          <b>Fingerprint:</b> <code>{fp}</code>
        </p>
        <p style={{ whiteSpace: "pre-wrap" }}>{msg}</p>

        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <button onClick={() => window.location.reload()}>Reload</button>
          <button onClick={() => void this.copyDiagnostics()}>Copy diagnostics</button>
        </div>

        <details style={{ marginTop: 14 }}>
          <summary>Details</summary>
          <pre style={{ overflow: "auto", padding: 10, border: "1px solid #ddd", borderRadius: 8 }}>
            {this.state.stack ?? "(no stack)"}
          </pre>
          <pre style={{ overflow: "auto", padding: 10, border: "1px solid #ddd", borderRadius: 8 }}>
            {this.state.componentStack ?? "(no component stack)"}
          </pre>
        </details>

        <details style={{ marginTop: 14 }}>
          <summary>Runtime</summary>
          <pre style={{ overflow: "auto", padding: 10, border: "1px solid #ddd", borderRadius: 8 }}>
            {JSON.stringify(this.props.config, null, 2)}
          </pre>
        </details>
      </div>
    );
  }
}

/* -------------------------------------------------------------------------------------------------
 * Mounting — single root, clear failures
 * ------------------------------------------------------------------------------------------------- */

function getRootElement(): HTMLElement {
  const el = document.getElementById("root");
  if (!el) {
    const msg =
      "Chat UI bootstrap failed: #root element not found. " +
      "Check apps/chat_ui/index.html contains <div id=\"root\">…</div>.";
    // eslint-disable-next-line no-console
    console.error(msg);
    throw new Error(msg);
  }
  return el;
}

function getOrCreateReactRoot(container: HTMLElement): Root {
  const existing = window.__FRANCIS_UI__?.root;
  if (existing) return existing;

  const root = createRoot(container);
  if (window.__FRANCIS_UI__) window.__FRANCIS_UI__.root = root;
  return root;
}

function render(): void {
  // Perf mark: best-effort (doesn’t break older browsers)
  try {
    performance.mark("francis_ui:boot_start");
  } catch {
    // ignore
  }

  const config = buildRuntimeConfig();
  initGlobalDebugState(config);
  installGlobalErrorHandlers(config);
  bootLog(config);

  const container = getRootElement();
  const root = getOrCreateReactRoot(container);

  const strict = envBool("VITE_FRANCIS_UI_STRICT_MODE", true);

  const tree = (
    <RootErrorBoundary config={config}>
      {strict ? (
        <React.StrictMode>
          <App />
        </React.StrictMode>
      ) : (
        <App />
      )}
    </RootErrorBoundary>
  );

  root.render(tree);

  try {
    performance.mark("francis_ui:boot_end");
    performance.measure("francis_ui:boot", "francis_ui:boot_start", "francis_ui:boot_end");
  } catch {
    // ignore
  }
}

// Execute bootstrap immediately.
render();
