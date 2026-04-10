from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from francis.kernel.paths import repo_root

__all__ = [
    "ContainmentPolicy",
    "ContainmentPlan",
    "ContainmentStep",
    "ContainmentReport",
    "NetworkIsolationMode",
    "ContainmentPlanner",
    "main",
]


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _is_windows() -> bool:
    return os.name == "nt"


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _norm_abs(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _run(cmd: list[str], *, timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        output = (p.stdout or "") + (p.stderr or "")
        return int(p.returncode), output.strip()
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def _dangerous_path(path: Path) -> bool:
    if _is_windows():
        drive = path.drive.upper()
        if path == Path(f"{drive}\\"):
            return True
        return any(
            str(path).lower().startswith(prefix)
            for prefix in (
                f"{drive.lower()}\\windows",
                f"{drive.lower()}\\program files",
                f"{drive.lower()}\\programdata",
            )
        )
    if path == Path("/"):
        return True
    return any(str(path).startswith(p) for p in ("/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sys", "/usr"))


class NetworkIsolationMode(str, Enum):
    none = "none"
    outbound = "outbound"
    all = "all"


@dataclass(frozen=True)
class ContainmentPolicy:
    root: str = ""
    out_dir: str | None = None
    quarantine_base: str | None = None
    dry_run: bool = True
    override_safety: bool = False
    allow_process_kill: bool = False
    allow_network_changes: bool = False
    allow_delete_or_move: bool = False
    quarantine_mode: str = "copy"
    zip_snapshots: bool = True
    cmd_timeout_sec: int = 30


@dataclass(frozen=True)
class ContainmentPlan:
    quarantine_paths: list[str] = field(default_factory=list)
    snapshot_paths: list[str] = field(default_factory=list)
    process_pids: list[int] = field(default_factory=list)
    process_names: list[str] = field(default_factory=list)
    network_mode: NetworkIsolationMode = NetworkIsolationMode.none
    notes: str = ""


@dataclass
class ContainmentStep:
    time: str
    action: str
    target: str
    status: str
    details: str = ""


@dataclass
class ContainmentReport:
    started: str
    finished: str
    host: dict[str, str]
    policy: dict[str, str]
    steps: list[ContainmentStep] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "started": self.started,
                "finished": self.finished,
                "host": self.host,
                "policy": self.policy,
                "steps": [s.__dict__ for s in self.steps],
                "artifacts": self.artifacts,
            },
            indent=2,
        )


