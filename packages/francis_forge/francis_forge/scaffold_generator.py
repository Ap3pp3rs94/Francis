from __future__ import annotations

from .spec import CapabilitySpec


def _python_module_name(slug: str) -> str:
    name = slug.replace("-", "_")
    if not name:
        return "capability"
    if name[0].isdigit():
        return f"capability_{name}"
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)


def generate_stage_files(spec: CapabilitySpec) -> dict[str, str]:
    module_name = f"{_python_module_name(spec.slug)}.py"
    readme = (
        f"# {spec.name}\n\n"
        f"## Description\n{spec.description}\n\n"
        f"## Rationale\n{spec.rationale or 'N/A'}\n\n"
        f"## Risk Tier\n{spec.risk_tier}\n"
    )
    module = (
        "from __future__ import annotations\n\n"
        f"CAPABILITY_NAME = \"{spec.name}\"\n"
        f"CAPABILITY_DESCRIPTION = \"{spec.description}\"\n\n"
        "def run(payload: dict | None = None) -> dict:\n"
        "    data = payload or {}\n"
        "    return {\"status\": \"ok\", \"capability\": CAPABILITY_NAME, \"input\": data}\n"
    )
    return {
        "README.md": readme,
        module_name: module,
    }
