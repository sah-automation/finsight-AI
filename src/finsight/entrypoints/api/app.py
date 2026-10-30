"""FastAPI application factory aggregating the FinSight API entrypoint routers."""

from __future__ import annotations

from fastapi import FastAPI

from finsight.entrypoints.api import ask, current_user, documents, onboarding, source_viewer, upload


def create_app() -> FastAPI:
    app = FastAPI(
        title='FinSight AI API',
        version='0.1.0',
        description='FinSight AI backend API contract',
    )

    primary_routers = (
        ask.router,
        documents.router,
        onboarding.router,
        upload.router,
        source_viewer.router,
        current_user.router,
    )
    for router_obj in primary_routers:
        app.include_router(router_obj)

    # Include common router aliases used by existing callers/tests.
    for extra in getattr(ask, 'EXTRA_ROUTERS', ()):
        app.include_router(extra)
    for extra in getattr(current_user, 'EXTRA_ROUTERS', ()):
        app.include_router(extra)

    return app


app = create_app()
