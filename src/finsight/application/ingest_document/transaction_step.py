"""Named ingestion step: transaction."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class TransactionStep(PipelineStepWorker):
    step_name = 'transaction'
