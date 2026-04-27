from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

from francis.kernel.paths import data_dir, repo_root
from francis.plugin_system import PluginLoader, PluginRegistry, PluginValidator


def _gen_dir() -> Path:
    return repo_root() / "plugins" / "generated"


def _art_dir() -> Path:
    return data_dir() / "artifacts" / "plugins"


def _safe_name(name: str) -> str:
    keep = []
    for ch in name.lower():
        if ch.isalnum() or ch in ("_", "-"):
            keep.append(ch)
    out = "".join(keep).strip("-_")
    return out or "plugin"


def _write_contract_spec(plugin_id: str, name: str, description: str, root: Path) -> Path:
    spec_path = root / "plugin.spec.json"
    payload = {
        "plugin_id": plugin_id,
        "name": name,
        "version": "0.1.0",
        "description": description,
        "origin": "generated",
        "entrypoint": "plugin.py",
        "risk_class": "normal",
        "capabilities": ["generated", "tool"],
        "permissions": {"scopes": ["workspace:read"]},
        "constraints": {"max_payload_bytes": 4096},
        "sandbox_profile": "default",
        "telemetry": {"audit_level": "standard", "redaction_rules": ["default"]},
        "compatibility": {"min_core_version": "0.3.0"},
        "metadata": {
            "status": "staged",
            "promotion_status": "staged",
            "auto_promoted": False,
            "next_step": "review_validate_and_explicitly_enable_before_use",
        },
        "tools": [
            {
                "tool_name": f"generated.{plugin_id}.run",
                "action": "run",
                "summary": f"Run {name}",
                "description": description or f"Execute {name}.",
                "methods": ["execute"],
                "resources": ["workspace"],
                "policy_tags": ["generated", "local_only"],
                "requires_approvals": False,
                "requires_trust_level": 0,
                "rate_limits": {"burst": 5, "window_seconds": 60},
                "idempotency": False,
                "dry_run_supported": True,
                "input_schema": {"type": "object", "additionalProperties": True},
                "output_schema": {"type": "object", "additionalProperties": True},
            }
        ],
    }
    spec_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return spec_path


def _write_registry_snapshot(spec_path: Path, root: Path) -> tuple[Path, dict]:
    loader = PluginLoader()
    spec = loader.load(spec_path)
    if spec is None:
        raise ValueError(f"failed_to_load_spec:{spec_path}")

    validation = PluginValidator().validate(spec)
    if not validation.valid:
        raise ValueError(f"invalid_spec:{validation.reason}")

    registry = PluginRegistry()
    registered = registry.register(spec)
    if not registered.valid:
        raise ValueError(f"registry_rejected:{registered.reason}")

    snapshot_path = root / "plugin.registry.json"
    registry.write_catalog(snapshot_path)
    return snapshot_path, validation.to_dict() if hasattr(validation, "to_dict") else {
        "valid": validation.valid,
        "reason": validation.reason,
        "errors": list(validation.errors),
        "warnings": list(validation.warnings),
    }


def build_plugin(name: str, description: str = "") -> dict:
    plugin_id = f"{int(time.time())}_{_safe_name(name)}"
    root = _gen_dir() / plugin_id
    root.mkdir(parents=True, exist_ok=True)

    (root / "plugin.yaml").write_text(
        f"name: {name}\\nid: {plugin_id}\\ndescription: {description}\\nentrypoint: plugin.py\\n",
        encoding="utf-8",
    )
    (root / "plugin.py").write_text(
        """\
def run(input: str) -> str:
    return f\"Plugin response: {input}\"
""",
        encoding="utf-8",
    )
    (root / "README.md").write_text(f"# {name}\\n\\n{description}\\n", encoding="utf-8")

    spec_path = _write_contract_spec(plugin_id, name, description, root)
    registry_snapshot_path, validation = _write_registry_snapshot(spec_path, root)

    art_dir = _art_dir()
    art_dir.mkdir(parents=True, exist_ok=True)
    zip_path = art_dir / f"{plugin_id}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file():
                z.write(p, arcname=str(Path(plugin_id) / p.relative_to(root)))

    return {
        "plugin_id": plugin_id,
        "generated_dir": str(root),
        "artifact_zip": str(zip_path),
        "spec_path": str(spec_path),
        "registry_snapshot": str(registry_snapshot_path),
        "validation": validation,
    }
