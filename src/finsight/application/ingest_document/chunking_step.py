"""Named ingestion step: chunking."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ChunkingStep(PipelineStepWorker):
    step_name = 'chunking'
