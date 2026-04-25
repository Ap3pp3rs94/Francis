/* eslint-disable no-console */
/**
 * Francis Chat UI — Vite configuration
 *
 * Principles
 * ----------
 * 1) Safe defaults:
 *    - Bind to loopback by default (reduces accidental LAN exposure).
 *    - CORS disabled by default (tight dev posture; use proxy for API access).
 *
 * 2) Deterministic & observable:
 *    - Config driven via env with clear normalization.
 *    - Explicit dev server behavior.
 *
 * 3) Forward-minded without overengineering:
 *    - Optional dev proxy for Francis API paths (no assumptions about backend hosting).
 *    - Loads repo-root .env by default to align with Francis global configuration.
 *
 * Notes
 * -----
 * - Vite only exposes variables prefixed with VITE_ to the browser.
 * - This config may read additional env vars, but they are NOT exposed unless VITE_.
 */

import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type ProxyOptions, type UserConfig } from "vite";
import path from "node:path";

/* -------------------------------------------------------------------------------------------------
 * env helpers (defensive, explicit)
 * ------------------------------------------------------------------------------------------------- */

function toBool(v: string | undefined, fallback: boolean): boolean {
  if (v === undefined) return fallback;
  const s = v.trim().toLowerCase();
  if (s === "1" || s === "true" || s === "yes" || s === "y" || s === "on") return true;
  if (s === "0" || s === "false" || s === "no" || s === "n" || s === "off") return false;
  return fallback;
}

function toInt(v: string | undefined, fallback: number, opts?: { min?: number; max?: number }): number {
  if (v === undefined) return fallback;
  const n = Number(v);
  if (!Number.isFinite(n)) return fallback;
  const i = Math.floor(n);
  const min = opts?.min ?? Number.NEGATIVE_INFINITY;
  const max = opts?.max ?? Number.POSITIVE_INFINITY;
  return Math.max(min, Math.min(max, i));
}

function normalizeBasePath(p: string | undefined, fallback = "/"): string {
  const raw = (p ?? "").trim();
  if (!raw) return fallback;

  // Vite expects base to start with "/" (or be absolute URL) and typically end with "/".
  if (raw.startsWith("http://") || raw.startsWith("https://")) {
    return raw.endsWith("/") ? raw : `${raw}/`;
  }

  let out = raw.startsWith("/") ? raw : `/${raw}`;
  out = out.endsWith("/") ? out : `${out}/`;
  return out;
}

function normalizeUrl(u: string | undefined, fallback: string): string {
  const raw = (u ?? "").trim();
  if (!raw) return fallback;
  return raw.replace(/\/+$/, "");
}

