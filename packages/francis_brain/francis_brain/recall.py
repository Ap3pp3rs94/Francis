from __future__ import annotations

from collections import Counter
from typing import Any

from francis_brain.calibration import calibrate_fabric_artifact, summarize_calibrated_artifacts
from francis_brain.memory_store import build_relation_index, load_snapshot, save_snapshot, summarize_snapshot
from francis_brain.retrieval.chunking import build_artifact_chunks, tokenize
from francis_brain.retrieval.rerank import rerank_results
from francis_brain.retrieval.vector_index import LexicalFabricIndex
from francis_brain.snapshots import build_fabric_snapshot
from francis_core.workspace_fs import WorkspaceFS

VOLATILE_SOURCES = {
    "runs.last",
    "telemetry.events",
    "incidents.incidents",
    "approvals.requests",
    "autonomy.last_dispatch",
    "autonomy.last_tick",
}


def _summarize_snapshot_with_calibration(snapshot: dict[str, Any], *, now: object | None = None) -> dict[str, Any]:
    summary = summarize_snapshot(snapshot)
    artifacts = snapshot.get("artifacts", []) if isinstance(snapshot.get("artifacts"), list) else []
    calibrated = summarize_calibrated_artifacts(artifacts, volatile_sources=VOLATILE_SOURCES, now=now)
    summary["volatile_sources"] = sorted(VOLATILE_SOURCES)
    summary["calibration"] = calibrated
    return summary


def _load_snapshot_for_query(
    fs: WorkspaceFS,
    *,
    refresh: bool,
    persist: bool,
) -> dict[str, Any]:
    if not refresh:
        existing = load_snapshot(fs)
        if isinstance(existing, dict):
            return existing
    snapshot = build_fabric_snapshot(fs)
    if persist:
        save_snapshot(fs, snapshot)
    return snapshot


def rebuild_fabric(fs: WorkspaceFS) -> dict[str, Any]:
    snapshot = build_fabric_snapshot(fs)
    save_snapshot(fs, snapshot)
    return snapshot


def summarize_fabric(fs: WorkspaceFS, *, refresh: bool = False, now: object | None = None) -> dict[str, Any]:
    snapshot = _load_snapshot_for_query(fs, refresh=refresh, persist=False)
    return _summarize_snapshot_with_calibration(snapshot, now=now)


def summarize_fabric_scope(
    fs: WorkspaceFS,
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    mission_id: str | None = None,
    refresh: bool = False,
    now: object | None = None,
) -> dict[str, Any]:
    snapshot = _load_snapshot_for_query(fs, refresh=refresh, persist=False)
    artifacts = snapshot.get("artifacts", []) if isinstance(snapshot.get("artifacts"), list) else []
    filtered_artifacts = [
        artifact
        for artifact in artifacts
        if _matches_filters(
            artifact,
            sources=set(),
            run_id=str(run_id or "").strip(),
            trace_id=str(trace_id or "").strip(),
            mission_id=str(mission_id or "").strip(),
        )
    ]
    source_counts = Counter(
        str(artifact.get("source", "")).strip()
        for artifact in filtered_artifacts
        if artifact.get("source")
    )
    lane_counts = Counter(
        str(artifact.get("retention_lane", "cold")).strip().lower() or "cold"
        for artifact in filtered_artifacts
    )
    scoped_snapshot = {
        "generated_at": snapshot.get("generated_at"),
        "summary": {
            "artifact_count": len(filtered_artifacts),
            "citation_ready_count": sum(
                1
                for artifact in filtered_artifacts
                if isinstance(artifact.get("provenance"), dict)
                and str(artifact["provenance"].get("rel_path", "")).strip()
            ),
            "source_counts": dict(source_counts),
            "lane_counts": {
                "hot": int(lane_counts.get("hot", 0)),
                "warm": int(lane_counts.get("warm", 0)),
                "cold": int(lane_counts.get("cold", 0)),
            },
        },
        "artifacts": filtered_artifacts,
    }
    return _summarize_snapshot_with_calibration(scoped_snapshot, now=now)


def _matches_filters(artifact: dict[str, Any], *, sources: set[str], run_id: str, trace_id: str, mission_id: str) -> bool:
    source = str(artifact.get("source", "")).strip().lower()
    relations = artifact.get("relationships", {}) if isinstance(artifact.get("relationships"), dict) else {}
    if sources and source not in sources:
        return False
    if run_id and str(relations.get("run_id", "")).strip() != run_id and str(artifact.get("id", "")).strip() != run_id:
        return False
    if trace_id and str(relations.get("trace_id", "")).strip() != trace_id:
        return False
    if mission_id and str(relations.get("mission_id", "")).strip() != mission_id:
        return False
    return True


def _citation_for_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    provenance = artifact.get("provenance", {}) if isinstance(artifact.get("provenance"), dict) else {}
    return {
        "artifact_id": artifact.get("id"),
        "source": artifact.get("source"),
        "rel_path": provenance.get("rel_path"),
        "line": provenance.get("line"),
        "record_index": provenance.get("record_index"),
        "ts": artifact.get("ts"),
    }


