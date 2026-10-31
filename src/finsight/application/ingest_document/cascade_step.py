"""Named ingestion step: cascade."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CascadeStep(PipelineStepWorker):
    step_name = 'cascade'
