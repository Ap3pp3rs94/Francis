from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = [
    "AttachmentType",
    "AttachmentMetadata",
    "Attachment",
    "create_attachment",
    "save_attachment",
]


class AttachmentType(str, Enum):
    FILE = "file"
    IMAGE = "image"
    DOCUMENT = "document"


@dataclass(frozen=True)
class AttachmentMetadata:
    attachment_id: str
    file_name: str
    file_size: int
    file_type: AttachmentType
    upload_timestamp: float


@dataclass(frozen=True)
class Attachment:
    metadata: AttachmentMetadata
    content: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "attachment_id": self.metadata.attachment_id,
            "file_name": self.metadata.file_name,
            "file_size": self.metadata.file_size,
            "file_type": self.metadata.file_type.value,
            "upload_timestamp": self.metadata.upload_timestamp,
        }


def create_attachment(file_path: str, file_type: str) -> Attachment:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError("The provided file path is invalid")

    content = path.read_bytes()
    metadata = AttachmentMetadata(
        attachment_id=str(uuid.uuid4()),
        file_name=path.name,
        file_size=len(content),
        file_type=AttachmentType(file_type),
        upload_timestamp=time.time(),
    )
    return Attachment(metadata=metadata, content=content)


def save_attachment(attachment: Attachment, storage_path: str) -> Path:
    dest_dir = Path(storage_path)
    if not dest_dir.is_dir():
        raise NotADirectoryError("The provided storage path is invalid")
    file_path = dest_dir / attachment.metadata.file_name
    file_path.write_bytes(attachment.content)
    return file_path
