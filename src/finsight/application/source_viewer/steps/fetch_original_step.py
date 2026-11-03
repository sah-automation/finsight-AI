"""Deep module: signed original-document link generation step."""

from __future__ import annotations

from typing import Any

from finsight.application.source_viewer._step_helpers import (
    _await,
    _coalesce,
    _resolve_original_storage_key_impl,
)
from finsight.application.source_viewer.step_result import StepResult

_TTL_KEYS = (
    'source_original_link_ttl_seconds',
    'original_link_ttl_seconds',
    'ttl_seconds',
    'expires_in',
    'expires',
    'expiry',
    'ttl',
    'original_ttl',
    'original_link_ttl',
    'download_ttl_seconds',
    'link_ttl',
    'link_ttl_seconds',
    'original_link_expiry',
    'expiry_seconds',
    'ttl_int',
    'default_expiry',
    'default_ttl',
)

_STORAGE_ALIASES = (
    'object_storage',
    'object_store',
    'storage',
    'storage_adapter',
    'storage_port',
    's3_storage',
    's3',
    'object_storage_adapter',
    'adapter',
)

_DOCUMENT_REPOSITORY_ALIASES = (
    'document_repository',
    'document_repo',
    'documents',
    'document_store',
    'documents_repository',
    'documents_repo',
    'doc_repository',
    'doc_repo',
    'repository',
    'repo',
)

_EXPLICIT_STORAGE_KEY_NAMES = (
    'storage_key',
    'storageKey',
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
)


class FetchOriginalStep:
    """Mint a signed download link for the original document."""

    def __init__(
        self,
        *,
        object_storage: Any = None,
        storage: Any = None,
        object_store: Any = None,
        document_repository: Any = None,
        documents: Any = None,
        document_repo: Any = None,
        ttl: Any = None,
        ttl_seconds: Any = None,
        original_link_ttl_seconds: Any = None,
        source_original_link_ttl_seconds: Any = None,
        expires_in: Any = None,
        **_aliases: Any,
    ) -> None:
        resolved_storage = object_storage
        if resolved_storage is None:
            resolved_storage = storage
        if resolved_storage is None:
            resolved_storage = object_store
        if resolved_storage is None:
            for key in _STORAGE_ALIASES:
                value = _aliases.get(key)
                if value is not None:
                    resolved_storage = value
                    break
        resolved_repo = document_repository
        if resolved_repo is None:
            resolved_repo = document_repo
        if resolved_repo is None:
            resolved_repo = documents
        if resolved_repo is None:
            for key in _DOCUMENT_REPOSITORY_ALIASES:
                value = _aliases.get(key)
                if value is not None:
                    resolved_repo = value
                    break
        resolved_ttl = ttl
        if resolved_ttl is None:
            for candidate in (
                ttl_seconds,
                expires_in,
                original_link_ttl_seconds,
                source_original_link_ttl_seconds,
            ):
                if candidate is not None:
                    resolved_ttl = candidate
                    break
        if resolved_ttl is None:
            for key in _TTL_KEYS:
                value = _aliases.get(key)
                if value is not None:
                    resolved_ttl = value
                    break
        if resolved_ttl is None:
            resolved_ttl = 300
        try:
            resolved_ttl_int = int(resolved_ttl)
        except (TypeError, ValueError):
            resolved_ttl_int = 300
        if resolved_ttl_int < 1:
            resolved_ttl_int = 300
        self._object_storage = resolved_storage
        self._document_repository = resolved_repo
        self._ttl = resolved_ttl_int

    def _context_value(self, context: Any, *attrs: str) -> Any:
        for attr in attrs:
            value = getattr(context, attr, None)
            if value is not None:
                return value
        extras = getattr(context, 'extras', None)
        if isinstance(extras, dict):
            for attr in attrs:
                value = extras.get(attr)
                if value is not None:
                    return value
        return None

    def _original_requested(self, context: Any) -> bool:
        value = getattr(context, 'original_requested', None)
        if value is not None:
            return bool(value)
        extras = getattr(context, 'extras', None)
        if isinstance(extras, dict):
            for key in ('_original', 'original', 'original_only'):
                if extras.get(key):
                    return True
        for attr in ('_original', 'original', 'original_only'):
            if getattr(context, attr, None):
                return True
        return False

    def _request_ttl(self, context: Any) -> Any:
        return self._context_value(context, *_TTL_KEYS)

    def _object_from_context(self, context: Any, attr: str) -> Any:
        value = getattr(context, attr, None)
        if value is None:
            extras = getattr(context, 'extras', None)
            if isinstance(extras, dict):
                value = extras.get(attr) or extras.get(f'{attr}_obj')
        return value

    def _resolve_original_storage_key(
        self,
        version_obj: Any,
        document_obj: Any,
        company_id: Any,
        document_id_input: Any,
        version_id_input: Any,
    ) -> Any:
        return _resolve_original_storage_key_impl(
            self._object_storage,
            version_obj,
            document_obj,
            company_id,
            document_id_input,
            version_id_input,
        )

    async def _run(self, context: Any) -> StepResult:
        original_requested = self._original_requested(context)

        if not original_requested:
            return StepResult.continue_(context)

        if getattr(context, 'original_available', None) is False:
            return StepResult.stop_with_not_available(context)

        storage = self._object_storage
        company_id = self._context_value(context, 'company_id', 'companyId', 'tenant_id', 'company')
        version_obj = self._object_from_context(context, 'version_obj')
        document_obj = self._object_from_context(context, 'document_obj')

        document_id = self._context_value(
            context, 'document_id', 'documentId', 'doc_id', 'docId', 'document'
        )
        version_id = self._context_value(
            context, 'version_id', 'versionId', 'version', 'document_version', 'document_version_id'
        )

        storage_key = _coalesce(
            self._context_value(context, *_EXPLICIT_STORAGE_KEY_NAMES),
            self._resolve_original_storage_key(
                version_obj, document_obj, company_id, document_id, version_id
            ),
        )

        if storage is None or storage_key is None:
            return StepResult.stop_with_not_available(context)

        ttl_override = self._request_ttl(context)
        ttl_int = self._ttl
        if ttl_override is not None:
            try:
                parsed = int(ttl_override)
                if parsed >= 1:
                    ttl_int = parsed
            except (TypeError, ValueError):
                pass

        try:
            signed = await _await(
                storage.generate_presigned_download_url(
                    company_id,
                    storage_key,
                    expires_in=ttl_int,
                    source_original_link_ttl_seconds=ttl_int,
                )
            )
        except Exception:
            return StepResult.stop_with_not_available(context)

        context.signed_original_link = signed
        try:
            context.original_link = signed
        except Exception:
            pass
        return StepResult.continue_(context)

    async def run(self, context: Any) -> StepResult:
        return await self._run(context)


__all__ = ['FetchOriginalStep']
