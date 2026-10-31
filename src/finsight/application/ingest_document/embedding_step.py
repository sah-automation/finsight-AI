"""Named ingestion step: embedding."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class EmbeddingStep(PipelineStepWorker):
    step_name = 'embedding'
