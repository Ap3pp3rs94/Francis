from __future__ import annotations

import json
from pathlib import Path

from francis_connectors.library import (
    build_connector_library,
    build_connector_provenance,
    list_connector_entries,
    quarantine_connector,
    revoke_connector,
)
from francis_core.workspace_fs import WorkspaceFS


def _fs(root: Path) -> WorkspaceFS:
    workspace = (root / "workspace").resolve()
    return WorkspaceFS(
        roots=[workspace],
        journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
    )


def _write_registry(fs: WorkspaceFS, rows: list[dict[str, object]]) -> None:
    fs.write_text(
        "connectors/registry.json",
        json.dumps({"connectors": rows}, ensure_ascii=False, indent=2),
    )


def test_connector_library_counts_external_review_required_entries(tmp_path: Path) -> None:
    fs = _fs(tmp_path)
    _write_registry(
        fs,
        [
            {
                "id": "community-sync",
                "name": "Community Sync",
                "slug": "community-sync",
                "status": "active",
                "enabled": True,
                "risk_tier": "high",
                "provenance": {
                    "source_kind": "third_party",
                },
            }
        ],
    )

    entries = list_connector_entries(fs)
    library = build_connector_library(entries)
    imported = next(row for row in entries if row["id"] == "community-sync")
    provenance = build_connector_provenance(imported)

    assert library["connector_count"] >= 8
    assert library["active_count"] == 1
    assert library["external_count"] == 1
    assert library["review_required_count"] == 1
    assert provenance["kind"] == "third_party"
    assert provenance["label"] == "Third-Party"
    assert provenance["review_required"] is True
    assert "provenance anchors" in provenance["promotion_rule_detail"].lower()


def test_connector_provenance_accepts_traceable_vendor_review(tmp_path: Path) -> None:
    fs = _fs(tmp_path)
    _write_registry(
        fs,
        [
            {
                "id": "vendor-sync",
                "name": "Vendor Sync",
                "slug": "vendor-sync",
                "status": "active",
                "enabled": True,
                "risk_tier": "medium",
                "module": "vendor.connectors.sync",
                "provenance": {
                    "source_kind": "vendor",
                    "vendor": "Verified Vendor",
                    "source_ref": "vendor://verified/sync",
                    "review_state": "approved",
                },
            }
        ],
    )

    entries = list_connector_entries(fs)
    imported = next(row for row in entries if row["id"] == "vendor-sync")
    provenance = build_connector_provenance(imported)

    assert provenance["kind"] == "vendor"
    assert provenance["label"] == "Vendor Provided"
    assert provenance["traceable"] is True
    assert provenance["review_required"] is False
    assert provenance["review_state"] == "approved"
    assert provenance["source_label"] == "Verified Vendor"


def test_quarantine_and_revoke_connector_preserve_audit(tmp_path: Path) -> None:
    fs = _fs(tmp_path)

    quarantined = quarantine_connector(
        fs,
        "discord",
        reason="Connector is emitting unreviewed external traffic.",
        actor="connectors:architect",
    )
    assert quarantined is not None
    assert quarantined["status"] == "quarantined"
    assert quarantined["enabled"] is False
    assert quarantined["previous_status"] == "available"
    assert quarantined["quarantine_reason"] == "Connector is emitting unreviewed external traffic."
    assert quarantined["quarantined_by"] == "connectors:architect"
    assert quarantined["provenance"]["review_state"] == "quarantined"

    revoked = revoke_connector(
        fs,
        "discord",
        reason="Connector is no longer trusted for governed use.",
        actor="connectors:architect",
    )
    assert revoked is not None
    assert revoked["status"] == "revoked"
    assert revoked["enabled"] is False
    assert revoked["previous_status"] == "quarantined"
    assert revoked["quarantined_at"]
    assert revoked["revoked_at"]
    assert revoked["revocation_reason"] == "Connector is no longer trusted for governed use."
    assert revoked["revoked_by"] == "connectors:architect"
    assert revoked["provenance"]["review_state"] == "revoked"
