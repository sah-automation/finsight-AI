"""Composition helpers for the ask-question use case."""

from __future__ import annotations

from typing import Any

from finsight.composition.container import build_container, get_default_container, resolve_config


def get_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    return _resolve_ask_use_case(*args, **kwargs)


def _resolve_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    provided = kwargs.get('use_case')
    if provided is not None:
        return provided

    container = _resolve_container(kwargs)
    if container is not None:
        use_case = getattr(container, 'ask_question_use_case', None)
        if use_case is not None:
            return use_case

    resolve_config(*args, **kwargs)
    built = build_container(*args, **kwargs)
    use_case = getattr(built, 'ask_question_use_case', None)
    if use_case is not None:
        return use_case

    container = get_default_container()
    if container is not None:
        use_case = getattr(container, 'ask_question_use_case', None)
        if use_case is not None:
            return use_case

    raise RuntimeError('ask use case could not be resolved from the composition root')


def _resolve_container(kwargs: dict[str, Any]) -> Any:
    for key in ('container', 'composition', 'root', 'app', 'context'):
        candidate = kwargs.get(key)
        if candidate is not None:
            return candidate
    if not any(kwargs.values()):
        return get_default_container()
    return None


__all__ = ['get_ask_use_case']
