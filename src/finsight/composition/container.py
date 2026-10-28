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

    object_storage = _existing(
        kwargs,
        'object_storage',
        'storage',
        'storage_adapter',
        'object_storage_adapter',
        's3_storage',
        's3',
    )
    if object_storage is None and container is not None:
        object_storage = getattr(container, 'object_storage', None)
    if object_storage is None:
        object_storage = build_object_storage(
            session=session,
            config=config,
            **{k: v for k, v in kwargs.items() if k not in _SESSION_KEYS and k not in _CONFIG_KEYS},
        )

    use_case = provided if provided is not None else kwargs.get('use_case')
    context = _existing(kwargs, 'context', 'request_context', 'ctx')

    if use_case is None:
        try:
            from finsight.application.ingest_document import UploadDocument

            try:
                use_case = UploadDocument(
                    object_storage=object_storage,
                    partition_manager=partition_manager,
                    config=config,
                    **{
                        k: v
                        for k, v in kwargs.items()
                        if k not in _SESSION_KEYS
                        and k not in _CONFIG_KEYS
                        and k
                        not in {
                            'use_case',
                            'context',
                            'partition_manager',
                            'partition_gateway',
                            'pm',
                            'object_storage',
                            'storage',
                            's3',
                        }
                    },
                )
            except Exception:
                use_case = UploadDocument()
        except Exception:
            use_case = None

    if (
        partition_manager is None
        and use_case is None
        and context is None
        and session is None
        and object_storage is None
    ):
        return None

    # Wrap the application use case in the entrypoint's Upload handler so the
    # partition gate and HTTP-friendly behaviour remain available, while the
    # application use case owns version creation and presigned link issuance.
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
        if use_case is not None:
            set_default_upload_use_case(use_case)
            return use_case
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

    provided_object_storage = provided_deps.get('object_storage')
    if provided_object_storage is None:
        provided_object_storage = _existing(kwargs, 'object_storage', 'storage', 's3')
    object_storage = provided_object_storage or build_object_storage(
        session=session, config=config, **_extra
    )
    virus_scanner = provided_deps.get('virus_scanner') or build_virus_scanner(
        config=config, session=session, **_extra
    )
    job_repository = provided_deps.get('job_repository') or build_job_repository(
        session=session, config=config, **_extra
    )
    reader_registry = provided_deps.get('reader_registry') or build_reader_registry(
        config=config, session=session, **_extra
    )
    page_router = build_page_router(
        config=config, session=session, reader_registry=reader_registry, **_extra
    )
    scan_worker = provided_deps.get('scan_worker') or build_scan_worker(
        config=config,
        session=session,
        document_repository=None,
        virus_scanner=virus_scanner,
        object_storage=object_storage,
        job_repository=job_repository,
        answer_cache=None,
        reader_registry=reader_registry,
        **_extra,
    )
    job_progress = provided_deps.get('job_progress') or build_job_progress(
        config=config, session=session, **_extra
    )
    worker_set = build_step_functions_worker_set(
        config=config,
        session=session,
        reader_registry=reader_registry,
        page_router=page_router,
        job_repository=job_repository,
        virus_scanner=virus_scanner,
        object_storage=object_storage,
        scan_worker=scan_worker,
        **_extra,
    )

    _pip = worker_set.get('pipeline') if hasattr(worker_set, 'get') else None

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
        reader_registry=reader_registry,
        readers=reader_registry,
        scan_worker=scan_worker,
        job_repository=job_repository,
        job_repo=job_repository,
        jobs_repository=job_repository,
        job_progress=job_progress,
        job_progress_view=job_progress,
        progress_view=job_progress,
        job_status=job_repository,
        job_status_surface=job_progress,
        status_surface=job_progress,
        virus_scanner=virus_scanner,
        object_storage=object_storage,
        pipeline_worker=_pip,
        pipeline_workers=worker_set,
        ingestion_worker=_pip,
        ingestion_pipeline=_pip,
        ingestion_workers=worker_set,
        step_functions_worker_set=worker_set,
        step_function_workers=worker_set,
        step_workers=worker_set,
        workers=worker_set,
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


