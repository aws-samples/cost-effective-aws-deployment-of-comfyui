from aws_cdk import (
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    Duration,
    CustomResource,
    aws_lambda as lambda_,
    custom_resources as cr,
    aws_cognito as cognito,
)
from constructs import Construct

import json
import urllib
from typing import List


class AuthConstruct(Construct):
    user_pool: cognito.UserPool
    user_pool_client: cognito.UserPoolClient
    user_pool_custom_domain: cognito.UserPoolDomain
    application_dns_name: str

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            alb: elbv2.ApplicationLoadBalancer,
            lambda_role: iam.Role,
            suffix: str,
            host_name: str,
            domain_name: str,
            saml_auth_enabled: bool,
            self_sign_up_enabled: bool,
            mfa_required: bool,
            allowed_sign_up_email_domains: List[str],
            **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Sets up the cognito infrastructure with the user pool, custom domain and app client for use by the ALB.
        cognito_custom_domain = f"comfyui-alb-auth-{suffix}"
        application_dns_name = f"{host_name}.{domain_name}" if host_name and domain_name else alb.load_balancer_dns_name

        # Create the user pool that holds our users
        user_pool = cognito.UserPool(
            scope,
            "ComfyUIuserPool",
            account_recovery=cognito.AccountRecovery.EMAIL_AND_PHONE_WITHOUT_MFA,
            auto_verify=cognito.AutoVerifiedAttrs(email=True, phone=True),
            self_sign_up_enabled=False if saml_auth_enabled else self_sign_up_enabled,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(mutable=True, required=True),
                given_name=cognito.StandardAttribute(
                    mutable=True, required=True),
                family_name=cognito.StandardAttribute(
                    mutable=True, required=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=True),
            mfa=cognito.Mfa.REQUIRED if not saml_auth_enabled and mfa_required else cognito.Mfa.OPTIONAL,
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

        # Auth Lambda
        if allowed_sign_up_email_domains is not None:
            checkEmailDomainFunction = lambda_.Function(
                scope,
                "checkEmailDomainFunction",
                runtime=lambda_.Runtime.PYTHON_3_12,
                role=lambda_role,
                handler="check_email_domain.handler",
                code=lambda_.Code.from_asset(
                    "./comfyui_aws_stack/lambda/auth_lambda"),
                timeout=Duration.seconds(amount=60),
                environment={
                    "ALLOWED_SIGN_UP_EMAIL_DOMAINS_STR": json.dumps(allowed_sign_up_email_domains),
                }
            )
            user_pool.add_trigger(
                cognito.UserPoolOperation.PRE_SIGN_UP,
                checkEmailDomainFunction
            )

        # Cognito Post Deploy fix
        post_process_function = lambda_.Function(
            scope,
            "UpdateCognitoCallbackUrlFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                "./comfyui_aws_stack/lambda/post_process_lambda"),
            handler="function.lambda_handler",
            environment={
                "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
                "COGNITO_CLIENT_ID": user_pool_client.user_pool_client_id,
            },
        )
        post_process_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:DescribeUserPoolClient",
                    "cognito-idp:UpdateUserPoolClient",
                ],
                resources=["*"],
            )
        )
        post_process_provider = cr.Provider(
            scope, "UpdateCognitoCallbackUrlProvider",
            on_event_handler=post_process_function,
        )
        CustomResource(
            scope, "UpdateCognitoCallbackUrl",
            service_token=post_process_provider.service_token,
        )

        # Output

        self.user_pool = user_pool
        self.user_pool_client = user_pool_client
        self.user_pool_custom_domain = user_pool_custom_domain
        self.application_dns_name = application_dns_name
