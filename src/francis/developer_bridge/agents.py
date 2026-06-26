from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

from .repo_tools import DeveloperBridgeError

_STATE_KIND = "developer_bridge.collaboration_agents_state"
_AGENT_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_KNOWN_AGENTS = ("codex", "claude", "ollama")
_DEFAULT_ENABLED = {
    "codex": True,
    "claude": True,
    "ollama": True,
}
_AGENT_DETAILS = {
    "codex": {
        "label": "Codex",
        "participant_kind": "interactive_and_optional_responder",
        "local_runner": "francis.developer_bridge.codex_responder",
        "authority": "relay_only",
    },
    "claude": {
        "label": "Claude",
        "participant_kind": "external_mcp_client",
        "local_runner": "",
        "authority": "relay_only",
    },
    "ollama": {
        "label": "Ollama",
        "participant_kind": "local_model_participant",
        "local_runner": "francis.developer_bridge.ollama_participant",
        "authority": "relay_only",
    },
}
_OPERATOR_CONSOLE = {
    "surface": "chat_ui",
    "actor": "chat_ui.system",
    "client_can_be_operator_console": True,
    "client_is_automatic_execution_authority": False,
}
_MAX_REASON_CHARS = 500
_MAX_RECEIPTS = 200


def collaboration_agents_status() -> dict[str, object]:
    """Read the bounded collaboration participant control state."""

    state = _load_state()
    receipt_dicts = _receipt_dicts(_list(state.get("receipts")))
    receipts = receipt_dicts[-10:]
    agents = _agent_records(state, receipts=receipt_dicts)
    return {
        "kind": "developer_bridge.collaboration_agents_status",
        "ok": True,
        "mode": "read_only",
        "relay": "developer_bridge_collaboration_prompt_relay_v0",
        "agents": agents,
        "agent_count": len(agents),
        "known_agents": list(_KNOWN_AGENTS),
        "state_path": _display_path(_state_path()),
        "receipts": receipts,
        "toggle_receipt_contract": _toggle_receipt_contract(),
        "toggle_receipt_summary": _toggle_receipt_summary(receipts, agents=agents),
        "operator_console": dict(_OPERATOR_CONSOLE),
        "definitions": {
            "operator_toggle_proof": (
                "Typed proof that a participant toggle receipt recorded actor, reason, previous/current state, "
                "operator-console status, and no capability or execution authority grant."
            ),
            "current_toggle_proof": (
                "Read-only per-agent projection of the latest receipt proving the current enabled/disabled state; "
                "legacy receipts stay labeled as projections and do not become stronger historical proof."
            ),
            "toggle_receipt_contract": (
                "Bounded checklist for what a collaboration participant toggle receipt proves before Codex or "
                "Francis1 can treat a participant as enabled or disabled."
            ),
        },
        "governance": _governance(write=False),
    }


