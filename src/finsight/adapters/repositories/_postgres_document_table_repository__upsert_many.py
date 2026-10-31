"""Auto-extracted helper for PostgresDocumentTableRepository._upsert_many."""

from __future__ import annotations

import uuid
from typing import (
    TYPE_CHECKING,
    Any,
)

from finsight.domain.entities.document_table import DocumentTable

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_document_table_repository_shared import (
    _RETURNING,
    _company,
    _row_to_table,
    _table_params,
    _to_table,
    _utcnow,
)

if TYPE_CHECKING:
    import builtins


if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository


async def _upsert_many(
    self: PostgresDocumentTableRepository, company_id: object, tables: object = None, **kwargs: Any
) -> builtins.list[DocumentTable]:
    company = _company(company_id)

    if tables is None:
        tables = kwargs.pop(
            'tables',
            kwargs.pop(
                'rows',
                kwargs.pop('records', kwargs.pop('items', kwargs.pop('documents', None))),
            ),
        )

    if tables is None:
        tables = []
    if (
        isinstance(tables, DocumentTable)
        or (
            isinstance(tables, dict)
            and (
                'table_id' in tables
                or 'payload' in tables
                or 'id' in tables
                or 'version_id' in tables
            )
        )
        or not isinstance(tables, (list, tuple, set))
    ):
        tables = [tables]

    if (
        not tables
        and kwargs
        and any(k in kwargs for k in ('table_id', 'payload', 'html', 'version_id', 'document_id'))
    ):
        tables = [dict(kwargs)]

    override_keys = (
        'version_id',
        'version',
        'document_id',
        'document',
        'page',
        'page_number',
        'index',
        'table_id',
        'payload',
        'html',
        'needs_review',
        'is_active',
    )
    normalized: builtins.list[DocumentTable] = []
    for item in tables:
        merged_item = item
        if isinstance(item, dict):
            merged_item = dict(item)
            for key in override_keys:
                if key in kwargs and key not in merged_item:
                    merged_item[key] = kwargs[key]
        table = _to_table(company, merged_item)
        if 'version' in kwargs and 'version_id' not in kwargs:
            if kwargs.get('version') is not None:
                table.version_id = str(kwargs.get('version'))
        if 'page_number' in kwargs and (table.page is None):
            try:
                table.page = kwargs.get('page_number')
                table.page_number = kwargs.get('page_number')
            except Exception:
                pass
        normalized.append(table)

    saved: builtins.list[DocumentTable] = []
    if self._session is None:
        store = self._memory.setdefault(company, {})
        for table in normalized:
            if table.company_id is None:
                table.company_id = __import__(
                    'finsight.core.types', fromlist=['CompanyId']
                ).CompanyId(company)
            if str(table.company_id) != company:
                raise ValueError('document table company_id must match the repository tenant')
            if table.id is None:
                table.id = str(uuid.uuid4())
            table.id = str(table.id)
            table.document_table_id = table.id
            existing_id = None
            for rid, row in store.items():
                if str(row.version_id) == str(table.version_id) and str(row.table_id) == str(
                    table.table_id
                ):
                    existing_id = rid
                    break
            if existing_id is not None:
                table.id = existing_id
                table.document_table_id = existing_id
                table.row_id = existing_id
                table.table_row_id = existing_id
            if table.created_at is None:
                table.created_at = _utcnow()
            if table.updated_at is None:
                table.updated_at = _utcnow()
            store[table.id] = table
            saved.append(table)
        return saved

    await self._set_rls_context(company)
    for table in normalized:
        params = _table_params(company, table)
        result = await self._execute(
            'INSERT INTO document_tables '
            '(id, company_id, document_id, version_id, page_number, positional_index, '
            'table_id, payload, html, needs_review, is_active) '
            'VALUES (:id, :company_id, :document_id, :version_id, :page_number, '
            ':positional_index, :table_id, :payload::jsonb, :html, :needs_review, :is_active) '
            'ON CONFLICT (company_id, version_id, table_id) DO UPDATE SET '
            'document_id = EXCLUDED.document_id, '
            'page_number = EXCLUDED.page_number, '
            'positional_index = EXCLUDED.positional_index, '
            'payload = EXCLUDED.payload, '
            'html = EXCLUDED.html, '
            'needs_review = EXCLUDED.needs_review, '
            'is_active = EXCLUDED.is_active, '
            'updated_at = now() '
            'RETURNING ' + _RETURNING,
            params,
        )
        saved.append(_row_to_table(await self._fetchone(result)) or table)
    return saved
