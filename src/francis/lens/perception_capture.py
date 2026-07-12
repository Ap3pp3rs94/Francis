"""Authority-bound desktop capture and bounded Lens ring-buffer primitives.

This module implements the pixel and storage core only. It does not expose an
API route, launch a process, grant capture authority, or attach itself to the
resident host. A separately governed execution path must own that lifecycle.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import struct
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.lens.perception_authority import lens_perception_desktop_authority_receipt_status

LENS_PERCEPTION_RING_BUFFER_KIND = "lens.perception.ring_buffer_manifest"
LENS_PERCEPTION_RING_BUFFER_VERSION = 1

_DEFAULT_MAX_WIDTH = 960
_DEFAULT_MAX_HEIGHT = 540
_DEFAULT_RETENTION_SECONDS = 120.0
_DEFAULT_MAX_FRAMES = 240
_DEFAULT_CHANGE_THRESHOLD = 0.02
_DEFAULT_MAX_LAG_SECONDS = 5.0
_FRAME_FILE_PATTERN = re.compile(r"^frame_[0-9]{13}_[0-9]{6}_[0-9a-f]{12}\.png$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

AuthorityStatusProvider = Callable[[str, int], dict[str, Any]]


class PerceptionCaptureError(RuntimeError):
    """Fail-closed capture error with a stable machine-readable code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class DesktopFrame:
    captured_at: float
    origin_x: int
    origin_y: int
    source_width: int
    source_height: int
    width: int
    height: int
    bgra: bytes = field(repr=False)
    backend: str = "synthetic"

    def __post_init__(self) -> None:
        if not math.isfinite(self.captured_at) or self.captured_at < 0.0:
            raise ValueError("desktop_frame_timestamp_invalid")
        if self.source_width <= 0 or self.source_height <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("desktop_frame_dimensions_invalid")
        if len(self.bgra) != self.width * self.height * 4:
            raise ValueError("desktop_frame_pixel_length_invalid")


@dataclass(frozen=True, slots=True)
class FrameChange:
    score: float
    changed: bool
    difference_hash: str
    sample: bytes = field(repr=False)


