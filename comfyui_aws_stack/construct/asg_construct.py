from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_autoscaling as autoscaling,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from cdk_nag import NagSuppressions
from typing import Optional

class AsgConstruct(Construct):
    auto_scaling_group: autoscaling.AutoScalingGroup

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            vpc: ec2.Vpc,
            use_spot: bool,
            spot_price: str,
            auto_scale_down: bool,
            schedule_auto_scaling: bool,
            timezone: str,
            schedule_scale_down: str,
            schedule_scale_up: str,
            desired_capacity: Optional[int] = None,  # ★ これを明示的に追加
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.desired_capacity = desired_capacity  # ★ 自分で保持。必要に応じて .desired_capacity を内部で使いながら、AutoScalingGroup の min_capacity / max_capacity などに反映するのが正しい使い方です。

        # Create Auto Scaling Group Security Group
        asg_security_group = ec2.SecurityGroup(
            scope,
            "AsgSecurityGroup",
            vpc=vpc,
            description="Security Group for ASG",
            allow_all_outbound=True,
        )

        # EC2 Role for AWS internal use (if necessary)
        ec2_role = iam.Role(
            scope,
            "EC2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedEC2InstanceDefaultPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonEC2ContainerServiceforEC2Role")
            ],
            inline_policies={
                "EbsManagementPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "ec2:CreateVolume",
                                "ec2:AttachVolume",
                                "ec2:DetachVolume",
                                "ec2:DeleteVolume",
                                "ec2:CreateTags",
                                "ec2:DescribeVolumes",
                                "ec2:DescribeInstances"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        user_data_script = ec2.UserData.for_linux()
        user_data_script.add_commands("""
            #!/bin/bash
            REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region) 
            docker plugin install public.ecr.aws/j1l5j1d1/rexray-ebs --grant-all-permissions REXRAY_PREEMPT=true EBS_REGION=$REGION
            systemctl restart docker
        """)

        # Create an Auto Scaling Group with two EBS volumes
        launchTemplate = ec2.LaunchTemplate(
            scope,
            "Host",
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(
                hardware_type=ecs.AmiHardwareType.GPU
            ),
            key_pair=ec2.KeyPair.from_key_pair_name(scope, "KeyPair", "comfyui-ssh-key"),
            role=ec2_role,
            security_group=asg_security_group,
            user_data=user_data_script,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(volume_size=50,
                                                     encrypted=True)
                )
            ],
        )
        auto_scaling_group = autoscaling.AutoScalingGroup(
            scope,
            "ASG",
            vpc=vpc,
            # Use Mixed Instance Policy to increase availability in case capacity is not available.
            mixed_instances_policy=autoscaling.MixedInstancesPolicy(
                instances_distribution=autoscaling.InstancesDistribution(
                    on_demand_base_capacity=1, #スポット確保が失敗した場合はオンデマンドで1台確保
                    on_demand_percentage_above_base_capacity=100 if not use_spot else 50, #fallback to 50% on-demand if spot is not available
                    on_demand_allocation_strategy=autoscaling.OnDemandAllocationStrategy.LOWEST_PRICE,
                    spot_allocation_strategy=autoscaling.SpotAllocationStrategy.CAPACITY_OPTIMIZED, #確保できないのでLOWEST_PRICE→CAPACITY_OPTIMIZEDに変更
                    # spot_instance_pools=None, #確保できないのでまずはオンデマンドで起動
                    spot_max_price=spot_price,
                ),
                launch_template=launchTemplate,
                launch_template_overrides=[
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g6.2xlarge")),
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g5.2xlarge")),
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g4dn.2xlarge")),
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g6.xlarge")),
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g5.xlarge")),
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g4dn.xlarge")),
                ],
            ),
            min_capacity=1,
            max_capacity=1,
            new_instances_protected_from_scale_in=False,
        )

        auto_scaling_group.apply_removal_policy(RemovalPolicy.DESTROY)

        cpu_utilization_metric = cloudwatch.Metric(
            namespace='AWS/EC2',
            metric_name='CPUUtilization',
            dimensions_map={
                'AutoScalingGroupName': auto_scaling_group.auto_scaling_group_name
            },
            statistic='Average',
            period=Duration.minutes(1)
        )

        # Scale down to zero if no activity for an hour
        if auto_scale_down:
            # create a CloudWatch alarm to track the CPU utilization
            cpu_alarm = cloudwatch.Alarm(
                scope,
                "CPUUtilizationAlarm",
                metric=cpu_utilization_metric,
                threshold=1,
                evaluation_periods=60,
                datapoints_to_alarm=60,
                comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD
            )
            scaling_action = autoscaling.StepScalingAction(
                scope,
                "ScalingAction",
                auto_scaling_group=auto_scaling_group,
                adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            )
            # Add scaling adjustments
            scaling_action.add_adjustment(
                # scaling adjustment (reduce instance count by 1)
                adjustment=-1,
                upper_bound=1   # upper threshold for CPU utilization
            )
            scaling_action.add_adjustment(
                adjustment=0,   # No change in instance count
                lower_bound=1   # Apply this when the metric is above 2%
            )
            # Link the StepScalingAction to the CloudWatch alarm
            cpu_alarm.add_alarm_action(
                cw_actions.AutoScalingAction(scaling_action)
            )

        # Scheduled Scaling:
        # 平日・休日問わず、毎日18時〜翌2時（26時）にスケールアップ、それ以外はスケールダウン
        if schedule_auto_scaling:
            # 平日・休日問わず、毎日18時〜翌2時（26時）にスケールアップ、それ以外はスケールダウン
            for day in range(0, 7):  # 0=Sun, ..., 6=Sat
                # スケールアップ: 18:00 JST
                autoscaling.ScheduledAction(
                    scope,
                    f"ScaleUpDay{day}",
                    auto_scaling_group=auto_scaling_group,
                    desired_capacity=1,
                    time_zone=timezone,
                    schedule=autoscaling.Schedule.cron(
                        week_day=str(day), hour="18", minute="0"
                    )
                )
                # スケールダウン: 翌2:00 JST（26時）
                autoscaling.ScheduledAction(
                    scope,
                    f"ScaleDownDay{day}",
                    auto_scaling_group=auto_scaling_group,
                    desired_capacity=1,
                    time_zone=timezone,
                    schedule=autoscaling.Schedule.cron(
                        week_day=str((day + 1) % 7), hour="2", minute="0"
                    )
                )

        # Nag

        NagSuppressions.add_resource_suppressions(
            [asg_security_group],
            suppressions=[
                {"id": "AwsSolutions-EC23",
                 "reason": "The Security Group and ALB needs to allow 0.0.0.0/0 inbound access for the ALB to be publicly accessible. Additional security is provided via Cognito authentication."
                 },
                {"id": "AwsSolutions-ELB2",
                 "reason": "Adding access logs requires extra S3 bucket so removing it for sample purposes."},
            ],
            apply_to_children=True
        )

        NagSuppressions.add_resource_suppressions(
            [auto_scaling_group],
            suppressions=[
                {"id": "AwsSolutions-L1",
                 "reason": "Lambda Runtime is provided by custom resource provider and drain ecs hook implicitely and not critical for sample"
                 },
                {"id": "AwsSolutions-SNS2",
                 "reason": "SNS topic is implicitly created by LifeCycleActions and is not critical for sample purposes."
                 },
                {"id": "AwsSolutions-SNS3",
                 "reason": "SNS topic is implicitly created by LifeCycleActions and is not critical for sample purposes."
                 },
                {"id": "AwsSolutions-AS3",
                 "reason": "Not all notifications are critical for ComfyUI sample"
                 }
            ],
            apply_to_children=True
        )

        # Output

        self.auto_scaling_group = auto_scaling_group
