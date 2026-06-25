from __future__ import annotations

import argparse
import json
import sys
import textwrap
import time
from typing import TextIO

from .collaboration import read_collaboration_transcript
from .repo_tools import DeveloperBridgeError


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.watch:
            if args.new_only:
                _watch_new_items(args, sys.stdout)
                return 0
            while True:
                _print_transcript(args, sys.stdout)
                sys.stdout.flush()
                time.sleep(args.poll_seconds)
        _print_transcript(args, sys.stdout)
    except KeyboardInterrupt:
        return 0
    except DeveloperBridgeError as exc:
        print(json.dumps(exc.to_dict(), indent=2, sort_keys=True), file=sys.stderr)
        return 2
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="collaboration_log",
        description="Read the Francis developer bridge collaboration relay transcript.",
    )
    parser.add_argument("--agent", default="", help="Filter to relay entries involving this agent.")
    parser.add_argument("--source-agent", default="", help="Filter to relay entries from this agent.")
    parser.add_argument("--target-agent", default="", help="Filter to relay entries for this agent.")
    parser.add_argument(
        "--status",
        default="",
        choices=["", "queued", "acknowledged", "delivered", "blocked", "closed"],
        help="Filter by relay status. Empty means all statuses.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum relay entries to display, capped at 50.")
    parser.add_argument("--json", action="store_true", help="Print the bounded transcript payload as JSON.")
    parser.add_argument("--brief", action="store_true", help="Print only the operator-facing messages.")
    parser.add_argument("--hide-auto-acks", action="store_true", help="Hide generic Codex auto-ack relay entries.")
    parser.add_argument("--watch", action="store_true", help="Poll and print the transcript repeatedly.")
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="With --watch, print only relay entries created after the watcher starts.",
    )
    parser.add_argument("--poll-seconds", type=float, default=15.0, help="Polling interval for --watch.")
    return parser


def _print_transcript(args: argparse.Namespace, out: TextIO) -> None:
    result = _read_transcript(args)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True), file=out)
        return
    _write_text(result, args, out)


def _read_transcript(args: argparse.Namespace) -> dict[str, object]:
    return read_collaboration_transcript(
        agent=args.agent,
        source_agent=args.source_agent,
        target_agent=args.target_agent,
        status=args.status,
        limit=args.limit,
    )


def _watch_new_items(args: argparse.Namespace, out: TextIO) -> None:
    result = _read_transcript(args)
    seen = _seen_item_ids(result)
    _write_watch_header(result, args, out)
    out.flush()
    while True:
        time.sleep(args.poll_seconds)
        result = _read_transcript(args)
        for item in _visible_items(_new_items_since(result, seen), args):
            if args.json:
                print(json.dumps(item, indent=2, ensure_ascii=False, sort_keys=True), file=out)
            elif args.brief:
                _write_brief_item(item, out)
            else:
                _write_item(item, out)
        out.flush()


def _write_watch_header(result: dict[str, object], args: argparse.Namespace, out: TextIO) -> None:
    filters = result.get("filters")
    if not isinstance(filters, dict):
        filters = {}
    if args.brief:
        print("Francis Communication - messages only", file=out)
        print("new messages only; existing backlog suppressed", file=out)
        print("", file=out)
        return
    else:
        print("Francis developer bridge collaboration follow mode", file=out)
    print("mode: new relay entries only; existing backlog is suppressed", file=out)
    print(f"relay_root: {result.get('relay_root', '')}", file=out)
    print(
        "filters: "
        f"agent={filters.get('agent', '') or '*'} "
        f"source={filters.get('source_agent', '') or '*'} "
        f"target={filters.get('target_agent', '') or '*'} "
        f"status={filters.get('status', '') or '*'} "
        f"limit={filters.get('limit', '')}",
        file=out,
    )
    print("", file=out)


def _seen_item_ids(result: dict[str, object]) -> set[str]:
    return {item_id for item in _iter_items(result) if (item_id := _item_id(item))}


def _new_items_since(result: dict[str, object], seen: set[str]) -> list[dict[str, object]]:
    new_items: list[dict[str, object]] = []
    for item in reversed(_iter_items(result)):
        item_id = _item_id(item)
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        new_items.append(item)
    return new_items


