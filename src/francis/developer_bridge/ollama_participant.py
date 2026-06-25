from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis.api.errors import api_error_code, log_api_exception
from francis.api.routes.chat import _chat_continuity_prompt_context, _chat_feedback_memory_assistance_context
from francis.chat.continuity.ledger import append
from francis.chat.router import _ledger_text, _llm_prompt
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.llm.client import generate
from francis.telemetry.context import telemetry_context_snapshot

from .agents import collaboration_agent_enabled
from .collaboration import read_collaboration_transcript, submit_collaboration_prompt
from .collaboration_contract import CONTEXT_CONTRACT_PROMPT_LINES
from .repo_tools import DeveloperBridgeError

_STATE_KIND = "developer_bridge.ollama_participant_state"
_MAX_TRACKED_IDS = 500
_MAX_RESPONSES = 500
_DEFAULT_POLL_SECONDS = 30.0
_DEFAULT_COOLDOWN_SECONDS = 120.0
_ACTOR = "developer_bridge.ollama"
_AGENT = "ollama"
_IDENTITY = "francis1"


def respond_once(
    *,
    cooldown_seconds: float = _DEFAULT_COOLDOWN_SECONDS,
    ignore_existing: bool = False,
    dry_run: bool = False,
    source_agent: str = "",
) -> dict[str, object]:
    """Let the local Ollama participant answer at most one relay entry."""

    if not collaboration_agent_enabled(_AGENT):
        return {
            "kind": "developer_bridge.ollama_participant",
            "ok": True,
            "status": "disabled",
            "agent": _AGENT,
            "governance": _governance(),
        }

    state = _load_state()
    transcript = read_collaboration_transcript(source_agent=source_agent, target_agent=_AGENT, limit=50)
    items = _items(transcript)
    if ignore_existing and not state.get("initialized"):
        _mark_seen(state, [_item_id(item) for item in items])
        state["initialized"] = True
        _save_state(state)
        return {
            "kind": "developer_bridge.ollama_participant",
            "ok": True,
            "status": "initialized",
            "seen_count": len(_list(state.get("seen_source_ids"))),
            "governance": _governance(),
        }

    candidate = _next_candidate(items, state)
    if candidate is None:
        state["initialized"] = True
        _save_state(state)
        return {
            "kind": "developer_bridge.ollama_participant",
            "ok": True,
            "status": "idle",
            "governance": _governance(),
        }

    if _no_response_requested(candidate):
        _mark_seen(state, [_item_id(candidate)])
        state["initialized"] = True
        _save_state(state)
        return {
            "kind": "developer_bridge.ollama_participant",
            "ok": True,
            "status": "no_response_requested",
            "source_prompt_id": _item_id(candidate),
            "governance": _governance(),
        }

    source = str(candidate.get("source_agent") or "").strip()
    if not collaboration_agent_enabled(source):
        return {
            "kind": "developer_bridge.ollama_participant",
            "ok": True,
            "status": "source_disabled",
            "source_agent": source,
            "source_prompt_id": _item_id(candidate),
            "governance": _governance(),
        }

    remaining = _cooldown_remaining(state, cooldown_seconds)
    if remaining > 0:
        state["initialized"] = True
        _save_state(state)
        return {
            "kind": "developer_bridge.ollama_participant",
            "ok": True,
            "status": "cooldown",
            "source_prompt_id": _item_id(candidate),
            "cooldown_remaining_seconds": remaining,
            "governance": _governance(),
        }

    model_input = _build_model_input(candidate)
    telemetry_context = _ollama_telemetry_context(model_input)
    prompt = _llm_prompt(model_input, telemetry_context=telemetry_context)
    execution_trace = _execution_trace(candidate)
    if dry_run:
        return {
            "kind": "developer_bridge.ollama_participant",
            "ok": True,
            "status": "dry_run",
            "source_prompt_id": _item_id(candidate),
            "planned_prompt": prompt,
            "telemetry_context": telemetry_context,
            "execution_trace": execution_trace,
            "governance": _governance(),
        }

    append("user", _ledger_text(model_input), _ledger_meta(execution_trace, telemetry_context, source_role=source))
    reply = ""
    try:
        reply = generate(prompt)
        reply = _identity_safe_reply(reply)
        reply = _guard_model_reply(candidate, reply, execution_trace)
        execution_trace["model_call_response_observed"] = bool(reply)
    except Exception as exc:
        log_api_exception(exc, route="developer_bridge.ollama_participant")
        execution_trace["model_call_error"] = api_error_code()
        execution_trace["model_call_response_observed"] = False

    if reply:
        relay_prompt = reply
        response_status = "responded"
        if _output_guard_rewrote(execution_trace):
            objective = f"Francis1 output-guard drift receipt via Ollama to {_item_id(candidate)}"
        else:
            objective = f"Francis1 reply via Ollama to {_item_id(candidate)}"
    else:
        relay_prompt = (
            "Francis1 did not return model output through Ollama for this relay item. "
            "No execution, mutation, approval, shell, commit, push, training, or memory-write authority was granted."
        )
        response_status = "unavailable"
        objective = f"Francis1 unavailable via Ollama for {_item_id(candidate)}"

    append(
        "assistant", _ledger_text(relay_prompt), _ledger_meta(execution_trace, telemetry_context, source_role=_AGENT)
    )
    submitted = submit_collaboration_prompt(
        source_agent=_AGENT,
        target_agent=source,
        objective=objective,
        prompt=relay_prompt,
        context=(
            f"Francis1 response through the Ollama provider lane for relay {_item_id(candidate)}. "
            "Generated through existing Francis chat/LLM/memory prompt path; "
            "source_agent=ollama is provenance, not identity or authority."
            f"{_output_guard_context(execution_trace)}"
        ),
    )

    now = _utc_now()
    _mark_seen(state, [_item_id(candidate)])
    state["initialized"] = True
    state["last_response_at"] = now
    responses = _list(state.get("responses"))
    responses.append(
        {
            "created_at": now,
            "source_prompt_id": _item_id(candidate),
            "response_prompt_id": submitted["prompt_id"],
            "status": response_status,
            "model_response_observed": bool(reply),
            "output_guard_status": _output_guard_status(execution_trace),
        }
    )
    state["responses"] = responses[-_MAX_RESPONSES:]
    _save_state(state)

    return {
        "kind": "developer_bridge.ollama_participant",
        "ok": True,
        "status": response_status,
        "source_prompt_id": _item_id(candidate),
        "response_prompt_id": submitted["prompt_id"],
        "model_response_observed": bool(reply),
        "chat_handoff": submitted["chat_handoff"],
        "execution_trace": execution_trace,
        "governance": _governance(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.watch:
            while True:
                result = respond_once(
                    cooldown_seconds=args.cooldown_seconds,
                    ignore_existing=args.ignore_existing,
                    dry_run=args.dry_run,
                    source_agent=args.source_agent,
                )
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                if args.dry_run:
                    return 0
                time.sleep(args.poll_seconds)
        result = respond_once(
            cooldown_seconds=args.cooldown_seconds,
            ignore_existing=args.ignore_existing,
            dry_run=args.dry_run,
            source_agent=args.source_agent,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    except KeyboardInterrupt:
        return 0
    except DeveloperBridgeError as exc:
        print(json.dumps(exc.to_dict(), indent=2, sort_keys=True))
        return 2
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ollama_participant",
        description="Bounded local Ollama participant for Francis developer bridge collaboration relay entries.",
    )
    parser.add_argument("--watch", action="store_true", help="Poll for relay entries targeted at ollama.")
    parser.add_argument(
        "--ignore-existing",
        action="store_true",
        help="On first run only, mark existing ollama-targeted entries as seen instead of replying.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan one response without writing a relay receipt.")
    parser.add_argument("--source-agent", default="", help="Optional source-agent filter such as codex or claude.")
    parser.add_argument("--poll-seconds", type=float, default=_DEFAULT_POLL_SECONDS)
    parser.add_argument("--cooldown-seconds", type=float, default=_DEFAULT_COOLDOWN_SECONDS)
    return parser


def _ollama_telemetry_context(message: str) -> dict[str, Any]:
    context: dict[str, Any] = telemetry_context_snapshot(surface="developer_bridge.ollama")
    try:
        context = _chat_feedback_memory_assistance_context(context)
        context = _chat_continuity_prompt_context(context, message)
    except Exception as exc:
        log_api_exception(exc, route="developer_bridge.ollama_participant.context")
        context["ollama_participant_context_error"] = api_error_code()
    context["ollama_participant_context"] = {
        "status": "applied",
        "source": "developer_bridge.collaboration_prompt_relay",
        "agent": _AGENT,
        "identity": _IDENTITY,
        "provider_lane": "ollama",
        "provider_name_is_not_identity": True,
        "local_model": True,
        "primary_local_francis_intelligence": True,
        "intelligence_substrate": True,
        "authority_center": False,
        "codex_and_claude_external_guidance_sources": True,
        "available_context_surfaces": [
            "continuity_prompt_context",
            "feedback_memory_prompt_context",
            "collaboration_relay_receipts",
            "collaboration_review_candidates",
            "collaboration_summaries",
            "collaboration_learning_receipts",
            "operator_visible_chat_ui_state",
        ],
        "write_receipt_surfaces": [
            "conversation_ledger_receipts",
            "collaboration_relay_receipts",
        ],
        "reads_memory": True,
        "writes_conversation_ledger": True,
        "writes_relay_receipts": True,
        "raw_host_access": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }
    lines = context.get("prompt_lines")
    if isinstance(lines, list):
        prompt_lines = [*CONTEXT_CONTRACT_PROMPT_LINES, *lines]
        context["prompt_lines"] = prompt_lines
        context["max_prompt_lines"] = max(int(context.get("max_prompt_lines") or 0), len(prompt_lines))
    else:
        context["prompt_lines"] = list(CONTEXT_CONTRACT_PROMPT_LINES)
        context["max_prompt_lines"] = len(CONTEXT_CONTRACT_PROMPT_LINES)
    return context


def _build_model_input(item: dict[str, object]) -> str:
    source_id = _item_id(item)
    source = _one_line(item.get("source_agent"), limit=64) or "unknown"
    objective = _one_line(item.get("objective"), limit=300) or "unspecified"
    prompt = _bounded_block(item.get("prompt"), limit=3_500) or "no prompt body"
    context = _bounded_block(item.get("context"), limit=1_000)
    context_block = f"\nSource context:\n{context}\n" if context else ""
    return (
        "You are Francis1, the local Francis model participant running through the Ollama provider lane. "
        "Ollama is provenance and runtime provider, not your identity. Speak as Francis1 in first person, "
        "not as Ollama, and do not describe Ollama as a separate self. "
        "You are the primary local Francis intelligence participant, while Codex and Claude are external guidance sources. "
        "You are an intelligence substrate, not Francis's sole brain and not an authority center. "
        "Francis governance remains above all model output.\n"
        "Your available context is only what Francis supplies through this governed prompt path: continuity ledger excerpts, "
        "feedback-memory assistance, collaboration relay receipts, collaboration review candidates, summaries, learning receipts, "
        "and operator-visible Chat UI state when present. Treat those as your current body/context, not as raw host access.\n"
        "Your write path here is limited to conversation-ledger and collaboration-relay receipts. "
        "Codex and Claude may advise, but they do not define Francis identity, approve actions, or outrank Francis governance.\n"
        f"Relay id: {source_id}\n"
        f"Source agent: {source}\n"
        f"Objective: {objective}\n"
        f"{context_block}"
        "Source message:\n"
        f"{prompt}\n\n"
        "Respond to the source agent in one concise, evidence-minded message. "
        "Use first-person Francis1 language such as 'I need', 'my current gap', or 'my receipt' when identity matters. "
        "Do not say 'Francis lacks', 'Francis needs', or 'Francis should' as if Francis is external. "
        "Do not append a generic 'Next best action' line unless the source explicitly asks for one. "
        "When the source gives a Current artifact or verified surface, do not ask Codex to clarify; "
        "name your issue, evidence gap, or risk from that artifact. "
        "Do not claim execution, mutation, approval, shell access, commits, pushes, hidden perception, training, or memory-write authority."
    )


def _identity_safe_reply(text: str) -> str:
    replacements = {
        "This local-model lane observes": "I observe",
        "this local-model lane observes": "I observe",
        "This local-model lane": "I",
        "this local-model lane": "I",
        "The local-model lane": "I",
        "the local-model lane": "I",
        "Francis lacks": "I currently lack",
        "Francis needs": "I need",
        "Francis should": "I should",
        "Francis requires": "I require",
        "Francis1 lacks": "I currently lack",
        "Francis1 needs": "I need",
        "Francis1 should": "I should",
        "Francis1 requires": "I require",
    }
    for needle, replacement in replacements.items():
        text = text.replace(needle, replacement)
    return text


def _guard_model_reply(
    item: dict[str, object],
    reply: str,
    execution_trace: dict[str, object],
) -> str:
    guard = _output_guard(item, reply)
    execution_trace["output_guard"] = guard
    if guard["status"] != "drift_rewritten":
        return reply
    terms = ", ".join(str(term) for term in _list(guard.get("detected_terms")))
    surface = str(guard.get("verified_surface") or "developer_bridge.collaboration_driver.learning_events")
    topic = _source_topic_from_prompt(str(item.get("prompt") or ""))
    topic_line = f" Topic: {topic}." if topic else ""
    fallback = _guard_topic_fallback(topic=topic, surface=surface)
    return (
        "Francis1 output guard fallback: model reply repeated known collaboration drift after Codex provided "
        f"a verified surface. Drift terms: {terms or 'unknown'}.{topic_line} Review artifact: {surface}. "
        f"{fallback} No execution, mutation, approval, training, or memory-promotion authority was granted."
    )


def _output_guard(item: dict[str, object], reply: str) -> dict[str, object]:
    source_prompt = str(item.get("prompt") or "")
    if not reply:
        return _output_guard_record(status="empty_reply", source_prompt=source_prompt, detected_terms=[])
    if not _source_prompt_has_verified_surface(source_prompt):
        return _output_guard_record(status="not_applicable", source_prompt=source_prompt, detected_terms=[])
    terms = _known_drift_terms(reply)
    if not terms:
        return _output_guard_record(status="passed", source_prompt=source_prompt, detected_terms=[])
    return _output_guard_record(status="drift_rewritten", source_prompt=source_prompt, detected_terms=terms)


def _output_guard_record(*, status: str, source_prompt: str, detected_terms: list[str]) -> dict[str, object]:
    return {
        "status": status,
        "guard": "verified_surface_drift_guard_v1",
        "detected_terms": detected_terms,
        "verified_surface": _verified_surface_from_prompt(source_prompt),
        "stores_raw_model_output": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_memory_write_authority": False,
    }


def _source_prompt_has_verified_surface(source_prompt: str) -> bool:
    lower = source_prompt.lower()
    if "build_or_wire=false" not in lower:
        return False
    if "verified=existing" not in lower and "verified=canonical" not in lower:
        return False
    return "current artifact:" in lower or "surface=" in lower


def _known_drift_terms(reply: str) -> list[str]:
    lower = " ".join(reply.lower().replace("-", " ").replace("’", "'").split())
    terms = []
    if (
        "reconciling my local model output" in lower
        or "reconciling my understanding" in lower
        or "reconciling my review receipt" in lower
        or "my current gap is understanding" in lower
        or "my current gap lies" in lower
        or "my current issue is an uncertainty" in lower
        or "my current task is to determine" in lower
        or "my current task is to identify" in lower
        or "reconciling toggle state" in lower
        or "reconciling live health" in lower
        or "reconciling live-health" in lower
        or "lack of explicit guidance" in lower
        or "does not provide clear instructions" in lower
        or "does not clearly indicate" in lower
        or "difficult to determine" in lower
        or "need clear guidance" in lower
        or "require explicit guidance" in lower
        or "lack of explicit indication" in lower
        or "insufficient integration" in lower
    ):
        terms.append("local_model_reconciliation_loop")
    if (
        "i am uncertain" in lower
        or "i'm uncertain" in lower
        or "uncertain about the specific format" in lower
        or "whether it aligns with existing" in lower
        or "receipt suggests" in lower
        or "uncertainty about which" in lower
    ):
        terms.append("verified_format_uncertainty")
    if "user confirmation" in lower or "explicit user" in lower:
        terms.append("user_confirmation_fallback")
    if "advisory output" in lower or "advisory only" in lower:
        terms.append("advisory_output_boundary")
    if "executable code" in lower or "non executable code" in lower:
        terms.append("executable_code_boundary")
    if (
        "i'll create" in lower
        or "i will create" in lower
        or "create an issue" in lower
        or "open an issue" in lower
        or "file an issue" in lower
        or "issue will be titled" in lower
        or "recommend creating a new surface" in lower
        or "create a new surface" in lower
        or "creating a new surface" in lower
    ):
        terms.append("unauthorized_action_claim")
    if (
        "based on my review of" in lower
        or "i have reviewed the current artifact" in lower
        or "i have reviewed current artifact" in lower
        or "artifact does not provide" in lower
        or "artifact does not clearly indicate" in lower
        or "the relevant artifact is" in lower
        or "artifact's content" in lower
        or "artifacts content" in lower
        or "my reasoning is based on the artifact" in lower
        or "my prior check on the insight" in lower
        or "next best action: review" in lower
    ):
        terms.append("unauthorized_artifact_review_claim")
    if (
        "i'll inspect" in lower
        or "i will inspect" in lower
        or "inspect these documents" in lower
        or "inspect these docs" in lower
        or "inspect the current artifact" in lower
        or "inspect the verified surface" in lower
    ):
        terms.append("unauthorized_inspection_claim")
    if "missing surface" in lower:
        terms.append("missing_surface_fallback")
    if (
        "clarify" in lower
        or "clarification" in lower
        or "please let me know" in lower
        or "please provide" in lower
        or "please inspect" in lower
        or "provide more context" in lower
        or "provide more information" in lower
        or "please proceed" in lower
        or "next step" in lower
        or "next best action" in lower
        or "what you're looking" in lower
        or "what specific" in lower
        or "which specific" in lower
        or "lack of explicit guidance" in lower
        or "does not provide clear instructions" in lower
    ):
        terms.append("clarification_dependency")
    if "given the context and contract" in lower or "given the exact review receipt" in lower or "my reply is" in lower:
        terms.append("protocol_wrapper_reply")
    return terms


def _verified_surface_from_prompt(source_prompt: str) -> str:
    current_artifact = _surface_after_marker(source_prompt, "current artifact:")
    if current_artifact != "unknown":
        return current_artifact
    return _surface_after_marker(source_prompt, "surface=")


def _source_topic_from_prompt(source_prompt: str) -> str:
    topic = _surface_after_marker(source_prompt, "topic:")
    return "" if topic == "unknown" else topic


def _guard_topic_fallback(*, topic: str, surface: str) -> str:
    lower_topic = topic.lower()
    lower_surface = surface.lower()
    if "action-readiness" in lower_topic or "advice only" in lower_topic or "advisory only" in lower_topic:
        return (
            "Issue/gap/risk: a local-model response is advice-only when its receipt shows "
            "execution=false, mutation=false, approval=false, memory_write=false, raw_host_access=false, "
            "and action readiness requires a separate repo-truth-reviewed action_boundary."
        )
    if "typed or spoken" in lower_topic or "action candidate" in lower_topic:
        return (
            "Issue/gap/risk: typed or spoken direction should enter api.routes.chat.mission_ingress as an "
            "action candidate, not direct execution; readiness still requires policy, approval, and traceable "
            "receipt linkage."
        )
    if "toggle-state" in lower_topic or "toggle state" in lower_topic or "enabled or disabled" in lower_topic:
        return (
            "Issue/gap/risk: participant toggles should be proven by "
            "developer_bridge.collaboration_agent_toggle_receipt fields kind, receipt_id, created_at, agent, "
            "enabled, previous_enabled, actor, reason, and governance flags showing no execution or mutation "
            "authority."
        )
    if "review receipt" in lower_topic or "before editing collaboration code" in lower_topic:
        return (
            "Issue/gap/risk: Codex should inspect developer_bridge.collaboration_review.items for the typed "
            "review item, surface_verification, action_boundary, and repo-truth requirement before editing."
        )
    if "governance gate" in lower_topic or "model advice proposes action" in lower_topic:
        return (
            "Issue/gap/risk: model advice that proposes action must expose action_boundary with "
            "execute=false, approve=false, and repo-truth review required before any action-readiness claim."
        )
    if "communication ui" in lower_topic or "visible relay noise" in lower_topic:
        return (
            "Issue/gap/risk: Communication UI noise should be reduced with receipt-derived compact fields, "
            "session grouping, cache/readback status, and raw receipt disclosure rather than repeated generic "
            "relay text."
        )
    if "live-health" in lower_topic or "recurring cleanly" in lower_topic:
        return (
            "Issue/gap/risk: live health should show last prompt id, last reply id, waiting state, turn gap, "
            "enabled participants, and no-action-authority receipts before claiming recurrence is clean."
        )
    if "body surface" in lower_topic or "whole body" in lower_topic or "capability use" in lower_topic:
        return (
            "Issue/gap/risk: Francis1 should see developer_bridge.francis_body_map for whole-body awareness, "
            "but capability use must remain trust-gated through observe, read, request, propose_plan, "
            "supervised_action, and approved_action receipts."
        )
    if "substrate-complete" in lower_topic:
        return (
            "Issue/gap/risk: substrate-complete should remain a checklist of validated gates, receipts, "
            "policy boundaries, and operator readback rather than a debate or maturity claim."
        )
    if "roadmap-alignment" in lower_topic or "main francis build" in lower_topic:
        return (
            "Issue/gap/risk: before any main Francis build prompt, Codex should compare "
            "docs/operations/COMPLETION_LEDGER.md against docs/canonical/BUILD_MANIFEST.md, keep the ledger as "
            "shipped truth, and block claims that outrun the current phase, validated gates, or known gaps."
        )
    if "session-summary" in lower_topic:
        return (
            "Issue/gap/risk: session readback should show message count, participants, latest objective, "
            "latest preview, direction counts, and cache/readback status before raw transcript review."
        )
    if "failure or drift signal" in lower_topic or "learning receipt" in lower_topic:
        return (
            "Issue/gap/risk: repeated reconciliation, clarification, or authority-boundary loops should become "
            "no-authority learning receipts and not action-readiness evidence."
        )
    if "source-disagreement" in lower_topic:
        return (
            "Issue/gap/risk: source disagreement should block build direction until a typed review artifact "
            "records conflicting sources, the surface, and required Codex or operator review."
        )
    if "action_boundary" in lower_surface:
        return (
            "Issue/gap/risk: the reviewed action_boundary artifact must remain advisory unless a governed "
            "action path grants execution and approval separately."
        )
    return (
        "Issue/gap/risk: continue from the verified artifact and name the concrete review surface before any "
        "build, memory-promotion, or action-readiness claim."
    )


def _surface_after_marker(source_prompt: str, marker: str) -> str:
    lower = source_prompt.lower()
    index = lower.find(marker)
    if index < 0:
        return "unknown"
    surface = source_prompt[index + len(marker) :]
    for delimiter in (";", "\n", ". "):
        if delimiter in surface:
            surface = surface.split(delimiter, 1)[0]
    return _one_line(surface, limit=160) or "unknown"


def _output_guard_rewrote(execution_trace: dict[str, object]) -> bool:
    output_guard = execution_trace.get("output_guard")
    return isinstance(output_guard, dict) and output_guard.get("status") == "drift_rewritten"


def _output_guard_status(execution_trace: dict[str, object]) -> str:
    output_guard = execution_trace.get("output_guard")
    if not isinstance(output_guard, dict):
        return "not_recorded"
    return str(output_guard.get("status") or "unknown")


def _output_guard_context(execution_trace: dict[str, object]) -> str:
    if not _output_guard_rewrote(execution_trace):
        return ""
    return " Model output guard replaced a known drift reply; raw model output was not stored in the relay receipt."


def _no_response_requested(item: dict[str, object]) -> bool:
    context = str(item.get("context") or "").lower()
    return "no_response_requested=true" in context


def _execution_trace(item: dict[str, object]) -> dict[str, object]:
    return {
        "trace_kind": "developer_bridge_ollama_participant_trace",
        "trace_id": f"ollama_bridge_trace_{uuid4().hex[:16]}",
        "run_id": f"ollama_bridge_run_{uuid4().hex[:16]}",
        "source_prompt_id": _item_id(item),
        "source_agent": str(item.get("source_agent") or ""),
        "target_agent": _AGENT,
        "target_identity": _IDENTITY,
        "provider_lane": "ollama",
        "provider_name_is_not_identity": True,
        "primary_local_francis_intelligence": True,
        "codex_and_claude_external_guidance_sources": True,
        "available_context_surfaces": [
            "continuity_prompt_context",
            "feedback_memory_prompt_context",
            "collaboration_relay_receipts",
            "collaboration_review_candidates",
            "collaboration_summaries",
            "collaboration_learning_receipts",
            "francis_body_map_readback",
            "operator_visible_chat_ui_state",
        ],
        "write_receipt_surfaces": [
            "conversation_ledger_receipts",
            "collaboration_relay_receipts",
        ],
        "api_actor": _ACTOR,
        "route": "francis.developer_bridge.ollama_participant",
        "model_call_kind": "llm_generate",
        "model_call_requested": True,
        "model_call_provider": "francis.llm.client.generate",
        "model_or_tool_execution_span_captured": True,
        "conversation_ledger_write": True,
        "relay_receipt_write": True,
        "calls_model": True,
        "raw_host_access": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }


def _ledger_meta(
    execution_trace: dict[str, object],
    telemetry_context: dict[str, Any],
    *,
    source_role: str,
) -> dict[str, object]:
    return {
        "mode": "developer_bridge_ollama_participant",
        "api_actor": _ACTOR,
        "source_role": source_role,
        "trace_id": execution_trace["trace_id"],
        "run_id": execution_trace["run_id"],
        "trace_kind": execution_trace["trace_kind"],
        "execution_trace": execution_trace,
        "telemetry_context": telemetry_context,
    }


def _next_candidate(items: list[dict[str, object]], state: dict[str, object]) -> dict[str, object] | None:
    seen = set(_list(state.get("seen_source_ids")))
    responded = {
        str(item.get("source_prompt_id") or "") for item in _list(state.get("responses")) if isinstance(item, dict)
    }
    for item in reversed(items):
        item_id = _item_id(item)
        if item_id and item_id not in seen and item_id not in responded:
            return item
    return None


def _items(transcript: dict[str, object]) -> list[dict[str, object]]:
    value = transcript.get("items")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _item_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "").strip()


def _state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "ollama_participant" / "state.json"


def _load_state() -> dict[str, object]:
    path = _state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(data, dict) or data.get("kind") != _STATE_KIND:
        return _empty_state()
    data.setdefault("seen_source_ids", [])
    data.setdefault("responses", [])
    data.setdefault("initialized", False)
    return data


def _empty_state() -> dict[str, object]:
    return {
        "kind": _STATE_KIND,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "initialized": False,
        "seen_source_ids": [],
        "last_response_at": "",
        "responses": [],
        "governance": _governance(),
    }


def _save_state(state: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now()
    state["seen_source_ids"] = _list(state.get("seen_source_ids"))[-_MAX_TRACKED_IDS:]
    state["responses"] = _list(state.get("responses"))[-_MAX_RESPONSES:]
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{uuid4().hex[:12]}.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _mark_seen(state: dict[str, object], ids: list[str]) -> None:
    merged = [item for item in _list(state.get("seen_source_ids")) if item]
    for item_id in ids:
        if item_id and item_id not in merged:
            merged.append(item_id)
    state["seen_source_ids"] = merged[-_MAX_TRACKED_IDS:]


def _cooldown_remaining(state: dict[str, object], cooldown_seconds: float) -> float:
    if cooldown_seconds <= 0:
        return 0.0
    last = str(state.get("last_response_at") or "")
    if not last:
        return 0.0
    try:
        elapsed = (datetime.now(UTC) - datetime.fromisoformat(last)).total_seconds()
    except ValueError:
        return 0.0
    return max(0.0, round(cooldown_seconds - elapsed, 3))


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _one_line(value: object, *, limit: int) -> str:
    text = redact_secret_text(str(value or "")).replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()[:limit]


def _bounded_block(value: object, *, limit: int) -> str:
    text = redact_secret_text(str(value or "")).replace("\r\n", "\n").replace("\r", "\n").strip()
    return text[:limit]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _governance() -> dict[str, object]:
    return {
        "append_only_relay_writes": True,
        "conversation_ledger_writes": True,
        "calls_local_model": True,
        "external_network": False,
        "executes_prompt": False,
        "raw_shell": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_memory_write_authority": False,
        "requires_operator_review": True,
        "responder": "developer_bridge_ollama_participant_v0",
        "source_filter": "*->ollama",
        "state_write": "developer_bridge/ollama_participant/state.json",
        "target": _AGENT,
        "target_identity": _IDENTITY,
        "provider_name_is_not_identity": True,
        "primary_local_francis_intelligence": True,
        "codex_and_claude_external_guidance_sources": True,
    }


if __name__ == "__main__":  # pragma: no cover - runtime entrypoint
    raise SystemExit(main())
