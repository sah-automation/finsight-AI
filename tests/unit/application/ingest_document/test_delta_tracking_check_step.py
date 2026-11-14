from __future__ import annotations

import asyncio
from types import SimpleNamespace

from finsight.application.ingest_document.delta_tracking_check_step import DeltaTrackingCheckStep


def test_delta_tracking_check_reports_status_without_touching_data() -> None:
    cfg = SimpleNamespace(documents=SimpleNamespace(delta_tracking=False))
    step = DeltaTrackingCheckStep(config=cfg)
    ctx = SimpleNamespace()

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.delta_tracking is False
    assert ctx.status == 'ok'


def test_delta_tracking_check_defaults_true() -> None:
    step = DeltaTrackingCheckStep()
    ctx = SimpleNamespace()

    asyncio.run(step.run(ctx))

    assert ctx.delta_tracking is True
