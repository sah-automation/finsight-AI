"""Compatibility re-export module for ingestion pipeline workers."""

from __future__ import annotations

from .ingestion_pipeline import IngestionPipeline
from .ingestion_worker import IngestionWorker
from .ingestion_workers import IngestionWorkers
from .pipeline_step_worker import PipelineStepWorker

# Compatibility aliases for removed name-only step subclasses (#165).
PipelineWorker = PipelineStepWorker
StepWorker = PipelineStepWorker
ReadWorker = PipelineStepWorker
ParseWorker = PipelineStepWorker
ExtractWorker = PipelineStepWorker
ReadStepWorker = PipelineStepWorker
DeltaWorker = PipelineStepWorker
ChunkWorker = PipelineStepWorker
ChunkingWorker = PipelineStepWorker
ParseChunksWorker = PipelineStepWorker
EmbedWorker = PipelineStepWorker
EmbeddingWorker = PipelineStepWorker
SaveWorker = PipelineStepWorker
CommitWorker = PipelineStepWorker
PersistWorker = PipelineStepWorker
TransactionWorker = PipelineStepWorker
TransactionalSaveWorker = PipelineStepWorker
CascadeWorker = PipelineStepWorker
PostProcessWorker = PipelineStepWorker
FinalizeWorker = PipelineStepWorker
AfterCommitWorker = PipelineStepWorker
MetricWorker = PipelineStepWorker
MetricsWorker = PipelineStepWorker
ExtractMetricsWorker = PipelineStepWorker
SaveMetricsWorker = PipelineStepWorker
CacheWorker = PipelineStepWorker
CacheClearWorker = PipelineStepWorker
ClearCacheWorker = PipelineStepWorker
AnswerCacheWorker = PipelineStepWorker
DeltaTrackingCheckWorker = PipelineStepWorker
ProcessingWorker = PipelineStepWorker

# Backwards-compatible names formerly exported from name-only modules.
CommitStep = PipelineStepWorker
ExtractStep = PipelineStepWorker
FinalizeStep = PipelineStepWorker
MetricsStep = PipelineStepWorker
ParseStep = PipelineStepWorker
ParseChunksStep = PipelineStepWorker
PersistStep = PipelineStepWorker
PostProcessStep = PipelineStepWorker
TransactionStep = PipelineStepWorker
TransactionalSaveStep = PipelineStepWorker
AnswerCacheStep = PipelineStepWorker
ClearCacheStep = PipelineStepWorker
ExtractMetricsStep = PipelineStepWorker
SaveMetricsStep = PipelineStepWorker
ChunkingStep = PipelineStepWorker
EmbeddingStep = PipelineStepWorker
CacheClearStep = PipelineStepWorker

__all__ = [
    'IngestionPipeline',
    'IngestionWorker',
    'IngestionWorkers',
    'PipelineStepWorker',
]