function isAbsoluteHttpUrl(u: string): boolean {
  try {
    const parsed = new URL(u);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function buildProxy(target: string, ws: boolean): ProxyOptions {
  return {
    target,
    changeOrigin: true,
    secure: false,
    ws,
    // Keep paths intact; backend owns routing.
    rewrite: (p) => p,
    configure: (proxy) => {
      // Helpful hardening: don’t crash on transient proxy errors during dev.
      proxy.on("error", (err, _req, _res) => {
        // eslint-disable-next-line no-console
        console.warn("[vite-proxy] error:", err?.message || err);
      });
    },
  };
}

/* -------------------------------------------------------------------------------------------------
 * config
 * ------------------------------------------------------------------------------------------------- */

export default defineConfig(({ mode, command }): UserConfig => {
  /**
   * Repo layout:
   *   D:\francis\apps\chat_ui\vite.config.ts
   * Repo root is two parents up.
   */
  const repoRoot = path.resolve(__dirname, "..", "..");

  /**
   * Load env from repo root (centralized configuration).
   * This aligns with your root `.env.example` model and avoids per-app duplication.
   *
   * Prefix is "" here so the config can read non-VITE values if needed,
   * but Vite will still only expose VITE_* to the browser.
   */
  const env = loadEnv(mode, repoRoot, "");

  // --- Dev server knobs (safe + deterministic defaults)
  const devHost = (env.VITE_DEV_HOST ?? "127.0.0.1").trim();
  const devPort = toInt(env.VITE_DEV_PORT, 5173, { min: 1, max: 65535 });
  const devStrictPort = toBool(env.VITE_DEV_STRICT_PORT, true);
  const devOpen = toBool(env.VITE_DEV_OPEN, false);

  // Polling is sometimes needed on Windows/network drives/AV-heavy systems.
  const devUsePolling = toBool(env.VITE_DEV_POLLING, false);
  const devPollInterval = toInt(env.VITE_DEV_POLLING_INTERVAL_MS, 250, { min: 50, max: 10_000 });

  // Base path for serving UI (reverse proxy deployments may host under /ui/ etc.)
  const base = normalizeBasePath(env.VITE_BASE_PATH ?? env.VITE_BASE, "/");

  // --- API integration defaults
  const defaultApi = "http://127.0.0.1:8000";

  /**
   * If the UI uses absolute URLs, no proxy is required.
   * But proxy is valuable for:
   *   - avoiding CORS during development
   *   - enabling same-origin mode later (VITE_FRANCIS_API_BASE_URL="/")
   *
   * Enabled by default because it has zero effect unless the UI calls these paths.
   */
  const proxyEnabled = toBool(env.VITE_DEV_PROXY_ENABLED, true);

  /**
   * Proxy target:
   * Prefer explicit proxy target; otherwise if API_BASE_URL is absolute use it; else fall back.
   */
  const apiBaseFromEnv = normalizeUrl(env.VITE_FRANCIS_API_BASE_URL, defaultApi);
  const proxyTarget = normalizeUrl(
    env.VITE_FRANCIS_API_PROXY_TARGET,
    isAbsoluteHttpUrl(apiBaseFromEnv) ? apiBaseFromEnv : defaultApi,
  );

  const proxy: Record<string, ProxyOptions> | undefined = proxyEnabled
    ? {
        // Core API namespaces (present/future)
        "/continuity": buildProxy(proxyTarget, false),
        "/approvals": buildProxy(proxyTarget, false),
        "/credentials": buildProxy(proxyTarget, false),
        "/web_learning": buildProxy(proxyTarget, false),
        "/web-learning": buildProxy(proxyTarget, false),
        "/system": buildProxy(proxyTarget, false),
        "/health": buildProxy(proxyTarget, false),

        // Chat websocket + related routes
        "/chat": buildProxy(proxyTarget, true),
      }
    : undefined;

  // --- Build knobs
  const buildSourcemap = toBool(env.VITE_BUILD_SOURCEMAP, false);
  const chunkWarn = toInt(env.VITE_BUILD_CHUNK_WARN_KB, 1200, { min: 200, max: 10_000 });

  /**
   * Vite plugins:
   * - react() provides JSX transform + Fast Refresh.
   * - No additional plugins until you explicitly add needs (e.g., PWA, SVGR, etc.).
   */
  const plugins = [react()];

  const config: UserConfig = {
    // Load .env from repo root (central config)
    envDir: repoRoot,

    // Ensure only VITE_* variables are injected into the client.
    envPrefix: ["VITE_"],

    base,

    plugins,

    server: {
      host: devHost,
      port: devPort,
      strictPort: devStrictPort,
      open: devOpen,

      /**
       * CORS:
       * - Disabled by default. Prefer proxy for API calls (same-origin ergonomics).
       * - If you explicitly need CORS, set VITE_DEV_CORS=true (and consider tightening origins).
       */
      cors: toBool(env.VITE_DEV_CORS, false),

      /**
       * File system serving posture:
       * - Keep strict to avoid serving arbitrary files outside the project.
       */
      fs: {
        strict: true,
      },

      /**
       * Watch settings:
       * - Polling is sometimes required on Windows / corporate AV / network drives.
       */
      watch: devUsePolling
        ? {
            usePolling: true,
            interval: devPollInterval,
          }
        : undefined,

      /**
       * Proxy to backend (optional).
       * Has no impact unless the UI makes requests to these paths.
       */
      proxy,

      /**
       * Mild hardening headers for dev UX.
       * (Production headers should be enforced by reverse proxy / CDN.)
       */
      headers: {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
      },
    },

    preview: {
      host: (env.VITE_PREVIEW_HOST ?? "127.0.0.1").trim(),
      port: toInt(env.VITE_PREVIEW_PORT, 4173, { min: 1, max: 65535 }),
      strictPort: toBool(env.VITE_PREVIEW_STRICT_PORT, true),
    },

    build: {
      target: "es2022",
      outDir: "dist",
      emptyOutDir: true,

      sourcemap: buildSourcemap,

      /**
       * Keep this reasonably high; the console UI can grow with dashboards.
       * We want warnings, not noisy spam.
       */
      chunkSizeWarningLimit: chunkWarn,

      /**
       * Rollup output remains default; Vite already does sensible vendor splitting.
       * Add manualChunks only if you hit caching/perf issues in real usage.
       */
      rollupOptions: {
        output: {
          /**
           * Slightly more deterministic chunk naming helps operators debug deployments.
           * (No assumptions about CDN; still cache-friendly.)
           */
          entryFileNames: "assets/[name]-[hash].js",
          chunkFileNames: "assets/[name]-[hash].js",
          assetFileNames: "assets/[name]-[hash][extname]",
        },
      },
    },

    /**
     * OptimizeDeps:
     * - Keep default; Vite will pre-bundle as needed.
     * - Add includes/excludes only if you encounter dev-server dependency scan issues.
     */
    optimizeDeps: undefined,

    /**
     * Logging:
     * - Vite defaults are fine; if you want quieter output, set VITE_LOG_LEVEL.
     */
    logLevel: (env.VITE_LOG_LEVEL as UserConfig["logLevel"]) ?? undefined,

    /**
     * Clear screen can hide useful stack traces during debugging.
     * Let operators control it.
     */
    clearScreen: toBool(env.VITE_CLEAR_SCREEN, command === "serve"),
  };

  return config;
});
