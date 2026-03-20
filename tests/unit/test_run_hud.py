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

    def fake_run(app, **kwargs) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(run_hud.uvicorn, "run", fake_run)

    run_hud.main()

    assert captured["app"] is run_hud.hud_app
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8767
    assert captured["log_level"] == "warning"
    assert captured["reload"] is False
    assert captured["workers"] == 1
