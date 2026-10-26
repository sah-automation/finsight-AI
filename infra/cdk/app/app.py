#!/usr/bin/env python3
"""AWS CDK app for FinSight AI.

Run from `infra/cdk` (or through `make infra-synth`) so the `stacks` package
resolves from the working directory:

    cd infra/cdk && python -m app.app
"""

from __future__ import annotations

import os
from pathlib import Path

import aws_cdk as cdk
import yaml
from stacks.auth import AuthStack
from stacks.compute import ComputeStack
from stacks.data import DataStack
from stacks.messaging import MessagingStack
from stacks.network import NetworkStack
from stacks.observability import ObservabilityStack

CDK_ROOT = Path(__file__).resolve().parent.parent


def _load_envs() -> dict[str, dict[str, object]]:
    """Load the known environment names from config/envs.yaml."""
    envs_file = CDK_ROOT / 'config' / 'envs.yaml'
    loaded = yaml.safe_load(envs_file.read_text(encoding='utf-8')) or {}
    if not isinstance(loaded, dict):
        raise TypeError(f'{envs_file} must contain a mapping of environment names')
    return loaded


def _lambda_asset() -> str | None:
    """Return the API zip path when it has been built, otherwise None."""
    default_zip = CDK_ROOT.parents[1] / 'dist' / 'lambda' / 'api.zip'
    candidate = Path(os.getenv('LAMBDA_ZIP', str(default_zip)))
    return str(candidate) if candidate.exists() else None


def main() -> None:
    """Build the stack graph for one environment and synthesize it."""
    app = cdk.App()

    env_name = app.node.try_get_context('env') or os.getenv('CDK_ENV') or 'dev'
    known_envs = _load_envs()
    if env_name not in known_envs:
        raise ValueError(f'Unknown environment {env_name!r}; expected one of {sorted(known_envs)}')

    account = app.node.try_get_context('account') or os.getenv('CDK_DEFAULT_ACCOUNT')
    region = app.node.try_get_context('region') or os.getenv('CDK_DEFAULT_REGION') or 'us-east-1'
    env = cdk.Environment(account=account, region=region)

    # Stacks in dependency order.
    net = NetworkStack(app, f'FinSight-{env_name}-Network', env=env, env_name=env_name)
    data = DataStack(app, f'FinSight-{env_name}-Data', env=env, env_name=env_name, vpc=net.vpc)
    msg = MessagingStack(app, f'FinSight-{env_name}-Messaging', env=env, env_name=env_name)
    auth = AuthStack(app, f'FinSight-{env_name}-Auth', env=env, env_name=env_name)
    ComputeStack(
        app,
        f'FinSight-{env_name}-Compute',
        env=env,
        env_name=env_name,
        vpc=net.vpc,
        data=data,
        messaging=msg,
        auth=auth,
        lambda_zip=_lambda_asset(),
    )
    ObservabilityStack(app, f'FinSight-{env_name}-Observability', env=env, env_name=env_name)

    app.synth()


if __name__ == '__main__':
    main()
