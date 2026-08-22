PYTHON ?= python3.12
VENV ?= .venv
CDK ?= $(VENV)/bin/cdk

.PHONY: help venv install lint test synth diff deploy destroy bootstrap

help:
	@echo "make install   - create venv and install dependencies"
	@echo "make lint      - ruff + mypy"
	@echo "make test      - unit tests"
	@echo "make synth     - cdk synth"
	@echo "make deploy    - cdk deploy"
	@echo "make destroy   - cdk destroy"

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -r requirements-dev.txt
	$(VENV)/bin/npm --version >/dev/null 2>&1 || true

lint:
	$(VENV)/bin/ruff check src infra config tests scripts app.py
	$(VENV)/bin/mypy src infra config || true

test:
	$(VENV)/bin/pytest tests -q -m "not integration and not e2e" --cov=src --cov-report=term-missing

synth:
	$(CDK) synth

diff:
	$(CDK) diff

bootstrap:
	$(CDK) bootstrap

deploy:
	$(CDK) deploy --require-approval never

destroy:
	$(CDK) destroy --force
