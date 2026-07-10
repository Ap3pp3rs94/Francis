from __future__ import annotations

import binascii
import hashlib
import json
import struct
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from francis.lens.ui_render_proof import validate_lens_ui_render_proof


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def _write_png(path: Path, width: int, height: int) -> None:
    rows = b"".join(b"\x00" + bytes((20 + row, 40, 80, 255)) * width for row in range(height))
    payload = b"\x89PNG\r\n\x1a\n"
    payload += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    payload += _png_chunk(b"IDAT", zlib.compress(rows))
    payload += _png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _artifact(root: Path, path: Path, *, width: int | None = None, height: int | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }
    if width is not None:
        payload["width"] = width
    if height is not None:
        payload["height"] = height
    return payload


def _valid_proof(root: Path, *, created_at: datetime) -> tuple[Path, dict[str, object]]:
    lens_png = root / "output" / "playwright" / "lens.png"
    chat_png = root / "output" / "playwright" / "chat.png"
    snapshot = root / "output" / "playwright" / "snapshot.yml"
    _write_png(lens_png, 8, 6)
    _write_png(chat_png, 12, 10)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(
        "Francis MCP Status\ntakeover_ready\ntool-call-policy-proof\n"
        "Agent Relay Controls\nLive Conversation\nTechnical receipt\n",
        encoding="utf-8",
    )
    proof: dict[str, object] = {
        "kind": "francis.lens.ui_render_proof",
        "schema_version": "francis.lens.ui_render_proof.v1",
        "created_at": created_at.isoformat(),
        "repo_head": "abc123",
        "page": {
            "url": "http://127.0.0.1:5173/diagnostics",
            "title": "Francis Console",
            "console_error_count": 0,
        },
        "lens": {
            "rendered": True,
            "status": "ready",
            "posture": "takeover_ready",
            "blocker_count": 0,
            "tool_count": 23,
            "latest_receipt_id": "tool-call-policy-proof",
            "read_only": True,
            "execution_authority": False,
            "mutation_authority": False,
            "text_length": 1200,
            "markers": {
                name: True
                for name in (
                    "lens_heading",
                    "status_ready",
                    "posture_ready",
                    "zero_blockers",
                    "policy_safe",
                    "receipt_visible",
                    "read_only",
                )
            },
        },
        "chat": {
            "rendered": True,
            "text_length": 8000,
            "markers": {
                name: True
                for name in (
                    "agent_relay",
                    "active_agents",
                    "authority_bounded",
                    "live_conversation",
                    "technical_receipts",
                    "operator_console",
                )
            },
        },
        "artifacts": {
            "lens_screenshot": _artifact(root, lens_png, width=8, height=6),
            "chat_screenshot": _artifact(root, chat_png, width=12, height=10),
            "snapshot": _artifact(root, snapshot),
        },
        "canonical_runtime": {
            "status": "ready",
            "process_scan_status": "none_observed",
            "process_scan_checked": True,
            "process_scan_candidate_count": 0,
            "competing_count": 0,
            "renderer_process_count": 1,
            "overlay_pid": 101,
            "hotkey_pid": 102,
            "tray_pid": 103,
            "supervisor_pid": 104,
            "resident_host_pid": 105,
            "renderer_pid": 106,
        },
        "governance": {
            "browser_read_only": True,
            "captured_existing_surface": True,
            "no_physical_input": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    proof_path = root / "data" / "logs" / "operations" / "one_visible_loop" / "render-proof.json"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(proof), encoding="utf-8")
    return proof_path, proof


def test_lens_ui_render_proof_accepts_fresh_correlated_artifacts(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    proof_path, _proof = _valid_proof(tmp_path, created_at=now - timedelta(seconds=5))

    result = validate_lens_ui_render_proof(
        proof_path,
        repo_root=tmp_path,
        expected_repo_head="abc123",
        now=now,
    )

    assert result["ok"] is True
    assert result["status"] == "render_verified"
    assert result["chat_render_verified"] is True
    assert result["lens_render_verified"] is True
    assert result["blockers"] == []
    assert result["governance"]["grants_execution_authority"] is False


def test_lens_ui_render_proof_rejects_stale_authority_and_hash_drift(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    proof_path, proof = _valid_proof(tmp_path, created_at=now - timedelta(hours=2))
    proof["repo_head"] = "old-head"
    lens = proof["lens"]
    assert isinstance(lens, dict)
    lens["execution_authority"] = True
    artifacts = proof["artifacts"]
    assert isinstance(artifacts, dict)
    lens_screenshot = artifacts["lens_screenshot"]
    assert isinstance(lens_screenshot, dict)
    lens_screenshot["sha256"] = "0" * 64
    proof_path.write_text(json.dumps(proof), encoding="utf-8")

    result = validate_lens_ui_render_proof(
        proof_path,
        repo_root=tmp_path,
        expected_repo_head="abc123",
        now=now,
    )

    assert result["ok"] is False
    assert result["chat_render_verified"] is False
    assert result["lens_render_verified"] is False
    assert "ui_render_proof_stale" in result["blockers"]
    assert "ui_render_proof_head_mismatch" in result["blockers"]
    assert "lens_ui_authority_drift" in result["blockers"]
    assert "lens_screenshot_hash_mismatch" in result["blockers"]


def test_lens_ui_render_proof_rejects_unchecked_process_scan(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    proof_path, proof = _valid_proof(tmp_path, created_at=now - timedelta(seconds=5))
    runtime = proof["canonical_runtime"]
    assert isinstance(runtime, dict)
    runtime["process_scan_checked"] = False
    proof_path.write_text(json.dumps(proof), encoding="utf-8")

    result = validate_lens_ui_render_proof(
        proof_path,
        repo_root=tmp_path,
        expected_repo_head="abc123",
        now=now,
    )

    assert result["ok"] is False
    assert "canonical_runtime_process_scan_not_checked" in result["blockers"]
