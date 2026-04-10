from __future__ import annotations

from pathlib import Path

from . import Attachment, create_attachment

__all__ = ["intake_attachment"]


def intake_attachment(file_path: str, *, file_type: str = "file") -> Attachment | None:
    path = Path(file_path)
    if not path.exists():
        return None
    try:
        return create_attachment(str(path), file_type)
    except Exception:
        return None
