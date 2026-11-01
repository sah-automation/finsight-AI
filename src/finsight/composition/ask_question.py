"""Composition helpers for the ask-question use case."""

from __future__ import annotations

from typing import Any

from finsight.application.ask_question import AskQuestion


def get_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    return _get_ask_use_case_impl(*args, **kwargs)


def _get_ask_use_case_impl(*args: Any, **kwargs: Any) -> Any:
    """Return the wired ask-question use case."""
    provided = (
        kwargs.get('ask_question_use_case') or kwargs.get('ask_use_case') or kwargs.get('use_case')
    )
    if provided is not None:
        return provided

    from .container import get_default_container, resolve_config, resolve_session

    config = resolve_config(*args, **kwargs)
    if config is None:
        config = kwargs.get('config')

    # Reuse an already-wired container use case when possible.
    container = None
    for key in ('container', 'composition', 'root', 'app', 'context'):
        candidate = kwargs.get(key)
        if candidate is not None:
            container = candidate
            break
    if container is None and not args and not kwargs:
        container = get_default_container()
    if container is not None:
        for attr in (
            'ask_question_use_case',
            'ask_use_case',
            'ask_question',
            'ask',
            'qa_use_case',
            'question_use_case',
        ):
            value = getattr(container, attr, None)
            if value is not None:
                return value

    if args or kwargs:
        # Reuse container built from call arguments.
        from .container import build_container

        built = build_container(*args, **kwargs)
        for attr in (
            'ask_question_use_case',
            'ask_use_case',
            'ask_question',
            'ask',
            'qa_use_case',
            'question_use_case',
        ):
            value = getattr(built, attr, None)
            if value is not None:
                return value

    llm = kwargs.get('llm_gateway') or kwargs.get('llm')
    embedding = kwargs.get('embedding_provider') or kwargs.get('embedding')
    search = kwargs.get('hybrid_search') or kwargs.get('search')
    reranker = kwargs.get('reranker')
    metrics = kwargs.get('metric_repository') or kwargs.get('metrics')
    cache = kwargs.get('answer_cache') or kwargs.get('cache')
    waiting = kwargs.get('waiting_line') or kwargs.get('waiting')
    tracing = kwargs.get('tracing') or kwargs.get('tracer') or kwargs.get('tracing_port')

    if llm is None:
        from .container import build_llm_gateway

        llm = build_llm_gateway(config=config)
    if embedding is None:
        from .container import build_embedding_provider

        embedding = build_embedding_provider(config=config)
    if search is None:
        from .container import build_hybrid_search

        search = build_hybrid_search(config=config)
    if reranker is None:
        from .container import build_reranker

        reranker = build_reranker(config=config)
    if metrics is None:
        from .container import build_metric_repository

        metrics = build_metric_repository(config=config)
    if cache is None:
        from .container import build_answer_cache

        cache = build_answer_cache(config=config)
    if waiting is None:
        from .container import build_waiting_line

        waiting = build_waiting_line(config=config)
    if tracing is None:
        from .container import build_tracing

        tracing = build_tracing(config=config)

    try:
        signing_key = config.signing_key if config is not None else kwargs.get('signing_key')
    except Exception:
        signing_key = kwargs.get('signing_key')

    return AskQuestion(
        config=(config if config is not None else kwargs.get('config')),
        llm_gateway=llm,
        embedding_provider=embedding,
        hybrid_search=search,
        reranker=reranker,
        metric_repository=metrics,
        answer_cache=cache,
        waiting_line=waiting,
        tracing=tracing,
        signing_key=signing_key if signing_key is not None else kwargs.get('signing_key', ''),
        **{
            k: v
            for k, v in kwargs.items()
            if k
            not in {
                'config',
                'session',
                'signing_key',
                'tracing',
                'tracer',
                'tracing_port',
            }
            and not k.endswith('_use_case')
        },
    )


def build_ask_question(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


def build_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


def build_ask_question_use_case(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


def resolve_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


__all__ = [
    'build_ask_question',
    'build_ask_question_use_case',
    'build_ask_use_case',
    'get_ask_use_case',
    'resolve_ask_use_case',
]
