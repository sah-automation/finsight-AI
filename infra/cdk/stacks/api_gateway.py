"""CDK stack: API Gateway HTTP API with custom domain, throttling, and access logging.

This stack creates an HTTP API with a custom domain name, API throttling from
config, and CloudWatch access logging with configurable retention. WAF integration
is gated by the ``waf_enabled`` switch (off for pilot per ADR-0005).
"""

from __future__ import annotations

from typing import Any

from aws_cdk import CfnOutput, Fn, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigatewayv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct

from stacks.env_config import load_env_config

__all__ = ['ApiGatewayStack']

# Constants for validation
_RETENTION_THRESHOLD_DAYS = 30
_DEFAULT_WAF_RATE_LIMIT = 1000
_REQUIRED_API_GATEWAY_KEYS = (
    'custom_domain',
    'acm_certificate_arn',
    'throttling',
    'access_logging',
    'waf_enabled',
)
_LOG_GROUP_NAME_PREFIX = '/aws/apigateway/finsight-'
_LOG_GROUP_NAME_SUFFIX = '-api/access'
_CERT_IMPORT_COMMENT = (
    'Import the ACM certificate from us-east-1 (required for CloudFront/API Gateway custom domains)'
)


def _validate_positive_number(value: object, env_name: str, key_path: str) -> int:
    """Validate that value is a positive number and return as int."""
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(
            f'Environment {env_name!r} {key_path} must be a positive number, got {value!r}'
        )
    return int(value)


