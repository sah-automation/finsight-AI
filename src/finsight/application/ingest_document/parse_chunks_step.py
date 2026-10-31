"""Named ingestion step: parse_chunks."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ParseChunksStep(PipelineStepWorker):
    step_name = 'parse_chunks'
