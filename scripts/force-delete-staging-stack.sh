#!/bin/bash
#
# force-delete-staging-stack.sh
#
# CloudFormationスタックが ROLLBACK_FAILED や DELETE_FAILED 状態でロックされた場合に、
# スタックの「枠」だけを強制的に削除し、クリーンな状態から再デプロイできるようにします。

set -e

# --- 設定 ---
STACK_NAME="ComfyUIStack"
REGION="us-east-2"
PROFILE="default"

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
echo "▶️ ステージングスタックの強制削除を開始します..."
echo "   - スタック名: $STACK_NAME"
echo "   - リージョン: $REGION"

STATUS=$(get_stack_status)
if [ "$STATUS" == "NOT_FOUND" ]; then
  echo "✅ スタックは既に存在しません。クリーンアップは不要です。"
  exit 0
fi
echo "ℹ️ 現在のスタック状態: $STATUS"

# ROLLBACK_FAILED の場合は、まず通常の削除を試みて DELETE_FAILED に移行させる
if [ "$STATUS" == "ROLLBACK_FAILED" ]; then
  echo "⏳ スタックが ROLLBACK_FAILED のため、通常の削除を試行して DELETE_FAILED に移行させます..."
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION" --profile "$PROFILE"
  echo "⏳ DELETE_FAILED 状態になるのを待ちます... (最大5分)"
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

# DELETE_FAILED 状態でなければエラー
STATUS=$(get_stack_status)
if [ "$STATUS" != "DELETE_FAILED" ]; then
  echo "❌ スタックが DELETE_FAILED 状態に移行しませんでした。手動での確認が必要です。"
  exit 1
fi

echo "ℹ️ 削除に失敗したリソースを特定し、保持対象としてリストアップします..."
RETAIN_RESOURCES=$(aws cloudformation list-stack-resources \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --profile "$PROFILE" \
  --query "StackResourceSummaries[?ResourceStatus!='DELETE_COMPLETE'].LogicalResourceId" \
  --output text)

if [ -z "$RETAIN_RESOURCES" ]; then
    echo "⚠️ 保持するリソースが見つかりませんでした。スタックの削除を試みますが、リソースが残存する可能性があります。"
    RETAIN_RESOURCES="" # 引数を空にする
else
    echo "以下のリソースを保持してスタックを削除します:"
    echo "$RETAIN_RESOURCES"
fi

echo "⏳ 全リソースを保持する設定で、スタックの強制削除を実行します..."
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --profile "$PROFILE" \
  $(if [ -n "$RETAIN_RESOURCES" ]; then echo "--retain-resources $RETAIN_RESOURCES"; fi)

echo "⏳ スタックの完全削除を待ちます..."
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --profile "$PROFILE"

echo "✅ ステージングスタック ($STACK_NAME) の枠の削除が完了しました。"
