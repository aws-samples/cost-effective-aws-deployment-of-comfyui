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

cdk-deploy: setup
	@echo "Running cdk bootstrap..."
	npx cdk bootstrap
	@echo "Running cdk deploy..."
	npx cdk deploy

cdk-deploy-force: setup
	@echo "Running cdk bootstrap..."
	npx cdk bootstrap
	@echo "Running cdk deploy..."
	npx cdk deploy --require-approval never

test: install-python
	pytest -vv

test-update: install-python
	pytest --snapshot-update

clean:
	@echo "Removing virtual environment and node modules..."
	rm -rf venv node_modules
