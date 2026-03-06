from __future__ import annotations

import argparse
import logging
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("francis.scaffold")
DRY_RUN = False


def ensure_dir(rel: str) -> None:
    path = ROOT / rel
    existed = path.exists()
    if DRY_RUN:
        if existed:
            LOGGER.debug("Dry-run: dir already exists: %s", rel)
        else:
            LOGGER.info("Dry-run: create dir: %s", rel)
        return
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        LOGGER.error("Permission denied creating dir: %s (%s)", rel, exc)
        return
    if existed:
        LOGGER.debug("Dir already exists: %s", rel)
    else:
        LOGGER.info("Created dir: %s", rel)


def write_if_missing(rel: str, content: str = "") -> None:
    path = ROOT / rel
    if path.exists():
        LOGGER.debug("Skipped existing file: %s", rel)
        return
    if DRY_RUN:
        LOGGER.info("Dry-run: create file: %s", rel)
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except PermissionError as exc:
        LOGGER.error("Permission denied writing file: %s (%s)", rel, exc)
        return
    LOGGER.info("Created file: %s", rel)


def write(rel: str, content: str) -> None:
    path = ROOT / rel
    if DRY_RUN:
        LOGGER.info("Dry-run: overwrite file: %s", rel)
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except PermissionError as exc:
        LOGGER.error("Permission denied writing file: %s (%s)", rel, exc)
        return
    LOGGER.info("Wrote file: %s", rel)


DIRECTORIES = [
    "docs/lore",
    "docs/architecture",
    "docs/governance",
    "docs/operations",
    "docs/product",
    "services/gateway/app/middleware",
    "services/gateway/app/routes",
    "services/gateway/app/schemas",
    "services/orchestrator/app/routes",
    "services/orchestrator/app/middleware",
    "services/worker/app/executors",
    "services/worker/app/safety",
    "services/observer/app/probes",
    "services/observer/app/anomaly",
    "services/hud/app/views",
    "services/hud/app/static",
    "services/voice/app",
    "packages/francis_core/francis_core",
    "packages/francis_brain/francis_brain/retrieval",
    "packages/francis_policy/francis_policy/policy_as_code/examples",
    "packages/francis_skills/francis_skills/toolbelt",
    "packages/francis_skills/francis_skills/packs/system",
    "packages/francis_skills/francis_skills/packs/repo",
    "packages/francis_skills/francis_skills/packs/workspace",
    "packages/francis_skills/francis_skills/packs/ops",
    "packages/francis_presence/francis_presence/templates",
    "packages/francis_forge/francis_forge",
    "packages/francis_connectors/francis_connectors",
    "packages/francis_llm/francis_llm/prompts",
    "packages/francis_llm/francis_llm/evals",
    "policies/examples",
    "schemas/events",
    "schemas/api",
    "proto",
    "infra/postgres/migrations",
    "infra/redis",
    "infra/qdrant",
    "infra/observability/grafana/dashboards",
    "infra/secrets",
    "scripts",
    "tools",
    "runtime/prompts_cache",
    "runtime/models",
    "runtime/embeddings",
    "runtime/keys",
    "workspace/runs",
    "workspace/presence/digests",
    "workspace/missions",
    "workspace/queue",
    "workspace/incidents/evidence",
    "workspace/forge/staging",
    "workspace/forge/reports",
    "workspace/logs",
    "tests/unit",
    "tests/integration",
    "tests/redteam",
    "tests/evals",
    ".github/workflows",
]