def set_collaboration_agent_enabled(
    agent: str,
    enabled: bool,
    *,
    actor: str = "",
    reason: str = "",
) -> dict[str, object]:
    """Toggle one known collaboration participant without granting tool authority."""

    clean_agent = _agent_id(agent)
    if clean_agent not in _KNOWN_AGENTS:
        raise DeveloperBridgeError(
            "unknown_collaboration_agent",
            f"agent must be one of: {', '.join(_KNOWN_AGENTS)}",
        )
    clean_actor = _bounded_text(actor, max_chars=96) or "operator"
    clean_reason = _bounded_text(reason, max_chars=_MAX_REASON_CHARS)
    state = _load_state()
    now = _utc_now()
    agents = _state_agents(state)
    previous = _agent_state(agents, clean_agent)
    previous_enabled = bool(previous.get("enabled", _DEFAULT_ENABLED[clean_agent]))
    current_enabled = bool(enabled)
    receipt_governance = _governance(write=True)
    current = {
        **previous,
        "enabled": current_enabled,
        "updated_at": now,
        "updated_by": redact_secret_text(clean_actor),
        "reason": redact_secret_text(clean_reason),
    }
    agents[clean_agent] = current
    state["agents"] = agents
    receipt = {
        "kind": "developer_bridge.collaboration_agent_toggle_receipt",
        "receipt_id": f"collab-agent-toggle-{uuid4().hex[:16]}",
        "created_at": now,
        "agent": clean_agent,
        "enabled": current_enabled,
        "previous_enabled": previous_enabled,
        "actor": redact_secret_text(clean_actor),
        "reason": redact_secret_text(clean_reason),
        "operator_toggle_proof": _operator_toggle_proof(
            agent=clean_agent,
            actor=clean_actor,
            reason=clean_reason,
            previous_enabled=previous_enabled,
            current_enabled=current_enabled,
            governance=receipt_governance,
        ),
        "governance": receipt_governance,
    }
    receipts = _list(state.get("receipts"))
    receipts.append(receipt)
    state["receipts"] = receipts[-_MAX_RECEIPTS:]
    _save_state(state)

    return {
        "kind": "developer_bridge.collaboration_agent_toggle",
        "ok": True,
        "agent": clean_agent,
        "enabled": current_enabled,
        "receipt": receipt,
        "status": collaboration_agents_status(),
        "governance": receipt_governance,
    }


def collaboration_agent_enabled(agent: str) -> bool:
    clean_agent = _optional_agent_id(agent)
    if not clean_agent:
        return True
    if clean_agent not in _KNOWN_AGENTS:
        return True
    state = _load_state()
    return bool(_agent_state(_state_agents(state), clean_agent).get("enabled", _DEFAULT_ENABLED[clean_agent]))


def disabled_collaboration_agents(*agents: str) -> list[str]:
    return [agent for agent in agents if not collaboration_agent_enabled(agent)]


def enforce_collaboration_agents_enabled(*agents: str) -> None:
    disabled = disabled_collaboration_agents(*agents)
    if disabled:
        raise DeveloperBridgeError(
            "collaboration_agent_disabled",
            f"collaboration relay agent disabled: {', '.join(disabled)}",
        )


def _state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_agents" / "state.json"


def _load_state() -> dict[str, object]:
    path = _state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(data, dict) or data.get("kind") != _STATE_KIND:
        return _empty_state()
    data.setdefault("agents", {})
    data.setdefault("receipts", [])
    return data


def _empty_state() -> dict[str, object]:
    now = _utc_now()
    return {
        "kind": _STATE_KIND,
        "created_at": now,
        "updated_at": now,
        "agents": {},
        "receipts": [],
        "governance": _governance(write=True),
    }


