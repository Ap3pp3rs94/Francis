from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.powershell_script_runner import run_powershell_script


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fr017-stage17-validation-gate.ps1"
REQUIRED_GATE_SCRIPTS = [
    "fr017-stage17-validation-gate.ps1",
    "fr017-measurement-intake.ps1",
    "fr017-mockup-readiness-gate.ps1",
    "fr017-mannequin-interface-gate.ps1",
    "fr017-pilot-static-fit-gate.ps1",
    "fr017-pilot-movement-gate.ps1",
    "fr017-quick-release-cable-snag-gate.ps1",
    "fr017-engineering-review-gate.ps1",
    "fr017-final-physical-gate.ps1",
    "fr017-final-decision-record-gate.ps1",
    "fr017-completion-ledger-gate.ps1",
    "fr017-evidence-chain-status.ps1",
]


def _powershell() -> str:
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _run_gate(*args: str):
    return run_powershell_script(
        _powershell(),
        SCRIPT,
        args,
        cwd=ROOT,
        timeout_seconds=20,
    )


def _payload(stdout: str) -> dict[str, object]:
    return json.loads(stdout)


def _copy_stage17_package(tmp_path: Path) -> Path:
    shutil.copy2(ROOT / "FRANCIS_FR-017_Forearm_Cuffs_v1.0", tmp_path / "FRANCIS_FR-017_Forearm_Cuffs_v1.0")
    package_root = tmp_path / "FR-017_Stage17_Package"
    shutil.copytree(ROOT / "FR-017_Stage17_Package", package_root)
    return package_root / "FR-017-STAGE17-PACKAGE-MANIFEST.json"


def _copy_gate_scripts(tmp_path: Path) -> Path:
    scripts_root = tmp_path / "scripts"
    scripts_root.mkdir()
    for script_name in REQUIRED_GATE_SCRIPTS:
        shutil.copy2(ROOT / "scripts" / script_name, scripts_root / script_name)
    return scripts_root


