from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_logs as logs,
    aws_s3 as s3,
    aws_iam as iam,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_actions as elb_actions,
    aws_elasticloadbalancingv2_targets as targets,
    aws_events as events,
    aws_events_targets as event_targets,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    Duration,
    RemovalPolicy,
    CustomResource,
    aws_certificatemanager as acm,
    aws_lambda as lambda_,
    aws_lambda_python_alpha as lambda_python,
    custom_resources as cr,
    aws_cognito as cognito,

)
from cdk_nag import NagSuppressions
from constructs import Construct
import json
import urllib.parse

# Load the Environment Configuration from the JSON file
with open(
    "./comfyui_aws_stack/cert.json",
    "r",
) as file:
    config = json.load(file)

class ComfyUIStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Use the default VPC
        #vpc = ec2.Vpc.from_lookup(self, "VPC", is_default=True)
        vpc = ec2.Vpc(self, "CustomVPC",
                    max_azs=2,  # Define the maximum number of Availability Zones
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
                    ])


        # Enable VPC Flow Logs
        flow_log = ec2.FlowLog(
            self,
            "FlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(),
        )

        # Create Auto Scaling Group Security Group
        asg_security_group = ec2.SecurityGroup(
            self,
            "AsgSecurityGroup",
            vpc=vpc,
            description="Security Group for ASG",
            allow_all_outbound=True,
        )

        # Allow inbound traffic on port 80
        asg_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "Allow inbound traffic on port 80",
        )
        # Allow inbound traffic on port 443
        asg_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "Allow inbound traffic on port 443",
        )

        # EC2 Role for AWS internal use (if necessary)
        ec2_role = iam.Role(
            self,
            "EC2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2FullAccess"), # check if less privilege can be given
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedEC2InstanceDefaultPolicy")
            ]
        )

        user_data_script = ec2.UserData.for_linux()
        user_data_script.add_commands("""
            #!/bin/bash
            REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region) 
            docker plugin install rexray/ebs --grant-all-permissions REXRAY_PREEMPT=true EBS_REGION=$REGION
            systemctl restart docker
        """)

        asg_name="ComfyASG"
        # Create an Auto Scaling Group with two EBS volumes
        auto_scaling_group = autoscaling.AutoScalingGroup(
            self,
            "ASG",
            auto_scaling_group_name=asg_name,
            vpc=vpc,
            instance_type=ec2.InstanceType("g4dn.2xlarge"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(
                hardware_type=ecs.AmiHardwareType.GPU
            ),
            role=ec2_role,
            min_capacity=0,
            max_capacity=1,
            desired_capacity=1,
            new_instances_protected_from_scale_in=False,
            security_group=asg_security_group,
            user_data=user_data_script,
            block_devices=[
                autoscaling.BlockDevice(
                    device_name="/dev/xvda",
                    volume=autoscaling.BlockDeviceVolume.ebs(volume_size=50, 
                                                             encrypted=True)
                )
            ]
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

        # create a CloudWatch alarm to track the CPU utilization
        cpu_alarm = cloudwatch.Alarm(
            self,
            "CPUUtilizationAlarm",
            metric=cpu_utilization_metric,
            threshold=1,
            evaluation_periods=60,
            datapoints_to_alarm=60,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD
        )

        scaling_action = autoscaling.StepScalingAction(
            self,
            "ScalingAction",
            auto_scaling_group=auto_scaling_group,
            adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=Duration.seconds(120)
        )

        # Add scaling adjustments
        scaling_action.add_adjustment(
            adjustment=-1,  # scaling adjustment (reduce instance count by 1)
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

        # Create an ECS Cluster
        cluster = ecs.Cluster(
            self, "ComfyUICluster", 
            vpc=vpc, 
            cluster_name="ComfyUICluster", 
            container_insights=True
        )
        
        # Create ASG Capacity Provider for the ECS Cluster
        capacity_provider = ecs.AsgCapacityProvider(
            self, "AsgCapacityProvider",
            auto_scaling_group=auto_scaling_group,
            enable_managed_scaling=False,  # Enable managed scaling
            enable_managed_termination_protection=False,  # Disable managed termination protection
            target_capacity_percent=100
        )

        cluster.add_asg_capacity_provider(capacity_provider)

        # Create IAM Role for ECS Task Execution
        task_exec_role = iam.Role(
            self,
            "ECSTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # ECR Repository
        ecr_repository = ecr.Repository.from_repository_name(
            self, 
            "comfyui", 
            "comfyui")


        # CloudWatch Logs Group
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name="/ecs/comfy-ui",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Docker Volume Configuration
        volume = ecs.Volume(
            name="ComfyUIVolume",
            docker_volume_configuration=ecs.DockerVolumeConfiguration(
                scope=ecs.Scope.SHARED,
                driver="rexray/ebs",
                driver_opts={
                    "volumetype": "gp3",
                    "size": "250"  # Size in GiB
                },
                autoprovision=True
            )
        )

        task_definition = ecs.Ec2TaskDefinition(
            self,
            "TaskDef",
            network_mode=ecs.NetworkMode.AWS_VPC,
            task_role=task_exec_role,
            execution_role=task_exec_role,
            volumes=[volume]
        )

        # Add container to the task definition
        container = task_definition.add_container(
            "ComfyUIContainer",
            image=ecs.ContainerImage.from_ecr_repository(ecr_repository, "latest"),
            gpu_count=1,
            memory_reservation_mib=30720,
            cpu=7680,
            logging=ecs.LogDriver.aws_logs(stream_prefix="comfy-ui", log_group=log_group),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8181/system_stats || exit 1"],
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
                source_volume="ComfyUIVolume",
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
            self,
            "ServiceSecurityGroup",
            vpc=vpc,
            description="Security Group for ECS Service",
            allow_all_outbound=True,
        )

        # Allow inbound traffic on port 8181
        service_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(8181),
            "Allow inbound traffic on port 8181",
        )

        # Create ECS Service
        service = ecs.Ec2Service(
            self,
            "ComfyUIService",
            service_name="ComfyUIService",
            cluster=cluster,
            task_definition=task_definition,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider=capacity_provider.capacity_provider_name, weight=1
                )
            ],
            security_groups=[service_security_group],
            health_check_grace_period=Duration.seconds(30)
        )

        # Add self-signed certificate to the Load Balancer to support https
        cert_function = lambda_python.PythonFunction(
            self,
            "RegisterSelfSignedCert",
            entry="./comfyui_aws_stack/cert_lambda",
            index="function.py",
            handler="lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(amount=120),
        )

        cert_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["acm:ImportCertificate"], resources=["*"]
            )
        )

        cert_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["acm:AddTagsToCertificate"], resources=["*"]
            )
        )

        provider = cr.Provider(
            self, "SelfSignedCertCustomResourceProvider", on_event_handler=cert_function
        )

        custom_resource = CustomResource(
            self,
            "SelfSignedCertCustomResource",
            service_token=provider.service_token,
            properties={
                "email_address": config["self_signed_certificate"]["email_address"],
                "common_name": config["self_signed_certificate"]["common_name"],
                "city": config["self_signed_certificate"]["city"],
                "state": config["self_signed_certificate"]["state"],
                "country_code": config["self_signed_certificate"]["country_code"],
                "organization": config["self_signed_certificate"]["organization"],
                "organizational_unit": config["self_signed_certificate"][
                    "organizational_unit"
                ],
                "validity_seconds": config["self_signed_certificate"][
                    "validity_seconds"
                ],
            },
        )

        cert_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["acm:DeleteCertificate"],
                resources=["*"],
            )
        )

        certificate = acm.Certificate.from_certificate_arn(
            self, id="SelfSignedCert", certificate_arn=custom_resource.ref
        )

        # Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(self, "ComfyUIALB", vpc=vpc, load_balancer_name="ComfyUIALB", internet_facing=True)

        # Access logging for the Load Balancer
        log_bucket = s3.Bucket.from_bucket_name(
            self, "LogBucket", "my-access-logs-bucket"
        )
        alb.log_access_logs(log_bucket, "load-balancer-logs/")

        # Redirect Load Balancer traffic on port 80 to port 443
        alb.add_redirect(
            source_protocol=elbv2.ApplicationProtocol.HTTP,
            source_port=80,
            target_protocol=elbv2.ApplicationProtocol.HTTPS,
            target_port=443
        )

        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AutoScalingFullAccess"),
            ]
        )

        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["ecs:DescribeServices", 
                     "ecs:ListTasks",
                     "elasticloadbalancing:ModifyListener",
                     "elasticloadbalancing:ModifyRule",
                     "elasticloadbalancing:DescribeRules",
                     "elasticloadbalancing:DescribeListeners",
                     "ecs:DescribeServices",
                     "ecs:UpdateService",
                     "ssm:SendCommand"],
            resources=["*"]
        ))

        admin_lambda = lambda_python.PythonFunction(
            self,
            "AdminFunction",
            entry="./comfyui_aws_stack/admin_lambda", 
            index="admin.py", 
            handler="handler", 
            role=lambda_role,
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(amount=60)
        )

        restart_docker_lambda = lambda_python.PythonFunction(
            self,
            "RestartDockerFunction",
            entry="./comfyui_aws_stack/admin_lambda", 
            index="restart_docker.py", 
            handler="handler", 
            role=lambda_role,
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(amount=60)
        )

        shutdown_lambda = lambda_python.PythonFunction(
            self,
            "ShutdownFunction",
            index="shutdown.py", 
            entry="./comfyui_aws_stack/admin_lambda", 
            handler="handler", 
            role=lambda_role, 
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(amount=60)
        )

        scaleup_trigger_lambda = lambda_.Function(
            self,
            "ScaleUpTriggerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=lambda_role,
            handler="scaleup_trigger.handler",
            code=lambda_.Code.from_asset("./comfyui_aws_stack/admin_lambda"),
            timeout=Duration.seconds(amount=60)
        )

        scalein_listener_lambda = lambda_.Function(
            self,
            "ScaleinListenerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=lambda_role,
            handler="scalein_listener.handler",
            code=lambda_.Code.from_asset("./comfyui_aws_stack/admin_lambda"),
            timeout=Duration.seconds(amount=60)
        )

        scaleup_listener_lambda = lambda_.Function(
            self,
            "ScaleupListenerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=lambda_role,
            handler="scaleup_listener.handler",
            code=lambda_.Code.from_asset("./comfyui_aws_stack/admin_lambda"),
            timeout=Duration.seconds(amount=60)
        )

        # Add target groups for ECS service
        ecs_target_group = elbv2.ApplicationTargetGroup(
            self,
            "EcsTargetGroup",
            port=8181,
            vpc=vpc,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            targets=[
                service.load_balancer_target(
                    container_name="ComfyUIContainer", container_port=8181
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

        lambda_admin_target_group = elbv2.ApplicationTargetGroup(
            self,
            "LambdaAdminTargetGroup",
            target_group_name="LambdaAdminTargetGroup",
            vpc=vpc,
            target_type=elbv2.TargetType.LAMBDA,
            targets=[targets.LambdaTarget(admin_lambda)]
        )

        lambda_restart_docker_target_group = elbv2.ApplicationTargetGroup(
            self,
            "LambdaRestartDockerTargetGroup",
            target_group_name="LambdaRestartDockerTargetGroup",
            vpc=vpc,
            target_type=elbv2.TargetType.LAMBDA,
            targets=[targets.LambdaTarget(restart_docker_lambda)]
        )

        lambda_shutdown_target_group = elbv2.ApplicationTargetGroup(
            self,
            "LambdaShutdownTargetGroup",
            target_group_name="LambdaShutdownTargetGroup",
            vpc=vpc,
            target_type=elbv2.TargetType.LAMBDA,
            targets=[targets.LambdaTarget(shutdown_lambda)]
        )

        lambda_scaleup_target_group = elbv2.ApplicationTargetGroup(
            self,
            "LambdaScaleupTargetGroup",
            target_group_name="LambdaScaleupTargetGroup",
            vpc=vpc,
            target_type=elbv2.TargetType.LAMBDA,
            targets=[targets.LambdaTarget(scaleup_trigger_lambda)]
        )

        # Add listener to the Load Balancer on port 443
        listener = alb.add_listener(
            "Listener", 
            certificates=[certificate], 
            port=443, 
            protocol=elbv2.ApplicationProtocol.HTTPS,
            default_action=elbv2.ListenerAction.forward([ecs_target_group])
        )

        """
        Sets up the cognito infrastructure with the user pool, custom domain
        and app client for use by the ALB.
        """
        cognito_custom_domain = "comfyui-alb-auth-a"
        application_dns_name = alb.load_balancer_dns_name

        # Create the user pool that holds our users
        user_pool = cognito.UserPool(
            self,
            "ComfyUIuserPool",
            account_recovery=cognito.AccountRecovery.EMAIL_AND_PHONE_WITHOUT_MFA,
            auto_verify=cognito.AutoVerifiedAttrs(email=True, phone=True),
            self_sign_up_enabled=False,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(mutable=True, required=True),
                given_name=cognito.StandardAttribute(mutable=True, required=True),
                family_name=cognito.StandardAttribute(mutable=True, required=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED
        )

        # Add a custom domain for the hosted UI
        user_pool_custom_domain = user_pool.add_domain(
            "user-pool-domain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=cognito_custom_domain
            )
        )

        # Create an app client that the ALB can use for authentication
        user_pool_client = user_pool.add_client(
            "alb-app-client",
            user_pool_client_name="AlbAuthentication",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                callback_urls=[
                    # This is the endpoint where the ALB accepts the
                    # response from Cognito
                    f"https://{application_dns_name}/oauth2/idpresponse",

                    # This is here to allow a redirect to the login page
                    # after the logout has been completed
                    f"https://{application_dns_name}"
                ],
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID
                ]
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ]
        )

        # Logout URLs and redirect URIs can't be set in CDK constructs natively ...yet
        user_pool_client_cf: cognito.CfnUserPoolClient = user_pool_client.node.default_child
        user_pool_client_cf.logout_ur_ls = [
            # This is here to allow a redirect to the login page
            # after the logout has been completed
            f"https://{application_dns_name}"
        ]

        user_pool_full_domain = user_pool_custom_domain.base_url()
        redirect_uri = urllib.parse.quote('https://' + application_dns_name)
        user_pool_logout_url = f"{user_pool_full_domain}/logout?" \
                                    + f"client_id={user_pool_client.user_pool_client_id}&" \
                                    + f"logout_uri={redirect_uri}"

        user_pool_user_info_url = f"{user_pool_full_domain}/oauth2/userInfo"

        lambda_admin_rule = elbv2.ApplicationListenerRule(
            self,
            "LambdaAdminRule",
            listener=listener,
            priority=5,
            conditions=[elbv2.ListenerCondition.path_patterns(["/admin"])],
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward([lambda_admin_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
        )

        admin_lambda.add_environment("ASG_NAME", auto_scaling_group.auto_scaling_group_name)
        admin_lambda.add_environment("ECS_CLUSTER_NAME", cluster.cluster_name)
        admin_lambda.add_environment("ECS_SERVICE_NAME", service.service_name)

        lambda_restart_docker_rule = elbv2.ApplicationListenerRule(
            self,
            "LambdaRestartDockerRule",
            listener=listener,
            priority=10,
            conditions=[elbv2.ListenerCondition.path_patterns(["/admin/restart"])],
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward([lambda_restart_docker_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
        )

        restart_docker_lambda.add_environment("ASG_NAME", auto_scaling_group.auto_scaling_group_name)
        restart_docker_lambda.add_environment("ECS_CLUSTER_NAME", cluster.cluster_name)
        restart_docker_lambda.add_environment("ECS_SERVICE_NAME", service.service_name)
        restart_docker_lambda.add_environment("LISTENER_RULE_ARN", lambda_admin_rule.listener_rule_arn)

        lambda_shutdown_rule = elbv2.ApplicationListenerRule(
            self,
            "LambdaShutdownRule",
            listener=listener,
            priority=15,
            conditions=[elbv2.ListenerCondition.path_patterns(["/admin/shutdown"])],
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward([lambda_shutdown_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
        )

        shutdown_lambda.add_environment("ASG_NAME", auto_scaling_group.auto_scaling_group_name)

        lambda_scaleup_rule = elbv2.ApplicationListenerRule(
            self,
            "LambdaScaleupRule",
            listener=listener,
            priority=20, 
            conditions=[elbv2.ListenerCondition.path_patterns(["/admin/scaleup"])],
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward([lambda_scaleup_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
        )

        scaleup_trigger_lambda.add_environment("ASG_NAME", auto_scaling_group.auto_scaling_group_name)
        scaleup_trigger_lambda.add_environment("ECS_CLUSTER_NAME", cluster.cluster_name)
        scaleup_trigger_lambda.add_environment("ECS_SERVICE_NAME", service.service_name)

        # Add authentication action as the first priority rule
        auth_rule = listener.add_action(
            "AuthenticateRule",
            priority=25, 
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward([ecs_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
            conditions=[elbv2.ListenerCondition.path_patterns(["/*"])]
        )

        #CloudWatch Event Rule for ASG scale-in events
        scale_in_event_pattern = events.EventPattern(
            source=["aws.autoscaling"],
            detail_type=["EC2 Instance-terminate Lifecycle Action"],
            detail={
                "AutoScalingGroupName": [auto_scaling_group.auto_scaling_group_name]
            }
        )

        scale_in_event_rule = events.Rule(
            self,
            "ScaleInEventRule",
            event_pattern=scale_in_event_pattern,
            targets=[event_targets.LambdaFunction(scalein_listener_lambda)]
        )

        scalein_listener_lambda.add_environment("ASG_NAME", auto_scaling_group.auto_scaling_group_name)
        scalein_listener_lambda.add_environment("LISTENER_RULE_ARN", lambda_admin_rule.listener_rule_arn)

        ecs_task_state_change_event_rule = events.Rule(
            self,
            "EcsTaskStateChangeRule",
            event_pattern=events.EventPattern(
                source=["aws.ecs"],
                detail_type=["ECS Task State Change"],
                detail={
                    "clusterArn": [cluster.cluster_arn],
                    "lastStatus": ["RUNNING"],
                }
            ),
            targets=[event_targets.LambdaFunction(scaleup_listener_lambda)]
        )

        scaleup_listener_lambda.add_environment("ASG_NAME", auto_scaling_group.auto_scaling_group_name)
        scaleup_listener_lambda.add_environment("ECS_CLUSTER_NAME", cluster.cluster_name)
        scaleup_listener_lambda.add_environment("ECS_SERVICE_NAME", service.service_name)
        scaleup_listener_lambda.add_environment("LISTENER_RULE_ARN", lambda_admin_rule.listener_rule_arn)


        NagSuppressions.add_resource_suppressions(
            [asg_security_group,service_security_group,alb],
            suppressions=[
                {"id": "AwsSolutions-EC23",
                 "reason": "The Security Group and ALB needs to allow 0.0.0.0/0 inbound access for the ALB to be publicly accessible. Additional security is provided via Cognito authentication."
                }
            ],
            apply_to_children=True
        )

        NagSuppressions.add_resource_suppressions(
            [provider, auto_scaling_group],
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