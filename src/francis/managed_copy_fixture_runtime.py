from __future__ import annotations

import argparse
import ctypes
import json
import os
import time
from pathlib import Path
from typing import Any


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def _creation_token() -> int:
    if os.name != "nt":
        stat = Path("/proc/self/stat").read_text(encoding="utf-8")
        closing = stat.rfind(")")
        return int(stat[closing + 2 :].split()[19])
    windll_type = getattr(ctypes, "WinDLL", None)
    if windll_type is None:
        return 0
    from ctypes import wintypes

    kernel32 = windll_type("kernel32", use_last_error=True)
    get_times = kernel32.GetProcessTimes
    get_times.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    get_times.restype = wintypes.BOOL
    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel_time = wintypes.FILETIME()
    user_time = wintypes.FILETIME()
    if not get_times(kernel32.GetCurrentProcess(), creation, exit_time, kernel_time, user_time):
        return 0
    return (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--copy-id", required=True)
    parser.add_argument("--tenant-key", required=True)
    parser.add_argument("--lease-id", required=True)
    parser.add_argument("--runtime-nonce", required=True)
    parser.add_argument("--descriptor-fingerprint", required=True)
    parser.add_argument("--lease-seconds", required=True, type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    tenant_root = Path.cwd().resolve(strict=True)
    state_dir = Path(args.state_dir).resolve(strict=True)
    expected_parent = (tenant_root / "receipts" / "runtime_start").resolve(strict=True)
    if state_dir.parent != expected_parent or state_dir.name != args.lease_id:
        return 2

    creation_token = _creation_token()
    if not creation_token:
        return 3
    identity = {
        "kind": "francis.stage18.managed_copies.fixture_runtime_handshake",
        "fixture_runtime": True,
        "ready": True,
        "pid": os.getpid(),
        "process_creation_token": creation_token,
        "parent_pid": os.getppid(),
        "copy_id": args.copy_id,
        "tenant_key": args.tenant_key,
        "lease_id": args.lease_id,
        "runtime_nonce": args.runtime_nonce,
        "descriptor_fingerprint": args.descriptor_fingerprint,
        "handshake_identity": "stage18_fixed_fixture_runtime_v1",
    }
    _write_json_atomic(state_dir / "handshake.json", identity)

    deadline = time.monotonic() + args.lease_seconds
    sequence = 0
    while time.monotonic() < deadline and not (state_dir / "cleanup.signal").exists():
        sequence += 1
        _write_json_atomic(
            state_dir / "heartbeat.json",
            {
                **identity,
                "kind": "francis.stage18.managed_copies.fixture_runtime_heartbeat",
                "heartbeat_identity": "stage18_fixed_fixture_heartbeat_v1",
                "sequence": sequence,
                "observed_at_unix_ms": int(time.time() * 1000),
            },
        )
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
