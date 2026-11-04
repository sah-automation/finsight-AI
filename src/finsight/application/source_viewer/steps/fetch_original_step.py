"""Deep module: signed original-document link generation step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.application.source_viewer._step_helpers import (
    _await,
    _coalesce,
    _get_attr,
    _text,
)
from finsight.application.source_viewer.step_result import StepResult

if TYPE_CHECKING:
    from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
    from finsight.domain.ports.document_repository import DocumentRepository
    from finsight.domain.ports.object_storage import ObjectStorage

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
_ORIGINAL_KEYS = ('_original', 'original', 'original_only')
_STORAGE_KEY_NAMES = (
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
_NESTED_KEY_NAMES = (
    'storage_key',
    's3_key',
    'object_key',
    'file_key',
    'source_key',
    'storage_path',
    'key',
    'path',
    'uri',
)


class FetchOriginalStep:
    """Mint a signed download link for the original document."""

    def __init__(
        self,
        *,
        object_storage: ObjectStorage | None = None,
        document_repository: DocumentRepository | None = None,
        ttl_seconds: int,
    ) -> None:
        self._object_storage = object_storage
        self._document_repository = document_repository
        self._ttl_seconds = int(ttl_seconds)

    def _request_ttl(self, context: SourceViewerContext) -> Any:
        return _get_attr(context, *_TTL_KEYS)

    async def _run(self, context: SourceViewerContext) -> StepResult:
        original_requested = bool(context.original_requested) or any(
            bool(_get_attr(context, key)) for key in _ORIGINAL_KEYS
        )
        if not original_requested:
            return StepResult.continue_(context)
        if context.original_available is False:
            return StepResult.stop_with_not_available(context)

        company_id = _get_attr(context, 'company_id', 'companyId', 'tenant_id', 'company')
        document_id = _get_attr(context, 'document_id', 'documentId', 'doc_id', 'docId')
        version_id = _get_attr(
            context, 'version_id', 'versionId', 'version', 'document_version', 'document_version_id'
        )
        storage_key = _coalesce(
            _get_attr(context, *_STORAGE_KEY_NAMES),
            _resolve_storage_key(
                self._object_storage,
                context.version_obj,
                context.document_obj,
                company_id,
                document_id,
                version_id,
            ),
        )
        if self._object_storage is None or storage_key is None:
            return StepResult.stop_with_not_available(context)

        ttl_int = self._ttl_seconds
        ttl_override = self._request_ttl(context)
        if ttl_override is not None:
            try:
                parsed = int(ttl_override)
                if parsed >= 1:
                    ttl_int = parsed
            except (TypeError, ValueError):
                pass

        try:
            signed = await _await(
                self._object_storage.generate_presigned_download_url(
                    company_id,
                    storage_key,
                    expires_in=ttl_int,
                    source_original_link_ttl_seconds=ttl_int,
                )
            )
        except (TypeError, ValueError, RuntimeError):
            return StepResult.stop_with_not_available(context)

        context.signed_original_link = signed
        return StepResult.continue_(context)

    async def run(self, context: SourceViewerContext) -> StepResult:
        """Execute this pipeline step."""
        return await self._run(context)


def _resolve_storage_key(  # noqa: PLR0913, PLR0917
    storage: Any,
    version_obj: Any,
    document_obj: Any,
    company_id: Any,
    document_id_input: Any,
    version_id_input: Any,
) -> Any:
    for obj in (version_obj, document_obj):
        key = _get_attr(obj, *_STORAGE_KEY_NAMES)
        if key is not None:
            return key
        for attr in ('metadata', 'extras', 'meta', 'data', 'properties'):
            nested = _get_attr(obj, attr)
            if isinstance(nested, dict):
                key = _get_attr(nested, *_NESTED_KEY_NAMES)
                if key is not None:
                    return key

    company = str(company_id)
    document_id = _coalesce(
        document_id_input,
        _get_attr(version_obj, 'document_id', 'documentId', 'doc_id'),
        _get_attr(document_obj, 'document_id', 'documentId', 'doc_id', 'id'),
    )
    version_id = _coalesce(
        version_id_input,
        _get_attr(version_obj, 'version_id', 'document_version_id', 'id', 'version'),
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
        ),
        _get_attr(
            document_obj,
            'filename',
            'file_name',
            'original_filename',
            'title',
            'name',
        ),
    )
    if storage is None or document_id is None or filename is None:
        return None
    for name in (
        'build_key',
        'generate_key',
        'create_key',
        'key_for',
        'compose_key',
        'build_storage_key',
    ):
        builder = getattr(storage, name, None)
        if callable(builder):
            try:
                return builder(company, document_id, version_id, filename)
            except (TypeError, ValueError, AttributeError):
                pass
    safe_name = _text(filename).strip().split('/')[-1] or 'document'
    version_part = str(version_id) if version_id is not None else 'version'
    return f'{company}/documents/{document_id}/versions/{version_part}/{safe_name}'


__all__ = ['FetchOriginalStep']
