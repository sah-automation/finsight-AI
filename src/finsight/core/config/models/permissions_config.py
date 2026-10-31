from typing import Any

from pydantic import model_validator

from .role_permission_entry import RolePermissionEntry
from .strict_base_model import (
    StrictBaseModel,
)


class PermissionsConfig(StrictBaseModel):
    roles: list[dict[str, Any]]
    categories: list[dict[str, Any]]
    permissions: dict[str, RolePermissionEntry]

    @model_validator(mode='after')
    def validate_permissions_complete(self) -> 'PermissionsConfig':
        role_ids = {r.get('id') for r in self.roles}
        expected_roles = {
            'executive_leadership',
            'corporate_finance_planners',
            'audit_compliance',
            'system_admin',
        }
        if role_ids != expected_roles:
            raise ValueError('permissions must define exactly the 4 Phase 1 roles')
        category_ids = {c.get('id') for c in self.categories}
        expected_categories = {
            'invoice',
            'bank_statement',
            'financial_statement',
            'budget',
            'contract',
            'board_report',
        }
        if category_ids != expected_categories:
            raise ValueError('permissions must define exactly the 6 categories')
        if set(self.permissions.keys()) != expected_roles:
            raise ValueError('permissions matrix must cover all roles')
        for role_id, role_perm in self.permissions.items():
            if role_id == 'system_admin':
                continue  # system_admin may have empty categories
            if set(role_perm.categories.keys()) != expected_categories:
                raise ValueError(f'role {role_id} must define all categories')
        return self
