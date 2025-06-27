#!/bin/bash

set -e

STACK_NAME="ComfyUIStack"

# CloudFormationからECSクラスターとサービス名を取得
echo "🔍 CloudFormationスタックからリソース名を取得中..."
CLUSTER_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name "$STACK_NAME" \
  --query "StackResources[?ResourceType=='AWS::ECS::Cluster'].PhysicalResourceId" \
  --output text)

SERVICE_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name "$STACK_NAME" \
  --query "StackResources[?ResourceType=='AWS::ECS::Service'].PhysicalResourceId" \
  --output text)

if [ -z "$CLUSTER_NAME" ] || [ -z "$SERVICE_NAME" ]; then
  echo "❌ CLUSTER_NAME または SERVICE_NAME を取得できませんでした。"
  exit 1
fi

echo "✅ CLUSTER_NAME: $CLUSTER_NAME"
echo "✅ SERVICE_NAME: $SERVICE_NAME"

echo ""
echo "🕒 最新のECSイベントを取得:"
aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
  --query "services[0].events[?createdAt!=null].[createdAt,message]" --output table

echo ""
echo "📦 ECSサービスのタスク一覧を取得:"
aws ecs list-tasks --cluster "$CLUSTER_NAME" --service-name "$SERVICE_NAME" --output table

echo ""
echo "📦 現在のタスクのステータス確認:"
aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
  --query "services[].{Status: status, Running: runningCount, Desired: desiredCount}" \
  --output table

echo ""
echo "📦 タスク定義を確認:"
TASK_ARN=$(aws ecs list-tasks --cluster "$CLUSTER_NAME" --service-name "$SERVICE_NAME" --output text | awk '{print $2}')
if [ -n "$TASK_ARN" ]; then
  TASK_DEF_ARN=$(aws ecs describe-tasks --cluster "$CLUSTER_NAME" --tasks "$TASK_ARN" \
    --query "tasks[0].taskDefinitionArn" --output text)
  echo "📄 タスク定義ARN: $TASK_DEF_ARN"
  aws ecs describe-task-definition --task-definition "$TASK_DEF_ARN" --query "taskDefinition.containerDefinitions" --output table
else
  echo "⚠️ 実行中のタスクが見つかりませんでした"
fi

echo ""
echo "📜 CloudWatchロググループ一覧（comfyを含むもの）:"
aws logs describe-log-groups \
  --query "logGroups[?contains(logGroupName, 'comfy')].logGroupName" --output table

echo ""
echo "📋 Slack通知のログ確認（Lambdaなど）:"
aws logs describe-log-groups \
  --query "logGroups[?contains(logGroupName, 'Slack') || contains(logGroupName, 'lambda')].logGroupName" --output table

echo ""
echo "💡 ECSサービスやログ設定が不足している可能性があります。CDK定義やログ設定をご確認ください。"

echo "✅ トラブルシューティング完了"