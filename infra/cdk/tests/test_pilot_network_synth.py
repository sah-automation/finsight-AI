"""Pilot network contract, proven at the CDK synth seam (issue #361).

Only externally observable template behaviour is asserted: which resources
exist and how the Lambda functions are configured. No AWS credentials and no
internal helper names or constructor arguments are involved.

The ``vector_store`` switch selects the path: dev/prod use ``neon_pgvector``
(no VPC, no NAT gateway), staging uses ``aurora_pgvector`` (VPC retained).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

CDK_DIR = Path(__file__).resolve().parents[1]
PILOT_ENVS = ('dev', 'prod')
STANDARD_ENV = 'staging'
_EXPECTED_PROD_FUNCTION_COUNT = 2

TemplateMap = dict[str, dict[str, object]]


def _synthesize(env_name: str) -> TemplateMap:
    """Synthesize one environment's cloud assembly and parse every template."""
    with tempfile.TemporaryDirectory() as tmp:
        outdir = Path(tmp) / 'cdk.out'
        env = os.environ.copy()
        env['CDK_OUTDIR'] = str(outdir)
        env['CDK_ENV'] = env_name
        env['JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION'] = '1'
        env.pop('CDK_DEFAULT_ACCOUNT', None)
        env.pop('CDK_DEFAULT_REGION', None)
        env.pop('LAMBDA_ZIP', None)
        env.pop('GATEWAY_ZIP', None)

        result = subprocess.run(
            [sys.executable, '-m', 'app.app'],
            cwd=CDK_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

        return {
            path.name.removesuffix('.template.json'): json.loads(path.read_text(encoding='utf-8'))
            for path in outdir.glob('*.template.json')
        }


@pytest.fixture(scope='module')
def templates() -> Callable[[str], TemplateMap]:
    """Synthesize each environment once for the whole module."""
    cache: dict[str, TemplateMap] = {}

    def get(env_name: str) -> TemplateMap:
        if env_name not in cache:
            cache[env_name] = _synthesize(env_name)
        return cache[env_name]

    return get


def _resource_types(template: dict[str, object]) -> list[str]:
    resources = template.get('Resources', {})
    assert isinstance(resources, dict)
    return [
        str(resource.get('Type')) for resource in resources.values() if isinstance(resource, dict)
    ]


def _lambda_functions(template: dict[str, object]) -> dict[str, dict[str, object]]:
    resources = template.get('Resources', {})
    assert isinstance(resources, dict)
    return {
        name: resource
        for name, resource in resources.items()
        if isinstance(resource, dict) and resource.get('Type') == 'AWS::Lambda::Function'
    }


def test_pilot_environments_have_no_nat_gateway(templates: Callable[[str], TemplateMap]) -> None:
    """No pilot template may contain a NAT gateway, in dev or prod."""
    for env_name in PILOT_ENVS:
        synthesized = templates(env_name)
        assert synthesized, f'{env_name} synthesized no templates'
        gateways = [
            (stack, resource_type)
            for stack, template in synthesized.items()
            for resource_type in _resource_types(template)
            if resource_type == 'AWS::EC2::NatGateway'
        ]
        assert gateways == [], f'{env_name} still has NAT gateways: {gateways}'


def test_pilot_environments_have_no_network_stack(templates: Callable[[str], TemplateMap]) -> None:
    """Taking the Lambdas out of the VPC lets the Network stacks disappear."""
    for env_name in PILOT_ENVS:
        assert f'FinSight-{env_name}-Network' not in templates(env_name)


def test_pilot_lambdas_have_no_vpc_config(templates: Callable[[str], TemplateMap]) -> None:
    """Every dev/prod Lambda must use Lambda-managed network egress."""
    for env_name in PILOT_ENVS:
        compute = templates(env_name)[f'FinSight-{env_name}-Compute']
        functions = _lambda_functions(compute)
        assert functions, f'{env_name} compute template has no Lambda functions'
        for name, function in functions.items():
            properties = function.get('Properties', {})
            assert isinstance(properties, dict)
            assert 'VpcConfig' not in properties, f'{env_name}/{name} is still VPC-attached'


def test_prod_synthesizes_both_api_and_gateway_lambdas(
    templates: Callable[[str], TemplateMap],
) -> None:
    """The no-VPC contract must cover the model gateway, not just the API."""
    functions = _lambda_functions(templates('prod')['FinSight-prod-Compute'])
    assert len(functions) == _EXPECTED_PROD_FUNCTION_COUNT, (
        f'expected API and gateway Lambdas, found {sorted(functions)}'
    )


def test_standard_path_keeps_its_vpc(templates: Callable[[str], TemplateMap]) -> None:
    """The undeployed aurora_pgvector option must not silently disappear."""
    network = templates(STANDARD_ENV)['FinSight-staging-Network']
    resource_types = _resource_types(network)

    assert 'AWS::EC2::VPC' in resource_types
    assert 'AWS::EC2::NatGateway' in resource_types

    compute = templates(STANDARD_ENV)['FinSight-staging-Compute']
    functions = _lambda_functions(compute)
    assert functions
    for name, function in functions.items():
        properties = function.get('Properties', {})
        assert isinstance(properties, dict)
        assert 'VpcConfig' in properties, f'staging/{name} lost its VPC attachment'
