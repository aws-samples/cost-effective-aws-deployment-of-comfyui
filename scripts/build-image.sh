#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Building ComfyUI Docker Image${NC}"
echo -e "${GREEN}========================================${NC}"

# Get AWS account and region (optional for local build)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
AWS_REGION=${AWS_REGION:-$(aws configure get region 2>/dev/null || echo "")}
AWS_REGION=${AWS_REGION:-us-east-1}

# Image configuration
IMAGE_NAME="comfyui"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if [ -n "$AWS_ACCOUNT_ID" ]; then
    ECR_REPOSITORY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE_NAME}"
    echo -e "${YELLOW}AWS Account ID: ${AWS_ACCOUNT_ID}${NC}"
    echo -e "${YELLOW}AWS Region: ${AWS_REGION}${NC}"
    echo -e "${YELLOW}ECR Repository: ${ECR_REPOSITORY}${NC}"
else
    echo -e "${YELLOW}AWS credentials not configured - building image locally only${NC}"
    ECR_REPOSITORY=""
fi

echo -e "${YELLOW}Image Name: ${IMAGE_NAME}${NC}"
echo -e "${YELLOW}Image Tag: ${IMAGE_TAG}${NC}"

# Build the Docker image
echo -e "\n${GREEN}Building Docker image...${NC}"
cd comfyui_aws_stack/docker

# Use current timestamp to bust cache and ensure latest version
CACHEBUST=$(date +%s)

if [ -n "$ECR_REPOSITORY" ]; then
    docker build \
      --platform linux/amd64 \
      --build-arg CACHEBUST=${CACHEBUST} \
      -t ${IMAGE_NAME}:${IMAGE_TAG} \
      -t ${ECR_REPOSITORY}:${IMAGE_TAG} \
      .
else
    docker build \
      --platform linux/amd64 \
      --build-arg CACHEBUST=${CACHEBUST} \
      -t ${IMAGE_NAME}:${IMAGE_TAG} \
      .
fi

cd ../..

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Docker image built successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
if [ -n "$ECR_REPOSITORY" ]; then
    echo -e "ECR Tag: ${ECR_REPOSITORY}:${IMAGE_TAG}"
    echo -e "\nNext steps:"
    echo -e "  1. Push to ECR: ${YELLOW}make docker-push${NC}"
    echo -e "  2. Or build and push: ${YELLOW}make docker-build-push${NC}"
else
    echo -e "\n${YELLOW}Note: AWS credentials not configured.${NC}"
    echo -e "To push to ECR, please configure AWS credentials and rebuild."
fi

