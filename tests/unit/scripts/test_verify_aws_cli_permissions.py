"""Tests for the operator permission verifier.

The verifier proves two things after an IAM policy change: the application's
own work still succeeds, and the guardrails still block. These tests pin the
classification of AWS CLI responses (so a "not found" is never mistaken for a
"denied") and the safety property that no probe can create or destroy state.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'verify_aws_cli_permissions.py'


def _load() -> Any:
    spec = importlib.util.spec_from_file_location('verify_aws_cli_permissions', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify = _load()


@pytest.mark.parametrize(
    'output',
    [
        'An error occurred (AccessDenied) when calling the PutObject operation: not authorized',
        (
            'An error occurred (AccessDenied) when calling the DeleteUser operation: '
            'with an explicit deny in an identity-based policy: arn:aws:iam::...:policy/x'
        ),
        'An error occurred (403) when calling the HeadObject operation: Forbidden',
    ],
)
def test_a_refusal_is_classified_as_denied(output: str) -> None:
    assert verify.classify(output, 1) == 'DENY'


@pytest.mark.parametrize(
    'output',
    [
        'An error occurred (404) when calling the HeadObject operation: Not Found',
        'An error occurred (ParameterNotFound) when calling the GetParameter operation',
        'An error occurred (ResourceNotFoundException) when calling the GetSecretValue operation',
        'An error occurred (InvalidCiphertextException) when calling the Decrypt operation',
        'An error occurred (ValidationError) when calling the UpdateStack operation',
    ],
)
def test_a_missing_resource_is_classified_as_allowed(output: str) -> None:
    assert verify.classify(output, 1) == 'ALLOW'


def test_a_successful_call_is_classified_as_allowed() -> None:
    assert verify.classify('{"Stacks": []}', 0) == 'ALLOW'


def test_an_unrecognised_failure_is_not_reported_as_a_verdict() -> None:
    assert verify.classify('command not found', 127) == 'ERROR'


def test_every_probe_declares_an_expectation() -> None:
    for probe in verify.LIVE_PROBES:
        assert probe.expectation in {'ALLOW', 'DENY'}, probe.label
    for probe in verify.SIMULATOR_PROBES:
        assert probe.expectation in {'allowed', 'explicitDeny', 'implicitDeny'}, probe.label


def test_no_probe_can_create_or_destroy_state() -> None:
    """A probe that mutates the account would be a bug in the verifier itself."""
    forbidden = (
        'create-stack',
        'create-user',
        'create-role',
        'create-bucket',
        'create-open-id',
        'put-user-policy',
        'put-role-policy',
        'put-user-permissions-boundary',
        'attach-user-policy',
        'update-assume-role-policy',
        'put-parameter',
        'put-object',
        'delete-bucket',
        'delete-role',
        'delete-policy',
    )
    for probe in verify.LIVE_PROBES:
        joined = ' '.join(probe.args)
        for action in forbidden:
            assert action not in joined, f'{probe.label} must not run {action}'


def test_the_probes_cover_the_guardrails_that_matter() -> None:
    labels = ' '.join(probe.label for probe in verify.LIVE_PROBES)
    for subject in ('CreateUser', 'organizations', 'AlternateContact', 'AccessKey'):
        assert subject.lower() in labels.lower()


def test_the_probes_cover_the_work_the_agent_still_needs() -> None:
    labels = ' '.join(probe.label for probe in verify.LIVE_PROBES)
    for subject in ('CloudFormation', 'Parameter', 'budget', 'anomaly', 'Lambda'):
        assert subject.lower() in labels.lower()


def test_the_simulator_checks_the_resource_scoped_decisions() -> None:
    resources = ' '.join(probe.resource for probe in verify.SIMULATOR_PROBES)
    assert 'foreign' in resources
    assert 'finsight' in resources
