#!/bin/bash

set -e  # エラーで即終了
exec > >(tee -a /tmp/entrypoint.log) 2>&1
set -x

VENV_PATH="/home/user/opt/ComfyUI/.venv"
COMFYUI_PATH="/home/user/opt/ComfyUI"
MASTER_GUIDE_PATH="/home/user/opt/Book-SD-MasterGuide"
MODEL_DL_SCRIPT="$MASTER_GUIDE_PATH/basemodels.sh"  # ダウンロードスクリプトのパス
RES_DL_SCRIPT="$MASTER_GUIDE_PATH/SharedComfy.sh" # 追加ファイルのパス
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

# venv存在チェック（なければSlack通知＋終了）
if [ ! -f "$VENV_PATH/bin/activate" ]; then
  echo "❌ Python venv ($VENV_PATH) が見つかりません！"
  notify_slack "❌ Python venv ($VENV_PATH) が見つかりません（$HOSTNAME）"
  exit 2
fi

python "$COMFYUI_PATH/main.py" \
  --listen 0.0.0.0 \
  --port $PORT \
  --output-directory "$COMFYUI_PATH/output/" &
MAIN_PID=$!

# 数秒待って起動確認
sleep 5

# baseモデルのダウンロード
if [ -f "$MODEL_DL_SCRIPT" ]; then
  chmod +x "$MODEL_DL_SCRIPT"
  bash "$MODEL_DL_SCRIPT"
else
  echo "⚠️ モデルダウンロードスクリプトが見つかりません: $MODEL_DL_SCRIPT"
fi
# 追加モデル・ワークフロー等のダウンロード
if [ -f "$RES_DL_SCRIPT" ]; then
  chmod +x "$RES_DL_SCRIPT"
  bash "$RES_DL_SCRIPT"
else
  echo "⚠️ 追加ファイルインストールスクリプトが見つかりません: $RES_DL_SCRIPT"
fi



# 通知: 再起動予告
notify_slack "♻️ 追加モデル、追加ファイルのダウンロード完了 → ComfyUI を再起動します（$HOSTNAME）"

# ComfyUIプロセスを終了させてコンテナ自動再起動（ECSやDockerのRestartPolicy任せ）
kill -SIGTERM "$MAIN_PID"
