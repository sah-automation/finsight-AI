"""Unit tests for the audit-record step."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.application.source_viewer.source_viewer_context import SourceViewerContext
from finsight.application.source_viewer.steps.audit_step import AuditStep


class _AuditLog:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[dict[str, Any]] = []
        self._fail = fail

    async def append(self, company_id: Any = None, **kwargs: Any) -> None:
        if self._fail:
            raise RuntimeError('audit failure')
        self.records.append({'company_id': company_id, **kwargs})


def _context(**overrides: Any) -> SourceViewerContext:
    values: dict[str, Any] = {
        'company_id': 'c1',
        'user_id': 'u1',
        'role': 'analyst',
        'trace_id': 't1',
        'document_id': 'd1',
        'version_id': 'v1',
        'chunk_id': 'ch1',
        'page': 2,
        'needs_review': False,
        'newer_available': False,
        'locator_token': 'signed.token',
        'outcome': 'success',
    }
    values.update(overrides)
    return SourceViewerContext(**values)


def test_audit_written_for_success() -> None:
    audit = _AuditLog()
    ctx = _context()
    result = asyncio.run(AuditStep(audit_log=audit).run(ctx))
    assert result.kind == 'continue'
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record['company_id'] == 'c1'
    assert record['event_type'] == 'source_view'
    assert record['action'] == 'source_view'
    assert record['actor'] == 'u1'
    assert record['role'] == 'analyst'
    assert record['citation_locator'] == 'signed.token'
    assert record['outcome'] == 'success'
    assert record['trace_id'] == 't1'
    assert record['resource_type'] == 'source_view'
    assert record['details']['document_id'] == 'd1'
    assert record['details']['chunk_id'] == 'ch1'
    assert record['details']['page'] == 2


def test_audit_written_for_denial() -> None:
    audit = _AuditLog()
    result = asyncio.run(AuditStep(audit_log=audit).run(_context(outcome='not_available')))
    assert result.kind == 'continue'
    assert len(audit.records) == 1
    assert audit.records[0]['outcome'] == 'not_available'


def test_audit_written_for_error() -> None:
    audit = _AuditLog()
    asyncio.run(AuditStep(audit_log=audit).run(_context(outcome='error')))
    assert audit.records[0]['outcome'] == 'error'


def test_missing_audit_log_is_a_noop() -> None:
    result = asyncio.run(AuditStep(audit_log=None).run(_context()))
    assert result.kind == 'continue'


def test_audit_failure_does_not_stop_the_pipeline() -> None:
    result = asyncio.run(AuditStep(audit_log=_AuditLog(fail=True)).run(_context()))
    assert result.kind == 'continue'


from finsight.core.types import Role


def test_role_enum_value_is_recorded() -> None:
    audit = _AuditLog()
    asyncio.run(AuditStep(audit_log=audit).run(_context(role=Role.EXECUTIVE_LEADERSHIP)))
    assert audit.records[0]['role'] == Role.EXECUTIVE_LEADERSHIP.value
