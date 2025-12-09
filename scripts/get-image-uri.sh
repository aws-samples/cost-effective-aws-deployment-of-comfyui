#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get AWS account and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-$(aws configure get region)}
AWS_REGION=${AWS_REGION:-us-east-1}

# Image configuration
IMAGE_NAME="comfyui"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ECR_REPOSITORY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE_NAME}"

echo -e "${GREEN}Current Image URI:${NC}"
echo -e "${YELLOW}${ECR_REPOSITORY}:${IMAGE_TAG}${NC}"

echo -e "\n${GREEN}To use this image in CDK deployment, set:${NC}"
echo -e "${YELLOW}export COMFYUI_IMAGE_URI=${ECR_REPOSITORY}:${IMAGE_TAG}${NC}"

# Check if image exists in ECR
if aws ecr describe-images --repository-name ${IMAGE_NAME} --image-ids imageTag=${IMAGE_TAG} --region ${AWS_REGION} >/dev/null 2>&1; then
    echo -e "\n${GREEN}✓ Image exists in ECR${NC}"
    
    # Get image details
    IMAGE_DETAILS=$(aws ecr describe-images \
        --repository-name ${IMAGE_NAME} \
        --image-ids imageTag=${IMAGE_TAG} \
        --region ${AWS_REGION} \
        --query 'imageDetails[0]' \
        --output json)
    
    IMAGE_SIZE=$(echo $IMAGE_DETAILS | jq -r '.imageSizeInBytes')
    IMAGE_PUSHED=$(echo $IMAGE_DETAILS | jq -r '.imagePushedAt')
    
    # Convert bytes to MB
    IMAGE_SIZE_MB=$((IMAGE_SIZE / 1024 / 1024))
    
    echo -e "${GREEN}Image Size:${NC} ${IMAGE_SIZE_MB} MB"
    echo -e "${GREEN}Pushed At:${NC} ${IMAGE_PUSHED}"
else
    echo -e "\n${YELLOW}⚠ Image does not exist in ECR${NC}"
    echo -e "Build and push the image first:"
    echo -e "  ${YELLOW}make docker-build-push${NC}"
fi

