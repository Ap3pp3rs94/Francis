from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any


class LexicalFabricIndex:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = [chunk for chunk in chunks if isinstance(chunk, dict)]
        self.chunk_map = {str(chunk.get("chunk_id")): chunk for chunk in self.chunks}
        self.chunk_count = len(self.chunks)
        self.doc_freq: dict[str, int] = {}
        self.term_freqs: dict[str, Counter[str]] = {}
        self.postings: dict[str, list[str]] = defaultdict(list)

        for chunk in self.chunks:
            chunk_id = str(chunk.get("chunk_id", "")).strip()
            tokens = [str(token).strip().lower() for token in chunk.get("tokens", []) if str(token).strip()]
            if not chunk_id or not tokens:
                continue
            frequencies = Counter(tokens)
            self.term_freqs[chunk_id] = frequencies
            for token in frequencies:
                self.doc_freq[token] = int(self.doc_freq.get(token, 0)) + 1
                self.postings[token].append(chunk_id)

    def search(
        self,
        query_tokens: list[str],
        *,
        allowed_artifact_ids: set[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized = [str(token).strip().lower() for token in query_tokens if str(token).strip()]
        if not normalized:
            return []

        scores: dict[str, float] = defaultdict(float)
        matched_terms: dict[str, set[str]] = defaultdict(set)
        for token in normalized:
            docs = self.postings.get(token, [])
            if not docs:
                continue
            idf = math.log(1.0 + (self.chunk_count + 1) / (1 + int(self.doc_freq.get(token, 0))))
            for chunk_id in docs:
                chunk = self.chunk_map.get(chunk_id, {})
                artifact_id = str(chunk.get("artifact_id", "")).strip()
                if allowed_artifact_ids is not None and artifact_id not in allowed_artifact_ids:
                    continue
                frequency = float(self.term_freqs.get(chunk_id, Counter()).get(token, 0))
                if frequency <= 0:
                    continue
                scores[chunk_id] += frequency * idf
                matched_terms[chunk_id].add(token)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        results: list[dict[str, Any]] = []
        for chunk_id, score in ranked[: max(1, min(int(limit), 100))]:
            chunk = self.chunk_map.get(chunk_id)
            if not chunk:
                continue
            results.append(
                {
                    "chunk_id": chunk_id,
                    "artifact_id": str(chunk.get("artifact_id", "")).strip(),
                    "chunk_index": int(chunk.get("chunk_index", 0) or 0),
                    "score": float(score),
                    "text": str(chunk.get("text", "")),
                    "matched_terms": sorted(matched_terms.get(chunk_id, set())),
                }
            )
        return results
