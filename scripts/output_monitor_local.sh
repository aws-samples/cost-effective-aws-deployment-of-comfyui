#!/bin/bash
# Gemini Local Monitoring Loop
# To stop this script, run: pkill -f output_monitor_local.sh

INSTANCE_ID="i-008b97e8d557f9208"
REGION="us-east-1"
TARGET_DIR="/home/user/opt/ComfyUI/output"
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/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"
LAST_FILE_PATH="/tmp/gemini_last_file.txt"
CHECK_INTERVAL=5

echo "Gemini監視ループ、起動。$(date)"
touch "${LAST_FILE_PATH}" # 初回実行のためにファイルを作成

while true; do
  # 1. コンテナ内の最新ファイル名を取得するコマンドを送信
  COMMAND_ID=$(aws ssm send-command \
    --instance-ids "${INSTANCE_ID}" \
    --document-name "AWS-RunShellScript" \
    --parameters "{\"commands\":[\"docker exec c6b0caae3c95 ls -t ${TARGET_DIR} | head -n 1\"]}" \
    --query "Command.CommandId" \
    --output text \
    --region "${REGION}")

  # 少し待つ
  sleep 2

  # 2. コマンドの実行結果（ファイル名）を取得
  LATEST_FILE=$(aws ssm get-command-invocation \
    --command-id "${COMMAND_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --query "StandardOutputContent" \
    --output text \
    --region "${REGION}" | tr -d '[:space:]') # 改行などを削除

  # 3. 前回のファイル名と比較
  LAST_FILE=$(cat "${LAST_FILE_PATH}" | tr -d '[:space:]')

  if [[ -n "${LATEST_FILE}" && "${LATEST_FILE}" != "${LAST_FILE}" ]]; then
    echo "新しいファイルを発見！: ${LATEST_FILE} at $(date)" \
    
    # VRAMとDisk情報を取得するコマンドを送信・実行
    STATS_COMMAND_ID=$(aws ssm send-command \
      --instance-ids "${INSTANCE_ID}" \
      --document-name "AWS-RunShellScript" \
      --parameters "{\"commands\":[\"docker exec c6b0caae3c95 nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits | awk '{printf \\\"%.0f/%.0f MiB\", \\$1, \\$2}'\",\"docker exec c6b0caae3c95 df -h ${TARGET_DIR} | awk 'NR==2 {print \\$3 \\\"/\\\" \\$2 \\" (\\\" \\$5 \\\" used)\\\"}'\"]}" \
      --query "Command.CommandId" \
      --output text \
      --region "${REGION}") \
    
    sleep 2
    
    STATS_OUTPUT=$(aws ssm get-command-invocation \
      --command-id "${STATS_COMMAND_ID}" \
      --instance-id "${INSTANCE_ID}" \
      --query "StandardOutputContent" \
      --output text \
      --region "${REGION}") \
      
    VRAM_INFO=$(echo "${STATS_OUTPUT}" | head -n 1)
    DISK_INFO=$(echo "${STATS_OUTPUT}" | tail -n 1)
    
    IMAGE_URL="https://comfyui.aicu.jp/view?filename=${LATEST_FILE}&type=output&subfolder="
    
    JSON_PAYLOAD="{\"text\": \"🎨 新画像: ${LATEST_FILE}\\nVRAM: ${VRAM_INFO}\\nDisk: ${DISK_INFO}\\nURL: ${IMAGE_URL}\"}"
    
    # 4. Slackに通知
    curl -s -X POST -H 'Content-type: application/json' --data "${JSON_PAYLOAD}" "${SLACK_WEBHOOK_URL}"
    
    # 5. 最終ファイル名を更新
    echo "${LATEST_FILE}" > "${LAST_FILE_PATH}"
  fi

  sleep "${CHECK_INTERVAL}"
done
