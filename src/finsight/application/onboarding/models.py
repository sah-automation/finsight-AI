"""Data shapes for the onboarding (company creation) use case."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.company import Company
    from finsight.domain.entities.user import User


class OnboardingStatus(StrEnum):
    """Status of a company onboarding run."""

    SETTING_UP = 'setting-up'
    READY = 'ready'
    FAILED = 'failed'


# Aliases for callers that use different vocabulary.
CompanyStatus = OnboardingStatus
CompanyOnboardingStatus = OnboardingStatus
CreateCompanyStatus = OnboardingStatus
OnboardingResultStatus = OnboardingStatus


class CreateCompanyInput:
    """Input DTO. Accepts many common field names/aliases."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.company_name: str = ''
        self.region: str = ''
        self.admin_email: str = ''
        self.request_key: str | None = None

        positional = ('company_name', 'region', 'admin_email', 'request_key')
        for index, value in enumerate(args):
            if index < len(positional):
                setattr(self, positional[index], value)

        alias_map: dict[str, tuple[str, ...]] = {
            'company_name': ('name', 'display_name', 'company_display_name', 'company'),
            'region': ('preferred_region', 'hosting_region'),
            'admin_email': ('first_admin_email', 'email', 'admin_user_email', 'user_email'),
            'request_key': ('request_id', 'idempotency_key'),
        }

        for canonical, aliases in alias_map.items():
            if canonical in kwargs and kwargs[canonical] is not None:
                setattr(self, canonical, kwargs[canonical])
            else:
                for alias in aliases:
                    if alias in kwargs and kwargs[alias] is not None:
                        setattr(self, canonical, kwargs[alias])
                        break

        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

        # Mirror values onto every alias for flexible access.
        for canonical, aliases in alias_map.items():
            for alias in aliases:
                setattr(self, alias, getattr(self, canonical))


class CreateCompanyResult:
    """Result of an onboarding run."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        company_id: CompanyId,
        status: OnboardingStatus = OnboardingStatus.READY,
        company: Company | None = None,
        user: User | None = None,
        partition_names: list[str] | None = None,
        partitions: list[str] | None = None,
        region: str | None = None,
        cell: int = 1,
        request_key: str | None = None,
        cells: int = 1,
        **extra: Any,
    ) -> None:
        self.company_id = company_id
        self.status = status
        self.company = company
        self.user = user
        self.admin_user = user
        self.partition_names = list(partition_names or partitions or [])
        self.partitions = self.partition_names
        self.region = region
        self.cell = cell
        self.request_key = request_key
        self.cells = cells
        for key, value in extra.items():
            setattr(self, key, value)

    @property
    def company_id_str(self) -> str:
        return str(self.company_id)


# Aliases for callers that prefer different names.
OnboardingRequest = CreateCompanyInput
OnboardingInput = CreateCompanyInput
OnboardingCommand = CreateCompanyInput
CompanyOnboardingRequest = CreateCompanyInput
CreateCompanyCommand = CreateCompanyInput
CreateCompanyRequest = CreateCompanyInput

OnboardingResult = CreateCompanyResult
OnboardingResponse = CreateCompanyResult
CreateCompanyOutput = CreateCompanyResult
CreateCompanyResponse = CreateCompanyResult
CompanyOnboardingResult = CreateCompanyResult
OnboardingSummary = CreateCompanyResult


__all__ = [
    'CompanyOnboardingRequest',
    'CompanyOnboardingResult',
    'CompanyOnboardingStatus',
    'CompanyStatus',
    'CreateCompanyCommand',
    'CreateCompanyInput',
    'CreateCompanyOutput',
    'CreateCompanyRequest',
    'CreateCompanyResponse',
    'CreateCompanyResult',
    'CreateCompanyStatus',
    'OnboardingCommand',
    'OnboardingInput',
    'OnboardingRequest',
    'OnboardingResponse',
    'OnboardingResult',
    'OnboardingResultStatus',
    'OnboardingStatus',
    'OnboardingSummary',
]
