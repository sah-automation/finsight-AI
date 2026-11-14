"""Compatibility dispatch for document-table repository method aliases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .postgres_document_table_repository import PostgresDocumentTableRepository

_UPSERT_ALIASES = (
    'upsert',
    'save',
    'add',
    'create',
    'store',
    'persist',
    'insert',
    'update',
)


def _mark_handler(self: PostgresDocumentTableRepository) -> Any:
    async def _mark(*a: Any, **k: Any) -> Any:
        return await self._mark_inactive(*a, **k)

    return _mark


def _upsert_handler(self: PostgresDocumentTableRepository, lname: str) -> Any:
    async def _upsert(*a: Any, **k: Any) -> Any:
        if 'tables' in lname or 'rows' in lname or 'records' in lname:
            return await self.upsert_document_tables(*a, **k)
        if any(isinstance(v, (list, tuple, set)) for v in a):
            return await self.upsert_document_tables(*a, **k)
        return await self.upsert_document_table(*a, **k)

    return _upsert


def _plural_get_handler(self: PostgresDocumentTableRepository) -> Any:
    async def _plural_get_list(*a: Any, **k: Any) -> Any:
        return await self.list_document_tables(*a, **k)

    return _plural_get_list


def _get_handler(self: PostgresDocumentTableRepository) -> Any:
    async def _get_call(*a: Any, **k: Any) -> Any:
        return await self.get_document_table(*a, **k)

    return _get_call


def _list_handler(self: PostgresDocumentTableRepository) -> Any:
    async def _list_call(*a: Any, **k: Any) -> Any:
        return await self.list_document_tables(*a, **k)

    return _list_call


async def _getattr(self: PostgresDocumentTableRepository, name: str) -> Any:
    lname = name.lower()
    if name.startswith('_'):
        raise AttributeError(name)
    if 'inactive' in lname or 'deactiv' in lname or 'supersed' in lname or 'mark' in lname:
        return _mark_handler(self)
    if any(alias in lname for alias in _UPSERT_ALIASES):
        return _upsert_handler(self, lname)
    if lname.startswith('get') and 'tables' in lname:
        return _plural_get_handler(self)
    if lname.startswith('get') or 'fetch' in lname:
        return _get_handler(self)
    return _list_handler(self)
