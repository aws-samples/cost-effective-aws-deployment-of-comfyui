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

    except Exception as e:
        # Handle any exceptions that occur
        print(f"Error: {e}")
        message = "Error occurred. Unable to scale ComfyUI."

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="X-UA-Compatible" content="ie=edge">
        <!-- <meta http-equiv="refresh" content="0; URL=https://www.youtube.com/watch?v=dQw4w9WgXcQ" /> -->
        <title>My Website</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #202020;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                color: #333;
            }}
            main {{
                text-align: center;
                background-color: #ffffff;
                padding: 40px;
                border-radius: 5px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                max-width: 600px;
            }}
            h1 {{
                margin-bottom: 20px;
            }}
            p {{
                margin-bottom: 30px;
            }}
            .video-link {{
                display: inline-block;
                background-color: #54646f;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 2px;
                transition: background-color 0.3s ease;
            }}
            .video-link:hover {{
                background-color: #005fa3;
            }}
        </style>
    </head>
    <body>
        <main>
            <h1>{message}</h1>
            <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ" class="video-link" target="_blank">Watch Video</a>  
        </main>
    </body>
    </html>
    """

    return {"statusCode": 200, "body": html, "headers": {"Content-Type": "text/html"}}
