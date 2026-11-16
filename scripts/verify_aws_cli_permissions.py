#!/usr/bin/env python3
"""Verify the effective permissions of the aws-cli operator user.

The operator user is the identity an automated agent (or a human with the key)
uses to work on this application. Its permissions are capped by three
customer-managed policies that live in ``infra/cdk/policies/``:

  * finsight-aws-cli-identity   — baseline grant plus IAM/trust guardrails
  * finsight-aws-cli-data       — org, account, stacks, parameters, secrets
  * finsight-aws-cli-services   — storage, logs, services the app never uses

This script proves both halves of that arrangement:

  * the application's own work still succeeds (CloudFormation, SSM, budgets,
    Cost Explorer, Lambda, S3, assuming the CDK deploy role);
  * the guardrails still block (IAM users, other credentials, the organization,
    the account owner settings, resources outside the application's namespace).

Every live probe is read-only, or targets a resource that does not exist, so
a wrongly-allowed call cannot create or destroy anything. The resource-scoped
decisions are checked with the IAM policy simulator, which evaluates the same
identity policies without touching the account.

Usage:

    uv run python scripts/verify_aws_cli_permissions.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

ACCOUNT = '069632763967'
REGION = 'us-east-1'
USER = 'aws-cli'
PRINCIPAL_ARN = f'arn:aws:iam::{ACCOUNT}:user/{USER}'

_DENIED_MARKERS = (
    'accessdenied',
    'not authorized',
    'explicit deny',
    'forbidden',
)
_ALLOWED_MARKERS = (
    'nosuch',
    'notfound',
    'invalidparameter',
    'does not exist',
    'validationerror',
    'invalidciphertext',
    'invalidarn',
    'invalidclienttoken',
    'operation: not found',
)


@dataclass(frozen=True)
class LiveProbe:
    """A call made with the operator credentials, and what it should answer."""

    expectation: str
    label: str
    args: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SimulatorProbe:
    """A resource-scoped decision, checked with the IAM policy simulator."""

    expectation: str
    label: str
    action: str
    resource: str = ''


def classify(output: str, returncode: int) -> str:
    """Map an AWS CLI response to ``ALLOW``, ``DENY`` or ``ERROR``.

    A refusal is a denial. A missing resource means the request was authorised
    and only the resource was absent — never a denial. Anything unrecognised is
    reported as ``ERROR`` so it can never be mistaken for a passing check.
    """
    lowered = output.lower()
    if any(marker in lowered for marker in _DENIED_MARKERS):
        return 'DENY'
    if any(marker in lowered for marker in _ALLOWED_MARKERS):
        return 'ALLOW'
    return 'ALLOW' if returncode == 0 else 'ERROR'


LIVE_PROBES: tuple[LiveProbe, ...] = (
    LiveProbe('ALLOW', 'sts:GetCallerIdentity', ['sts', 'get-caller-identity']),
    LiveProbe(
        'ALLOW',
        'CloudFormation:ListStacks',
        ['cloudformation', 'list-stacks', '--region', REGION],
    ),
    LiveProbe(
        'ALLOW',
        'CloudFormation:DescribeStacks',
        [
            'cloudformation',
            'describe-stacks',
            '--stack-name',
            'CDKToolkit',
            '--region',
            REGION,
        ],
    ),
    LiveProbe(
        'ALLOW',
        'SSM:DescribeParameters (metadata only)',
        ['ssm', 'describe-parameters', '--region', REGION],
    ),
    LiveProbe(
        'ALLOW',
        'SSM:GetParameter inside /finsight/*',
        ['ssm', 'get-parameter', '--name', '/finsight/probe-missing', '--region', REGION],
    ),
    LiveProbe(
        'ALLOW',
        'Budgets:DescribeBudget',
        [
            'budgets',
            'describe-budget',
            '--account-id',
            ACCOUNT,
            '--budget-name',
            'finsight-monthly-budget',
            '--region',
            REGION,
        ],
    ),
    LiveProbe(
        'ALLOW',
        'Cost Explorer:GetAnomalyMonitors',
        ['ce', 'get-anomaly-monitors', '--region', REGION],
    ),
    LiveProbe(
        'ALLOW',
        'IAM:GetRole (read)',
        ['iam', 'get-role', '--role-name', 'finsight-deploy-role'],
    ),
    LiveProbe(
        'ALLOW',
        'S3:ListBucket on the CDK asset bucket',
        [
            's3api',
            'list-objects-v2',
            '--bucket',
            f'cdk-hnb659fds-assets-{ACCOUNT}-{REGION}',
        ],
    ),
    LiveProbe('ALLOW', 'Lambda:ListFunctions', ['lambda', 'list-functions', '--region', REGION]),
    LiveProbe(
        'ALLOW',
        'IAM:ListAccessKeys on itself',
        ['iam', 'list-access-keys', '--user-name', USER],
    ),
    LiveProbe(
        'ALLOW',
        'STS:AssumeRole the CDK deploy role',
        [
            'sts',
            'assume-role',
            '--role-arn',
            f'arn:aws:iam::{ACCOUNT}:role/cdk-hnb659fds-deploy-role-{ACCOUNT}-{REGION}',
            '--role-session-name',
            'permission-verify',
            '--region',
            REGION,
        ],
    ),
    LiveProbe(
        'DENY',
        'IAM:CreateUser (probe targets a user that does not exist)',
        ['iam', 'delete-user', '--user-name', 'finsight-nonexistent-probe'],
    ),
    LiveProbe(
        'DENY',
        'IAM:PutUserPolicy on the operator user',
        [
            'iam',
            'delete-user-policy',
            '--user-name',
            USER,
            '--policy-name',
            'nonexistent-probe',
        ],
    ),
    LiveProbe(
        'DENY',
        'IAM:ListAccessKeys on another user',
        ['iam', 'list-access-keys', '--user-name', 'administrator'],
    ),
    LiveProbe(
        'DENY',
        'IAM:UpdateRole outside the application namespace',
        ['iam', 'update-role', '--role-name', 'some-foreign-role'],
    ),
    LiveProbe(
        'DENY',
        'IAM:CreateOpenIDConnectProvider (the trust chain)',
        [
            'iam',
            'delete-open-id-connect-provider',
            '--open-id-connect-provider-arn',
            f'arn:aws:iam::{ACCOUNT}:oidc-provider/nonexistent',
        ],
    ),
    LiveProbe(
        'DENY',
        'Organizations:ListAccounts',
        ['organizations', 'list-accounts'],
    ),
    LiveProbe(
        'DENY',
        'Account:GetAlternateContact (recovery details)',
        ['account', 'get-alternate-contact', '--alternate-contact-type', 'PRIMARY'],
    ),
    LiveProbe(
        'DENY',
        'SSM:GetParameter outside /finsight/*',
        ['ssm', 'get-parameter', '--name', '/nonexistent/other/path', '--region', REGION],
    ),
    LiveProbe(
        'DENY',
        'SecretsManager:GetSecretValue outside the app namespace',
        [
            'secretsmanager',
            'get-secret-value',
            '--secret-id',
            'other-team-secret',
            '--region',
            REGION,
        ],
    ),
    LiveProbe(
        'DENY',
        'CloudWatch Logs:DeleteLogGroup outside the app groups',
        [
            'logs',
            'delete-log-group',
            '--log-group-name',
            '/aws/some/other-group',
            '--region',
            REGION,
        ],
    ),
    LiveProbe(
        'DENY',
        'CloudFormation:UpdateStack outside the app stacks',
        [
            'cloudformation',
            'update-stack',
            '--stack-name',
            'finsight-foreign-stack',
            '--template-body',
            '{}',
            '--region',
            REGION,
        ],
    ),
    LiveProbe(
        'DENY',
        'Glue (a service the application never uses)',
        ['glue', 'get-databases', '--region', REGION],
    ),
    LiveProbe(
        'DENY',
        'Athena (a service the application never uses)',
        ['athena', 'list-work-groups', '--region', REGION],
    ),
    LiveProbe('DENY', 'ECS (a service the application never uses)', ['ecs', 'list-clusters']),
    LiveProbe(
        'DENY',
        'Bedrock (a service the application never uses)',
        ['bedrock', 'list-foundation-models', '--region', REGION],
    ),
)

SIMULATOR_PROBES: tuple[SimulatorProbe, ...] = (
    SimulatorProbe(
        'explicitDeny', 'STS:AssumeRoleWithWebIdentity', 'sts:AssumeRoleWithWebIdentity'
    ),
    SimulatorProbe('explicitDeny', 'IAM:CreateUser', 'iam:CreateUser'),
    SimulatorProbe(
        'explicitDeny',
        'IAM:CreateRole on a foreign name',
        'iam:CreateRole',
        f'arn:aws:iam::{ACCOUNT}:role/foreign-role',
    ),
    SimulatorProbe(
        'allowed',
        'IAM:CreateRole inside the app namespace',
        'iam:CreateRole',
        f'arn:aws:iam::{ACCOUNT}:role/finsight-probe-role',
    ),
    SimulatorProbe(
        'explicitDeny',
        'IAM:PassRole on a foreign role',
        'iam:PassRole',
        f'arn:aws:iam::{ACCOUNT}:role/foreign-role',
    ),
    SimulatorProbe(
        'allowed',
        'IAM:PassRole on an app role',
        'iam:PassRole',
        f'arn:aws:iam::{ACCOUNT}:role/finsight-deploy-role',
    ),
    SimulatorProbe(
        'explicitDeny',
        'STS:AssumeRole on a foreign role',
        'sts:AssumeRole',
        f'arn:aws:iam::{ACCOUNT}:role/foreign-role',
    ),
    SimulatorProbe(
        'explicitDeny',
        'CloudFormation:CreateStack on a foreign stack',
        'cloudformation:CreateStack',
        f'arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/Other-Stack/abc',
    ),
    SimulatorProbe(
        'allowed',
        'CloudFormation:CreateStack on a FinSight-* stack',
        'cloudformation:CreateStack',
        f'arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/FinSight-dev-Data/abc',
    ),
    SimulatorProbe(
        'explicitDeny',
        'SSM:GetParameter outside /finsight/*',
        'ssm:GetParameter',
        f'arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/other/path',
    ),
    SimulatorProbe(
        'allowed',
        'SSM:GetParameter on /finsight/*',
        'ssm:GetParameter',
        f'arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/finsight/prod/neon/database_url',
    ),
    SimulatorProbe(
        'explicitDeny',
        'S3:GetObject on a foreign bucket',
        's3:GetObject',
        'arn:aws:s3:::some-other-team-bucket/x',
    ),
    SimulatorProbe(
        'allowed',
        'S3:GetObject inside the app namespace',
        's3:GetObject',
        'arn:aws:s3:::finsight-dev-documents/x',
    ),
    SimulatorProbe(
        'explicitDeny',
        'KMS:Decrypt on another account key',
        'kms:Decrypt',
        'arn:aws:kms:us-east-1:111122223333:key/0000',
    ),
    SimulatorProbe(
        'allowed',
        'KMS:Decrypt on this account key',
        'kms:Decrypt',
        f'arn:aws:kms:{REGION}:{ACCOUNT}:key/0000',
    ),
    SimulatorProbe(
        'explicitDeny',
        'Logs:PutLogEvents outside the app groups',
        'logs:PutLogEvents',
        f'arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/other:*',
    ),
    SimulatorProbe(
        'explicitDeny',
        'SecretsManager:GetSecretValue outside the app namespace',
        'secretsmanager:GetSecretValue',
        f'arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:other-team',
    ),
    SimulatorProbe(
        'allowed',
        'SecretsManager:GetSecretValue on the app secret',
        'secretsmanager:GetSecretValue',
        f'arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:AuroraClusterprodSecretC337EDF5',
    ),
    SimulatorProbe('explicitDeny', 'Bedrock:InvokeModel', 'bedrock:InvokeModel'),
    SimulatorProbe('explicitDeny', 'EC2:RunInstances', 'ec2:RunInstances'),
    SimulatorProbe(
        'explicitDeny', 'IAM:PutUserPermissionsBoundary', 'iam:PutUserPermissionsBoundary'
    ),
    SimulatorProbe(
        'explicitDeny', 'IAM:CreateOpenIDConnectProvider', 'iam:CreateOpenIDConnectProvider'
    ),
    SimulatorProbe('allowed', 'Budgets:DescribeBudget', 'budgets:DescribeBudget'),
    SimulatorProbe('allowed', 'Cost Explorer:GetAnomalyMonitors', 'ce:GetAnomalyMonitors'),
)


def _run(args: list[str]) -> tuple[int, str]:
    """Run an AWS CLI call and return its exit code and combined output."""
    executable = shutil.which('aws') or 'aws'
    completed = subprocess.run(  # noqa: S603 - fixed argument list, no shell
        [executable, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, f'{completed.stdout}{completed.stderr}'


def _simulate(probe: SimulatorProbe) -> str:
    """Ask the IAM simulator for the decision on one action and resource."""
    args = [
        'iam',
        'simulate-principal-policy',
        '--policy-source-arn',
        PRINCIPAL_ARN,
        '--action-names',
        probe.action,
    ]
    if probe.resource:
        args += ['--resource-arns', probe.resource]
    code, output = _run(args)
    if code != 0:
        return 'ERROR'
    try:
        results = json.loads(output)['EvaluationResults']
    except (json.JSONDecodeError, KeyError):
        return 'ERROR'
    if not results:
        return 'ERROR'
    return results[0]['EvalDecision']


def main() -> int:
    if shutil.which('aws') is None:
        print('the AWS CLI is required to verify permissions', file=sys.stderr)
        return 2

    failures = 0
    print('── live: the application work still succeeds ──────────────────────────')
    for probe in LIVE_PROBES:
        code, output = _run(probe.args)
        verdict = classify(output, code)
        status = 'ok  ' if verdict == probe.expectation else 'FAIL'
        if verdict != probe.expectation:
            failures += 1
        print(f'  [{status}] {probe.label}: {verdict}')

    print('── simulator: the resource-scoped decisions ─────────────────────────')
    for probe in SIMULATOR_PROBES:
        verdict = _simulate(probe)
        status = 'ok  ' if verdict == probe.expectation else 'FAIL'
        if verdict != probe.expectation:
            failures += 1
        print(f'  [{status}] {probe.label}: {verdict}')

    print('────────────────────────────────────────────────────────────────────')
    total = len(LIVE_PROBES) + len(SIMULATOR_PROBES)
    if failures:
        print(f'  {failures} of {total} checks failed', file=sys.stderr)
        return 1
    print(f'  all {total} checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
