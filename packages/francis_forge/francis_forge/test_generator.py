from __future__ import annotations

from .spec import CapabilitySpec
from .scaffold_generator import _python_module_name


def generate_test_files(spec: CapabilitySpec) -> dict[str, str]:
    module_name = _python_module_name(spec.slug)
    test_file = f"test_{module_name}.py"
    content = (
        "from __future__ import annotations\n\n"
        f"from {module_name} import run\n\n"
        "def test_run_returns_ok() -> None:\n"
        "    out = run({\"sample\": True})\n"
        "    assert out[\"status\"] == \"ok\"\n"
    )
    return {test_file: content}
