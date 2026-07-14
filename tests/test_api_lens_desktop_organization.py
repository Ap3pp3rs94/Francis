from __future__ import annotations

import json
from pathlib import Path

from francis.lens.desktop_organization import (
    LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
    LENS_DESKTOP_ORGANIZATION_SCOPE,
)


def _client(monkeypatch, tmp_path: Path):
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({"test.lens.desktop_organization": [LENS_DESKTOP_ORGANIZATION_SCOPE]}),
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    return TestClient(create_app())


def test_desktop_organization_plan_route_denies_coordinate_only_drag(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/lens/orb/desktop-organization/plan",
        json={
            "actor": "test.lens.desktop_organization",
            "objective": "move the icon",
            "workspace": {"left": 0, "top": 0, "width": 640, "height": 480},
            "targets": [{"x": 847, "y": 203, "target_x": 300, "target_y": 500}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "denied"
    assert "coordinate_only_target_rejected" in body["blockers"]
    assert body["physical_input_performed"] is False
    assert body["desktop_effect_performed"] is False


def test_desktop_organization_semantic_targets_route_is_read_only(monkeypatch, tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")
    (desktop / "Archive").mkdir()
    monkeypatch.setenv("FRANCIS_LENS_DESKTOP_SEMANTIC_ROOTS", str(desktop))
    client = _client(monkeypatch, tmp_path)

    response = client.get(
        "/lens/orb/desktop-organization/semantic-targets",
        params={"actor": "test.lens.desktop_organization"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["semantic_target_count"] == 2
    assert body["organization_ready"] is False
    assert "desktop_icon_screen_rect_mapping_not_ready" in body["organization_blockers"]
    assert body["governance"]["read_only_contract"] is True
    assert body["governance"]["file_contents_read"] is False
    assert body["governance"]["filesystem_write"] is False
    serialized = str(body)
    assert str(desktop) not in serialized
    assert "not read" not in serialized


def test_desktop_organization_position_evidence_route_maps_bounded_rectangles(
    monkeypatch,
    tmp_path: Path,
) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")
    monkeypatch.setenv("FRANCIS_LENS_DESKTOP_SEMANTIC_ROOTS", str(desktop))
    client = _client(monkeypatch, tmp_path)
    semantic = client.get(
        "/lens/orb/desktop-organization/semantic-targets",
        params={"actor": "test.lens.desktop_organization"},
    ).json()
    target = semantic["semantic_targets"][0]
    evidence_path = tmp_path / "repo" / "data" / "runtime" / "lens-perception" / "desktop-icon-position-evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(
            {
                "kind": LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
                "evidence_id": "pos-evidence-route",
                "source": "uia_shell_desktop_snapshot",
                "targets": [
                    {
                        "target_id": target["target_id"],
                        "stable_identity_digest": target["stable_identity_digest"],
                        "current_rect": {"left": 40, "top": 80, "width": 96, "height": 96},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    response = client.get(
        "/lens/orb/desktop-organization/position-evidence",
        params={"actor": "test.lens.desktop_organization"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["position_evidence_ready"] is True
    assert body["mapped_target_count"] == 1
    assert body["semantic_targets"][0]["screen_rect_available"] is True
    assert body["semantic_targets"][0]["current_rect"] == {"left": 40, "top": 80, "width": 96, "height": 96}
    assert body["organization_ready"] is False
    assert body["governance"]["input_execution_authority"] is False
    assert body["governance"]["desktop_effect_performed"] is False
    serialized = str(body)
    assert str(desktop) not in serialized
    assert "not read" not in serialized


def test_desktop_organization_position_capture_route_is_permission_gated(monkeypatch, tmp_path: Path) -> None:
    from francis.api.routes import lens as lens_routes

    calls: list[dict[str, object]] = []

    def fake_capture(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "kind": "lens.orb.desktop_organization.position_capture",
            "status": "blocked",
            "ok": False,
            "blockers": ["desktop_icon_position_capture_disabled"],
            "write_attempted": False,
            "write_succeeded": False,
            "governance": {
                "input_execution_authority": False,
                "desktop_effect_performed": False,
            },
        }

    monkeypatch.setattr(lens_routes, "capture_desktop_icon_position_evidence", fake_capture)
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/lens/orb/desktop-organization/position-evidence/capture",
        json={"actor": "test.lens.desktop_organization", "limit": 12, "write_evidence": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["governance"]["input_execution_authority"] is False
    assert calls == [{"limit": 12, "write_evidence": False}]


def test_desktop_organization_reversal_evidence_route_creates_bounded_pre_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")
    monkeypatch.setenv("FRANCIS_LENS_DESKTOP_SEMANTIC_ROOTS", str(desktop))
    client = _client(monkeypatch, tmp_path)
    semantic = client.get(
        "/lens/orb/desktop-organization/semantic-targets",
        params={"actor": "test.lens.desktop_organization"},
    ).json()
    target = semantic["semantic_targets"][0]
    position = {
        "kind": LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
        "position_evidence_ready": True,
        "semantic_targets": [
            {
                **target,
                "screen_rect_available": True,
                "current_rect": {"left": 40, "top": 80, "width": 96, "height": 96},
            }
        ],
    }
    plan = client.post(
        "/lens/orb/desktop-organization/plan",
        json={
            "actor": "test.lens.desktop_organization",
            "objective": "organize desktop icons",
            "workspace": {"left": 0, "top": 0, "width": 640, "height": 480},
            "targets": position["semantic_targets"],
        },
    ).json()["plan"]

    response = client.post(
        "/lens/orb/desktop-organization/reversal-evidence",
        json={
            "actor": "test.lens.desktop_organization",
            "plan": plan,
            "position_readback": position,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["capturable"] is True
    assert body["reversible"] is True
    assert body["pre_state"]["targets"][0]["pre_rect"] == {"left": 40, "top": 80, "width": 96, "height": 96}
    assert body["governance"]["input_execution_authority"] is False
    assert body["governance"]["desktop_effect_performed"] is False
    assert str(desktop) not in str(body)


def test_desktop_organization_execute_route_stays_preflight_only(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    plan_body = client.post(
        "/lens/orb/desktop-organization/plan",
        json={
            "actor": "test.lens.desktop_organization",
            "objective": "organize desktop icons",
            "workspace": {"left": 0, "top": 0, "width": 640, "height": 480},
            "targets": [
                {
                    "target_id": "icon-a",
                    "kind": "file_icon",
                    "label": "Archive",
                    "semantic_source": "uia_shell_desktop_snapshot",
                    "stable_identity": "desktop://Archive",
                    "current_rect": {"left": 20, "top": 200, "width": 96, "height": 96},
                }
            ],
        },
    ).json()
    plan = plan_body["plan"]
    target_ids = [step["semantic_target"]["target_id"] for step in plan["steps"]]

    response = client.post(
        "/lens/orb/desktop-organization/execute",
        json={
            "actor": "test.lens.desktop_organization",
            "plan": plan,
            "approval": {
                "approved": True,
                "approval_id": "approval-desktop-org",
                "approved_plan_id": plan["plan_id"],
                "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
                "semantic_target_ids": target_ids,
                "max_step_count": len(target_ids),
                "reversibility_required": True,
            },
            "reversal_evidence": {
                "evidence_id": "pre-state-desktop-org",
                "capturable": True,
                "reversible": True,
                "semantic_target_ids": target_ids,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked_orb_actuator_required"
    assert body["preflight"]["contract_gates_satisfied"] is True
    assert body["allowed_to_execute"] is False
    assert body["execution_attempted"] is False
    assert body["physical_input_performed"] is False
    assert body["desktop_effect_performed"] is False


def test_desktop_organization_orb_sequence_route_returns_visible_only_items(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    plan_body = client.post(
        "/lens/orb/desktop-organization/plan",
        json={
            "actor": "test.lens.desktop_organization",
            "objective": "organize desktop icons",
            "workspace": {"left": 0, "top": 0, "width": 640, "height": 480},
            "targets": [
                {
                    "target_id": "icon-b",
                    "kind": "file_icon",
                    "label": "Budget.xlsx",
                    "semantic_source": "uia_shell_desktop_snapshot",
                    "stable_identity": "desktop://Budget.xlsx",
                    "current_rect": {"left": 220, "top": 200, "width": 96, "height": 96},
                },
                {
                    "target_id": "icon-a",
                    "kind": "file_icon",
                    "label": "Archive",
                    "semantic_source": "uia_shell_desktop_snapshot",
                    "stable_identity": "desktop://Archive",
                    "current_rect": {"left": 20, "top": 200, "width": 96, "height": 96},
                },
            ],
        },
    ).json()
    plan = plan_body["plan"]
    target_ids = [step["semantic_target"]["target_id"] for step in plan["steps"]]

    response = client.post(
        "/lens/orb/desktop-organization/orb-sequence",
        json={
            "actor": "test.lens.desktop_organization",
            "plan": plan,
            "approval": {
                "approved": True,
                "approval_id": "approval-desktop-org",
                "approved_plan_id": plan["plan_id"],
                "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
                "semantic_target_ids": target_ids,
                "max_step_count": len(target_ids),
                "reversibility_required": True,
            },
            "reversal_evidence": {
                "evidence_id": "pre-state-desktop-org",
                "capturable": True,
                "reversible": True,
                "semantic_target_ids": target_ids,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "orb_sequence_ready"
    assert body["sequence_item_count"] == 2
    assert body["requires_visible_orb_pointer"] is True
    assert body["requires_sequential_consumption"] is True
    assert body["allowed_to_execute"] is False
    assert body["desktop_effect_performed"] is False
    assert body["governance"]["one_desktop_target_per_sequence_item"] is True
    assert body["governance"]["batch_desktop_mutation"] is False
    assert [item["orb_intent"]["kind"] for item in body["sequence_items"]] == [
        "orb_carry_desktop_icon",
        "orb_carry_desktop_icon",
    ]
    assert [item["semantic_target"]["target_id"] for item in body["sequence_items"]] == ["icon-a", "icon-b"]
    assert all(item["physical_input_performed"] is False for item in body["sequence_items"])
    assert "desktop://" not in str(body)


def test_desktop_organization_orb_sequence_run_route_moves_orb_pointer_only(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    plan_body = client.post(
        "/lens/orb/desktop-organization/plan",
        json={
            "actor": "test.lens.desktop_organization",
            "objective": "organize desktop icons",
            "workspace": {"left": 0, "top": 0, "width": 640, "height": 480},
            "targets": [
                {
                    "target_id": "icon-a",
                    "kind": "file_icon",
                    "label": "Archive",
                    "semantic_source": "uia_shell_desktop_snapshot",
                    "stable_identity": "desktop://Archive",
                    "current_rect": {"left": 20, "top": 200, "width": 96, "height": 96},
                }
            ],
        },
    ).json()
    plan = plan_body["plan"]
    target_ids = [step["semantic_target"]["target_id"] for step in plan["steps"]]
    sequence = client.post(
        "/lens/orb/desktop-organization/orb-sequence",
        json={
            "actor": "test.lens.desktop_organization",
            "plan": plan,
            "approval": {
                "approved": True,
                "approval_id": "approval-desktop-org",
                "approved_plan_id": plan["plan_id"],
                "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
                "semantic_target_ids": target_ids,
                "max_step_count": len(target_ids),
                "reversibility_required": True,
            },
            "reversal_evidence": {
                "evidence_id": "pre-state-desktop-org",
                "capturable": True,
                "reversible": True,
                "semantic_target_ids": target_ids,
            },
        },
    ).json()

    response = client.post(
        "/lens/orb/desktop-organization/orb-sequence/run",
        json={
            "actor": "test.lens.desktop_organization",
            "orb_sequence": sequence,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "orb_visible_sequence_complete"
    assert body["ok"] is True
    assert body["consumed_item_count"] == 1
    assert body["orb_pointer_state_written"] is True
    assert body["operator_receipts_written"] is True
    assert body["desktop_effect_performed"] is False
    assert body["physical_input_performed"] is False
    assert body["uses_user_os_cursor"] is False
    assert body["consumed_items"][0]["source_move"]["x"] == 68
    assert body["consumed_items"][0]["source_move"]["y"] == 232
    assert body["consumed_items"][0]["destination_move"]["x"] == 64
    assert body["consumed_items"][0]["destination_move"]["y"] == 48
    assert "desktop://" not in str(body)


def test_desktop_organization_orb_item_actuation_route_is_default_denied(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FRANCIS_LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENABLE", raising=False)
    client = _client(monkeypatch, tmp_path)
    plan_body = client.post(
        "/lens/orb/desktop-organization/plan",
        json={
            "actor": "test.lens.desktop_organization",
            "objective": "organize desktop icons",
            "workspace": {"left": 0, "top": 0, "width": 640, "height": 480},
            "targets": [
                {
                    "target_id": "icon-a",
                    "kind": "file_icon",
                    "label": "Archive",
                    "semantic_source": "uia_shell_desktop_snapshot",
                    "stable_identity": "desktop://Archive",
                    "current_rect": {"left": 20, "top": 200, "width": 96, "height": 96},
                }
            ],
        },
    ).json()
    plan = plan_body["plan"]
    target_ids = [step["semantic_target"]["target_id"] for step in plan["steps"]]
    sequence = client.post(
        "/lens/orb/desktop-organization/orb-sequence",
        json={
            "actor": "test.lens.desktop_organization",
            "plan": plan,
            "approval": {
                "approved": True,
                "approval_id": "approval-desktop-org",
                "approved_plan_id": plan["plan_id"],
                "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
                "semantic_target_ids": target_ids,
                "max_step_count": len(target_ids),
                "reversibility_required": True,
            },
            "reversal_evidence": {
                "evidence_id": "pre-state-desktop-org",
                "capturable": True,
                "reversible": True,
                "semantic_target_ids": target_ids,
            },
        },
    ).json()

    response = client.post(
        "/lens/orb/desktop-organization/orb-sequence/actuate-item",
        json={
            "actor": "test.lens.desktop_organization",
            "orb_sequence": sequence,
            "order": 1,
            "post_position_readback": {
                "position_evidence_ready": True,
                "semantic_targets": [
                    {
                        "target_id": "icon-a",
                        "current_rect": {"left": 16, "top": 16, "width": 96, "height": 96},
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "denied"
    assert body["ok"] is False
    assert "desktop_organization_orb_actuation_env_gate_required" in body["blockers"]
    assert body["execution_attempted"] is False
    assert body["desktop_effect_performed"] is False
    assert body["physical_input_performed"] is False
    assert body["uses_user_os_cursor"] is False
