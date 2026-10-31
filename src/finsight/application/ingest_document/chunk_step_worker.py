"""Named ingestion step worker: chunk."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ChunkStepWorker(PipelineStepWorker):
    step_name = 'chunk'
