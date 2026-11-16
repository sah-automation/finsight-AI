"""Compute stack: Lambda functions, API Gateway, and scoped permissions."""

from __future__ import annotations

import json

# CDK constructs are accepted as opaque objects to avoid over-coupling this stack.
from aws_cdk import Stack
from aws_cdk import aws_apigatewayv2 as apigatewayv2
from aws_cdk import aws_apigatewayv2_authorizers as apigatewayv2_auth
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from stacks.env_config import load_env_config

PLACEHOLDER_CODE = """\
def handler(event, context):
    raise RuntimeError('build dist/lambda/api.zip before deploying')
"""


def _app_environment(env_name: str) -> str:
    """Map a CDK environment name (dev/prod) to the loader's ENVIRONMENT value.

    The config loader only accepts ``development|test|staging|production`` and
    selects ``config/{environment}.yaml`` from it, so the CDK name (``dev``)
    must not be passed through verbatim (issue #276).
    """
    environment = load_env_config(env_name).get('environment')
    if not isinstance(environment, str) or not environment:
        raise ValueError(f'Environment {env_name!r} is missing an "environment" value')
    return environment


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
        api_gateway: object = None,
        lambda_zip: str | None = None,
        gateway_zip: str | None = None,
        step_functions: object = None,
        workflow: object = None,
        workflows: object = None,
        state_machine: object = None,
        observability: object = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.observability = observability

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

        # Observability environment (issue #276): OTLP export to the
        # CloudWatch Logs OTLP endpoint, plus the application environment the
        # config loader validates. The endpoint is the AWS-documented pattern
        # (https://logs.{region}.amazonaws.com/v1/logs) with the region taken
        # from the stack, so no account or region is hard-coded (ADR-0002).
        # ``AWS_REGION`` is intentionally *not* declared here: the Lambda
        # runtime reserves and injects it automatically, so it is already
        # present at runtime.
        environment: dict[str, str] = {
            'OTLP_ENDPOINT': f'https://logs.{self.region}.amazonaws.com/v1/logs',
            'ENVIRONMENT': _app_environment(env_name),
        }

        # OTLP routing headers (issue #287): CloudWatch Logs OTLP ingestion
        # requires ``x-aws-logs-group`` and ``x-aws-logs-stream`` naming the
        # destination Observability log group and stream. Wired from the
        # cross-stack observability construct; serialized as JSON so the
        # runtime can rebuild the header map from config without reading env
        # directly (adapters never read os.environ).
        observability_headers: dict[str, str] = {}
        if observability is not None:
            routing = getattr(observability, 'otlp_routing_headers', None)
            if callable(routing):
                observability_headers = routing()
        if observability_headers:
            environment['OTLP_HEADERS'] = json.dumps(observability_headers)

        lambda_kwargs['environment'] = environment

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

        # Model-gateway function (issue #330): only for prod where
        # llm_transport=remote_gateway. The gateway runs behind the AWS Lambda
        # Web Adapter with handler=run.sh and response_stream invoke mode for
        # NDJSON streaming of litellm chunks.
        self.gateway_fn = None
        if env_name == 'prod':
            self.gateway_fn = self._create_gateway_function(
                env_name, gateway_zip, vpc, observability
            )
            # Grant the API function permission to invoke the gateway
            self.gateway_fn.grant_invoke(self.api_fn)
            # Expose the gateway function URL to the API function via env
            gateway_url = self.gateway_fn.add_function_url(
                auth_type=lambda_.FunctionUrlAuthType.AWS_IAM,
                invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM,
            )
            self.api_fn.add_environment('MODEL_GATEWAY_URL', gateway_url.url)

        # Scoped permissions for Aurora, DynamoDB, S3, queues, and workflows.
        self._grant_scoped_permissions(
            role, data, messaging, auth, step_functions, workflow, workflows, state_machine
        )

        # Observability: allow the runtime to put structured span records on
        # the Observability log group (issue #276).
        self._grant_observability_permissions(role)

        # HTTP API from ApiGatewayStack with Cognito authorization.
        http_api = getattr(api_gateway, 'http_api', None) if api_gateway is not None else None
        if http_api is None:
            raise ValueError('ApiGatewayStack must be provided to ComputeStack')

        self.http_api = http_api
        self.api = http_api
        self.api_gateway = http_api

        user_pool = getattr(auth, 'user_pool', None) if auth is not None else None
        if user_pool is None:
            raise ValueError('AuthStack with user_pool must be provided to ComputeStack')

        # Create JWT authorizer for HTTP API
        # Cognito issuer URL format: https://cognito-idp.{region}.amazonaws.com/{user_pool_id}
        issuer_url = f'https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}'
        user_pool_client = getattr(auth, 'user_pool_client', None)
        if user_pool_client is None:
            raise ValueError('AuthStack with user_pool_client must be provided to ComputeStack')
        audience = [user_pool_client.user_pool_client_id]

        self.jwt_authorizer = apigatewayv2_auth.HttpJwtAuthorizer(
            f'JwtAuthorizer{env_name}',
            jwt_issuer=issuer_url,
            jwt_audience=audience,
            authorizer_name=f'finsight-{env_name}-jwt-authorizer',
            identity_source=['$request.header.Authorization'],
        )

        # Create Lambda integration
        lambda_integration = integrations.HttpLambdaIntegration(
            f'ApiLambdaIntegration{env_name}',
            self.api_fn,
        )

        # Add routes with JWT authorizer
        self._add_http_api_routes(lambda_integration, self.jwt_authorizer)

    def _add_http_api_routes(
        self,
        integration: integrations.HttpLambdaIntegration,
        authorizer: apigatewayv2_auth.HttpJwtAuthorizer,
    ) -> None:
        """Add standard routes to the HTTP API."""
        self.http_api.add_routes(
            path='/{proxy+}',
            methods=[apigatewayv2.HttpMethod.ANY],
            integration=integration,
            authorizer=authorizer,
        )
        self.http_api.add_routes(
            path='/',
            methods=[apigatewayv2.HttpMethod.ANY],
            integration=integration,
            authorizer=authorizer,
        )

    def _grant_observability_permissions(self, role: object) -> None:
        """Grant the runtime role write access to the Observability log group."""

        log_group = getattr(self.observability, 'log_group', None) if self.observability else None
        if log_group is not None and hasattr(log_group, 'grant_write'):
            # grant_write = logs:CreateLogStream + logs:PutLogEvents on this
            # log group only (scoped to the Observability group).
            log_group.grant_write(role)

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

    def _create_gateway_function(
        self,
        env_name: str,
        gateway_zip: str | None,
        vpc: object | None,
        observability: object | None,
    ) -> lambda_.Function:
        """Create the model-gateway Lambda function (issue #330).

        The gateway runs behind the AWS Lambda Web Adapter layer. Key settings:
        - Handler: 'run.sh' (the startup script included in gateway.zip)
        - Layer: LambdaAdapterLayerX86 (public layer, us-east-1)
        - Runtime: Python 3.12 (the adapter boots uvicorn from run.sh)
        - Memory: 512 MB (enough for litellm + uvicorn)
        - Env: MODEL_GATEWAY_MASTER_KEY from SSM, plus OTLP/ENVIRONMENT
        """
        # Web Adapter layer ARN for x86_64 in us-east-1 (pinned to v30)
        adapter_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            f'LambdaWebAdapterLayer{env_name}',
            f'arn:aws:lambda:{self.region}:753240598075:layer:LambdaAdapterLayerX86:30',
        )

        gateway_code = (
            lambda_.Code.from_asset(gateway_zip)
            if gateway_zip
            else lambda_.Code.from_inline(PLACEHOLDER_CODE)
        )
        gateway_role = iam.Role(
            self,
            f'GatewayLambdaExecutionRole{env_name}',
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

        # SSM parameter for the shared master key (SecureString)
        master_key = f'{{{{resolve:ssmsecure:/finsight/{env_name}/model_gateway_master_key}}}}'

        gateway_environment: dict[str, str] = {
            'OTLP_ENDPOINT': f'https://logs.{self.region}.amazonaws.com/v1/logs',
            'ENVIRONMENT': _app_environment(env_name),
            'MODEL_GATEWAY_MASTER_KEY': master_key,
            'AWS_LAMBDA_EXEC_WRAPPER': '/opt/bootstrap',
            'AWS_LWA_INVOKE_MODE': 'response_stream',
            'PORT': '8080',
        }

        observability_headers: dict[str, str] = {}
        if observability is not None:
            routing = getattr(observability, 'otlp_routing_headers', None)
            if callable(routing):
                observability_headers = routing()
        if observability_headers:
            gateway_environment['OTLP_HEADERS'] = json.dumps(observability_headers)

        gateway_kwargs: dict[str, object] = {'layers': [adapter_layer]}
        if vpc is not None:
            gateway_kwargs['vpc'] = vpc

        return lambda_.Function(
            self,
            f'GatewayFunction{env_name}',
            function_name=f'finsight-{env_name}-gateway',
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler='run.sh',
            code=gateway_code,
            role=gateway_role,
            memory_size=512,
            environment=gateway_environment,
            **gateway_kwargs,
        )
