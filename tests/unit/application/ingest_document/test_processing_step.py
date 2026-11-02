from __future__ import annotations

import asyncio
from types import SimpleNamespace

from finsight.application.ingest_document.processing_step import ProcessingStep


def test_processing_step_transitions_state_and_reports_status() -> None:
    step = ProcessingStep(config=None)
    ctx = SimpleNamespace(company_id='co', version_id='v1')

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.status == 'processing'
