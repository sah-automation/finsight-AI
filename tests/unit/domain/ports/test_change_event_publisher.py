from __future__ import annotations

import inspect

import pytest

from finsight.domain.ports import ChangeEventPublisher

EXPECTED_OPERATIONS = {'publish', 'publish_many'}


def _abstract_methods() -> dict[str, object]:
    return {
        name: member
        for name, member in inspect.getmembers(ChangeEventPublisher, inspect.isfunction)
        if getattr(member, '__isabstractmethod__', False)
    }


def test_publisher_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        ChangeEventPublisher()  # type: ignore[abstract]


def test_publisher_declares_single_and_batch_publishing() -> None:
    assert set(_abstract_methods()) == EXPECTED_OPERATIONS


def test_every_publisher_method_requires_company_id() -> None:
    for name, member in _abstract_methods().items():
        parameters = list(inspect.signature(member).parameters)  # type: ignore[arg-type]
        assert parameters[0] == 'self', name
        assert parameters[1] == 'company_id', name
