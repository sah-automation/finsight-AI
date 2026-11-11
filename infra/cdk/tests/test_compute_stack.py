"""Synthesis tests for the compute stack (issue #276).

The stack is deploy-neutral: these tests inspect the synthesized CloudFormation
template only. They never create AWS resources.

``AWS_REGION`` is a Lambda-reserved variable that the runtime injects
automatically, so it is deliberately absent from the declared environment.
"""

from __future__ import annotations

import json

import aws_cdk as cdk
from aws_cdk.assertions import Template
from stacks.auth import AuthStack
from stacks.compute import ComputeStack, _app_environment
from stacks.observability import ObservabilityStack

# Pin the account/region so the region-derived OTLP endpoint is deterministic.
_ENV = cdk.Environment(account='123456789012', region='us-east-1')


def _compute_template(env_name: str = 'dev') -> Template:
    app = cdk.App()
    auth = AuthStack(app, f'FinSight-{env_name}-Auth', env=_ENV, env_name=env_name)
    observability = ObservabilityStack(
        app, f'FinSight-{env_name}-Observability', env=_ENV, env_name=env_name
    )
    compute = ComputeStack(
        app,
        f'FinSight-{env_name}-Compute',
        env=_ENV,
        env_name=env_name,
        auth=auth,
        observability=observability,
    )
    return Template.from_stack(compute)


def _api_lambda(template: Template) -> dict[str, object]:
    functions = template.find_resources('AWS::Lambda::Function')
    api_functions = {key: value for key, value in functions.items() if 'ApiFunction' in key}
    assert len(api_functions) == 1, f'expected one API Lambda, found {sorted(functions)}'
    return next(iter(api_functions.values()))


def _environment_variables(template: Template) -> dict[str, object]:
    return _api_lambda(template)['Properties']['Environment']['Variables']


def test_lambda_environment_includes_otlp_endpoint_and_environment() -> None:
    variables = _environment_variables(_compute_template('dev'))

    assert 'OTLP_ENDPOINT' in variables
    assert 'ENVIRONMENT' in variables


def test_lambda_otlp_endpoint_targets_cloudwatch_logs() -> None:
    endpoint = _environment_variables(_compute_template('dev'))['OTLP_ENDPOINT']

    assert endpoint == 'https://logs.us-east-1.amazonaws.com/v1/logs'


def test_lambda_environment_uses_loader_environment_name() -> None:
    # The config loader only accepts development|test|staging|production, so the
    # CDK name (dev/prod) must be mapped rather than passed through verbatim.
    expected = {'dev': 'development', 'staging': 'staging', 'prod': 'production'}
    for env_name, app_environment in expected.items():
        variables = _environment_variables(_compute_template(env_name))
        assert variables['ENVIRONMENT'] == app_environment


def test_app_environment_maps_every_known_cdk_environment() -> None:
    assert _app_environment('dev') == 'development'
    assert _app_environment('staging') == 'staging'
    assert _app_environment('prod') == 'production'


def test_lambda_does_not_declare_reserved_aws_region() -> None:
    # AWS Lambda reserves AWS_REGION and injects it at runtime; CDK refuses to
    # synthesize if it is declared. This test locks in that constraint.
    variables = _environment_variables(_compute_template('dev'))
    assert 'AWS_REGION' not in variables


def test_role_is_granted_put_log_events_on_observability_log_group() -> None:
    template = _compute_template('dev')
    statements = _policy_statements(template)

    put_events = [
        statement for statement in statements if 'logs:PutLogEvents' in _actions(statement)
    ]
    assert put_events, 'expected a policy granting logs:PutLogEvents'


def test_put_log_events_is_scoped_to_the_observability_log_group() -> None:
    template = _compute_template('dev')
    statements = [
        statement
        for statement in _policy_statements(template)
        if 'logs:PutLogEvents' in _actions(statement)
    ]
    assert statements, 'expected a policy granting logs:PutLogEvents'

    for statement in statements:
        resources = statement.get('Resource')
        assert resources is not None
        # grant_write resolves to the Observability stack's exported log-group
        # ARN, never a wildcard.
        rendered = json.dumps(resources)
        assert 'Observability' in rendered, 'logs grant must target the Observability stack'
        assert 'AppLogGroup' in rendered, 'logs grant must target the log group ARN'
        assert '*' not in rendered, 'logs grant must not be a wildcard'


def _policy_statements(template: Template) -> list[dict[str, object]]:
    statements: list[dict[str, object]] = []
    for policy in template.find_resources('AWS::IAM::Policy').values():
        document = policy['Properties'].get('PolicyDocument', {})
        entries = document.get('Statement', [])
        if isinstance(entries, dict):
            entries = [entries]
        statements.extend(entries)
    return statements


def _actions(statement: dict[str, object]) -> list[str]:
    action = statement.get('Action', [])
    if isinstance(action, str):
        return [action]
    return [str(item) for item in action]
