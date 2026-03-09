from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from francis_core.workspace_fs import WorkspaceFS

from .contracts import SkillCall, SkillResult, SkillSpec
from .registry import SkillRegistry
from .toolbelt.files import workspace_read, workspace_search, workspace_write
from .toolbelt.git import repo_diff, repo_status
from .toolbelt.shell import run_pytest, run_ruff
from .validator import validate_args

SkillHandler = Callable[[dict[str, Any], WorkspaceFS, Path], dict[str, Any]]


def build_default_registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register_spec(
        SkillSpec(
            name="workspace.read",
            description="Read text from a file in workspace scope.",
            risk_tier="low",
            mutating=False,
            args_schema={"path": "str", "max_chars": "optional:int"},
            tags=["workspace", "read"],
        )
    )
    registry.register_spec(
        SkillSpec(
            name="workspace.search",
            description="Search text across workspace files.",
            risk_tier="low",
            mutating=False,
            args_schema={"query": "str", "path": "optional:str", "max_hits": "optional:int"},
            tags=["workspace", "search"],
        )
    )
    registry.register_spec(
        SkillSpec(
            name="workspace.write",
            description="Write or append text to a workspace file.",
            risk_tier="medium",
            mutating=True,
            args_schema={"path": "str", "content": "str", "append": "optional:bool"},
            tags=["workspace", "write"],
        )
    )
    registry.register_spec(
        SkillSpec(
            name="repo.status",
            description="Get git status for the current repository.",
            risk_tier="low",
            mutating=False,
            args_schema={},
            tags=["repo", "git"],
        )
    )
    registry.register_spec(
        SkillSpec(
            name="repo.diff",
            description="Get git diff output for current repository.",
            risk_tier="low",
            mutating=False,
            args_schema={"path": "optional:str", "max_chars": "optional:int"},
            tags=["repo", "git"],
        )
    )
    registry.register_spec(
        SkillSpec(
            name="repo.tests",
            description="Run pytest in the repository using fast/full lanes.",
            risk_tier="low",
            mutating=False,
            args_schema={
                "lane": "optional:str",
                "target": "optional:str",
                "max_failures": "optional:int",
                "quiet": "optional:bool",
            },
            tags=["repo", "tests"],
        )
    )
    registry.register_spec(
        SkillSpec(
            name="repo.lint",
            description="Run ruff check in the repository.",
            risk_tier="low",
            mutating=False,
            args_schema={"target": "optional:str"},
            tags=["repo", "lint"],
        )
    )
    return registry


def _workspace_read_handler(args: dict[str, Any], fs: WorkspaceFS, _repo_root: Path) -> dict[str, Any]:
    return workspace_read(
        fs,
        path=str(args.get("path", "")),
        max_chars=int(args.get("max_chars", 20000)),
    )


def _workspace_search_handler(args: dict[str, Any], fs: WorkspaceFS, _repo_root: Path) -> dict[str, Any]:
    return workspace_search(
        fs,
        query=str(args.get("query", "")),
        path=str(args.get("path", ".")),
        max_hits=int(args.get("max_hits", 20)),
    )


def _workspace_write_handler(args: dict[str, Any], fs: WorkspaceFS, _repo_root: Path) -> dict[str, Any]:
    return workspace_write(
        fs,
        path=str(args.get("path", "")),
        content=str(args.get("content", "")),
        append=bool(args.get("append", False)),
    )


def _repo_status_handler(_args: dict[str, Any], _fs: WorkspaceFS, repo_root: Path) -> dict[str, Any]:
    return repo_status(repo_root)


def _repo_diff_handler(args: dict[str, Any], _fs: WorkspaceFS, repo_root: Path) -> dict[str, Any]:
    return repo_diff(
        repo_root,
        path=str(args.get("path", "")),
        max_chars=int(args.get("max_chars", 12000)),
    )


def _repo_tests_handler(args: dict[str, Any], _fs: WorkspaceFS, repo_root: Path) -> dict[str, Any]:
    return run_pytest(
        repo_root,
        lane=str(args.get("lane", "full")),
        target=str(args.get("target", "")),
        max_failures=int(args.get("max_failures", 1)),
        quiet=bool(args.get("quiet", True)),
    )


def _repo_lint_handler(args: dict[str, Any], _fs: WorkspaceFS, repo_root: Path) -> dict[str, Any]:
    return run_ruff(repo_root, target=str(args.get("target", ".")))


HANDLERS: dict[str, SkillHandler] = {
    "workspace.read": _workspace_read_handler,
    "workspace.search": _workspace_search_handler,
    "workspace.write": _workspace_write_handler,
    "repo.status": _repo_status_handler,
    "repo.diff": _repo_diff_handler,
    "repo.tests": _repo_tests_handler,
    "repo.lint": _repo_lint_handler,
}


class SkillExecutor:
    def __init__(self, *, registry: SkillRegistry, fs: WorkspaceFS, repo_root: Path) -> None:
        self.registry = registry
        self.fs = fs
        self.repo_root = repo_root

    @classmethod
    def with_defaults(cls, *, fs: WorkspaceFS, repo_root: Path) -> SkillExecutor:
        return cls(registry=build_default_registry(), fs=fs, repo_root=repo_root)

    def execute(self, call: SkillCall) -> SkillResult:
        spec = self.registry.get(call.name)
        if spec is None:
            return SkillResult(ok=False, error=f"unknown skill: {call.name}")

        valid, reason = validate_args(spec, call.args)
        if not valid:
            return SkillResult(ok=False, error=reason)

        handler = HANDLERS.get(call.name)
        if handler is None:
            return SkillResult(ok=False, error=f"handler missing: {call.name}")

        try:
            output = handler(call.args, self.fs, self.repo_root)
            return SkillResult(
                ok=True,
                output=output,
                receipts={
                    "skill": spec.name,
                    "risk_tier": spec.risk_tier,
                    "mutating": spec.mutating,
                    "requires_approval": spec.requires_approval,
                },
            )
        except Exception as exc:
            return SkillResult(ok=False, error=str(exc))
