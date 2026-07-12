from __future__ import annotations

import json
import os
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from francis.kernel.paths import data_dir
from francis.unreal_presence_adapter import UnrealPresenceAdapter, UnrealPresenceAdapterConfig
from francis.unreal_presence_intent_ipc import PresenceIntentPipeConfig, WindowsNamedPipePresenceIntentReceiver
from francis.unreal_presence_intents import UnrealPresenceIntentGateway
from francis.unreal_presence_ipc import PresencePipeConfig, WindowsNamedPipePresencePublisher
from francis.unreal_presence_receipts import LocalJsonPresenceDeliveryReceiptStore
from francis.unreal_presence_selection import unreal_presence_selection_readback
from francis.unreal_presence_wire import PresenceIpcAuthenticator


UNREAL_PRESENCE_HOST_STATUS_KIND = "francis.grounded_presence.core_host_status"
UNREAL_PRESENCE_HOST_STATUS_SCHEMA_VERSION = "francis.grounded_presence.core_host_status.v1"
_VOLATILE_SNAPSHOT_DIGEST_FIELDS = frozenset({"generated_at", "observed_at", "age_seconds"})


@dataclass(frozen=True, slots=True)
class UnrealPresenceHostConfig:
    adapter_id: str = "unreal_presence_1"
    session_id: str = "francis_unreal_stage1_v1"
    publish_interval_seconds: float = 1.0
    heartbeat_seconds: float = 3.0
    exit_after_seconds: float = 0.0
    status_path: Path = data_dir() / "runtime" / "unreal-presence-host" / "status.json"

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> UnrealPresenceHostConfig:
        values = os.environ if environ is None else environ
        adapter_id = str(values.get("FRANCIS_UNREAL_PRESENCE_ADAPTER_ID") or "unreal_presence_1").strip()
        session_id = str(values.get("FRANCIS_UNREAL_PRESENCE_SESSION_ID") or "francis_unreal_stage1_v1").strip()
        interval = _bounded_float(values.get("FRANCIS_UNREAL_PRESENCE_PUBLISH_INTERVAL_SECONDS"), 1.0, 0.2, 10.0)
        heartbeat = _bounded_float(values.get("FRANCIS_UNREAL_PRESENCE_HEARTBEAT_SECONDS"), 3.0, 1.0, 30.0)
        exit_after = _bounded_float(values.get("FRANCIS_UNREAL_PRESENCE_HOST_EXIT_AFTER_SECONDS"), 0.0, 0.0, 86_400.0)
        configured_status = str(values.get("FRANCIS_UNREAL_PRESENCE_HOST_STATUS_PATH") or "").strip()
        status_path = (
            Path(configured_status)
            if configured_status
            else data_dir() / "runtime" / "unreal-presence-host" / "status.json"
        )
        if not _contract_id(adapter_id) or not _contract_id(session_id):
            raise ValueError("unreal_presence_host_identity_invalid")
        if not status_path.is_absolute() or str(status_path).startswith(("\\\\", "//")):
            raise ValueError("unreal_presence_host_status_path_invalid")
        return cls(
            adapter_id=adapter_id,
            session_id=session_id,
            publish_interval_seconds=interval,
            heartbeat_seconds=heartbeat,
            exit_after_seconds=exit_after,
            status_path=status_path.resolve(strict=False),
        )


