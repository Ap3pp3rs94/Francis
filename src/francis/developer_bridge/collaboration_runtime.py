from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from francis.kernel.paths import data_dir, repo_root

from .agents import collaboration_agents_status


ProcessInfo = dict[str, object]


@dataclass(frozen=True)
class RuntimeSpec:
    name: str
    argv: tuple[str, ...]
    required_fragments: tuple[str, ...]
    log_name: str


def desired_runtime_specs() -> list[RuntimeSpec]:
    py = _runtime_python_executable()
    return [
        RuntimeSpec(
            name="codex_ollama_responder",
            argv=(
                py,
                "-u",
                "-m",
                "francis.developer_bridge.codex_responder",
                "--watch",
                "--ignore-existing",
                "--source-agent",
                "ollama",
                "--poll-seconds",
                "2",
                "--cooldown-seconds",
                "0",
            ),
            required_fragments=(
                "francis.developer_bridge.codex_responder",
                "--source-agent",
                "ollama",
                "--cooldown-seconds",
                "0",
            ),
            log_name="codex_ollama_responder.log",
        ),
        RuntimeSpec(
            name="ollama_codex_participant",
            argv=(
                py,
                "-u",
                "-m",
                "francis.developer_bridge.ollama_participant",
                "--watch",
                "--ignore-existing",
                "--source-agent",
                "codex",
                "--poll-seconds",
                "2",
                "--cooldown-seconds",
                "0",
            ),
            required_fragments=(
                "francis.developer_bridge.ollama_participant",
                "--source-agent",
                "codex",
                "--cooldown-seconds",
                "0",
            ),
            log_name="ollama_codex_participant.log",
        ),
        RuntimeSpec(
            name="codex_ollama_conversation_driver",
            argv=(
                py,
                "-u",
                "-m",
                "francis.developer_bridge.collaboration_driver",
                "--watch",
                "--ignore-existing",
                "--poll-seconds",
                "5",
                "--max-turns",
                "0",
                "--turn-gap-seconds",
                "30",
                "--summary-every-turns",
                "6",
                "--repeat-closed",
                "--session-gap-seconds",
                "10",
            ),
            required_fragments=(
                "francis.developer_bridge.collaboration_driver",
                "--max-turns",
                "0",
                "--turn-gap-seconds",
                "30",
                "--repeat-closed",
            ),
            log_name="codex_ollama_conversation_driver.log",
        ),
    ]


def _runtime_python_executable() -> str:
    root = repo_root()
    venv_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def ensure_collaboration_runtime_once(
    *,
    process_listing: Sequence[ProcessInfo] | None = None,
    starter: Callable[[RuntimeSpec], int] | None = None,
) -> dict[str, object]:
    specs = desired_runtime_specs()
    processes = list(process_listing) if process_listing is not None else _iter_python_processes()
    start = starter or _start_process
    items: list[dict[str, object]] = []

    for spec in specs:
        matches = _matching_processes(spec, processes)
        if matches:
            items.append(
                {
                    "name": spec.name,
                    "status": "running",
                    "pids": [match["pid"] for match in matches],
                    "command": _command_display(spec.argv),
                    "log_path": str(_log_path(spec)),
                }
            )
            continue

        pid = start(spec)
        items.append(
            {
                "name": spec.name,
                "status": "started",
                "pids": [pid],
                "command": _command_display(spec.argv),
                "log_path": str(_log_path(spec)),
            }
        )

    result = {
        "ok": True,
        "kind": "developer_bridge.collaboration_runtime_supervisor",
        "generated_at": _now(),
        "repo_root": str(repo_root()),
        "desired_count": len(specs),
        "processes": items,
        "governance": _governance(),
    }
    _write_state(result)
    return result


