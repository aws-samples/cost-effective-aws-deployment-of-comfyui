FROM nvidia/cuda:12.3.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=America/Los_Angeles

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev git git-lfs  \
    ffmpeg libsm6 libxext6 cmake libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

# awscli のインストール（Slack通知前に使うため）
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && ./aws/install


# Create and switch to a new user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
RUN mkdir -p /home/user/opt/ComfyUI && chown -R user /home/user/opt/ComfyUI

# Pyenv and Python setup
RUN curl https://pyenv.run | bash
ENV PATH=$HOME/.pyenv/shims:$HOME/.pyenv/bin:$PATH
ENV PYTHON_VERSION=3.10.12
RUN pyenv install $PYTHON_VERSION && \
    pyenv global $PYTHON_VERSION && \
    pyenv rehash && \
    pip install --no-cache-dir --upgrade pip setuptools wheel 

# Set the working directory
WORKDIR /home/user/opt/ComfyUI

# Clone ComfyUI directly into /home/user/opt/ComfyUI
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI .

# Create a Python virtual environment in a directory
ENV TEMP_VENV_PATH=/home/user/opt/ComfyUI/.venv
RUN python -m venv $TEMP_VENV_PATH

RUN . $TEMP_VENV_PATH/bin/activate && pip install xformers!=0.0.18 --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121

# Clone ComfyUI-Manager and install its requirements
RUN mkdir -p custom_nodes/ComfyUI-Manager && \
    git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Manager custom_nodes/ComfyUI-Manager && \
    . $TEMP_VENV_PATH/bin/activate && pip install --no-cache-dir --upgrade torch torchvision GitPython && \
    pip install -r custom_nodes/ComfyUI-Manager/requirements.txt
    
# カスタムノード追加
RUN cd ./custom_nodes && \
    git clone https://github.com/yhayano-ponotech/comfyui-save-image-local.git

# Slack通知: basemodels.txt ダウンロード前
ARG SLACK_WEBHOOK_URL
RUN if [ ! -z "$SLACK_WEBHOOK_URL" ]; then \
      curl -s -X POST -H 'Content-type: application/json' \
      --data "{\"text\":\"📦 Dockerビルド中: モデルダウンロード準備中\"}" \
      "$SLACK_WEBHOOK_URL"; \
    fi

# Book-SD-MasterGuide リポジトリから basemodels.txt を取得
WORKDIR /home/user/opt/
RUN git clone https://github.com/aicuai/Book-SD-MasterGuide.git

# モデル保存先作成とbasemodels.sh実行
WORKDIR /home/user/opt/ComfyUI
RUN mkdir -p models/checkpoints models/vae && \
    cp /home/user/opt/Book-SD-MasterGuide/basemodels.txt ./basemodels.sh && \
    bash ./basemodels.sh

# Copy the configuration file
COPY comfyui_config/extra_model_paths.yaml ./extra_model_paths.yaml

CMD ["bash", "-c", "source /home/user/opt/ComfyUI/.venv/bin/activate && exec python /home/user/opt/ComfyUI/main.py --listen 0.0.0.0 --port 8181 --output-directory /home/user/opt/ComfyUI/output/"]
