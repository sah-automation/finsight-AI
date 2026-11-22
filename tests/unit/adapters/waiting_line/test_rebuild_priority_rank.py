"""The rebuild ranks must be mapped below live questions and uploads."""

from __future__ import annotations

import pytest

from finsight.adapters.waiting_line.waiting_line_settings import priority_rank

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('rebuild_kind', ['rebuilds', 'background'])
def test_rebuild_rank_is_below_live_and_upload(rebuild_kind: str) -> None:
    live_rank = max(priority_rank('question'), priority_rank('search'), priority_rank('model'))
    upload_rank = priority_rank('upload')

    assert priority_rank(rebuild_kind) > live_rank
    assert priority_rank(rebuild_kind) > upload_rank
