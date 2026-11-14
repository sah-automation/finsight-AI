"""Metering adapter helpers (top-level utilities)."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finsight.core.config.price_table import (
    PriceTable,
    load_price_table,
)

_LOGGER = logging.getLogger(__name__)

# table name -> {(pk, sk): item}
_TABLES: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}

_DEFAULT_TABLE_NAME = 'metering'


def _text(value: object) -> str:
    return '' if value is None else str(value)


def _decimal_text(value: object) -> str | None:
    if value is None:
        return None
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return format(number, 'f')


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if isinstance(arg, Mapping):
            return arg
        if hasattr(arg, 'metering') or hasattr(arg, 'switches') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return None


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    sections = ('metering',)
    for name in names:
        if config is None:
            break
        if isinstance(config, Mapping):
            if config.get(name) is not None:
                return config.get(name)
            for section in sections:
                nested = config.get(section)
                if isinstance(nested, Mapping) and nested.get(name) is not None:
                    return nested.get(name)
        else:
            value = getattr(config, name, None)
            if value is not None:
                return value
            for section in sections:
                nested = getattr(config, section, None)
                if nested is None:
                    continue
                value = (
                    nested.get(name) if isinstance(nested, Mapping) else getattr(nested, name, None)
                )
                if value is not None:
                    return value
    return default


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _is_table(obj: Any) -> bool:
    return obj is not None and any(
        hasattr(obj, method) for method in ('put_item', 'batch_write_item', 'get_item')
    )


async def _maybe_await(value: Any, *args: Any, **kwargs: Any) -> Any:
    result = value(*args, **kwargs) if callable(value) else value
    if inspect.isawaitable(result):
        return await result
    return result


def _coerce_price_table(value: Any) -> PriceTable:
    if isinstance(value, PriceTable):
        return value
    if isinstance(value, Mapping):
        return PriceTable(value)
    if isinstance(value, (str, Path)):
        return load_price_table(value)
    return load_price_table()


def _resolve_switches_enabled(config: Any) -> bool:
    switches = None
    if config is not None:
        switches = (
            config.get('switches')
            if isinstance(config, Mapping)
            else getattr(config, 'switches', None)
        )
    if isinstance(switches, Mapping):
        return bool(switches.get('usage_metering_enabled', True))
    if switches is not None:
        return bool(getattr(switches, 'usage_metering_enabled', True))
    return True
