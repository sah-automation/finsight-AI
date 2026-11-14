"""Contract tests for composition providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.composition import CompositionContainer, providers
from finsight.composition.providers import (
    ProviderError,
    get_ask_use_case,
    get_documents_use_case,
    get_feedback_use_case,
    get_onboarding_use_case,
    get_source_viewer_use_case,
    get_threads_use_case,
    get_upload_use_case,
    init,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class _FakeAsk:
    pass


class _FakeUpload:
    pass


class _FakeDocuments:
    pass


class _FakeOnboarding:
    pass


class _FakeSourceViewer:
    pass


class _FakeThreads:
    pass


class _FakeFeedback:
    pass


@pytest.fixture(autouse=True)
def _reset_provider_container(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep the module-level provider slot deterministic between tests."""
    monkeypatch.setattr(providers, '_container', None)
    yield


def _container_with(key: str, fake: object) -> CompositionContainer:
    container = CompositionContainer()
    for name in ('ask', 'upload', 'documents', 'onboarding', 'source_viewer'):
        container.use_cases[name] = object()
    container.use_cases[key] = fake
    init(container)
    return container


def test_get_ask_use_case() -> None:
    fake = _FakeAsk()
    _container_with('ask', fake)
    assert get_ask_use_case() is fake


def test_get_upload_use_case() -> None:
    fake = _FakeUpload()
    _container_with('upload', fake)
    assert get_upload_use_case() is fake


def test_get_documents_use_case() -> None:
    fake = _FakeDocuments()
    _container_with('documents', fake)
    assert get_documents_use_case() is fake


def test_get_onboarding_use_case() -> None:
    fake = _FakeOnboarding()
    _container_with('onboarding', fake)
    assert get_onboarding_use_case() is fake


def test_get_source_viewer_use_case() -> None:
    fake = _FakeSourceViewer()
    _container_with('source_viewer', fake)
    assert get_source_viewer_use_case() is fake


def test_get_threads_use_case() -> None:
    fake = _FakeThreads()
    _container_with('threads', fake)
    assert get_threads_use_case() is fake


def test_get_feedback_use_case() -> None:
    fake = _FakeFeedback()
    _container_with('feedback', fake)
    assert get_feedback_use_case() is fake


def test_provider_raises_before_initialisation() -> None:
    with pytest.raises(ProviderError, match='not initialised'):
        get_ask_use_case()


def test_init_raises_when_a_required_use_case_is_missing() -> None:
    container = CompositionContainer()
    for name in ('upload', 'documents', 'onboarding', 'source_viewer'):
        container.use_cases[name] = object()

    with pytest.raises(ProviderError, match='missing use cases at startup: ask'):
        init(container)


def test_provider_raises_when_an_optional_use_case_is_missing() -> None:
    container = CompositionContainer()
    for name in ('ask', 'upload', 'documents', 'onboarding', 'source_viewer'):
        container.use_cases[name] = object()
    init(container)

    with pytest.raises(ProviderError, match='threads use case is not configured'):
        get_threads_use_case()


def test_init_rejects_none_container() -> None:
    with pytest.raises(ProviderError, match='must not be None'):
        init(None)  # type: ignore[arg-type]