class ContainmentPlanner:
    def __init__(self, policy: ContainmentPolicy | None = None) -> None:
        self.policy = policy or ContainmentPolicy()
        root_raw = (self.policy.root or "").strip()
        root = repo_root() if not root_raw else _norm_abs(root_raw)
        out_dir = _norm_abs(self.policy.out_dir) if self.policy.out_dir else root / "data" / "logs" / "operations"
        quarantine_base = (
            _norm_abs(self.policy.quarantine_base) if self.policy.quarantine_base else root / "data" / "quarantine"
        )

        self.root = root
        self.out_dir = out_dir
        self.quarantine_base = quarantine_base
        _safe_mkdir(self.out_dir)
        _safe_mkdir(self.quarantine_base)

        self.session_id = _ts()
        self.session_dir = self.quarantine_base / f"containment_{self.session_id}"
        _safe_mkdir(self.session_dir)

        self.log_path = self.out_dir / f"containment_{self.session_id}.log"
        self.report_path = self.out_dir / f"containment_{self.session_id}.report.json"
        self.manifest_path = self.session_dir / "manifest.jsonl"
        self._steps: list[ContainmentStep] = []

    def _add_step(self, action: str, target: str, status: str, details: str = "") -> None:
        self._steps.append(
            ContainmentStep(
                time=datetime.utcnow().isoformat(timespec="seconds"),
                action=action,
                target=target,
                status=status,
                details=details,
            )
        )
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(f"[{self._steps[-1].time}] {action} {target} {status} {details}\n")
        except Exception:
            pass

    def snapshot_paths(self, paths: list[str], *, label: str = "snapshot") -> str | None:
        if not paths:
            self._add_step("snapshot", "(none)", "SKIPPED", "No paths provided")
            return None

        snap_dir = self.session_dir / "snapshots"
        if not self.policy.dry_run:
            _safe_mkdir(snap_dir)

        copied: list[Path] = []
        for p in paths:
            src = _norm_abs(p)
            if not src.exists():
                self._add_step("snapshot", str(src), "SKIPPED", "Not found")
                continue
            if _dangerous_path(src) and not self.policy.override_safety:
                self._add_step("snapshot", str(src), "BLOCKED", "Dangerous path")
                continue

            dest = snap_dir / src.name
            if self.policy.dry_run:
                self._add_step("snapshot_copy", str(src), "DRYRUN", f"Would copy to: {dest}")
                copied.append(dest)
                continue
            try:
                if src.is_dir():
                    shutil.copytree(src, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dest)
                copied.append(dest)
                self._add_step("snapshot_copy", str(src), "OK", f"Copied to: {dest}")
            except Exception as exc:
                self._add_step("snapshot_copy", str(src), "FAILED", f"{type(exc).__name__}: {exc}")

        if not copied or not self.policy.zip_snapshots:
            return None

        zip_path = self.session_dir / f"{label}_{self.session_id}.zip"
        if self.policy.dry_run:
            self._add_step("snapshot_zip", str(zip_path), "DRYRUN", "Would create zip")
            return str(zip_path)

        try:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for item in copied:
                    if item.is_dir():
                        for file in item.rglob("*"):
                            if file.is_file():
                                z.write(file, arcname=str(file.relative_to(self.session_dir)))
                    else:
                        z.write(item, arcname=str(item.relative_to(self.session_dir)))
            self._add_step("snapshot_zip", str(zip_path), "OK", "Created zip")
            return str(zip_path)
        except Exception as exc:
            self._add_step("snapshot_zip", str(zip_path), "FAILED", f"{type(exc).__name__}: {exc}")
            return None

    def quarantine_paths(self, paths: list[str], *, reason: str = "suspicious") -> list[str]:
        if not paths:
            self._add_step("quarantine", "(none)", "SKIPPED", "No paths provided")
            return []

        qdir = self.session_dir / "quarantine"
        if not self.policy.dry_run:
            _safe_mkdir(qdir)

        mode = self.policy.quarantine_mode.strip().lower()
        if mode not in ("copy", "move"):
            mode = "copy"
        if mode == "move" and not self.policy.allow_delete_or_move:
            self._add_step("quarantine", str(qdir), "BLOCKED", "Move not allowed; using copy")
            mode = "copy"

        quarantined: list[str] = []
        for p in paths:
            src = _norm_abs(p)
            if not src.exists():
                self._add_step("quarantine", str(src), "SKIPPED", "Not found")
                continue
            if _dangerous_path(src) and not self.policy.override_safety:
                self._add_step("quarantine", str(src), "BLOCKED", "Dangerous path")
                continue

            dest = qdir / src.name
            if not self.policy.dry_run and dest.exists():
                dest = qdir / f"{src.name}_{_ts()}"

            if self.policy.dry_run:
                self._add_step("quarantine", str(src), "DRYRUN", f"Would {mode} -> {dest}")
                quarantined.append(str(dest))
                continue

            try:
                if src.is_dir():
                    if mode == "move":
                        shutil.move(str(src), str(dest))
                    else:
                        shutil.copytree(src, dest, dirs_exist_ok=True)
                else:
                    if mode == "move":
                        shutil.move(str(src), str(dest))
                    else:
                        shutil.copy2(src, dest)
                    try:
                        os.chmod(dest, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
                    except Exception:
                        pass
                quarantined.append(str(dest))
                self._add_step("quarantine", str(src), "OK", f"{mode} -> {dest}")
                with self.manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"source": str(src), "dest": str(dest), "reason": reason}) + "\n")
            except Exception as exc:
                self._add_step("quarantine", str(src), "FAILED", f"{type(exc).__name__}: {exc}")

        return quarantined

    def stop_process_pids(self, pids: list[int]) -> None:
        if not pids:
            self._add_step("stop_process", "(none)", "SKIPPED", "No PIDs provided")
            return
        if not self.policy.allow_process_kill:
            self._add_step("stop_process", ",".join(map(str, pids)), "BLOCKED", "Not allowed")
            return

        for pid in pids:
            target = f"pid:{pid}"
            if self.policy.dry_run:
                self._add_step("stop_process", target, "DRYRUN", "Would stop process")
                continue
            cmd = ["taskkill", "/PID", str(pid), "/F"] if _is_windows() else ["kill", "-9", str(pid)]
            code, out = _run(cmd, timeout=self.policy.cmd_timeout_sec)
            status = "OK" if code == 0 else "FAILED"
            self._add_step("stop_process", target, status, out[:500])

    def stop_process_names(self, names: list[str]) -> None:
        if not names:
            self._add_step("stop_process_name", "(none)", "SKIPPED", "No names provided")
            return
        if not self.policy.allow_process_kill:
            self._add_step("stop_process_name", ",".join(names), "BLOCKED", "Not allowed")
            return

        for name in names:
            n = name.strip()
            if not n:
                continue
            target = f"name:{n}"
            if self.policy.dry_run:
                self._add_step("stop_process_name", target, "DRYRUN", "Would stop by name")
                continue
            cmd = ["taskkill", "/IM", n, "/F"] if _is_windows() else ["pkill", "-9", n]
            code, out = _run(cmd, timeout=self.policy.cmd_timeout_sec)
            status = "OK" if code == 0 else "FAILED"
            self._add_step("stop_process_name", target, status, out[:500])

    def isolate_network(self, mode: NetworkIsolationMode) -> None:
        if mode == NetworkIsolationMode.none:
            self._add_step("network_isolate", "none", "SKIPPED", "Mode=none")
            return
        if not self.policy.allow_network_changes:
            self._add_step("network_isolate", mode.value, "BLOCKED", "Not allowed")
            return
        if self.policy.dry_run:
            self._add_step("network_isolate", mode.value, "DRYRUN", "Would adjust firewall")
            return

        if _is_windows():
            cmds = [["netsh", "advfirewall", "set", "allprofiles", "state", "on"]]
            if mode in (NetworkIsolationMode.outbound, NetworkIsolationMode.all):
                cmds.append(
                    ["netsh", "advfirewall", "set", "allprofiles", "firewallpolicy", "blockinbound,blockoutbound"]
                )
            for cmd in cmds:
                code, out = _run(cmd, timeout=self.policy.cmd_timeout_sec)
                status = "OK" if code == 0 else "FAILED"
                self._add_step("network_isolate", " ".join(cmd), status, out[:500])
        else:
            if shutil.which("ufw"):
                cmds = [["ufw", "--force", "enable"]]
                if mode in (NetworkIsolationMode.outbound, NetworkIsolationMode.all):
                    cmds.append(["ufw", "default", "deny", "outgoing"])
                if mode == NetworkIsolationMode.all:
                    cmds.append(["ufw", "default", "deny", "incoming"])
                for cmd in cmds:
                    code, out = _run(cmd, timeout=self.policy.cmd_timeout_sec)
                    status = "OK" if code == 0 else "FAILED"
                    self._add_step("network_isolate", " ".join(cmd), status, out[:500])
            else:
                self._add_step("network_isolate", mode.value, "SKIPPED", "ufw not available")

    def finalize_report(self) -> ContainmentReport:
        report = ContainmentReport(
            started=self.session_id,
            finished=_ts(),
            host={
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "hostname": platform.node(),
            },
            policy={
                "root": str(self.root),
                "out_dir": str(self.out_dir),
                "quarantine_base": str(self.quarantine_base),
                "session_dir": str(self.session_dir),
                "dry_run": str(self.policy.dry_run),
                "override_safety": str(self.policy.override_safety),
                "allow_process_kill": str(self.policy.allow_process_kill),
                "allow_network_changes": str(self.policy.allow_network_changes),
                "allow_delete_or_move": str(self.policy.allow_delete_or_move),
                "quarantine_mode": self.policy.quarantine_mode,
            },
            steps=list(self._steps),
            artifacts={
                "log": str(self.log_path),
                "report": str(self.report_path),
                "session_dir": str(self.session_dir),
                "manifest": str(self.manifest_path),
            },
        )

        try:
            self.report_path.write_text(report.to_json() + "\n", encoding="utf-8")
            self._add_step("write_report", str(self.report_path), "OK", "Wrote JSON report")
        except Exception as exc:
            self._add_step("write_report", str(self.report_path), "FAILED", f"{type(exc).__name__}: {exc}")

        return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="containment")
    parser.add_argument("--root", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--override-safety", action="store_true")
    parser.add_argument("--allow-kill", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--allow-delete-or-move", action="store_true")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--quarantine-base", default="")
    parser.add_argument("--quarantine-mode", default="copy", choices=["copy", "move"])
    parser.add_argument("--quarantine-path", action="append", default=[])
    parser.add_argument("--quarantine-reason", default="suspicious")
    parser.add_argument("--snapshot-path", action="append", default=[])
    parser.add_argument("--no-zip-snapshots", action="store_true")
    parser.add_argument("--kill-pid", action="append", default=[])
    parser.add_argument("--kill-name", action="append", default=[])
    parser.add_argument("--network-isolate", default="none", choices=[m.value for m in NetworkIsolationMode])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    policy = ContainmentPolicy(
        root=args.root,
        out_dir=args.out_dir or None,
        quarantine_base=args.quarantine_base or None,
        dry_run=not bool(args.apply),
        override_safety=bool(args.override_safety),
        allow_process_kill=bool(args.allow_kill),
        allow_network_changes=bool(args.allow_network),
        allow_delete_or_move=bool(args.allow_delete_or_move),
        quarantine_mode=args.quarantine_mode,
        zip_snapshots=not bool(args.no_zip_snapshots),
    )

    engine = ContainmentPlanner(policy)
    if args.snapshot_path:
        engine.snapshot_paths(args.snapshot_path, label="snapshot")

    pids: list[int] = []
    for raw in args.kill_pid:
        try:
            pids.append(int(str(raw).strip()))
        except Exception:
            engine._add_step("parse_pid", str(raw), "FAILED", "Not an int")
    if pids:
        engine.stop_process_pids(pids)

    if args.kill_name:
        engine.stop_process_names(args.kill_name)

    if args.quarantine_path:
        engine.quarantine_paths(args.quarantine_path, reason=args.quarantine_reason)

    try:
        mode = NetworkIsolationMode(args.network_isolate)
    except Exception:
        mode = NetworkIsolationMode.none
    engine.isolate_network(mode)

    report = engine.finalize_report()
    failed = sum(1 for s in report.steps if s.status == "FAILED")
    print(f"FAILED: {failed}")
    print(f"Log: {report.artifacts.get('log')}")
    print(f"Report: {report.artifacts.get('report')}")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