def read_collaboration_runtime_health(
    *,
    process_listing: Sequence[ProcessInfo] | None = None,
) -> dict[str, object]:
    specs = desired_runtime_specs()
    processes = list(process_listing) if process_listing is not None else _iter_python_processes()
    helper_items = [_helper_readback_item(spec, _matching_processes(spec, processes)) for spec in specs]
    supervisor_state = _read_json(_state_path(), expected_kind="developer_bridge.collaboration_runtime_supervisor")
    driver_state = _read_json(_driver_state_path(), expected_kind="developer_bridge.collaboration_driver_state")
    agents = collaboration_agents_status()
    enabled_agents = [
        item for item in _list(agents.get("agents")) if isinstance(item, dict) and bool(item.get("enabled"))
    ]
    all_helpers_running = all(item["running"] for item in helper_items)
    loop = _collaboration_loop_readback(driver_state)
    health_status = "healthy" if all_helpers_running and driver_state else "degraded"
    return {
        "kind": "developer_bridge.collaboration_runtime_health",
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.collaboration_runtime",
        "status": health_status,
        "generated_at": _now(),
        "desired_count": len(specs),
        "helper_count": len(helper_items),
        "helpers": helper_items,
        "supervisor": {
            "state_observed": bool(supervisor_state),
            "state_path": _display_path(_state_path()),
            "generated_at": _safe_str(supervisor_state.get("generated_at")),
            "age_seconds": _age_seconds(_safe_str(supervisor_state.get("generated_at"))),
        },
        "collaboration_loop": loop,
        "participants": {
            "enabled_count": len(enabled_agents),
            "total_count": _safe_int(agents.get("agent_count"), default=len(_list(agents.get("agents")))),
            "items": [
                {
                    "agent": _safe_str(item.get("agent")),
                    "label": _safe_str(item.get("label")),
                    "enabled": bool(item.get("enabled")),
                    "authority": _safe_str(item.get("authority")),
                }
                for item in _list(agents.get("agents"))
                if isinstance(item, dict)
            ],
        },
        "governance": _health_governance(),
    }


def _helper_readback_item(spec: RuntimeSpec, matches: list[ProcessInfo]) -> dict[str, object]:
    process_readback = _process_readback(matches)
    return {
        "name": spec.name,
        "status": "running" if matches else "missing",
        "running": bool(matches),
        "pids": process_readback["pids"],
        "process_count": process_readback["process_count"],
        "process_model": process_readback["process_model"],
        "effective_worker_count": process_readback["effective_worker_count"],
        "effective_pids": process_readback["effective_pids"],
        "wrapper_process_count": process_readback["wrapper_process_count"],
        "wrapper_pids": process_readback["wrapper_pids"],
        "processes": process_readback["processes"],
        "required_fragments": list(spec.required_fragments),
        "command": _command_display(spec.argv),
        "log_path": str(_log_path(spec)),
        "starts_arbitrary_commands": False,
    }


def _process_readback(matches: list[ProcessInfo]) -> dict[str, object]:
    ordered = sorted(matches, key=_process_pid)
    child_parent_pids = {
        _process_parent_pid(match)
        for match in ordered
        if _process_parent_pid(match) > 0
        and any(_process_pid(other) == _process_parent_pid(match) for other in ordered)
    }
    processes: list[dict[str, object]] = []
    for match in ordered:
        pid = _process_pid(match)
        parent_pid = _process_parent_pid(match)
        role = "launcher_wrapper" if pid in child_parent_pids else "effective_worker"
        processes.append({"pid": pid, "parent_pid": parent_pid, "role": role})

    pids = [item["pid"] for item in processes if isinstance(item.get("pid"), int) and item.get("pid")]
    effective_pids = [item["pid"] for item in processes if item.get("role") == "effective_worker"]
    wrapper_pids = [item["pid"] for item in processes if item.get("role") == "launcher_wrapper"]
    process_model = _process_model(len(pids), len(wrapper_pids), len(effective_pids))
    return {
        "pids": pids,
        "process_count": len(pids),
        "process_model": process_model,
        "effective_worker_count": len(effective_pids),
        "effective_pids": effective_pids,
        "wrapper_process_count": len(wrapper_pids),
        "wrapper_pids": wrapper_pids,
        "processes": processes,
    }