ROOT_FILES = {
    "README.md": (
        "# Francis\n\n"
        "Francis is a local-first AI operator platform.\n\n"
        "## Core Principles\n\n"
        "- User is pilot; Francis is operator.\n"
        "- Event-driven autonomy reactor, never blind loops.\n"
        "- Every mutating action leaves receipts (run_id, logs, diffs).\n"
        "- Scope boundaries and approvals are non-negotiable.\n"
    ),
    "AGENTS.md": (
        "# AGENTS\n\n"
        "## Role\n\n"
        "Codex is the builder of Francis. The user is the architect and product owner.\n\n"
        "## Cadence\n\n"
        "Objective -> Rules -> Tasks -> Full Files -> Verify -> Report\n\n"
        "## Safety\n\n"
        "- No destructive operations.\n"
        "- Constrain writes to allowed workspace/repo scope.\n"
        "- Log all meaningful actions with traceable run ids.\n"
    ),
    "VISION.md": (
        "# Vision\n\n"
        "Francis is an operator layer over the PC, designed to feel like a calm and capable digital colleague.\n\n"
        "## North Star\n\n"
        "- Francis Lens overlays mission context, blockers, and action chips across active work.\n"
        "- Francis can take over execution on command in Pilot Mode, then return control with receipts.\n"
        "- Away Mode advances queued work safely and returns with a grounded shift summary.\n\n"
        "## Grounding Contract\n\n"
        "- Francis never fabricates system state.\n"
        "- Francis never claims completion without evidence.\n"
        "- Francis only acts inside explicit user-approved scope.\n"
    ),
    "ROADMAP.md": (
        "# Roadmap\n\n"
        "## Stage 1-4 Foundations\n\n"
        "- Presence: grounded briefings and context-aware communication.\n"
        "- Observer: high-signal environment events.\n"
        "- Brain: durable memory lanes and receipts.\n"
        "- Missions: explicit goals and progress tracking.\n"
        "- Forge: staged capability generation and promotion gates.\n\n"
        "## Stage 5+\n\n"
        "- Event-driven autonomy kernel.\n"
        "- Francis Lens control surface and takeover UX.\n"
        "- Work telemetry connectors.\n"
        "- Digital twin workflows and remote approvals.\n"
    ),
    "CHANGELOG.md": "# Changelog\n\n## Unreleased\n- Architecture scaffold created.\n",
    "LICENSE": "MIT\n",
    ".env.example": "FRANCIS_WORKSPACE_ROOT=./workspace\n",
    ".gitignore": ".venv/\n__pycache__/\n*.pyc\nruntime/keys/*\n",
    ".gitattributes": "* text=auto\n",
    ".editorconfig": (
        "root = true\n\n[*]\ncharset = utf-8\nend_of_line = lf\n"
        "insert_final_newline = true\nindent_style = space\nindent_size = 4\n"
    ),
    "SECURITY.md": "# Security\n\nSee docs/governance/INCIDENTS.md.\n",
    "CODEOWNERS": "* @owner\n",
    "CONTRIBUTING.md": "# Contributing\n\nRun tests and quality checks before merging.\n",
    "Makefile": ".PHONY: test\n\ntest:\n\tpytest\n",
    "pyproject.toml": (
        "[project]\n"
        'name = "francis"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
    ),
}


DOCS = [
    "docs/lore/LORE.md",
    "docs/lore/PRIME_DIRECTIVE.md",
    "docs/lore/PRESENCE.md",
    "docs/lore/RITUALS.md",
    "docs/lore/VOICE.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/architecture/DATAFLOWS.md",
    "docs/architecture/MODULE_BOUNDARIES.md",
    "docs/architecture/EVENTING.md",
    "docs/architecture/STORAGE.md",
    "docs/architecture/OBSERVABILITY.md",
    "docs/architecture/THREAT_MODEL.md",
    "docs/governance/AUTONOMY.md",
    "docs/governance/POLICIES.md",
    "docs/governance/RBAC.md",
    "docs/governance/APPROVALS.md",
    "docs/governance/AUDIT.md",
    "docs/governance/INCIDENTS.md",
    "docs/governance/COMPLIANCE.md",
    "docs/operations/RUNBOOK.md",
    "docs/operations/BACKUPS.md",
    "docs/operations/MIGRATIONS.md",
    "docs/operations/ON_CALL.md",
    "docs/operations/DRILLS.md",
    "docs/product/CAPABILITIES.md",
    "docs/product/MISSIONS.md",
    "docs/product/FORGE.md",
    "docs/product/MARKETPLACE.md",
    "docs/product/HUD.md",
]


SERVICE_PYPROJECTS = [
    "services/gateway/pyproject.toml",
    "services/orchestrator/pyproject.toml",
    "services/worker/pyproject.toml",
    "services/observer/pyproject.toml",
    "services/hud/pyproject.toml",
    "services/voice/pyproject.toml",
]


