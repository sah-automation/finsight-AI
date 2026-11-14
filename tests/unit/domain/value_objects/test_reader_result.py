from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from finsight.domain.value_objects import ReaderResult

EXPECTED_CONFIDENCE = 0.5


def test_reader_result_carries_fields() -> None:
    result = ReaderResult(text='hello', tables=[{'t': 1}], page_numbers=[1, 2], confidence=0.5)
    assert result.text == 'hello'
    assert result.tables == [{'t': 1}]
    assert result.page_numbers == [1, 2]
    assert result.confidence == EXPECTED_CONFIDENCE


def test_reader_result_is_frozen() -> None:
    result = ReaderResult(text='hello')
    with pytest.raises(FrozenInstanceError):
        result.text = 'changed'


def test_reader_result_defaults() -> None:
    result = ReaderResult()
    assert result.text == ''
    assert result.tables == []
    assert result.page_numbers == []
    assert result.confidence is None
    assert result.locators == []


def test_reader_result_carries_locators() -> None:
    locators = [{'page': 1, 'sheet': 'A1'}]
    result = ReaderResult(locators=locators)
    assert result.locators == locators


def test_reader_result_tolerates_missing_locators() -> None:
    result = ReaderResult(locators=None)
    assert result.locators == []


def test_reader_result_page_numbers_must_be_integers() -> None:
    with pytest.raises(TypeError):
        ReaderResult(page_numbers=[1.0])  # type: ignore[list-item]

    with pytest.raises(TypeError):
        ReaderResult(page_numbers=[True])  # type: ignore[list-item]
