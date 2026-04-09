from pathlib import Path

from services.orchestrator.app.lens_snapshot import build_lens_snapshot


def test_lens_snapshot_profile_is_opt_in(tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()

    payload = build_lens_snapshot(workspace_root, profile=True)
    profile = payload.get("build_profile", {})
    phase_names = {str(phase.get("name", "")) for phase in profile.get("phases", [])}

    assert profile["surface"] == "lens_snapshot_profile"
    assert profile["total_ms"] >= 0
    assert profile["phase_count"] >= len(phase_names) >= 8
    assert profile["slowest"]
    assert profile["reused"]["approval_snapshot"] is False
    assert {"approval_snapshot", "control", "missions", "current_work", "next_best_action"} <= phase_names
    assert payload["fabric"]["pending"] is True

    plain_payload = build_lens_snapshot(workspace_root)
    assert plain_payload["fabric"]["pending"] is True
    assert "build_profile" not in plain_payload


def test_lens_snapshot_jsonl_cache_invalidates_when_file_changes(tmp_path: Path) -> None:
    workspace_root = (tmp_path / "workspace").resolve()
    inbox_path = workspace_root / "inbox" / "messages.jsonl"
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(
        '{"id":"msg-1","ts":"2026-04-09T10:00:00+00:00","title":"One","severity":"info"}\n',
        encoding="utf-8",
    )

    first = build_lens_snapshot(workspace_root)
    assert first["inbox"]["count"] == 1

    inbox_path.write_text(
        "\n".join(
            [
                '{"id":"msg-1","ts":"2026-04-09T10:00:00+00:00","title":"One","severity":"info"}',
                '{"id":"msg-2","ts":"2026-04-09T10:01:00+00:00","title":"Two","severity":"alert"}',
                "",
            ]
        ),
        encoding="utf-8",
    )

    second = build_lens_snapshot(workspace_root)
    assert second["inbox"]["count"] == 2
    assert second["inbox"]["alert_count"] == 1
