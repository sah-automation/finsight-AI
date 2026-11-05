"""CORS origin resolution helpers for CDK stacks.

Keeping this logic out of ``data.py`` keeps that module under the repo's
size limit while still allowing bucket CORS rules to be configuration-driven.
"""

from __future__ import annotations

from typing import Any

_ORIGIN_KEYS = (
    'cors_allowed_origins',
    'allowed_origins',
    'allowed_cors_origins',
    'cors_origins',
    'web_origins',
    'frontend_origins',
    'app_origins',
    'api_origins',
    'allowed_web_origins',
    'origins',
    'web_origin',
    'frontend_origin',
    'app_origin',
    'origin',
    'allowed_origin',
)
_ORIGIN_CONTAINER_KEYS = (
    'cors',
    'web',
    'frontend',
    'app',
    'ui',
    'frontend_app',
    'storage',
    'data',
    'network',
    'edge',
    'http',
)


def _collect_cors_allowed_origins(value: object, origins: list[str], seen: set[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        candidate = value.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            origins.append(candidate)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _collect_cors_allowed_origins(item, origins, seen)
        return
    if not isinstance(value, dict):
        return
    for key in _ORIGIN_KEYS:
        if key in value:
            _collect_cors_allowed_origins(value[key], origins, seen)
    for container in _ORIGIN_CONTAINER_KEYS:
        nested = value.get(container)
        if isinstance(nested, dict):
            for key in _ORIGIN_KEYS:
                if key in nested:
                    _collect_cors_allowed_origins(nested[key], origins, seen)


def _resolve_cors_allowed_origins(config: dict[str, Any], env_name: str) -> list[str]:
    origins: list[str] = []
    seen: set[str] = set()
    _collect_cors_allowed_origins(config, origins, seen)
    if origins:
        return origins
    if str(env_name).lower() in {'prod', 'production'}:
        return ['https://app.example.com']
    return ['*', 'http://localhost:3000', 'http://127.0.0.1:3000']
