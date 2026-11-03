"""ASGI entrypoint for the FinSight API (deployment/public surface).

Deployment/public surface: re-exports ``app`` and ``create_app`` from
:mod:`finsight.entrypoints.api.app`. Retained because the CDK handler references
this module. Owner: platform; removal condition: none.
"""

from finsight.entrypoints.api.app import create_app

__all__ = ['create_app']
