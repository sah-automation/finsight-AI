"""Security tests for the permission matrix."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from finsight.core.types import Action, Category, Role
from finsight.domain.services.permission_policy import is_permission_allowed

pytestmark = pytest.mark.security

PERMISSIONS_PATH = Path(__file__).parents[2] / 'config' / 'permissions.yaml'
MIGRATIONS_DIR = Path(__file__).parents[2] / 'migrations' / 'versions'
_ROLE_CHECK_PATTERN = re.compile(r'CHECK\s*\(\s*role\s+IN\s*\(([^)]*)\)', re.IGNORECASE)

EXPECTED_PERMISSIONS: dict[Role, dict[Category, frozenset[Action]]] = {
    Role.EXECUTIVE_LEADERSHIP: {
        Category.FINANCIALS: frozenset({Action.READ}),
        Category.METRICS: frozenset({Action.READ}),
        Category.FORECASTS: frozenset({Action.READ}),
        Category.RISKS: frozenset({Action.READ}),
        Category.DECISIONS: frozenset({Action.READ, Action.APPROVE}),
        Category.DOCUMENTS: frozenset({Action.READ}),
        Category.AUDIT: frozenset(),
    },
    Role.CORPORATE_FINANCE_PLANNERS: {
        Category.FINANCIALS: frozenset({Action.READ}),
        Category.METRICS: frozenset({Action.READ, Action.WRITE}),
        Category.FORECASTS: frozenset({Action.READ, Action.WRITE}),
        Category.RISKS: frozenset({Action.READ, Action.WRITE}),
        Category.DECISIONS: frozenset({Action.READ, Action.WRITE}),
        Category.DOCUMENTS: frozenset({Action.READ, Action.UPLOAD}),
        Category.AUDIT: frozenset(),
    },
    Role.AUDIT_COMPLIANCE: {
        Category.FINANCIALS: frozenset({Action.READ}),
        Category.METRICS: frozenset({Action.READ}),
        Category.FORECASTS: frozenset({Action.READ}),
        Category.RISKS: frozenset({Action.READ}),
        Category.DECISIONS: frozenset({Action.READ}),
        Category.DOCUMENTS: frozenset({Action.READ}),
        Category.AUDIT: frozenset({Action.READ}),
    },
    Role.SYSTEM_ADMIN: {
        Category.FINANCIALS: frozenset({Action.CONFIGURE}),
        Category.METRICS: frozenset({Action.CONFIGURE}),
        Category.FORECASTS: frozenset({Action.CONFIGURE}),
        Category.RISKS: frozenset({Action.CONFIGURE}),
        Category.DECISIONS: frozenset({Action.CONFIGURE}),
        Category.DOCUMENTS: frozenset({Action.CONFIGURE}),
        Category.AUDIT: frozenset({Action.READ}),
    },
}


def _migration_order(path: Path) -> int:
    prefix = path.name.split('_', 1)[0]
    return int(prefix) if prefix.isdigit() else 0


def _latest_migration_role_ids() -> set[str]:
    """Return the role values from the newest migration that defines the check."""
    for path in sorted(MIGRATIONS_DIR.glob('*.py'), key=_migration_order, reverse=True):
        matches = _ROLE_CHECK_PATTERN.findall(path.read_text())
        if matches:
            return {value.strip().strip('\'"') for value in matches[-1].split(',')}
    raise AssertionError(f'No users.role check found in {MIGRATIONS_DIR}')


@pytest.fixture(scope='module')
def permissions() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(PERMISSIONS_PATH.read_text())
    return loaded


@pytest.fixture(scope='module')
def matrix(permissions: dict[str, Any]) -> dict[str, Any]:
    loaded: dict[str, Any] = permissions['permissions']
    return loaded


class TestPermissionMatrixIntegrity:
    """The YAML matrix must stay aligned with the typed enums."""

    def test_roles_match_the_domain_enum(self, permissions: dict[str, Any]) -> None:
        configured = {role['id'] for role in permissions['roles']}

        assert configured == {role.value for role in Role}

    def test_categories_match_the_domain_enum(self, permissions: dict[str, Any]) -> None:
        configured = {category['id'] for category in permissions['categories']}

        assert configured == {category.value for category in Category}

    def test_actions_match_the_domain_enum(self, permissions: dict[str, Any]) -> None:
        configured = {action['id'] for action in permissions['actions']}

        assert configured == {action.value for action in Action}

    def test_every_role_defines_every_category(self, permissions: dict[str, Any]) -> None:
        known_categories = {category.value for category in Category}

        for role_id, category_map in permissions['permissions'].items():
            assert set(category_map) == known_categories, role_id

    def test_matrix_references_known_roles_and_categories(
        self, permissions: dict[str, Any]
    ) -> None:
        known_roles = {role.value for role in Role}
        known_categories = {category.value for category in Category}
        known_actions = {action.value for action in Action}

        assert set(permissions['permissions']) == known_roles
        for role_id, category_map in permissions['permissions'].items():
            assert role_id in known_roles
            assert set(category_map) <= known_categories
            for actions in category_map.values():
                assert set(actions) <= known_actions

    def test_has_no_default_fallback(self, permissions: dict[str, Any]) -> None:
        assert 'default' not in permissions


class TestPermissionPolicy:
    """The evaluator must match the agreed role/action/category table."""

    @pytest.mark.parametrize('role', list(Role))
    @pytest.mark.parametrize('category', list(Category))
    @pytest.mark.parametrize('action', list(Action))
    def test_matrix_matches_the_expected_policy(
        self,
        matrix: dict[str, Any],
        role: Role,
        category: Category,
        action: Action,
    ) -> None:
        expected = action in EXPECTED_PERMISSIONS[role][category]

        assert is_permission_allowed(matrix, role, category, action) is expected

    def test_only_executive_leadership_can_approve(self, matrix: dict[str, Any]) -> None:
        for role in Role:
            expected = role is Role.EXECUTIVE_LEADERSHIP

            assert (
                is_permission_allowed(matrix, role, Category.DECISIONS, Action.APPROVE) is expected
            )

    def test_system_admin_cannot_read_financial_content(self, matrix: dict[str, Any]) -> None:
        content_categories = (
            Category.FINANCIALS,
            Category.METRICS,
            Category.FORECASTS,
            Category.RISKS,
            Category.DECISIONS,
            Category.DOCUMENTS,
        )

        for category in content_categories:
            assert not is_permission_allowed(matrix, Role.SYSTEM_ADMIN, category, Action.READ)

    def test_audit_compliance_can_read_the_audit_trail(self, matrix: dict[str, Any]) -> None:
        assert is_permission_allowed(matrix, Role.AUDIT_COMPLIANCE, Category.AUDIT, Action.READ)
        assert not is_permission_allowed(
            matrix, Role.AUDIT_COMPLIANCE, Category.AUDIT, Action.WRITE
        )

    def test_no_role_can_delete(self, matrix: dict[str, Any]) -> None:
        for role in Role:
            for category in Category:
                assert not is_permission_allowed(matrix, role, category, Action.DELETE)

    @pytest.mark.parametrize(
        'retired_role',
        ['admin', 'analyst', 'viewer', 'approver', 'finance_manager'],
    )
    def test_retired_roles_are_denied(self, matrix: dict[str, Any], retired_role: str) -> None:
        for category in Category:
            assert not is_permission_allowed(matrix, retired_role, category, Action.READ)

    def test_denies_when_role_is_absent(self) -> None:
        assert not is_permission_allowed({}, Role.SYSTEM_ADMIN, Category.AUDIT, Action.READ)


class TestMigrationVocabulary:
    """The database check must use the same role IDs as the domain."""

    def test_role_check_matches_the_domain_enum(self) -> None:
        assert _latest_migration_role_ids() == {role.value for role in Role}
