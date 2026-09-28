# OpenCode Status Bar - Makefile

.PHONY: help install uninstall run run-debug test coverage coverage-html lint clean

help:
	@echo "OpenCode Status Bar"
	@echo ""
	@echo "  make install        Build and install the app and OpenCode plugin"
	@echo "  make uninstall      Remove the app and OpenCode plugin"
	@echo "  make run            Run the menu bar app from this folder"
	@echo "  make run-debug      Same, with debug logs printed to the terminal"
	@echo "  make test           Run the Python and plugin tests"
	@echo "  make coverage       Python tests with a coverage report"
	@echo "  make coverage-html  Same, as HTML"
	@echo "  make lint           Lint Python code and shell scripts"
	@echo "  make clean          Remove caches and build artifacts"

install:
	@./install.sh

uninstall:
	@./uninstall.sh

run:
	@uv run python -c "from opencode_status_bar.app import main; main()"

run-debug:
	@OPENCODE_DEBUG=1 OPENCODE_LOG_LEVEL=DEBUG uv run python -c "from opencode_status_bar.app import main; main()"

test:
	@uv run pytest tests/ -q
	@node --test tests/opencode-status-bar-plugin.test.mjs

coverage:
	@uv run pytest tests/ --cov=src/opencode_status_bar --cov-report=term-missing

coverage-html:
	@uv run pytest tests/ --cov=src/opencode_status_bar --cov-report=html
	@open htmlcov/index.html

lint:
	@uv run ruff check src tests tools
	@uvx --from shellcheck-py shellcheck install.sh uninstall.sh

clean:
	@rm -rf .coverage htmlcov/ .pytest_cache .ruff_cache src/*.egg-info
	@find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "Build artifacts cleaned"
