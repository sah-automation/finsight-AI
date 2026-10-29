"""Prompt-injection security tests.

The input gate and prompt-injection detector are not implemented yet. This
test is intentionally pending so the gap is visible instead of passing by
accident.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.security, pytest.mark.placeholder]


def test_prompt_injection_detection_is_pending() -> None:
    pytest.skip('Placeholder pending input gate (#74/#80): add tests when it lands.')
