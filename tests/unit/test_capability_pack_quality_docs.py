from __future__ import annotations

from francis.economy.markets.capability_pack_quality_docs import analyze_capability_pack_quality_docs


def test_capability_pack_quality_docs_pass_for_existing_declared_doc_path() -> None:
    analysis = analyze_capability_pack_quality_docs(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "quality": {"docs": ["docs/deploy.md#ops-pack"]},
                "metadata": {
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                },
            }
        ],
        available_doc_paths={"docs/deploy.md"},
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready"
    assert analysis["pack_total"] == 1
    assert analysis["ready_pack_count"] == 1
    assert analysis["available_doc_path_count"] == 1
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["does_not_read_doc_contents"] is True
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_validation_receipts"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["documented_count"] == 1
    assert pack["declared_doc_reference_count"] == 1
    assert pack["existing_doc_reference_count"] == 1
    assert pack["missing_doc_reference_count"] == 0
    assert pack["invalid_doc_reference_count"] == 0
    assert pack["doc_files"] == ["docs/deploy.md"]
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_quality_docs_block_missing_invalid_and_unknown_refs() -> None:
    analysis = analyze_capability_pack_quality_docs(
        [
            {
                "capability": "generated.legacy.empty",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "quality": {"docs": []},
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                },
            },
            {
                "capability": "generated.legacy.bad",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "quality": {"docs": ["../outside.md", "docs/missing.md#section"]},
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                },
            },
        ],
        available_doc_paths={"docs/existing.md"},
    )

    assert analysis["status"] == "blocked"
    assert analysis["blocked_pack_count"] == 1
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_quality_docs"

    pack = analysis["packs"][0]
    assert pack["ready"] is False
    assert pack["blockers"] == [
        "docs_missing",
        "doc_reference_invalid",
        "doc_reference_not_found",
    ]
    assert pack["documented_count"] == 1
    assert pack["declared_doc_reference_count"] == 2
    assert pack["existing_doc_reference_count"] == 0
    assert pack["missing_doc_reference_count"] == 1
    assert pack["invalid_doc_reference_count"] == 1
    assert pack["missing_doc_references_sample"] == ["docs/missing.md#section"]
    assert pack["invalid_doc_references_sample"] == ["../outside.md"]
    failing = {item["capability"]: item for item in pack["failing_capabilities_sample"]}
    assert failing["generated.legacy.empty"]["gaps"] == ["docs_missing"]
    assert failing["generated.legacy.bad"]["gaps"] == [
        "doc_reference_invalid",
        "doc_reference_not_found",
    ]
