#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Updating ECS Service${NC}"
echo -e "${GREEN}========================================${NC}"

# Get AWS account and region
AWS_REGION=${AWS_REGION:-$(aws configure get region)}
AWS_REGION=${AWS_REGION:-us-east-1}

echo -e "${YELLOW}AWS Region: ${AWS_REGION}${NC}"

# Get the ECS cluster and service names from CloudFormation
STACK_NAME=${STACK_NAME:-ComfyUIStack}
echo -e "${YELLOW}Stack Name: ${STACK_NAME}${NC}"

echo -e "\n${GREEN}Getting ECS cluster and service information...${NC}"

# Get cluster name
CLUSTER_NAME=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${AWS_REGION} \
    --query "Stacks[0].Outputs[?OutputKey=='ECSClusterName'].OutputValue" \
    --output text 2>/dev/null)

if [ -z "$CLUSTER_NAME" ] || [ "$CLUSTER_NAME" == "None" ]; then
    echo -e "${RED}Error: Could not find ECS cluster name in CloudFormation outputs.${NC}"
    echo -e "${YELLOW}Attempting to find cluster with ComfyUI prefix...${NC}"
    CLUSTER_NAME=$(aws ecs list-clusters --region ${AWS_REGION} --query 'clusterArns[?contains(@, `ComfyUI`)]' --output text | head -1 | awk -F'/' '{print $NF}')
fi

# Get service name
SERVICE_NAME=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${AWS_REGION} \
    --query "Stacks[0].Outputs[?OutputKey=='ECSServiceName'].OutputValue" \
    --output text 2>/dev/null)

if [ -z "$SERVICE_NAME" ] || [ "$SERVICE_NAME" == "None" ]; then
    echo -e "${RED}Error: Could not find ECS service name in CloudFormation outputs.${NC}"
    echo -e "${YELLOW}Attempting to find service in cluster...${NC}"
    SERVICE_NAME=$(aws ecs list-services --cluster ${CLUSTER_NAME} --region ${AWS_REGION} --query 'serviceArns[0]' --output text | awk -F'/' '{print $NF}')
fi

if [ -z "$CLUSTER_NAME" ] || [ -z "$SERVICE_NAME" ]; then
    echo -e "${RED}Error: Could not determine ECS cluster or service name.${NC}"
    echo -e "${YELLOW}Please ensure the stack is deployed and set the following environment variables:${NC}"
    echo -e "  export CLUSTER_NAME=<your-cluster-name>"
    echo -e "  export SERVICE_NAME=<your-service-name>"
    exit 1
fi

echo -e "${GREEN}Cluster Name: ${CLUSTER_NAME}${NC}"
echo -e "${GREEN}Service Name: ${SERVICE_NAME}${NC}"

# Force new deployment
echo -e "\n${GREEN}Forcing new deployment of ECS service...${NC}"
aws ecs update-service \
    --cluster ${CLUSTER_NAME} \
    --service ${SERVICE_NAME} \
    --force-new-deployment \
    --region ${AWS_REGION} \
    > /dev/null

echo -e "${GREEN}Service update initiated!${NC}"

# Wait for service to stabilize (optional)
echo -e "\n${YELLOW}Waiting for service to stabilize (this may take a few minutes)...${NC}"
echo -e "${YELLOW}Press Ctrl+C to skip waiting and exit.${NC}"

aws ecs wait services-stable \
    --cluster ${CLUSTER_NAME} \
    --services ${SERVICE_NAME} \
    --region ${AWS_REGION} || true

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}ECS Service updated successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Cluster: ${CLUSTER_NAME}"
echo -e "Service: ${SERVICE_NAME}"
echo -e "\nThe service is now running with the latest Docker image."
echo -e "You can check the service status with:"
echo -e "  ${YELLOW}aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${AWS_REGION}${NC}"