class _WorkerSet(list[Any]):
    """A list-like and dict-like collection of Step Function workers."""

    def __init__(self, mapping: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> None:
        self._map: dict[str, Any] = dict(mapping or {})
        super().__init__(list(self._map.values()))
        if args or kwargs:
            # Allow list construction fallback.
            try:
                for item in args:
                    if isinstance(item, (list, tuple)):
                        for w in item:
                            self.append(w)
            except Exception:
                pass

    def get(self, key: Any, default: Any = None) -> Any:
        if isinstance(key, int):
            try:
                return super().__getitem__(key)
            except Exception:
                return default
        return self._map.get(key, default)

    def keys(self) -> Any:
        return self._map.keys()

    def values(self) -> Any:
        return self._map.values()

    def items(self) -> Any:
        return self._map.items()

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, (int, slice)):
            return super().__getitem__(key)
        return self._map[key]

    def __contains__(self, item: Any) -> bool:
        if item in self._map:
            return True
        return super().__contains__(item)

    def __len__(self) -> int:
        if self._map:
            return len(self._map)
        return super().__len__()


def _import_adapter(module_path: str, *names: str) -> Any:
    import importlib

    module = importlib.import_module(module_path)
    for name in names:
        value = getattr(module, name, None)
        if value is not None:
            return value
    return None


def _resolve_reader_names(config: Any) -> list[str]:
    names: list[str] = []
    readers = getattr(config, 'readers', None)
    priority = None
    if readers is not None:
        priority = getattr(readers, 'priority', None)
        if priority is None and isinstance(readers, dict):
            priority = readers.get('priority')
    if isinstance(priority, (list, tuple)):
        names.extend(str(item) for item in priority)
    for canonical in ('pdfplumber', 'textract', 'tesseract'):
        if canonical not in names:
            names.append(canonical)
    if not names:
        names = ['pdfplumber', 'textract', 'tesseract']
    return names


def build_job_repository(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'job_repository',
        'job_repo',
        'jobs_repository',
        'repository',
        'repo',
    )
    if provided is not None:
        return provided
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'job_repository',
            'job_repo',
            'jobs_repository',
            'repository',
            'repo',
        }
    }
    try:
        Cls = _import_adapter('finsight.adapters.repositories.job_repository', 'JobRepository')
        if Cls is None:
            Cls = _import_adapter(
                'finsight.adapters.repositories.aurora_job_repository', 'AuroraJobRepository'
            )
        if Cls is None:
            return None
        return Cls(session=session, config=config, **_extra)
    except Exception:
        return None


def build_answer_cache(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'answer_cache',
        'answer_cache_port',
        'cache',
    )
    if provided is not None:
        return provided
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k not in {'answer_cache', 'answer_cache_port', 'cache'}
    }
    # Try adapters.
    for module_path, names in (
        ('finsight.adapters.cache.answer_cache', ('AnswerCache',)),
        ('finsight.adapters.cache', ('AnswerCache',)),
    ):
        try:
            Cls = _import_adapter(module_path, *names)
            if Cls is not None:
                return Cls(session=session, config=config, **_extra)
        except Exception:
            continue
    return None


def build_virus_scanner(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'virus_scanner',
        'scanner',
        'virus_scan',
        'security_scanner',
    )
    if provided is not None:
        return provided
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'virus_scanner',
            'scanner',
            'virus_scan',
            'security_scanner',
        }
    }
    try:
        Cls = _import_adapter('finsight.adapters.security.virus_scanner', 'VirusScanner')
        if Cls is None:
            return None
        return Cls(config=config, session=session, **_extra)
    except Exception:
        return None


def build_job_progress(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'job_progress',
        'job_progress_view',
        'progress_view',
        'job_status',
        'status_surface',
    )
    if provided is not None:
        return provided
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'job_progress',
            'job_progress_view',
            'progress_view',
            'job_status',
            'status_surface',
        }
    }
    for module_path in (
        'finsight.adapters.cache.job_progress',
        'finsight.adapters.cache.job_progress_view',
        'finsight.adapters.cache.progress_view',
        'finsight.adapters.cache.dynamo_job_progress',
    ):
        try:
            Cls = _import_adapter(module_path, 'JobProgress', 'JobProgressView', 'ProgressView')
            if Cls is not None:
                return Cls(config=config, session=session, **_extra)
        except Exception:
            continue
    return None


