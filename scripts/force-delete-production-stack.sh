#!/bin/bash
#
# force-delete-production-stack.sh
#
# CloudFormationスタックが ROLLBACK_FAILED や DELETE_FAILED 状態でロックされた場合に、
# スタックの「枠」だけを強制的に削除し、クリーンな状態から再デプロイできるようにします。
# 注意: このスクリプトはスタック管理下のAWSリソース（VPC, ALB, EC2等）は削除しません。
#      リソースはAWS上に残存するため、次の `cdk deploy` で再利用されるか、
#      手動でのクリーンアップが必要です。

set -e

# --- 設定 ---
STACK_NAME="ComfyUIStack"
REGION="us-east-1"
PROFILE="default" # 必要に応じてAWSプロファイルを指定

# --- 関数 ---
get_stack_status() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query "Stacks[0].StackStatus" \
    --output text 2>/dev/null || echo "NOT_FOUND"
}

# --- メイン処理 ---
echo "▶️ 本番スタックの強制削除を開始します..."
echo "   - スタック名: $STACK_NAME"
echo "   - リージョン: $REGION"

# 1. スタックの存在確認
STATUS=$(get_stack_status)
if [ "$STATUS" == "NOT_FOUND" ]; then
  echo "✅ スタックは既に存在しません。クリーンアップは不要です。"
  exit 0
fi
echo "ℹ️ 現在のスタック状態: $STATUS"

# 2. 通常の削除を試行 (DELETE_FAILEDに移行させるため)
if [ "$STATUS" != "DELETE_FAILED" ]; then
  echo "⏳ 通常のスタック削除を試行します... (これにより DELETE_FAILED 状態に移行する場合があります)"
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION" --profile "$PROFILE" \
  
  echo "⏳ スタックが DELETE_FAILED 状態になるのを待ちます... (最大5分)"
  for i in {1..60}; do
    STATUS=$(get_stack_status)
    echo "   ...現在の状態: $STATUS"
    if [ "$STATUS" == "DELETE_FAILED" ]; then
      echo "✅ スタックが DELETE_FAILED 状態に移行しました。"
      break
    fi
    if [ "$STATUS" == "NOT_FOUND" ]; then
      echo "✅ スタックは正常に削除されました。強制削除は不要です。"
      exit 0
    fi
    sleep 5
  done
fi

# 3. DELETE_FAILED 状態でなければエラー
STATUS=$(get_stack_status)
if [ "$STATUS" != "DELETE_FAILED" ]; then
  echo "❌ スタックが DELETE_FAILED 状態に移行しませんでした。手動での確認が必要です。"
  exit 1
fi

# 4. 保持するリソースをすべてリストアップ
echo "ℹ️ 削除に失敗したリソースを特定し、保持対象としてリストアップします..."
RETAIN_RESOURCES=$(aws cloudformation list-stack-resources \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --profile "$PROFILE" \
  --query "StackResourceSummaries[?ResourceStatus!='DELETE_COMPLETE'].LogicalResourceId" \
  --output text)

if [ -z "$RETAIN_RESOURCES" ]; then
    echo "❌ 保持するリソースが見つかりませんでした。処理を中断します。"
    exit 1
fi

echo "以下のリソースを保持してスタックを削除します:"
echo "$RETAIN_RESOURCES"

# 5. リソースを保持してスタックを強制削除
echo "⏳ 全リソースを保持する設定で、スタックの強制削除を実行します..."
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --profile "$PROFILE" \
  --retain-resources $RETAIN_RESOURCES

echo "⏳ スタックの完全削除を待ちます..."
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --profile "$PROFILE"

echo "✅ 本番スタック ($STACK_NAME) の枠の削除が完了しました。"
echo "   次の 'cdk deploy' を実行できる状態になりました。"
