"""Shared helpers for PostgresDocumentTableRepository."""

from __future__ import annotations

import contextlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from finsight.domain.entities.document_table import DocumentTable

_TABLE = 'document_tables'

_RETURNING = (
    'id, company_id, document_id, version_id, page_number, positional_index, '
    'table_id, payload, html, needs_review, is_active, created_at, updated_at'
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _company(company_id: object) -> str:
    if company_id is None:
        raise ValueError('company_id is required for document table queries')
    return str(company_id)


def _is_table(value: object) -> bool:
    return isinstance(value, DocumentTable) or (
        hasattr(value, 'company_id') and hasattr(value, 'version_id') and hasattr(value, 'table_id')
    )


def _to_table(company_id: object, value: object = None, **kwargs: object) -> DocumentTable:
    company = _company(company_id)
    if isinstance(value, DocumentTable):
        if value.company_id is not None and str(value.company_id) != company:
            raise ValueError('document table company_id must match the repository tenant')
        if value.company_id is None:
            try:
                value.company_id = __import__(
                    'finsight.core.types', fromlist=['CompanyId']
                ).CompanyId(company)
            except Exception:
                from finsight.core.types import CompanyId

                value.company_id = CompanyId(company)
        if value.id is None:
            value.id = str(uuid.uuid4())
        return value
    if isinstance(value, dict):
        merged = dict(value)
        merged.update(kwargs)
        merged.setdefault('company_id', company)
        return DocumentTable(**merged)
    merged_kwargs = dict(kwargs)
    merged_kwargs.setdefault('company_id', company)
    if value is not None and not isinstance(value, (list, tuple, dict)):
        merged_kwargs.setdefault('payload', value)
    return DocumentTable(**merged_kwargs)


def _row_value(row: object, *names: str) -> object:
    mapping = getattr(row, '_mapping', None)
    if mapping is None and isinstance(row, dict):
        mapping = row
    if mapping is not None:
        for name in names:
            try:
                if name in mapping:
                    return mapping[name]
            except TypeError:
                continue
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _row_to_table(row: object | None) -> DocumentTable | None:
    if row is None:
        return None
    payload = _row_value(row, 'payload', 'payload_json')
    if isinstance(payload, str):
        with contextlib.suppress(TypeError, ValueError):
            payload = json.loads(payload)
    html = _row_value(row, 'html', 'html_text', 'table_html', 'html_content')
    page = _row_value(row, 'page_number', 'page', 'page_from')
    table_index = _row_value(row, 'positional_index', 'table_index', 'index', 'ordinal')
    needs_review = _row_value(row, 'needs_review')
    is_active = _row_value(row, 'is_active')
    return DocumentTable(
        id=_row_value(row, 'id', 'document_table_id'),
        company_id=_row_value(row, 'company_id'),
        document_id=_row_value(row, 'document_id'),
        version_id=_row_value(row, 'version_id', 'document_version_id'),
        page_number=page,
        index=table_index if table_index is not None else 0,
        table_id=_row_value(row, 'table_id'),
        payload=payload,
        html=html,
        needs_review=bool(needs_review) if needs_review is not None else False,
        is_active=True if is_active is None else bool(is_active),
        created_at=_row_value(row, 'created_at'),
        updated_at=_row_value(row, 'updated_at'),
    )


def _table_params(company: str, table: DocumentTable) -> dict[str, Any]:
    if table.company_id is not None and str(table.company_id) != company:
        raise ValueError('document table company_id must match the repository tenant')
    payload = table.payload
    if isinstance(payload, str):
        with contextlib.suppress(TypeError, ValueError):
            payload = json.loads(payload)
    page = table.page if table.page is not None else table.page_number
    index = table.index if table.index is not None else table.ordinal
    return {
        'id': str(table.id),
        'company_id': company,
        'document_id': _text(table.document_id),
        'version_id': _text(table.version_id),
        'page_number': page,
        'positional_index': int(index) if index is not None else 0,
        'table_id': _text(table.table_id),
        'payload': json.dumps(payload)
        if not isinstance(payload, str) and payload is not None
        else payload,
        'html': table.html,
        'needs_review': bool(table.needs_review),
        'is_active': bool(table.is_active),
    }


def _matches(row: DocumentTable, filters: dict[str, Any]) -> bool:
    if filters.get('version_ids'):
        if str(row.version_id) not in {str(x) for x in filters['version_ids']}:
            return False
    if filters.get('version_id') is not None:
        if str(row.version_id) != str(filters['version_id']):
            return False
    if filters.get('document_ids'):
        if str(row.document_id) not in {str(x) for x in filters['document_ids']}:
            return False
    if filters.get('document_id') is not None:
        if str(row.document_id) != str(filters['document_id']):
            return False
    if filters.get('page') is not None:
        if str(row.page if row.page is not None else row.page_number) != str(filters['page']):
            return False
    if filters.get('pages'):
        if str(row.page if row.page is not None else row.page_number) not in {
            str(x) for x in filters['pages']
        }:
            return False
    if filters.get('table_id') is not None:
        if str(row.table_id) != str(filters['table_id']):
            return False
    if filters.get('table_ids'):
        if str(row.table_id) not in {str(x) for x in filters['table_ids']} and str(row.id) not in {
            str(x) for x in filters['table_ids']
        }:
            return False
    if filters.get('needs_review') is not None:
        if bool(row.needs_review) != bool(filters['needs_review']):
            return False
    if filters.get('is_active') is not None:
        if bool(row.is_active) != bool(filters['is_active']):
            return False
    return not (
        filters.get('is_active') is None
        and filters.get('include_inactive') is False
        and not row.is_active
    )
