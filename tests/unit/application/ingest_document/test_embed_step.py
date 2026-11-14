from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from finsight.application.ingest_document.embed_step import EmbedStep


class _FakeEmbedder:
    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    async def embed(self, texts: Any, **kwargs: Any) -> list[list[float]]:
        return [[0.1] * self.dim for _ in texts]

    async def embed_text(self, texts: Any, **kwargs: Any) -> list[list[float]]:
        return [[0.1] * self.dim for _ in texts]

    async def embed_documents(self, texts: Any, **kwargs: Any) -> list[list[float]]:
        return [[0.1] * self.dim for _ in texts]

    async def encode(self, texts: Any, **kwargs: Any) -> list[list[float]]:
        return [[0.1] * self.dim for _ in texts]

    async def generate(self, texts: Any, **kwargs: Any) -> list[list[float]]:
        return [[0.1] * self.dim for _ in texts]


def test_embed_step_generates_vectors_for_chunks() -> None:
    embedder = _FakeEmbedder(dim=4)
    step = EmbedStep(embedding=embedder, chunk_repository=None, config=None)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
        chunks=['para one', 'para two'],
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.vectors is not None
    assert len(ctx.vectors) == 2
    assert all(len(v) == 4 for v in ctx.vectors)
    assert ctx.embedded_count == 2
    assert ctx.status == 'processing'


def test_embed_step_returns_committed_when_version_already_committed() -> None:
    embedder = _FakeEmbedder()
    step = EmbedStep(embedding=embedder, chunk_repository=None, config=None)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
        version=SimpleNamespace(state='committed'),
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.committed is True
    assert ctx.idempotent is True
    assert ctx.idempotent_noop is True


def test_embed_step_uses_existing_chunks_from_context() -> None:
    embedder = _FakeEmbedder(dim=4)
    step = EmbedStep(embedding=embedder, chunk_repository=None, config=None)
    ctx = SimpleNamespace(
        company_id='co',
        version_id='v1',
        document_id='doc1',
        key='co/documents/doc1/versions/v1',
        chunks=['existing chunk 1', 'existing chunk 2'],
    )

    result = asyncio.run(step.run(ctx))

    assert result is ctx
    assert ctx.vectors is not None
    assert len(ctx.vectors) == 2
    assert ctx.chunks == ['existing chunk 1', 'existing chunk 2']
