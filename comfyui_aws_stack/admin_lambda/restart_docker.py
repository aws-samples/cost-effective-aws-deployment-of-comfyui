import boto3
import os

def send_docker_restart_command(instance_id):
    ssm_client = boto3.client('ssm')
    command = "sudo systemctl restart docker"
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': [command]}
    )
    return response['Command']['CommandId']

def handler(event, context):

    asg_name = os.environ.get("ASG_NAME")
    cluster_name = os.environ.get("ECS_CLUSTER_NAME")
    service_name = os.environ.get("ECS_SERVICE_NAME")
    listener_rule_arn = os.environ.get('LISTENER_RULE_ARN')

    ecs_client = boto3.client('ecs')
    scaling_client = boto3.client('autoscaling')
    elbv2_client = boto3.client('elbv2')

    try:
        asg_response = scaling_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name]
        )

        desired_capacity = asg_response['AutoScalingGroups'][0]['DesiredCapacity']
        if desired_capacity == 1:
            # Check if the service has the expected number of RUNNING tasks
            response = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            running_count = response['services'][0]['runningCount']
            if running_count >= 1:
                instances = asg_response['AutoScalingGroups'][0]['Instances']
                # Assuming max capacity of 1, get the first instance ID
                if instances:
                    instance_id = instances[0]['InstanceId']
                    command_id = send_docker_restart_command(instance_id)      
                    # Update the listener rule to redirect to the admin page per default
                    elbv2_client.modify_rule(
                        RuleArn=listener_rule_arn,
                        Conditions=[
                            {
                                'Field': 'path-pattern',
                                'Values': ['/','/admin']
                            }
                        ]
                    )
                    message = f"Docker restart command sent. Command ID: {command_id}"
                else:
                    message = "No running instance found for ASG"
    except Exception as e:
        message = f"Error: {str(e)}"

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
            <p>{message}</p>
        </main>
    </body>
    </html>
    """

    return {"statusCode": 200, "body": html, "headers": {"Content-Type": "text/html"}}