def test_fr017_stage17_validation_gate_reports_documented_but_physically_blocked() -> None:
    proc = _run_gate("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = _payload(proc.stdout)
    assert payload["kind"] == "francis.fr017.stage17.validation_gate"
    assert payload["status"] == "blocked_physical_validation"
    assert payload["documentation_complete"] is True
    assert payload["evidence_containers_complete"] is True
    assert payload["physical_validation_complete"] is False
    assert payload["physical_validation_status"] == "not_complete"
    assert payload["powered_or_frame_coupled_testing_cleared"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert payload["fr018_status"] == "not_cleared"
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False
    assert payload["grants_execution_authority"] is False
    assert payload["grants_mutation_authority"] is False
    assert payload["record_count"] == 25
    assert payload["custom_record_count"] == 19
    assert payload["required_gate_scripts"] == REQUIRED_GATE_SCRIPTS
    assert payload["missing_gate_scripts"] == []
    assert payload["invalid_gate_scripts"] == []
    assert payload["failed_checks"] == []
    assert payload["missing_measurement_runbook_terms"] == []
    assert payload["missing_measurement_template_contracts"] == []
    assert payload["missing_measurement_template_fields"] == []
    assert payload["missing_mockup_template_contracts"] == []
    assert payload["missing_mockup_template_fields"] == []
    assert payload["missing_mannequin_template_contracts"] == []
    assert payload["missing_mannequin_template_fields"] == []
    assert payload["missing_static_fit_template_contracts"] == []
    assert payload["missing_static_fit_template_fields"] == []
    assert payload["missing_movement_template_contracts"] == []
    assert payload["missing_movement_template_fields"] == []
    assert payload["missing_release_cable_template_contracts"] == []
    assert payload["missing_release_cable_template_fields"] == []
    assert payload["missing_engineering_template_contracts"] == []
    assert payload["missing_engineering_template_fields"] == []
    assert payload["missing_final_decision_template_contracts"] == []
    assert payload["missing_final_decision_template_fields"] == []
    assert payload["missing_completion_ledger_template_terms"] == []
    assert "safety_critical_landmark_confirmation" in payload["blocked_inputs"]
    assert "pilot_static_fit_session" in payload["blocked_inputs"]
    assert "professional_engineering_review" in payload["blocked_inputs"]
    assert "human_final_stage17_completion_decision" in payload["blocked_inputs"]
    assert "unconfirmed_landmark_boundaries" in payload["safety_fail_conditions"]
    assert "unreachable_release" in payload["safety_fail_conditions"]


def test_fr017_stage17_validation_gate_fails_closed_when_manifest_missing(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "missing-manifest.json"
    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(missing_manifest))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert payload["documentation_complete"] is False
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
    assert "manifest_exists" in payload["failed_checks"]
    assert payload["read_only_contract"] is True


def test_fr017_stage17_validation_gate_fails_closed_if_required_gate_script_is_missing(
    tmp_path: Path,
) -> None:
    scripts_root = _copy_gate_scripts(tmp_path)
    (scripts_root / "fr017-final-decision-record-gate.ps1").unlink()

    proc = _run_gate("-Mode", "Status", "-GateScriptRoot", str(scripts_root))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "required_gate_scripts_exist" in payload["failed_checks"]
    assert payload["missing_gate_scripts"] == ["fr017-final-decision-record-gate.ps1"]
    assert payload["invalid_gate_scripts"] == []
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_required_gate_script_is_invalid(
    tmp_path: Path,
) -> None:
    scripts_root = _copy_gate_scripts(tmp_path)
    (scripts_root / "fr017-final-decision-record-gate.ps1").write_text(
        "param(\n",
        encoding="utf-8",
    )

    proc = _run_gate("-Mode", "Status", "-GateScriptRoot", str(scripts_root))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "required_gate_scripts_parse" in payload["failed_checks"]
    assert payload["missing_gate_scripts"] == []
    assert payload["invalid_gate_scripts"] == ["fr017-final-decision-record-gate.ps1"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_fr018_is_cleared(tmp_path: Path) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"]["fr_018_implementation"] = "cleared"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert payload["fr018_status"] == "cleared"
    assert payload["fr018_implementation_cleared"] is False
    assert "fr018_not_cleared" in payload["failed_checks"]


def test_fr017_stage17_validation_gate_fails_closed_if_landmark_blocked_input_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["blocked_inputs"] = [
        item for item in manifest["blocked_inputs"] if item != "safety_critical_landmark_confirmation"
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "blocked_inputs_preserved" in payload["failed_checks"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_final_decision_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    final_decision_template_path = package_root / "FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json"
    template = json.loads(final_decision_template_path.read_text(encoding="utf-8"))
    del template["decision_locks"]["fr018_implementation_not_cleared"]
    del template["completion_decision"]["completion_decision_notes"]
    final_decision_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "final_decision_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_final_decision_template_fields"] == [
        "decision_locks.fr018_implementation_not_cleared",
        "completion_decision.completion_decision_notes",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_final_decision_template_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    final_decision_template_path = package_root / "FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json"
    template = json.loads(final_decision_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["completion_decision_notes"]
    final_decision_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "final_decision_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_final_decision_template_contracts"] == ["completion_decision_notes"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_completion_ledger_template_terms_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    ledger_template_path = package_root / "FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md"
    template = ledger_template_path.read_text(encoding="utf-8").replace(
        "physical_validation_complete: false",
        "physical validation status pending",
    )
    ledger_template_path.write_text(template, encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "completion_ledger_handoff_template_terms" in payload["failed_checks"]
    assert payload["missing_completion_ledger_template_terms"] == ["physical_validation_complete: false"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_runbook_terms_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    runbook_path = package_root / "FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md"
    runbook = runbook_path.read_text(encoding="utf-8").replace(
        "This runbook is not physical validation evidence.",
        "This capture guide is pending review.",
    )
    runbook_path.write_text(runbook, encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_capture_runbook_terms" in payload["failed_checks"]
    assert payload["missing_measurement_runbook_terms"] == ["This runbook is not physical validation evidence."]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_landmark_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["landmark_confirmation"]["skin_safe_marking_used"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_measurement_template_fields"] == ["landmark_confirmation.skin_safe_marking_used"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["sides"]["left"]["wrist_clearance_gap"]
    del template["safety_screen"]["tingling"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_measurement_template_fields"] == [
        "sides.left.wrist_clearance_gap",
        "safety_screen.tingling",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_template_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["measurement_conditions"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_conditions"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_placeholder_values_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["placeholder_values"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["placeholder_values"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_contract_text_is_pending(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    template["field_contract"]["measurement_tool"] = " pending "
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_tool"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


@pytest.mark.parametrize(
    ("template_name", "failed_check", "missing_key"),
    [
        (
            "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json",
            "mockup_input_template_contracts",
            "missing_mockup_template_contracts",
        ),
        (
            "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json",
            "mannequin_input_template_contracts",
            "missing_mannequin_template_contracts",
        ),
        (
            "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json",
            "static_fit_input_template_contracts",
            "missing_static_fit_template_contracts",
        ),
        (
            "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json",
            "movement_input_template_contracts",
            "missing_movement_template_contracts",
        ),
        (
            "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json",
            "release_cable_input_template_contracts",
            "missing_release_cable_template_contracts",
        ),
        (
            "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json",
            "engineering_input_template_contracts",
            "missing_engineering_template_contracts",
        ),
    ],
)
def test_fr017_stage17_validation_gate_fails_closed_if_downstream_placeholder_contract_is_missing(
    tmp_path: Path,
    template_name: str,
    failed_check: str,
    missing_key: str,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    template_path = manifest_path.parent / template_name
    template = json.loads(template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["placeholder_values"]
    template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert failed_check in payload["failed_checks"]
    assert payload[missing_key] == ["placeholder_values"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


@pytest.mark.parametrize(
    ("template_name", "contract_field", "failed_check", "missing_key"),
    [
        (
            "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json",
            "build_method",
            "mockup_input_template_contracts",
            "missing_mockup_template_contracts",
        ),
        (
            "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json",
            "test_subject",
            "mannequin_input_template_contracts",
            "missing_mannequin_template_contracts",
        ),
        (
            "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json",
            "test_duration",
            "static_fit_input_template_contracts",
            "missing_static_fit_template_contracts",
        ),
        (
            "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json",
            "test_duration",
            "movement_input_template_contracts",
            "missing_movement_template_contracts",
        ),
        (
            "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json",
            "test_duration",
            "release_cable_input_template_contracts",
            "missing_release_cable_template_contracts",
        ),
        (
            "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json",
            "review_scope",
            "engineering_input_template_contracts",
            "missing_engineering_template_contracts",
        ),
    ],
)
def test_fr017_stage17_validation_gate_fails_closed_if_downstream_contract_text_is_pending(
    tmp_path: Path,
    template_name: str,
    contract_field: str,
    failed_check: str,
    missing_key: str,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    template_path = manifest_path.parent / template_name
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["field_contract"][contract_field] = " pending "
    template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert failed_check in payload["failed_checks"]
    assert payload[missing_key] == [contract_field]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


@pytest.mark.parametrize(
    ("template_name", "failed_check", "missing_key"),
    [
        (
            "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json",
            "static_fit_input_template_contracts",
            "missing_static_fit_template_contracts",
        ),
        (
            "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json",
            "movement_input_template_contracts",
            "missing_movement_template_contracts",
        ),
        (
            "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json",
            "release_cable_input_template_contracts",
            "missing_release_cable_template_contracts",
        ),
    ],
)
def test_fr017_stage17_validation_gate_fails_closed_if_test_duration_contract_is_missing(
    tmp_path: Path,
    template_name: str,
    failed_check: str,
    missing_key: str,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    template_path = manifest_path.parent / template_name
    template = json.loads(template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["test_duration"]
    template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert failed_check in payload["failed_checks"]
    assert payload[missing_key] == ["test_duration"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_units_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["units"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["units"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_date_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_date"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["evidence_date"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_tool_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["measurement_tool"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_tool"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_tool_exclusions_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["measurement_tool_exclusions"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_tool_exclusions"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_method_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["measurement_method"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_method"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_method_exclusions_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["measurement_method_exclusions"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_method_exclusions"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_posture_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["measurement_posture"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_posture"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_posture_exclusions_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["measurement_posture_exclusions"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_posture_exclusions"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_measurement_notes_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    measurement_template_path = package_root / "FR-017-MEASUREMENTS-INPUT-TEMPLATE.json"
    template = json.loads(measurement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["measurement_notes"]
    measurement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "measurement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_measurement_template_contracts"] == ["measurement_notes"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mockup_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mockup_template_path = package_root / "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json"
    template = json.loads(mockup_template_path.read_text(encoding="utf-8"))
    del template["materials"]["quick_release"]
    del template["sides"]["right"]["cable_sleeve_outer_route_only"]
    mockup_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mockup_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_mockup_template_fields"] == [
        "materials.quick_release",
        "sides.right.cable_sleeve_outer_route_only",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mockup_template_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mockup_template_path = package_root / "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json"
    template = json.loads(mockup_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["constraints"]
    mockup_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mockup_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_mockup_template_contracts"] == ["constraints"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mockup_build_method_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mockup_template_path = package_root / "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json"
    template = json.loads(mockup_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["build_method"]
    mockup_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mockup_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_mockup_template_contracts"] == ["build_method"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mockup_date_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mockup_template_path = package_root / "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json"
    template = json.loads(mockup_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_date"]
    mockup_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mockup_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_mockup_template_contracts"] == ["evidence_date"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mockup_chronology_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mockup_template_path = package_root / "FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json"
    template = json.loads(mockup_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_chronology"]
    mockup_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mockup_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_mockup_template_contracts"] == ["evidence_chronology"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mannequin_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mannequin_template_path = package_root / "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json"
    template = json.loads(mannequin_template_path.read_text(encoding="utf-8"))
    del template["interfaces"]["fr045_left_wrist_joint"]["clearance_passed"]
    del template["fail_observations"]["release_hidden"]
    mannequin_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mannequin_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_mannequin_template_fields"] == [
        "interfaces.fr045_left_wrist_joint.clearance_passed",
        "fail_observations.release_hidden",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mannequin_template_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mannequin_template_path = package_root / "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json"
    template = json.loads(mannequin_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["required_pass_checks"]
    mannequin_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mannequin_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_mannequin_template_contracts"] == ["required_pass_checks"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mannequin_test_subject_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mannequin_template_path = package_root / "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json"
    template = json.loads(mannequin_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["test_subject"]
    mannequin_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mannequin_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_mannequin_template_contracts"] == ["test_subject"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mannequin_date_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mannequin_template_path = package_root / "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json"
    template = json.loads(mannequin_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_date"]
    mannequin_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mannequin_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_mannequin_template_contracts"] == ["evidence_date"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_mannequin_chronology_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    mannequin_template_path = package_root / "FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json"
    template = json.loads(mannequin_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_chronology"]
    mannequin_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "mannequin_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_mannequin_template_contracts"] == ["evidence_chronology"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_static_fit_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    static_fit_template_path = package_root / "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json"
    template = json.loads(static_fit_template_path.read_text(encoding="utf-8"))
    del template["preconditions"]["observer_present"]
    del template["sides"]["right"]["static_checks"]["glove_removal_path_open"]
    static_fit_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "static_fit_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_static_fit_template_fields"] == [
        "preconditions.observer_present",
        "sides.right.static_checks.glove_removal_path_open",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_static_fit_template_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    static_fit_template_path = package_root / "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json"
    template = json.loads(static_fit_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["symptoms"]
    static_fit_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "static_fit_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_static_fit_template_contracts"] == ["symptoms"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_static_fit_evidence_date_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    static_fit_template_path = package_root / "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json"
    template = json.loads(static_fit_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_date"]
    static_fit_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "static_fit_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_static_fit_template_contracts"] == ["evidence_date"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_static_fit_chronology_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    static_fit_template_path = package_root / "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json"
    template = json.loads(static_fit_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_chronology"]
    static_fit_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "static_fit_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_static_fit_template_contracts"] == ["evidence_chronology"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_static_fit_pilot_identity_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    static_fit_template_path = package_root / "FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json"
    template = json.loads(static_fit_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["pilot_identity_linkage"]
    static_fit_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "static_fit_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_static_fit_template_contracts"] == ["pilot_identity_linkage"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_movement_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    movement_template_path = package_root / "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"
    template = json.loads(movement_template_path.read_text(encoding="utf-8"))
    del template["evidence"]["test_duration_minutes"]
    del template["sides"]["left"]["post_movement"]["no_new_pressure_marks"]
    movement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "movement_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_movement_template_fields"] == [
        "evidence.test_duration_minutes",
        "sides.left.post_movement.no_new_pressure_marks",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_movement_template_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    movement_template_path = package_root / "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"
    template = json.loads(movement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["record_linkage"]
    movement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "movement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_movement_template_contracts"] == ["record_linkage"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_movement_evidence_date_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    movement_template_path = package_root / "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"
    template = json.loads(movement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_date"]
    movement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "movement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_movement_template_contracts"] == ["evidence_date"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_movement_chronology_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    movement_template_path = package_root / "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"
    template = json.loads(movement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_chronology"]
    movement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "movement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_movement_template_contracts"] == ["evidence_chronology"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_movement_pilot_identity_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    movement_template_path = package_root / "FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json"
    template = json.loads(movement_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["pilot_identity_linkage"]
    movement_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "movement_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_movement_template_contracts"] == ["pilot_identity_linkage"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_release_cable_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    release_cable_template_path = package_root / "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    template = json.loads(release_cable_template_path.read_text(encoding="utf-8"))
    del template["evidence"]["pilot_id"]
    del template["sides"]["left"]["cable_sleeve_checks"]["no_wrist_bone_crossing"]
    release_cable_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "release_cable_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_release_cable_template_fields"] == [
        "evidence.pilot_id",
        "sides.left.cable_sleeve_checks.no_wrist_bone_crossing",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_release_cable_template_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    release_cable_template_path = package_root / "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    template = json.loads(release_cable_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["fail_observations"]
    release_cable_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "release_cable_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_release_cable_template_contracts"] == ["fail_observations"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_release_cable_evidence_date_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    release_cable_template_path = package_root / "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    template = json.loads(release_cable_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_date"]
    release_cable_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "release_cable_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_release_cable_template_contracts"] == ["evidence_date"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_release_cable_chronology_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    release_cable_template_path = package_root / "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    template = json.loads(release_cable_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_chronology"]
    release_cable_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "release_cable_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_release_cable_template_contracts"] == ["evidence_chronology"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_release_cable_pilot_identity_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    release_cable_template_path = package_root / "FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json"
    template = json.loads(release_cable_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["pilot_identity_linkage"]
    release_cable_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "release_cable_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_release_cable_template_contracts"] == ["pilot_identity_linkage"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_engineering_template_fields_are_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    engineering_template_path = package_root / "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    template = json.loads(engineering_template_path.read_text(encoding="utf-8"))
    del template["review_constraints"]["no_powered_testing_cleared"]
    del template["review_decision"]["fr018_implementation_cleared"]
    engineering_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "engineering_input_template_required_fields" in payload["failed_checks"]
    assert payload["missing_engineering_template_fields"] == [
        "review_constraints.no_powered_testing_cleared",
        "review_decision.fr018_implementation_cleared",
    ]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_engineering_evidence_date_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    engineering_template_path = package_root / "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    template = json.loads(engineering_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_date"]
    engineering_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "engineering_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_engineering_template_contracts"] == ["evidence_date"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_engineering_chronology_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    engineering_template_path = package_root / "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    template = json.loads(engineering_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["evidence_chronology"]
    engineering_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "engineering_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_engineering_template_contracts"] == ["evidence_chronology"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_engineering_review_scope_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    engineering_template_path = package_root / "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    template = json.loads(engineering_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["review_scope"]
    engineering_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "engineering_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_engineering_template_contracts"] == ["review_scope"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_engineering_pilot_identity_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    engineering_template_path = package_root / "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    template = json.loads(engineering_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["pilot_identity_linkage"]
    engineering_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "engineering_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_engineering_template_contracts"] == ["pilot_identity_linkage"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False


def test_fr017_stage17_validation_gate_fails_closed_if_engineering_template_contract_is_missing(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_stage17_package(tmp_path)
    package_root = manifest_path.parent
    engineering_template_path = package_root / "FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json"
    template = json.loads(engineering_template_path.read_text(encoding="utf-8"))
    del template["field_contract"]["required_false_checks"]
    engineering_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    proc = _run_gate("-Mode", "Status", "-ManifestPath", str(manifest_path))

    assert proc.returncode == 1
    payload = _payload(proc.stdout)
    assert payload["status"] == "failed_contract"
    assert "engineering_input_template_contracts" in payload["failed_checks"]
    assert payload["missing_engineering_template_contracts"] == ["required_false_checks"]
    assert payload["physical_validation_complete"] is False
    assert payload["fr018_implementation_cleared"] is False
