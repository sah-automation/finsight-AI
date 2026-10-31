"""Named ingestion step worker: cascade."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class CascadeStepWorker(PipelineStepWorker):
    step_name = 'cascade'
