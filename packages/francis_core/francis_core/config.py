from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    workspace_root: str = os.environ.get(
        "FRANCIS_WORKSPACE_ROOT",
        str((Path(__file__).resolve().parents[3] / "workspace").resolve()),
    )


settings = Settings()
