"""Named ingestion step: transactional_save."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class TransactionalSaveStep(PipelineStepWorker):
    step_name = 'transactional_save'
