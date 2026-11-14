# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
"""Redaction helpers for tracing spans."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from finsight.domain.value_objects.span import company_to_trace_attribute

_LOGGER = logging.getLogger(__name__)

_SENSITIVE_NAME_TOKENS: tuple[str, ...] = (
    'question',
    'chunk',
    'answer',
    'pii',
    'signed_url',
    'signedurl',
    'credential',
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
)


# Metric keys that are safe to keep on spans even though their names contain
# sensitive substrings. These are aggregates (counts/latencies), never content.
_TOKEN_METRIC_KEYS: frozenset[str] = frozenset(
    {
        'first_token_latency_ms',
        'tokens_prompt',
        'tokens_completion',
        'tokens_total',
        'prompt_tokens',
        'completion_tokens',
        'total_tokens',
        'input_tokens',
        'output_tokens',
        'token_count',
    }
)

_PII_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
    re.compile(r'\bBearer\s+[A-Za-z0-9._-]+\b', re.IGNORECASE),
)


def _looks_sensitive_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    if '://' in lowered:
        return True
    for token in ('pii', 'ssn', 'password', 'secret', 'signed', 'private'):
        if token in lowered:
            return True
    return any(pattern.search(value) for pattern in _PII_VALUE_PATTERNS)


def _sanitize_mapping(value: Mapping[Any, Any]) -> dict[str, Any]:
    """Recursively sanitize a mapping's keys and values."""
    cleaned: dict[str, Any] = {}
    for nested_key, nested_value in value.items():
        keep, sanitized = _sanitize_attribute(nested_key, nested_value)
        if keep:
            cleaned[str(nested_key)] = sanitized
    return cleaned


def _sanitize_list(value: Any) -> list[Any]:
    """Recursively sanitize a list/tuple's items."""
    cleaned_list: list[Any] = []
    for item in value:
        if isinstance(item, Mapping):
            cleaned_list.append(_sanitize_mapping(item))
        elif _looks_sensitive_text(item):
            continue
        else:
            cleaned_list.append(item)
    return cleaned_list


def _sanitize_genai_content(value: Any) -> tuple[bool, Any]:
    """Sanitize GenAI semantic-convention content values.

    gen_ai.prompt.* / gen_ai.completion.* keys carry full LLM content behind
    the opt-in llm_content_capture_enabled switch. The key itself survives
    name-based redaction, but the values are still walked to strip PII,
    credentials and signed URLs.
    """
    if isinstance(value, Mapping):
        return True, _sanitize_mapping(value)
    if isinstance(value, (list, tuple)):
        return True, _sanitize_list(value)
    if _looks_sensitive_text(value):
        return False, None
    return True, value


def _sanitize_attribute(key: Any, value: Any) -> tuple[bool, Any]:
    """Sanitize a single span attribute key-value pair."""
    key_text = str(key)
    lowered = key_text.lower()

    # Allow-list LLM token-count and latency metrics. Their names contain
    # substrings ("token", "prompt") that would otherwise trip the
    # sensitive-name blocklist, but the values are aggregates, not content.
    if lowered in _TOKEN_METRIC_KEYS:
        if isinstance(value, Mapping):
            return True, _sanitize_mapping(value)
        return True, value

    # GenAI semantic-convention content keys (gen_ai.prompt.*,
    # gen_ai.completion.*) carry full LLM content behind the opt-in
    # llm_content_capture_enabled switch. They must survive name-based
    # redaction so dev traces show meaningful content, but their values are
    # still walked below to strip PII, credentials and signed URLs.
    if lowered.startswith(('gen_ai.prompt.', 'gen_ai.completion.')):
        return _sanitize_genai_content(value)

    if any(token in lowered for token in _SENSITIVE_NAME_TOKENS):
        return False, None
    if 'url' in lowered:
        return False, None

    if isinstance(value, Mapping):
        return True, _sanitize_mapping(value)
    if isinstance(value, (list, tuple)):
        return True, _sanitize_list(value)
    if _looks_sensitive_text(value):
        return False, None
    # Convert company identifiers embedded in attributes, but never
    # re-hash the already-hashed wire-safe attributes.
    if 'company' in lowered and lowered not in {'company_hash', 'company_present'}:
        try:
            return True, company_to_trace_attribute(value)
        except Exception as exc:
            _LOGGER.debug('company attribute conversion failed: %s', exc)
    return True, value


def _sanitize_attributes(attributes: Any) -> dict[str, Any]:
    if attributes is None:
        return {}
    if not isinstance(attributes, Mapping):
        attributes = {'value': attributes}

    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        keep, sanitized = _sanitize_attribute(key, value)
        if keep:
            cleaned[str(key)] = sanitized
    return cleaned


STANDARD_REDACTED_FIELDS = _SENSITIVE_NAME_TOKENS
REDACTED_SPAN_FIELDS = _SENSITIVE_NAME_TOKENS

__all__ = [
    'REDACTED_SPAN_FIELDS',
    'STANDARD_REDACTED_FIELDS',
    '_SENSITIVE_NAME_TOKENS',
    '_sanitize_attributes',
]
