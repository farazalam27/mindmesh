.PHONY: help install dev-install test lint format type-check clean build up down logs shell migrate

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make dev-install   - Install development dependencies"
	@echo "  make test          - Run all tests"
	@echo "  make lint          - Run linting checks"
	@echo "  make format        - Format code with black and isort"
	@echo "  make type-check    - Run mypy type checking"
	@echo "  make clean         - Clean up cache and temporary files"
	@echo "  make build         - Build Docker images"
	@echo "  make up            - Start all services"
	@echo "  make down          - Stop all services"
	@echo "  make logs          - Show service logs"
	@echo "  make shell         - Open shell in api-gateway container"
	@echo "  make migrate       - Run database migrations"

# Installation
install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Testing
test: test-unit test-integration test-bdd

test-unit:
	pytest tests/unit -v --cov=mindmesh --cov-report=term-missing

test-integration:
	pytest tests/integration -v

test-bdd:
	behave tests/bdd

test-coverage:
	pytest --cov=mindmesh --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

# Code quality
lint:
	flake8 mindmesh services tests
	black --check mindmesh services tests
	isort --check-only mindmesh services tests

format:
	black mindmesh services tests
	isort mindmesh services tests

type-check:
	mypy mindmesh services

# Docker operations
build:
	docker-compose build

build-no-cache:
	docker-compose build --no-cache

up:
	docker-compose up -d

down:
	docker-compose down

down-volumes:
	docker-compose down -v

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api-gateway

logs-processor:
	docker-compose logs -f data-processor

logs-worker:
	docker-compose logs -f celery-worker

ps:
	docker-compose ps

# Development helpers
shell:
	docker-compose exec api-gateway /bin/bash

shell-db:
	docker-compose exec postgres psql -U mindmesh -d mindmesh

redis-cli:
	docker-compose exec redis redis-cli

# Database operations
migrate:
	docker-compose exec api-gateway alembic upgrade head

migrate-create:
	docker-compose exec api-gateway alembic revision --autogenerate -m "$(message)"

migrate-down:
	docker-compose exec api-gateway alembic downgrade -1

# Spark operations
spark-shell:
	docker-compose exec spark-master /opt/bitnami/spark/bin/spark-shell

spark-submit:
	docker-compose exec spark-master /opt/bitnami/spark/bin/spark-submit $(args)

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

# Development workflow shortcuts
dev: down clean build up logs

restart:
	docker-compose restart $(service)

rebuild:
	docker-compose up -d --build $(service)

# Production build
prod-build:
	docker build -f Dockerfile.prod -t mindmesh:latest .

# Environment setup
setup-env:
	cp .env.example .env
	@echo "Environment file created. Please update .env with your configuration."

# Pre-commit hooks
pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files