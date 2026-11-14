from __future__ import annotations

import pytest

from finsight.core.types import CompanyId
from finsight.domain.services import DocumentStamp

SHA256_HEX_LENGTH = 64


def test_initial_stamp_is_deterministic_and_hex() -> None:
    first = DocumentStamp.initial(CompanyId('company-a'))
    second = DocumentStamp.initial(CompanyId('company-a'))

    assert first == second
    assert first.company_id == 'company-a'
    assert first.generation == 0
    assert len(first.value) == SHA256_HEX_LENGTH
    assert set(first.value) <= set('0123456789abcdef')


def test_initial_stamp_differs_per_company() -> None:
    assert (
        DocumentStamp.initial(CompanyId('company-a')).value
        != DocumentStamp.initial(CompanyId('company-b')).value
    )


def test_same_document_versions_keep_the_same_stamp() -> None:
    versions = {'doc-1': 'v1', 'doc-2': 'v3'}

    first = DocumentStamp.from_versions(CompanyId('company-a'), versions)
    second = DocumentStamp.from_versions(CompanyId('company-a'), versions)

    assert first.value == second.value


def test_changed_version_changes_the_stamp() -> None:
    previous = DocumentStamp.from_versions(CompanyId('company-a'), {'doc-1': 'v1'})
    updated = DocumentStamp.from_versions(CompanyId('company-a'), {'doc-1': 'v2'})

    assert previous.value != updated.value


def test_added_and_removed_documents_change_the_stamp() -> None:
    base = {'doc-1': 'v1'}
    added = {**base, 'doc-2': 'v1'}
    removed = {}

    base_stamp = DocumentStamp.from_versions(CompanyId('company-a'), base)

    assert DocumentStamp.from_versions(CompanyId('company-a'), added).value != base_stamp.value
    assert DocumentStamp.from_versions(CompanyId('company-a'), removed).value != base_stamp.value


def test_document_order_does_not_change_the_stamp() -> None:
    first = DocumentStamp.from_versions(CompanyId('company-a'), {'doc-1': 'v1', 'doc-2': 'v2'})
    second = DocumentStamp.from_versions(CompanyId('company-a'), {'doc-2': 'v2', 'doc-1': 'v1'})

    assert first.value == second.value


def test_updated_for_always_advances_even_with_no_state_change() -> None:
    versions = {'doc-1': 'v1'}
    stamp = DocumentStamp.from_versions(CompanyId('company-a'), versions)

    next_stamp = stamp.updated_for(versions)

    assert next_stamp.generation == stamp.generation + 1
    assert next_stamp.value != stamp.value
    assert next_stamp.company_id == stamp.company_id


def test_missing_company_id_fails_loudly() -> None:
    with pytest.raises(ValueError, match='company_id'):
        DocumentStamp.initial(CompanyId(''))


def test_blank_document_marker_fails_loudly() -> None:
    with pytest.raises(ValueError, match='version marker'):
        DocumentStamp.from_versions(CompanyId('company-a'), {'doc-1': ' '})


def test_negative_generation_fails_loudly() -> None:
    with pytest.raises(ValueError, match='generation'):
        DocumentStamp.from_versions(CompanyId('company-a'), generation=-1)
