from aws_cdk import (
    Stack,
    CfnOutput
)
from constructs import Construct

from comfyui_aws_stack.construct.vpc_construct import VpcConstruct
from comfyui_aws_stack.construct.alb_construct import AlbConstruct
from comfyui_aws_stack.construct.asg_construct import AsgConstruct
from comfyui_aws_stack.construct.ecs_construct import EcsConstruct
from comfyui_aws_stack.construct.admin_construct import AdminConstruct
from comfyui_aws_stack.construct.auth_construct import AuthConstruct
from aws_cdk import (
    aws_chatbot as chatbot,
    aws_iam as iam
)

import os
import hashlib
from typing import List


class ComfyUIStack(Stack):

    def __init__(self,
                 scope: Construct,
                 construct_id: str,
                 # VPC
                 cheap_vpc: bool = True,
                 # Spot
                 use_spot: bool = True,
                 spot_price: str = "0.752",
                 # Auto Scaling
                 auto_scale_down: bool = True,
                 schedule_auto_scaling: bool = False,
                 timezone: str = "UTC",
                 schedule_scale_up: str = "0 9 * * 1-5",
                 schedule_scale_down: str = "0 18 * * *",
                 # Sign up
                 self_sign_up_enabled: bool = False,
                 allowed_sign_up_email_domains: List[str] = None,
                 mfa_required: bool = False,
                 saml_auth_enabled: bool = False,
                 # Network Restriction
                 allowed_ip_v4_address_ranges: List[str] = None,
                 allowed_ip_v6_address_ranges: List[str] = None,
                 # WAF Rate Limiting
                 waf_rate_limit_enabled: bool = False,
                 waf_rate_limit_requests: int = 300,
                 waf_rate_limit_interval: int = 300,
                 # Custom Domain
                 host_name: str = None,
                 domain_name: str = None,
                 hosted_zone_id: str = None,
                 # Slack
                 slack_workspace_id: str = None,
                 slack_channel_id: str = None,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Setting
        region = self.region
        unique_input = f"{self.account}-{self.region}-{self.stack_name}"
        unique_hash = hashlib.sha256(
            unique_input.encode('utf-8')).hexdigest()[:10]
        suffix = unique_hash.lower()

        # Check host
        is_sagemaker_studio = "SAGEMAKER_APP_TYPE_LOWERCASE" in os.environ

        # VPC

        vpc_construct = VpcConstruct(
            self, "VpcConstruct",
            cheap_vpc=cheap_vpc
        )

        # ALB

        alb_construct = AlbConstruct(
            self, "AlbConstruct",
            vpc=vpc_construct.vpc,
            is_sagemaker_studio=is_sagemaker_studio,
            allowed_ip_v4_address_ranges=allowed_ip_v4_address_ranges,
            allowed_ip_v6_address_ranges=allowed_ip_v6_address_ranges,
            waf_rate_limit_enabled=waf_rate_limit_enabled,
            waf_rate_limit_requests=waf_rate_limit_requests,
            waf_rate_limit_interval=waf_rate_limit_interval,
            host_name=host_name,
            domain_name=domain_name,
            hosted_zone_id=hosted_zone_id,
        )

        # Auth

        auth_construct = AuthConstruct(
            self, "AuthConstruct",
            alb=alb_construct.alb,
            suffix=suffix,
            host_name=host_name,
            domain_name=domain_name,
            saml_auth_enabled=saml_auth_enabled,
            self_sign_up_enabled=self_sign_up_enabled,
            mfa_required=mfa_required,
            allowed_sign_up_email_domains=allowed_sign_up_email_domains,
        )

        # ASG

        asg_construct = AsgConstruct(
            self, "AsgConstruct",
            vpc=vpc_construct.vpc,
            use_spot=use_spot,
            spot_price=spot_price,
            auto_scale_down=auto_scale_down,
            schedule_auto_scaling=schedule_auto_scaling,
            timezone=timezone,
            schedule_scale_down=schedule_scale_down,
            schedule_scale_up=schedule_scale_up,
            slack_workspace_id=slack_workspace_id,
            slack_channel_id=slack_channel_id,
        )

        # ECS

        ecs_construct = EcsConstruct(
            self, "EcsConstruct",
            vpc=vpc_construct.vpc,
            auto_scaling_group=asg_construct.auto_scaling_group,
            alb_security_group=alb_construct.alb_security_group,
            is_sagemaker_studio=is_sagemaker_studio,
            suffix=suffix,
            region=region,
            user_pool=auth_construct.user_pool,
            user_pool_client=auth_construct.user_pool_client,
            slack_workspace_id=slack_workspace_id,
            slack_channel_id=slack_channel_id,
        )

        # Slack

        if slack_workspace_id and slack_channel_id:
            slack_channel = chatbot.SlackChannelConfiguration(
                self, "SlackChannel",
                slack_channel_configuration_name="TestChannel",
                slack_workspace_id=slack_workspace_id,
                slack_channel_id=slack_channel_id,
                notification_topics=[
                    asg_construct.asg_events_topic, ecs_construct.ecs_health_topic]
            )
            slack_channel.role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchReadOnlyAccess"
                )
            )
            slack_channel.role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonQFullAccess"
                )
            )

        # Admin Lambda

        admin_construct = AdminConstruct(
            self, "AdminConstruct",
            vpc=vpc_construct.vpc,
            cluster=ecs_construct.cluster,
            service=ecs_construct.service,
            auto_scaling_group=asg_construct.auto_scaling_group,
            user_pool_logout_url=auth_construct.user_pool_logout_url,
        )

        # Associate resources to ALB

        alb_construct.associate_resources(
            ecs_target_group=ecs_construct.ecs_target_group,
            lambda_admin_target_group=admin_construct.lambda_admin_target_group,
            lambda_restart_docker_target_group=admin_construct.lambda_restart_docker_target_group,
            lambda_shutdown_target_group=admin_construct.lambda_shutdown_target_group,
            lambda_scaleup_target_group=admin_construct.lambda_scaleup_target_group,
            lambda_signout_target_group=admin_construct.lambda_signout_target_group,
            user_pool=auth_construct.user_pool,
            user_pool_client=auth_construct.user_pool_client,
            user_pool_custom_domain=auth_construct.user_pool_custom_domain,
        )

        # Add env variables to lambda

        admin_construct.add_environments(
            lambda_admin_rule=alb_construct.lambda_admin_rule,
        )

        # Output

        CfnOutput(self, "Endpoint", value=auth_construct.application_dns_name)
        CfnOutput(self, "UserPoolId",
                  value=auth_construct.user_pool.user_pool_id)
        CfnOutput(self, "CognitoDomainName",
                  value=auth_construct.user_pool_custom_domain.domain_name)
