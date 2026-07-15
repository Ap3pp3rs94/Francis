from __future__ import annotations

import os
import re

_RUNTIME_IDENTITY_ENV = "FRANCIS_RUNTIME_IDENTITY"
_RUNTIME_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")


def runtime_identity() -> str:
    value = (os.getenv(_RUNTIME_IDENTITY_ENV) or "").strip()
    return value if _RUNTIME_IDENTITY_PATTERN.fullmatch(value) else ""


def scoped_runtime_label(default_label: str) -> str:
    identity = runtime_identity()
    return f"{default_label} [{identity}]" if identity else default_label


def canonical_orb_identity_id() -> str:
    identity = runtime_identity()
    return f"francis.proof_orb.{identity}" if identity else "francis.operator_orb"
