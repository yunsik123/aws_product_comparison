#!/bin/bash
# ECS Fargate Deployment Script for Nongshim Competitor Compare
# Usage: ./deploy.sh [region]

set -e

# Configuration
AWS_REGION="${1:-ap-northeast-2}"
CLUSTER_NAME="nongshim-cluster"
BACKEND_SERVICE="nongshim-backend-service"
STREAMLIT_SERVICE="nongshim-streamlit-service"
BACKEND_TASK="nongshim-backend-task"
STREAMLIT_TASK="nongshim-streamlit-task"

echo "=== Nongshim Competitor Compare ECS Deployment ==="
echo "Region: $AWS_REGION"
echo ""

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

echo "AWS Account: $AWS_ACCOUNT_ID"
echo "ECR URI: $ECR_URI"
echo ""

# Create ECR repositories if they don't exist
echo "=== Creating ECR Repositories ==="
aws ecr describe-repositories --repository-names nongshim-backend --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name nongshim-backend --region $AWS_REGION

aws ecr describe-repositories --repository-names nongshim-streamlit --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name nongshim-streamlit --region $AWS_REGION

echo "ECR repositories ready."
echo ""

# Login to ECR
echo "=== Logging in to ECR ==="
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI
echo ""

# Build and push images
echo "=== Building Docker Images ==="
cd ../..
docker build -t nongshim-backend:latest -f infra/docker/Dockerfile.backend ./backend
docker build -t nongshim-streamlit:latest -f infra/docker/Dockerfile.streamlit ./streamlit_app

echo "=== Pushing to ECR ==="
docker tag nongshim-backend:latest $ECR_URI/nongshim-backend:latest
docker tag nongshim-streamlit:latest $ECR_URI/nongshim-streamlit:latest
docker push $ECR_URI/nongshim-backend:latest
docker push $ECR_URI/nongshim-streamlit:latest
echo ""

# Create ECS Cluster if not exists
echo "=== Setting up ECS Cluster ==="
aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION | grep -q "ACTIVE" || \
    aws ecs create-cluster --cluster-name $CLUSTER_NAME --region $AWS_REGION

echo "ECS Cluster ready."
echo ""

# Create CloudWatch Log Groups
echo "=== Creating Log Groups ==="
aws logs create-log-group --log-group-name /ecs/nongshim-backend --region $AWS_REGION 2>/dev/null || true
aws logs create-log-group --log-group-name /ecs/nongshim-streamlit --region $AWS_REGION 2>/dev/null || true
echo ""

# Register task definitions
echo "=== Registering Task Definitions ==="

# Backend task definition
cat > /tmp/backend-task.json << EOF
{
    "family": "$BACKEND_TASK",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "256",
    "memory": "512",
    "executionRoleArn": "arn:aws:iam::$AWS_ACCOUNT_ID:role/ecsTaskExecutionRole",
    "containerDefinitions": [
        {
            "name": "backend",
            "image": "$ECR_URI/nongshim-backend:latest",
            "portMappings": [
                {
                    "containerPort": 8000,
                    "protocol": "tcp"
                }
            ],
            "essential": true,
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/nongshim-backend",
                    "awslogs-region": "$AWS_REGION",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "environment": [
                {"name": "AWS_REGION", "value": "$AWS_REGION"}
            ]
        }
    ]
}
EOF

aws ecs register-task-definition --cli-input-json file:///tmp/backend-task.json --region $AWS_REGION

# Streamlit task definition
cat > /tmp/streamlit-task.json << EOF
{
    "family": "$STREAMLIT_TASK",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "256",
    "memory": "512",
    "executionRoleArn": "arn:aws:iam::$AWS_ACCOUNT_ID:role/ecsTaskExecutionRole",
    "containerDefinitions": [
        {
            "name": "streamlit",
            "image": "$ECR_URI/nongshim-streamlit:latest",
            "portMappings": [
                {
                    "containerPort": 8501,
                    "protocol": "tcp"
                }
            ],
            "essential": true,
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/nongshim-streamlit",
                    "awslogs-region": "$AWS_REGION",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "environment": [
                {"name": "BACKEND_URL", "value": "http://backend:8000"}
            ]
        }
    ]
}
EOF

aws ecs register-task-definition --cli-input-json file:///tmp/streamlit-task.json --region $AWS_REGION

echo "Task definitions registered."
echo ""

# Create or update services
echo "=== Creating/Updating ECS Services ==="
echo "NOTE: You need to configure VPC, subnets, and security groups for your environment."
echo ""
echo "Example service creation command:"
echo "aws ecs create-service \\"
echo "    --cluster $CLUSTER_NAME \\"
echo "    --service-name $BACKEND_SERVICE \\"
echo "    --task-definition $BACKEND_TASK \\"
echo "    --desired-count 1 \\"
echo "    --launch-type FARGATE \\"
echo "    --network-configuration 'awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}' \\"
echo "    --region $AWS_REGION"
echo ""

# Cleanup
rm -f /tmp/backend-task.json /tmp/streamlit-task.json

echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Configure VPC, subnets, and security groups"
echo "2. Create an Application Load Balancer (optional)"
echo "3. Create ECS services with proper network configuration"
echo "4. Set up environment variables in AWS Secrets Manager or Parameter Store"
echo ""
echo "Once services are running, access:"
echo "- Backend API: http://<ALB-DNS>:8000/docs"
echo "- Streamlit UI: http://<ALB-DNS>:8501"
