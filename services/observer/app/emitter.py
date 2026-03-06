from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS


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

        incident_ids: list[str] = []
        for item in anomalies:
            incident_id = str(uuid4())
            incident_ids.append(incident_id)
            incident = {
                "id": incident_id,
                "ts": ts,
                "run_id": run_id,
                "severity": item.get("severity", "warning"),
                "kind": item.get("kind", "observer.anomaly"),
                "message": item.get("message", ""),
                "evidence": item.get("evidence", {}),
                "status": "open",
            }
            self._append_jsonl("incidents/incidents.jsonl", incident)

        self.ledger.append(
            run_id=run_id,
            kind="observer.scan",
            summary={
                "level": score.get("level"),
                "anomaly_count": len(anomalies),
                "incident_count": len(incident_ids),
            },
        )
        return {
            "event_id": event["id"],
            "decision_id": decision["id"],
            "incident_ids": incident_ids,
        }
