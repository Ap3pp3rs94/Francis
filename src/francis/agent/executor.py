from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from francis.agent import delegation as delegation_store
from francis.deliberation.planner import PlanStateMachine, create_plan, plan_from_dict, revise_plan
from francis.kernel.paths import data_dir
from francis.missions import store as mission_store

logger = logging.getLogger(__name__)

# Backward-compatible optional override for task storage path.
# If unset, storage is resolved from data_dir() at call time.
TASKS_DIR: Path | str | None = None

LOCK_FILENAME = ".lock"
RECORD_FILENAME = "record.json"

CAPABILITY_ALLOWLIST: dict[str, Callable[[dict[str, Any], str], dict[str, Any]]] = {}

__all__ = ["ExecutionResult", "Executor", "main"]


class CapabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    capability: str
    objective: str
    ok: bool
    data: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:16]}"


def _new_run_id() -> str:
    return f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"


def _payload_trace_id(payload: dict[str, Any]) -> str:
    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else {}
    sandbox = payload.get("sandbox") if isinstance(payload.get("sandbox"), dict) else {}
    receipt_sandbox = receipt.get("sandbox") if isinstance(receipt.get("sandbox"), dict) else {}
    audit_event = receipt.get("audit_event") if isinstance(receipt.get("audit_event"), dict) else {}
    sandbox_audit = sandbox.get("audit_event") if isinstance(sandbox.get("audit_event"), dict) else {}
    return (
        _safe_str(payload.get("trace_id")).strip()
        or _safe_str(payload.get("traceId")).strip()
        or _safe_str(receipt.get("trace_id")).strip()
        or _safe_str(sandbox.get("trace_id")).strip()
        or _safe_str(receipt_sandbox.get("trace_id")).strip()
        or _safe_str(audit_event.get("trace_id")).strip()
        or _safe_str(sandbox_audit.get("trace_id")).strip()
    )


def _payload_run_id(payload: dict[str, Any]) -> str:
    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else {}
    sandbox = payload.get("sandbox") if isinstance(payload.get("sandbox"), dict) else {}
    receipt_sandbox = receipt.get("sandbox") if isinstance(receipt.get("sandbox"), dict) else {}
    audit_event = receipt.get("audit_event") if isinstance(receipt.get("audit_event"), dict) else {}
    sandbox_audit = sandbox.get("audit_event") if isinstance(sandbox.get("audit_event"), dict) else {}
    return (
        _safe_str(payload.get("run_id")).strip()
        or _safe_str(payload.get("runId")).strip()
        or _safe_str(receipt.get("run_id")).strip()
        or _safe_str(sandbox.get("run_id")).strip()
        or _safe_str(receipt_sandbox.get("run_id")).strip()
        or _safe_str(audit_event.get("run_id")).strip()
        or _safe_str(sandbox_audit.get("run_id")).strip()
    )


def _payload_artifact_dir(payload: dict[str, Any]) -> str:
    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else {}
    sandbox = payload.get("sandbox") if isinstance(payload.get("sandbox"), dict) else {}
    receipt_sandbox = receipt.get("sandbox") if isinstance(receipt.get("sandbox"), dict) else {}
    audit_event = receipt.get("audit_event") if isinstance(receipt.get("audit_event"), dict) else {}
    sandbox_audit = sandbox.get("audit_event") if isinstance(sandbox.get("audit_event"), dict) else {}
    return (
        _safe_str(payload.get("artifact_dir")).strip()
        or _safe_str(payload.get("artifact_path")).strip()
        or _safe_str(receipt.get("artifact_dir")).strip()
        or _safe_str(receipt.get("artifact_path")).strip()
        or _safe_str(sandbox.get("artifact_dir")).strip()
        or _safe_str(sandbox.get("artifact_path")).strip()
        or _safe_str(receipt_sandbox.get("artifact_dir")).strip()
        or _safe_str(receipt_sandbox.get("artifact_path")).strip()
        or _safe_str(audit_event.get("artifact_dir")).strip()
        or _safe_str(sandbox_audit.get("artifact_dir")).strip()
    )


