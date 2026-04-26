import assert from "node:assert/strict";
import test from "node:test";

import { CredentialManagerApiError, CredentialManagerClient } from "./index.ts";

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

test("CredentialManagerClient.requestCredential sends an explicit credential actor", async () => {
  let capturedBody: Record<string, unknown> | null = null;
  const restoreFetch = installFetch(async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({ ok: true, request_id: "creq_test", approval_id: "apr_test", status: "pending" });
  });

  try {
    const client = new CredentialManagerClient("http://127.0.0.1:8000", { defaultTimeoutMs: 100 });
    const result = await client.requestCredential({
      scope_id: "openai_readonly",
      provider: "openai",
      reason: "test",
    });

    assert.equal(result.ok, true);
    assert.equal(result.approval_id, "apr_test");
    assert.equal(capturedBody?.scope_id, "openai_readonly");
    assert.equal(capturedBody?.actor, "chat_ui.credentials");
  } finally {
    restoreFetch();
  }
});

test("CredentialManagerClient.revokeCredential sends an explicit credential actor", async () => {
  let capturedBody: Record<string, unknown> | null = null;
  const restoreFetch = installFetch(async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({ ok: true, id: "cred_test", status: "pending" });
  });

  try {
    const client = new CredentialManagerClient("http://127.0.0.1:8000", { defaultTimeoutMs: 100 });
    const result = await client.revokeCredential({ id: "cred_test", reason: "cleanup" });

    assert.equal(result.ok, true);
    assert.equal(result.id, "cred_test");
    assert.equal(capturedBody?.id, "cred_test");
    assert.equal(capturedBody?.actor, "chat_ui.credentials");
  } finally {
    restoreFetch();
  }
});

test("CredentialManagerClient treats backend denials as mutation errors", async () => {
  const restoreFetch = installFetch(async () =>
    jsonResponse({ ok: false, status: "denied", error: "api_permission_denied" }),
  );

  try {
    const client = new CredentialManagerClient("http://127.0.0.1:8000", { defaultTimeoutMs: 100 });

    await assert.rejects(
      () => client.requestCredential({ scope_id: "openai_readonly", actor: "chat_ui.credentials" }),
      (err: unknown) => err instanceof CredentialManagerApiError && err.message === "api_permission_denied",
    );
  } finally {
    restoreFetch();
  }
});
