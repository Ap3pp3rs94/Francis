from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from francis.kernel.paths import repo_root

from .contracts import McpGatewayError, ToolResult, ToolSpec

_ALLOWED_COMMAND_KINDS = {"git_status", "pytest_targeted", "ruff_check", "mypy_targeted"}
_DEFAULT_TIMEOUT_SEC = 900


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _gateway_root() -> Path:
    override = os.environ.get("FRANCIS_MCP_GATEWAY_STATE_DIR")
    root = Path(override) if override else repo_root() / ".francis" / "mcp_gateway"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _proposal_dir() -> Path:
    path = _gateway_root() / "proposals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _receipt_dir() -> Path:
    path = _gateway_root() / "receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def _safe_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _has_shell_metacharacters(value: str) -> bool:
    return any(token in value for token in (";", "&&", "||", "|", "`", "$(", "\n", "\r"))


def _run_process(argv: list[str], *, timeout_sec: int = _DEFAULT_TIMEOUT_SEC) -> dict[str, Any]:
    started = _utc_now()
    proc = subprocess.run(
        argv,
        cwd=repo_root(),
        text=True,
        capture_output=True,
        timeout=max(1, min(int(timeout_sec), 3600)),
        check=False,
    )
    return {
        "argv": argv,
        "returncode": int(proc.returncode),
        "stdout_tail": proc.stdout[-12000:],
        "stderr_tail": proc.stderr[-12000:],
        "started_at": started,
        "finished_at": _utc_now(),
    }


def _write_receipt(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
    ).hexdigest()[:16]
    receipt = {
        "id": f"mcp-{kind}-{digest}",
        "kind": kind,
        "created_at": _utc_now(),
        "payload": payload,
    }
    path = _receipt_dir() / f"{receipt['id']}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"receipt_id": receipt["id"], "receipt_path": str(path)}


def _health() -> ToolResult:
    return ToolResult(
        ok=True,
        status="ready",
        tool="francis.health",
        data={
            "repo_root": str(repo_root()),
            "python": sys.version.split()[0],
            "gateway": "francis-mcp-gateway-v0",
            "time": _utc_now(),
        },
        governance={
            "read_only": True,
            "mutates_repo": False,
            "raw_shell": False,
            "authority": "readback",
        },
    )


def _repo_status() -> ToolResult:
    branch = _run_process(["git", "branch", "--show-current"], timeout_sec=30)
    head = _run_process(["git", "--no-pager", "log", "-1", "--oneline"], timeout_sec=30)
    status = _run_process(["git", "--no-pager", "status", "--short"], timeout_sec=30)
    dirty = bool(status["stdout_tail"].strip())

    return ToolResult(
        ok=True,
        status="ready",
        tool="francis.repo.status",
        data={
            "repo_root": str(repo_root()),
            "branch": branch["stdout_tail"].strip(),
            "head": head["stdout_tail"].strip(),
            "dirty": dirty,
            "status_short": status["stdout_tail"].splitlines()[:200],
        },
        governance={
            "read_only": True,
            "mutates_repo": False,
            "raw_shell": False,
            "authority": "readback",
        },
    )


def _git_diff(args: dict[str, Any]) -> ToolResult:
    base = _clean_text(args.get("base"), "HEAD")
    head = _clean_text(args.get("head"), "")

    if base.startswith("-") or head.startswith("-"):
        raise McpGatewayError("invalid ref")
    if _has_shell_metacharacters(base) or _has_shell_metacharacters(head):
        raise McpGatewayError("unsafe ref")

    argv = ["git", "--no-pager", "diff", "--stat"]
    if head:
        argv.append(f"{base}..{head}")
    elif base != "HEAD":
        argv.append(base)

    result = _run_process(argv, timeout_sec=60)
    ok = result["returncode"] == 0

    return ToolResult(
        ok=ok,
        status="complete" if ok else "failed",
        tool="francis.git.diff",
        data=result,
        governance={
            "read_only": True,
            "mutates_repo": False,
            "raw_shell": False,
            "authority": "readback",
        },
        error=None if ok else "git diff failed",
    )


