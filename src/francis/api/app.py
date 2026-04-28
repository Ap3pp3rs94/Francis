from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from francis.api.routes import (
    approvals,
    artifacts,
    attachments,
    chat,
    continuity,
    credentials,
    domain_learner,
    digital_twin,
    domains,
    evolution,
    explanation,
    federation,
    forge,
    industrial,
    lens,
    memory_timeline,
    missions,
    operations,
    plugins,
    reactor,
    resilience,
    simulation,
    supervised_exec,
    system,
    trust,
    web_learning,
)
from francis.kernel.paths import repo_root


def create_app() -> FastAPI:
    """Create the Francis API application."""
    app = FastAPI(title="Francis API")
    _configure_cors(app)

    _mount_controller_ui(app)

    app.include_router(system.router, prefix="/system", tags=["system"])
    app.include_router(chat.router, prefix="/chat", tags=["chat"])
    app.include_router(attachments.router, prefix="/attachments", tags=["attachments"])
    app.include_router(continuity.router, prefix="/continuity", tags=["continuity"])
    app.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
    app.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
    app.include_router(plugins.router, prefix="/plugins", tags=["plugins"])
    app.include_router(trust.router, prefix="/trust", tags=["trust"])
    app.include_router(trust.router, prefix="/system/trust", tags=["trust"])

    app.include_router(domains.router, prefix="/domains", tags=["domains"])
    app.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
    app.include_router(supervised_exec.router, prefix="/operations", tags=["operations"])
    app.include_router(operations.router, prefix="/operations", tags=["operations"])
    app.include_router(domain_learner.router, prefix="/domains", tags=["domains"])
    app.include_router(resilience.router, prefix="/resilience", tags=["resilience"])
    app.include_router(evolution.router, prefix="/evolution", tags=["evolution"])
    app.include_router(credentials.router, prefix="/credentials", tags=["credentials"])
    app.include_router(web_learning.router, prefix="/web_learning", tags=["web_learning"])
    app.include_router(web_learning.router, prefix="/web-learning", tags=["web_learning"])
    app.include_router(web_learning.router, prefix="/system/web_learning", tags=["web_learning"])
    app.include_router(web_learning.router, prefix="/system/web-learning", tags=["web_learning"])
    app.include_router(federation.router, prefix="/federation", tags=["federation"])
    app.include_router(forge.router, prefix="/forge", tags=["forge"])
    app.include_router(explanation.router, prefix="/explanation", tags=["explanation"])
    app.include_router(explanation.router, prefix="/explanations", tags=["explanation"])
    app.include_router(memory_timeline.router, prefix="/memory/timeline", tags=["memory_timeline"])
    app.include_router(missions.router, prefix="/missions", tags=["missions"])
    app.include_router(reactor.router, prefix="/reactor", tags=["reactor"])
    app.include_router(lens.router, prefix="/lens", tags=["lens"])
    app.include_router(industrial.router, prefix="/industrial", tags=["industrial"])
    app.include_router(digital_twin.router, prefix="/digital_twin", tags=["digital_twin"])

    return app


def _configure_cors(app: FastAPI) -> None:
    origins = os.environ.get("FRANCIS_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    allow_origins = [o.strip() for o in origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _mount_controller_ui(app: FastAPI) -> None:
    controller_dir = repo_root() / "apps" / "controller_ui"
    if controller_dir.exists():
        app.mount("/controller", StaticFiles(directory=str(controller_dir), html=True), name="controller")
