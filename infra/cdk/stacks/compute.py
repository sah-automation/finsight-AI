"""Compute stack: Lambda functions, API Gateway, and scoped permissions."""

from __future__ import annotations

# CDK constructs are accepted as opaque objects to avoid over-coupling this stack.
from aws_cdk import Stack
from aws_cdk import aws_apigateway as apigw
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
        vpc: object = None,
        data: object = None,
        messaging: object = None,
        auth: object = None,
        lambda_zip: str | None = None,
        step_functions: object = None,
        workflow: object = None,
        workflows: object = None,
        state_machine: object = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name

        # Basic execution role. Least privilege is tightened below.
        role = iam.Role(
            self,
            f'LambdaExecutionRole{env_name}',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    'service-role/AWSLambdaVPCAccessExecutionRole'
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    'service-role/AWSLambdaBasicExecutionRole'
                ),
            ],
        )

        zip_path = lambda_zip
        code = (
            lambda_.Code.from_asset(zip_path)
            if zip_path
            else lambda_.Code.from_inline(PLACEHOLDER_CODE)
        )

        lambda_kwargs: dict[str, object] = {}
        if vpc is not None:
            lambda_kwargs['vpc'] = vpc

        self.api_fn = lambda_.Function(
            self,
            f'ApiFunction{env_name}',
            function_name=f'finsight-{env_name}-api',
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler='finsight.entrypoints.api.main.handler',
            code=code,
            role=role,
            memory_size=1024,
            **lambda_kwargs,
        )

        # Scoped permissions for Aurora, DynamoDB, S3, queues, and workflows.
        self._grant_scoped_permissions(
            role, data, messaging, auth, step_functions, workflow, workflows, state_machine
        )

        # API Gateway with Cognito authorization.
        self.rest_api = apigw.RestApi(
            self,
            f'ApiGateway{env_name}',
            rest_api_name=f'finsight-{env_name}-api',
            deploy=True,
        )
        self.api = self.rest_api
        self.api_gateway = self.rest_api

        user_pool = getattr(auth, 'user_pool', None) if auth is not None else None
        if user_pool is not None:
            self.authorizer = apigw.CognitoUserPoolsAuthorizer(
                self,
                f'ApiAuthorizer{env_name}',
                cognito_user_pools=[user_pool],
                authorizer_name=f'finsight-{env_name}-authorizer',
                identity_source='method.request.header.Authorization',
            )
            self.cognito_authorizer = self.authorizer

            integration = apigw.LambdaIntegration(self.api_fn, proxy=True)
            auth_type = apigw.AuthorizationType.COGNITO
            root_method = self.rest_api.root.add_method(
                'ANY',
                integration,
                authorizer=self.authorizer,
                authorization_type=auth_type,
            )
            proxy = self.rest_api.root.add_resource('{proxy+}')
            proxy.add_method(
                'ANY',
                integration,
                authorizer=self.authorizer,
                authorization_type=auth_type,
            )
            self.protected_methods = [root_method]
        else:
            self.authorizer = None
            self.cognito_authorizer = None

    def _grant_scoped_permissions(  # noqa: PLR0912
        self,
        role: object,
        data: object,
        messaging: object,
        auth: object,
        *workflow_candidates: object,
    ) -> None:
        del auth  # Reserved for future scoped Cognito permissions.

        # Aurora
        cluster = None
        if data is not None:
            cluster = (
                getattr(data, 'cluster', None)
                or getattr(data, 'source_of_truth', None)
                or getattr(data, 'aurora_cluster', None)
                or getattr(data, 'aurora', None)
            )
        if cluster is not None and hasattr(cluster, 'grant_connect'):
            cluster.grant_connect(role, 'finsight')

        # DynamoDB tables
        if data is not None:
            table_attrs = (
                'answer_cache',
                'role_cache',
                'metering',
                'job_progress',
                'sessions',
                'chat_history',
                'chat_threads',
                'jobs',
                'documents',
            )
            for attr in table_attrs:
                table = getattr(data, attr, None)
                if table is not None and hasattr(table, 'grant_read_write_data'):
                    table.grant_read_write_data(role)

            # S3 buckets
            bucket_attrs = (
                'documents_bucket',
                'reports_bucket',
                'backups_bucket',
                'artifacts_bucket',
                'uploads_bucket',
            )
            for attr in bucket_attrs:
                bucket = getattr(data, attr, None)
                if bucket is not None and hasattr(bucket, 'grant_read_write'):
                    bucket.grant_read_write(role)

        # SQS queues
        if messaging is not None:
            queue_attrs = (
                'ingestion',
                'reprocessing',
                'reports',
                'dlq',
                'ingestion_queue',
                'reprocessing_queue',
                'reports_queue',
                'dead_letter_queue',
            )
            for attr in queue_attrs:
                queue = getattr(messaging, attr, None)
                if queue is not None:
                    if hasattr(queue, 'grant_send_messages'):
                        queue.grant_send_messages(role)
                    if hasattr(queue, 'grant_consume_messages'):
                        queue.grant_consume_messages(role)

        # Step Functions state machines
        for candidate in workflow_candidates:
            state_machine = None
            if candidate is not None:
                state_machine = (
                    getattr(candidate, 'state_machine', None)
                    or getattr(candidate, 'step_function', None)
                    or getattr(candidate, 'stateMachine', None)
                    or getattr(candidate, 'ingestion_state_machine', None)
                    or candidate
                )
            if state_machine is not None and hasattr(state_machine, 'grant_start_execution'):
                state_machine.grant_start_execution(role)
