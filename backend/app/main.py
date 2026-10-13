from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import clients, decision, forecast, health, ingestion, kpi, rca, scenario
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI Business Decision Agent", docs_url="/api/docs", openapi_url="/api/openapi.json")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.monotonic()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = str(int((time.monotonic() - start) * 1000))
        return response

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(clients.router, prefix=settings.api_prefix)
    app.include_router(ingestion.router, prefix=settings.api_prefix)
    app.include_router(ingestion.canonical_fields_router, prefix=settings.api_prefix)
    app.include_router(kpi.router, prefix=settings.api_prefix)
    app.include_router(rca.router, prefix=settings.api_prefix)
    app.include_router(forecast.router, prefix=settings.api_prefix)
    app.include_router(scenario.router, prefix=settings.api_prefix)
    app.include_router(decision.router, prefix=settings.api_prefix)
    return app


app = create_app()
