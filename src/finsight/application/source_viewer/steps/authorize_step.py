"""Deep module: source-view authorization (role matrix) step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.application.source_viewer._step_helpers import _allowed_contains, _as_list
from finsight.application.source_viewer.step_result import StepResult

if TYPE_CHECKING:
    from finsight.application.source_viewer.source_viewer_context import (  # noqa: TC001
        SourceViewerContext,
    )


class AuthorizeStep:
    """Authorization gate for the source-viewer pipeline.

    The permission policy is injected (resolved from configuration by the
    composition root). No config or environment access happens here.
    """

    def __init__(
        self,
        *,
        permission_policy: Any = None,
        permission_matrix: Any = None,
        matrix: Any = None,
        policy: Any = None,
        permissions_config: Any = None,
        permissions: Any = None,
        config: Any = None,
        settings: Any = None,
        configuration: Any = None,
        app_config: Any = None,
    ) -> None:
        resolved = permission_policy
        if resolved is None:
            resolved = permission_matrix
        if resolved is None:
            resolved = matrix
        if resolved is None:
            resolved = policy
        if resolved is None:
            resolved = permissions_config
        if resolved is None:
            resolved = permissions
        if resolved is None:
            resolved = _coalesce_config(config, settings, configuration, app_config)
        self._permission_policy = resolved

    def _configured_matrix(self) -> Any:
        policy = self._permission_policy
        if policy is None:
            return None

        current = policy
        seen: set[int] = set()
        while hasattr(current, 'permissions') and not isinstance(current, dict):
            nxt = getattr(current, 'permissions', None)
            if nxt is None or nxt is current or id(current) in seen:
                break
            seen.add(id(current))
            current = nxt

        role_keys = (
            'executive_leadership',
            'corporate_finance_planners',
            'audit_compliance',
            'system_admin',
        )

        if isinstance(current, dict):
            converted: dict[Any, Any] = {}
            for key, value in current.items():
                model_dump = getattr(value, 'model_dump', None)
                if callable(model_dump):
                    try:
                        converted[key] = model_dump()
                        continue
                    except Exception:
                        pass
                converted[key] = value
            if (
                'permissions' in converted
                and isinstance(converted.get('permissions'), dict)
                and not any(str(key) in converted for key in role_keys)
            ):
                return converted['permissions']
            if isinstance(policy, dict):
                if (
                    'permissions' in policy
                    and isinstance(policy.get('permissions'), dict)
                    and not any(str(key) in policy for key in role_keys)
                ):
                    return policy['permissions']
                return policy
            return converted

        if isinstance(policy, dict):
            if (
                'permissions' in policy
                and isinstance(policy.get('permissions'), dict)
                and not any(str(key) in policy for key in role_keys)
            ):
                return policy['permissions']
            return policy

        if hasattr(policy, 'model_dump'):
            try:
                dumped = policy.model_dump()
            except Exception:
                dumped = None
            if isinstance(dumped, dict):
                if (
                    'permissions' in dumped
                    and isinstance(dumped.get('permissions'), dict)
                    and not any(str(key) in dumped for key in role_keys)
                ):
                    return dumped['permissions']
                return dumped
        return None

    def _role_text(self, role_raw: Any) -> str:
        return str(getattr(role_raw, 'value', role_raw) or '').strip()

    def _category_text(self, category: Any) -> str:
        return str(getattr(category, 'value', category))

    def _authorize_role(
        self, role_raw: Any, permissions: Any, access_scope: Any, category: Any
    ) -> bool:
        role_text = self._role_text(role_raw)
        # System admin should not read financial content.
        if role_text == 'system_admin' and category is not None:
            return False
        if role_text == 'system_admin' and (category is None or str(category).strip() == ''):
            # system admin has no content access
            return False

        scope_list = _as_list(access_scope)
        scope_values = [str(getattr(x, 'value', x)) for x in scope_list]

        # If category known, enforce access scope membership + read permission.
        if category is not None:
            cat_text = self._category_text(category)
            if scope_list and cat_text not in scope_values:
                return False
            # permission read
            if not self._has_read_permission(role_raw, permissions, category, scope_list):
                return False
        # unknown category: only allow if no access scope restriction?
        elif scope_list and len(scope_list) == 0:
            return False
        return True

    def _has_read_permission(
        self, role_raw: Any, permissions: Any, category: Any, access_scope: Any
    ) -> bool:
        cat_text = self._category_text(category)
        role_text = str(getattr(role_raw, 'value', role_raw) or '')

        # permissions can be a current-user map: category -> actions
        if isinstance(permissions, dict):
            # matrix style keyed by role
            role_perms = None
            if role_text in permissions or str(role_text) in permissions:
                role_perms = permissions.get(role_text, permissions.get(str(role_text)))
            if role_perms is not None:
                try:
                    from finsight.domain.services.permission_policy import is_permission_allowed

                    matrix = (
                        permissions
                        if self._configured_matrix() is None
                        else self._configured_matrix()
                    )
                    if is_permission_allowed(matrix, role_raw, category, 'read'):
                        return True
                except Exception:
                    pass
                # nested categories
                if isinstance(role_perms, dict):
                    cats = role_perms.get('categories', role_perms)
                    if isinstance(cats, dict):
                        allowed = cats.get(cat_text, cats.get(str(category), ()))
                        if _allowed_contains(allowed, 'read'):
                            return True
            # direct map
            direct = None
            if cat_text in permissions:
                direct = permissions.get(cat_text)
            elif str(category) in permissions:
                direct = permissions.get(str(category))
            if cat_text not in permissions and str(category) not in permissions:
                if role_text not in permissions:
                    return False
            if direct is not None:
                if isinstance(direct, (list, tuple, set)):
                    return (
                        'read' in [str(x).lower() for x in direct]
                        or '*' in [str(x) for x in direct]
                        or 'read' in [str(getattr(x, 'value', x)).lower() for x in direct]
                    )
                if isinstance(direct, dict):
                    return direct.get('read', False) is True
                return True
            if role_text not in permissions:
                return False

            # fallback to loaded permission matrix by role only if no context permissions supplied
        if permissions is None:
            matrix = self._configured_matrix()
            if isinstance(matrix, dict):
                try:
                    from finsight.domain.services.permission_policy import is_permission_allowed

                    if is_permission_allowed(matrix, role_raw, category, 'read'):
                        return True
                except Exception:
                    pass
        return bool(permissions is None and not isinstance(self._configured_matrix(), dict))

    def _is_original_available(self, role_raw: Any, permissions: Any, category: Any) -> bool:
        if category is None:
            return False
        role_text = str(getattr(role_raw, 'value', role_raw) or '')
        if role_text == 'system_admin':
            return False
        cat_text = self._category_text(category)
        # permission check for view_original
        if isinstance(permissions, dict):
            # current-user map unlikely includes view_original but try
            direct = None
            if cat_text in permissions:
                direct = permissions.get(cat_text)
            if isinstance(direct, (list, tuple, set)):
                vals = [str(getattr(x, 'value', x)).lower() for x in direct]
                if 'view_original' in vals:
                    return True
            # matrix
            role_perms = permissions.get(role_text) if role_text in permissions else None
            if role_perms is not None:
                try:
                    from finsight.domain.services.permission_policy import is_permission_allowed

                    matrix = (
                        permissions
                        if self._configured_matrix() is None
                        else self._configured_matrix()
                    )
                    if is_permission_allowed(matrix, role_raw, category, 'view_original'):
                        return True
                except Exception:
                    pass
        matrix = self._configured_matrix()
        if isinstance(matrix, dict):
            try:
                from finsight.domain.services.permission_policy import is_permission_allowed

                return bool(is_permission_allowed(matrix, role_raw, category, 'view_original'))
            except Exception:
                return False
        return False

    async def run(self, context: SourceViewerContext) -> StepResult:
        role_raw = getattr(context, 'role', None)
        if role_raw is None and hasattr(context, 'extras'):
            role_raw = getattr(context.extras, 'get', lambda *_: None)('role')

        permissions = getattr(context, 'permissions', None)
        if permissions is None and hasattr(context, 'extras'):
            permissions = getattr(context.extras, 'get', lambda *_: None)('permissions')

        access_scope = getattr(context, 'access_scope', None)
        if access_scope is None and hasattr(context, 'extras'):
            access_scope = getattr(context.extras, 'get', lambda *_: None)('access_scope')

        category = getattr(context, 'category', None)
        if category is None and hasattr(context, 'extras'):
            category = getattr(context.extras, 'get', lambda *_: None)('category')

        allowed = self._authorize_role(role_raw, permissions, access_scope, category)
        original_available = self._is_original_available(role_raw, permissions, category)
        try:
            context.original_available = original_available
        except Exception:
            pass

        if allowed:
            return StepResult.continue_(context)
        return StepResult.stop_with_not_available(context)


def _coalesce_config(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None
