from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_actions as elb_actions,
    Duration,
    CustomResource,
    aws_certificatemanager as acm,
    aws_lambda as lambda_,
    custom_resources as cr,
    aws_cognito as cognito,
    aws_wafv2 as wafv2,
    aws_route53 as route53,
    aws_route53_targets as route53_targets,
    BundlingOptions,
)
from constructs import Construct
from cdk_nag import NagSuppressions

from typing import List


config = {
    "self_signed_certificate": {
        "email_address": "customer@example.com",
        "common_name": "example.com",
        "city": ".",
        "state": ".",
        "country_code": "AT",
        "organization": ".",
        "organizational_unit": ".",
        "validity_seconds": 157680000
    }
}


class AlbConstruct(Construct):
    scope: Construct
    alb: elbv2.ApplicationLoadBalancer
    alb_security_group: ec2.SecurityGroup
    certificate: acm.Certificate
    listener: elbv2.ApplicationListener
    lambdaAdminRule: elbv2.ApplicationListenerRule

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            vpc: ec2.Vpc,
            is_sagemaker_studio: bool,
            allowed_ip_v4_address_ranges: List[str],
            allowed_ip_v6_address_ranges: List[str],
            waf_rate_limit_enabled: bool,
            waf_rate_limit_requests: int,
            waf_rate_limit_interval: int,
            host_name: str,
            domain_name: str,
            hosted_zone_id: str,
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create ALB Security Group
        alb_security_group = ec2.SecurityGroup(
            scope,
            "ALBSecurityGroup",
            vpc=vpc,
            description="Security Group for ALB",
            allow_all_outbound=True,
        )
        alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "Allow inbound traffic on port 443",
        )

        # Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(
            scope, "ComfyUIALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group
        )

        # Redirect Load Balancer traffic on port 80 to port 443
        alb.add_redirect(
            source_protocol=elbv2.ApplicationProtocol.HTTP,
            source_port=80,
            target_protocol=elbv2.ApplicationProtocol.HTTPS,
            target_port=443
        )

        # Certificate
        if host_name and domain_name and hosted_zone_id:
            hostedZone = route53.HostedZone.from_hosted_zone_attributes(
                scope,
                "HostedZone",
                hosted_zone_id=hosted_zone_id,
                zone_name=domain_name
            )
            route53.ARecord(
                scope,
                "AliasRecord",
                zone=hostedZone,
                target=route53.RecordTarget.from_alias(
                    route53_targets.LoadBalancerTarget(alb)
                ),
                record_name=f"{host_name}.{domain_name}",
            )
            certificate = acm.Certificate(
                scope,
                "Certificate",
                domain_name=f"{host_name}.{domain_name}",
                validation=acm.CertificateValidation.from_dns(hostedZone),
            )
        else:
            # Add self-signed certificate to the Load Balancer to support https
            cert_function = lambda_.Function(
                scope,
                "RegisterSelfSignedCert",
                handler="function.lambda_handler",
                code=lambda_.Code.from_asset("./comfyui_aws_stack/lambda/cert_lambda", bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_10.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output --platform manylinux_2_12_x86_64 --only-binary=:all: && cp -au . /asset-output",
                    ],
                    platform="linux/amd64",
                    network="sagemaker" if is_sagemaker_studio else None
                )),
                runtime=lambda_.Runtime.PYTHON_3_10,
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
                scope, "SelfSignedCertCustomResourceProvider", on_event_handler=cert_function
            )
            custom_resource = CustomResource(
                scope,
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
                scope, id="SelfSignedCert", certificate_arn=custom_resource.ref
            )

        # WAF: ipv4 ipv6 restriction and rate limiting
        if allowed_ip_v4_address_ranges or allowed_ip_v6_address_ranges or waf_rate_limit_enabled:
            wafRules = []
            rule_priority = 1

            if allowed_ip_v4_address_ranges:
                ipv4 = wafv2.CfnIPSet(
                    scope,
                    "IpV4Set",
                    addresses=allowed_ip_v4_address_ranges,
                    ip_address_version="IPV4",
                    scope="REGIONAL",
                )
                wafRules += [
                    wafv2.CfnWebACL.RuleProperty(
                        name="IpV4SetRule",
                        priority=rule_priority,
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            cloud_watch_metrics_enabled=True,
                            metric_name="IpV4SetRule",
                            sampled_requests_enabled=True,
                        ),
                        statement=wafv2.CfnWebACL.StatementProperty(
                            ip_set_reference_statement={"arn": ipv4.attr_arn}
                        ),
                        action=wafv2.CfnWebACL.RuleActionProperty(
                            allow=wafv2.CfnWebACL.AllowActionProperty(),
                        ),
                    )
                ]
                rule_priority += 1

            if allowed_ip_v6_address_ranges:
                ipv6 = wafv2.CfnIPSet(
                    scope,
                    "IpV6Set",
                    addresses=allowed_ip_v6_address_ranges,
                    ip_address_version="IPV6",
                    scope="REGIONAL",
                )
                wafRules += [
                    wafv2.CfnWebACL.RuleProperty(
                        name="IpV6SetRule",
                        priority=rule_priority,
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            cloud_watch_metrics_enabled=True,
                            metric_name="IpV6SetRule",
                            sampled_requests_enabled=True,
                        ),
                        statement=wafv2.CfnWebACL.StatementProperty(
                            ip_set_reference_statement={"arn": ipv6.attr_arn}
                        ),
                        action=wafv2.CfnWebACL.RuleActionProperty(
                            allow=wafv2.CfnWebACL.AllowActionProperty(),
                        ),
                    )
                ]
                rule_priority += 1

            # Rate limiting rule for /api/prompt path only
            if waf_rate_limit_enabled:
                wafRules += [
                    wafv2.CfnWebACL.RuleProperty(
                        name="RateLimitRule",
                        priority=rule_priority,
                        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                            cloud_watch_metrics_enabled=True,
                            metric_name="RateLimitRule",
                            sampled_requests_enabled=True,
                        ),
                        statement=wafv2.CfnWebACL.StatementProperty(
                            rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                                limit=waf_rate_limit_requests,
                                aggregate_key_type="IP",
                                evaluation_window_sec=waf_rate_limit_interval,
                                scope_down_statement=wafv2.CfnWebACL.StatementProperty(
                                    byte_match_statement=wafv2.CfnWebACL.ByteMatchStatementProperty(
                                        field_to_match=wafv2.CfnWebACL.FieldToMatchProperty(
                                            uri_path={}
                                        ),
                                        positional_constraint="STARTS_WITH",
                                        search_string="/api/prompt",
                                        text_transformations=[
                                            wafv2.CfnWebACL.TextTransformationProperty(
                                                priority=0,
                                                type="NONE"
                                            )
                                        ]
                                    )
                                )
                            )
                        ),
                        action=wafv2.CfnWebACL.RuleActionProperty(
                            block=wafv2.CfnWebACL.BlockActionProperty(),
                        ),
                    )
                ]

            waf = wafv2.CfnWebACL(
                scope,
                "WebACL",
                default_action=wafv2.CfnWebACL.DefaultActionProperty(
                    allow={} if not (
                        allowed_ip_v4_address_ranges or allowed_ip_v6_address_ranges) else None,
                    block={} if (
                        allowed_ip_v4_address_ranges or allowed_ip_v6_address_ranges) else None
                ),
                scope="REGIONAL",
                visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                    cloud_watch_metrics_enabled=True,
                    metric_name="WebACL",
                    sampled_requests_enabled=True,
                ),
                rules=wafRules,
            )
            waf_association = wafv2.CfnWebACLAssociation(
                scope,
                "WebACLAssociation",
                resource_arn=alb.load_balancer_arn,
                web_acl_arn=waf.attr_arn,
            )

        # Output

        self.scope = scope
        self.alb = alb
        self.alb_security_group = alb_security_group
        self.certificate = certificate

    def associate_resources(
            self,
            ecs_target_group: elbv2.ApplicationTargetGroup,
            lambda_admin_target_group: elbv2.ApplicationTargetGroup,
            lambda_restart_docker_target_group: elbv2.ApplicationTargetGroup,
            lambda_shutdown_target_group: elbv2.ApplicationTargetGroup,
            lambda_scaleup_target_group: elbv2.ApplicationTargetGroup,
            lambda_signout_target_group: elbv2.ApplicationTargetGroup,
            user_pool: cognito.UserPool,
            user_pool_client: cognito.UserPoolClient,
            user_pool_custom_domain: cognito.UserPoolDomain,
    ):
        scope = self.scope
        alb = self.alb
        certificate = self.certificate

        # Add listener to the Load Balancer on port 443
        listener = alb.add_listener(
            "Listener",
            certificates=[certificate],
            port=443,
            protocol=elbv2.ApplicationProtocol.HTTPS,
            default_action=elbv2.ListenerAction.forward([ecs_target_group])
        )

        # ALB Rule
        lambda_admin_rule = elbv2.ApplicationListenerRule(
            scope,
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

        lambda_restart_docker_rule = elbv2.ApplicationListenerRule(
            scope,
            "LambdaRestartDockerRule",
            listener=listener,
            priority=10,
            conditions=[elbv2.ListenerCondition.path_patterns(
                ["/admin/restart"])],
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward(
                    [lambda_restart_docker_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
        )

        lambda_shutdown_rule = elbv2.ApplicationListenerRule(
            scope,
            "LambdaShutdownRule",
            listener=listener,
            priority=15,
            conditions=[elbv2.ListenerCondition.path_patterns(
                ["/admin/shutdown"])],
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward(
                    [lambda_shutdown_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
        )

        lambda_scaleup_rule = elbv2.ApplicationListenerRule(
            scope,
            "LambdaScaleupRule",
            listener=listener,
            priority=20,
            conditions=[elbv2.ListenerCondition.path_patterns(
                ["/admin/scaleup"])],
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward(
                    [lambda_scaleup_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
        )

        lambda_signout_rule = elbv2.ApplicationListenerRule(
            scope,
            "LambdaSignoutRule",
            listener=listener,
            priority=25,
            conditions=[elbv2.ListenerCondition.path_patterns(["/signout"])],
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward(
                    [lambda_signout_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
        )

        # Add authentication action as the first priority rule
        auth_rule = listener.add_action(
            "AuthenticateRule",
            priority=30,
            action=elb_actions.AuthenticateCognitoAction(
                next=elbv2.ListenerAction.forward([ecs_target_group]),
                user_pool=user_pool,
                user_pool_client=user_pool_client,
                user_pool_domain=user_pool_custom_domain,
            ),
            conditions=[elbv2.ListenerCondition.path_patterns(["/*"])]
        )

        # Nag

        NagSuppressions.add_resource_suppressions(
            [alb],
            suppressions=[
                {"id": "AwsSolutions-EC23",
                 "reason": "The Security Group and ALB needs to allow 0.0.0.0/0 inbound access for the ALB to be publicly accessible. Additional security is provided via Cognito authentication."
                 },
                {"id": "AwsSolutions-ELB2",
                 "reason": "Adding access logs requires extra S3 bucket so removing it for sample purposes."},
            ],
            apply_to_children=True
        )

        self.listener = listener
        self.lambda_admin_rule = lambda_admin_rule
