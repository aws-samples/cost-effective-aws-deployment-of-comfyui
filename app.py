#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import Environment
from aws_cdk import Aspects
from comfyui_aws_stack.comfyui_aws_stack import ComfyUIStack
from cdk_nag import AwsSolutionsChecks, NagSuppressions

app = cdk.App()
comfy_ui_stack = ComfyUIStack(app, "ComfyUIStack",
                              env = Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"],
                                                region=os.environ["CDK_DEFAULT_REGION"])
    )

Aspects.of(app).add(AwsSolutionsChecks(verbose=False))
NagSuppressions.add_stack_suppressions( stack=comfy_ui_stack, suppressions=[
    { "id": "AwsSolutions-IAM4", "reason": "For sample purposes the managed policy is sufficient"},
    { "id": "AwsSolutions-IAM5", "reason": "Some rules require '*' wildcard as an example ACM operations, and other are sufficient for Sample"}])

app.synth()