def _stale_state_warning(artifact: dict[str, Any]) -> str | None:
    source = str(artifact.get("source", "")).strip().lower()
    if source not in VOLATILE_SOURCES:
        return None
    ts = str(artifact.get("ts", "")).strip()
    if not ts:
        return "volatile source without timestamp"
    return f"volatile source: confirm freshness against current state ({source})"


def query_fabric(
    fs: WorkspaceFS,
    *,
    query: str,
    limit: int = 8,
    sources: list[str] | None = None,
    run_id: str | None = None,
    trace_id: str | None = None,
    mission_id: str | None = None,
    include_related: bool = True,
    refresh: bool = False,
    now: object | None = None,
) -> dict[str, Any]:
    normalized_query = " ".join(str(query or "").strip().split())
    if not normalized_query:
        raise ValueError("query is required")

    snapshot = _load_snapshot_for_query(fs, refresh=refresh, persist=False)
    artifacts = snapshot.get("artifacts", []) if isinstance(snapshot.get("artifacts"), list) else []
    normalized_sources = {str(item).strip().lower() for item in (sources or []) if str(item).strip()}
    normalized_run_id = str(run_id or "").strip()
    normalized_trace_id = str(trace_id or "").strip()
    normalized_mission_id = str(mission_id or "").strip()

    filtered_artifacts = [
        artifact
        for artifact in artifacts
        if isinstance(artifact, dict)
        and _matches_filters(
            artifact,
            sources=normalized_sources,
            run_id=normalized_run_id,
            trace_id=normalized_trace_id,
            mission_id=normalized_mission_id,
        )
    ]
    artifact_map = {str(item.get("id", "")).strip(): item for item in filtered_artifacts if str(item.get("id", "")).strip()}
    chunks = build_artifact_chunks(filtered_artifacts)
    index = LexicalFabricIndex(chunks)
    query_tokens = tokenize(normalized_query)
    raw_hits = index.search(query_tokens, allowed_artifact_ids=set(artifact_map), limit=max(limit * 4, 20))
    ranked = rerank_results(raw_hits, artifact_map, limit=limit)
    relation_index = build_relation_index(filtered_artifacts)

    results: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    result_artifacts: list[dict[str, Any]] = []
    for row in ranked:
        artifact = row["artifact"]
        result_artifacts.append(artifact)
        citation = _citation_for_artifact(artifact)
        citations.append(citation)
        related: list[dict[str, Any]] = []
        if include_related:
            relations = artifact.get("relationships", {}) if isinstance(artifact.get("relationships"), dict) else {}
            seen_related: set[str] = {str(artifact.get("id", "")).strip()}
            for key in ("run_id", "trace_id", "mission_id", "stage_id", "session_id", "approval_id"):
                value = str(relations.get(key, "")).strip()
                if not value:
                    continue
                for related_id in relation_index.get((key, value), [])[:6]:
                    if related_id in seen_related:
                        continue
                    seen_related.add(related_id)
                    related_artifact = artifact_map.get(related_id)
                    if not related_artifact:
                        continue
                    related.append(
                        {
                            "artifact_id": related_id,
                            "source": related_artifact.get("source"),
                            "title": related_artifact.get("title"),
                            "reason": f"shared {key}={value}",
                            "citation": _citation_for_artifact(related_artifact),
                        }
                    )
                if len(related) >= 3:
                    break

        why = [f"matched terms: {', '.join(row['matched_terms'])}"] if row["matched_terms"] else []
        stale = _stale_state_warning(artifact)
        if stale:
            why.append(stale)
        calibration = calibrate_fabric_artifact(artifact, volatile_sources=VOLATILE_SOURCES, now=now)
        why.extend(calibration["caveats"])
        results.append(
            {
                "artifact_id": artifact.get("id"),
                "source": artifact.get("source"),
                "kind": artifact.get("kind"),
                "title": artifact.get("title"),
                "summary": artifact.get("body"),
                "score": row.get("score"),
                "matched_terms": row.get("matched_terms", []),
                "retention_lane": artifact.get("retention_lane"),
                "ts": artifact.get("ts"),
                "status": artifact.get("status"),
                "severity": artifact.get("severity"),
                "verification_status": artifact.get("verification_status"),
                "confidence": calibration["confidence"],
                "trust_badge": calibration["trust_badge"],
                "can_claim_done": calibration["can_claim_done"],
                "citation": citation,
                "why": why,
                "calibration": calibration,
                "excerpts": row.get("excerpts", []),
                "relationships": artifact.get("relationships", {}),
                "related": related,
            }
        )

    return {
        "status": "ok",
        "query": normalized_query,
        "filters": {
            "sources": sorted(normalized_sources),
            "run_id": normalized_run_id or None,
            "trace_id": normalized_trace_id or None,
            "mission_id": normalized_mission_id or None,
            "include_related": include_related,
            "refresh": refresh,
            "limit": max(1, min(int(limit), 25)),
        },
        "snapshot": _summarize_snapshot_with_calibration(snapshot, now=now),
        "calibration": summarize_calibrated_artifacts(
            result_artifacts,
            volatile_sources=VOLATILE_SOURCES,
            now=now,
        ),
        "result_count": len(results),
        "results": results,
        "citations": citations,
    }
