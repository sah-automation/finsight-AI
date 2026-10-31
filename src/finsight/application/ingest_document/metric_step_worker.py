"""Named ingestion step worker: metric."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class MetricStepWorker(PipelineStepWorker):
    step_name = 'metric'
