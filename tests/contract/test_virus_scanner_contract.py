"""Contract tests for the VirusScanner port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.security.virus_scanner import VirusScanner
from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from finsight.domain.ports.virus_scanner import VirusScanner as VirusScannerPort

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')


@pytest.fixture
def scanner() -> VirusScannerPort:
    return VirusScanner(enabled=False)


class TestVirusScannerContract:
    async def test_disabled_scan_returns_clean(self, scanner: VirusScannerPort) -> None:
        result = await scanner.scan(COMPANY, 'object-key', bucket='documents')

        assert result is not None
        assert getattr(result, 'clean', False) is True

    async def test_scan_object_alias_behaves_like_scan(self, scanner: VirusScannerPort) -> None:
        result = await scanner.scan_object(COMPANY, 'object-key')

        assert getattr(result, 'clean', False) is True