def _process_model(process_count: int, wrapper_count: int, worker_count: int) -> str:
    if process_count <= 0:
        return "unmatched"
    if wrapper_count > 0 and worker_count > 0:
        return "wrapper_child_pair"
    if process_count == 1 and worker_count == 1:
        return "single_process"
    return "multiple_effective_workers"


def _process_pid(process: ProcessInfo) -> int:
    return _safe_int(process.get("pid") or process.get("ProcessId"), default=0)


def _process_parent_pid(process: ProcessInfo) -> int:
    return _safe_int(process.get("parent_pid") or process.get("ParentProcessId") or process.get("ppid"), default=0)


def _collaboration_loop_readback(driver_state: dict[str, object]) -> dict[str, object]:
    waiting = bool(driver_state.get("waiting_for_ollama"))
    remaining = _turn_gap_remaining_seconds(_safe_str(driver_state.get("next_prompt_after")))
    recurrence_state = "waiting_for_ollama" if waiting else "turn_gap" if remaining > 0 else "ready_for_next_prompt"
    participant_state = _read_json(
        _ollama_participant_state_path(),
        expected_kind="developer_bridge.ollama_participant_state",
    )
    return {
        "state_observed": bool(driver_state),
        "state_path": _display_path(_driver_state_path()),
        "turn_count": _safe_int(driver_state.get("turn_count"), default=0),
        "recurrence_state": recurrence_state,
        "waiting_for_ollama": waiting,
        "last_codex_prompt_id": _safe_str(driver_state.get("last_codex_prompt_id")),
        "last_ollama_prompt_id": _safe_str(driver_state.get("last_ollama_prompt_id")),
        "last_note_id": _safe_str(driver_state.get("last_note_id")),
        "last_insight_id": _safe_str(driver_state.get("last_insight_id")),
        "last_learning_event_id": _safe_str(driver_state.get("last_learning_event_id")),
        "next_prompt_after": _safe_str(driver_state.get("next_prompt_after")),
        "turn_gap_remaining_seconds": remaining,
        "updated_at": _safe_str(driver_state.get("updated_at")),
        "age_seconds": _age_seconds(_safe_str(driver_state.get("updated_at"))),
        "latest_turn": _latest_turn_readback(driver_state),
        "latest_review_receipt": _latest_review_receipt_readback(driver_state),
        "latest_learning_receipt": _latest_learning_receipt_readback(driver_state),
        "current_learning_signal": _current_learning_signal_readback(driver_state),
        "latest_local_model_response": _latest_local_model_response_readback(participant_state),
    }


def _latest_local_model_response_readback(participant_state: dict[str, object]) -> dict[str, object]:
    responses = [item for item in _list(participant_state.get("responses")) if isinstance(item, dict)]
    if not responses:
        advice_only_proof = _local_model_advice_only_proof(
            observed=False,
            source_prompt_id="",
            response_prompt_id="",
            output_guard_status="unknown",
        )
        return {
            "observed": False,
            "state_observed": bool(participant_state),
            "state_path": _display_path(_ollama_participant_state_path()),
            "source": "ollama_participant.responses[-1]",
            "created_at": "",
            "age_seconds": None,
            "source_prompt_id": "",
            "response_prompt_id": "",
            "status": "unobserved",
            "output_guard_status": "unknown",
            "model_response_observed": False,
            "is_passed": False,
            "is_guard_rewrite": False,
            "stores_full_transcript": False,
            "grants_training_authority": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_capability_authority": False,
            "advice_only_proof": advice_only_proof,
        }
    latest = responses[-1]
    output_guard_status = _safe_str(latest.get("output_guard_status")) or "unknown"
    source_prompt_id = _safe_str(latest.get("source_prompt_id"))
    response_prompt_id = _safe_str(latest.get("response_prompt_id"))
    advice_only_proof = _local_model_advice_only_proof(
        observed=True,
        source_prompt_id=source_prompt_id,
        response_prompt_id=response_prompt_id,
        output_guard_status=output_guard_status,
    )
    return {
        "observed": True,
        "state_observed": bool(participant_state),
        "state_path": _display_path(_ollama_participant_state_path()),
        "source": "ollama_participant.responses[-1]",
        "created_at": _safe_str(latest.get("created_at")),
        "age_seconds": _age_seconds(_safe_str(latest.get("created_at"))),
        "source_prompt_id": source_prompt_id,
        "response_prompt_id": response_prompt_id,
        "status": _safe_str(latest.get("status")) or "unknown",
        "output_guard_status": output_guard_status,
        "model_response_observed": bool(latest.get("model_response_observed")),
        "is_passed": output_guard_status == "passed",
        "is_guard_rewrite": output_guard_status.endswith("_rewritten")
        or output_guard_status
        in {
            "empty_reply",
            "disabled",
        },
        "stores_full_transcript": False,
        "grants_training_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_capability_authority": False,
        "advice_only_proof": advice_only_proof,
    }


