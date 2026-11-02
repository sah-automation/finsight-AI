"""Compatibility alias for removed name-only step subclass (#165)."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker

ChunkStepWorker = PipelineStepWorker
