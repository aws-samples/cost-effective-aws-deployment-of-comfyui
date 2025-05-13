#!/bin/bash

set -e  # エラーで即終了

VENV_PATH="/home/user/opt/ComfyUI/.venv"
COMFYUI_PATH="/home/user/opt/ComfyUI"
MODEL_DL_SCRIPT="$COMFYUI_PATH/basemodels.sh"  # ダウンロードスクリプトのパス
PORT=8181

# Slack通知関数
notify_slack() {
  if [ ! -z "$SLACK_WEBHOOK_URL" ]; then
    curl -s -X POST -H 'Content-type: application/json' \
      --data "{\"text\":\"$1\"}" "$SLACK_WEBHOOK_URL" > /dev/null
  fi
}

# 通知: 初回起動
notify_slack "🚀 ComfyUI 初回起動中...（$HOSTNAME）"

# ComfyUI 起動（バックグラウンド）
source "$VENV_PATH/bin/activate"
python "$COMFYUI_PATH/main.py" \
  --listen 0.0.0.0 \
  --port $PORT \
  --output-directory "$COMFYUI_PATH/output/" &
MAIN_PID=$!

# 数秒待って起動確認
sleep 5

# モデル・ワークフロー等のダウンロード
if [ -f "$MODEL_DL_SCRIPT" ]; then
  chmod +x "$MODEL_DL_SCRIPT"
  bash "$MODEL_DL_SCRIPT"
else
  echo "⚠️ モデルダウンロードスクリプトが見つかりません: $MODEL_DL_SCRIPT"
fi

# 通知: 再起動予告
notify_slack "♻️ モデルダウンロード完了 → ComfyUI を再起動します（$HOSTNAME）"

# ComfyUIプロセスを終了させてコンテナ自動再起動（ECSやDockerのRestartPolicy任せ）
kill -SIGTERM "$MAIN_PID"
