"""Reader factory helpers."""

from __future__ import annotations

from typing import Any

from .reader_factory_instance import ReaderFactoryInstance as ReaderFactoryInstance  # noqa: PLC0414
from .reader_registry import build_reader_registry

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


def _reader_factory_builders() -> dict[str, Any]:
    from .container import _READER_FACTORY_BUILDERS

    return _READER_FACTORY_BUILDERS


def _reader_factory_aliases() -> dict[str, Any]:
    from .container import _READER_FACTORY_ALIASES

    return _READER_FACTORY_ALIASES


class ReaderFactory:
    """Factory for creating reader instances or a full reader registry."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        has_name = any(
            k in kwargs for k in ('name', 'reader', 'reader_name', 'reader_type')
        ) or any(isinstance(a, str) for a in args)
        if has_name:
            self.config = kwargs.get('config', kwargs.get('settings'))
            try:
                self.config = (
                    self.config if self.config is not None else resolve_config(*args, **kwargs)
                )
            except Exception:
                self.config = resolve_config(*args, **kwargs) if args or kwargs else None
            self.session = kwargs.get('session', kwargs.get('db_session'))
            if self.session is None:
                try:
                    self.session = resolve_session(*args, **kwargs)
                except Exception:
                    self.session = None
            self.registry = None
            self.readers = None
            self.reader_registry = None
            return
        try:
            self.config = resolve_config(*args, **kwargs) if args or kwargs else None
        except Exception:
            self.config = None
        try:
            self.session = resolve_session(*args, **kwargs) if args or kwargs else None
        except Exception:
            self.session = None
        filtered = {
            k: v for k, v in kwargs.items() if k not in _SESSION_KEYS and k not in _CONFIG_KEYS
        }
        try:
            self.registry = build_reader_registry(
                config=self.config, session=self.session, **filtered
            )
        except Exception:
            try:
                self.registry = build_reader_registry(*args, **kwargs)
            except Exception:
                self.registry = None
        self.readers = self.registry
        self.reader_registry = self.registry

        def _create(*a: Any, **k: Any) -> Any:
            kk = dict(k)
            kk.setdefault('config', self.config)
            kk.setdefault('session', self.session)
            return ReaderFactory.create(*a, **kk)

        self.create = _create  # type: ignore[method-assign]
        self.build = _create  # type: ignore[method-assign]
        self.get_reader = _create  # type: ignore[method-assign]

    def get(self, name: Any, default: Any = None) -> Any:
        registry: Any = getattr(self, 'registry', None)
        if registry is None:
            try:
                registry = build_reader_registry()
            except Exception:
                registry = None
        if isinstance(registry, dict):
            try:
                return registry.get(name, default)
            except Exception:
                return default
        return default

    def __getitem__(self, key: Any) -> Any:
        registry: Any = getattr(self, 'registry', None)
        if registry is None:
            registry = build_reader_registry()
        if isinstance(registry, dict):
            return registry[key]
        raise KeyError(key)

    def __contains__(self, item: Any) -> bool:
        registry: Any = getattr(self, 'registry', None)
        if registry is None:
            return False
        if isinstance(registry, dict):
            return item in registry
        return False

    @staticmethod
    def available_names() -> list[str]:
        return [
            'pdfplumber',
            'textract',
            'tesseract',
            'self_hosted_layout',
            'table',
            'excel',
            'csv',
            'docx',
        ]

    @staticmethod
    def _resolve_config(*args: Any, **kwargs: Any) -> Any:
        return resolve_config(*args, **kwargs)

    @staticmethod
    def _resolve_session(*args: Any, **kwargs: Any) -> Any:
        return resolve_session(*args, **kwargs)

    @classmethod
    def create(cls, *args: Any, **kwargs: Any) -> Any:
        name = kwargs.pop('name', None)
        if name is None:
            name = kwargs.pop('reader', None)
        if name is None:
            name = kwargs.pop('reader_name', None)
        if name is None:
            name = kwargs.pop('reader_type', None)

        positional_names: list[str] = []
        positional_others: list[Any] = []
        for arg in args:
            if isinstance(arg, str):
                positional_names.append(arg)
            else:
                positional_others.append(arg)
        if name is None and positional_names:
            name = positional_names[0]
        if positional_others and 'config' not in kwargs and 'session' not in kwargs:
            # First non-string positional is normally the config object.
            kwargs.setdefault('config', positional_others[0])
            if len(positional_others) > 1:
                kwargs.setdefault('session', positional_others[1])

        config = kwargs.get('config', kwargs.get('settings'))
        session = kwargs.get('session', kwargs.get('db_session'))

        if name is None:
            # Factory "create(config)" -> full registry.
            filtered = {
                k: v
                for k, v in kwargs.items()
                if k not in {'name', 'reader', 'reader_name', 'reader_type'}
            }
            return build_reader_registry(*positional_others, **filtered)

        # Single reader creation.
        if config is None:
            try:
                config = resolve_config(**kwargs)
            except Exception:
                config = None
        if session is None:
            try:
                session = resolve_session(**kwargs)
            except Exception:
                session = None

        factory_map = _reader_factory_builders()
        key = str(name).strip().lower()
        matched = None
        for candidate_key, builder in factory_map.items():
            if candidate_key == key or candidate_key.replace('_', '') == key.replace('_', ''):
                matched = builder
                break
        if matched is None:
            # Alias matching.
            for alias, canonical in _reader_factory_aliases().items():
                if alias == key:
                    matched = factory_map.get(canonical)
                    break

        extra = {
            k: v
            for k, v in kwargs.items()
            if k not in _SESSION_KEYS
            and k not in _CONFIG_KEYS
            and k
            not in {
                'config',
                'session',
                'settings',
                'db_session',
                'name',
                'reader',
                'reader_name',
                'reader_type',
            }
        }

        if matched is not None and matched is not build_reader_registry:
            return matched(config=config, session=session, **extra)

        # Fallback: registry lookup.
        try:
            registry = build_reader_registry(config=config, session=session, **extra)
            return registry.get(str(name)) if hasattr(registry, 'get') else registry.get(name)
        except ImportError:
            return None

        except Exception:
            raise

    @classmethod
    def build(cls, *args: Any, **kwargs: Any) -> Any:
        return cls.create(*args, **kwargs)

    @classmethod
    def build_registry(cls, *args: Any, **kwargs: Any) -> Any:
        return build_reader_registry(*args, **kwargs)

    @classmethod
    def get_reader(cls, *args: Any, **kwargs: Any) -> Any:
        return cls.create(*args, **kwargs)

    @classmethod
    def from_config(cls, *args: Any, **kwargs: Any) -> Any:
        return build_reader_registry(*args, **kwargs)


def build_reader_factory(*args: Any, **kwargs: Any) -> Any:
    # Prefer class-level factory semantics when a reader name is explicitly supplied.
    has_name = any(k in kwargs for k in ('name', 'reader', 'reader_name', 'reader_type')) or any(
        isinstance(a, str) for a in args
    )
    if has_name:
        return ReaderFactory.create(*args, **kwargs)
    try:
        return ReaderFactoryInstance(*args, **kwargs)
    except Exception:
        try:
            return build_reader_registry(*args, **kwargs)
        except Exception:
            return ReaderFactory


def build_reader(*args: Any, **kwargs: Any) -> Any:
    return ReaderFactory.create(*args, **kwargs)


def create_reader(*args: Any, **kwargs: Any) -> Any:
    return ReaderFactory.create(*args, **kwargs)


def get_reader(*args: Any, **kwargs: Any) -> Any:
    return ReaderFactory.create(*args, **kwargs)