def _load_api_gateway_config(env_name: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load and validate API Gateway configuration for an environment.

    The ``config`` parameter can be injected for testing; otherwise it is
    loaded from the environment config file.
    """
    env_config = load_env_config(env_name) if config is None else dict(config)
    if 'api_gateway' not in env_config:
        raise ValueError(f'Environment {env_name!r} is missing an api_gateway section')
    api_config = env_config['api_gateway']
    if not isinstance(api_config, dict):
        raise TypeError(f'Environment {env_name!r} api_gateway section must be a mapping')

    # Check required keys
    for key in _REQUIRED_API_GATEWAY_KEYS:
        if key not in api_config:
            raise ValueError(f'Environment {env_name!r} api_gateway missing required key: {key}')

    # Validate throttling config
    throttling = api_config['throttling']
    if not isinstance(throttling, dict):
        raise TypeError(f'Environment {env_name!r} api_gateway.throttling must be a mapping')
    for key in ('rate_limit', 'burst_limit'):
        if key not in throttling:
            raise ValueError(
                f'Environment {env_name!r} api_gateway.throttling missing required key: {key}'
            )
        _validate_positive_number(throttling[key], env_name, f'api_gateway.throttling.{key}')

    # Validate access logging config
    access_logging = api_config['access_logging']
    if not isinstance(access_logging, dict):
        raise TypeError(f'Environment {env_name!r} api_gateway.access_logging must be a mapping')
    if 'retention_days' not in access_logging:
        raise ValueError(
            f'Environment {env_name!r} api_gateway.access_logging missing retention_days'
        )
    _validate_positive_number(
        access_logging['retention_days'], env_name, 'api_gateway.access_logging.retention_days'
    )

    # Validate waf_enabled
    waf_enabled = api_config['waf_enabled']
    if not isinstance(waf_enabled, bool):
        raise TypeError(f'Environment {env_name!r} api_gateway.waf_enabled must be a boolean')

    # Validate/normalize waf_rate_limit
    if 'waf_rate_limit' in api_config:
        api_config['waf_rate_limit'] = _validate_positive_number(
            api_config['waf_rate_limit'], env_name, 'api_gateway.waf_rate_limit'
        )
    else:
        api_config['waf_rate_limit'] = _DEFAULT_WAF_RATE_LIMIT

    return api_config


class ApiGatewayStack(Stack):
    """HTTP API with custom domain, throttling, access logging, and optional WAF."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        *,
        env_config: dict[str, Any] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        config = env_config if env_config is not None else load_env_config(env_name)
        api_config = _load_api_gateway_config(env_name, config=config)

        custom_domain = api_config['custom_domain']
        acm_certificate_arn = api_config['acm_certificate_arn']
        rate_limit = int(api_config['throttling']['rate_limit'])
        burst_limit = int(api_config['throttling']['burst_limit'])
        retention_days = int(api_config['access_logging']['retention_days'])
        waf_enabled = api_config['waf_enabled']
        waf_rate_limit = int(api_config['waf_rate_limit'])

        # Removal policy from config
        removal_policy_name = str(config['removal_policy']).lower()
        removal_policy = (
            RemovalPolicy.RETAIN if removal_policy_name == 'retain' else RemovalPolicy.DESTROY
        )

        # Create the HTTP API.
        self.http_api = apigatewayv2.HttpApi(
            self,
            f'HttpApi{env_name}',
            api_name=f'finsight-{env_name}-api',
            description=f'FinSight {env_name} HTTP API',
            default_domain_mapping=None,  # We'll add custom domain mapping separately
        )

        # Configure the default stage with throttling and access logging.
        # HTTP API stages expose throttling via DefaultRouteSettings
        # (ThrottlingRateLimit/ThrottlingBurstLimit); the REST-API-only
        # ``ThrottleSettings`` property name is rejected by CloudFormation.
        default_stage = self.http_api.default_stage
        if default_stage is not None:
            cfn_stage = default_stage.node.default_child
            cfn_stage.add_property_override(
                'DefaultRouteSettings',
                {
                    'ThrottlingRateLimit': rate_limit,
                    'ThrottlingBurstLimit': burst_limit,
                },
            )

            # Create access log group for API Gateway
            log_group_name = f'{_LOG_GROUP_NAME_PREFIX}{env_name}{_LOG_GROUP_NAME_SUFFIX}'
            self.access_log_group = logs.LogGroup(
                self,
                f'ApiAccessLogGroup{env_name}',
                log_group_name=log_group_name,
                retention=(
                    logs.RetentionDays.ONE_MONTH
                    if retention_days >= _RETENTION_THRESHOLD_DAYS
                    else logs.RetentionDays.ONE_WEEK
                ),
                removal_policy=removal_policy,
            )

            # Enable access logging on the stage
            cfn_stage.add_property_override(
                'AccessLogSettings',
                {
                    'DestinationArn': self.access_log_group.log_group_arn,
                    'Format': (
                        '$context.requestId $context.identity.sourceIp $context.requestTime '
                        '$context.httpMethod $context.routeKey $context.protocol $context.status '
                        '$context.responseLength $context.responseLatency'
                    ),
                },
            )
        else:
            # Fallback if no default stage (should not happen with HttpApi)
            log_group_name = f'{_LOG_GROUP_NAME_PREFIX}{env_name}{_LOG_GROUP_NAME_SUFFIX}'
            self.access_log_group = logs.LogGroup(
                self,
                f'ApiAccessLogGroup{env_name}',
                log_group_name=log_group_name,
                retention=(
                    logs.RetentionDays.ONE_MONTH
                    if retention_days >= _RETENTION_THRESHOLD_DAYS
                    else logs.RetentionDays.ONE_WEEK
                ),
                removal_policy=removal_policy,
            )

        # Custom domain mapping - only if ACM certificate ARN is provided
        self.domain_mapping = None
        self.certificate = None

        if acm_certificate_arn and acm_certificate_arn.strip():
            # _CERT_IMPORT_COMMENT
            self.certificate = acm.Certificate.from_certificate_arn(
                self,
                f'ApiCertificate{env_name}',
                certificate_arn=acm_certificate_arn,
            )

            # Create the domain name resource
            domain_name = apigatewayv2.DomainName(
                self,
                f'ApiDomainName{env_name}',
                domain_name=custom_domain,
                certificate=self.certificate,
            )

            # Map the domain name to the HTTP API
            if default_stage is not None:
                self.domain_mapping = apigatewayv2.ApiMapping(
                    self,
                    f'ApiMapping{env_name}',
                    api=self.http_api,
                    domain_name=domain_name,
                    stage=default_stage,
                )

            # Note: Route53 record creation is typically handled outside this stack
            # or requires a hosted zone reference. The domain name is ready for
            # manual or external Route53 configuration.

        # WAF integration (gated by waf_enabled switch)
        self.web_acl = None
        self.web_acl_association = None

        if waf_enabled:
            # Create a basic WAF Web ACL with AWS Managed Rules
            self.web_acl = wafv2.CfnWebACL(
                self,
                f'ApiWebAcl{env_name}',
                name=f'finsight-{env_name}-api-waf',
                scope='REGIONAL',
                default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
                visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                    sampled_requests_enabled=True,
                    cloud_watch_metrics_enabled=True,
                    metric_name=f'finsight-{env_name}-api-waf',
                ),
                rules=[
                    # AWS Managed Rules - Core Rule Set
                    wafv2.CfnWebACL.RuleProperty(
                        name='AWSManagedRulesCommonRuleSet',
                        priority=1,
                        override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                        statement=wafv2.CfnWebACL.StatementProperty(
                            managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                                vendor_name='AWS',
                                name='AWSManagedRulesCommonRuleSet',
                            )
                        ),
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            sampled_requests_enabled=True,
                            cloud_watch_metrics_enabled=True,
                            metric_name='CommonRuleSet',
                        ),
                    ),
                    # AWS Managed Rules - Known Bad Inputs
                    wafv2.CfnWebACL.RuleProperty(
                        name='AWSManagedRulesKnownBadInputsRuleSet',
                        priority=2,
                        override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                        statement=wafv2.CfnWebACL.StatementProperty(
                            managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                                vendor_name='AWS',
                                name='AWSManagedRulesKnownBadInputsRuleSet',
                            )
                        ),
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            sampled_requests_enabled=True,
                            cloud_watch_metrics_enabled=True,
                            metric_name='KnownBadInputsRuleSet',
                        ),
                    ),
                    # Rate-based rule (optional, can be tuned)
                    wafv2.CfnWebACL.RuleProperty(
                        name='RateLimitRule',
                        priority=3,
                        action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                        statement=wafv2.CfnWebACL.StatementProperty(
                            rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                                limit=waf_rate_limit,
                                aggregate_key_type='IP',
                            )
                        ),
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            sampled_requests_enabled=True,
                            cloud_watch_metrics_enabled=True,
                            metric_name='RateLimitRule',
                        ),
                    ),
                ],
            )

            # Associate WAF Web ACL with the API Gateway stage
            if default_stage is not None:
                # ARN: arn:aws:apigateway:{region}::/apis/{api_id}/stages/{stage_name}
                stage_arn = Fn.sub(
                    r'arn:aws:apigateway:${AWS::Region}::/apis/${ApiId}/stages/${StageName}',
                    {
                        'ApiId': self.http_api.http_api_id,
                        'StageName': default_stage.stage_name,
                    },
                )
                self.web_acl_association = wafv2.CfnWebACLAssociation(
                    self,
                    f'ApiWebAclAssociation{env_name}',
                    resource_arn=stage_arn,
                    web_acl_arn=self.web_acl.attr_arn,
                )

        # Outputs for cross-stack references
        self.http_api_id = self.http_api.http_api_id
        self.http_api_url = self.http_api.api_endpoint
        self.access_log_group_arn = self.access_log_group.log_group_arn
        self.access_log_group_name = self.access_log_group.log_group_name
        # The deploy workflow captures the custom domain from this output
        # (``aws cloudformation describe-stacks ... CustomDomainName``).
        cfn_output = CfnOutput(
            self,
            f'CustomDomainName{env_name}',
            value=custom_domain if self.domain_mapping is not None else self.http_api_url,
            description='HTTPS entry point for the deployed API',
        )
        del cfn_output
        if self.domain_mapping is not None:
            self.custom_domain_name = custom_domain
        if self.web_acl is not None:
            self.web_acl_arn = self.web_acl.attr_arn

    def add_route_integration(
        self,
        route_key: str,
        integration: integrations.HttpIntegration,
        *,
        authorizer: apigatewayv2.HttpAuthorizer | None = None,
    ) -> apigatewayv2.HttpRoute:
        """Add a route with integration to the HTTP API."""
        return self.http_api.add_routes(
            path=route_key.split(' ', 1)[-1] if ' ' in route_key else route_key,
            methods=[apigatewayv2.HttpMethod.ANY]
            if ' ' not in route_key
            else [apigatewayv2.HttpMethod[route_key.split(' ', maxsplit=1)[0]]],
            integration=integration,
            authorizer=authorizer,
        )[0]

    def grant_invoke(self, role: iam.IRole) -> None:
        """Grant invoke permissions on the HTTP API to a role."""
        role.add_to_policy(
            iam.PolicyStatement(
                actions=['execute-api:Invoke'],
                resources=[f'{self.http_api_id}/*/*'],
            )
        )
