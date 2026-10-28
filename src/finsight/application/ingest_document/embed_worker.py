"""Embed worker."""

from __future__ import annotations

from .pipeline_step_worker import PipelineStepWorker


class EmbedWorker(PipelineStepWorker):
    step_name = 'embed'
