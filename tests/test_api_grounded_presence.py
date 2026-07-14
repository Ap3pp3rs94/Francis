from __future__ import annotations

import json


def test_continuity_presence_route_composes_grounded_readbacks(monkeypatch) -> None:
    from francis.api.routes import continuity

    monkeypatch.setattr(
        continuity,
        "mission_continuity_snapshot",
        lambda **_: {
            "mission_briefing": {
                "headline": "Continue from the grounded handoff.",
                "focus": [{"id": "mission_1", "title": "Handoff", "status": "queued"}],
                "memory_receipts": [{"receipt_id": "receipt_1", "mission_id": "mission_1"}],
            },
            "mission_status_counts": {"queued": 1},
            "recent_missions": [],
        },
    )
    operator_payload = {"ok": True}
    monkeypatch.setattr(continuity, "_observer_briefing", lambda: {"observed_at": 1710000000.0})
    monkeypatch.setattr(continuity, "_operator_payload", lambda **_: operator_payload)
    monkeypatch.setattr(continuity, "_operator_surface", lambda **_: {"available": True})
    monkeypatch.setattr(continuity, "_orb_surface", lambda **_: {"available": True, "state": {}})

    body = continuity.presence()

    assert body["ok"] is True
    assert body["route"] == "/continuity/presence"
    presence = body["presence"]
    assert isinstance(presence, dict)
    assert presence["kind"] == "francis.grounded_presence.snapshot"
    assert presence["stage"]["status"] == "ready"
    assert presence["intent"]["available"] is False
    assert presence["intent"]["request_only"] is True
    assert presence["freshness"]["sources"]["continuity_briefing"]["status"] == "observed"
    assert presence["voice"]["status"] == "unknown"
    assert presence["unreal_adapter"]["status"] == "contract_defined_runtime_not_implemented"


def test_continuity_briefing_reuses_mission_and_operator_readbacks(monkeypatch) -> None:
    from francis.api.routes import continuity

    continuity_payload = {
        "mission_briefing": {},
        "mission_status_counts": {},
        "recent_missions": [],
    }
    operator_payload = {"ok": True, "generated_at": 1710000001.0}
    observed: dict[str, object] = {}

    monkeypatch.setattr(continuity, "mission_continuity_snapshot", lambda **_: continuity_payload)
    monkeypatch.setattr(continuity, "_observer_briefing", lambda: {})

    def operator_readback(*, continuity):
        observed["continuity"] = continuity
        return operator_payload

    def operator_surface(*, payload):
        observed["operator_surface"] = payload
        return {"available": True}

    def orb_surface(*, operator_report):
        observed["orb"] = operator_report
        return {"available": True, "state": {}}

    monkeypatch.setattr(continuity, "_operator_payload", operator_readback)
    monkeypatch.setattr(continuity, "_operator_surface", operator_surface)
    monkeypatch.setattr(continuity, "_orb_surface", orb_surface)
    monkeypatch.setattr(
        continuity,
        "unreal_presence_selection_readback",
        lambda: {"valid": False},
    )
    monkeypatch.setattr(
        continuity,
        "unreal_presence_runtime_readback",
        lambda **_: {"observed": False},
    )

    body = continuity.briefing()

    assert body["ok"] is True
    assert observed == {
        "continuity": continuity_payload,
        "operator_surface": operator_payload,
        "orb": operator_payload,
    }


def test_continuity_presence_routes_are_declared_on_router() -> None:
    from francis.api.routes import continuity

    paths = {getattr(route, "path", "") for route in continuity.router.routes}

    assert "/presence" in paths
    assert "/grounded-presence" in paths
    assert "/presence/contracts" in paths
    assert "/grounded-presence/contracts" in paths
    assert "/presence/unreal-selection" in paths
    assert "/grounded-presence/unreal-selection" in paths
    assert "/presence/unreal-runtime" in paths
    assert "/grounded-presence/unreal-runtime" in paths


def test_continuity_unreal_selection_route_sanitizes_readback_exception(monkeypatch) -> None:
    from francis.api.routes import continuity

    def fail_selection() -> dict[str, object]:
        raise RuntimeError("selection traceback token=selection-secret")

    monkeypatch.setattr(continuity, "unreal_presence_selection_readback", fail_selection)

    body = continuity.presence_unreal_selection()
    serialized = json.dumps(body, sort_keys=True)

    assert body["status"] == "selection_readback_unavailable"
    assert body["error"] == "internal_api_error"
    assert body["valid"] is False
    assert "selection-secret" not in serialized
    assert "traceback" not in serialized.lower()


