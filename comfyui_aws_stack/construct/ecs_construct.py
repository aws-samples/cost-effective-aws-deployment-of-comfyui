from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_ecr_assets as ecr_assets,
    aws_logs as logs,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as elbv2,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
    aws_chatbot as chatbot,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_kms as kms,
    Duration,
    RemovalPolicy,
    Size,
)
from constructs import Construct
from cdk_nag import NagSuppressions


class EcsConstruct(Construct):
    cluster: ecs.Cluster
    service: ecs.IService
    ecs_target_group: elbv2.ApplicationTargetGroup
    ecs_health_topic: sns.Topic

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            vpc: ec2.Vpc,
            auto_scaling_group: autoscaling.AutoScalingGroup,
            alb_security_group: ec2.SecurityGroup,
            is_sagemaker_studio: bool,
            suffix: str,
            region: str,
            user_pool: cognito.UserPool,
            user_pool_client: cognito.UserPoolClient,
            slack_workspace_id: str = None,
            slack_channel_id: str = None,
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create an ECS Cluster
        cluster = ecs.Cluster(
            scope, "ComfyUICluster",
            vpc=vpc,
            container_insights=True
        )

        # Create ASG Capacity Provider for the ECS Cluster
        capacity_provider = ecs.AsgCapacityProvider(
            scope, "AsgCapacityProvider",
            auto_scaling_group=auto_scaling_group,
            enable_managed_scaling=False,  # Enable managed scaling
            # Disable managed termination protection
            enable_managed_termination_protection=False,
            target_capacity_percent=100
        )

        cluster.add_asg_capacity_provider(capacity_provider)

        # Create IAM Role for ECS Task Execution
        task_exec_role = iam.Role(
            scope,
            "ECSTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # ECR Repository
        docker_image_asset = ecr_assets.DockerImageAsset(
            scope,
            "ComfyUIImage",
            directory="comfyui_aws_stack/docker",
            platform=ecr_assets.Platform.LINUX_AMD64,
            network_mode=ecr_assets.NetworkMode.custom(
                "sagemaker") if is_sagemaker_studio else None
        )

        # CloudWatch Logs Group
        log_group = logs.LogGroup(
            scope,
            "LogGroup",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Docker Volume Configuration
        volume = ecs.Volume(
            name="ComfyUIVolume-" + suffix,
            docker_volume_configuration=ecs.DockerVolumeConfiguration(
                scope=ecs.Scope.SHARED,
                driver="public.ecr.aws/j1l5j1d1/rexray-ebs",
                driver_opts={
                    "volumetype": "gp3",
                    "size": "250"  # Size in GiB
                },
                autoprovision=True
            )
        )

        task_definition = ecs.Ec2TaskDefinition(
            scope,
            "TaskDef",
            network_mode=ecs.NetworkMode.AWS_VPC,
            task_role=task_exec_role,
            execution_role=task_exec_role,
            volumes=[volume]
        )

        # Linux parameters for swap configuration
        linux_parameters = ecs.LinuxParameters(
            self,
            "LinuxParameters",
            max_swap=Size.mebibytes(10240),  # 10GB swap memory (10 * 1024 MiB)
            swappiness=60    # Default swappiness value
        )

        # Add container to the task definition
        container = task_definition.add_container(
            "ComfyUIContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                docker_image_asset.repository,
                docker_image_asset.image_tag
            ),
            gpu_count=1,
            memory_reservation_mib=15000,
            memory_limit_mib=15000,  # Set total memory limit
            linux_parameters=linux_parameters,
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="comfy-ui", log_group=log_group),
            health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL", "curl -f http://localhost:8181/system_stats || exit 1"],
                interval=Duration.seconds(15),
                timeout=Duration.seconds(10),
                retries=8,
                start_period=Duration.seconds(30)
            ),
            environment={
                "AWS_REGION": region,
                "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
                "COGNITO_CLIENT_ID": user_pool_client.user_pool_client_id,
                # Add other env variables here
            }
        )

        # Mount the host volume to the container
        container.add_mount_points(
            ecs.MountPoint(
                container_path="/home/user/opt/ComfyUI",
                source_volume=volume.name,
                read_only=False
            )
        )

        # Port mappings for the container
        container.add_port_mappings(
            ecs.PortMapping(
                container_port=8181,
                host_port=8181,
                app_protocol=ecs.AppProtocol.http,
                name="comfyui-port-mapping",
                protocol=ecs.Protocol.TCP,
            )
        )

        # Create ECS Service Security Group
        service_security_group = ec2.SecurityGroup(
            scope,
            "ServiceSecurityGroup",
            vpc=vpc,
            description="Security Group for ECS Service",
            allow_all_outbound=True,
        )

        # Allow inbound traffic on port 8181
        service_security_group.add_ingress_rule(
            ec2.Peer.security_group_id(alb_security_group.security_group_id),
            ec2.Port.tcp(8181),
            "Allow inbound traffic on port 8181",
        )

        # Create ECS Service
        service = ecs.Ec2Service(
            scope,
            "ComfyUIService",
            cluster=cluster,
            task_definition=task_definition,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider=capacity_provider.capacity_provider_name, weight=1
                )
            ],
            security_groups=[service_security_group],
            health_check_grace_period=Duration.seconds(30),
            min_healthy_percent=0,
        )

        # Add target groups for ECS service
        ecs_target_group = elbv2.ApplicationTargetGroup(
            scope,
            "EcsTargetGroup",
            port=8181,
            vpc=vpc,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            targets=[
                service.load_balancer_target(
                    container_name=container.container_name, container_port=8181
                )],
            health_check=elbv2.HealthCheck(
                enabled=True,
                path="/system_stats",
                port="8181",
                protocol=elbv2.Protocol.HTTP,
                healthy_http_codes="200",  # Adjust as needed
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                unhealthy_threshold_count=3,
                healthy_threshold_count=2,
            )
        )

        # CloudWatch Monitoring and Slack Notifications
        ecs_health_topic = None
        if slack_workspace_id and slack_channel_id:
            # Create SNS Topic for ECS Task Health Alerts
            ecs_health_topic = sns.Topic(
                self, "EcsHealthTopic",
                display_name="ECS Task Health Alerts",
                enforce_ssl=True
            )

            # Monitor ECS Task Count using Container Insights
            running_tasks_metric = cloudwatch.Metric(
                namespace="ECS/ContainerInsights",
                metric_name="RunningTaskCount",
                dimensions_map={
                    "ClusterName": cluster.cluster_name,
                    "ServiceName": service.service_name
                },
                period=Duration.minutes(1)
            )

            # Alarm when task count is 0
            no_running_tasks_alarm = cloudwatch.Alarm(
                self, "NoRunningTasksAlarm",
                metric=running_tasks_metric,
                evaluation_periods=3,
                threshold=0,
                comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_OR_EQUAL_TO_THRESHOLD,
                alarm_description="Alert when there are no running tasks in the service",
                treat_missing_data=cloudwatch.TreatMissingData.BREACHING
            )

            # Attach SNS topic to the alarm
            no_running_tasks_alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(ecs_health_topic)
            )

            # Also monitor ALB target health
            target_group_health_metric = cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="UnHealthyHostCount",
                dimensions_map={
                    "TargetGroup": ecs_target_group.target_group_arn.split(":")[-1],
                    # This might need to be adjusted to match your ALB name pattern
                    "LoadBalancer": "app/ComfyUIALB"
                },
                period=Duration.minutes(1)
            )

            # Create alarm for unhealthy hosts
            unhealthy_hosts_alarm = cloudwatch.Alarm(
                self, "UnhealthyHostsAlarm",
                metric=target_group_health_metric,
                evaluation_periods=3,
                threshold=0,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                alarm_description="Alert when there are unhealthy hosts in the target group",
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
            )

            # Add SNS action to the alarm
            unhealthy_hosts_alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(ecs_health_topic)
            )

        # Nag

        NagSuppressions.add_resource_suppressions(
            [alb_security_group, service_security_group],
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
            [task_definition],
            suppressions=[
                {"id": "AwsSolutions-ECS2",
                 "reason": "Recent aws-cdk-lib version adds 'AWS_REGION' environment variable implicitly."
                 },
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

        if ecs_health_topic:
            NagSuppressions.add_resource_suppressions(
                [ecs_health_topic],
                suppressions=[
                    {"id": "AwsSolutions-SNS2",
                     "reason": "SNS topic is implicitly created by LifeCycleActions and is not critical for sample purposes."
                     },
                    {"id": "AwsSolutions-SNS3",
                     "reason": "SNS topic is implicitly created by LifeCycleActions and is not critical for sample purposes."
                     },
                ],
            )

        # Output

        self.cluster = cluster
        self.service = service
        self.ecs_target_group = ecs_target_group
        self.ecs_health_topic = ecs_health_topic
