#!/usr/bin/env node
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import os from "node:os";
import path from "node:path";

const CONTRACT = {
  ok: true,
  kind: "francis.stage13.trust_calibration.browser_readback_runner_contract",
  stage: "Stage 13 / Trust Calibration",
  target: "stage13_operator_browser_visual_readback",
  actor: "chat_ui.trust_calibration",
  required_scope: "trust_calibration.browser_visual_readback.write",
  ui_surface_id: "francis-trust-calibration",
  ui_url_default: "http://127.0.0.1:5173/",
  api_url_default: "http://127.0.0.1:8000",
  receipt_route: "/trust-calibration/operator-browser-visual-readback",
  required_visible_signals: [
    "Stage 13 calibration",
    "Record visual readback",
    "Missing verification",
    "Forbidden language",
    "Claim guards",
    "stage13_operator_browser_visual_readback",
    "side effects denied",
    "Completion review blocked",
  ],
  artifact_directory: "output/playwright",
  writes_receipt: "only_after_browser_visible_signals_are_observed_and_ui_action_succeeds",
  closes_stage: false,
  writes_memory: false,
  grants_execution_authority: false,
  grants_mutation_authority: false,
};

const DEFAULT_CHROME_PATHS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/usr/bin/microsoft-edge",
];

function parseArgs(argv) {
  const options = {
    uiUrl: process.env.FRANCIS_STAGE13_UI_URL || CONTRACT.ui_url_default,
    apiUrl: process.env.FRANCIS_STAGE13_API_URL || CONTRACT.api_url_default,
    chromePath: process.env.CHROME_PATH || process.env.FRANCIS_BROWSER_PATH || "",
    outDir: "output/playwright",
    timeoutMs: 30000,
    debugPort: 9222,
    headed: false,
    printContract: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--print-contract") {
      options.printContract = true;
    } else if (arg === "--ui-url") {
      options.uiUrl = requiredValue(argv, ++index, arg);
    } else if (arg === "--api-url") {
      options.apiUrl = requiredValue(argv, ++index, arg);
    } else if (arg === "--chrome-path") {
      options.chromePath = requiredValue(argv, ++index, arg);
    } else if (arg === "--out-dir") {
      options.outDir = requiredValue(argv, ++index, arg);
    } else if (arg === "--timeout-ms") {
      options.timeoutMs = toInt(requiredValue(argv, ++index, arg), 30000);
    } else if (arg === "--debug-port") {
      options.debugPort = toInt(requiredValue(argv, ++index, arg), 9222);
    } else if (arg === "--headed") {
      options.headed = true;
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return options;
}

function requiredValue(argv, index, flag) {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`${flag} requires a value`);
  }
  return value;
}

function toInt(value, fallback) {
  const parsed = Number.parseInt(String(value), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function printHelp() {
  console.log(`Usage: node scripts/trust-calibration-browser-readback.mjs [options]

Options:
  --print-contract       Print the governed runner contract and exit.
  --ui-url <url>         Vite UI URL. Default: ${CONTRACT.ui_url_default}
  --api-url <url>        Francis API URL. Default: ${CONTRACT.api_url_default}
  --chrome-path <path>   Chrome or Edge executable path.
  --out-dir <path>       Artifact directory. Default: output/playwright
  --debug-port <port>    Chrome DevTools port. Default: 9222
  --timeout-ms <ms>      Browser/API wait timeout. Default: 30000
  --headed               Launch a visible browser window instead of headless.
`);
}

function findBrowser(explicitPath) {
  const candidates = [explicitPath, ...DEFAULT_CHROME_PATHS].filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return "";
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url, options = {}, timeoutMs = 5000) {
  const parsed = new URL(url);
  const client = parsed.protocol === "https:" ? https : http;
  const method = String(options.method || "GET").toUpperCase();
  return await new Promise((resolve, reject) => {
    const request = client.request(
      parsed,
      {
        method,
        headers: options.headers || {},
        timeout: timeoutMs,
      },
      (response) => {
        const chunks = [];
        response.setEncoding("utf8");
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const body = chunks.join("");
          if ((response.statusCode || 0) < 200 || (response.statusCode || 0) >= 300) {
            reject(new Error(`${url} returned HTTP ${response.statusCode}`));
            return;
          }
          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(new Error(`Invalid JSON from ${url}: ${error instanceof Error ? error.message : String(error)}`));
          }
        });
      },
    );
    request.on("timeout", () => {
      request.destroy(new Error(`${url} timed out after ${timeoutMs}ms`));
    });
    request.on("error", reject);
    if (options.body) {
      request.write(options.body);
    }
    request.end();
  });
}

