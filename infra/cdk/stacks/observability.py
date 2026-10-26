from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_logs as logs
from constructs import Construct


class ObservabilityStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.log_group = logs.LogGroup(
            self,
            f'AppLogGroup{env_name}',
            log_group_name=f'/aws/lambda/finsight-{env_name}',
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY if env_name != 'prod' else RemovalPolicy.RETAIN,
        )
