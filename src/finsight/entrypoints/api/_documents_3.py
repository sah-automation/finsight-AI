# ruff: noqa: I001, F403, F405
from __future__ import annotations
from typing import Any
from fastapi import Body
from ._documents_0 import *
from ._documents_1 import *
from ._documents_2 import *

list_document = list_documents
search_document = search_documents
get_documents = list_documents
delete_documents = delete_document
restore_documents = restore_document
purge_documents = purge_document
recycle = recycle_bin
trash = recycle_bin
trash_bin = recycle_bin
deleted_documents = recycle_bin
metadata = get_document


async def health() -> dict[str, str]:
    return {'status': 'ok'}


async def http_list(context: Any = None) -> Any:
    return await _handle(context, context=context)


async def http_get(document_id: str, context: Any = None) -> Any:
    return await _handle({'document_id': document_id}, context=context, action='get')


async def http_create(payload: Any = Body(default=None), context: Any = None) -> Any:
    return await _handle(payload, context=context)


async def http_delete(document_id: str, context: Any = None) -> Any:
    return await _handle({'document_id': document_id}, context=context, action='delete')


__all__ = [
    'delete_documents',
    'deleted_documents',
    'get_documents',
    'health',
    'http_create',
    'http_delete',
    'http_get',
    'http_list',
    'list_document',
    'metadata',
    'purge_documents',
    'recycle',
    'restore_documents',
    'search_document',
    'trash',
    'trash_bin',
]
