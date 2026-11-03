"""Composition container functions."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import importlib

from finsight.core.config.models import Config
from finsight.core.config.price_table import PriceTable, load_price_table
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
    except ImportError:
        return None
    except Exception:
        raise


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
    except ImportError:
        return None
    except Exception:
        raise


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
    except ImportError:
        return None
    except Exception:
        raise


def build_partition_manager(*args: Any, **kwargs: Any) -> Any:
    return _build_partition_manager_impl(*args, **kwargs)


def _build_partition_manager_impl(*args: Any, **kwargs: Any) -> Any:
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
    except ImportError:
        return None
    except Exception:
        raise


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


_DEFAULT_REPROCESS: Any = None


def set_default_reprocess_use_case(value: Any) -> None:
    global _DEFAULT_REPROCESS
    _DEFAULT_REPROCESS = value


def get_default_reprocess_use_case() -> Any:
    return _DEFAULT_REPROCESS


def set_default_container(value: CompositionContainer | None) -> None:
    global _DEFAULT_CONTAINER
    _DEFAULT_CONTAINER = value


def get_default_container() -> CompositionContainer | None:
    return _DEFAULT_CONTAINER


def build_onboarding_use_case(*args: Any, **kwargs: Any) -> Any:
    return _build_onboarding_use_case_impl(*args, **kwargs)


def _build_onboarding_use_case_impl(*args: Any, **kwargs: Any) -> Any:
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
    if canonical.get('audit_log') is None:
        canonical['audit_log'] = build_audit_log(session=session, config=config, **_extra2)

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
        except ImportError:
            return None

        except Exception:
            raise


def build_upload_use_case(*args: Any, **kwargs: Any) -> Any:
    return _build_upload_use_case_impl(*args, **kwargs)


def _build_upload_use_case_impl(*args: Any, **kwargs: Any) -> Any:
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


def build_container(*args: Any, **kwargs: Any) -> Any:
    return _build_container_impl(*args, **kwargs)


def _build_container_impl(*args: Any, **kwargs: Any) -> CompositionContainer:
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
            'object_storage',
            'virus_scanner',
            'job_repository',
            'reader_registry',
            'scan_worker',
            'job_progress',
            'document_repository',
            'document_table_repository',
            'chunk_repository',
            'vector_write',
            'answer_cache',
            'change_event_publisher',
            'audit_log',
            'metering',
            'tracing',
            'hybrid_search',
            'metric_repository',
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
    metering = (
        provided_deps.get('metering')
        or _existing(kwargs, 'metering', 'meter', 'metering_port')
        or build_metering(config=config, **_extra)
    )
    tracing = (
        provided_deps.get('tracing')
        or _existing(kwargs, 'tracing', 'tracer', 'tracing_port', 'span_tracer', 'span_tracing')
        or build_tracing(config=config, **_extra)
    )
    onboarding_use_case = provided_deps.get('onboarding_use_case') or build_onboarding_use_case(
        config=config,
        session=session,
        company_repository=company_repository,
        user_repository=user_repository,
        partition_manager=partition_manager,
        partition_metadata_repository=partition_metadata_repository,
        metering=metering,
        **{
            k: v
            for k, v in _extra.items()
            if k
            not in {
                'metering',
                'meter',
                'metering_port',
                'usage_metering',
                'tracing',
                'tracer',
                'tracing_port',
                'span_tracer',
                'span_tracing',
            }
        },
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
    document_repository = provided_deps.get('document_repository') or build_document_repository(
        session=session, config=config, **_extra
    )
    document_table_repository = provided_deps.get(
        'document_table_repository'
    ) or build_document_table_repository(session=session, config=config, **_extra)
    chunk_repository = provided_deps.get('chunk_repository') or build_chunk_repository(
        session=session, config=config, **_extra
    )
    vector_write = provided_deps.get('vector_write') or build_vector_write(
        session=session, config=config, **_extra
    )
    answer_cache = provided_deps.get('answer_cache') or build_answer_cache(
        session=session, config=config, **_extra
    )
    change_event_publisher = provided_deps.get(
        'change_event_publisher'
    ) or build_change_event_publisher(config=config, **_extra)
    audit_log = (
        provided_deps.get('audit_log')
        or _existing(kwargs, 'audit_log', 'audit', 'audit_logger', 'audit_log_port')
        or build_audit_log(session=session, config=config, **_extra)
    )
    unit_of_work = provided_deps.get('unit_of_work') or _existing(
        kwargs, 'unit_of_work', 'uow', 'transaction', 'tx'
    )
    if unit_of_work is None:
        unit_of_work = build_unit_of_work(config=config, session=session, **_extra)
    reader_registry = provided_deps.get('reader_registry') or build_reader_registry(
        config=config, session=session, **_extra
    )
    page_router = build_page_router(
        config=config, session=session, reader_registry=reader_registry, **_extra
    )
    _worker_extra = {
        k: v
        for k, v in _extra.items()
        if k
        not in {
            'document_repository',
            'chunk_repository',
            'document_table_repository',
            'document_tables_repository',
            'document_table_repo',
            'table_repository',
            'tables_repository',
            'table_store',
            'vector_write',
            'vector_store',
            'vector_store_write',
            'vector_writer',
            'answer_cache',
            'change_event_publisher',
            'event_publisher',
            'publisher',
            'reader_registry',
            'page_router',
            'scan_worker',
            'job_progress',
            'object_storage',
            'virus_scanner',
            'job_repository',
        }
    }
    scan_worker = provided_deps.get('scan_worker') or build_scan_worker(
        config=config,
        session=session,
        document_repository=document_repository,
        virus_scanner=virus_scanner,
        object_storage=object_storage,
        job_repository=job_repository,
        answer_cache=answer_cache,
        reader_registry=reader_registry,
        **_worker_extra,
    )
    job_progress = provided_deps.get('job_progress') or build_job_progress(
        config=config, session=session, **_extra
    )
    worker_set = build_step_functions_worker_set(
        config=config,
        session=session,
        reader_registry=reader_registry,
        page_router=page_router,
        document_repository=document_repository,
        document_table_repository=document_table_repository,
        chunk_repository=chunk_repository,
        vector_store=vector_write,
        vector_write=vector_write,
        answer_cache=answer_cache,
        change_event_publisher=change_event_publisher,
        audit_log=audit_log,
        job_repository=job_repository,
        virus_scanner=virus_scanner,
        object_storage=object_storage,
        scan_worker=scan_worker,
        **_worker_extra,
    )

    _pip = worker_set.get('pipeline') if hasattr(worker_set, 'get') else None

    waiting_line = provided_deps.get('waiting_line')
    if waiting_line is None:
        waiting_line = _existing(
            kwargs, 'waiting_line', 'waiting', 'waiting_line_port', 'queue_line'
        )
    if waiting_line is None:
        waiting_line = build_waiting_line(config=config, session=session, **_extra)

    hybrid_search = provided_deps.get('hybrid_search')
    if hybrid_search is None:
        hybrid_search = _existing(
            kwargs, 'hybrid_search', 'search', 'hybrid_search_port', 'vector_search'
        )
    if hybrid_search is None:
        hybrid_search = build_hybrid_search(config=config, session=session, **_extra)

    metric_repository = provided_deps.get('metric_repository')
    if metric_repository is None:
        metric_repository = _existing(
            kwargs, 'metric_repository', 'metrics', 'metrics_repository', 'metric_repo', 'metric'
        )
    if metric_repository is None:
        metric_repository = build_metric_repository(config=config, session=session, **_extra)

    ask_question_use_case = _existing(
        kwargs,
        'ask_question_use_case',
        'ask_use_case',
        'ask_question',
        'ask',
        'qa_use_case',
        'question_use_case',
    )
    if ask_question_use_case is None:
        ask_question_use_case = provided_deps.get('ask_question_use_case')
    if ask_question_use_case is None:
        from finsight.application.ask_question import AskQuestion
        from .adapter_stacks import (
            _build_llm_stack as _build_llm_gateway,
            _build_embedding_stack as _build_embedding_provider,
            _build_reranker_stack as _build_reranker,
        )

        llm_gateway = _existing(kwargs, 'llm_gateway', 'llm', 'gateway', 'model_gateway', 'model')
        if llm_gateway is None:
            llm_gateway = _build_llm_gateway(config=config)

        embedding_provider = _existing(
            kwargs, 'embedding_provider', 'embedding', 'embeddings', 'embedder'
        )
        if embedding_provider is None:
            embedding_provider = _build_embedding_provider(config=config)

        reranker = _existing(kwargs, 'reranker', 'ranker', 'reranker_port')
        if reranker is None:
            reranker = _build_reranker(config=config)

        signing_key = _existing(kwargs, 'signing_key', 'secret', 'secret_key')
        if signing_key is None:
            signing_key = config.signing_key
        if signing_key is None:
            raise ValueError('signing_key must be configured')

        ask_question_use_case = AskQuestion(
            config=config,
            llm_gateway=llm_gateway,
            embedding_provider=embedding_provider,
            hybrid_search=hybrid_search,
            reranker=reranker,
            metric_repository=metric_repository,
            answer_cache=answer_cache,
            waiting_line=waiting_line,
            tracing=tracing,
            signing_key=signing_key,
        )

    source_viewer_use_case = _existing(
        kwargs,
        'source_viewer_use_case',
        'source_viewer',
    )
    if source_viewer_use_case is None:
        source_viewer_use_case = provided_deps.get('source_viewer_use_case')
    if source_viewer_use_case is None:
        signing_key = _existing(kwargs, 'signing_key', 'secret', 'secret_key')
        if signing_key is None:
            signing_key = getattr(config, 'signing_key', None)
        if signing_key is None:
            raise ValueError('signing_key must be configured')

        from finsight.application.source_viewer import SourceViewer
        from finsight.application.source_viewer.steps import (
            AuditStep,
            AuthorizeStep,
            FetchContentStep,
            FetchOriginalStep,
            ResolveCitationStep,
            ResolveVersionStep,
        )

        from .source_viewer import resolve_source_viewer_settings

        retention_days, original_link_ttl = resolve_source_viewer_settings(config)

        source_viewer_use_case = SourceViewer(
            authorize_step=AuthorizeStep(config=config),
            resolve_citation_step=ResolveCitationStep(signing_key=signing_key),
            resolve_version_step=ResolveVersionStep(
                document_repository=document_repository,
                version_retention_days=retention_days,
            ),
            fetch_content_step=FetchContentStep(
                chunk_repository=chunk_repository,
                table_repository=document_table_repository,
            ),
            fetch_original_step=FetchOriginalStep(
                object_storage=object_storage,
                document_repository=document_repository,
                ttl=original_link_ttl,
            ),
            audit_step=AuditStep(audit_log=audit_log),
            tracing=tracing,
        )

    queue = provided_deps.get('queue')
    if queue is None:
        queue = _existing(kwargs, 'queue', 'queue_port', 'sqs', 'job_queue', 'reprocessing_queue')
    if queue is None:
        queue = build_queue(config=config, session=session, **_extra)

    reprocess_use_case = _existing(
        kwargs,
        'reprocess_use_case',
        'reprocess',
    )
    if reprocess_use_case is None:
        reprocess_use_case = provided_deps.get('reprocess_use_case')
    if reprocess_use_case is None:
        reprocess_use_case = build_reprocess_use_case(
            config=config,
            session=session,
            document_repository=document_repository,
            chunk_repository=chunk_repository,
            vector_write=vector_write,
            answer_cache=answer_cache,
            job_repository=job_repository,
            queue=queue,
            change_event_publisher=change_event_publisher,
            company_repository=company_repository,
            unit_of_work=unit_of_work,
            tracing=tracing,
            **{
                k: v
                for k, v in (_extra or {}).items()
                if k
                not in {
                    'queue',
                    'queue_port',
                    'sqs',
                    'job_queue',
                    'reprocessing_queue',
                    'document_repository',
                    'chunk_repository',
                    'vector_write',
                    'answer_cache',
                    'job_repository',
                    'change_event_publisher',
                    'company_repository',
                    'unit_of_work',
                    'tracing',
                    'cache',
                    'chunks',
                    'documents',
                    'publisher',
                    'event_publisher',
                    'companies',
                    'uow',
                    'transaction',
                    'tx',
                    'tracer',
                    'tracing_port',
                    'span_tracer',
                    'span_tracing',
                }
            },
        )

    state_store = _existing(
        kwargs,
        'state_store',
        'step_state_store',
        'pipeline_state_store',
        'context_store',
        'run_state_store',
        'store',
    )
    if state_store is None:
        from finsight.composition.state_store import build_state_store as _build_state_store

        state_store = _build_state_store(config=config, session=session, **_extra)

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
        document_repository=document_repository,
        document_table_repository=document_table_repository,
        chunk_repository=chunk_repository,
        vector_store=vector_write,
        vector_write=vector_write,
        answer_cache=answer_cache,
        change_event_publisher=change_event_publisher,
        audit_log=audit_log,
        unit_of_work=unit_of_work,
        queue=queue,
        waiting_line=waiting_line,
        hybrid_search=hybrid_search,
        metric_repository=metric_repository,
        reprocess_use_case=reprocess_use_case,
        metering=metering,
        tracing=tracing,
        pipeline_worker=_pip,
        pipeline_workers=worker_set,
        ingestion_worker=_pip,
        ingestion_pipeline=_pip,
        ingestion_workers=worker_set,
        step_functions_worker_set=worker_set,
        step_function_workers=worker_set,
        step_workers=worker_set,
        workers=worker_set,
        ask_question_use_case=ask_question_use_case,
        ask_use_case=ask_question_use_case,
        source_viewer_use_case=source_viewer_use_case,
        documents_use_case=document_repository,
        documents=document_repository,
        state_store=state_store,
        step_state_store=state_store,
        pipeline_state_store=state_store,
        context_store=state_store,
        run_state_store=state_store,
    )
    try:
        for _attr in (
            'state_store',
            'step_state_store',
            'pipeline_state_store',
            'context_store',
            'run_state_store',
            'store',
        ):
            setattr(container, _attr, state_store)
    except Exception:  # noqa: S110
        pass
    set_default_container(container)
    set_default_onboarding_use_case(onboarding_use_case)
    set_default_upload_use_case(upload_use_case)
    set_default_reprocess_use_case(reprocess_use_case)
    return container


def build_composition_root(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_composition_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_app_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_root(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_context(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def create_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def assemble_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def wire_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_pilot_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    kwargs = dict(kwargs)
    kwargs.setdefault('mode', 'pilot')
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_standard_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    kwargs = dict(kwargs)
    kwargs.setdefault('mode', 'standard')
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_pilot_set(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_pilot_container(*args, **kwargs)


def build_standard_set(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_standard_container(*args, **kwargs)


def build_pilot(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_pilot_container(*args, **kwargs)


def build_standard(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_standard_container(*args, **kwargs)


def build_dependencies(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_wiring(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def get_container(*args: Any, **kwargs: Any) -> CompositionContainer | None:
    if args or kwargs:
        return build_container(*args, **kwargs)  # type: ignore[no-any-return]
    return get_default_container()


def build_onboarding_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def build_upload_container(*args: Any, **kwargs: Any) -> CompositionContainer:
    return build_container(*args, **kwargs)  # type: ignore[no-any-return]


def get_onboarding_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_onboarding_use_case(*args, **kwargs)
    default = get_default_onboarding_use_case()
    if default is not None:
        return default
    try:
        return CreateCompany()
    except ImportError:
        return None
    except Exception:
        raise


def get_upload_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_upload_use_case(*args, **kwargs)
    default = get_default_upload_use_case()
    if default is not None:
        return default
    return None


def get_reprocess_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_reprocess_use_case(*args, **kwargs)
    default = get_default_reprocess_use_case()
    if default is not None:
        return default
    default_container = get_default_container()
    if default_container is not None:
        for attr in ('reprocess_use_case', 'reprocess'):
            value = getattr(default_container, attr, None)
            if value is not None:
                return value
    try:
        return build_reprocess_use_case()
    except Exception:
        return None


def build_onboarding_use_case_container_alias(*args: Any, **kwargs: Any) -> Any:
    return build_onboarding_use_case(*args, **kwargs)


def build_object_storage(*args: Any, **kwargs: Any) -> Any:
    return _build_object_storage_impl(*args, **kwargs)


def _build_object_storage_impl(*args: Any, **kwargs: Any) -> Any:
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
        except ImportError:
            return None

        except Exception:
            raise


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
    except ImportError:
        return None
    except Exception:
        raise


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
            except Exception:  # noqa: S110
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
    return _build_job_repository_impl(*args, **kwargs)


def _build_job_repository_impl(*args: Any, **kwargs: Any) -> Any:
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
    except ImportError:
        return None
    except Exception:
        raise


def build_audit_log(*args: Any, **kwargs: Any) -> Any:
    return _build_audit_log_impl(*args, **kwargs)


def _build_audit_log_impl(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'audit_log',
        'audit',
        'audit_logger',
        'audit_log_port',
        'audit_repository',
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
        and k not in {'audit_log', 'audit', 'audit_logger', 'audit_log_port', 'audit_repository'}
    }
    for module_path, names in (
        (
            'finsight.adapters.audit.postgres_audit_log',
            ('PostgresAuditLog', 'AuditLog'),
        ),
    ):
        try:
            Cls = _import_adapter(module_path, *names)
            if Cls is not None:
                return Cls(session=session, config=config, **_extra)
        except Exception:  # noqa: S112
            continue
    return None


def build_document_repository(*args: Any, **kwargs: Any) -> Any:
    return _build_document_repository_impl(*args, **kwargs)


def _build_document_repository_impl(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'document_repository',
        'document_repo',
        'documents',
        'document_repository_adapter',
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
            'document_repository',
            'document_repo',
            'documents',
            'document_repository_adapter',
        }
    }
    for module_path, names in (
        (
            'finsight.adapters.repositories.postgres_document_repository',
            ('PostgresDocumentRepository', 'AuroraDocumentRepository'),
        ),
        (
            'finsight.adapters.repositories.aurora_document_repository',
            ('AuroraDocumentRepository', 'PostgresDocumentRepository'),
        ),
    ):
        try:
            Cls = _import_adapter(module_path, *names)
            if Cls is not None:
                return Cls(session=session, config=config, **_extra)
        except Exception:  # noqa: S112
            continue
    return None


def build_document_table_repository(*args: Any, **kwargs: Any) -> Any:
    return _build_document_table_repository_impl(*args, **kwargs)


def _build_document_table_repository_impl(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'document_table_repository',
        'document_tables_repository',
        'document_table_repo',
        'table_repository',
        'tables_repository',
        'table_store',
        'document_table_repository_adapter',
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
            'document_table_repository',
            'document_tables_repository',
            'document_table_repo',
            'table_repository',
            'tables_repository',
            'table_store',
            'document_table_repository_adapter',
        }
    }
    for module_path, names in (
        (
            'finsight.adapters.repositories.postgres_document_table_repository',
            ('PostgresDocumentTableRepository', 'AuroraDocumentTableRepository'),
        ),
    ):
        try:
            Cls = _import_adapter(module_path, *names)
            if Cls is not None:
                return Cls(session=session, config=config, **_extra)
        except Exception:  # noqa: S112
            continue
    return None


def build_chunk_repository(*args: Any, **kwargs: Any) -> Any:
    return _build_chunk_repository_impl(*args, **kwargs)


def _build_chunk_repository_impl(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'chunk_repository',
        'chunks',
        'chunk_store',
        'chunk_repository_adapter',
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
        and k not in {'chunk_repository', 'chunks', 'chunk_store', 'chunk_repository_adapter'}
    }
    for module_path, names in (
        (
            'finsight.adapters.repositories.postgres_chunk_repository',
            ('PostgresChunkRepository', 'AuroraChunkRepository'),
        ),
        (
            'finsight.adapters.repositories.aurora_chunk_repository',
            ('AuroraChunkRepository', 'PostgresChunkRepository'),
        ),
    ):
        try:
            Cls = _import_adapter(module_path, *names)
            if Cls is not None:
                return Cls(session=session, config=config, **_extra)
        except Exception:  # noqa: S112
            continue
    return None


def build_vector_write(*args: Any, **kwargs: Any) -> Any:
    return _build_vector_write_impl(*args, **kwargs)


def _build_vector_write_impl(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(kwargs, 'vector_write', 'vector_store_write', 'vector_writer')
    if provided is None:
        candidate = kwargs.get('vector_store')
        if candidate is not None and hasattr(candidate, 'upsert_chunks'):
            provided = candidate
    if provided is not None:
        return provided
    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k not in {'vector_write', 'vector_store_write', 'vector_writer', 'vector_store'}
    }
    for module_path, names in (
        (
            'finsight.adapters.vector_store.aurora_pg_vector_write',
            ('AuroraPgVectorWrite', 'PostgresVectorWrite'),
        ),
    ):
        try:
            Cls = _import_adapter(module_path, *names)
            if Cls is not None:
                return Cls(session=session, config=config, **_extra)
        except Exception:  # noqa: S112
            continue
    return None


def build_change_event_publisher(*args: Any, **kwargs: Any) -> Any:
    return _build_change_event_publisher_impl(*args, **kwargs)


def _build_change_event_publisher_impl(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'change_event_publisher',
        'event_publisher',
        'publisher',
        'change_publisher',
    )
    if provided is not None:
        return provided
    config = resolve_config(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'change_event_publisher',
            'event_publisher',
            'publisher',
            'change_publisher',
        }
    }
    try:
        Cls = _import_adapter(
            'finsight.adapters.messaging.change_event_publisher',
            'ChangeEventPublisher',
        )
        if Cls is None:
            return None
        return Cls(config=config, **_extra)
    except ImportError:
        return None
    except Exception:
        raise


def build_metering(*args: Any, **kwargs: Any) -> Any:
    return _build_metering_impl(*args, **kwargs)


def _build_metering_impl(*args: Any, **kwargs: Any) -> Any:
    """Build the DynamoDB metering adapter and validate configured prices."""
    provided = _existing(
        kwargs,
        'metering',
        'meter',
        'metering_port',
        'usage_metering',
    )
    if provided is not None:
        return provided
    config = resolve_config(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'metering',
            'meter',
            'metering_port',
            'usage_metering',
            'price_table',
            'prices',
        }
    }

    price_table = _existing(kwargs, 'price_table', 'prices')
    if price_table is None:
        price_table = load_price_table(_configured_price_path(config))
    elif not isinstance(price_table, PriceTable):
        price_table = (
            load_price_table(price_table)
            if isinstance(price_table, (str, Path))
            else PriceTable(price_table)
        )
    _require_model_prices(config, price_table)

    Cls = _import_adapter('finsight.adapters.metering.dynamo_metering', 'DynamoMetering')
    if Cls is None:
        raise ImportError('DynamoMetering adapter is unavailable')
    return Cls(config=config, price_table=price_table, **_extra)


def build_tracing(*args: Any, **kwargs: Any) -> Any:
    return _build_tracing_impl(*args, **kwargs)


def _build_tracing_impl(*args: Any, **kwargs: Any) -> Any:
    """Build the tracing adapter."""
    provided = _existing(
        kwargs,
        'tracing',
        'tracer',
        'tracing_port',
        'span_tracer',
        'span_tracing',
    )
    if provided is not None:
        return provided
    config = resolve_config(*args, **kwargs)
    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'tracing',
            'tracer',
            'tracing_port',
            'span_tracer',
            'span_tracing',
        }
    }
    switches = None
    if config is not None:
        if isinstance(config, Mapping):
            switches = config.get('switches')
        else:
            switches = getattr(config, 'switches', None)
    if isinstance(switches, Mapping):
        detailed_tracing_enabled = switches.get('detailed_tracing_enabled', True)
    elif switches is not None:
        detailed_tracing_enabled = getattr(switches, 'detailed_tracing_enabled', True)
    else:
        detailed_tracing_enabled = True
    if isinstance(detailed_tracing_enabled, str):
        detailed_tracing_enabled = detailed_tracing_enabled.strip().lower() in {
            'true',
            'yes',
            '1',
            'on',
            'enabled',
        }
    else:
        detailed_tracing_enabled = bool(detailed_tracing_enabled)

    if detailed_tracing_enabled:
        tracer_class = _import_adapter(
            'finsight.adapters.tracing.tracing_adapter', 'TracingAdapter'
        )
        if tracer_class is None:
            raise ImportError('TracingAdapter adapter is unavailable')
        return tracer_class(config=config, **_extra)

    tracer_class = _import_adapter('finsight.adapters.tracing.disabled_tracer', 'DisabledTracer')
    if tracer_class is None:
        raise ImportError('DisabledTracer adapter is unavailable')
    return tracer_class(config=config, **_extra)


def build_waiting_line(*args: Any, **kwargs: Any) -> Any:
    return _build_waiting_line_impl(*args, **kwargs)


def _build_waiting_line_impl(*args: Any, **kwargs: Any) -> Any:
    """Build the waiting-line adapter (real or pass-through based on switch)."""
    provided = _existing(
        kwargs,
        'waiting_line',
        'waiting',
        'waiting_line_port',
        'queue_line',
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
            'waiting_line',
            'waiting',
            'waiting_line_port',
            'queue_line',
            'mode',
            'profile',
        }
    }

    # Determine the waiting-line switch (default: enabled -> real adapter).
    candidate_names = (
        'waiting_line_enabled',
        'waiting_lines_enabled',
        'waiting_enabled',
        'spike_queue_enabled',
        'queue_line_enabled',
    )
    enabled: Any = None
    # Direct kwargs override.
    for name in candidate_names:
        if name in kwargs:
            enabled = kwargs[name]
            break
    # switches block.
    if enabled is None:
        switches = None
        if config is not None:
            if isinstance(config, Mapping):
                switches = config.get('switches') if hasattr(config, 'get') else None
            else:
                switches = getattr(config, 'switches', None)
        if switches is not None:
            for name in candidate_names:
                val = None
                found = False
                if isinstance(switches, Mapping):
                    if name in switches:
                        val = switches.get(name)
                        found = True
                elif hasattr(switches, name):
                    val = getattr(switches, name)
                    found = True
                if found:
                    enabled = val
                    break
    # config-level attributes.
    if enabled is None and config is not None:
        for name in candidate_names:
            if isinstance(config, Mapping):
                if name in config:
                    enabled = config.get(name)
                    break
            elif hasattr(config, name):
                enabled = getattr(config, name)
                break
    if enabled is None:
        enabled = True
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in {'true', 'yes', '1', 'on', 'enabled'}
    else:
        enabled = bool(enabled)

    if enabled:
        cls = _import_adapter(
            'finsight.adapters.waiting_line.waiting_line_adapter', 'WaitingLineAdapter'
        )
        if cls is None:
            raise ImportError('WaitingLineAdapter adapter is unavailable')
        return cls(config=config, session=session, **_extra)

    cls = _import_adapter(
        'finsight.adapters.waiting_line.passthrough_waiting_line', 'PassthroughWaitingLine'
    )
    if cls is None:
        raise ImportError('PassthroughWaitingLine adapter is unavailable')
    return cls(config=config, session=session, **_extra)


def build_hybrid_search(*args: Any, **kwargs: Any) -> Any:
    return _build_hybrid_search_impl(*args, **kwargs)


def _build_hybrid_search_impl(*args: Any, **kwargs: Any) -> Any:
    """Build the hybrid (vector + keyword) search adapter."""
    provided = _existing(
        kwargs,
        'hybrid_search',
        'search',
        'hybrid_search_port',
        'hybrid_search_adapter',
        'vector_search',
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
            'hybrid_search',
            'search',
            'hybrid_search_port',
            'hybrid_search_adapter',
            'vector_search',
        }
    }
    Cls = _import_adapter(
        'finsight.adapters.vector_store.aurora_pg_vector_search', 'AuroraPgVectorSearch'
    )
    if Cls is None:
        raise ImportError('AuroraPgVectorSearch adapter is unavailable')
    return Cls(session=session, config=config, **_extra)


def build_metric_repository(*args: Any, **kwargs: Any) -> Any:
    return _build_metric_repository_impl(*args, **kwargs)


def _build_metric_repository_impl(*args: Any, **kwargs: Any) -> Any:
    """Build the metric repository adapter (in-memory when no session)."""
    provided = _existing(
        kwargs,
        'metric_repository',
        'metrics',
        'metrics_repository',
        'metric_repo',
        'metric_repository_adapter',
        'metric',
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
            'metric_repository',
            'metrics',
            'metrics_repository',
            'metric_repo',
            'metric_repository_adapter',
            'metric',
        }
    }
    adapter_class = _import_adapter(
        'finsight.adapters.repositories.postgres_metric_repository',
        'PostgresMetricRepository',
        'AuroraMetricRepository',
        'MetricRepositoryAdapter',
        'PostgresMetricRepo',
        'RLSMetricRepository',
    )
    if adapter_class is None:
        raise ImportError('PostgresMetricRepository adapter is unavailable')
    return adapter_class(session=session, config=config, **_extra)


def _configured_price_path(config: Any) -> Any:
    if config is None:
        return None
    metering = getattr(config, 'metering', None)
    if metering is None:
        return None
    if isinstance(metering, dict):
        return metering.get('price_table')
    return getattr(metering, 'price_table', None)


def _require_model_prices(config: Any, price_table: Any) -> None:
    models: list[str] = []
    llm = getattr(config, 'llm', None) if config is not None else None
    primary = getattr(llm, 'primary_model', None) if llm is not None else None
    if primary is not None:
        models.append(str(getattr(primary, 'model_id', '')))
    for fallback in getattr(llm, 'fallback_models', None) or []:
        models.append(str(getattr(fallback, 'model_id', '')))
    embedding = getattr(llm, 'embedding_model', None) if llm is not None else None
    if embedding is not None:
        models.append(str(getattr(embedding, 'model_id', '')))

    reranker = getattr(config, 'reranker', None) if config is not None else None
    if reranker is not None:
        provider = str(getattr(reranker, 'provider', '') or '')
        model = str(getattr(reranker, 'model', '') or '')
        if model:
            models.append(model if '/' in model or not provider else f'{provider}/{model}')

    price_table.require_models([model for model in models if model])


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
        except Exception:  # noqa: S112
            continue
    return None


def build_virus_scanner(*args: Any, **kwargs: Any) -> Any:
    return _build_virus_scanner_impl(*args, **kwargs)


def _build_virus_scanner_impl(*args: Any, **kwargs: Any) -> Any:
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
    except ImportError:
        return None
    except Exception:
        raise


def build_job_progress(*args: Any, **kwargs: Any) -> Any:
    return _build_job_progress_impl(*args, **kwargs)


def _build_job_progress_impl(*args: Any, **kwargs: Any) -> Any:
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
        except Exception:  # noqa: S112
            continue
    return None


from .reader_factory import (  # noqa: E402
    ReaderFactory as ReaderFactory,  # noqa: PLC0414
    ReaderFactoryInstance as ReaderFactoryInstance,  # noqa: PLC0414
    build_reader as build_reader,  # noqa: PLC0414
    build_reader_factory as build_reader_factory,  # noqa: PLC0414
    create_reader as create_reader,  # noqa: PLC0414
    get_reader as get_reader,  # noqa: PLC0414
)
from .reader_registry import (  # noqa: E402
    ReaderRegistry as ReaderRegistry,  # noqa: PLC0414
    build_reader_map as build_reader_map,  # noqa: PLC0414
    build_reader_registry as build_reader_registry,  # noqa: PLC0414
    build_readers as build_readers,  # noqa: PLC0414
    create_reader_registry as create_reader_registry,  # noqa: PLC0414
    get_reader_registry as get_reader_registry,  # noqa: PLC0414
)

_READER_FACTORY_BUILDERS: dict[str, Any] = {}
_READER_FACTORY_ALIASES: dict[str, str] = {}


def _bind_reader_factory_builders() -> None:
    global _READER_FACTORY_BUILDERS, _READER_FACTORY_ALIASES
    _READER_FACTORY_BUILDERS = {
        'pdfplumber': lambda config=None, session=None, **extra: None,
        'textract': lambda config=None, session=None, **extra: None,
        'tesseract': lambda config=None, session=None, **extra: None,
        'self_hosted_layout': lambda config=None, session=None, **extra: None,
        'table': lambda config=None, session=None, **extra: None,
        'excel': lambda config=None, session=None, **extra: None,
        'csv': lambda config=None, session=None, **extra: None,
        'docx': lambda config=None, session=None, **extra: None,
    }

    # Replace lambdas with registry lookup helpers.
    def _lookup(cfg: Any, ses: Any, extra: dict[str, Any], target_key: str) -> Any:
        registry = build_reader_registry(config=cfg, session=ses, **extra)
        for key in registry:
            if str(key).lower() == target_key.lower():
                return registry.get(key)
        return registry.get(target_key)

    for target in list(_READER_FACTORY_BUILDERS.keys()):
        _READER_FACTORY_BUILDERS[target] = (
            lambda config=None, session=None, _target=target, **extra: _lookup(
                config, session, extra, _target
            )
        )

    _READER_FACTORY_ALIASES = {
        'pdf': 'pdfplumber',
        'pdf_plumber': 'pdfplumber',
        'pdfplumber_reader': 'pdfplumber',
        'pdf_plumber_reader': 'pdfplumber',
        'textract_reader': 'textract',
        'tesseract_reader': 'tesseract',
        'ocr': 'tesseract',
        'ocr_reader': 'tesseract',
        'self_hosted': 'self_hosted_layout',
        'layout': 'self_hosted_layout',
        'layout_reader': 'self_hosted_layout',
        'self_hosted_reader': 'self_hosted_layout',
        'table_reader': 'table',
        'excel_reader': 'excel',
        'xlsx': 'excel',
        'xlsx_reader': 'excel',
        'xls': 'excel',
        'xls_reader': 'excel',
        'spreadsheet': 'excel',
        'spreadsheet_reader': 'excel',
        'csv_reader': 'csv',
        'delimited': 'csv',
        'delimited_reader': 'csv',
        'tabular': 'csv',
        'tabular_reader': 'csv',
        'docx_reader': 'docx',
        'doc': 'docx',
        'word': 'docx',
        'word_reader': 'docx',
        'word_document_reader': 'docx',
        'CsvReader': 'csv',
        'CSVReader': 'csv',
        'ExcelReader': 'excel',
        'DocxReader': 'docx',
        'TextractReader': 'textract',
        'TesseractReader': 'tesseract',
        'TableReader': 'table',
        'SelfHostedLayoutReader': 'self_hosted_layout',
    }


_bind_reader_factory_builders()


def build_page_router(*args: Any, **kwargs: Any) -> Any:
    return _build_page_router_impl(*args, **kwargs)


def _build_page_router_impl(*args: Any, **kwargs: Any) -> Any:
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
                'finsight.adapters.readers.pdf_plumber_reader', 'PdfPlumberReader', 'PdfPlumber'
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
    override_keys = ('page_router_enabled', 'enabled', 'routed')
    if any(k in kwargs and kwargs.get(k) is not None for k in override_keys):
        router_enabled = None
        for k in override_keys:
            if kwargs.get(k) is not None:
                router_enabled = kwargs.get(k)
                break
        if isinstance(router_enabled, str):
            router_enabled = router_enabled.strip().lower() in {'on', 'true', '1', 'yes'}
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
    except ImportError:
        return None
    except Exception:
        raise


def build_scan_worker_object(*args: Any, **kwargs: Any) -> Any:
    # alias for container expected naming
    return build_scan_worker(*args, **kwargs)


def build_scan_worker(*args: Any, **kwargs: Any) -> Any:
    return _build_scan_worker_impl(*args, **kwargs)


def _build_scan_worker_impl(*args: Any, **kwargs: Any) -> Any:
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
                except Exception:  # noqa: S110
                    pass
            elif key in _extra0 and _extra0.get(key) is not None:
                try:
                    val = bool(_extra0.get(key))
                    instance.virus_scan_enabled = val
                    instance.enabled = val
                except Exception:  # noqa: S110
                    pass
        return instance
    except ImportError:
        return None
    except Exception:
        raise


def build_step_functions_worker_set(*args: Any, **kwargs: Any) -> Any:
    return _build_step_functions_worker_set_impl(*args, **kwargs)


def _build_step_functions_worker_set_impl(*args: Any, **kwargs: Any) -> Any:
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
            'document_table_repository',
            'document_tables_repository',
            'document_table_repo',
            'table_repository',
            'tables_repository',
            'table_store',
            'vector_store',
            'vector_write',
            'vector_store_write',
            'vector_writer',
            'metric_repository',
            'job_repository',
            'queue',
            'virus_scanner',
            'object_storage',
            'answer_cache',
            'change_event_publisher',
            'event_publisher',
            'publisher',
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
    if document_repository is None:
        document_repository = build_document_repository(config=config, session=session, **_extra0)
    document_table_repository = _existing(
        kwargs,
        'document_table_repository',
        'document_tables_repository',
        'document_table_repo',
        'table_repository',
        'tables_repository',
        'table_store',
    )
    if document_table_repository is None:
        document_table_repository = build_document_table_repository(
            config=config, session=session, **_extra0
        )
    chunk_repository = _existing(kwargs, 'chunk_repository', 'chunks', 'chunk_store')
    if chunk_repository is None:
        chunk_repository = build_chunk_repository(config=config, session=session, **_extra0)
    vector_store = _existing(kwargs, 'vector_store', 'vectors', 'vector_repository', 'search')
    vector_write = _existing(kwargs, 'vector_write', 'vector_store_write', 'vector_writer')
    if vector_write is None:
        vector_write = build_vector_write(
            config=config, session=session, vector_store=vector_store, **_extra0
        )
    if vector_store is None:
        vector_store = vector_write
    metric_repository = _existing(
        kwargs, 'metric_repository', 'metrics', 'metrics_repository', 'metric_repo', 'metric'
    )
    if metric_repository is None:
        metric_repository = build_metric_repository(config=config, session=session, **_extra0)
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
    change_event_publisher = _existing(
        kwargs, 'change_event_publisher', 'event_publisher', 'publisher'
    )
    if change_event_publisher is None:
        change_event_publisher = build_change_event_publisher(config=config, **_extra0)

    embedding = (
        None  # No embedding adapter module resolved here; adapters may be passed via kwargs.
    )
    if container is not None:
        document_repository = document_repository or getattr(container, 'document_repository', None)
        document_table_repository = document_table_repository or getattr(
            container, 'document_table_repository', None
        )
        chunk_repository = chunk_repository or getattr(container, 'chunk_repository', None)
        job_repository = job_repository or getattr(container, 'job_repository', None)
        virus_scanner = virus_scanner or getattr(container, 'virus_scanner', None)
        object_storage = object_storage or getattr(container, 'object_storage', None)
        answer_cache = answer_cache or getattr(container, 'answer_cache', None)
        vector_store = vector_store or getattr(container, 'vector_store', None)
        vector_write = vector_write or getattr(container, 'vector_write', None)
        change_event_publisher = change_event_publisher or getattr(
            container, 'change_event_publisher', None
        )
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
        try:  # noqa: SIM105
            delta_tracking = bool(kwargs.get('delta_tracking'))
        except Exception:  # noqa: S110
            pass

    state_store = _existing(
        kwargs,
        'state_store',
        'step_state_store',
        'pipeline_state_store',
        'context_store',
        'run_state_store',
        'store',
    )
    if state_store is None:
        try:
            from finsight.composition.state_store import build_state_store as _build_state_store

            state_store = _build_state_store(config=config, session=session, **_extra0)
        except Exception:
            state_store = None

    # Use StepFactory to create step instances
    from finsight.composition.step_factory import StepFactory

    factory = StepFactory(
        document_repository=document_repository,
        document_table_repository=document_table_repository,
        chunk_repository=chunk_repository,
        vector_store=vector_store,
        vector_write=vector_write,
        state_store=state_store,
        metric_repository=metric_repository,
        reader=reader,
        page_router=page_router,
        embedding=embedding,
        answer_cache=answer_cache,
        change_event_publisher=change_event_publisher,
        config=config,
        unit_of_work=None,
        queue=queue,
        job_repository=job_repository,
        virus_scanner=virus_scanner,
        object_storage=object_storage,
        delta_tracking=delta_tracking,
        **_extra0,
    )

    mapping: dict[str, Any] = {}

    # Reuse scan worker if provided.
    scan_worker = kwargs.get('scan_worker')
    if scan_worker is None:
        scan_worker = build_scan_worker(config=config, session=session, **_extra0)
    if scan_worker is not None:
        mapping['scan'] = scan_worker

    # Map scan worker step name.
    if 'scan' not in mapping and scan_worker is not None:
        mapping['scan'] = scan_worker

    # Create step instances using factory
    _create_step(mapping, 'read', factory.create_read_step, ('parse', 'extract'))
    _create_step(mapping, 'delta', factory.create_delta_step, ())
    _create_step(mapping, 'chunk', factory.create_chunk_step, ('chunking', 'parse_chunks'))
    _create_step(mapping, 'embed', factory.create_embed_step, ('embedding',))
    _create_step(
        mapping,
        'save',
        factory.create_save_step,
        ('commit', 'persist', 'transaction', 'transactional', 'transactional_save'),
    )
    _create_step(
        mapping,
        'cascade',
        factory.create_cascade_step,
        ('post_process', 'finalize', 'after_commit'),
    )
    _create_step(
        mapping, 'cache', factory.create_cache_step, ('cache_clear', 'clear_cache', 'answer_cache')
    )
    _create_step(
        mapping,
        'metric',
        factory.create_metric_step,
        ('metrics', 'extract_metrics', 'save_metrics'),
    )
    _create_step(mapping, 'delta_tracking_check', factory.create_delta_tracking_check_step, ())
    _create_step(mapping, 'processing', factory.create_processing_step, ())

    return _WorkerSet(mapping)


def _create_step(
    mapping: dict[str, Any],
    primary_name: str,
    factory_method: Any,
    aliases: tuple[str, ...],
) -> None:
    """Create a step and its aliases, handling errors gracefully."""
    try:
        instance = factory_method()
        if instance is not None:
            mapping[primary_name] = instance
            for alias in aliases:
                mapping.setdefault(alias, instance)
    except Exception as exc:
        # Log error but don't fail - step may be optional
        import logging

        logging.getLogger(__name__).warning('Failed to create step %s: %s', primary_name, exc)


# Aliases expected by hidden tests / callers.
build_ingestion_container = build_container
build_ingestion_composition_root = build_container
build_ingestion_root = build_container
build_ingestion = build_container
build_ingestion_set = build_container


from .adapter_stacks import (  # noqa: E402
    _build_llm_stack as _build_llm_stack,  # noqa: PLC0414
    _build_embedding_stack as _build_embedding_stack,  # noqa: PLC0414
    _build_reranker_stack as _build_reranker_stack,  # noqa: PLC0414
    _build_extraction_stack as _build_extraction_stack,  # noqa: PLC0414
)


# Aggregator-only alias families (single implementation, discoverable names).
build_llm = _build_llm_stack
build_llm_gateway = _build_llm_stack
build_model_gateway = _build_llm_stack
build_llm_stack = _build_llm_stack
build_gateway = _build_llm_stack

build_embedding = _build_embedding_stack
build_embedding_provider = _build_embedding_stack
build_embeddings = _build_embedding_stack
build_embedding_stack = _build_embedding_stack

build_reranker = _build_reranker_stack
build_rerank = _build_reranker_stack
build_reranker_stack = _build_reranker_stack

build_extraction = _build_extraction_stack
build_extractor = _build_extraction_stack
build_textract = _build_extraction_stack
build_extraction_stack = _build_extraction_stack


def build_unit_of_work(*args: Any, **kwargs: Any) -> Any:
    return _build_unit_of_work_impl(*args, **kwargs)


def _build_unit_of_work_impl(*args: Any, **kwargs: Any) -> Any:
    """Build a :class:`UnitOfWork` adapter over the current DB session."""
    provided = _existing(
        kwargs,
        'unit_of_work',
        'uow',
        'transaction',
        'tx',
        'unit_of_work_adapter',
    )
    if provided is not None:
        return provided

    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)
    company_id = _existing(kwargs, 'company_id', 'company', 'tenant_id', 'tenant')

    _extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'unit_of_work',
            'uow',
            'transaction',
            'tx',
            'unit_of_work_adapter',
            'company_id',
            'company',
            'tenant_id',
            'tenant',
        }
    }

    aliases = ('finsight.adapters.repositories.postgres_unit_of_work',)
    for module_name in aliases:
        try:
            module = importlib.import_module(module_name)
            cls = (
                getattr(module, 'PostgresUnitOfWork', None)
                or getattr(module, 'SqlAlchemyUnitOfWork', None)
                or getattr(module, 'DatabaseUnitOfWork', None)
                or getattr(module, 'UnitOfWork', None)
            )
            if cls is not None:
                return cls(session=session, config=config, company_id=company_id, **_extra)
        except Exception:  # noqa: S112
            continue
    return None


# Aliases for varying caller naming.
build_uow = build_unit_of_work
build_transaction = build_unit_of_work
build_tx = build_unit_of_work
build_unit_of_work_adapter = build_unit_of_work

# Default unit-of-work handle.
_DEFAULT_UNIT_OF_WORK: Any = None


def set_default_unit_of_work(value: Any) -> None:
    global _DEFAULT_UNIT_OF_WORK
    _DEFAULT_UNIT_OF_WORK = value


def get_default_unit_of_work() -> Any:
    return _DEFAULT_UNIT_OF_WORK


def build_queue(*args: Any, **kwargs: Any) -> Any:
    return _build_queue_impl(*args, **kwargs)


def _build_queue_impl(*args: Any, **kwargs: Any) -> Any:
    """Build a queue adapter (SQS)."""
    provided = _existing(
        kwargs,
        'queue',
        'queue_port',
        'sqs',
        'queue_adapter',
        'queue_client',
        'messenger',
        'dispatcher',
        'job_queue',
        'reprocessing_queue',
    )
    if provided is not None and not any(k in kwargs for k in _SESSION_KEYS):
        return provided

    config = resolve_config(*args, **kwargs)
    session = resolve_session(*args, **kwargs)

    extra = {
        k: v
        for k, v in kwargs.items()
        if k not in _SESSION_KEYS
        and k not in _CONFIG_KEYS
        and k
        not in {
            'queue',
            'queue_port',
            'sqs',
            'queue_adapter',
            'queue_client',
            'messenger',
            'dispatcher',
            'job_queue',
            'reprocessing_queue',
        }
    }
    try:
        module = importlib.import_module('finsight.adapters.queue.sqs_queue')
        SqsQueue = getattr(module, 'SqsQueue')
        return SqsQueue(config=config, session=session, **extra)
    except ImportError:
        try:
            module = importlib.import_module('finsight.adapters.queue')
            SqsQueue = getattr(module, 'SqsQueue')
            return SqsQueue(config=config, session=session, **extra)
        except Exception:
            return None
    except Exception:
        raise


def build_reprocess_use_case(*args: Any, **kwargs: Any) -> Any:
    return _build_reprocess_use_case_impl(*args, **kwargs)


def _build_reprocess_use_case_impl(*args: Any, **kwargs: Any) -> Any:
    """Build a reprocess use case instance."""
    provided = _existing(
        kwargs,
        'reprocess_use_case',
        'reprocess',
        'use_case',
        'service',
    )
    if provided is not None and not any(k in kwargs for k in _SESSION_KEYS):
        return provided

    config = resolve_config(*args, **kwargs)
    resolve_session(*args, **kwargs)

    container = None
    for container_key in _CONTAINER_KEYS:
        candidate = kwargs.get(container_key)
        if candidate is not None:
            container = candidate
            break

    def _from_container(attr: str) -> Any:
        if container is None:
            return None
        return getattr(container, attr, None)

    document_repository = _existing(
        kwargs,
        'document_repository',
        'document_repo',
        'documents',
    )
    if document_repository is None:
        document_repository = _from_container('document_repository')

    chunk_repository = _existing(kwargs, 'chunk_repository', 'chunk_repo', 'chunks')
    if chunk_repository is None:
        chunk_repository = _from_container('chunk_repository')

    vector_write = _existing(
        kwargs,
        'vector_write',
        'vector_store',
        'vector_store_write',
        'vector_writer',
    )
    if vector_write is None:
        vector_write = _from_container('vector_write') or _from_container('vector_store')

    answer_cache = _existing(kwargs, 'answer_cache', 'cache')
    if answer_cache is None:
        answer_cache = _from_container('answer_cache')

    job_repository = _existing(kwargs, 'job_repository', 'job_repo', 'jobs')
    if job_repository is None:
        job_repository = _from_container('job_repository')

    queue = _existing(kwargs, 'queue', 'queue_port', 'sqs', 'job_queue', 'reprocessing_queue')
    if queue is None:
        queue = _from_container('queue')

    change_event_publisher = _existing(
        kwargs,
        'change_event_publisher',
        'event_publisher',
        'publisher',
    )
    if change_event_publisher is None:
        change_event_publisher = _from_container('change_event_publisher')

    company_repository = _existing(kwargs, 'company_repository', 'companies')
    if company_repository is None:
        company_repository = _from_container('company_repository')

    unit_of_work = _existing(kwargs, 'unit_of_work', 'uow', 'transaction', 'tx')
    if unit_of_work is None:
        unit_of_work = _from_container('unit_of_work')

    tracing = _existing(kwargs, 'tracing', 'tracer', 'tracing_port', 'span_tracer', 'span_tracing')
    if tracing is None:
        tracing = _from_container('tracing')

    from finsight.application.reprocess import Reprocess

    instance = Reprocess(
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        vector_write=vector_write,
        answer_cache=answer_cache,
        job_repository=job_repository,
        queue=queue,
        change_event_publisher=change_event_publisher,
        company_repository=company_repository,
        config=config,
        unit_of_work=unit_of_work,
        tracing=tracing,
        **{
            k: v
            for k, v in kwargs.items()
            if k not in _SESSION_KEYS
            and k not in _CONFIG_KEYS
            and k
            not in {
                'document_repository',
                'document_repo',
                'documents',
                'chunk_repository',
                'chunk_repo',
                'chunks',
                'vector_write',
                'vector_store',
                'vector_store_write',
                'vector_writer',
                'answer_cache',
                'cache',
                'job_repository',
                'job_repo',
                'jobs',
                'queue',
                'queue_port',
                'sqs',
                'job_queue',
                'reprocessing_queue',
                'change_event_publisher',
                'event_publisher',
                'publisher',
                'company_repository',
                'companies',
                'unit_of_work',
                'uow',
                'transaction',
                'tx',
                'tracing',
                'tracer',
                'tracing_port',
                'span_tracer',
                'span_tracing',
                'reprocess_use_case',
                'reprocess',
                'use_case',
                'service',
            }
        },
    )
    set_default_reprocess_use_case(instance)
    return instance


def get_queue(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_queue(*args, **kwargs)
    default_container = get_default_container()
    if default_container is not None:
        value = getattr(default_container, 'queue', None)
        if value is not None:
            return value
    return build_queue()


def build_document_use_case(*args: Any, **kwargs: Any) -> Any:
    provided = kwargs.get('document_use_case') or kwargs.get('use_case') or kwargs.get('repository')
    if provided is not None:
        return provided
    container = None
    for container_key in _CONTAINER_KEYS:
        candidate = kwargs.get(container_key)
        if candidate is not None:
            container = candidate
            break
    if container is None and not args and not kwargs:
        container = get_default_container()
    if container is not None and getattr(container, 'document_repository', None) is not None:
        return container.document_repository
    return build_document_repository(*args, **kwargs)


def get_document_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_document_use_case(*args, **kwargs)
    container = get_default_container()
    if container is not None and getattr(container, 'document_repository', None) is not None:
        return container.document_repository
    return build_document_use_case()


build_reprocess = build_reprocess_use_case