def _validate_test_targets(raw_targets: Any) -> list[str]:
    targets = _safe_list(raw_targets)
    if not targets:
        raise McpGatewayError("targets must be a non-empty list")

    safe_targets: list[str] = []
    for target in targets:
        normalized = target.replace("\\", "/")
        if not normalized.startswith("tests/"):
            raise McpGatewayError(f"test target outside tests/: {target}")
        if _has_shell_metacharacters(target):
            raise McpGatewayError(f"unsafe test target: {target}")
        safe_targets.append(target)

    return safe_targets


def _validate_generic_targets(raw_targets: Any, *, tool_name: str) -> list[str]:
    targets = _safe_list(raw_targets)
    if not targets:
        raise McpGatewayError(f"{tool_name} requires targets")

    for target in targets:
        if target.startswith("-") or _has_shell_metacharacters(target):
            raise McpGatewayError(f"unsafe {tool_name} target: {target}")

    return targets


def _tests_run_targeted(args: dict[str, Any]) -> ToolResult:
    targets = _validate_test_targets(args.get("targets"))
    timeout_sec = int(args.get("timeout_sec") or _DEFAULT_TIMEOUT_SEC)
    argv = [sys.executable, "-m", "pytest", *targets]
    result = _run_process(argv, timeout_sec=timeout_sec)
    receipt = _write_receipt("tests-run-targeted", {"targets": targets, "result": result})
    ok = result["returncode"] == 0

    return ToolResult(
        ok=ok,
        status="passed" if ok else "failed",
        tool="francis.tests.run_targeted",
        data={**result, **receipt},
        governance={
            "read_only": False,
            "mutates_repo": False,
            "raw_shell": False,
            "authority": "bounded_pytest",
            "targets": targets,
        },
        error=None if ok else "targeted tests failed",
    )


def _command_argv(kind: str, args: dict[str, Any]) -> list[str]:
    if kind == "git_status":
        return ["git", "--no-pager", "status", "--short"]

    if kind == "pytest_targeted":
        return [sys.executable, "-m", "pytest", *_validate_test_targets(args.get("targets"))]

    if kind == "ruff_check":
        targets = _validate_generic_targets(args.get("targets"), tool_name="ruff_check")
        return [sys.executable, "-m", "ruff", "check", *targets]

    if kind == "mypy_targeted":
        targets = _validate_generic_targets(args.get("targets"), tool_name="mypy_targeted")
        return [sys.executable, "-m", "mypy", *targets]

    raise McpGatewayError(f"unsupported command kind: {kind}")


