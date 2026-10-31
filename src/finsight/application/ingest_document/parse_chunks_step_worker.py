"""Named ingestion step worker: parse_chunks."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ParseChunksStepWorker(PipelineStepWorker):
    step_name = 'parse_chunks'
