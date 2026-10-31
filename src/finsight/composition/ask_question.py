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

    sess = resolve_session(*args, **kwargs)

    return AskQuestion(
        llm_gateway=llm,
        embedding_provider=embedding,
        hybrid_search=search,
        reranker=reranker,
        metric_repository=metrics,
        answer_cache=cache,
        waiting_line=waiting,
        config=config if config is not None else kwargs.get('config'),
        session=sess,
        **{
            k: v
            for k, v in kwargs.items()
            if k not in {'config', 'session'} and not k.endswith('_use_case')
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
