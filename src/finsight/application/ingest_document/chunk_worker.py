"""Chunk worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class ChunkWorker(PipelineStepWorker):
    step_name = 'chunk'
