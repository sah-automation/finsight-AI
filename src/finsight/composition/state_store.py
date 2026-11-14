"""Composition helpers for the state-store seam."""

from __future__ import annotations

from typing import Any


def build_state_store(*args: Any, **kwargs: Any) -> Any:
    provided = kwargs.get('state_store') or kwargs.get('store')
    if provided is not None:
        return provided
    try:
        import importlib

        module = importlib.import_module('finsight.adapters.state_store.in_memory_state_store')
        InMemoryStateStore = module.InMemoryStateStore
        return InMemoryStateStore(*args, **kwargs)
    except Exception:
        return None


def build_in_memory_state_store(*args: Any, **kwargs: Any) -> Any:
    return build_state_store(*args, **kwargs)


def get_state_store(*args: Any, **kwargs: Any) -> Any:
    if args or kwargs:
        return build_state_store(*args, **kwargs)
    return build_state_store()


__all__ = ['build_in_memory_state_store', 'build_state_store', 'get_state_store']