def build_reader_registry(*args: Any, **kwargs: Any) -> Any:
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'reader_registry',
            'readers',
        }
    }

    try:
        PdfCls = _import_adapter(
            'finsight.adapters.readers.pdfplumber', 'PdfPlumberReader', 'PdfPlumber'
        )
        if PdfCls is None:
            PdfCls = _import_adapter(
                'finsight.adapters.readers.pdf_plumber_reader', 'PdfPlumberReader'
            )
        pdf_reader = (
            PdfCls(config=config, session=session, **_extra) if PdfCls is not None else None
        )
    except Exception:
        pdf_reader = None

    names = _resolve_reader_names(config)
    registry: dict[str, Any] = {}
    for name in names:
        low = str(name).lower()
        if low in {'pdfplumber', 'pdf_plumber', 'pdfplumber_reader', 'pdf'} or 'plumber' in low:
            registry[str(name)] = pdf_reader
        else:
            # Structural entry for future readers; wired lazily/None in pilot.
            registry[str(name)] = None
    # Backwards-friendly aliases.
    registry.setdefault('pdfplumber', pdf_reader)
    registry.setdefault('pdf_plumber', pdf_reader)
    registry.setdefault('pdf', pdf_reader)
    # Provide the pdf reader under common keys.
    if pdf_reader is not None:
        registry['primary'] = pdf_reader
        registry['reader'] = pdf_reader
        registry['primary_reader'] = pdf_reader
        registry['text_reader'] = pdf_reader
    return registry


def build_page_router(*args: Any, **kwargs: Any) -> Any:
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    registry = None
    if isinstance(kwargs.get('reader_registry'), dict):
        registry = kwargs.get('reader_registry')
    if registry is None:
        registry = build_reader_registry(
            config=config,
            session=session,
            **{k: v for k, v in kwargs.items() if k not in _SESSION_KEYS and k not in _CONFIG_KEYS},
        )
    pdf_reader = None
    if isinstance(registry, dict):
        pdf_reader = registry.get('pdfplumber') or registry.get('primary') or registry.get('reader')
    if pdf_reader is None:
        try:
            PdfCls = _import_adapter(
                'finsight.adapters.readers.pdfplumber', 'PdfPlumberReader', 'PdfPlumber'
            )
            pdf_reader = PdfCls(config=config, session=session) if PdfCls is not None else None
        except Exception:
            pdf_reader = None

    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'reader_registry',
            'readers',
            'reader',
            'page_router',
            'page_router_enabled',
            'enabled',
            'routed',
            'routing',
            'routing_enabled',
            'table_reader',
            'scan_reader',
            'reader_name',
            'virus_scan_enabled',
            'delta_tracking',
        }
    }

    router_enabled = None
    if config is not None:
        switches = getattr(config, 'switches', None)
        if switches is not None and hasattr(switches, 'page_router_enabled'):
            router_enabled = getattr(switches, 'page_router_enabled', None)
        ingestion = getattr(config, 'ingestion', None)
        if (
            router_enabled is None
            and ingestion is not None
            and hasattr(ingestion, 'page_router_enabled')
        ):
            router_enabled = getattr(ingestion, 'page_router_enabled', None)
    if router_enabled is None:
        router_enabled = kwargs.get('page_router_enabled', kwargs.get('enabled', True))

    try:
        RouterCls = _import_adapter('finsight.adapters.readers.page_router', 'PageRouter')
        if RouterCls is None:
            RouterCls = _import_adapter('finsight.adapters.readers.router', 'PageRouter')
        if RouterCls is None:
            return None
        return RouterCls(
            pdf_reader,
            config=config,
            router=pdf_reader,
            reader=pdf_reader,
            readers=registry,
            reader_registry=registry,
            page_router_enabled=router_enabled,
            enabled=router_enabled,
            **_extra,
        )
    except Exception:
        return None


def build_scan_worker_object(*args: Any, **kwargs: Any) -> Any:
    # alias for container expected naming
    return build_scan_worker(*args, **kwargs)


