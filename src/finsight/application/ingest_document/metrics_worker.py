"""Metrics worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class MetricsWorker(PipelineStepWorker):
    step_name = 'metrics'
