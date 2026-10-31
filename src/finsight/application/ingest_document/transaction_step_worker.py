"""Named ingestion step worker: transaction."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class TransactionStepWorker(PipelineStepWorker):
    step_name = 'transaction'
