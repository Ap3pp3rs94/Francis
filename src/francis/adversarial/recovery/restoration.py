from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

__all__ = [
    "RestorationPolicy",
    "RestorationPlan",
    "RestorationStep",
    "RestorationReport",
    "RestorationRunner",
    "main",
]


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _iso_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _run_capture(cmd: list[str], *, timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        output = (p.stdout or "") + (p.stderr or "")
        return int(p.returncode), output.strip()
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def _dangerous_target(path: Path, *, override: bool) -> bool:
    if override:
        return False
    if os.name == "nt":
        drive_root = Path(f"{path.drive}\\")
        if path == drive_root:
            return True
        return any(
            str(path).lower().startswith(prefix)
            for prefix in (f"{path.drive.lower()}\\windows", f"{path.drive.lower()}\\program files")
        )
    if path == Path("/"):
        return True
    return any(str(path).startswith(p) for p in ("/etc", "/bin", "/usr", "/var", "/sys"))


def _within_root(child: Path, root: Path) -> bool:
    try:
        return str(child.resolve()).lower().startswith(str(root.resolve()).lower().rstrip("\\/") + os.sep)
    except Exception:
        return False


@dataclass(frozen=True)
class RestorationPolicy:
    root: Path
    plan_path: Path
    out_dir: Path
    session_dir: Path
    dry_run: bool = True
    timeout_sec: int = 60
    allow_outside_root: bool = False
    override_safety: bool = False
    default_overwrite: bool = True


@dataclass(frozen=True)
class RestorationStep:
    time: str
    kind: str
    name: str
    status: str
    details: str = ""


@dataclass(frozen=True)
class RestorationPlan:
    items: list[dict[str, Any]]
    post_commands: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RestorationReport:
    started: str
    finished: str
    host: dict[str, str]
    policy: dict[str, str]
    plan: dict[str, Any]
    steps: list[RestorationStep] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "started": self.started,
                "finished": self.finished,
                "host": self.host,
                "policy": self.policy,
                "plan": self.plan,
                "steps": [s.__dict__ for s in self.steps],
                "artifacts": self.artifacts,
            },
            indent=2,
        )


