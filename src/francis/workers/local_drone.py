from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from francis.llm import client as llm_client

DEFAULT_LOCAL_DRONE_MODEL = "llama3.2:3b"
DEFAULT_STATE_ROOT = ".francis/local-drones"
DEFAULT_MAX_CONTEXT_CHARS = 24000


@dataclass(frozen=True)
class LocalDroneResult:
    status: str
    worker_id: str
    drone_id: str
    model: str
    task: str
    context_path: str
    context_sha256: str
    context_chars_used: int
    packet_path: str
    receipt_path: str
    provider: str = "ollama"
    authority: str = "advisory_only"
    can_commit: bool = False
    can_push: bool = False
    can_claim_completion: bool = False


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_context(path: Path, *, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS) -> tuple[str, str, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars], _sha256_text(text), min(len(text), max_chars)


def build_local_drone_prompt(*, task: str, context_text: str) -> str:
    return f"""You are a short-lived Francis local-model drone.

Your output is advisory evidence only. You do not own architecture, commit,
push, claim completion, request broad rewrites, or bypass governance.

Task:
{task}

Context:
{context_text}

Return exactly these sections:

STATUS
FILES INSPECTED
FILES CHANGED
EXACT CHANGE OR ANALYSIS
VALIDATION TO RUN
RISKS
RECOMMENDED NEXT STEP
"""


def run_local_drone(
    *,
    task: str,
    context_path: Path,
    worker_id: str,
    drone_id: str,
    state_root: Path,
    model: str = DEFAULT_LOCAL_DRONE_MODEL,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    call_model: bool = True,
    generate: Callable[..., str] = llm_client.generate,
) -> LocalDroneResult:
    context_text, context_sha256, context_chars_used = read_context(
        context_path,
        max_chars=max_context_chars,
    )
    prompt = build_local_drone_prompt(task=task, context_text=context_text)
    response = ""
    status = "skipped"
    if call_model:
        response = generate(prompt, model=model)
        status = "completed" if response else "unavailable"

    state_root.mkdir(parents=True, exist_ok=True)
    packet_dir = state_root / worker_id
    packet_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    safe_drone_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in drone_id)[:80]
    packet_path = packet_dir / f"{stamp}-{safe_drone_id}.md"
    receipt_path = state_root / "receipts.jsonl"
    packet_text = "\n".join(
        [
            "# Francis Local Drone Packet",
            "",
            f"status: {status}",
            "provider: ollama",
            f"model: {model}",
            f"worker_id: {worker_id}",
            f"drone_id: {drone_id}",
            "authority: advisory_only",
            "can_commit: false",
            "can_push: false",
            "can_claim_completion: false",
            f"context_path: {context_path}",
            f"context_sha256: {context_sha256}",
            f"context_chars_used: {context_chars_used}",
            "",
            "## Task",
            "",
            task,
            "",
            "## Local Model Output",
            "",
            response
            if response
            else "No local-model output was produced. Treat this packet as unavailable/skipped evidence.",
            "",
        ]
    )
    packet_path.write_text(packet_text, encoding="utf-8")

    result = LocalDroneResult(
        status=status,
        worker_id=worker_id,
        drone_id=drone_id,
        model=model,
        task=task,
        context_path=str(context_path),
        context_sha256=context_sha256,
        context_chars_used=context_chars_used,
        packet_path=str(packet_path),
        receipt_path=str(receipt_path),
    )
    receipt = {
        "kind": "francis.local_drone.receipt",
        "at": datetime.now(UTC).isoformat(),
        **asdict(result),
    }
    with receipt_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an advisory local-model drone packet.")
    parser.add_argument("--task", required=True)
    parser.add_argument("--context-path", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--drone-id", default="drone-1")
    parser.add_argument("--state-root", default=DEFAULT_STATE_ROOT)
    parser.add_argument("--model", default=DEFAULT_LOCAL_DRONE_MODEL)
    parser.add_argument("--max-context-chars", type=int, default=DEFAULT_MAX_CONTEXT_CHARS)
    parser.add_argument("--no-model-call", action="store_true")
    args = parser.parse_args(argv)

    result = run_local_drone(
        task=args.task,
        context_path=Path(args.context_path),
        worker_id=args.worker_id,
        drone_id=args.drone_id,
        state_root=Path(args.state_root),
        model=args.model,
        max_context_chars=max(1000, min(args.max_context_chars, DEFAULT_MAX_CONTEXT_CHARS)),
        call_model=not args.no_model_call,
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
