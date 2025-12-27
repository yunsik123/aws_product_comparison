# Makefile for Nongshim Competitor Compare

.PHONY: help install run test lint clean build push deploy logs

# Default region for AWS deployment
AWS_REGION ?= ap-northeast-2
AWS_ACCOUNT_ID ?= $(shell aws sts get-caller-identity --query Account --output text)
ECR_REPO_BACKEND = nongshim-backend
ECR_REPO_STREAMLIT = nongshim-streamlit
IMAGE_TAG ?= latest

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make run        - Run locally with docker-compose"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linter"
	@echo "  make clean      - Clean up containers and cache"
	@echo "  make build      - Build Docker images"
	@echo "  make push       - Push images to ECR"
	@echo "  make deploy     - Deploy to AWS ECS"
	@echo "  make logs       - View ECS logs"

install:
	cd backend && pip install -r requirements.txt
	cd streamlit_app && pip install -r requirements.txt
	pip install pytest pytest-asyncio

run:
	docker-compose up --build

run-dev:
	@echo "Starting backend..."
	cd backend && uvicorn app.main:app --reload --port 8000 &
	@echo "Starting streamlit..."
	cd streamlit_app && streamlit run app.py --server.port 8501

test:
	PYTHONPATH=. pytest tests/ -v

test-cov:
	PYTHONPATH=. pytest tests/ -v --cov=backend/app --cov-report=html

lint:
	flake8 backend/app
	flake8 streamlit_app

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -f cache.db

# Docker build commands
build:
	docker build -t $(ECR_REPO_BACKEND):$(IMAGE_TAG) -f infra/docker/Dockerfile.backend ./backend
	docker build -t $(ECR_REPO_STREAMLIT):$(IMAGE_TAG) -f infra/docker/Dockerfile.streamlit ./streamlit_app

# ECR login and push
push: build
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	docker tag $(ECR_REPO_BACKEND):$(IMAGE_TAG) $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_BACKEND):$(IMAGE_TAG)
	docker tag $(ECR_REPO_STREAMLIT):$(IMAGE_TAG) $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_STREAMLIT):$(IMAGE_TAG)
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_BACKEND):$(IMAGE_TAG)
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_STREAMLIT):$(IMAGE_TAG)

# Deploy to ECS
deploy:
	cd infra/ecs && ./deploy.sh

# View ECS logs
logs:
	aws logs tail /ecs/nongshim-backend --follow --region $(AWS_REGION)

logs-streamlit:
	aws logs tail /ecs/nongshim-streamlit --follow --region $(AWS_REGION)
