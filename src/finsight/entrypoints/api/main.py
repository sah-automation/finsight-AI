"""ASGI entrypoint alias for the FinSight API."""

from finsight.entrypoints.api.app import app, create_app

__all__ = ['app', 'create_app']
