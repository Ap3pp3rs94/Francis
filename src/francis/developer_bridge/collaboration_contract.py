from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
from uuid import uuid4

from francis.chat.continuity.ledger import append
from francis.kernel.paths import data_dir

CONTEXT_CONTRACT_ID = "francis1-collaboration-compact-contract-v1"
ACCESS_CONTRACT_ID = "francis1-governed-access-contract-v1"
CONTEXT_CONTRACT_SCHEMA_VERSION = "developer_bridge_collaboration_context_contract_v1"
CONTEXT_CONTRACT_LEDGER_MODE = "developer_bridge_collaboration_context_contract"
CONTEXT_CONTRACT_PROMPT_LINE = (
    "Francis1 collaboration contract francis1-collaboration-compact-contract-v1: "
    "Francis1 speaks first-person through the local Ollama provider lane; source labels are provenance; "
    "each reply gives one build issue plus one receipt/review artifact; no execution, mutation, approval, or memory-write authority."
)
FRANCIS1_GOVERNED_ACCESS_PROMPT_LINE = (
    "Francis1 governed-access contract francis1-governed-access-contract-v1: "
    "Francis1 is the primary local Francis intelligence participant; Codex and Claude are external guidance sources; "
    "available context comes only through Francis-provided continuity, feedback-memory, relay, review, exploration, summary, and learning receipts; "
    "write access is limited to conversation-ledger and relay receipts through existing governed paths; "
    "no raw shell, repo mutation, approval, model training, memory promotion, or governance bypass."
)
CONTEXT_CONTRACT_PROMPT_LINES = (CONTEXT_CONTRACT_PROMPT_LINE, FRANCIS1_GOVERNED_ACCESS_PROMPT_LINE)


def ensure_context_contract(*, session_id: str) -> dict[str, object]:
    contract = _payload(session_id=session_id)
    _write_json_receipt(_contract_path(), contract)
    return contract


def append_context_contract_to_continuity(*, session_id: str) -> None:
    append(
        "system",
        " ".join(CONTEXT_CONTRACT_PROMPT_LINES),
        {
            "mode": CONTEXT_CONTRACT_LEDGER_MODE,
            "session_id": session_id,
            "contract_id": CONTEXT_CONTRACT_ID,
            "access_contract_id": ACCESS_CONTRACT_ID,
            "schema_version": CONTEXT_CONTRACT_SCHEMA_VERSION,
            "source": "developer_bridge.collaboration_contract",
            "stores_full_transcript": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
        },
    )


def context_contract_path() -> Path:
    return _contract_path()


def context_contract_governance() -> dict[str, object]:
    return {
        "surface": "developer_bridge.collaboration_driver.context_contracts",
        "advisory_only": True,
        "stores_full_transcript": False,
        "derived_from_operator_direction": True,
        "prompt_compaction_contract": True,
        "writes_continuity_summary": True,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_model_authority": False,
    }


def _payload(*, session_id: str) -> dict[str, object]:
    return {
        "kind": "developer_bridge.collaboration_context_contract",
        "schema_version": CONTEXT_CONTRACT_SCHEMA_VERSION,
        "id": CONTEXT_CONTRACT_ID,
        "access_contract_id": ACCESS_CONTRACT_ID,
        "created_at": _utc_now(),
        "session_id": session_id,
        "purpose": "Keep visible collaboration prompts compact while preserving the stable Francis1 collaboration contract.",
        "prompt_line": CONTEXT_CONTRACT_PROMPT_LINE,
        "access_prompt_line": FRANCIS1_GOVERNED_ACCESS_PROMPT_LINE,
        "stable_rules": [
            "Francis1 is the local Francis model participant and speaks in first person through a provider lane.",
            "Provider and source-agent labels are provenance and audit fields, not identity or authority.",
            "Francis1 is the primary local Francis intelligence participant; Codex and Claude are external guidance sources.",
            "Francis1's available context is whatever Francis supplies through continuity, feedback-memory, relay, review, exploration, summary, and learning receipts.",
            "Codex and local-model replies are advisory build signals until reviewed against repo truth.",
            "Each collaboration reply should name one concrete build issue and one typed receipt or review artifact.",
            "Repeated meta loops become bounded learning receipts instead of repeated debate.",
            "No relay prompt grants execution, mutation, approval, shell, commit, push, training, or memory-write authority.",
        ],
        "governed_access": {
            "identity": "Francis1 is the primary local Francis intelligence participant, not the Ollama provider.",
            "external_guidance_sources": ["codex", "claude"],
            "available_context_surfaces": [
                "continuity_prompt_context",
                "feedback_memory_prompt_context",
                "collaboration_relay_receipts",
                "collaboration_review_candidates",
                "collaboration_exploration_receipts",
                "collaboration_summaries",
                "collaboration_learning_receipts",
                "operator_visible_chat_ui_state",
            ],
            "write_surfaces": [
                "conversation_ledger_receipts",
                "collaboration_relay_receipts",
            ],
            "denied_authority": [
                "raw_shell",
                "repo_mutation",
                "approval",
                "model_training",
                "memory_promotion",
                "governance_bypass",
            ],
        },
        "visible_prompt_policy": {
            "style": "compact",
            "carry_stable_rules_by_contract_id": True,
            "avoid_repeating_contract_every_turn": True,
            "prefer_topic_plus_answer_shape": True,
        },
        "governance": context_contract_governance(),
    }


def _contract_path() -> Path:
    return (
        data_dir()
        / "integrations"
        / "developer_bridge"
        / "collaboration_driver"
        / "context_contracts"
        / (f"{CONTEXT_CONTRACT_ID}.json")
    )


def _write_json_receipt(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{uuid4().hex[:12]}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
