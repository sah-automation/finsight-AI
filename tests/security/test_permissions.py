"""Security tests for the permission matrix."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from finsight.core.types import Action, Category, Role
from finsight.domain.services.permission_policy import is_permission_allowed

pytestmark = pytest.mark.security

PERMISSIONS_PATH = Path(__file__).parents[2] / 'config' / 'permissions.yaml'


@pytest.fixture(scope='module')
def permissions() -> dict[str, Any]:
    return yaml.safe_load(PERMISSIONS_PATH.read_text())


@pytest.fixture(scope='module')
def matrix(permissions: dict[str, Any]) -> dict[str, Any]:
    return {**permissions['permissions'], 'default': permissions['default']}


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

    def test_matrix_references_known_roles_and_categories(
        self, permissions: dict[str, Any]
    ) -> None:
        known_roles = {role.value for role in Role}
        known_categories = {category.value for category in Category} | {'*'}
        known_actions = {action.value for action in Action} | {'*'}

        for role_id, category_map in permissions['permissions'].items():
            assert role_id in known_roles
            assert set(category_map) <= known_categories
            for actions in category_map.values():
                assert set(actions) <= known_actions

        for actions in permissions['default'].values():
            assert set(actions) <= known_actions


class TestPermissionEnforcement:
    """The evaluator must deny every action the matrix does not grant."""

    @pytest.mark.parametrize('action', list(Action))
    def test_admin_can_do_everything(self, matrix: dict[str, Any], action: Action) -> None:
        for category in Category:
            assert is_permission_allowed(matrix, Role.ADMIN, category, action)

    def test_viewer_can_only_read(self, matrix: dict[str, Any]) -> None:
        for category in Category:
            assert is_permission_allowed(matrix, Role.VIEWER, category, Action.READ)
            for action in Action:
                if action is not Action.READ:
                    assert not is_permission_allowed(matrix, Role.VIEWER, category, action)

    def test_analyst_can_write_metrics_but_not_financials(self, matrix: dict[str, Any]) -> None:
        assert is_permission_allowed(matrix, Role.ANALYST, Category.METRICS, Action.WRITE)
        assert not is_permission_allowed(matrix, Role.ANALYST, Category.FINANCIALS, Action.WRITE)

    def test_analyst_can_upload_documents_but_cannot_approve(self, matrix: dict[str, Any]) -> None:
        assert is_permission_allowed(matrix, Role.ANALYST, Category.DOCUMENTS, Action.UPLOAD)
        assert not is_permission_allowed(matrix, Role.ANALYST, Category.DECISIONS, Action.APPROVE)

    def test_approver_can_approve_decisions_only(self, matrix: dict[str, Any]) -> None:
        assert is_permission_allowed(matrix, Role.APPROVER, Category.DECISIONS, Action.APPROVE)
        assert not is_permission_allowed(matrix, Role.APPROVER, Category.FORECASTS, Action.APPROVE)

    def test_approver_cannot_read_financials(self, matrix: dict[str, Any]) -> None:
        assert not is_permission_allowed(matrix, Role.APPROVER, Category.FINANCIALS, Action.READ)
        assert is_permission_allowed(matrix, Role.APPROVER, Category.DECISIONS, Action.READ)

    def test_unknown_roles_get_the_read_only_default(self, matrix: dict[str, Any]) -> None:
        for category in Category:
            assert is_permission_allowed(matrix, 'auditor', category, Action.READ)
            assert not is_permission_allowed(matrix, 'auditor', category, Action.WRITE)

    def test_denies_when_no_default_exists(self) -> None:
        assert not is_permission_allowed({}, Role.ANALYST, Category.METRICS, Action.READ)
