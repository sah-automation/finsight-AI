"""Named ingestion step worker: embedding."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class EmbeddingStepWorker(PipelineStepWorker):
    step_name = 'embedding'
