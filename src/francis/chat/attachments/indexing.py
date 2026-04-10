from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from francis.kernel.paths import data_dir

__all__ = ["AttachmentIndex", "index_attachment", "get_attachment_index"]


def _index_path() -> Path:
    return data_dir() / "attachments" / "index.jsonl"


@dataclass(frozen=True)
class AttachmentIndex:
    attachment_id: str
    file_path: str
    upload_time: float


def index_attachment(attachment_id: str, file_path: str) -> AttachmentIndex | None:
    if not attachment_id or not file_path:
        return None
    entry = AttachmentIndex(attachment_id=attachment_id, file_path=file_path, upload_time=time.time())
    index_path = _index_path()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("", encoding="utf-8") if not index_path.exists() else None
    with index_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry.__dict__) + "\n")
    return entry


def get_attachment_index(attachment_id: str) -> AttachmentIndex | None:
    index_path = _index_path()
    if not attachment_id or not index_path.exists():
        return None
    try:
        for line in index_path.read_text(encoding="utf-8", errors="replace").splitlines():
            obj = json.loads(line)
            if obj.get("attachment_id") == attachment_id:
                return AttachmentIndex(
                    attachment_id=obj.get("attachment_id", ""),
                    file_path=obj.get("file_path", ""),
                    upload_time=float(obj.get("upload_time", 0.0)),
                )
    except Exception:
        return None
    return None
