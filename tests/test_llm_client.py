from __future__ import annotations

from francis.llm import client


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_generate_prefers_francis_ollama_env(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_OLLAMA_BASE_URL", "http://127.0.0.1:11434/")
    monkeypatch.setenv("FRANCIS_LLM_CHAT_MODEL", "francis-chat")
    monkeypatch.setenv("FRANCIS_LLM_REQUEST_TIMEOUT_S", "90")
    monkeypatch.delenv("FRANCIS_LLM_NUM_CTX", raising=False)
    monkeypatch.delenv("FRANCIS_LLM_NUM_PREDICT", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("LLM_REQUEST_TIMEOUT_S", raising=False)
    monkeypatch.delenv("OLLAMA_NUM_CTX", raising=False)
    monkeypatch.delenv("OLLAMA_NUM_PREDICT", raising=False)

    captured: dict[str, object] = {}

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"response": "ok"})

    monkeypatch.setattr(client.httpx, "post", fake_post)

    assert client.generate("say only ok") == "ok"
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["timeout"] == 90
    assert captured["json"] == {
        "model": "francis-chat",
        "prompt": "say only ok",
        "stream": False,
        "options": {
            "num_ctx": 8192,
            "num_predict": 512,
        },
    }


def test_generate_accepts_explicit_model_override(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("FRANCIS_LLM_CHAT_MODEL", "francis-chat")

    captured: dict[str, object] = {}

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"response": "ok"})

    monkeypatch.setattr(client.httpx, "post", fake_post)

    assert client.generate("say only ok", model="llama3.2:3b", timeout_seconds=12) == "ok"
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["timeout"] == 12
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "llama3.2:3b"


def test_resolve_ollama_config_falls_back_to_legacy_env(monkeypatch) -> None:
    monkeypatch.delenv("FRANCIS_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("FRANCIS_LLM_CHAT_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:7b-instruct")

    base, model = client.resolve_ollama_config()

    assert base == "http://localhost:11434"
    assert model == "qwen2.5:7b-instruct"


def test_resolve_ollama_timeout_seconds_uses_bounded_francis_env(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_LLM_REQUEST_TIMEOUT_S", "600")
    monkeypatch.delenv("LLM_REQUEST_TIMEOUT_S", raising=False)

    assert client.resolve_ollama_timeout_seconds() == 300


def test_resolve_ollama_timeout_seconds_falls_back_to_legacy_env(monkeypatch) -> None:
    monkeypatch.delenv("FRANCIS_LLM_REQUEST_TIMEOUT_S", raising=False)
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_S", "75")

    assert client.resolve_ollama_timeout_seconds() == 75


def test_resolve_ollama_options_uses_bounded_francis_env(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_LLM_NUM_CTX", "999999")
    monkeypatch.setenv("FRANCIS_LLM_NUM_PREDICT", "8")
    monkeypatch.delenv("OLLAMA_NUM_CTX", raising=False)
    monkeypatch.delenv("OLLAMA_NUM_PREDICT", raising=False)

    assert client.resolve_ollama_options() == {
        "num_ctx": 32768,
        "num_predict": 128,
    }


def test_resolve_ollama_options_falls_back_to_legacy_env(monkeypatch) -> None:
    monkeypatch.delenv("FRANCIS_LLM_NUM_CTX", raising=False)
    monkeypatch.delenv("FRANCIS_LLM_NUM_PREDICT", raising=False)
    monkeypatch.setenv("OLLAMA_NUM_CTX", "4096")
    monkeypatch.setenv("OLLAMA_NUM_PREDICT", "768")

    assert client.resolve_ollama_options() == {
        "num_ctx": 4096,
        "num_predict": 768,
    }


def test_resolve_ollama_config_uses_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("FRANCIS_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("FRANCIS_LLM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_DEFAULT_MODEL", raising=False)

    class _FakeSettings:
        ollama_base_url = "http://127.0.0.1:11434"
        ollama_default_model = "francis-chat"
        llm_request_timeout_seconds = 90

    monkeypatch.setattr(client, "Settings", _FakeSettings)

    base, model = client.resolve_ollama_config()

    assert base == "http://127.0.0.1:11434"
    assert model == "francis-chat"
