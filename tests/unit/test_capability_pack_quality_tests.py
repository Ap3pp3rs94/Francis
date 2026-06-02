from __future__ import annotations

from francis.economy.markets.capability_pack_quality_tests import analyze_capability_pack_quality_tests


def test_capability_pack_quality_tests_pass_for_existing_declared_test_path() -> None:
    analysis = analyze_capability_pack_quality_tests(
        [
            {
                "capability": "generated.deploy",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "quality": {"tests": ["tests/test_deploy.py::test_deploy_pack"]},
                "metadata": {
                    "pack_id": "ops.deploy",
                    "pack_version": "1.0.0",
                    "pack_name": "Ops Deploy Pack",
                },
            }
        ],
        available_test_paths={"tests/test_deploy.py"},
    )

    assert analysis["stage"] == "Stage 17 / Capability Economy"
    assert analysis["status"] == "ready"
    assert analysis["pack_total"] == 1
    assert analysis["ready_pack_count"] == 1
    assert analysis["available_test_path_count"] == 1
    assert analysis["governance"]["read_only"] is True
    assert analysis["governance"]["does_not_read_test_contents"] is True
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_quality_docs"

    pack = analysis["packs"][0]
    assert pack["pack_id"] == "ops.deploy"
    assert pack["ready"] is True
    assert pack["blockers"] == []
    assert pack["tested_count"] == 1
    assert pack["declared_test_reference_count"] == 1
    assert pack["existing_test_reference_count"] == 1
    assert pack["missing_test_reference_count"] == 0
    assert pack["invalid_test_reference_count"] == 0
    assert pack["test_files"] == ["tests/test_deploy.py"]
    assert pack["failing_capabilities_sample"] == []


def test_capability_pack_quality_tests_block_missing_invalid_and_unknown_refs() -> None:
    analysis = analyze_capability_pack_quality_tests(
        [
            {
                "capability": "generated.legacy.empty",
                "version": "0.1.0",
                "source": "generated",
                "status": "staged",
                "quality": {"tests": []},
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
                "quality": {"tests": ["../outside.py", "tests/test_missing.py::test_missing"]},
                "metadata": {
                    "pack_id": "legacy.generated",
                    "pack_version": "0.0.0-migration",
                    "pack_name": "Legacy Generated Pack",
                },
            },
        ],
        available_test_paths={"tests/test_existing.py"},
    )

    assert analysis["status"] == "blocked"
    assert analysis["blocked_pack_count"] == 1
    assert analysis["next_smallest_truthful_gap"] == "stage17_capability_pack_quality_tests"

    pack = analysis["packs"][0]
    assert pack["ready"] is False
    assert pack["blockers"] == [
        "tests_missing",
        "test_reference_invalid",
        "test_reference_not_found",
    ]
    assert pack["tested_count"] == 1
    assert pack["declared_test_reference_count"] == 2
    assert pack["existing_test_reference_count"] == 0
    assert pack["missing_test_reference_count"] == 1
    assert pack["invalid_test_reference_count"] == 1
    assert pack["missing_test_references_sample"] == ["tests/test_missing.py::test_missing"]
    assert pack["invalid_test_references_sample"] == ["../outside.py"]
    failing = {item["capability"]: item for item in pack["failing_capabilities_sample"]}
    assert failing["generated.legacy.empty"]["gaps"] == ["tests_missing"]
    assert failing["generated.legacy.bad"]["gaps"] == [
        "test_reference_invalid",
        "test_reference_not_found",
    ]
