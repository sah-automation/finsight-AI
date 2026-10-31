# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import inspect
import logging
from typing import Any


class _JobRetryList(list[Any]):
    """List that records a structured alert whenever a job enters retry."""

    def append(self, item: Any) -> None:
        try:
            _LOGGER.warning('job entered retry list', extra={'job_in_retry_list': True})
        except Exception as exc:  # pragma: no cover - best-effort logging
            _LOGGER.debug('job retry alert log failed', exc_info=exc)
        super().append(item)


_LOGGER = logging.getLogger(__name__)


def _coerce_str(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return str(value)


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in kwargs and kwargs.get(name) is not None:
            return kwargs.pop(name)
    for name in names:
        if name in kwargs:
            return kwargs.get(name)
    return default


async def _await_value(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, 'queue') or hasattr(arg, 'switches') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
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


def _queue_config(config: Any) -> Any:
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get('queue') or config.get('queue_config') or config
    value = getattr(config, 'queue', None)
    if value is None:
        value = getattr(config, 'queue_config', None)
    if value is None and hasattr(config, 'ingestion_queue_url'):
        return config
    return value


__all__ = [
    '_LOGGER',
    '_JobRetryList',
    '_await_value',
    '_coerce_str',
    '_first',
    '_queue_config',
    '_resolve_config',
]
