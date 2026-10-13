# Y33-Bot 开发入口。Linux/macOS 直接用 make；Windows 推荐 git-bash（或直接跑 scripts/dev_setup.sh）。
#
#   make setup    # 建 .venv + 装依赖 + 生成 config.toml（= bash scripts/dev_setup.sh）
#   make check    # 启动自检（健康状态）
#   make test     # pytest
#   make lint     # ruff check + ruff format --check

SHELL := /bin/bash
PY ?= python3
VENV ?= .venv
CONFIG ?= config.toml
PYTEST_ARGS ?=

ifeq ($(OS),Windows_NT)
  VENV_CANDIDATE := $(VENV)/Scripts/python.exe
else
  VENV_CANDIDATE := $(VENV)/bin/python
endif

# 优先用仓库内的 .venv；没有 .venv 时（例如 CI 里直接用 setup-python 的解释器）回退到 $(PY)，
# 这样 `make test` 在有/无虚拟环境的干净环境里都能一键跑通。
VENV_PY := $(if $(wildcard $(VENV_CANDIDATE)),$(VENV_CANDIDATE),$(PY))

.DEFAULT_GOAL := help

.PHONY: help setup install run check lint fmt test coverage smoke clean

help:  ## 显示可用目标
	@echo "Y33-Bot make targets:"
	@echo "  (Windows console: run 'chcp 65001' first if CJK text looks garbled.)"
	@echo "Y33-Bot make 目标："
	@echo "  setup    建 .venv + 装依赖 + 生成 config.toml（等价 bash scripts/dev_setup.sh）"
	@echo "  install  只装依赖（含开发依赖）+ 可编辑安装本包"
	@echo "  run      常驻启动：$(VENV_PY) -m y33bot run --config $(CONFIG)"
	@echo "  check    启动自检：$(VENV_PY) -m y33bot check --config $(CONFIG)"
	@echo "  smoke    入口冒烟：版本号 + 模块可导入"
	@echo "  lint     ruff check + ruff format --check"
	@echo "  fmt      ruff format（就地格式化）"
	@echo "  test     pytest（可用 PYTEST_ARGS=\"--cov=y33bot --cov-fail-under=70\" 追加参数；CI 就是这么调的）"
	@echo "  coverage pytest --cov=y33bot --cov-report=term-missing"
	@echo "  clean    删除缓存与构建产物（不动 .venv / data）"

setup:  ## 一键准备开发环境
	bash scripts/dev_setup.sh

install:  ## 仅安装依赖
	$(VENV_PY) -m pip install -r requirements-dev.txt
	$(VENV_PY) -m pip install -e .

run:  ## 常驻启动服务
	$(VENV_PY) -m y33bot run --config $(CONFIG)

check:  ## 启动自检
	$(VENV_PY) -m y33bot check --config $(CONFIG)

smoke:  ## 入口冒烟
	$(VENV_PY) -m y33bot --version
	$(VENV_PY) -c "import y33bot, y33bot.cli, y33bot.service; print('import OK', y33bot.__version__)"

lint:  ## 静态检查
	$(VENV_PY) -m ruff check .
	$(VENV_PY) -m ruff format --check .

fmt:  ## 格式化
	$(VENV_PY) -m ruff format .

test:  ## 跑测试（PYTEST_ARGS 可追加参数）
	$(VENV_PY) -m pytest $(PYTEST_ARGS)

coverage:  ## 跑测试 + 覆盖率
	$(VENV_PY) -m pytest --cov=y33bot --cov-report=term-missing

clean:  ## 清理缓存与构建产物
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