async function waitForJson(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "";
  while (Date.now() < deadline) {
    try {
      return await fetchJson(url, {}, Math.min(timeoutMs, 2000));
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
      await delay(250);
    }
  }
  throw new Error(`Timed out waiting for ${url}: ${lastError}`);
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
    this.ws = new WebSocket(wsUrl);
  }

  async open(timeoutMs) {
    if (this.ws.readyState === WebSocket.OPEN) return;
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("CDP websocket open timeout")), timeoutMs);
      this.ws.addEventListener(
        "open",
        () => {
          clearTimeout(timer);
          this.ws.addEventListener("message", (event) => this.handleMessage(event));
          resolve();
        },
        { once: true },
      );
      this.ws.addEventListener(
        "error",
        () => {
          clearTimeout(timer);
          reject(new Error(`CDP websocket error for ${this.wsUrl}`));
        },
        { once: true },
      );
    });
  }

  handleMessage(event) {
    const message = JSON.parse(String(event.data));
    if (!message.id || !this.pending.has(message.id)) {
      return;
    }
    const { resolve, reject } = this.pending.get(message.id);
    this.pending.delete(message.id);
    if (message.error) {
      reject(new Error(JSON.stringify(message.error)));
    } else {
      resolve(message.result ?? {});
    }
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    const payload = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(payload);
    });
  }

  close() {
    try {
      this.ws.close();
    } catch {
      // Best effort cleanup only.
    }
  }
}

async function waitForEval(cdp, expression, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastValue = null;
  while (Date.now() < deadline) {
    const result = await cdp.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    lastValue = result.result?.value ?? null;
    if (lastValue) return lastValue;
    await delay(500);
  }
  throw new Error(`Timed out waiting for browser expression. Last value: ${JSON.stringify(lastValue)}`);
}

async function captureScreenshot(cdp, filePath) {
  const result = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  fs.writeFileSync(filePath, Buffer.from(result.data, "base64"));
}

function chromeArgs(options, profileDir) {
  const args = [
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-sync",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-allow-origins=*",
    "--remote-debugging-address=127.0.0.1",
    `--remote-debugging-port=${options.debugPort}`,
    `--user-data-dir=${profileDir}`,
    "--window-size=1365,900",
    "about:blank",
  ];
  if (!options.headed) {
    args.unshift("--headless=new");
  }
  return args;
}

function tail(text, maxLength = 2000) {
  return text.length > maxLength ? text.slice(text.length - maxLength) : text;
}

