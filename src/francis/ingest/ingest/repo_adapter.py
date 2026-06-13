from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text

from ..shared.models import RepoMap, RepoRiskSignal
from .source import bounded_file_scan, canonical_path, is_sensitive_path

SCRIPT_EXTENSIONS = {".sh", ".ps1", ".bat", ".cmd"}
NODE_MANIFESTS = {"package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "tsconfig.json"}
PYTHON_MANIFESTS = {"pyproject.toml", "requirements.txt", "setup.py", "poetry.lock", "pytest.ini"}
RUST_MANIFESTS = {"Cargo.toml", "Cargo.lock"}
GO_MANIFESTS = {"go.mod", "go.sum"}
DOCKER_MANIFESTS = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
SOURCE_DIRS = {"src", "lib", "app", "apps", "packages", "cmd", "internal", "pkg"}
TEST_PATTERNS = (
    re.compile(r"(^|/)(tests?|specs?)/", re.IGNORECASE),
    re.compile(r"(^|/)(test_|.*(_test|\.test|\.spec)\.)", re.IGNORECASE),
)
NETWORK_HINT_RE = re.compile(
    r"\b(curl|wget|invoke-webrequest|irm|git\s+clone|npm\s+i|npm\s+install|pnpm\s+i|"
    r"pnpm\s+install|yarn\s+install|npm\s+publish|pnpm\s+publish|yarn\s+publish|"
    r"pip\s+install|docker\s+pull|docker\s+push|ssh|scp|rsync)\b",
    re.IGNORECASE,
)
DESTRUCTIVE_HINT_RE = re.compile(
    r"\b(rm\s+-rf|remove-item|del\s+/s|rmdir\s+/s|drop\s+database|terraform\s+destroy|"
    r"kubectl\s+delete|docker\s+system\s+prune)\b",
    re.IGNORECASE,
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _sorted_unique(items: list[str]) -> list[str]:
    return sorted(_unique(items))


def _add_signal(
    signals: list[RepoRiskSignal],
    *,
    signal_id: str,
    severity: str,
    path: str,
    detail: str,
) -> None:
    key = (signal_id, path)
    if any((item.id, item.path) == key for item in signals):
        return
    signals.append(RepoRiskSignal(id=signal_id, severity=severity, path=path, detail=detail))


def _git_command(root: Path, *args: str) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", f"git_metadata_unavailable:{exc.__class__.__name__}"
    if proc.returncode != 0:
        return "", "git_metadata_unavailable"
    return redact_secret_text(proc.stdout.strip()), ""


def _git_metadata(root: Path) -> tuple[dict[str, Any], list[str]]:
    if not (root / ".git").exists():
        return {}, []
    warnings: list[str] = []
    branch, err = _git_command(root, "branch", "--show-current")
    if err:
        warnings.append(err)
    head, err = _git_command(root, "rev-parse", "HEAD")
    if err and err not in warnings:
        warnings.append(err)
    remotes_raw, err = _git_command(root, "remote", "-v")
    if err and err not in warnings:
        warnings.append(err)
    status_raw, err = _git_command(root, "status", "--porcelain")
    if err and err not in warnings:
        warnings.append(err)
    remotes = _unique([line.strip() for line in remotes_raw.splitlines() if line.strip()])
    dirty_paths = [line for line in status_raw.splitlines() if line.strip()]
    return (
        {
            "branch": branch,
            "head_commit": head,
            "remotes": remotes,
            "dirty": bool(dirty_paths),
            "dirty_path_count": len(dirty_paths),
            "metadata_source": "local_git_cli_no_network",
        },
        warnings,
    )


def _package_manager(files: set[str]) -> str:
    if "pnpm-lock.yaml" in files:
        return "pnpm"
    if "yarn.lock" in files:
        return "yarn"
    return "npm"


def _package_script_command(package_manager: str, script: str) -> str:
    if package_manager == "yarn":
        return f"yarn {script}"
    if package_manager == "pnpm":
        return f"pnpm {script}"
    if script == "test":
        return "npm test"
    return f"npm run {script}"


class RepoAdapter:
    def __init__(self, *, max_files: int = 2_000) -> None:
        self.max_files = max_files

    def inspect(self, repo_root: str | Path, *, source_id: str = "") -> RepoMap:
        root = canonical_path(repo_root)
        scan = bounded_file_scan(root, max_files=self.max_files)
        files = [item.relative_path for item in scan.files]
        file_set = set(files)
        root_names = {Path(path).parts[0] for path in files if Path(path).parts}
        signals: list[RepoRiskSignal] = []
        warnings = list(scan.warnings)
        git, git_warnings = _git_metadata(root)
        warnings.extend(git_warnings)

        scripts = self._script_commands(root, file_set, signals)
        languages = self._languages(files, file_set)
        package_managers = self._package_managers(file_set)
        manifest_files = self._manifest_files(files)
        test_files = self._test_files(files)
        docs_readmes = self._docs(files)
        entrypoints = self._entrypoints(root, file_set)
        config_files = self._config_files(files)
        source_directories = sorted(name for name in root_names if name in SOURCE_DIRS)
        dependency_manifests = self._dependency_manifests(files)
        license_file = next((item for item in files if Path(item).name.lower().startswith("license")), "")
        protected_sensitive_files = self._sensitive_files(files)

        self._path_risks(files, signals, protected_sensitive_files)
        self._script_risks(scripts, signals)

        return RepoMap(
            source_id=source_id,
            repo_root=str(root),
            is_git_repo=(root / ".git").exists(),
            git=git,
            detected_languages=languages,
            package_managers=package_managers,
            manifest_files=manifest_files,
            script_commands=scripts,
            test_files=test_files,
            docs_readmes=docs_readmes,
            entrypoints=entrypoints,
            config_files=config_files,
            source_directories=source_directories,
            dependency_manifests=dependency_manifests,
            license_file=license_file,
            risk_signals=sorted(signals, key=lambda item: (item.severity, item.id, item.path)),
            suggested_validation_commands=self._suggested_validation_commands(
                package_manager=_package_manager(file_set),
                scripts=scripts,
                file_set=file_set,
                test_files=test_files,
            ),
            protected_sensitive_files=protected_sensitive_files,
            files_inspected_count=len(scan.files),
            warnings=warnings,
        )

    def _languages(self, files: list[str], file_set: set[str]) -> list[str]:
        languages: list[str] = []
        if file_set & NODE_MANIFESTS or any(Path(path).suffix in {".js", ".jsx", ".ts", ".tsx"} for path in files):
            languages.append("javascript/typescript")
        if file_set & PYTHON_MANIFESTS or any(Path(path).suffix == ".py" for path in files):
            languages.append("python")
        if file_set & RUST_MANIFESTS or any(Path(path).suffix == ".rs" for path in files):
            languages.append("rust")
        if file_set & GO_MANIFESTS or any(Path(path).suffix == ".go" for path in files):
            languages.append("go")
        if file_set & DOCKER_MANIFESTS:
            languages.append("docker")
        return _sorted_unique(languages)

    def _package_managers(self, file_set: set[str]) -> list[str]:
        managers: list[str] = []
        if "package.json" in file_set:
            managers.append("npm")
        if "pnpm-lock.yaml" in file_set:
            managers.append("pnpm")
        if "yarn.lock" in file_set:
            managers.append("yarn")
        if "pyproject.toml" in file_set:
            managers.append("python/pyproject")
        if "requirements.txt" in file_set:
            managers.append("pip")
        if "Cargo.toml" in file_set:
            managers.append("cargo")
        if "go.mod" in file_set:
            managers.append("go modules")
        return managers

    def _manifest_files(self, files: list[str]) -> list[str]:
        manifest_names = NODE_MANIFESTS | PYTHON_MANIFESTS | RUST_MANIFESTS | GO_MANIFESTS | DOCKER_MANIFESTS
        extra = {".gitignore", ".dockerignore", ".editorconfig", ".pre-commit-config.yaml"}
        return _sorted_unique([path for path in files if Path(path).name in manifest_names or Path(path).name in extra])

    def _dependency_manifests(self, files: list[str]) -> list[str]:
        names = NODE_MANIFESTS | PYTHON_MANIFESTS | RUST_MANIFESTS | GO_MANIFESTS | {"Makefile"}
        return _sorted_unique([path for path in files if Path(path).name in names])

    def _test_files(self, files: list[str]) -> list[str]:
        return _sorted_unique([path for path in files if any(pattern.search(path) for pattern in TEST_PATTERNS)])

    def _docs(self, files: list[str]) -> list[str]:
        out = []
        for path in files:
            name = Path(path).name.lower()
            if name.startswith("readme") or path.lower().startswith("docs/"):
                out.append(path)
        return _sorted_unique(out)

    def _config_files(self, files: list[str]) -> list[str]:
        config_names = {
            ".editorconfig",
            ".gitignore",
            ".pre-commit-config.yaml",
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "next.config.js",
            "next.config.mjs",
            "pytest.ini",
            "mypy.ini",
            ".ruff.toml",
            "ruff.toml",
            "alembic.ini",
            "Makefile",
        }
        out = []
        for path in files:
            name = Path(path).name
            if name in config_names or path.startswith(".github/workflows/"):
                out.append(path)
        return _sorted_unique(out)

    def _script_commands(
        self,
        root: Path,
        file_set: set[str],
        signals: list[RepoRiskSignal],
    ) -> dict[str, dict[str, str]]:
        commands: dict[str, dict[str, str]] = {}
        if "package.json" in file_set:
            package = _read_json(root / "package.json")
            scripts = package.get("scripts")
            if isinstance(scripts, dict):
                package_scripts: dict[str, str] = {}
                for key, value in sorted(scripts.items(), key=lambda item: str(item[0])):
                    script_name = _safe_str(key).strip()
                    command = redact_secret_text(_safe_str(value).strip())
                    if not script_name or not command:
                        continue
                    package_scripts[script_name] = command
                    if script_name in {"preinstall", "postinstall", "install"}:
                        signal_id = f"package_{script_name}_script" if script_name != "install" else "install_script"
                        _add_signal(
                            signals,
                            signal_id=signal_id,
                            severity="high",
                            path="package.json",
                            detail=f"package.json declares {script_name} script",
                        )
                if package_scripts:
                    commands["package.json"] = package_scripts
        if "pyproject.toml" in file_set:
            pyproject = _read_toml(root / "pyproject.toml")
            project = pyproject.get("project") if isinstance(pyproject.get("project"), dict) else {}
            scripts = project.get("scripts") if isinstance(project, dict) else {}
            if isinstance(scripts, dict):
                commands["pyproject.toml"] = {
                    _safe_str(key).strip(): redact_secret_text(_safe_str(value).strip())
                    for key, value in scripts.items()
                    if _safe_str(key).strip() and _safe_str(value).strip()
                }
        return commands

    def _entrypoints(self, root: Path, file_set: set[str]) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        if "package.json" in file_set:
            package = _read_json(root / "package.json")
            for key in ("main", "module", "bin"):
                value = package.get(key)
                if isinstance(value, str) and value.strip():
                    out.append({"source": "package.json", "kind": key, "value": redact_secret_text(value.strip())})
                elif isinstance(value, dict):
                    for name, target in sorted(value.items(), key=lambda item: str(item[0])):
                        out.append(
                            {
                                "source": "package.json",
                                "kind": f"{key}:{redact_secret_text(_safe_str(name).strip())}",
                                "value": redact_secret_text(_safe_str(target).strip()),
                            }
                        )
        if "pyproject.toml" in file_set:
            pyproject = _read_toml(root / "pyproject.toml")
            project = pyproject.get("project") if isinstance(pyproject.get("project"), dict) else {}
            scripts = project.get("scripts") if isinstance(project, dict) else {}
            if isinstance(scripts, dict):
                for name, target in sorted(scripts.items(), key=lambda item: str(item[0])):
                    out.append(
                        {
                            "source": "pyproject.toml",
                            "kind": f"console_script:{redact_secret_text(_safe_str(name).strip())}",
                            "value": redact_secret_text(_safe_str(target).strip()),
                        }
                    )
        return out

    def _sensitive_files(self, files: list[str]) -> list[dict[str, str]]:
        out = []
        for path in files:
            if is_sensitive_path(path):
                out.append({"path": path, "reason": "sensitive_name_or_extension", "contents_read": "false"})
        return out[:200]

    def _path_risks(
        self,
        files: list[str],
        signals: list[RepoRiskSignal],
        protected_sensitive_files: list[dict[str, str]],
    ) -> None:
        for path in files:
            name = Path(path).name.lower()
            suffix = Path(path).suffix.lower()
            if suffix in SCRIPT_EXTENSIONS:
                _add_signal(
                    signals,
                    signal_id="shell_script_present",
                    severity="medium",
                    path=path,
                    detail="shell or command script present; execution requires lab boundary",
                )
            if name == "dockerfile":
                _add_signal(
                    signals, signal_id="dockerfile_present", severity="medium", path=path, detail="Dockerfile present"
                )
            if name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
                _add_signal(
                    signals,
                    signal_id="compose_file_present",
                    severity="medium",
                    path=path,
                    detail="Compose file present",
                )
            if path.startswith(".github/workflows/") or name in {".gitlab-ci.yml", "azure-pipelines.yml"}:
                _add_signal(
                    signals, signal_id="ci_workflow_present", severity="medium", path=path, detail="CI workflow present"
                )
            if is_sensitive_path(path):
                _add_signal(
                    signals,
                    signal_id="env_file_present" if name.startswith(".env") else "credential_like_file_present",
                    severity="high",
                    path=path,
                    detail="sensitive-looking file detected; contents were not inspected",
                )
            if re.search(r"(^|/)(deploy|release|publish|upload|ship)[^/]*", path, re.IGNORECASE):
                _add_signal(
                    signals, signal_id="deploy_script_present", severity="high", path=path, detail="deploy-like path"
                )
            if re.search(r"(^|/)(migrations?|alembic|db/migrate)(/|$)", path, re.IGNORECASE):
                _add_signal(
                    signals,
                    signal_id="migration_script_present",
                    severity="medium",
                    path=path,
                    detail="database migration-like path",
                )
        if protected_sensitive_files:
            _add_signal(
                signals,
                signal_id="credential_like_file_present",
                severity="high",
                path="multiple" if len(protected_sensitive_files) > 1 else protected_sensitive_files[0]["path"],
                detail=f"{len(protected_sensitive_files)} sensitive-looking file(s) detected",
            )

    def _script_risks(self, scripts: dict[str, dict[str, str]], signals: list[RepoRiskSignal]) -> None:
        for manifest, commands in scripts.items():
            for name, command in commands.items():
                path = f"{manifest}#{name}"
                if NETWORK_HINT_RE.search(command):
                    _add_signal(
                        signals,
                        signal_id="network_command_hint",
                        severity="medium",
                        path=path,
                        detail="declared command contains network-related tool hints",
                    )
                if DESTRUCTIVE_HINT_RE.search(command):
                    _add_signal(
                        signals,
                        signal_id="destructive_command_hint",
                        severity="high",
                        path=path,
                        detail="declared command contains destructive command hints",
                    )
                if re.search(r"\b(deploy|publish|upload|release)\b", name + " " + command, re.IGNORECASE):
                    _add_signal(
                        signals,
                        signal_id="deploy_script_present",
                        severity="high",
                        path=path,
                        detail="declared command appears deploy or publish related",
                    )

    def _suggested_validation_commands(
        self,
        *,
        package_manager: str,
        scripts: dict[str, dict[str, str]],
        file_set: set[str],
        test_files: list[str],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        package_scripts = scripts.get("package.json", {})
        for script in ("test", "lint", "build"):
            if script in package_scripts:
                out.append(
                    {
                        "command": _package_script_command(package_manager, script),
                        "source": f"package.json#{script}",
                        "requires_execute": True,
                        "requires_network": False,
                        "lab_required": True,
                    }
                )
        if "pyproject.toml" in file_set or "pytest.ini" in file_set or any(path.endswith(".py") for path in test_files):
            out.append(
                {
                    "command": "python -m pytest",
                    "source": "python_tests_detected",
                    "requires_execute": True,
                    "requires_network": False,
                    "lab_required": True,
                }
            )
        if "Cargo.toml" in file_set:
            out.append(
                {
                    "command": "cargo test",
                    "source": "Cargo.toml",
                    "requires_execute": True,
                    "requires_network": False,
                    "lab_required": True,
                }
            )
        if "go.mod" in file_set:
            out.append(
                {
                    "command": "go test ./...",
                    "source": "go.mod",
                    "requires_execute": True,
                    "requires_network": False,
                    "lab_required": True,
                }
            )
        return out


def detect_repo(path: str | Path) -> dict[str, Any]:
    root = canonical_path(path)
    if not root.is_dir():
        return {"is_repo": False, "reason": "not_directory", "path": str(root)}
    markers = []
    strong_markers = {
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "pnpm-lock.yaml",
        "package-lock.json",
        "yarn.lock",
        "requirements.txt",
    }
    for marker in [".git", *sorted(strong_markers), "README.md"]:
        if (root / marker).exists():
            markers.append(marker)
    has_readme = bool([marker for marker in markers if marker.lower().startswith("readme")])
    has_source_dir = any((root / name).is_dir() for name in ("src", "lib", "app", "packages", "cmd", "internal"))
    is_repo = bool(".git" in markers or strong_markers.intersection(markers) or (has_readme and has_source_dir))
    return {
        "is_repo": is_repo,
        "reason": "repo_markers_detected" if is_repo else "insufficient_repo_markers",
        "path": str(root),
        "markers": markers,
        "has_source_directory": has_source_dir,
        "inspection_mode": "read_only_no_network_no_execution",
        "git_internals_read": False,
    }
