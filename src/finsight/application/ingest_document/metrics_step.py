"""Named ingestion step: metrics."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class MetricsStep(PipelineStepWorker):
    step_name = 'metrics'