PACKAGE_PYPROJECTS = [
    "packages/francis_core/pyproject.toml",
    "packages/francis_brain/pyproject.toml",
    "packages/francis_policy/pyproject.toml",
    "packages/francis_skills/pyproject.toml",
    "packages/francis_presence/pyproject.toml",
    "packages/francis_forge/pyproject.toml",
    "packages/francis_connectors/pyproject.toml",
    "packages/francis_llm/pyproject.toml",
]


STUB_FILES = [
    "services/gateway/app/middleware/request_id.py",
    "services/gateway/app/middleware/auth.py",
    "services/gateway/app/middleware/rbac.py",
    "services/gateway/app/middleware/rate_limit.py",
    "services/gateway/app/middleware/panic_mode.py",
    "services/gateway/app/routes/auth.py",
    "services/gateway/app/routes/proxy.py",
    "services/gateway/app/routes/admin.py",
    "services/gateway/app/schemas/common.py",
    "services/gateway/app/schemas/auth.py",
    "services/worker/app/queue.py",
    "services/worker/app/executors/skill_executor.py",
    "services/worker/app/executors/mission_executor.py",
    "services/worker/app/executors/forge_executor.py",
    "services/worker/app/safety/sandbox.py",
    "services/worker/app/safety/resource_limits.py",
    "services/observer/app/probes/disk.py",
    "services/observer/app/probes/cpu.py",
    "services/observer/app/probes/memory.py",
    "services/observer/app/probes/network.py",
    "services/observer/app/probes/processes.py",
    "services/observer/app/probes/repo.py",
    "services/observer/app/probes/services.py",
    "services/observer/app/anomaly/baselines.py",
    "services/observer/app/anomaly/detectors.py",
    "services/observer/app/anomaly/scoring.py",
    "services/observer/app/emitter.py",
    "services/hud/app/views/dashboard.py",
    "services/hud/app/views/runs.py",
    "services/hud/app/views/missions.py",
    "services/hud/app/views/inbox.py",
    "services/hud/app/views/incidents.py",
    "services/voice/app/stt.py",
    "services/voice/app/tts.py",
    "services/voice/app/wakeword.py",
    "packages/francis_brain/francis_brain/lanes.py",
    "packages/francis_brain/francis_brain/memory_store.py",
    "packages/francis_brain/francis_brain/recall.py",
    "packages/francis_brain/francis_brain/reflection.py",
    "packages/francis_brain/francis_brain/snapshots.py",
    "packages/francis_brain/francis_brain/embeddings.py",
    "packages/francis_brain/francis_brain/retrieval/vector_index.py",
    "packages/francis_brain/francis_brain/retrieval/rerank.py",
    "packages/francis_brain/francis_brain/retrieval/chunking.py",
    "packages/francis_policy/francis_policy/decisions.py",
    "packages/francis_policy/francis_policy/approvals.py",
    "packages/francis_policy/francis_policy/rbac.py",
    "packages/francis_policy/francis_policy/constraints.py",
    "packages/francis_policy/francis_policy/panic_mode.py",
    "packages/francis_policy/francis_policy/policy_as_code/parser.py",
    "packages/francis_policy/francis_policy/policy_as_code/evaluator.py",
    "packages/francis_skills/francis_skills/contracts.py",
    "packages/francis_skills/francis_skills/executor.py",
    "packages/francis_skills/francis_skills/validator.py",
    "packages/francis_skills/francis_skills/toolbelt/shell.py",
    "packages/francis_skills/francis_skills/toolbelt/files.py",
    "packages/francis_skills/francis_skills/toolbelt/git.py",
    "packages/francis_skills/francis_skills/toolbelt/http.py",
    "packages/francis_skills/francis_skills/toolbelt/parsing.py",
    "packages/francis_presence/francis_presence/tone.py",
    "packages/francis_presence/francis_presence/narrator.py",
    "packages/francis_presence/francis_presence/rituals.py",
    "packages/francis_presence/francis_presence/triggers.py",
    "packages/francis_presence/francis_presence/notifications.py",
    "packages/francis_forge/francis_forge/proposal_engine.py",
    "packages/francis_forge/francis_forge/scaffold_generator.py",
    "packages/francis_forge/francis_forge/test_generator.py",
    "packages/francis_forge/francis_forge/validation.py",
    "packages/francis_forge/francis_forge/diff_analyzer.py",
    "packages/francis_forge/francis_forge/promotion.py",
    "packages/francis_forge/francis_forge/catalog.py",
    "packages/francis_connectors/francis_connectors/filesystem.py",
    "packages/francis_connectors/francis_connectors/email.py",
    "packages/francis_connectors/francis_connectors/discord.py",
    "packages/francis_connectors/francis_connectors/telegram.py",
    "packages/francis_connectors/francis_connectors/home_assistant.py",
    "packages/francis_connectors/francis_connectors/calendar.py",
    "packages/francis_connectors/francis_connectors/webhooks.py",
    "packages/francis_llm/francis_llm/local_ollama.py",
    "packages/francis_llm/francis_llm/local_llamacpp.py",
    "packages/francis_llm/francis_llm/openai_api.py",
    "packages/francis_llm/francis_llm/tools_schema.py",
    "packages/francis_llm/francis_llm/evals/harness.py",
    "packages/francis_llm/francis_llm/evals/scoring.py",
    "scripts/bootstrap.ps1",
    "scripts/dev.ps1",
    "scripts/run.ps1",
    "scripts/test.ps1",
    "scripts/lint.ps1",
    "scripts/doctor.ps1",
    "scripts/migrate.ps1",
    "scripts/seed.ps1",
    "scripts/release.ps1",
    "tools/replace_doc_block.py",
    "tools/snapshot_repo.py",
    "tools/redact_logs.py",
    "tools/generate_capability_pack.py",
    "tests/integration/test_observer_emits_events.py",
    "tests/integration/test_mission_tick.py",
    "tests/redteam/test_prompt_injection.py",
    "tests/redteam/test_fs_escape_attempts.py",
    "tests/redteam/test_policy_bypass.py",
    "tests/evals/test_golden_tasks.py",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold the Francis architecture tree.")
    parser.add_argument("--dry-run", action="store_true", help="Preview creates/writes without changing files.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity.")
    return parser.parse_args()


def configure_logging(verbose: int) -> None:
    level = logging.DEBUG if verbose > 0 else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def main() -> None:
    global DRY_RUN
    args = parse_args()
    configure_logging(args.verbose)
    DRY_RUN = bool(args.dry_run)
    if DRY_RUN:
        LOGGER.info("Dry-run enabled. No files will be written.")

    for d in DIRECTORIES:
        ensure_dir(d)

    for path, content in ROOT_FILES.items():
        write_if_missing(path, content)

    for doc in DOCS:
        title = Path(doc).stem.replace("_", " ")
        write_if_missing(doc, f"# {title}\n")

    for pyproject in SERVICE_PYPROJECTS:
        service_name = Path(pyproject).parts[1]
        write_if_missing(
            pyproject,
            (
                "[project]\n"
                f'name = "francis-{service_name}"\n'
                'version = "0.1.0"\n'
                'requires-python = ">=3.10"\n'
            ),
        )

    for pyproject in PACKAGE_PYPROJECTS:
        package_name = Path(pyproject).parts[1]
        write_if_missing(
            pyproject,
            (
                "[project]\n"
                f'name = "{package_name}"\n'
                'version = "0.1.0"\n'
                'requires-python = ">=3.10"\n'
            ),
        )

    for path in STUB_FILES:
        if path.endswith(".py"):
            write_if_missing(path, "# stub\n")
        elif path.endswith(".ps1"):
            write_if_missing(path, "Write-Host 'TODO'\n")
        else:
            write_if_missing(path, "")

    write_if_missing("services/__init__.py", "")
    write_if_missing("services/gateway/__init__.py", "")
    write_if_missing("services/gateway/app/__init__.py", "")
    write_if_missing("services/gateway/app/routes/__init__.py", "")
    write_if_missing("services/orchestrator/__init__.py", "")
    write_if_missing("services/orchestrator/app/__init__.py", "")
    write_if_missing("services/orchestrator/app/routes/__init__.py", "")
    write_if_missing("packages/francis_core/francis_core/__init__.py", "")
    write_if_missing("packages/francis_brain/francis_brain/__init__.py", "")
    write_if_missing("packages/francis_policy/francis_policy/__init__.py", "")
    write_if_missing("packages/francis_skills/francis_skills/__init__.py", "")
    write_if_missing("packages/francis_presence/francis_presence/__init__.py", "")
    write_if_missing("packages/francis_forge/francis_forge/__init__.py", "")
    write_if_missing("packages/francis_connectors/francis_connectors/__init__.py", "")
    write_if_missing("packages/francis_llm/francis_llm/__init__.py", "")

    write_if_missing("policies/default.yaml", "mode: default\n")
    write_if_missing("policies/strict.yaml", "mode: strict\n")
    write_if_missing("policies/paranoia.yaml", "mode: paranoia\n")
    write_if_missing("policies/examples/home_guardian.yaml", "profile: home_guardian\n")
    write_if_missing("policies/examples/business_ops.yaml", "profile: business_ops\n")
    write_if_missing("policies/examples/dev_mode.yaml", "profile: dev_mode\n")

    for schema in [
        "schemas/events/run_started.json",
        "schemas/events/run_finished.json",
        "schemas/events/skill_executed.json",
        "schemas/events/mission_tick.json",
        "schemas/events/anomaly_detected.json",
        "schemas/events/incident_created.json",
        "schemas/api/inbox_message.json",
        "schemas/api/approval_request.json",
        "schemas/api/capability_meta.json",
    ]:
        write_if_missing(schema, "{}\n")

    write_if_missing("proto/francis_events.proto", 'syntax = "proto3";\npackage francis;\n')
    write_if_missing("proto/generate.ps1", "Write-Host 'Generate proto bindings'\n")

    write_if_missing("infra/docker-compose.yml", "version: '3.9'\nservices: {}\n")
    write_if_missing("infra/postgres/init.sql", "-- init\n")
    write_if_missing("infra/postgres/migrations/0001_init.sql", "-- migration\n")
    write_if_missing("infra/postgres/migrations/0002_audit.sql", "-- migration\n")
    write_if_missing("infra/postgres/migrations/0003_runs.sql", "-- migration\n")
    write_if_missing("infra/postgres/migrations/0004_memory_lanes.sql", "-- migration\n")
    write_if_missing("infra/redis/redis.conf", "# redis conf\n")
    write_if_missing("infra/qdrant/collections.md", "# Qdrant\n")
    write_if_missing("infra/observability/prometheus.yml", "global:\n  scrape_interval: 15s\n")
    write_if_missing("infra/observability/loki.yml", "auth_enabled: false\n")
    write_if_missing("infra/observability/grafana/provisioning.yml", "apiVersion: 1\n")
    write_if_missing("infra/observability/grafana/dashboards/francis.json", "{}\n")
    write_if_missing("infra/secrets/README.md", "# Secrets\n\nNever commit real secrets.\n")

    write_if_missing("runtime/keys/.gitkeep", "")
    write_if_missing("workspace/journals/decisions.jsonl", "")
    write_if_missing("workspace/runs/run_ledger.jsonl", "")
    write_if_missing("workspace/runs/last_run.json", "{}\n")
    write_if_missing("workspace/brain/facts.json", "{}\n")
    write_if_missing("workspace/brain/projects.json", "{}\n")
    write_if_missing("workspace/brain/procedures.json", "{}\n")
    write_if_missing("workspace/brain/lessons.jsonl", "")
    write_if_missing("workspace/presence/last_state.json", "{}\n")
    write_if_missing("workspace/presence/digests/daily.jsonl", "")
    write_if_missing("workspace/presence/digests/weekly.jsonl", "")
    write_if_missing("workspace/missions/missions.json", "{}\n")
    write_if_missing("workspace/missions/history.jsonl", "")
    write_if_missing("workspace/queue/jobs.jsonl", "")
    write_if_missing("workspace/queue/deadletter.jsonl", "")
    write_if_missing("workspace/incidents/incidents.jsonl", "")
    write_if_missing("workspace/forge/catalog.json", "{}\n")
    write_if_missing("workspace/logs/francis.log.jsonl", "")

    write_if_missing(".github/workflows/ci.yml", "name: ci\non: [push, pull_request]\njobs: {}\n")
    write_if_missing(".github/workflows/lint.yml", "name: lint\non: [push, pull_request]\njobs: {}\n")
    write_if_missing(".github/workflows/security.yml", "name: security\non: [push, pull_request]\njobs: {}\n")

    write_if_missing("services/gateway/app/main.py", "from fastapi import FastAPI\n\napp = FastAPI(title='Francis Gateway', version='0.1.0')\n")
    write_if_missing(
        "services/gateway/app/routes/health.py",
        "from fastapi import APIRouter\n\nrouter = APIRouter(tags=['health'])\n\n\n@router.get('/health')\ndef health() -> dict:\n    return {'status': 'ok'}\n",
    )
    write_if_missing("services/worker/app/main.py", "def main() -> None:\n    return None\n")
    write_if_missing("services/observer/app/main.py", "def main() -> None:\n    return None\n")
    write_if_missing("services/hud/app/main.py", "def main() -> None:\n    return None\n")
    write_if_missing(
        "services/hud/app/static/index.html",
        "<!doctype html><html><body><h1>Francis HUD</h1></body></html>\n",
    )
    write_if_missing("services/voice/app/main.py", "def main() -> None:\n    return None\n")

    write_if_missing("packages/francis_policy/francis_policy/risk_tiers.py", "from enum import Enum\n\n\nclass RiskTier(str, Enum):\n    LOW = 'low'\n    MEDIUM = 'medium'\n    HIGH = 'high'\n    CRITICAL = 'critical'\n")
    write_if_missing("packages/francis_skills/francis_skills/registry.py", "class SkillRegistry:\n    def __init__(self) -> None:\n        self._skills: dict[str, dict] = {}\n\n    def register(self, name: str, meta: dict) -> None:\n        self._skills[name] = meta\n\n    def list(self) -> list[str]:\n        return sorted(self._skills.keys())\n")
    write_if_missing("packages/francis_forge/francis_forge/spec.py", "from dataclasses import dataclass\n\n\n@dataclass\nclass CapabilitySpec:\n    name: str\n    description: str\n")
    write_if_missing("packages/francis_llm/francis_llm/router.py", "def route_model(task: str) -> str:\n    return 'local'\n")
    write_if_missing("packages/francis_llm/francis_llm/evals/golden_tasks.yaml", "tasks: []\n")
    write_if_missing("tests/evals/golden_tasks.yaml", "tasks: []\n")

    write_if_missing("tests/unit/test_policy_engine.py", "from francis_policy.risk_tiers import RiskTier\n\n\ndef test_risk_tier_enum() -> None:\n    assert RiskTier.LOW.value == 'low'\n")
    write_if_missing("tests/unit/test_registry.py", "from francis_skills.registry import SkillRegistry\n\n\ndef test_registry_registers() -> None:\n    reg = SkillRegistry()\n    reg.register('disk', {'kind': 'probe'})\n    assert reg.list() == ['disk']\n")
    write_if_missing("tests/unit/test_forge_spec.py", "from francis_forge.spec import CapabilitySpec\n\n\ndef test_forge_spec() -> None:\n    spec = CapabilitySpec(name='x', description='y')\n    assert spec.name == 'x'\n")
    write_if_missing("tests/integration/test_api_health.py", "from fastapi.testclient import TestClient\n\nfrom apps.api.main import app\n\n\ndef test_api_health() -> None:\n    c = TestClient(app)\n    r = c.get('/health')\n    assert r.status_code == 200\n")
    write_if_missing("tests/integration/test_inbox_pipeline.py", "from fastapi.testclient import TestClient\n\nfrom apps.api.main import app\n\n\ndef test_inbox_pipeline() -> None:\n    c = TestClient(app)\n    r = c.post('/inbox', json={'severity': 'info', 'title': 'hello', 'body': 'world'})\n    assert r.status_code == 200\n")

    if DRY_RUN:
        LOGGER.info("Scaffold dry-run complete.")
    else:
        LOGGER.info("Scaffold complete.")


if __name__ == "__main__":
    main()
