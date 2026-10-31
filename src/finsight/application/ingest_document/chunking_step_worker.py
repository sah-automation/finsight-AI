"""Named ingestion step worker: chunking."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ChunkingStepWorker(PipelineStepWorker):
    step_name = 'chunking'
