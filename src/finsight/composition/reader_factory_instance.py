"""Reader factory instance."""

from __future__ import annotations

from typing import Any

_SESSION_KEYS = (
    'session',
    'db_session',
    'database_session',
    'connection',
    'engine',
    'session_or_engine',
    'db_connection',
    'session_factory',
)

_CONFIG_KEYS = (
    'config',
    'settings',
    'configuration',
    'app_config',
)


def resolve_config(*args: Any, **kwargs: Any) -> Any:
    from .container import resolve_config as _resolve_config

    return _resolve_config(*args, **kwargs)


def resolve_session(*args: Any, **kwargs: Any) -> Any:
    from .container import resolve_session as _resolve_session

    return _resolve_session(*args, **kwargs)


class ReaderFactoryInstance:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = resolve_config(*args, **kwargs) if args or kwargs else None
        try:
            self.session = resolve_session(*args, **kwargs) if args or kwargs else None
        except Exception:
            self.session = None
        from .reader_registry import build_reader_registry as _build_reader_registry

        self.registry = _build_reader_registry(
            config=self.config,
            session=self.session,
            **{k: v for k, v in kwargs.items() if k not in _SESSION_KEYS and k not in _CONFIG_KEYS},
        )
        self.readers = self.registry
        self.reader_registry = self.registry

    def create(self, *args: Any, **kwargs: Any) -> Any:
        if args and isinstance(args[0], str):
            kwargs = dict(kwargs)
            kwargs.setdefault('config', self.config)
            kwargs.setdefault('session', self.session)
            from .reader_factory import ReaderFactory as _ReaderFactory

            return _ReaderFactory.create(args[0], **kwargs)
        kwargs = dict(kwargs)
        kwargs.setdefault('config', self.config)
        kwargs.setdefault('session', self.session)
        from .reader_factory import ReaderFactory as _ReaderFactory

        return _ReaderFactory.create(**kwargs)

    def get(self, name: Any, default: Any = None) -> Any:
        return self.registry.get(name, default)

    def __getitem__(self, key: Any) -> Any:
        return self.registry[key]

    def __contains__(self, item: Any) -> bool:
        return item in self.registry
