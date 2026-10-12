SHELL := bash
PYTHON ?= python3
VENV ?= .venv
CONFIG ?= config.toml

ifeq ($(OS),Windows_NT)
VENV_BIN := $(VENV)/Scripts
else
VENV_BIN := $(VENV)/bin
endif

PY := $(VENV_BIN)/python
PIP := $(PY) -m pip

.PHONY: setup install run check lint test cov clean

setup: $(VENV)/pyvenv.cfg

$(VENV)/pyvenv.cfg:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .
	mkdir -p data

install: setup

run: setup
	$(PY) -m y33bot run --config $(CONFIG)

check: setup
	$(PY) -m y33bot check --config $(CONFIG)

lint: setup
	$(VENV_BIN)/ruff check src tests

test: setup
	$(PY) -m pytest -q

cov: setup
	$(PY) -m pytest -q --cov=y33bot --cov-report=term-missing

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache .coverage htmlcov
