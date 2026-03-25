from __future__ import annotations

from types import SimpleNamespace

from services.hud.app import run_hud


def test_run_hud_main_runs_imported_fastapi_app(monkeypatch) -> None:
    parser = SimpleNamespace(
        parse_args=lambda: SimpleNamespace(
            host="127.0.0.1",
            port=8767,
            log_level="warning",
        )
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(run_hud, "build_parser", lambda: parser)

    def fake_config(app, **kwargs):
        captured["app"] = app
        captured.update(kwargs)
        return SimpleNamespace(app=app, **kwargs)

    class FakeServer:
        def __init__(self, config) -> None:
            captured["config"] = config

        def run(self) -> None:
            captured["server_run_called"] = True

    monkeypatch.setattr(run_hud.uvicorn, "Config", fake_config)
    monkeypatch.setattr(run_hud.uvicorn, "Server", FakeServer)

    run_hud.main()

    assert captured["app"] is run_hud.hud_app
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8767
    assert captured["log_level"] == "warning"
    assert captured["reload"] is False
    assert captured["workers"] == 1
    assert captured["server_run_called"] is True
