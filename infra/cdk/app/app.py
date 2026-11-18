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
from stacks.api_gateway import ApiGatewayStack
from stacks.auth import AuthStack
from stacks.compute import ComputeStack
from stacks.data import DataStack
from stacks.env_config import load_envs, uses_aurora_vpc
from stacks.messaging import MessagingStack
from stacks.network import NetworkStack
from stacks.observability import ObservabilityStack
from stacks.step_functions import StepFunctionsStack

CDK_ROOT = Path(__file__).resolve().parent.parent


def _lambda_asset() -> str | None:
    """Return the API zip path when it has been built, otherwise None."""
    return _require_zip_or_none('LAMBDA_ZIP', CDK_ROOT.parents[1] / 'dist' / 'lambda' / 'api.zip')


def _gateway_asset() -> str | None:
    """Return the gateway zip path when it has been built, otherwise None."""
    return _require_zip_or_none(
        'GATEWAY_ZIP', CDK_ROOT.parents[1] / 'dist' / 'lambda' / 'gateway.zip'
    )


def _require_zip_or_none(env_var: str, default_zip: Path) -> str | None:
    """Resolve a Lambda asset path, failing loudly when explicitly misconfigured.

    An unset variable keeps the placeholder behavior (synth-only contexts may
    not have built the packages). An explicitly-set variable that does not
    exist is a configuration error — ``cdk deploy`` re-runs this app from
    ``cdk.json``, so a wrong value there would otherwise silently deploy
    placeholder code that raises on import.
    """
    candidate = Path(os.getenv(env_var, str(default_zip)))
    if not candidate.exists():
        if os.getenv(env_var):
            raise SystemExit(
                f'{env_var} is set to {candidate!s} but that path does not exist; '
                'build the Lambda packages or unset the variable'
            )
        return None
    return str(candidate)


def main() -> None:
    """Build the stack graph for one environment and synthesize it."""
    app = cdk.App()

    env_name = app.node.try_get_context('env') or os.getenv('CDK_ENV') or 'dev'
    known_envs = load_envs()
    if env_name not in known_envs:
        raise ValueError(f'Unknown environment {env_name!r}; expected one of {sorted(known_envs)}')

    account = app.node.try_get_context('account') or os.getenv('CDK_DEFAULT_ACCOUNT')
    region = app.node.try_get_context('region') or os.getenv('CDK_DEFAULT_REGION') or 'us-east-1'
    env = cdk.Environment(account=account, region=region)

    # The vector_store switch decides whether infrastructure needs a VPC. The
    # pilot (neon_pgvector) has none: Lambdas use their managed network to reach
    # Neon, the model providers, SSM and CloudWatch Logs, so the Network stack
    # and its NAT gateways are not synthesized at all (issue #361).
    env_config = known_envs[env_name]
    net = (
        NetworkStack(
            app,
            f'FinSight-{env_name}-Network',
            env=env,
            env_name=env_name,
            env_config=env_config,
        )
        if uses_aurora_vpc(env_name, env_config)
        else None
    )
    vpc = net.vpc if net is not None else None

    # Stacks in dependency order.
    data = DataStack(
        app,
        f'FinSight-{env_name}-Data',
        env=env,
        env_name=env_name,
        vpc=vpc,
        env_config=env_config,
    )
    msg = MessagingStack(app, f'FinSight-{env_name}-Messaging', env=env, env_name=env_name)
    auth = AuthStack(app, f'FinSight-{env_name}-Auth', env=env, env_name=env_name)
    api_gateway = ApiGatewayStack(
        app,
        f'FinSight-{env_name}-ApiGateway',
        env=env,
        env_name=env_name,
        env_config=env_config,
    )
    step_functions = StepFunctionsStack(
        app,
        f'FinSight-{env_name}-StepFunctions',
        env=env,
        env_name=env_name,
        messaging=msg,
    )
    observability = ObservabilityStack(
        app, f'FinSight-{env_name}-Observability', env=env, env_name=env_name
    )
    ComputeStack(
        app,
        f'FinSight-{env_name}-Compute',
        env=env,
        env_name=env_name,
        vpc=vpc,
        data=data,
        messaging=msg,
        auth=auth,
        api_gateway=api_gateway,
        lambda_zip=_lambda_asset(),
        gateway_zip=_gateway_asset(),
        step_functions=step_functions,
        observability=observability,
    )

    app.synth()


if __name__ == '__main__':
    main()
