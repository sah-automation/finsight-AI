"""Deep module: version resolution (metadata, retention, newer detection) step."""

from __future__ import annotations

from typing import Any

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

_ALLOWED_STATES = frozenset({'', 'committed', 'needs_review', 'superseded', 'done'})


class ResolveVersionStep:
    """Fetch and validate the cited document version and resolve its metadata."""

    def __init__(
        self,
        *,
        document_repository: Any = None,
        document_repo: Any = None,
        doc_repository: Any = None,
        doc_repo: Any = None,
        repository: Any = None,
        repo: Any = None,
        documents: Any = None,
        documents_repository: Any = None,
        version_retention_days: Any = None,
        retention_days: Any = None,
        retention_window_days: Any = None,
        version_retention_window_days: Any = None,
        retention: Any = None,
        version_retention: Any = None,
        retention_window: Any = None,
    ) -> None:
        resolved_repo = None
        for candidate in (
            document_repository,
            document_repo,
            doc_repository,
            doc_repo,
            repository,
            repo,
            documents,
            documents_repository,
        ):
            if candidate is not None:
                resolved_repo = candidate
                break

        resolved_days: Any = None
        for candidate in (
            version_retention_days,
            retention_days,
            retention_window_days,
            version_retention_window_days,
            retention,
            version_retention,
            retention_window,
        ):
            if candidate is not None:
                resolved_days = candidate
                break

        self._document_repository = resolved_repo

        try:
            self._retention_days = int(resolved_days) if resolved_days is not None else 365
        except (TypeError, ValueError):
            self._retention_days = 365

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

    async def _resolve_version_obj(self, context: Any, company_id: Any) -> Any:
        pre_supplied = getattr(context, 'version_obj', None)
        if pre_supplied is None:
            extras = getattr(context, 'extras', None)
            if isinstance(extras, dict):
                pre_supplied = extras.get('version_obj') or extras.get('document_version_obj')
        if pre_supplied is not None:
            return pre_supplied

        repo = self._document_repository
        version_id = self._context_value(context, 'version_id')
        if repo is not None and version_id is not None:
            try:
                return await _await(_call_document_get_version(repo, company_id, version_id))
            except Exception:
                return None
        extras = getattr(context, 'extras', None)
        if isinstance(extras, dict):
            return extras.get('version_obj') or extras.get('document_version_obj')
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

    async def _detect_newer(
        self, context: Any, version_obj: Any, company_id: Any
    ) -> tuple[bool, Any, Any]:
        v_document_id = _coalesce(
            _get_attr(version_obj, 'document_id', 'documentId', 'doc_id'),
            getattr(context, 'document_id', None),
        )
        cited_id = _normalize_version_key(version_obj) or _text(
            getattr(context, 'version_id', None)
        )

        newer_available = False
        newer_id: Any = None
        repo = self._document_repository
        versions_list: Any = None
        if repo is not None and v_document_id is not None:
            try:
                versions_list = await _await(
                    _call_document_list_versions(repo, company_id, v_document_id)
                )
            except Exception:
                versions_list = None
        if versions_list is None and repo is not None:
            try:
                versions_list = await _await(_call_document_list_versions(repo, company_id, None))
            except Exception:
                versions_list = None

        if versions_list is not None:
            for item in _as_list(versions_list):
                if _normalize_version_key(item) == cited_id:
                    continue
                if (
                    _normalize_state(
                        _get_attr(item, 'state', 'status', 'document_state', 'lifecycle_state')
                    )
                    != 'committed'
                ):
                    continue
                if _is_newer_version(version_obj, item):
                    newer_available = True
                    newer_id = _normalize_version_key(item)
                    break

        if not newer_available and repo is not None:
            try:
                latest = await _await(
                    _call_document_latest_version(
                        repo, company_id, v_document_id or getattr(context, 'document_id', None)
                    )
                )
            except Exception:
                latest = None
            if latest is not None:
                latest_id = _normalize_version_key(latest)
                if latest_id is not None and latest_id != cited_id:
                    newer_available = True
                    newer_id = latest_id

        return newer_available, newer_id, v_document_id

    async def _resolve_metadata(
        self, context: Any, version_obj: Any, company_id: Any, v_document_id: Any
    ) -> tuple[Any, str, Any]:
        document_title = _coalesce(
            _get_attr(
                version_obj,
                'document_title',
                'title',
                'filename',
                'file_name',
                'original_filename',
            )
        )
        document_obj: Any = None
        if document_title is None:
            repo = self._document_repository
            if repo is not None and v_document_id is not None:
                try:
                    document_obj = await _await(_call_document_get(repo, company_id, v_document_id))
                except Exception:
                    document_obj = None
            document_title = _coalesce(
                _get_attr(document_obj, 'title', 'name', 'filename', 'document_title')
            )
        if document_title is None:
            document_title = _text(
                v_document_id
                or getattr(context, 'document_id', None)
                or getattr(context, 'version_id', None)
            )

        category = _coalesce(
            getattr(context, 'category', None),
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

    def _apply(
        self,
        context: Any,
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
        resolved_document_id = _coalesce(v_document_id, getattr(context, 'document_id', None))
        if resolved_document_id is not None:
            context.document_id = resolved_document_id

    async def run(self, context: Any) -> StepResult:
        company_id = getattr(context, 'company_id', None)
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
