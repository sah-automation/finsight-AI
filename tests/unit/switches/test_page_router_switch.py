from __future__ import annotations

import pytest

from finsight.adapters.readers.page_router import PageRouter
from finsight.adapters.readers.pdfplumber_reader import PdfPlumberReader
from finsight.core.types import CompanyId


@pytest.mark.switch
class TestPageRouterSwitch:
    @pytest.mark.switch
    async def test_page_router_on(self) -> None:
        primary = PdfPlumberReader()
        table = PdfPlumberReader()
        router = PageRouter(
            reader=primary,
            table_reader=table,
            page_router_enabled=True,
        )
        assert router.page_router_enabled is True
        assert router.enabled is True
        assert router.routed is True

    @pytest.mark.switch
    async def test_page_router_off(self) -> None:
        primary = PdfPlumberReader()
        router = PageRouter(
            reader=primary,
            page_router_enabled=False,
        )
        assert router.page_router_enabled is False
        assert router.enabled is False
        result = await router.read(
            CompanyId('company-1'),
            file_path='tests/fixtures/documents/pdf__company-a__2025-FY__annual-report.pdf',
        )
        assert result.page_numbers
