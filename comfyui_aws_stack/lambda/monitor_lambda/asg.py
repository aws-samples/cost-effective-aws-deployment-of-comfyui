import boto3
import os
import json


def handler(event, context):
    asg_name = os.environ['ASG_NAME']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']

    # イベントBridgeからのイベントを解析
    print(f"Received event: {json.dumps(event)}")

    # イベントタイプを取得
    detail_type = event.get('detail-type', '')

    # エラー関連のイベントタイプのリスト
    error_event_types = [
        "EC2 Instance Launch Unsuccessful",
        "EC2 Instance Terminate Unsuccessful",
        "EC2 Auto Scaling Instance Launch Error",
        "EC2 Auto Scaling Instance Terminate Error",
        "EC2 Auto Scaling Group Launch Error"
    ]

    # イベントがエラー関連かチェック
    if detail_type in error_event_types:
        # イベント詳細を取得
        detail = event.get('detail', {})
        cause = detail.get('Cause', 'Unknown cause')
        status_message = detail.get('StatusMessage', 'No status message')
        request_id = detail.get('RequestId', 'Unknown')
        activity_id = detail.get('ActivityId', 'Unknown')

        # SNSクライアントを初期化
        sns = boto3.client('sns')

        # エラーメッセージを構築
        message = {
            'default': f"ASG Scaling Event Error: {detail_type} - {cause}",
            'sms': f"ASG Error: {detail_type}",
            'email': f"""ASG Scaling Event Error\n\n
Event Type: {detail_type}
Cause: {cause}
Status Message: {status_message}
Request ID: {request_id}
Activity ID: {activity_id}
ASG: {asg_name}"""
        }

        # SNS通知を送信
        sns.publish(
            TopicArn=sns_topic_arn,
            Message=json.dumps(message),
            Subject=f"ASG Scaling Event Error - {asg_name}",
            MessageStructure='json'
        )

        print(f"Published error notification for event: {detail_type}")
    else:
        print(f"Non-error event received, no notification sent: {detail_type}")

    return {
        'statusCode': 200,
        'body': json.dumps('ASG event processing completed')
    }
