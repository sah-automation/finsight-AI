"""Role/category/action permission evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import Action, Category, Role

PermissionMatrix = Mapping[str, Mapping[str, Sequence[str]]]


def is_permission_allowed(
    permissions: PermissionMatrix,
    role: Role | str,
    category: Category,
    action: Action,
) -> bool:
    """Return True when the role may perform the action on the category."""
    role_id = str(getattr(role, 'value', role))
    role_permissions = permissions.get(role_id)
    if role_permissions is None:
        role_permissions = permissions.get('default')
    if role_permissions is None:
        return False

    action_id = str(getattr(action, 'value', action))
    category_id = str(getattr(category, 'value', category))

    allowed = role_permissions.get('*', ())
    if '*' in allowed or action_id in allowed:
        return True

    category_allowed = role_permissions.get(category_id, ())
    return '*' in category_allowed or action_id in category_allowed
