from __future__ import annotations

import inspect

import pytest

from finsight.domain.ports import ChunkRepository

EXPECTED_OPERATIONS = {
    'delete_chunks_by_version',
    'get_chunk',
    'list_chunks_by_document',
    'list_chunks_by_version',
    'mark_chunks_inactive',
    'mark_version_chunks_inactive',
    'upsert_chunk',
    'upsert_chunks',
}


def _abstract_methods() -> dict[str, object]:
    return {
        name: member
        for name, member in inspect.getmembers(ChunkRepository, inspect.isfunction)
        if getattr(member, '__isabstractmethod__', False)
    }


def test_repository_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        ChunkRepository()  # type: ignore[abstract]


def test_repository_declares_the_chunk_lifecycle_operations() -> None:
    assert set(_abstract_methods()) == EXPECTED_OPERATIONS


def test_every_repository_method_requires_company_id() -> None:
    for name, member in _abstract_methods().items():
        parameters = list(inspect.signature(member).parameters)  # type: ignore[arg-type]
        assert parameters[0] == 'self', name
        assert parameters[1] == 'company_id', name
