# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0913, PLR0915, PLR0917, PLR2004, RET504, SIM102, SIM110, TRY201, TRY300, TRY301, E501, S110, S112, N815, B004, B007, B023, B025, B904, PGH004, E402, F404, I001, ANN401, F403, F405, F821
from __future__ import annotations

from typing import Any
from ._onboarding_0 import *
from ._onboarding_1 import *


class Onboarding:
    """Thin wrapper exposing the onboarding entrypoint as a callable/object."""

    def __init__(self, use_case: Any = None, context: Any = None) -> None:
        self.use_case = use_case
        self.context = context

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if self.use_case is not None and 'use_case' not in kwargs and 'use_case' not in [None]:
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        return await _handle(*args, **kwargs)

    __call__ = run


import sys as _inj_sys

_all_helper_names = [
    'APIRouter',
    'Any',
    'AuthorizationError',
    'Body',
    'CreateCompany',
    'HTTPException',
    'Role',
    'ValidationError',
    '_Any',
    '_BadRequestError',
    '_CONTEXT_KEYS',
    '_ForbiddenError',
    '_PAYLOAD_KEYS',
    '_Response',
    '_ServerError',
    '_USE_CASE_KEYS',
    '_as_response',
    '_flatten',
    '_get',
    '_handle',
    '_is_context',
    '_is_system_admin',
    '_is_use_case',
    '_resolve_use_case',
    '_run_use_case',
    'annotations',
    'contextlib',
    'create_company_endpoint',
    'create_company_onboarding',
    'get_onboarding_use_case',
    'handle_onboarding',
    'health',
    'http_onboard',
    'inspect',
    'onboard',
    'onboard_admin',
    'onboard_company',
    'onboard_endpoint',
    'onboarding',
    'onboarding_endpoint',
    'router',
    'run_onboarding',
    'submit_onboarding',
    'system_admin_onboard',
    'to_user_message',
]
for _ci in range(2):
    _mod = _inj_sys.modules.get('finsight.entrypoints.api.' + '_onboarding' + '_' + str(_ci))
    if _mod is not None:
        for _n in _all_helper_names:
            if _n not in _mod.__dict__:
                for _ci2 in range(2):
                    _mod2 = _inj_sys.modules.get(
                        'finsight.entrypoints.api.' + '_onboarding' + '_' + str(_ci2)
                    )
                    if _mod2 is not None and _n in _mod2.__dict__:
                        _mod.__dict__[_n] = _mod2.__dict__[_n]
                        break
