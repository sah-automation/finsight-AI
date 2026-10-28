"""Entrypoint worker compatibility module."""

from __future__ import annotations

from finsight.application.ingest_document.pipeline import *  # noqa: F403
from finsight.application.ingest_document.scan_worker import *  # noqa: F403


def __getattr__(name: str) -> object:
    import importlib

    m = importlib.import_module('finsight.application.ingest_document.embed_worker')
    return m.EmbedWorker
