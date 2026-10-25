"""Prompt-injection security tests.

The input gate and prompt-injection detector are not implemented yet. This
test is intentionally pending so the gap is visible instead of passing by
accident.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


def test_prompt_injection_detection_is_pending() -> None:
    pytest.skip(
        'Prompt-injection detection is not implemented yet; add tests when the input gate lands.'
    )
