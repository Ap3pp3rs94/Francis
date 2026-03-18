from __future__ import annotations

from francis_llm import (
    DEFAULT_OLLAMA_FAST_MODEL,
    DEFAULT_OLLAMA_HEAVY_MODEL,
    build_chat_request,
    build_generate_request,
    get_ollama_host,
    resolve_route,
    route_model,
)


def test_route_model_prefers_fast_local_model_for_operator_loops() -> None:
    assert route_model("lens.current_work.operator_loop") == DEFAULT_OLLAMA_FAST_MODEL


def test_route_model_prefers_heavy_local_model_for_analysis_and_scaffolding() -> None:
    assert route_model("capability.scaffolding.analysis") == DEFAULT_OLLAMA_HEAVY_MODEL


def test_resolve_route_keeps_local_fallback_between_fast_and_heavy_models() -> None:
    route = resolve_route("knowledge_fabric.analysis")

    assert route.provider == "ollama"
    assert route.model == DEFAULT_OLLAMA_HEAVY_MODEL
    assert route.fallback_provider == "ollama"
    assert route.fallback_model == DEFAULT_OLLAMA_FAST_MODEL
    assert route.local_first is True
    assert "heavy-work" in route.reason


def test_route_respects_explicit_ollama_model_overrides() -> None:
    env = {
        "FRANCIS_PROVIDER": "ollama",
        "FRANCIS_OLLAMA_FAST_MODEL": "llama3.2:3b",
        "FRANCIS_OLLAMA_HEAVY_MODEL": "phi4:14b-q6",
    }

    assert route_model("hud.summary", env=env) == "llama3.2:3b"
    assert route_model("architecture.review", env=env) == "phi4:14b-q6"


def test_get_ollama_host_uses_governed_host_override() -> None:
    assert get_ollama_host({"FRANCIS_OLLAMA_HOST": "http://127.0.0.1:11434"}) == "http://127.0.0.1:11434"


def test_local_ollama_request_builders_follow_router_model_selection() -> None:
    generate_payload = build_generate_request(
        "capability.scaffolding",
        "Explain the staged pack boundary.",
    )
    chat_payload = build_chat_request(
        "current_work.next_action",
        [{"role": "user", "content": "What matters now?"}],
    )

    assert generate_payload["model"] == DEFAULT_OLLAMA_HEAVY_MODEL
    assert generate_payload["stream"] is False
    assert chat_payload["model"] == DEFAULT_OLLAMA_FAST_MODEL
    assert chat_payload["messages"][0]["role"] == "user"
