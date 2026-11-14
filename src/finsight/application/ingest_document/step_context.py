"""Typed, freely mutable pipeline step context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepContext:
    """Freely mutable context carrying a single ingestion run's state."""

    company_id: Any = None
    company: Any = None
    tenant_id: Any = None
    document_id: Any = None
    documentId: Any = None  # noqa: N815
    doc_id: Any = None
    version_id: Any = None
    document_version_id: Any = None
    id: Any = None
    version: Any = None
    document_version: Any = None
    key: Any = None
    object_key: Any = None
    s3_key: Any = None
    file_key: Any = None

    reader_result: Any = None
    metrics: Any = None
    chunks: Any = None
    chunk_entities: Any = None
    changed_chunk_entities: Any = None
    removed_chunk_ids: Any = None
    chunk_count: Any = None
    chunks_count: Any = None
    vectors: Any = None
    embedded_count: Any = None
    vector_count: Any = None
    delta_tracking: Any = None
    branch: Any = None

    state: Any = None
    status: Any = None
    committed: Any = None
    idempotent: Any = None
    idempotent_noop: Any = None
    extras: Any = None
    markers: Any = field(default_factory=dict)
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.company is not None and self.company_id is None:
            self.company_id = self.company
        if self.tenant_id is not None and self.company_id is None:
            self.company_id = self.tenant_id
        if self.company_id is not None and self.company is None:
            self.company = self.company_id
        if self.tenant_id is None and self.company_id is not None:
            self.tenant_id = self.company_id

        if self.documentId is not None and self.document_id is None:
            self.document_id = self.documentId
        if self.doc_id is not None and self.document_id is None:
            self.document_id = self.doc_id

        if self.document_version_id is not None and self.version_id is None:
            self.version_id = self.document_version_id
        if self.id is not None and self.version_id is None:
            self.version_id = self.id

        if self.document_version is not None and self.version is None:
            self.version = self.document_version

        if self.object_key is not None and self.key is None:
            self.key = self.object_key
        if self.s3_key is not None and self.key is None:
            self.key = self.s3_key
        if self.file_key is not None and self.key is None:
            self.key = self.file_key

        if self.chunks_count is not None and self.chunk_count is None:
            self.chunk_count = self.chunks_count

        if not isinstance(self.markers, dict):
            try:
                self.markers = dict(self.markers or {})
            except Exception:  # noqa: BLE001
                self.markers = {}
        if not isinstance(self.metadata, dict):
            try:
                self.metadata = dict(self.metadata or {})
            except Exception:  # noqa: BLE001
                self.metadata = {}
        if self.extras is None:
            self.extras = {}


PipelineContext = StepContext
PipelineStepContext = StepContext
IngestionContext = StepContext
IngestionStepContext = StepContext
Context = StepContext
StepState = StepContext
RunContext = StepContext


__all__ = [
    'Context',
    'IngestionContext',
    'IngestionStepContext',
    'PipelineContext',
    'PipelineStepContext',
    'RunContext',
    'StepContext',
    'StepState',
]
