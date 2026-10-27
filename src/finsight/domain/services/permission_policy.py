"""Role/category/action permission evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import Action, DocumentCategory, Role

PermissionMatrix = Mapping[str, Mapping[str, Sequence[str]]]


def is_permission_allowed(
    permissions: PermissionMatrix,
    role: Role | str,
    category: DocumentCategory | str,
    action: Action | str,
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

    # Handle new permissions format with role_actions
    if isinstance(role_permissions, dict):
        role_actions = role_permissions.get('role_actions', [])
        if isinstance(role_actions, (list, tuple, set)) and action_id in role_actions:
            return True
        categories = role_permissions.get('categories', role_permissions)
        category_allowed = categories.get(category_id, ()) if isinstance(categories, dict) else ()
    else:
        return False

    allowed = category_allowed if isinstance(category_allowed, (list, tuple, set)) else ()
    if isinstance(allowed, str):
        allowed = [allowed]
    return bool('*' in allowed or action_id in allowed)
