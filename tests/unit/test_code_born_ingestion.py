from __future__ import annotations

import json
from pathlib import Path

from francis.__main__ import main
from francis.governance import approvals
from francis.ingest import IngestService, RepoAdapter, classify_source, detect_repo


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "scripts").mkdir()
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "migrations").mkdir()
    (repo / "README.md").write_text("# Fixture Repo\n\nA small local repo fixture.\n", encoding="utf-8")
    (repo / "src" / "index.ts").write_text("export const answer = 42;\n", encoding="utf-8")
    (repo / "tests" / "index.test.ts").write_text("import { answer } from '../src/index';\n", encoding="utf-8")
    (repo / "scripts" / "deploy.sh").write_text("#!/usr/bin/env bash\ncurl https://example.invalid\n", encoding="utf-8")
    (repo / "scripts" / "write-marker.js").write_text(
        "require('fs').writeFileSync('lab-ran.txt', 'ran');\n",
        encoding="utf-8",
    )
    (repo / "migrations" / "001_init.sql").write_text("create table example(id int);\n", encoding="utf-8")
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (repo / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (repo / ".env").write_text("API_TOKEN=super-secret-token-value\n", encoding="utf-8")
    (repo / "package.json").write_text(
        json.dumps(
            {
                "name": "fixture",
                "main": "src/index.ts",
                "scripts": {
                    "build": "tsc",
                    "lint": "eslint src",
                    "postinstall": "node scripts/postinstall.js",
                    "test": "node scripts/write-marker.js",
                    "publish": "npm publish",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return repo


def test_source_record_creation_for_file_and_folder_defaults_to_conservative_permissions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")
    folder_path = tmp_path / "plain_folder"
    folder_path.mkdir()

    service = IngestService()
    file_result = service.add_source(file_path, actor="test.ingest")
    folder_result = service.add_source(folder_path, actor="test.ingest")

    assert file_result["ok"] is True
    assert folder_result["ok"] is True
    assert file_result["source"]["type"] == "file"
    assert folder_result["source"]["type"] == "folder"
    assert file_result["source"]["status"] == "indexed"
    assert file_result["source"]["permissions"] == {
        "read": True,
        "execute": False,
        "network": False,
        "write": False,
        "destructive": False,
    }
    assert (data_root / "ingest" / "_source_registry.json").exists()
    assert (data_root / "ingest" / "incoming").is_dir()
    assert Path(file_result["receipt_path"]).exists()
    assert file_result["receipt"]["operation"] == "source.add"


def test_repo_detection_and_read_only_repo_map_extraction(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "francis_data"))
    repo = _fixture_repo(tmp_path)

    assert classify_source(repo) == "repo"
    assert detect_repo(repo)["is_repo"] is True

    repo_map = RepoAdapter().inspect(repo, source_id="src_fixture")
    signal_ids = {signal.id for signal in repo_map.risk_signals}

    assert "javascript/typescript" in repo_map.detected_languages
    assert "npm" in repo_map.package_managers
    assert "package.json" in repo_map.manifest_files
    assert repo_map.script_commands["package.json"]["test"] == "node scripts/write-marker.js"
    assert "tests/index.test.ts" in repo_map.test_files
    assert "README.md" in repo_map.docs_readmes
    assert "src" in repo_map.source_directories
    assert repo_map.entrypoints == [{"source": "package.json", "kind": "main", "value": "src/index.ts"}]
    assert "package_postinstall_script" in signal_ids
    assert "shell_script_present" in signal_ids
    assert "dockerfile_present" in signal_ids
    assert "ci_workflow_present" in signal_ids
    assert "env_file_present" in signal_ids
    assert "deploy_script_present" in signal_ids
    assert "migration_script_present" in signal_ids
    assert "network_command_hint" in signal_ids
    assert repo_map.protected_sensitive_files == [
        {"path": ".env", "reason": "sensitive_name_or_extension", "contents_read": "false"}
    ]
    assert any(item["command"] == "npm test" for item in repo_map.suggested_validation_commands)


def test_ingest_repo_writes_records_candidates_and_receipts_without_execution_or_secret_persistence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)

    result = IngestService().add_source(repo, actor="test.ingest")

    assert result["ok"] is True
    assert result["source"]["type"] == "repo"
    assert result["repo"]["execution"] == {
        "ran_repo_scripts": False,
        "ran_install": False,
        "ran_build": False,
        "ran_tests": False,
        "network_accessed": False,
        "lab_boundary": result["repo"]["execution"]["lab_boundary"],
    }
    assert result["repo"]["execution"]["lab_boundary"]["supports_unknown_repo_execution"] is False
    candidates = {item["name"]: item for item in result["repo"]["candidates"]}
    assert candidates["inspect_project_structure"]["status"] == "drafted"
    assert candidates["explain_repo_architecture"]["permissions_required"]["execute"] is False
    assert candidates["run_project_tests"]["status"] == "discovered"
    assert candidates["run_project_tests"]["permissions_required"]["execute"] is True
    assert candidates["run_project_tests"]["risk_level"] in {"medium", "high"}
    assert candidates["build_project"]["permissions_required"]["write"] is True
    assert candidates["package_project"]["permissions_required"]["network"] is True
    assert candidates["inspect_container_build"]["permissions_required"]["execute"] is False
    assert candidates["inspect_database_migrations"]["status"] == "discovered"
    assert candidates["inspect_cli_entrypoint"]["risk_level"] == "low"

    registry_text = (data_root / "ingest" / "_source_registry.json").read_text(encoding="utf-8")
    capability_text = (data_root / "ingest" / "_capability_registry.json").read_text(encoding="utf-8")
    receipt_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (data_root / "artifacts" / "ingest").rglob("*.json")
    )
    assert "super-secret-token-value" not in registry_text
    assert "super-secret-token-value" not in capability_text
    assert "super-secret-token-value" not in receipt_text
    assert result["repo"]["receipt"]["operation"] == "repo.inspect"
    assert any(item["operation"] == "capability.extract" for item in _receipt_payloads(data_root))


def test_ingest_cli_add_outputs_json_and_writes_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)

    rc = main(["ingest", "add", str(repo), "--actor", "test.ingest.cli"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["source"]["type"] == "repo"
    assert payload["repo"]["execution"]["ran_repo_scripts"] is False
    assert Path(payload["repo"]["repo_map_path"]).exists()
    assert Path(payload["repo"]["candidate_artifact_path"]).exists()


def test_lab_plan_blocks_execute_candidate_and_writes_plan_receipt_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]

    result = service.plan_lab(source["id"], "run_project_tests", actor="test.lab")

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert result["plan"]["candidate_name"] == "run_project_tests"
    assert result["plan"]["permissions_required"]["execute"] is True
    assert result["plan"]["permissions_required"]["explicit_operator_permission"] is True
    assert result["plan"]["permissions_required"]["sandbox_required"] is True
    assert "francis_lab_runner_not_implemented" in result["plan"]["blockers"]
    assert "network_isolation_not_available" in result["plan"]["blockers"]
    assert result["plan"]["workspace"] == {
        "created": False,
        "mode": "plan_only",
        "path": "",
        "source_copied": False,
        "writes_allowed": False,
    }
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_tests"] is False
    assert result["receipt"]["operation"] == "lab.plan"
    assert Path(result["artifact_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_execute_refuses_unknown_repo_execution_and_writes_refusal_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]

    result = service.refuse_lab_execution(source["id"], "run_project_tests", actor="test.lab.execute")

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert result["execution"]["executed"] is False
    assert result["execution"]["execution_authority"] is False
    assert result["execution"]["network_accessed"] is False
    assert result["execution"]["wrote_to_repo"] is False
    assert result["refusal"]["executed"] is False
    assert result["refusal"]["permission_scope"] == "francis.lab.execute"
    assert "lab_execution_disabled_in_v0" in result["refusal"]["blockers"]
    assert result["receipt"]["operation"] == "lab.execution.refuse"
    assert result["receipt"]["result_status"] == "blocked"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_prepare_creates_empty_workspace_manifest_without_source_copy_or_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]

    result = service.prepare_lab_workspace(source["id"], "run_project_tests", actor="test.lab.prepare")
    workspace = result["workspace"]
    workspace_root = Path(workspace["path"])

    assert result["ok"] is True
    assert result["status"] == "prepared"
    assert workspace_root.is_dir()
    assert (workspace_root / "work").is_dir()
    assert (workspace_root / "artifacts").is_dir()
    assert (workspace_root / "logs").is_dir()
    assert (workspace_root / "tmp").is_dir()
    assert Path(workspace["manifest_path"]).exists()
    assert Path(result["artifact_path"]).exists()
    assert workspace["source_copied"] is False
    assert workspace["source_reference"]["mode"] == "reference_only_read_only"
    assert workspace["source_reference"]["contents_copied"] is False
    assert workspace["workspace_policy"]["execution_enabled"] is False
    assert workspace["workspace_policy"]["runner_bound"] is False
    assert workspace["workspace_policy"]["source_write_allowed"] is False
    assert workspace["preflight"]["execution_ready"] is False
    assert "source_copy_not_performed" in workspace["preflight"]["blockers"]
    assert result["receipt"]["operation"] == "lab.workspace.prepare"
    assert not (workspace_root / "package.json").exists()
    assert not (workspace_root / "src").exists()
    assert "super-secret-token-value" not in Path(workspace["manifest_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_prepare_creates_workspace_and_keeps_execution_disabled(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    source = IngestService().add_source(repo, actor="test.ingest")["source"]

    rc = main(["lab", "prepare", source["id"], "inspect_project_structure", "--actor", "test.lab.cli"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "prepared"
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["ran_repo_scripts"] is False
    assert payload["workspace"]["workspace_policy"]["execution_enabled"] is False
    assert Path(payload["workspace"]["path"]).is_dir()
    assert Path(payload["manifest_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_execution_preflight_records_exact_action_without_approval_or_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]

    result = service.preflight_lab_execution(source["id"], "run_project_tests", actor="test.lab.preflight")
    preflight = result["preflight"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert preflight["status"] == "blocked"
    assert preflight["approval"]["required"] is True
    assert preflight["approval"]["gate"] == "approvals_gate"
    assert preflight["approval"]["action"] == "francis.lab.execute"
    assert preflight["approval"]["approval_id"] == ""
    assert preflight["approval"]["approval_created"] is False
    assert preflight["approval"]["approval_consumed"] is False
    assert preflight["action_hash"].startswith("sha256:")
    assert preflight["approval"]["action_hash"] == preflight["action_hash"]
    assert preflight["exact_action"]["candidate_name"] == "run_project_tests"
    assert preflight["readiness"]["execution_ready"] is False
    assert preflight["readiness"]["approval_consumption_ready"] is False
    assert "runner_binding_absent" in preflight["blockers"]
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.execution.preflight"
    assert Path(result["artifact_path"]).exists()
    preflight_text = Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in preflight_text
    assert not (data_root / "approvals").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_preflight_outputs_blocked_exact_action_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    source = IngestService().add_source(repo, actor="test.ingest")["source"]

    rc = main(["lab", "preflight", source["id"], "run_project_tests", "--actor", "test.lab.cli"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert payload["preflight"]["approval"]["approval_created"] is False
    assert payload["preflight"]["approval"]["approval_consumed"] is False
    assert payload["preflight"]["execution_authority"] is False
    assert payload["preflight"]["executed"] is False
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_request_approval_creates_pending_exact_action_without_consuming_or_executing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]

    result = service.request_lab_execution_approval(
        source["id"],
        "run_project_tests",
        actor="test.lab.approval",
    )
    request = result["approval_request"]
    approval = result["approval"]
    approval_path = Path(result["approval_path"])

    assert result["ok"] is True
    assert result["status"] == "needs_approval"
    assert request["approval_created"] is True
    assert request["approval_consumed"] is False
    assert request["execution_authority"] is False
    assert request["executed"] is False
    assert request["action"] == "francis.lab.execute"
    assert request["approval_id"] == approval["id"]
    assert request["action_hash"] == result["preflight"]["action_hash"]
    assert approval["status"] == "pending"
    assert approval["action"] == "francis.lab.execute"
    assert approval["payload"]["action_hash"] == request["action_hash"]
    assert approval["payload"]["governance"]["execution_authority"] is False
    assert approval_path.exists()
    assert approval_path.parent == data_root / "approvals" / "pending"
    assert not (data_root / "approvals" / "approved" / f"{approval['id']}.json").exists()
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.execution.approval_request"
    assert Path(result["artifact_path"]).exists()
    combined = approval_path.read_text(encoding="utf-8") + Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in combined
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_request_approval_creates_pending_request_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    source = IngestService().add_source(repo, actor="test.ingest")["source"]

    rc = main(["lab", "request-approval", source["id"], "run_project_tests", "--actor", "test.lab.cli"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "needs_approval"
    assert payload["approval_request"]["approval_created"] is True
    assert payload["approval_request"]["approval_consumed"] is False
    assert payload["approval_request"]["execution_authority"] is False
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["approval_path"]).exists()
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_approval_consumption_preflight_binds_pending_approval_without_consuming_or_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]

    result = service.preflight_lab_approval_consumption(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.consume",
    )
    consumption = result["approval_consumption"]
    runner_contract = result["runner_contract"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert consumption["approval_id"] == approval_id
    assert consumption["approval_status"] == "pending"
    assert consumption["binding"]["approval_record_found"] is True
    assert consumption["binding"]["exact_match"] is True
    assert consumption["binding"]["approval_approved"] is False
    assert consumption["approval_consumed"] is False
    assert consumption["execution_authority"] is False
    assert consumption["executed"] is False
    assert "approval_not_approved" in consumption["blockers"]
    assert "governed_lab_runner_not_bound" in consumption["blockers"]
    assert runner_contract["runner_bound"] is False
    assert runner_contract["execution_enabled"] is False
    assert runner_contract["current_controls"]["approval_exact_match"] is True
    assert runner_contract["current_controls"]["approval_consumption_ready"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.execution.approval_consumption_preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["runner_contract_path"]).exists()
    assert (data_root / "approvals" / "pending" / f"{approval_id}.json").exists()
    assert not (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    combined = Path(result["artifact_path"]).read_text(encoding="utf-8") + Path(
        result["runner_contract_path"]
    ).read_text(encoding="utf-8")
    assert "super-secret-token-value" not in combined
    assert not (repo / "lab-ran.txt").exists()


def test_lab_approval_consumption_preflight_checks_approved_exact_action_but_still_blocks_runner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    decision = approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_approval_consumption(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.consume",
    )

    assert decision["ok"] is True
    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert result["approval_consumption"]["approval_status"] == "approved"
    assert result["approval_consumption"]["binding"]["approval_approved"] is True
    assert result["approval_consumption"]["binding"]["exact_match"] is True
    assert result["approval_consumption"]["approval_consumed"] is False
    assert "approval_not_approved" not in result["approval_consumption"]["blockers"]
    assert "approval_consumption_disabled_in_v0" in result["approval_consumption"]["blockers"]
    assert "governed_lab_runner_not_bound" in result["approval_consumption"]["blockers"]
    assert result["runner_contract"]["current_controls"]["approval_approved"] is True
    assert result["runner_contract"]["runner_bound"] is False
    assert result["execution"]["executed"] is False
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_runner_readiness_projects_missing_sandbox_controls_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]

    result = service.preflight_lab_runner_readiness(
        source["id"],
        "run_project_tests",
        approval_id=approval_id,
        actor="test.lab.runner",
    )
    readiness = result["runner_readiness"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert readiness["status"] == "blocked"
    assert readiness["approval_id"] == approval_id
    assert readiness["execution_authority"] is False
    assert readiness["executed"] is False
    assert readiness["network_accessed"] is False
    assert readiness["wrote_to_repo"] is False
    assert readiness["current_controls"]["workspace_manifest_present"] is True
    assert readiness["current_controls"]["workspace_subdirs_present"] is True
    assert readiness["current_controls"]["source_reference_read_only"] is True
    assert readiness["current_controls"]["source_not_copied"] is True
    assert readiness["current_controls"]["approved_exact_action_record"] is False
    assert "approved_exact_action_record" in readiness["missing_controls"]
    assert "governed_runner_bound" in readiness["missing_controls"]
    assert "network_isolation_enforced" in readiness["missing_controls"]
    assert "filesystem_write_boundary_enforced" in readiness["missing_controls"]
    assert "resource_limits_enforced" in readiness["missing_controls"]
    assert "execution_receipt_sink_bound" in readiness["missing_controls"]
    assert result["approval_binding"]["approval_consumed"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.runner.readiness.preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert (data_root / "approvals" / "pending" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_runner_readiness_accepts_approved_exact_action_but_still_blocks_runner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_runner_readiness(
        source["id"],
        "run_project_tests",
        approval_id=approval_id,
        actor="test.lab.runner",
    )
    readiness = result["runner_readiness"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert readiness["current_controls"]["approved_exact_action_record"] is True
    assert readiness["current_controls"]["approval_not_stale_or_reused"] is True
    assert "approved_exact_action_record" not in readiness["missing_controls"]
    assert "governed_runner_bound" in readiness["missing_controls"]
    assert "command_allowlist_declared" in readiness["missing_controls"]
    assert readiness["execution_authority"] is False
    assert result["approval_binding"]["approval_consumed"] is False
    assert result["execution"]["executed"] is False
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_runner_binding_projects_receipt_sink_contract_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_runner_binding(
        source["id"],
        "run_project_tests",
        approval_id=approval_id,
        actor="test.lab.binding",
    )
    binding = result["runner_binding"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert binding["approval_id"] == approval_id
    assert binding["current_controls"]["approved_exact_action_record"] is True
    assert binding["current_controls"]["runner_readiness_ready"] is False
    assert binding["runner_binding"]["runner_bound"] is False
    assert binding["runner_binding"]["runner_identity_verified"] is False
    assert binding["execution_receipt_sink"]["bound"] is False
    assert binding["execution_receipt_sink"]["sensitive_values_redacted"] is True
    assert binding["approval_consumed"] is False
    assert binding["runner_bound"] is False
    assert binding["receipt_sink_bound"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert "governed_runner_bound" in binding["missing_controls"]
    assert "execution_receipt_sink_bound" in binding["missing_controls"]
    assert "execution_receipt_schema_bound" in binding["missing_controls"]
    assert "approval_consumption_ready" in binding["missing_controls"]
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.runner.binding.preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_runner_enforcement_preflight_blocks_until_controls_are_bound_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_runner_enforcement(
        source["id"],
        "run_project_tests",
        approval_id=approval_id,
        actor="test.lab.enforcement",
    )
    enforcement = result["runner_enforcement"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert enforcement["approval_id"] == approval_id
    assert enforcement["enforcement_interface"]["mode"] == "preflight_only_no_execution"
    assert enforcement["current_checks"]["runner_binding_record_present"] is True
    assert enforcement["current_checks"]["workspace_matches_binding"] is True
    assert enforcement["current_checks"]["action_hash_matches_binding"] is True
    assert enforcement["current_checks"]["runner_binding_status_ready"] is False
    assert enforcement["current_checks"]["runner_identity_verified"] is False
    assert enforcement["current_checks"]["command_allowlist_bound"] is False
    assert enforcement["current_checks"]["network_policy_bound"] is False
    assert enforcement["current_checks"]["filesystem_policy_bound"] is False
    assert enforcement["current_checks"]["execution_receipt_prewrite_bound"] is False
    assert enforcement["current_checks"]["execution_receipt_final_write_bound"] is False
    assert enforcement["current_checks"]["receipt_sink_sensitive_redaction_declared"] is True
    assert enforcement["approval_consumed"] is False
    assert enforcement["runner_bound"] is False
    assert enforcement["receipt_sink_bound"] is False
    assert enforcement["execution_authority"] is False
    assert enforcement["executed"] is False
    assert "runner_binding_status_ready" in enforcement["missing_checks"]
    assert "runner_identity_verified" in enforcement["missing_checks"]
    assert "command_allowlist_bound" in enforcement["missing_checks"]
    assert "network_policy_bound" in enforcement["missing_checks"]
    assert "execution_receipt_prewrite_bound" in enforcement["missing_checks"]
    assert "approval_consumed" in enforcement["missing_checks"]
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.runner.enforcement.preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_approval_consumption_handoff_blocks_until_runner_enforcement_ready_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_approval_consumption_handoff(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.handoff",
    )
    handoff = result["approval_consumption_handoff"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert handoff["approval_id"] == approval_id
    assert handoff["approval_status"] == "approved"
    assert handoff["approval_binding"]["approval_approved"] is True
    assert handoff["approval_binding"]["exact_match"] is True
    assert handoff["current_checks"]["approval_approved"] is True
    assert handoff["current_checks"]["approval_exact_action_binding"] is True
    assert handoff["current_checks"]["approval_not_consumed"] is True
    assert handoff["current_checks"]["runner_enforcement_ready"] is False
    assert handoff["current_checks"]["runner_bound"] is False
    assert handoff["current_checks"]["receipt_sink_bound"] is False
    assert handoff["current_checks"]["approval_consumption_not_disabled"] is False
    assert handoff["handoff_contract"]["mode"] == "preflight_only_no_consumption"
    assert handoff["handoff_contract"]["approval_consumption_enabled"] is False
    assert handoff["approval_consumed"] is False
    assert handoff["execution_authority"] is False
    assert handoff["executed"] is False
    assert "runner_enforcement_ready" in handoff["missing_checks"]
    assert "runner_bound" in handoff["missing_checks"]
    assert "receipt_sink_bound" in handoff["missing_checks"]
    assert "approval_consumption_not_disabled" in handoff["missing_checks"]
    assert result["runner_enforcement"]["execution_authority"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.execution.approval_consumption_handoff"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_execution_receipt_sink_reservation_blocks_until_sink_prewrite_ready_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_execution_receipt_sink_reservation(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.receipt_sink",
    )
    reservation = result["execution_receipt_sink_reservation"]
    reserved = reservation["reserved_execution_receipt"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert reservation["approval_id"] == approval_id
    assert reservation["reservation_contract"]["mode"] == "prewrite_reservation_only_no_execution"
    assert reservation["reservation_contract"]["writes_execution_receipt"] is False
    assert reservation["current_checks"]["approval_handoff_present"] is True
    assert reservation["current_checks"]["approval_approved"] is True
    assert reservation["current_checks"]["approval_handoff_ready"] is False
    assert reservation["current_checks"]["runner_enforcement_ready"] is False
    assert reservation["current_checks"]["receipt_sink_bound"] is False
    assert reservation["current_checks"]["execution_receipt_prewrite_bound"] is False
    assert reservation["current_checks"]["execution_receipt_final_write_bound"] is False
    assert reservation["current_checks"]["reserved_receipt_id_created"] is True
    assert reservation["current_checks"]["reserved_receipt_path_scoped"] is True
    assert reservation["current_checks"]["execution_receipt_not_written"] is True
    assert reserved["reserved"] is True
    assert reserved["written"] is False
    assert reserved["prewrite_bound"] is False
    assert reserved["final_write_bound"] is False
    assert reservation["reservation_created"] is True
    assert reservation["prewrite_bound"] is False
    assert reservation["final_write_bound"] is False
    assert reservation["execution_receipt_written"] is False
    assert reservation["approval_consumed"] is False
    assert reservation["execution_authority"] is False
    assert reservation["executed"] is False
    assert "approval_handoff_ready" in reservation["missing_checks"]
    assert "receipt_sink_bound" in reservation["missing_checks"]
    assert "execution_receipt_prewrite_bound" in reservation["missing_checks"]
    assert "execution_receipt_final_write_bound" in reservation["missing_checks"]
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.execution.receipt_sink_reservation"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(reserved["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_runner_command_allowlist_binding_blocks_until_allowlist_bound_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_runner_command_allowlist_binding(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.command_allowlist",
    )
    command_allowlist = result["runner_command_allowlist"]
    command_plan = command_allowlist["command_plan"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert command_allowlist["approval_id"] == approval_id
    assert command_allowlist["allowlist_contract"]["mode"] == "allowlist_binding_preflight_only_no_execution"
    assert command_plan["command_count"] >= 1
    assert command_plan["source"] == "exact_action"
    assert any("test" in command["command"] for command in command_plan["commands"])
    assert all(command["allowlisted"] is False for command in command_plan["commands"])
    assert all(command["bound"] is False for command in command_plan["commands"])
    assert all(command["executed"] is False for command in command_plan["commands"])
    assert command_allowlist["current_checks"]["command_plan_present"] is True
    assert command_allowlist["current_checks"]["commands_from_exact_action"] is True
    assert command_allowlist["current_checks"]["receipt_sink_reservation_ready"] is False
    assert command_allowlist["current_checks"]["command_allowlist_declared"] is False
    assert command_allowlist["current_checks"]["command_allowlist_bound"] is False
    assert command_allowlist["current_checks"]["every_command_has_allowlist_entry"] is False
    assert command_allowlist["current_checks"]["no_command_execution_enabled"] is True
    assert command_allowlist["current_checks"]["receipt_sink_prewrite_bound"] is False
    assert command_allowlist["current_checks"]["receipt_sink_final_write_bound"] is False
    assert command_allowlist["allowlist_declared"] is False
    assert command_allowlist["allowlist_bound"] is False
    assert command_allowlist["command_execution_enabled"] is False
    assert command_allowlist["approval_consumed"] is False
    assert command_allowlist["execution_authority"] is False
    assert command_allowlist["executed"] is False
    assert "receipt_sink_reservation_ready" in command_allowlist["missing_checks"]
    assert "command_allowlist_declared" in command_allowlist["missing_checks"]
    assert "command_allowlist_bound" in command_allowlist["missing_checks"]
    assert "every_command_has_allowlist_entry" in command_allowlist["missing_checks"]
    assert result["execution_receipt_sink_reservation"]["execution_receipt_written"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.runner.command_allowlist.binding"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_runner_command_allowlist_declaration_declares_entries_without_binding_or_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_runner_command_allowlist_declaration(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.command_declaration",
    )
    declaration = result["runner_command_allowlist_declaration"]
    allowlist = declaration["allowlist_declaration"]
    entries = allowlist["entries"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert declaration["approval_id"] == approval_id
    assert declaration["declaration_contract"]["mode"] == "allowlist_declaration_preflight_only_no_binding"
    assert declaration["declaration_created"] is True
    assert declaration["allowlist_declared"] is True
    assert declaration["allowlist_bound"] is False
    assert declaration["command_execution_enabled"] is False
    assert declaration["approval_consumed"] is False
    assert declaration["execution_authority"] is False
    assert declaration["executed"] is False
    assert allowlist["entry_count"] >= 1
    assert len(entries) == declaration["command_plan"]["command_count"]
    assert all(entry["declared"] is True for entry in entries)
    assert all(entry["bound"] is False for entry in entries)
    assert all(entry["executed"] is False for entry in entries)
    assert all(entry["network_allowed"] is False for entry in entries)
    assert all(entry["write_allowed"] is False for entry in entries)
    assert all(entry["destructive_allowed"] is False for entry in entries)
    assert declaration["current_checks"]["command_allowlist_declared"] is True
    assert declaration["current_checks"]["every_command_has_declaration"] is True
    assert declaration["current_checks"]["every_declaration_source_is_exact_action"] is True
    assert declaration["current_checks"]["command_allowlist_bound"] is False
    assert declaration["current_checks"]["command_execution_disabled"] is True
    assert declaration["current_checks"]["approval_not_consumed"] is True
    assert declaration["current_checks"]["execution_authority_absent"] is True
    assert declaration["current_checks"]["commands_not_executed"] is True
    assert "command_allowlist_bound" in declaration["missing_checks"]
    assert "receipt_sink_prewrite_bound" in declaration["missing_checks"]
    assert "receipt_sink_final_write_bound" in declaration["missing_checks"]
    assert "command_allowlist_declared" not in declaration["missing_checks"]
    assert result["runner_command_allowlist"]["allowlist_bound"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.runner.command_allowlist.declaration"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_runner_command_allowlist_enforcement_preflight_blocks_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_runner_command_allowlist_enforcement(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.allowlist_enforcement",
    )
    enforcement = result["runner_command_allowlist_enforcement"]
    projection = enforcement["enforcement_projection"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert enforcement["approval_id"] == approval_id
    assert enforcement["enforcement_contract"]["mode"] == "allowlist_enforcement_preflight_only_no_execution"
    assert projection["entry_count"] >= 1
    assert all(entry["declared"] is True for entry in projection["entries"])
    assert all(entry["bound"] is False for entry in projection["entries"])
    assert all(entry["enforced"] is False for entry in projection["entries"])
    assert all(entry["executed"] is False for entry in projection["entries"])
    assert enforcement["allowlist_declared"] is True
    assert enforcement["allowlist_bound"] is False
    assert enforcement["allowlist_enforced"] is False
    assert enforcement["command_execution_enabled"] is False
    assert enforcement["approval_consumed"] is False
    assert enforcement["execution_authority"] is False
    assert enforcement["executed"] is False
    assert enforcement["current_checks"]["allowlist_entries_declared"] is True
    assert enforcement["current_checks"]["every_entry_has_command_hash"] is True
    assert enforcement["current_checks"]["every_entry_from_exact_action"] is True
    assert enforcement["current_checks"]["runner_enforcement_ready"] is False
    assert enforcement["current_checks"]["runner_bound"] is False
    assert enforcement["current_checks"]["runner_identity_verified"] is False
    assert enforcement["current_checks"]["command_allowlist_bound"] is False
    assert enforcement["current_checks"]["command_allowlist_enforced"] is False
    assert enforcement["current_checks"]["command_execution_disabled"] is True
    assert enforcement["current_checks"]["approval_not_consumed"] is True
    assert enforcement["current_checks"]["execution_authority_absent"] is True
    assert enforcement["current_checks"]["commands_not_executed"] is True
    assert "runner_enforcement_ready" in enforcement["missing_checks"]
    assert "runner_bound" in enforcement["missing_checks"]
    assert "runner_identity_verified" in enforcement["missing_checks"]
    assert "command_allowlist_bound" in enforcement["missing_checks"]
    assert "command_allowlist_enforced" in enforcement["missing_checks"]
    assert "allowlist_entries_declared" not in enforcement["missing_checks"]
    assert result["runner_command_allowlist_declaration"]["allowlist_declared"] is True
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.runner.command_allowlist.enforcement_preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_runner_sandbox_readiness_preflight_blocks_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_runner_sandbox_readiness(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.sandbox_readiness",
    )
    readiness = result["runner_sandbox_readiness"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert readiness["approval_id"] == approval_id
    assert readiness["sandbox_contract"]["mode"] == "sandbox_readiness_preflight_only_no_execution"
    assert readiness["sandbox_profile"]["manifest_present"] is True
    assert readiness["sandbox_profile"]["source_not_copied"] is True
    assert readiness["sandbox_bound"] is False
    assert readiness["sandbox_enforced"] is False
    assert readiness["runner_bound"] is False
    assert readiness["runner_identity_verified"] is False
    assert readiness["allowlist_enforced"] is False
    assert readiness["receipt_prewrite_bound"] is False
    assert readiness["receipt_final_write_bound"] is False
    assert readiness["approval_consumed"] is False
    assert readiness["execution_authority"] is False
    assert readiness["executed"] is False
    assert readiness["current_checks"]["workspace_manifest_present"] is True
    assert readiness["current_checks"]["workspace_subdirs_present"] is True
    assert readiness["current_checks"]["workspace_owned_by_francis"] is True
    assert readiness["current_checks"]["source_reference_read_only"] is True
    assert readiness["current_checks"]["source_not_copied"] is True
    assert readiness["current_checks"]["network_blocked_or_policy_bound"] is True
    assert readiness["current_checks"]["runner_command_allowlist_enforcement_ready"] is False
    assert readiness["current_checks"]["sandbox_provider_bound"] is False
    assert readiness["current_checks"]["sandbox_workspace_isolated"] is False
    assert readiness["current_checks"]["source_mounted_readonly"] is False
    assert readiness["current_checks"]["command_allowlist_enforced"] is False
    assert readiness["current_checks"]["receipt_sink_prewrite_bound"] is False
    assert readiness["current_checks"]["receipt_sink_final_write_bound"] is False
    assert readiness["current_checks"]["approval_not_consumed"] is True
    assert readiness["current_checks"]["execution_authority_absent"] is True
    assert readiness["current_checks"]["commands_not_executed"] is True
    assert "workspace_manifest_present" not in readiness["missing_checks"]
    assert "source_not_copied" not in readiness["missing_checks"]
    assert "network_blocked_or_policy_bound" not in readiness["missing_checks"]
    assert "sandbox_provider_bound" in readiness["missing_checks"]
    assert "sandbox_workspace_isolated" in readiness["missing_checks"]
    assert "source_mounted_readonly" in readiness["missing_checks"]
    assert "command_allowlist_enforced" in readiness["missing_checks"]
    assert "receipt_sink_prewrite_bound" in readiness["missing_checks"]
    assert "receipt_sink_final_write_bound" in readiness["missing_checks"]
    assert result["runner_command_allowlist_enforcement"]["allowlist_enforced"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.runner.sandbox_readiness.preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_contract_blocks_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_contract(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.sandbox_provider_contract",
    )
    contract = result["sandbox_provider_contract"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert contract["contract_kind"] == "francis.lab.sandbox_provider_contract"
    assert contract["contract_mode"] == "provider_contract_preflight_only_no_execution"
    assert contract["provider_kind"] == "unbound"
    assert contract["provider_contract_declared"] is True
    assert contract["sandbox_provider_bound"] is False
    assert contract["sandbox_bound"] is False
    assert contract["sandbox_enforced"] is False
    assert contract["workspace_isolation_bound"] is False
    assert contract["filesystem_write_policy_bound"] is False
    assert contract["network_policy_bound"] is True
    assert contract["resource_limits_bound"] is False
    assert contract["timeout_policy_bound"] is False
    assert contract["stdout_stderr_capture_bound"] is False
    assert contract["kill_switch_bound"] is False
    assert contract["command_allowlist_enforced"] is False
    assert contract["approval_consumed"] is False
    assert contract["execution_authority"] is False
    assert contract["executed"] is False
    assert contract["repo_code_executed"] is False
    assert contract["network_accessed"] is False
    assert contract["current_checks"]["runner_sandbox_readiness_present"] is True
    assert contract["current_checks"]["provider_contract_declared"] is True
    assert contract["current_checks"]["network_blocked_or_policy_bound"] is True
    assert contract["current_checks"]["sandbox_provider_bound"] is False
    assert contract["current_checks"]["sandbox_bound"] is False
    assert contract["current_checks"]["sandbox_enforced"] is False
    assert "provider_contract_declared" not in contract["missing_checks"]
    assert "network_blocked_or_policy_bound" not in contract["missing_checks"]
    assert "sandbox_provider_bound" in contract["missing_checks"]
    assert "sandbox_bound" in contract["missing_checks"]
    assert "sandbox_enforced" in contract["missing_checks"]
    assert "workspace_isolation_bound" in contract["missing_checks"]
    assert result["runner_sandbox_readiness"]["sandbox_bound"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_contract.preflight"
    assert Path(result["sandbox_provider_contract_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert "super-secret-token-value" not in Path(result["sandbox_provider_contract_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_binding_preflight_blocks_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_binding(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.sandbox_provider_binding",
    )
    binding = result["sandbox_provider_binding"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert binding["binding_kind"] == "francis.lab.sandbox_provider_binding_preflight"
    assert binding["binding_mode"] == "binding_preflight_only_no_execution"
    assert binding["provider_contract_present"] is True
    assert binding["provider_contract_declared"] is True
    assert binding["provider_kind_selected"] is False
    assert binding["provider_binary_or_service_verified"] is False
    assert binding["provider_policy_manifest_bound"] is False
    assert binding["sandbox_provider_bound"] is False
    assert binding["sandbox_bound"] is False
    assert binding["sandbox_enforced"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert binding["repo_code_executed"] is False
    assert binding["network_accessed"] is False
    assert binding["current_checks"]["provider_binding_contract_declared"] is True
    assert binding["current_checks"]["provider_kind_selected"] is False
    assert binding["current_checks"]["provider_binary_or_service_verified"] is False
    assert binding["current_checks"]["network_blocked_or_policy_bound"] is True
    assert "provider_binding_contract_declared" not in binding["missing_checks"]
    assert "network_blocked_or_policy_bound" not in binding["missing_checks"]
    assert "provider_kind_selected" in binding["missing_checks"]
    assert "provider_binary_or_service_verified" in binding["missing_checks"]
    assert "sandbox_provider_bound" in binding["missing_checks"]
    assert "sandbox_bound" in binding["missing_checks"]
    assert result["sandbox_provider_contract"]["provider_contract_declared"] is True
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_binding.preflight"
    assert Path(result["sandbox_provider_binding_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert "super-secret-token-value" not in Path(result["sandbox_provider_binding_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_selection_preflight_records_metadata_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_selection(
        source["id"],
        "run_project_tests",
        approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(policy_manifest),
        actor="test.lab.sandbox_provider_selection",
    )
    selection = result["sandbox_provider_selection"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert selection["selection_kind"] == "francis.lab.sandbox_provider_selection_preflight"
    assert selection["selection_mode"] == "selection_verification_preflight_only_no_execution"
    assert selection["requested_provider_kind"] == "local_process_sandbox"
    assert selection["selected_provider_kind"] == "local_process_sandbox"
    assert selection["provider_kind_selected"] is True
    assert selection["provider_kind_allowed_by_policy"] is True
    assert selection["provider_reference_checked"] is True
    assert selection["provider_reference_present"] is True
    assert selection["provider_reference_verified"] is True
    assert selection["provider_binary_or_service_verified"] is False
    assert selection["provider_policy_manifest_present"] is True
    assert selection["provider_policy_manifest_bound"] is True
    assert selection["sandbox_provider_bound"] is False
    assert selection["sandbox_bound"] is False
    assert selection["sandbox_enforced"] is False
    assert selection["execution_authority"] is False
    assert selection["executed"] is False
    assert selection["repo_code_executed"] is False
    assert selection["network_accessed"] is False
    assert selection["current_checks"]["provider_kind_selected"] is True
    assert selection["current_checks"]["provider_reference_verified"] is True
    assert selection["current_checks"]["provider_policy_manifest_bound"] is True
    assert selection["current_checks"]["provider_binary_or_service_verified"] is False
    assert "provider_kind_selected" not in selection["missing_checks"]
    assert "provider_reference_verified" not in selection["missing_checks"]
    assert "provider_policy_manifest_bound" not in selection["missing_checks"]
    assert "provider_binary_or_service_verified" in selection["missing_checks"]
    assert "sandbox_provider_bound" in selection["missing_checks"]
    assert result["sandbox_provider_binding"]["provider_contract_declared"] is True
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_selection.preflight"
    assert Path(result["sandbox_provider_selection_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(result["sandbox_provider_selection_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_verifier_preflight_declares_contract_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_verifier(
        source["id"],
        "run_project_tests",
        approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(policy_manifest),
        actor="test.lab.sandbox_provider_verifier",
    )
    verifier = result["sandbox_provider_verifier"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert verifier["verifier_kind"] == "francis.lab.sandbox_provider_verifier_preflight"
    assert verifier["verifier_mode"] == "static_identity_policy_verification_no_execution"
    assert verifier["provider_kind"] == "local_process_sandbox"
    assert verifier["provider_selection_present"] is True
    assert verifier["provider_kind_selected"] is True
    assert verifier["provider_reference_verified"] is True
    assert verifier["provider_policy_manifest_bound"] is True
    assert verifier["verifier_contract_declared"] is True
    assert verifier["verifier_implementation_bound"] is True
    assert verifier["verifier_identity_bound"] is True
    assert verifier["verifier_policy_bound"] is True
    assert verifier["verifier_receipt_contract_bound"] is True
    assert verifier["static_identity_verification_performed"] is True
    assert verifier["provider_reference_fingerprint_captured"] is True
    assert verifier["provider_policy_manifest_hash_captured"] is True
    assert verifier["provider_binary_or_service_verified"] is True
    assert verifier["provider_runtime_probe_performed"] is False
    assert verifier["provider_version_captured"] is True
    assert verifier["provider_identity_fingerprint_captured"] is True
    assert verifier["provider_identity"]["provider_reference_fingerprint"].startswith("sha256:")
    assert verifier["provider_identity"]["provider_identity_fingerprint"].startswith("sha256:")
    assert verifier["provider_identity"]["provider_version"] == "0.1.0"
    assert verifier["provider_policy_manifest"]["manifest_hash"].startswith("sha256:")
    assert verifier["provider_policy_manifest"]["network_disabled_by_manifest"] is True
    assert verifier["provider_policy_manifest"]["direct_execution_disabled_by_manifest"] is True
    assert "secret_token" not in verifier["provider_policy_manifest"]["manifest_keys"]
    assert verifier["provider_runtime_probe"]["status"] == "not_performed"
    assert verifier["service_query_performed"] is False
    assert verifier["process_launched"] is False
    assert verifier["container_launched"] is False
    assert verifier["sandbox_provider_bound"] is False
    assert verifier["sandbox_bound"] is False
    assert verifier["sandbox_enforced"] is False
    assert verifier["execution_authority"] is False
    assert verifier["executed"] is False
    assert verifier["repo_code_executed"] is False
    assert verifier["network_accessed"] is False
    assert verifier["current_checks"]["verifier_contract_declared"] is True
    assert verifier["current_checks"]["verifier_implementation_bound"] is True
    assert verifier["current_checks"]["provider_binary_or_service_verified"] is True
    assert verifier["current_checks"]["process_launched"] is False
    assert verifier["current_checks"]["container_launched"] is False
    assert "verifier_contract_declared" not in verifier["missing_checks"]
    assert "provider_kind_selected" not in verifier["missing_checks"]
    assert "provider_reference_verified" not in verifier["missing_checks"]
    assert "provider_policy_manifest_bound" not in verifier["missing_checks"]
    assert "verifier_implementation_bound" not in verifier["missing_checks"]
    assert "verifier_identity_bound" not in verifier["missing_checks"]
    assert "provider_binary_or_service_verified" not in verifier["missing_checks"]
    assert "provider_identity_fingerprint_captured" not in verifier["missing_checks"]
    assert "provider_runtime_probe_performed" in verifier["missing_checks"]
    assert "sandbox_provider_bound" in verifier["missing_checks"]
    assert result["sandbox_provider_selection"]["provider_reference_verified"] is True
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_verifier.preflight"
    assert Path(result["sandbox_provider_verifier_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(result["sandbox_provider_verifier_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_runtime_probe_preflight_declares_contract_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_runtime_probe(
        source["id"],
        "run_project_tests",
        approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(policy_manifest),
        actor="test.lab.sandbox_provider_runtime_probe",
    )
    runtime_probe = result["sandbox_provider_runtime_probe"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert runtime_probe["probe_kind"] == "francis.lab.sandbox_provider_runtime_probe_preflight"
    assert runtime_probe["probe_mode"] == "runtime_probe_contract_preflight_only_no_provider_execution"
    assert runtime_probe["verifier_present"] is True
    assert runtime_probe["verifier_static_identity_ready"] is True
    assert runtime_probe["provider_identity_fingerprint_captured"] is True
    assert runtime_probe["provider_binary_or_service_verified"] is True
    assert runtime_probe["runtime_probe_contract_declared"] is True
    assert runtime_probe["runtime_probe_authorization_required"] is True
    assert runtime_probe["runtime_probe_policy_bound"] is True
    assert runtime_probe["runtime_probe_timeout_policy_declared"] is True
    assert runtime_probe["runtime_probe_network_blocked_by_contract"] is True
    assert runtime_probe["runtime_probe_workspace_isolation_required"] is True
    assert runtime_probe["runtime_probe_receipt_contract_declared"] is True
    assert runtime_probe["runtime_probe_repo_execution_separated"] is True
    assert runtime_probe["runtime_probe_runner_bound"] is False
    assert runtime_probe["runtime_probe_sandbox_bound"] is False
    assert runtime_probe["runtime_probe_service_query_guard_bound"] is False
    assert runtime_probe["runtime_probe_output_capture_bound"] is False
    assert runtime_probe["runtime_probe_kill_switch_bound"] is False
    assert runtime_probe["provider_runtime_probe_performed"] is False
    assert runtime_probe["service_query_performed"] is False
    assert runtime_probe["process_launched"] is False
    assert runtime_probe["container_launched"] is False
    assert runtime_probe["sandbox_provider_bound"] is False
    assert runtime_probe["execution_authority"] is False
    assert runtime_probe["executed"] is False
    assert runtime_probe["repo_code_executed"] is False
    assert runtime_probe["network_accessed"] is False
    assert runtime_probe["current_checks"]["runtime_probe_contract_declared"] is True
    assert runtime_probe["current_checks"]["provider_runtime_probe_performed"] is False
    assert "runtime_probe_contract_declared" not in runtime_probe["missing_checks"]
    assert "runtime_probe_authorization_required" not in runtime_probe["missing_checks"]
    assert "runtime_probe_network_blocked_by_contract" not in runtime_probe["missing_checks"]
    assert "runtime_probe_receipt_contract_declared" not in runtime_probe["missing_checks"]
    assert "runtime_probe_repo_execution_separated" not in runtime_probe["missing_checks"]
    assert "runtime_probe_runner_bound" in runtime_probe["missing_checks"]
    assert "runtime_probe_sandbox_bound" in runtime_probe["missing_checks"]
    assert "provider_runtime_probe_performed" in runtime_probe["missing_checks"]
    assert "sandbox_provider_bound" in runtime_probe["missing_checks"]
    assert result["sandbox_provider_verifier"]["provider_binary_or_service_verified"] is True
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.preflight"
    assert Path(result["sandbox_provider_runtime_probe_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(result["sandbox_provider_runtime_probe_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_runtime_probe_harness_preflight_declares_controls_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_runtime_probe_harness(
        source["id"],
        "run_project_tests",
        approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(policy_manifest),
        actor="test.lab.sandbox_provider_runtime_probe_harness",
    )
    harness = result["sandbox_provider_runtime_probe_harness"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert harness["harness_kind"] == "francis.lab.sandbox_provider_runtime_probe_harness_preflight"
    assert harness["harness_mode"] == "runtime_probe_harness_preflight_only_no_provider_execution"
    assert harness["runtime_probe_preflight_present"] is True
    assert harness["runtime_probe_contract_declared"] is True
    assert harness["runtime_probe_authorization_required"] is True
    assert harness["runtime_probe_network_blocked_by_contract"] is True
    assert harness["runtime_probe_workspace_isolation_required"] is True
    assert harness["runtime_probe_receipt_contract_declared"] is True
    assert harness["runtime_probe_repo_execution_separated"] is True
    assert harness["runtime_probe_runner_contract_declared"] is True
    assert harness["runtime_probe_sandbox_contract_declared"] is True
    assert harness["runtime_probe_service_query_guard_declared"] is True
    assert harness["runtime_probe_output_capture_declared"] is True
    assert harness["runtime_probe_kill_switch_declared"] is True
    assert harness["runtime_probe_runner_bound"] is False
    assert harness["runtime_probe_sandbox_bound"] is False
    assert harness["runtime_probe_service_query_guard_bound"] is False
    assert harness["runtime_probe_output_capture_bound"] is False
    assert harness["runtime_probe_kill_switch_bound"] is False
    assert harness["provider_runtime_probe_performed"] is False
    assert harness["service_query_performed"] is False
    assert harness["process_launched"] is False
    assert harness["container_launched"] is False
    assert harness["sandbox_provider_bound"] is False
    assert harness["execution_authority"] is False
    assert harness["executed"] is False
    assert harness["repo_code_executed"] is False
    assert harness["network_accessed"] is False
    assert "runtime_probe_runner_contract_declared" not in harness["missing_checks"]
    assert "runtime_probe_sandbox_contract_declared" not in harness["missing_checks"]
    assert "runtime_probe_service_query_guard_declared" not in harness["missing_checks"]
    assert "runtime_probe_runner_bound" in harness["missing_checks"]
    assert "runtime_probe_sandbox_bound" in harness["missing_checks"]
    assert "runtime_probe_service_query_guard_bound" in harness["missing_checks"]
    assert "runtime_probe_output_capture_bound" in harness["missing_checks"]
    assert "runtime_probe_kill_switch_bound" in harness["missing_checks"]
    assert "provider_runtime_probe_performed" in harness["missing_checks"]
    assert result["sandbox_provider_runtime_probe"]["runtime_probe_contract_declared"] is True
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe_harness.preflight"
    assert Path(result["sandbox_provider_runtime_probe_harness_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(result["sandbox_provider_runtime_probe_harness_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_runtime_probe_runner_readiness_declares_interface_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_runtime_probe_runner_readiness(
        source["id"],
        "run_project_tests",
        approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(policy_manifest),
        actor="test.lab.sandbox_provider_runtime_probe_runner_readiness",
    )
    readiness = result["sandbox_provider_runtime_probe_runner_readiness"]
    harness = result["sandbox_provider_runtime_probe_harness"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert readiness["status"] == "blocked"
    assert readiness["runner_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_readiness"
    assert readiness["runner_mode"] == "probe_runner_interface_readiness_only_no_provider_execution"
    assert readiness["sandbox_provider_runtime_probe_harness_id"] == harness["id"]
    assert readiness["runtime_probe_harness_present"] is True
    assert readiness["runtime_probe_harness_contract_declared"] is True
    assert readiness["probe_runner_interface_declared"] is True
    assert readiness["probe_runner_implementation_bound"] is False
    assert readiness["probe_runner_identity_bound"] is False
    assert readiness["probe_runner_policy_bound"] is False
    assert readiness["probe_runner_sandbox_bound"] is False
    assert readiness["probe_runner_network_blocked"] is False
    assert readiness["probe_runner_workspace_isolated"] is False
    assert readiness["probe_runner_timeout_bound"] is False
    assert readiness["probe_runner_output_capture_bound"] is False
    assert readiness["probe_runner_kill_switch_bound"] is False
    assert readiness["probe_runner_receipt_contract_bound"] is False
    assert readiness["provider_runtime_probe_performed"] is False
    assert readiness["service_query_performed"] is False
    assert readiness["process_launched"] is False
    assert readiness["container_launched"] is False
    assert readiness["sandbox_provider_bound"] is False
    assert readiness["sandbox_bound"] is False
    assert readiness["sandbox_enforced"] is False
    assert readiness["approval_consumed"] is False
    assert readiness["execution_authority"] is False
    assert readiness["executed"] is False
    assert readiness["repo_code_executed"] is False
    assert readiness["network_accessed"] is False
    assert readiness["wrote_to_repo"] is False
    assert "probe_runner_interface_declared" not in readiness["missing_checks"]
    assert "runtime_probe_harness_contract_declared" not in readiness["missing_checks"]
    assert "probe_runner_implementation_bound" in readiness["missing_checks"]
    assert "probe_runner_identity_bound" in readiness["missing_checks"]
    assert "probe_runner_sandbox_bound" in readiness["missing_checks"]
    assert "probe_runner_network_blocked" in readiness["missing_checks"]
    assert "probe_runner_workspace_isolated" in readiness["missing_checks"]
    assert "probe_runner_timeout_bound" in readiness["missing_checks"]
    assert "probe_runner_output_capture_bound" in readiness["missing_checks"]
    assert "probe_runner_kill_switch_bound" in readiness["missing_checks"]
    assert "probe_runner_receipt_contract_bound" in readiness["missing_checks"]
    assert "provider_runtime_probe_performed" in readiness["missing_checks"]
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe_runner.readiness"
    assert Path(result["sandbox_provider_runtime_probe_runner_readiness_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(result["sandbox_provider_runtime_probe_runner_readiness_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_runtime_probe_runner_binding_preflight_blocks_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_runtime_probe_runner_binding(
        source["id"],
        "run_project_tests",
        approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(policy_manifest),
        actor="test.lab.sandbox_provider_runtime_probe_runner_binding",
    )
    binding = result["sandbox_provider_runtime_probe_runner_binding"]
    readiness = result["sandbox_provider_runtime_probe_runner_readiness"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert binding["status"] == "blocked"
    assert binding["runner_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_binding_preflight"
    assert binding["binding_mode"] == "probe_runner_binding_preflight_no_provider_execution"
    assert binding["sandbox_provider_runtime_probe_runner_readiness_id"] == readiness["id"]
    assert binding["runner_readiness_present"] is True
    assert binding["probe_runner_interface_declared"] is True
    assert binding["probe_runner_binding_contract_declared"] is True
    assert binding["probe_runner_readiness_ready"] is False
    assert binding["probe_runner_implementation_bound"] is False
    assert binding["probe_runner_identity_bound"] is False
    assert binding["probe_runner_policy_bound"] is False
    assert binding["probe_runner_sandbox_bound"] is False
    assert binding["probe_runner_network_blocked"] is False
    assert binding["probe_runner_workspace_isolated"] is False
    assert binding["probe_runner_timeout_bound"] is False
    assert binding["probe_runner_output_capture_bound"] is False
    assert binding["probe_runner_kill_switch_bound"] is False
    assert binding["probe_runner_receipt_contract_bound"] is False
    assert binding["probe_runner_bound"] is False
    assert binding["runtime_probe_bound"] is False
    assert binding["provider_runtime_probe_performed"] is False
    assert binding["service_query_performed"] is False
    assert binding["process_launched"] is False
    assert binding["container_launched"] is False
    assert binding["sandbox_provider_bound"] is False
    assert binding["sandbox_bound"] is False
    assert binding["sandbox_enforced"] is False
    assert binding["approval_consumed"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert binding["repo_code_executed"] is False
    assert binding["network_accessed"] is False
    assert binding["wrote_to_repo"] is False
    assert "probe_runner_binding_contract_declared" not in binding["missing_checks"]
    assert "probe_runner_readiness_ready" in binding["missing_checks"]
    assert "probe_runner_bound" in binding["missing_checks"]
    assert "runtime_probe_bound" in binding["missing_checks"]
    assert "provider_runtime_probe_performed" in binding["missing_checks"]
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe_runner.binding_preflight"
    assert Path(result["sandbox_provider_runtime_probe_runner_binding_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(result["sandbox_provider_runtime_probe_runner_binding_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_lab_sandbox_provider_runtime_probe_runner_enforcement_preflight_blocks_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0", '
        '"secret_token": "super-secret-token-value"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_sandbox_provider_runtime_probe_runner_enforcement(
        source["id"],
        "run_project_tests",
        approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(provider_reference),
        provider_policy_manifest=str(policy_manifest),
        actor="test.lab.sandbox_provider_runtime_probe_runner_enforcement",
    )
    enforcement = result["sandbox_provider_runtime_probe_runner_enforcement"]
    binding = result["sandbox_provider_runtime_probe_runner_binding"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert enforcement["status"] == "blocked"
    assert enforcement["runner_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_enforcement_preflight"
    assert enforcement["enforcement_mode"] == "probe_runner_enforcement_preflight_no_provider_execution"
    assert enforcement["sandbox_provider_runtime_probe_runner_binding_id"] == binding["id"]
    assert enforcement["runner_binding_present"] is True
    assert enforcement["probe_runner_binding_contract_declared"] is True
    assert enforcement["probe_runner_enforcement_contract_declared"] is True
    assert enforcement["probe_runner_binding_ready"] is False
    assert enforcement["probe_runner_enforcement_bound"] is False
    assert enforcement["probe_runner_bound"] is False
    assert enforcement["runtime_probe_bound"] is False
    assert enforcement["probe_runner_identity_bound"] is False
    assert enforcement["probe_runner_policy_bound"] is False
    assert enforcement["probe_runner_sandbox_bound"] is False
    assert enforcement["probe_runner_network_blocked"] is False
    assert enforcement["probe_runner_workspace_isolated"] is False
    assert enforcement["probe_runner_timeout_bound"] is False
    assert enforcement["probe_runner_output_capture_bound"] is False
    assert enforcement["probe_runner_kill_switch_bound"] is False
    assert enforcement["probe_runner_receipt_contract_bound"] is False
    assert enforcement["provider_runtime_probe_performed"] is False
    assert enforcement["service_query_performed"] is False
    assert enforcement["process_launched"] is False
    assert enforcement["container_launched"] is False
    assert enforcement["approval_consumed"] is False
    assert enforcement["execution_authority"] is False
    assert enforcement["executed"] is False
    assert enforcement["repo_code_executed"] is False
    assert enforcement["network_accessed"] is False
    assert enforcement["wrote_to_repo"] is False
    assert "probe_runner_enforcement_contract_declared" not in enforcement["missing_checks"]
    assert "probe_runner_binding_ready" in enforcement["missing_checks"]
    assert "probe_runner_enforcement_bound" in enforcement["missing_checks"]
    assert "probe_runner_bound" in enforcement["missing_checks"]
    assert "runtime_probe_bound" in enforcement["missing_checks"]
    assert "provider_runtime_probe_performed" in enforcement["missing_checks"]
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe_runner.enforcement_preflight"
    assert Path(result["sandbox_provider_runtime_probe_runner_enforcement_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    artifact_text = Path(result["sandbox_provider_runtime_probe_runner_enforcement_path"]).read_text(encoding="utf-8")
    assert "metadata only provider reference" not in artifact_text
    assert "super-secret-token-value" not in artifact_text
    assert not (repo / "lab-ran.txt").exists()


def test_lab_execution_receipt_write_readiness_blocks_without_writing_execution_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_execution_receipt_write_readiness(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.receipt_write",
    )
    readiness = result["execution_receipt_write_readiness"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert readiness["approval_id"] == approval_id
    assert (
        readiness["receipt_write_contract"]["mode"]
        == "receipt_write_readiness_preflight_only_no_execution_receipt_write"
    )
    assert readiness["reserved_execution_receipt"]["id"]
    assert readiness["reserved_execution_receipt"]["operation"] == "lab.execution.run"
    assert readiness["receipt_schema_bound"] is False
    assert readiness["prewrite_bound"] is False
    assert readiness["final_write_bound"] is False
    assert readiness["execution_receipt_prewritten"] is False
    assert readiness["execution_receipt_finalized"] is False
    assert readiness["approval_consumed"] is False
    assert readiness["execution_authority"] is False
    assert readiness["executed"] is False
    assert readiness["current_checks"]["reserved_execution_receipt_id_present"] is True
    assert readiness["current_checks"]["reserved_execution_receipt_path_present"] is True
    assert readiness["current_checks"]["reserved_execution_receipt_not_written"] is True
    assert readiness["current_checks"]["prewrite_before_execution_required"] is True
    assert readiness["current_checks"]["final_write_after_execution_required"] is True
    assert readiness["current_checks"]["receipt_schema_bound"] is False
    assert readiness["current_checks"]["receipt_prewrite_writer_bound"] is False
    assert readiness["current_checks"]["receipt_final_writer_bound"] is False
    assert readiness["current_checks"]["approval_not_consumed"] is True
    assert readiness["current_checks"]["execution_authority_absent"] is True
    assert readiness["current_checks"]["commands_not_executed"] is True
    assert "reserved_execution_receipt_id_present" not in readiness["missing_checks"]
    assert "reserved_execution_receipt_not_written" not in readiness["missing_checks"]
    assert "receipt_prewrite_writer_bound" in readiness["missing_checks"]
    assert "receipt_final_writer_bound" in readiness["missing_checks"]
    assert "sandbox_bound" in readiness["missing_checks"]
    assert result["runner_sandbox_readiness"]["sandbox_bound"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.execution.receipt_write_readiness.preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_execution_receipt_prewrite_binding_binds_contract_without_writing_execution_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_execution_receipt_prewrite_binding(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.receipt_prewrite",
    )
    binding = result["execution_receipt_prewrite_binding"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert binding["approval_id"] == approval_id
    assert binding["execution_receipt_schema"]["operation"] == "lab.execution.run"
    assert binding["execution_receipt_schema"]["sensitive_value_policy"]["store_sensitive_values"] is False
    assert binding["prewrite_contract"]["mode"] == "prewrite_contract_bound_no_execution_receipt_write"
    assert binding["final_write_contract"]["mode"] == "final_write_contract_bound_no_execution_receipt_write"
    assert binding["contract_binding"]["mode"] == "contract_binding_only_no_execution_receipt_write"
    assert binding["contract_binding"]["schema_hash"]
    assert binding["contract_binding"]["prewrite_contract_hash"]
    assert binding["contract_binding"]["final_write_contract_hash"]
    assert binding["receipt_schema_bound"] is True
    assert binding["prewrite_contract_bound"] is True
    assert binding["final_write_contract_bound"] is True
    assert binding["prewrite_writer_bound"] is False
    assert binding["final_write_writer_bound"] is False
    assert binding["execution_receipt_prewritten"] is False
    assert binding["execution_receipt_finalized"] is False
    assert binding["approval_consumed"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert binding["current_checks"]["schema_contract_bound"] is True
    assert binding["current_checks"]["prewrite_contract_bound"] is True
    assert binding["current_checks"]["final_write_contract_bound"] is True
    assert binding["current_checks"]["reserved_execution_receipt_not_written"] is True
    assert binding["current_checks"]["prewrite_writer_bound"] is False
    assert binding["current_checks"]["final_writer_bound"] is False
    assert binding["current_checks"]["approval_not_consumed"] is True
    assert binding["current_checks"]["execution_authority_absent"] is True
    assert binding["current_checks"]["commands_not_executed"] is True
    assert "schema_contract_bound" not in binding["missing_checks"]
    assert "prewrite_contract_bound" not in binding["missing_checks"]
    assert "final_write_contract_bound" not in binding["missing_checks"]
    assert "prewrite_writer_bound" in binding["missing_checks"]
    assert "final_writer_bound" in binding["missing_checks"]
    assert "sandbox_bound" in binding["missing_checks"]
    assert result["execution_receipt_write_readiness"]["execution_receipt_prewritten"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.execution.receipt_prewrite_binding.preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_execution_receipt_writer_preflight_declares_boundary_without_writing_execution_receipt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    result = service.preflight_lab_execution_receipt_writer(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.receipt_writer",
    )
    writer = result["execution_receipt_writer_preflight"]

    assert result["ok"] is True
    assert result["status"] == "blocked"
    assert writer["approval_id"] == approval_id
    assert writer["writer_contract"]["mode"] == "writer_preflight_only_no_execution_receipt_write"
    assert writer["writer_contract"]["writes_reserved_execution_receipt"] is False
    assert writer["writer_boundary"]["reserved_path_within_sink"] is True
    assert writer["writer_boundary"]["reserved_receipt_not_written"] is True
    assert writer["writer_boundary"]["writes_reserved_execution_receipt"] is False
    assert writer["writer_interface_declared"] is True
    assert writer["writer_implementation_bound"] is False
    assert writer["writer_path_within_sink"] is True
    assert writer["atomic_write_plan_declared"] is True
    assert writer["redaction_policy_bound"] is True
    assert writer["prewrite_writer_bound"] is False
    assert writer["final_write_writer_bound"] is False
    assert writer["execution_receipt_prewritten"] is False
    assert writer["execution_receipt_finalized"] is False
    assert writer["approval_consumed"] is False
    assert writer["execution_authority"] is False
    assert writer["executed"] is False
    assert writer["prewrite_operation"]["performed"] is False
    assert writer["prewrite_operation"]["writes_reserved_execution_receipt"] is False
    assert writer["prewrite_operation"]["would_use_temp_path"].endswith(".tmp")
    assert writer["final_write_operation"]["performed"] is False
    assert writer["final_write_operation"]["writes_reserved_execution_receipt"] is False
    assert writer["final_write_operation"]["would_use_temp_path"].endswith(".tmp")
    assert writer["current_checks"]["reserved_execution_receipt_path_within_sink"] is True
    assert writer["current_checks"]["reserved_execution_receipt_not_written"] is True
    assert writer["current_checks"]["writer_boundary_declared"] is True
    assert writer["current_checks"]["atomic_write_plan_declared"] is True
    assert writer["current_checks"]["redaction_policy_bound"] is True
    assert writer["current_checks"]["writer_implementation_bound"] is False
    assert writer["current_checks"]["prewrite_writer_bound"] is False
    assert writer["current_checks"]["final_writer_bound"] is False
    assert writer["current_checks"]["approval_not_consumed"] is True
    assert writer["current_checks"]["execution_authority_absent"] is True
    assert writer["current_checks"]["commands_not_executed"] is True
    assert "reserved_execution_receipt_path_within_sink" not in writer["missing_checks"]
    assert "reserved_execution_receipt_not_written" not in writer["missing_checks"]
    assert "writer_implementation_bound" in writer["missing_checks"]
    assert "prewrite_writer_bound" in writer["missing_checks"]
    assert "final_writer_bound" in writer["missing_checks"]
    assert result["execution_receipt_prewrite_binding"]["execution_receipt_prewritten"] is False
    assert result["execution"]["executed"] is False
    assert result["execution"]["ran_repo_scripts"] is False
    assert result["receipt"]["operation"] == "lab.execution.receipt_writer.preflight"
    assert Path(result["artifact_path"]).exists()
    assert Path(result["receipt_path"]).exists()
    assert not Path(result["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert "super-secret-token-value" not in Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()


def test_lab_synthetic_execution_receipt_prewrite_and_finalize_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    prewrite_result = service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    prewritten = prewrite_result["execution_receipt"]
    receipt_path = Path(prewrite_result["execution_receipt_path"])

    assert prewrite_result["ok"] is True
    assert prewrite_result["status"] == "prewritten"
    assert prewritten["operation"] == "lab.execution.run"
    assert prewritten["mode"] == "synthetic_noop_execution_receipt"
    assert prewritten["phase"] == "prewrite"
    assert prewritten["synthetic"] is True
    assert prewritten["noop"] is True
    assert prewritten["prewritten"] is True
    assert prewritten["finalized"] is False
    assert prewritten["approval_consumed"] is False
    assert prewritten["execution_authority"] is False
    assert prewritten["executed"] is False
    assert prewritten["ran_repo_scripts"] is False
    assert prewritten["ran_install"] is False
    assert prewritten["ran_build"] is False
    assert prewritten["ran_tests"] is False
    assert prewritten["network_accessed"] is False
    assert prewritten["wrote_to_repo"] is False
    assert prewritten["store_sensitive_values"] is False
    assert "synthetic_noop_execution_receipt_only" in prewritten["warnings"]
    assert prewrite_result["execution"]["executed"] is False
    assert prewrite_result["execution"]["ran_repo_scripts"] is False
    assert prewrite_result["receipt"]["operation"] == "lab.execution.receipt.synthetic_prewrite"
    assert receipt_path.exists()
    assert Path(prewrite_result["receipt_path"]).exists()
    assert receipt_path == Path(prewrite_result["reserved_execution_receipt"]["path"])
    assert "super-secret-token-value" not in receipt_path.read_text(encoding="utf-8")
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()

    finalize_result = service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    finalized = finalize_result["execution_receipt"]

    assert finalize_result["ok"] is True
    assert finalize_result["status"] == "blocked"
    assert finalized["id"] == prewritten["id"]
    assert finalized["phase"] == "finalize"
    assert finalized["status"] == "blocked"
    assert finalized["result_status"] == "blocked"
    assert finalized["synthetic"] is True
    assert finalized["noop"] is True
    assert finalized["prewritten"] is True
    assert finalized["finalized"] is True
    assert finalized["approval_consumed"] is False
    assert finalized["execution_authority"] is False
    assert finalized["executed"] is False
    assert finalized["ran_repo_scripts"] is False
    assert finalized["network_accessed"] is False
    assert "synthetic_noop_execution_receipt_finalized" in finalized["warnings"]
    assert finalize_result["receipt"]["operation"] == "lab.execution.receipt.synthetic_finalize"
    assert Path(finalize_result["execution_receipt_path"]) == receipt_path
    assert receipt_path.exists()
    assert "super-secret-token-value" not in receipt_path.read_text(encoding="utf-8")
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_synthetic_noop_approval_consumption_enforces_single_use_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )

    result = service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    record = result["approval_consumption_record"]
    artifact_path = Path(result["approval_consumption_record_path"])

    assert result["ok"] is True
    assert result["status"] == "consumed"
    assert record["approval_id"] == approval_id
    assert record["status"] == "consumed"
    assert record["approval_consumed"] is True
    assert record["single_use_enforced"] is True
    assert record["consumption_kind"] == "synthetic_noop_execution_receipt"
    assert record["execution_authority"] is False
    assert record["executed"] is False
    assert record["ran_repo_scripts"] is False
    assert record["network_accessed"] is False
    assert record["wrote_to_repo"] is False
    assert record["store_sensitive_values"] is False
    assert result["receipt"]["operation"] == "lab.execution.approval.consume_synthetic_noop"
    assert artifact_path.exists()
    assert Path(result["receipt_path"]).exists()
    assert "super-secret-token-value" not in artifact_path.read_text(encoding="utf-8")
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()

    reuse = service.preflight_lab_approval_consumption(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.consume",
    )

    assert reuse["status"] == "refused"
    assert reuse["approval_consumption"]["binding"]["approval_consumed"] is True
    assert reuse["approval_consumption"]["binding"]["approval_consumption_record_id"] == record["id"]
    assert "approval_already_consumed" in reuse["approval_consumption"]["blockers"]
    assert reuse["execution"]["executed"] is False
    assert not (repo / "lab-ran.txt").exists()

    envelope_result = service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    envelope = envelope_result["noop_runner_envelope"]
    envelope_path = Path(envelope_result["noop_runner_envelope_path"])

    assert envelope_result["ok"] is True
    assert envelope_result["status"] == "completed"
    assert envelope["status"] == "completed"
    assert envelope["runner_kind"] == "francis.lab.noop_runner"
    assert envelope["runner_mode"] == "builtin_noop_only"
    assert envelope["approval_consumption_record_id"] == record["id"]
    assert envelope["approval_consumed"] is True
    assert envelope["single_use_enforced"] is True
    assert envelope["noop_performed"] is True
    assert envelope["execution_authority"] is False
    assert envelope["executed"] is False
    assert envelope["commands_executed"] is False
    assert envelope["repo_code_executed"] is False
    assert envelope["ran_repo_scripts"] is False
    assert envelope["network_accessed"] is False
    assert envelope["wrote_to_repo"] is False
    assert envelope_result["execution"]["builtin_noop_performed"] is True
    assert envelope_result["execution"]["executed"] is False
    assert envelope_result["receipt"]["operation"] == "lab.runner.noop_envelope"
    assert envelope_path.exists()
    assert "super-secret-token-value" not in envelope_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    transcript_result = service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )
    transcript = transcript_result["noop_runner_transcript"]
    transcript_path = Path(transcript_result["noop_runner_transcript_path"])

    assert transcript_result["ok"] is True
    assert transcript_result["status"] == "completed"
    assert transcript["status"] == "completed"
    assert transcript["noop_runner_envelope_id"] == envelope["id"]
    assert transcript["capture_kind"] == "francis.lab.noop_runner_transcript"
    assert transcript["capture_mode"] == "builtin_noop_empty_output"
    assert transcript["noop_performed"] is True
    assert transcript["builtin_noop_output_captured"] is True
    assert transcript["real_process_output_captured"] is False
    assert transcript["stdout"]["bytes"] == 0
    assert transcript["stderr"]["bytes"] == 0
    assert transcript["stdout_content_stored"] is False
    assert transcript["stderr_content_stored"] is False
    assert transcript["output_content_stored"] is False
    assert transcript["execution_authority"] is False
    assert transcript["executed"] is False
    assert transcript["commands_executed"] is False
    assert transcript["repo_code_executed"] is False
    assert transcript["ran_repo_scripts"] is False
    assert transcript["network_accessed"] is False
    assert transcript["wrote_to_repo"] is False
    assert transcript_result["execution"]["builtin_noop_output_captured"] is True
    assert transcript_result["execution"]["real_process_output_captured"] is False
    assert transcript_result["execution"]["executed"] is False
    assert transcript_result["receipt"]["operation"] == "lab.runner.noop_transcript"
    assert transcript_path.exists()
    assert "super-secret-token-value" not in transcript_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    repeat_transcript = service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )

    assert repeat_transcript["ok"] is False
    assert repeat_transcript["status"] == "blocked"
    assert repeat_transcript["prior_noop_runner_transcript_path"] == str(transcript_path)
    assert "noop_runner_transcript_not_already_completed" in repeat_transcript["blockers"]
    assert transcript_path.exists()
    assert json.loads(transcript_path.read_text(encoding="utf-8"))["noop_runner_transcript"]["status"] == "completed"
    assert not (repo / "lab-ran.txt").exists()

    identity_result = service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )
    identity = identity_result["noop_runner_identity_binding"]
    identity_path = Path(identity_result["noop_runner_identity_binding_path"])

    assert identity_result["ok"] is True
    assert identity_result["status"] == "completed"
    assert identity["status"] == "completed"
    assert identity["noop_runner_transcript_id"] == transcript["id"]
    assert identity["noop_runner_envelope_id"] == envelope["id"]
    assert identity["runner_id"] == "francis.lab.runner.builtin_noop.v0"
    assert identity["runner_identity_bound"] is True
    assert identity["builtin_noop_only"] is True
    assert identity["live_runner_bound"] is False
    assert identity["sandbox_runner_bound"] is False
    assert identity["execution_authority"] is False
    assert identity["executed"] is False
    assert identity["commands_executed"] is False
    assert identity["repo_code_executed"] is False
    assert identity["network_accessed"] is False
    assert identity["real_process_output_captured"] is False
    assert identity["candidate_validated"] is False
    assert identity["capability_promoted"] is False
    assert identity_result["execution"]["builtin_noop_runner_identity_bound"] is True
    assert identity_result["execution"]["live_runner_bound"] is False
    assert identity_result["execution"]["sandbox_runner_bound"] is False
    assert identity_result["execution"]["candidate_validated"] is False
    assert identity_result["receipt"]["operation"] == "lab.runner.noop_identity_bind"
    assert identity_path.exists()
    assert "super-secret-token-value" not in identity_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    mount_readiness_result = service.preflight_lab_source_mount_readiness(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.source_mount",
    )
    mount_readiness = mount_readiness_result["source_mount_readiness"]
    mount_readiness_path = Path(mount_readiness_result["source_mount_readiness_path"])

    assert mount_readiness_result["ok"] is True
    assert mount_readiness_result["status"] == "ready"
    assert mount_readiness["status"] == "ready"
    assert mount_readiness["noop_runner_identity_binding_id"] == identity["id"]
    assert mount_readiness["workspace"]["source_reference"]["mode"] == "reference_only_read_only"
    assert mount_readiness["source_mount_mode"] == "reference_only_read_only"
    assert mount_readiness["source_reference_ready"] is True
    assert mount_readiness["read_only_reference_confirmed"] is True
    assert mount_readiness["read_only_mount_bound"] is False
    assert mount_readiness["source_mount_enforced"] is False
    assert mount_readiness["source_copied"] is False
    assert mount_readiness["source_write_allowed"] is False
    assert mount_readiness["runner_identity_verified"] is True
    assert mount_readiness["live_runner_bound"] is False
    assert mount_readiness["sandbox_runner_bound"] is False
    assert mount_readiness["execution_authority"] is False
    assert mount_readiness["executed"] is False
    assert mount_readiness["commands_executed"] is False
    assert mount_readiness["repo_code_executed"] is False
    assert mount_readiness["network_accessed"] is False
    assert mount_readiness["candidate_validated"] is False
    assert mount_readiness["capability_promoted"] is False
    assert mount_readiness_result["execution"]["source_mount_readiness_recorded"] is True
    assert mount_readiness_result["execution"]["source_mount_ready"] is True
    assert mount_readiness_result["execution"]["read_only_mount_bound"] is False
    assert mount_readiness_result["execution"]["source_mount_enforced"] is False
    assert mount_readiness_result["execution"]["executed"] is False
    assert mount_readiness_result["receipt"]["operation"] == "lab.source_mount.readiness"
    assert mount_readiness_path.exists()
    assert "super-secret-token-value" not in mount_readiness_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    mount_contract_result = service.preflight_lab_source_mount_contract(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.source_mount_contract",
    )
    mount_contract = mount_contract_result["source_mount_contract"]
    mount_contract_path = Path(mount_contract_result["source_mount_contract_path"])

    assert mount_contract_result["ok"] is True
    assert mount_contract_result["status"] == "ready"
    assert mount_contract["status"] == "ready"
    assert mount_contract["source_mount_readiness_id"] == mount_readiness["id"]
    assert mount_contract["contract_kind"] == "francis.lab.source_mount_contract"
    assert mount_contract["contract_mode"] == "contract_only_no_live_mount"
    assert mount_contract["mount_mode"] == "future_read_only_source_mount"
    assert mount_contract["contract_declared"] is True
    assert mount_contract["source_mount_contract"]["mode"] == "contract_only_no_live_mount"
    assert mount_contract["source_mount_contract"]["mount_mode"] == "future_read_only_source_mount"
    assert "os_readonly_mount_or_equivalent" in mount_contract["source_mount_contract"]["requires"]
    assert mount_contract["source_mount_contract"]["allowed_read_roots"] == [source["canonical_path"]]
    assert mount_contract["source_mount_contract"]["denied_write_roots"] == [source["canonical_path"]]
    assert mount_contract["live_mount_bound"] is False
    assert mount_contract["mount_enforced"] is False
    assert mount_contract["read_only_mount_bound"] is False
    assert mount_contract["source_copied"] is False
    assert mount_contract["source_write_allowed"] is False
    assert mount_contract["live_runner_bound"] is False
    assert mount_contract["sandbox_runner_bound"] is False
    assert mount_contract["execution_authority"] is False
    assert mount_contract["executed"] is False
    assert mount_contract["commands_executed"] is False
    assert mount_contract["repo_code_executed"] is False
    assert mount_contract["network_accessed"] is False
    assert mount_contract["candidate_validated"] is False
    assert mount_contract["capability_promoted"] is False
    assert mount_contract_result["execution"]["source_mount_contract_recorded"] is True
    assert mount_contract_result["execution"]["source_mount_contract_declared"] is True
    assert mount_contract_result["execution"]["live_mount_bound"] is False
    assert mount_contract_result["execution"]["mount_enforced"] is False
    assert mount_contract_result["execution"]["executed"] is False
    assert mount_contract_result["receipt"]["operation"] == "lab.source_mount.contract"
    assert mount_contract_path.exists()
    assert "super-secret-token-value" not in mount_contract_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    run_boundary_result = service.preflight_lab_run_boundary(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.run_boundary",
    )
    run_boundary = run_boundary_result["run_boundary_preflight"]
    provider_contract = run_boundary_result["sandbox_provider_contract"]
    provider_binding = run_boundary_result["sandbox_provider_binding"]
    provider_selection = run_boundary_result["sandbox_provider_selection"]
    provider_verifier = run_boundary_result["sandbox_provider_verifier"]
    provider_runtime_probe = run_boundary_result["sandbox_provider_runtime_probe"]
    provider_runtime_probe_harness = run_boundary_result["sandbox_provider_runtime_probe_harness"]
    run_boundary_path = Path(run_boundary_result["run_boundary_preflight_path"])

    assert run_boundary_result["ok"] is True
    assert run_boundary_result["status"] == "blocked"
    assert run_boundary["status"] == "blocked"
    assert run_boundary["boundary_kind"] == "francis.lab.run_boundary_preflight"
    assert run_boundary["boundary_mode"] == "preflight_only_no_execution"
    assert run_boundary["run_mode"] == "future_sandboxed_rebuild_run_test"
    assert run_boundary["source_mount_contract_id"] == mount_contract["id"]
    assert run_boundary["sandbox_provider_contract_id"] == provider_contract["id"]
    assert run_boundary["sandbox_provider_binding_id"] == provider_binding["id"]
    assert run_boundary["sandbox_provider_selection_id"] == provider_selection["id"]
    assert run_boundary["sandbox_provider_verifier_id"] == provider_verifier["id"]
    assert run_boundary["sandbox_provider_runtime_probe_id"] == provider_runtime_probe["id"]
    assert run_boundary["sandbox_provider_runtime_probe_harness_id"] == provider_runtime_probe_harness["id"]
    assert run_boundary["source_mount_contract_declared"] is True
    assert run_boundary["sandbox_provider_contract_declared"] is True
    assert run_boundary["sandbox_provider_binding_ready"] is False
    assert run_boundary["sandbox_provider_selection_ready"] is False
    assert run_boundary["sandbox_provider_verifier_ready"] is False
    assert run_boundary["sandbox_provider_runtime_probe_ready"] is False
    assert run_boundary["sandbox_provider_runtime_probe_harness_ready"] is False
    assert run_boundary["runtime_probe_harness_contract_declared"] is True
    assert run_boundary["runtime_probe_runner_bound"] is False
    assert run_boundary["runtime_probe_sandbox_bound"] is False
    assert run_boundary["runtime_probe_service_query_guard_bound"] is False
    assert run_boundary["runtime_probe_output_capture_bound"] is False
    assert run_boundary["runtime_probe_kill_switch_bound"] is False
    assert run_boundary["provider_runtime_probe_performed"] is False
    assert run_boundary["sandbox_provider_bound"] is False
    assert run_boundary["read_only_mount_bound"] is False
    assert run_boundary["mount_enforced"] is False
    assert run_boundary["sandbox_bound"] is False
    assert run_boundary["sandbox_enforced"] is False
    assert run_boundary["command_allowlist_enforced"] is False
    assert run_boundary["writer_implementation_bound"] is False
    assert run_boundary["receipt_prewrite_bound"] is False
    assert run_boundary["receipt_final_write_bound"] is False
    assert run_boundary["approval_consumed"] is False
    assert run_boundary["execution_authority"] is False
    assert run_boundary["executed"] is False
    assert run_boundary["commands_executed"] is False
    assert run_boundary["repo_code_executed"] is False
    assert run_boundary["network_accessed"] is False
    assert run_boundary["candidate_validated"] is False
    assert run_boundary["capability_promoted"] is False
    assert "read_only_mount_bound" in run_boundary["missing_checks"]
    assert "sandbox_provider_contract_ready" in run_boundary["missing_checks"]
    assert "sandbox_provider_binding_ready" in run_boundary["missing_checks"]
    assert "sandbox_provider_selection_ready" in run_boundary["missing_checks"]
    assert "sandbox_provider_verifier_ready" in run_boundary["missing_checks"]
    assert "sandbox_provider_runtime_probe_ready" in run_boundary["missing_checks"]
    assert "sandbox_provider_runtime_probe_harness_ready" in run_boundary["missing_checks"]
    assert "runtime_probe_harness_contract_declared" not in run_boundary["missing_checks"]
    assert "runtime_probe_runner_bound" in run_boundary["missing_checks"]
    assert "runtime_probe_sandbox_bound" in run_boundary["missing_checks"]
    assert "runtime_probe_service_query_guard_bound" in run_boundary["missing_checks"]
    assert "runtime_probe_output_capture_bound" in run_boundary["missing_checks"]
    assert "runtime_probe_kill_switch_bound" in run_boundary["missing_checks"]
    assert "provider_runtime_probe_performed" in run_boundary["missing_checks"]
    assert "provider_kind_selected" in run_boundary["missing_checks"]
    assert "verifier_implementation_bound" not in run_boundary["missing_checks"]
    assert "verifier_identity_bound" not in run_boundary["missing_checks"]
    assert "provider_binary_or_service_verified" in run_boundary["missing_checks"]
    assert "sandbox_provider_bound" in run_boundary["missing_checks"]
    assert "sandbox_bound" in run_boundary["missing_checks"]
    assert "command_allowlist_enforced" in run_boundary["missing_checks"]
    assert "writer_implementation_bound" in run_boundary["missing_checks"]
    assert run_boundary_result["execution"]["run_boundary_preflight_recorded"] is True
    assert run_boundary_result["execution"]["run_boundary_ready"] is False
    assert run_boundary_result["execution"]["executed"] is False
    assert run_boundary_result["receipt"]["operation"] == "lab.run_boundary.preflight"
    assert run_boundary_path.exists()
    assert "super-secret-token-value" not in run_boundary_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    probe_boundary_result = service.preflight_lab_sandbox_provider_runtime_probe_execution_boundary(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.runtime_probe_execution_boundary",
    )
    probe_boundary = probe_boundary_result["sandbox_provider_runtime_probe_execution_boundary"]
    probe_boundary_path = Path(probe_boundary_result["sandbox_provider_runtime_probe_execution_boundary_path"])

    assert probe_boundary_result["ok"] is True
    assert probe_boundary_result["status"] == "blocked"
    assert probe_boundary["status"] == "blocked"
    assert probe_boundary["boundary_kind"] == "francis.lab.sandbox_provider_runtime_probe_execution_boundary"
    assert probe_boundary["boundary_mode"] == "execution_boundary_preflight_only_no_provider_execution"
    assert probe_boundary["run_boundary_preflight_id"] == run_boundary["id"]
    assert probe_boundary["run_boundary_present"] is True
    assert probe_boundary["run_boundary_ready"] is False
    assert probe_boundary["runtime_probe_runner_enforcement_present"] is True
    assert probe_boundary["runtime_probe_runner_enforcement_ready"] is False
    assert probe_boundary["runtime_probe_runner_enforcement_bound"] is False
    assert probe_boundary["runtime_probe_bound"] is False
    assert probe_boundary["provider_probe_execution_boundary_declared"] is True
    assert probe_boundary["provider_probe_execution_boundary_bound"] is False
    assert probe_boundary["provider_runtime_probe_performed"] is False
    assert probe_boundary["execution_receipt_writer_bound"] is False
    assert probe_boundary["sandbox_bound"] is False
    assert probe_boundary["sandbox_enforced"] is False
    assert probe_boundary["process_launched"] is False
    assert probe_boundary["container_launched"] is False
    assert probe_boundary["repo_code_executed"] is False
    assert probe_boundary["network_accessed"] is False
    assert probe_boundary["wrote_to_repo"] is False
    assert probe_boundary["execution_receipt_written"] is False
    assert "provider_probe_execution_boundary_declared" not in probe_boundary["missing_checks"]
    assert "run_boundary_ready" in probe_boundary["missing_checks"]
    assert "runtime_probe_runner_enforcement_bound" in probe_boundary["missing_checks"]
    assert "provider_runtime_probe_performed" in probe_boundary["missing_checks"]
    assert "execution_receipt_not_written" not in probe_boundary["missing_checks"]
    assert probe_boundary_result["execution"]["provider_runtime_probe_execution_boundary_recorded"] is True
    assert probe_boundary_result["execution"]["provider_runtime_probe_execution_boundary_ready"] is False
    assert probe_boundary_result["execution"]["provider_runtime_probe_performed"] is False
    assert probe_boundary_result["execution"]["process_launched"] is False
    assert probe_boundary_result["execution"]["container_launched"] is False
    assert probe_boundary_result["execution"]["executed"] is False
    assert probe_boundary_result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.execution_boundary"
    assert probe_boundary_path.exists()
    assert "super-secret-token-value" not in probe_boundary_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    probe_refusal_result = service.refuse_lab_sandbox_provider_runtime_probe(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.runtime_probe_refusal",
    )
    probe_refusal = probe_refusal_result["sandbox_provider_runtime_probe_refusal"]
    probe_refusal_path = Path(probe_refusal_result["sandbox_provider_runtime_probe_refusal_path"])

    assert probe_refusal_result["ok"] is True
    assert probe_refusal_result["status"] == "blocked"
    assert probe_refusal["status"] == "blocked"
    assert probe_refusal["refusal_kind"] == "francis.lab.sandbox_provider_runtime_probe_refusal"
    assert probe_refusal["refusal_mode"] == "refusal_only_no_provider_execution"
    assert probe_refusal["execution_boundary_id"] == probe_boundary["id"]
    assert probe_refusal["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.refuse"
    assert probe_refusal["provider_runtime_probe_performed"] is False
    assert probe_refusal["provider_binary_executed"] is False
    assert probe_refusal["service_query_performed"] is False
    assert probe_refusal["process_launched"] is False
    assert probe_refusal["container_launched"] is False
    assert probe_refusal["repo_code_executed"] is False
    assert probe_refusal["network_accessed"] is False
    assert probe_refusal["wrote_to_repo"] is False
    assert probe_refusal["execution_receipt_written"] is False
    assert probe_refusal["approval_consumed"] is False
    assert "sandbox_provider_runtime_probe_refused_in_v0" in probe_refusal["blockers"]
    assert "no_governed_provider_probe_runner_bound" in probe_refusal["blockers"]
    assert probe_refusal_result["execution"]["provider_runtime_probe_execution_boundary_recorded"] is True
    assert probe_refusal_result["execution"]["provider_runtime_probe_performed"] is False
    assert probe_refusal_result["execution"]["provider_binary_executed"] is False
    assert probe_refusal_result["execution"]["process_launched"] is False
    assert probe_refusal_result["execution"]["container_launched"] is False
    assert probe_refusal_result["execution"]["execution_receipt_written"] is False
    assert probe_refusal_result["execution"]["approval_consumed"] is False
    assert probe_refusal_result["execution"]["executed"] is False
    assert probe_refusal_result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.refuse"
    assert probe_refusal_path.exists()
    assert "super-secret-token-value" not in probe_refusal_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    probe_approval_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.runtime_probe_approval_request",
    )
    probe_approval_request = probe_approval_result["sandbox_provider_runtime_probe_approval_request"]
    probe_approval_path = Path(probe_approval_result["sandbox_provider_runtime_probe_approval_request_path"])
    pending_probe_approval_path = Path(probe_approval_result["approval_path"])

    assert probe_approval_result["ok"] is True
    assert probe_approval_result["status"] == "needs_approval"
    assert probe_approval_request["status"] == "needs_approval"
    assert probe_approval_request["action"] == "francis.lab.sandbox_provider_runtime_probe"
    assert probe_approval_request["approval_created"] is True
    assert probe_approval_request["approval_id"] == probe_approval_result["approval"]["id"]
    assert probe_approval_request["upstream_approval_id"] == approval_id
    assert (
        probe_approval_request["execution_boundary_id"]
        == probe_approval_result["sandbox_provider_runtime_probe_execution_boundary"]["id"]
    )
    assert probe_approval_request["permission_scope"] == ("ingest.lab.sandbox.provider_runtime_probe.request_approval")
    assert probe_approval_request["approval_consumed"] is False
    assert probe_approval_request["upstream_approval_consumed"] is False
    assert probe_approval_request["execution_authority"] is False
    assert probe_approval_request["executed"] is False
    assert probe_approval_request["provider_runtime_probe_performed"] is False
    assert probe_approval_request["provider_binary_executed"] is False
    assert probe_approval_request["service_query_performed"] is False
    assert probe_approval_request["process_launched"] is False
    assert probe_approval_request["container_launched"] is False
    assert probe_approval_request["repo_code_executed"] is False
    assert probe_approval_request["execution_receipt_written"] is False
    assert "sandbox_provider_runtime_probe_requires_operator_approval" in probe_approval_request["blockers"]
    assert probe_approval_result["execution"]["approval_request_created"] is True
    assert probe_approval_result["execution"]["provider_runtime_probe_performed"] is False
    assert probe_approval_result["execution"]["provider_binary_executed"] is False
    assert probe_approval_result["execution"]["process_launched"] is False
    assert probe_approval_result["execution"]["container_launched"] is False
    assert probe_approval_result["execution"]["execution_receipt_written"] is False
    assert probe_approval_result["execution"]["approval_consumed"] is False
    assert probe_approval_result["execution"]["executed"] is False
    assert probe_approval_result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.approval_request"
    assert probe_approval_path.exists()
    assert pending_probe_approval_path.exists()
    assert "super-secret-token-value" not in probe_approval_path.read_text(encoding="utf-8")
    assert "super-secret-token-value" not in pending_probe_approval_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    provider_probe_approval_id = probe_approval_request["approval_id"]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")
    probe_consumption_result = service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.lab.runtime_probe_approval_consume",
    )
    probe_consumption = probe_consumption_result["sandbox_provider_runtime_probe_approval_consumption"]
    probe_consumption_path = Path(probe_consumption_result["sandbox_provider_runtime_probe_approval_consumption_path"])

    assert probe_consumption_result["ok"] is True
    assert probe_consumption_result["status"] == "consumed"
    assert probe_consumption["status"] == "consumed"
    assert probe_consumption["action"] == "francis.lab.sandbox_provider_runtime_probe"
    assert probe_consumption["approval_id"] == provider_probe_approval_id
    assert probe_consumption["approval_request_id"] == probe_approval_request["id"]
    assert probe_consumption["upstream_approval_id"] == approval_id
    assert probe_consumption["execution_boundary_id"] == probe_approval_request["execution_boundary_id"]
    assert probe_consumption["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.consume_approval"
    assert probe_consumption["approval_status"] == "approved"
    assert probe_consumption["approval_consumed"] is True
    assert probe_consumption["single_use_enforced"] is True
    assert probe_consumption["upstream_approval_consumed"] is False
    assert probe_consumption["execution_authority"] is False
    assert probe_consumption["executed"] is False
    assert probe_consumption["provider_runtime_probe_performed"] is False
    assert probe_consumption["provider_binary_executed"] is False
    assert probe_consumption["service_query_performed"] is False
    assert probe_consumption["process_launched"] is False
    assert probe_consumption["container_launched"] is False
    assert probe_consumption["repo_code_executed"] is False
    assert probe_consumption["network_accessed"] is False
    assert probe_consumption["wrote_to_repo"] is False
    assert probe_consumption["execution_receipt_written"] is False
    assert probe_consumption["store_sensitive_values"] is False
    assert probe_consumption_result["approval_binding"]["exact_match"] is True
    assert probe_consumption_result["approval_binding"]["approval_consumed"] is False
    assert probe_consumption_result["execution"]["approval_consumed"] is True
    assert probe_consumption_result["execution"]["provider_runtime_probe_approval_consumed"] is True
    assert probe_consumption_result["execution"]["provider_runtime_probe_performed"] is False
    assert probe_consumption_result["execution"]["provider_binary_executed"] is False
    assert probe_consumption_result["execution"]["process_launched"] is False
    assert probe_consumption_result["execution"]["container_launched"] is False
    assert probe_consumption_result["execution"]["execution_receipt_written"] is False
    assert probe_consumption_result["execution"]["executed"] is False
    assert probe_consumption_result["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.approval.consume"
    assert probe_consumption_path.exists()
    assert Path(probe_consumption_result["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{provider_probe_approval_id}.json").exists()
    assert "super-secret-token-value" not in probe_consumption_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    probe_invocation_result = service.preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.lab.runtime_probe_invocation_boundary",
    )
    probe_invocation = probe_invocation_result["sandbox_provider_runtime_probe_invocation_boundary"]
    probe_invocation_path = Path(probe_invocation_result["sandbox_provider_runtime_probe_invocation_boundary_path"])

    assert probe_invocation_result["ok"] is True
    assert probe_invocation_result["status"] == "blocked"
    assert probe_invocation["status"] == "blocked"
    assert probe_invocation["boundary_kind"] == "francis.lab.sandbox_provider_runtime_probe_invocation_boundary"
    assert probe_invocation["boundary_mode"] == "invocation_boundary_preflight_only_no_provider_execution"
    assert probe_invocation["invocation_mode"] == "future_sandbox_provider_runtime_probe_invocation"
    assert probe_invocation["approval_id"] == provider_probe_approval_id
    assert probe_invocation["approval_consumption_id"] == probe_consumption["id"]
    assert probe_invocation["approval_request_id"] == probe_approval_request["id"]
    assert probe_invocation["execution_boundary_id"] == probe_approval_request["execution_boundary_id"]
    assert probe_invocation["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.invocation_boundary"
    assert probe_invocation["approval_consumed"] is True
    assert probe_invocation["single_use_consumption_found"] is True
    assert probe_invocation["single_use_enforced"] is True
    assert probe_invocation["exact_action_binding_verified"] is True
    assert probe_invocation["execution_boundary_present"] is True
    assert probe_invocation["execution_boundary_recorded"] is True
    assert probe_invocation["execution_boundary_ready"] is False
    assert probe_invocation["provider_probe_execution_boundary_bound"] is False
    assert probe_invocation["probe_runner_bound"] is False
    assert probe_invocation["probe_runner_policy_bound"] is False
    assert probe_invocation["probe_runner_sandbox_bound"] is False
    assert probe_invocation["probe_runner_timeout_bound"] is False
    assert probe_invocation["probe_runner_output_capture_bound"] is False
    assert probe_invocation["probe_runner_kill_switch_bound"] is False
    assert probe_invocation["probe_runner_receipt_writer_bound"] is False
    assert probe_invocation["execution_authority"] is False
    assert probe_invocation["executed"] is False
    assert probe_invocation["provider_runtime_probe_performed"] is False
    assert probe_invocation["provider_binary_executed"] is False
    assert probe_invocation["service_query_performed"] is False
    assert probe_invocation["process_launched"] is False
    assert probe_invocation["container_launched"] is False
    assert probe_invocation["repo_code_executed"] is False
    assert probe_invocation["network_accessed"] is False
    assert probe_invocation["wrote_to_repo"] is False
    assert probe_invocation["execution_receipt_written"] is False
    assert "execution_boundary_ready" in probe_invocation["missing_checks"]
    assert "provider_probe_execution_boundary_bound" in probe_invocation["missing_checks"]
    assert "probe_runner_bound" in probe_invocation["missing_checks"]
    assert "probe_runner_receipt_writer_bound" in probe_invocation["missing_checks"]
    assert "provider_runtime_probe_invocation_blocked_until_governed_runner_bound" in probe_invocation["blockers"]
    assert probe_invocation_result["execution"]["provider_runtime_probe_invocation_boundary_recorded"] is True
    assert probe_invocation_result["execution"]["provider_runtime_probe_invocation_boundary_ready"] is False
    assert probe_invocation_result["execution"]["approval_consumed"] is True
    assert probe_invocation_result["execution"]["provider_runtime_probe_performed"] is False
    assert probe_invocation_result["execution"]["provider_binary_executed"] is False
    assert probe_invocation_result["execution"]["process_launched"] is False
    assert probe_invocation_result["execution"]["container_launched"] is False
    assert probe_invocation_result["execution"]["execution_receipt_written"] is False
    assert probe_invocation_result["execution"]["executed"] is False
    assert probe_invocation_result["receipt"]["operation"] == ("lab.sandbox.provider_runtime_probe.invocation_boundary")
    assert probe_invocation_path.exists()
    assert Path(probe_invocation_result["receipt_path"]).exists()
    assert "super-secret-token-value" not in probe_invocation_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    probe_pre_execution_result = service.preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.lab.runtime_probe_runner_pre_execution_boundary",
    )
    probe_pre_execution = probe_pre_execution_result["sandbox_provider_runtime_probe_runner_pre_execution_boundary"]
    probe_pre_execution_path = Path(
        probe_pre_execution_result["sandbox_provider_runtime_probe_runner_pre_execution_boundary_path"]
    )

    assert probe_pre_execution_result["ok"] is True
    assert probe_pre_execution_result["status"] == "blocked"
    assert probe_pre_execution["status"] == "blocked"
    assert (
        probe_pre_execution["boundary_kind"]
        == "francis.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary"
    )
    assert probe_pre_execution["boundary_mode"] == "runner_pre_execution_boundary_no_provider_execution"
    assert probe_pre_execution["pre_execution_mode"] == "future_sandbox_provider_runtime_probe_runner_pre_execution"
    assert probe_pre_execution["approval_id"] == provider_probe_approval_id
    assert probe_pre_execution["approval_consumption_id"] == probe_consumption["id"]
    assert probe_pre_execution["invocation_boundary_id"] == probe_invocation["id"]
    assert probe_pre_execution["approval_request_id"] == probe_approval_request["id"]
    assert probe_pre_execution["execution_boundary_id"] == probe_approval_request["execution_boundary_id"]
    assert (
        probe_pre_execution["permission_scope"]
        == "ingest.lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary"
    )
    assert probe_pre_execution["invocation_boundary_found"] is True
    assert probe_pre_execution["invocation_boundary_recorded"] is True
    assert probe_pre_execution["invocation_boundary_ready"] is False
    assert probe_pre_execution["approval_consumed"] is True
    assert probe_pre_execution["single_use_consumption_found"] is True
    assert probe_pre_execution["single_use_enforced"] is True
    assert probe_pre_execution["exact_action_binding_verified"] is True
    assert probe_pre_execution["runner_identity_declared"] is True
    assert probe_pre_execution["runner_identity_bound"] is False
    assert probe_pre_execution["runner_policy_declared"] is True
    assert probe_pre_execution["runner_policy_bound"] is False
    assert probe_pre_execution["sandbox_policy_declared"] is True
    assert probe_pre_execution["sandbox_policy_bound"] is False
    assert probe_pre_execution["sandbox_bound"] is False
    assert probe_pre_execution["sandbox_enforced"] is False
    assert probe_pre_execution["network_block_declared"] is True
    assert probe_pre_execution["network_block_bound"] is False
    assert probe_pre_execution["timeout_policy_declared"] is True
    assert probe_pre_execution["timeout_policy_bound"] is False
    assert probe_pre_execution["output_capture_declared"] is True
    assert probe_pre_execution["output_capture_bound"] is False
    assert probe_pre_execution["kill_switch_declared"] is True
    assert probe_pre_execution["kill_switch_bound"] is False
    assert probe_pre_execution["execution_receipt_writer_declared"] is True
    assert probe_pre_execution["execution_receipt_writer_bound"] is False
    assert probe_pre_execution["execution_authority"] is False
    assert probe_pre_execution["executed"] is False
    assert probe_pre_execution["provider_runtime_probe_performed"] is False
    assert probe_pre_execution["provider_binary_executed"] is False
    assert probe_pre_execution["service_query_performed"] is False
    assert probe_pre_execution["process_launched"] is False
    assert probe_pre_execution["container_launched"] is False
    assert probe_pre_execution["repo_code_executed"] is False
    assert probe_pre_execution["network_accessed"] is False
    assert probe_pre_execution["wrote_to_repo"] is False
    assert probe_pre_execution["execution_receipt_written"] is False
    assert "invocation_boundary_ready" in probe_pre_execution["missing_checks"]
    assert "runner_identity_bound" in probe_pre_execution["missing_checks"]
    assert "runner_policy_bound" in probe_pre_execution["missing_checks"]
    assert "sandbox_policy_bound" in probe_pre_execution["missing_checks"]
    assert "network_block_bound" in probe_pre_execution["missing_checks"]
    assert "execution_receipt_writer_bound" in probe_pre_execution["missing_checks"]
    assert (
        "provider_runtime_probe_runner_pre_execution_boundary_blocked_until_live_runner_controls_bound"
        in probe_pre_execution["blockers"]
    )
    assert (
        probe_pre_execution_result["execution"]["provider_runtime_probe_runner_pre_execution_boundary_recorded"] is True
    )
    assert (
        probe_pre_execution_result["execution"]["provider_runtime_probe_runner_pre_execution_boundary_ready"] is False
    )
    assert probe_pre_execution_result["execution"]["provider_runtime_probe_performed"] is False
    assert probe_pre_execution_result["execution"]["provider_binary_executed"] is False
    assert probe_pre_execution_result["execution"]["process_launched"] is False
    assert probe_pre_execution_result["execution"]["container_launched"] is False
    assert probe_pre_execution_result["execution"]["execution_receipt_written"] is False
    assert probe_pre_execution_result["execution"]["executed"] is False
    assert probe_pre_execution_result["receipt"]["operation"] == (
        "lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary"
    )
    assert probe_pre_execution_path.exists()
    assert Path(probe_pre_execution_result["receipt_path"]).exists()
    assert "super-secret-token-value" not in probe_pre_execution_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    probe_control_binding_result = service.preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.lab.runtime_probe_runner_control_binding",
    )
    probe_control_binding = probe_control_binding_result["sandbox_provider_runtime_probe_runner_control_binding"]
    probe_control_binding_path = Path(
        probe_control_binding_result["sandbox_provider_runtime_probe_runner_control_binding_path"]
    )

    assert probe_control_binding_result["ok"] is True
    assert probe_control_binding_result["status"] == "blocked"
    assert probe_control_binding["status"] == "blocked"
    assert probe_control_binding["binding_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_control_binding"
    assert probe_control_binding["binding_mode"] == "control_binding_preflight_only_no_provider_execution"
    assert (
        probe_control_binding["control_binding_mode"] == "future_sandbox_provider_runtime_probe_runner_control_binding"
    )
    assert probe_control_binding["approval_id"] == provider_probe_approval_id
    assert probe_control_binding["approval_consumption_id"] == probe_consumption["id"]
    assert probe_control_binding["invocation_boundary_id"] == probe_invocation["id"]
    assert probe_control_binding["pre_execution_boundary_id"] == probe_pre_execution["id"]
    assert (
        probe_control_binding["permission_scope"] == "ingest.lab.sandbox.provider_runtime_probe.runner_control_binding"
    )
    assert probe_control_binding["pre_execution_boundary_found"] is True
    assert probe_control_binding["pre_execution_boundary_recorded"] is True
    assert probe_control_binding["pre_execution_boundary_ready"] is False
    assert probe_control_binding["approval_consumed"] is True
    assert probe_control_binding["single_use_consumption_found"] is True
    assert probe_control_binding["single_use_enforced"] is True
    assert probe_control_binding["exact_action_binding_verified"] is True
    assert probe_control_binding["control_binding_recorded"] is True
    assert probe_control_binding["runner_identity_declared"] is True
    assert probe_control_binding["runner_identity_binding_recorded"] is True
    assert probe_control_binding["runner_identity_bound"] is False
    assert probe_control_binding["runner_policy_declared"] is True
    assert probe_control_binding["runner_policy_binding_recorded"] is True
    assert probe_control_binding["runner_policy_bound"] is False
    assert probe_control_binding["sandbox_policy_declared"] is True
    assert probe_control_binding["sandbox_policy_binding_recorded"] is True
    assert probe_control_binding["sandbox_policy_bound"] is False
    assert probe_control_binding["sandbox_bound"] is False
    assert probe_control_binding["sandbox_enforced"] is False
    assert probe_control_binding["network_block_declared"] is True
    assert probe_control_binding["network_block_binding_recorded"] is True
    assert probe_control_binding["network_block_bound"] is False
    assert probe_control_binding["timeout_policy_binding_recorded"] is True
    assert probe_control_binding["timeout_policy_bound"] is False
    assert probe_control_binding["output_capture_binding_recorded"] is True
    assert probe_control_binding["output_capture_bound"] is False
    assert probe_control_binding["kill_switch_binding_recorded"] is True
    assert probe_control_binding["kill_switch_bound"] is False
    assert probe_control_binding["execution_receipt_writer_binding_recorded"] is True
    assert probe_control_binding["execution_receipt_writer_bound"] is False
    assert probe_control_binding["execution_authority"] is False
    assert probe_control_binding["executed"] is False
    assert probe_control_binding["provider_runtime_probe_performed"] is False
    assert probe_control_binding["provider_binary_executed"] is False
    assert probe_control_binding["service_query_performed"] is False
    assert probe_control_binding["process_launched"] is False
    assert probe_control_binding["container_launched"] is False
    assert probe_control_binding["repo_code_executed"] is False
    assert probe_control_binding["network_accessed"] is False
    assert probe_control_binding["wrote_to_repo"] is False
    assert probe_control_binding["execution_receipt_written"] is False
    assert "pre_execution_boundary_ready" in probe_control_binding["missing_checks"]
    assert "runner_identity_bound" in probe_control_binding["missing_checks"]
    assert "runner_policy_bound" in probe_control_binding["missing_checks"]
    assert "sandbox_policy_bound" in probe_control_binding["missing_checks"]
    assert "network_block_bound" in probe_control_binding["missing_checks"]
    assert "execution_receipt_writer_bound" in probe_control_binding["missing_checks"]
    assert (
        "provider_runtime_probe_runner_control_binding_blocked_until_live_runner_enforced"
        in probe_control_binding["blockers"]
    )
    assert probe_control_binding_result["execution"]["provider_runtime_probe_runner_control_binding_recorded"] is True
    assert probe_control_binding_result["execution"]["provider_runtime_probe_runner_control_binding_ready"] is False
    assert probe_control_binding_result["execution"]["provider_runtime_probe_performed"] is False
    assert probe_control_binding_result["execution"]["provider_binary_executed"] is False
    assert probe_control_binding_result["execution"]["process_launched"] is False
    assert probe_control_binding_result["execution"]["container_launched"] is False
    assert probe_control_binding_result["execution"]["execution_receipt_written"] is False
    assert probe_control_binding_result["execution"]["executed"] is False
    assert probe_control_binding_result["receipt"]["operation"] == (
        "lab.sandbox.provider_runtime_probe.runner_control_binding"
    )
    assert probe_control_binding_path.exists()
    assert Path(probe_control_binding_result["receipt_path"]).exists()
    assert "super-secret-token-value" not in probe_control_binding_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    sandboxed_boundary_result = service.preflight_lab_sandboxed_rebuild_run_test_boundary(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.lab.sandboxed_rebuild_run_test_boundary",
    )
    sandboxed_boundary = sandboxed_boundary_result["sandboxed_rebuild_run_test_boundary"]
    sandboxed_boundary_path = Path(sandboxed_boundary_result["sandboxed_rebuild_run_test_boundary_path"])

    assert sandboxed_boundary_result["ok"] is True
    assert sandboxed_boundary_result["status"] == "blocked"
    assert sandboxed_boundary["status"] == "blocked"
    assert sandboxed_boundary["boundary_kind"] == "francis.lab.sandboxed_rebuild_run_test_boundary"
    assert sandboxed_boundary["boundary_mode"] == "sandboxed_rebuild_run_test_boundary_no_execution"
    assert sandboxed_boundary["run_mode"] == "future_sandboxed_rebuild_run_test"
    assert sandboxed_boundary["approval_id"] == provider_probe_approval_id
    assert sandboxed_boundary["control_binding_id"] == probe_control_binding["id"]
    assert sandboxed_boundary["pre_execution_boundary_id"] == probe_pre_execution["id"]
    assert sandboxed_boundary["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.boundary"
    assert sandboxed_boundary["control_binding_found"] is True
    assert sandboxed_boundary["control_binding_recorded"] is True
    assert sandboxed_boundary["control_binding_ready"] is False
    assert sandboxed_boundary["approval_consumed"] is True
    assert sandboxed_boundary["execution_approval_required"] is True
    assert sandboxed_boundary["execution_approval_consumed"] is False
    assert sandboxed_boundary["runner_identity_bound"] is False
    assert sandboxed_boundary["runner_policy_bound"] is False
    assert sandboxed_boundary["sandbox_policy_bound"] is False
    assert sandboxed_boundary["sandbox_bound"] is False
    assert sandboxed_boundary["sandbox_enforced"] is False
    assert sandboxed_boundary["network_block_bound"] is False
    assert sandboxed_boundary["timeout_policy_bound"] is False
    assert sandboxed_boundary["output_capture_bound"] is False
    assert sandboxed_boundary["kill_switch_bound"] is False
    assert sandboxed_boundary["execution_receipt_writer_bound"] is False
    assert sandboxed_boundary["rebuild_declared"] is True
    assert sandboxed_boundary["run_declared"] is True
    assert sandboxed_boundary["test_declared"] is True
    assert sandboxed_boundary["execution_authority"] is False
    assert sandboxed_boundary["executed"] is False
    assert sandboxed_boundary["process_launched"] is False
    assert sandboxed_boundary["container_launched"] is False
    assert sandboxed_boundary["commands_executed"] is False
    assert sandboxed_boundary["repo_code_executed"] is False
    assert sandboxed_boundary["ran_install"] is False
    assert sandboxed_boundary["ran_build"] is False
    assert sandboxed_boundary["ran_tests"] is False
    assert sandboxed_boundary["network_accessed"] is False
    assert sandboxed_boundary["wrote_to_repo"] is False
    assert sandboxed_boundary["execution_receipt_written"] is False
    assert sandboxed_boundary["candidate_validated"] is False
    assert sandboxed_boundary["capability_promoted"] is False
    assert "control_binding_ready" in sandboxed_boundary["missing_checks"]
    assert "execution_approval_consumed" in sandboxed_boundary["missing_checks"]
    assert "runner_identity_bound" in sandboxed_boundary["missing_checks"]
    assert "sandbox_enforced" in sandboxed_boundary["missing_checks"]
    assert "execution_receipt_writer_bound" in sandboxed_boundary["missing_checks"]
    assert "sandboxed_rebuild_run_test_boundary_blocked_until_live_runner_enforced" in sandboxed_boundary["blockers"]
    assert sandboxed_boundary_result["execution"]["sandboxed_rebuild_run_test_boundary_recorded"] is True
    assert sandboxed_boundary_result["execution"]["sandboxed_rebuild_run_test_boundary_ready"] is False
    assert sandboxed_boundary_result["execution"]["execution_approval_required"] is True
    assert sandboxed_boundary_result["execution"]["execution_approval_consumed"] is False
    assert sandboxed_boundary_result["execution"]["ran_install"] is False
    assert sandboxed_boundary_result["execution"]["ran_build"] is False
    assert sandboxed_boundary_result["execution"]["ran_tests"] is False
    assert sandboxed_boundary_result["execution"]["repo_code_executed"] is False
    assert sandboxed_boundary_result["execution"]["executed"] is False
    assert sandboxed_boundary_result["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.boundary"
    assert sandboxed_boundary_path.exists()
    assert Path(sandboxed_boundary_result["receipt_path"]).exists()
    assert "super-secret-token-value" not in sandboxed_boundary_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    sandboxed_approval_result = service.request_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.lab.sandboxed_rebuild_run_test_approval_request",
    )
    sandboxed_approval_request = sandboxed_approval_result["sandboxed_rebuild_run_test_approval_request"]
    sandboxed_approval_path = Path(sandboxed_approval_result["sandboxed_rebuild_run_test_approval_request_path"])
    pending_sandboxed_approval_path = Path(sandboxed_approval_result["approval_path"])

    assert sandboxed_approval_result["ok"] is True
    assert sandboxed_approval_result["status"] == "needs_approval"
    assert sandboxed_approval_request["status"] == "needs_approval"
    assert sandboxed_approval_request["action"] == "francis.lab.sandboxed_rebuild_run_test"
    assert sandboxed_approval_request["approval_created"] is True
    assert sandboxed_approval_request["approval_id"] == sandboxed_approval_result["approval"]["id"]
    assert sandboxed_approval_request["upstream_approval_id"] == provider_probe_approval_id
    assert sandboxed_approval_request["sandboxed_boundary_id"] == sandboxed_boundary["id"]
    assert sandboxed_approval_request["control_binding_id"] == probe_control_binding["id"]
    assert sandboxed_approval_request["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.request_approval"
    assert sandboxed_approval_request["approval_consumed"] is False
    assert sandboxed_approval_request["upstream_approval_consumed"] is False
    assert sandboxed_approval_request["boundary_recorded"] is True
    assert sandboxed_approval_request["boundary_ready"] is False
    assert sandboxed_approval_request["execution_authority"] is False
    assert sandboxed_approval_request["executed"] is False
    assert sandboxed_approval_request["process_launched"] is False
    assert sandboxed_approval_request["container_launched"] is False
    assert sandboxed_approval_request["commands_executed"] is False
    assert sandboxed_approval_request["repo_code_executed"] is False
    assert sandboxed_approval_request["ran_install"] is False
    assert sandboxed_approval_request["ran_build"] is False
    assert sandboxed_approval_request["ran_tests"] is False
    assert sandboxed_approval_request["network_accessed"] is False
    assert sandboxed_approval_request["wrote_to_repo"] is False
    assert sandboxed_approval_request["execution_receipt_written"] is False
    assert sandboxed_approval_request["candidate_validated"] is False
    assert sandboxed_approval_request["capability_promoted"] is False
    assert "sandboxed_rebuild_run_test_requires_operator_execution_approval" in sandboxed_approval_request["blockers"]
    assert sandboxed_approval_result["execution"]["approval_request_created"] is True
    assert sandboxed_approval_result["execution"]["sandboxed_rebuild_run_test_approval_consumed"] is False
    assert sandboxed_approval_result["execution"]["ran_install"] is False
    assert sandboxed_approval_result["execution"]["ran_build"] is False
    assert sandboxed_approval_result["execution"]["ran_tests"] is False
    assert sandboxed_approval_result["execution"]["repo_code_executed"] is False
    assert sandboxed_approval_result["execution"]["executed"] is False
    assert sandboxed_approval_result["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.approval_request"
    assert sandboxed_approval_path.exists()
    assert pending_sandboxed_approval_path.exists()
    assert Path(sandboxed_approval_result["receipt_path"]).exists()
    assert "super-secret-token-value" not in sandboxed_approval_path.read_text(encoding="utf-8")
    assert "super-secret-token-value" not in pending_sandboxed_approval_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    sandboxed_approval_id = sandboxed_approval_request["approval_id"]
    approvals.decide(sandboxed_approval_id, "approve", actor="test.operator")
    sandboxed_consumption_result = service.consume_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.lab.sandboxed_rebuild_run_test_approval_consume",
    )
    sandboxed_consumption = sandboxed_consumption_result["sandboxed_rebuild_run_test_approval_consumption"]
    sandboxed_consumption_path = Path(
        sandboxed_consumption_result["sandboxed_rebuild_run_test_approval_consumption_path"]
    )

    assert sandboxed_consumption_result["ok"] is True
    assert sandboxed_consumption_result["status"] == "consumed"
    assert sandboxed_consumption["status"] == "consumed"
    assert sandboxed_consumption["action"] == "francis.lab.sandboxed_rebuild_run_test"
    assert sandboxed_consumption["approval_id"] == sandboxed_approval_id
    assert sandboxed_consumption["approval_request_id"] == sandboxed_approval_request["id"]
    assert sandboxed_consumption["upstream_approval_id"] == provider_probe_approval_id
    assert sandboxed_consumption["upstream_approval_consumption_id"] == probe_consumption["id"]
    assert sandboxed_consumption["sandboxed_boundary_id"] == sandboxed_boundary["id"]
    assert sandboxed_consumption["control_binding_id"] == probe_control_binding["id"]
    assert sandboxed_consumption["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.consume_approval"
    assert sandboxed_consumption["approval_status"] == "approved"
    assert sandboxed_consumption["approval_consumed"] is True
    assert sandboxed_consumption["single_use_enforced"] is True
    assert sandboxed_consumption["upstream_approval_consumed"] is False
    assert sandboxed_consumption["boundary_recorded"] is True
    assert sandboxed_consumption["boundary_ready"] is False
    assert sandboxed_consumption["execution_authority"] is False
    assert sandboxed_consumption["executed"] is False
    assert sandboxed_consumption["process_launched"] is False
    assert sandboxed_consumption["container_launched"] is False
    assert sandboxed_consumption["commands_executed"] is False
    assert sandboxed_consumption["repo_code_executed"] is False
    assert sandboxed_consumption["ran_install"] is False
    assert sandboxed_consumption["ran_build"] is False
    assert sandboxed_consumption["ran_tests"] is False
    assert sandboxed_consumption["network_accessed"] is False
    assert sandboxed_consumption["wrote_to_repo"] is False
    assert sandboxed_consumption["execution_receipt_written"] is False
    assert sandboxed_consumption["candidate_validated"] is False
    assert sandboxed_consumption["capability_promoted"] is False
    assert sandboxed_consumption["approval_binding"]["exact_match"] is True
    assert sandboxed_consumption_result["execution"]["sandboxed_rebuild_run_test_approval_consumed"] is True
    assert sandboxed_consumption_result["execution"]["execution_approval_consumed"] is True
    assert sandboxed_consumption_result["execution"]["ran_install"] is False
    assert sandboxed_consumption_result["execution"]["ran_build"] is False
    assert sandboxed_consumption_result["execution"]["ran_tests"] is False
    assert sandboxed_consumption_result["execution"]["repo_code_executed"] is False
    assert sandboxed_consumption_result["execution"]["executed"] is False
    assert sandboxed_consumption_result["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.approval.consume"
    assert sandboxed_consumption_path.exists()
    assert Path(sandboxed_consumption_result["receipt_path"]).exists()
    assert "super-secret-token-value" not in sandboxed_consumption_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    sandbox_runner_provider = tmp_path / "sandbox-runner"
    sandbox_runner_provider.write_text("metadata only sandbox runner reference\n", encoding="utf-8")
    sandbox_runner_policy = tmp_path / "sandbox-runner-policy.json"
    sandbox_runner_policy.write_text(
        json.dumps({"network": False, "execution": False, "secret_token": "super-secret-token-value"}),
        encoding="utf-8",
    )
    sandbox_runner_result = service.preflight_lab_sandboxed_rebuild_run_test_runner_binding(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        provider_kind="local_process_sandbox",
        provider_reference=str(sandbox_runner_provider),
        provider_policy_manifest=str(sandbox_runner_policy),
        actor="test.lab.sandboxed_rebuild_run_test_runner_binding",
    )
    sandbox_runner_binding = sandbox_runner_result["sandboxed_rebuild_run_test_runner_binding"]
    sandbox_runner_path = Path(sandbox_runner_result["sandboxed_rebuild_run_test_runner_binding_path"])

    assert sandbox_runner_result["ok"] is True
    assert sandbox_runner_result["status"] == "blocked"
    assert sandbox_runner_binding["status"] == "blocked"
    assert sandbox_runner_binding["approval_id"] == sandboxed_approval_id
    assert sandbox_runner_binding["approval_consumption_id"] == sandboxed_consumption["id"]
    assert sandbox_runner_binding["approval_request_id"] == sandboxed_approval_request["id"]
    assert sandbox_runner_binding["sandboxed_boundary_id"] == sandboxed_boundary["id"]
    assert sandbox_runner_binding["control_binding_id"] == probe_control_binding["id"]
    assert sandbox_runner_binding["source_id"] == source["id"]
    assert sandbox_runner_binding["candidate_name"] == "run_project_tests"
    assert sandbox_runner_binding["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.runner_binding"
    assert sandbox_runner_binding["binding_kind"] == "sandboxed_rebuild_run_test_runner_binding_preflight"
    assert sandbox_runner_binding["binding_mode"] == "static_provider_reference_only_no_live_runner"
    assert sandbox_runner_binding["provider_kind"] == "local_process_sandbox"
    assert sandbox_runner_binding["selected_provider_kind"] == "local_process_sandbox"
    assert sandbox_runner_binding["approval_consumed"] is True
    assert sandbox_runner_binding["single_use_enforced"] is True
    assert sandbox_runner_binding["static_provider_reference_bound"] is True
    assert sandbox_runner_binding["provider_reference_checked"] is True
    assert sandbox_runner_binding["provider_reference_present"] is True
    assert sandbox_runner_binding["provider_reference_verified"] is True
    assert sandbox_runner_binding["provider_policy_manifest_present"] is True
    assert sandbox_runner_binding["provider_policy_manifest_bound"] is True
    assert sandbox_runner_binding["runner_binding_declared"] is True
    assert sandbox_runner_binding["live_runner_bound"] is False
    assert sandbox_runner_binding["sandbox_runner_bound"] is False
    assert sandbox_runner_binding["sandbox_bound"] is False
    assert sandbox_runner_binding["sandbox_enforced"] is False
    assert sandbox_runner_binding["provider_binary_executed"] is False
    assert sandbox_runner_binding["provider_service_queried"] is False
    assert sandbox_runner_binding["execution_authority"] is False
    assert sandbox_runner_binding["executed"] is False
    assert sandbox_runner_binding["process_launched"] is False
    assert sandbox_runner_binding["container_launched"] is False
    assert sandbox_runner_binding["commands_executed"] is False
    assert sandbox_runner_binding["repo_code_executed"] is False
    assert sandbox_runner_binding["ran_install"] is False
    assert sandbox_runner_binding["ran_build"] is False
    assert sandbox_runner_binding["ran_tests"] is False
    assert sandbox_runner_binding["network_accessed"] is False
    assert sandbox_runner_binding["wrote_to_repo"] is False
    assert sandbox_runner_binding["execution_receipt_written"] is False
    assert sandbox_runner_binding["candidate_validated"] is False
    assert sandbox_runner_binding["capability_promoted"] is False
    assert "live_runner_bound" in sandbox_runner_binding["missing_checks"]
    assert "sandbox_runner_bound" in sandbox_runner_binding["missing_checks"]
    assert "sandbox_enforced" in sandbox_runner_binding["missing_checks"]
    assert "execution_receipt_writer_bound" in sandbox_runner_binding["missing_checks"]
    assert "live_sandbox_runner_not_bound" in sandbox_runner_binding["blockers"]
    assert sandbox_runner_result["execution"]["sandboxed_rebuild_run_test_runner_binding_recorded"] is True
    assert sandbox_runner_result["execution"]["static_provider_reference_bound"] is True
    assert sandbox_runner_result["execution"]["live_runner_bound"] is False
    assert sandbox_runner_result["execution"]["sandbox_enforced"] is False
    assert sandbox_runner_result["execution"]["ran_build"] is False
    assert sandbox_runner_result["execution"]["ran_tests"] is False
    assert sandbox_runner_result["execution"]["repo_code_executed"] is False
    assert sandbox_runner_result["execution"]["executed"] is False
    assert sandbox_runner_result["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.runner_binding"
    assert sandbox_runner_path.exists()
    assert Path(sandbox_runner_result["receipt_path"]).exists()
    assert "super-secret-token-value" not in sandbox_runner_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    sandbox_policy_result = service.preflight_lab_sandboxed_rebuild_run_test_sandbox_policy(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.lab.sandboxed_rebuild_run_test_sandbox_policy",
    )
    sandbox_policy = sandbox_policy_result["sandboxed_rebuild_run_test_sandbox_policy"]
    sandbox_policy_path = Path(sandbox_policy_result["sandboxed_rebuild_run_test_sandbox_policy_path"])

    assert sandbox_policy_result["ok"] is True
    assert sandbox_policy_result["status"] == "blocked"
    assert sandbox_policy["status"] == "blocked"
    assert sandbox_policy["approval_id"] == sandboxed_approval_id
    assert sandbox_policy["approval_consumption_id"] == sandboxed_consumption["id"]
    assert sandbox_policy["runner_binding_id"] == sandbox_runner_binding["id"]
    assert sandbox_policy["approval_request_id"] == sandboxed_approval_request["id"]
    assert sandbox_policy["sandboxed_boundary_id"] == sandboxed_boundary["id"]
    assert sandbox_policy["control_binding_id"] == probe_control_binding["id"]
    assert sandbox_policy["source_id"] == source["id"]
    assert sandbox_policy["candidate_name"] == "run_project_tests"
    assert sandbox_policy["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.sandbox_policy"
    assert sandbox_policy["policy_kind"] == "sandboxed_rebuild_run_test_sandbox_policy_preflight"
    assert sandbox_policy["policy_mode"] == "policy_preflight_no_live_sandbox"
    assert sandbox_policy["approval_consumed"] is True
    assert sandbox_policy["single_use_enforced"] is True
    assert sandbox_policy["runner_binding_present"] is True
    assert sandbox_policy["static_provider_reference_bound"] is True
    assert sandbox_policy["provider_kind_selected"] is True
    assert sandbox_policy["sandbox_policy_declared"] is True
    assert sandbox_policy["network_default_deny"] is True
    assert sandbox_policy["network_allowed"] is False
    assert sandbox_policy["repo_write_allowed"] is False
    assert sandbox_policy["destructive_allowed"] is False
    assert sandbox_policy["secret_storage_allowed"] is False
    assert sandbox_policy["source_read_only_reference"] is True
    assert sandbox_policy["command_execution_enabled"] is False
    assert sandbox_policy["command_allowlist_bound"] is False
    assert sandbox_policy["execution_receipt_writer_bound"] is False
    assert sandbox_policy["live_sandbox_bound"] is False
    assert sandbox_policy["sandbox_enforced"] is False
    assert sandbox_policy["process_launch_allowed"] is False
    assert sandbox_policy["container_launch_allowed"] is False
    assert sandbox_policy["provider_binary_execution_allowed"] is False
    assert sandbox_policy["provider_service_query_allowed"] is False
    assert sandbox_policy["timeout_policy_bound"] is False
    assert sandbox_policy["output_capture_bound"] is False
    assert sandbox_policy["kill_switch_bound"] is False
    assert sandbox_policy["execution_authority"] is False
    assert sandbox_policy["executed"] is False
    assert sandbox_policy["process_launched"] is False
    assert sandbox_policy["container_launched"] is False
    assert sandbox_policy["commands_executed"] is False
    assert sandbox_policy["repo_code_executed"] is False
    assert sandbox_policy["ran_install"] is False
    assert sandbox_policy["ran_build"] is False
    assert sandbox_policy["ran_tests"] is False
    assert sandbox_policy["network_accessed"] is False
    assert sandbox_policy["wrote_to_repo"] is False
    assert sandbox_policy["execution_receipt_written"] is False
    assert sandbox_policy["candidate_validated"] is False
    assert sandbox_policy["capability_promoted"] is False
    assert sandbox_policy["sandbox_policy"]["network_policy"]["default"] == "deny"
    assert sandbox_policy["sandbox_policy"]["filesystem_policy"]["source_mount"] == "read_only_reference"
    assert sandbox_policy["sandbox_policy"]["command_policy"]["command_execution_enabled"] is False
    assert "command_allowlist_bound" in sandbox_policy["missing_checks"]
    assert "execution_receipt_writer_bound" in sandbox_policy["missing_checks"]
    assert "live_sandbox_bound" in sandbox_policy["missing_checks"]
    assert "sandbox_enforced" in sandbox_policy["missing_checks"]
    assert "sandboxed_rebuild_run_test_sandbox_policy_preflight_only" in sandbox_policy["blockers"]
    assert sandbox_policy_result["execution"]["sandboxed_rebuild_run_test_sandbox_policy_recorded"] is True
    assert sandbox_policy_result["execution"]["sandbox_policy_declared"] is True
    assert sandbox_policy_result["execution"]["network_default_deny"] is True
    assert sandbox_policy_result["execution"]["repo_write_allowed"] is False
    assert sandbox_policy_result["execution"]["command_execution_enabled"] is False
    assert sandbox_policy_result["execution"]["live_sandbox_bound"] is False
    assert sandbox_policy_result["execution"]["sandbox_enforced"] is False
    assert sandbox_policy_result["execution"]["ran_build"] is False
    assert sandbox_policy_result["execution"]["ran_tests"] is False
    assert sandbox_policy_result["execution"]["repo_code_executed"] is False
    assert sandbox_policy_result["execution"]["executed"] is False
    assert sandbox_policy_result["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.sandbox_policy"
    assert sandbox_policy_path.exists()
    assert Path(sandbox_policy_result["receipt_path"]).exists()
    assert "super-secret-token-value" not in sandbox_policy_path.read_text(encoding="utf-8")
    assert not (repo / "lab-ran.txt").exists()

    sandboxed_reuse = service.consume_lab_sandboxed_rebuild_run_test_approval(
        source["id"],
        "run_project_tests",
        sandboxed_approval_id,
        actor="test.lab.sandboxed_rebuild_run_test_approval_consume",
    )

    assert sandboxed_reuse["ok"] is False
    assert sandboxed_reuse["status"] == "refused"
    assert sandboxed_reuse["approval_binding"]["approval_consumed"] is True
    assert (
        sandboxed_reuse["approval_binding"]["sandboxed_rebuild_run_test_approval_consumption_record_id"]
        == sandboxed_consumption["id"]
    )
    assert "sandboxed_rebuild_run_test_approval_already_consumed" in sandboxed_reuse["blockers"]
    assert sandboxed_reuse["execution"]["ran_build"] is False
    assert sandboxed_reuse["execution"]["ran_tests"] is False
    assert sandboxed_reuse["execution"]["executed"] is False
    assert not (repo / "lab-ran.txt").exists()

    probe_reuse = service.consume_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        provider_probe_approval_id,
        actor="test.lab.runtime_probe_approval_consume",
    )

    assert probe_reuse["ok"] is False
    assert probe_reuse["status"] == "refused"
    assert probe_reuse["approval_binding"]["approval_consumed"] is True
    assert (
        probe_reuse["approval_binding"]["provider_runtime_probe_approval_consumption_record_id"]
        == probe_consumption["id"]
    )
    assert "provider_runtime_probe_approval_already_consumed" in probe_reuse["blockers"]
    assert probe_reuse["execution"]["provider_runtime_probe_performed"] is False
    assert probe_reuse["execution"]["executed"] is False
    assert not (repo / "lab-ran.txt").exists()

    repeat_identity = service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )

    assert repeat_identity["ok"] is False
    assert repeat_identity["status"] == "blocked"
    assert repeat_identity["prior_noop_runner_identity_binding_path"] == str(identity_path)
    assert "noop_runner_identity_not_already_completed" in repeat_identity["blockers"]
    assert identity_path.exists()
    assert (
        json.loads(identity_path.read_text(encoding="utf-8"))["noop_runner_identity_binding"]["status"] == "completed"
    )
    assert not (repo / "lab-ran.txt").exists()

    repeat = service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )

    assert repeat["ok"] is False
    assert repeat["status"] == "blocked"
    assert repeat["prior_noop_runner_envelope_path"] == str(envelope_path)
    assert "noop_runner_envelope_not_already_completed" in repeat["blockers"]
    assert envelope_path.exists()
    assert json.loads(envelope_path.read_text(encoding="utf-8"))["noop_runner_envelope"]["status"] == "completed"
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_runner_readiness_outputs_blocked_controls_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]

    rc = main(
        [
            "lab",
            "runner-readiness",
            source["id"],
            "run_project_tests",
            "--approval-id",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert payload["runner_readiness"]["execution_authority"] is False
    assert payload["runner_readiness"]["executed"] is False
    assert "governed_runner_bound" in payload["runner_readiness"]["missing_controls"]
    assert payload["approval_binding"]["approval_consumed"] is False
    assert payload["execution"]["executed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_runner_binding_outputs_blocked_receipt_sink_contract_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]

    rc = main(
        [
            "lab",
            "runner-binding",
            source["id"],
            "run_project_tests",
            "--approval-id",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert payload["runner_binding"]["runner_binding"]["runner_bound"] is False
    assert payload["runner_binding"]["execution_receipt_sink"]["bound"] is False
    assert payload["runner_binding"]["approval_consumed"] is False
    assert payload["runner_binding"]["execution_authority"] is False
    assert "governed_runner_bound" in payload["runner_binding"]["missing_controls"]
    assert "execution_receipt_sink_bound" in payload["runner_binding"]["missing_controls"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_runner_enforcement_outputs_blocked_checks_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]

    rc = main(
        [
            "lab",
            "runner-enforcement",
            source["id"],
            "run_project_tests",
            "--approval-id",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert payload["runner_enforcement"]["runner_bound"] is False
    assert payload["runner_enforcement"]["receipt_sink_bound"] is False
    assert payload["runner_enforcement"]["execution_authority"] is False
    assert "runner_identity_verified" in payload["runner_enforcement"]["missing_checks"]
    assert "execution_receipt_prewrite_bound" in payload["runner_enforcement"]["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_approval_consumption_handoff_outputs_blocked_without_consuming_or_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "approval-consumption-handoff",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert payload["approval_consumption_handoff"]["approval_status"] == "approved"
    assert payload["approval_consumption_handoff"]["approval_consumed"] is False
    assert payload["approval_consumption_handoff"]["execution_authority"] is False
    assert payload["approval_consumption_handoff"]["current_checks"]["approval_approved"] is True
    assert payload["approval_consumption_handoff"]["current_checks"]["runner_enforcement_ready"] is False
    assert "approval_consumption_not_disabled" in payload["approval_consumption_handoff"]["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_execution_receipt_sink_reservation_outputs_blocked_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "execution-receipt-sink-reservation",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    reservation = payload["execution_receipt_sink_reservation"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert reservation["current_checks"]["reserved_receipt_id_created"] is True
    assert reservation["execution_receipt_written"] is False
    assert reservation["prewrite_bound"] is False
    assert reservation["final_write_bound"] is False
    assert reservation["approval_consumed"] is False
    assert reservation["execution_authority"] is False
    assert "execution_receipt_prewrite_bound" in reservation["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_runner_command_allowlist_binding_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "runner-command-allowlist-binding",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    command_allowlist = payload["runner_command_allowlist"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert command_allowlist["command_plan"]["command_count"] >= 1
    assert command_allowlist["allowlist_declared"] is False
    assert command_allowlist["allowlist_bound"] is False
    assert command_allowlist["command_execution_enabled"] is False
    assert command_allowlist["approval_consumed"] is False
    assert command_allowlist["execution_authority"] is False
    assert "command_allowlist_bound" in command_allowlist["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_runner_command_allowlist_declaration_outputs_declared_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "runner-command-allowlist-declaration",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    declaration = payload["runner_command_allowlist_declaration"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert declaration["allowlist_declaration"]["entry_count"] >= 1
    assert declaration["allowlist_declared"] is True
    assert declaration["allowlist_bound"] is False
    assert declaration["command_execution_enabled"] is False
    assert declaration["approval_consumed"] is False
    assert declaration["execution_authority"] is False
    assert "command_allowlist_bound" in declaration["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_runner_command_allowlist_enforcement_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "runner-command-allowlist-enforcement",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    enforcement = payload["runner_command_allowlist_enforcement"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert enforcement["enforcement_projection"]["entry_count"] >= 1
    assert enforcement["allowlist_declared"] is True
    assert enforcement["allowlist_bound"] is False
    assert enforcement["allowlist_enforced"] is False
    assert enforcement["command_execution_enabled"] is False
    assert enforcement["approval_consumed"] is False
    assert enforcement["execution_authority"] is False
    assert "command_allowlist_enforced" in enforcement["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_runner_sandbox_readiness_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "runner-sandbox-readiness",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    readiness = payload["runner_sandbox_readiness"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert readiness["sandbox_profile"]["manifest_present"] is True
    assert readiness["sandbox_bound"] is False
    assert readiness["sandbox_enforced"] is False
    assert readiness["runner_bound"] is False
    assert readiness["allowlist_enforced"] is False
    assert readiness["approval_consumed"] is False
    assert readiness["execution_authority"] is False
    assert "sandbox_provider_bound" in readiness["missing_checks"]
    assert "receipt_sink_prewrite_bound" in readiness["missing_checks"]
    assert "receipt_sink_final_write_bound" in readiness["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_contract_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-contract",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    contract = payload["sandbox_provider_contract"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert contract["contract_mode"] == "provider_contract_preflight_only_no_execution"
    assert contract["provider_contract_declared"] is True
    assert contract["sandbox_provider_bound"] is False
    assert contract["sandbox_bound"] is False
    assert contract["sandbox_enforced"] is False
    assert contract["execution_authority"] is False
    assert contract["executed"] is False
    assert "sandbox_provider_bound" in contract["missing_checks"]
    assert "sandbox_bound" in contract["missing_checks"]
    assert "sandbox_enforced" in contract["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_contract_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_binding_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-binding",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    binding = payload["sandbox_provider_binding"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert binding["binding_mode"] == "binding_preflight_only_no_execution"
    assert binding["provider_contract_declared"] is True
    assert binding["provider_kind_selected"] is False
    assert binding["provider_binary_or_service_verified"] is False
    assert binding["sandbox_provider_bound"] is False
    assert binding["sandbox_bound"] is False
    assert binding["sandbox_enforced"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert "provider_kind_selected" in binding["missing_checks"]
    assert "provider_binary_or_service_verified" in binding["missing_checks"]
    assert "sandbox_provider_bound" in binding["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_binding_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_selection_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-selection",
            source["id"],
            "run_project_tests",
            approval_id,
            "--provider-kind",
            "local_process_sandbox",
            "--provider-reference",
            str(provider_reference),
            "--provider-policy-manifest",
            str(policy_manifest),
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    selection = payload["sandbox_provider_selection"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert selection["selection_mode"] == "selection_verification_preflight_only_no_execution"
    assert selection["selected_provider_kind"] == "local_process_sandbox"
    assert selection["provider_reference_verified"] is True
    assert selection["provider_policy_manifest_bound"] is True
    assert selection["provider_binary_or_service_verified"] is False
    assert selection["sandbox_provider_bound"] is False
    assert selection["sandbox_bound"] is False
    assert selection["execution_authority"] is False
    assert selection["executed"] is False
    assert "provider_binary_or_service_verified" in selection["missing_checks"]
    assert "sandbox_provider_bound" in selection["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_selection_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_verifier_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-verifier",
            source["id"],
            "run_project_tests",
            approval_id,
            "--provider-kind",
            "local_process_sandbox",
            "--provider-reference",
            str(provider_reference),
            "--provider-policy-manifest",
            str(policy_manifest),
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    verifier = payload["sandbox_provider_verifier"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert verifier["verifier_mode"] == "static_identity_policy_verification_no_execution"
    assert verifier["verifier_contract_declared"] is True
    assert verifier["verifier_implementation_bound"] is True
    assert verifier["verifier_identity_bound"] is True
    assert verifier["provider_reference_verified"] is True
    assert verifier["provider_binary_or_service_verified"] is True
    assert verifier["provider_identity_fingerprint_captured"] is True
    assert verifier["provider_identity"]["provider_identity_fingerprint"].startswith("sha256:")
    assert verifier["provider_runtime_probe_performed"] is False
    assert verifier["service_query_performed"] is False
    assert verifier["process_launched"] is False
    assert verifier["container_launched"] is False
    assert verifier["sandbox_provider_bound"] is False
    assert verifier["execution_authority"] is False
    assert verifier["executed"] is False
    assert "verifier_implementation_bound" not in verifier["missing_checks"]
    assert "provider_binary_or_service_verified" not in verifier["missing_checks"]
    assert "provider_runtime_probe_performed" in verifier["missing_checks"]
    assert "sandbox_provider_bound" in verifier["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_verifier_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe",
            source["id"],
            "run_project_tests",
            approval_id,
            "--provider-kind",
            "local_process_sandbox",
            "--provider-reference",
            str(provider_reference),
            "--provider-policy-manifest",
            str(policy_manifest),
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    runtime_probe = payload["sandbox_provider_runtime_probe"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert runtime_probe["probe_mode"] == "runtime_probe_contract_preflight_only_no_provider_execution"
    assert runtime_probe["verifier_static_identity_ready"] is True
    assert runtime_probe["runtime_probe_contract_declared"] is True
    assert runtime_probe["runtime_probe_network_blocked_by_contract"] is True
    assert runtime_probe["provider_runtime_probe_performed"] is False
    assert runtime_probe["service_query_performed"] is False
    assert runtime_probe["process_launched"] is False
    assert runtime_probe["container_launched"] is False
    assert runtime_probe["execution_authority"] is False
    assert runtime_probe["executed"] is False
    assert "runtime_probe_runner_bound" in runtime_probe["missing_checks"]
    assert "provider_runtime_probe_performed" in runtime_probe["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_runtime_probe_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_harness_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-harness",
            source["id"],
            "run_project_tests",
            approval_id,
            "--provider-kind",
            "local_process_sandbox",
            "--provider-reference",
            str(provider_reference),
            "--provider-policy-manifest",
            str(policy_manifest),
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    harness = payload["sandbox_provider_runtime_probe_harness"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert harness["harness_mode"] == "runtime_probe_harness_preflight_only_no_provider_execution"
    assert harness["runtime_probe_runner_contract_declared"] is True
    assert harness["runtime_probe_sandbox_contract_declared"] is True
    assert harness["runtime_probe_service_query_guard_declared"] is True
    assert harness["runtime_probe_output_capture_declared"] is True
    assert harness["runtime_probe_kill_switch_declared"] is True
    assert harness["runtime_probe_runner_bound"] is False
    assert harness["runtime_probe_sandbox_bound"] is False
    assert harness["provider_runtime_probe_performed"] is False
    assert harness["service_query_performed"] is False
    assert harness["process_launched"] is False
    assert harness["container_launched"] is False
    assert harness["execution_authority"] is False
    assert harness["executed"] is False
    assert "runtime_probe_runner_bound" in harness["missing_checks"]
    assert "provider_runtime_probe_performed" in harness["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_runtime_probe_harness_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_runner_readiness_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-runner-readiness",
            source["id"],
            "run_project_tests",
            approval_id,
            "--provider-kind",
            "local_process_sandbox",
            "--provider-reference",
            str(provider_reference),
            "--provider-policy-manifest",
            str(policy_manifest),
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    readiness = payload["sandbox_provider_runtime_probe_runner_readiness"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert readiness["runner_mode"] == "probe_runner_interface_readiness_only_no_provider_execution"
    assert readiness["runtime_probe_harness_present"] is True
    assert readiness["runtime_probe_harness_contract_declared"] is True
    assert readiness["probe_runner_interface_declared"] is True
    assert readiness["probe_runner_implementation_bound"] is False
    assert readiness["probe_runner_identity_bound"] is False
    assert readiness["probe_runner_sandbox_bound"] is False
    assert readiness["provider_runtime_probe_performed"] is False
    assert readiness["service_query_performed"] is False
    assert readiness["process_launched"] is False
    assert readiness["container_launched"] is False
    assert readiness["execution_authority"] is False
    assert readiness["executed"] is False
    assert "probe_runner_interface_declared" not in readiness["missing_checks"]
    assert "probe_runner_implementation_bound" in readiness["missing_checks"]
    assert "probe_runner_sandbox_bound" in readiness["missing_checks"]
    assert "provider_runtime_probe_performed" in readiness["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_runtime_probe_runner_readiness_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_runner_binding_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-runner-binding",
            source["id"],
            "run_project_tests",
            approval_id,
            "--provider-kind",
            "local_process_sandbox",
            "--provider-reference",
            str(provider_reference),
            "--provider-policy-manifest",
            str(policy_manifest),
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    binding = payload["sandbox_provider_runtime_probe_runner_binding"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert binding["binding_mode"] == "probe_runner_binding_preflight_no_provider_execution"
    assert binding["runner_readiness_present"] is True
    assert binding["probe_runner_interface_declared"] is True
    assert binding["probe_runner_binding_contract_declared"] is True
    assert binding["probe_runner_readiness_ready"] is False
    assert binding["probe_runner_bound"] is False
    assert binding["runtime_probe_bound"] is False
    assert binding["provider_runtime_probe_performed"] is False
    assert binding["service_query_performed"] is False
    assert binding["process_launched"] is False
    assert binding["container_launched"] is False
    assert binding["execution_authority"] is False
    assert binding["executed"] is False
    assert "probe_runner_binding_contract_declared" not in binding["missing_checks"]
    assert "probe_runner_bound" in binding["missing_checks"]
    assert "runtime_probe_bound" in binding["missing_checks"]
    assert "provider_runtime_probe_performed" in binding["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_runtime_probe_runner_binding_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_runner_enforcement_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    provider_reference = tmp_path / "provider-bin"
    provider_reference.write_text("metadata only provider reference\n", encoding="utf-8")
    policy_manifest = tmp_path / "provider-policy.json"
    policy_manifest.write_text(
        '{"network": false, "execution": false, "provider_version": "0.1.0"}\n',
        encoding="utf-8",
    )
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-runner-enforcement",
            source["id"],
            "run_project_tests",
            approval_id,
            "--provider-kind",
            "local_process_sandbox",
            "--provider-reference",
            str(provider_reference),
            "--provider-policy-manifest",
            str(policy_manifest),
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    enforcement = payload["sandbox_provider_runtime_probe_runner_enforcement"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert enforcement["enforcement_mode"] == "probe_runner_enforcement_preflight_no_provider_execution"
    assert enforcement["runner_binding_present"] is True
    assert enforcement["probe_runner_binding_contract_declared"] is True
    assert enforcement["probe_runner_enforcement_contract_declared"] is True
    assert enforcement["probe_runner_binding_ready"] is False
    assert enforcement["probe_runner_enforcement_bound"] is False
    assert enforcement["probe_runner_bound"] is False
    assert enforcement["runtime_probe_bound"] is False
    assert enforcement["provider_runtime_probe_performed"] is False
    assert enforcement["service_query_performed"] is False
    assert enforcement["process_launched"] is False
    assert enforcement["container_launched"] is False
    assert enforcement["execution_authority"] is False
    assert enforcement["executed"] is False
    assert "probe_runner_enforcement_contract_declared" not in enforcement["missing_checks"]
    assert "probe_runner_enforcement_bound" in enforcement["missing_checks"]
    assert "runtime_probe_bound" in enforcement["missing_checks"]
    assert "provider_runtime_probe_performed" in enforcement["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["sandbox_provider_runtime_probe_runner_enforcement_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_execution_receipt_write_readiness_outputs_blocked_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "execution-receipt-write-readiness",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    readiness = payload["execution_receipt_write_readiness"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert readiness["reserved_execution_receipt"]["id"]
    assert readiness["prewrite_bound"] is False
    assert readiness["final_write_bound"] is False
    assert readiness["execution_receipt_prewritten"] is False
    assert readiness["execution_receipt_finalized"] is False
    assert readiness["approval_consumed"] is False
    assert readiness["execution_authority"] is False
    assert "receipt_prewrite_writer_bound" in readiness["missing_checks"]
    assert "receipt_final_writer_bound" in readiness["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_execution_receipt_prewrite_binding_outputs_contract_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "execution-receipt-prewrite-binding",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    binding = payload["execution_receipt_prewrite_binding"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert binding["receipt_schema_bound"] is True
    assert binding["prewrite_contract_bound"] is True
    assert binding["final_write_contract_bound"] is True
    assert binding["prewrite_writer_bound"] is False
    assert binding["final_write_writer_bound"] is False
    assert binding["execution_receipt_prewritten"] is False
    assert binding["execution_receipt_finalized"] is False
    assert binding["approval_consumed"] is False
    assert binding["execution_authority"] is False
    assert "prewrite_writer_bound" in binding["missing_checks"]
    assert "schema_contract_bound" not in binding["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_execution_receipt_writer_preflight_outputs_boundary_without_receipt_write(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "execution-receipt-writer-preflight",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    writer = payload["execution_receipt_writer_preflight"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert writer["writer_contract"]["mode"] == "writer_preflight_only_no_execution_receipt_write"
    assert writer["writer_boundary"]["reserved_path_within_sink"] is True
    assert writer["writer_boundary"]["reserved_receipt_not_written"] is True
    assert writer["writer_implementation_bound"] is False
    assert writer["prewrite_operation"]["performed"] is False
    assert writer["final_write_operation"]["performed"] is False
    assert writer["execution_receipt_prewritten"] is False
    assert writer["execution_receipt_finalized"] is False
    assert writer["approval_consumed"] is False
    assert writer["execution_authority"] is False
    assert "writer_implementation_bound" in writer["missing_checks"]
    assert "reserved_execution_receipt_path_within_sink" not in writer["missing_checks"]
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not Path(payload["reserved_execution_receipt"]["path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_synthetic_execution_receipt_prewrite_and_finalize_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")

    prewrite_rc = main(
        [
            "lab",
            "synthetic-execution-receipt-prewrite",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    prewrite_output = capsys.readouterr()
    prewrite_payload = json.loads(prewrite_output.out)
    prewritten = prewrite_payload["execution_receipt"]
    receipt_path = Path(prewrite_payload["execution_receipt_path"])

    assert prewrite_rc == 0
    assert prewrite_payload["ok"] is True
    assert prewrite_payload["status"] == "prewritten"
    assert prewritten["synthetic"] is True
    assert prewritten["noop"] is True
    assert prewritten["executed"] is False
    assert prewritten["approval_consumed"] is False
    assert prewrite_payload["execution"]["executed"] is False
    assert receipt_path.exists()
    assert not (repo / "lab-ran.txt").exists()

    finalize_rc = main(
        [
            "lab",
            "synthetic-execution-receipt-finalize",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    finalize_output = capsys.readouterr()
    finalize_payload = json.loads(finalize_output.out)
    finalized = finalize_payload["execution_receipt"]

    assert finalize_rc == 0
    assert finalize_payload["ok"] is True
    assert finalize_payload["status"] == "blocked"
    assert finalized["id"] == prewritten["id"]
    assert finalized["finalized"] is True
    assert finalized["executed"] is False
    assert finalized["approval_consumed"] is False
    assert finalize_payload["execution"]["network_accessed"] is False
    assert Path(finalize_payload["execution_receipt_path"]) == receipt_path
    assert receipt_path.exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_approval_consume_synthetic_noop_enforces_single_use_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )

    rc = main(
        [
            "lab",
            "approval-consume-synthetic-noop",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    record = payload["approval_consumption_record"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "consumed"
    assert record["approval_consumed"] is True
    assert record["single_use_enforced"] is True
    assert record["executed"] is False
    assert record["execution_authority"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.execution.approval.consume_synthetic_noop"
    assert Path(payload["approval_consumption_record_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert (data_root / "approvals" / "approved" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_noop_runner_envelope_completes_builtin_noop_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )

    rc = main(
        [
            "lab",
            "noop-runner-envelope",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    envelope = payload["noop_runner_envelope"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert envelope["noop_performed"] is True
    assert envelope["approval_consumed"] is True
    assert envelope["execution_authority"] is False
    assert envelope["executed"] is False
    assert envelope["commands_executed"] is False
    assert envelope["repo_code_executed"] is False
    assert payload["execution"]["builtin_noop_performed"] is True
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.runner.noop_envelope"
    assert Path(payload["noop_runner_envelope_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_noop_runner_transcript_records_empty_output_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )

    rc = main(
        [
            "lab",
            "noop-runner-transcript",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    transcript = payload["noop_runner_transcript"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert transcript["builtin_noop_output_captured"] is True
    assert transcript["real_process_output_captured"] is False
    assert transcript["stdout"]["bytes"] == 0
    assert transcript["stderr"]["bytes"] == 0
    assert transcript["output_content_stored"] is False
    assert transcript["execution_authority"] is False
    assert transcript["executed"] is False
    assert transcript["commands_executed"] is False
    assert transcript["repo_code_executed"] is False
    assert payload["execution"]["builtin_noop_output_captured"] is True
    assert payload["execution"]["real_process_output_captured"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.runner.noop_transcript"
    assert Path(payload["noop_runner_transcript_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_noop_runner_identity_binding_records_builtin_identity_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )

    rc = main(
        [
            "lab",
            "noop-runner-identity-binding",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    identity = payload["noop_runner_identity_binding"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert identity["runner_id"] == "francis.lab.runner.builtin_noop.v0"
    assert identity["runner_identity_bound"] is True
    assert identity["builtin_noop_only"] is True
    assert identity["live_runner_bound"] is False
    assert identity["sandbox_runner_bound"] is False
    assert identity["execution_authority"] is False
    assert identity["executed"] is False
    assert identity["commands_executed"] is False
    assert identity["repo_code_executed"] is False
    assert identity["candidate_validated"] is False
    assert identity["capability_promoted"] is False
    assert payload["execution"]["builtin_noop_runner_identity_bound"] is True
    assert payload["execution"]["live_runner_bound"] is False
    assert payload["execution"]["sandbox_runner_bound"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.runner.noop_identity_bind"
    assert Path(payload["noop_runner_identity_binding_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_source_mount_readiness_records_reference_only_boundary_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )

    rc = main(
        [
            "lab",
            "source-mount-readiness",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    readiness = payload["source_mount_readiness"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert readiness["source_mount_mode"] == "reference_only_read_only"
    assert readiness["read_only_mount_bound"] is False
    assert readiness["source_mount_enforced"] is False
    assert readiness["source_copied"] is False
    assert readiness["source_write_allowed"] is False
    assert readiness["runner_identity_verified"] is True
    assert readiness["live_runner_bound"] is False
    assert readiness["sandbox_runner_bound"] is False
    assert readiness["execution_authority"] is False
    assert readiness["executed"] is False
    assert readiness["commands_executed"] is False
    assert readiness["repo_code_executed"] is False
    assert readiness["candidate_validated"] is False
    assert readiness["capability_promoted"] is False
    assert payload["execution"]["source_mount_ready"] is True
    assert payload["execution"]["read_only_mount_bound"] is False
    assert payload["execution"]["source_mount_enforced"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.source_mount.readiness"
    assert Path(payload["source_mount_readiness_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_source_mount_contract_records_future_read_only_contract_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )

    rc = main(
        [
            "lab",
            "source-mount-contract",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    contract = payload["source_mount_contract"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert contract["contract_kind"] == "francis.lab.source_mount_contract"
    assert contract["contract_mode"] == "contract_only_no_live_mount"
    assert contract["mount_mode"] == "future_read_only_source_mount"
    assert contract["contract_declared"] is True
    assert contract["source_mount_contract"]["allowed_read_roots"] == [source["canonical_path"]]
    assert contract["source_mount_contract"]["denied_write_roots"] == [source["canonical_path"]]
    assert contract["live_mount_bound"] is False
    assert contract["mount_enforced"] is False
    assert contract["read_only_mount_bound"] is False
    assert contract["source_copied"] is False
    assert contract["source_write_allowed"] is False
    assert contract["live_runner_bound"] is False
    assert contract["sandbox_runner_bound"] is False
    assert contract["execution_authority"] is False
    assert contract["executed"] is False
    assert contract["commands_executed"] is False
    assert contract["repo_code_executed"] is False
    assert contract["candidate_validated"] is False
    assert contract["capability_promoted"] is False
    assert payload["execution"]["source_mount_contract_declared"] is True
    assert payload["execution"]["live_mount_bound"] is False
    assert payload["execution"]["mount_enforced"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.source_mount.contract"
    assert Path(payload["source_mount_contract_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_run_boundary_preflight_reports_blocked_controls_without_repo_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )

    rc = main(
        [
            "lab",
            "run-boundary-preflight",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    boundary = payload["run_boundary_preflight"]
    provider_contract = payload["sandbox_provider_contract"]
    provider_binding = payload["sandbox_provider_binding"]
    provider_selection = payload["sandbox_provider_selection"]
    provider_verifier = payload["sandbox_provider_verifier"]
    provider_runtime_probe = payload["sandbox_provider_runtime_probe"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert boundary["boundary_mode"] == "preflight_only_no_execution"
    assert boundary["run_mode"] == "future_sandboxed_rebuild_run_test"
    assert boundary["source_mount_contract_declared"] is True
    assert boundary["sandbox_provider_contract_id"] == provider_contract["id"]
    assert boundary["sandbox_provider_binding_id"] == provider_binding["id"]
    assert boundary["sandbox_provider_selection_id"] == provider_selection["id"]
    assert boundary["sandbox_provider_verifier_id"] == provider_verifier["id"]
    assert boundary["sandbox_provider_runtime_probe_id"] == provider_runtime_probe["id"]
    assert boundary["sandbox_provider_contract_declared"] is True
    assert boundary["sandbox_provider_binding_ready"] is False
    assert boundary["sandbox_provider_selection_ready"] is False
    assert boundary["sandbox_provider_verifier_ready"] is False
    assert boundary["sandbox_provider_runtime_probe_ready"] is False
    assert boundary["provider_runtime_probe_performed"] is False
    assert boundary["sandbox_provider_bound"] is False
    assert boundary["read_only_mount_bound"] is False
    assert boundary["mount_enforced"] is False
    assert boundary["sandbox_bound"] is False
    assert boundary["sandbox_enforced"] is False
    assert boundary["command_allowlist_enforced"] is False
    assert boundary["writer_implementation_bound"] is False
    assert boundary["execution_authority"] is False
    assert boundary["executed"] is False
    assert boundary["commands_executed"] is False
    assert boundary["repo_code_executed"] is False
    assert "sandbox_provider_contract_ready" in boundary["missing_checks"]
    assert "sandbox_provider_binding_ready" in boundary["missing_checks"]
    assert "sandbox_provider_selection_ready" in boundary["missing_checks"]
    assert "sandbox_provider_verifier_ready" in boundary["missing_checks"]
    assert "sandbox_provider_runtime_probe_ready" in boundary["missing_checks"]
    assert "provider_runtime_probe_performed" in boundary["missing_checks"]
    assert "provider_kind_selected" in boundary["missing_checks"]
    assert "verifier_implementation_bound" not in boundary["missing_checks"]
    assert "verifier_identity_bound" not in boundary["missing_checks"]
    assert "provider_binary_or_service_verified" in boundary["missing_checks"]
    assert "sandbox_provider_bound" in boundary["missing_checks"]
    assert "sandbox_bound" in boundary["missing_checks"]
    assert "writer_implementation_bound" in boundary["missing_checks"]
    assert payload["execution"]["run_boundary_preflight_recorded"] is True
    assert payload["execution"]["run_boundary_ready"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.run_boundary.preflight"
    assert Path(payload["run_boundary_preflight_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_execution_boundary_blocks_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-execution-boundary",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    boundary = payload["sandbox_provider_runtime_probe_execution_boundary"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert boundary["boundary_mode"] == "execution_boundary_preflight_only_no_provider_execution"
    assert boundary["run_boundary_present"] is True
    assert boundary["run_boundary_ready"] is False
    assert boundary["runtime_probe_runner_enforcement_present"] is True
    assert boundary["runtime_probe_runner_enforcement_bound"] is False
    assert boundary["provider_probe_execution_boundary_declared"] is True
    assert boundary["provider_probe_execution_boundary_bound"] is False
    assert boundary["provider_runtime_probe_performed"] is False
    assert boundary["execution_receipt_writer_bound"] is False
    assert boundary["sandbox_bound"] is False
    assert boundary["process_launched"] is False
    assert boundary["container_launched"] is False
    assert boundary["execution_authority"] is False
    assert boundary["executed"] is False
    assert boundary["repo_code_executed"] is False
    assert boundary["execution_receipt_written"] is False
    assert "provider_probe_execution_boundary_declared" not in boundary["missing_checks"]
    assert "run_boundary_ready" in boundary["missing_checks"]
    assert "runtime_probe_runner_enforcement_bound" in boundary["missing_checks"]
    assert "provider_runtime_probe_performed" in boundary["missing_checks"]
    assert "execution_receipt_not_written" not in boundary["missing_checks"]
    assert payload["execution"]["provider_runtime_probe_execution_boundary_recorded"] is True
    assert payload["execution"]["provider_runtime_probe_execution_boundary_ready"] is False
    assert payload["execution"]["process_launched"] is False
    assert payload["execution"]["container_launched"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.execution_boundary"
    assert Path(payload["sandbox_provider_runtime_probe_execution_boundary_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_refuse_writes_refusal_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-refuse",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    refusal = payload["sandbox_provider_runtime_probe_refusal"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert refusal["refusal_kind"] == "francis.lab.sandbox_provider_runtime_probe_refusal"
    assert refusal["execution_boundary_id"] == payload["sandbox_provider_runtime_probe_execution_boundary"]["id"]
    assert refusal["provider_runtime_probe_performed"] is False
    assert refusal["provider_binary_executed"] is False
    assert refusal["service_query_performed"] is False
    assert refusal["process_launched"] is False
    assert refusal["container_launched"] is False
    assert refusal["execution_authority"] is False
    assert refusal["executed"] is False
    assert refusal["repo_code_executed"] is False
    assert refusal["execution_receipt_written"] is False
    assert payload["execution"]["provider_runtime_probe_performed"] is False
    assert payload["execution"]["provider_binary_executed"] is False
    assert payload["execution"]["process_launched"] is False
    assert payload["execution"]["container_launched"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.refuse"
    assert Path(payload["sandbox_provider_runtime_probe_refusal_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_request_approval_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-request-approval",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    approval_request = payload["sandbox_provider_runtime_probe_approval_request"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "needs_approval"
    assert approval_request["action"] == "francis.lab.sandbox_provider_runtime_probe"
    assert approval_request["approval_created"] is True
    assert approval_request["approval_id"] == payload["approval"]["id"]
    assert approval_request["upstream_approval_id"] == approval_id
    assert approval_request["approval_consumed"] is False
    assert approval_request["upstream_approval_consumed"] is False
    assert approval_request["execution_authority"] is False
    assert approval_request["executed"] is False
    assert approval_request["provider_runtime_probe_performed"] is False
    assert approval_request["provider_binary_executed"] is False
    assert approval_request["service_query_performed"] is False
    assert approval_request["process_launched"] is False
    assert approval_request["container_launched"] is False
    assert approval_request["execution_receipt_written"] is False
    assert payload["execution"]["approval_request_created"] is True
    assert payload["execution"]["provider_runtime_probe_performed"] is False
    assert payload["execution"]["provider_binary_executed"] is False
    assert payload["execution"]["process_launched"] is False
    assert payload["execution"]["container_launched"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.approval_request"
    assert Path(payload["sandbox_provider_runtime_probe_approval_request_path"]).exists()
    assert Path(payload["approval_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_sandbox_provider_runtime_probe_consume_approval_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]
    approvals.decide(approval_id, "approve", actor="test.operator")
    service.prewrite_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.finalize_lab_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.synthetic_receipt",
    )
    service.consume_lab_approval_for_synthetic_execution_receipt(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.approval.consume",
    )
    service.run_lab_noop_runner_envelope(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_runner",
    )
    service.capture_lab_noop_runner_transcript(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_transcript",
    )
    service.bind_lab_noop_runner_identity(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.noop_identity",
    )
    approval_request_result = service.request_lab_sandbox_provider_runtime_probe_approval(
        source["id"],
        "run_project_tests",
        approval_id,
        actor="test.lab.runtime_probe_approval_request",
    )
    provider_probe_approval_id = approval_request_result["sandbox_provider_runtime_probe_approval_request"][
        "approval_id"
    ]
    approvals.decide(provider_probe_approval_id, "approve", actor="test.operator")

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-consume-approval",
            source["id"],
            "run_project_tests",
            provider_probe_approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    consumption = payload["sandbox_provider_runtime_probe_approval_consumption"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "consumed"
    assert consumption["action"] == "francis.lab.sandbox_provider_runtime_probe"
    assert consumption["approval_id"] == provider_probe_approval_id
    assert consumption["approval_consumed"] is True
    assert consumption["single_use_enforced"] is True
    assert consumption["execution_authority"] is False
    assert consumption["executed"] is False
    assert consumption["provider_runtime_probe_performed"] is False
    assert consumption["provider_binary_executed"] is False
    assert consumption["process_launched"] is False
    assert consumption["container_launched"] is False
    assert consumption["execution_receipt_written"] is False
    assert payload["execution"]["provider_runtime_probe_approval_consumed"] is True
    assert payload["execution"]["provider_runtime_probe_performed"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.approval.consume"
    assert Path(payload["sandbox_provider_runtime_probe_approval_consumption_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-invocation-boundary",
            source["id"],
            "run_project_tests",
            provider_probe_approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    invocation = payload["sandbox_provider_runtime_probe_invocation_boundary"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert invocation["boundary_kind"] == "francis.lab.sandbox_provider_runtime_probe_invocation_boundary"
    assert invocation["approval_id"] == provider_probe_approval_id
    assert invocation["approval_consumed"] is True
    assert invocation["single_use_enforced"] is True
    assert invocation["exact_action_binding_verified"] is True
    assert invocation["probe_runner_bound"] is False
    assert invocation["probe_runner_receipt_writer_bound"] is False
    assert invocation["execution_authority"] is False
    assert invocation["executed"] is False
    assert invocation["provider_runtime_probe_performed"] is False
    assert invocation["provider_binary_executed"] is False
    assert invocation["process_launched"] is False
    assert invocation["container_launched"] is False
    assert invocation["execution_receipt_written"] is False
    assert payload["execution"]["provider_runtime_probe_invocation_boundary_recorded"] is True
    assert payload["execution"]["provider_runtime_probe_performed"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.invocation_boundary"
    assert Path(payload["sandbox_provider_runtime_probe_invocation_boundary_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-runner-pre-execution-boundary",
            source["id"],
            "run_project_tests",
            provider_probe_approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    pre_execution = payload["sandbox_provider_runtime_probe_runner_pre_execution_boundary"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert pre_execution["boundary_kind"] == (
        "francis.lab.sandbox_provider_runtime_probe_runner_pre_execution_boundary"
    )
    assert pre_execution["approval_id"] == provider_probe_approval_id
    assert pre_execution["invocation_boundary_id"] == invocation["id"]
    assert pre_execution["approval_consumed"] is True
    assert pre_execution["single_use_enforced"] is True
    assert pre_execution["exact_action_binding_verified"] is True
    assert pre_execution["runner_identity_declared"] is True
    assert pre_execution["runner_identity_bound"] is False
    assert pre_execution["runner_policy_declared"] is True
    assert pre_execution["runner_policy_bound"] is False
    assert pre_execution["sandbox_policy_declared"] is True
    assert pre_execution["sandbox_policy_bound"] is False
    assert pre_execution["network_block_declared"] is True
    assert pre_execution["network_block_bound"] is False
    assert pre_execution["execution_receipt_writer_declared"] is True
    assert pre_execution["execution_receipt_writer_bound"] is False
    assert pre_execution["execution_authority"] is False
    assert pre_execution["executed"] is False
    assert pre_execution["provider_runtime_probe_performed"] is False
    assert pre_execution["provider_binary_executed"] is False
    assert pre_execution["process_launched"] is False
    assert pre_execution["container_launched"] is False
    assert pre_execution["execution_receipt_written"] is False
    assert payload["execution"]["provider_runtime_probe_runner_pre_execution_boundary_recorded"] is True
    assert payload["execution"]["provider_runtime_probe_performed"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.runner_pre_execution_boundary"
    assert Path(payload["sandbox_provider_runtime_probe_runner_pre_execution_boundary_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()

    rc = main(
        [
            "lab",
            "sandbox-provider-runtime-probe-runner-control-binding",
            source["id"],
            "run_project_tests",
            provider_probe_approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    control_binding = payload["sandbox_provider_runtime_probe_runner_control_binding"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert control_binding["binding_kind"] == "francis.lab.sandbox_provider_runtime_probe_runner_control_binding"
    assert control_binding["approval_id"] == provider_probe_approval_id
    assert control_binding["pre_execution_boundary_id"] == pre_execution["id"]
    assert control_binding["control_binding_recorded"] is True
    assert control_binding["runner_identity_binding_recorded"] is True
    assert control_binding["runner_identity_bound"] is False
    assert control_binding["runner_policy_binding_recorded"] is True
    assert control_binding["runner_policy_bound"] is False
    assert control_binding["sandbox_policy_binding_recorded"] is True
    assert control_binding["sandbox_policy_bound"] is False
    assert control_binding["network_block_binding_recorded"] is True
    assert control_binding["network_block_bound"] is False
    assert control_binding["execution_receipt_writer_binding_recorded"] is True
    assert control_binding["execution_receipt_writer_bound"] is False
    assert control_binding["execution_authority"] is False
    assert control_binding["executed"] is False
    assert control_binding["provider_runtime_probe_performed"] is False
    assert control_binding["provider_binary_executed"] is False
    assert control_binding["process_launched"] is False
    assert control_binding["container_launched"] is False
    assert control_binding["execution_receipt_written"] is False
    assert payload["execution"]["provider_runtime_probe_runner_control_binding_recorded"] is True
    assert payload["execution"]["provider_runtime_probe_performed"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandbox.provider_runtime_probe.runner_control_binding"
    assert Path(payload["sandbox_provider_runtime_probe_runner_control_binding_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()

    rc = main(
        [
            "lab",
            "sandboxed-rebuild-run-test-boundary",
            source["id"],
            "run_project_tests",
            provider_probe_approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    sandboxed_boundary = payload["sandboxed_rebuild_run_test_boundary"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert sandboxed_boundary["boundary_kind"] == "francis.lab.sandboxed_rebuild_run_test_boundary"
    assert sandboxed_boundary["control_binding_id"] == control_binding["id"]
    assert sandboxed_boundary["control_binding_recorded"] is True
    assert sandboxed_boundary["control_binding_ready"] is False
    assert sandboxed_boundary["execution_approval_required"] is True
    assert sandboxed_boundary["execution_approval_consumed"] is False
    assert sandboxed_boundary["runner_identity_bound"] is False
    assert sandboxed_boundary["sandbox_enforced"] is False
    assert sandboxed_boundary["execution_receipt_writer_bound"] is False
    assert sandboxed_boundary["execution_authority"] is False
    assert sandboxed_boundary["executed"] is False
    assert sandboxed_boundary["commands_executed"] is False
    assert sandboxed_boundary["repo_code_executed"] is False
    assert sandboxed_boundary["ran_install"] is False
    assert sandboxed_boundary["ran_build"] is False
    assert sandboxed_boundary["ran_tests"] is False
    assert payload["execution"]["sandboxed_rebuild_run_test_boundary_recorded"] is True
    assert payload["execution"]["execution_approval_consumed"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.boundary"
    assert Path(payload["sandboxed_rebuild_run_test_boundary_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()

    rc = main(
        [
            "lab",
            "sandboxed-rebuild-run-test-request-approval",
            source["id"],
            "run_project_tests",
            provider_probe_approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    approval_request = payload["sandboxed_rebuild_run_test_approval_request"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "needs_approval"
    assert approval_request["status"] == "needs_approval"
    assert approval_request["action"] == "francis.lab.sandboxed_rebuild_run_test"
    assert approval_request["approval_created"] is True
    assert approval_request["approval_id"] == payload["approval"]["id"]
    assert approval_request["upstream_approval_id"] == provider_probe_approval_id
    assert approval_request["sandboxed_boundary_id"] == sandboxed_boundary["id"]
    assert approval_request["control_binding_id"] == control_binding["id"]
    assert approval_request["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.request_approval"
    assert approval_request["approval_consumed"] is False
    assert approval_request["upstream_approval_consumed"] is False
    assert approval_request["boundary_recorded"] is True
    assert approval_request["boundary_ready"] is False
    assert approval_request["execution_authority"] is False
    assert approval_request["executed"] is False
    assert approval_request["commands_executed"] is False
    assert approval_request["repo_code_executed"] is False
    assert approval_request["ran_install"] is False
    assert approval_request["ran_build"] is False
    assert approval_request["ran_tests"] is False
    assert approval_request["network_accessed"] is False
    assert approval_request["wrote_to_repo"] is False
    assert approval_request["execution_receipt_written"] is False
    assert approval_request["candidate_validated"] is False
    assert approval_request["capability_promoted"] is False
    assert "sandboxed_rebuild_run_test_requires_operator_execution_approval" in approval_request["blockers"]
    assert payload["execution"]["approval_request_created"] is True
    assert payload["execution"]["sandboxed_rebuild_run_test_approval_consumed"] is False
    assert payload["execution"]["execution_approval_consumed"] is False
    assert payload["execution"]["ran_build"] is False
    assert payload["execution"]["ran_tests"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.approval_request"
    assert Path(payload["sandboxed_rebuild_run_test_approval_request_path"]).exists()
    assert Path(payload["approval_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()

    sandboxed_approval_id = approval_request["approval_id"]
    approvals.decide(sandboxed_approval_id, "approve", actor="test.operator")
    rc = main(
        [
            "lab",
            "sandboxed-rebuild-run-test-consume-approval",
            source["id"],
            "run_project_tests",
            sandboxed_approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    consumption = payload["sandboxed_rebuild_run_test_approval_consumption"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "consumed"
    assert consumption["status"] == "consumed"
    assert consumption["action"] == "francis.lab.sandboxed_rebuild_run_test"
    assert consumption["approval_id"] == sandboxed_approval_id
    assert consumption["approval_request_id"] == approval_request["id"]
    assert consumption["upstream_approval_id"] == provider_probe_approval_id
    assert consumption["sandboxed_boundary_id"] == sandboxed_boundary["id"]
    assert consumption["control_binding_id"] == control_binding["id"]
    assert consumption["approval_consumed"] is True
    assert consumption["single_use_enforced"] is True
    assert consumption["execution_authority"] is False
    assert consumption["executed"] is False
    assert consumption["commands_executed"] is False
    assert consumption["repo_code_executed"] is False
    assert consumption["ran_install"] is False
    assert consumption["ran_build"] is False
    assert consumption["ran_tests"] is False
    assert consumption["network_accessed"] is False
    assert consumption["wrote_to_repo"] is False
    assert consumption["execution_receipt_written"] is False
    assert consumption["candidate_validated"] is False
    assert consumption["capability_promoted"] is False
    assert payload["execution"]["sandboxed_rebuild_run_test_approval_consumed"] is True
    assert payload["execution"]["execution_approval_consumed"] is True
    assert payload["execution"]["ran_build"] is False
    assert payload["execution"]["ran_tests"] is False
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.approval.consume"
    assert Path(payload["sandboxed_rebuild_run_test_approval_consumption_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()

    provider_reference = tmp_path / "cli-sandbox-runner"
    provider_reference.write_text("metadata only cli sandbox runner reference\n", encoding="utf-8")
    provider_policy_manifest = tmp_path / "cli-sandbox-runner-policy.json"
    provider_policy_manifest.write_text(
        json.dumps({"network": False, "execution": False, "secret_token": "super-secret-token-value"}),
        encoding="utf-8",
    )
    rc = main(
        [
            "lab",
            "sandboxed-rebuild-run-test-runner-binding",
            source["id"],
            "run_project_tests",
            sandboxed_approval_id,
            "--provider-kind",
            "local_process_sandbox",
            "--provider-reference",
            str(provider_reference),
            "--provider-policy-manifest",
            str(provider_policy_manifest),
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    runner_binding = payload["sandboxed_rebuild_run_test_runner_binding"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert runner_binding["status"] == "blocked"
    assert runner_binding["approval_id"] == sandboxed_approval_id
    assert runner_binding["approval_consumption_id"] == consumption["id"]
    assert runner_binding["approval_request_id"] == approval_request["id"]
    assert runner_binding["sandboxed_boundary_id"] == sandboxed_boundary["id"]
    assert runner_binding["control_binding_id"] == control_binding["id"]
    assert runner_binding["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.runner_binding"
    assert runner_binding["binding_mode"] == "static_provider_reference_only_no_live_runner"
    assert runner_binding["static_provider_reference_bound"] is True
    assert runner_binding["provider_reference_verified"] is True
    assert runner_binding["provider_policy_manifest_bound"] is True
    assert runner_binding["runner_binding_declared"] is True
    assert runner_binding["live_runner_bound"] is False
    assert runner_binding["sandbox_runner_bound"] is False
    assert runner_binding["sandbox_enforced"] is False
    assert runner_binding["execution_authority"] is False
    assert runner_binding["executed"] is False
    assert runner_binding["commands_executed"] is False
    assert runner_binding["repo_code_executed"] is False
    assert runner_binding["ran_install"] is False
    assert runner_binding["ran_build"] is False
    assert runner_binding["ran_tests"] is False
    assert runner_binding["execution_receipt_written"] is False
    assert "live_runner_bound" in runner_binding["missing_checks"]
    assert "sandbox_runner_bound" in runner_binding["missing_checks"]
    assert "sandbox_enforced" in runner_binding["missing_checks"]
    assert payload["execution"]["sandboxed_rebuild_run_test_runner_binding_recorded"] is True
    assert payload["execution"]["static_provider_reference_bound"] is True
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.runner_binding"
    assert Path(payload["sandboxed_rebuild_run_test_runner_binding_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(payload["sandboxed_rebuild_run_test_runner_binding_path"]).read_text(
        encoding="utf-8"
    )
    assert not (repo / "lab-ran.txt").exists()

    rc = main(
        [
            "lab",
            "sandboxed-rebuild-run-test-sandbox-policy",
            source["id"],
            "run_project_tests",
            sandboxed_approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    sandbox_policy = payload["sandboxed_rebuild_run_test_sandbox_policy"]

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert sandbox_policy["status"] == "blocked"
    assert sandbox_policy["approval_id"] == sandboxed_approval_id
    assert sandbox_policy["approval_consumption_id"] == consumption["id"]
    assert sandbox_policy["runner_binding_id"] == runner_binding["id"]
    assert sandbox_policy["approval_request_id"] == approval_request["id"]
    assert sandbox_policy["sandboxed_boundary_id"] == sandboxed_boundary["id"]
    assert sandbox_policy["control_binding_id"] == control_binding["id"]
    assert sandbox_policy["permission_scope"] == "ingest.lab.sandboxed_rebuild_run_test.sandbox_policy"
    assert sandbox_policy["policy_kind"] == "sandboxed_rebuild_run_test_sandbox_policy_preflight"
    assert sandbox_policy["policy_mode"] == "policy_preflight_no_live_sandbox"
    assert sandbox_policy["approval_consumed"] is True
    assert sandbox_policy["runner_binding_present"] is True
    assert sandbox_policy["static_provider_reference_bound"] is True
    assert sandbox_policy["sandbox_policy_declared"] is True
    assert sandbox_policy["network_default_deny"] is True
    assert sandbox_policy["repo_write_allowed"] is False
    assert sandbox_policy["destructive_allowed"] is False
    assert sandbox_policy["secret_storage_allowed"] is False
    assert sandbox_policy["command_execution_enabled"] is False
    assert sandbox_policy["command_allowlist_bound"] is False
    assert sandbox_policy["execution_receipt_writer_bound"] is False
    assert sandbox_policy["live_sandbox_bound"] is False
    assert sandbox_policy["sandbox_enforced"] is False
    assert sandbox_policy["execution_authority"] is False
    assert sandbox_policy["executed"] is False
    assert sandbox_policy["commands_executed"] is False
    assert sandbox_policy["repo_code_executed"] is False
    assert sandbox_policy["ran_build"] is False
    assert sandbox_policy["ran_tests"] is False
    assert "command_allowlist_bound" in sandbox_policy["missing_checks"]
    assert "execution_receipt_writer_bound" in sandbox_policy["missing_checks"]
    assert "live_sandbox_bound" in sandbox_policy["missing_checks"]
    assert "sandbox_enforced" in sandbox_policy["missing_checks"]
    assert payload["execution"]["sandboxed_rebuild_run_test_sandbox_policy_recorded"] is True
    assert payload["execution"]["sandbox_policy_declared"] is True
    assert payload["execution"]["executed"] is False
    assert payload["receipt"]["operation"] == "lab.sandboxed_rebuild_run_test.sandbox_policy"
    assert Path(payload["sandboxed_rebuild_run_test_sandbox_policy_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert "super-secret-token-value" not in Path(payload["sandboxed_rebuild_run_test_sandbox_policy_path"]).read_text(
        encoding="utf-8"
    )
    assert not (repo / "lab-ran.txt").exists()


def test_lab_approval_consumption_preflight_refuses_mismatched_approval_id_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]

    result = service.preflight_lab_approval_consumption(
        source["id"],
        "inspect_project_structure",
        approval_id,
        actor="test.lab.consume",
    )
    binding = result["approval_consumption"]["binding"]

    assert result["ok"] is True
    assert result["status"] == "refused"
    assert binding["exact_match"] is False
    assert binding["refused"] is True
    assert "candidate_id" in binding["mismatch_fields"]
    assert "approval_exact_action_binding_mismatch" in result["approval_consumption"]["blockers"]
    assert result["approval_consumption"]["approval_consumed"] is False
    assert result["approval_consumption"]["execution_authority"] is False
    assert result["execution"]["executed"] is False
    assert result["receipt"]["result_status"] == "refused"
    assert (data_root / "approvals" / "pending" / f"{approval_id}.json").exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_approval_consumption_preflight_outputs_blocked_without_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]
    request = service.request_lab_execution_approval(source["id"], "run_project_tests", actor="test.lab.request")
    approval_id = request["approval"]["id"]

    rc = main(
        [
            "lab",
            "approval-consumption-preflight",
            source["id"],
            "run_project_tests",
            approval_id,
            "--actor",
            "test.lab.cli",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert payload["approval_consumption"]["approval_id"] == approval_id
    assert payload["approval_consumption"]["binding"]["exact_match"] is True
    assert payload["approval_consumption"]["approval_consumed"] is False
    assert payload["runner_contract"]["runner_bound"] is False
    assert payload["runner_contract"]["execution_enabled"] is False
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["network_accessed"] is False
    assert Path(payload["artifact_path"]).exists()
    assert Path(payload["runner_contract_path"]).exists()
    assert Path(payload["receipt_path"]).exists()
    assert not (repo / "lab-ran.txt").exists()


def test_lab_cli_execute_refuses_and_records_no_execution(monkeypatch, tmp_path: Path, capsys) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    repo = _fixture_repo(tmp_path)
    service = IngestService()
    source = service.add_source(repo, actor="test.ingest")["source"]

    rc = main(["lab", "execute", source["id"], "run_project_tests", "--actor", "test.lab.cli"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "blocked"
    assert payload["execution"]["executed"] is False
    assert payload["execution"]["ran_repo_scripts"] is False
    assert payload["refusal"]["receipt_path"] == payload["receipt_path"]
    assert not (repo / "lab-ran.txt").exists()


def _receipt_payloads(data_root: Path) -> list[dict[str, object]]:
    payloads = []
    for path in (data_root / "artifacts" / "ingest" / "receipts").glob("*.json"):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads
