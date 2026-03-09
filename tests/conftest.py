from __future__ import annotations

from pathlib import Path

import pytest

SLOW_TEST_FILES = {
    "test_approvals_flow.py",
    "test_autonomy_cycle.py",
    "test_autonomy_events.py",
    "test_control_surface.py",
    "test_forge_flow.py",
    "test_telemetry_pipeline.py",
    "test_tools_chain_and_forge_packs.py",
    "test_tools_runtime.py",
    "test_worker_cycle.py",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    for item in items:
        path = Path(str(item.fspath))
        parts = set(path.parts)
        name = path.name

        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
        if "redteam" in parts:
            item.add_marker(pytest.mark.redteam)
            item.add_marker(pytest.mark.slow)
        if "evals" in parts:
            item.add_marker(pytest.mark.evals)
            item.add_marker(pytest.mark.slow)
        if name in SLOW_TEST_FILES:
            item.add_marker(pytest.mark.slow)
