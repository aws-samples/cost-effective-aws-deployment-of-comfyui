#!/usr/bin/env python3
import os
import boto3
import aws_cdk as cdk
from aws_cdk import Environment
from aws_cdk import Aspects
from comfyui_aws_stack.comfyui_aws_stack import ComfyUIStack
from cdk_nag import AwsSolutionsChecks, NagSuppressions

app = cdk.App()

# Get AWS account information from credentials
# This uses AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN
# from environment variables
try:
    sts = boto3.client('sts')
    caller_identity = sts.get_caller_identity()
    account = caller_identity['Account']
    # Get region from environment variables or boto3 session
    region = os.environ.get('AWS_DEFAULT_REGION') or boto3.Session().region_name or 'us-east-1'
    print(f"AWS Account: {account}")
    print(f"AWS Region: {region}")
    print(f"AWS ARN: {caller_identity.get('Arn', 'N/A')}")
except Exception as e:
    print(f"Error: Could not retrieve AWS account information: {e}")
    print("Please ensure AWS credentials are properly configured.")
    import sys
    sys.exit(1)

comfy_ui_stack = ComfyUIStack(
    app, "ComfyUIStack",
    description="ComfyUI on AWS (uksb-ggn3251wsp)",
    env=Environment(
        account=account,
        region=region
    ),
    tags={
        "Repository": "aws-samples/cost-effective-aws-deployment-of-comfyui"
    },
    # Override Parameters (example)
    # auto_scale_down=False,
    # schedule_auto_scaling=True,
    # timezone="Asia/Tokyo",
    # schedule_scale_up="0 8 * * 1-5",
    # schedule_scale_down="0 19 * * *",
    # self_sign_up_enabled=True,
    # allowed_sign_up_email_domains=["amazon.com"],
)

Aspects.of(app).add(AwsSolutionsChecks(verbose=False))
NagSuppressions.add_stack_suppressions(stack=comfy_ui_stack, suppressions=[
    {"id": "AwsSolutions-L1", "reason": "Lambda Runtime is provided by custom resource provider and drain ecs hook implicitely and not critical for sample"},
    {"id": "AwsSolutions-IAM4",
        "reason": "For sample purposes the managed policy is sufficient"},
    {"id": "AwsSolutions-IAM5",
        "reason": "Some rules require '*' wildcard as an example ACM operations, and other are sufficient for Sample"},
    {"id": "CdkNagValidationFailure", "reason": "Suppressions for cdk nag"},
])

app.synth()
