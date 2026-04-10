from __future__ import annotations

import time
import zipfile
from pathlib import Path

from francis.kernel.paths import data_dir, repo_root


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

    art_dir = _art_dir()
    art_dir.mkdir(parents=True, exist_ok=True)
    zip_path = art_dir / f"{plugin_id}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file():
                z.write(p, arcname=str(Path(plugin_id) / p.relative_to(root)))

    return {"plugin_id": plugin_id, "generated_dir": str(root), "artifact_zip": str(zip_path)}
