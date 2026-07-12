from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

from francis.lens.perception_capture import (
    DesktopFrame,
    PerceptionCaptureError,
    PerceptionRingBuffer,
    Win32GdiDesktopFrameSource,
    analyze_frame_change,
    encode_desktop_frame_png,
)


def _frame(*, captured_at: float, value: int, width: int = 4, height: int = 3) -> DesktopFrame:
    pixel = bytes((value, value, value, 0))
    return DesktopFrame(
        captured_at=captured_at,
        origin_x=-1920,
        origin_y=0,
        source_width=3840,
        source_height=1080,
        width=width,
        height=height,
        bgra=pixel * width * height,
    )


def _active_authority(_receipt_id: str, _now: int) -> dict[str, bool]:
    return {"active": True}


def _png_scanlines(payload: bytes) -> tuple[int, int, bytes]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    width = 0
    height = 0
    compressed = bytearray()
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8]
        chunk = payload[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height = struct.unpack(">II", chunk[:8])
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
    return width, height, zlib.decompress(bytes(compressed))


def test_win32_capture_refuses_before_touching_pixels_without_active_authority() -> None:
    source = Win32GdiDesktopFrameSource(
        authority_receipt_id="expired-receipt",
        authority_status=lambda _receipt_id, _now: {"active": False},
    )

    with pytest.raises(PerceptionCaptureError, match="desktop_capture_authority_not_active") as exc_info:
        source.capture()

    assert exc_info.value.code == "desktop_capture_authority_not_active"


def test_ring_buffer_refuses_frame_write_without_active_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    ring = PerceptionRingBuffer(authority_status=lambda _receipt_id, _now: {"active": False})

    with pytest.raises(PerceptionCaptureError, match="desktop_capture_authority_not_active"):
        ring.append(_frame(captured_at=100.0, value=0), authority_receipt_id="inactive-receipt")

    assert not (tmp_path / "runtime" / "lens-perception").exists()


def test_png_encoder_and_change_detector_use_synthetic_pixels_only() -> None:
    first = _frame(captured_at=100.0, value=0)
    second = _frame(captured_at=100.5, value=255)

    first_change = analyze_frame_change(first, previous_sample=None)
    second_change = analyze_frame_change(second, previous_sample=first_change.sample)
    png = encode_desktop_frame_png(second)
    width, height, scanlines = _png_scanlines(png)

    assert first_change.changed is True
    assert first_change.score == 1.0
    assert second_change.changed is True
    assert second_change.score == 1.0
    assert len(second_change.difference_hash) == 16
    assert (width, height) == (4, 3)
    assert len(scanlines) == height * ((width * 4) + 1)
    assert all(scanlines[row * ((width * 4) + 1)] == 0 for row in range(height))
    assert "bgra=" not in repr(second)
    assert "sample=" not in repr(second_change)


def test_ring_buffer_prunes_by_time_and_count_without_exposing_pixels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    ring = PerceptionRingBuffer(
        retention_seconds=2.0,
        max_frames=2,
        authority_status=_active_authority,
    )

    ring.append(_frame(captured_at=100.0, value=0), authority_receipt_id="receipt-1")
    ring.append(_frame(captured_at=101.0, value=64), authority_receipt_id="receipt-1")
    readback = ring.append(_frame(captured_at=103.0, value=128), authority_receipt_id="receipt-1")

    runtime_root = tmp_path / "runtime" / "lens-perception"
    frame_files = sorted((runtime_root / "frames").glob("*.png"))
    manifest = json.loads((runtime_root / "ring-buffer.json").read_text(encoding="utf-8"))
    assert readback["ready"] is True
    assert readback["frame_count"] == 2
    assert readback["authority_receipt_id"] == "receipt-1"
    assert readback["coordinate_space"] == "windows_virtual_screen"
    assert readback["raw_pixels_in_readback"] is False
    assert readback["user_cursor_captured"] is False
    assert readback["keyboard_content_captured"] is False
    assert readback["visible_text_may_include_typed_content"] is True
    assert "bgra" not in json.dumps(readback)
    assert len(frame_files) == 2
    assert manifest["frame_count"] == 2
    assert manifest["frames"][0]["source_bounds"] == {
        "left": -1920,
        "top": 0,
        "width": 3840,
        "height": 1080,
    }
    assert manifest["governance"]["memory_write"] is False


def test_ring_buffer_count_limit_removes_only_owned_frame_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    root = tmp_path / "runtime" / "lens-perception"
    frames = root / "frames"
    frames.mkdir(parents=True)
    unrelated = frames / "operator-note.txt"
    unrelated.write_text("preserve", encoding="utf-8")
    ring = PerceptionRingBuffer(
        retention_seconds=120.0,
        max_frames=2,
        authority_status=_active_authority,
    )

    ring.append(_frame(captured_at=100.0, value=0), authority_receipt_id="receipt-2")
    ring.append(_frame(captured_at=101.0, value=32), authority_receipt_id="receipt-2")
    readback = ring.append(_frame(captured_at=102.0, value=64), authority_receipt_id="receipt-2")

    assert readback["frame_count"] == 2
    assert len(list(frames.glob("frame_*.png"))) == 2
    assert unrelated.read_text(encoding="utf-8") == "preserve"


def test_ring_buffer_fails_closed_on_corrupt_manifest_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    root = tmp_path / "runtime" / "lens-perception"
    root.mkdir(parents=True)
    (root / "ring-buffer.json").write_text(
        json.dumps(
            {
                "kind": "lens.perception.ring_buffer_manifest",
                "version": 1,
                "frames": {"not": "a list"},
            }
        ),
        encoding="utf-8",
    )

    readback = PerceptionRingBuffer().readback()

    assert readback["status"] == "empty"
    assert readback["ready"] is False
    assert readback["frame_count"] == 0


def test_ring_buffer_readback_rejects_stale_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    ring = PerceptionRingBuffer(authority_status=_active_authority)
    ring.append(_frame(captured_at=100.0, value=32), authority_receipt_id="receipt-stale")

    readback = ring.readback(now=106.0)

    assert readback["status"] == "stale"
    assert readback["ready"] is False
    assert readback["fresh"] is False
    assert readback["lag_ms"] == 6000.0


def test_ring_buffer_readback_rejects_tampered_latest_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path))
    ring = PerceptionRingBuffer(authority_status=_active_authority)
    ring.append(_frame(captured_at=100.0, value=32), authority_receipt_id="receipt-tampered")
    latest = next((tmp_path / "runtime" / "lens-perception" / "frames").glob("*.png"))
    latest.write_bytes(b"tampered")

    readback = PerceptionRingBuffer().readback(now=100.0)

    assert readback["status"] == "corrupt"
    assert readback["ready"] is False
    assert readback["fresh"] is True
    assert readback["integrity_valid"] is False
