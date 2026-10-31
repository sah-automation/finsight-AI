"""Named ingestion step: persist."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class PersistStep(PipelineStepWorker):
    step_name = 'persist'
