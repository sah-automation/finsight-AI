"""Named ingestion step: chunk."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ChunkStep(PipelineStepWorker):
    step_name = 'chunk'
