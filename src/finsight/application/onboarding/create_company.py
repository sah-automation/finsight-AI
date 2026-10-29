"""Use case: create (onboard) a company and prepare its partitions."""

from __future__ import annotations

import contextlib
import inspect
import re
import time
import uuid
from typing import Any

from finsight.core.errors import ConfigError, ValidationError
from finsight.core.types import CompanyId, Role, UserId
from finsight.domain.entities.company import Company

from .models import (
    CreateCompanyResult,
    OnboardingStatus,
)

_DEFAULT_PARTITION_TABLES = (
    'documents',
    'document_chunks',
    'document_tables',
    'metrics',
    'answers',
    'audit_logs',
)

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _first(mapping: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(mapping, dict):
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        elif hasattr(mapping, key):
            value = getattr(mapping, key, None)
            if value is not None:
                return value
    return default


def _slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return slug or 'company'


def _company_id_for(request_key: str | None) -> CompanyId:
    if request_key:
        return CompanyId(str(uuid.uuid5(uuid.NAMESPACE_URL, f'finsight:onboarding:{request_key}')))
    return CompanyId(str(uuid.uuid4()))


class CreateCompany:
    """Orchestrate the creation (onboarding) of a company tenant."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._company_repository = _get_attr(
            kwargs, 'company_repository', 'company_repo', default=None
        )
        self._user_repository = _get_attr(kwargs, 'user_repository', 'user_repo', default=None)
        self._partition_manager = _get_attr(
            kwargs, 'partition_manager', 'partition_gateway', default=None
        )
        self._partition_metadata_repository = _get_attr(
            kwargs,
            'partition_metadata_repository',
            'partition_metadata_repo',
            'partition_metadata',
            default=None,
        )
        self._audit_log = _get_attr(
            kwargs,
            'audit_log',
            'audit_logger',
            'audit_repository',
            'audit_log_repository',
            default=None,
        )
        self._role_cache = _get_attr(
            kwargs,
            'role_cache',
            'role_cache_port',
            'role_cache_repository',
            default=None,
        )
        self._metering = _get_attr(kwargs, 'metering', 'meter', 'metering_port', default=None)
        self._document_stamp = _get_attr(
            kwargs,
            'document_stamp',
            'document_stamp_repository',
            'stamp',
            'stamp_repository',
            default=None,
        )
        self._unit_of_work = _get_attr(
            kwargs, 'unit_of_work', 'uow', 'transaction', 'tx', default=None
        )
        self._config = _get_attr(
            kwargs, 'config', 'settings', 'configuration', 'app_config', default=None
        )

        positional = [
            '_company_repository',
            '_user_repository',
            '_partition_manager',
            '_partition_metadata_repository',
            '_audit_log',
            '_role_cache',
            '_metering',
            '_document_stamp',
            '_unit_of_work',
            '_config',
        ]
        for index, value in enumerate(args):
            if index < len(positional):
                setattr(self, positional[index], value)

        self._request_cache: dict[str, CreateCompanyResult] = {}
        self._allowed_regions = self._resolve_allowed_regions()
        self._tables = self._resolve_tables()

    # Public entry points
    def execute(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def run(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def __call__(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def onboard(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def create(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    def create_company(self, request: Any = None, **kwargs: Any) -> Any:
        return self._run(request, kwargs)

    async def _run(  # noqa: PLR0912
        self, request: Any = None, extra: dict[str, Any] | None = None
    ) -> CreateCompanyResult:
        extra = extra or {}
        request = self._normalise_input(request, extra)

        name = str(
            _get_attr(
                request,
                'company_name',
                'name',
                'display_name',
                'company_display_name',
                'company',
                default='',
            )
        ).strip()
        region = str(
            _get_attr(request, 'region', 'preferred_region', 'hosting_region', default='')
        ).strip()
        admin_email = str(
            _get_attr(
                request,
                'admin_email',
                'first_admin_email',
                'email',
                'admin_user_email',
                'user_email',
                default='',
            )
        ).strip()
        request_key_raw = _get_attr(
            request, 'request_key', 'request_id', 'idempotency_key', default=None
        )
        request_key = str(request_key_raw).strip() if request_key_raw is not None else None
        if request_key == '':
            request_key = None

        if not name:
            raise ValidationError('company name is required')
        if not region:
            raise ValidationError('region is required')
        if region not in self._allowed_regions:
            raise ValidationError(f'region {region!r} is not approved')
        if not admin_email or not _EMAIL_RE.match(admin_email):
            raise ValidationError('a valid admin email is required')

        if request_key is not None and request_key in self._request_cache:
            return self._request_cache[request_key]

        cells = self._resolve_cells()
        company_id = _company_id_for(request_key)

        tx = None
        if self._unit_of_work is not None:
            tx = await self._begin_transaction()

        try:
            start = time.monotonic()

            company = None
            if self._company_repository is not None:
                company = await _await(
                    self._company_repository.create_company(
                        company_id, name, _slugify(name) + '-' + str(company_id)[:8]
                    )
                )

            partition_names: list[str] = []
            if self._partition_manager is not None:
                for table in self._tables:
                    partition_name = await _await(
                        self._partition_manager.create_partition(company_id, table)
                    )
                    partition_names.append(str(partition_name))
                    await self._record_partition_metadata(company_id, str(partition_name), table)

            user_id = UserId(str(uuid.uuid4()))
            user = None
            if self._user_repository is not None:
                user = await _await(
                    self._user_repository.create_user(
                        company_id, user_id, admin_email, Role.SYSTEM_ADMIN
                    )
                )

            await self._initialise_document_stamp(company_id)
            await self._seed_role_cache(company_id, admin_email, user_id)
            await self._write_audit_log(company_id, name, region)
            await self._meter_run(start, company_id)

            result = CreateCompanyResult(
                company_id=company_id,
                status=OnboardingStatus.READY,
                company=company
                if company is not None
                else Company(
                    id=company_id, name=name, slug=_slugify(name) + '-' + str(company_id)[:8]
                ),
                user=user,
                partition_names=partition_names,
                region=region,
                cell=1,
                request_key=request_key,
                cells=cells,
            )

            if tx is not None:
                await self._commit_transaction(tx)

            if request_key is not None:
                self._request_cache[request_key] = result
            return result  # noqa: TRY300
        except Exception:
            if tx is not None:
                await self._rollback_transaction(tx)
            raise

    def _normalise_input(self, request: Any, extra: dict[str, Any]) -> Any:
        if request is None and not extra:
            return {}
        if isinstance(request, dict):
            merged = dict(request)
            merged.update(extra)
            return merged
        if request is not None and not extra:
            return request
        wrapper: dict[str, Any] = {}
        if request is not None:
            for attr in (
                'company_name',
                'name',
                'display_name',
                'company_display_name',
                'company',
                'region',
                'preferred_region',
                'hosting_region',
                'admin_email',
                'first_admin_email',
                'email',
                'admin_user_email',
                'user_email',
                'request_key',
                'request_id',
                'idempotency_key',
            ):
                value = _get_attr(request, attr, default=None)
                if value is not None:
                    wrapper[attr] = value
        wrapper.update(extra)
        return wrapper

    def _resolve_allowed_regions(self) -> set[str]:
        regions: set[str] = {'us', 'us-east-1', 'us-west-2', 'us-east-2'}
        if self._config is not None:
            scale = _get_attr(self._config, 'scale', default=None)
            if isinstance(scale, dict):
                cand = _first(scale, 'allowed_regions', 'regions', 'approved_regions', default=None)
                if isinstance(cand, (list, tuple, set)):
                    regions = {str(item) for item in cand}
            elif scale is not None:
                cand = _get_attr(
                    scale, 'allowed_regions', 'regions', 'approved_regions', default=None
                )
                if isinstance(cand, (list, tuple, set)):
                    regions = {str(item) for item in cand}
            region = _get_attr(self._config, 'region', default=None) or _get_attr(
                _get_attr(self._config, 'storage', default=None), 'region', default=None
            )
            if isinstance(region, str) and region:
                regions.add(region)
        return regions

    def _resolve_cells(self) -> int:
        cells = 1
        if self._config is not None:
            scale = _get_attr(self._config, 'scale', default=None)
            if isinstance(scale, dict):
                raw = _first(scale, 'cells', default=None)
            elif scale is not None:
                raw = _get_attr(scale, 'cells', default=None)
            else:
                raw = None
            if raw is None:
                raw = _get_attr(self._config, 'cells', default=None)
            if raw is None:
                return 1
            try:
                cells = int(raw)
            except (TypeError, ValueError):
                raise ConfigError('scale.cells must be an integer') from None
        if cells < 1:
            raise ConfigError('scale.cells must be 1 or more')
        return cells

    def _resolve_tables(self) -> tuple[str, ...]:
        manager = self._partition_manager
        if (
            manager is not None
            and hasattr(manager, '_tables')
            and isinstance(getattr(manager, '_tables', None), (list, tuple))
        ):
            return tuple(str(item) for item in manager._tables)
        return _DEFAULT_PARTITION_TABLES

    async def _record_partition_metadata(
        self, company_id: CompanyId, partition_name: str, table: str
    ) -> None:
        repo = self._partition_metadata_repository
        if repo is not None:
            method = None
            for candidate in ('record_partition', 'record_partition_metadata', 'record', 'create'):
                candidate_method = getattr(repo, candidate, None)
                if callable(candidate_method):
                    method = candidate_method
                    break
            if method is not None:
                try:
                    sig = inspect.signature(method)
                    kwargs = self._fill_kwargs(
                        sig,
                        {
                            'company_id': company_id,
                            'partition_name': partition_name,
                            'partition': partition_name,
                            'table_name': table,
                            'table': table,
                            'status': 'ready',
                        },
                    )
                    await _await(method(**kwargs))
                    return  # noqa: TRY300
                except TypeError:
                    pass
        pm = self._partition_manager
        if pm is not None:
            method = getattr(pm, 'record_partition_metadata', None)
            if callable(method):
                try:
                    await _await(method(company_id, partition_name, table))
                except TypeError:
                    pass
                else:
                    return
                with contextlib.suppress(TypeError):
                    await _await(
                        method(
                            company_id=company_id,
                            partition_name=partition_name,
                            table_name=table,
                        )
                    )

    async def _initialise_document_stamp(self, company_id: CompanyId) -> None:
        dep = self._document_stamp
        await self._invoke_optional(
            dep,
            (
                'create_document_stamp',
                'record_document_stamp',
                'create_stamp',
                'record_stamp',
                'create',
                'ensure',
                'seed',
                'initialize',
            ),
            {
                'company_id': company_id,
            },
        )

    async def _seed_role_cache(
        self, company_id: CompanyId, admin_email: str, user_id: UserId
    ) -> None:
        dep = self._role_cache
        await self._invoke_optional(
            dep,
            (
                'seed_role_cache',
                'initialize_role_cache',
                'seed',
                'initialize',
                'create',
                'create_role_version',
                'seed_role_version',
                'put',
                'warm',
            ),
            {
                'company_id': company_id,
                'user_id': user_id,
                'email': admin_email,
                'admin_email': admin_email,
                'role': Role.SYSTEM_ADMIN,
            },
        )

    async def _write_audit_log(self, company_id: CompanyId, name: str, region: str) -> None:
        dep = self._audit_log
        await self._invoke_optional(
            dep,
            (
                'write_audit_log',
                'record_audit',
                'write_audit',
                'record',
                'log',
                'append',
                'create',
                'create_audit_log',
            ),
            {
                'company_id': company_id,
                'action': 'company_onboarded',
                'event': 'company_onboarded',
                'resource': 'company',
                'resource_id': str(company_id),
                'details': {'name': name, 'region': region},
                'metadata': {'name': name, 'region': region},
            },
        )

    async def _meter_run(self, start: float, company_id: CompanyId) -> None:
        if self._metering is None:
            return
        duration_ms = (time.monotonic() - start) * 1000.0
        await self._invoke_optional(
            self._metering,
            ('record', 'record_run', 'meter', 'track', 'emit', 'record_metering'),
            {
                'company_id': company_id,
                'duration_ms': duration_ms,
                'duration': duration_ms,
                'service': 'onboarding',
                'operation': 'create_company',
                'units': 1,
            },
        )

    async def _invoke_optional(
        self, dep: Any, candidates: tuple[str, ...], context: dict[str, Any]
    ) -> None:
        if dep is None:
            return
        method = None
        for candidate in candidates:
            found = getattr(dep, candidate, None)
            if callable(found):
                method = found
                break
        if method is None:
            return
        try:
            sig = inspect.signature(method)
        except (TypeError, ValueError):
            sig = None
        kwargs = self._fill_kwargs(sig, context) if sig is not None else dict(context)
        if sig is not None:
            for param in sig.parameters.values():
                if (
                    param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
                    and param.default is param.empty
                    and param.name not in kwargs
                ):
                    return
        try:
            await _await(method(**kwargs))
        except TypeError:
            with contextlib.suppress(TypeError):
                await _await(method(context.get('company_id')))

    def _fill_kwargs(self, sig: Any, context: dict[str, Any]) -> dict[str, Any]:
        if sig is None:
            return dict(context)
        kwargs: dict[str, Any] = {}
        for param in sig.parameters.values():
            if param.kind not in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
                continue
            if param.name in context:
                kwargs[param.name] = context[param.name]
        return kwargs

    async def _begin_transaction(self) -> Any:
        uow = self._unit_of_work
        method = getattr(uow, 'begin', None)
        if not callable(method):
            method = getattr(uow, '__aenter__', None)
        if callable(method):
            return await _await(method())
        return uow

    async def _commit_transaction(self, tx: Any) -> None:
        method = getattr(tx, 'commit', None)
        if callable(method):
            await _await(method())
            return
        if self._unit_of_work is not None:
            method = getattr(self._unit_of_work, 'commit', None)
            if callable(method):
                await _await(method())

    async def _rollback_transaction(self, tx: Any) -> None:
        method = getattr(tx, 'rollback', None)
        if callable(method):
            with contextlib.suppress(Exception):
                await _await(method())


# Backwards-compatible aliases
CreateCompanyUseCase = CreateCompany
OnboardingUseCase = CreateCompany
OnboardingService = CreateCompany
CreateCompanyService = CreateCompany
CompanyOnboardingUseCase = CreateCompany
OnboardingOrchestrator = CreateCompany
