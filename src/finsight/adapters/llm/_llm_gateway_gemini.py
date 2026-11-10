"""Gemini 3+ provider-call adjustments for the LLM gateway (issue #262).

Gemini 3+ deprecates ``temperature``/``top_p``/``top_k``: they still work but
 LiteLLM warns on every call and the provider plans removal. The gateway omits
them for Gemini 3+ model ids and folds the deterministic-sampling guidance
into the system instructions instead. Other model families are untouched.
"""

from __future__ import annotations

import re
from typing import Any

# Make sampling behavior match the configured deterministic profiles
# (temperature 0.0 across all profiles) now that the parameter is not sent.
GEMINI_3_SAMPLING_GUIDANCE = (
    'Sampling guidance: answer deterministically — produce your single most '
    'likely response with no sampling variety, as if temperature were 0.'
)

_DEPRECATED_SAMPLING_KEYS = frozenset({'temperature', 'top_p', 'top_k'})

_GEMINI_VERSION_PATTERN = re.compile(r'gemini[-_ ]?(\d+)', re.IGNORECASE)

# The Gemini 3+ family: major version 3 and later.
_GEMINI_3_MAJOR = 3


def _is_gemini_3(model_id: Any) -> bool:
    """Return True when ``model_id`` belongs to the Gemini 3+ family."""
    if not isinstance(model_id, str):
        return False
    match = _GEMINI_VERSION_PATTERN.search(model_id)
    if match is None:
        return False
    try:
        return int(match.group(1)) >= _GEMINI_3_MAJOR
    except ValueError:
        return False


def _apply_gemini_3_sampling_guidance(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return messages with the determinism guidance appended to the system message.

    The input list is never mutated: a new list (and a new system dict) is
    returned, so concurrent chain steps that share the message list — e.g. a
    Gemini primary racing a non-Gemini backup — see only their own variant.
    """
    adjusted = list(messages)
    guidance = GEMINI_3_SAMPLING_GUIDANCE
    for index, message in enumerate(adjusted):
        if message.get('role') == 'system':
            content = str(message.get('content') or '').rstrip()
            system = dict(message)
            system['content'] = f'{content}\n\n{guidance}' if content else guidance
            adjusted[index] = system
            return adjusted
    adjusted.insert(0, {'role': 'system', 'content': guidance})
    return adjusted


def _without_deprecated_sampling(params: dict[str, Any]) -> dict[str, Any]:
    """Drop the deprecated sampling keys from caller-supplied parameters."""
    return {key: value for key, value in params.items() if key not in _DEPRECATED_SAMPLING_KEYS}
