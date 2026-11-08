"""Output verification for generated answers (pure domain)."""

from __future__ import annotations

from typing import Any

from ._output_gate_math import _extract_numbers
from ._output_gate_operations import _OutputGateOperations
from .output_verification_result import OutputVerificationResult


class OutputGate(_OutputGateOperations):
    """Pure output verification service."""


# Public, stable entry point for extracting numeric values from arbitrary text.
extract_numbers = _extract_numbers


def verify_output(*args: Any, **kwargs: Any) -> OutputVerificationResult:
    checker_kwargs: dict[str, object] = {}
    data = dict(kwargs)
    for key in (
        'mode',
        'pii_action',
        'pii_detection_enabled',
        'number_check_enabled',
        'config',
        'settings',
        'output_gate_config',
        'output_check_mode',
        'timing',
        'timing_mode',
    ):
        if key in data:
            checker_kwargs[key] = data.pop(key)
    return OutputGate(**checker_kwargs).check(*args, **data)  # type: ignore[no-any-return]


OutputVerifier = OutputGate
OutputVerification = OutputGate
OutputValidator = OutputGate
__all__ = [
    'OutputGate',
    'OutputValidator',
    'OutputVerification',
    'OutputVerificationResult',
    'OutputVerifier',
    'extract_numbers',
    'verify_output',
]
