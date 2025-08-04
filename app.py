#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import Environment
from aws_cdk import Aspects
from comfyui_aws_stack.comfyui_aws_stack import ComfyUIStack
from cdk_nag import AwsSolutionsChecks, NagSuppressions

app = cdk.App()

# CDK コンテキストから値を読み込むヘルパー
def ctx(key):
    return app.node.try_get_context(key)

comfy_ui_stack = ComfyUIStack(
    app, "ComfyUIStack",
    description="ComfyUI on AWS (uksb-ggn3251wsp)",
    env=Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region="us-east-2"
    ),
    tags={
        "Repository": "aws-samples/cost-effective-aws-deployment-of-comfyui"
    },
    instance_type=ctx("instance_type"),
    use_spot=ctx("use_spot"),
    spot_price=ctx("spot_price"),
    auto_scale_down=ctx("auto_scale_down"),
    schedule_auto_scaling=ctx("schedule_auto_scaling"),
    timezone=ctx("timezone"),
    schedule_scale_up=ctx("schedule_scale_up"),
    schedule_scale_down=ctx("schedule_scale_down"),
    self_sign_up_enabled=ctx("self_sign_up_enabled"),
    allowed_sign_up_email_domains=ctx("allowed_sign_up_email_domains"),
    host_name=ctx("host_name"),
    domain_name=ctx("domain_name"),
    hosted_zone_id=ctx("hosted_zone_id"),
    user_pool_id=ctx("user_pool_id"),
    user_pool_client_id=ctx("user_pool_client_id"),
    slack_webhook_url=ctx("slack_webhook_url"),
    user_pool_domain_name=ctx("user_pool_domain_name"),
)

Aspects.of(app).add(AwsSolutionsChecks(verbose=False))
NagSuppressions.add_stack_suppressions(stack=comfy_ui_stack, suppressions=[
    {"id": "AwsSolutions-L1", "reason": "Lambda Runtime is provided by custom resource provider and drain ecs hook implicitely and not critical for sample"},
    {"id": "AwsSolutions-IAM4", "reason": "For sample purposes the managed policy is sufficient"},
    {"id": "AwsSolutions-IAM5", "reason": "Some rules require '*' wildcard as an example ACM operations, and other are sufficient for Sample"},
    {"id": "CdkNagValidationFailure", "reason": "Suppressions for cdk nag"},
])

app.synth()