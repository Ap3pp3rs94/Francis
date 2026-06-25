from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis.kernel.paths import data_dir

from .agents import collaboration_agent_enabled
from .collaboration import read_collaboration_transcript, submit_collaboration_prompt
from .repo_tools import DeveloperBridgeError

_STATE_KIND = "developer_bridge.codex_relay_responder_state"
_MAX_TRACKED_IDS = 500
_MAX_RESPONSES = 500
_DEFAULT_POLL_SECONDS = 30.0
_DEFAULT_COOLDOWN_SECONDS = 120.0


def respond_once(
    *,
    cooldown_seconds: float = _DEFAULT_COOLDOWN_SECONDS,
    ignore_existing: bool = False,
    dry_run: bool = False,
    source_agent: str = "claude",
) -> dict[str, object]:
    """Respond to at most one new relay entry targeted at Codex."""

    if not collaboration_agent_enabled("codex"):
        return {
            "kind": "developer_bridge.codex_relay_responder",
            "ok": True,
            "status": "disabled",
            "agent": "codex",
            "governance": _governance(),
        }

    state = _load_state()
    transcript = read_collaboration_transcript(source_agent=source_agent, target_agent="codex", limit=50)
    items = _items(transcript)
    source_key = source_agent or "*"
    initialized_sources = set(str(item) for item in _list(state.get("initialized_sources")) if item)
    if ignore_existing and source_key not in initialized_sources:
        _mark_seen(state, [_item_id(item) for item in items])
        state["initialized"] = True
        initialized_sources.add(source_key)
        state["initialized_sources"] = sorted(initialized_sources)
        _save_state(state)
        return {
            "kind": "developer_bridge.codex_relay_responder",
            "ok": True,
            "status": "initialized",
            "source_agent": source_agent,
            "seen_count": len(_list(state.get("seen_source_ids"))),
            "governance": _governance(),
        }

    candidate = _next_candidate(items, state)
    if candidate is None:
        state["initialized"] = True
        _save_state(state)
        return {
            "kind": "developer_bridge.codex_relay_responder",
            "ok": True,
            "status": "idle",
            "governance": _governance(),
        }

    source = str(candidate.get("source_agent") or "").strip()
    if not collaboration_agent_enabled(source):
        return {
            "kind": "developer_bridge.codex_relay_responder",
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
            "kind": "developer_bridge.codex_relay_responder",
            "ok": True,
            "status": "cooldown",
            "source_prompt_id": _item_id(candidate),
            "cooldown_remaining_seconds": remaining,
            "governance": _governance(),
        }

    prompt = _build_reply(candidate)
    context = f"source={source or 'unknown'}; relay={_item_id(candidate)}; no_response_requested=true; no_action_authority=true."
    if dry_run:
        return {
            "kind": "developer_bridge.codex_relay_responder",
            "ok": True,
            "status": "dry_run",
            "source_prompt_id": _item_id(candidate),
            "planned_prompt": prompt,
            "context": context,
            "governance": _governance(),
        }

    submitted = submit_collaboration_prompt(
        source_agent="codex",
        target_agent=source,
        objective=f"auto-ack {source or 'unknown'} relay {_item_id(candidate)}",
        prompt=prompt,
        context=context,
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
        }
    )
    state["responses"] = responses[-_MAX_RESPONSES:]
    _save_state(state)

    return {
        "kind": "developer_bridge.codex_relay_responder",
        "ok": True,
        "status": "responded",
        "source_prompt_id": _item_id(candidate),
        "response_prompt_id": submitted["prompt_id"],
        "chat_handoff": submitted["chat_handoff"],
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
        prog="codex_responder",
        description="Bounded Codex auto-responder for developer bridge relay entries targeted at Codex.",
    )
    parser.add_argument("--watch", action="store_true", help="Poll for new relay entries targeted at Codex.")
    parser.add_argument(
        "--ignore-existing",
        action="store_true",
        help="On first run for the selected source, mark existing entries as seen instead of replying.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan one response without writing a relay receipt.")
    parser.add_argument("--source-agent", default="claude", help="Source-agent filter such as claude or ollama.")
    parser.add_argument("--poll-seconds", type=float, default=_DEFAULT_POLL_SECONDS)
    parser.add_argument("--cooldown-seconds", type=float, default=_DEFAULT_COOLDOWN_SECONDS)
    return parser


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


def _build_reply(item: dict[str, object]) -> str:
    source_id = _item_id(item)
    source = _one_line(item.get("source_agent"), limit=64) or "unknown"
    objective = _one_line(item.get("objective"), limit=120) or "unspecified"
    preview = _one_line(item.get("prompt"), limit=180) or "no prompt body"
    return (
        f"Auto-ack {source} relay {source_id}. Received; no_response_requested=true. "
        f"Objective: {objective}. Preview: {preview}. "
        "Receipt only; no execution, mutation, approval, commit, or push authority."
    )


def _state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "codex_responder" / "state.json"


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
    data.setdefault("initialized_sources", [])
    return data


def _empty_state() -> dict[str, object]:
    return {
        "kind": _STATE_KIND,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "initialized": False,
        "initialized_sources": [],
        "seen_source_ids": [],
        "last_response_at": "",
        "responses": [],
        "governance": _governance(),
    }


def _save_state(state: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _utc_now()
    state["governance"] = _governance()
    state["initialized_sources"] = _list(state.get("initialized_sources"))[-_MAX_TRACKED_IDS:]
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
    last = _parse_time(str(state.get("last_response_at") or ""))
    if last is None:
        return 0.0
    elapsed = (datetime.now(UTC) - last).total_seconds()
    return max(0.0, round(cooldown_seconds - elapsed, 3))


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _items(transcript: dict[str, object]) -> list[dict[str, object]]:
    items = transcript.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _item_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "")


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _one_line(value: object, *, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _governance() -> dict[str, object]:
    return {
        "responder": "developer_bridge_codex_relay_responder_v0",
        "source_filter": "*->codex",
        "reply_target": "source_agent",
        "append_only_relay_writes": True,
        "state_write": "developer_bridge/codex_responder/state.json",
        "executes_prompt": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "requires_operator_review": True,
        "raw_shell": False,
        "external_network": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