def _command_propose(args: dict[str, Any]) -> ToolResult:
    actor = _clean_text(args.get("actor"), "unknown")
    objective = _clean_text(args.get("objective"), "unspecified")
    kind = _clean_text(args.get("kind"))

    if kind not in _ALLOWED_COMMAND_KINDS:
        raise McpGatewayError(f"unsupported command kind: {kind}")

    argv = _command_argv(kind, args)
    proposal_payload = {
        "actor": actor,
        "objective": objective,
        "kind": kind,
        "argv": argv,
        "args": args,
        "created_at": _utc_now(),
    }
    proposal_id = hashlib.sha256(json.dumps(proposal_payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[
        :16
    ]
    proposal_payload["proposal_id"] = proposal_id

    proposal_path = _proposal_dir() / f"{proposal_id}.json"
    proposal_path.write_text(json.dumps(proposal_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return ToolResult(
        ok=True,
        status="approval_required",
        tool="francis.command.propose",
        data={
            "proposal_id": proposal_id,
            "proposal_path": str(proposal_path),
            "approval_phrase": f"APPROVE {proposal_id}",
            "argv_preview": argv,
        },
        governance={
            "read_only": False,
            "mutates_repo": kind != "git_status",
            "raw_shell": False,
            "authority": "manual_approval_required",
            "actor": actor,
            "objective": objective,
        },
    )


def _command_execute_approved(args: dict[str, Any]) -> ToolResult:
    proposal_id = _clean_text(args.get("proposal_id"))
    approval_phrase = _clean_text(args.get("approval_phrase"))

    if not proposal_id:
        raise McpGatewayError("proposal_id is required")

    if approval_phrase != f"APPROVE {proposal_id}":
        return ToolResult(
            ok=False,
            status="approval_required",
            tool="francis.command.execute_approved",
            data={"proposal_id": proposal_id, "expected_approval_phrase": f"APPROVE {proposal_id}"},
            governance={
                "read_only": False,
                "raw_shell": False,
                "authority": "manual_approval_required",
            },
            error="approval phrase missing or incorrect",
        )

    proposal_path = _proposal_dir() / f"{proposal_id}.json"
    if not proposal_path.exists():
        return ToolResult(
            ok=False,
            status="not_found",
            tool="francis.command.execute_approved",
            data={"proposal_id": proposal_id},
            governance={
                "read_only": False,
                "raw_shell": False,
                "authority": "proposal_required",
            },
            error="proposal not found",
        )
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    args_payload = proposal.get("args") if isinstance(proposal.get("args"), dict) else {}
    kind = _clean_text(proposal.get("kind"))
    argv = _command_argv(kind, args_payload)

    result = _run_process(argv, timeout_sec=int(args.get("timeout_sec") or _DEFAULT_TIMEOUT_SEC))
    receipt = _write_receipt("command-execute-approved", {"proposal": proposal, "result": result})
    ok = result["returncode"] == 0

    return ToolResult(
        ok=ok,
        status="complete" if ok else "failed",
        tool="francis.command.execute_approved",
        data={**result, **receipt},
        governance={
            "read_only": False,
            "raw_shell": False,
            "authority": "manual_approval_consumed",
            "proposal_id": proposal_id,
            "kind": kind,
        },
        error=None if ok else "approved command failed",
    )


def _receipts_readback(args: dict[str, Any]) -> ToolResult:
    receipt_id = _clean_text(args.get("receipt_id"))

    if not receipt_id:
        receipts = sorted(_receipt_dir().glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:20]
        return ToolResult(
            ok=True,
            status="ready",
            tool="francis.receipts.readback",
            data={"receipts": [path.stem for path in receipts]},
            governance={"read_only": True, "raw_shell": False, "authority": "readback"},
        )

    path = _receipt_dir() / f"{receipt_id}.json"
    if not path.exists():
        return ToolResult(
            ok=False,
            status="not_found",
            tool="francis.receipts.readback",
            data={"receipt_id": receipt_id},
            governance={"read_only": True, "raw_shell": False, "authority": "readback"},
            error="receipt not found",
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    return ToolResult(
        ok=True,
        status="ready",
        tool="francis.receipts.readback",
        data={"receipt": payload},
        governance={"read_only": True, "raw_shell": False, "authority": "readback"},
    )


def _screen_status(_args: dict[str, Any]) -> ToolResult:
    from francis.screen_readback.tools import screen_readback_status

    result = screen_readback_status()
    return ToolResult(
        ok=bool(result.get("ok")),
        status=_clean_text(result.get("status"), "ready"),
        tool="francis.screen.status",
        data=result,
        governance={
            "read_only": True,
            "raw_shell": False,
            "raw_input": False,
            "screenshots": False,
            "pixels": False,
            "authority": "screen_readback",
        },
        error=_clean_text(result.get("error")) or None,
    )


def _screen_session(args: dict[str, Any]) -> ToolResult:
    from francis.screen_readback.tools import session_readback

    result = session_readback(args)
    return ToolResult(
        ok=bool(result.get("ok")),
        status=_clean_text(result.get("status"), "ready"),
        tool="francis.screen.session",
        data=result,
        governance={
            "read_only": True,
            "raw_shell": False,
            "raw_input": False,
            "screenshots": False,
            "pixels": False,
            "authority": "screen_readback",
        },
        error=_clean_text(result.get("error")) or None,
    )


def _input_status(_args: dict[str, Any]) -> ToolResult:
    from francis.input_actuator.tools import input_status

    result = input_status()
    return ToolResult(
        ok=bool(result.get("ok")),
        status=_clean_text(result.get("status"), "ready"),
        tool="francis.input.status",
        data=result,
        governance={
            "read_only": True,
            "raw_shell": False,
            "authority": "input_actuator_readback",
        },
        error=_clean_text(result.get("error")) or None,
    )


def _input_propose(args: dict[str, Any]) -> ToolResult:
    from francis.input_actuator.tools import propose_input_action

    result = propose_input_action(args)
    return ToolResult(
        ok=bool(result.get("ok")),
        status=_clean_text(result.get("status"), "approval_required"),
        tool="francis.input.propose",
        data=result,
        governance={
            "read_only": False,
            "raw_shell": False,
            "authority": "manual_approval_required",
        },
        error=_clean_text(result.get("error")) or None,
    )


def _input_execute_approved(args: dict[str, Any]) -> ToolResult:
    from francis.input_actuator.tools import execute_approved_input_action

    result = execute_approved_input_action(args)
    return ToolResult(
        ok=bool(result.get("ok")),
        status=_clean_text(result.get("status"), "complete" if result.get("ok") else "blocked"),
        tool="francis.input.execute_approved",
        data=result,
        governance={
            "read_only": False,
            "raw_shell": False,
            "authority": "manual_approval_consumed" if result.get("ok") else "manual_approval_required",
        },
        error=_clean_text(result.get("error")) or None,
    )


def _input_receipts(args: dict[str, Any]) -> ToolResult:
    from francis.input_actuator.tools import input_receipts_readback

    result = input_receipts_readback(args)
    return ToolResult(
        ok=bool(result.get("ok")),
        status=_clean_text(result.get("status"), "ready"),
        tool="francis.input.receipts",
        data=result,
        governance={
            "read_only": True,
            "raw_shell": False,
            "authority": "input_actuator_readback",
        },
        error=_clean_text(result.get("error")) or None,
    )


_TOOL_SPECS = [
    ToolSpec("francis.health", "Read local Francis gateway health.", read_only=True),
    ToolSpec("francis.repo.status", "Read branch, head, and dirty state.", read_only=True),
    ToolSpec("francis.git.diff", "Read bounded git diff stat.", read_only=True),
    ToolSpec("francis.tests.run_targeted", "Run bounded pytest targets under tests/.", read_only=False),
    ToolSpec(
        "francis.command.propose",
        "Create a manual-approval command proposal.",
        read_only=False,
        requires_approval=True,
    ),
    ToolSpec(
        "francis.command.execute_approved",
        "Execute a previously approved bounded proposal.",
        read_only=False,
        requires_approval=True,
    ),
    ToolSpec("francis.receipts.readback", "Read MCP gateway receipts.", read_only=True),
    ToolSpec("francis.screen.status", "Read safe screen/session readback status.", read_only=True),
    ToolSpec("francis.screen.session", "Read bounded desktop/session context without pixels or control.", read_only=True),
    ToolSpec("francis.input.status", "Read governed input actuator status.", read_only=True),
    ToolSpec(
        "francis.input.propose",
        "Create a governed input action proposal.",
        read_only=False,
        requires_approval=True,
    ),
    ToolSpec(
        "francis.input.execute_approved",
        "Execute a previously approved governed input action.",
        read_only=False,
        requires_approval=True,
    ),
    ToolSpec("francis.input.receipts", "Read governed input actuator receipts.", read_only=True),
]

_TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], ToolResult]] = {
    "francis.health": lambda _args: _health(),
    "francis.repo.status": lambda _args: _repo_status(),
    "francis.git.diff": _git_diff,
    "francis.tests.run_targeted": _tests_run_targeted,
    "francis.command.propose": _command_propose,
    "francis.command.execute_approved": _command_execute_approved,
    "francis.receipts.readback": _receipts_readback,
    "francis.screen.status": _screen_status,
    "francis.screen.session": _screen_session,
    "francis.input.status": _input_status,
    "francis.input.propose": _input_propose,
    "francis.input.execute_approved": _input_execute_approved,
    "francis.input.receipts": _input_receipts,
}


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "read_only": spec.read_only,
            "requires_approval": spec.requires_approval,
        }
        for spec in _TOOL_SPECS
    ]


def run_tool(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return ToolResult(
            ok=False,
            status="unknown_tool",
            tool=name,
            error=f"unknown tool: {name}",
            governance={"raw_shell": False, "authority": "none"},
        ).to_dict()

    try:
        return handler(args or {}).to_dict()
    except McpGatewayError as exc:
        return ToolResult(
            ok=False,
            status="bad_request",
            tool=name,
            error=str(exc),
            governance={"raw_shell": False, "authority": "bounded_error"},
        ).to_dict()
    except subprocess.TimeoutExpired:
        return ToolResult(
            ok=False,
            status="timeout",
            tool=name,
            error="tool execution timed out",
            governance={"raw_shell": False, "authority": "bounded_timeout"},
        ).to_dict()
