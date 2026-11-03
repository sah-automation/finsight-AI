"""Deep module: content fetch (chunks and tables) step."""

from __future__ import annotations

from typing import Any

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
    _looks_table_id,
    _table_text,
    _table_to_payload,
    _text,
)
from finsight.application.source_viewer.step_result import StepResult


class FetchContentStep:
    """Retrieve the text and tables for the resolved version."""

    def __init__(
        self,
        *,
        chunk_repository: Any = None,
        chunk_repo: Any = None,
        chunks: Any = None,
        table_repository: Any = None,
        table_repo: Any = None,
        tables: Any = None,
        **_ignored: Any,
    ) -> None:
        resolved_chunk = None
        for candidate in (chunk_repository, chunk_repo, chunks):
            if candidate is not None:
                resolved_chunk = candidate
                break
        resolved_table = None
        for candidate in (table_repository, table_repo, tables):
            if candidate is not None:
                resolved_table = candidate
                break
        self._chunk_repository = resolved_chunk
        self._table_repository = resolved_table

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

    def _t_type(self, context: Any) -> Any:
        value = self._context_value(context, 't_type', 'type', 'content_type_hint')
        if value is not None:
            return value
        locator_payload = getattr(context, 'locator_payload', None)
        if isinstance(locator_payload, dict):
            return locator_payload.get('t')
        extras = getattr(context, 'extras', None)
        if isinstance(extras, dict):
            locator_payload = extras.get('locator_payload')
            if isinstance(locator_payload, dict):
                return locator_payload.get('t')
        return None

    def _ensure_highlight(self, context: Any) -> None:
        if getattr(context, 'highlight', None) is not None:
            return
        locator_payload = getattr(context, 'locator_payload', None)
        if not isinstance(locator_payload, dict):
            extras = getattr(context, 'extras', None)
            if isinstance(extras, dict):
                locator_payload = extras.get('locator_payload')
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
        self, context: Any, company_id: Any, version_id: Any, document_id: Any, page: Any
    ) -> list[Any]:
        repo = self._table_repository
        if repo is None:
            return []
        rows = await _call_table_list(repo, company_id, version_id, document_id, page)
        return _as_list(rows)

    async def _run_chunk(
        self,
        context: Any,
        company_id: Any,
        version_id: Any,
        document_id: Any,
        page: Any,
        supplied: Any,
    ) -> StepResult:
        repo = self._chunk_repository
        if repo is None:
            return StepResult.stop_with_not_available(context)
        try:
            chunk_obj = await _await(_call_chunk_get(repo, company_id, supplied))
        except Exception:
            chunk_obj = None
        if chunk_obj is None:
            return StepResult.stop_with_not_available(context)
        c_version = _get_attr(chunk_obj, 'version_id', 'version')
        if c_version is not None and version_id is not None and str(c_version) != str(version_id):
            return StepResult.stop_with_not_available(context)
        c_page = _get_attr(chunk_obj, 'page_number', 'page')
        if page is not None and c_page is not None and int(c_page) != int(page):
            return StepResult.stop_with_not_available(context)
        context.chunk_obj = chunk_obj
        text = _text(_get_attr(chunk_obj, 'text'))
        needs_review = bool(_get_attr(chunk_obj, 'needs_review'))
        context.text = text
        context.needs_review = needs_review
        context.content_type = 'text'
        tables_list: list[Any] = []
        rows = await self._list_raw_tables(context, company_id, version_id, document_id, page)
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

    async def _run_table(
        self,
        context: Any,
        company_id: Any,
        version_id: Any,
        document_id: Any,
        page: Any,
        supplied: Any,
    ) -> StepResult:
        matched = None
        rows = await self._list_raw_tables(context, company_id, version_id, document_id, page)
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
                matched = None
        if matched is None:
            return StepResult.stop_with_not_available(context)
        payload = _table_to_payload(matched)
        tables_list = [payload] if payload else []
        text = _coalesce(_get_attr(matched, 'text'), '') or _table_text(payload)
        if text is None:
            text = ''
        needs_review = bool(_get_attr(matched, 'needs_review'))
        context.chunk_obj = None
        context.text = text
        context.needs_review = needs_review
        context.content_type = 'table'
        context.table_payload = payload if tables_list else None
        context.tables = tables_list
        return StepResult.continue_(context)

    async def _run_aggregate(
        self, context: Any, company_id: Any, version_id: Any, document_id: Any, page: Any
    ) -> StepResult:
        t_type = self._t_type(context)
        chunk_repo = self._chunk_repository
        text = ''
        needs_review = False
        content_type = 'text'
        table_payload: Any = None
        tables_list: list[Any] = []
        if chunk_repo is not None:
            try:
                chunks = await _await(
                    _call_chunk_list(chunk_repo, company_id, version_id, document_id, page)
                )
            except Exception:
                chunks = []
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
        rows = await self._list_raw_tables(context, company_id, version_id, document_id, page)
        for row in rows:
            payload = _table_to_payload(row)
            if payload is None:
                continue
            row_page = _get_attr(row, 'page', 'page_number')
            if page is not None and row_page is not None and int(row_page) != int(page):
                continue
            tables_list.append(payload)
        if tables_list:
            table_payload = tables_list[0]
            content_type = (
                'table' if text.strip() == '' or str(t_type or '').lower() == 'table' else 'text'
            )
        else:
            content_type = 'text'
        if table_payload is None and tables_list:
            table_payload = tables_list[0]
        if text is None:
            text = ''
        context.chunk_obj = None
        context.text = text
        context.needs_review = needs_review
        context.content_type = content_type
        context.table_payload = table_payload
        context.tables = tables_list
        return StepResult.continue_(context)

    async def run(self, context: Any) -> StepResult:
        self._ensure_highlight(context)
        company_id = self._context_value(context, 'company_id', 'companyId', 'tenant_id', 'company')
        version_id = self._context_value(context, 'version_id', 'versionId', 'version')
        document_id = self._context_value(context, 'document_id', 'documentId', 'doc_id')
        if document_id is None:
            version_obj = getattr(context, 'version_obj', None)
            if version_obj is not None:
                document_id = _get_attr(version_obj, 'document_id', 'documentId', 'doc_id')
        page_raw = self._context_value(context, 'page', 'page_number', 'pageNumber', 'page_no')
        page = _as_int(page_raw) if isinstance(page_raw, str) else page_raw
        table_id = self._context_value(context, 'table_id', 'tableId', 'table')
        chunk_id = self._context_value(context, 'chunk_id', 'chunkId', 'chunk')
        supplied = table_id if table_id is not None else chunk_id
        if supplied is None:
            return await self._run_aggregate(context, company_id, version_id, document_id, page)
        t_type = self._t_type(context)
        is_table = (
            table_id is not None
            or (isinstance(t_type, str) and t_type.lower() in {'table', 'tables'})
            or _looks_table_id(supplied)
        )
        if is_table:
            return await self._run_table(
                context, company_id, version_id, document_id, page, supplied
            )
        return await self._run_chunk(context, company_id, version_id, document_id, page, supplied)


__all__ = ['FetchContentStep']
