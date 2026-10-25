"""Security tests for tenant isolation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from finsight.core.types import Category, RequestContext, Role
from tests.support.ast_inspection import find_methods_without_company_id

SRC_ROOT = Path(__file__).parents[2] / 'src' / 'finsight'

pytestmark = pytest.mark.security


def _context(company_id: str = 'company-a') -> RequestContext:
    return RequestContext(
        company_id=company_id,
        user_id='user-a',
        role=Role.ANALYST,
        trace_id='trace-a',
        permissions={},
        access_scope=[Category.METRICS],
    )


def _format_violations(violations: list[tuple[str, str, int]]) -> str:
    return '\n'.join(f'  {path}:{line} {name}' for path, name, line in violations)


class TestRequestContextIsolation:
    """The request context must carry a company id at all times."""

    def test_company_id_is_required(self) -> None:
        with pytest.raises(ValidationError):
            RequestContext(
                user_id='user-a',
                role=Role.ANALYST,
                trace_id='trace-a',
                permissions={},
                access_scope=[],
            )

    def test_company_id_is_preserved(self) -> None:
        assert _context().company_id == 'company-a'

    def test_company_id_cannot_be_none(self) -> None:
        with pytest.raises(ValidationError):
            _context(company_id=None)  # type: ignore[arg-type]


class TestDataAccessMethods:
    """Every data-access method must accept a company id."""

    def test_adapters_require_company_id(self) -> None:
        violations = find_methods_without_company_id(SRC_ROOT / 'adapters')

        assert not violations, 'Adapter data methods missing company_id:\n' + _format_violations(
            violations
        )

    def test_domain_ports_require_company_id(self) -> None:
        violations = find_methods_without_company_id(SRC_ROOT / 'domain' / 'ports')

        assert not violations, 'Port data methods missing company_id:\n' + _format_violations(
            violations
        )

    def test_scanner_detects_a_missing_company_id(self, tmp_path: Path) -> None:
        package = tmp_path / 'repositories'
        package.mkdir()
        (package / 'repository.py').write_text(
            'class Repository:\n'
            '    def get_document(self, document_id: str) -> str:\n'
            '        return document_id\n'
        )

        violations = find_methods_without_company_id(package)

        assert len(violations) == 1
        assert violations[0][1] == 'get_document'
