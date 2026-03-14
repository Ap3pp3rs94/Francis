from __future__ import annotations

from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import add_entry, list_entries
from francis_forge.library import (
    build_capability_library,
    build_capability_provenance,
    build_promotion_rules,
    build_quality_standard,
    next_patch_version,
)
from francis_forge.promotion import promote_stage, quarantine_entry, revoke_entry


def _fs(root) -> WorkspaceFS:
    workspace = (root / "workspace").resolve()
    return WorkspaceFS(
        roots=[workspace],
        journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
    )


def test_capability_library_groups_versions_and_assigns_next_patch(tmp_path) -> None:
    fs = _fs(tmp_path)
    add_entry(
        fs,
        {
            "id": "capability-stage-v1",
            "name": "Capability Stage",
            "slug": "capability-stage",
            "status": "active",
            "version": "0.1.0",
        },
    )
    add_entry(
        fs,
        {
            "id": "capability-stage-v2",
            "name": "Capability Stage",
            "slug": "capability-stage",
            "status": "staged",
            "version": "0.1.1",
        },
    )

    library = build_capability_library(list_entries(fs))

    assert next_patch_version(list_entries(fs), "capability-stage") == "0.1.2"
    assert library["pack_count"] == 1
    pack = library["packs"][0]
    assert pack["pack_id"] == "capability-stage"
    assert pack["version_count"] == 2
    assert pack["active_version"] == "0.1.0"
    assert pack["latest_version"] == "0.1.1"
    assert pack["focus_version"]["id"] == "capability-stage-v2"


def test_capability_quality_standard_requires_docs_tests_and_tool_pack() -> None:
    quality = build_quality_standard(
        {
            "validation": {"ok": True},
            "diff_summary": {
                "file_count": 2,
                "files": [
                    {"path": "forge/staging/capability-stage/README.md"},
                    {"path": "forge/staging/capability-stage/tests/test_capability_stage.py"},
                ],
            },
            "tool_pack": {"skill_name": "forge.pack.capability-stage"},
        }
    )

    assert quality["ok"] is True
    assert quality["score"] == "5/5"


def test_capability_provenance_requires_review_for_external_imports() -> None:
    pending = build_capability_provenance(
        {
            "id": "capability-import",
            "status": "staged",
            "imported_from_bundle_id": "bundle-123",
            "imported_at": "2026-03-13T12:00:00+00:00",
        },
        approval_status="pending",
    )
    approved = build_capability_provenance(
        {
            "id": "capability-import",
            "status": "staged",
            "imported_from_bundle_id": "bundle-123",
            "imported_at": "2026-03-13T12:00:00+00:00",
        },
        approval_status="approved",
    )

    assert pending["kind"] == "local_import"
    assert pending["label"] == "Local Import"
    assert pending["review_required"] is True
    assert pending["promotion_ready"] is False
    assert approved["review_state"] == "approved"
    assert approved["promotion_ready"] is True
    assert approved["source_label"] == "portability bundle bundle-123"


def test_capability_provenance_rule_blocks_third_party_without_traceable_review() -> None:
    entry = {
        "id": "capability-third-party",
        "status": "staged",
        "validation": {"ok": True},
        "diff_summary": {
            "file_count": 2,
            "files": [
                {"path": "forge/staging/capability-third-party/README.md"},
                {"path": "forge/staging/capability-third-party/tests/test_capability_third_party.py"},
            ],
        },
        "tool_pack": {"skill_name": "forge.pack.capability-third-party"},
        "provenance": {"source_kind": "third_party"},
    }

    blocked = build_promotion_rules(entry, approval_status="approved")
    allowed = build_promotion_rules(
        {
            **entry,
            "provenance": {
                "source_kind": "third_party",
                "source_ref": "gh://community/capability-pack",
                "review_state": "approved",
            },
        },
        approval_status="approved",
    )

    assert blocked["ready"] is False
    provenance_rule = next(rule for rule in blocked["rules"] if rule["kind"] == "provenance")
    assert provenance_rule["ok"] is False
    assert "provenance anchors" in provenance_rule["detail"].lower()
    assert allowed["ready"] is True


