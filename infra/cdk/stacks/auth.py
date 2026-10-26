from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = cognito.UserPool(
            self,
            f'UserPool{env_name}',
            user_pool_name=f'finsight-{env_name}-users',
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            removal_policy=RemovalPolicy.RETAIN if env_name == 'prod' else RemovalPolicy.DESTROY,
        )
        self.user_pool_client = self.user_pool.add_client(
            f'UserPoolClient{env_name}',
            user_pool_client_name=f'finsight-{env_name}-client',
            auth_flows=cognito.AuthFlow(user_srp=True),
        )
