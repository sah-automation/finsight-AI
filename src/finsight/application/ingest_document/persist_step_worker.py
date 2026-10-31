"""Named ingestion step worker: persist."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class PersistStepWorker(PipelineStepWorker):
    step_name = 'persist'
