"""Synthesis tests for the gateway function (issue #330)."""

from __future__ import annotations

import json

import aws_cdk as cdk
from aws_cdk.assertions import Template
from stacks.api_gateway import ApiGatewayStack
from stacks.auth import AuthStack
from stacks.compute import ComputeStack
from stacks.env_config import load_envs
from stacks.observability import ObservabilityStack

# Pin the account/region so the region-derived OTLP endpoint is deterministic.
_ENV = cdk.Environment(account='123456789012', region='us-east-1')


def _compute_template_with_gateway(
    env_name: str = 'prod', gateway_zip: str | None = None
) -> Template:
    """Synthesize a compute stack with optional gateway function."""
    app = cdk.App()
    auth = AuthStack(app, f'FinSight-{env_name}-Auth', env=_ENV, env_name=env_name)
    observability = ObservabilityStack(
        app, f'FinSight-{env_name}-Observability', env=_ENV, env_name=env_name
    )
    api_gateway = ApiGatewayStack(
        app,
        f'FinSight-{env_name}-ApiGateway',
        env=_ENV,
        env_name=env_name,
        env_config=load_envs()[env_name],
    )
    compute = ComputeStack(
        app,
        f'FinSight-{env_name}-Compute',
        env=_ENV,
        env_name=env_name,
        auth=auth,
        api_gateway=api_gateway,
        observability=observability,
        gateway_zip=gateway_zip,
    )
    return Template.from_stack(compute)


def _gateway_lambda(template: Template) -> dict[str, object]:
    functions = template.find_resources('AWS::Lambda::Function')
    gateway_functions = {key: value for key, value in functions.items() if 'GatewayFunction' in key}
    assert len(gateway_functions) == 1, (
        f'expected one Gateway Lambda, found {sorted(gateway_functions)}'
    )
    return next(iter(gateway_functions.values()))


def _api_lambda(template: Template) -> dict[str, object]:
    functions = template.find_resources('AWS::Lambda::Function')
    api_functions = {key: value for key, value in functions.items() if 'ApiFunction' in key}
    assert len(api_functions) == 1, f'expected one API Lambda, found {sorted(api_functions)}'
    return next(iter(api_functions.values()))


def test_gateway_function_exists_only_for_prod() -> None:
    """The model-gateway Lambda is only created for prod (remote_gateway transport)."""
    prod_template = _compute_template_with_gateway('prod', gateway_zip=None)
    dev_template = _compute_template_with_gateway('dev', gateway_zip=None)

    prod_functions = prod_template.find_resources('AWS::Lambda::Function')
    dev_functions = dev_template.find_resources('AWS::Lambda::Function')

    prod_gateway = {k: v for k, v in prod_functions.items() if 'GatewayFunction' in k}
    dev_gateway = {k: v for k, v in dev_functions.items() if 'GatewayFunction' in k}

    assert len(prod_gateway) == 1, 'prod must have the gateway function'
    assert len(dev_gateway) == 0, 'dev must not have the gateway function'


def test_gateway_function_has_web_adapter_layer() -> None:
    """The gateway function attaches the Lambda Web Adapter layer (x86_64)."""
    template = _compute_template_with_gateway('prod', gateway_zip=None)
    gateway = _gateway_lambda(template)

    layers = gateway['Properties'].get('Layers', [])
    # Layers are a list of ARNs (strings) in the synthesized template
    layer_arns = [str(layer) for layer in layers]
    # Lambda Web Adapter layer ARN pattern for us-east-1
    assert any('LambdaAdapterLayerX86' in arn for arn in layer_arns), layer_arns


def test_gateway_function_handler_is_run_sh() -> None:
    """The gateway function's handler is the startup script (run.sh)."""
    template = _compute_template_with_gateway('prod', gateway_zip=None)
    gateway = _gateway_lambda(template)

    handler = gateway['Properties'].get('Handler')
    assert handler == 'run.sh'


