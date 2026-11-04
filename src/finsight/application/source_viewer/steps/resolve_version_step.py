"""Deep module: version resolution (metadata, retention, newer detection) step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.application.source_viewer._step_helpers import (
    _as_list,
    _await,
    _call_document_get,
    _call_document_get_version,
    _call_document_latest_version,
    _call_document_list_versions,
    _coalesce,
    _get_attr,
    _is_expired,
    _is_newer_version,
    _normalize_state,
    _normalize_version_key,
    _text,
)
from finsight.application.source_viewer.step_result import StepResult

if TYPE_CHECKING:
    from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
    from finsight.domain.ports.document_repository import DocumentRepository

_ALLOWED_STATES = frozenset({'', 'committed', 'needs_review', 'superseded', 'done'})


class ResolveVersionStep:
    """Fetch and validate the cited document version and resolve its metadata."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository | None,
        version_retention_days: int,
    ) -> None:
        self._document_repository = document_repository
        self._retention_days = int(version_retention_days)

    async def _resolve_version_obj(self, context: SourceViewerContext, company_id: Any) -> Any:
        if context.version_obj is not None:
            return context.version_obj
        repo = self._document_repository
        if repo is not None and context.version_id is not None:
            try:
                return await _await(
                    _call_document_get_version(repo, company_id, context.version_id)
                )
            except (TypeError, ValueError, RuntimeError):
                return None
        return None

    def _company_ok(self, version_obj: Any, company_id: Any) -> bool:
        version_company = _get_attr(version_obj, 'company_id', 'companyId', 'tenant_id')
        return version_company is None or str(version_company) == str(company_id)

    def _retention_ok(self, version_obj: Any) -> bool:
        state = _normalize_state(
            _get_attr(version_obj, 'state', 'status', 'document_state', 'lifecycle_state')
        )
        if state != 'superseded':
            return True
        created_at = _get_attr(version_obj, 'created_at', 'updated_at')
        expired = _is_expired(created_at, self._retention_days)
        return expired is not True

    async def _detect_newer(  # noqa: PLR0912
        self, context: SourceViewerContext, version_obj: Any, company_id: Any
    ) -> tuple[bool, Any, Any]:
        v_document_id = _coalesce(
            _get_attr(version_obj, 'document_id', 'documentId', 'doc_id'),
            context.document_id,
        )
        cited_id = _normalize_version_key(version_obj) or _text(context.version_id)

        newer_available = False
        newer_id: Any = None
        repo = self._document_repository
        versions_list: Any = None
        if repo is not None and v_document_id is not None:
            try:
                versions_list = await _await(
                    _call_document_list_versions(repo, company_id, v_document_id)
                )
            except (TypeError, ValueError, RuntimeError):
                versions_list = None
        if versions_list is None and repo is not None:
            try:
                versions_list = await _await(_call_document_list_versions(repo, company_id, None))
            except (TypeError, ValueError, RuntimeError):
                versions_list = None

        if versions_list is not None:
            for item in _as_list(versions_list):
                if _normalize_version_key(item) == cited_id:
                    continue
                state = _normalize_state(
                    _get_attr(item, 'state', 'status', 'document_state', 'lifecycle_state')
                )
                if state != 'committed':
                    continue
                if _is_newer_version(version_obj, item):
                    newer_available = True
                    newer_id = _normalize_version_key(item)
                    break

        if not newer_available and repo is not None:
            try:
                latest = await _await(
                    _call_document_latest_version(
                        repo, company_id, v_document_id or context.document_id
                    )
                )
            except (TypeError, ValueError, RuntimeError):
                latest = None
            if latest is not None:
                latest_id = _normalize_version_key(latest)
                if latest_id is not None and latest_id != cited_id:
                    newer_available = True
                    newer_id = latest_id

        return newer_available, newer_id, v_document_id

    async def _resolve_metadata(
        self,
        context: SourceViewerContext,
        version_obj: Any,
        company_id: Any,
        v_document_id: Any,
    ) -> tuple[Any, str, Any]:
        document_title = _get_attr(
            version_obj,
            'document_title',
            'title',
            'filename',
            'file_name',
            'original_filename',
        )
        document_obj: Any = None
        if document_title is None:
            repo = self._document_repository
            if repo is not None and v_document_id is not None:
                try:
                    document_obj = await _await(_call_document_get(repo, company_id, v_document_id))
                except (TypeError, ValueError, RuntimeError):
                    document_obj = None
            document_title = _get_attr(document_obj, 'title', 'name', 'filename', 'document_title')
        if document_title is None:
            document_title = _text(v_document_id or context.document_id or context.version_id)

        category = _coalesce(
            context.category,
            _get_attr(version_obj, 'category', 'document_category', 'doc_category'),
        )
        return document_obj, document_title, category

    def _is_viewable(self, version_obj: Any, company_id: Any) -> bool:
        if not self._company_ok(version_obj, company_id):
            return False
        state = _normalize_state(
            _get_attr(version_obj, 'state', 'status', 'document_state', 'lifecycle_state')
        )
        if state not in _ALLOWED_STATES:
            return False
        return self._retention_ok(version_obj)

    def _apply(  # noqa: PLR0913, PLR0917
        self,
        context: SourceViewerContext,
        version_obj: Any,
        document_obj: Any,
        document_title: Any,
        category: Any,
        newer_available: bool,
        newer_id: Any,
        v_document_id: Any,
    ) -> None:
        context.version_obj = version_obj
        context.document_obj = document_obj
        context.document_title = document_title
        context.category = category
        context.newer_available = newer_available
        context.newer_id = newer_id
        resolved_document_id = _coalesce(v_document_id, context.document_id)
        if resolved_document_id is not None:
            context.document_id = resolved_document_id

    async def run(self, context: SourceViewerContext) -> StepResult:
        """Execute this pipeline step."""
        company_id = context.company_id
        version_obj = await self._resolve_version_obj(context, company_id)
        if version_obj is None or not self._is_viewable(version_obj, company_id):
            return StepResult.stop_with_not_available(context)
        newer_available, newer_id, v_document_id = await self._detect_newer(
            context, version_obj, company_id
        )
        document_obj, document_title, category = await self._resolve_metadata(
            context, version_obj, company_id, v_document_id
        )
        self._apply(
            context,
            version_obj,
            document_obj,
            document_title,
            category,
            newer_available,
            newer_id,
            v_document_id,
        )
        return StepResult.continue_(context)


__all__ = ['ResolveVersionStep']