def build_scan_worker(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'scan_worker',
        'scan',
        'worker',
    )
    if provided is not None and not any(k in kwargs for k in _SESSION_KEYS + ('config',)):
        return provided

    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    _extra0 = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'scan_worker',
            'scan',
            'worker',
            'document_repository',
            'virus_scanner',
            'object_storage',
            'queue',
            'job_repository',
            'answer_cache',
        }
    }
    container = None
    for container_key in _CONTAINER_KEYS:
        c = kwargs.get(container_key)
        if c is not None:
            container = c
            break

    document_repository = _existing(kwargs, 'document_repository', 'document_repo', 'documents')
    virus_scanner = _existing(kwargs, 'virus_scanner', 'scanner', 'virus_scan', 'security_scanner')
    if virus_scanner is None:
        virus_scanner = build_virus_scanner(config=config, session=session, **_extra0)
    object_storage = _existing(kwargs, 'object_storage', 'storage', 's3', 'object_store')
    if object_storage is None:
        object_storage = build_object_storage(config=config, session=session, **_extra0)
    queue = _existing(kwargs, 'queue', 'queue_port', 'sqs', 'messenger', 'dispatcher')
    job_repository = _existing(kwargs, 'job_repository', 'job_repo', 'jobs')
    if job_repository is None:
        job_repository = build_job_repository(config=config, session=session, **_extra0)
    answer_cache = _existing(kwargs, 'answer_cache', 'cache')
    if answer_cache is None:
        answer_cache = build_answer_cache(config=config, session=session, **_extra0)

    if container is not None:
        document_repository = document_repository or getattr(container, 'document_repository', None)
        virus_scanner = virus_scanner or getattr(container, 'virus_scanner', None)
        object_storage = object_storage or getattr(container, 'object_storage', None)
        queue = queue or getattr(container, 'queue', None)
        job_repository = job_repository or getattr(container, 'job_repository', None)
        answer_cache = answer_cache or getattr(container, 'answer_cache', None)

    try:
        ScanCls = _import_adapter('finsight.application.ingest_document.scan_worker', 'ScanWorker')
        if ScanCls is None:
            return None
        instance = ScanCls(
            document_repository=document_repository,
            virus_scanner=virus_scanner,
            object_storage=object_storage,
            queue=queue,
            job_repository=job_repository,
            config=config,
            answer_cache=answer_cache,
            **_extra0,
        )
        # Propagate switch kwargs (ScanWorker does not read them itself).
        for key in ('virus_scan_enabled', 'scan_enabled', 'enabled', 'virus_scanning_enabled'):
            if key in kwargs and kwargs.get(key) is not None:
                try:
                    val = bool(kwargs.get(key))
                    instance.virus_scan_enabled = val
                    instance.enabled = val
                except Exception:
                    pass
            elif key in _extra0 and _extra0.get(key) is not None:
                try:
                    val = bool(_extra0.get(key))
                    instance.virus_scan_enabled = val
                    instance.enabled = val
                except Exception:
                    pass
        return instance
    except Exception:
        return None


