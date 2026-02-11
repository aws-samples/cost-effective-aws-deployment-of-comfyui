# 1. SSM into EC2
aws ssm start-session --target "$(aws ec2 describe-instances --filters "Name=tag:Name,Values=ComfyUIStack/Host" "Name=instance-state-name,Values=running" --query 'Reservations[*].Instances[*].[InstanceId]' --output text)" --region $AWS_DEFAULT_REGION

# 2. SSH into Container
container_id=$(sudo docker container ls --format '{{.ID}} {{.Image}}' | grep 'cdk' | awk '{print $1}')
sudo docker exec -it $container_id /bin/bash

# 3. install models, loras, controlnets or whatever you need (you can also include all in a script and execute it to install)

# SDXL 1.0
wget -c https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors -P ./models/checkpoints/ 

# SDXL Video
wget -c https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt/resolve/main/svd_xt.safetensors -P ./models/checkpoints/

# SDXL Turbo
wget -c https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0.safetensors -P ./models/checkpoints/

# Blue Pencil XL
wget -c https://huggingface.co/bluepen5805/blue_pencil-XL/resolve/main/blue_pencil-XL-v2.0.0.safetensors -P ./models/checkpoints/ 
# Redmond V2 Lineart
wget -c https://huggingface.co/artificialguybr/LineAniRedmond-LinearMangaSDXL-V2/resolve/main/LineAniRedmondV2-Lineart-LineAniAF.safetensors -P ./models/checkpoints/ 

# LOGO Style
wget -c https://huggingface.co/artificialguybr/LogoRedmond-LogoLoraForSDXL-V2/resolve/main/LogoRedmondV2-Logo-LogoRedmAF.safetensors -P ./models/checkpoints/ 

# Sticker Style
wget -c https://huggingface.co/artificialguybr/StickersRedmond/resolve/main/StickersRedmond.safetensors -P ./models/checkpoints/ 

# T-shirt style
wget -c https://huggingface.co/artificialguybr/TshirtDesignRedmond-V2/resolve/main/TShirtDesignRedmondV2-Tshirtdesign-TshirtDesignAF.safetensors -P ./models/checkpoints/ 

# Negative Prompt Styles
wget -c https://civitai.com/api/download/models/245812 -P ./models/checkpoints/ 

# VAE
wget -c https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors -P ./models/checkpoints/ 

# Animatediff & custom nodes
wget -c https://huggingface.co/guoyww/animatediff/resolve/main/mm_sdxl_v10_beta.ckpt -P ./models/checkpoints/

# SDVN6-RealXL
wget -c https://civitai.com/api/download/models/134461 -O ./models/checkpoints/SDVN6-RealXL.safetensors

# DreamShaper XL
wget -c https://civitai.com/api/download/models/251662 -O ./models/checkpoints/DreamShaperXL.safetensors 

# FACE SWAP EXAMPLE Upscaler - https://huggingface.co/ai-forever/Real-ESRGAN
wget -c https://huggingface.co/ai-forever/Real-ESRGAN/blob/main/RealESRGAN_x2.pth -P ./models/upscale_models/
