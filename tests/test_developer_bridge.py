from __future__ import annotations

from fastapi.routing import APIRoute
import pytest

from francis.developer_bridge.repo_tools import (
    DeveloperBridgeError,
    read_repo_file,
    read_supervised_exec_receipt,
    search_repo,
)


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n")




def test_read_repo_file_is_repo_bounded_and_text_only(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_ROOT", str(tmp_path))
    target = tmp_path / "docs" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_text("Francis bridge note\n", encoding="utf-8")

    result = read_repo_file("docs/note.md")

    assert result["ok"] is True
    assert result["path"] == "docs/note.md"
    assert _normalize_newlines(result["content"]) == "Francis bridge note\n"
    assert result["truncated"] is False
    assert isinstance(result["sha256"], str)


def test_read_repo_file_denies_traversal_and_sensitive_paths(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_ROOT", str(tmp_path))
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")

    with pytest.raises(DeveloperBridgeError) as traversal:
        read_repo_file("../outside.txt")
    assert traversal.value.code == "path_traversal_denied"

    with pytest.raises(DeveloperBridgeError) as sensitive:
        read_repo_file(".env")
    assert sensitive.value.code == "sensitive_file_denied"


def test_search_repo_skips_sensitive_files(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_ROOT", str(tmp_path))
    public = tmp_path / "src" / "visible.txt"
    public.parent.mkdir(parents=True)
    public.write_text("developer bridge search needle\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("needle=secret\n", encoding="utf-8")

    result = search_repo("needle")

    assert result["ok"] is True
    assert result["results"] == [{"path": "src/visible.txt", "line": 1, "preview": "developer bridge search needle"}]
    assert result["skipped_sensitive"] == 1


def test_read_supervised_exec_receipt_is_bounded_to_artifact_root(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    receipt = tmp_path / "data" / "artifacts" / "supervised_exec" / "run-123" / "result.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"ok": true}\n', encoding="utf-8")

    result = read_supervised_exec_receipt("run-123", "result.json")

    assert result["ok"] is True
    assert result["run_id"] == "run-123"
    assert result["filename"] == "result.json"
    assert _normalize_newlines(result["content"]) == '{"ok": true}\n'

    with pytest.raises(DeveloperBridgeError) as bad_run_id:
        read_supervised_exec_receipt("../run-123", "result.json")
    assert bad_run_id.value.code == "run_id_denied"

    with pytest.raises(DeveloperBridgeError) as bad_filename:
        read_supervised_exec_receipt("run-123", "secrets.txt")
    assert bad_filename.value.code == "filename_denied"


def test_developer_bridge_routes_are_mounted() -> None:
    from francis.api.app import create_app

    app = create_app()
    routes = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/developer-bridge/status" in routes
    assert "/developer-bridge/read-file" in routes
    assert "/developer-bridge/search" in routes
    assert "/developer-bridge/git-diff-summary" in routes
    assert "/developer-bridge/completion-ledger" in routes
    assert "/developer-bridge/supervised-exec-receipt" in routes