def test_continuity_unreal_runtime_route_sanitizes_readback_exception(monkeypatch) -> None:
    from francis.api.routes import continuity

    monkeypatch.setattr(
        continuity,
        "unreal_presence_selection_readback",
        lambda: {"valid": True, "status": "operator_selection_confirmed"},
    )

    def fail_runtime(*, selection) -> dict[str, object]:
        raise RuntimeError("runtime traceback token=runtime-secret")

    monkeypatch.setattr(continuity, "unreal_presence_runtime_readback", fail_runtime)

    body = continuity.presence_unreal_runtime()
    serialized = json.dumps(body, sort_keys=True)

    assert body["status"] == "runtime_readback_unavailable"
    assert body["error"] == "internal_api_error"
    assert body["observed"] is False
    assert "runtime-secret" not in serialized
    assert "traceback" not in serialized.lower()


def test_continuity_presence_contract_status_keeps_runtime_and_authority_closed(monkeypatch) -> None:
    from francis.api.routes import continuity

    monkeypatch.delenv("FRANCIS_UNREAL_PRESENCE_SELECTION_PATH", raising=False)
    body = continuity.presence_contracts()

    assert body["status"] == "contracts_implemented_runtime_not_configured"
    assert body["contracts"] == {
        "snapshot": "francis.grounded_presence.snapshot.v1",
        "unreal_selection": "francis.grounded_presence.unreal_selection.v1",
        "unreal_runtime_status": "francis.grounded_presence.unreal_runtime_status.v1",
        "transport_envelope": "francis.grounded_presence.transport_envelope.v1",
        "delivery_receipt": "francis.grounded_presence.delivery_receipt.v1",
        "delivery_journal": "francis.grounded_presence.delivery_journal.v1",
        "delivery_attempt": "francis.grounded_presence.delivery_attempt.v1",
        "ipc_message": "francis.grounded_presence.ipc_message.v1",
        "delivery_ack": "francis.grounded_presence.delivery_ack.v1",
        "intent_event": "francis.grounded_presence.intent_event.v1",
        "intent_receipt": "francis.grounded_presence.intent_receipt.v1",
    }
    assert body["transport"]["network_allowed"] is False
    assert body["transport"]["cross_process_writer_lock"] == "windows_named_mutex"
    assert body["transport"]["application_authentication_status"] == (
        "hmac_sha256_environment_loader_implemented_unreal_injection_required"
    )
    assert body["transport"]["delivery_acknowledgement"] == ("signed_ack_with_durable_consumer_dedup_required")
    assert body["unreal"]["runtime_configured"] is False
    assert body["unreal"]["selection_status"] == "operator_confirmation_required"
    assert body["unreal"]["selection_configured"] is False
    assert body["intent_routing"]["dispatch_supported"] is False
    assert body["recovery"] == {
        "stale_snapshot_posture": "blocked_until_fresh_core_projection",
        "outbound_replay_posture": "durable_delivery_receipt_sequence_watermark",
        "inbound_replay_posture": "durable_accepted_intent_receipt_sequence_watermark",
        "receipt_failure_posture": "pre_send_attempt_plus_authenticated_ack_journal_recovery",
        "crash_window_posture": "exact_envelope_authenticated_reconciliation_after_restart",
    }
    assert body["authority"]["grants_execution_authority"] is False


def test_continuity_contract_status_reflects_selection_without_runtime_claim(monkeypatch) -> None:
    from francis.api.routes import continuity

    selection = {
        "kind": "francis.grounded_presence.unreal_selection_readback",
        "status": "operator_selection_confirmed",
        "configured": True,
        "valid": True,
        "selection_id": "gpu_0123456789abcdef0123456789abcdef",
        "project_selection_status": "operator_confirmed",
        "technology_selection_status": "operator_confirmed",
        "runtime_configured": False,
        "runtime_observed": False,
    }
    monkeypatch.setattr(continuity, "unreal_presence_selection_readback", lambda: dict(selection))
    monkeypatch.setattr(
        continuity,
        "unreal_presence_runtime_readback",
        lambda **_: {
            "status": "runtime_not_observed",
            "observed": False,
            "runtime": {},
        },
    )

    body = continuity.presence_contracts()
    selection_body = continuity.presence_unreal_selection()

    assert body["status"] == "contracts_implemented_operator_selection_confirmed_runtime_not_observed"
    assert body["unreal"]["selection_id"] == selection["selection_id"]
    assert body["unreal"]["project_selection_status"] == "operator_confirmed"
    assert body["unreal"]["technology_selection_status"] == "operator_confirmed"
    assert body["unreal"]["runtime_configured"] is False
    assert body["unreal"]["runtime_observed"] is False
    assert selection_body["status"] == selection["status"]
    assert selection_body["valid"] is True
    assert selection_body["selection_id"] == selection["selection_id"]
    assert selection_body["project_selection_status"] == "operator_confirmed"
    assert selection_body["technology_selection_status"] == "operator_confirmed"


