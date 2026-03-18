from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping


FAST_ROLE = "fast"
HEAVY_ROLE = "heavy"
DEFAULT_PROVIDER = "ollama"
DEFAULT_OLLAMA_FAST_MODEL = "llama3.1:8b"
DEFAULT_OLLAMA_HEAVY_MODEL = "phi4:14b"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"

_FAST_TASK_HINTS = (
    "action.deck",
    "approval",
    "brief",
    "current_work",
    "dashboard",
    "execution_feed",
    "handback",
    "hud",
    "inbox",
    "interject",
    "journal",
    "lens",
    "next_action",
    "operator_loop",
    "orb",
    "panic",
    "receipt",
    "repo.diff",
    "repo.lint",
    "repo.status",
    "repo.tests",
    "runs",
    "shift_report",
    "status",
    "summary",
    "swarm",
    "triage",
)

_HEAVY_TASK_HINTS = (
    "analysis",
    "apprenticeship",
    "architecture",
    "capability",
    "codegen",
    "connector_library",
    "dependency_library",
    "eval",
    "fabric",
    "federation",
    "forge",
    "long_context",
    "mission",
    "plan",
    "reason",
    "refactor",
    "review",
    "scaffold",
    "synthesis",
    "teaching",
)


@dataclass(frozen=True)
class ModelRoute:
    task: str
    normalized_task: str
    provider: str
    model: str
    role: str
    reason: str
    fallback_provider: str | None
    fallback_model: str | None
    ollama_host: str | None
    local_first: bool


def _read_env(env: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = str(env.get(key, "")).strip()
        if value:
            return value
    return ""


def _normalize_provider(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"local", "ollama"}:
        return "ollama"
    if normalized in {"llama.cpp", "llama_cpp", "llamacpp"}:
        return "llamacpp"
    if normalized in {"gpt", "openai"}:
        return "openai"
    if normalized in {"claude", "anthropic"}:
        return "anthropic"
    return normalized or DEFAULT_PROVIDER


def _provider_env_stem(provider: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", provider.upper())


def _parse_fallback_providers(env: Mapping[str, str], active_provider: str) -> list[str]:
    raw = _read_env(
        env,
        "FRANCIS_PROVIDER_FALLBACKS",
        "FRANCIS_LLM_FALLBACKS",
        "FRANCIS_MODEL_FALLBACKS",
    )
    if not raw:
        return []
    seen: set[str] = set()
    values: list[str] = []
    for part in raw.split(","):
        provider = _normalize_provider(part)
        if not provider or provider == active_provider or provider in seen:
            continue
        seen.add(provider)
        values.append(provider)
    return values


def normalize_task_name(task: str) -> str:
    compact = re.sub(r"[\s/_-]+", ".", str(task or "").strip().lower())
    return re.sub(r"\.+", ".", compact).strip(".")


def classify_task_role(task: str) -> tuple[str, str]:
    normalized = normalize_task_name(task)
    for hint in _HEAVY_TASK_HINTS:
        if hint in normalized:
            return HEAVY_ROLE, f"Task matched heavy-work hint '{hint}'."
    for hint in _FAST_TASK_HINTS:
        if hint in normalized:
            return FAST_ROLE, f"Task matched fast-loop hint '{hint}'."
    return FAST_ROLE, "Task did not match a heavy-work hint, so Francis keeps the operator loop responsive."


def _resolve_model_for_role(provider: str, role: str, env: Mapping[str, str]) -> str:
    provider_stem = _provider_env_stem(provider)
    keys = (
        f"FRANCIS_{provider_stem}_{role.upper()}_MODEL",
        f"{provider_stem}_{role.upper()}_MODEL",
        f"FRANCIS_LOCAL_{role.upper()}_MODEL",
        f"FRANCIS_{role.upper()}_MODEL",
    )
    configured = _read_env(env, *keys)
    if configured:
        return configured

    if provider == "ollama":
        return DEFAULT_OLLAMA_HEAVY_MODEL if role == HEAVY_ROLE else DEFAULT_OLLAMA_FAST_MODEL

    return f"{provider}:{role}"


def get_ollama_host(env: Mapping[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    return _read_env(source, "FRANCIS_OLLAMA_HOST", "OLLAMA_HOST", "OLLAMA_BASE_URL") or DEFAULT_OLLAMA_HOST


def resolve_route(task: str, env: Mapping[str, str] | None = None) -> ModelRoute:
    source = env if env is not None else os.environ
    provider = _normalize_provider(
        _read_env(source, "FRANCIS_PROVIDER", "FRANCIS_LLM_PROVIDER", "FRANCIS_MODEL_PROVIDER")
    )
    role, reason = classify_task_role(task)
    model = _resolve_model_for_role(provider, role, source)
    alternate_role = FAST_ROLE if role == HEAVY_ROLE else HEAVY_ROLE
    fallback_model = _resolve_model_for_role(provider, alternate_role, source)
    fallback_providers = _parse_fallback_providers(source, provider)
    fallback_provider = fallback_providers[0] if fallback_providers else provider

    return ModelRoute(
        task=str(task or ""),
        normalized_task=normalize_task_name(task),
        provider=provider,
        model=model,
        role=role,
        reason=reason,
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
        ollama_host=get_ollama_host(source) if provider == "ollama" or fallback_provider == "ollama" else None,
        local_first=provider in {"ollama", "llamacpp"},
    )


def route_model(task: str, env: Mapping[str, str] | None = None) -> str:
    return resolve_route(task, env=env).model


__all__ = [
    "DEFAULT_OLLAMA_FAST_MODEL",
    "DEFAULT_OLLAMA_HEAVY_MODEL",
    "DEFAULT_OLLAMA_HOST",
    "FAST_ROLE",
    "HEAVY_ROLE",
    "ModelRoute",
    "classify_task_role",
    "get_ollama_host",
    "normalize_task_name",
    "resolve_route",
    "route_model",
]
