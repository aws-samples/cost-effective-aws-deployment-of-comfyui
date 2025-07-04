from constructs import Construct
from aws_cdk import aws_lambda as lambda_, Duration, custom_resources as cr

class SlackNotificationConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, slack_webhook_url: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Lambda function that posts to Slack
        slack_lambda = lambda_.Function(
            self, "SlackNotifyLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="slack_notify.handler",
            code=lambda_.Code.from_asset("comfyui_aws_stack/lambda/slack_notify_lambda"),
            timeout=Duration.seconds(30),
            environment={
                "SLACK_WEBHOOK_URL": slack_webhook_url
            }
        )

        # Custom resource provider
        slack_provider = cr.Provider(
            self, "SlackNotifyProvider",
            on_event_handler=slack_lambda
        )

        # Expose service token to be used by a CustomResource elsewhere if needed
        self.service_token = slack_provider.service_token

        # 追加: Lambda 関数の参照を公開（他のConstructでの利用用）
        self.slack_lambda = slack_lambda
        self.slack_provider = slack_provider
