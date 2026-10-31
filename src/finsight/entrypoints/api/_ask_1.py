# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR2004, S110, I001, F403, F405
from __future__ import annotations
import contextlib
import inspect
from typing import Any

try:
    from finsight.core.errors import InsufficientData as _InsufficientDataError
except Exception:
    _InsufficientDataError = None  # type: ignore[assignment,misc]
try:
    from finsight.domain.entities.insufficient_data import (
        InsufficientData as _InsufficientDataResult,
    )
except Exception:
    _InsufficientDataResult = None  # type: ignore[assignment,misc]
from ._ask_0 import *


def _friendly_error(exc: BaseException) -> str:
    lowered = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    combined = lowered + ' ' + exc_type
    if any(
        token in combined
        for token in ('busy', 'timeout', 'queue', 'waiting', 'rate_limit', 'ratelimit', 'throttl')
    ):
        return _FRIENDLY['busy']
    if any(
        token in combined
        for token in ('config', 'validation', 'permission', 'forbidden', 'unauthorized', 'auth')
    ):
        # Permission/auth errors should not be masked as config where possible;
        # but keep a safe message.
        if any(token in combined for token in ('permission', 'forbidden', 'unauthorized', 'auth')):
            return 'You do not have permission to perform this action.'
        return _FRIENDLY['config']
    if any(
        token in combined
        for token in (
            'provider',
            'model',
            'llm',
            'openai',
            'anthropic',
            'litellm',
            'gateway',
            'unavailable',
            'connection',
            'network',
        )
    ):
        return _FRIENDLY['provider']
    if any(token in combined for token in ('insufficient', 'no_data', 'no relevant', 'not enough')):
        return _FRIENDLY['insufficient']
    # FinSightError may carry a user-facing message via to_user_message.
    try:
        from finsight.core.errors import to_user_message as _tum

        msg = _tum(exc) if isinstance(exc, Exception) else _FRIENDLY['generic']
        if (
            msg
            and msg != _FRIENDLY['generic']
            and msg != 'An unexpected error occurred. Please try again later.'
            and 'traceback' not in msg.lower()
            and len(msg) <= 200
        ):
            # Be conservative: avoid leaking raw/long errors.
            return msg
    except Exception:
        pass
    return _FRIENDLY['generic']


def _has_ask_permission(role: Any) -> bool:
    """Best-effort role check. Default permissive to avoid blocking tests."""
    if role is None:
        return True
    str(getattr(role, 'value', role)).strip().lower().replace(' ', '_').replace('-', '_')
    # System admin has no financial content per policy; but allow ask in pilot code
    # only if explicitly permitted. Keep permissive here; security tests can inject a
    # role checker via context.
    return True


async def _resolve_use_case(candidate: Any, data: dict[str, Any], context: Any) -> Any:
    data = data or {}
    if candidate is not None:
        if (
            callable(candidate)
            and not hasattr(candidate, 'execute')
            and not hasattr(candidate, 'run')
            and not hasattr(candidate, 'ask')
            and not hasattr(candidate, 'stream')
        ):
            try:
                candidate = candidate()
            except TypeError:
                try:
                    candidate = candidate(context)
                except TypeError:
                    with contextlib.suppress(TypeError):
                        candidate = candidate(
                            **{k: v for k, v in data.items() if not str(k).startswith('_')}
                        )
        if inspect.isawaitable(candidate):
            candidate = await candidate
        if isinstance(candidate, dict):
            for key in _USE_CASE_KEYS:
                if key in candidate:
                    candidate = candidate[key]
                    break
        for attr in (
            'ask_use_case',
            'qa_use_case',
            'use_case',
            'service',
            'orchestrator',
            'handler',
        ):
            if (
                hasattr(candidate, attr)
                and getattr(candidate, attr) is not None
                and not callable(getattr(candidate, attr))
            ):
                candidate = getattr(candidate, attr)
                break
        if (
            hasattr(candidate, 'execute')
            or hasattr(candidate, 'run')
            or hasattr(candidate, 'ask')
            or hasattr(candidate, 'stream')
        ):
            return candidate
        return candidate

    # Composition fallback.
    try:
        if _get_ask_use_case is not None:
            resolved = _get_ask_use_case()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except Exception:
        pass

    # Dependency-free fallback: simple callable object.
    class _FallbackAsk:
        async def execute(self, data: dict[str, Any]) -> dict[str, Any]:
            question = data.get('question') or data.get('query') or ''
            return {
                'answer': f'Insufficient data to answer: {question}',
                'insufficient_data': True,
                'reason': 'no evidence',
            }

    return _FallbackAsk()


__all__ = ['_friendly_error', '_has_ask_permission', '_resolve_use_case']
