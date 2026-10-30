"""FastAPI application factory aggregating the FinSight API entrypoint routers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from finsight.entrypoints.api import (
    ask,
    current_user,
    documents,
    feedback,
    onboarding,
    source_viewer,
    threads,
    upload,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title='FinSight AI API',
        version='0.1.0',
        description='FinSight AI backend API contract',
    )

    primary_routers = (
        ask.router,
        documents.router,
        feedback.router,
        onboarding.router,
        upload.router,
        source_viewer.router,
        current_user.router,
        threads.router,
    )
    for router_obj in primary_routers:
        app.include_router(router_obj)

    # Include common router aliases used by existing callers/tests.
    for extra in getattr(ask, 'EXTRA_ROUTERS', ()):
        app.include_router(extra)
    for extra in getattr(current_user, 'EXTRA_ROUTERS', ()):
        app.include_router(extra)
    for extra in getattr(threads, 'EXTRA_ROUTERS', ()):
        app.include_router(extra)
    for extra in getattr(feedback, 'EXTRA_ROUTERS', ()):
        app.include_router(extra)

    _install_ask_event_schema(app)
    return app


def _install_ask_event_schema(app: FastAPI) -> None:
    """Register the manually referenced SSE event model with OpenAPI components."""
    base_openapi = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = base_openapi()
            components = schema.setdefault('components', {})
            schemas = components.setdefault('schemas', {})
            schemas['AskQuestionEvent'] = ask.AskQuestionEvent.model_json_schema()
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]


app = create_app()
