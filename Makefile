all: cdk-deploy

setup: install-python install-node

install-python: venv/touchfile
venv/touchfile: requirements.txt
	@echo "Creating virtual environment..."
	python3 -m venv venv
	@echo "Activating venv..."
	. venv/bin/activate
	@echo "Installing Python requirements..."
	pip install -r requirements.txt
	touch venv/touchfile

install-node: node_modules
node_modules: package.json package-lock.json
	@echo "Installing Node.js requirements..."
	npm install

docker-build:
	@echo "Building Docker image..."
	docker build -t comfyui-aws:latest comfyui_aws_stack/docker/
	@echo "Docker image built successfully!"

cdk-bootstrap: setup
	@echo "Running cdk bootstrap..."
	npx cdk bootstrap

cdk-deploy: setup
	@echo "Running cdk deploy..."
	npx cdk deploy

cdk-deploy-force: setup
	@echo "Running cdk deploy..."
	npx cdk deploy --require-approval never

test: install-python
	pytest -vv

test-update: install-python
	pytest --snapshot-update

clean:
	@echo "Removing virtual environment and node modules..."
	rm -rf venv node_modules

# Docker Image Management
docker-build:
	@echo "Building Docker image locally..."
	@bash scripts/build-image.sh

docker-push:
	@echo "Pushing Docker image to ECR..."
	@bash scripts/push-image.sh

docker-build-push: docker-build docker-push
	@echo "Docker image built and pushed successfully!"

# Get current ECR image URI
docker-get-uri:
	@bash scripts/get-image-uri.sh

# Update ECS Service with new image
ecs-update:
	@echo "Updating ECS Service with new image..."
	@bash scripts/update-ecs-service.sh

# Full deployment: build, push, and update ECS
docker-deploy: docker-build-push ecs-update
	@echo "Full deployment completed successfully!"
