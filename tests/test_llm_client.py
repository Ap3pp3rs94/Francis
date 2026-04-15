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
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_DEFAULT_MODEL", raising=False)

    captured: dict[str, object] = {}

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"response": "ok"})

    monkeypatch.setattr(client.httpx, "post", fake_post)

    assert client.generate("say only ok") == "ok"
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["timeout"] == 45
    assert captured["json"] == {
        "model": "francis-chat",
        "prompt": "say only ok",
        "stream": False,
    }


def test_resolve_ollama_config_falls_back_to_legacy_env(monkeypatch) -> None:
    monkeypatch.delenv("FRANCIS_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("FRANCIS_LLM_CHAT_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:7b-instruct")

    base, model = client.resolve_ollama_config()

    assert base == "http://localhost:11434"
    assert model == "qwen2.5:7b-instruct"


def test_resolve_ollama_config_uses_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("FRANCIS_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("FRANCIS_LLM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_DEFAULT_MODEL", raising=False)

    class _FakeSettings:
        ollama_base_url = "http://127.0.0.1:11434"
        ollama_default_model = "francis-chat"

    monkeypatch.setattr(client, "Settings", _FakeSettings)

    base, model = client.resolve_ollama_config()

    assert base == "http://127.0.0.1:11434"
    assert model == "francis-chat"
