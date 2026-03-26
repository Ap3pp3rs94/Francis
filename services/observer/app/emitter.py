from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS


OBSERVER_MANAGED_KINDS = {
    "cpu.high_load",
    "disk.low_free_space",
    "memory.low_available",
    "repo.high_drift",
}
TERMINAL_INCIDENT_STATUSES = {"resolved", "closed", "mitigated", "superseded"}


class ObserverEmitter:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.fs = WorkspaceFS(
            roots=[workspace_root],
            journal_path=(workspace_root / "journals" / "fs.jsonl").resolve(),
        )
        self.ledger = RunLedger(self.fs, rel_path="runs/run_ledger.jsonl")

    def _append_jsonl(self, rel_path: str, payload: dict[str, Any]) -> None:
        try:
            existing = self.fs.read_text(rel_path)
        except Exception:
            existing = ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        existing += json.dumps(payload, ensure_ascii=False) + "\n"
        self.fs.write_text(rel_path, existing)

    def _read_jsonl(self, rel_path: str) -> list[dict[str, Any]]:
        try:
            raw = self.fs.read_text(rel_path)
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except Exception:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows

    def _write_jsonl(self, rel_path: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            self.fs.write_text(rel_path, "")
            return
        payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        self.fs.write_text(rel_path, payload)

    def _incident_key(self, item: dict[str, Any]) -> str:
        kind = str(item.get("kind", "observer.anomaly")).strip().lower() or "observer.anomaly"
        return f"observer:{kind}"

    def _is_managed_incident(self, row: dict[str, Any]) -> bool:
        kind = str(row.get("kind", "")).strip().lower()
        source = str(row.get("source", "")).strip().lower()
        incident_key = str(row.get("incident_key", "")).strip().lower()
        return kind in OBSERVER_MANAGED_KINDS or source == "observer" or incident_key.startswith("observer:")

    def _managed_incident_status(self, row: dict[str, Any]) -> str:
        return str(row.get("status", row.get("state", "open"))).strip().lower() or "open"

    def emit_cycle(
        self,
        *,
        run_id: str,
        snapshot: dict[str, Any],
        anomalies: list[dict[str, Any]],
        score: dict[str, Any],
    ) -> dict[str, Any]:
        ts = utc_now_iso()
        event = {
            "id": str(uuid4()),
            "ts": ts,
            "kind": "observer.snapshot",
            "run_id": run_id,
            "level": score.get("level"),
            "anomaly_count": len(anomalies),
            "snapshot": snapshot,
        }
        self._append_jsonl("logs/francis.log.jsonl", event)

        decision = {
            "id": str(uuid4()),
            "ts": ts,
            "kind": "observer.decision",
            "run_id": run_id,
            "headline": score.get("headline"),
            "level": score.get("level"),
            "anomaly_count": len(anomalies),
        }
        self._append_jsonl("journals/decisions.jsonl", decision)

        incidents = self._read_jsonl("incidents/incidents.jsonl")
        current_by_key = {self._incident_key(item): item for item in anomalies}
        open_positions_by_key: dict[str, list[int]] = {}
        for index, row in enumerate(incidents):
            if not self._is_managed_incident(row):
                continue
            status = self._managed_incident_status(row)
            if status in TERMINAL_INCIDENT_STATUSES:
                continue
            key = str(row.get("incident_key", "")).strip().lower() or self._incident_key(row)
            open_positions_by_key.setdefault(key, []).append(index)

        incident_ids: list[str] = []
        opened_count = 0
        refreshed_count = 0
        resolved_count = 0
        deduped_count = 0
        changed = False

        for key, item in current_by_key.items():
            positions = open_positions_by_key.get(key, [])
            anomaly_kind = str(item.get("kind", "observer.anomaly")).strip().lower() or "observer.anomaly"
            anomaly_severity = str(item.get("severity", "warning")).strip().lower() or "warning"
            anomaly_message = str(item.get("message", "")).strip()
            anomaly_evidence = item.get("evidence", {})
            if not isinstance(anomaly_evidence, dict):
                anomaly_evidence = {"value": anomaly_evidence}

            if positions:
                canonical_index = positions[-1]
                canonical = incidents[canonical_index]
                canonical_id = str(canonical.get("id", "")).strip() or str(uuid4())
                previous_run_id = str(canonical.get("created_run_id", "")).strip() or str(canonical.get("run_id", "")).strip()
                canonical["id"] = canonical_id
                seen_count = int(canonical.get("seen_count", 1) or 1) + 1
                canonical["run_id"] = run_id
                canonical["severity"] = anomaly_severity
                canonical["kind"] = anomaly_kind
                canonical["message"] = anomaly_message
                canonical["evidence"] = anomaly_evidence
                canonical["status"] = "open"
                canonical["state"] = "open"
                canonical["source"] = "observer"
                canonical["incident_key"] = key
                canonical["updated_at"] = ts
                canonical["last_seen_at"] = ts
                canonical["last_seen_run_id"] = run_id
                canonical["seen_count"] = seen_count
                canonical.setdefault("first_seen_at", canonical.get("ts") or ts)
                canonical.setdefault("created_run_id", previous_run_id or run_id)
                incidents[canonical_index] = canonical
                incident_ids.append(canonical_id)
                refreshed_count += 1
                changed = True

                for duplicate_index in positions[:-1]:
                    duplicate = incidents[duplicate_index]
                    duplicate["status"] = "superseded"
                    duplicate["state"] = "superseded"
                    duplicate["source"] = "observer"
                    duplicate["incident_key"] = key
                    duplicate["updated_at"] = ts
                    duplicate["resolved_at"] = ts
                    duplicate["resolved_by_run_id"] = run_id
                    duplicate["superseded_by"] = canonical_id
                    duplicate["resolution_reason"] = "observer_duplicate_incident"
                    incidents[duplicate_index] = duplicate
                    deduped_count += 1
                    changed = True
            else:
                incident_id = str(uuid4())
                incident_ids.append(incident_id)
                incidents.append(
                    {
                        "id": incident_id,
                        "ts": ts,
                        "run_id": run_id,
                        "severity": anomaly_severity,
                        "kind": anomaly_kind,
                        "message": anomaly_message,
                        "evidence": anomaly_evidence,
                        "status": "open",
                        "state": "open",
                        "source": "observer",
                        "incident_key": key,
                        "first_seen_at": ts,
                        "last_seen_at": ts,
                        "created_run_id": run_id,
                        "last_seen_run_id": run_id,
                        "seen_count": 1,
                    }
                )
                opened_count += 1
                changed = True

        for key, positions in open_positions_by_key.items():
            if key in current_by_key:
                continue
            for position in positions:
                row = incidents[position]
                row["status"] = "resolved"
                row["state"] = "resolved"
                row["source"] = "observer"
                row["incident_key"] = key
                row["updated_at"] = ts
                row["resolved_at"] = ts
                row["resolved_by_run_id"] = run_id
                row["resolution_reason"] = "observer_scan_clear"
                incidents[position] = row
                resolved_count += 1
                changed = True

        if changed:
            self._write_jsonl("incidents/incidents.jsonl", incidents)

        self.ledger.append(
            run_id=run_id,
            kind="observer.scan",
            summary={
                "level": score.get("level"),
                "anomaly_count": len(anomalies),
                "opened_incident_count": opened_count,
                "refreshed_incident_count": refreshed_count,
                "resolved_incident_count": resolved_count,
                "deduped_incident_count": deduped_count,
                "active_incident_count": len(incident_ids),
            },
        )
        return {
            "event_id": event["id"],
            "decision_id": decision["id"],
            "incident_ids": incident_ids,
            "opened_incident_count": opened_count,
            "refreshed_incident_count": refreshed_count,
            "resolved_incident_count": resolved_count,
            "deduped_incident_count": deduped_count,
        }
