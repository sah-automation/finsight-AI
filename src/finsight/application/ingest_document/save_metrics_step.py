"""Named ingestion step: save_metrics."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class SaveMetricsStep(PipelineStepWorker):
    step_name = 'save_metrics'