class Win32GdiDesktopFrameSource:
    """Capture the Windows virtual desktop after validating sensing authority."""

    def __init__(
        self,
        *,
        authority_receipt_id: str,
        max_width: int = _DEFAULT_MAX_WIDTH,
        max_height: int = _DEFAULT_MAX_HEIGHT,
        authority_status: AuthorityStatusProvider | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        cleaned_receipt_id = str(authority_receipt_id or "").strip()
        if not cleaned_receipt_id:
            raise ValueError("desktop_capture_authority_receipt_required")
        if max_width <= 0 or max_height <= 0:
            raise ValueError("desktop_capture_dimensions_invalid")
        self.authority_receipt_id = cleaned_receipt_id
        self.max_width = min(int(max_width), 7_680)
        self.max_height = min(int(max_height), 4_320)
        self._authority_status = authority_status or _desktop_authority_status
        self._clock = clock

    def capture(self) -> DesktopFrame:
        observed_at = self._clock()
        authority = self._authority_status(self.authority_receipt_id, int(observed_at))
        if authority.get("active") is not True:
            raise PerceptionCaptureError("desktop_capture_authority_not_active")
        if os.name != "nt":
            raise PerceptionCaptureError("desktop_capture_platform_unsupported")
        return self._capture_windows(captured_at=observed_at)

    def _capture_windows(self, *, captured_at: float) -> DesktopFrame:
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            raise PerceptionCaptureError("desktop_capture_win32_unavailable")
        user32 = win_dll("user32", use_last_error=True)
        gdi32 = win_dll("gdi32", use_last_error=True)

        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.GetDC.restype = wintypes.HDC
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.ReleaseDC.restype = ctypes.c_int
        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        gdi32.CreateCompatibleBitmap.restype = wintypes.HANDLE
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
        gdi32.SelectObject.restype = wintypes.HANDLE
        gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
        gdi32.SetStretchBltMode.restype = ctypes.c_int
        gdi32.StretchBlt.argtypes = [
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.DWORD,
        ]
        gdi32.StretchBlt.restype = wintypes.BOOL
        gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
        gdi32.DeleteObject.restype = wintypes.BOOL
        gdi32.DeleteDC.argtypes = [wintypes.HDC]
        gdi32.DeleteDC.restype = wintypes.BOOL

        class BitmapInfoHeader(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        class BitmapInfo(ctypes.Structure):
            _fields_ = [("bmiHeader", BitmapInfoHeader), ("bmiColors", wintypes.DWORD * 1)]

        gdi32.GetDIBits.argtypes = [
            wintypes.HDC,
            wintypes.HANDLE,
            wintypes.UINT,
            wintypes.UINT,
            wintypes.LPVOID,
            ctypes.POINTER(BitmapInfo),
            wintypes.UINT,
        ]
        gdi32.GetDIBits.restype = ctypes.c_int

        origin_x = int(user32.GetSystemMetrics(76))
        origin_y = int(user32.GetSystemMetrics(77))
        source_width = int(user32.GetSystemMetrics(78))
        source_height = int(user32.GetSystemMetrics(79))
        if source_width <= 0 or source_height <= 0:
            raise PerceptionCaptureError("desktop_capture_virtual_screen_unavailable")
        scale = min(1.0, self.max_width / source_width, self.max_height / source_height)
        width = max(1, round(source_width * scale))
        height = max(1, round(source_height * scale))

        screen_dc = user32.GetDC(None)
        if not screen_dc:
            raise PerceptionCaptureError("desktop_capture_screen_dc_unavailable")
        memory_dc = None
        bitmap = None
        previous_bitmap = None
        bitmap_selected = False
        try:
            memory_dc = gdi32.CreateCompatibleDC(screen_dc)
            if not memory_dc:
                raise PerceptionCaptureError("desktop_capture_memory_dc_unavailable")
            bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
            if not bitmap:
                raise PerceptionCaptureError("desktop_capture_bitmap_unavailable")
            previous_bitmap = gdi32.SelectObject(memory_dc, bitmap)
            if not previous_bitmap or previous_bitmap == ctypes.c_void_p(-1).value:
                raise PerceptionCaptureError("desktop_capture_bitmap_select_failed")
            bitmap_selected = True
            gdi32.SetStretchBltMode(memory_dc, 3)
            raster_operation = 0x00CC0020 | 0x40000000
            copied = gdi32.StretchBlt(
                memory_dc,
                0,
                0,
                width,
                height,
                screen_dc,
                origin_x,
                origin_y,
                source_width,
                source_height,
                raster_operation,
            )
            if not copied:
                raise PerceptionCaptureError("desktop_capture_bitblt_failed")
            restored_bitmap = gdi32.SelectObject(memory_dc, previous_bitmap)
            if not restored_bitmap or restored_bitmap == ctypes.c_void_p(-1).value:
                raise PerceptionCaptureError("desktop_capture_bitmap_restore_failed")
            bitmap_selected = False

            byte_count = width * height * 4
            pixels = (ctypes.c_ubyte * byte_count)()
            bitmap_info = BitmapInfo()
            bitmap_info.bmiHeader.biSize = ctypes.sizeof(BitmapInfoHeader)
            bitmap_info.bmiHeader.biWidth = width
            bitmap_info.bmiHeader.biHeight = -height
            bitmap_info.bmiHeader.biPlanes = 1
            bitmap_info.bmiHeader.biBitCount = 32
            bitmap_info.bmiHeader.biCompression = 0
            bitmap_info.bmiHeader.biSizeImage = byte_count
            scanlines = gdi32.GetDIBits(
                memory_dc,
                bitmap,
                0,
                height,
                pixels,
                ctypes.byref(bitmap_info),
                0,
            )
            if scanlines != height:
                raise PerceptionCaptureError("desktop_capture_pixel_read_failed")
            return DesktopFrame(
                captured_at=captured_at,
                origin_x=origin_x,
                origin_y=origin_y,
                source_width=source_width,
                source_height=source_height,
                width=width,
                height=height,
                bgra=bytes(pixels),
                backend="win32_gdi_stretchblt",
            )
        finally:
            if memory_dc and previous_bitmap and bitmap_selected:
                gdi32.SelectObject(memory_dc, previous_bitmap)
            if bitmap:
                gdi32.DeleteObject(bitmap)
            if memory_dc:
                gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(None, screen_dc)


class PerceptionRingBuffer:
    """Persist authority-correlated frames under bounded runtime retention."""

    def __init__(
        self,
        *,
        retention_seconds: float = _DEFAULT_RETENTION_SECONDS,
        max_frames: int = _DEFAULT_MAX_FRAMES,
        change_threshold: float = _DEFAULT_CHANGE_THRESHOLD,
        authority_status: AuthorityStatusProvider | None = None,
    ) -> None:
        if not math.isfinite(retention_seconds) or retention_seconds <= 0.0 or max_frames <= 0:
            raise ValueError("lens_perception_ring_buffer_limits_invalid")
        if not math.isfinite(change_threshold) or not 0.0 <= change_threshold <= 1.0:
            raise ValueError("lens_perception_change_threshold_invalid")
        self.root = data_dir() / "runtime" / "lens-perception"
        self.frames_dir = self.root / "frames"
        self.manifest_path = self.root / "ring-buffer.json"
        self.retention_seconds = min(float(retention_seconds), 600.0)
        self.max_frames = min(int(max_frames), 1_200)
        self.change_threshold = float(change_threshold)
        self._authority_status = authority_status or _desktop_authority_status
        self._items = self._load_items()
        self._previous_sample: bytes | None = None
        self._sequence = 0

    def append(self, frame: DesktopFrame, *, authority_receipt_id: str) -> dict[str, Any]:
        receipt_id = str(authority_receipt_id or "").strip()
        if not receipt_id:
            raise ValueError("desktop_capture_authority_receipt_required")
        authority = self._authority_status(receipt_id, int(frame.captured_at))
        if authority.get("active") is not True:
            raise PerceptionCaptureError("desktop_capture_authority_not_active")
        change = analyze_frame_change(
            frame,
            previous_sample=self._previous_sample,
            threshold=self.change_threshold,
        )
        self._previous_sample = change.sample
        png = encode_desktop_frame_png(frame)
        digest = hashlib.sha256(png).hexdigest()
        self._sequence += 1
        frame_name = f"frame_{int(frame.captured_at * 1000):013d}_{self._sequence:06d}_{digest[:12]}.png"
        frame_path = self.frames_dir / frame_name
        _atomic_write_bytes(frame_path, png)
        item = {
            "frame_id": frame_name.removesuffix(".png"),
            "file_name": frame_name,
            "captured_at": frame.captured_at,
            "authority_receipt_id": receipt_id,
            "capture_backend": frame.backend,
            "coordinate_space": "windows_virtual_screen",
            "source_bounds": {
                "left": frame.origin_x,
                "top": frame.origin_y,
                "width": frame.source_width,
                "height": frame.source_height,
            },
            "stored_frame": {
                "width": frame.width,
                "height": frame.height,
                "format": "png_rgba8",
                "byte_count": len(png),
                "sha256": digest,
            },
            "change": {
                "score": change.score,
                "threshold": self.change_threshold,
                "changed": change.changed,
                "difference_hash": change.difference_hash,
            },
            "user_cursor_captured": False,
            "keyboard_content_captured": False,
            "visible_text_may_include_typed_content": True,
        }
        self._items.append(item)
        self._items.sort(key=_frame_sort_key)
        self._prune(reference_time=frame.captured_at)
        self._write_manifest(updated_at=frame.captured_at)
        return self.readback(now=frame.captured_at)

    def readback(self, *, now: float | None = None) -> dict[str, Any]:
        observed_at = time.time() if now is None else float(now)
        oldest = self._items[0] if self._items else {}
        latest = self._items[-1] if self._items else {}
        oldest_at = _safe_float(oldest.get("captured_at"))
        newest_at = _safe_float(latest.get("captured_at"))
        age_seconds = observed_at - newest_at if newest_at is not None else None
        fresh = bool(age_seconds is not None and 0.0 <= age_seconds <= _DEFAULT_MAX_LAG_SECONDS)
        latest_stored = _as_dict(latest.get("stored_frame"))
        latest_change = _as_dict(latest.get("change"))
        integrity_valid = self._frame_integrity_valid(latest) if latest else False
        ready = bool(self._items and fresh and integrity_valid)
        return {
            "kind": "lens.perception.ring_buffer_readback",
            "status": (
                "ready"
                if ready
                else "corrupt"
                if self._items and not integrity_valid
                else "stale"
                if self._items
                else "empty"
            ),
            "ready": ready,
            "source": "desktop_ring_buffer",
            "frame_count": len(self._items),
            "retention_seconds": self.retention_seconds,
            "max_frames": self.max_frames,
            "buffer_depth_seconds": (
                round(max(0.0, newest_at - oldest_at), 6) if newest_at is not None and oldest_at is not None else 0.0
            ),
            "oldest_frame_at": oldest_at,
            "newest_frame_at": newest_at,
            "lag_ms": round(age_seconds * 1000.0, 3) if age_seconds is not None else None,
            "max_lag_ms": int(_DEFAULT_MAX_LAG_SECONDS * 1000),
            "fresh": fresh,
            "integrity_valid": integrity_valid,
            "latest_frame_id": str(latest.get("frame_id") or ""),
            "latest_frame_sha256": str(latest_stored.get("sha256") or ""),
            "latest_frame_byte_count": _safe_int(latest_stored.get("byte_count")),
            "latest_change_score": _safe_float(latest_change.get("score")),
            "latest_change_detected": latest_change.get("changed") is True,
            "latest_difference_hash": str(latest_change.get("difference_hash") or ""),
            "authority_receipt_id": str(latest.get("authority_receipt_id") or ""),
            "coordinate_space": "windows_virtual_screen",
            "raw_pixels_in_readback": False,
            "user_cursor_captured": False,
            "keyboard_content_captured": False,
            "visible_text_may_include_typed_content": True,
        }

    def _load_items(self) -> list[dict[str, Any]]:
        payload = _read_json(self.manifest_path)
        if (
            payload.get("kind") != LENS_PERCEPTION_RING_BUFFER_KIND
            or payload.get("version") != LENS_PERCEPTION_RING_BUFFER_VERSION
        ):
            return []
        raw_items = payload.get("frames")
        if not isinstance(raw_items, list):
            return []
        items = [item for item in raw_items if isinstance(item, dict) and self._manifest_item_valid(item)]
        return sorted(items, key=_frame_sort_key)[-self.max_frames :]

    def _manifest_item_valid(self, item: dict[str, Any]) -> bool:
        file_name = str(item.get("file_name") or "")
        stored = _as_dict(item.get("stored_frame"))
        return bool(
            _FRAME_FILE_PATTERN.fullmatch(file_name)
            and (self.frames_dir / file_name).is_file()
            and _safe_float(item.get("captured_at")) is not None
            and str(item.get("authority_receipt_id") or "").strip()
            and _SHA256_PATTERN.fullmatch(str(stored.get("sha256") or ""))
            and _safe_int(stored.get("byte_count")) > 0
        )

    def _frame_integrity_valid(self, item: dict[str, Any]) -> bool:
        file_name = str(item.get("file_name") or "")
        stored = _as_dict(item.get("stored_frame"))
        if not _FRAME_FILE_PATTERN.fullmatch(file_name):
            return False
        try:
            payload = (self.frames_dir / file_name).read_bytes()
        except OSError:
            return False
        return bool(
            len(payload) == _safe_int(stored.get("byte_count"))
            and hashlib.sha256(payload).hexdigest() == str(stored.get("sha256") or "")
        )

    def _prune(self, *, reference_time: float) -> None:
        cutoff = reference_time - self.retention_seconds
        retained = [item for item in self._items if (_safe_float(item.get("captured_at")) or 0.0) >= cutoff]
        retained = retained[-self.max_frames :]
        retained_ids = {str(item.get("frame_id") or "") for item in retained}
        for item in self._items:
            if str(item.get("frame_id") or "") not in retained_ids:
                self._delete_frame(item)
        self._items = retained

    def _delete_frame(self, item: dict[str, Any]) -> None:
        file_name = str(item.get("file_name") or "")
        if not _FRAME_FILE_PATTERN.fullmatch(file_name):
            return
        try:
            (self.frames_dir / file_name).unlink(missing_ok=True)
        except OSError:
            return

    def _write_manifest(self, *, updated_at: float) -> None:
        _atomic_write_json(
            self.manifest_path,
            {
                "kind": LENS_PERCEPTION_RING_BUFFER_KIND,
                "version": LENS_PERCEPTION_RING_BUFFER_VERSION,
                "status": "ready" if self._items else "empty",
                "source": "desktop_ring_buffer",
                "updated_at": updated_at,
                "retention_seconds": self.retention_seconds,
                "max_frames": self.max_frames,
                "frame_count": len(self._items),
                "frames": self._items,
                "governance": {
                    "runtime_state_only": True,
                    "memory_write": False,
                    "user_cursor_captured": False,
                    "keyboard_content_captured": False,
                    "visible_text_may_include_typed_content": True,
                },
            },
        )


def analyze_frame_change(
    frame: DesktopFrame,
    *,
    previous_sample: bytes | None,
    threshold: float = _DEFAULT_CHANGE_THRESHOLD,
) -> FrameChange:
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("lens_perception_change_threshold_invalid")
    sample = _luma_sample(frame, columns=64, rows=36)
    if previous_sample is None or len(previous_sample) != len(sample):
        score = 1.0
    else:
        score = sum(abs(current - previous) for current, previous in zip(sample, previous_sample, strict=True))
        score /= len(sample) * 255.0
    return FrameChange(
        score=round(score, 6),
        changed=previous_sample is None or score >= threshold,
        difference_hash=_difference_hash(frame),
        sample=sample,
    )


def lens_perception_ring_buffer_readback(*, now: float | None = None) -> dict[str, Any]:
    return PerceptionRingBuffer().readback(now=now)


def encode_desktop_frame_png(frame: DesktopFrame) -> bytes:
    scanlines = bytearray()
    stride = frame.width * 4
    for row_index in range(frame.height):
        source = frame.bgra[row_index * stride : (row_index + 1) * stride]
        rgba = bytearray(stride)
        rgba[0::4] = source[2::4]
        rgba[1::4] = source[1::4]
        rgba[2::4] = source[0::4]
        rgba[3::4] = b"\xff" * frame.width
        scanlines.append(0)
        scanlines.extend(rgba)
    header = struct.pack(">IIBBBBB", frame.width, frame.height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=3))
        + _png_chunk(b"IEND", b"")
    )


