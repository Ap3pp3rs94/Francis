from __future__ import annotations

from francis.lens.desktop_organization import (
    LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
    LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV,
    LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV,
    LENS_DESKTOP_ORGANIZATION_SCOPE,
    actuate_desktop_organization_orb_sequence_item,
    create_desktop_organization_orb_sequence,
    create_desktop_organization_reversal_evidence,
    execute_desktop_organization_plan,
    lens_desktop_icon_position_evidence,
    lens_desktop_icon_semantic_targets,
    preflight_desktop_organization_execution,
    propose_desktop_organization_plan,
    run_desktop_organization_orb_sequence,
)
from francis.lens.desktop_icon_positions import (
    LENS_DESKTOP_ICON_POSITION_CAPTURE_ENV,
    capture_desktop_icon_position_evidence,
)


def _workspace() -> dict[str, int]:
    return {"left": 0, "top": 0, "width": 640, "height": 480}


def _icon(target_id: str, label: str, *, left: int, desktop_position_index: int) -> dict[str, object]:
    return {
        "target_id": target_id,
        "kind": "file_icon",
        "label": label,
        "semantic_source": "uia_shell_desktop_snapshot",
        "stable_identity": f"desktop://{label}",
        "current_rect": {"left": left, "top": 200, "width": 96, "height": 96},
        "desktop_position_index": desktop_position_index,
    }


