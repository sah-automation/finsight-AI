# Core Errors - Custom error types grouped by meaning

from __future__ import annotations

from typing import Any


class FinSightError(Exception):
    """Base exception for all FinSight errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        self.retryable = retryable

    def __str__(self) -> str:
        return f'[{self.code}] {self.message}'


# ============================================================
# Error Categories
# ============================================================


class UserFacingError(FinSightError):
    """Errors safe to show to users. Generic messages, no internal details."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details, retryable=False)


class RetryableError(FinSightError):
    """Errors that warrant a retry with backoff."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details, retryable=True)


class PolicyBlocked(FinSightError):
    """Blocked by policy (permissions, rate limits, content policy)."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details, retryable=False)


class InsufficientData(FinSightError):
    """Normal result when data is lacking - not a failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details, retryable=False)


# ============================================================
# Specific Errors
# ============================================================


# Configuration
class ConfigError(FinSightError):
    """Configuration validation or loading error."""


# Authentication & Authorization
class AuthenticationError(UserFacingError):
    """Authentication failed."""


class AuthorizationError(PolicyBlocked):
    """Not authorized for this action."""


class TokenExpiredError(AuthenticationError):
    """Auth token has expired."""


# Document Processing
class DocumentError(FinSightError):
    """Base for document processing errors."""


class DocumentNotFoundError(UserFacingError):
    """Document not found."""


class DocumentProcessingError(RetryableError):
    """Document processing failed."""


class UnsupportedFormatError(UserFacingError):
    """File format not supported."""


class DocumentTooLargeError(UserFacingError):
    """Document exceeds size limit."""


# Ingestion
class IngestionError(FinSightError):
    """Ingestion pipeline error."""


class IngestionJobNotFoundError(UserFacingError):
    """Ingestion job not found."""


# Question Answering
class QuestionError(FinSightError):
    """Question answering error."""


class QuestionTooLongError(UserFacingError):
    """Question exceeds maximum length."""


class NoRelevantDocumentsError(InsufficientData):
    """No relevant documents found for question."""


class CitationVerificationFailedError(FinSightError):
    """Answer failed citation verification."""


# Vector Store
class VectorStoreError(RetryableError):
    """Vector store operation failed."""


class EmbeddingError(RetryableError):
    """Embedding generation failed."""


# LLM
class LLMError(RetryableError):
    """LLM gateway error."""


class LLMRateLimitError(RetryableError):
    """LLM rate limit exceeded."""


class LLMContextWindowError(UserFacingError):
    """Context window exceeded."""


class AllModelsFailedError(FinSightError):
    """All fallback models exhausted."""


# External Services
class ExternalServiceError(RetryableError):
    """External service (AWS, etc.) error."""


class TextractError(ExternalServiceError):
    """AWS Textract error."""


class S3Error(ExternalServiceError):
    """S3 operation error."""


class DynamoDBError(ExternalServiceError):
    """DynamoDB operation error."""


class SQSError(ExternalServiceError):
    """SQS operation error."""


class CognitoError(ExternalServiceError):
    """Cognito error."""


# Database
class DatabaseError(RetryableError):
    """Database operation error."""


class DatabaseConnectionError(RetryableError):
    """Database connection failed."""


# Cache
class CacheError(RetryableError):
    """Cache operation error."""


# Queue
class QueueError(RetryableError):
    """Queue operation error."""


# Validation
class ValidationError(UserFacingError):
    """Input validation error."""


# Business Rules
class BusinessRuleError(UserFacingError):
    """Business rule violation."""


class ConflictError(UserFacingError):
    """Resource conflict (e.g., concurrent modification)."""


# ============================================================
# Error Mapping for Entrypoints
# ============================================================

# Map error types to user-friendly messages
USER_FRIENDLY_MESSAGES = {
    AuthenticationError: 'Please sign in to continue.',
    TokenExpiredError: 'Your session has expired. Please sign in again.',
    AuthorizationError: "You don't have permission to perform this action.",
    DocumentNotFoundError: 'Document not found.',
    DocumentTooLargeError: 'Document is too large. Maximum size is 100MB.',
    UnsupportedFormatError: (
        'Unsupported file format. Please upload PDF, Excel, CSV, or Word documents.'
    ),
    QuestionTooLongError: 'Question is too long. Please shorten it.',
    NoRelevantDocumentsError: 'No relevant documents found to answer your question.',
    LLMRateLimitError: 'Service is busy. Please try again in a moment.',
    LLMContextWindowError: 'Question is too complex. Please try a simpler question.',
    AllModelsFailedError: 'AI service is temporarily unavailable. Please try again later.',
    VectorStoreError: 'Search service is temporarily unavailable.',
    DatabaseError: 'Service is temporarily unavailable. Please try again.',
    CacheError: 'Cache service is temporarily unavailable.',
    QueueError: 'Background processing is busy. Please try again.',
    InsufficientData: 'Insufficient data to complete this request.',
    ValidationError: 'Invalid input. Please check your request.',
    BusinessRuleError: 'This operation is not allowed.',
    ConflictError: 'Resource was modified by another request. Please retry.',
    ConfigError: 'Service configuration error. Please contact support.',
}


def to_user_message(error: Exception) -> str:
    """Convert an error to a user-friendly message."""
    for error_type, message in USER_FRIENDLY_MESSAGES.items():
        if isinstance(error, error_type):
            return message
    # Default for unexpected errors
    return 'An unexpected error occurred. Please try again later.'
