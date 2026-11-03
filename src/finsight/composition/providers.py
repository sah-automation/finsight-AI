"""Typed providers exposing use cases from a wired composition container."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from finsight.application.ask_question import AskQuestion
from finsight.application.ingest_document.upload_document import UploadDocument
from finsight.application.onboarding import OnboardingUseCase
from finsight.application.source_viewer import SourceViewer

if TYPE_CHECKING:
    from .composition_container import CompositionContainer

# The documents, threads and feedback surfaces do not yet have dedicated
# application use-case classes (see Candidate 4 out-of-scope notes). Their
# providers therefore expose the wired collaborator as ``Any`` until those
# classes exist; ``ask``, ``upload``, ``onboarding`` and ``source_viewer``
# return their concrete use-case types.
DocumentsUseCase = Any
ThreadsUseCase = Any
FeedbackUseCase = Any


class ProviderError(RuntimeError, KeyError):
    """Raised when a provider is not initialised or a use case is missing."""


_container: Any = None

# Use cases the app cannot serve without. ``threads`` and ``feedback`` are not
# wired in the container yet (no application use-case classes exist), so they
# are resolved on demand and raise ProviderError when a caller needs them.
_STARTUP_USE_CASES = ('ask', 'upload', 'documents', 'onboarding', 'source_viewer')


def init(container: CompositionContainer) -> None:
    """Store the built container and fail loudly when a required use case is missing."""
    global _container  # noqa: PLW0603
    if container is None:
        raise ProviderError('composition provider container must not be None')
    _validate_startup_use_cases(container)
    _container = container


def _validate_startup_use_cases(container: CompositionContainer) -> None:
    """Raise :class:`ProviderError` when a required use case is not wired."""
    use_cases = getattr(container, 'use_cases', None)
    if not isinstance(use_cases, Mapping):
        raise ProviderError('composition container must expose a use_cases mapping')
    missing = [name for name in _STARTUP_USE_CASES if use_cases.get(name) is None]
    if missing:
        raise ProviderError(f'missing use cases at startup: {", ".join(missing)}')


def _get_container() -> CompositionContainer:
    """Return the container registered by :func:`init`, failing loudly when unset."""
    if _container is None:
        raise ProviderError('composition providers are not initialised; call init(container) first')
    return cast('CompositionContainer', _container)


def _resolve_use_case(canonical: str) -> Any:
    """Return the use case registered under ``canonical`` or raise :class:`ProviderError`."""
    container = _get_container()
    use_cases = getattr(container, 'use_cases', None)
    if not isinstance(use_cases, Mapping) or canonical not in use_cases:
        raise ProviderError(f'{canonical} use case is not configured in the container')
    value = use_cases[canonical]
    if value is None:
        raise ProviderError(f'{canonical} use case is not configured in the container')
    return value


def get_ask_use_case() -> AskQuestion:
    """Return the wired ask-question use case."""
    return cast('AskQuestion', _resolve_use_case('ask'))


def get_upload_use_case() -> UploadDocument:
    """Return the wired document-upload use case."""
    return cast('UploadDocument', _resolve_use_case('upload'))


def get_documents_use_case() -> DocumentsUseCase:
    """Return the wired documents collaborator (repository until a use case exists)."""
    return cast('DocumentsUseCase', _resolve_use_case('documents'))


def get_onboarding_use_case() -> OnboardingUseCase:
    """Return the wired onboarding use case."""
    return cast('OnboardingUseCase', _resolve_use_case('onboarding'))


def get_source_viewer_use_case() -> SourceViewer:
    """Return the wired source-viewer use case."""
    return cast('SourceViewer', _resolve_use_case('source_viewer'))


def get_threads_use_case() -> ThreadsUseCase:
    """Return the wired threads collaborator."""
    return cast('ThreadsUseCase', _resolve_use_case('threads'))


def get_feedback_use_case() -> FeedbackUseCase:
    """Return the wired feedback collaborator."""
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
