from __future__ import annotations

import argparse
import json
import logging
import re
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

CANARY_PREFIX = "FRANCIS_CANARY_"

__all__ = [
    "HoneypotGenerator",
    "HoneyArtifact",
    "GenerateOptions",
    "generate_honeypots",
    "load_registry",
    "save_registry",
    "scan_path",
    "main",
]


@dataclass(frozen=True)
class HoneyArtifact:
    artifact_id: str
    kind: str
    name: str
    path: str | None
    canary_token: str
    created_utc: str
    notes: str = ""


@dataclass(frozen=True)
class GenerateOptions:
    target_dir: str
    count: int = 5
    overwrite: bool = False


class HoneypotGenerator:
    _active: bool = False

    @classmethod
    def initialize(cls) -> None:
        cls._active = True

    @classmethod
    def is_active(cls) -> bool:
        return cls._active

    def generate(self, opts: GenerateOptions) -> list[HoneyArtifact]:
        return generate_honeypots(opts)


def _utc_now() -> str:
    return __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _make_canary(artifact_id: str) -> str:
    return f"{CANARY_PREFIX}{artifact_id}"


def _write_text(path: Path, content: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"File exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _template(canary: str) -> str:
    return "\n".join(
        [
            "CONFIDENTIAL - DECOY",
            "This file is a canary for detection.",
            f"token={canary}",
            "If this token appears outside approved systems, investigate.",
            "",
        ]
    )


def generate_honeypots(opts: GenerateOptions) -> list[HoneyArtifact]:
    target = Path(opts.target_dir)
    target.mkdir(parents=True, exist_ok=True)

    artifacts: list[HoneyArtifact] = []
    created = _utc_now()

    for i in range(max(0, int(opts.count))):
        artifact_id = secrets.token_hex(6).upper()
        canary = _make_canary(artifact_id)
        name = f"decoy_{i + 1}.txt"
        path = target / name
        if path.exists() and not opts.overwrite:
            name = f"decoy_{i + 1}_{artifact_id[:6]}.txt"
            path = target / name

        _write_text(path, _template(canary), overwrite=opts.overwrite)
        artifacts.append(
            HoneyArtifact(
                artifact_id=artifact_id,
                kind="honeyfile",
                name=name,
                path=str(path),
                canary_token=canary,
                created_utc=created,
                notes="decoy honeyfile",
            )
        )

    return artifacts


def load_registry(path: str | Path) -> list[HoneyArtifact]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [HoneyArtifact(**item) for item in data]
    except Exception as exc:
        logger.error("Failed to load registry: %s", exc)
        return []


def save_registry(path: str | Path, artifacts: Iterable[HoneyArtifact]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(a) for a in artifacts]
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def scan_text(text: str, tokens: set[str]) -> list[str]:
    hits = re.findall(rf"{re.escape(CANARY_PREFIX)}[A-F0-9]+", text)
    return [hit for hit in hits if hit in tokens]


def scan_path(registry: Iterable[HoneyArtifact], path: str | Path) -> list[str]:
    tokens = {a.canary_token for a in registry}
    target = Path(path)
    if not target.exists():
        return []

    if target.is_file():
        try:
            text = target.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        return scan_text(text, tokens)

    hits: list[str] = []
    for file in target.rglob("*"):
        if not file.is_file():
            continue
        if any(part.startswith(".") for part in file.parts):
            continue
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        hits.extend(scan_text(text, tokens))
    return hits


def _cmd_generate(args: argparse.Namespace) -> int:
    opts = GenerateOptions(target_dir=args.target, count=args.count, overwrite=args.overwrite)
    items = generate_honeypots(opts)
    reg_path = Path(args.target) / "honeypot_registry.json"
    existing = load_registry(reg_path)
    save_registry(reg_path, [*existing, *items])
    print(f"Generated {len(items)} honeypots in {args.target}")
    print(f"Registry: {reg_path}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    items = load_registry(args.registry)
    if not items:
        print("(no registry entries)")
        return 0
    for item in items:
        print(f"- {item.canary_token} {item.path or item.name}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    items = load_registry(args.registry)
    hits = scan_path(items, args.path)
    if not hits:
        print("No hits.")
        return 0
    print("Hits:")
    for hit in sorted(set(hits)):
        print(f"- {hit}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="honeypot_generator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate")
    gen.add_argument("--target", required=True)
    gen.add_argument("--count", type=int, default=5)
    gen.add_argument("--overwrite", action="store_true")
    gen.set_defaults(func=_cmd_generate)

    lst = sub.add_parser("list")
    lst.add_argument("--registry", required=True)
    lst.set_defaults(func=_cmd_list)

    scn = sub.add_parser("scan")
    scn.add_argument("--registry", required=True)
    scn.add_argument("--path", required=True)
    scn.set_defaults(func=_cmd_scan)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
