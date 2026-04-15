from __future__ import annotations

from francis.settings import Settings


def test_settings_reads_canonical_francis_env_aliases(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "workstation")
    monkeypatch.setenv("FRANCIS_API_HOST", "0.0.0.0")
    monkeypatch.setenv("FRANCIS_API_PORT", "8010")
    monkeypatch.setenv("FRANCIS_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("FRANCIS_LLM_CHAT_MODEL", "francis-chat")

    settings = Settings()

    assert settings.francis_env == "workstation"
    assert settings.francis_api_host == "0.0.0.0"
    assert settings.francis_api_port == 8010
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_default_model == "francis-chat"
