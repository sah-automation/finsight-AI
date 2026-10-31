"""Named ingestion step: delta."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class DeltaStep(PipelineStepWorker):
    step_name = 'delta'
