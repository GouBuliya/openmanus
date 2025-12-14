.PHONY: help install dev lint format typecheck test test-unit test-integration test-e2e clean proto serve

PYTHON := python
UV := uv

help:  ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## 安装生产依赖
	$(UV) sync

dev:  ## 安装开发依赖
	$(UV) sync --dev
	$(UV) run pre-commit install

lint:  ## 运行代码检查
	$(UV) run ruff check src tests

format:  ## 格式化代码
	$(UV) run ruff format src tests
	$(UV) run ruff check --fix src tests

typecheck:  ## 运行类型检查
	$(UV) run mypy src

test:  ## 运行所有测试
	$(UV) run pytest tests -v

test-unit:  ## 运行单元测试
	$(UV) run pytest tests/unit -v -m unit

test-integration:  ## 运行集成测试
	$(UV) run pytest tests/integration -v -m integration

test-e2e:  ## 运行端到端测试
	$(UV) run pytest tests/e2e -v -m e2e

test-cov:  ## 运行测试并生成覆盖率报告
	$(UV) run pytest tests --cov=src/openmanus --cov-report=html --cov-report=term

proto:  ## 生成 gRPC 代码
	./scripts/generate_proto.sh

serve:  ## 启动开发服务器
	$(UV) run uvicorn openmanus.api.rest.app:app --reload --host 0.0.0.0 --port 8000

clean:  ## 清理临时文件
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
