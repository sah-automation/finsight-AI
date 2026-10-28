from __future__ import annotations

import pytest

from finsight.domain.value_objects import ReaderResult


def test_reader_result_carries_fields() -> None:
    result = ReaderResult(text='hello', tables=[{'t': 1}], page_numbers=[1, 2], confidence=0.5)
    assert result.text == 'hello'
    assert result.tables == [{'t': 1}]
    assert result.page_numbers == [1, 2]
    assert result.confidence == 0.5


def test_reader_result_is_frozen() -> None:
    result = ReaderResult(text='hello')
    with pytest.raises(Exception):
        result.text = 'changed'


def test_reader_result_defaults() -> None:
    result = ReaderResult()
    assert result.text == ''
    assert result.tables == []
    assert result.page_numbers == []
    assert result.confidence is None
