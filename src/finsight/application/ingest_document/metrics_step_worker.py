"""Named ingestion step worker: metrics."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class MetricsStepWorker(PipelineStepWorker):
    step_name = 'metrics'
