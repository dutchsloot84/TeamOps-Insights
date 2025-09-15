PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
PACKAGE_DIR := services/ingest/jira_ingestor
LAMBDA_ZIP := $(PACKAGE_DIR)/jira_ingestor.zip
BUILD_DIR := build
TF_DIR := infra
TF ?= terraform
TF_ARGS ?=
DEV_PACKAGES := black isort flake8 mypy bandit pytest boto3 types-requests types-python-dateutil

.PHONY: venv build clean clean-build lint test tf-init tf-plan tf-apply tf-destroy deploy

venv:
	@if [ ! -d $(VENV) ]; then $(PYTHON) -m venv $(VENV); fi
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r $(PACKAGE_DIR)/requirements.txt
	$(BIN)/pip install $(DEV_PACKAGES)

clean:
	rm -rf $(VENV) $(BUILD_DIR) $(PACKAGE_DIR)/__pycache__ $(PACKAGE_DIR)/tests/__pycache__
	rm -f $(LAMBDA_ZIP)

clean-build:
	rm -rf $(BUILD_DIR)
	rm -f $(LAMBDA_ZIP)

build: venv clean-build
	mkdir -p $(BUILD_DIR)
	$(BIN)/pip install -r $(PACKAGE_DIR)/requirements.txt -t $(BUILD_DIR)
	cp $(PACKAGE_DIR)/handler.py $(PACKAGE_DIR)/jira_api.py $(PACKAGE_DIR)/adf_md.py $(PACKAGE_DIR)/__init__.py $(BUILD_DIR)/
	find $(BUILD_DIR) -name "__pycache__" -type d -exec rm -rf {} +
	cd $(BUILD_DIR) && zip -r ../$(LAMBDA_ZIP) .

lint: venv
	$(BIN)/black --check $(PACKAGE_DIR) infra
	$(BIN)/isort --check-only $(PACKAGE_DIR) infra
	$(BIN)/flake8 $(PACKAGE_DIR)
	$(BIN)/mypy $(PACKAGE_DIR)
	$(BIN)/bandit -q -r $(PACKAGE_DIR) -x $(PACKAGE_DIR)/tests

test: venv
	PYTHONPATH=$(PWD) $(BIN)/pytest -q $(PACKAGE_DIR)/tests

tf-init:
	cd $(TF_DIR) && $(TF) init

tf-plan:
	cd $(TF_DIR) && $(TF) plan $(TF_ARGS)

tf-apply:
	cd $(TF_DIR) && $(TF) apply $(TF_ARGS)

tf-destroy:
	cd $(TF_DIR) && $(TF) destroy $(TF_ARGS)

deploy: build tf-apply