async function run(options) {
  const chromePath = findBrowser(options.chromePath);
  if (!chromePath) {
    return {
      ok: false,
      status: "browser_executable_missing",
      contract: CONTRACT,
    };
  }

  const outDir = path.resolve(options.outDir);
  fs.mkdirSync(outDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const profileDir = path.join(os.tmpdir(), `francis-stage13-chrome-${stamp}`);
  const beforeScreenshot = path.join(outDir, `stage13-browser-readback-before-${stamp}.png`);
  const afterScreenshot = path.join(outDir, `stage13-browser-readback-after-${stamp}.png`);
  const stderrChunks = [];

  const chrome = spawn(chromePath, chromeArgs(options, profileDir), {
    stdio: ["ignore", "ignore", "pipe"],
  });
  chrome.stderr.on("data", (chunk) => stderrChunks.push(String(chunk)));
  const chromeExit = new Promise((resolve) => {
    chrome.once("exit", (code, signal) => {
      resolve({ code, signal });
    });
  });

  let cdp = null;
  try {
    const version = await Promise.race([
      waitForJson(`http://127.0.0.1:${options.debugPort}/json/version`, options.timeoutMs),
      chromeExit.then((exit) => {
        throw new Error(`Browser exited before DevTools became ready: ${JSON.stringify(exit)}`);
      }),
    ]);
    const target = await fetchJson(
      `http://127.0.0.1:${options.debugPort}/json/new?${encodeURIComponent(options.uiUrl)}`,
      { method: "PUT" },
      options.timeoutMs,
    );
    cdp = new CdpClient(target.webSocketDebuggerUrl);
    await cdp.open(options.timeoutMs);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await waitForEval(cdp, "document.body && document.body.innerText.includes('Approvals')", options.timeoutMs);

    const tabResult = await cdp.send("Runtime.evaluate", {
      expression: `(() => {
        const buttons = [...document.querySelectorAll("button")];
        const system = buttons.find((button) => (button.textContent || "").trim() === "System");
        if (!system) {
          return { clicked: false, buttons: buttons.slice(0, 40).map((button) => (button.textContent || "").trim()) };
        }
        system.click();
        return { clicked: true };
      })()`,
      returnByValue: true,
    });
    if (!tabResult.result?.value?.clicked) {
      throw new Error(`System tab not found: ${JSON.stringify(tabResult.result?.value)}`);
    }

    await waitForEval(cdp, browserVisibleExpression(), options.timeoutMs);
    await captureScreenshot(cdp, beforeScreenshot);

    const clickResult = await cdp.send("Runtime.evaluate", {
      expression: `(() => {
        const buttons = [...document.querySelectorAll("button")];
        const button = buttons.find((item) => (item.textContent || "").trim() === "Record visual readback");
        if (!button) {
          return { clicked: false, reason: "button_missing", body: document.body.innerText.slice(0, 2000) };
        }
        button.click();
        return { clicked: true };
      })()`,
      returnByValue: true,
    });
    if (!clickResult.result?.value?.clicked) {
      throw new Error(`Readback button not clicked: ${JSON.stringify(clickResult.result?.value)}`);
    }

    const notice = await waitForEval(
      cdp,
      `(() => {
        const body = document.body.innerText || "";
        const match = body.match(/Browser visual readback recorded as trust_calibration_browser_visual_[a-z0-9]+\\./);
        return match ? match[0] : false;
      })()`,
      options.timeoutMs,
    );
    await captureScreenshot(cdp, afterScreenshot);

    const status = await fetchJson(`${options.apiUrl}/trust-calibration/status`, {}, options.timeoutMs);
    const completionReview = await fetchJson(
      `${options.apiUrl}/trust-calibration/completion-review`,
      {},
      options.timeoutMs,
    );
    const readbacks = await fetchJson(
      `${options.apiUrl}/trust-calibration/operator-browser-visual-readbacks?limit=1`,
      {},
      options.timeoutMs,
    );
    return {
      ok: true,
      kind: "francis.stage13.trust_calibration.browser_readback_runner_result",
      contract: CONTRACT,
      chrome: {
        executable: chromePath,
        product: version.Browser || "",
        protocol_version: version["Protocol-Version"] || "",
      },
      notice,
      artifacts: {
        before_screenshot: beforeScreenshot,
        after_screenshot: afterScreenshot,
      },
      status: {
        status: status.status,
        ready_count: status.ready_count,
        required_count: status.required_count,
        operator_browser_visual_readback_observed: status.operator_browser_visual_readback_observed,
        latest_operator_browser_visual_readback_receipt_id: status.latest_operator_browser_visual_readback_receipt_id,
        next_smallest_truthful_gap: status.next_smallest_truthful_gap,
      },
      completion_review: {
        status: completionReview.status,
        stage13_completion_review_ready: completionReview.stage13_completion_review_ready,
        ready_count: completionReview.ready_count,
        required_count: completionReview.required_count,
        blockers: completionReview.blockers,
        next_smallest_truthful_gap: completionReview.next_smallest_truthful_gap,
      },
      latest_readback_receipt: readbacks.items?.[0] ?? null,
    };
  } catch (error) {
    return {
      ok: false,
      kind: "francis.stage13.trust_calibration.browser_readback_runner_result",
      status: "browser_readback_failed",
      error: error instanceof Error ? error.message : String(error),
      contract: CONTRACT,
      chrome: {
        executable: chromePath,
        stderr_tail: tail(stderrChunks.join("")),
        exit_code: chrome.exitCode,
      },
      writes_receipt: false,
      next_smallest_truthful_gap: "stage13_operator_browser_visual_readback",
    };
  } finally {
    if (cdp) {
      try {
        await cdp.send("Browser.close");
      } catch {
        // Best effort cleanup only.
      }
      cdp.close();
    }
    if (!chrome.killed) {
      chrome.kill();
    }
  }
}

function browserVisibleExpression() {
  return `(() => {
    const body = document.body.innerText || "";
    const card = document.getElementById("${CONTRACT.ui_surface_id}");
    const cardText = card ? card.innerText : "";
    return Boolean(
      card &&
      cardText.includes("Stage 13 calibration") &&
      cardText.includes("Record visual readback") &&
      body.includes("Missing verification") &&
      body.includes("Forbidden language") &&
      body.includes("Claim guards") &&
      body.includes("stage13_operator_browser_visual_readback") &&
      body.includes("side effects denied") &&
      body.includes("Completion review blocked")
    );
  })()`;
}

async function main() {
  const keepAlive = setInterval(() => {
    // Keep Node alive while browser/network probes are pending or failing early.
  }, 1000);
  const options = parseArgs(process.argv.slice(2));
  try {
    if (options.printContract) {
      console.log(JSON.stringify(CONTRACT, null, 2));
      return 0;
    }
    const result = await Promise.race([
      run(options),
      delay(options.timeoutMs + 5000).then(() => ({
        ok: false,
        kind: "francis.stage13.trust_calibration.browser_readback_runner_result",
        status: "browser_readback_runner_timeout",
        error: `Browser readback runner did not complete within ${options.timeoutMs + 5000}ms`,
        contract: CONTRACT,
        writes_receipt: false,
        next_smallest_truthful_gap: "stage13_operator_browser_visual_readback",
      })),
    ]);
    console.log(JSON.stringify(result, null, 2));
    return result.ok ? 0 : 1;
  } finally {
    clearInterval(keepAlive);
  }
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
