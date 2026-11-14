"""Typed settings for the waiting-line adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_QUICK_FIRST = 'quick_first'
_FIRST_COME = 'first_come'
_ORDERINGS = frozenset({_QUICK_FIRST, _FIRST_COME})
_PRIORITY_RANKS = {
    'quick': 0,
    'question': 0,
    'search': 0,
    'rerank': 0,
    'model': 0,
    'upload': 1,
    'ingestion': 1,
    'report': 2,
    'reprocess': 2,
    'background': 3,
}


def _text(value: object) -> str:
    return '' if value is None else str(value).strip()


def _first(values: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if values.get(name) is not None:
            return values.get(name)
    return default


def _nested_value(container: object, name: str) -> Any:
    if container is None:
        return None
    if isinstance(container, dict):
        return container.get(name)
    return getattr(container, name, None)


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    sections = ('waiting_line', 'scale', 'traffic', 'queue', 'question_flow')
    for name in names:
        if config is None:
            break
        if isinstance(config, dict):
            if config.get(name) is not None:
                return config.get(name)
            for section in sections:
                value = _nested_value(config.get(section), name)
                if value is not None:
                    return value
        else:
            value = getattr(config, name, None)
            if value is not None:
                return value
            for section in sections:
                value = _nested_value(getattr(config, section, None), name)
                if value is not None:
                    return value
    return default


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if any(hasattr(arg, attr) for attr in ('scale', 'traffic', 'queue', 'switches', 'app')):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        config = getattr(container, 'config', None) if container is not None else None
        if config is not None:
            return config
    return None


def _int(value: object, default: int) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _float(value: object, default: float) -> float:
    try:
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value))
    except (TypeError, ValueError):
        return default


def priority_rank(value: object) -> int:
    """Map a work kind or numeric priority to a quick-first rank."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return _PRIORITY_RANKS.get(_text(value).lower(), 1)


@dataclass(frozen=True)
class WaitingLineSettings:
    """Validated settings for one waiting line."""

    max_concurrency: int = 20
    max_per_company: int = 10
    max_wait_seconds: float = 5.0
    queue_priority: str = _QUICK_FIRST
    max_queue_depth: int = 100

    @classmethod
    def from_kwargs(cls, args: tuple[object, ...], kwargs: dict[str, Any]) -> WaitingLineSettings:
        config = kwargs.get('config') or _resolve_config(*args, **kwargs)
        max_concurrency = _int(
            _first(
                kwargs,
                'max_concurrency',
                'concurrency',
                'cap',
                default=_config_value(
                    config, 'max_concurrency', 'lambda_reserved_concurrency', default=20
                ),
            ),
            20,
        )
        max_per_company = _int(
            _first(
                kwargs,
                'max_per_company',
                'per_company_concurrency',
                'company_concurrency',
                default=_config_value(
                    config,
                    'waiting_line_max_per_company',
                    'question_max_parallel_per_company',
                    default=max(1, max_concurrency // 2),
                ),
            ),
            max(1, max_concurrency // 2),
        )
        settings = cls(
            max_concurrency=max_concurrency,
            max_per_company=max_per_company,
            max_wait_seconds=_float(
                _first(
                    kwargs,
                    'max_wait_seconds',
                    'timeout_seconds',
                    'queue_max_wait_seconds',
                    default=_config_value(
                        config, 'queue_max_wait_seconds', 'max_wait_seconds', default=5.0
                    ),
                ),
                5.0,
            ),
            queue_priority=_text(
                _first(
                    kwargs,
                    'queue_priority',
                    'ordering',
                    'mode',
                    default=_config_value(config, 'queue_priority', default=_QUICK_FIRST),
                )
            ).lower()
            or _QUICK_FIRST,
            max_queue_depth=_int(
                _first(
                    kwargs,
                    'max_queue_depth',
                    'queue_max_depth',
                    'queue_depth',
                    default=_config_value(
                        config, 'max_queue_depth', 'queue_max_depth', default=100
                    ),
                ),
                100,
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.max_concurrency < 1:
            raise ValueError('max_concurrency must be at least 1')
        if self.max_per_company < 1:
            raise ValueError('max_per_company must be at least 1')
        if self.max_wait_seconds <= 0:
            raise ValueError('max_wait_seconds must be greater than 0')
        if self.max_queue_depth < 0:
            raise ValueError('max_queue_depth must be 0 (unlimited) or greater')
        if self.queue_priority not in _ORDERINGS:
            raise ValueError(
                f'queue_priority must be one of {sorted(_ORDERINGS)}, got {self.queue_priority!r}'
            )


__all__ = ['WaitingLineSettings', 'priority_rank']