class UnrealPresenceHost:
    def __init__(self, config: UnrealPresenceHostConfig, *, environ: Mapping[str, str] | None = None) -> None:
        self.config = config
        self.environ = dict(os.environ if environ is None else environ)
        selection = unreal_presence_selection_readback(environ=self.environ)
        if selection.get("valid") is not True:
            raise ValueError("unreal_presence_selection_not_confirmed")
        self.selection_id = str(selection.get("selection_id") or "")
        self.authenticator = PresenceIpcAuthenticator.from_environment(self.environ)
        receipt_store = LocalJsonPresenceDeliveryReceiptStore()
        adapter_config = UnrealPresenceAdapterConfig(
            adapter_id=config.adapter_id,
            session_id=config.session_id,
            ttl_ms=5_000,
        )
        self.adapter = UnrealPresenceAdapter.from_delivery_receipts(adapter_config, receipt_store=receipt_store)
        self.publisher = WindowsNamedPipePresencePublisher(
            PresencePipeConfig(
                adapter_id=config.adapter_id,
                session_id=config.session_id,
                connect_timeout_ms=2_000,
                ack_timeout_ms=2_000,
                authentication_key_id=self.authenticator.key_id,
            ),
            authenticator=self.authenticator,
            receipt_store=receipt_store,
        )
        self.gateway = UnrealPresenceIntentGateway(adapter_id=config.adapter_id, session_id=config.session_id)
        self.intent_receiver = WindowsNamedPipePresenceIntentReceiver(
            PresenceIntentPipeConfig(
                adapter_id=config.adapter_id,
                session_id=config.session_id,
                wait_timeout_ms=1_000,
                authentication_key_id=self.authenticator.key_id,
            ),
            gateway=self.gateway,
            authenticator=self.authenticator,
        )
        self._stop = threading.Event()
        self._state_lock = threading.Lock()
        self._latest_envelope_id = ""
        self._last_snapshot_digest = ""
        self._last_publish_monotonic = 0.0
        self._pending_envelope: dict[str, Any] | None = None
        self._pending_snapshot_digest = ""
        self._publish_count = 0
        self._publish_failure_count = 0
        self._last_publish: dict[str, Any] = {}
        self._last_intent: dict[str, Any] = {}
        self._intent_thread: threading.Thread | None = None

    def run(self) -> int:
        started = time.monotonic()
        self._intent_thread = threading.Thread(
            target=self._intent_loop,
            name="FrancisUnrealPresenceIntentReceiver",
            daemon=True,
        )
        self._intent_thread.start()
        self._write_status("running")
        try:
            while not self._stop.is_set():
                if self.config.exit_after_seconds and time.monotonic() - started >= self.config.exit_after_seconds:
                    break
                self.publish_current_presence()
                self._stop.wait(self.config.publish_interval_seconds)
        finally:
            self._stop.set()
            if self._intent_thread is not None:
                self._intent_thread.join(timeout=3.0)
            self._write_status("stopped")
        return 0

    def stop(self) -> None:
        self._stop.set()

    def publish_current_presence(self) -> dict[str, Any]:
        snapshot = _current_presence_snapshot()
        snapshot_digest = _digest(snapshot)
        now = time.monotonic()
        if (
            snapshot_digest == self._last_snapshot_digest
            and now - self._last_publish_monotonic < self.config.heartbeat_seconds
        ):
            return {"status": "unchanged", "published": False}
        if self._pending_envelope is not None:
            envelope = deepcopy(self._pending_envelope)
            pending_snapshot_digest = self._pending_snapshot_digest
        else:
            projection = self.adapter.prepare(snapshot)
            if not projection.accepted:
                result = projection.to_dict()
                with self._state_lock:
                    self._last_publish = result
                    self._last_publish_monotonic = now
                    self._publish_failure_count += 1
                self._write_status("running")
                return result
            envelope = deepcopy(dict(projection.envelope))
            pending_snapshot_digest = snapshot_digest
            self._pending_envelope = deepcopy(envelope)
            self._pending_snapshot_digest = pending_snapshot_digest

        result = self.publisher.publish(envelope).to_dict()
        publisher_readback = self.publisher.readback()
        exact_retry_required = (
            publisher_readback.get("receipt_recovery_pending") is True
            and publisher_readback.get("pending_recovery_source") == "delivery_attempt"
        )
        with self._state_lock:
            self._last_publish = result
            self._last_publish_monotonic = now
            if result.get("delivered") is True:
                self._publish_count += 1
                self._last_snapshot_digest = pending_snapshot_digest
                self._latest_envelope_id = str(result.get("envelope_id") or "")
                self._pending_envelope = None
                self._pending_snapshot_digest = ""
            else:
                self._publish_failure_count += 1
                if not exact_retry_required:
                    self._pending_envelope = None
                    self._pending_snapshot_digest = ""
        self._write_status("running")
        return result

    def readback(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "kind": UNREAL_PRESENCE_HOST_STATUS_KIND,
                "schema_version": UNREAL_PRESENCE_HOST_STATUS_SCHEMA_VERSION,
                "observed_at": datetime.now(UTC).isoformat(),
                "process_id": os.getpid(),
                "status": "stopping" if self._stop.is_set() else "running",
                "adapter_id": self.config.adapter_id,
                "session_id": self.config.session_id,
                "selection_id": self.selection_id,
                "authentication_key_id": self.authenticator.key_id,
                "publish_count": self._publish_count,
                "publish_failure_count": self._publish_failure_count,
                "latest_envelope_id": self._latest_envelope_id,
                "last_publish": dict(self._last_publish),
                "last_intent": dict(self._last_intent),
                "exact_retry_pending": self._pending_envelope is not None,
                "pending_envelope_id": str((self._pending_envelope or {}).get("envelope_id") or ""),
                "publisher": self.publisher.readback(),
                "intent_receiver": self.intent_receiver.readback(),
                "stores_presence_payload": False,
                "network_used": False,
                "authority": _authority(),
            }

    def _intent_loop(self) -> None:
        while not self._stop.is_set():
            with self._state_lock:
                expected_envelope_id = self._latest_envelope_id
            result = self.intent_receiver.receive_once(expected_source_envelope_id=expected_envelope_id).to_dict()
            if result.get("received") is True:
                with self._state_lock:
                    self._last_intent = result
                self._write_status("running")

    def _write_status(self, status: str) -> None:
        payload = self.readback()
        payload["status"] = status
        path = self.config.status_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _current_presence_snapshot() -> dict[str, Any]:
    from francis.api.routes.continuity import presence

    payload = presence()
    snapshot = payload.get("presence")
    if not isinstance(snapshot, dict) or snapshot.get("kind") != "francis.grounded_presence.snapshot":
        raise ValueError("grounded_presence_snapshot_unavailable")
    return snapshot


def _digest(payload: Mapping[str, Any]) -> str:
    import hashlib

    canonical = json.dumps(
        _semantic_digest_value(payload),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _semantic_digest_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _semantic_digest_value(item)
            for key, item in value.items()
            if str(key) not in _VOLATILE_SNAPSHOT_DIGEST_FIELDS
        }
    if isinstance(value, list | tuple):
        return [_semantic_digest_value(item) for item in value]
    return value


def _authority() -> dict[str, bool]:
    return {
        "francis_core_authoritative": True,
        "grants_execution_authority": False,
        "grants_desktop_authority": False,
        "grants_network_authority": False,
        "grants_memory_write_authority": False,
        "grants_approval_authority": False,
    }


def _contract_id(value: str) -> str:
    return value if value and len(value) <= 160 and all(char.isalnum() or char in "-_." for char in value) else ""


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if not minimum <= parsed <= maximum:
        raise ValueError("unreal_presence_host_interval_invalid")
    return parsed


def main() -> int:
    host = UnrealPresenceHost(UnrealPresenceHostConfig.from_environment())
    try:
        return host.run()
    except KeyboardInterrupt:
        host.stop()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
