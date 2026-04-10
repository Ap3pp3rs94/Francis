from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

__all__ = [
    "AttachmentType",
    "ParsedData",
    "TextParser",
    "JSONParser",
    "CSVParser",
    "PDFParser",
]


class AttachmentType(str, Enum):
    TEXT = "text"
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"


@dataclass(frozen=True)
class ParsedData:
    attachment_id: str
    content_type: AttachmentType
    data: dict[str, Any] | list[dict[str, Any]] | str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attachment_id": self.attachment_id,
            "content_type": self.content_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class BaseParser:
    def __init__(self, attachment_id: str, content_type: AttachmentType) -> None:
        self.attachment_id = attachment_id
        self.content_type = content_type

    def parse(self, content: str | bytes) -> ParsedData:
        raise NotImplementedError


class TextParser(BaseParser):
    def parse(self, content: str | bytes) -> ParsedData:
        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        metadata = {"line_count": len(text.splitlines())}
        return ParsedData(
            attachment_id=self.attachment_id,
            content_type=self.content_type,
            data=text,
            metadata=metadata,
        )


class JSONParser(BaseParser):
    def parse(self, content: str | bytes) -> ParsedData:
        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        data = json.loads(text)
        return ParsedData(attachment_id=self.attachment_id, content_type=self.content_type, data=data)


class CSVParser(BaseParser):
    def parse(self, content: str | bytes) -> ParsedData:
        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        reader = csv.DictReader(text.splitlines())
        data = [row for row in reader]
        metadata = {"rows": len(data)}
        return ParsedData(
            attachment_id=self.attachment_id,
            content_type=self.content_type,
            data=data,
            metadata=metadata,
        )


class PDFParser(BaseParser):
    def parse(self, content: str | bytes) -> ParsedData:
        try:
            import PyPDF2
        except Exception as exc:
            raise RuntimeError("PyPDF2 library is required for PDF parsing.") from exc

        data_bytes = content.encode("utf-8") if isinstance(content, str) else content
        reader = PyPDF2.PdfReader(io.BytesIO(data_bytes))
        text_content = "".join(page.extract_text() or "" for page in reader.pages)
        metadata = {"page_count": len(reader.pages)}
        return ParsedData(
            attachment_id=self.attachment_id,
            content_type=self.content_type,
            data=text_content,
            metadata=metadata,
        )
