import json
import boto3
import os

def handler(event, context):

    scaling_client = boto3.client('autoscaling')
    ecs_client = boto3.client('ecs')
    elbv2_client = boto3.client('elbv2')

    # Retrieve the listener rule ARN from environment variables
    asg_name = os.environ.get('ASG_NAME')
    cluster_name = os.environ['ECS_CLUSTER_NAME']
    service_name = os.environ['ECS_SERVICE_NAME']
    listener_rule_arn = os.environ['LISTENER_RULE_ARN']

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
                # Update the listener rule to redirect to the admin page per default
                elbv2_client.modify_rule(
                    RuleArn=listener_rule_arn,
                    Conditions=[
                        {
                            'Field': 'path-pattern',
                            'Values': ['/admin']
                        }
                    ]
                )

    except Exception as e:
        # Handle any exceptions that occur
        print(f"Error: {e}")
        message = "Error occurred. Unable to modify Listener Rule."

    return {"statusCode": 200}