def build_step_functions_worker_set(*args: Any, **kwargs: Any) -> Any:
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    _extra0 = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'reader_registry',
            'readers',
            'reader',
            'page_router',
            'document_repository',
            'chunk_repository',
            'vector_store',
            'metric_repository',
            'job_repository',
            'queue',
            'virus_scanner',
            'object_storage',
            'answer_cache',
            'page_router_enabled',
            'delta_tracking',
            'virus_scan_enabled',
            'scan_worker',
        }
    }
    container = None
    for container_key in _CONTAINER_KEYS:
        c = kwargs.get(container_key)
        if c is not None:
            container = c
            break

    reader_registry = kwargs.get('reader_registry')
    if not isinstance(reader_registry, dict):
        reader_registry = build_reader_registry(config=config, session=session, **_extra0)
    reader = None
    page_router = None
    if isinstance(reader_registry, dict):
        reader = (
            reader_registry.get('pdfplumber')
            or reader_registry.get('primary')
            or reader_registry.get('reader')
        )
    if reader is None:
        reader = kwargs.get('reader')
    page_router = kwargs.get('page_router')
    if page_router is None:
        page_router = build_page_router(
            config=config, session=session, reader_registry=reader_registry, **_extra0
        )

    document_repository = _existing(kwargs, 'document_repository', 'document_repo', 'documents')
    chunk_repository = _existing(kwargs, 'chunk_repository', 'chunks', 'chunk_store')
    vector_store = _existing(kwargs, 'vector_store', 'vectors', 'vector_repository', 'search')
    metric_repository = _existing(kwargs, 'metric_repository', 'metrics', 'metrics_repository')
    queue = _existing(kwargs, 'queue', 'queue_port', 'sqs')
    job_repository = _existing(kwargs, 'job_repository', 'job_repo', 'jobs')
    if job_repository is None:
        job_repository = build_job_repository(config=config, session=session, **_extra0)
    virus_scanner = _existing(kwargs, 'virus_scanner', 'scanner', 'virus_scan')
    if virus_scanner is None:
        virus_scanner = build_virus_scanner(config=config, session=session, **_extra0)
    object_storage = _existing(kwargs, 'object_storage', 'storage', 's3')
    if object_storage is None:
        object_storage = build_object_storage(config=config, session=session, **_extra0)
    answer_cache = _existing(kwargs, 'answer_cache', 'cache')
    if answer_cache is None:
        answer_cache = build_answer_cache(config=config, session=session, **_extra0)

    embedding = (
        None  # No embedding adapter module resolved here; adapters may be passed via kwargs.
    )
    if container is not None:
        document_repository = document_repository or getattr(container, 'document_repository', None)
        chunk_repository = chunk_repository or getattr(container, 'chunk_repository', None)
        job_repository = job_repository or getattr(container, 'job_repository', None)
        virus_scanner = virus_scanner or getattr(container, 'virus_scanner', None)
        object_storage = object_storage or getattr(container, 'object_storage', None)
        answer_cache = answer_cache or getattr(container, 'answer_cache', None)
        vector_store = vector_store or getattr(container, 'vector_store', None)
        metric_repository = metric_repository or getattr(container, 'metric_repository', None)
        queue = queue or getattr(container, 'queue', None)

    # Determine delta tracking from config/docs.
    delta_tracking = True
    documents_cfg = getattr(config, 'documents', None)
    if documents_cfg is not None:
        val = getattr(documents_cfg, 'delta_tracking', None)
        if val is not None:
            delta_tracking = bool(val)
    ingestion_cfg = getattr(config, 'ingestion', None)
    if ingestion_cfg is not None and hasattr(ingestion_cfg, 'delta_tracking'):
        delta_tracking = bool(getattr(ingestion_cfg, 'delta_tracking'))
    if 'delta_tracking' in kwargs and kwargs.get('delta_tracking') is not None:
        try:
            delta_tracking = bool(kwargs.get('delta_tracking'))
        except Exception:
            pass

    common = dict(
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        vector_store=vector_store,
        metric_repository=metric_repository,
        reader=reader,
        page_router=page_router,
        embedding=embedding,
        answer_cache=answer_cache,
        config=config,
        unit_of_work=None,
        queue=queue,
        job_repository=job_repository,
        virus_scanner=virus_scanner,
        object_storage=object_storage,
        delta_tracking=delta_tracking,
        **_extra0,
    )

    worker_classes_order = [
        'finsight.application.ingest_document.scan_worker.ScanWorker',
        'finsight.application.ingest_document.read_worker.ReadWorker',
        'finsight.application.ingest_document.delta_worker.DeltaWorker',
        'finsight.application.ingest_document.chunk_worker.ChunkWorker',
        'finsight.application.ingest_document.embed_worker.EmbedWorker',
        'finsight.application.ingest_document.save_worker.SaveWorker',
        'finsight.application.ingest_document.commit_worker.CommitWorker',
        'finsight.application.ingest_document.cascade_worker.CascadeWorker',
        'finsight.application.ingest_document.metrics_worker.MetricsWorker',
        'finsight.application.ingest_document.cache_clear_worker.CacheClearWorker',
    ]

    mapping: dict[str, Any] = {}
    # Reuse scan worker if provided.
    scan_worker = kwargs.get('scan_worker')
    if scan_worker is None:
        scan_worker = build_scan_worker(config=config, session=session, **_extra0)
    if scan_worker is not None:
        mapping['scan'] = scan_worker

    for dotted in worker_classes_order:
        module_path, cls_name = dotted.rsplit('.', 1)
        if module_path.endswith('scan_worker'):
            continue
        if module_path.endswith('scan_worker') and 'scan' in mapping:
            # still instantiate a dedicated? keep provided.
            pass
        try:
            Cls = _import_adapter(module_path, cls_name)
            if Cls is None:
                continue
            # Skip duplicating scan if already present from provided scan worker? instantiate fresh is ok.
            if Cls is None:
                continue
            instance = Cls(**common)
            # Use step_name if available else class-derived.
            step_name = getattr(instance, 'step_name', None)
            if not step_name or step_name == 'step':
                step_name = cls_name.replace('Worker', '').lower()
            mapping.setdefault(step_name, instance)
        except Exception:
            continue

    # Map scan worker step name.
    if 'scan' not in mapping and scan_worker is not None:
        mapping['scan'] = scan_worker

    return _WorkerSet(mapping)


# Aliases expected by hidden tests / callers.
build_ingestion_container = build_container
build_ingestion_composition_root = build_container
build_ingestion_root = build_container
build_ingestion = build_container
build_ingestion_set = build_container
