import assert from "node:assert/strict";
import test from "node:test";

import { TrustApiError, TrustClient } from "./index.ts";

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

test("TrustClient.adjust sends an explicit trust mutation actor", async () => {
  let capturedBody: Record<string, unknown> | null = null;
  const restoreFetch = installFetch(async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({ ok: true, status: "applied", applied: true, level: 3 });
  });

  try {
    const client = new TrustClient("http://127.0.0.1:8000", { mutationsEnabled: true, retry: { retries: 0 } });
    const result = await client.adjust({ op: "set", value: 3, reason: "test" });

    assert.equal(result.ok, true);
    assert.equal(result.level, 3);
    assert.equal(capturedBody?.op, "set");
    assert.equal(capturedBody?.actor, "chat_ui.trust");
  } finally {
    restoreFetch();
  }
});

test("TrustClient.adjust treats backend denials as mutation errors", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({ ok: false, status: "denied", error: "api_permission_denied" }),
  );

  try {
    const client = new TrustClient("http://127.0.0.1:8000", { mutationsEnabled: true, retry: { retries: 0 } });

    await assert.rejects(
      () => client.adjust({ op: "set", value: 3, actor: "chat_ui.trust" }),
      (err: unknown) => err instanceof TrustApiError && err.message === "api_permission_denied",
    );
  } finally {
    restoreFetch();
  }
});
