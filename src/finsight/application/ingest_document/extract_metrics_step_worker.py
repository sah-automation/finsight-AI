"""Named ingestion step worker: extract_metrics."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ExtractMetricsStepWorker(PipelineStepWorker):
    step_name = 'extract_metrics'
