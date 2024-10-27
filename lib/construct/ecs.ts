import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecr_assets from "aws-cdk-lib/aws-ecr-assets";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as autoscaling from "aws-cdk-lib/aws-autoscaling";
import { Construct } from "constructs";
import { NagSuppressions } from "cdk-nag";

interface EcsConstructProps {
  vpc: ec2.Vpc;
  autoScalingGroup: autoscaling.AutoScalingGroup;
  albSecurityGroup: ec2.SecurityGroup;
  isSagemakerStudio: boolean;
  suffix: string;
}

export class EcsConstruct extends Construct {
  public readonly cluster: ecs.Cluster;
  public readonly service: ecs.Ec2Service;
  public readonly ecsTargetGroup: elbv2.ApplicationTargetGroup;

  constructor(scope: Construct, id: string, props: EcsConstructProps) {
    super(scope, id);

    const {
      vpc,
      autoScalingGroup,
      albSecurityGroup,
      isSagemakerStudio,
      suffix,
    } = props;

    // Cluster

    const cluster = new ecs.Cluster(this, "ComfyUICluster", {
      vpc,
      containerInsights: true,
    });

    const capacityProvider = new ecs.AsgCapacityProvider(
      this,
      "AsgCapacityProvider",
      {
        autoScalingGroup,
        enableManagedScaling: false,
        enableManagedTerminationProtection: false,
        targetCapacityPercent: 100,
      }
    );

    cluster.addAsgCapacityProvider(capacityProvider);

    // Task

    const taskExecRole = new iam.Role(this, "ECSTaskExecutionRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AmazonECSTaskExecutionRolePolicy"
        ),
      ],
    });

    const dockerImageAsset = new ecr_assets.DockerImageAsset(
      this,
      "ComfyUIImage",
      {
        directory: "./docker",
        platform: ecr_assets.Platform.LINUX_AMD64,
        networkMode: isSagemakerStudio
          ? ecr_assets.NetworkMode.custom("sagemaker")
          : undefined,
      }
    );

    const logGroup = new logs.LogGroup(this, "LogGroup", {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const volume: ecs.Volume = {
      name: `ComfyUIVolume-${suffix}`,
      dockerVolumeConfiguration: {
        scope: ecs.Scope.SHARED,
        driver: "rexray/ebs",
        driverOpts: {
          volumetype: "gp3",
          size: "250",
        },
        autoprovision: true,
      },
    };

    const taskDefinition = new ecs.Ec2TaskDefinition(this, "TaskDef", {
      networkMode: ecs.NetworkMode.AWS_VPC,
      taskRole: taskExecRole,
      executionRole: taskExecRole,
      volumes: [volume],
    });

    const container = taskDefinition.addContainer("ComfyUIContainer", {
      image: ecs.ContainerImage.fromEcrRepository(
        dockerImageAsset.repository,
        dockerImageAsset.imageTag
      ),
      gpuCount: 1,
      memoryReservationMiB: 15000,
      logging: ecs.LogDriver.awsLogs({
        streamPrefix: "comfy-ui",
        logGroup,
      }),
      healthCheck: {
        command: [
          "CMD-SHELL",
          "curl -f http://localhost:8181/system_stats || exit 1",
        ],
        interval: cdk.Duration.seconds(15),
        timeout: cdk.Duration.seconds(10),
        retries: 8,
        startPeriod: cdk.Duration.seconds(30),
      },
    });

    container.addMountPoints({
      containerPath: "/home/user/opt/ComfyUI",
      sourceVolume: volume.name,
      readOnly: false,
    });

    container.addPortMappings({
      containerPort: 8181,
      hostPort: 8181,
      appProtocol: ecs.AppProtocol.http,
      name: "comfyui-port-mapping",
      protocol: ecs.Protocol.TCP,
    });

    // Service

    const serviceSecurityGroup = new ec2.SecurityGroup(
      this,
      "ServiceSecurityGroup",
      {
        vpc,
        description: "Security Group for ECS Service",
        allowAllOutbound: true,
      }
    );

    serviceSecurityGroup.addIngressRule(
      ec2.Peer.securityGroupId(albSecurityGroup.securityGroupId),
      ec2.Port.tcp(8181),
      "Allow inbound traffic on port 8181"
    );

    const service = new ecs.Ec2Service(this, "ComfyUIService", {
      cluster: cluster,
      taskDefinition,
      capacityProviderStrategies: [
        {
          capacityProvider: capacityProvider.capacityProviderName,
          weight: 1,
        },
      ],
      securityGroups: [serviceSecurityGroup],
      healthCheckGracePeriod: cdk.Duration.seconds(30),
      minHealthyPercent: 0,
    });

    // Create Target Group

    const ecsTargetGroup = new elbv2.ApplicationTargetGroup(
      this,
      "EcsTargetGroup",
      {
        port: 8181,
        vpc,
        protocol: elbv2.ApplicationProtocol.HTTP,
        targetType: elbv2.TargetType.IP,
        targets: [
          service.loadBalancerTarget({
            containerName: container.containerName,
            containerPort: 8181,
          }),
        ],
        healthCheck: {
          enabled: true,
          path: "/system_stats",
          port: "8181",
          protocol: elbv2.Protocol.HTTP,
          healthyHttpCodes: "200", // Adjust as needed
          interval: cdk.Duration.seconds(30),
          timeout: cdk.Duration.seconds(5),
          unhealthyThresholdCount: 3,
          healthyThresholdCount: 2,
        },
      }
    );

    // Nag

    NagSuppressions.addResourceSuppressions(
      [taskDefinition],
      [
        {
          id: "AwsSolutions-ECS2",
          reason:
            "Recent aws-cdk-lib version adds 'AWS_REGION' environment variable implicitly.",
        },
      ],
      true
    );

    // Output

    this.cluster = cluster;
    this.service = service;
    this.ecsTargetGroup = ecsTargetGroup;
  }
}
