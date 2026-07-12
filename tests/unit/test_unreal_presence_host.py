from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import francis.unreal_presence_host as host_module
from francis.unreal_presence_host import UnrealPresenceHost, UnrealPresenceHostConfig, _digest


class _Adapter:
    def __init__(self) -> None:
        self.prepare_count = 0

    def prepare(self, _snapshot: dict[str, Any]) -> SimpleNamespace:
        self.prepare_count += 1
        return SimpleNamespace(
            accepted=True,
            envelope={
                "envelope_id": "gpe_0123456789abcdef0123456789abcdef",
                "sequence": 1,
                "integrity": {"payload_digest": "a" * 64},
            },
        )


class _Publisher:
    def __init__(self) -> None:
        self.envelopes: list[dict[str, Any]] = []
        self.pending = False

    def publish(self, envelope: dict[str, Any]) -> SimpleNamespace:
        self.envelopes.append(envelope)
        if len(self.envelopes) == 1:
            self.pending = True
            payload = {
                "status": "ack_timeout",
                "delivered": False,
                "envelope_id": envelope["envelope_id"],
            }
        else:
            self.pending = False
            payload = {
                "status": "delivered_after_reconciliation",
                "delivered": True,
                "envelope_id": envelope["envelope_id"],
            }
        return SimpleNamespace(to_dict=lambda: payload)

    def readback(self) -> dict[str, Any]:
        return {
            "receipt_recovery_pending": self.pending,
            "pending_recovery_source": "delivery_attempt" if self.pending else "",
        }


def test_host_retries_exact_envelope_after_ambiguous_delivery(monkeypatch: Any, tmp_path: Path) -> None:
    snapshot = {"kind": "francis.grounded_presence.snapshot", "schema_version": "v1"}
    monkeypatch.setattr(host_module, "_current_presence_snapshot", lambda: snapshot)

    host = object.__new__(UnrealPresenceHost)
    host.config = UnrealPresenceHostConfig(status_path=tmp_path / "status.json")
    host.adapter = _Adapter()
    host.publisher = _Publisher()
    host._state_lock = threading.Lock()
    host._latest_envelope_id = ""
    host._last_snapshot_digest = ""
    host._last_publish_monotonic = 0.0
    host._pending_envelope = None
    host._pending_snapshot_digest = ""
    host._publish_count = 0
    host._publish_failure_count = 0
    host._last_publish = {}
    monkeypatch.setattr(host, "_write_status", lambda _status: None)

    ambiguous = host.publish_current_presence()
    reconciled = host.publish_current_presence()

    assert ambiguous["status"] == "ack_timeout"
    assert reconciled["status"] == "delivered_after_reconciliation"
    assert host.adapter.prepare_count == 1
    assert host.publisher.envelopes[0] == host.publisher.envelopes[1]
    assert host._pending_envelope is None
    assert host._publish_count == 1
    assert host._publish_failure_count == 1


def test_host_semantic_digest_ignores_only_volatile_observation_clocks() -> None:
    first = {
        "kind": "francis.grounded_presence.snapshot",
        "generated_at": "2026-07-12T12:00:00Z",
        "presence": {"state": "attention_required"},
        "freshness": {
            "status": "observed",
            "sources": {
                "continuity_briefing": {
                    "status": "observed",
                    "observed_at": "2026-07-12T11:59:59Z",
                    "age_seconds": 1.0,
                }
            },
        },
    }
    later_clock = {
        **first,
        "generated_at": "2026-07-12T12:00:01Z",
        "freshness": {
            "status": "observed",
            "sources": {
                "continuity_briefing": {
                    "status": "observed",
                    "observed_at": "2026-07-12T12:00:00Z",
                    "age_seconds": 1.5,
                }
            },
        },
    }
    changed_state = {
        **later_clock,
        "presence": {"state": "handoff"},
    }

    assert _digest(first) == _digest(later_clock)
    assert _digest(first) != _digest(changed_state)