def test_desktop_icon_semantic_targets_reads_bounded_metadata_without_paths(tmp_path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")
    (desktop / "Archive").mkdir()
    (desktop / "desktop.ini").write_text("shell metadata", encoding="utf-8")
    (desktop / "Francis.lnk").write_text("not read", encoding="utf-8")

    result = lens_desktop_icon_semantic_targets(roots=[desktop], limit=10)

    assert result["status"] == "ready"
    assert result["ready"] is True
    assert result["semantic_target_count"] == 3
    assert result["organization_ready"] is False
    assert "desktop_icon_screen_rect_mapping_not_ready" in result["organization_blockers"]
    assert result["governance"]["read_only_contract"] is True
    assert result["governance"]["raw_paths_stored"] is False
    assert result["governance"]["file_contents_read"] is False
    target_kinds = {target["label_summary"]: target["target_kind"] for target in result["semantic_targets"]}
    assert target_kinds == {
        "Archive": "folder_icon",
        "Budget": "file_icon",
        "Francis": "shortcut_icon",
    }
    serialized = str(result)
    assert str(desktop) not in serialized
    assert "not read" not in serialized
    assert all(target["screen_rect_available"] is False for target in result["semantic_targets"])


def test_desktop_icon_position_evidence_maps_semantic_targets_without_actuation(tmp_path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")
    semantic = lens_desktop_icon_semantic_targets(roots=[desktop], limit=10)
    target = semantic["semantic_targets"][0]

    result = lens_desktop_icon_position_evidence(
        semantic_readback=semantic,
        position_evidence={
            "kind": LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
            "evidence_id": "pos-evidence-1",
            "source": "uia_shell_desktop_snapshot",
            "targets": [
                {
                    "target_id": target["target_id"],
                    "stable_identity_digest": target["stable_identity_digest"],
                    "current_rect": {"left": 40, "top": 80, "width": 96, "height": 96},
                }
            ],
        },
    )

    assert result["status"] == "ready"
    assert result["position_evidence_ready"] is True
    assert result["mapped_target_count"] == 1
    assert result["organization_ready"] is False
    assert result["organization_blockers"] == [
        "desktop_reversibility_evidence_not_captured",
        "desktop_plan_approval_required",
    ]
    mapped = result["semantic_targets"][0]
    assert mapped["screen_rect_available"] is True
    assert mapped["current_rect"] == {"left": 40, "top": 80, "width": 96, "height": 96}
    assert result["governance"]["input_execution_authority"] is False
    assert result["governance"]["desktop_effect_performed"] is False
    assert "not read" not in str(result)


def test_desktop_icon_position_evidence_rejects_unknown_or_mismatched_targets(tmp_path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")
    semantic = lens_desktop_icon_semantic_targets(roots=[desktop], limit=10)
    target = semantic["semantic_targets"][0]

    result = lens_desktop_icon_position_evidence(
        semantic_readback=semantic,
        position_evidence={
            "kind": LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
            "evidence_id": "pos-evidence-1",
            "source": "uia_shell_desktop_snapshot",
            "targets": [
                {
                    "target_id": target["target_id"],
                    "stable_identity_digest": "wrong-digest",
                    "current_rect": {"left": 40, "top": 80, "width": 96, "height": 96},
                },
                {
                    "target_id": "unknown-icon",
                    "stable_identity_digest": "unknown-digest",
                    "current_rect": {"left": 120, "top": 80, "width": 96, "height": 96},
                },
            ],
        },
    )

    assert result["status"] == "blocked"
    assert result["position_evidence_ready"] is False
    assert "desktop_icon_position_evidence_identity_mismatch" in result["blockers"]
    assert "desktop_icon_position_evidence_target_mismatch" in result["blockers"]
    assert result["semantic_targets"][0]["screen_rect_available"] is False
    assert result["organization_ready"] is False
    assert result["governance"]["desktop_effect_performed"] is False


def test_desktop_icon_position_capture_is_disabled_without_explicit_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(LENS_DESKTOP_ICON_POSITION_CAPTURE_ENV, raising=False)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")

    result = capture_desktop_icon_position_evidence(roots=[desktop])

    assert result["status"] == "blocked"
    assert result["ok"] is False
    assert "desktop_icon_position_capture_disabled" in result["blockers"]
    assert result["write_attempted"] is False
    assert result["write_succeeded"] is False
    assert result["governance"]["input_execution_authority"] is False
    assert result["governance"]["desktop_effect_performed"] is False


def test_desktop_icon_position_capture_writes_bounded_evidence_from_listview_items(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")

    result = capture_desktop_icon_position_evidence(
        roots=[desktop],
        listview_items=[{"label": "Budget", "current_rect": {"left": 40, "top": 80, "width": 96, "height": 96}}],
    )

    assert result["status"] == "ready"
    assert result["ok"] is True
    assert result["matched_target_count"] == 1
    assert result["write_attempted"] is True
    assert result["write_succeeded"] is True
    assert result["position_readback"]["position_evidence_ready"] is True
    assert result["position_readback"]["semantic_targets"][0]["current_rect"] == {
        "left": 40,
        "top": 80,
        "width": 96,
        "height": 96,
    }
    evidence_path = tmp_path / "data" / "runtime" / "lens-perception" / "desktop-icon-position-evidence.json"
    assert evidence_path.exists()
    serialized = evidence_path.read_text(encoding="utf-8")
    assert str(desktop) not in serialized
    assert "not read" not in serialized
    assert "Budget.xlsx" not in serialized


def test_desktop_reversal_evidence_satisfies_execution_preflight_after_plan_approval(tmp_path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")
    semantic = lens_desktop_icon_semantic_targets(roots=[desktop], limit=10)
    target = semantic["semantic_targets"][0]
    position = lens_desktop_icon_position_evidence(
        semantic_readback=semantic,
        position_evidence={
            "kind": LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
            "evidence_id": "pos-evidence-1",
            "source": "uia_shell_desktop_snapshot",
            "targets": [
                {
                    "target_id": target["target_id"],
                    "stable_identity_digest": target["stable_identity_digest"],
                    "current_rect": {"left": 40, "top": 80, "width": 96, "height": 96},
                }
            ],
        },
    )
    plan = propose_desktop_organization_plan(
        actor="test.lens.desktop_organization",
        objective="organize desktop icons",
        targets=position["semantic_targets"],
        workspace=_workspace(),
        max_steps=10,
    )["plan"]

    reversal = create_desktop_organization_reversal_evidence(
        actor="test.lens.desktop_organization",
        plan=plan,
        position_readback=position,
    )
    execution = preflight_desktop_organization_execution(
        actor="test.lens.desktop_organization",
        plan=plan,
        approval={
            "approved": True,
            "approval_id": "approval-desktop-org",
            "approved_plan_id": plan["plan_id"],
            "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
            "semantic_target_ids": reversal["semantic_target_ids"],
            "max_step_count": len(reversal["semantic_target_ids"]),
            "reversibility_required": True,
        },
        reversal_evidence=reversal,
    )

    assert reversal["status"] == "ready"
    assert reversal["capturable"] is True
    assert reversal["reversible"] is True
    assert reversal["pre_state"]["targets"][0]["pre_rect"] == {"left": 40, "top": 80, "width": 96, "height": 96}
    assert reversal["governance"]["desktop_effect_performed"] is False
    assert execution["status"] == "blocked_actuator_not_implemented"
    assert execution["contract_gates_satisfied"] is True
    assert execution["allowed_to_execute"] is False


def test_desktop_organization_execution_rejects_arbitrary_backend_after_gates(tmp_path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "Budget.xlsx").write_text("not read", encoding="utf-8")
    semantic = lens_desktop_icon_semantic_targets(roots=[desktop], limit=10)
    target = semantic["semantic_targets"][0]
    position = lens_desktop_icon_position_evidence(
        semantic_readback=semantic,
        position_evidence={
            "kind": LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
            "evidence_id": "pos-evidence-1",
            "source": "uia_shell_desktop_snapshot",
            "targets": [
                {
                    "target_id": target["target_id"],
                    "stable_identity_digest": target["stable_identity_digest"],
                    "current_rect": {"left": 40, "top": 80, "width": 96, "height": 96},
                }
            ],
        },
    )
    plan = propose_desktop_organization_plan(
        actor="test.lens.desktop_organization",
        objective="organize desktop icons",
        targets=position["semantic_targets"],
        workspace=_workspace(),
        max_steps=10,
    )["plan"]
    reversal = create_desktop_organization_reversal_evidence(
        actor="test.lens.desktop_organization",
        plan=plan,
        position_readback=position,
    )
    calls: list[dict[str, object]] = []

    def fake_backend(received_plan: dict[str, object]) -> dict[str, object]:
        calls.append(received_plan)
        return {
            "ok": True,
            "moved_target_count": 1,
            "confirmed_target_count": 1,
            "moved_targets": [{"target_id": reversal["semantic_target_ids"][0]}],
            "confirmed_targets": [{"target_id": reversal["semantic_target_ids"][0]}],
            "blockers": [],
            "desktop_effect_performed": True,
            "desktop_effect_confirmed": True,
        }

    execution = execute_desktop_organization_plan(
        actor="test.lens.desktop_organization",
        plan=plan,
        approval={
            "approved": True,
            "approval_id": "approval-desktop-org",
            "approved_plan_id": plan["plan_id"],
            "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
            "semantic_target_ids": reversal["semantic_target_ids"],
            "max_step_count": len(reversal["semantic_target_ids"]),
            "reversibility_required": True,
        },
        reversal_evidence=reversal,
        move_backend=fake_backend,
    )

    assert execution["status"] == "blocked_orb_actuator_required"
    assert execution["ok"] is False
    assert execution["allowed_to_execute"] is False
    assert execution["desktop_effect_performed"] is False
    assert execution["desktop_effect_confirmed"] is False
    assert execution["physical_input_performed"] is False
    assert "desktop_organization_arbitrary_move_backend_rejected" in execution["blockers"]
    assert calls == []
    assert execution["orb_sequence"]["status"] == "orb_sequence_ready"


def _plan() -> dict[str, object]:
    result = propose_desktop_organization_plan(
        actor="test.lens.desktop_organization",
        objective="organize the desktop icons",
        targets=[
            _icon("icon-b", "Budget.xlsx", left=220, desktop_position_index=1),
            _icon("icon-a", "Archive", left=20, desktop_position_index=0),
        ],
        workspace=_workspace(),
        max_steps=10,
    )
    return result["plan"]


def _approved_sequence() -> dict[str, object]:
    plan = _plan()
    target_ids = [
        step["semantic_target"]["target_id"]
        for step in plan["steps"]  # type: ignore[index]
    ]
    return create_desktop_organization_orb_sequence(
        actor="test.lens.desktop_organization",
        plan=plan,
        approval={
            "approved": True,
            "approval_id": "approval-desktop-org",
            "approved_plan_id": plan["plan_id"],
            "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
            "semantic_target_ids": target_ids,
            "max_step_count": len(target_ids),
            "reversibility_required": True,
        },
        reversal_evidence={
            "evidence_id": "pre-state-desktop-org",
            "capturable": True,
            "reversible": True,
            "semantic_target_ids": target_ids,
        },
    )


def test_desktop_organization_rejects_coordinate_only_drag_targets() -> None:
    result = propose_desktop_organization_plan(
        actor="test.lens.desktop_organization",
        objective="move the icon",
        targets=[{"x": 847, "y": 203, "target_x": 300, "target_y": 500}],
        workspace=_workspace(),
    )

    assert result["ok"] is False
    assert result["status"] == "denied"
    assert "coordinate_only_target_rejected" in result["blockers"]
    assert "lens_semantic_target_mapping_required" in result["blockers"]
    assert result["physical_input_performed"] is False
    assert result["desktop_effect_performed"] is False
    assert result["governance"]["coordinate_only_drag_authority"] is False


def test_desktop_organization_excludes_configured_game_targets(monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_LENS_GAME_TARGET_ID", "sand")
    monkeypatch.setenv("FRANCIS_LENS_GAME_TARGET_PROCESSES", "Sand.exe,Sand_BE.exe")

    result = propose_desktop_organization_plan(
        actor="test.lens.desktop_organization",
        objective="organize desktop icons",
        targets=[
            _icon("icon-game", "Sand", left=20, desktop_position_index=23),
            _icon("icon-a", "Archive", left=220, desktop_position_index=0),
        ],
        workspace=_workspace(),
        max_steps=10,
    )

    assert result["ok"] is False
    assert result["status"] == "denied"
    assert "desktop_organization_game_target_isolated" in result["blockers"]
    assert result["execution_authority"] is False
    assert result["desktop_effect_performed"] is False


def test_desktop_organization_plan_decides_bounded_icon_destinations() -> None:
    result = propose_desktop_organization_plan(
        actor="test.lens.desktop_organization",
        objective="organize desktop icons",
        targets=[
            _icon("icon-b", "Budget.xlsx", left=220, desktop_position_index=1),
            _icon("icon-a", "Archive", left=20, desktop_position_index=0),
        ],
        workspace=_workspace(),
        max_steps=10,
    )

    assert result["ok"] is True
    assert result["status"] == "plan_proposed"
    assert result["requires_plan_level_approval"] is True
    assert result["requires_reversibility_evidence"] is True
    assert result["preview_only"] is True
    plan = result["plan"]
    assert plan["requires_plan_level_approval"] is True
    assert plan["execution_authority"] is False
    assert [step["semantic_target"]["target_id"] for step in plan["steps"]] == ["icon-a", "icon-b"]
    assert plan["steps"][0]["to_rect"] == {"left": 16, "top": 16, "width": 96, "height": 96}
    assert plan["steps"][1]["to_rect"] == {"left": 128, "top": 16, "width": 96, "height": 96}
    assert "desktop://" not in str(plan)


def test_desktop_organization_orb_sequence_is_one_visible_drag_per_step() -> None:
    plan = _plan()
    target_ids = [
        step["semantic_target"]["target_id"]
        for step in plan["steps"]  # type: ignore[index]
    ]

    result = create_desktop_organization_orb_sequence(
        actor="test.lens.desktop_organization",
        plan=plan,
        approval={
            "approved": True,
            "approval_id": "approval-desktop-org",
            "approved_plan_id": plan["plan_id"],
            "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
            "semantic_target_ids": target_ids,
            "max_step_count": len(target_ids),
            "reversibility_required": True,
        },
        reversal_evidence={
            "evidence_id": "pre-state-desktop-org",
            "capturable": True,
            "reversible": True,
            "semantic_target_ids": target_ids,
        },
    )

    assert result["status"] == "orb_sequence_ready"
    assert result["ok"] is True
    assert result["allowed_to_execute"] is False
    assert result["execution_attempted"] is False
    assert result["desktop_effect_performed"] is False
    assert result["sequence_item_count"] == 2
    assert result["requires_sequential_consumption"] is True
    assert result["governance"]["one_desktop_target_per_sequence_item"] is True
    assert result["governance"]["batch_desktop_mutation"] is False
    first, second = result["sequence_items"]
    assert [item["order"] for item in result["sequence_items"]] == [1, 2]
    assert first["orb_intent"] == {
        "kind": "orb_carry_desktop_icon",
        "metadata": {
            "desktop_organization_plan_id": plan["plan_id"],
            "desktop_organization_step_id": "desktop-org-step-001",
            "semantic_target_id": "icon-a",
            "semantic_target_kind": "file_icon",
            "stable_identity_digest": first["semantic_target"]["stable_identity_digest"],
            "desktop_position_index": 0,
            "requires_visible_orb_body": True,
            "single_action_only": True,
            "batch_desktop_mutation": False,
            "desktop_shell_target_required": True,
        },
    }
    assert first["from_center"] == {"x": 68, "y": 232}
    assert first["to_center"] == {"x": 64, "y": 48}
    assert second["from_center"] == {"x": 268, "y": 232}
    assert second["to_center"] == {"x": 176, "y": 48}
    assert second["orb_intent"]["metadata"]["desktop_position_index"] == 1
    assert all(item["requires_single_action_consumption"] is True for item in result["sequence_items"])
    assert all(item["physical_input_performed"] is False for item in result["sequence_items"])
    assert "desktop://" not in str(result)


def test_desktop_organization_orb_sequence_runner_traces_one_item_at_a_time() -> None:
    plan = _plan()
    target_ids = [
        step["semantic_target"]["target_id"]
        for step in plan["steps"]  # type: ignore[index]
    ]
    sequence = create_desktop_organization_orb_sequence(
        actor="test.lens.desktop_organization",
        plan=plan,
        approval={
            "approved": True,
            "approval_id": "approval-desktop-org",
            "approved_plan_id": plan["plan_id"],
            "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
            "semantic_target_ids": target_ids,
            "max_step_count": len(target_ids),
            "reversibility_required": True,
        },
        reversal_evidence={
            "evidence_id": "pre-state-desktop-org",
            "capturable": True,
            "reversible": True,
            "semantic_target_ids": target_ids,
        },
    )
    calls: list[dict[str, object]] = []

    def fake_submitter(payload: dict[str, object]) -> dict[str, object]:
        calls.append(payload)
        intent = payload["intent"]
        assert isinstance(intent, dict)
        return {
            "ok": True,
            "status": "complete",
            "feedback_state": "complete",
            "intent": intent,
            "backend": {
                "result": {
                    "pointer_state": {"x": intent["x"], "y": intent["y"]},
                    "desktop_effect_performed": False,
                    "physical_input_performed": False,
                }
            },
            "operator_receipt_id": f"receipt-{len(calls)}",
            "governance": {
                "virtual_pointer_only": True,
                "uses_user_os_cursor": False,
                "user_mouse_taken": False,
                "physical_input_performed": False,
                "desktop_effect_performed": False,
            },
        }

    result = run_desktop_organization_orb_sequence(
        actor="test.lens.desktop_organization",
        orb_sequence=sequence,
        submitter=fake_submitter,
    )

    assert result["status"] == "orb_visible_sequence_complete"
    assert result["ok"] is True
    assert result["consumed_item_count"] == 2
    assert result["orb_pointer_state_written"] is True
    assert result["operator_receipts_written"] is True
    assert result["desktop_effect_performed"] is False
    assert result["physical_input_performed"] is False
    assert result["uses_user_os_cursor"] is False
    assert [call["intent"]["kind"] for call in calls] == ["move_to", "move_to", "move_to", "move_to"]  # type: ignore[index]
    assert [call["intent"]["x"] for call in calls] == [68, 64, 268, 176]  # type: ignore[index]
    assert [call["intent"]["y"] for call in calls] == [232, 48, 232, 48]  # type: ignore[index]
    assert result["consumed_items"][0]["source_move"]["operator_receipt_id"] == "receipt-1"
    assert result["consumed_items"][0]["destination_move"]["operator_receipt_id"] == "receipt-2"


def test_desktop_organization_orb_sequence_runner_blocks_unexpected_desktop_effect() -> None:
    plan = _plan()
    target_ids = [
        step["semantic_target"]["target_id"]
        for step in plan["steps"]  # type: ignore[index]
    ]
    sequence = create_desktop_organization_orb_sequence(
        actor="test.lens.desktop_organization",
        plan=plan,
        approval={
            "approved": True,
            "approval_id": "approval-desktop-org",
            "approved_plan_id": plan["plan_id"],
            "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
            "semantic_target_ids": target_ids,
            "max_step_count": len(target_ids),
            "reversibility_required": True,
        },
        reversal_evidence={
            "evidence_id": "pre-state-desktop-org",
            "capturable": True,
            "reversible": True,
            "semantic_target_ids": target_ids,
        },
    )
    calls: list[dict[str, object]] = []

    def unsafe_submitter(payload: dict[str, object]) -> dict[str, object]:
        calls.append(payload)
        intent = payload["intent"]
        assert isinstance(intent, dict)
        return {
            "ok": True,
            "status": "complete",
            "feedback_state": "complete",
            "intent": intent,
            "backend": {"result": {"pointer_state": {"x": intent["x"], "y": intent["y"]}}},
            "operator_receipt_id": "receipt-unsafe",
            "governance": {
                "virtual_pointer_only": True,
                "uses_user_os_cursor": False,
                "user_mouse_taken": False,
                "physical_input_performed": False,
                "desktop_effect_performed": True,
            },
        }

    result = run_desktop_organization_orb_sequence(
        actor="test.lens.desktop_organization",
        orb_sequence=sequence,
        submitter=unsafe_submitter,
    )

    assert result["status"] == "blocked"
    assert result["ok"] is False
    assert "orb_pointer_desktop_effect_rejected" in result["blockers"]
    assert result["consumed_item_count"] == 1
    assert len(calls) == 1
    assert result["desktop_effect_performed"] is False


def test_desktop_organization_orb_item_actuation_denies_without_explicit_gate(monkeypatch) -> None:
    monkeypatch.delenv(LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV, raising=False)
    sequence = _approved_sequence()
    calls: list[dict[str, object]] = []

    result = actuate_desktop_organization_orb_sequence_item(
        actor="test.lens.desktop_organization",
        orb_sequence=sequence,
        order=1,
        post_position_readback={
            "position_evidence_ready": True,
            "semantic_targets": [
                {
                    "target_id": "icon-a",
                    "current_rect": {"left": 16, "top": 16, "width": 96, "height": 96},
                }
            ],
        },
        submitter=lambda payload: calls.append(payload) or {},
    )

    assert result["status"] == "denied"
    assert result["ok"] is False
    assert "desktop_organization_orb_actuation_env_gate_required" in result["blockers"]
    assert result["execution_attempted"] is False
    assert result["desktop_effect_performed"] is False
    assert calls == []


def test_desktop_organization_orb_item_actuation_denies_without_shell_adapter(monkeypatch) -> None:
    monkeypatch.setenv(LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV, "1")
    monkeypatch.delenv(LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV, raising=False)
    sequence = _approved_sequence()
    calls: list[dict[str, object]] = []

    result = actuate_desktop_organization_orb_sequence_item(
        actor="test.lens.desktop_organization",
        orb_sequence=sequence,
        order=1,
        post_position_readback={
            "position_evidence_ready": True,
            "semantic_targets": [
                {
                    "target_id": "icon-a",
                    "current_rect": {"left": 16, "top": 16, "width": 96, "height": 96},
                }
            ],
        },
        submitter=lambda payload: calls.append(payload) or {},
    )

    assert result["status"] == "denied"
    assert result["ok"] is False
    assert "desktop_organization_shell_adapter_env_gate_required" in result["blockers"]
    assert result["execution_attempted"] is False
    assert result["governance"]["desktop_shell_adapter_required"] is True
    assert result["governance"]["desktop_shell_adapter_enabled"] is False
    assert calls == []


def test_desktop_organization_orb_item_actuation_confirms_single_shell_adapter_move(monkeypatch) -> None:
    monkeypatch.setenv(LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV, "1")
    monkeypatch.setenv(LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV, "1")
    sequence = _approved_sequence()
    calls: list[dict[str, object]] = []
    adapter_calls: list[dict[str, object]] = []

    def fake_submitter(payload: dict[str, object]) -> dict[str, object]:
        calls.append(payload)
        intent = payload["intent"]
        assert isinstance(intent, dict)
        assert intent["kind"] == "orb_carry_desktop_icon"
        assert intent["metadata"]["semantic_target_id"] == "icon-a"
        assert intent["metadata"]["francis_owned_cursor"] is True
        return {
            "ok": True,
            "status": "complete",
            "feedback_state": "complete",
            "intent": intent,
            "backend": {
                "result": {
                    "desktop_effect_performed": False,
                    "physical_input_performed": False,
                    "pointer_state": {"x": intent["x"], "y": intent["y"]},
                }
            },
            "operator_receipt_id": f"receipt-{intent['metadata']['visible_orb_phase']}",
            "governance": {
                "virtual_pointer_only": True,
                "uses_user_os_cursor": False,
                "user_mouse_taken": False,
                "physical_input_performed": False,
                "desktop_effect_performed": False,
            },
        }

    def fake_position_adapter(**kwargs: object) -> dict[str, object]:
        adapter_calls.append(kwargs)
        return {
            "ok": True,
            "status": "applied",
            "desktop_effect_performed": True,
            "uses_user_os_cursor": False,
            "physical_input_performed": False,
            "blockers": [],
        }

    result = actuate_desktop_organization_orb_sequence_item(
        actor="test.lens.desktop_organization",
        orb_sequence=sequence,
        order=1,
        post_position_readback={
            "position_evidence_ready": True,
            "semantic_targets": [
                {
                    "target_id": "icon-a",
                    "current_rect": {"left": 16, "top": 16, "width": 96, "height": 96},
                }
            ],
        },
        submitter=fake_submitter,
        position_adapter=fake_position_adapter,
    )

    assert result["status"] == "desktop_item_actuation_confirmed"
    assert result["ok"] is True
    assert result["sequence_item_id"] == "desktop-org-orb-item-001"
    assert result["semantic_target_id"] == "icon-a"
    assert result["operator_receipt_id"] == "receipt-destination_center"
    assert result["operator_receipt_ids"] == [
        "receipt-source_center",
        "receipt-carry_001",
        "receipt-carry_002",
        "receipt-carry_003",
        "receipt-carry_004",
        "receipt-carry_005",
        "receipt-destination_center",
    ]
    assert result["visual_orb_cursor_used"] is True
    assert result["carry_frame_count"] == 6
    assert result["shell_adapter_status"] == "applied"
    assert result["desktop_effect_performed"] is True
    assert result["desktop_effect_confirmed"] is True
    assert result["physical_input_performed"] is False
    assert result["uses_user_os_cursor"] is False
    assert result["readback"]["confirmed"] is True
    assert len(calls) == 7
    assert calls[0]["intent"]["kind"] == "orb_carry_desktop_icon"  # type: ignore[index]
    assert calls[0]["intent"]["metadata"]["carry_phase"] == "source_center"  # type: ignore[index]
    assert calls[0]["intent"]["x"] == 68  # type: ignore[index]
    assert calls[0]["intent"]["y"] == 232  # type: ignore[index]
    assert calls[-1]["intent"]["kind"] == "orb_carry_desktop_icon"  # type: ignore[index]
    assert calls[-1]["intent"]["metadata"]["carry_phase"] == "destination_center"  # type: ignore[index]
    assert calls[-1]["intent"]["x"] == 64  # type: ignore[index]
    assert calls[-1]["intent"]["y"] == 48  # type: ignore[index]
    assert [call["desktop_position_index"] for call in adapter_calls] == [0, 0, 0, 0, 0, 0]
    assert adapter_calls[0]["target_id"] == "icon-a"
    assert adapter_calls[0]["to_rect"] == {"left": 19, "top": 169, "width": 96, "height": 96}
    assert adapter_calls[-1]["to_rect"] == {"left": 16, "top": 16, "width": 96, "height": 96}


def test_desktop_organization_orb_item_actuation_captures_post_readback_after_shell_adapter(monkeypatch) -> None:
    monkeypatch.setenv(LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV, "1")
    monkeypatch.setenv(LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV, "1")
    sequence = _approved_sequence()
    events: list[str] = []

    def fake_submitter(payload: dict[str, object]) -> dict[str, object]:
        events.append("submit")
        intent = payload["intent"]
        assert isinstance(intent, dict)
        return {
            "ok": True,
            "status": "complete",
            "feedback_state": "complete",
            "intent": intent,
            "backend": {
                "result": {
                    "desktop_effect_performed": False,
                    "physical_input_performed": False,
                    "pointer_state": {"x": intent["x"], "y": intent["y"]},
                }
            },
            "operator_receipt_id": f"receipt-{intent['metadata']['visible_orb_phase']}",
            "governance": {
                "virtual_pointer_only": True,
                "uses_user_os_cursor": False,
                "user_mouse_taken": False,
                "physical_input_performed": False,
                "desktop_effect_performed": False,
            },
        }

    def fake_position_adapter(**_kwargs: object) -> dict[str, object]:
        events.append("adapter")
        return {
            "ok": True,
            "status": "applied",
            "desktop_effect_performed": True,
            "uses_user_os_cursor": False,
            "physical_input_performed": False,
            "blockers": [],
        }

    def fake_post_readback() -> dict[str, object]:
        events.append("readback")
        return {
            "position_evidence_ready": True,
            "semantic_targets": [
                {
                    "target_id": "icon-a",
                    "current_rect": {"left": 16, "top": 16, "width": 96, "height": 96},
                }
            ],
        }

    result = actuate_desktop_organization_orb_sequence_item(
        actor="test.lens.desktop_organization",
        orb_sequence=sequence,
        order=1,
        post_position_readback_provider=fake_post_readback,
        submitter=fake_submitter,
        position_adapter=fake_position_adapter,
    )

    assert result["status"] == "desktop_item_actuation_confirmed"
    assert result["ok"] is True
    assert events == ["submit", *["submit", "adapter"] * 6, "readback"]
    assert result["readback"]["confirmed"] is True


def test_desktop_organization_orb_item_actuation_blocks_readback_mismatch(monkeypatch) -> None:
    monkeypatch.setenv(LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV, "1")
    monkeypatch.setenv(LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV, "1")
    sequence = _approved_sequence()

    def fake_submitter(payload: dict[str, object]) -> dict[str, object]:
        intent = payload["intent"]
        assert isinstance(intent, dict)
        return {
            "ok": True,
            "status": "complete",
            "feedback_state": "complete",
            "intent": intent,
            "backend": {
                "result": {
                    "desktop_effect_performed": False,
                    "physical_input_performed": False,
                    "pointer_state": {"x": intent["x"], "y": intent["y"]},
                }
            },
            "operator_receipt_id": f"receipt-{intent['metadata']['visible_orb_phase']}",
            "governance": {
                "virtual_pointer_only": True,
                "uses_user_os_cursor": False,
                "user_mouse_taken": False,
                "physical_input_performed": False,
                "desktop_effect_performed": False,
            },
        }

    def fake_position_adapter(**_kwargs: object) -> dict[str, object]:
        return {
            "ok": True,
            "status": "applied",
            "desktop_effect_performed": True,
            "uses_user_os_cursor": False,
            "physical_input_performed": False,
            "blockers": [],
        }

    result = actuate_desktop_organization_orb_sequence_item(
        actor="test.lens.desktop_organization",
        orb_sequence=sequence,
        order=1,
        post_position_readback={
            "position_evidence_ready": True,
            "semantic_targets": [
                {
                    "target_id": "icon-a",
                    "current_rect": {"left": 240, "top": 240, "width": 96, "height": 96},
                }
            ],
        },
        submitter=fake_submitter,
        position_adapter=fake_position_adapter,
    )

    assert result["status"] == "blocked"
    assert result["ok"] is False
    assert result["desktop_effect_performed"] is True
    assert result["desktop_effect_confirmed"] is False
    assert "desktop_organization_post_action_position_mismatch" in result["blockers"]


def test_desktop_organization_execution_denies_without_approval_and_reversal() -> None:
    result = preflight_desktop_organization_execution(
        actor="test.lens.desktop_organization",
        plan=_plan(),
        approval={},
        reversal_evidence={},
    )

    assert result["status"] == "denied"
    assert result["allowed_to_execute"] is False
    assert "plan_level_approval_required" in result["blockers"]
    assert "pre_state_required" in result["blockers"]
    assert "reversibility_evidence_required" in result["blockers"]
    assert result["execution_attempted"] is False
    assert result["physical_input_performed"] is False
    assert result["desktop_effect_performed"] is False


def test_desktop_organization_execution_still_blocks_when_contract_gates_pass() -> None:
    plan = _plan()
    target_ids = [
        step["semantic_target"]["target_id"]
        for step in plan["steps"]  # type: ignore[index]
    ]
    result = preflight_desktop_organization_execution(
        actor="test.lens.desktop_organization",
        plan=plan,
        approval={
            "approved": True,
            "approval_id": "approval-desktop-org",
            "approved_plan_id": plan["plan_id"],
            "scopes": [LENS_DESKTOP_ORGANIZATION_SCOPE],
            "semantic_target_ids": target_ids,
            "max_step_count": len(target_ids),
            "reversibility_required": True,
        },
        reversal_evidence={
            "evidence_id": "pre-state-desktop-org",
            "capturable": True,
            "reversible": True,
            "semantic_target_ids": target_ids,
        },
    )

    assert result["status"] == "blocked_actuator_not_implemented"
    assert result["blockers"] == ["desktop_reorganization_actuator_not_implemented"]
    assert result["contract_gates_satisfied"] is True
    assert result["execution_ready_for_future_actuator"] is True
    assert result["allowed_to_execute"] is False
    assert result["execution_attempted"] is False
    assert result["physical_input_performed"] is False
    assert result["desktop_effect_performed"] is False
