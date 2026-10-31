"""Named ingestion step worker: transactional_save."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class TransactionalSaveStepWorker(PipelineStepWorker):
    step_name = 'transactional_save'
