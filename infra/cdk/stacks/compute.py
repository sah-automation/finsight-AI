"""Compute stack: Lambda functions and their execution role."""

from __future__ import annotations

from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

PLACEHOLDER_CODE = """\
def handler(event, context):
    raise RuntimeError('build dist/lambda/api.zip before deploying')
"""


class ComputeStack(Stack):
    """Lambda functions for the API entrypoints."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        vpc: ec2.Vpc,
        data: object,
        messaging: object,
        auth: object,
        lambda_zip: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]

        # Basic execution role. Least privilege is tightened as handlers land.
        role = iam.Role(
            self,
            f'LambdaExecutionRole{env_name}',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    'service-role/AWSLambdaVPCAccessExecutionRole'
                ),
            ],
        )

        code = (
            lambda_.Code.from_asset(lambda_zip)
            if lambda_zip
            else lambda_.Code.from_inline(PLACEHOLDER_CODE)
        )

        # Placeholder Lambda function (real zip package per DI-21).
        # data, messaging, and auth are accepted for dependency wiring and
        # permissions that land with the handlers.
        self.api_fn = lambda_.Function(
            self,
            f'ApiFunction{env_name}',
            function_name=f'finsight-{env_name}-api',
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler='finsight.entrypoints.api.main.handler',
            code=code,
            vpc=vpc,
            role=role,
            memory_size=1024,
        )
