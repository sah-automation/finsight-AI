"""FastAPI application factory aggregating the FinSight API entrypoint routers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from finsight.composition import build_container, providers
from finsight.core.config.loader import load_config
from finsight.core.logging import set_switch_values
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
from finsight.entrypoints.api.correlation_middleware import CorrelationMiddleware
from finsight.entrypoints.api.readiness import build_readiness_report


def create_app() -> FastAPI:
    """Build the container, wire the providers, and assemble the FastAPI app."""
    config = load_config()
    container = build_container(config)

    switches = getattr(config, 'switches', None)
    if switches is not None and hasattr(switches, 'model_dump'):
        values = switches.model_dump()
    elif isinstance(switches, dict):
        values = dict(switches)
    else:
        values = {}
    set_switch_values(values)
    logging.getLogger(__name__).info('Active switch values: %s', values)

    providers.init(container)

    app = FastAPI(
        title='FinSight AI API',
        version='0.1.0',
        description='FinSight AI backend API contract',
    )
    _install_app_wiring(app, container)
    _include_routers(app)
    _install_ask_event_schema(app)
    return app


def _install_app_wiring(app: FastAPI, container: Any) -> None:
    app.state.container = container
    app.state.tracing = getattr(container, 'tracing', None)
    app.add_middleware(
        CorrelationMiddleware,  # type: ignore[arg-type]
        tracing=getattr(container, 'tracing', None),
        container=container,
    )
    _install_root_health(app)
    _install_ready_endpoint(app)


def _install_ready_endpoint(app: FastAPI) -> None:
    """Expose a distinct readiness endpoint that probes dependencies."""

    @app.get('/ready')
    async def _root_ready(request: Request) -> JSONResponse:
        container = getattr(getattr(request, 'app', None), 'state', None)
        container = getattr(container, 'container', None) if container is not None else None
        if container is None:
            container = getattr(app.state, 'container', None)
        report = await build_readiness_report(container)
        status_code = 200 if bool(report.get('ready', False)) else 503
        return JSONResponse(report, status_code=status_code)


def _include_routers(app: FastAPI) -> None:
    """Mount the primary routers and their legacy aliases."""
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

    for module in (ask, current_user, threads, feedback):
        for extra in getattr(module, 'EXTRA_ROUTERS', ()):
            app.include_router(extra)


def _install_root_health(app: FastAPI) -> None:
    """Expose a stable root-level health endpoint for external probes."""

    @app.get('/health')
    async def _root_health() -> dict[str, str]:
        return {'status': 'ok'}


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
