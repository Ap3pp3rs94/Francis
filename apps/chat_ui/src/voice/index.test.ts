import assert from "node:assert/strict";
import test from "node:test";

import {
  FRANCIS_BROWSER_VOICE_ACTOR,
  FRANCIS_BROWSER_VOICE_CLIENT_ORIGIN,
  FrancisVoiceClient,
  buildVoiceIngressPayload,
  classifyVoiceSound,
  classifyVoiceTranscript,
  isFrancisStopPhrase,
} from "./index.ts";

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function installFetch(handler: FetchHandler): () => void {
  const globals = globalThis as typeof globalThis & { fetch?: typeof fetch };
  const originalFetch = globals.fetch;

  globals.fetch = (async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = input instanceof Request ? input.url : input.toString();
    return await handler(url, init);
  }) as typeof fetch;

  return () => {
    if (originalFetch) {
      globals.fetch = originalFetch;
      return;
    }
    delete globals.fetch;
  };
}

test("classifyVoiceTranscript wakes only when the transcript targets Francis", () => {
  const passive = classifyVoiceTranscript("there is a truck outside");
  assert.equal(passive.kind, "passive");
  assert.equal(passive.forward_to_chat, false);
  assert.equal(passive.use_llm, false);

  const wake = classifyVoiceTranscript("Francis can you hear me");
  assert.equal(wake.kind, "wake");
  assert.equal(wake.wake_phrase_detected, true);
  assert.equal(wake.forward_to_chat, true);
  assert.equal(wake.use_llm, true);
});

test("classifyVoiceSound treats sound without speech as awareness only", () => {
  const noise = classifyVoiceSound({
    soundObserved: true,
    speechObserved: false,
    transcript: "",
  });

  assert.equal(noise.kind, "noise");
  assert.equal(noise.awareness_state, "ambient_noise_observed");
  assert.equal(noise.forward_to_chat, false);
});

test("isFrancisStopPhrase recognizes only bounded Francis stop interrupts", () => {
  assert.equal(isFrancisStopPhrase("Francis stop"), true);
  assert.equal(isFrancisStopPhrase("hey Francis stop"), true);
  assert.equal(isFrancisStopPhrase("Frances stop"), true);
  assert.equal(isFrancisStopPhrase("stop"), false);
  assert.equal(isFrancisStopPhrase("Francis please stop talking"), false);
});

test("buildVoiceIngressPayload marks browser voice origin without claiming ChatGPT app origin", () => {
  const payload = buildVoiceIngressPayload({
    transcript: "Francis hello",
    forward_to_chat: true,
    use_llm: true,
    turn_id: "turn_ui_voice",
  });

  assert.equal(payload.actor, FRANCIS_BROWSER_VOICE_ACTOR);
  assert.equal(payload.source, "chat_ui.voice");
  assert.equal(payload.client_origin, FRANCIS_BROWSER_VOICE_CLIENT_ORIGIN);
  assert.equal(payload.turn_id, "turn_ui_voice");
  assert.equal(payload.forward_to_chat, true);
  assert.equal(payload.use_llm, true);
});

test("FrancisVoiceClient posts passive transcripts without chat forwarding", async () => {
  let capturedBody: Record<string, unknown> | null = null;
  const restoreFetch = installFetch(async (url, init) => {
    assert.equal(url, "http://127.0.0.1:8000/chatgpt-voice/ingress");
    capturedBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return jsonResponse({
      ok: true,
      status: "recorded",
      reply: "I recorded the transcript for Francis. Chat forwarding was not requested.",
    });
  });

  try {
    const client = new FrancisVoiceClient("http://127.0.0.1:8000/");
    const result = await client.recordTranscript({
      transcript: "ambient room speech",
      forward_to_chat: false,
      use_llm: false,
      turn_id: "turn_passive",
    });

    assert.equal(result.ok, true);
    assert.equal(capturedBody?.actor, FRANCIS_BROWSER_VOICE_ACTOR);
    assert.equal(capturedBody?.client_origin, FRANCIS_BROWSER_VOICE_CLIENT_ORIGIN);
    assert.equal(capturedBody?.forward_to_chat, false);
    assert.equal(capturedBody?.use_llm, false);
  } finally {
    restoreFetch();
  }
});
