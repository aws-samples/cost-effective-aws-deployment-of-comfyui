import json
import boto3
import os


def handler(event, context):

    asg_name = os.environ.get("ASG_NAME")

    # Validate environment variables
    if not asg_name:
        return {
            'statusCode': 400,
            'body': json.dumps('ASG name not provided')
        }

    # Clients
    asg_client = boto3.client('autoscaling')

    try:
        # Get the current ASG configuration
        asg_response = asg_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name]
        )

        # Check if the desired capacity is already 1
        desired_capacity = asg_response['AutoScalingGroups'][0]['DesiredCapacity']
        if desired_capacity == 1:
            # Update the desired capacity of the ASG
            response = asg_client.set_desired_capacity(
                AutoScalingGroupName=asg_name,
                DesiredCapacity=0,
                HonorCooldown=False
            )
            message = "ComfyUI is shutting down"
        else:
            message = "ComfyUI is already shutdown"

    except Exception as e:
        # Handle any exceptions that occur
        print(f"Error: {e}")
        message = "Error occurred. Unable to scale ComfyUI."

    return {
        "statusCode": 302,
        "headers": {
            "Location": "/"
        }
    }
