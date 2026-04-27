from __future__ import annotations

from pathlib import Path

_PLUGIN_ACTOR = "test.plugins.write"


def test_forge_proposal_and_promotion_readback(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    raw_secret = "sk-" + ("z" * 24)

    empty_status = client.get("/forge/status")
    assert empty_status.status_code == 200
    assert empty_status.json()["proposal_count"] == 0
    assert empty_status.json()["proposal_review_count"] == 0
    assert empty_status.json()["promotion_count"] == 0

    built = client.post(
        "/plugins/build",
        json={
            "name": "Forge Readback Plugin",
            "description": "Readback coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": {
                "friction_summary": "Repeated Forge proposal review",
                "proposal_evidence": ["mission.forge.readback"],
                "tests": ["tests/test_api_forge.py::test_forge_proposal_and_promotion_readback"],
                "docs": ["README.md"],
                "risk_tier": "normal",
                "api_key": raw_secret,
            },
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])

    proposals = client.get("/forge/proposals/list", params={"plugin_id": plugin_id})
    assert proposals.status_code == 200
    proposals_body = proposals.json()
    assert proposals_body["total"] == 1
    proposal_item = proposals_body["items"][0]
    assert proposal_item["id"] == proposal_id
    assert proposal_item["proposal_id"] == proposal_id
    assert proposal_item["plugin_id"] == plugin_id
    assert proposal_item["friction"]["evidence"] == ["mission.forge.readback"]
    assert proposal_item["proposal_context"]["api_key"] == "[REDACTED:secret]"
    assert "raw_secret" not in str(proposals_body)
    assert raw_secret not in str(proposals_body)

    proposal_get = client.get("/forge/proposals/get", params={"id": proposal_id})
    assert proposal_get.status_code == 200
    proposal_get_body = proposal_get.json()
    assert proposal_get_body["ok"] is True
    assert proposal_get_body["item"]["proposal_id"] == proposal_id
    assert proposal_get_body["item"]["relative_path"] == f"proposals/{proposal_id}.json"
    assert raw_secret not in str(proposal_get_body)

    enabled = client.post(
        "/plugins/enable",
        json={
            "id": plugin_id,
            "reason": f"promote after readback api_key={raw_secret}",
            "actor": _PLUGIN_ACTOR,
        },
    )
    assert enabled.status_code == 200
    enabled_body = enabled.json()
    assert enabled_body["ok"] is True
    receipt_id = str(enabled_body["promotion_receipt_id"])

    promotions = client.get("/forge/promotions/list", params={"plugin_id": plugin_id})
    assert promotions.status_code == 200
    promotions_body = promotions.json()
    assert promotions_body["total"] == 1
    promotion_item = promotions_body["items"][0]
    assert promotion_item["id"] == receipt_id
    assert promotion_item["receipt_id"] == receipt_id
    assert promotion_item["plugin_id"] == plugin_id
    assert promotion_item["proposal_id"] == proposal_id
    assert promotion_item["proposal_evidence"] == ["mission.forge.readback"]
    assert promotion_item["quality"]["tests"] == ["tests/test_api_forge.py::test_forge_proposal_and_promotion_readback"]
    assert "api_key=[REDACTED:secret]" in promotion_item["reason"]
    assert raw_secret not in str(promotions_body)

    promotion_get = client.get("/forge/promotions/get", params={"id": receipt_id})
    assert promotion_get.status_code == 200
    promotion_get_body = promotion_get.json()
    assert promotion_get_body["ok"] is True
    assert promotion_get_body["item"]["receipt_id"] == receipt_id
    assert promotion_get_body["item"]["relative_path"] == f"promotions/{receipt_id}.json"
    assert raw_secret not in str(promotion_get_body)

    final_status = client.get("/forge/status")
    assert final_status.status_code == 200
    assert final_status.json()["proposal_count"] == 1
    assert final_status.json()["promotion_count"] == 1

    invalid = client.get("/forge/proposals/get", params={"id": "../outside"})
    assert invalid.status_code == 200
    assert invalid.json()["ok"] is False
    assert invalid.json()["error"] == "invalid_id"


def test_forge_proposal_decision_receipts_without_promotion(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    raw_secret = "sk-" + ("p" * 24)

    built = client.post(
        "/plugins/build",
        json={
            "name": "Forge Review Plugin",
            "description": "Proposal review coverage",
            "actor": _PLUGIN_ACTOR,
            "meta": {
                "friction_summary": "Repeated Forge proposal approval review",
                "proposal_evidence": ["mission.forge.review"],
                "tests": ["tests/test_api_forge.py::test_forge_proposal_decision_receipts_without_promotion"],
                "docs": ["README.md"],
                "risk_tier": "normal",
            },
        },
    )
    assert built.status_code == 200
    built_body = built.json()
    assert built_body["ok"] is True
    plugin_id = str(built_body["plugin_id"])
    proposal_id = str(built_body["proposal_id"])
    proposal_path = Path(str(built_body["proposal_path"]))

    denied = client.post(
        "/forge/proposals/decision",
        json={"id": proposal_id, "action": "approve", "reason": "missing scoped actor"},
    )
    assert denied.status_code == 200
    denied_body = denied.json()
    assert denied_body["ok"] is False
    assert denied_body["applied"] is False
    assert denied_body["error"] == "api_permission_denied"
    assert denied_body["governance"]["gate"] == "permission_gate"
    assert denied_body["governance"]["reason"] == "missing_actor"

    decided = client.post(
        "/forge/proposals/decision",
        json={
            "id": proposal_id,
            "action": "approve",
            "actor": _PLUGIN_ACTOR,
            "reason": f"approve proposal api_key={raw_secret}",
            "notes": f"review note token={raw_secret}",
            "meta": {"ticket": "FORGE-REVIEW", "api_key": raw_secret},
        },
    )
    assert decided.status_code == 200
    decided_body = decided.json()
    assert decided_body["ok"] is True
    assert decided_body["applied"] is True
    assert decided_body["status"] == "approved"
    assert decided_body["proposal_id"] == proposal_id
    assert decided_body["plugin_id"] == plugin_id
    assert decided_body["governance"]["promotion_authority"] is False
    assert decided_body["governance"]["execution_authority"] is False
    assert raw_secret not in str(decided_body)
    review_receipt = decided_body["review_receipt"]
    receipt_id = str(review_receipt["receipt_id"])
    receipt_path = Path(str(review_receipt["path"]))
    assert review_receipt["kind"] == "plugin.proposal.review.receipt"
    assert review_receipt["proposal_id"] == proposal_id
    assert review_receipt["plugin_id"] == plugin_id
    assert review_receipt["status"] == "approved"
    assert review_receipt["previous_status"] == "staged"
    assert "api_key=[REDACTED:secret]" in review_receipt["reason"]
    assert review_receipt["meta"]["api_key"] == "[REDACTED:secret]"

    proposal_get = client.get("/forge/proposals/get", params={"id": proposal_id})
    assert proposal_get.status_code == 200
    proposal_body = proposal_get.json()
    assert proposal_body["ok"] is True
    proposal_item = proposal_body["item"]
    assert proposal_item["status"] == "approved"
    assert proposal_item["review_receipt_id"] == receipt_id
    assert proposal_item["review"]["status"] == "approved"
    assert raw_secret not in str(proposal_body)

    reviews = client.get("/forge/proposal_reviews/list", params={"proposal_id": proposal_id})
    assert reviews.status_code == 200
    reviews_body = reviews.json()
    assert reviews_body["total"] == 1
    assert reviews_body["items"][0]["id"] == receipt_id
    assert reviews_body["items"][0]["proposal_id"] == proposal_id
    assert raw_secret not in str(reviews_body)

    review_get = client.get("/forge/proposal_reviews/get", params={"id": receipt_id})
    assert review_get.status_code == 200
    review_get_body = review_get.json()
    assert review_get_body["ok"] is True
    assert review_get_body["item"]["relative_path"] == f"proposal_reviews/{receipt_id}.json"
    assert raw_secret not in str(review_get_body)

    fetched_plugin = client.get(f"/plugins/get?id={plugin_id}")
    assert fetched_plugin.status_code == 200
    plugin_item = fetched_plugin.json()["item"]
    assert plugin_item["status"] == "staged"
    assert plugin_item["enabled"] is False

    final_status = client.get("/forge/status")
    assert final_status.status_code == 200
    final_status_body = final_status.json()
    assert final_status_body["proposal_count"] == 1
    assert final_status_body["proposal_review_count"] == 1
    assert final_status_body["promotion_count"] == 0

    persisted_text = "\n".join(
        [
            proposal_path.read_text(encoding="utf-8"),
            receipt_path.read_text(encoding="utf-8"),
        ]
    )
    assert raw_secret not in persisted_text
