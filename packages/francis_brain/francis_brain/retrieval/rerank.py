from __future__ import annotations

from collections import defaultdict
from typing import Any

from francis_brain.lanes import lane_weight, recency_weight, severity_weight


def _source_weight(source: str) -> float:
    normalized = str(source or "").strip().lower()
    if normalized in {
        "runs.last",
        "runs.ledger",
        "journals.decisions",
        "forge.catalog",
        "apprenticeship.skills",
        "apprenticeship.sessions",
        "approvals.requests",
    }:
        return 3.0
    if normalized.startswith("autonomy.") or normalized.startswith("control."):
        return 2.0
    return 1.0


def rerank_results(
    chunk_hits: list[dict[str, Any]],
    artifacts_by_id: dict[str, dict[str, Any]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    excerpts: dict[str, list[str]] = defaultdict(list)
    for hit in chunk_hits:
        artifact_id = str(hit.get("artifact_id", "")).strip()
        artifact = artifacts_by_id.get(artifact_id)
        if not artifact:
            continue
        bucket = aggregated.setdefault(
            artifact_id,
            {
                "artifact_id": artifact_id,
                "lexical_score": 0.0,
                "matched_terms": set(),
                "chunk_count": 0,
            },
        )
        bucket["lexical_score"] = max(float(bucket["lexical_score"]), float(hit.get("score", 0.0)))
        bucket["matched_terms"].update(hit.get("matched_terms", []))
        bucket["chunk_count"] = int(bucket["chunk_count"]) + 1
        excerpt = str(hit.get("text", "")).strip()
        if excerpt and excerpt not in excerpts[artifact_id]:
            excerpts[artifact_id].append(excerpt[:260])

    ranked: list[dict[str, Any]] = []
    for artifact_id, row in aggregated.items():
        artifact = artifacts_by_id[artifact_id]
        relations = artifact.get("relationships", {})
        relation_count = sum(1 for value in relations.values() if str(value or "").strip())
        total_score = (
            float(row["lexical_score"])
            + lane_weight(str(artifact.get("retention_lane", "cold")))
            + recency_weight(str(artifact.get("ts", "")))
            + severity_weight(str(artifact.get("severity", artifact.get("status", ""))))
            + _source_weight(str(artifact.get("source", "")))
            + min(2.0, relation_count * 0.4)
        )
        ranked.append(
            {
                **row,
                "matched_terms": sorted(str(item) for item in row["matched_terms"]),
                "score": round(total_score, 4),
                "artifact": artifact,
                "excerpts": excerpts.get(artifact_id, [])[:2],
            }
        )

    ranked.sort(key=lambda item: (float(item["score"]), str(item["artifact"].get("ts", ""))), reverse=True)
    return ranked[: max(1, min(int(limit), 50))]
