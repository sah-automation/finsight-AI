"""Deep module: source-view authorization (role matrix) step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from finsight.application.source_viewer._step_helpers import _allowed_contains, _as_list
from finsight.application.source_viewer.step_result import StepResult
from finsight.domain.services.permission_policy import is_permission_allowed

if TYPE_CHECKING:
    from finsight.application.source_viewer.source_viewer_context import SourceViewerContext

PermissionsConfig = Any

_ROLE_KEYS = (
    'executive_leadership',
    'corporate_finance_planners',
    'audit_compliance',
    'system_admin',
)


class AuthorizeStep:
    """Authorization gate for the source-viewer pipeline.

    The permission policy is injected (resolved from configuration by the
    composition root). No config or environment access happens here.
    """

    def __init__(
        self,
        *,
        permission_policy: PermissionsConfig | dict[str, Any] | None = None,
    ) -> None:
        self._permission_policy = permission_policy

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

        if isinstance(current, dict):
            converted: dict[Any, Any] = {}
            for key, value in current.items():
                model_dump = getattr(value, 'model_dump', None)
                if callable(model_dump):
                    try:
                        converted[key] = model_dump()
                        continue
                    except (TypeError, ValueError, AttributeError):
                        pass
                converted[key] = value
            if self._is_permission_map(converted):
                return converted['permissions']
            return policy if isinstance(policy, dict) else converted

        if isinstance(policy, dict):
            return policy['permissions'] if self._is_permission_map(policy) else policy

        model_dump = getattr(policy, 'model_dump', None)
        if callable(model_dump):
            try:
                dumped = model_dump()
            except (TypeError, ValueError, AttributeError):
                dumped = None
            if isinstance(dumped, dict):
                return dumped['permissions'] if self._is_permission_map(dumped) else dumped
        return None

    @staticmethod
    def _is_permission_map(candidate: dict[Any, Any]) -> bool:
        return isinstance(candidate.get('permissions'), dict) and not any(
            str(key) in candidate for key in _ROLE_KEYS
        )

    def _role_text(self, role_raw: Any) -> str:
        return str(getattr(role_raw, 'value', role_raw) or '').strip()

    def _category_text(self, category: Any) -> str:
        return str(getattr(category, 'value', category))

    def _authorize_role(
        self, role_raw: Any, permissions: Any, access_scope: Any, category: Any
    ) -> bool:
        role_text = self._role_text(role_raw)
        # System admin should not read financial content.
        if role_text == 'system_admin':
            return False

        scope_list = _as_list(access_scope)
        scope_values = [str(getattr(x, 'value', x)) for x in scope_list]

        # If category known, enforce access scope membership + read permission.
        if category is not None:
            cat_text = self._category_text(category)
            if scope_list and cat_text not in scope_values:
                return False
            if not self._has_read_permission(role_raw, permissions, category, scope_list):
                return False
        return True

    def _has_read_permission(  # noqa: PLR0911, PLR0912
        self, role_raw: Any, permissions: Any, category: Any, access_scope: Any
    ) -> bool:
        _ = access_scope
        cat_text = self._category_text(category)
        role_text = str(getattr(role_raw, 'value', role_raw) or '')

        if isinstance(permissions, dict):
            role_perms = permissions.get(role_text, permissions.get(str(role_text)))
            if role_perms is not None:
                if self._allowed_by_matrix(permissions, role_raw, category, 'read'):
                    return True
                if isinstance(role_perms, dict):
                    cats = role_perms.get('categories', role_perms)
                    if isinstance(cats, dict):
                        allowed = cats.get(cat_text, cats.get(str(category), ()))
                        if _allowed_contains(allowed, 'read'):
                            return True

            direct = permissions.get(cat_text, permissions.get(str(category)))
            if (
                cat_text not in permissions
                and str(category) not in permissions
                and role_text not in permissions
            ):
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

        if permissions is None:
            matrix = self._configured_matrix()
            if isinstance(matrix, dict) and self._allowed_by_matrix(
                matrix, role_raw, category, 'read'
            ):
                return True
        return bool(permissions is None and not isinstance(self._configured_matrix(), dict))

    def _allowed_by_matrix(self, matrix: Any, role_raw: Any, category: Any, action: str) -> bool:
        try:
            return bool(is_permission_allowed(matrix, role_raw, category, action))
        except (TypeError, ValueError):
            return False

    def _is_original_available(self, role_raw: Any, permissions: Any, category: Any) -> bool:
        if category is None:
            return False
        role_text = str(getattr(role_raw, 'value', role_raw) or '')
        if role_text == 'system_admin':
            return False
        cat_text = self._category_text(category)
        if isinstance(permissions, dict):
            direct = permissions.get(cat_text)
            if isinstance(direct, (list, tuple, set)):
                values = [str(getattr(x, 'value', x)).lower() for x in direct]
                if 'view_original' in values:
                    return True
            if permissions.get(role_text) is not None:
                matrix = permissions
                if self._configured_matrix() is not None:
                    matrix = self._configured_matrix()
                if self._allowed_by_matrix(matrix, role_raw, category, 'view_original'):
                    return True
        matrix = self._configured_matrix()
        if isinstance(matrix, dict):
            return self._allowed_by_matrix(matrix, role_raw, category, 'view_original')
        return False

    async def run(self, context: SourceViewerContext) -> StepResult:
        """Execute this pipeline step."""
        role_raw = context.role
        permissions = context.permissions
        access_scope = context.access_scope
        category = context.category

        allowed = self._authorize_role(role_raw, permissions, access_scope, category)
        context.original_available = self._is_original_available(role_raw, permissions, category)

        if allowed:
            return StepResult.continue_(context)
        return StepResult.stop_with_not_available(context)


__all__ = ['AuthorizeStep']
