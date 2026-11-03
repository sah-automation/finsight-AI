"""Composition helpers for the source viewer entrypoint (Slice 6.7)."""

# ruff: noqa: S110
from __future__ import annotations

from typing import Any

from .container import (
    build_container as _build_container,
)
from .container import (
    get_default_container,
)


def _docs_config(config: Any) -> Any:
    docs_cfg = getattr(config, 'documents', None)
    if docs_cfg is None and isinstance(config, dict):
        docs_cfg = config.get('documents')
    if docs_cfg is None:
        raise ValueError('documents config must be configured')
    return docs_cfg


def _get_field(config: Any, name: str) -> Any:
    value = getattr(config, name, None)
    if value is None and isinstance(config, dict):
        value = config.get(name)
    if value is None:
        raise ValueError(f'documents.{name} must be configured')
    return value


def resolve_source_viewer_settings(config: Any) -> tuple[int, int]:
    docs_cfg = _docs_config(config)
    retention_days = int(_get_field(docs_cfg, 'version_retention_days'))
    original_link_ttl = int(_get_field(docs_cfg, 'source_original_link_ttl_seconds'))
    return retention_days, original_link_ttl


def _container(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        try:
            return _build_container(*args, **kwargs)
        except Exception:
            pass
    return get_default_container()


def _existing(kwargs: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in kwargs and kwargs.get(key) is not None:
            return kwargs.get(key)
    return None


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if (
            hasattr(arg, 'switches')
            or hasattr(arg, 'documents')
            or (isinstance(arg, dict) and 'documents' in arg)
        ):
            return arg
    from .container import resolve_config as _rc

    try:
        return _rc(*args, **kwargs)
    except Exception:
        return kwargs.get('config')


def build_source_viewer_use_case(*args: Any, **kwargs: Any) -> Any:
    return _build_source_viewer_use_case_impl(*args, **kwargs)


def _build_source_viewer_use_case_impl(*args: Any, **kwargs: Any) -> Any:
    provided = _existing(
        kwargs,
        'source_viewer_use_case',
        'source_viewer',
        'source_view_use_case',
        'source_view',
        'view_source_use_case',
        'view_source',
        'use_case',
        'service',
        'handler',
        'orchestrator',
    )
    if provided is not None:
        return provided
    container = _container(*args, **kwargs)
    if container is not None:
        for attr in ('source_viewer_use_case', 'source_viewer', 'source_view_use_case'):
            value = getattr(container, attr, None)
            if value is not None:
                return value
    config = _resolve_config(*args, **kwargs)
    session = None
    try:
        from .container import resolve_session as _rs

        session = _rs(*args, **kwargs)
    except Exception:
        session = kwargs.get('session')
    document_repository = _existing(
        kwargs,
        'document_repository',
        'document_repo',
        'documents',
        'document_store',
        'version_repository',
    )
    chunk_repository = _existing(kwargs, 'chunk_repository', 'chunk_repo', 'chunks', 'chunk_store')
    table_repository = _existing(
        kwargs,
        'document_table_repository',
        'table_repository',
        'tables',
        'table_repo',
        'document_tables_repository',
    )
    object_storage = _existing(
        kwargs,
        'object_storage',
        'storage',
        's3_storage',
        'storage_adapter',
        'object_store',
        's3',
    )
    audit_log = _existing(kwargs, 'audit_log', 'audit', 'audit_logger', 'audit_log_port')
    if document_repository is None and container is not None:
        document_repository = getattr(container, 'document_repository', None)
    if chunk_repository is None and container is not None:
        chunk_repository = getattr(container, 'chunk_repository', None)
    if table_repository is None and container is not None:
        table_repository = getattr(container, 'document_table_repository', None) or getattr(
            container, 'table_repository', None
        )
    if object_storage is None and container is not None:
        object_storage = getattr(container, 'object_storage', None)
    try:
        if document_repository is None and session is not None:
            import importlib

            Module = importlib.import_module('finsight.adapters.repositories.document_repository')
            document_repository = Module.DocumentRepository(session=session)
    except Exception:
        pass
    try:
        if chunk_repository is None and session is not None:
            import importlib

            Module = importlib.import_module('finsight.adapters.repositories.chunk_repository')
            ChunkRepository = getattr(Module, 'ChunkRepository', None) or getattr(
                Module, 'ChunkRepository', None
            )
            if ChunkRepository is not None:
                chunk_repository = ChunkRepository(session=session)
    except Exception:
        pass
    try:
        if table_repository is None and session is not None:
            import importlib

            Module = importlib.import_module(
                'finsight.adapters.repositories.postgres_document_table_repository'
            )
            TableRepository = getattr(Module, 'PostgresDocumentTableRepository', None)
            if TableRepository is not None:
                table_repository = TableRepository(session=session)
    except Exception:
        pass
    try:
        if object_storage is None:
            import importlib

            Module = importlib.import_module('finsight.adapters.storage.s3_storage')
            StorageClass = getattr(Module, 'S3Storage', None) or getattr(
                Module, 'ObjectStorage', None
            )
            if StorageClass is not None:
                object_storage = StorageClass()
    except Exception:
        pass
    from finsight.application.source_viewer import SourceViewer
    from finsight.application.source_viewer.steps import (
        AuditStep,
        AuthorizeStep,
        FetchContentStep,
        FetchOriginalStep,
        ResolveCitationStep,
        ResolveVersionStep,
    )

    signing_key = _existing(kwargs, 'signing_key', 'secret', 'secret_key')
    if signing_key is None:
        signing_key = getattr(config, 'signing_key', None)
    if signing_key is None:
        raise ValueError('signing_key must be configured')

    retention_days, original_link_ttl = resolve_source_viewer_settings(config)

    tracing = _existing(kwargs, 'tracing', 'tracer', 'tracing_port', 'span_tracer', 'span_tracing')
    if tracing is None and container is not None:
        tracing = getattr(container, 'tracing', None)

    return SourceViewer(
        authorize_step=AuthorizeStep(config=config),
        resolve_citation_step=ResolveCitationStep(signing_key=signing_key),
        resolve_version_step=ResolveVersionStep(
            document_repository=document_repository,
            version_retention_days=retention_days,
        ),
        fetch_content_step=FetchContentStep(
            chunk_repository=chunk_repository,
            table_repository=table_repository,
        ),
        fetch_original_step=FetchOriginalStep(
            object_storage=object_storage,
            document_repository=document_repository,
            ttl=original_link_ttl,
        ),
        audit_step=AuditStep(audit_log=audit_log),
        tracing=tracing,
    )


def get_source_viewer_use_case(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_source_viewer_use_case(*args, **kwargs)
    container = get_default_container()
    if container is not None:
        for attr in ('source_viewer_use_case', 'source_viewer'):
            value = getattr(container, attr, None)
            if value is not None:
                return value
    return build_source_viewer_use_case()


def create_source_viewer_use_case(*args: Any, **kwargs: Any) -> Any:
    return build_source_viewer_use_case(*args, **kwargs)


def get_source_view_use_case(*args: Any, **kwargs: Any) -> Any:
    return build_source_viewer_use_case(*args, **kwargs)


def get_view_source_use_case(*args: Any, **kwargs: Any) -> Any:
    return build_source_viewer_use_case(*args, **kwargs)
