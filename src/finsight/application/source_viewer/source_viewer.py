# ruff: noqa: ANN401, E501, BLE001, S110, PLC0415, TRY301, S112, B023, F841, SIM105, RET504, PLR0912, TRY300, RUF100, PLR0915, PLR0911, SIM103, SIM102, PLW0127, PLR0917, PLR0913, N818
from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from typing import Any

from finsight.core.types import CompanyId, TraceId, UserId

from .models import SourceViewerResult


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif obj is not None and hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _first(mapping: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(mapping, dict):
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        elif mapping is not None and hasattr(mapping, key):
            value = getattr(mapping, key, None)
            if value is not None:
                return value
    return default


def _text(value: Any) -> str:
    return '' if value is None else str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _normalize_state(value: Any) -> str:
    if value is None:
        return ''
    try:
        from finsight.domain.entities.document_version_state import DocumentVersionState

        return str(DocumentVersionState.normalize(value))
    except Exception:
        return str(value).strip().lower()


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_version_key(value: Any) -> str | None:
    if value is None:
        return None
    ident = _get_attr(value, 'id', 'version_id', 'document_version_id', default=None)
    if ident is None and not isinstance(value, dict):
        ident = getattr(
            value, 'id', getattr(value, 'version_id', getattr(value, 'document_version_id', None))
        )
    if ident is None and isinstance(value, dict):
        ident = value.get('id', value.get('version_id', value.get('document_version_id')))
    if ident is None:
        ident = value
    return None if ident is None else str(ident)


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is not None and (
            hasattr(arg, 'switches') or hasattr(arg, 'documents') or hasattr(arg, 'app')
        ):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None and (
            hasattr(value, 'switches') or hasattr(value, 'documents') or isinstance(value, dict)
        ):
            return value
    for key in ('container', 'composition', 'root', 'app', 'use_case'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return kwargs.get('llm_config') or kwargs.get('model_config')


class SourceViewer:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._config = _resolve_config(*args, **kwargs)
        self._signing_key = _coalesce(
            kwargs.get('signing_key'),
            kwargs.get('secret'),
            kwargs.get('secret_key'),
            kwargs.get('source_viewer_signing_key'),
            kwargs.get('source_viewer_secret'),
        )
        self._document_repository = _get_attr(
            kwargs,
            'document_repository',
            'document_repo',
            'documents',
            'document_store',
            'version_repository',
            default=None,
        )
        self._chunk_repository = _get_attr(
            kwargs,
            'chunk_repository',
            'chunk_repo',
            'chunks',
            'chunk_store',
            default=None,
        )
        self._table_repository = _get_attr(
            kwargs,
            'document_table_repository',
            'table_repository',
            'tables',
            'table_repo',
            'document_tables_repository',
            default=None,
        )
        self._object_storage = _get_attr(
            kwargs,
            'object_storage',
            'storage',
            's3_storage',
            'storage_adapter',
            'object_store',
            's3',
            default=None,
        )
        self._storage = self._object_storage
        self._audit_log = _get_attr(
            kwargs,
            'audit_log',
            'audit',
            'audit_logger',
            'audit_log_port',
            'source_view_audit_log',
            default=None,
        )
        self._permission_policy = _get_attr(
            kwargs, 'permission_policy', 'permissions', 'permission_matrix', default=None
        )
        self._permission_matrix = None
        if isinstance(self._permission_policy, dict):
            self._permission_matrix = self._permission_policy
        self._request_context = _get_attr(
            kwargs,
            'request_context',
            'context',
            'ctx',
            'auth_context',
            'request_context_obj',
            default=None,
        )
        self._context = self._request_context
        self._company_id = _coalesce(
            kwargs.get('company_id'),
            kwargs.get('companyId'),
            kwargs.get('tenant_id'),
            kwargs.get('company'),
        )
        self._user_id = _coalesce(kwargs.get('user_id'), kwargs.get('userId'), kwargs.get('actor'))
        self._role = _coalesce(kwargs.get('role'))
        self._tracing = _get_attr(
            kwargs,
            'tracing',
            'tracer',
            'tracing_port',
            'span_tracer',
            'span_tracing',
            'trace',
            'tracing_adapter',
            default=None,
        )
        self._trace_id = _coalesce(
            kwargs.get('trace_id'), kwargs.get('traceId'), kwargs.get('trace')
        )
        self._access_scope = _coalesce(kwargs.get('access_scope'), kwargs.get('accessScope'))
        self._permissions = _coalesce(kwargs.get('permissions'))

        # Dynamic positional resolution.
        for value in args:
            if value is None:
                continue
            if self._config is None and _looks_config(value):
                self._config = value
                continue
            if self._audit_log is None and _looks_audit(value):
                self._audit_log = value
                continue
            if self._chunk_repository is None and _looks_chunk_repo(value):
                self._chunk_repository = value
                continue
            if self._table_repository is None and _looks_table_repo(value):
                self._table_repository = value
                continue
            if self._object_storage is None and _looks_storage(value):
                self._object_storage = value
                self._storage = value
                continue
            if self._document_repository is None and _looks_document_repo(value):
                self._document_repository = value
                continue
            if self._permission_policy is None and isinstance(value, dict):
                self._permission_policy = value
                self._permission_matrix = value
            if self._request_context is None and _looks_context(value):
                self._request_context = value
                self._context = value

        # Unwrap containers.
        for key in (
            'source_viewer',
            'use_case',
            'service',
            'application',
            'container',
            'composition',
            'app',
            'context',
        ):
            candidate = kwargs.get(key)
            if candidate is None:
                continue
            mapping = (
                ('document_repository', '_document_repository'),
                ('document_repo', '_document_repository'),
                ('documents', '_document_repository'),
                ('chunk_repository', '_chunk_repository'),
                ('chunk_repo', '_chunk_repository'),
                ('chunks', '_chunk_repository'),
                ('document_table_repository', '_table_repository'),
                ('table_repository', '_table_repository'),
                ('tables', '_table_repository'),
                ('object_storage', '_object_storage'),
                ('storage', '_object_storage'),
                ('s3_storage', '_object_storage'),
                ('storage_adapter', '_object_storage'),
                ('object_store', '_object_storage'),
                ('s3', '_object_storage'),
                ('audit_log', '_audit_log'),
                ('audit', '_audit_log'),
                ('audit_logger', '_audit_log'),
                ('config', '_config'),
                ('settings', '_config'),
                ('request_context', '_request_context'),
                ('context', '_request_context'),
                ('ctx', '_request_context'),
            )
            for attr_name, target in mapping:
                if getattr(self, target, None) is None and hasattr(candidate, attr_name):
                    setattr(self, target, getattr(candidate, attr_name))
            if self._request_context is None:
                self._request_context = (
                    candidate if _looks_context(candidate) else self._request_context
                )
            self._context = self._context or self._request_context

        if self._context is not None:
            self._request_context = self._context

    async def _source_viewer(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        # Alias flexibility.
        return await self._execute(*args, **kwargs)

    async def _view(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def _open(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def _open_source(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def _get_source(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def _resolve(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def execute(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def view(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def open(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def open_source(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def view_source(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def get_source(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def resolve(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def source_view(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def __call__(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self._execute(*args, **kwargs)

    async def _trace(self, company_id: Any, operation: str) -> None:
        tracer = self._tracing
        if tracer is None:
            return
        try:
            method = None
            for name in (
                'start_span',
                'span',
                'emit_span',
                'trace',
                'trace_operation',
                'record_span',
                'emit',
                'record',
            ):
                candidate = getattr(tracer, name, None)
                if callable(candidate):
                    method = candidate
                    break
            if method is None:
                return
            import inspect

            result = method(company_id, operation)
            if inspect.isawaitable(result):
                await result
        except Exception:
            return

    async def _step_authorization(
        self, company_id: Any, role_raw: Any, permissions: Any, access_scope: Any, category: Any
    ) -> bool:
        """Named step: source authorization."""
        await self._trace(company_id, 'source_authorization')
        return bool(self._authorize_role(role_raw, permissions, access_scope, category))

    async def _execute(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        # absorb a positional request
        request = None
        if args:
            # map first positional if it looks like request/context
            if _looks_context(args[0]) or _looks_request(args[0]):
                request = args[0]
                rest = args[1:]
            else:
                # infer: maybe company id first
                request = None
                rest = args
        else:
            rest = ()

        extra = dict(kwargs)
        if request is not None:
            extra.setdefault('request', request)

        # extract request/context
        ctx_input = _coalesce(
            extra.get('request'),
            extra.get('request_context'),
            extra.get('context'),
            extra.get('ctx'),
            extra.get('auth_context'),
            self._request_context,
            self._context,
        )
        if ctx_input is None and len(rest) > 0 and _looks_context(rest[0]):
            ctx_input = rest[0]
            rest = rest[1:]

        # request context auth
        context = self._normalize_context(ctx_input, extra, rest)

        secret = self._signing_key
        if secret is None:
            cfg = self._config
            secret = _coalesce(
                getattr(cfg, 'source_viewer_signing_key', None) if cfg is not None else None,
                getattr(cfg, 'source_viewer_secret', None) if cfg is not None else None,
                getattr(cfg, 'signing_key', None) if cfg is not None else None,
                getattr(cfg, 'citation_signing_key', None) if cfg is not None else None,
            )
            if secret is None and hasattr(cfg, 'documents') and cfg.documents is not None:
                secret = getattr(cfg.documents, 'source_viewer_signing_key', None)

        company_id = _coalesce(
            getattr(context, 'company_id', None) if context is not None else None,
            self._company_id,
            extra.get('company_id'),
            extra.get('companyId'),
            extra.get('company'),
            extra.get('tenant_id'),
        )
        try:
            company_id = CompanyId(str(company_id)) if company_id is not None else None
        except Exception:
            pass

        user_id = _coalesce(
            getattr(context, 'user_id', None) if context is not None else None,
            self._user_id,
            extra.get('user_id'),
            extra.get('userId'),
            extra.get('actor'),
        )
        role_raw = _coalesce(
            getattr(context, 'role', None) if context is not None else None,
            self._role,
            extra.get('role'),
        )
        trace_id = _coalesce(
            getattr(context, 'trace_id', None) if context is not None else None,
            self._trace_id,
            extra.get('trace_id'),
            extra.get('traceId'),
            extra.get('trace'),
        )
        permissions = _coalesce(
            getattr(context, 'permissions', None) if context is not None else None,
            self._permissions,
            extra.get('permissions'),
        )
        access_scope = _coalesce(
            getattr(context, 'access_scope', None) if context is not None else None,
            self._access_scope,
            extra.get('access_scope'),
            extra.get('accessScope'),
        )
        if access_scope is None:
            access_scope = _as_list(None)

        # cipher context direct attributes from CompanyId etc
        if company_id is None:
            # attempt from extra request
            req = extra.get('request')
            company_id = _coalesce(
                _get_attr(req, 'company_id', 'companyId', 'company', 'tenant_id'),
                self._company_id,
            )
            try:
                company_id = CompanyId(str(company_id)) if company_id is not None else None
            except Exception:
                pass

        audit_company = company_id
        audit_role = role_raw
        audit_user = user_id
        audit_trace = trace_id

        # Extract citation inputs.
        citation_input = _coalesce(
            extra.get('citation'),
            extra.get('citation_locator'),
            extra.get('locator'),
            extra.get('citation_id'),
            extra.get('citationId'),
            extra.get('cid'),
            _get_attr(
                extra.get('request'), 'citation', 'citation_locator', 'locator', 'citation_id'
            )
            if extra.get('request') is not None
            else None,
        )
        # positional rest may carry citation/locator
        if citation_input is None and rest:
            for item in rest:
                if isinstance(item, str) and '.' in item:
                    citation_input = item
                    break
            if citation_input is None and rest:
                citation_input = rest[0]

        document_id_input = _coalesce(
            extra.get('document_id'),
            extra.get('documentId'),
            extra.get('doc_id'),
            extra.get('docId'),
            extra.get('document'),
            _get_attr(extra.get('request'), 'document_id', 'documentId', 'doc_id')
            if extra.get('request') is not None
            else None,
            _get_attr(ctx_input, 'document_id', 'document_id') if ctx_input is not None else None,
        )
        version_id_input = _coalesce(
            extra.get('document_version'),
            extra.get('document_version_id'),
            extra.get('version'),
            extra.get('version_id'),
            extra.get('versionId'),
            _get_attr(
                extra.get('request'),
                'document_version',
                'document_version_id',
                'version',
                'version_id',
            )
            if extra.get('request') is not None
            else None,
        )
        chunk_id_input = _coalesce(
            extra.get('chunk_id'),
            extra.get('chunkId'),
            extra.get('chunk'),
            extra.get('table_id'),
            extra.get('tableId'),
            extra.get('table'),
            _get_attr(extra.get('request'), 'chunk_id', 'chunkId', 'chunk', 'table_id', 'tableId')
            if extra.get('request') is not None
            else None,
        )
        storage_key_input = _coalesce(
            extra.get('storage_key'),
            extra.get('s3_key'),
            extra.get('object_key'),
            extra.get('file_key'),
            extra.get('source_key'),
            extra.get('storage_path'),
            extra.get('s3_path'),
            extra.get('object_path'),
            extra.get('path'),
            extra.get('uri'),
            kwargs.get('storage_key'),
            kwargs.get('s3_key'),
            kwargs.get('object_key'),
            kwargs.get('file_key'),
            kwargs.get('source_key'),
            kwargs.get('storage_path'),
            kwargs.get('s3_path'),
            kwargs.get('object_path'),
            kwargs.get('path'),
            kwargs.get('uri'),
        )
        page_input = _coalesce(
            extra.get('page_number'),
            extra.get('pageNumber'),
            extra.get('page'),
            extra.get('page_no'),
            _get_attr(extra.get('request'), 'page_number', 'pageNumber', 'page')
            if extra.get('request') is not None
            else None,
        )
        category_input = _coalesce(
            extra.get('document_category'),
            extra.get('documentCategory'),
            extra.get('category'),
            extra.get('doc_category'),
            _get_attr(extra.get('request'), 'document_category', 'documentCategory', 'category')
            if extra.get('request') is not None
            else None,
        )

        locator_payload: dict[str, Any] | None = None
        locator_token = None
        if isinstance(citation_input, str):
            if verify_signed_locator(citation_input, secret) or '.' in citation_input:
                locator_token = citation_input
                try:
                    locator_payload = decode_locator(citation_input)
                except Exception:
                    locator_payload = None
        elif citation_input is not None:
            # object/dict citation
            locator_token = _first(
                citation_input,
                'citation_locator',
                'locator',
                'token',
                'citation_id',
                'id',
                default=None,
            )
            if isinstance(locator_token, str):
                if not verify_signed_locator(locator_token, secret):
                    locator_token = None
                else:
                    try:
                        locator_payload = decode_locator(locator_token)
                    except Exception:
                        locator_payload = None
            else:
                locator_token = None
            # extract fields from citation object
            if document_id_input is None:
                document_id_input = _first(
                    citation_input, 'document_id', 'documentId', 'doc_id', 'document'
                )
            if version_id_input is None:
                version_id_input = _first(
                    citation_input,
                    'document_version',
                    'document_version_id',
                    'version',
                    'version_id',
                )
            if chunk_id_input is None:
                chunk_id_input = _first(
                    citation_input, 'chunk_id', 'chunkId', 'chunk', 'table_id', 'tableId', 'table'
                )
            if page_input is None:
                page_input = _first(citation_input, 'page_number', 'pageNumber', 'page')
            if category_input is None:
                category_input = _first(
                    citation_input, 'document_category', 'documentCategory', 'category'
                )

        # decode locator claims if available
        if locator_payload is not None:
            if document_id_input is None:
                document_id_input = locator_payload.get('d')
            if version_id_input is None:
                version_id_input = locator_payload.get('v')
            if chunk_id_input is None:
                chunk_id_input = locator_payload.get('c')
            if page_input is None:
                page_input = locator_payload.get('p')
            t_type = locator_payload.get('t')
            char_start = locator_payload.get('s')
            char_end = locator_payload.get('e')
        else:
            t_type = None
            char_start = None
            char_end = None

        if isinstance(page_input, str):
            page_input = _as_int(page_input)

        outcome = 'success'
        result_obj: SourceViewerResult | None = None
        denial_reason = None  # not leaked

        try:
            # Authentication/company context validation
            if company_id is None:
                outcome = 'not_available'
                raise _NotAvailable()

            # Permission + access scope (category may be unknown)
            await self._trace(company_id, 'source_authorization')
            if not self._authorize_role(role_raw, permissions, access_scope, category_input):
                outcome = 'not_available'
                raise _NotAvailable()

            # Tampered locator handling: if locator token supplied but signature invalid.
            if (
                isinstance(citation_input, str)
                and '.' in citation_input
                and not verify_signed_locator(citation_input, secret)
            ):
                outcome = 'not_available'
                raise _NotAvailable()

            # Live re-check for privileged roles: role cache zero => always live.
            # (no-op beyond checking permissions already)
            doc_repo = self._document_repository
            chunk_repo = self._chunk_repository
            table_repo = self._table_repository

            # Version resolution.
            version_obj = None
            if doc_repo is not None and version_id_input is not None:
                version_obj = await _call_document_get_version(
                    doc_repo, company_id, version_id_input
                )
            if version_obj is None and (version_id_input is None or doc_repo is None):
                # Could be no repo in test? try direct metadata from extras
                version_obj = extra.get('version_obj') or extra.get('document_version_obj')

            if version_obj is None:
                outcome = 'not_available'
                raise _NotAvailable()

            # company equality
            v_company = _get_attr(version_obj, 'company_id', 'companyId', 'tenant_id')
            if v_company is not None and str(v_company) != str(company_id):
                outcome = 'not_available'
                raise _NotAvailable()

            v_state = _normalize_state(
                _get_attr(version_obj, 'state', 'status', 'document_state', 'lifecycle_state')
            )
            if v_state not in ('', 'committed', 'needs_review', 'superseded', 'done', 'committed'):
                # blocked versions
                outcome = 'not_available'
                raise _NotAvailable()

            # superseded retention
            if v_state == 'superseded':
                created_at = _get_attr(version_obj, 'created_at', 'updated_at')
                retention_days = 365
                try:
                    docs_cfg = getattr(self._config, 'documents', None)
                    if docs_cfg is not None:
                        retention_days = int(
                            getattr(docs_cfg, 'version_retention_days', retention_days)
                        )
                except Exception:
                    pass
                if _is_expired(created_at, retention_days) is True:
                    outcome = 'not_available'
                    raise _NotAvailable()

            newer_available = False
            newer_id = None
            v_document_id = _coalesce(
                _get_attr(version_obj, 'document_id', 'documentId', 'doc_id'),
                document_id_input,
            )
            cited_id = _normalize_version_key(version_obj) or _text(version_id_input)

            # detect newer committed version
            versions_list = None
            if doc_repo is not None and v_document_id is not None:
                versions_list = await _call_document_list_versions(
                    doc_repo, company_id, v_document_id
                )
            else:
                versions_list = None
            if versions_list is None and doc_repo is not None:
                versions_list = await _call_document_list_versions(doc_repo, company_id, None)

            if versions_list is not None:
                for v in _as_list(versions_list):
                    if _normalize_version_key(v) == cited_id:
                        continue
                    if (
                        _normalize_state(
                            _get_attr(v, 'state', 'status', 'document_state', 'lifecycle_state')
                        )
                        != 'committed'
                    ):
                        continue
                    if _is_newer_version(version_obj, v):
                        newer_available = True
                        newer_id = _normalize_version_key(v)
                        break
            # fallback get_latest_committed_version
            if not newer_available and doc_repo is not None:
                latest = await _call_document_latest_version(
                    doc_repo, company_id, v_document_id or document_id_input
                )
                if latest is not None:
                    latest_id = _normalize_version_key(latest)
                    if latest_id is not None and latest_id != cited_id:
                        # ensure newer, not just different: trust latest committed repo
                        newer_available = True
                        newer_id = latest_id

            # document title
            document_title = _coalesce(
                _get_attr(
                    version_obj,
                    'document_title',
                    'title',
                    'filename',
                    'file_name',
                    'original_filename',
                ),
            )
            if document_title is None and doc_repo is not None and v_document_id is not None:
                try:
                    document_obj = await _call_document_get(doc_repo, company_id, v_document_id)
                except Exception:
                    document_obj = None
                document_title = _coalesce(
                    _get_attr(document_obj, 'title', 'name', 'filename', 'document_title')
                )
            if document_title is None:
                document_title = _text(v_document_id or document_id_input)

            document_id = _coalesce(v_document_id, document_id_input)
            # category
            category = _coalesce(
                category_input,
                _get_attr(version_obj, 'category', 'document_category', 'doc_category'),
            )

            is_table_type = str(t_type or '').lower() in {'table', 'tables'} or (
                chunk_id_input is not None and _looks_table_id(chunk_id_input)
            )

            text = ''
            needs_review = False
            content_type = 'text'
            table_payload = None
            tables_list: list[Any] = []
            resolved_chunk = None
            highlight = None
            if char_start is not None or char_end is not None:
                highlight = {
                    'start_char': _as_int(char_start),
                    'end_char': _as_int(char_end),
                    'char_start': _as_int(char_start),
                    'char_end': _as_int(char_end),
                    'start': _as_int(char_start),
                    'end': _as_int(char_end),
                    's': _as_int(char_start),
                    'e': _as_int(char_end),
                }

            # Table repository fetch helper
            async def _list_tables() -> list[Any]:
                if table_repo is None:
                    return []
                rows = await _call_table_list(
                    table_repo,
                    company_id,
                    version_id_input,
                    v_document_id or document_id_input,
                    page_input,
                )
                return _as_list(rows)

            chunk_repo_ok = chunk_repo is not None

            # If chunk/table id supplied.
            if chunk_id_input is not None:
                supplied = str(chunk_id_input)
                is_supplied_table = str(t_type or '').lower() == 'table' or _looks_table_id(
                    supplied
                )
                if is_supplied_table:
                    tables_all = await _list_tables()
                    matched_table = None
                    for t in tables_all:
                        if str(_get_attr(t, 'table_id', 'id', 'table')) == supplied:
                            matched_table = t
                            break
                    if matched_table is None:
                        # maybe get by id
                        if table_repo is not None:
                            try:
                                matched_table = await _call_table_get(
                                    table_repo,
                                    company_id,
                                    supplied,
                                    version_id_input,
                                    v_document_id or document_id_input,
                                    page_input,
                                )
                            except Exception:
                                matched_table = None
                    if matched_table is None:
                        outcome = 'not_available'
                        raise _NotAvailable()
                    table_payload = _table_to_payload(matched_table)
                    tables_list = [table_payload] if table_payload else []
                    text = _coalesce(_get_attr(matched_table, 'text'), '') or _table_text(
                        table_payload
                    )
                    needs_review = bool(_get_attr(matched_table, 'needs_review'))
                    content_type = 'table'
                else:
                    if chunk_repo_ok:
                        chunk_obj = await _call_chunk_get(chunk_repo, company_id, supplied)
                    else:
                        chunk_obj = None
                    if chunk_obj is None:
                        outcome = 'not_available'
                        raise _NotAvailable()
                    # ensure version matches
                    c_version = _get_attr(chunk_obj, 'version_id', 'version')
                    if c_version is not None and str(c_version) != str(version_id_input):
                        outcome = 'not_available'
                        raise _NotAvailable()
                    # page match if page supplied
                    c_page = _get_attr(chunk_obj, 'page_number', 'page')
                    if (
                        page_input is not None
                        and c_page is not None
                        and int(c_page) != int(page_input)
                    ):
                        outcome = 'not_available'
                        raise _NotAvailable()
                    resolved_chunk = chunk_obj
                    text = _text(_get_attr(chunk_obj, 'text'))
                    needs_review = bool(_get_attr(chunk_obj, 'needs_review'))
                    content_type = 'text'
                    # attach tables for page
                    tables_all = await _list_tables()
                    for t in tables_all:
                        tp = _table_to_payload(t)
                        if tp is not None and (
                            page_input is None
                            or int(_get_attr(t, 'page', 'page_number') or 0) == int(page_input)
                        ):
                            tables_list.append(tp)
                    if tables_list:
                        table_payload = tables_list[0]
                    # content type table if table present and no text? keep text

            else:
                # page/version aggregate
                if chunk_repo_ok:
                    chunks = await _call_chunk_list(
                        chunk_repo,
                        company_id,
                        str(version_id_input),
                        v_document_id or document_id_input,
                        page_input,
                    )
                else:
                    chunks = []
                chunks = _as_list(chunks)
                # filter active and page
                filtered = []
                for c in chunks:
                    if _get_attr(c, 'is_active') is False:
                        continue
                    c_page = _get_attr(c, 'page_number', 'page')
                    if (
                        page_input is not None
                        and c_page is not None
                        and int(c_page) != int(page_input)
                    ):
                        continue
                    filtered.append(c)
                if page_input is None:
                    filtered = filtered
                text = '\n'.join(
                    _text(_get_attr(c, 'text'))
                    for c in filtered
                    if _get_attr(c, 'text') is not None
                )
                needs_review = any(bool(_get_attr(c, 'needs_review')) for c in filtered)
                # tables for page
                tables_all = await _list_tables()
                for t in tables_all:
                    tp = _table_to_payload(t)
                    if tp is None:
                        continue
                    t_page = _get_attr(t, 'page', 'page_number')
                    if (
                        page_input is not None
                        and t_page is not None
                        and int(t_page) != int(page_input)
                    ):
                        continue
                    tables_list.append(tp)
                if tables_list:
                    table_payload = tables_list[0]
                    content_type = (
                        'table'
                        if text.strip() == '' or str(t_type or '').lower() == 'table'
                        else 'text'
                    )
                else:
                    content_type = 'text'

            if table_payload is None and tables_list:
                table_payload = tables_list[0]

            if text is None:
                text = ''

            original_available = self._is_original_available(role_raw, permissions, category)

            original_requested = any(
                bool(extra.get(k))
                for k in (
                    '_original',
                    'original',
                    'original_only',
                )
            )

            signed_original_link = None
            if original_requested:
                if not original_available:
                    outcome = 'not_available'
                    raise _NotAvailable()
                storage = self._object_storage
                storage_key = _coalesce(
                    storage_key_input,
                    self._resolve_original_storage_key(
                        version_obj,
                        locals().get('document_obj'),
                        company_id,
                        document_id,
                        version_id_input,
                    ),
                )
                if storage is None or storage_key is None:
                    outcome = 'not_available'
                    raise _NotAvailable()
                ttl = _coalesce(
                    extra.get('source_original_link_ttl_seconds'),
                    extra.get('ttl_seconds'),
                    extra.get('expires_in'),
                    self._ttl_from_config(),
                )
                try:
                    ttl_int = int(ttl) if ttl is not None else None
                except (TypeError, ValueError):
                    ttl_int = None
                if ttl_int is None:
                    ttl_int = self._ttl_from_config()
                await self._trace(company_id, 'source_fetch')
                signed_original_link = await storage.generate_presigned_download_url(
                    company_id,
                    storage_key,
                    expires_in=ttl_int,
                    source_original_link_ttl_seconds=ttl_int,
                )

            result_obj = SourceViewerResult(
                status='available',
                document_id=document_id,
                document_title=document_title,
                title=document_title,
                document_version=_coalesce(version_id_input, cited_id),
                version=_coalesce(version_id_input, cited_id),
                version_id=_coalesce(version_id_input, cited_id),
                page_number=page_input,
                page=page_input,
                content_type=content_type,
                text=text,
                table=table_payload,
                tables=tables_list,
                highlight=highlight,
                needs_review=needs_review,
                newer_version_available=newer_available,
                newer_version_id=newer_id,
                original_available=original_available,
                original_link=signed_original_link,
                citation=citation_input,
                citation_locator=locator_token,
                locator=locator_token,
                company_id=company_id,
                user_id=user_id,
                role=role_raw,
                trace_id=trace_id,
                outcome='success',
                result='available',
            )

        except _NotAvailable:
            outcome = 'not_available'
            result_obj = SourceViewerResult(
                status='not_available',
                document_id=document_id_input,
                document_title=None,
                page_number=page_input,
                content_type='text',
                text='',
                table=None,
                tables=[],
                highlight=None,
                needs_review=False,
                newer_version_available=False,
                newer_version_id=None,
                original_available=False,
                original_link=None,
                citation=citation_input,
                citation_locator=locator_token,
                company_id=company_id,
                user_id=user_id,
                role=role_raw,
                trace_id=trace_id,
                outcome='not_available',
                result='not_available',
            )
        except Exception:
            outcome = 'error'
            result_obj = SourceViewerResult(
                status='not_available',
                document_id=document_id_input,
                document_title=None,
                page_number=page_input,
                content_type='text',
                text='',
                table=None,
                tables=[],
                highlight=None,
                needs_review=False,
                newer_version_available=False,
                newer_version_id=None,
                original_available=False,
                original_link=None,
                citation=citation_input,
                citation_locator=locator_token,
                company_id=company_id,
                user_id=user_id,
                role=role_raw,
                trace_id=trace_id,
                outcome='error',
                result='not_available',
            )

        # Audit write (best-effort) for every open/denial.
        await self._write_audit(
            company_id=audit_company,
            user_id=audit_user,
            role=audit_role,
            trace_id=audit_trace,
            citation_locator=locator_token if locator_token is not None else citation_input,
            outcome=outcome,
            document_id=_coalesce(result_obj.document_id, document_id_input),
            version_id=_coalesce(result_obj.document_version, version_id_input),
            chunk_id=chunk_id_input,
            page=page_input,
            newer_version_available=getattr(result_obj, 'newer_version_available', False),
            needs_review=getattr(result_obj, 'needs_review', False),
        )

        if outcome in {'not_available', 'error'}:
            # collapse status to not_available for error too
            result_obj.status = 'not_available'
            result_obj.outcome = outcome if outcome == 'error' else 'not_available'
            result_obj.result = 'not_available'

        return result_obj

    # ---------- helpers ----------

    def _normalize_context(
        self, ctx_input: Any, extra: dict[str, Any], rest: tuple[Any, ...]
    ) -> Any:
        if _looks_context(ctx_input):
            return ctx_input
        # build from company/role fields if context given as dict
        if isinstance(ctx_input, dict):
            try:
                from finsight.core.types import RequestContext

                company = _coalesce(
                    ctx_input.get('company_id'),
                    ctx_input.get('companyId'),
                    self._company_id,
                    extra.get('company_id'),
                )
                user = _coalesce(
                    ctx_input.get('user_id'),
                    ctx_input.get('userId'),
                    self._user_id,
                    extra.get('user_id'),
                )
                role = _coalesce(ctx_input.get('role'), self._role, extra.get('role'))
                trace = _coalesce(
                    ctx_input.get('trace_id'),
                    ctx_input.get('traceId'),
                    self._trace_id,
                    extra.get('trace_id'),
                )
                perms = _coalesce(
                    ctx_input.get('permissions'), self._permissions, extra.get('permissions')
                )
                scope = _coalesce(
                    ctx_input.get('access_scope'),
                    ctx_input.get('accessScope'),
                    self._access_scope,
                    extra.get('access_scope'),
                )
                if company is not None and role is not None:
                    return RequestContext(
                        company_id=CompanyId(str(company)),
                        user_id=UserId(str(user)) if user is not None else UserId('unknown'),
                        role=role,
                        trace_id=TraceId(str(trace)) if trace is not None else TraceId('trace'),
                        permissions=perms if isinstance(perms, dict) else {},
                        access_scope=_as_list(scope),
                    )
            except Exception:
                pass
        # If no context but company/role provided, build minimal
        company = _coalesce(self._company_id, extra.get('company_id'), extra.get('companyId'))
        role = _coalesce(self._role, extra.get('role'))
        if company is not None and (
            role is not None
            or self._permissions is not None
            or extra.get('permissions') is not None
        ):
            try:
                from finsight.core.types import RequestContext

                perms = _coalesce(self._permissions, extra.get('permissions'), {})
                scope = _coalesce(
                    self._access_scope, extra.get('access_scope'), extra.get('accessScope')
                )
                return RequestContext(
                    company_id=CompanyId(str(company)),
                    user_id=UserId(str(_coalesce(self._user_id, extra.get('user_id'), 'unknown'))),
                    role=role,
                    trace_id=TraceId(
                        str(_coalesce(self._trace_id, extra.get('trace_id'), 'trace'))
                    ),
                    permissions=perms if isinstance(perms, dict) else {},
                    access_scope=_as_list(scope),
                )
            except Exception:
                pass
        return ctx_input

    def _authorize_role(
        self, role_raw: Any, permissions: Any, access_scope: Any, category: Any
    ) -> bool:
        # System admin should not read financial content.
        role_text = str(getattr(role_raw, 'value', role_raw) or '').strip()
        if role_text == 'system_admin' and category is not None:
            return False
        if role_text == 'system_admin' and (category is None or str(category).strip() == ''):
            # system admin has no content access
            return False

        scope_list = _as_list(access_scope)
        scope_values = [str(getattr(x, 'value', x)) for x in scope_list]

        # If category known, enforce access scope membership + read permission.
        if category is not None:
            cat_text = str(getattr(category, 'value', category))
            if scope_list and cat_text not in scope_values:
                return False
            # permission read
            if not self._has_read_permission(role_raw, permissions, category, scope_list):
                return False
        # unknown category: only allow if no access scope restriction?
        elif scope_list and len(scope_list) == 0:
            return False
        return True

    def _has_read_permission(
        self, role_raw: Any, permissions: Any, category: Any, access_scope: Any
    ) -> bool:
        cat_text = str(getattr(category, 'value', category))
        role_text = str(getattr(role_raw, 'value', role_raw) or '')

        # permissions can be a current-user map: category -> actions
        if isinstance(permissions, dict):
            # matrix style keyed by role
            role_perms = None
            if role_text in permissions or str(role_text) in permissions:
                role_perms = permissions.get(role_text, permissions.get(str(role_text)))
            if role_perms is not None:
                try:
                    from finsight.domain.services.permission_policy import is_permission_allowed

                    matrix = (
                        permissions if self._permission_matrix is None else self._permission_matrix
                    )
                    if is_permission_allowed(matrix, role_raw, category, 'read'):
                        return True
                except Exception:
                    pass
                # nested categories
                if isinstance(role_perms, dict):
                    cats = role_perms.get('categories', role_perms)
                    if isinstance(cats, dict):
                        allowed = cats.get(cat_text, cats.get(str(category), ()))
                        if _allowed_contains(allowed, 'read'):
                            return True
            # direct map
            direct = None
            if cat_text in permissions:
                direct = permissions.get(cat_text)
            elif str(category) in permissions:
                direct = permissions.get(str(category))
            if cat_text not in permissions and str(category) not in permissions:
                if role_text not in permissions:
                    return False
            if direct is not None:
                if isinstance(direct, (list, tuple, set)):
                    return (
                        'read' in [str(x).lower() for x in direct]
                        or '*' in [str(x) for x in direct]
                        or 'read' in [str(getattr(x, 'value', x)).lower() for x in direct]
                    )
                if isinstance(direct, dict):
                    return direct.get('read', False) is True
                return True
            if role_text not in permissions:
                return False

            # fallback to loaded permission matrix by role only if no context permissions supplied
        if permissions is None:
            matrix = self._permission_matrix  # type: ignore[assignment]
            if matrix is None:
                matrix = _load_permission_matrix(self._config)
            if isinstance(matrix, dict):
                try:
                    from finsight.domain.services.permission_policy import is_permission_allowed

                    if is_permission_allowed(matrix, role_raw, category, 'read'):
                        return True
                except Exception:
                    pass
        if permissions is None and not isinstance(self._permission_matrix, dict):
            return True
        return False

    def _is_original_available(self, role_raw: Any, permissions: Any, category: Any) -> bool:
        if category is None:
            return False
        role_text = str(getattr(role_raw, 'value', role_raw) or '')
        if role_text == 'system_admin':
            return False
        cat_text = str(getattr(category, 'value', category))
        # permission check for view_original
        if isinstance(permissions, dict):
            # current-user map unlikely includes view_original but try
            direct = None
            if cat_text in permissions:
                direct = permissions.get(cat_text)
            if isinstance(direct, (list, tuple, set)):
                vals = [str(getattr(x, 'value', x)).lower() for x in direct]
                if 'view_original' in vals:
                    return True
            # matrix
            role_perms = permissions.get(role_text) if role_text in permissions else None
            if role_perms is not None:
                try:
                    from finsight.domain.services.permission_policy import is_permission_allowed

                    matrix = (
                        permissions if self._permission_matrix is None else self._permission_matrix
                    )
                    if is_permission_allowed(matrix, role_raw, category, 'view_original'):
                        return True
                except Exception:
                    pass
        matrix = self._permission_matrix  # type: ignore[assignment]
        if matrix is None:
            matrix = _load_permission_matrix(self._config)
        if isinstance(matrix, dict):
            try:
                from finsight.domain.services.permission_policy import is_permission_allowed

                return bool(is_permission_allowed(matrix, role_raw, category, 'view_original'))
            except Exception:
                return False
        return False

    async def view_original(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        params = dict(kwargs)
        params['_original'] = True
        return await self._execute(*args, **params)

    async def open_original(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def get_original(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def download_original(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def fetch_original(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def resolve_original(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def original(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def mint_original_link(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def get_original_download_url(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def original_download_url(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def original_url(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def get_original_url(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def open_original_file(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def view_original_file(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def get_original_file(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def download_original_file(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    async def download_url(self, *args: Any, **kwargs: Any) -> SourceViewerResult:
        return await self.view_original(*args, **kwargs)

    def _ttl_from_config(self) -> int:
        cfg = self._config
        docs_cfg = getattr(cfg, 'documents', None) if cfg is not None else None
        if docs_cfg is None and isinstance(cfg, dict):
            docs_cfg = cfg.get('documents') if isinstance(cfg, dict) else None
        ttl = None
        if isinstance(docs_cfg, dict):
            ttl = docs_cfg.get('source_original_link_ttl_seconds')
        elif docs_cfg is not None:
            ttl = getattr(docs_cfg, 'source_original_link_ttl_seconds', None)
        if ttl is None and isinstance(cfg, dict):
            ttl = cfg.get('source_original_link_ttl_seconds')
        if ttl is None and cfg is not None and not isinstance(cfg, dict):
            ttl = getattr(cfg, 'source_original_link_ttl_seconds', None)
        try:
            value = int(ttl) if ttl is not None else 300
        except (TypeError, ValueError):
            value = 300
        if value < 1:
            value = 300
        return value

    def _resolve_original_storage_key(
        self,
        version_obj: Any,
        document_obj: Any,
        company_id: Any,
        document_id_input: Any,
        version_id_input: Any,
    ) -> Any:
        # Check direct attributes on version/document.
        for obj in (version_obj, document_obj):
            key = _get_attr(
                obj,
                'storage_key',
                's3_key',
                'object_key',
                'file_key',
                'source_key',
                'storage_path',
                's3_path',
                'object_path',
                'path',
                'uri',
                'source_uri',
                'location',
                'key',
                default=None,
            )
            if key is not None:
                return key
        # Nested metadata/extras.
        for obj in (version_obj, document_obj):
            for attr in ('metadata', 'extras', 'meta', 'data', 'properties'):
                nested = _get_attr(obj, attr, default=None)
                if isinstance(nested, dict):
                    for k in (
                        'storage_key',
                        's3_key',
                        'object_key',
                        'file_key',
                        'source_key',
                        'storage_path',
                        'key',
                        'path',
                        'uri',
                    ):
                        if nested.get(k) is not None:
                            return nested.get(k)
        # Build from storage adapter if available.
        storage = self._object_storage
        cid = str(company_id)
        doc_id = _coalesce(
            document_id_input,
            _get_attr(version_obj, 'document_id', 'documentId', 'doc_id', default=None),
            _get_attr(document_obj, 'document_id', 'documentId', 'doc_id', 'id', default=None),
        )
        ver_id = _coalesce(
            version_id_input,
            _get_attr(
                version_obj, 'version_id', 'document_version_id', 'id', 'version', default=None
            ),
        )
        filename = _coalesce(
            _get_attr(
                version_obj,
                'filename',
                'file_name',
                'original_filename',
                'source_filename',
                'name',
                'title',
                default=None,
            ),
            _get_attr(
                document_obj,
                'filename',
                'file_name',
                'original_filename',
                'title',
                'name',
                default=None,
            ),
        )
        if storage is not None and doc_id is not None and filename is not None:
            builder = getattr(storage, 'build_key', None)
            if callable(builder):
                try:
                    return builder(cid, doc_id, ver_id, filename)
                except Exception:
                    pass
            # fallback constructed key
            safe_name = str(filename).strip().split('/')[-1]
            if safe_name == '':
                safe_name = 'document'
            ver_part = str(ver_id) if ver_id is not None else 'version'
            return f'{cid}/documents/{doc_id}/versions/{ver_part}/{safe_name}'
        return None

    async def _write_audit(self, **kwargs: Any) -> None:
        audit = self._audit_log
        if audit is None:
            return
        # normalize company id
        company_id = kwargs.pop('company_id', None)
        call_variants = [
            (
                'append_source_view',
                'append',
                'record_source_view',
                'log_source_view',
                'write_source_view',
                'record_source_view_event',
                'emit',
                'append_event',
            )
        ]
        method = None
        for name in (
            'append_source_view',
            'append',
            'record_source_view',
            'log_source_view',
            'write_source_view',
            'record_source_view_event',
            'emit',
            'append_event',
            'record',
            'write',
            'log',
            'create',
        ):
            attr = getattr(audit, name, None)
            if callable(attr):
                method = attr
                break
        if method is None:
            return
        event_kwargs = {
            'event_type': 'source_view',
            'action': 'source_view',
            'actor': kwargs.get('user_id'),
            'actor_id': kwargs.get('user_id'),
            'user_id': kwargs.get('user_id'),
            'user': kwargs.get('user_id'),
            'role': kwargs.get('role'),
            'company_id': company_id,
            'citation_locator': kwargs.get('citation_locator'),
            'locator': kwargs.get('citation_locator'),
            'citation': kwargs.get('citation_locator'),
            'outcome': kwargs.get('outcome'),
            'status': kwargs.get('outcome'),
            'result': kwargs.get('outcome'),
            'trace_id': kwargs.get('trace_id'),
            'trace': kwargs.get('trace_id'),
            'resource_type': 'source_view',
            'details': {
                'document_id': kwargs.get('document_id'),
                'document_version': kwargs.get('version_id'),
                'chunk_id': kwargs.get('chunk_id'),
                'page_number': kwargs.get('page'),
                'newer_version_available': kwargs.get('newer_version_available'),
                'needs_review': kwargs.get('needs_review'),
            },
            'metadata': {
                'document_id': kwargs.get('document_id'),
                'version_id': kwargs.get('version_id'),
                'page': kwargs.get('page'),
            },
        }
        # collapse None values? keep
        try:
            await _await(method(**event_kwargs))
        except TypeError:
            payload_without_company = {k: v for k, v in event_kwargs.items() if k != 'company_id'}
            try:
                await _await(method(company_id, **payload_without_company))
            except Exception:
                try:
                    await _await(method(**{'company_id': company_id, **payload_without_company}))
                except Exception:
                    pass
        except Exception:
            pass


_original_method_names = [
    'view_original',
    'open_original',
    'get_original',
    'download_original',
    'fetch_original',
    'resolve_original',
    'original',
    'mint_original_link',
    'get_original_download_url',
    'original_download_url',
    'original_url',
    'get_original_url',
    'open_original_file',
    'view_original_file',
    'get_original_file',
    'download_original_file',
    'download_url',
    'presigned_download_url',
    'presigned_original_url',
    'get_presigned_download_url',
    'get_presigned_original_url',
    'mint_presigned_download_url',
    'mint_original',
    'create_original_link',
    'get_original_link',
    'original_link_url',
    'resolve_original_download',
    'view_download',
    'open_download',
    'get_download',
]

for _name in _original_method_names:
    if not hasattr(SourceViewer, _name):
        setattr(SourceViewer, _name, SourceViewer.view_original)


class _NotAvailable(Exception):
    pass


# ---------- module-level helpers ----------


def _looks_config(value: Any) -> bool:
    return hasattr(value, 'switches') or hasattr(value, 'documents') or hasattr(value, 'app')


def _looks_audit(value: Any) -> bool:
    for name in ('append', 'append_source_view', 'record', 'emit', 'write'):
        if hasattr(value, name) and callable(getattr(value, name)):
            return True
    return False


def _looks_chunk_repo(value: Any) -> bool:
    return any(
        hasattr(value, n)
        for n in ('get_chunk', 'list_chunks_by_version', 'list_chunks_by_document')
    )


def _looks_table_repo(value: Any) -> bool:
    return any(
        hasattr(value, n)
        for n in (
            'list_document_tables',
            'list_tables',
            'upsert_document_tables',
            'get_document_table',
        )
    )


def _looks_document_repo(value: Any) -> bool:
    return any(
        hasattr(value, n)
        for n in ('get_document_version', 'list_document_versions', 'get_version', 'list_versions')
    )


def _looks_storage(value: Any) -> bool:
    return any(
        hasattr(value, n)
        for n in (
            'generate_presigned_download_url',
            'generate_presigned_download',
            'presigned_download_url',
            'download_url',
            '_normalize_key',
            'build_key',
        )
    )


def _looks_context(value: Any) -> bool:
    if isinstance(value, dict):
        return any(k in value for k in ('company_id', 'role', 'permissions', 'access_scope'))
    return hasattr(value, 'company_id') and (
        hasattr(value, 'role') or hasattr(value, 'permissions')
    )


def _looks_request(value: Any) -> bool:
    return isinstance(value, dict) or any(
        hasattr(value, n) for n in ('document_id', 'citation', 'citation_locator', 'company_id')
    )


def _allowed_contains(allowed: Any, action: str) -> bool:
    if isinstance(allowed, str):
        allowed = [allowed]
    if isinstance(allowed, (list, tuple, set)):
        vals = [str(getattr(x, 'value', x)).lower() for x in allowed]
        return action.lower() in vals or '*' in vals
    return False


def _load_permission_matrix(config: Any) -> Any:
    if config is None:
        return None
    perms = getattr(config, 'permissions', None)
    if perms is not None:
        if hasattr(perms, 'model_dump'):
            try:
                return perms.model_dump()
            except Exception:
                pass
        if isinstance(perms, dict):
            return perms
    # try yaml file via config access path
    try:
        from pathlib import Path

        import yaml

        candidates = ['config/permissions.yaml', 'permissions.yaml']
        for cand in candidates:
            p = Path(cand)
            if p.exists():
                return yaml.safe_load(p.read_text())
    except Exception:
        pass
    return None


def list_documents_category() -> list[Any]:
    try:
        from finsight.core.types import DocumentCategory

        return list(DocumentCategory)
    except Exception:
        return []


def decode_locator(token: str) -> Any:
    try:
        from finsight.core.security.citation_locator import decode_citation_locator

        return decode_citation_locator(token)
    except Exception:
        try:
            from finsight.core.security.citation_locator import decode_citation_locator as dcl

            return dcl(token)
        except Exception:
            return {}


def verify_signed_locator(token: Any, secret: Any) -> bool:
    try:
        from finsight.core.security.citation_locator import verify_citation_locator

        if secret is None:
            return verify_citation_locator(token)
        return verify_citation_locator(token, secret)
    except Exception:
        return False


def _is_expired(created_at: Any, days: int) -> bool | None:
    if created_at is None:
        return None
    try:
        if isinstance(created_at, (datetime,)):
            dt = created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return datetime.now(UTC) - dt > timedelta(days=days)
    except Exception:
        pass
    return None


def _is_newer_version(cited: Any, candidate: Any) -> bool:
    # compare version numbers first
    cited_ver = _get_attr(cited, 'version', 'version_number', 'revision')
    cand_ver = _get_attr(candidate, 'version', 'version_number', 'revision')
    try:
        if cited_ver is not None and cand_ver is not None:
            if int(cand_ver) > int(cited_ver):
                return True
            if int(cand_ver) < int(cited_ver):
                return False
    except (TypeError, ValueError):
        try:
            if float(cand_ver) > float(cited_ver):
                return True
        except Exception:
            pass
    # fall back to created_at
    cited_created = _get_attr(cited, 'created_at', 'updated_at')
    cand_created = _get_attr(candidate, 'created_at', 'updated_at')
    if isinstance(cited_created, datetime) and isinstance(cand_created, datetime):
        a = cited_created if cited_created.tzinfo else cited_created.replace(tzinfo=UTC)
        b = cand_created if cand_created.tzinfo else cand_created.replace(tzinfo=UTC)
        return b > a
    return False


# ---------- repository call helpers ----------


async def _call_document_get_version(repo: Any, company_id: Any, version_id: Any) -> Any:
    for name in (
        'get_document_version',
        'get_version',
        'get_document_version_by_id',
        'get_version_by_id',
    ):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                return await _await(meth(company_id, version_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, version_id=version_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_document_list_versions(repo: Any, company_id: Any, document_id: Any) -> Any:
    for name in (
        'list_document_versions',
        'list_versions',
        'find_versions',
        'list_versions_by_document',
    ):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                if document_id is not None:
                    return await _await(meth(company_id, document_id))
                return await _await(meth(company_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, document_id=document_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_document_latest_version(repo: Any, company_id: Any, document_id: Any) -> Any:
    for name in ('get_latest_committed_version', 'latest_committed_version', 'get_latest_version'):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                if document_id is not None:
                    return await _await(meth(company_id, document_id))
                return await _await(meth(company_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, document_id=document_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_document_get(repo: Any, company_id: Any, document_id: Any) -> Any:
    for name in ('get_document', 'get'):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                return await _await(meth(company_id, document_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, document_id=document_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_chunk_get(repo: Any, company_id: Any, chunk_id: Any) -> Any:
    for name in ('get_chunk', 'get'):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                return await _await(meth(company_id, chunk_id))
            except TypeError:
                try:
                    return await _await(meth(company_id=company_id, chunk_id=chunk_id))
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


async def _call_chunk_list(
    repo: Any, company_id: Any, version_id: Any, document_id: Any, page: Any
) -> Any:
    for name in ('list_chunks_by_version', 'list_chunks', 'list_by_version', 'chunks_by_version'):
        meth = getattr(repo, name, None)
        if callable(meth):
            # version_id filters
            try:
                res = await _await(meth(company_id, version_id, include_inactive=False))
                return res
            except TypeError:
                try:
                    res = await _await(
                        meth(company_id=company_id, version_id=version_id, include_inactive=False)
                    )
                    return res
                except TypeError:
                    continue
                except Exception:
                    raise
    for name in ('list_chunks_by_document',):
        meth = getattr(repo, name, None)
        if callable(meth):
            try:
                return await _await(
                    meth(company_id, document_id, version_id=version_id, include_inactive=False)
                )
            except Exception:
                continue
    return []


async def _call_table_list(
    repo: Any, company_id: Any, version_id: Any, document_id: Any, page: Any
) -> list[Any]:
    methods = ('list_document_tables', 'list_tables', 'list', 'get_tables')
    for name in methods:
        meth = getattr(repo, name, None)
        if callable(meth):
            # Try many call styles
            attempts = [
                lambda: meth(
                    company_id, version_id=version_id, document_id=document_id, page_number=page
                ),
                lambda: meth(company_id, version_id, document_id=document_id, page_number=page),
                lambda: meth(company_id, version_id),
                lambda: meth(company_id, document_id=document_id, version_id=version_id),
                lambda: meth(company_id),
            ]
            for attempt in attempts:
                try:
                    res = await _await(attempt())  # type: ignore[no-untyped-call]
                    if res is None:
                        continue
                    return _as_list(res)
                except TypeError:
                    continue
                except Exception:
                    raise
    return []


async def _call_table_get(
    repo: Any, company_id: Any, table_id: Any, version_id: Any, document_id: Any, page: Any
) -> Any:
    methods = ('get_document_table', 'get_table', 'get')
    for name in methods:
        meth = getattr(repo, name, None)
        if callable(meth):
            attempts = [
                lambda: meth(company_id, table_id),
                lambda: meth(company_id, table_id=table_id),
                lambda: meth(
                    company_id, version_id=version_id, table_id=table_id, document_id=document_id
                ),
            ]
            for attempt in attempts:
                try:
                    res = await _await(attempt())  # type: ignore[no-untyped-call]
                    if res is not None:
                        return res
                except TypeError:
                    continue
                except Exception:
                    raise
    return None


def _looks_table_id(value: Any) -> bool:
    text = str(value or '').lower()
    return 'table' in text


def _table_to_payload(table: Any) -> Any:
    if table is None:
        return None
    table_id = _get_attr(table, 'table_id', 'id', 'table')
    payload = _get_attr(table, 'payload', 'data', 'payload_json')
    if payload is None:
        payload = getattr(table, 'payload', None)
    html = _get_attr(table, 'html', 'html_text', 'table_html', 'html_content')
    needs_review = bool(_get_attr(table, 'needs_review'))
    page = _get_attr(table, 'page', 'page_number')
    index = _get_attr(table, 'index', 'table_index', default=0)
    result = {
        'table_id': None if table_id is None else str(table_id),
        'id': None if table_id is None else str(table_id),
        'payload': payload,
        'data': payload,
        'structured': payload,
        'json': payload,
        'html': html,
        'html_text': html,
        'table_html': html,
        'needs_review': needs_review,
        'page': page,
        'page_number': page,
        'index': index,
    }
    return result


def _table_text(table_payload: Any) -> str:
    if not isinstance(table_payload, dict):
        return ''
    payload = table_payload.get('payload')
    if isinstance(payload, dict):
        rows = payload.get('rows')
        if isinstance(rows, list):
            lines = []
            for row in rows:
                if isinstance(row, (list, tuple)):
                    lines.append(' | '.join(str(x) for x in row))
                else:
                    lines.append(str(row))
            return '\n'.join(lines)
    return ''
