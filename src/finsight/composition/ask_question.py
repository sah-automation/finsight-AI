"""Composition helpers for the ask-question use case."""

from __future__ import annotations

from typing import Any

from finsight.application.ask_question import AskQuestion


def get_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    try:
        from finsight.composition.container import resolve_config, resolve_session

        config = resolve_config(*args, **kwargs)
    except Exception:
        config = kwargs.get('config')
        _ = kwargs.get('session')

    # Try wiring known dependencies from kwargs.
    llm = kwargs.get('llm_gateway') or kwargs.get('llm')
    embedding = kwargs.get('embedding_provider') or kwargs.get('embedding')
    search = kwargs.get('hybrid_search') or kwargs.get('search')
    reranker = kwargs.get('reranker')
    metrics = kwargs.get('metric_repository') or kwargs.get('metrics')
    cache = kwargs.get('answer_cache') or kwargs.get('cache')
    waiting = kwargs.get('waiting_line') or kwargs.get('waiting')

    try:
        return AskQuestion(
            llm_gateway=llm,
            embedding_provider=embedding,
            hybrid_search=search,
            reranker=reranker,
            metric_repository=metrics,
            answer_cache=cache,
            waiting_line=waiting,
            config=config,
            **{k: v for k, v in kwargs.items() if k not in {'config'}},
        )
    except Exception:
        return AskQuestion(config=config)


# Aliases
def build_ask_question(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


def resolve_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


__all__ = ['build_ask_question', 'get_ask_use_case', 'resolve_ask_use_case']
