from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

SUMMARY_VERSION = 1
SUMMARY_TAIL_LIMIT = 20
SUMMARY_RECENT_LIMIT = 20


@dataclass(frozen=True)
class LedgerEvent:
    ts: str
    kind: str
    run_id: str
    summary: dict[str, Any]


class RunLedger:
    def __init__(self, fs: WorkspaceFS, rel_path: str = "runs/run_ledger.jsonl") -> None:
        self.fs = fs
        self.rel_path = rel_path

    def _resolve_path(self, rel_path: str) -> Path:
        return (self.fs.roots[0] / rel_path).resolve()

    def _summary_rel_path(self) -> str:
        if self.rel_path.endswith(".jsonl"):
            return f"{self.rel_path[:-6]}.summary.json"
        return f"{self.rel_path}.summary.json"

    def _summary_path(self) -> Path:
        return self._resolve_path(self._summary_rel_path())

    def _load_summary_doc(self) -> dict[str, Any] | None:
        try:
            raw = self.fs.read_text(self._summary_rel_path())
        except Exception:
            return None
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        if int(parsed.get("version", 0) or 0) != SUMMARY_VERSION:
            return None
        return parsed

    def _write_summary_doc(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.fs.write_text(self._summary_rel_path(), json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    def _summary_is_stale(self) -> bool:
        ledger_path = self._resolve_path(self.rel_path)
        summary_path = self._summary_path()
        if not ledger_path.exists():
            return False
        if not summary_path.exists():
            return True
        try:
            return ledger_path.stat().st_mtime_ns > summary_path.stat().st_mtime_ns
        except Exception:
            return True

    def _normalized_summary_doc(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        doc = payload if isinstance(payload, dict) else {}
        count = max(0, int(doc.get("count", 0) or 0))
        tail = [dict(row) for row in doc.get("tail", []) if isinstance(row, dict)][-SUMMARY_TAIL_LIMIT:]
        recent_runs = [dict(row) for row in doc.get("recent_runs", []) if isinstance(row, dict)]
        recent_runs.sort(key=lambda row: str(row.get("last_ts", "")), reverse=True)
        return {
            "version": SUMMARY_VERSION,
            "updated_at": str(doc.get("updated_at", "")).strip() or utc_now_iso(),
            "count": count,
            "tail": tail,
            "recent_runs": recent_runs[:SUMMARY_RECENT_LIMIT],
        }

    def _update_recent_runs(self, rows: list[dict[str, Any]], event: dict[str, Any]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            run_id = str(row.get("run_id", "")).strip()
            if run_id:
                grouped[run_id] = dict(row)

        run_id = str(event.get("run_id", "")).strip()
        ts = str(event.get("ts", "")).strip()
        kind = str(event.get("kind", "")).strip()
        if run_id:
            bucket = grouped.setdefault(
                run_id,
                {
                    "run_id": run_id,
                    "first_ts": ts,
                    "last_ts": ts,
                    "event_count": 0,
                    "last_kind": "",
                },
            )
            bucket["event_count"] = max(0, int(bucket.get("event_count", 0) or 0)) + 1
            first_ts = str(bucket.get("first_ts", "")).strip()
            if ts and (not first_ts or ts < first_ts):
                bucket["first_ts"] = ts
            last_ts = str(bucket.get("last_ts", "")).strip()
            if ts and (not last_ts or ts >= last_ts):
                bucket["last_ts"] = ts
                if kind:
                    bucket["last_kind"] = kind

        recent_runs = list(grouped.values())
        recent_runs.sort(key=lambda row: str(row.get("last_ts", "")), reverse=True)
        return recent_runs[:SUMMARY_RECENT_LIMIT]

    def rebuild_summary(self) -> dict[str, Any]:
        ledger_path = self._resolve_path(self.rel_path)
        if not ledger_path.exists():
            return self._write_summary_doc(
                {
                    "version": SUMMARY_VERSION,
                    "updated_at": utc_now_iso(),
                    "count": 0,
                    "tail": [],
                    "recent_runs": [],
                }
            )

        count = 0
        tail: list[dict[str, Any]] = []
        grouped: dict[str, dict[str, Any]] = {}
        with ledger_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except Exception:
                    continue
                if not isinstance(parsed, dict):
                    continue
                count += 1
                tail.append(parsed)
                if len(tail) > SUMMARY_TAIL_LIMIT:
                    tail = tail[-SUMMARY_TAIL_LIMIT:]

                run_id = str(parsed.get("run_id", "")).strip()
                if not run_id:
                    continue
                ts = str(parsed.get("ts", "")).strip()
                kind = str(parsed.get("kind", "")).strip()
                bucket = grouped.setdefault(
                    run_id,
                    {
                        "run_id": run_id,
                        "first_ts": ts,
                        "last_ts": ts,
                        "event_count": 0,
                        "last_kind": "",
                    },
                )
                bucket["event_count"] = max(0, int(bucket.get("event_count", 0) or 0)) + 1
                first_ts = str(bucket.get("first_ts", "")).strip()
                if ts and (not first_ts or ts < first_ts):
                    bucket["first_ts"] = ts
                last_ts = str(bucket.get("last_ts", "")).strip()
                if ts and (not last_ts or ts >= last_ts):
                    bucket["last_ts"] = ts
                    if kind:
                        bucket["last_kind"] = kind

        recent_runs = list(grouped.values())
        recent_runs.sort(key=lambda row: str(row.get("last_ts", "")), reverse=True)
        return self._write_summary_doc(
            {
                "version": SUMMARY_VERSION,
                "updated_at": utc_now_iso(),
                "count": count,
                "tail": tail,
                "recent_runs": recent_runs[:SUMMARY_RECENT_LIMIT],
            }
        )

    def summary(self, *, recent_limit: int = 5, tail_limit: int = 5) -> dict[str, Any]:
        doc = self._load_summary_doc()
        if doc is None or self._summary_is_stale():
            doc = self.rebuild_summary()
        normalized = self._normalized_summary_doc(doc)
        recent_n = max(0, min(int(recent_limit), SUMMARY_RECENT_LIMIT))
        tail_n = max(0, min(int(tail_limit), SUMMARY_TAIL_LIMIT))
        return {
            "count": int(normalized.get("count", 0) or 0),
            "recent": [dict(row) for row in normalized.get("recent_runs", [])[:recent_n]],
            "tail": [dict(row) for row in normalized.get("tail", [])[-tail_n:]],
            "updated_at": normalized.get("updated_at"),
        }

    def append(self, *, run_id: str, kind: str, summary: dict[str, Any]) -> LedgerEvent:
        event = LedgerEvent(ts=utc_now_iso(), kind=kind, run_id=run_id, summary=summary)
        self.fs.append_jsonl(self.rel_path, event.__dict__)
        try:
            doc = self._load_summary_doc()
            if doc is None or self._summary_is_stale():
                self.rebuild_summary()
            else:
                normalized = self._normalized_summary_doc(doc)
                normalized["updated_at"] = event.ts
                normalized["count"] = max(0, int(normalized.get("count", 0) or 0)) + 1
                tail = [dict(row) for row in normalized.get("tail", []) if isinstance(row, dict)]
                tail.append(dict(event.__dict__))
                normalized["tail"] = tail[-SUMMARY_TAIL_LIMIT:]
                normalized["recent_runs"] = self._update_recent_runs(
                    [dict(row) for row in normalized.get("recent_runs", []) if isinstance(row, dict)],
                    dict(event.__dict__),
                )
                self._write_summary_doc(normalized)
        except Exception:
            pass
        return event

    def tail(self, n: int = 10) -> list[dict[str, Any]]:
        if 0 < int(n) <= SUMMARY_TAIL_LIMIT:
            summary = self.summary(tail_limit=n)
            return [dict(row) for row in summary.get("tail", [])]
        try:
            raw = self.fs.read_text(self.rel_path)
        except Exception:
            return []
        items: list[dict[str, Any]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return items[-max(0, n) :] if n > 0 else []
