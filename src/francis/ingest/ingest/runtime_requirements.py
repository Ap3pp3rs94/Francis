"""Static inference of a repo's environment/runtime requirements (observation only).

This is read-only ingest classification: it inspects the repo map plus manifest
contents to infer whether a repo would need network, Docker, nested containers, a
display, a browser, a long-running service, or external credentials to actually
run. The point (surfaced by the ScreenEnv ingest) is to classify *why* a repo is
not compatible with the default locked-down Lab -- NOT to make it run, and NOT to
weaken any Lab gate. It recommends a future specialized profile; it never grants
network or Docker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..shared.models import RepoMap

# Dependency / import tokens that imply a given requirement. Matched as
# case-insensitive substrings against manifest text and detected import lines.
_DOCKER_TOKENS = ("docker", "docker-compose", "dockerfile", "podman", "containerd")
_NESTED_CONTAINER_TOKENS = ("docker-in-docker", "dind", "sandbox", "kubernetes", "k8s", "nested container")
_DISPLAY_TOKENS = ("xfce", "x11", "wayland", "xvfb", "display", "desktop", "tkinter", "pyqt", "pygtk", "gtk")
_BROWSER_TOKENS = ("playwright", "selenium", "pyppeteer", "puppeteer", "chromium", "webdriver", "headless")
_NETWORK_TOKENS = ("requests", "httpx", "urllib3", "aiohttp", "websocket", "grpc", "socket", "paramiko")
_SERVICE_RUNTIME_TOKENS = ("fastapi", "uvicorn", "flask", "gunicorn", "django", "starlette", "tornado", "mcp")
_CREDENTIAL_TOKENS = ("openai", "huggingface_hub", "anthropic", "boto3", "google-cloud", "azure", "stripe", "api_key")

_MANIFEST_NAMES = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "Pipfile",
    "environment.yml",
)
_MAX_MANIFEST_BYTES = 256 * 1024


@dataclass(frozen=True)
class RuntimeRequirements:
    requires_network: bool = False
    requires_docker: bool = False
    requires_nested_container: bool = False
    requires_display: bool = False
    requires_browser: bool = False
    requires_service_runtime: bool = False
    requires_external_credentials: bool = False
    requires_dependency_install: bool = False
    default_lab_compatible: bool = True
    recommended_lab_profile: str = "default"
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_text(path: Path) -> str:
    try:
        if path.is_file() and path.stat().st_size <= _MAX_MANIFEST_BYTES:
            return path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return ""
    return ""


def _gather_corpus(repo_map: RepoMap) -> tuple[str, list[str]]:
    """Concatenate manifest + a bounded scan of source/test imports into one lower-cased blob."""

    root = Path(repo_map.repo_root)
    parts: list[str] = []
    sources: list[str] = []
    for name in _MANIFEST_NAMES:
        text = _read_text(root / name)
        if text:
            parts.append(text)
            sources.append(name)
    # Bounded scan of detected test files for import-level signals.
    for rel in list(repo_map.test_files)[:20]:
        text = _read_text(root / rel)
        if text:
            parts.append(text)
            sources.append(rel)
    return "\n".join(parts), sources


def _hits(corpus: str, tokens: tuple[str, ...]) -> list[str]:
    return [t for t in tokens if t in corpus]


def classify_runtime_requirements(repo_map: RepoMap) -> RuntimeRequirements:
    """Infer runtime/environment requirements for a repo. Read-only; never executes."""

    corpus, _sources = _gather_corpus(repo_map)
    risk_ids = {str(getattr(s, "id", "")).strip() for s in repo_map.risk_signals}

    docker_hits = _hits(corpus, _DOCKER_TOKENS) or (
        ["dockerfile_present"] if {"dockerfile_present", "compose_file_present"} & risk_ids else []
    )
    nested_hits = _hits(corpus, _NESTED_CONTAINER_TOKENS)
    display_hits = _hits(corpus, _DISPLAY_TOKENS)
    browser_hits = _hits(corpus, _BROWSER_TOKENS)
    network_hits = _hits(corpus, _NETWORK_TOKENS) or (
        ["network_command_hint"] if "network_command_hint" in risk_ids else []
    )
    service_hits = _hits(corpus, _SERVICE_RUNTIME_TOKENS)
    credential_hits = _hits(corpus, _CREDENTIAL_TOKENS) or (
        ["credential_like_file_present"] if "credential_like_file_present" in risk_ids else []
    )
    # Any third-party dependency manifest implies an install step (network at build).
    install_needed = bool(repo_map.dependency_manifests) or bool(
        {"pyproject.toml", "requirements.txt", "package.json", "setup.py"} & set(repo_map.manifest_files)
    )

    requires_docker = bool(docker_hits)
    requires_nested = bool(nested_hits) or requires_docker  # docker usage from inside Lab implies nesting
    requires_display = bool(display_hits)
    requires_browser = bool(browser_hits)
    requires_network = bool(network_hits) or bool(credential_hits)
    requires_service = bool(service_hits)
    requires_credentials = bool(credential_hits)

    evidence: list[str] = []
    for label, hits in (
        ("docker", docker_hits),
        ("nested_container", nested_hits),
        ("display", display_hits),
        ("browser", browser_hits),
        ("network", network_hits),
        ("service_runtime", service_hits),
        ("external_credentials", credential_hits),
    ):
        if hits:
            evidence.append(f"{label}:{','.join(sorted(set(hits))[:6])}")
    if install_needed:
        evidence.append("dependency_install_required")

    incompatible = any(
        (
            requires_docker,
            requires_nested,
            requires_display,
            requires_browser,
            requires_network,
            requires_service,
            requires_credentials,
        )
    )
    default_compatible = not incompatible

    if default_compatible:
        profile = "default"
    else:
        needs = []
        if requires_docker or requires_nested:
            needs.append("container")
        if requires_display:
            needs.append("display")
        if requires_browser:
            needs.append("browser")
        if requires_network or requires_credentials:
            needs.append("network")
        if requires_service:
            needs.append("service")
        profile = "specialized:" + "+".join(needs) if needs else "specialized"

    return RuntimeRequirements(
        requires_network=requires_network,
        requires_docker=requires_docker,
        requires_nested_container=requires_nested,
        requires_display=requires_display,
        requires_browser=requires_browser,
        requires_service_runtime=requires_service,
        requires_external_credentials=requires_credentials,
        requires_dependency_install=install_needed,
        default_lab_compatible=default_compatible,
        recommended_lab_profile=profile,
        evidence=evidence,
    )


__all__ = ["RuntimeRequirements", "classify_runtime_requirements"]
