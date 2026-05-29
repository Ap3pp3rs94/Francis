from __future__ import annotations

from francis.api.errors import api_error_message
import os
import re
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.kernel.paths import data_dir, repo_root

router = APIRouter()

MAX_UPLOAD_BYTES = int(os.environ.get("FRANCIS_UPLOAD_MAX_BYTES", "10485760"))
_ATTACHMENTS_WRITE_SCOPE = "attachments.write"


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


def _upload_write_permission(actor: object, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_ATTACHMENTS_WRITE_SCOPE],
        route=route,
        method=method,
    )


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, object]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_uploading_attachments",
            "evidence": decision.evidence,
        },
    }


@router.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    actor: str = Form("api.attachments"),
    request_actor: str = Form(""),
) -> dict[str, object]:
    try:
        permission = _upload_write_permission(
            request_actor.strip() or actor.strip() or "api.attachments",
            route=request.url.path,
            method=request.method,
        )
        if not permission.allowed:
            return _permission_denied(permission)

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
        return {"ok": False, "error": api_error_message(exc)}
