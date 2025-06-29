from aws_cdk import (
    aws_ec2 as ec2,
)
from constructs import Construct
from cdk_nag import NagSuppressions


class VpcConstruct(Construct):
    vpc: ec2.Vpc

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            cheap_vpc: bool,
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if cheap_vpc:
            natInstance = ec2.NatProvider.instance_v2(
                instance_type=ec2.InstanceType("t4g.nano"),
                default_allowed_traffic=ec2.NatTrafficDirection.OUTBOUND_ONLY,
            )

        vpc = ec2.Vpc(
            scope, "CustomVPC",
            max_azs=3,  # Define the maximum number of Availability Zones
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ],
            nat_gateway_provider=natInstance if cheap_vpc else None,
            gateway_endpoints={
                # ECR Image Layer
                "S3": ec2.GatewayVpcEndpointOptions(
                    service=ec2.GatewayVpcEndpointAwsService.S3
                )
            }
        )

        if cheap_vpc:
            natInstance.security_group.add_ingress_rule(
                ec2.Peer.ipv4(vpc.vpc_cidr_block),
                ec2.Port.all_traffic(),
                "Allow NAT Traffic from inside VPC",
            )

        # Enable VPC Flow Logs
        flow_log = ec2.FlowLog(
            scope,
            "FlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(),
        )

        # Nag

        NagSuppressions.add_resource_suppressions(
            [vpc],
            suppressions=[
                {"id": "AwsSolutions-EC28",
                 "reason": "NAT Instance does not require autoscaling."
                 },
                {"id": "AwsSolutions-EC29",
                 "reason": "NAT Instance does not require autoscaling."
                 },
            ],
            apply_to_children=True
        )

        # Output

        self.vpc = vpc
