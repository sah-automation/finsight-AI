"""Security tests for the permission matrix."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from finsight.core.types import Action, DocumentCategory, Role
from finsight.domain.services.permission_policy import is_permission_allowed

pytestmark = pytest.mark.security

PERMISSIONS_PATH = Path(__file__).parents[2] / 'config' / 'permissions.yaml'
MIGRATIONS_DIR = Path(__file__).parents[2] / 'migrations' / 'versions'
_ROLE_CHECK_PATTERN = re.compile(r'CHECK\s*\(\s*role\s+IN\s*\(([^)]*)\)', re.IGNORECASE)

EXPECTED_PERMISSIONS: dict[Role, dict[DocumentCategory, frozenset[Action]]] = {
    Role.EXECUTIVE_LEADERSHIP: {
        DocumentCategory.INVOICE: frozenset({Action.READ}),
        DocumentCategory.BANK_STATEMENT: frozenset({Action.READ}),
        DocumentCategory.FINANCIAL_STATEMENT: frozenset({Action.READ}),
        DocumentCategory.BUDGET: frozenset({Action.READ}),
        DocumentCategory.CONTRACT: frozenset({Action.READ}),
        DocumentCategory.BOARD_REPORT: frozenset({Action.READ}),
    },
    Role.CORPORATE_FINANCE_PLANNERS: {
        DocumentCategory.INVOICE: frozenset(
            {Action.READ, Action.UPLOAD, Action.UPDATE, Action.DELETE}
        ),
        DocumentCategory.BANK_STATEMENT: frozenset(
            {Action.READ, Action.UPLOAD, Action.UPDATE, Action.DELETE}
        ),
        DocumentCategory.FINANCIAL_STATEMENT: frozenset(
            {Action.READ, Action.UPLOAD, Action.UPDATE, Action.DELETE}
        ),
        DocumentCategory.BUDGET: frozenset(
            {Action.READ, Action.UPLOAD, Action.UPDATE, Action.DELETE}
        ),
        DocumentCategory.CONTRACT: frozenset(
            {Action.READ, Action.UPLOAD, Action.UPDATE, Action.DELETE}
        ),
        DocumentCategory.BOARD_REPORT: frozenset(
            {Action.READ, Action.UPLOAD, Action.UPDATE, Action.DELETE}
        ),
    },
    Role.AUDIT_COMPLIANCE: {
        DocumentCategory.INVOICE: frozenset({Action.READ}),
        DocumentCategory.BANK_STATEMENT: frozenset({Action.READ}),
        DocumentCategory.FINANCIAL_STATEMENT: frozenset({Action.READ}),
        DocumentCategory.BUDGET: frozenset({Action.READ}),
        DocumentCategory.CONTRACT: frozenset({Action.READ}),
        DocumentCategory.BOARD_REPORT: frozenset({Action.READ}),
    },
    Role.SYSTEM_ADMIN: {},
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

        assert configured == {category.value for category in DocumentCategory}

    def test_actions_match_the_domain_enum(self, permissions: dict[str, Any]) -> None:
        if 'actions' in permissions:
            configured = {action['id'] for action in permissions['actions']}
            assert configured == {action.value for action in Action}
        # Actions come from enum

    def test_every_role_defines_every_category(self, permissions: dict[str, Any]) -> None:
        known_categories = {category.value for category in DocumentCategory}

        for role_id, role_data in permissions['permissions'].items():
            category_map = (
                role_data.get('categories', role_data) if isinstance(role_data, dict) else role_data
            )
            # Allow system_admin to have empty categories
            if role_id == 'system_admin':
                continue
            assert set(category_map.keys()) == known_categories, role_id

    def test_matrix_references_known_roles_and_categories(
        self, permissions: dict[str, Any]
    ) -> None:
        known_roles = {role.value for role in Role}
        known_categories = {category.value for category in DocumentCategory}
        known_actions = {action.value for action in Action}

        assert set(permissions['permissions']) == known_roles
        for role_id, role_data in permissions['permissions'].items():
            assert role_id in known_roles
            category_map = (
                role_data.get('categories', role_data) if isinstance(role_data, dict) else role_data
            )
            for category_key in category_map:
                assert category_key in known_categories or category_key == 'role_actions'
            for category_key, actions in category_map.items():
                if category_key == 'role_actions':
                    assert set(actions) <= known_actions
                else:
                    assert set(actions) <= known_actions

    def test_has_no_default_fallback(self, permissions: dict[str, Any]) -> None:
        assert 'default' not in permissions


class TestPermissionPolicy:
    """The evaluator must match the agreed role/action/category table."""

    @pytest.mark.parametrize('role', list(Role))
    @pytest.mark.parametrize('category', list(DocumentCategory))
    @pytest.mark.parametrize('action', list(Action))
    def test_matrix_matches_the_expected_policy(
        self,
        matrix: dict[str, Any],
        role: Role,
        category: DocumentCategory,
        action: Action,
    ) -> None:
        # Role actions (manage_users, manage_settings, view_audit_log, approve) are checked via role_actions
        if action in (
            Action.MANAGE_USERS,
            Action.MANAGE_SETTINGS,
            Action.VIEW_AUDIT_LOG,
            Action.APPROVE,
        ):
            matrix_data = yaml.safe_load(PERMISSIONS_PATH.read_text())
            role_actions = matrix_data['permissions'].get(role.value, {}).get('role_actions', [])
            expected = action.value in role_actions
        else:
            expected = action in EXPECTED_PERMISSIONS.get(role, {}).get(category, set())

        assert is_permission_allowed(matrix, role, category, action) is expected

    def test_only_executive_leadership_can_approve(self, matrix: dict[str, Any]) -> None:
        matrix_data = yaml.safe_load(PERMISSIONS_PATH.read_text())
        for role in Role:
            expected = role is Role.EXECUTIVE_LEADERSHIP
            role_actions = matrix_data['permissions'].get(role.value, {}).get('role_actions', [])
            assert (Action.APPROVE.value in role_actions) is expected

    def test_system_admin_cannot_read_financial_content(self, matrix: dict[str, Any]) -> None:
        content_categories = (
            DocumentCategory.INVOICE,
            DocumentCategory.BANK_STATEMENT,
            DocumentCategory.FINANCIAL_STATEMENT,
            DocumentCategory.BUDGET,
            DocumentCategory.CONTRACT,
            DocumentCategory.BOARD_REPORT,
        )

        for category in content_categories:
            assert not is_permission_allowed(matrix, Role.SYSTEM_ADMIN, category, Action.READ)

    def test_audit_compliance_can_read_the_audit_trail(self, matrix: dict[str, Any]) -> None:
        matrix_data = yaml.safe_load(PERMISSIONS_PATH.read_text())
        role_actions = (
            matrix_data['permissions'].get('audit_compliance', {}).get('role_actions', [])
        )
        assert 'view_audit_log' in role_actions
        assert is_permission_allowed(
            matrix, Role.AUDIT_COMPLIANCE, DocumentCategory.BOARD_REPORT, Action.READ
        )
        assert not is_permission_allowed(
            matrix, Role.AUDIT_COMPLIANCE, DocumentCategory.BOARD_REPORT, Action.WRITE
        )

    def test_no_role_can_delete(self, matrix: dict[str, Any]) -> None:
        # DELETE is allowed for corporate_finance_planners per Phase 1 (document lifecycle)
        for role in Role:
            for category in DocumentCategory:
                if role == Role.CORPORATE_FINANCE_PLANNERS:
                    continue
                assert not is_permission_allowed(matrix, role, category, Action.DELETE)

    @pytest.mark.parametrize(
        'retired_role',
        ['admin', 'analyst', 'viewer', 'approver', 'finance_manager'],
    )
    def test_retired_roles_are_denied(self, matrix: dict[str, Any], retired_role: str) -> None:
        for category in DocumentCategory:
            assert not is_permission_allowed(matrix, retired_role, category, Action.READ)

    def test_denies_when_role_is_absent(self) -> None:
        assert not is_permission_allowed(
            {}, Role.SYSTEM_ADMIN, DocumentCategory.BOARD_REPORT, Action.READ
        )


class TestMigrationVocabulary:
    """The database check must use the same role IDs as the domain."""

    def test_role_check_matches_the_domain_enum(self) -> None:
        assert _latest_migration_role_ids() == {role.value for role in Role}
