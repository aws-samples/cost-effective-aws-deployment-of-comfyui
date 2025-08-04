#!/bin/bash
TARGET_DIR="/home/user/opt/ComfyUI/output"
BASE_URL="https://comfyui.aicu.jp"
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/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"
CHECK_INTERVAL=5

# スクリプト起動時に一度だけ通知を送信
curl -s -X POST -H 'Content-type: application/json' --data '{"text": "🚀 監視スクリプト、起動しました！これから張り込みを開始します！"}' "${SLACK_WEBHOOK_URL}"

LAST_NOTIFIED_FILE=""

while true; do
  LATEST_FILE=$(ls -t "${TARGET_DIR}" 2>/dev/null | head -n 1)
  if [[ -n "${LATEST_FILE}" && "${LATEST_FILE}" != "${LAST_NOTIFIED_FILE}" ]]; then
    LAST_NOTIFIED_FILE="${LATEST_FILE}"
    VRAM_INFO=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits | awk '{printf "%.0f/%.0f MiB", $1, $2}')
    DISK_INFO=$(df -h "${TARGET_DIR}" | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')
    IMAGE_URL="${BASE_URL}/view?filename=${LATEST_FILE}&type=output&subfolder="
    
    # シンプルなテキスト形式のペイロード
    JSON_PAYLOAD="{\"text\": \"🎨 新画像: ${LATEST_FILE}\\nVRAM: ${VRAM_INFO}\\nDisk: ${DISK_INFO}\\nURL: ${IMAGE_URL}\"}"
    
    curl -s -X POST -H 'Content-type: application/json' --data "${JSON_PAYLOAD}" "${SLACK_WEBHOOK_URL}"
  fi
  sleep ${CHECK_INTERVAL}
done
