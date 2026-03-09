from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from francis_core.workspace_fs import WorkspaceFS

SNAPSHOT_PATH = "brain/fabric/snapshot.json"
RELATION_KEYS = ("run_id", "trace_id", "mission_id", "stage_id", "session_id", "approval_id")


def load_snapshot(fs: WorkspaceFS, *, rel_path: str = SNAPSHOT_PATH) -> dict[str, Any] | None:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def save_snapshot(fs: WorkspaceFS, snapshot: dict[str, Any], *, rel_path: str = SNAPSHOT_PATH) -> dict[str, Any]:
    fs.write_text(rel_path, json.dumps(snapshot, ensure_ascii=False, indent=2))
    return snapshot


def summarize_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {
            "available": False,
            "generated_at": None,
            "artifact_count": 0,
            "source_count": 0,
            "citation_ready_count": 0,
            "lane_counts": {"hot": 0, "warm": 0, "cold": 0},
            "top_sources": [],
        }

    summary = snapshot.get("summary", {}) if isinstance(snapshot.get("summary"), dict) else {}
    source_counts = summary.get("source_counts", {}) if isinstance(summary.get("source_counts"), dict) else {}
    lane_counts = summary.get("lane_counts", {}) if isinstance(summary.get("lane_counts"), dict) else {}
    citation_ready_count = int(summary.get("citation_ready_count", 0) or 0)
    return {
        "available": True,
        "generated_at": snapshot.get("generated_at"),
        "artifact_count": int(summary.get("artifact_count", 0) or 0),
        "source_count": len(source_counts),
        "citation_ready_count": citation_ready_count,
        "lane_counts": {
            "hot": int(lane_counts.get("hot", 0) or 0),
            "warm": int(lane_counts.get("warm", 0) or 0),
            "cold": int(lane_counts.get("cold", 0) or 0),
        },
        "top_sources": [
            {"source": key, "count": int(value)}
            for key, value in sorted(source_counts.items(), key=lambda item: (int(item[1]), item[0]), reverse=True)[:5]
        ],
    }


def build_relation_index(artifacts: list[dict[str, Any]]) -> dict[tuple[str, str], list[str]]:
    index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for artifact in artifacts:
        artifact_id = str(artifact.get("id", "")).strip()
        if not artifact_id:
            continue
        relations = artifact.get("relationships", {})
        if not isinstance(relations, dict):
            continue
        for key in RELATION_KEYS:
            value = str(relations.get(key, "")).strip()
            if not value:
                continue
            bucket = index[(key, value)]
            if artifact_id not in bucket:
                bucket.append(artifact_id)
    return index
