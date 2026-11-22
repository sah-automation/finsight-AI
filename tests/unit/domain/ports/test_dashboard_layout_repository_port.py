from __future__ import annotations

import inspect

from finsight.domain.ports import DashboardLayoutRepositoryPort

EXPECTED_OPERATIONS = {'get_layout', 'save_layout', 'delete_layout'}


def _abstract_methods() -> dict[str, object]:
    return {
        name: member
        for name, member in inspect.getmembers(DashboardLayoutRepositoryPort, inspect.isfunction)
        if getattr(member, '__isabstractmethod__', False)
    }


def test_port_has_ticket_name() -> None:
    assert DashboardLayoutRepositoryPort.__name__ == 'DashboardLayoutRepositoryPort'


def test_port_declares_layout_operations() -> None:
    assert set(_abstract_methods()) == EXPECTED_OPERATIONS


def test_read_and_save_require_keyword_only_visible_ids() -> None:
    for name in ('get_layout', 'save_layout'):
        member = _abstract_methods()[name]
        visible = inspect.signature(member).parameters['visible_ids']  # type: ignore[arg-type]
        assert visible.kind is inspect.Parameter.KEYWORD_ONLY
        assert visible.default is inspect.Parameter.empty


def test_delete_does_not_require_visible_ids() -> None:
    member = _abstract_methods()['delete_layout']
    assert 'visible_ids' not in inspect.signature(member).parameters  # type: ignore[arg-type]
