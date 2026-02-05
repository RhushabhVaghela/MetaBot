.PHONY: install install-dev test test-cov lint format clean build

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	PYTHONPATH=. OPENCLAW_AUTH_TOKEN=test_token_12345 python3 -m pytest tests/ -v

test-cov:
	PYTHONPATH=. OPENCLAW_AUTH_TOKEN=test_token_12345 python3 -m pytest tests/ --cov=core --cov=adapters --cov=modules --cov-report=html --cov-report=term

lint:
	ruff check .

format:
	ruff format .

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache htmlcov .coverage

build:
	python -m build