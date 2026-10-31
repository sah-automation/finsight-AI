# ruff: noqa: PLR0912, PLR0915, B904, I001, F403, F405
from __future__ import annotations
from typing import Any
from finsight.core.types import DocumentCategory
from ._upload_0 import *
from ._upload_1 import *


def _extract_company_id(context: Any, data: dict[str, Any]) -> Any:
    value = _get(data, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId')
    if value is None and context is not None:
        if isinstance(context, dict):
            value = _get(context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId')
            if value is None and 'user' in context:
                value = _extract_company_id(context.get('user'), {})
            if value is None and 'context' in context:
                value = _extract_company_id(context.get('context'), {})
        else:
            value = _get(context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId')
            if value is None and hasattr(context, 'company_id'):
                value = getattr(context, 'company_id', None)
    return value


def _try_context_role(context: Any) -> Any:
    if context is None:
        return None
    if isinstance(context, dict):
        for key in ('role', 'role_id', 'roleId', 'roles'):
            if key in context:
                return context.get(key)
        for nested in ('user', 'principal', 'identity', 'current_user'):
            if nested in context:
                found = _try_context_role(context.get(nested))
                if found is not None:
                    return found
        return None
    return _get(context, 'role')


async def _validate_form(data: dict[str, Any], config: Any = None) -> None:
    company_id = data.get('company_id')
    if company_id is None or str(company_id).strip() == '':
        raise _BadRequestError('company_id is required.')

    upload_type_raw = _get(data, 'upload_type')
    if upload_type_raw is None:
        raise _BadRequestError('upload_type is required (new or update).')
    upload_type = str(upload_type_raw).strip().lower()
    if upload_type not in _UPLOAD_TYPES:
        raise _BadRequestError('upload_type must be new or update.')
    data['upload_type'] = upload_type

    document_category = _get(data, 'document_category')
    if document_category is None:
        raise _BadRequestError('document_category is required.')
    category_text = str(document_category).strip()

    allowed_categories: list[str] | None = None
    if config is not None:
        candidate = None
        if isinstance(config, dict):
            candidate = config.get('documents', config.get('document', {}))
        else:
            candidate = _get(config, 'documents', 'document')
        categories = None
        if isinstance(candidate, dict):
            categories = candidate.get('categories', candidate.get('category', None))
        elif candidate is not None:
            categories = _get(candidate, 'categories', 'category')
        if isinstance(categories, (list, tuple, set)):
            allowed_categories = [str(item) for item in categories]
    request_allowed = _get(data, 'categories', 'allowed_categories', 'document_categories')
    if isinstance(request_allowed, (list, tuple, set)):
        allowed_categories = [str(item) for item in request_allowed]

    if allowed_categories is not None:
        if category_text not in allowed_categories:
            raise _BadRequestError('document_category is not allowed.')
    else:
        try:
            DocumentCategory(category_text)
        except ValueError:
            raise _BadRequestError('document_category is not valid.')
    data['document_category'] = category_text

    period = _get(data, 'period')
    if period is None:
        raise _BadRequestError('period is required.')
    period_text = str(period).strip()
    if not _PERIOD_RE.match(period_text):
        raise _BadRequestError('period must be YYYY-QX or YYYY-MM.')
    data['period'] = period_text

    status_value = _get(data, 'status')
    if status_value is None:
        raise _BadRequestError('status is required (draft or final).')
    status_text = str(status_value).strip().lower()
    if status_text not in _STATUS_VALUES:
        raise _BadRequestError('status must be draft or final.')
    data['status'] = status_text

    if upload_type == 'update':
        replaces = _get(data, 'replaces_document_id')
        if replaces is None or str(replaces).strip() == '':
            raise _BadRequestError('replaces_document_id is required for update uploads.')


__all__ = ['_extract_company_id', '_try_context_role', '_validate_form']
