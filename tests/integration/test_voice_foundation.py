from fastapi.testclient import TestClient

from services.voice.app.main import app
import services.voice.app.operator as voice_operator


client = TestClient(app)


def test_voice_status_reports_modules() -> None:
    response = client.get("/voice/status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "voice"
    assert set(body["modules"]) == {"stt", "tts", "wakeword"}
    assert body["charter"]["receipts_required"] is True
    assert "/voice/briefing/live" in body["surfaces"]["briefing"]
    assert body["surfaces"]["command_preview"] == "/voice/command/preview"


def test_voice_stt_preview_normalizes_utterance() -> None:
    response = client.post(
        "/voice/stt/preview",
        json={"utterance": "  launch   mission   report  ", "locale": "en-US"},
    )

    assert response.status_code == 200
    preview = response.json()["preview"]
    assert preview["normalized_text"] == "launch mission report"
    assert preview["word_count"] == 3
    assert preview["trust"] == "Likely"


def test_voice_tts_briefing_uses_mode_contract() -> None:
    response = client.post(
        "/voice/tts/briefing",
        json={"objective": "Verify the service foundation slice", "mode": "pilot"},
    )

    assert response.status_code == 200
    briefing = response.json()["briefing"]
    assert "Pilot mode." in briefing
    assert "Objective: Verify the service foundation slice." in briefing
    assert "Claims remain tied to visible receipts and current scope." in briefing


def test_voice_live_briefing_uses_live_lens_state(monkeypatch) -> None:
    receipts: list[dict[str, object]] = []

    class StubLedger:
        def append(self, *, run_id: str, kind: str, summary: dict[str, object]) -> None:
            receipts.append({"run_id": run_id, "kind": kind, "summary": summary})

    monkeypatch.setattr(voice_operator, "_ledger", StubLedger())
    monkeypatch.setattr(
        voice_operator,
        "build_lens_snapshot",
        lambda: {
            "workspace_root": "D:/francis/workspace",
            "control": {"mode": "away", "kill_switch": False},
            "incidents": {"open_count": 2, "highest_severity": "high"},
            "approvals": {"pending_count": 1},
            "missions": {
                "active_count": 1,
                "active": [{"title": "Live Lens", "status": "active"}],
            },
            "inbox": {"alert_count": 1},
            "runs": {"last_run": {"summary": "Lens state is flowing live."}},
            "objective": {"label": "Live Lens"},
        },
    )
    monkeypatch.setattr(
        voice_operator,
        "get_lens_actions",
        lambda max_actions=3: {
            "status": "ok",
            "action_chips": [
                {
                    "kind": "observer.scan",
                    "label": "Run Observer Scan",
                    "risk_tier": "low",
                    "trust_badge": "Likely",
                    "reason": "Observer scan requested.",
                    "execute_via": {"endpoint": "/lens/actions/execute"},
                },
                {
                    "kind": "control.remote.approvals",
                    "label": "Review Pending Approvals",
                    "risk_tier": "low",
                    "trust_badge": "Confirmed",
                    "reason": "1 pending approval available.",
                    "execute_via": {"endpoint": "/lens/actions/execute"},
                },
            ],
        },
    )

    response = client.get("/voice/briefing/live", params={"mode": "away", "max_actions": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    briefing = payload["briefing"]
    assert briefing["mode"] == "away"
    assert "Incident pressure is high." in briefing["headline"]
    assert any("Control mode is away" in line for line in briefing["lines"])
    assert any("Recommended next actions: Run Observer Scan" in line for line in briefing["lines"])
    assert briefing["grounding"]["trust"] == "Confirmed"
    assert receipts[-1]["kind"] == "voice.live_briefing"


def test_voice_operator_presence_is_pure(monkeypatch) -> None:
    receipts: list[dict[str, object]] = []

    class StubLedger:
        def append(self, *, run_id: str, kind: str, summary: dict[str, object]) -> None:
            receipts.append({"run_id": run_id, "kind": kind, "summary": summary})

    monkeypatch.setattr(voice_operator, "_ledger", StubLedger())
    monkeypatch.setattr(
        voice_operator,
        "build_lens_snapshot",
        lambda: {
            "workspace_root": "D:/francis/workspace",
            "control": {"mode": "assist", "kill_switch": False},
            "incidents": {"open_count": 0, "highest_severity": "nominal"},
            "approvals": {"pending_count": 0},
            "missions": {"active_count": 0, "active": []},
            "inbox": {"alert_count": 0},
            "runs": {"last_run": {}},
            "objective": {"label": "Systematically build Francis"},
        },
    )
    monkeypatch.setattr(
        voice_operator,
        "get_lens_actions",
        lambda max_actions=3: {"status": "ok", "action_chips": [], "blocked_actions": []},
    )

    presence = voice_operator.build_operator_presence(mode="assist", max_actions=2)

    assert presence["surface"] == "voice"
    assert presence["mode"] == "assist"
    assert presence["receipt_mode"] == "explicit"
    assert receipts == []


def test_voice_command_preview_ranks_real_lens_actions(monkeypatch) -> None:
    receipts: list[dict[str, object]] = []

    class StubLedger:
        def append(self, *, run_id: str, kind: str, summary: dict[str, object]) -> None:
            receipts.append({"run_id": run_id, "kind": kind, "summary": summary})

    monkeypatch.setattr(voice_operator, "_ledger", StubLedger())
    monkeypatch.setattr(
        voice_operator,
        "get_lens_actions",
        lambda max_actions=5: {
            "status": "ok",
            "action_chips": [
                {
                    "kind": "control.panic",
                    "label": "Panic Stop (Kill Switch)",
                    "enabled": True,
                    "risk_tier": "high",
                    "trust_badge": "Confirmed",
                    "requires_confirmation": True,
                    "reason": "Instantly block all mutating actions.",
                    "execute_via": {"endpoint": "/lens/actions/execute"},
                },
                {
                    "kind": "observer.scan",
                    "label": "Run Observer Scan",
                    "enabled": True,
                    "risk_tier": "low",
                    "trust_badge": "Likely",
                    "reason": "Observer scan requested.",
                    "execute_via": {"endpoint": "/lens/actions/execute"},
                },
            ],
        },
    )

    response = client.post(
        "/voice/command/preview",
        json={"utterance": "panic stop the system now", "locale": "en-US", "max_actions": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    assert payload["intent"]["kind"] == "action.suggestion"
    assert payload["matches"][0]["kind"] == "control.panic"
    assert payload["matches"][0]["requires_confirmation"] is True
    assert payload["governance"]["execution"] == "not_performed"
    assert receipts[-1]["kind"] == "voice.command.preview"


def test_voice_command_preview_briefing_request_does_not_emit_live_briefing_receipt(monkeypatch) -> None:
    receipts: list[dict[str, object]] = []

    class StubLedger:
        def append(self, *, run_id: str, kind: str, summary: dict[str, object]) -> None:
            receipts.append({"run_id": run_id, "kind": kind, "summary": summary})

    monkeypatch.setattr(voice_operator, "_ledger", StubLedger())
    monkeypatch.setattr(
        voice_operator,
        "build_lens_snapshot",
        lambda: {
            "workspace_root": "D:/francis/workspace",
            "control": {"mode": "assist", "kill_switch": False},
            "incidents": {"open_count": 0, "highest_severity": "nominal"},
            "approvals": {"pending_count": 1},
            "missions": {"active_count": 1, "active": [{"title": "Live Lens", "status": "active"}]},
            "inbox": {"alert_count": 0},
            "runs": {"last_run": {"summary": "Lens state is flowing live."}},
            "objective": {"label": "Live Lens"},
        },
    )
    monkeypatch.setattr(
        voice_operator,
        "get_lens_actions",
        lambda max_actions=5: {"status": "ok", "action_chips": [], "blocked_actions": []},
    )

    response = client.post(
        "/voice/command/preview",
        json={"utterance": "status report", "locale": "en-US", "max_actions": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"]["kind"] == "briefing.request"
    assert payload["briefing"]["surface"] == "voice"
    assert [receipt["kind"] for receipt in receipts] == ["voice.command.preview"]
