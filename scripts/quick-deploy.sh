#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ComfyUI Quick Deploy Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if we should use pre-built image
echo -e "\n${BLUE}Would you like to use a pre-built Docker image?${NC}"
echo -e "This is recommended to avoid timeout issues during deployment."
echo -e "${YELLOW}1) Yes, build and push image first (Recommended)${NC}"
echo -e "2) No, build during CDK deployment"
read -p "Enter your choice (1 or 2): " choice

case $choice in
    1)
        echo -e "\n${GREEN}Building and pushing Docker image...${NC}"
        
        # Build the image
        make docker-build
        
        # Push to ECR
        make docker-push
        
        # Get the image URI
        AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        AWS_REGION=${AWS_REGION:-$(aws configure get region)}
        AWS_REGION=${AWS_REGION:-us-east-1}
        IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui:latest"
        
        echo -e "\n${GREEN}Image built and pushed successfully!${NC}"
        echo -e "Image URI: ${YELLOW}${IMAGE_URI}${NC}"
        
        # Set environment variable
        export COMFYUI_IMAGE_URI=$IMAGE_URI
        
        # Deploy with pre-built image
        echo -e "\n${GREEN}Deploying with pre-built image...${NC}"
        npx cdk deploy
        ;;
    2)
        echo -e "\n${YELLOW}Building image during CDK deployment...${NC}"
        echo -e "${YELLOW}Note: This may take longer and could timeout for slow networks.${NC}"
        
        # Deploy without pre-built image
        npx cdk deploy
        ;;
    *)
        echo -e "${RED}Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nNext steps:"
echo -e "1. Check the AWS Console for your ALB URL"
echo -e "2. Create a Cognito user or configure SAML"
echo -e "3. Access ComfyUI via the ALB URL"
echo -e "\nFor more information, see:"
echo -e "- User Guide: ${YELLOW}docs/USER_GUIDE.md${NC}"
echo -e "- Deploy Options: ${YELLOW}docs/DEPLOY_OPTION.md${NC}"

