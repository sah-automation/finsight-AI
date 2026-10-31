# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0913, PLR0915, PLR0917, PLR2004, RET504, SIM102, SIM110, TRY201, TRY300, TRY301, E501, S110, S112, N815, B004, B007, B023, B025, B904, PGH004, E402, F404, I001, ANN401, F403, F405, F821
from __future__ import annotations

from typing import Any
from ._upload_0 import *
from ._upload_1 import *
from ._upload_2 import *
from ._upload_3 import *


class Upload:
    def __init__(
        self, use_case: Any = None, context: Any = None, partition_manager: Any = None, **deps: Any
    ) -> None:
        self.use_case = use_case
        self.context = context
        self.partition_manager = partition_manager
        self.deps = deps

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if (
            self.use_case is not None
            and 'use_case' not in kwargs
            and 'upload_use_case' not in kwargs
        ):
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        if self.partition_manager is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('partition_manager', self.partition_manager)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


UploadHandler = Upload

UploadEndpoint = Upload

UploadEntrypoint = Upload

import sys as _inj_sys

_all_helper_names = [
    'APIRouter',
    'Any',
    'AuthorizationError',
    'Body',
    'DocumentCategory',
    'HTTPException',
    'Role',
    'ValidationError',
    '_BadRequestError',
    '_CHECKER_KEYS',
    '_CONTEXT_KEYS',
    '_ForbiddenError',
    '_PARTITION_MANAGER_KEYS',
    '_PARTITION_METADATA_KEYS',
    '_PAYLOAD_KEYS',
    '_PERIOD_RE',
    '_PartitionMissingError',
    '_STATUS_VALUES',
    '_ServerError',
    '_UPLOAD_TYPES',
    '_USE_CASE_KEYS',
    '_UploadResponse',
    '_as_response',
    '_await',
    '_call_method',
    '_extract_company_id',
    '_flatten',
    '_get',
    '_handle',
    '_is_context',
    '_is_partition_manager',
    '_is_partition_metadata_repo',
    '_is_use_case',
    '_partition_exists',
    '_resolve_use_case',
    '_run_use_case',
    '_truthy',
    '_try_context_role',
    '_validate_form',
    'annotations',
    'contextlib',
    'create_upload',
    'get_upload_use_case',
    'handle_file_upload',
    'handle_upload',
    'health',
    'http_upload',
    'inspect',
    'process_upload',
    're',
    'router',
    'run_upload',
    'submit_upload',
    'to_user_message',
    'upload',
    'upload_document',
    'upload_endpoint',
    'upload_file',
    'uploads',
]
for _ci in range(4):
    _mod = _inj_sys.modules.get('finsight.entrypoints.api.' + '_upload' + '_' + str(_ci))
    if _mod is not None:
        for _n in _all_helper_names:
            if _n not in _mod.__dict__:
                for _ci2 in range(4):
                    _mod2 = _inj_sys.modules.get(
                        'finsight.entrypoints.api.' + '_upload' + '_' + str(_ci2)
                    )
                    if _mod2 is not None and _n in _mod2.__dict__:
                        _mod.__dict__[_n] = _mod2.__dict__[_n]
                        break
