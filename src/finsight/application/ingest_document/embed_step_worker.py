"""Named ingestion step worker: embed."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class EmbedStepWorker(PipelineStepWorker):
    step_name = 'embed'
