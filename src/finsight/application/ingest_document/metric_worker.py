"""Metric worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class MetricWorker(PipelineStepWorker):
    step_name = 'metric'