def _local_model_advice_only_proof(
    *,
    observed: bool,
    source_prompt_id: str,
    response_prompt_id: str,
    output_guard_status: str,
) -> dict[str, object]:
    guard_passed = output_guard_status == "passed"
    guard_rewrite = output_guard_status.endswith("_rewritten") or output_guard_status in {
        "empty_reply",
        "disabled",
    }
    return {
        "kind": "developer_bridge.local_model_advice_only_proof",
        "proof_status": "advice_only_observed" if observed else "unobserved",
        "model_response_observed": observed,
        "source_prompt_id": source_prompt_id,
        "response_prompt_id": response_prompt_id,
        "output_guard_status": output_guard_status,
        "output_guard_passed": guard_passed,
        "output_guard_rewrite_observed": guard_rewrite,
        "response_is_advice_only": True,
        "action_readiness_claim_allowed": False,
        "requires_codex_or_operator_review_before_action_readiness": True,
        "stores_full_transcript": False,
        "grants_training_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_capability_authority": False,
    }


def _latest_review_receipt_readback(driver_state: dict[str, object]) -> dict[str, object]:
    latest_turn = _latest_turn_readback(driver_state)
    insight_id = _safe_str(latest_turn.get("insight_id")) or _safe_str(driver_state.get("last_insight_id"))
    if not insight_id:
        return {
            "observed": False,
            "insight_id": "",
            "review_item_id": "",
            "review_artifact": "",
            "review_route": "/developer-bridge/collaboration-review",
            "source": "collaboration_loop.last_insight_id",
            "requires_codex_or_operator_review_before_implementation": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
        }
    return {
        "observed": True,
        "insight_id": insight_id,
        "review_item_id": f"review-{insight_id}",
        "review_artifact": f"developer_bridge.collaboration_review.items:review_candidate:{insight_id}",
        "review_route": "/developer-bridge/collaboration-review?limit=1",
        "source": "collaboration_loop.last_insight_id",
        "requires_codex_or_operator_review_before_implementation": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }


