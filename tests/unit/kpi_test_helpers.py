"""Shared fixtures for KPI computation unit tests."""

from __future__ import annotations

from typing import Any

from finsight.core.types import CompanyId
from finsight.domain.entities.metric import Metric

COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000001')
RULE_VERSION = 'rule-v1'


def make_metric(
    name: str,
    value: object,
    *,
    metric_id: str,
    period: str = '2026-Q3',
    currency: str | None = 'USD',
    units: str | None = 'USD',
    version: str = 'version-1',
    page: int = 1,
    table_id: str | None = None,
    chunk_id: str | None = None,
    start_char: int | None = None,
    end_char: int | None = None,
) -> Metric:
    """Build a Metric with optional provenance and dimensional fields."""
    source_location: dict[str, Any] = {'page': page}
    if table_id:
        source_location['table'] = table_id
    if chunk_id:
        source_location['chunk'] = chunk_id
    if start_char is not None:
        source_location['start_char'] = start_char
    if end_char is not None:
        source_location['end_char'] = end_char

    return Metric(
        metric_id=metric_id,
        company_id=COMPANY,
        name=name,
        value=value,
        unit=units,
        currency=currency,
        period=period,
        document_id='doc-1',
        document_version_id=version,
        source_location=source_location,
    )


def citation_id(
    version: str = 'version-1',
    page: int = 1,
    table_id: str | None = None,
    chunk_id: str | None = None,
    start_char: int | None = None,
    end_char: int | None = None,
) -> str:
    """Build the expected CitationId for a test Metric."""
    parts = ['cit:v1', version, f'p{page}']
    if table_id:
        parts.append(f't{table_id}')
    if chunk_id:
        parts.append(f'c{chunk_id}')
    if start_char is not None and end_char is not None:
        parts.append(f'o{start_char}-{end_char}')
    return ':'.join(parts)


__all__ = ['COMPANY', 'RULE_VERSION', 'citation_id', 'make_metric']