def load_plan(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Plan not found: {path}")
    raw = path.read_text(encoding="utf-8", errors="replace")
    return json.loads(raw)


def write_template_plan(path: Path) -> None:
    template = {
        "version": 1,
        "created": _iso_now(),
        "items": [
            {
                "action": "copy_file",
                "source": str(path.parent / "backups" / "good" / "example.txt"),
                "target": str(path.parent / "restored" / "example.txt"),
                "overwrite": True,
            }
        ],
        "post_commands": [{"name": "restart_service", "cmd": ["echo", "restart"], "allow": False}],
    }
    _safe_mkdir(path.parent)
    path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")


class RestorationRunner:
    def __init__(self, policy: RestorationPolicy) -> None:
        self.p = policy
        self.steps: list[RestorationStep] = []
        _safe_mkdir(self.p.out_dir)
        _safe_mkdir(self.p.session_dir)

        self.log_path = self.p.out_dir / f"restoration_{self.p.session_dir.name}.log"
        self.report_path = self.p.out_dir / f"restoration_{self.p.session_dir.name}.report.json"
        self.manifest_path = self.p.session_dir / "manifest.jsonl"

    def _add_step(self, kind: str, name: str, status: str, details: str = "") -> None:
        self.steps.append(RestorationStep(time=_iso_now(), kind=kind, name=name, status=status, details=details))
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(f"[{self.steps[-1].time}] {kind} {name} {status} {details}\n")
        except Exception:
            pass

    def _append_manifest(self, obj: dict[str, Any]) -> None:
        try:
            with self.manifest_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj) + "\n")
        except Exception:
            self._add_step("note", "manifest", "WARN", "Failed writing manifest")

    def _validate_target(self, target: Path) -> tuple[bool, str]:
        if _dangerous_target(target, override=self.p.override_safety):
            return False, f"Dangerous target: {target}"
        if not self.p.allow_outside_root and not _within_root(target, self.p.root):
            return False, f"Outside root: {target}"
        return True, "OK"

    def _copy_file(self, source: Path, target: Path, overwrite: bool) -> None:
        if not source.exists():
            self._add_step("copy_file", str(source), "FAILED", "Source missing")
            return
        ok, reason = self._validate_target(target)
        if not ok:
            self._add_step("copy_file", str(target), "FAILED", reason)
            return
        if target.exists() and not overwrite:
            self._add_step("copy_file", str(target), "SKIPPED", "Overwrite disabled")
            return
        if self.p.dry_run:
            self._add_step("copy_file", f"{source} -> {target}", "WHATIF")
            return
        try:
            _safe_mkdir(target.parent)
            shutil.copy2(source, target)
            self._add_step("copy_file", f"{source} -> {target}", "OK")
            self._append_manifest({"type": "copy_file", "source": str(source), "target": str(target)})
        except Exception as exc:
            self._add_step("copy_file", f"{source} -> {target}", "FAILED", f"{type(exc).__name__}: {exc}")

    def _copy_tree(self, source: Path, target: Path, overwrite: bool) -> None:
        if not source.exists() or not source.is_dir():
            self._add_step("copy_tree", str(source), "FAILED", "Source missing or not dir")
            return
        ok, reason = self._validate_target(target)
        if not ok:
            self._add_step("copy_tree", str(target), "FAILED", reason)
            return
        if target.exists() and not overwrite:
            self._add_step("copy_tree", str(target), "SKIPPED", "Overwrite disabled")
            return
        if self.p.dry_run:
            self._add_step("copy_tree", f"{source} -> {target}", "WHATIF")
            return
        try:
            if target.exists() and overwrite:
                shutil.rmtree(target)
            shutil.copytree(source, target, dirs_exist_ok=False)
            self._add_step("copy_tree", f"{source} -> {target}", "OK")
            self._append_manifest({"type": "copy_tree", "source": str(source), "target": str(target)})
        except Exception as exc:
            self._add_step("copy_tree", f"{source} -> {target}", "FAILED", f"{type(exc).__name__}: {exc}")

    def _write_text(self, target: Path, content: str, overwrite: bool) -> None:
        ok, reason = self._validate_target(target)
        if not ok:
            self._add_step("write_text", str(target), "FAILED", reason)
            return
        if target.exists() and not overwrite:
            self._add_step("write_text", str(target), "SKIPPED", "Overwrite disabled")
            return
        if self.p.dry_run:
            self._add_step("write_text", str(target), "WHATIF", f"bytes={len(content)}")
            return
        try:
            _safe_mkdir(target.parent)
            target.write_text(content, encoding="utf-8")
            self._add_step("write_text", str(target), "OK")
            self._append_manifest({"type": "write_text", "target": str(target)})
        except Exception as exc:
            self._add_step("write_text", str(target), "FAILED", f"{type(exc).__name__}: {exc}")

    def _run_post_command(self, name: str, cmd: list[str], allow: bool) -> None:
        if not allow:
            self._add_step("command", name, "SKIPPED", "Not allowed")
            return
        if self.p.dry_run:
            self._add_step("command", name, "WHATIF", " ".join(cmd))
            return
        code, out = _run_capture(cmd, timeout=self.p.timeout_sec)
        status = "OK" if code == 0 else "WARN"
        self._add_step("command", name, status, f"exit={code}")
        self._append_manifest({"type": "post_command", "name": name, "cmd": cmd, "exit": code})
        try:
            out_file = self.p.session_dir / "post_commands" / f"{name}.txt"
            _safe_mkdir(out_file.parent)
            out_file.write_text(out, encoding="utf-8")
        except Exception:
            pass

    def apply_plan(self, plan: dict[str, Any]) -> None:
        items = plan.get("items", [])
        if not isinstance(items, list):
            self._add_step("guard", "items", "FAILED", "items must be list")
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", "")).strip().lower()
            overwrite = bool(item.get("overwrite", self.p.default_overwrite))
            if action == "copy_file":
                self._copy_file(Path(str(item.get("source", ""))), Path(str(item.get("target", ""))), overwrite)
            elif action == "copy_tree":
                self._copy_tree(Path(str(item.get("source", ""))), Path(str(item.get("target", ""))), overwrite)
            elif action == "write_text":
                self._write_text(Path(str(item.get("target", ""))), str(item.get("content", "")), overwrite)
            else:
                self._add_step("action", action or "unknown", "SKIPPED", "Unsupported action")

        post = plan.get("post_commands", []) or []
        if isinstance(post, list):
            for cmd in post:
                if not isinstance(cmd, dict):
                    continue
                name = str(cmd.get("name", "post_command"))
                allow = bool(cmd.get("allow", False))
                cmd_list = cmd.get("cmd", [])
                if not isinstance(cmd_list, list) or not cmd_list:
                    self._add_step("command", name, "SKIPPED", "cmd missing")
                    continue
                self._run_post_command(name, [str(x) for x in cmd_list], allow)

    def finalize(self, plan: dict[str, Any]) -> RestorationReport:
        report = RestorationReport(
            started=self.p.session_dir.name,
            finished=_ts(),
            host={
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "hostname": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "",
                "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
            },
            policy={
                "root": str(self.p.root),
                "plan_path": str(self.p.plan_path),
                "out_dir": str(self.p.out_dir),
                "session_dir": str(self.p.session_dir),
                "dry_run": str(self.p.dry_run),
                "timeout_sec": str(self.p.timeout_sec),
                "allow_outside_root": str(self.p.allow_outside_root),
                "override_safety": str(self.p.override_safety),
            },
            plan=plan,
            steps=list(self.steps),
            artifacts={
                "log": str(self.log_path),
                "report": str(self.report_path),
                "manifest": str(self.manifest_path),
                "session_dir": str(self.p.session_dir),
            },
        )

        try:
            self.report_path.write_text(report.to_json() + "\n", encoding="utf-8")
            self._add_step("report", "write", "OK", str(self.report_path))
        except Exception as exc:
            self._add_step("report", "write", "FAILED", f"{type(exc).__name__}: {exc}")

        return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="restoration")
    parser.add_argument("--root", default="")
    parser.add_argument("--plan", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--session-base", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--timeout-sec", type=int, default=60)
    parser.add_argument("--allow-outside-root", action="store_true")
    parser.add_argument("--override-safety", action="store_true")
    parser.add_argument("--init-plan", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repo_root() if not str(args.root).strip() else Path(args.root).expanduser().resolve()
    plan_path = Path(args.plan) if args.plan else root / "data" / "config" / "restoration-plan.json"
    plan_path = plan_path.expanduser().resolve()
    out_dir = Path(args.out_dir) if args.out_dir else root / "data" / "logs" / "operations"
    out_dir = out_dir.expanduser().resolve()
    session_base = Path(args.session_base) if args.session_base else root / "data" / "restoration"
    session_base = session_base.expanduser().resolve()
    session_dir = session_base / f"restoration_{_ts()}"

    policy = RestorationPolicy(
        root=root,
        plan_path=plan_path,
        out_dir=out_dir,
        session_dir=session_dir,
        dry_run=not bool(args.apply),
        timeout_sec=max(1, int(args.timeout_sec)),
        allow_outside_root=bool(args.allow_outside_root),
        override_safety=bool(args.override_safety),
    )

    runner = RestorationRunner(policy)

    if args.init_plan:
        write_template_plan(plan_path)
        runner._add_step("note", "init_plan", "OK", f"Wrote template: {plan_path}")
        runner.finalize({"version": 1, "notes": "template_created"})
        return 0

    try:
        plan = load_plan(plan_path)
    except Exception as exc:
        runner._add_step("guard", "load_plan", "FAILED", f"{type(exc).__name__}: {exc}")
        runner.finalize({"error": "load_plan_failed"})
        return 1

    runner.apply_plan(plan)
    report = runner.finalize(plan)
    failed = sum(1 for s in report.steps if s.status == "FAILED")
    print(f"FAILED: {failed}")
    print(f"Report: {report.artifacts.get('report')}")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
