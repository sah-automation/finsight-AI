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


def _sanitize_attributes(attributes: Any) -> dict[str, Any]:
    if attributes is None:
        return {}
    if not isinstance(attributes, Mapping):
        attributes = {'value': attributes}

    def _sanitize(key: Any, value: Any) -> tuple[bool, Any]:
        key_text = str(key)
        lowered = key_text.lower()
        # Allow-list LLM token-count and latency metrics. Their names contain
        # substrings ("token", "prompt") that would otherwise trip the
        # sensitive-name blocklist, but the values are aggregates, not content.
        if lowered in _TOKEN_METRIC_KEYS:
            if isinstance(value, Mapping):
                metric_cleaned: dict[str, Any] = {}
                for nested_key, nested_value in value.items():
                    keep, sanitized = _sanitize(nested_key, nested_value)
                    if keep:
                        metric_cleaned[str(nested_key)] = sanitized
                return True, metric_cleaned
            return True, value
        if any(token in lowered for token in _SENSITIVE_NAME_TOKENS):
            return False, None
        if 'url' in lowered:
            return False, None
        if isinstance(value, Mapping):
            cleaned: dict[str, Any] = {}
            for nested_key, nested_value in value.items():
                keep, sanitized = _sanitize(nested_key, nested_value)
                if keep:
                    cleaned[str(nested_key)] = sanitized
            return True, cleaned
        if isinstance(value, (list, tuple)):
            cleaned_list = []
            for item in value:
                if isinstance(item, Mapping):
                    cleaned_item: dict[str, Any] = {}
                    for nested_key, nested_value in item.items():
                        keep, sanitized = _sanitize(nested_key, nested_value)
                        if keep:
                            cleaned_item[str(nested_key)] = sanitized
                    cleaned_list.append(cleaned_item)
                elif _looks_sensitive_text(item):
                    continue
                else:
                    cleaned_list.append(item)
            return True, cleaned_list
        if _looks_sensitive_text(value):
            return False, None
        # Convert company identifiers embedded in attributes.
        if 'company' in lowered:
            try:
                return True, company_to_trace_attribute(value)
            except Exception as exc:
                _LOGGER.debug('company attribute conversion failed: %s', exc)
        return True, value

    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        keep, sanitized = _sanitize(key, value)
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
