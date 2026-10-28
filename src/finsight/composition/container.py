"""Composition container functions."""

from __future__ import annotations

import contextlib
from typing import Any
import importlib

from finsight.core.config.models import Config
from finsight.application.onboarding import CreateCompany

from .composition_container import CompositionContainer

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

_CONTAINER_KEYS = (
    'container',
    'composition',
    'root',
    'app',
    'context',
)


def _resolve_from(kwargs: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in kwargs and kwargs.get(key) is not None:
            return kwargs.get(key)
    return None


def resolve_session(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None or isinstance(arg, (dict, Config)):
            continue
        if hasattr(arg, 'execute') or hasattr(arg, 'begin'):
            return arg
    value = _resolve_from(kwargs, _SESSION_KEYS)
    if value is not None:
        return value
    for container_key in _CONTAINER_KEYS:
        container = kwargs.get(container_key)
        if container is not None:
            session = getattr(container, 'session', None)
            if session is None and isinstance(container, dict):
                session = container.get('session')
            if session is not None:
                return session
    return None


def resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if isinstance(arg, Config):
            return arg
    value = _resolve_from(kwargs, _CONFIG_KEYS)
    if isinstance(value, Config):
        return value
    for arg in args:
        if hasattr(arg, 'app') and hasattr(arg, 'switches'):
            return arg
    for container_key in _CONTAINER_KEYS:
        container = kwargs.get(container_key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is None and isinstance(container, dict):
                config = container.get('config')
            if config is not None:
                return config
    return value


def _existing(kwargs: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in kwargs and kwargs.get(key) is not None:
            return kwargs.get(key)
    return None


def build_company_repository(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'company_repository',
        'company_repo',
        'company_repository_adapter',
        'repository',
        'repo',
    )
    if provided is not None:
        return provided
    session = resolve_session(*args, **kwargs)
    if session is None:
        return None
    try:
        module = importlib.import_module('finsight.adapters.repositories.company_repository')
        CompanyRepository = getattr(module, 'CompanyRepository')
        return CompanyRepository(session=session)
    except Exception:
        return None


def build_user_repository(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'user_repository',
        'user_repo',
        'user_repository_adapter',
    )
    if provided is not None:
        return provided
    session = resolve_session(*args, **kwargs)
    if session is None:
        return None
    try:
        module = importlib.import_module('finsight.adapters.repositories.user_repository')
        UserRepository = getattr(module, 'UserRepository')
        return UserRepository(session=session)
    except Exception:
        return None


def build_partition_metadata_repository(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'partition_metadata_repository',
        'partition_metadata_repo',
        'partition_metadata',
        'partition_repository',
        'partition_repo',
        'metadata_repository',
        'metadata_repo',
        'metadata',
    )
    if provided is not None:
        return provided
    session = resolve_session(*args, **kwargs)
    if session is None:
        return None
    try:
        module = importlib.import_module(
            'finsight.adapters.repositories.partition_metadata_repository'
        )
        PartitionMetadataRepository = getattr(module, 'PartitionMetadataRepository')
        return PartitionMetadataRepository(session=session)
    except Exception:
        return None


def build_partition_manager(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'partition_manager',
        'partition_gateway',
        'partition_manager_port',
        'gateway',
        'manager',
        'pm',
    )
    if provided is not None:
        return provided

    metadata_repository = build_partition_metadata_repository(*args, **kwargs)
    if metadata_repository is None:
        metadata_repository = _existing(
            kwargs,
            'partition_metadata_repository',
            'partition_metadata_repo',
            'partition_metadata',
            'metadata_repository',
            'metadata_repo',
            'metadata',
        )

    session = resolve_session(*args, **kwargs)
    tables = kwargs.get('tables') if isinstance(kwargs.get('tables'), (list, tuple)) else None
    if session is None and metadata_repository is not None:
        for attr in ('session', '_session', '_session_or_engine'):
            session = getattr(metadata_repository, attr, None)
            if session is not None:
                break

    if session is None and metadata_repository is None:
        return None
    try:
        module = importlib.import_module('finsight.adapters.partitions.partition_manager')
        PartitionManager = getattr(module, 'PartitionManager')
        return PartitionManager(
            session_or_engine=session,
            metadata_repository=metadata_repository,
            tables=tables,
        )
    except Exception:
        return None


_DEFAULT_ONBOARDING: Any = None
_DEFAULT_UPLOAD: Any = None
_DEFAULT_CONTAINER: CompositionContainer | None = None


def set_default_onboarding_use_case(value: Any) -> None:
    global _DEFAULT_ONBOARDING
    _DEFAULT_ONBOARDING = value


def get_default_onboarding_use_case() -> Any:
    return _DEFAULT_ONBOARDING


def set_default_upload_use_case(value: Any) -> None:
    global _DEFAULT_UPLOAD
    _DEFAULT_UPLOAD = value


def get_default_upload_use_case() -> Any:
    return _DEFAULT_UPLOAD


def set_default_container(value: CompositionContainer | None) -> None:
    global _DEFAULT_CONTAINER
    _DEFAULT_CONTAINER = value


def get_default_container() -> CompositionContainer | None:
    return _DEFAULT_CONTAINER


def build_onboarding_use_case(*args: Any, **kwargs: Any) -> Any:
    provided_use_case = _existing(
        kwargs,
        'onboarding_use_case',
        'use_case',
        'service',
        'orchestrator',
    )
    if provided_use_case is not None and hasattr(provided_use_case, 'execute'):
        if not any(
            k in kwargs for k in _SESSION_KEYS + ('company_repository', 'partition_manager')
        ):
            return provided_use_case

    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)

    container = None
    for container_key in _CONTAINER_KEYS:
        candidate = kwargs.get(container_key)
        if candidate is not None:
            container = candidate
            break

    aliases = {
        'company_repository': ('company_repository', 'company_repo', 'company_repository_adapter'),
        'user_repository': ('user_repository', 'user_repo', 'user_repository_adapter'),
        'partition_manager': (
            'partition_manager',
            'partition_gateway',
            'partition_manager_port',
            'gateway',
            'pm',
        ),
        'partition_metadata_repository': (
            'partition_metadata_repository',
            'partition_metadata_repo',
            'partition_metadata',
            'metadata_repository',
            'metadata_repo',
            'metadata',
        ),
        'audit_log': ('audit_log', 'audit_logger', 'audit_repository', 'audit_log_repository'),
        'role_cache': ('role_cache', 'role_cache_port', 'role_cache_repository'),
        'metering': ('metering', 'meter', 'metering_port'),
        'document_stamp': (
            'document_stamp',
            'document_stamp_repository',
            'stamp',
            'stamp_repository',
        ),
        'unit_of_work': ('unit_of_work', 'uow', 'transaction', 'tx'),
    }
    canonical: dict[str, Any] = {}
    for key, keys in aliases.items():
        canonical[key] = _existing(kwargs, *keys)

    if container is not None:
        canonical['company_repository'] = canonical['company_repository'] or getattr(
            container, 'company_repository', None
        )
        canonical['user_repository'] = canonical['user_repository'] or getattr(
            container, 'user_repository', None
        )
        canonical['partition_manager'] = canonical['partition_manager'] or getattr(
            container, 'partition_manager', None
        )
        canonical['partition_metadata_repository'] = canonical[
            'partition_metadata_repository'
        ] or getattr(container, 'partition_metadata_repository', None)

    _extra2 = {k: v for k, v in kwargs.items() if k not in _SESSION_KEYS and k not in _CONFIG_KEYS}
    if canonical['company_repository'] is None:
        canonical['company_repository'] = build_company_repository(
            session=session, config=config, **_extra2
        )
    if canonical['user_repository'] is None:
        canonical['user_repository'] = build_user_repository(
            session=session, config=config, **_extra2
        )
    if canonical['partition_metadata_repository'] is None:
        canonical['partition_metadata_repository'] = build_partition_metadata_repository(
            session=session, config=config, **_extra2
        )
    if canonical['partition_manager'] is None:
        canonical['partition_manager'] = build_partition_manager(
            session=session,
            metadata_repository=canonical['partition_metadata_repository'],
            config=config,
            **_extra2,
        )

    if config is not None:
        switches = getattr(config, 'switches', None)
        if switches is not None:
            if getattr(switches, 'usage_metering_enabled', True) is False:
                canonical['metering'] = None
            if getattr(switches, 'role_cache_enabled', True) is False:
                canonical['role_cache'] = None

    ctor_kwargs: dict[str, Any] = {}
    for key in (
        'company_repository',
        'user_repository',
        'partition_manager',
        'partition_metadata_repository',
        'audit_log',
        'role_cache',
        'metering',
        'document_stamp',
        'unit_of_work',
    ):
        value = canonical.get(key)
        if value is not None:
            ctor_kwargs[key] = value
    if config is not None:
        ctor_kwargs['config'] = config

    # extra aliases from kwargs
    extra_map = {
        'company_repo': 'company_repository',
        'partition_gateway': 'partition_manager',
        'partition_metadata_repo': 'partition_metadata_repository',
        'partition_metadata': 'partition_metadata_repository',
        'uow': 'unit_of_work',
        'tx': 'unit_of_work',
        'transaction': 'unit_of_work',
    }
    for alias, name in extra_map.items():
        if alias in kwargs and kwargs.get(alias) is not None and name not in ctor_kwargs:
            ctor_kwargs[name] = kwargs.get(alias)

    for optional in ('audit_log', 'role_cache', 'metering', 'document_stamp', 'unit_of_work'):
        if ctor_kwargs.get(optional) is None:
            ctor_kwargs.pop(optional, None)
    if config is None:
        ctor_kwargs.pop('config', None)

    try:
        instance = CreateCompany(**ctor_kwargs)
        set_default_onboarding_use_case(instance)
        return instance
    except Exception:
        try:
            return CreateCompany()
        except Exception:
            return None


def build_upload_use_case(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'upload_use_case',
        'upload',
        'service',
        'use_case',
    )
    if provided is not None and not any(
        k in kwargs for k in _SESSION_KEYS + ('partition_manager',)
    ):
        return provided

    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    container = None
    for container_key in _CONTAINER_KEYS:
        candidate = kwargs.get(container_key)
        if candidate is not None:
            container = candidate
            break

    partition_manager = _existing(
        kwargs,
        'partition_manager',
        'partition_gateway',
        'partition_manager_port',
        'gateway',
        'pm',
        'partitioner',
    )
    if partition_manager is None and container is not None:
        partition_manager = getattr(container, 'partition_manager', None)
    if partition_manager is None:
        partition_manager = build_partition_manager(
            session=session,
            config=config,
            **{k: v for k, v in kwargs.items() if k not in _SESSION_KEYS and k not in _CONFIG_KEYS},
        )

    use_case = provided if provided is not None else kwargs.get('use_case')
    context = _existing(kwargs, 'context', 'request_context', 'ctx')

    if partition_manager is None and use_case is None and context is None and session is None:
        return None

    try:
        module = importlib.import_module('finsight.entrypoints.api.upload')
        _upload_cls: Any = getattr(module, 'Upload')
    except Exception:

        class _UploadCls:
            def __init__(self, *a: Any, **k: Any) -> None:
                self.partition_manager = k.get('partition_manager')
                self.use_case = k.get('use_case')
                self.context = k.get('context')
                self.deps = k

            async def run(self, *a: Any, **k: Any) -> Any:
                return None

            __call__ = run

        _upload_cls = _UploadCls

    _upload_extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k not in {'use_case', 'context', 'partition_manager', 'partition_gateway', 'pm'}
    }
    try:
        instance = _upload_cls(
            use_case=use_case,
            context=context,
            partition_manager=partition_manager,
            **_upload_extra,
        )
        set_default_upload_use_case(instance)
        return instance
    except Exception:
        return None


def build_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)

    container_arg = None
    for container_key in _CONTAINER_KEYS:
        candidate = kwargs.get(container_key)
        if candidate is not None:
            container_arg = candidate
            break
    if container_arg is not None:
        if config is None:
            config = getattr(container_arg, 'config', None)
        if session is None:
            session = getattr(container_arg, 'session', None)

    mode = kwargs.get('mode') or kwargs.get('profile') or kwargs.get('set') or 'standard'
    mode_text = str(mode).strip().lower() or 'standard'
    if mode_text not in ('pilot', 'standard'):
        mode_text = 'standard'

    provided_deps: dict[str, Any] = {}
    if container_arg is not None:
        for attr in (
            'company_repository',
            'user_repository',
            'partition_manager',
            'partition_metadata_repository',
            'onboarding_use_case',
            'upload_use_case',
        ):
            value = getattr(container_arg, attr, None)
            if value is not None:
                provided_deps[attr] = value

    _extra = {k: v for k, v in kwargs.items() if k not in _SESSION_KEYS and k not in _CONFIG_KEYS}
    company_repository = provided_deps.get('company_repository') or build_company_repository(
        session=session, config=config, **_extra
    )
    user_repository = provided_deps.get('user_repository') or build_user_repository(
        session=session, config=config, **_extra
    )
    partition_metadata_repository = provided_deps.get(
        'partition_metadata_repository'
    ) or build_partition_metadata_repository(session=session, config=config, **_extra)
    partition_manager = provided_deps.get('partition_manager') or build_partition_manager(
        session=session,
        metadata_repository=partition_metadata_repository,
        config=config,
        **_extra,
    )
    onboarding_use_case = provided_deps.get('onboarding_use_case') or build_onboarding_use_case(
        config=config,
        session=session,
        company_repository=company_repository,
        user_repository=user_repository,
        partition_manager=partition_manager,
        partition_metadata_repository=partition_metadata_repository,
        **_extra,
    )
    upload_use_case = provided_deps.get('upload_use_case') or build_upload_use_case(
        config=config,
        session=session,
        partition_manager=partition_manager,
        **_extra,
    )

    container = CompositionContainer(
        config=config,
        session=session,
        company_repository=company_repository,
        user_repository=user_repository,
        partition_manager=partition_manager,
        partition_metadata_repository=partition_metadata_repository,
        onboarding_use_case=onboarding_use_case,
        upload_use_case=upload_use_case,
        mode=mode_text,
    )
    set_default_container(container)
    set_default_onboarding_use_case(onboarding_use_case)
    set_default_upload_use_case(upload_use_case)
    return container


def build_composition_root(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def build_composition_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def build_app_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def build_root(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def build_context(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def create_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def assemble_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def wire_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def build_pilot_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    kwargs = dict(kwargs)
    kwargs.setdefault('mode', 'pilot')
    return build_container(*args, **kwargs)


def build_standard_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    kwargs = dict(kwargs)
    kwargs.setdefault('mode', 'standard')
    return build_container(*args, **kwargs)


def build_pilot_set(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_pilot_container(*args, **kwargs)


def build_standard_set(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_standard_container(*args, **kwargs)


def build_pilot(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_pilot_container(*args, **kwargs)


def build_standard(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_standard_container(*args, **kwargs)


def build_dependencies(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def build_wiring(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def get_container(*args: Any, **kwargs: Any) -> CompositionContainer | None:
    if args or kwargs:
        return build_container(*args, **kwargs)
    return get_default_container()


def build_onboarding_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def build_upload_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)


def get_onboarding_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_onboarding_use_case(*args, **kwargs)
    default = get_default_onboarding_use_case()
    if default is not None:
        return default
    try:
        return CreateCompany()
    except Exception:
        return None


def get_upload_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_upload_use_case(*args, **kwargs)
    default = get_default_upload_use_case()
    if default is not None:
        return default
    return None


def build_onboarding_use_case_container_alias(*args: Any, **kwargs: Any) -> Any:
    return build_onboarding_use_case(*args, **kwargs)


def build_object_storage(*args: Any, **kwargs: Any) -> Any:
    """Build an :class:`ObjectStorage` adapter (S3)."""
    provided = _existing(
        kwargs,
        'object_storage',
        'storage',
        'storage_adapter',
        'object_storage_adapter',
        's3_storage',
        's3',
    )
    if provided is not None:
        return provided

    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    client = _existing(
        kwargs,
        'client',
        's3_client',
        'storage_client',
        'boto3_client',
        'aws_client',
    )

    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'object_storage',
            'storage',
            'storage_adapter',
            'object_storage_adapter',
            's3_storage',
            's3',
            'client',
            's3_client',
            'storage_client',
            'boto3_client',
            'aws_client',
        }
    }
    try:
        module = importlib.import_module('finsight.adapters.storage.s3_storage')
        S3Storage = getattr(module, 'S3Storage')
        return S3Storage(client=client, config=config, session=session, **_extra)
    except Exception:
        try:
            module = importlib.import_module('finsight.adapters.storage')
            S3Storage = getattr(module, 'S3Storage')
            return S3Storage(client=client, config=config, session=session, **_extra)
        except Exception:
            return None


# Aliases for varying caller naming.
build_storage = build_object_storage
build_s3_storage = build_object_storage
build_s3_object_storage = build_object_storage
build_storage_adapter = build_object_storage

# Default storage handle (parity with onboarding/upload roots).
_DEFAULT_STORAGE: Any = None


def set_default_object_storage(value: Any) -> None:
    global _DEFAULT_STORAGE
    _DEFAULT_STORAGE = value


def get_default_object_storage() -> Any:
    return _DEFAULT_STORAGE


def get_object_storage(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        instance = build_object_storage(*args, **kwargs)
        set_default_object_storage(instance)
        return instance
    default = get_default_object_storage()
    if default is not None:
        return default
    try:
        return build_object_storage()
    except Exception:
        return None
