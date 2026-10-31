"""Named ingestion step: metric."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class MetricStep(PipelineStepWorker):
    step_name = 'metric'
