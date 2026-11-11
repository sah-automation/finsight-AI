"""Contract tests: full content capture gated behind llm_content_capture_enabled (#277).

Runs against both TracingPort implementations (TracingAdapter, DisabledTracer)
and all three traced decorators (TracedLLM, TracedEmbedding, TracedReranker).
Asserts that GenAI content attributes appear only when the switch is on, that
sensitive fields are redacted even when capture is on, and that the redaction
blocklist is enforced by every tracer implementation.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.adapters.embedding.lite_llm_embedding import LiteLLMEmbedding
from finsight.adapters.embedding.metered_embedding import MeteredEmbedding
from finsight.adapters.embedding.retrying_embedding import RetryingEmbedding
from finsight.adapters.embedding.traced_embedding import TracedEmbedding
from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway
from finsight.adapters.llm.metered_llm import MeteredLLM
from finsight.adapters.llm.retrying_llm import RetryingLLM
from finsight.adapters.llm.traced_llm import TracedLLM
from finsight.adapters.rerank.cohere_reranker import CohereReranker
from finsight.adapters.rerank.metered_reranker import MeteredReranker
from finsight.adapters.rerank.retrying_reranker import RetryingReranker
from finsight.adapters.rerank.traced_reranker import TracedReranker
from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.core.config.models.switches_config import SwitchesConfig

pytestmark = pytest.mark.contract

COMPANY = 'company-a'


def _switches(capture: bool) -> SwitchesConfig:
    return SwitchesConfig(
        llm_content_capture_enabled=capture,
        detailed_tracing_enabled=True,
        usage_metering_enabled=True,
        reranker_enabled=True,
    )


def _config(capture: bool) -> SimpleNamespace:
    return SimpleNamespace(switches=_switches(capture))


def _make_tracers() -> dict[str, Any]:
    return {
        'TracingAdapter': TracingAdapter(service_name='test', enabled=True),
        'DisabledTracer': DisabledTracer(),
    }


async def _ok_completion(**kwargs: Any) -> list[dict[str, Any]]:
    return [{'choices': [{'delta': {'content': 'hello world'}}]}]


async def _ok_embedding(**kwargs: Any) -> dict[str, Any]:
    return {'data': [{'embedding': [0.1, 0.2]}]}


class _OkScorer:
    async def rerank(self, **kwargs: Any) -> list[dict[str, Any]]:
        documents = kwargs.get('documents') or []
        return [{'index': i, 'relevance_score': 1.0} for i in range(len(documents))]


def _rerank_config(capture: bool) -> SimpleNamespace:
    return SimpleNamespace(
        reranker=SimpleNamespace(
            model='rerank-test',
            provider='cohere',
            top_n=20,
            timeout_seconds=5,
            max_retries=1,
            batch_size=2,
        ),
        retrieval=SimpleNamespace(
            evidence_min_score=0.30,
            evidence_min_search_score=0.50,
            evidence_min_chunks=1,
        ),
        switches=_switches(capture),
    )


# ---------------------------------------------------------------- LLM
@pytest.mark.parametrize('capture', [True, False])
@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_traced_llm_content_capture_gating(tracer_name: str, capture: bool) -> None:
    tracer = _make_tracers()[tracer_name]
    cfg = _config(capture)
    provider = LiteLLMGateway(
        completion_func=_ok_completion, model='test-model', max_retries=0, config=cfg
    )
    traced = TracedLLM(MeteredLLM(RetryingLLM(provider, retries=0), metering=None), tracing=tracer)

    asyncio.run(
        traced.complete(
            COMPANY,
            messages=[{'role': 'user', 'content': 'ask me'}],
            prompt='ask me',
            question='ask me',
        )
    )

    attrs = tracer.emitted_spans(COMPANY)[0].attributes
    if capture:
        assert 'genai.request.messages' in attrs or 'genai.response.messages' in attrs
    else:
        assert 'genai.request.messages' not in attrs
        assert 'genai.response.messages' not in attrs


# ---------------------------------------------------------------- Embedding
@pytest.mark.parametrize('capture', [True, False])
@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_traced_embedding_content_capture_gating(tracer_name: str, capture: bool) -> None:
    tracer = _make_tracers()[tracer_name]
    cfg = _config(capture)
    provider = LiteLLMEmbedding(
        embedding_func=_ok_embedding, model_id='test-model', dimensions=2, config=cfg
    )
    traced = TracedEmbedding(
        MeteredEmbedding(RetryingEmbedding(provider), metering=None), tracing=tracer
    )

    asyncio.run(traced.embed(COMPANY, text='chunk text here'))

    attrs = tracer.emitted_spans(COMPANY)[0].attributes
    if capture:
        assert 'genai.embedding.texts' in attrs
        assert 'chunk text here' in str(attrs['genai.embedding.texts'])
    else:
        assert 'genai.embedding.texts' not in attrs


# ---------------------------------------------------------------- Rerank
@pytest.mark.parametrize('capture', [True, False])
@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_traced_reranker_content_capture_gating(tracer_name: str, capture: bool) -> None:
    tracer = _make_tracers()[tracer_name]
    cfg = _rerank_config(capture)
    provider = CohereReranker(client=_OkScorer(), config=cfg)
    traced = TracedReranker(
        MeteredReranker(RetryingReranker(provider, retries=1), metering=None), tracing=tracer
    )

    asyncio.run(
        traced.rerank(
            COMPANY, question='which?', candidates=[{'company_id': COMPANY, 'text': 'doc text'}]
        )
    )

    attrs = tracer.emitted_spans(COMPANY)[0].attributes
    if capture:
        assert 'genai.rerank.query' in attrs or 'genai.rerank.candidates' in attrs
    else:
        assert 'genai.rerank.query' not in attrs
        assert 'genai.rerank.candidates' not in attrs


# ---------------------------------------------------------------- Redaction blocklist coverage
SENSITIVE_FIELDS = [
    'question',
    'chunk_text',
    'answer',
    'pii',
    'credentials',
    'signed_url',
    'secret',
    'token',
    'password',
    'prompt',
    'raw_text',
    'document_text',
    'api_key',
    'email',
    'phone',
    'address',
    'ssn',
    'credit_card',
    'authorization',
]


@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
@pytest.mark.parametrize('field', SENSITIVE_FIELDS)
def test_redaction_blocklist_coverage(tracer_name: str, field: str) -> None:
    tracer = _make_tracers()[tracer_name]
    asyncio.run(
        tracer.start_span(
            COMPANY, 'op', attributes={field: 'leaky-value', 'safe_field': 'ok-value'}
        )
    )
    attrs = tracer.emitted_spans(COMPANY)[0].attributes
    assert field not in attrs, f'sensitive field {field!r} leaked into span attributes'
    assert attrs.get('safe_field') == 'ok-value'


@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_disabled_tracer_redacts_sensitive_fields(tracer_name: str) -> None:
    tracer = _make_tracers()[tracer_name]
    asyncio.run(
        tracer.start_span(COMPANY, 'op', attributes={'question': 'secret q', 'model_name': 'm'})
    )
    attrs = tracer.emitted_spans(COMPANY)[0].attributes
    assert 'question' not in attrs
    assert attrs.get('model_name') == 'm'


@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_content_capture_redacts_sensitive_nested_field(tracer_name: str) -> None:
    """When capture is on, sensitive nested fields inside content are redacted."""
    tracer = _make_tracers()[tracer_name]
    cfg = _config(True)
    provider = LiteLLMGateway(
        completion_func=_ok_completion, model='test-model', max_retries=0, config=cfg
    )
    traced = TracedLLM(
        MeteredLLM(RetryingLLM(provider, retries=0), metering=None),
        tracing=tracer,
    )
    asyncio.run(
        traced.complete(
            COMPANY,
            messages=[{'role': 'user', 'content': 'hi', 'credentials': 'leak'}],
            prompt='hi',
            question='hi',
        )
    )
    attrs = tracer.emitted_spans(COMPANY)[0].attributes
    if 'genai.request.messages' in attrs:
        serialized = str(attrs['genai.request.messages'])
        assert 'leak' not in serialized
        assert 'credentials' not in serialized