def _desktop_authority_status(receipt_id: str, now: int) -> dict[str, Any]:
    return lens_perception_desktop_authority_receipt_status(receipt_id, now=now)


def _luma_sample(frame: DesktopFrame, *, columns: int, rows: int) -> bytes:
    values = bytearray()
    for row in range(rows):
        y = min(frame.height - 1, (row * frame.height) // rows)
        for column in range(columns):
            x = min(frame.width - 1, (column * frame.width) // columns)
            offset = (y * frame.width + x) * 4
            blue, green, red = frame.bgra[offset : offset + 3]
            values.append((29 * blue + 150 * green + 77 * red) >> 8)
    return bytes(values)


def _difference_hash(frame: DesktopFrame) -> str:
    sample = _luma_sample(frame, columns=9, rows=8)
    value = 0
    for row in range(8):
        row_start = row * 9
        for column in range(8):
            value = (value << 1) | int(sample[row_start + column] > sample[row_start + column + 1])
    return f"{value:016x}"


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _frame_sort_key(item: dict[str, Any]) -> tuple[float, str]:
    return (_safe_float(item.get("captured_at")) or 0.0, str(item.get("frame_id") or ""))


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_bytes(
        path,
        (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8"),
    )


__all__ = [
    "DesktopFrame",
    "FrameChange",
    "LENS_PERCEPTION_RING_BUFFER_KIND",
    "LENS_PERCEPTION_RING_BUFFER_VERSION",
    "PerceptionCaptureError",
    "PerceptionRingBuffer",
    "Win32GdiDesktopFrameSource",
    "analyze_frame_change",
    "encode_desktop_frame_png",
    "lens_perception_ring_buffer_readback",
]
