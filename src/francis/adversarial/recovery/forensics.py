from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from francis.kernel.paths import repo_root

__all__ = [
    "ForensicsPolicy",
    "ForensicsStep",
    "ForensicsReport",
    "CommandSpec",
    "ForensicsRunner",
    "main",
]


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _run_capture(cmd: list[str], *, timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        output = (p.stdout or "") + (p.stderr or "")
        return int(p.returncode), output.strip()
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def _sha256_file(path: Path, *, max_bytes: int) -> str:
    h = hashlib.sha256()
    read = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            read += len(chunk)
            if max_bytes > 0 and read >= max_bytes:
                break
    return h.hexdigest()


@dataclass(frozen=True)
class ForensicsPolicy:
    root: str = ""
    out_dir: str | None = None
    session_base: str | None = None
    timeout_sec: int = 30
    include_dirs: bool = False
    max_artifact_bytes: int = 250_000_000
    max_hash_bytes: int = 50_000_000
    make_zip: bool = False


@dataclass
class ForensicsStep:
    time: str
    kind: str
    name: str
    status: str
    details: str = ""


@dataclass
class ForensicsReport:
    started: str
    finished: str
    host: dict[str, str]
    policy: dict[str, str]
    steps: list[ForensicsStep] = field(default_factory=list)
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


@dataclass(frozen=True)
class CommandSpec:
    name: str
    cmd: list[str]
    platform: str = "any"


class ForensicsRunner:
    def __init__(self, policy: ForensicsPolicy | None = None) -> None:
        self.policy = policy or ForensicsPolicy()
        root_raw = (self.policy.root or "").strip()
        root = repo_root() if not root_raw else Path(root_raw).expanduser().resolve()
        out_dir = (
            Path(self.policy.out_dir).expanduser().resolve()
            if self.policy.out_dir
            else root / "data" / "logs" / "operations"
        )
        session_base = (
            Path(self.policy.session_base).expanduser().resolve()
            if self.policy.session_base
            else root / "data" / "forensics"
        )

        self.root = root
        self.out_dir = out_dir
        self.session_base = session_base
        _safe_mkdir(self.out_dir)
        _safe_mkdir(self.session_base)

        self.session_id = _ts()
        self.session_dir = self.session_base / f"forensics_{self.session_id}"
        self.commands_dir = self.session_dir / "commands"
        self.artifacts_dir = self.session_dir / "artifacts"
        _safe_mkdir(self.commands_dir)
        _safe_mkdir(self.artifacts_dir)

        self.log_path = self.out_dir / f"forensics_{self.session_id}.log"
        self.report_path = self.out_dir / f"forensics_{self.session_id}.report.json"
        self.manifest_path = self.session_dir / "manifest.jsonl"
        self._steps: list[ForensicsStep] = []

    def _add_step(self, kind: str, name: str, status: str, details: str = "") -> None:
        self._steps.append(
            ForensicsStep(
                time=datetime.utcnow().isoformat(timespec="seconds"),
                kind=kind,
                name=name,
                status=status,
                details=details,
            )
        )
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(f"[{self._steps[-1].time}] {kind} {name} {status} {details}\n")
        except Exception:
            pass

    def _append_manifest(self, obj: dict) -> None:
        try:
            with self.manifest_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj) + "\n")
        except Exception:
            self._add_step("note", "manifest", "WARN", "Failed writing manifest")

    def _platform_ok(self, spec: CommandSpec) -> bool:
        if spec.platform == "any":
            return True
        if spec.platform == "windows":
            return os.name == "nt"
        if spec.platform == "linux":
            return platform.system().lower() == "linux"
        if spec.platform == "darwin":
            return platform.system().lower() == "darwin"
        return True

    def run_command(self, spec: CommandSpec) -> str | None:
        if not self._platform_ok(spec):
            self._add_step("command", spec.name, "SKIPPED", f"platform={spec.platform}")
            return None

        out_file = self.commands_dir / f"{spec.name}.txt"
        code, out = _run_capture(spec.cmd, timeout=self.policy.timeout_sec)
        try:
            out_file.write_text(
                f"NAME: {spec.name}\nCMD: {' '.join(spec.cmd)}\nEXIT: {code}\n\n{out}\n",
                encoding="utf-8",
            )
        except Exception as exc:
            self._add_step("command", spec.name, "FAILED", f"write: {type(exc).__name__}")
            return None

        status = "OK" if code == 0 else "WARN"
        self._add_step("command", spec.name, status, f"output={out_file}")
        self._append_manifest({"type": "command", "name": spec.name, "cmd": spec.cmd, "output": str(out_file)})
        return str(out_file)

    def default_commands(self) -> list[CommandSpec]:
        if os.name == "nt":
            return [
                CommandSpec("whoami", ["whoami", "/all"], platform="windows"),
                CommandSpec("systeminfo", ["systeminfo"], platform="windows"),
                CommandSpec("ipconfig", ["ipconfig", "/all"], platform="windows"),
                CommandSpec("tasklist", ["tasklist", "/v"], platform="windows"),
            ]
        sysname = platform.system().lower()
        if sysname == "linux":
            return [
                CommandSpec("uname", ["uname", "-a"], platform="linux"),
                CommandSpec("ip_addr", ["ip", "a"], platform="linux"),
                CommandSpec("ps", ["ps", "auxww"], platform="linux"),
            ]
        if sysname == "darwin":
            return [
                CommandSpec("uname", ["uname", "-a"], platform="darwin"),
                CommandSpec("ifconfig", ["ifconfig"], platform="darwin"),
                CommandSpec("ps", ["ps", "auxww"], platform="darwin"),
            ]
        return [CommandSpec("uname", ["uname", "-a"], platform="any")]

    def collect_baseline(self) -> None:
        for spec in self.default_commands():
            self.run_command(spec)

    def collect_artifacts(self, paths: list[str]) -> None:
        if not paths:
            self._add_step("artifact", "(none)", "SKIPPED", "No artifact paths")
            return
        for p in paths:
            src = Path(p).expanduser().resolve()
            if not src.exists():
                self._add_step("artifact", str(src), "SKIPPED", "Not found")
                continue
            try:
                if src.is_dir():
                    if not self.policy.include_dirs:
                        self._add_step("artifact", str(src), "SKIPPED", "Dir excluded")
                        continue
                    self._zip_directory(src)
                else:
                    self._copy_file(src)
            except Exception as exc:
                self._add_step("artifact", str(src), "FAILED", f"{type(exc).__name__}: {exc}")

    def _copy_file(self, src: Path) -> None:
        size = src.stat().st_size
        if self.policy.max_artifact_bytes > 0 and size > self.policy.max_artifact_bytes:
            self._add_step("artifact", str(src), "SKIPPED", "File too large")
            return
        dest = self.artifacts_dir / src.name
        if dest.exists():
            dest = self.artifacts_dir / f"{src.stem}_{_ts()}{src.suffix}"
        shutil.copy2(src, dest)
        sha = _sha256_file(dest, max_bytes=self.policy.max_hash_bytes)
        self._add_step("artifact", str(src), "OK", f"copied={dest}")
        self._append_manifest({"type": "file", "source": str(src), "dest": str(dest), "sha256": sha})

    def _zip_directory(self, src_dir: Path) -> None:
        dest = self.artifacts_dir / f"{src_dir.name}.zip"
        if dest.exists():
            dest = self.artifacts_dir / f"{src_dir.name}_{_ts()}.zip"
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for file in src_dir.rglob("*"):
                if file.is_file():
                    z.write(file, arcname=str(file.relative_to(src_dir)))
        sha = _sha256_file(dest, max_bytes=self.policy.max_hash_bytes)
        self._add_step("artifact", str(src_dir), "OK", f"zipped={dest}")
        self._append_manifest({"type": "dir_zip", "source": str(src_dir), "dest": str(dest), "sha256": sha})

    def make_zip_bundle(self) -> str | None:
        zip_path = self.out_dir / f"forensics_{self.session_id}.zip"
        try:
            if zip_path.exists():
                zip_path.unlink()
        except Exception:
            pass
        try:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for file in self.session_dir.rglob("*"):
                    if file.is_file():
                        z.write(file, arcname=str(file.relative_to(self.session_dir)))
            self._add_step("zip", str(zip_path), "OK", "Bundled session")
            self._append_manifest({"type": "zip_bundle", "zip_path": str(zip_path)})
            return str(zip_path)
        except Exception as exc:
            self._add_step("zip", str(zip_path), "FAILED", f"{type(exc).__name__}: {exc}")
            return None

    def finalize_report(self) -> ForensicsReport:
        report = ForensicsReport(
            started=self.session_id,
            finished=_ts(),
            host={
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "hostname": platform.node(),
                "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
            },
            policy={
                "root": str(self.root),
                "out_dir": str(self.out_dir),
                "session_base": str(self.session_base),
                "session_dir": str(self.session_dir),
                "timeout_sec": str(self.policy.timeout_sec),
                "include_dirs": str(self.policy.include_dirs),
                "max_artifact_bytes": str(self.policy.max_artifact_bytes),
                "max_hash_bytes": str(self.policy.max_hash_bytes),
                "make_zip": str(self.policy.make_zip),
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
            self._add_step("report", str(self.report_path), "OK", "Wrote JSON report")
        except Exception as exc:
            self._add_step("report", str(self.report_path), "FAILED", f"{type(exc).__name__}: {exc}")

        return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="forensics")
    parser.add_argument("--root", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--session-base", default="")
    parser.add_argument("--timeout-sec", type=int, default=30)
    parser.add_argument("--artifact-path", action="append", default=[])
    parser.add_argument("--include-dirs", action="store_true")
    parser.add_argument("--max-artifact-bytes", type=int, default=250_000_000)
    parser.add_argument("--max-hash-bytes", type=int, default=50_000_000)
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument("--zip", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    policy = ForensicsPolicy(
        root=args.root,
        out_dir=args.out_dir or None,
        session_base=args.session_base or None,
        timeout_sec=max(1, int(args.timeout_sec)),
        include_dirs=bool(args.include_dirs),
        max_artifact_bytes=int(args.max_artifact_bytes),
        max_hash_bytes=int(args.max_hash_bytes),
        make_zip=bool(args.zip),
    )

    runner = ForensicsRunner(policy)
    if not args.no_baseline:
        runner.collect_baseline()
    else:
        runner._add_step("note", "baseline", "SKIPPED", "Baseline disabled")

    if args.artifact_path:
        runner.collect_artifacts(args.artifact_path)

    if policy.make_zip:
        runner.make_zip_bundle()

    report = runner.finalize_report()
    failed = sum(1 for s in report.steps if s.status == "FAILED")
    print(f"FAILED: {failed}")
    print(f"Log: {report.artifacts.get('log')}")
    print(f"Report: {report.artifacts.get('report')}")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
