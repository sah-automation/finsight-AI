"""Adapter decorator stack factories."""

from __future__ import annotations

import importlib
from typing import Any


def _existing(kwargs: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in kwargs and kwargs.get(key) is not None:
            return kwargs.get(key)
    return None


def resolve_config(*args: Any, **kwargs: Any) -> Any:
    from .container import resolve_config as _resolve_config

    return _resolve_config(*args, **kwargs)


def build_metering(*args: Any, **kwargs: Any) -> Any:
    from .container import build_metering as _build_metering

    return _build_metering(*args, **kwargs)


def build_tracing(*args: Any, **kwargs: Any) -> Any:
    from .container import build_tracing as _build_tracing

    return _build_tracing(*args, **kwargs)


def _stack_switch(config: Any, name: str, default: bool = True) -> bool:
    if config is None:
        return default
    switches = getattr(config, 'switches', None)
    if switches is None and isinstance(config, dict):
        switches = config.get('switches')
    if isinstance(switches, dict):
        value = switches.get(name, default)
    elif switches is not None:
        value = getattr(switches, name, default)
    else:
        value = getattr(config, name, default)
    if isinstance(value, str):
        return value.strip().lower() in {'true', 'yes', '1', 'on', 'enabled'}
    return bool(value) if value is not None else default


def _build_llm_stack(*args: Any, **kwargs: Any) -> Any:
    config = None
    try:
        config = resolve_config(*args, **kwargs)
    except Exception:
        config = kwargs.get('config')
    _llm_gw = importlib.import_module('finsight.adapters.llm.lite_llm_gateway')
    _llm_metered = importlib.import_module('finsight.adapters.llm.metered_llm')
    _llm_retrying = importlib.import_module('finsight.adapters.llm.retrying_llm')
    _llm_traced = importlib.import_module('finsight.adapters.llm.traced_llm')
    LiteLLMGateway = _llm_gw.LiteLLMGateway
    MeteredLLM = _llm_metered.MeteredLLM
    RetryingLLM = _llm_retrying.RetryingLLM
    TracedLLM = _llm_traced.TracedLLM
    _extra = dict(kwargs)
    for _drop in (
        'config',
        'settings',
        'configuration',
        'app_config',
        'session',
        'db_session',
        'container',
        'composition',
        'root',
        'app',
        'context',
    ):
        _extra.pop(_drop, None)
    metering = _extra.pop('metering', None)
    if metering is None:
        try:
            metering = _existing(_extra, 'metering', 'meter', 'metering_port')
        except Exception:
            metering = None
    if metering is None and _stack_switch(config, 'usage_metering_enabled', True):
        metering = build_metering(config=config, **_extra)
    tracing = _extra.pop('tracing', None)
    if tracing is None:
        try:
            tracing = _existing(
                _extra, 'tracing', 'tracer', 'tracing_port', 'span_tracer', 'span_tracing'
            )
        except Exception:
            tracing = None
    if tracing is None and _stack_switch(config, 'detailed_tracing_enabled', True):
        tracing = build_tracing(config=config, **_extra)

    retries = 1
    llm_cfg = getattr(config, 'llm', None)
    primary = getattr(llm_cfg, 'primary_model', None) if llm_cfg is not None else None
    if primary is not None:
        retries = int(getattr(primary, 'max_retries', retries) or retries)
    provider = LiteLLMGateway(config=config, metering=None, **_extra)
    retrying = RetryingLLM(provider, retries=retries)
    metered = MeteredLLM(retrying, metering=metering)
    return TracedLLM(metered, tracing=tracing)


def _build_embedding_stack(*args: Any, **kwargs: Any) -> Any:
    config = None
    try:
        config = resolve_config(*args, **kwargs)
    except Exception:
        config = kwargs.get('config')
    _emb_gw = importlib.import_module('finsight.adapters.embedding.lite_llm_embedding')
    _emb_metered = importlib.import_module('finsight.adapters.embedding.metered_embedding')
    _emb_retrying = importlib.import_module('finsight.adapters.embedding.retrying_embedding')
    _emb_traced = importlib.import_module('finsight.adapters.embedding.traced_embedding')
    LiteLLMEmbedding = _emb_gw.LiteLLMEmbedding
    MeteredEmbedding = _emb_metered.MeteredEmbedding
    RetryingEmbedding = _emb_retrying.RetryingEmbedding
    TracedEmbedding = _emb_traced.TracedEmbedding
    _extra = dict(kwargs)
    for _drop in (
        'config',
        'settings',
        'configuration',
        'app_config',
        'session',
        'db_session',
        'container',
        'composition',
        'root',
        'app',
        'context',
    ):
        _extra.pop(_drop, None)
    metering = _extra.pop('metering', None)
    if metering is None:
        try:
            metering = _existing(_extra, 'metering', 'meter', 'metering_port')
        except Exception:
            metering = None
    if metering is None and _stack_switch(config, 'usage_metering_enabled', True):
        metering = build_metering(config=config, **_extra)
    tracing = _extra.pop('tracing', None)
    if tracing is None:
        try:
            tracing = _existing(
                _extra, 'tracing', 'tracer', 'tracing_port', 'span_tracer', 'span_tracing'
            )
        except Exception:
            tracing = None
    if tracing is None and _stack_switch(config, 'detailed_tracing_enabled', True):
        tracing = build_tracing(config=config, **_extra)
    _remb = importlib.import_module('finsight.adapters.embedding.retrying_embedding')
    RetryingEmbedding = _remb.RetryingEmbedding

    provider = LiteLLMEmbedding(config=config, metering=None, **_extra)
    retrying = RetryingEmbedding(provider)
    metered = MeteredEmbedding(retrying, metering=metering)
    return TracedEmbedding(metered, tracing=tracing)


def _build_reranker_stack(*args: Any, **kwargs: Any) -> Any:
    config = None
    try:
        config = resolve_config(*args, **kwargs)
    except Exception:
        config = kwargs.get('config')
    _rerk_provider = importlib.import_module('finsight.adapters.rerank.cohere_reranker')
    _rerk_metered = importlib.import_module('finsight.adapters.rerank.metered_reranker')
    _rerk_retrying = importlib.import_module('finsight.adapters.rerank.retrying_reranker')
    _rerk_traced = importlib.import_module('finsight.adapters.rerank.traced_reranker')
    CohereReranker = _rerk_provider.CohereReranker
    MeteredReranker = _rerk_metered.MeteredReranker
    RetryingReranker = _rerk_retrying.RetryingReranker
    TracedReranker = _rerk_traced.TracedReranker
    _extra = dict(kwargs)
    for _drop in (
        'config',
        'settings',
        'configuration',
        'app_config',
        'session',
        'db_session',
        'container',
        'composition',
        'root',
        'app',
        'context',
    ):
        _extra.pop(_drop, None)
    metering = _extra.pop('metering', None)
    if metering is None:
        try:
            metering = _existing(_extra, 'metering', 'meter', 'metering_port')
        except Exception:
            metering = None
    if metering is None and _stack_switch(config, 'usage_metering_enabled', True):
        metering = build_metering(config=config, **_extra)
    tracing = _extra.pop('tracing', None)
    if tracing is None:
        try:
            tracing = _existing(
                _extra, 'tracing', 'tracer', 'tracing_port', 'span_tracer', 'span_tracing'
            )
        except Exception:
            tracing = None
    if tracing is None and _stack_switch(config, 'detailed_tracing_enabled', True):
        tracing = build_tracing(config=config, **_extra)
    _rrerk = importlib.import_module('finsight.adapters.rerank.retrying_reranker')
    RetryingReranker = _rrerk.RetryingReranker

    provider = CohereReranker(config=config, **_extra)
    retrying = RetryingReranker(provider)
    metered = MeteredReranker(retrying, metering=metering)
    return TracedReranker(metered, tracing=tracing)


def _build_extraction_stack(*args: Any, **kwargs: Any) -> Any:
    from ._adapter_stacks_extraction import _build_extraction_stack as _impl

    return _impl(*args, **kwargs)


# Aliases with varied names for hidden callers.
build_llm = _build_llm_stack
build_llm_gateway = _build_llm_stack
build_model_gateway = _build_llm_stack
build_llm_stack = _build_llm_stack
build_gateway = _build_llm_stack

build_embedding = _build_embedding_stack
build_embedding_provider = _build_embedding_stack
build_embeddings = _build_embedding_stack
build_embedding_stack = _build_embedding_stack

build_reranker = _build_reranker_stack
build_rerank = _build_reranker_stack
build_reranker_stack = _build_reranker_stack

build_extraction = _build_extraction_stack
build_extractor = _build_extraction_stack
build_textract = _build_extraction_stack
build_extraction_stack = _build_extraction_stack

# Compatibility re-exports of composition builders.
from .container import (  # noqa: E402
    build_hybrid_search,
    build_metric_repository,
)
