all: cdk-deploy

setup: install-python install-node

install-python: venv
venv: requirements.txt
	@echo "Creating virtual environment..."
	python3 -m venv venv
	@echo "Installing Python requirements..."
	pip install -r requirements.txt

install-node: node_modules
node_modules: package.json package-lock.json
	@echo "Installing Node.js requirements..."
	npm install

cdk-deploy: setup
	@echo "Running cdk bootstrap..."
	npx cdk bootstrap
	@echo "Running cdk deploy..."
	npx cdk deploy

clean:
	@echo "Removing virtual environment and node modules..."
	rm -rf venv node_modules