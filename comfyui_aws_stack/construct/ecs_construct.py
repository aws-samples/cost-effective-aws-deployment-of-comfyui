from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_ecr_assets as ecr_assets,
    aws_logs as logs,
    aws_iam as iam,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as elbv2,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from cdk_nag import NagSuppressions


class EcsConstruct(Construct):
    cluster: ecs.Cluster
    service: ecs.IService
    ecs_target_group: elbv2.ApplicationTargetGroup

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            vpc: ec2.Vpc,
            auto_scaling_group: autoscaling.AutoScalingGroup,
            alb_security_group: ec2.SecurityGroup,
            is_sagemaker_studio: bool,
            suffix: str,
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

        # Add container to the task definition
        container = task_definition.add_container(
            "ComfyUIContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                docker_image_asset.repository,
                docker_image_asset.image_tag
            ),
            gpu_count=1,
            memory_reservation_mib=15000,
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="comfy-ui", log_group=log_group),
            health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL", "curl -f http://localhost:8181/system_stats || exit 1"],
                interval=Duration.seconds(15),
                timeout=Duration.seconds(10),
                retries=8,
                start_period=Duration.seconds(30)
            )
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

        # Output

        self.cluster = cluster
        self.service = service
        self.ecs_target_group = ecs_target_group
