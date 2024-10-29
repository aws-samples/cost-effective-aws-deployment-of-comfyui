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
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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
                    "AmazonEC2FullAccess"),  # check if less privilege can be given
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedEC2InstanceDefaultPolicy")
            ]
        )

        user_data_script = ec2.UserData.for_linux()
        user_data_script.add_commands("""
            #!/bin/bash
            REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region) 
            docker plugin install rexray/ebs --grant-all-permissions REXRAY_PREEMPT=true EBS_REGION=$REGION
            systemctl restart docker
        """)

        # Create an Auto Scaling Group with two EBS volumes
        launchTemplate = ec2.LaunchTemplate(
            scope,
            "Host",
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(
                hardware_type=ecs.AmiHardwareType.GPU
            ),
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
                    on_demand_base_capacity=0,
                    on_demand_percentage_above_base_capacity=0 if use_spot else 100,
                    on_demand_allocation_strategy=autoscaling.OnDemandAllocationStrategy.LOWEST_PRICE,
                    spot_allocation_strategy=autoscaling.SpotAllocationStrategy.LOWEST_PRICE,
                    spot_instance_pools=1,
                    spot_max_price=spot_price,
                ),
                launch_template=launchTemplate,
                launch_template_overrides=[
                    autoscaling.LaunchTemplateOverrides(
                        instance_type=ec2.InstanceType("g4dn.xlarge")),
                    autoscaling.LaunchTemplateOverrides(
                        instance_type=ec2.InstanceType("g5.xlarge")),
                    autoscaling.LaunchTemplateOverrides(
                        instance_type=ec2.InstanceType("g6.xlarge")),
                    autoscaling.LaunchTemplateOverrides(
                        instance_type=ec2.InstanceType("g4dn.2xlarge")),
                    autoscaling.LaunchTemplateOverrides(
                        instance_type=ec2.InstanceType("g5.2xlarge")),
                    autoscaling.LaunchTemplateOverrides(
                        instance_type=ec2.InstanceType("g6.2xlarge")),
                ],
            ),
            min_capacity=0,
            max_capacity=1,
            desired_capacity=1,
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
                cooldown=Duration.seconds(120)
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
        # (default) set desired capacity to 0 after work hour and 1 on start of work hour (only mon-fri)
        # Use TZ identifier for timezone https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        if schedule_auto_scaling:
            # Create a scheduled action to set the desired capacity to 0
            after_work_hours_action = autoscaling.ScheduledAction(
                scope,
                "AfterWorkHoursAction",
                auto_scaling_group=auto_scaling_group,
                desired_capacity=0,
                time_zone=timezone,
                schedule=autoscaling.Schedule.expression(schedule_scale_down)
            )
            # Create a scheduled action to set the desired capacity to 1
            start_work_hours_action = autoscaling.ScheduledAction(
                scope,
                "StartWorkHoursAction",
                auto_scaling_group=auto_scaling_group,
                desired_capacity=1,
                time_zone=timezone,
                schedule=autoscaling.Schedule.expression(schedule_scale_up)
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