def test_gateway_function_runtime_is_python_3_12() -> None:
    """The gateway function uses Python 3.12 runtime."""
    template = _compute_template_with_gateway('prod', gateway_zip=None)
    gateway = _gateway_lambda(template)

    runtime = gateway['Properties'].get('Runtime')
    assert runtime == 'python3.12'


def test_gateway_function_has_master_key_from_ssm() -> None:
    """The gateway function gets MODEL_GATEWAY_MASTER_KEY_PARAM pointing to SSM."""
    template = _compute_template_with_gateway('prod', gateway_zip=None)
    gateway = _gateway_lambda(template)

    env_vars = gateway['Properties']['Environment']['Variables']
    param_name = env_vars.get('MODEL_GATEWAY_MASTER_KEY_PARAM')
    assert param_name is not None
    # CDK uses a Ref to the SSM parameter resource
    assert isinstance(param_name, dict) and 'Ref' in param_name
    param_ref = param_name['Ref']
    assert param_ref.startswith('ModelGatewayMasterKeyprod')
    # The parameter should exist as an SSM StringParameter resource
    ssm_params = template.find_resources('AWS::SSM::Parameter')
    gateway_params = {k: v for k, v in ssm_params.items() if 'ModelGatewayMasterKey' in k}
    assert len(gateway_params) == 1
    gateway_param = next(iter(gateway_params.values()))
    assert gateway_param['Properties']['Name'] == '/finsight/prod/model_gateway_master_key'
    assert gateway_param['Properties']['Type'] == 'SecureString'


def test_gateway_function_has_response_stream_invoke_mode() -> None:
    """The gateway function URL uses RESPONSE_STREAM for NDJSON streaming."""
    template = _compute_template_with_gateway('prod', gateway_zip=None)

    # Find the Lambda Function URL resource
    urls = template.find_resources('AWS::Lambda::Url')
    gateway_urls = {k: v for k, v in urls.items() if 'Gateway' in k}
    assert len(gateway_urls) == 1
    gateway_url = next(iter(gateway_urls.values()))

    invoke_mode = gateway_url['Properties'].get('InvokeMode')
    assert invoke_mode == 'RESPONSE_STREAM'


def test_api_function_has_model_gateway_url_env() -> None:
    """The API function gets MODEL_GATEWAY_URL pointing to the gateway function URL."""
    template = _compute_template_with_gateway('prod', gateway_zip=None)
    api_fn = _api_lambda(template)

    env_vars = api_fn['Properties']['Environment']['Variables']
    gateway_url = env_vars.get('MODEL_GATEWAY_URL')
    assert gateway_url is not None
    # Should reference the gateway function URL
    assert 'Fn::GetAtt' in str(gateway_url) or 'Ref' in str(gateway_url)


def test_api_function_can_invoke_gateway() -> None:
    """The API function's role has lambda:InvokeFunction on the gateway function."""
    template = _compute_template_with_gateway('prod', gateway_zip=None)

    # Find the policy on the API function's role that grants InvokeFunction
    # grant_invoke adds the permission to the grantee's (API function's) role policy
    policies = template.find_resources('AWS::IAM::Policy')
    api_role_policies = {k: v for k, v in policies.items() if 'LambdaExecutionRole' in k}

    found_invoke = False
    for policy in api_role_policies.values():
        statements = policy['Properties'].get('PolicyDocument', {}).get('Statement', [])
        for stmt in statements:
            if stmt.get('Effect') == 'Allow' and 'lambda:InvokeFunction' in stmt.get('Action', []):
                resources = stmt.get('Resource', [])
                if isinstance(resources, str):
                    resources = [resources]
                # Resources can be strings or CloudFormation intrinsic function dicts
                for r in resources:
                    r_str = json.dumps(r) if isinstance(r, dict) else str(r)
                    if 'GatewayFunction' in r_str:
                        found_invoke = True
                        break

    assert found_invoke, 'API function role must have InvokeFunction on GatewayFunction'
