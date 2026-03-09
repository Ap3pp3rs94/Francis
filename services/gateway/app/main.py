from __future__ import annotations

from fastapi import FastAPI, Request

from services.gateway.app.middleware.auth import attach_actor_context, get_actor
from services.gateway.app.middleware.panic_mode import enforce_panic_mode, is_panic_mode_enabled
from services.gateway.app.middleware.rate_limit import InMemoryRateLimiter, enforce_rate_limit
from services.gateway.app.middleware.request_id import attach_request_id, get_request_id
from services.gateway.app.routes.admin import router as admin_router
from services.gateway.app.routes.auth import router as auth_router
from services.gateway.app.routes.health import router as health_router
from services.gateway.app.routes.proxy import router as proxy_router

SERVICE_NAME = "gateway"
SERVICE_VERSION = "0.2.0"


def _build_app() -> FastAPI:
    app = FastAPI(title="Francis Gateway", version=SERVICE_VERSION)
    app.state.rate_limiter = InMemoryRateLimiter(limit=240, window_seconds=60.0)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        return await attach_request_id(request, call_next)

    @app.middleware("http")
    async def actor_context_middleware(request: Request, call_next):
        return await attach_actor_context(request, call_next)

    @app.middleware("http")
    async def panic_mode_middleware(request: Request, call_next):
        return await enforce_panic_mode(request, call_next)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        return await enforce_rate_limit(request, call_next)

    @app.get("/")
    def root(request: Request) -> dict[str, object]:
        actor = get_actor(request)
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "version": request.app.version,
            "request_id": get_request_id(request),
            "panic_mode": is_panic_mode_enabled(request),
            "actor": actor.as_dict(),
            "surfaces": ["health", "auth", "admin", "proxy"],
        }

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(proxy_router)
    return app


app = _build_app()
