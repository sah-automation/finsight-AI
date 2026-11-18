"""Network stack, retained only for the ``aurora_pgvector`` standard path."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from stacks.env_config import uses_aurora_vpc

if TYPE_CHECKING:
    from collections.abc import Mapping


class NetworkStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        env_config: Mapping[str, Any] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The pilot has no VPC to attach Lambdas to or to route through a NAT
        # gateway, so the stack synthesizes no resources at all for it.
        self.vpc: ec2.Vpc | None = None
        if not uses_aurora_vpc(env_name, env_config):
            return

        self.vpc = ec2.Vpc(
            self,
            f'Vpc{env_name}',
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name='Public', subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name='Private', subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name='Isolated', subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24
                ),
            ],
        )