def test_promote_stage_supersedes_prior_active_version(tmp_path) -> None:
    fs = _fs(tmp_path)
    add_entry(
        fs,
        {
            "id": "capability-stage-v1",
            "name": "Capability Stage",
            "slug": "capability-stage",
            "status": "active",
            "version": "0.1.0",
            "validation": {"ok": True},
            "diff_summary": {
                "file_count": 2,
                "files": [
                    {"path": "forge/staging/capability-stage-v1/README.md"},
                    {"path": "forge/staging/capability-stage-v1/tests/test_capability_stage.py"},
                ],
            },
            "tool_pack": {"skill_name": "forge.pack.capability-stage"},
        },
    )
    add_entry(
        fs,
        {
            "id": "capability-stage-v2",
            "name": "Capability Stage",
            "slug": "capability-stage",
            "status": "staged",
            "version": "0.1.1",
            "validation": {"ok": True},
            "diff_summary": {
                "file_count": 2,
                "files": [
                    {"path": "forge/staging/capability-stage-v2/README.md"},
                    {"path": "forge/staging/capability-stage-v2/tests/test_capability_stage.py"},
                ],
            },
            "tool_pack": {"skill_name": "forge.pack.capability-stage"},
        },
    )

    promoted = promote_stage(fs, "capability-stage-v2")
    assert promoted is not None
    assert promoted["status"] == "active"

    rows = {row["id"]: row for row in list_entries(fs)}
    assert rows["capability-stage-v1"]["status"] == "superseded"
    assert rows["capability-stage-v1"]["superseded_by"] == "capability-stage-v2"
    assert rows["capability-stage-v2"]["status"] == "active"


def test_quarantine_entry_marks_lifecycle_and_provenance(tmp_path) -> None:
    fs = _fs(tmp_path)
    add_entry(
        fs,
        {
            "id": "capability-quarantine",
            "name": "Capability Quarantine",
            "slug": "capability-quarantine",
            "status": "staged",
            "version": "0.2.0",
            "provenance": {"source_kind": "third_party", "source_ref": "gh://community/capability-quarantine"},
        },
    )

    quarantined = quarantine_entry(
        fs,
        "capability-quarantine",
        reason="Third-party provenance failed review.",
        actor="lens:architect",
    )

    assert quarantined is not None
    assert quarantined["status"] == "quarantined"
    assert quarantined["quarantine_reason"] == "Third-party provenance failed review."
    assert quarantined["quarantined_by"] == "lens:architect"
    assert quarantined["provenance"]["review_state"] == "quarantined"
    assert quarantined["provenance"]["review_note"] == "Third-party provenance failed review."


def test_revoke_entry_marks_lifecycle_and_preserves_audit(tmp_path) -> None:
    fs = _fs(tmp_path)
    add_entry(
        fs,
        {
            "id": "capability-revoke",
            "name": "Capability Revoke",
            "slug": "capability-revoke",
            "status": "quarantined",
            "version": "1.0.0",
            "quarantined_at": "2026-03-13T01:00:00+00:00",
            "quarantine_reason": "Quarantined before final revocation.",
            "provenance": {"source_kind": "vendor", "vendor": "Verified Vendor", "review_state": "quarantined"},
        },
    )

    revoked = revoke_entry(
        fs,
        "capability-revoke",
        reason="Capability is no longer trusted for governed use.",
        actor="lens:architect",
    )

    assert revoked is not None
    assert revoked["status"] == "revoked"
    assert revoked["previous_status"] == "quarantined"
    assert revoked["revocation_reason"] == "Capability is no longer trusted for governed use."
    assert revoked["revoked_by"] == "lens:architect"
    assert revoked["quarantined_at"] == "2026-03-13T01:00:00+00:00"
    assert revoked["provenance"]["review_state"] == "revoked"
    assert revoked["provenance"]["review_note"] == "Capability is no longer trusted for governed use."
