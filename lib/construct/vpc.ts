import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

export interface VpcProps {
  cheapVpc: boolean;
}

export class VpcConstruct extends Construct {
  public readonly vpc: ec2.Vpc;

  constructor(scope: Construct, id: string, props: VpcProps) {
    super(scope, id);

    let natInstance: ec2.NatInstanceProviderV2 | undefined;
    if (props.cheapVpc) {
      natInstance = ec2.NatProvider.instanceV2({
        instanceType: new ec2.InstanceType('t4g.nano'),
        defaultAllowedTraffic: ec2.NatTrafficDirection.OUTBOUND_ONLY,
      });
    }

    const vpc = new ec2.Vpc(this, 'CustomVPC', {
      maxAzs: 2,
      subnetConfiguration: [
        {
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
      ],
      natGatewayProvider: props.cheapVpc ? natInstance : undefined,
      gatewayEndpoints: {
        S3: {
          service: ec2.GatewayVpcEndpointAwsService.S3,
        },
      },
    });

    if (props.cheapVpc && natInstance) {
      natInstance.connections.allowFrom(
        ec2.Peer.ipv4(vpc.vpcCidrBlock),
        ec2.Port.allTraffic(),
        'Allow NAT Traffic from inside VPC'
      );
    }

    new ec2.FlowLog(this, "FlowLog", {
      resourceType: ec2.FlowLogResourceType.fromVpc(vpc),
      destination: ec2.FlowLogDestination.toCloudWatchLogs(),
    });

    // Nag

    NagSuppressions.addResourceSuppressions(
      [vpc],
      [
        {
          id: "AwsSolutions-EC28",
          reason: "NAT Instance does not require autoscaling.",
        },
        {
          id: "AwsSolutions-EC29",
          reason: "NAT Instance does not require autoscaling.",
        },
      ],
      true
    );

    // Output
    this.vpc = vpc;
  }
}
