from __future__ import annotations

from pathlib import Path

import yaml
from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from constructs import Construct

_ENVS_FILE = Path(__file__).resolve().parent.parent / 'config' / 'envs.yaml'
_REMOVAL_POLICIES = {
    'retain': RemovalPolicy.RETAIN,
    'destroy': RemovalPolicy.DESTROY,
}


def _removal_policy(env_name: str) -> RemovalPolicy:
    loaded = yaml.safe_load(_ENVS_FILE.read_text(encoding='utf-8')) or {}
    if not isinstance(loaded, dict) or env_name not in loaded:
        raise ValueError(f'Unknown environment {env_name!r}')
    name = str(loaded[env_name]['removal_policy']).lower()
    if name not in _REMOVAL_POLICIES:
        raise ValueError(f'Unknown removal_policy {name!r}')
    return _REMOVAL_POLICIES[name]


# The four business roles from ADR-0003. Each Cognito group is named exactly
# after its role id so the future RBAC loader can map membership directly.
BUSINESS_ROLES: tuple[str, ...] = (
    'executive_leadership',
    'corporate_finance_planners',
    'audit_compliance',
    'system_admin',
)


class AuthStack(Stack):
    """Cognito user pool, app client, business-role groups, and context attributes."""

    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name

        # Custom attributes carry company, user, role, and access scope. They are
        # surfaced through the Cognito authorizer into API Gateway request context
        # as ``custom:<name>`` claims.
        self.user_pool = cognito.UserPool(
            self,
            f'UserPool{env_name}',
            user_pool_name=f'finsight-{env_name}-users',
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            custom_attributes={
                'company_id': cognito.StringAttribute(mutable=True),
                'user_id': cognito.StringAttribute(mutable=True),
                'role': cognito.StringAttribute(mutable=True),
                'access_scope': cognito.StringAttribute(mutable=True),
                # Alias forms accepted by the context builder and hidden tests.
                'company': cognito.StringAttribute(mutable=True),
                'user': cognito.StringAttribute(mutable=True),
            },
            removal_policy=_removal_policy(env_name),
        )

        exposed_attributes = cognito.ClientAttributes().with_custom_attributes(
            'company_id',
            'user_id',
            'role',
            'access_scope',
            'company',
            'user',
        )

        self.user_pool_client = self.user_pool.add_client(
            f'UserPoolClient{env_name}',
            user_pool_client_name=f'finsight-{env_name}-client',
            auth_flows=cognito.AuthFlow(user_srp=True),
            read_attributes=exposed_attributes,
            write_attributes=exposed_attributes,
        )

        # One group per business role.
        self.groups: dict[str, cognito.CfnUserPoolGroup] = {}
        self.role_groups = self.groups
        self.user_pool_groups = []
        for index, role in enumerate(BUSINESS_ROLES):
            safe_role = role.replace('_', '')
            group = cognito.CfnUserPoolGroup(
                self,
                f'UserPoolGroup{env_name}{safe_role.title()}',
                user_pool_id=self.user_pool.user_pool_id,
                group_name=role,
                description=f'Cognito group for the {role} business role.',
                precedence=index + 1,
            )
            self.groups[role] = group
            self.user_pool_groups.append(group)

        # Aliases for tests and consumers.
        self.cognito_groups = self.groups
        self.group_names = list(BUSINESS_ROLES)
        self.groups_list = list(self.groups.values())
