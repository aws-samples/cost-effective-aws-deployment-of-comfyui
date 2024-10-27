import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";

import * as autoscaling from "aws-cdk-lib/aws-autoscaling";
import * as iam from "aws-cdk-lib/aws-iam";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as cw_actions from "aws-cdk-lib/aws-cloudwatch-actions";
import { Construct } from "constructs";
import { NagSuppressions } from "cdk-nag";

interface AsgConstructProps {
  vpc: ec2.Vpc;
  useSpot: boolean;
  spotPrice?: string;
  autoScaleDown: boolean;
  scheduleAutoScaling: boolean;
  timezone: string;
  scheduleScaleDown: string;
  scheduleScaleUp: string;
}

export class AsgConstruct extends Construct {
  public readonly autoScalingGroup: autoscaling.AutoScalingGroup;

  constructor(scope: Construct, id: string, props: AsgConstructProps) {
    super(scope, id);

    const {
      vpc,
      useSpot,
      spotPrice,
      autoScaleDown,
      scheduleAutoScaling,
      timezone,
      scheduleScaleDown,
      scheduleScaleUp,
    } = props;

    const asgSecurityGroup = new ec2.SecurityGroup(this, "AsgSecurityGroup", {
      vpc,
      description: "Security Group for ASG",
      allowAllOutbound: true,
    });

    const ec2Role = new iam.Role(this, "EC2Role", {
      assumedBy: new iam.ServicePrincipal("ec2.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonEC2FullAccess"),
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "AmazonSSMManagedEC2InstanceDefaultPolicy"
        ),
      ],
    });

    const userData = ec2.UserData.forLinux();
    userData.addCommands(`
      #!/bin/bash
      REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
      docker plugin install rexray/ebs --grant-all-permissions REXRAY_PREEMPT=true EBS_REGION=$REGION
      systemctl restart docker
    `);

    const launchTemplate = new ec2.LaunchTemplate(this, "Host", {
      machineImage: ecs.EcsOptimizedImage.amazonLinux2(ecs.AmiHardwareType.GPU),
      role: ec2Role,
      securityGroup: asgSecurityGroup,
      userData,
      blockDevices: [
        {
          deviceName: "/dev/xvda",
          volume: ec2.BlockDeviceVolume.ebs(50, {
            encrypted: true,
          }),
        },
      ],
    });

    const autoScalingGroup = new autoscaling.AutoScalingGroup(this, "ASG", {
      vpc,
      mixedInstancesPolicy: {
        instancesDistribution: {
          onDemandBaseCapacity: 0,
          onDemandPercentageAboveBaseCapacity: useSpot ? 0 : 100,
          onDemandAllocationStrategy:
            autoscaling.OnDemandAllocationStrategy.LOWEST_PRICE,
          spotAllocationStrategy:
            autoscaling.SpotAllocationStrategy.LOWEST_PRICE,
          spotInstancePools: 1,
          spotMaxPrice: spotPrice,
        },
        launchTemplate,
        launchTemplateOverrides: [
          { instanceType: new ec2.InstanceType("g4dn.xlarge") },
          { instanceType: new ec2.InstanceType("g5.xlarge") },
          { instanceType: new ec2.InstanceType("g6.xlarge") },
          { instanceType: new ec2.InstanceType("g4dn.2xlarge") },
          { instanceType: new ec2.InstanceType("g5.2xlarge") },
          { instanceType: new ec2.InstanceType("g6.2xlarge") },
        ],
      },
      minCapacity: 0,
      maxCapacity: 1,
      desiredCapacity: 1,
      newInstancesProtectedFromScaleIn: false,
    });

    autoScalingGroup.applyRemovalPolicy(cdk.RemovalPolicy.DESTROY);

    const cpuUtilizationMetric = new cloudwatch.Metric({
      namespace: "AWS/EC2",
      metricName: "CPUUtilization",
      dimensionsMap: {
        AutoScalingGroupName: autoScalingGroup.autoScalingGroupName,
      },
      statistic: "Average",
      period: cdk.Duration.minutes(1),
    });

    if (autoScaleDown) {
      const cpuAlarm = new cloudwatch.Alarm(this, "CPUUtilizationAlarm", {
        metric: cpuUtilizationMetric,
        threshold: 1,
        evaluationPeriods: 60,
        datapointsToAlarm: 60,
        comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
      });

      const scalingAction = new autoscaling.StepScalingAction(
        this,
        "ScalingAction",
        {
          autoScalingGroup,
          adjustmentType: autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
          //   cooldown: cdk.Duration.seconds(120),
        }
      );

      scalingAction.addAdjustment({
        adjustment: -1,
        upperBound: 1,
      });

      scalingAction.addAdjustment({
        adjustment: 0,
        lowerBound: 1,
      });

      cpuAlarm.addAlarmAction(new cw_actions.AutoScalingAction(scalingAction));
    }

    if (scheduleAutoScaling) {
      new autoscaling.ScheduledAction(this, "AfterWorkHoursAction", {
        autoScalingGroup,
        desiredCapacity: 0,
        timeZone: timezone,
        schedule: autoscaling.Schedule.expression(scheduleScaleDown),
      });

      new autoscaling.ScheduledAction(this, "StartWorkHoursAction", {
        autoScalingGroup,
        desiredCapacity: 1,
        timeZone: timezone,
        schedule: autoscaling.Schedule.expression(scheduleScaleUp),
      });
    }

    // Nag

    NagSuppressions.addResourceSuppressions(
      [autoScalingGroup],
      [
        {
          id: "AwsSolutions-L1",
          reason:
            "Lambda Runtime is provided by custom resource provider and drain ecs hook implicitely and not critical for sample",
        },
        {
          id: "AwsSolutions-AS3",
          reason: "Not all notifications are critical for ComfyUI sample",
        },
      ],
      true
    );

    // Output

    this.autoScalingGroup = autoScalingGroup;
  }
}
