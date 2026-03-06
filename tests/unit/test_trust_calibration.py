from __future__ import annotations

from services.orchestrator.app.autonomy.trust_calibration import (
    calibrate_cycle_result,
    calibrate_dispatch_result,
    calibrate_reactor_tick,
)


def test_cycle_verification_confirmed_on_completed_execution() -> None:
    cycle = {
        "halted_reason": "completed",
        "executed_actions": [{"kind": "observer.scan"}],
        "blocked_actions": [],
        "event_state": {"critical_incident_count": 0},
    }
    verification = calibrate_cycle_result(cycle)
    assert verification["verification_status"] == "verified"
    assert verification["confidence"] == "confirmed"
    assert verification["can_claim_done"] is True


def test_cycle_verification_blocked_on_critical() -> None:
    cycle = {
        "halted_reason": "critical_anomaly",
        "executed_actions": [],
        "blocked_actions": [],
        "event_state": {"critical_incident_count": 1},
    }
    verification = calibrate_cycle_result(cycle)
    assert verification["verification_status"] == "blocked"
    assert verification["confidence"] == "uncertain"
    assert verification["can_claim_done"] is False


def test_dispatch_verification_blocked_when_critical_incident_present() -> None:
    verification = calibrate_dispatch_result(
        halted_reason="critical_incident_present",
        processed_count=0,
        failed_count=0,
        retried_count=0,
        released_count=0,
        due_preview_count=1,
        critical_incident_count=1,
        processed=[],
    )
    assert verification["verification_status"] == "blocked"
    assert verification["confidence"] == "uncertain"
    assert verification["can_claim_done"] is False


def test_dispatch_verification_confirmed_when_all_cycles_verified() -> None:
    verification = calibrate_dispatch_result(
        halted_reason="completed",
        processed_count=1,
        failed_count=0,
        retried_count=0,
        released_count=0,
        due_preview_count=1,
        critical_incident_count=0,
        processed=[
            {
                "verification": {
                    "verification_status": "verified",
                    "confidence": "confirmed",
                    "can_claim_done": True,
                }
            }
        ],
    )
    assert verification["verification_status"] == "verified"
    assert verification["confidence"] == "confirmed"
    assert verification["can_claim_done"] is True


def test_reactor_verification_partial_when_guardrail_cooldown_active() -> None:
    verification = calibrate_reactor_tick(
        collect_result={"seen_count": 3, "queued_count": 1, "duplicate_count": 0},
        dispatch_result={
            "verification": {
                "verification_status": "verified",
                "confidence": "confirmed",
                "can_claim_done": True,
            }
        },
        guardrail_receipt={"cooldown_active": True},
    )
    assert verification["verification_status"] == "partial"
    assert verification["confidence"] == "likely"
    assert verification["can_claim_done"] is False
