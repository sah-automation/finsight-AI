# Core Types - Shared IDs, enums, and type definitions

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

from pydantic import BaseModel

# ============================================================
# Strongly-typed IDs (NewType for static checking, runtime is str)
# ============================================================

CompanyId = NewType('CompanyId', str)
UserId = NewType('UserId', str)
DocumentId = NewType('DocumentId', str)
ChunkId = NewType('ChunkId', str)
JobId = NewType('JobId', str)
MetricId = NewType('MetricId', str)
AnswerId = NewType('AnswerId', str)
RecommendationId = NewType('RecommendationId', str)
ReportId = NewType('ReportId', str)
TraceId = NewType('TraceId', str)


# ============================================================
# Enums
# ============================================================


class Role(StrEnum):
    """User roles in the system.

    The IDs match the four roles in the config switch guide (5.29) and the
    `users.role` check constraint in the initial migration. ADR-0003 records
    the decision to retire the earlier `admin`/`analyst`/`viewer`/`approver`
    and `finance_manager` vocabularies.
    """

    EXECUTIVE_LEADERSHIP = 'executive_leadership'
    CORPORATE_FINANCE_PLANNERS = 'corporate_finance_planners'
    AUDIT_COMPLIANCE = 'audit_compliance'
    SYSTEM_ADMIN = 'system_admin'


class Category(StrEnum):
    """Data categories for permissions."""

    FINANCIALS = 'financials'
    METRICS = 'metrics'
    FORECASTS = 'forecasts'
    RISKS = 'risks'
    DECISIONS = 'decisions'
    DOCUMENTS = 'documents'
    AUDIT = 'audit'


class Action(StrEnum):
    """Actions that can be performed."""

    READ = 'read'
    WRITE = 'write'
    DELETE = 'delete'
    APPROVE = 'approve'
    UPLOAD = 'upload'
    CONFIGURE = 'configure'


class DocumentStatus(StrEnum):
    """Document processing state machine."""

    RECEIVED = 'received'
    STORED = 'stored'
    PROCESSING = 'processing'
    COMMITTED = 'committed'
    FAILED = 'failed'


class JobStatus(StrEnum):
    """Background job status."""

    PENDING = 'pending'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    RETRYING = 'retrying'


class ChunkType(StrEnum):
    """Type of content chunk."""

    TEXT = 'text'
    TABLE = 'table'
    IMAGE = 'image'
    HEADER = 'header'
    FOOTER = 'footer'


class ModelProvider(StrEnum):
    """LLM provider."""

    LITELLM = 'litellm'
    BEDROCK = 'bedrock'
    OPENAI = 'openai'
    ANTHROPIC = 'anthropic'
    COHERE = 'cohere'


# ============================================================
# Shared Value Objects (immutable, compare by value)
# ============================================================


@dataclass(frozen=True, slots=True)
class Money:
    """Monetary value with currency and units."""

    amount: int  # Stored in minor units (cents) to avoid float issues
    currency: str = 'USD'
    units: str = 'ones'  # ones, thousands, millions

    def __post_init__(self) -> None:
        if self.currency not in ('USD', 'EUR', 'GBP'):
            raise ValueError(f'Unsupported currency: {self.currency}')
        if self.units not in ('ones', 'thousands', 'millions'):
            raise ValueError(f'Unsupported units: {self.units}')

    @property
    def decimal_amount(self) -> float:
        """Get amount as decimal (major units)."""
        return self.amount / 100

    def scaled_amount(self, target_units: str) -> int:
        """Convert to target units (returns minor units in target)."""
        unit_multipliers = {
            'ones': 1,
            'thousands': 1000,
            'millions': 1_000_000,
        }
        if target_units not in unit_multipliers:
            raise ValueError(f'Unknown units: {target_units}')
        return self.amount * unit_multipliers[self.units] // unit_multipliers[target_units]


@dataclass(frozen=True, slots=True)
class Period:
    """Fiscal period."""

    fiscal_year: int
    fiscal_quarter: int | None = None  # 1-4, None = full year
    start_date: str | None = None  # ISO format
    end_date: str | None = None  # ISO format

    # Fiscal quarter range constant
    _MIN_FISCAL_QUARTER: int = 1
    _MAX_FISCAL_QUARTER: int = 4

    def __post_init__(self) -> None:
        if self.fiscal_quarter is not None and not (
            self._MIN_FISCAL_QUARTER <= self.fiscal_quarter <= self._MAX_FISCAL_QUARTER
        ):
            raise ValueError('fiscal_quarter must be 1-4')


@dataclass(frozen=True, slots=True)
class Citation:
    """Source citation for an answer."""

    document_id: DocumentId
    page_number: int | None = None
    table_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    chunk_id: ChunkId | None = None


@dataclass(frozen=True, slots=True)
class Confidence:
    """Confidence score with reasoning."""

    score: float  # 0.0 to 1.0
    reasoning: str

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError('Confidence score must be between 0.0 and 1.0')


# ============================================================
# Request Context (passed through application layer)
# ============================================================


class RequestContext(BaseModel):
    """Context for a request - already validated by entrypoint."""

    company_id: CompanyId
    user_id: UserId
    role: Role
    trace_id: TraceId
    permissions: dict[Category, list[Action]]  # What this role can do
    access_scope: list[Category]  # Categories this request can access

    model_config = {'frozen': True}
