from __future__ import annotations

import argparse
import ast
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "Finding",
    "AttackSurface",
    "AttackSurfaceMapper",
    "main",
]


@dataclass(frozen=True)
class Finding:
    category: str
    severity: str
    path: str
    line: int | None = None
    message: str = ""


@dataclass
class AttackSurface:
    assets: list[str]
    entry_points: list[str]
    trust_boundaries: list[str]
    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def summarize(self) -> str:
        counts = {"high": 0, "medium": 0, "low": 0}
        for f in self.findings:
            sev = (f.severity or "low").lower()
            counts[sev] = counts.get(sev, 0) + 1
        return (
            f"AttackSurface(findings={len(self.findings)}, "
            f"high={counts.get('high', 0)}, medium={counts.get('medium', 0)}, low={counts.get('low', 0)})"
        )


class AttackSurfaceMapper:
    DEFAULT_INCLUDE = ("**/*.py", "**/*.ps1", "**/*.yaml", "**/*.yml", "**/*.json")
    DEFAULT_EXCLUDE = (
        "**/.git/**",
        "**/.venv/**",
        "**/venv/**",
        "**/__pycache__/**",
        "**/node_modules/**",
        "**/dist/**",
        "**/build/**",
    )

    def __init__(
        self,
        root: Path,
        include: tuple[str, ...] = DEFAULT_INCLUDE,
        exclude: tuple[str, ...] = DEFAULT_EXCLUDE,
    ) -> None:
        self.root = root
        self.include = include
        self.exclude = exclude

    def map(self, scenarios: list[dict[str, str]] | None = None, *, max_files: int = 5000) -> AttackSurface:
        surface = AttackSurface(assets=[], entry_points=[], trust_boundaries=[])
        files = list(_iter_files(self.root, self.include, self.exclude, max_files=max_files))
        surface.assets = [str(p.relative_to(self.root)) for p in files]

        if scenarios:
            surface.entry_points = sorted({s.get("entry_point", "") for s in scenarios if s.get("entry_point")})
            surface.trust_boundaries = sorted({s.get("boundary", "") for s in scenarios if s.get("boundary")})

        for path in files:
            self._analyze_file(path, surface)

        return surface

    def _analyze_file(self, path: Path, surface: AttackSurface) -> None:
        text = _read_text(path)
        rel = str(path.relative_to(self.root)).replace("\\", "/")

        if any(k in text.lower() for k in ("api_key", "apikey", "secret", "password", "token", "private_key")):
            surface.add(Finding(category="secrets_risk", severity="medium", path=rel, message="Keyword match"))

        if path.suffix.lower() == ".py":
            self._analyze_python(rel, text, surface)

        if path.suffix.lower() == ".ps1":
            if "Invoke-Expression" in text or "iex" in text.lower():
                surface.add(
                    Finding(
                        category="script_execution",
                        severity="medium",
                        path=rel,
                        message="PowerShell dynamic execution detected",
                    )
                )

    def _analyze_python(self, rel: str, text: str, surface: AttackSurface) -> None:
        lowered = text.lower()
        if "subprocess" in lowered or "os.system" in lowered:
            surface.add(Finding(category="process_execution", severity="medium", path=rel))
        if "socket" in lowered or "requests" in lowered or "urllib" in lowered:
            surface.add(Finding(category="network_capability", severity="medium", path=rel))

        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            surface.add(
                Finding(
                    category="syntax_error",
                    severity="low",
                    path=rel,
                    line=exc.lineno,
                    message=exc.msg,
                )
            )
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                surface.add(
                    Finding(
                        category="dynamic_code_execution",
                        severity="high",
                        path=rel,
                        line=getattr(node, "lineno", None),
                        message=f"use of {node.func.id}",
                    )
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if getattr(node.func, "attr", "") in {"run", "Popen", "call", "check_call", "check_output"}:
                    for kw in getattr(node, "keywords", []) or []:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            surface.add(
                                Finding(
                                    category="shell_execution",
                                    severity="high",
                                    path=rel,
                                    line=getattr(node, "lineno", None),
                                    message="subprocess with shell=True",
                                )
                            )


def _iter_files(root: Path, include: tuple[str, ...], exclude: tuple[str, ...], *, max_files: int) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, pat) for pat in exclude):
            continue
        if include and not any(fnmatch.fnmatch(rel, pat) for pat in include):
            continue
        out.append(path)
        if len(out) >= max_files:
            break
    return out


def _read_text(path: Path, limit_bytes: int = 2_000_000) -> str:
    data = path.read_bytes()
    if len(data) > limit_bytes:
        data = data[:limit_bytes]
    return data.decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="attack_surface_mapper")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[4]))
    parser.add_argument("--max-files", type=int, default=5000)
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    mapper = AttackSurfaceMapper(root=root)
    surface = mapper.map(max_files=args.max_files)

    print(surface.summarize())
    for finding in surface.findings[:200]:
        line = f":{finding.line}" if finding.line else ""
        print(f"[{finding.severity}] {finding.category} {finding.path}{line} {finding.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
