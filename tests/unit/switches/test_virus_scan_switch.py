from __future__ import annotations

import pytest

from finsight.adapters.security.virus_scanner import VirusScanner
from finsight.core.types import CompanyId


@pytest.mark.switch
class TestVirusScanSwitch:
    @pytest.mark.switch
    async def test_virus_scan_on(self) -> None:
        scanner = VirusScanner(virus_scan_enabled=True)
        result = await scanner.scan(
            CompanyId('company-1'),
            'company-1/documents/doc/versions/v1/file.pdf',
            content=b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE',
        )
        assert result.clean is False

    @pytest.mark.switch
    async def test_virus_scan_off(self) -> None:
        scanner = VirusScanner(virus_scan_enabled=False)
        result = await scanner.scan(
            CompanyId('company-1'),
            'company-1/documents/doc/versions/v1/file.pdf',
            content=b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE',
        )
        assert result.clean is True
        assert 'disabled' in str(result.detail).lower()
