import aws_cdk as cdk
from aws_cdk.assertions import Template

from comfyui_aws_stack.comfyui_aws_stack import ComfyUIStack

def test_comfyui_aws_stack_snapshot(snapshot):
    app = cdk.App()
    stack = ComfyUIStack(
        app, 
        "ComfyUIStack", 
        env=cdk.Environment(account="123456789012", region="us-east-1")
    )

    template = Template.from_stack(stack)
    assert template.to_json() == snapshot
