from __future__ import annotations

from pathlib import Path


def bootstrap_package(package_name: str, module_globals: dict[str, object]) -> None:
    package_root = Path(__file__).resolve().parent / "packages" / package_name / package_name
    init_path = package_root / "__init__.py"
    if not init_path.exists():
        raise ModuleNotFoundError(f"Local package source not found for {package_name!r} at {init_path}")

    module_globals["__file__"] = str(init_path)
    module_globals["__package__"] = package_name
    module_globals["__path__"] = [str(package_root)]
    exec(compile(init_path.read_text(encoding="utf-8"), str(init_path), "exec"), module_globals)
