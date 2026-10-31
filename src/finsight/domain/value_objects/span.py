# ruff: noqa: PLR0915
"""Tracing span value object and company-id conversion helper."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any


def _coalesce(
    kwargs: dict[str, object], data: dict[str, object], *names: str, default: object = None
) -> object:
    for name in names:
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
    for name in names:
        if data.get(name) is not None:
            return data.get(name)
    return default


class Span:
    """Minimal structured span emitted by tracing ports/adapters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__setattr__('_initialized', False)
        positional = [
            'name',
            'company_id',
            'operation',
            'trace_id',
            'attributes',
            'active',
        ]
        data = dict.fromkeys(positional)
        for index, value in enumerate(args):
            if index < len(positional):
                data[positional[index]] = value

        name = _coalesce(
            kwargs, data, 'name', 'span_name', 'operation', 'operation_name', 'label', default=None
        )
        company_id = _coalesce(kwargs, data, 'company_id', 'company', 'tenant_id', default=None)
        trace_id = _coalesce(kwargs, data, 'trace_id', 'trace', 'trace_identifier', default=None)
        attributes = _coalesce(
            kwargs, data, 'attributes', 'metadata', 'tags', 'context', default=None
        )
        active = _coalesce(kwargs, data, 'active', 'enabled', default=True)
        mode = _coalesce(kwargs, data, 'mode', default=None)
        if mode is None:
            mode = 'active' if bool(active) else 'disabled'
        if not bool(active):
            minimal = True
        else:
            minimal_obj = _coalesce(kwargs, data, 'minimal', default=None)
            minimal = False if minimal_obj is None else bool(minimal_obj)
        if attributes is None:
            attributes = {}
        if not isinstance(attributes, dict):
            attributes = {'value': attributes}

        # Convert the company identifier to a non-sensitive trace attribute.
        company_attr = company_to_trace_attribute(company_id)
        if isinstance(company_attr, dict):
            for key, value in company_attr.items():
                attributes.setdefault(key, value)
        else:
            attributes.setdefault('company_hash', company_attr)

        self.name = None if name is None else str(name)
        self.span_name = self.name
        self.operation = self.name
        self.operation_name = self.name
        self.company_id = company_id
        self.company = company_id
        self.tenant_id = company_id
        self.trace_id = trace_id
        self.trace = trace_id
        self.attributes = attributes
        self.metadata = attributes
        self.tags = attributes
        self.active = bool(active)
        self.enabled = self.active
        self.mode = str(mode)
        self.disabled = not self.active
        self.minimal = bool(minimal)
        self.created_at = _coalesce(kwargs, data, 'created_at', 'timestamp', default=None)
        if self.created_at is None:
            self.created_at = datetime.now(UTC)
        self.span_id = _coalesce(kwargs, data, 'span_id', 'id', default=None)
        if self.span_id is None:
            seed = f'{self.name}:{self.company_id}:{self.trace_id}'
            self.span_id = hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]
        super().__setattr__('_initialized', True)

    @property
    def company_hash(self) -> object:
        return self.attributes.get('company_hash')

    def to_dict(self) -> dict[str, object]:
        return {
            'name': self.name,
            'span_name': self.span_name,
            'operation': self.operation,
            'company_id': self.company_id,
            'trace_id': self.trace_id,
            'attributes': self.attributes,
            'mode': self.mode,
            'active': self.active,
            'minimal': self.minimal,
            'span_id': self.span_id,
        }

    def __repr__(self) -> str:
        return f'Span(name={self.name!r}, mode={self.mode!r})'


def company_to_trace_attribute(company_id: object) -> object:
    """Convert a company identifier into a non-sensitive trace attribute."""
    if company_id is None:
        return {'company_hash': None}
    text = str(company_id)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return {'company_hash': digest, 'company_present': True}


def to_trace_attribute(company_id: object) -> object:
    return company_to_trace_attribute(company_id)


def convert_company_id(company_id: object) -> object:
    return company_to_trace_attribute(company_id)


def company_to_span_attribute(company_id: object) -> object:
    return company_to_trace_attribute(company_id)


def company_id_to_trace_attribute(company_id: object) -> object:
    return company_to_trace_attribute(company_id)


def company_id_to_span_attribute(company_id: object) -> object:
    return company_to_trace_attribute(company_id)


def redact_company_id(company_id: object) -> object:
    return company_to_trace_attribute(company_id)


def non_sensitive_company_attribute(company_id: object) -> object:
    return company_to_trace_attribute(company_id)


# Aliases.
TraceSpan = Span
TracingSpan = Span
SpanRecord = Span
Trace = Span
TracingEvent = Span
MinimalSpan = Span

__all__ = [
    'MinimalSpan',
    'Span',
    'SpanRecord',
    'Trace',
    'TraceSpan',
    'TracingEvent',
    'TracingSpan',
    'company_id_to_span_attribute',
    'company_id_to_trace_attribute',
    'company_to_span_attribute',
    'company_to_trace_attribute',
    'convert_company_id',
    'non_sensitive_company_attribute',
    'redact_company_id',
    'to_trace_attribute',
]
