"""Contract tests for composition providers."""

from __future__ import annotations

from finsight.composition import CompositionContainer
from finsight.composition.providers import (
    get_ask_use_case,
    get_documents_use_case,
    get_feedback_use_case,
    get_onboarding_use_case,
    get_source_viewer_use_case,
    get_threads_use_case,
    get_upload_use_case,
    init,
)


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


def test_get_ask_use_case() -> None:
    fake = _FakeAsk()
    container = CompositionContainer()
    container.use_cases['ask'] = fake
    init(container)
    assert get_ask_use_case() is fake


def test_get_upload_use_case() -> None:
    fake = _FakeUpload()
    container = CompositionContainer()
    container.use_cases['upload'] = fake
    init(container)
    assert get_upload_use_case() is fake


def test_get_documents_use_case() -> None:
    fake = _FakeDocuments()
    container = CompositionContainer()
    container.use_cases['documents'] = fake
    init(container)
    assert get_documents_use_case() is fake


def test_get_onboarding_use_case() -> None:
    fake = _FakeOnboarding()
    container = CompositionContainer()
    container.use_cases['onboarding'] = fake
    init(container)
    assert get_onboarding_use_case() is fake


def test_get_source_viewer_use_case() -> None:
    fake = _FakeSourceViewer()
    container = CompositionContainer()
    container.use_cases['source_viewer'] = fake
    init(container)
    assert get_source_viewer_use_case() is fake


def test_get_threads_use_case() -> None:
    fake = _FakeThreads()
    container = CompositionContainer()
    container.use_cases['threads'] = fake
    init(container)
    assert get_threads_use_case() is fake


def test_get_feedback_use_case() -> None:
    fake = _FakeFeedback()
    container = CompositionContainer()
    container.use_cases['feedback'] = fake
    init(container)
    assert get_feedback_use_case() is fake
