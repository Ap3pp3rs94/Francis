import os
import subprocess
import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repo_root_runtime_imports_without_pythonpath() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(
            """
            import francis_brain
            import francis_connectors
            import francis_core
            import francis_forge
            import francis_llm
            import francis_policy
            import francis_presence
            import francis_skills
            from uvicorn.importer import import_from_string

            assert hasattr(francis_brain, "RunLedger")
            assert hasattr(francis_core, "WorkspaceFS")
            assert hasattr(francis_forge, "CapabilitySpec")
            assert hasattr(francis_llm, "route_model")
            assert hasattr(francis_policy, "RiskTier")
            assert hasattr(francis_presence, "compose_operator_presence")
            assert hasattr(francis_skills, "SkillExecutor")

            for target in (
                "services.gateway.app.main:app",
                "services.hud.app.main:app",
                "services.orchestrator.app.main:app",
                "services.voice.app.main:app",
            ):
                import_from_string(target)
            """
        )],
        capture_output=True,
        cwd=REPO_ROOT,
        env=env,
        text=True,
    )
    assert result.returncode == 0, f"{result.stderr}\n{result.stdout}"
