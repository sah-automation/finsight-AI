# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0913, PLR0915, PLR0917, PLR2004, RET504, SIM102, SIM110, TRY201, TRY300, TRY301, E501, S110, S112, N815, B004, B007, B023, B025, B904, PGH004, E402, F404, I001, ANN401, F403, F405, F821
from __future__ import annotations

from typing import Any
from ._current_user_0 import *
from ._current_user_1 import *


class CurrentUser(BaseModel):
    """Authenticated user context used for navigation and access decisions."""

    company_id: str = Field(..., description='Authenticated company id.')
    company_name: str = Field(..., description='Company display name.')
    company_display_name: str = Field(..., description='Company display name (alias).')
    user_id: str | None = Field(default=None, description='Authenticated user id.')
    role: str = Field(..., description='Role identifier (ids from permissions.yaml).')
    role_id: str = Field(..., description='Role identifier (alias).')
    role_name: str | None = Field(default=None, description='Human-readable role name.')
    permissions: list[str] = Field(
        default_factory=list,
        description='Flat list of permission actions granted to the role.',
    )
    permission_actions: list[str] = Field(
        default_factory=list,
        description='Alias for permissions.',
    )
    actions: list[str] = Field(
        default_factory=list,
        description='Alias for permissions.',
    )
    role_actions: list[str] = Field(
        default_factory=list,
        description='Role-level actions (from permissions.yaml role_actions).',
    )
    category_permissions: dict[str, list[str]] = Field(
        default_factory=dict,
        description='Category scoped actions derived from permissions.yaml.',
    )


current_user = _handle

me = _handle

get_current_user = _handle

get_me = _handle

whoami = _handle

current_user_context = _handle

user_context = _handle

get_current_user_context = _handle

for _r in (
    router,
    router_me,
    router_current_user,
    router_current_user_underscore,
    router_users_me,
    router_user_me,
    router_auth_me,
    router_whoami,
):

    @_r.get('', operation_id='current_user_root_' + _r.prefix.strip('/'))
    async def _get_root(context: Any = None) -> CurrentUser:
        return await _handle(context=context)  # type: ignore[no-any-return]

    @_r.get('/', operation_id='current_user_slash_' + _r.prefix.strip('/'))
    async def _get_slash(context: Any = None) -> CurrentUser:
        return await _handle(context=context)  # type: ignore[no-any-return]


for _r in (router_users_me, router_user_me, router_auth_me):

    @_r.get('/me', operation_id='current_user_nested_me_' + _r.prefix.strip('/'))
    async def _get_nested_me(context: Any = None) -> CurrentUser:
        return await _handle(context=context)  # type: ignore[no-any-return]


__all__ = [
    'EXTRA_ROUTERS',
    'CurrentUser',
    'CurrentUserResponse',
    'current_user',
    'current_user_context',
    'get_current_user',
    'get_current_user_context',
    'get_me',
    'me',
    'router',
    'router_auth_me',
    'router_current_user',
    'router_current_user_underscore',
    'router_me',
    'router_user_me',
    'router_users_me',
    'router_whoami',
    'user_context',
    'whoami',
]

CurrentUserResponse = CurrentUser

import sys as _inj_sys

_all_helper_names = [
    'APIRouter',
    'Any',
    'BaseModel',
    'ConfigError',
    'EXTRA_ROUTERS',
    'Field',
    'HTTPException',
    'Role',
    'TYPE_CHECKING',
    '_CONTEXT_KEYS',
    '_await',
    '_context_lookup',
    '_ensure_config',
    '_extract_context_and_ids',
    '_fetch_company_name',
    '_find_repo_candidates',
    '_get',
    '_handle',
    '_http_current_user',
    '_is_context',
    '_normalize_role',
    'annotations',
    'get_config',
    'inspect',
    'load_config',
    'router',
    'router_auth_me',
    'router_current_user',
    'router_current_user_underscore',
    'router_me',
    'router_user_me',
    'router_users_me',
    'router_whoami',
]
for _ci in range(2):
    _mod = _inj_sys.modules.get('finsight.entrypoints.api.' + '_current_user' + '_' + str(_ci))
    if _mod is not None:
        for _n in _all_helper_names:
            if _n not in _mod.__dict__:
                for _ci2 in range(2):
                    _mod2 = _inj_sys.modules.get(
                        'finsight.entrypoints.api.' + '_current_user' + '_' + str(_ci2)
                    )
                    if _mod2 is not None and _n in _mod2.__dict__:
                        _mod.__dict__[_n] = _mod2.__dict__[_n]
                        break


import sys as _cu_sys

_mod = _cu_sys.modules.get('finsight.entrypoints.api._current_user_1')
if _mod is not None and 'CurrentUser' in globals():
    _mod.__dict__['CurrentUser'] = globals()['CurrentUser']