def _attach_execution_handles(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    if not _payload_trace_id(payload):
        payload["trace_id"] = _new_trace_id()
    if not _payload_run_id(payload):
        payload["run_id"] = _new_run_id()


def _payload_audit_references(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    references = {
        "trace_id": _payload_trace_id(payload),
        "run_id": _payload_run_id(payload),
        "artifact_dir": _payload_artifact_dir(payload),
    }
    return {key: value for key, value in references.items() if value}


def tasks_dir() -> Path:
    override = TASKS_DIR
    if isinstance(override, Path):
        return override
    if isinstance(override, str):
        text = override.strip()
        if text:
            return Path(text).expanduser().resolve()
    return data_dir() / "tasks"


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        text = data.decode("utf-16", errors="replace")
    elif data.startswith(b"\xef\xbb\xbf"):
        text = data.decode("utf-8-sig", errors="replace")
    elif b"\x00" in data[:200]:
        try:
            text = data.decode("utf-16", errors="replace")
        except Exception:
            text = data.decode("utf-8", errors="replace")
    else:
        text = data.decode("utf-8", errors="replace")

    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    obj = json.loads(text)
    if isinstance(obj, dict):
        return obj
    raise ValueError(f"Invalid JSON dict: {path.as_posix()}")


def _parse_iso_dt(value: str) -> datetime | None:
    try:
        s2 = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def task_dir(task_id: str) -> Path:
    return tasks_dir() / task_id


def record_path(task_id: str) -> Path:
    return task_dir(task_id) / RECORD_FILENAME


def lock_path(task_id: str) -> Path:
    return task_dir(task_id) / LOCK_FILENAME


def load_task(task_id: str) -> dict[str, Any]:
    path = record_path(task_id)
    if not path.exists():
        raise FileNotFoundError(f"Task record not found: {path.as_posix()}")
    return _read_json(path)


def save_task(task: dict[str, Any]) -> None:
    tid = _safe_str(task.get("task_id"))
    if not tid:
        raise ValueError("Task missing task_id")
    _atomic_write_json(record_path(tid), task)


def _try_acquire_lock(task_id: str, worker_id: str, *, stale_seconds: int = 3600) -> bool:
    path = lock_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            age = time.time() - path.stat().st_mtime
            if age <= stale_seconds:
                return False
            path.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            return False

    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            payload = {"worker_id": worker_id, "locked_at": _utc_now_iso()}
            os.write(fd, json.dumps(payload).encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except Exception:
        return False


def _release_lock(task_id: str) -> None:
    path = lock_path(task_id)
    try:
        if path.exists():
            path.unlink()  # type: ignore[arg-type]
    except Exception:
        pass


def _append_task_audit(task_id: str, event: str, details: dict[str, Any]) -> None:
    try:
        append = getattr(delegation_store, "_append_audit", None)
        if callable(append):
            append(task_id, event, details)
    except Exception:
        pass


def _task_mission_id(task: dict[str, Any]) -> str:
    inputs = task.get("inputs")
    if not isinstance(inputs, dict):
        return ""
    mission_id = _safe_str(inputs.get("mission_id")).strip()
    if mission_id:
        return mission_id
    meta = inputs.get("meta")
    if isinstance(meta, dict):
        return _safe_str(meta.get("mission_id")).strip()
    return ""


def _sync_task_transition_to_mission(task: dict[str, Any], *, note: str) -> None:
    mission_id = _task_mission_id(task)
    if not mission_id:
        return
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    payload = result.get("data") if isinstance(result.get("data"), dict) else {}
    result_status = _safe_str(payload.get("status")).strip().lower()
    governance = payload.get("governance") if isinstance(payload.get("governance"), dict) else {}
    mission_store.record_linked_task_transition(
        mission_id,
        _safe_str(task.get("task_id")).strip(),
        task_status=_safe_str(task.get("status")).strip(),
        result_status=result_status,
        status_reason=_safe_str(task.get("status_reason")).strip(),
        governance=governance,
        task_updated_at=_safe_str(task.get("updated_at")).strip(),
        actor=_safe_str(task.get("assigned_to")).strip() or "executor",
        note=note,
    )


def _register_capabilities() -> None:
    CAPABILITY_ALLOWLIST.setdefault("chat.summarize", _cap_chat_summarize)
    CAPABILITY_ALLOWLIST.setdefault("plan.create", _cap_plan_create)
    CAPABILITY_ALLOWLIST.setdefault("plan.revise", _cap_plan_revise)
    CAPABILITY_ALLOWLIST.setdefault("plugin.list", _cap_plugin_list)
    CAPABILITY_ALLOWLIST.setdefault("plugin.get", _cap_plugin_get)
    CAPABILITY_ALLOWLIST.setdefault("plugin.enable", _cap_plugin_enable)
    CAPABILITY_ALLOWLIST.setdefault("plugin.disable", _cap_plugin_disable)
    CAPABILITY_ALLOWLIST.setdefault("plugin.install", _cap_plugin_install)
    CAPABILITY_ALLOWLIST.setdefault("plugin.uninstall", _cap_plugin_uninstall)
    CAPABILITY_ALLOWLIST.setdefault("plugin.run", _cap_plugin_run)
    CAPABILITY_ALLOWLIST.setdefault("plugin.tool.run", _cap_plugin_tool_run)
    CAPABILITY_ALLOWLIST.setdefault("plugin.reload", _cap_plugin_reload)
    try:
        from . import supervised_exec
    except Exception as exc:
        logger.error("Failed to load supervised_exec capability: %s", exc)
    else:
        CAPABILITY_ALLOWLIST.setdefault("codex.supervised_exec", supervised_exec.run_supervised_exec)
    try:
        from . import git_push
    except Exception as exc:
        logger.error("Failed to load git.push capability: %s", exc)
    else:
        CAPABILITY_ALLOWLIST.setdefault("git.push", git_push.run_git_push)


def run_capability(capability: str, inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    _register_capabilities()
    if capability not in CAPABILITY_ALLOWLIST:
        allowed = ", ".join(sorted(CAPABILITY_ALLOWLIST.keys()))
        raise CapabilityError(f"Capability not allowed: {capability}. Allowed: {allowed}")
    return CAPABILITY_ALLOWLIST[capability](inputs, objective)


def _preview_text_file(path: Path, *, max_bytes: int, max_lines: int) -> tuple[int, str]:
    try:
        data = path.read_bytes()[: max(0, int(max_bytes))]
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            text = data.decode("utf-16", errors="replace")
        elif data.startswith(b"\xef\xbb\xbf"):
            text = data.decode("utf-8-sig", errors="replace")
        elif b"\x00" in data[:200]:
            try:
                text = data.decode("utf-16", errors="replace")
            except Exception:
                text = data.decode("utf-8", errors="replace")
        else:
            text = data.decode("utf-8", errors="replace")
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")
        lines = text.splitlines()
        preview = "\n".join(lines[: max(0, int(max_lines))])
        return len(preview.splitlines()), preview
    except Exception as exc:
        return 0, f"[error reading file] {exc}"


def _summarize_json_file(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {
        "file": path.as_posix(),
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).replace(microsecond=0).isoformat(),
        "kind": "json",
    }
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(obj, dict):
            item["keys"] = sorted(list(obj.keys()))[:50]
        elif isinstance(obj, list):
            item["kind"] = "json.list"
            item["len"] = len(obj)
        else:
            item["kind"] = "json.scalar"
            item["type"] = type(obj).__name__
    except Exception as exc:
        item["kind"] = "json.error"
        item["error"] = str(exc)
    return item


def _cap_chat_summarize(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    root_s = _safe_str(inputs.get("path", ""))
    if not root_s:
        return {
            "kind": "chat.summarize.result",
            "input_path": "",
            "files_considered": 0,
            "items": [],
            "text": "No input path provided.",
        }

    root = Path(root_s)
    if not root.exists() or not root.is_dir():
        return {
            "kind": "chat.summarize.result",
            "input_path": root_s,
            "files_considered": 0,
            "items": [],
            "text": f"Path not found or not a directory: {root_s}",
        }

    max_files = max(1, min(int(inputs.get("max_files", 10) or 10), 200))
    include_globs = inputs.get("include_globs")
    if not isinstance(include_globs, list) or not include_globs:
        include_globs = ["*.json", "*.log"]
    max_lines = max(1, min(int(inputs.get("max_log_lines", 40) or 40), 400))
    max_bytes = max(1024, min(int(inputs.get("max_log_bytes", 65536) or 65536), 1024 * 1024))

    files: list[Path] = []
    for pat in include_globs:
        try:
            files.extend(list(root.glob(str(pat))))
        except Exception:
            continue

    uniq: dict[Path, Path] = {}
    for path in files:
        try:
            uniq[path.resolve()] = path
        except Exception:
            uniq[path] = path
    files = sorted(uniq.values(), key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]

    items: list[dict[str, Any]] = []
    for path in files:
        if path.suffix.lower() == ".json":
            items.append(_summarize_json_file(path))
        else:
            preview_lines, preview = _preview_text_file(path, max_bytes=max_bytes, max_lines=max_lines)
            items.append(
                {
                    "file": path.as_posix(),
                    "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).replace(microsecond=0).isoformat(),
                    "kind": "log",
                    "preview_lines": preview_lines,
                    "preview": preview,
                }
            )

    lines = [f"Summarized {len(items)} file(s) from: {root.as_posix()}"]
    for item in items:
        kind = _safe_str(item.get("kind", ""))
        name = Path(_safe_str(item.get("file", ""))).name
        if kind == "json":
            keys = item.get("keys")
            lines.append(f"- json={name} keys={len(keys) if isinstance(keys, list) else 0}")
        else:
            lines.append(f"- log={name} lines={item.get('preview_lines')}")

    return {
        "kind": "chat.summarize.result",
        "input_path": root.as_posix(),
        "files_considered": len(items),
        "items": items,
        "text": "\n".join(lines),
        "objective": objective,
    }


def _plan_receipt_summary(plan_payload: dict[str, Any]) -> dict[str, Any]:
    steps = plan_payload.get("steps") if isinstance(plan_payload.get("steps"), list) else []
    checkpoints = plan_payload.get("checkpoints") if isinstance(plan_payload.get("checkpoints"), list) else []
    current_step = next(
        (step for step in steps if isinstance(step, dict) and _safe_str(step.get("status")).strip() == "in_progress"),
        {},
    )
    return {
        "plan_status": _safe_str(plan_payload.get("status")).strip() or None,
        "plan_current_step_id": _safe_str(current_step.get("step_id")).strip() or None,
        "plan_current_step_title": _safe_str(current_step.get("title")).strip() or None,
        "plan_step_count": len(steps),
        "plan_checkpoint_count": len(checkpoints),
    }


def _cap_plan_create(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    goal = _safe_str(inputs.get("goal", objective))
    constraints = inputs.get("constraints")
    plan = create_plan(goal, constraints if isinstance(constraints, dict) else None)
    machine = PlanStateMachine(plan)
    machine.start()
    plan_payload = plan.to_dict()
    return {
        "kind": "plan.create.result",
        "plan": plan_payload,
        **_plan_receipt_summary(plan_payload),
    }


def _cap_plan_revise(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    raw_plan = inputs.get("plan")
    reason = _safe_str(inputs.get("reason", "execution_failed"))
    if not isinstance(raw_plan, dict):
        return {"kind": "plan.revise.result", "ok": False, "error": "plan_missing"}
    plan = plan_from_dict(raw_plan)
    revised = revise_plan(plan, reason)
    plan_payload = revised.to_dict()
    return {
        "kind": "plan.revise.result",
        "ok": True,
        "plan": plan_payload,
        **_plan_receipt_summary(plan_payload),
        "objective": objective,
    }


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _safe_str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        out = int(value)
    except Exception:
        out = default
    return max(minimum, min(out, maximum))


def _coerce_tags(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    out: list[str] = []
    for raw in value:
        text = _safe_str(raw).strip()
        if text and text not in out:
            out.append(text)
    return out


def _coerce_meta(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _cap_plugin_list(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    try:
        from francis.api.routes import plugins as plugin_routes

        result = plugin_routes.list_plugins(
            limit=_coerce_int(inputs.get("limit"), 200, 1, 5000),
            offset=_coerce_int(inputs.get("offset"), 0, 0, 10_000_000),
            status=_safe_str(inputs.get("status")).strip() or None,
            enabled=inputs.get("enabled") if isinstance(inputs.get("enabled"), bool) else None,
            source_kind=_safe_str(inputs.get("source_kind")).strip() or None,
            tag=_safe_str(inputs.get("tag")).strip() or None,
            tags=_coerce_tags(inputs.get("tags")),
            search=_safe_str(inputs.get("search")).strip() or None,
        )
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.list.result"
            result["objective"] = objective
            return result
        return {"kind": "plugin.list.result", "ok": False, "error": "unexpected_result_type", "objective": objective}
    except Exception as exc:
        return {"kind": "plugin.list.result", "ok": False, "error": str(exc), "objective": objective}


def _cap_plugin_get(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    plugin_id = _safe_str(inputs.get("id") or inputs.get("plugin_id")).strip()
    if not plugin_id:
        return {"kind": "plugin.get.result", "ok": False, "error": "plugin_id_required", "objective": objective}
    try:
        from francis.api.routes import plugins as plugin_routes

        result = plugin_routes.get_plugin(id=plugin_id)
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.get.result"
            result["objective"] = objective
            return result
        return {"kind": "plugin.get.result", "ok": False, "error": "unexpected_result_type", "objective": objective}
    except Exception as exc:
        return {"kind": "plugin.get.result", "ok": False, "error": str(exc), "objective": objective}


def _cap_plugin_enable(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    plugin_id = _safe_str(inputs.get("id") or inputs.get("plugin_id")).strip()
    if not plugin_id:
        return {"kind": "plugin.enable.result", "ok": False, "error": "plugin_id_required", "objective": objective}
    try:
        from francis.api.routes import plugins as plugin_routes

        payload = plugin_routes.PluginToggleIn(
            id=plugin_id,
            reason=_safe_str(inputs.get("reason")).strip() or objective or "requested",
            meta=_coerce_meta(inputs.get("meta")),
        )
        result = plugin_routes.enable_plugin(payload)
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.enable.result"
            result["objective"] = objective
            return result
        return {"kind": "plugin.enable.result", "ok": False, "error": "unexpected_result_type", "objective": objective}
    except Exception as exc:
        return {"kind": "plugin.enable.result", "ok": False, "error": str(exc), "objective": objective}


def _cap_plugin_disable(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    plugin_id = _safe_str(inputs.get("id") or inputs.get("plugin_id")).strip()
    if not plugin_id:
        return {"kind": "plugin.disable.result", "ok": False, "error": "plugin_id_required", "objective": objective}
    try:
        from francis.api.routes import plugins as plugin_routes

        payload = plugin_routes.PluginToggleIn(
            id=plugin_id,
            reason=_safe_str(inputs.get("reason")).strip() or objective or "requested",
            meta=_coerce_meta(inputs.get("meta")),
        )
        result = plugin_routes.disable_plugin(payload)
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.disable.result"
            result["objective"] = objective
            return result
        return {"kind": "plugin.disable.result", "ok": False, "error": "unexpected_result_type", "objective": objective}
    except Exception as exc:
        return {"kind": "plugin.disable.result", "ok": False, "error": str(exc), "objective": objective}


def _cap_plugin_install(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    source_kind = _safe_str(inputs.get("source_kind")).strip()
    source_ref = _safe_str(inputs.get("source_ref")).strip()
    if not source_kind:
        return {"kind": "plugin.install.result", "ok": False, "error": "source_kind_required", "objective": objective}
    if not source_ref:
        return {"kind": "plugin.install.result", "ok": False, "error": "source_ref_required", "objective": objective}

    capabilities = inputs.get("capabilities")
    cap_list = [item for item in capabilities if isinstance(item, dict)] if isinstance(capabilities, list) else []

    try:
        from francis.api.routes import plugins as plugin_routes

        payload = plugin_routes.PluginInstallIn(
            source_kind=source_kind,
            source_ref=source_ref,
            version=_safe_str(inputs.get("version")).strip() or None,
            ref=_safe_str(inputs.get("ref")).strip() or None,
            sha256=_safe_str(inputs.get("sha256")).strip() or None,
            capabilities=cap_list,
            reason=_safe_str(inputs.get("reason")).strip() or objective or "requested",
            dry_run=_coerce_bool(inputs.get("dry_run"), default=False),
            force=_coerce_bool(inputs.get("force"), default=False),
            meta=_coerce_meta(inputs.get("meta")),
        )
        result = plugin_routes.install_plugin(payload)
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.install.result"
            result["objective"] = objective
            return result
        return {"kind": "plugin.install.result", "ok": False, "error": "unexpected_result_type", "objective": objective}
    except Exception as exc:
        return {"kind": "plugin.install.result", "ok": False, "error": str(exc), "objective": objective}


def _cap_plugin_uninstall(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    plugin_id = _safe_str(inputs.get("id") or inputs.get("plugin_id")).strip()
    if not plugin_id:
        return {"kind": "plugin.uninstall.result", "ok": False, "error": "plugin_id_required", "objective": objective}
    try:
        from francis.api.routes import plugins as plugin_routes

        payload = plugin_routes.PluginUninstallIn(
            id=plugin_id,
            reason=_safe_str(inputs.get("reason")).strip() or objective or "requested",
            force=_coerce_bool(inputs.get("force"), default=False),
            meta=_coerce_meta(inputs.get("meta")),
        )
        result = plugin_routes.uninstall_plugin(payload)
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.uninstall.result"
            result["objective"] = objective
            return result
        return {
            "kind": "plugin.uninstall.result",
            "ok": False,
            "error": "unexpected_result_type",
            "objective": objective,
        }
    except Exception as exc:
        return {"kind": "plugin.uninstall.result", "ok": False, "error": str(exc), "objective": objective}


def _cap_plugin_run(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    plugin_id = _safe_str(inputs.get("id") or inputs.get("plugin_id")).strip()
    if not plugin_id:
        return {"kind": "plugin.run.result", "ok": False, "error": "plugin_id_required", "objective": objective}
    action = _safe_str(inputs.get("action")).strip() or "run"
    run_input = inputs["input"] if "input" in inputs else inputs.get("payload")
    approval_id = _safe_str(inputs.get("approval_id")).strip()
    meta = _coerce_meta(inputs.get("meta"))
    if approval_id and "approval_id" not in meta:
        meta["approval_id"] = approval_id
    try:
        from francis.api.routes import plugins as plugin_routes

        payload = plugin_routes.PluginRunIn(
            id=plugin_id,
            action=action,
            input=run_input,
            reason=_safe_str(inputs.get("reason")).strip() or objective or "requested",
            approval_id=approval_id or None,
            idempotency_key=_safe_str(inputs.get("idempotency_key")).strip() or None,
            meta=meta,
        )
        result = plugin_routes.run_plugin(payload)
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.run.result"
            result["objective"] = objective
            return result
        return {"kind": "plugin.run.result", "ok": False, "error": "unexpected_result_type", "objective": objective}
    except Exception as exc:
        return {"kind": "plugin.run.result", "ok": False, "error": str(exc), "objective": objective}


def _cap_plugin_tool_run(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    tool_id = _safe_str(inputs.get("tool_id") or inputs.get("id")).strip()
    if not tool_id:
        return {"kind": "plugin.tool.run.result", "ok": False, "error": "tool_id_required", "objective": objective}
    run_input = inputs["input"] if "input" in inputs else inputs.get("payload")
    approval_id = _safe_str(inputs.get("approval_id")).strip()
    meta = _coerce_meta(inputs.get("meta"))
    if approval_id and "approval_id" not in meta:
        meta["approval_id"] = approval_id
    try:
        from francis.api.routes import plugins as plugin_routes

        payload = plugin_routes.PluginToolRunIn(
            id=tool_id,
            input=run_input,
            reason=_safe_str(inputs.get("reason")).strip() or objective or "requested",
            approval_id=approval_id or None,
            idempotency_key=_safe_str(inputs.get("idempotency_key")).strip() or None,
            meta=meta,
        )
        result = plugin_routes.run_plugin_tool(payload)
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.tool.run.result"
            result["objective"] = objective
            return result
        return {
            "kind": "plugin.tool.run.result",
            "ok": False,
            "error": "unexpected_result_type",
            "objective": objective,
        }
    except Exception as exc:
        return {"kind": "plugin.tool.run.result", "ok": False, "error": str(exc), "objective": objective}


def _cap_plugin_reload(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    del inputs
    try:
        from francis.api.routes import plugins as plugin_routes

        result = plugin_routes.reload_plugins()
        if isinstance(result, dict):
            result = dict(result)
            result["kind"] = "plugin.reload.result"
            result["objective"] = objective
            return result
        return {"kind": "plugin.reload.result", "ok": False, "error": "unexpected_result_type", "objective": objective}
    except Exception as exc:
        return {"kind": "plugin.reload.result", "ok": False, "error": str(exc), "objective": objective}


def _is_expired(task: dict[str, Any]) -> bool:
    ttl = task.get("ttl_sec")
    if ttl is None:
        return False
    try:
        ttl_i = int(ttl)
        if ttl_i <= 0:
            return False
    except Exception:
        return False
    created = _parse_iso_dt(_safe_str(task.get("created_at", ""))) or _parse_iso_dt(
        _safe_str(task.get("updated_at", ""))
    )
    if not created:
        return False
    return (datetime.now(UTC) - created).total_seconds() > ttl_i


def execute_task(task_id: str, worker_id: str) -> dict[str, Any]:
    task = load_task(task_id)
    if task.get("status") in ("complete", "failed", "canceled"):
        return task

    if _is_expired(task):
        task["updated_at"] = _utc_now_iso()
        task["status"] = "failed"
        task["status_reason"] = "expired_ttl"
        task["assigned_to"] = worker_id
        task["attempts"] = int(task.get("attempts", 0) or 0) + 1
        save_task(task)
        _append_task_audit(
            task_id, "status_updated", {"to": "failed", "assigned_to": worker_id, "reason": "expired_ttl"}
        )
        return task

    capability = _safe_str(task.get("capability", ""))
    objective = _safe_str(task.get("objective", ""))
    inputs = task.get("inputs")
    if not capability or not isinstance(inputs, dict):
        task["updated_at"] = _utc_now_iso()
        task["status"] = "failed"
        task["status_reason"] = "invalid_inputs"
        task["assigned_to"] = worker_id
        task["attempts"] = int(task.get("attempts", 0) or 0) + 1
        save_task(task)
        _append_task_audit(
            task_id, "status_updated", {"to": "failed", "assigned_to": worker_id, "reason": "invalid_inputs"}
        )
        return task

    _register_capabilities()
    if capability not in CAPABILITY_ALLOWLIST:
        task["updated_at"] = _utc_now_iso()
        task["status"] = "failed"
        task["status_reason"] = f"capability_not_allowed:{capability}"
        task["assigned_to"] = worker_id
        task["attempts"] = int(task.get("attempts", 0) or 0) + 1
        task["result"] = {
            "kind": "task.result",
            "task_id": task_id,
            "capability": capability,
            "objective": objective,
            "started_at": task["updated_at"],
            "finished_at": task["updated_at"],
            "ok": False,
            "data": {"kind": "error", "error": f"capability_not_allowed:{capability}"},
        }
        save_task(task)
        _append_task_audit(
            task_id,
            "status_updated",
            {"to": "failed", "assigned_to": worker_id, "reason": f"capability_not_allowed:{capability}"},
        )
        return task

    started = _utc_now_iso()
    task["updated_at"] = started
    task["status"] = "running"
    task["assigned_to"] = worker_id
    task["status_reason"] = None
    save_task(task)
    _append_task_audit(task_id, "status_updated", {"to": "running", "assigned_to": worker_id, "reason": None})
    _sync_task_transition_to_mission(task, note="task_started")

    ok = True
    payload: dict[str, Any] | None = None
    status_reason: str | None = None
    try:
        payload = run_capability(capability, dict(inputs), objective)
    except Exception as exc:
        ok = False
        status_reason = f"{type(exc).__name__}: {exc}"
        payload = {"kind": "error", "capability": capability, "objective": objective, "error": status_reason}
    if ok and isinstance(payload, dict) and payload.get("ok") is False:
        ok = False
        status_reason = _safe_str(payload.get("error") or payload.get("status") or "capability_failed")
    _attach_execution_handles(payload)

    finished = _utc_now_iso()
    task = load_task(task_id)
    task["updated_at"] = finished
    task["attempts"] = int(task.get("attempts", 0) or 0) + 1
    task["status"] = "complete" if ok else "failed"
    task["status_reason"] = status_reason if not ok else None
    if not ok:
        try:
            raw_plan = inputs.get("plan")
            if isinstance(raw_plan, dict):
                revised = revise_plan(plan_from_dict(raw_plan), status_reason or "execution_failed")
                if isinstance(payload, dict):
                    payload["plan_revision"] = revised.to_dict()
        except Exception as exc:
            logger.error("Plan revision failed: %s", exc)
    task["result"] = {
        "kind": "task.result",
        "task_id": task_id,
        "capability": capability,
        "objective": objective,
        "started_at": started,
        "finished_at": finished,
        "ok": ok,
        "data": payload,
    }
    save_task(task)
    audit_details = {"to": task["status"], "assigned_to": worker_id, "reason": task["status_reason"]}
    audit_details.update(_payload_audit_references(payload))
    _append_task_audit(task_id, "status_updated", audit_details)
    payload_status = ""
    if isinstance(payload, dict):
        payload_status = _safe_str(payload.get("status")).strip().lower()
    if payload_status not in {"pending", "needs_approval", "blocked", "denied"}:
        _sync_task_transition_to_mission(task, note="task_finished")
    return task


def _iter_task_ids() -> list[str]:
    root = tasks_dir()
    if not root.exists():
        return []
    return [d.name for d in root.iterdir() if d.is_dir() and (d / RECORD_FILENAME).exists()]


def _is_runnable(task: dict[str, Any]) -> bool:
    if _safe_str(task.get("status", "")) not in ("pending", ""):
        return False
    capability = _safe_str(task.get("capability", ""))
    if not capability:
        return False
    _register_capabilities()
    if capability not in CAPABILITY_ALLOWLIST:
        return False
    if _is_expired(task):
        return False
    return True


def pick_next_task_id() -> str | None:
    candidates: list[tuple[int, str, str]] = []
    for tid in _iter_task_ids():
        try:
            task = load_task(tid)
        except Exception:
            continue
        if not _is_runnable(task):
            continue
        pr = int(task.get("priority", 0) or 0)
        upd = _safe_str(task.get("updated_at", ""))
        candidates.append((pr, upd, tid))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def cmd_run_once(args: argparse.Namespace) -> int:
    tid = _safe_str(args.task_id)
    worker = _safe_str(args.worker_id) or "worker"
    if not tid:
        print(json.dumps({"ok": False, "error": "missing_task_id"}, indent=2))
        return 2
    if not _try_acquire_lock(tid, worker):
        print(json.dumps({"ok": False, "task_id": tid, "error": "locked"}, indent=2))
        return 3
    try:
        record = execute_task(task_id=tid, worker_id=worker)
        print(json.dumps(record, indent=2, ensure_ascii=False, default=str))
        return 0 if record.get("status") == "complete" else 1
    finally:
        _release_lock(tid)


def cmd_work(args: argparse.Namespace) -> int:
    worker = _safe_str(args.worker_id) or "worker"
    poll_ms = max(100, int(args.poll_ms))
    idle_limit = max(1, int(args.idle_cycles))
    print_records = bool(args.print_records)

    idle = 0
    while True:
        tid = pick_next_task_id()
        if not tid:
            idle += 1
            if idle >= idle_limit:
                return 0
            time.sleep(poll_ms / 1000.0)
            continue

        if not _try_acquire_lock(tid, worker):
            time.sleep(poll_ms / 1000.0)
            continue

        try:
            record = execute_task(task_id=tid, worker_id=worker)
            if print_records:
                print(json.dumps(record, indent=2, ensure_ascii=False, default=str))
        finally:
            _release_lock(tid)


class Executor:
    def run_once(self, task_id: str, *, worker_id: str = "worker") -> ExecutionResult:
        record = execute_task(task_id=task_id, worker_id=worker_id)
        result = record.get("result") or {}
        return ExecutionResult(
            task_id=str(record.get("task_id", task_id)),
            capability=str(record.get("capability", "")),
            objective=str(record.get("objective", "")),
            ok=bool(result.get("ok")),
            data=result,
        )

    def work(self, *, poll_ms: int = 1000, idle_cycles: int = 5, worker_id: str = "worker") -> int:
        args = argparse.Namespace(poll_ms=poll_ms, idle_cycles=idle_cycles, worker_id=worker_id, print_records=False)
        return cmd_work(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="executor")
    parser.add_argument("--worker-id", default="worker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_once = sub.add_parser("run-once")
    run_once.add_argument("--task-id", required=True)
    run_once.set_defaults(fn=cmd_run_once)

    work = sub.add_parser("work")
    work.add_argument("--poll-ms", type=int, default=1000)
    work.add_argument("--idle-cycles", type=int, default=5)
    work.add_argument("--print-records", action="store_true")
    work.set_defaults(fn=cmd_work)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
