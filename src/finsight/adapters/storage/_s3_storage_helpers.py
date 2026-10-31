# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import inspect
from typing import Any


def _as_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return str(value)


def _await_maybe(value: Any) -> Any:
    if inspect.isawaitable(value):
        return _await_sync(value)
    return value


def _await_sync(value: Any) -> Any:
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        # Return the awaitable; caller must await. We only call this when
        # the surrounding method is async, so direct await is preferred.
        return value
    if loop is None:
        return asyncio.run(value)
    return loop.run_until_complete(value)


async def _await_value(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in kwargs and kwargs.get(name) is not None:
            return kwargs.pop(name)
    for name in names:
        if name in kwargs:
            return kwargs.get(name)
    return default


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, 'storage') or hasattr(arg, 'documents_bucket') or hasattr(arg, 'switches'):
            # Heuristic: config-like objects.
            if hasattr(arg, 'storage') or hasattr(arg, 'documents_bucket') or hasattr(arg, 'app'):
                return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for container_key in ('container', 'composition', 'root', 'app', 'context'):
        value = kwargs.get(container_key)
        if value is not None:
            cfg = getattr(value, 'config', None)
            if cfg is None and isinstance(value, dict):
                cfg = value.get('config')
            if cfg is not None:
                return cfg
    for arg in args:
        if hasattr(arg, 'config'):
            cfg = getattr(arg, 'config', None)
            if cfg is not None:
                return cfg
    return None


def _storage_config(config: Any) -> Any:
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get('storage') or config.get('storage_config')
    for attr in ('storage', 'storage_config', 's3', 's3_config'):
        value = getattr(config, attr, None)
        if value is not None:
            return value
    if hasattr(config, 'documents_bucket'):
        return config
    return None


def _encryption_config(config: Any) -> Any:
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get('encryption') or config.get('encryption_config')
    for attr in ('encryption', 'encryption_config', 'security'):
        value = getattr(config, attr, None)
        if value is not None:
            return value
    return None


def _resolve_session(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None or isinstance(arg, dict):
            continue
        if hasattr(arg, 'client') and callable(getattr(arg, 'client', None)):
            return arg
        if hasattr(arg, 'generate_presigned_url'):
            # Already a client; handled separately.
            continue
        if hasattr(arg, 'execute') or hasattr(arg, 'begin'):
            return arg
    for key in ('session', 'db_session', 'session_or_engine', 'connection', 'engine'):
        value = kwargs.get(key)
        if value is not None:
            return value
    return None


def _coerce_str(value: Any) -> str:
    return _as_text(value).strip()


__all__ = [
    '_as_text',
    '_await_maybe',
    '_await_sync',
    '_await_value',
    '_coerce_str',
    '_encryption_config',
    '_first',
    '_resolve_config',
    '_resolve_session',
    '_storage_config',
]
