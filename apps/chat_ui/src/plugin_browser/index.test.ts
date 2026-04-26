import assert from "node:assert/strict";
import test from "node:test";

import { PluginBrowserApiError, PluginBrowserClient } from "./index.ts";

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function installFetch(handler: FetchHandler): () => void {
  const globals = globalThis as typeof globalThis & {
    fetch?: typeof fetch;
    window?: { setTimeout: typeof setTimeout; clearTimeout: typeof clearTimeout };
  };
  const originalFetch = globals.fetch;
  const originalWindow = globals.window;

  globals.window = {
    setTimeout,
    clearTimeout,
  };
  globals.fetch = (async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = input instanceof Request ? input.url : input.toString();
    return await handler(url, init);
  }) as typeof fetch;

  return () => {
    if (originalFetch) {
      globals.fetch = originalFetch;
    } else {
      delete globals.fetch;
    }
    if (originalWindow) {
      globals.window = originalWindow;
    } else {
      delete globals.window;
    }
  };
}

test("PluginBrowserClient lifecycle mutations send an explicit plugin actor", async () => {
  const captured: Record<string, Record<string, unknown>> = {};
  const restoreFetch = installFetch(async (url, init) => {
    captured[new URL(url).pathname] = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({ ok: true, id: "pl_echo", plugin_id: "pl_echo", enabled: true, status: "enabled" });
  });

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    await client.enable({ id: "pl_echo" });
    await client.disable({ id: "pl_echo" });
    await client.install({ source_kind: "registry", source_ref: "acme/echo" });
    await client.uninstall({ id: "pl_echo" });
    await client.reload();

    assert.equal(captured["/plugins/enable"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/disable"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/install"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/uninstall"]?.actor, "chat_ui.plugins");
    assert.equal(captured["/plugins/reload"]?.actor, "chat_ui.plugins");
  } finally {
    restoreFetch();
  }
});

test("PluginBrowserClient treats backend permission denials as mutation errors", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({ ok: false, status: "denied", error: "api_permission_denied" }),
  );

  try {
    const client = new PluginBrowserClient("http://127.0.0.1:8000", { retry: { retries: 0 } });

    await assert.rejects(
      () => client.install({ source_kind: "registry", source_ref: "acme/echo", actor: "chat_ui.plugins" }),
      (err: unknown) => err instanceof PluginBrowserApiError && err.message === "api_permission_denied",
    );
  } finally {
    restoreFetch();
  }
});
