"""Contract tests: ingestion/embed step produces embedding spans (#288).

Proves that an upload/ingestion flow produces embedding spans carrying the
input chunk texts (visible in dev) with non-zero duration, correlated to the
request trace.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.adapters.embedding.traced_embedding import TracedEmbedding
from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.application.ingest_document.embed_step import EmbedStep
from finsight.core.config import load_config
from finsight.core.logging.context import bind_request_context, reset_request_context
from finsight.core.types import CompanyId

pytestmark = pytest.mark.contract

COMPANY = CompanyId('co-1')
TRACE_ID = 'req-ingest-1'


class _FakeEmbedder:
    async def embed(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return [[0.1, 0.2, 0.3]]


def _trace_id_of(span: Any) -> Any:
    return span.trace_id or span.attributes.get('trace_id')


def _embed_span(spans: list[Any]) -> Any:
    emb = [s for s in spans if 'genai.embedding.texts' in s.attributes]
    assert emb, 'expected an embedding span carrying input texts'
    return emb[0]


def test_ingest_embed_step_emits_embedding_span_with_input_texts() -> None:
    """The embed step emits an embedding span with the input texts and duration."""
    config = load_config('test')
    tracer = TracingAdapter(config=config, service_name='test', enabled=True)
    inner = _FakeEmbedder()
    embedded = TracedEmbedding(inner, tracing=tracer, config=config)
    embedded.config = config

    step = EmbedStep(
        embedding=embedded,
        chunk_repository=None,
        document_repository=None,
        config=config,
        state_store=None,
    )

    ctx = SimpleNamespace(
        company_id=COMPANY,
        version_id='v-1',
        key='co-1/documents/d-1/versions/v-1/file.pdf',
        chunks=['Revenue grew 12 percent year over year.'],
    )

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        asyncio.run(step.run(ctx))
    finally:
        reset_request_context(tokens)

    spans = tracer.emitted_spans(COMPANY)
    assert spans, 'expected at least one emitted span'
    emb = _embed_span(spans)
    assert emb.attributes.get('duration_ms', 0) > 0
    texts = emb.attributes.get('genai.embedding.texts')
    assert isinstance(texts, list) and texts
    assert any('Revenue grew 12 percent' in str(t) for t in texts)
    assert _trace_id_of(emb) == TRACE_ID
