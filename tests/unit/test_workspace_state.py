from __future__ import annotations

from pathlib import Path

from tests.integration import workspace_state


def test_isolated_workspace_files_truncates_append_only_runtime_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(workspace_state, "WORKSPACE_ROOT", tmp_path)
    journal_path = tmp_path / "journals" / "fs.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text("original\n", encoding="utf-8")

    with workspace_state.isolated_workspace_files(("journals/fs.jsonl",)):
        with journal_path.open("a", encoding="utf-8") as handle:
            handle.write("added\n")

    assert journal_path.read_text(encoding="utf-8") == "original\n"


def test_isolated_workspace_files_restores_directory_tree(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(workspace_state, "WORKSPACE_ROOT", tmp_path)
    portability_dir = tmp_path / "portability"
    original_file = portability_dir / "imports" / "bundle.json"
    original_file.parent.mkdir(parents=True, exist_ok=True)
    original_file.write_text("{\"status\":\"original\"}\n", encoding="utf-8")

    with workspace_state.isolated_workspace_files(("portability",)):
        original_file.unlink()
        replacement = portability_dir / "imports" / "replacement.json"
        replacement.write_text("{\"status\":\"temporary\"}\n", encoding="utf-8")

    assert original_file.read_text(encoding="utf-8") == "{\"status\":\"original\"}\n"
    assert not (portability_dir / "imports" / "replacement.json").exists()