def _latest_learning_receipt_readback(driver_state: dict[str, object]) -> dict[str, object]:
    learning_event_id = _safe_str(driver_state.get("last_learning_event_id"))
    if not learning_event_id:
        return {
            "observed": False,
            "learning_event_id": "",
            "learning_artifact": "",
            "learning_route": "/developer-bridge/collaboration-learning",
            "source": "collaboration_loop.last_learning_event_id",
            "records_model_drift_as_learning": True,
            "requires_codex_or_operator_review_before_tuning": True,
            "stores_full_transcript": False,
            "grants_training_authority": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
        }
    return {
        "observed": True,
        "learning_event_id": learning_event_id,
        "learning_artifact": f"developer_bridge.collaboration_driver.learning_events:{learning_event_id}",
        "learning_route": "/developer-bridge/collaboration-learning?limit=1",
        "source": "collaboration_loop.last_learning_event_id",
        "records_model_drift_as_learning": True,
        "requires_codex_or_operator_review_before_tuning": True,
        "stores_full_transcript": False,
        "grants_training_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }


def _current_learning_signal_readback(driver_state: dict[str, object]) -> dict[str, object]:
    signal = driver_state.get("latest_learning_signal")
    if not isinstance(signal, dict) or not bool(signal.get("observed")):
        return {
            "observed": False,
            "failure_type": "",
            "repeated_terms": [],
            "recent_turn_count": 0,
            "latest_turn": 0,
            "learning_event_id": "",
            "learning_artifact": "",
            "source": "collaboration_loop.latest_learning_signal",
            "updated_at": "",
            "age_seconds": None,
            "records_model_drift_as_learning": True,
            "requires_codex_or_operator_review_before_tuning": True,
            "stores_full_transcript": False,
            "grants_training_authority": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
        }
    learning_event_id = _safe_str(signal.get("learning_event_id")) or _safe_str(
        driver_state.get("last_learning_event_id")
    )
    return {
        "observed": True,
        "failure_type": _safe_str(signal.get("failure_type")),
        "repeated_terms": [_safe_str(item) for item in _list(signal.get("repeated_terms")) if _safe_str(item)],
        "recent_turn_count": _safe_int(signal.get("recent_turn_count"), default=0),
        "latest_turn": _safe_int(signal.get("latest_turn"), default=0),
        "learning_event_id": learning_event_id,
        "learning_artifact": (
            f"developer_bridge.collaboration_driver.learning_events:{learning_event_id}" if learning_event_id else ""
        ),
        "source": "collaboration_loop.latest_learning_signal",
        "updated_at": _safe_str(signal.get("updated_at")),
        "age_seconds": _age_seconds(_safe_str(signal.get("updated_at"))),
        "records_model_drift_as_learning": bool(signal.get("records_model_drift_as_learning", True)),
        "requires_codex_or_operator_review_before_tuning": bool(
            signal.get("requires_codex_or_operator_review_before_tuning", True)
        ),
        "stores_full_transcript": bool(signal.get("stores_full_transcript")),
        "grants_training_authority": bool(signal.get("grants_training_authority")),
        "grants_execution_authority": bool(signal.get("grants_execution_authority")),
        "grants_mutation_authority": bool(signal.get("grants_mutation_authority")),
        "grants_approval_authority": bool(signal.get("grants_approval_authority")),
        "grants_memory_write_authority": bool(signal.get("grants_memory_write_authority")),
    }


def _latest_turn_readback(driver_state: dict[str, object]) -> dict[str, object]:
    turns = [item for item in _list(driver_state.get("turns")) if isinstance(item, dict)]
    if not turns:
        return {}
    latest = turns[-1]
    return {
        "turn": _safe_int(latest.get("turn"), default=0),
        "turn_label": _safe_str(latest.get("turn_label")),
        "topic": _safe_str(latest.get("topic")),
        "codex_prompt_id": _safe_str(latest.get("codex_prompt_id")),
        "ollama_prompt_id": _safe_str(latest.get("ollama_prompt_id")),
        "note_id": _safe_str(latest.get("note_id")),
        "insight_id": _safe_str(latest.get("insight_id")),
        "created_at": _safe_str(latest.get("created_at")),
    }


def _iter_python_processes() -> list[ProcessInfo]:
    if os.name == "nt":
        return _iter_windows_python_processes()
    return _iter_posix_python_processes()


def _iter_windows_python_processes() -> list[ProcessInfo]:
    command = (
        "$items = Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'python|py' } | "
        "Select-Object ProcessId,ParentProcessId,CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    rows = payload if isinstance(payload, list) else [payload]
    processes: list[ProcessInfo] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        command_line = str(row.get("CommandLine") or "")
        if not command_line:
            continue
        processes.append(
            {
                "pid": int(row.get("ProcessId") or 0),
                "parent_pid": int(row.get("ParentProcessId") or 0),
                "command_line": command_line,
            }
        )
    return processes


def _iter_posix_python_processes() -> list[ProcessInfo]:
    completed = subprocess.run(
        ["ps", "-eo", "pid=,ppid=,command="],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        return []
    processes: list[ProcessInfo] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, rest = stripped.partition(" ")
        ppid_text, _, command_line = rest.strip().partition(" ")
        if "python" not in command_line and "francis.developer_bridge" not in command_line:
            continue
        try:
            pid = int(pid_text)
            parent_pid = int(ppid_text)
        except ValueError:
            continue
        processes.append({"pid": pid, "parent_pid": parent_pid, "command_line": command_line})
    return processes


def _matching_processes(spec: RuntimeSpec, processes: Sequence[ProcessInfo]) -> list[ProcessInfo]:
    matches: list[ProcessInfo] = []
    for process in processes:
        command_line = str(process.get("command_line") or process.get("CommandLine") or "")
        if not command_line:
            continue
        if all(fragment in command_line for fragment in spec.required_fragments):
            matches.append(process)
    return matches


def _start_process(spec: RuntimeSpec) -> int:
    log_path = _log_path(spec)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("ab", buffering=0)
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    process = subprocess.Popen(
        list(spec.argv),
        cwd=str(repo_root()),
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    return int(process.pid)


def _state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_runtime" / "state.json"


def _driver_state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_driver" / "state.json"


def _ollama_participant_state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "ollama_participant" / "state.json"


def _log_path(spec: RuntimeSpec) -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_runtime" / "logs" / spec.log_name


def _write_state(payload: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _command_display(argv: Sequence[str]) -> str:
    return " ".join(argv)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, *, expected_kind: str) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("kind") != expected_kind:
        return {}
    return data


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _safe_str(value: object) -> str:
    return " ".join(str(value or "").split())


def _safe_int(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip() or str(default))
        except ValueError:
            return default
    return default


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(data_dir()).as_posix()
    except ValueError:
        return path.as_posix()


def _turn_gap_remaining_seconds(value: str) -> float:
    parsed = _parse_utc(value)
    if parsed is None:
        return 0.0
    return round(max((parsed - datetime.now(UTC)).total_seconds(), 0.0), 3)


def _age_seconds(value: str) -> float | None:
    parsed = _parse_utc(value)
    if parsed is None:
        return None
    return round(max((datetime.now(UTC) - parsed).total_seconds(), 0.0), 3)


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _governance() -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_runtime",
        "starts_bounded_local_helpers": True,
        "starts_arbitrary_commands": False,
        "grants_model_execution_authority": False,
        "grants_repo_mutation_authority": False,
        "grants_approval_authority": False,
        "relay": "developer_bridge_collaboration_prompt_relay_v0",
        "managed_helpers": [
            "francis.developer_bridge.codex_responder",
            "francis.developer_bridge.ollama_participant",
            "francis.developer_bridge.collaboration_driver",
        ],
    }


def _health_governance() -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_runtime",
        "read_only": True,
        "reads_runtime_state": True,
        "reads_driver_state": True,
        "reads_agent_toggle_state": True,
        "starts_bounded_local_helpers": False,
        "starts_arbitrary_commands": False,
        "executes_prompt": False,
        "calls_model": False,
        "trains_model": False,
        "stores_full_transcript": False,
        "grants_model_execution_authority": False,
        "grants_repo_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="collaboration_runtime",
        description="Keep the bounded Francis developer bridge Codex/Ollama collaboration helpers alive.",
    )
    parser.add_argument("--watch", action="store_true", help="Continuously ensure the collaboration helpers are alive.")
    parser.add_argument("--poll-seconds", type=float, default=10.0, help="Supervisor polling interval for --watch.")
    parser.add_argument("--quiet", action="store_true", help="Write receipts without printing each supervisor check.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    interval = max(float(args.poll_seconds), 1.0)
    try:
        while True:
            result = ensure_collaboration_runtime_once()
            if not bool(args.quiet):
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str), flush=True)
            if not bool(args.watch):
                return 0
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
