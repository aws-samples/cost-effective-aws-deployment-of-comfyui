import json
import boto3
import os

def handler(event, context):

    client = boto3.client('autoscaling')
    elbv2_client = boto3.client('elbv2')

    # Retrieve the listener rule ARN from environment variables
    asg_name = os.environ.get('ASG_NAME')
    listener_rule_arn = os.environ.get('LISTENER_RULE_ARN')

    if not listener_rule_arn:
        return {
            'statusCode': 400,
            'body': json.dumps('Listener Rule ARN not provided')
        }

    try:
        asg_response = client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name]
        )

        desired_capacity = asg_response['AutoScalingGroups'][0]['DesiredCapacity']
        if desired_capacity == 0:
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

    except Exception as e:
        # Handle any exceptions that occur
        print(f"Error: {e}")
        message = "Error occurred. Unable to modify Listener Rule."

    return {"statusCode": 200}
