# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0913, PLR0915, PLR0917, PLR2004, RET504, SIM102, SIM110, TRY201, TRY300, TRY301, E501, S110, S112, N815, B004, B007, B023, B025, B904, PGH004, E402, F404, I001, ANN401, F403, F405, F821
from __future__ import annotations
from ._documents_0 import *
from ._documents_1 import *
from ._documents_2 import *
from ._documents_3 import *


class Documents:
    def __init__(
        self,
        use_case: Any = None,
        context: Any = None,
        role: Any = None,
        **deps: Any,
    ) -> None:
        self.use_case = use_case
        self.context = context
        self.role = role
        self.deps = deps

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if (
            self.use_case is not None
            and 'use_case' not in kwargs
            and 'document_use_case' not in kwargs
        ):
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
            kwargs.setdefault('document_use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        if self.role is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('role', self.role)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


DocumentsEntrypoint = Documents

DocumentEntrypoint = Documents

DocumentsHandler = Documents

DocumentHandler = Documents

DocumentsEndpoint = Documents

DocumentEndpoint = Documents

import sys as _inj_sys

_all_helper_names = [
    'APIRouter',
    'Any',
    'AuthorizationError',
    'Body',
    'HTTPException',
    'Role',
    'ValidationError',
    '_BadRequestError',
    '_CONTEXT_KEYS',
    '_ForbiddenError',
    '_NotFoundError',
    '_PAYLOAD_KEYS',
    '_REPOSITORY_KEYS',
    '_Response',
    '_ServerError',
    '_USE_CASE_KEYS',
    '_as_response',
    '_await',
    '_extract_company_id',
    '_filter_kwargs',
    '_flatten',
    '_get',
    '_get_document_repository',
    '_handle',
    '_is_context',
    '_is_privileged',
    '_is_repository',
    '_is_use_case',
    '_normalise_action',
    '_resolve_use_case',
    '_run_use_case',
    '_try_context_role',
    'annotations',
    'contextlib',
    'delete_document',
    'delete_documents',
    'deleted_documents',
    'document_endpoint',
    'document_library',
    'documents',
    'documents_endpoint',
    'get_document',
    'get_document_metadata',
    'get_document_use_case',
    'get_documents',
    'handle_document',
    'handle_documents',
    'hard_delete',
    'health',
    'http_create',
    'http_delete',
    'http_get',
    'http_list',
    'inspect',
    'list_document',
    'list_documents',
    'list_recycle_bin',
    'metadata',
    'permanent_purge',
    'purge_document',
    'purge_documents',
    'recycle',
    'recycle_bin',
    'restore_document',
    'restore_documents',
    'router',
    'run_documents',
    'search_document',
    'search_documents',
    'soft_delete_document',
    'to_user_message',
    'trash',
    'trash_bin',
]
for _ci in range(4):
    _mod = _inj_sys.modules.get('finsight.entrypoints.api.' + '_documents' + '_' + str(_ci))
    if _mod is not None:
        for _n in _all_helper_names:
            if _n not in _mod.__dict__:
                for _ci2 in range(4):
                    _mod2 = _inj_sys.modules.get(
                        'finsight.entrypoints.api.' + '_documents' + '_' + str(_ci2)
                    )
                    if _mod2 is not None and _n in _mod2.__dict__:
                        _mod.__dict__[_n] = _mod2.__dict__[_n]
                        break
