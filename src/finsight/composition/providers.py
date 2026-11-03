"""Typed providers exposing use cases from a wired composition container."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

try:  # pragma: no cover - import is covered by unit tests
    from finsight.application.ask_question import AskQuestion
except Exception:
    AskQuestion = Any  # type: ignore[assignment,misc]

try:  # pragma: no cover - import is covered by unit tests
    from finsight.application.ingest_document.upload_document import UploadDocument
except Exception:
    UploadDocument = Any  # type: ignore[assignment,misc]

try:  # pragma: no cover - import is covered by unit tests
    from finsight.application.onboarding import OnboardingUseCase
except Exception:
    OnboardingUseCase = Any  # type: ignore[assignment,misc]

try:  # pragma: no cover - import is covered by unit tests
    from finsight.application.source_viewer.source_viewer_use_case import (
        SourceViewerUseCase,
    )
except Exception:
    SourceViewerUseCase = Any  # type: ignore[assignment,misc]

# Use cases that are not yet promoted to dedicated application classes fall back
# to ``Any`` so the provider remains importable in all configurations.
DocumentsUseCase = Any
ThreadsUseCase = Any
FeedbackUseCase = Any


class ProviderError(RuntimeError, KeyError):
    """Raised when a provider is not initialised or a use case is missing."""


_container: Any = None


def init(container: Any) -> None:
    """Store the built container in the module-level private slot.

    Called once at application startup. Passing ``None`` fails loudly.
    """
    global _container  # noqa: PLW0603
    if container is None:
        raise ProviderError('composition provider container must not be None')
    _container = container


def _get_container() -> Any:
    if _container is None:
        raise ProviderError('composition providers are not initialised; call init(container) first')
    return _container


_CONFIGS: dict[str, dict[str, Any]] = {
    'ask': {
        'aliases': (
            'ask_question',
            'ask_question_use_case',
            'ask_use_case',
            'qa',
            'question',
            'question_use_case',
        ),
        'attrs': (
            'ask_question_use_case',
            'ask_use_case',
            'ask_question',
            'ask',
            'qa_use_case',
            'question_use_case',
        ),
    },
    'upload': {
        'aliases': (
            'upload_use_case',
            'ingestion',
            'ingestion_use_case',
        ),
        'attrs': (
            'upload_use_case',
            'upload',
            'ingestion_use_case',
            'ingestion',
        ),
    },
    'documents': {
        'aliases': (
            'document',
            'documents_use_case',
            'document_use_case',
            'docs_use_case',
            'docs',
        ),
        'attrs': (
            'documents_use_case',
            'document_use_case',
            'docs_use_case',
            'documents',
            'document',
        ),
    },
    'onboarding': {
        'aliases': (
            'onboarding_use_case',
            'create_company',
            'create_company_use_case',
            'company_onboarding_use_case',
            'create_company_service',
        ),
        'attrs': (
            'onboarding_use_case',
            'onboarding',
            'create_company_use_case',
            'create_company',
            'create_company_service',
        ),
    },
    'source_viewer': {
        'aliases': (
            'source_view',
            'source_viewer_use_case',
            'source_view_use_case',
            'view_source',
            'view_source_use_case',
        ),
        'attrs': (
            'source_viewer_use_case',
            'source_viewer',
            'source_view_use_case',
            'source_view',
            'view_source_use_case',
            'view_source',
        ),
    },
    'threads': {
        'aliases': (
            'thread',
            'threads_use_case',
            'thread_use_case',
        ),
        'attrs': (
            'threads_use_case',
            'thread_use_case',
            'threads',
            'thread',
        ),
    },
    'feedback': {
        'aliases': (
            'feedbacks',
            'feedback_use_case',
            'feedbacks_use_case',
        ),
        'attrs': (
            'feedback_use_case',
            'feedbacks_use_case',
            'feedback',
            'feedbacks',
        ),
    },
}


def _resolve_use_case(canonical: str) -> Any:
    container = _get_container()
    config = _CONFIGS[canonical]
    aliases: tuple[str, ...] = config['aliases']
    attrs: tuple[str, ...] = config['attrs']
    keys = (canonical, *aliases)

    use_cases = getattr(container, 'use_cases', None)
    if isinstance(use_cases, Mapping):
        for key in keys:
            if key in use_cases:
                value = use_cases[key]
                if value is None:
                    raise ProviderError(f'{canonical} use case is not configured in the container')
                return value

    for attr in attrs:
        if hasattr(container, attr):
            value = getattr(container, attr)
            if value is not None:
                return value

    deps = getattr(container, 'deps', None)
    if isinstance(deps, Mapping):
        for key in keys + attrs:
            if key in deps:
                value = deps.get(key)
                if value is not None:
                    return value

    if hasattr(container, 'get'):
        try:
            for key in keys:
                value = container.get(key)
                if value is not None:
                    return value
        except Exception:  # noqa: S110
            pass

    raise ProviderError(f'{canonical} use case is not configured in the container')


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
    'AskQuestion',
    'DocumentsUseCase',
    'FeedbackUseCase',
    'OnboardingUseCase',
    'ProviderError',
    'SourceViewerUseCase',
    'ThreadsUseCase',
    'UploadDocument',
    'get_ask_use_case',
    'get_documents_use_case',
    'get_feedback_use_case',
    'get_onboarding_use_case',
    'get_source_viewer_use_case',
    'get_threads_use_case',
    'get_upload_use_case',
    'init',
]
