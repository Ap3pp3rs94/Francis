from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request


def _ensure_package_paths() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    for pkg in [
        repo_root / "packages" / "francis_core",
        repo_root / "packages" / "francis_brain",
        repo_root / "packages" / "francis_policy",
        repo_root / "packages" / "francis_skills",
        repo_root / "packages" / "francis_presence",
        repo_root / "packages" / "francis_forge",
        repo_root / "packages" / "francis_connectors",
        repo_root / "packages" / "francis_llm",
    ]:
        path = str(pkg.resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_app() -> FastAPI:
    _ensure_package_paths()

    from services.orchestrator.app.routes.apprenticeship import router as apprenticeship_router
    from services.orchestrator.app.routes.approvals import router as approvals_router
    from services.orchestrator.app.routes.autonomy import router as autonomy_router
    from services.orchestrator.app.routes.capabilities import router as capabilities_router
    from services.orchestrator.app.routes.control import router as control_router
    from services.orchestrator.app.routes.fabric import router as fabric_router
    from services.orchestrator.app.routes.federation import router as federation_router
    from services.orchestrator.app.routes.forge import router as forge_router
    from services.orchestrator.app.routes.health import router as health_router
    from services.orchestrator.app.routes.inbox import router as inbox_router
    from services.orchestrator.app.routes.lens import router as lens_router
    from services.orchestrator.app.routes.managed_copies import router as managed_copies_router
    from services.orchestrator.app.routes.missions import router as missions_router
    from services.orchestrator.app.routes.observer import router as observer_router
    from services.orchestrator.app.routes.portability import router as portability_router
    from services.orchestrator.app.routes.presence import router as presence_router
    from services.orchestrator.app.routes.receipts import router as receipts_router
    from services.orchestrator.app.routes.runs import router as runs_router
    from services.orchestrator.app.routes.swarm import router as swarm_router
    from services.orchestrator.app.routes.telemetry import router as telemetry_router
    from services.orchestrator.app.routes.tools import router as tools_router
    from services.orchestrator.app.routes.worker import router as worker_router

    app = FastAPI(title="Francis Orchestrator", version="0.2.0")

    @app.middleware("http")
    async def attach_run_id(request: Request, call_next):
        run_id = uuid4()
        request.state.run_id = run_id
        request.state.trace_id = request.headers.get("x-trace-id", "").strip() or str(run_id)
        return await call_next(request)

    app.include_router(health_router)
    app.include_router(capabilities_router)
    app.include_router(control_router)
    app.include_router(fabric_router)
    app.include_router(portability_router)
    app.include_router(swarm_router)
    app.include_router(federation_router)
    app.include_router(managed_copies_router)
    app.include_router(telemetry_router)
    app.include_router(receipts_router)
    app.include_router(lens_router)
    app.include_router(tools_router)
    app.include_router(worker_router)
    app.include_router(inbox_router)
    app.include_router(presence_router)
    app.include_router(runs_router)
    app.include_router(missions_router)
    app.include_router(apprenticeship_router)
    app.include_router(approvals_router)
    app.include_router(forge_router)
    app.include_router(observer_router)
    app.include_router(autonomy_router)
    return app


app = _build_app()
