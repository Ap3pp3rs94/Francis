from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from francis.kernel.paths import data_dir, repo_root

router = APIRouter()

MAX_UPLOAD_BYTES = int(os.environ.get("FRANCIS_UPLOAD_MAX_BYTES", "10485760"))


def upload_dir() -> Path:
    raw = (os.environ.get("FRANCIS_UPLOAD_DIR") or "").strip()
    if not raw:
        return data_dir() / "uploads" / "inbox"
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = repo_root() / p
    return p.resolve()


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r'[<>:"|?*\x00-\x1F]', "_", base)
    base = base.strip().strip(".")
    return base or "upload.bin"


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        root = upload_dir()
        root.mkdir(parents=True, exist_ok=True)
        name = _safe_filename(file.filename or "upload.bin")
        out = root / name
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            return {"ok": False, "error": "file_too_large", "max_bytes": MAX_UPLOAD_BYTES}
        out.write_bytes(data)
        return {"ok": True, "stored": str(out), "bytes": out.stat().st_size}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
