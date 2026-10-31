"""Named ingestion step worker: save_metrics."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class SaveMetricsStepWorker(PipelineStepWorker):
    step_name = 'save_metrics'
