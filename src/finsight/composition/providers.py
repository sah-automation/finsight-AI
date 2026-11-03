"""Typed providers exposing use cases from a wired composition container."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from finsight.application.ask_question import AskQuestion
from finsight.application.ingest_document.upload_document import UploadDocument
from finsight.application.onboarding import OnboardingUseCase
from finsight.application.source_viewer.source_viewer_use_case import SourceViewerUseCase

if TYPE_CHECKING:
    from .composition_container import CompositionContainer

# Use cases that are not yet promoted to dedicated application classes fall back
# to ``Any`` so the providers remain importable in all configurations.
DocumentsUseCase = Any
ThreadsUseCase = Any
FeedbackUseCase = Any


class ProviderError(RuntimeError, KeyError):
    """Raised when a provider is not initialised or a use case is missing."""


_container: Any = None


def init(container: CompositionContainer) -> None:
    """Store the built container in the module-level private slot."""
    global _container  # noqa: PLW0603
    if container is None:
        raise ProviderError('composition provider container must not be None')
    _container = container


def _get_container() -> CompositionContainer:
    if _container is None:
        raise ProviderError('composition providers are not initialised; call init(container) first')
    return cast('CompositionContainer', _container)


def _resolve_use_case(canonical: str) -> Any:
    container = _get_container()
    use_cases = getattr(container, 'use_cases', None)
    if not isinstance(use_cases, Mapping) or canonical not in use_cases:
        raise ProviderError(f'{canonical} use case is not configured in the container')
    value = use_cases[canonical]
    if value is None:
        raise ProviderError(f'{canonical} use case is not configured in the container')
    return value


def get_ask_use_case() -> AskQuestion:
    return cast('AskQuestion', _resolve_use_case('ask'))


def get_upload_use_case() -> UploadDocument:
    return cast('UploadDocument', _resolve_use_case('upload'))


def get_documents_use_case() -> DocumentsUseCase:
    return cast('DocumentsUseCase', _resolve_use_case('documents'))


def get_onboarding_use_case() -> OnboardingUseCase:
    return cast('OnboardingUseCase', _resolve_use_case('onboarding'))


def get_source_viewer_use_case() -> SourceViewerUseCase:
    return cast('SourceViewerUseCase', _resolve_use_case('source_viewer'))


def get_threads_use_case() -> ThreadsUseCase:
    return cast('ThreadsUseCase', _resolve_use_case('threads'))


def get_feedback_use_case() -> FeedbackUseCase:
    return cast('FeedbackUseCase', _resolve_use_case('feedback'))


__all__ = [
    'DocumentsUseCase',
    'FeedbackUseCase',
    'ProviderError',
    'get_ask_use_case',
    'get_documents_use_case',
    'get_feedback_use_case',
    'get_onboarding_use_case',
    'get_source_viewer_use_case',
    'get_threads_use_case',
    'get_upload_use_case',
    'init',
]