def _save_state(state: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now()
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{uuid4().hex[:12]}.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _agent_records(state: dict[str, object], *, receipts: list[dict[str, object]]) -> list[dict[str, object]]:
    agents = _state_agents(state)
    records: list[dict[str, object]] = []
    for agent in _KNOWN_AGENTS:
        current = _agent_state(agents, agent)
        details = _AGENT_DETAILS[agent]
        current_toggle_proof = _current_toggle_proof(
            agent=agent,
            current=current,
            latest_receipt=_latest_receipt_for_agent(receipts, agent),
        )
        records.append(
            {
                "agent": agent,
                "label": details["label"],
                "enabled": bool(current.get("enabled", _DEFAULT_ENABLED[agent])),
                "participant_kind": details["participant_kind"],
                "local_runner": details["local_runner"],
                "authority": details["authority"],
                "updated_at": current.get("updated_at", ""),
                "updated_by": current.get("updated_by", ""),
                "reason": current.get("reason", ""),
                "latest_toggle_receipt_id": current_toggle_proof["receipt_id"],
                "latest_toggle_proof_status": current_toggle_proof["proof_status"],
                "current_toggle_proof": current_toggle_proof,
                "writes_relay_receipts": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            }
        )
    return records


def _state_agents(state: dict[str, object]) -> dict[str, object]:
    value = state.get("agents")
    return value if isinstance(value, dict) else {}


def _agent_state(agents: dict[str, object], agent: str) -> dict[str, object]:
    value = agents.get(agent)
    if isinstance(value, dict):
        return dict(value)
    return {"enabled": _DEFAULT_ENABLED[agent]}


def _agent_id(value: str) -> str:
    text = str(value or "").strip().lower()
    if not _AGENT_RE.fullmatch(text):
        raise DeveloperBridgeError(
            "agent_id_denied", "agent id must be lowercase letters, numbers, dot, underscore, or dash"
        )
    return text


def _optional_agent_id(value: str) -> str:
    if not str(value or "").strip():
        return ""
    return _agent_id(value)


def _bounded_text(value: object, *, max_chars: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\n", " ")
    return " ".join(text.split())[:max_chars]


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _receipt_dicts(receipts: list[object]) -> list[dict[str, object]]:
    return [item for item in receipts if isinstance(item, dict)]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(data_dir()).as_posix()
    except ValueError:
        return path.as_posix()


def _operator_toggle_proof(
    *,
    agent: str,
    actor: str,
    reason: str,
    previous_enabled: bool,
    current_enabled: bool,
    governance: dict[str, object],
) -> dict[str, object]:
    actor_recorded = bool(actor)
    reason_recorded = bool(reason)
    operator_console_actor = actor == _OPERATOR_CONSOLE["actor"]
    return {
        "kind": "developer_bridge.collaboration_agent_toggle_proof",
        "proof_status": "operator_console_recorded" if operator_console_actor else "actor_recorded",
        "agent": agent,
        "actor_recorded": actor_recorded,
        "reason_recorded": reason_recorded,
        "previous_state_observed": True,
        "current_state_observed": True,
        "previous_enabled": previous_enabled,
        "current_enabled": current_enabled,
        "state_changed": previous_enabled != current_enabled,
        "operator_console_actor": operator_console_actor,
        "client_can_be_operator_console": bool(governance["client_can_be_operator_console"]),
        "client_is_automatic_execution_authority": bool(governance["client_is_automatic_execution_authority"]),
        "requires_operator_review": bool(governance["requires_operator_review"]),
        "proves_capability_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _latest_receipt_for_agent(receipts: list[dict[str, object]], agent: str) -> dict[str, object]:
    for receipt in reversed(receipts):
        if str(receipt.get("agent") or "") == agent:
            return receipt
    return {}


def _current_toggle_proof(
    *,
    agent: str,
    current: dict[str, object],
    latest_receipt: dict[str, object],
) -> dict[str, object]:
    explicit = _dict(latest_receipt.get("operator_toggle_proof"))
    current_enabled = bool(current.get("enabled", _DEFAULT_ENABLED[agent]))
    if explicit:
        return {
            "kind": "developer_bridge.collaboration_agent_current_toggle_proof",
            "proof_status": str(explicit.get("proof_status") or "operator_toggle_proof_recorded"),
            "source": "operator_toggle_proof",
            "agent": agent,
            "receipt_id": latest_receipt.get("receipt_id", ""),
            "created_at": latest_receipt.get("created_at", ""),
            "actor": latest_receipt.get("actor", ""),
            "reason": latest_receipt.get("reason", ""),
            "explicit_operator_toggle_proof": True,
            "legacy_projection": False,
            "default_state_projection": False,
            "requires_new_toggle_for_explicit_operator_proof": False,
            "actor_recorded": bool(explicit.get("actor_recorded")),
            "reason_recorded": bool(explicit.get("reason_recorded")),
            "previous_state_observed": bool(explicit.get("previous_state_observed")),
            "current_state_observed": bool(explicit.get("current_state_observed")),
            "previous_enabled": bool(explicit.get("previous_enabled")),
            "current_enabled": bool(explicit.get("current_enabled")),
            "state_changed": bool(explicit.get("state_changed")),
            "client_can_be_operator_console": bool(explicit.get("client_can_be_operator_console")),
            "client_is_automatic_execution_authority": bool(explicit.get("client_is_automatic_execution_authority")),
            "proves_capability_authority": bool(explicit.get("proves_capability_authority")),
            "grants_execution_authority": bool(explicit.get("grants_execution_authority")),
            "grants_mutation_authority": bool(explicit.get("grants_mutation_authority")),
            "grants_approval_authority": bool(explicit.get("grants_approval_authority")),
            "grants_memory_write_authority": bool(explicit.get("grants_memory_write_authority")),
            "grants_training_authority": bool(explicit.get("grants_training_authority")),
        }
    if latest_receipt:
        previous_enabled = bool(latest_receipt.get("previous_enabled"))
        receipt_enabled = bool(latest_receipt.get("enabled"))
        return {
            "kind": "developer_bridge.collaboration_agent_current_toggle_proof",
            "proof_status": "legacy_receipt_projected",
            "source": "legacy_toggle_receipt",
            "agent": agent,
            "receipt_id": latest_receipt.get("receipt_id", ""),
            "created_at": latest_receipt.get("created_at", ""),
            "actor": latest_receipt.get("actor", ""),
            "reason": latest_receipt.get("reason", ""),
            "explicit_operator_toggle_proof": False,
            "legacy_projection": True,
            "default_state_projection": False,
            "requires_new_toggle_for_explicit_operator_proof": True,
            "actor_recorded": bool(latest_receipt.get("actor")),
            "reason_recorded": bool(latest_receipt.get("reason")),
            "previous_state_observed": "previous_enabled" in latest_receipt,
            "current_state_observed": "enabled" in latest_receipt,
            "previous_enabled": previous_enabled,
            "current_enabled": receipt_enabled,
            "state_changed": previous_enabled != receipt_enabled,
            "client_can_be_operator_console": bool(
                _dict(latest_receipt.get("governance")).get("client_can_be_operator_console")
            ),
            "client_is_automatic_execution_authority": bool(
                _dict(latest_receipt.get("governance")).get("client_is_automatic_execution_authority")
            ),
            "proves_capability_authority": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        }
    return {
        "kind": "developer_bridge.collaboration_agent_current_toggle_proof",
        "proof_status": "default_state_no_toggle_receipt",
        "source": "default_agent_state",
        "agent": agent,
        "receipt_id": "",
        "created_at": "",
        "actor": "",
        "reason": "",
        "explicit_operator_toggle_proof": False,
        "legacy_projection": False,
        "default_state_projection": True,
        "requires_new_toggle_for_explicit_operator_proof": True,
        "actor_recorded": False,
        "reason_recorded": False,
        "previous_state_observed": False,
        "current_state_observed": True,
        "previous_enabled": current_enabled,
        "current_enabled": current_enabled,
        "state_changed": False,
        "client_can_be_operator_console": True,
        "client_is_automatic_execution_authority": False,
        "proves_capability_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _toggle_receipt_contract() -> dict[str, object]:
    return {
        "kind": "developer_bridge.collaboration_agent_toggle_receipt_contract",
        "schema_version": "developer_bridge_collaboration_agent_toggle_receipt_contract_v1",
        "receipt_kind": "developer_bridge.collaboration_agent_toggle_receipt",
        "known_agents": list(_KNOWN_AGENTS),
        "required_receipt_fields": [
            "receipt_id",
            "created_at",
            "agent",
            "previous_enabled",
            "enabled",
            "actor",
            "reason",
            "operator_toggle_proof",
            "governance",
        ],
        "required_proof_fields": [
            "actor_recorded=true",
            "reason_recorded=true",
            "previous_state_observed=true",
            "current_state_observed=true",
            "previous_enabled",
            "current_enabled",
            "client_can_be_operator_console=true",
            "client_is_automatic_execution_authority=false",
            "grants_execution_authority=false",
            "grants_mutation_authority=false",
            "grants_approval_authority=false",
            "grants_memory_write_authority=false",
            "grants_training_authority=false",
        ],
        "operator_console_actor": _OPERATOR_CONSOLE["actor"],
        "operator_console_surface": _OPERATOR_CONSOLE["surface"],
        "client_can_be_operator_console": True,
        "client_is_automatic_execution_authority": False,
        "disabled_participant_blocks_new_relay_submissions": True,
        "writes_agent_control_state": True,
        "writes_relay_receipts": False,
        "executes_prompt": False,
        "calls_model": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
        "next_codex_action": (
            "Read collaboration_agents_status.toggle_receipt_contract and the latest receipt's "
            "operator_toggle_proof before changing participant-control behavior."
        ),
    }


def _toggle_receipt_summary(receipts: list[dict[str, object]], *, agents: list[dict[str, object]]) -> dict[str, object]:
    latest = receipts[-1] if receipts else {}
    latest_proof = _dict(latest.get("operator_toggle_proof")) if latest else {}
    proof_count = sum(1 for item in receipts if isinstance(item.get("operator_toggle_proof"), dict))
    legacy_count = len(receipts) - proof_count
    current_proofs = [_dict(agent.get("current_toggle_proof")) for agent in agents]
    explicit_agents = [
        str(agent.get("agent") or "")
        for agent, proof in zip(agents, current_proofs, strict=False)
        if bool(proof.get("explicit_operator_toggle_proof"))
    ]
    missing_explicit_agents = [
        str(agent.get("agent") or "")
        for agent, proof in zip(agents, current_proofs, strict=False)
        if not bool(proof.get("explicit_operator_toggle_proof"))
    ]
    return {
        "receipt_count": len(receipts),
        "proof_receipt_count": proof_count,
        "legacy_receipt_count": legacy_count,
        "latest_receipt_id": latest.get("receipt_id", ""),
        "latest_agent": latest.get("agent", ""),
        "latest_previous_enabled": latest.get("previous_enabled", False),
        "latest_enabled": latest.get("enabled", False),
        "latest_has_operator_toggle_proof": bool(latest_proof),
        "latest_actor_recorded": bool(latest_proof.get("actor_recorded")),
        "latest_reason_recorded": bool(latest_proof.get("reason_recorded")),
        "latest_proves_capability_authority": bool(latest_proof.get("proves_capability_authority")),
        "latest_grants_execution_authority": bool(latest_proof.get("grants_execution_authority")),
        "latest_grants_mutation_authority": bool(latest_proof.get("grants_mutation_authority")),
        "latest_grants_approval_authority": bool(latest_proof.get("grants_approval_authority")),
        "latest_grants_memory_write_authority": bool(latest_proof.get("grants_memory_write_authority")),
        "latest_grants_training_authority": bool(latest_proof.get("grants_training_authority")),
        "agent_current_toggle_proof_count": len(current_proofs),
        "agent_explicit_operator_toggle_proof_count": len(explicit_agents),
        "agent_legacy_projection_count": sum(1 for proof in current_proofs if bool(proof.get("legacy_projection"))),
        "agent_default_state_projection_count": sum(
            1 for proof in current_proofs if bool(proof.get("default_state_projection"))
        ),
        "agents_with_explicit_operator_toggle_proof": explicit_agents,
        "agents_missing_explicit_operator_toggle_proof": missing_explicit_agents,
        "all_agents_have_current_toggle_readback": len(current_proofs) == len(_KNOWN_AGENTS),
        "all_agents_have_explicit_operator_toggle_proof": len(explicit_agents) == len(_KNOWN_AGENTS),
    }


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _governance(*, write: bool) -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_agents",
        "read_only": not write,
        "writes_agent_control_state": write,
        "writes_relay_receipts": False,
        "executes_prompt": False,
        "calls_model": False,
        "trains_model": False,
        "client_can_be_operator_console": True,
        "client_is_automatic_execution_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
        "requires_operator_review": True,
    }
