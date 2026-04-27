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
