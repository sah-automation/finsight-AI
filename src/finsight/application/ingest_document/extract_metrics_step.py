"""Named ingestion step: extract_metrics."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ExtractMetricsStep(PipelineStepWorker):
    step_name = 'extract_metrics'
