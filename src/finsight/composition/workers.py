"""Composition helper."""

from __future__ import annotations

from typing import Any


def build_scan_worker(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.scan_worker import ScanWorker

    return ScanWorker(*args, **kwargs)


def get_scan_worker(*args: Any, **kwargs: Any) -> Any:
    return build_scan_worker(*args, **kwargs)


def create_scan_worker(*args: Any, **kwargs: Any) -> Any:
    return build_scan_worker(*args, **kwargs)


def build_ingestion_worker(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.ingestion_pipeline import IngestionPipeline

    return IngestionPipeline(*args, **kwargs)


def get_ingestion_worker(*args: Any, **kwargs: Any) -> Any:
    return build_ingestion_worker(*args, **kwargs)


def create_ingestion_worker(*args: Any, **kwargs: Any) -> Any:
    return build_ingestion_worker(*args, **kwargs)


def build_ingestion_pipeline(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.ingestion_pipeline import IngestionPipeline

    return IngestionPipeline(*args, **kwargs)


def build_pipeline_worker(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.pipeline_worker import PipelineWorker

    return PipelineWorker(*args, **kwargs)


def build_read_worker(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.read_worker import ReadWorker

    return ReadWorker(*args, **kwargs)


def build_chunk_worker(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.chunk_worker import ChunkWorker

    return ChunkWorker(*args, **kwargs)


def build_embed_worker(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.embed_worker import EmbedWorker

    return EmbedWorker(*args, **kwargs)


def build_save_worker(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.save_worker import SaveWorker

    return SaveWorker(*args, **kwargs)


def build_cascade_worker(*args: Any, **kwargs: Any) -> Any:
    from finsight.application.ingest_document.cascade_worker import CascadeWorker

    return CascadeWorker(*args, **kwargs)


def __getattr__(name: str) -> object:
    import importlib

    m = importlib.import_module('finsight.application.ingest_document.scan_worker')
    return m.ScanWorker
