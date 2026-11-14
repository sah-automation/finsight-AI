"""Contract tests for the DocumentReader port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.readers.pdf_plumber_reader import PdfPlumberReader
from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from finsight.domain.ports.document_reader import DocumentReader

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')


@pytest.fixture
def reader() -> DocumentReader:
    return PdfPlumberReader()


class TestDocumentReaderContract:
    async def test_empty_input_returns_an_empty_result(self, reader: DocumentReader) -> None:
        result = await reader.read(COMPANY, b'')

        assert result.text == ''
        assert result.tables == []
        assert result.page_numbers == []

    async def test_aliases_delegate_to_read(self, reader: DocumentReader) -> None:
        direct = await reader.read(COMPANY, b'')
        extracted = await reader.extract(COMPANY, b'')

        assert extracted.text == direct.text
