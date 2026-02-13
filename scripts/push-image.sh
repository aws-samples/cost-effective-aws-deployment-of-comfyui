#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Pushing ComfyUI Docker Image to ECR${NC}"
echo -e "${GREEN}========================================${NC}"

# Get AWS account and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-$(aws configure get region)}
AWS_REGION=${AWS_REGION:-us-east-1}

echo -e "${YELLOW}AWS Account ID: ${AWS_ACCOUNT_ID}${NC}"
echo -e "${YELLOW}AWS Region: ${AWS_REGION}${NC}"

# Image configuration
IMAGE_NAME="comfyui"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ECR_REPOSITORY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE_NAME}"

echo -e "${YELLOW}Image Name: ${IMAGE_NAME}${NC}"
echo -e "${YELLOW}Image Tag: ${IMAGE_TAG}${NC}"
echo -e "${YELLOW}ECR Repository: ${ECR_REPOSITORY}${NC}"

# Check if ECR repository exists, create if not
echo -e "\n${GREEN}Checking ECR repository...${NC}"
if ! aws ecr describe-repositories --repository-names ${IMAGE_NAME} --region ${AWS_REGION} >/dev/null 2>&1; then
    echo -e "${YELLOW}Creating ECR repository: ${IMAGE_NAME}${NC}"
    aws ecr create-repository \
        --repository-name ${IMAGE_NAME} \
        --region ${AWS_REGION} \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256
    echo -e "${GREEN}ECR repository created successfully!${NC}"
else
    echo -e "${GREEN}ECR repository already exists.${NC}"
fi

# Login to ECR
echo -e "\n${GREEN}Logging in to ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Push the image
echo -e "\n${GREEN}Pushing image to ECR...${NC}"
docker push ${ECR_REPOSITORY}:${IMAGE_TAG}

# Tag as latest if not already
if [ "${IMAGE_TAG}" != "latest" ]; then
    echo -e "\n${GREEN}Tagging image as latest...${NC}"
    docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${ECR_REPOSITORY}:latest
    docker push ${ECR_REPOSITORY}:latest
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Docker image pushed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Image URI: ${ECR_REPOSITORY}:${IMAGE_TAG}"
echo -e "\nYou can now use this image in your CDK deployment."
echo -e "Set the environment variable:"
echo -e "  ${YELLOW}export COMFYUI_IMAGE_URI=${ECR_REPOSITORY}:${IMAGE_TAG}${NC}"

