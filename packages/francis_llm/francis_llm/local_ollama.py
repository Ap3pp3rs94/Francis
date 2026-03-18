from __future__ import annotations

import json
from typing import Any, Mapping, Sequence
from urllib import request

from .router import get_ollama_host, resolve_route


def build_generate_request(
    task: str,
    prompt: str,
    *,
    system: str | None = None,
    env: Mapping[str, str] | None = None,
    model: str | None = None,
    stream: bool = False,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    route = resolve_route(task, env=env)
    payload: dict[str, Any] = {
        "model": model or route.model,
        "prompt": prompt,
        "stream": stream,
    }
    if system:
        payload["system"] = system
    if options:
        payload["options"] = dict(options)
    return payload


def build_chat_request(
    task: str,
    messages: Sequence[Mapping[str, Any]],
    *,
    env: Mapping[str, str] | None = None,
    model: str | None = None,
    stream: bool = False,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    route = resolve_route(task, env=env)
    payload: dict[str, Any] = {
        "model": model or route.model,
        "messages": [dict(message) for message in messages],
        "stream": stream,
    }
    if options:
        payload["options"] = dict(options)
    return payload


def _post_json(
    path: str,
    payload: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    timeout: float = 120.0,
) -> Any:
    host = get_ollama_host(env)
    endpoint = f"{host.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    if not raw.strip():
        return {}
    if bool(payload.get("stream")):
        return [json.loads(line) for line in raw.splitlines() if line.strip()]
    return json.loads(raw)


def generate(
    task: str,
    prompt: str,
    *,
    system: str | None = None,
    env: Mapping[str, str] | None = None,
    model: str | None = None,
    stream: bool = False,
    options: Mapping[str, Any] | None = None,
    timeout: float = 120.0,
) -> Any:
    payload = build_generate_request(
        task,
        prompt,
        system=system,
        env=env,
        model=model,
        stream=stream,
        options=options,
    )
    return _post_json("/api/generate", payload, env=env, timeout=timeout)


def chat(
    task: str,
    messages: Sequence[Mapping[str, Any]],
    *,
    env: Mapping[str, str] | None = None,
    model: str | None = None,
    stream: bool = False,
    options: Mapping[str, Any] | None = None,
    timeout: float = 120.0,
) -> Any:
    payload = build_chat_request(
        task,
        messages,
        env=env,
        model=model,
        stream=stream,
        options=options,
    )
    return _post_json("/api/chat", payload, env=env, timeout=timeout)


__all__ = [
    "build_chat_request",
    "build_generate_request",
    "chat",
    "generate",
]
