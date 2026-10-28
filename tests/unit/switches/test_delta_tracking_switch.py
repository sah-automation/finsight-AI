from __future__ import annotations

import pytest

from finsight.application.ingest_document.delta_worker import DeltaWorker as PipelineStepWorker
from finsight.core.types import CompanyId

CID = CompanyId('company-1')


@pytest.mark.switch
class TestDeltaTrackingSwitch:
    @pytest.mark.switch
    async def test_delta_tracking_on(self) -> None:
        worker = PipelineStepWorker(delta_tracking=True)
        result = await worker.handle(
            company_id=CID,
            version_id='version-1',
            key='company-1/documents/doc/versions/version-1/file.pdf',
            step='delta',
        )
        assert result['delta_tracking'] is True
        assert result['branch'] == 'delta'

    @pytest.mark.switch
    async def test_delta_tracking_off(self) -> None:
        worker = PipelineStepWorker(delta_tracking=False)
        result = await worker.handle(
            company_id=CID,
            version_id='version-1',
            key='company-1/documents/doc/versions/version-1/file.pdf',
            step='delta',
        )
        assert result['delta_tracking'] is False
        assert result['branch'] == 'full_reprocess'