def test_continuity_contract_status_reflects_observed_unreal_runtime(monkeypatch) -> None:
    from francis.api.routes import continuity

    monkeypatch.setattr(
        continuity,
        "unreal_presence_selection_readback",
        lambda: {
            "status": "operator_selection_confirmed",
            "configured": True,
            "valid": True,
            "selection_id": "gpu_0123456789abcdef0123456789abcdef",
            "project_selection_status": "operator_confirmed",
            "technology_selection_status": "operator_confirmed",
        },
    )
    runtime = {
        "status": "runtime_observed",
        "observed": True,
        "runtime": {"transport": {"configured": True}},
    }
    monkeypatch.setattr(continuity, "unreal_presence_runtime_readback", lambda **_: dict(runtime))

    body = continuity.presence_contracts()

    assert body["status"] == "contracts_implemented_runtime_observed"
    assert body["unreal"]["runtime_status"] == "runtime_observed"
    assert body["unreal"]["runtime_configured"] is True
    assert body["unreal"]["runtime_observed"] is True
    runtime_body = continuity.presence_unreal_runtime()
    assert runtime_body["status"] == runtime["status"]
    assert runtime_body["observed"] is True
    assert runtime_body["runtime"] == runtime["runtime"]


def test_continuity_surfaces_preserve_source_timestamps_and_backlog(monkeypatch) -> None:
    from francis.api.routes import continuity

    monkeypatch.setattr(
        continuity,
        "operator_mode_snapshot",
        lambda: {
            "ok": True,
            "generated_at": 1783598396.0,
            "control_mode": {"id": "assist"},
            "focus": {},
            "posture": {},
            "backlog": {"pending_approvals": 1},
        },
    )
    monkeypatch.setattr(
        continuity,
        "orb_status_snapshot",
        lambda: {
            "ok": True,
            "generated_at": 1783598397.0,
            "state": {"semantic_state": "blocked"},
        },
    )
    monkeypatch.setattr(
        continuity,
        "lens_overlay_runtime_readback",
        lambda: {
            "ready": True,
            "process_alive": True,
            "voice": {"voice_provider": "ElevenLabs"},
            "overlay_voice": {
                "status": "listening",
                "voice_provider": "ElevenLabs",
                "selected_voice": "Emma",
                "wake_listening": False,
            },
            "voice_provider_readiness": {
                "selected_provider": "ElevenLabs",
                "active_provider_configured": True,
            },
        },
    )

    operator = continuity._operator_surface()
    orb = continuity._orb_surface()

    assert operator["observed_at"] == 1783598396.0
    assert operator["backlog"] == {"pending_approvals": 1}
    assert orb["observed_at"] == 1783598397.0
    assert orb["voice"] == {
        "provider": "ElevenLabs",
        "selected_voice": "Emma",
        "identity_status": "ready",
        "input_provider": "ElevenLabs",
        "output_provider": "ElevenLabs",
        "listening": False,
        "speaking": False,
        "blockers": [],
        "source": "lens.host_manifest.overlay_runtime_readback",
    }


def test_orb_voice_surface_reports_speaking_only_from_explicit_live_status(monkeypatch) -> None:
    from francis.api.routes import continuity

    monkeypatch.setattr(
        continuity,
        "lens_overlay_runtime_readback",
        lambda: {
            "ready": True,
            "process_alive": True,
            "voice": {"voice_provider": "ElevenLabs"},
            "overlay_voice": {
                "status": "speaking",
                "voice_provider": "ElevenLabs",
                "selected_voice": "Emma",
                "wake_listening": False,
            },
            "voice_provider_readiness": {
                "selected_provider": "ElevenLabs",
                "active_provider_configured": True,
            },
        },
    )

    assert continuity._orb_voice_surface()["speaking"] is True
