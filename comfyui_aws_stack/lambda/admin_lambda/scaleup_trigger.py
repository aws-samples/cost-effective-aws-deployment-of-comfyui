import json
import boto3
import os


def handler(event, context):

    asg_name = os.environ.get("ASG_NAME")
    ecs_cluster_name = os.environ.get("ECS_CLUSTER_NAME")
    ecs_service_name = os.environ.get("ECS_SERVICE_NAME")

    # Clients
    asg_client = boto3.client('autoscaling')
    ecs_client = boto3.client('ecs')
    try:
        # Get the current ASG configuration
        asg_response = asg_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name]
        )
        desired_capacity = asg_response['AutoScalingGroups'][0]['DesiredCapacity']

        # Get the current status of ECS service
        ecs_response = ecs_client.describe_services(
            cluster=ecs_cluster_name,
            services=[ecs_service_name]
        )
        current_service_desired_count = ecs_response['services'][0]['desiredCount']
        running_tasks_count = ecs_response['services'][0]['runningCount']

        if desired_capacity < 1:
            # Update the desired capacity of the ASG
            response = asg_client.set_desired_capacity(
                AutoScalingGroupName=asg_name,
                DesiredCapacity=1,
                HonorCooldown=False
            )

            # Update ECS Service Desired Count
            ecs_response = ecs_client.describe_services(
                cluster=ecs_cluster_name,
                services=[ecs_service_name]
            )
            current_service_desired_count = ecs_response['services'][0]['desiredCount']

            # Increment ECS Service Desired Count
            if current_service_desired_count < 1:
                ecs_client.update_service(
                    cluster=ecs_cluster_name,
                    service=ecs_service_name,
                    desiredCount=1
                )

            message = """ComfyUI is triggered to scale up again.
                         Please refresh in 5-10 minutes."""
        elif desired_capacity == 1 and running_tasks_count < 1:
            message = """ComfyUI is currently scaling back up. 
                         Please refresh in 5-8 minutes."""
        elif desired_capacity == 1 and running_tasks_count == 1:
            message = "ComfyUI is already up and running."
        else:
            message = "ComfyUI is in an unexpected state."
        print(f"Debug: {message}")

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