def _iter_items(result: dict[str, object]) -> list[dict[str, object]]:
    items = result.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _item_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "")


def _write_text(result: dict[str, object], args: argparse.Namespace, out: TextIO) -> None:
    filters = result.get("filters")
    if not isinstance(filters, dict):
        filters = {}
    if args.brief:
        print("Francis Communication - messages only", file=out)
        print("", file=out)
        items = result.get("items")
        visible = _visible_items(items, args)
        if not visible:
            print("No operator-facing relay messages matched the filters.", file=out)
            return
        for item in visible:
            _write_brief_item(item, out)
        return

    print("Francis developer bridge collaboration transcript", file=out)
    print(f"relay_root: {result.get('relay_root', '')}", file=out)
    print(
        "filters: "
        f"agent={filters.get('agent', '') or '*'} "
        f"source={filters.get('source_agent', '') or '*'} "
        f"target={filters.get('target_agent', '') or '*'} "
        f"status={filters.get('status', '') or '*'} "
        f"limit={filters.get('limit', '')}",
        file=out,
    )
    print("scope: Francis relay receipts only; no raw MCP stream or private model chat.", file=out)
    print("", file=out)

    items = result.get("items")
    if not isinstance(items, list) or not items:
        print("No collaboration relay records matched the filters.", file=out)
        return

    for item in _visible_items(items, args):
        if not isinstance(item, dict):
            continue
        if args.brief:
            _write_brief_item(item, out)
        else:
            _write_item(item, out)


def _write_item(item: dict[str, object], out: TextIO) -> None:
    print(
        f"[{item.get('created_at', '')}] {item.get('status', '')} {item.get('direction', '')} {item.get('id', '')}",
        file=out,
    )
    _write_field("objective", item.get("objective"), out)
    _write_field("prompt", item.get("prompt"), out)
    _write_field("context", item.get("context"), out)
    handoff = item.get("chat_handoff")
    if isinstance(handoff, dict):
        _write_field("chat", handoff.get("chat_text"), out)
        print(
            "  chat_echo_required: "
            f"source={handoff.get('source_chat_echo_required')} "
            f"target={handoff.get('target_chat_echo_required')}",
            file=out,
        )
    governance = item.get("governance")
    if isinstance(governance, dict):
        print(
            "  governance: "
            f"executes_prompt={governance.get('executes_prompt')} "
            f"mutation_authority={governance.get('grants_mutation_authority')} "
            f"operator_review={governance.get('requires_operator_review')}",
            file=out,
        )
    print("", file=out)


def _write_brief_item(item: dict[str, object], out: TextIO) -> None:
    timestamp = _brief_time(item.get("created_at"))
    direction = str(item.get("direction") or "").replace("->", " -> ")
    prompt = _clean_message(item.get("prompt"))
    objective = _clean_message(item.get("objective"))
    message = prompt or objective or "(empty relay message)"
    wrapped = textwrap.fill(message, width=110, subsequent_indent="    ")
    print(f"[{timestamp}] {direction}", file=out)
    print(f"  {wrapped}", file=out)
    print("", file=out)


def _write_field(label: str, value: object, out: TextIO) -> None:
    text = str(value or "").strip()
    if not text:
        return
    wrapped = textwrap.fill(text, width=96, subsequent_indent="  ")
    print(f"  {label}: {wrapped}", file=out)


def _visible_items(items: object, args: argparse.Namespace) -> list[dict[str, object]]:
    if not isinstance(items, list):
        return []
    records = [item for item in items if isinstance(item, dict)]
    if getattr(args, "hide_auto_acks", False):
        records = [item for item in records if not _is_auto_ack(item)]
    return records


def _is_auto_ack(item: dict[str, object]) -> bool:
    objective = str(item.get("objective") or "").lower()
    context = str(item.get("context") or "").lower()
    prompt = str(item.get("prompt") or "").lower()
    return (
        objective.startswith("auto-ack ") or "no_response_requested=true" in context or prompt.startswith("auto-ack ")
    )


def _brief_time(value: object) -> str:
    text = str(value or "").strip()
    if "T" in text:
        return text.split("T", 1)[1].split(".", 1)[0]
    return text or "unknown-time"


def _clean_message(value: object) -> str:
    return " ".join(str(value or "").split())


if __name__ == "__main__":
    raise SystemExit(main())
