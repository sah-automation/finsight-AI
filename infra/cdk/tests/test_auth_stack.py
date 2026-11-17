"""Synthesis tests for the auth stack (Cognito user pool and app client)."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk.assertions import Template
from stacks.auth import AuthStack


def _template(env_name: str = 'prod') -> Template:
    app = cdk.App()
    stack = AuthStack(
        app,
        f'FinSight-{env_name}-Auth',
        env=cdk.Environment(account='123456789012', region='us-east-1'),
        env_name=env_name,
    )
    return Template.from_stack(stack)


def test_app_client_allows_admin_user_password_auth() -> None:
    """The deploy pipeline obtains a smoke-test JWT via admin-initiate-auth.

    There is no hosted UI or OAuth flow in the pipeline, so the app client
    must explicitly allow the ADMIN_USER_PASSWORD auth flow (with SRP as the
    interactive default). Without it the smoke gate cannot authenticate.
    """
    template = _template('prod')
    clients = template.find_resources('AWS::Cognito::UserPoolClient')
    assert len(clients) == 1
    explicit = next(iter(clients.values()))['Properties'].get('ExplicitAuthFlows', [])
    assert 'ALLOW_ADMIN_USER_PASSWORD_AUTH' in explicit, explicit
    assert 'ALLOW_USER_SRP_AUTH' in explicit, explicit
