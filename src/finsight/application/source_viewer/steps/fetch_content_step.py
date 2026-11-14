"""Deep module: content fetch (chunks and tables) step."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from finsight.application.source_viewer._step_helpers import (
    _as_int,
    _as_list,
    _await,
    _call_chunk_get,
    _call_chunk_list,
    _call_table_get,
    _call_table_list,
    _coalesce,
    _get_attr,
    _text,
)
from finsight.application.source_viewer.step_result import StepResult

if TYPE_CHECKING:
    from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
    from finsight.domain.ports.chunk_repository import ChunkRepository
    from finsight.domain.ports.document_table_repository import DocumentTableRepository

_TABLE_ID_HINT = 'table'

logger = logging.getLogger(__name__)


class FetchContentStep:
    """Retrieve the text and tables for the resolved version."""

    def __init__(
        self,
        *,
        chunk_repository: ChunkRepository | None = None,
        table_repository: DocumentTableRepository | None = None,
    ) -> None:
        self._chunk_repository = chunk_repository
        self._table_repository = table_repository

    def _t_type(self, context: SourceViewerContext) -> Any:
        value = _get_attr(context, 't_type', 'type', 'content_type_hint')
        if value is not None:
            return value
        locator_payload = context.locator_payload
        if isinstance(locator_payload, dict):
            return locator_payload.get('t')
        return None

    def _ensure_highlight(self, context: SourceViewerContext) -> None:
        if context.highlight is not None:
            return
        locator_payload = context.locator_payload
        if not isinstance(locator_payload, dict):
            return
        start = _as_int(locator_payload.get('s'))
        end = _as_int(locator_payload.get('e'))
        if start is None and end is None:
            return
        context.highlight = {
            'start_char': start,
            'end_char': end,
            'char_start': start,
            'char_end': end,
            'start': start,
            'end': end,
            's': start,
            'e': end,
        }

    async def _list_raw_tables(
        self, company_id: Any, version_id: Any, document_id: Any, page: Any
    ) -> list[Any]:
        repo = self._table_repository
        if repo is None:
            return []
        rows = await _call_table_list(repo, company_id, version_id, document_id, page)
        return _as_list(rows)

    async def _run_chunk(  # noqa: PLR0913, PLR0917
        self,
        context: SourceViewerContext,
        company_id: Any,
        version_id: Any,
        document_id: Any,
        page: Any,
        supplied: Any,
    ) -> StepResult:
        repo = self._chunk_repository
        if repo is None:
            return StepResult.stop_with_not_available(context)
        chunk_obj = await _await(_call_chunk_get(repo, company_id, supplied))
        if chunk_obj is None:
            return StepResult.stop_with_not_available(context)
        c_version = _get_attr(chunk_obj, 'version_id', 'version')
        if c_version is not None and version_id is not None and str(c_version) != str(version_id):
            return StepResult.stop_with_not_available(context)
        c_page = _get_attr(chunk_obj, 'page_number', 'page')
        if page is not None and c_page is not None and int(c_page) != int(page):
            return StepResult.stop_with_not_available(context)
        context.chunk_obj = chunk_obj
        context.text = _text(_get_attr(chunk_obj, 'text'))
        context.needs_review = bool(_get_attr(chunk_obj, 'needs_review'))
        context.content_type = 'text'
        tables_list: list[Any] = []
        rows = await self._list_raw_tables(company_id, version_id, document_id, page)
        for row in rows:
            payload = _table_to_payload(row)
            if payload is None:
                continue
            if not (page is None or int(_get_attr(row, 'page', 'page_number') or 0) == int(page)):
                continue
            tables_list.append(payload)
        context.table_payload = tables_list[0] if tables_list else None
        context.tables = tables_list
        return StepResult.continue_(context)

    async def _run_table(  # noqa: PLR0913, PLR0917
        self,
        context: SourceViewerContext,
        company_id: Any,
        version_id: Any,
        document_id: Any,
        page: Any,
        supplied: Any,
    ) -> StepResult:
        matched = None
        rows = await self._list_raw_tables(company_id, version_id, document_id, page)
        for row in rows:
            if str(_get_attr(row, 'table_id', 'id', 'table')) == str(supplied):
                matched = row
                break
        repo = self._table_repository
        if matched is None and repo is not None:
            try:
                matched = await _await(
                    _call_table_get(repo, company_id, supplied, version_id, document_id, page)
                )
            except Exception:
                logger.debug('table get failed (trace_id=%s)', context.trace_id, exc_info=True)
                matched = None
        if matched is None:
            return StepResult.stop_with_not_available(context)
        payload = _table_to_payload(matched)
        tables_list = [payload] if payload else []
        text = _coalesce(_get_attr(matched, 'text'), '') or _table_text(payload)
        if text is None:
            text = ''
        context.chunk_obj = None
        context.text = text
        context.needs_review = bool(_get_attr(matched, 'needs_review'))
        context.content_type = 'table'
        context.table_payload = payload if tables_list else None
        context.tables = tables_list
        return StepResult.continue_(context)

    async def _run_aggregate(
        self,
        context: SourceViewerContext,
        company_id: Any,
        version_id: Any,
        document_id: Any,
        page: Any,
    ) -> StepResult:
        t_type = self._t_type(context)
        chunk_repo = self._chunk_repository
        if chunk_repo is not None:
            chunks = await _call_chunk_list(chunk_repo, company_id, version_id, document_id, page)
        else:
            chunks = []
        chunks = _as_list(chunks)
        filtered: list[Any] = []
        for row in chunks:
            if _get_attr(row, 'is_active') is False:
                continue
            row_page = _get_attr(row, 'page_number', 'page')
            if page is not None and row_page is not None and int(row_page) != int(page):
                continue
            filtered.append(row)
        text = '\n'.join(
            _text(_get_attr(row, 'text')) for row in filtered if _get_attr(row, 'text') is not None
        )
        needs_review = any(bool(_get_attr(row, 'needs_review')) for row in filtered)
        tables_list: list[Any] = []
        rows = await self._list_raw_tables(company_id, version_id, document_id, page)
        for row in rows:
            payload = _table_to_payload(row)
            if payload is None:
                continue
            row_page = _get_attr(row, 'page', 'page_number')
            if page is not None and row_page is not None and int(row_page) != int(page):
                continue
            tables_list.append(payload)
        table_payload = tables_list[0] if tables_list else None
        if tables_list:
            content_type = (
                'table' if text.strip() == '' or str(t_type or '').lower() == 'table' else 'text'
            )
        else:
            content_type = 'text'
        context.chunk_obj = None
        context.text = text
        context.needs_review = needs_review
        context.content_type = content_type
        context.table_payload = table_payload
        context.tables = tables_list
        return StepResult.continue_(context)

    async def run(self, context: SourceViewerContext) -> StepResult:
        """Execute this pipeline step."""
        self._ensure_highlight(context)
        company_id = _get_attr(context, 'company_id', 'companyId', 'tenant_id', 'company')
        version_id = _get_attr(context, 'version_id', 'versionId', 'version')
        document_id = _get_attr(context, 'document_id', 'documentId', 'doc_id')
        if document_id is None:
            document_id = _get_attr(context.version_obj, 'document_id', 'documentId', 'doc_id')
        page_raw = _get_attr(context, 'page', 'page_number', 'pageNumber', 'page_no')
        page = _as_int(page_raw) if isinstance(page_raw, str) else page_raw
        table_id = _get_attr(context, 'table_id', 'tableId', 'table')
        chunk_id = _get_attr(context, 'chunk_id', 'chunkId', 'chunk')
        supplied = table_id if table_id is not None else chunk_id
        if supplied is None:
            return await self._run_aggregate(context, company_id, version_id, document_id, page)
        t_type = self._t_type(context)
        is_table = (
            table_id is not None
            or (isinstance(t_type, str) and t_type.lower() in {'table', 'tables'})
            or _TABLE_ID_HINT in str(supplied).lower()
        )
        if is_table:
            return await self._run_table(
                context, company_id, version_id, document_id, page, supplied
            )
        return await self._run_chunk(context, company_id, version_id, document_id, page, supplied)


def _table_to_payload(table: Any) -> Any:
    if table is None:
        return None
    table_id = _get_attr(table, 'table_id', 'id', 'table')
    payload = _get_attr(table, 'payload', 'data', 'payload_json')
    if payload is None:
        payload = getattr(table, 'payload', None)
    html = _get_attr(table, 'html', 'html_text', 'table_html', 'html_content')
    page = _get_attr(table, 'page', 'page_number')
    return {
        'table_id': None if table_id is None else str(table_id),
        'id': None if table_id is None else str(table_id),
        'payload': payload,
        'data': payload,
        'structured': payload,
        'json': payload,
        'html': html,
        'html_text': html,
        'table_html': html,
        'needs_review': bool(_get_attr(table, 'needs_review')),
        'page': page,
        'page_number': page,
        'index': _get_attr(table, 'index', 'table_index', default=0),
    }


def _table_text(table_payload: Any) -> str:
    if not isinstance(table_payload, dict):
        return ''
    payload = table_payload.get('payload')
    if not isinstance(payload, dict):
        return ''
    rows = payload.get('rows')
    if not isinstance(rows, list):
        return ''
    lines = []
    for row in rows:
        if isinstance(row, (list, tuple)):
            lines.append(' | '.join(str(x) for x in row))
        else:
            lines.append(str(row))
    return '\n'.join(lines)


__all__ = ['FetchContentStep']
