# OpenCode Status Bar - Makefile
#
# Native macOS menu bar app (rumps)

.PHONY: help install uninstall run run-debug backfill test test-unit test-integration test-integration-visible coverage coverage-html mutation mutation-mini mutation-security mutation-risk mutation-browse mutation-results mutation-clean mutation-show mutation-report mutation-report-bg mutation-debug test-audit clean clean-db clean-all roadmap

# Default target
help:
	@echo "OpenCode Status Bar"
	@echo ""
	@echo "Usage:"
	@echo "  make install                Build and install the app and OpenCode plugin"
	@echo "  make uninstall              Remove the app and OpenCode plugin"
	@echo "  make run                    Run the menu bar app"
	@echo "  make run-debug              Run with debug logs enabled"
	@echo "  make backfill               Load historical data (app must be stopped)"
	@echo "  make test                   Run unit + integration DB/API tests"
	@echo "  make test-unit              Run unit tests only"
	@echo "  make test-integration       Run all integration tests (headless)"
	@echo "  make test-integration-db    Run integration DB tests"
	@echo "  make test-integration-api   Run integration API tests"
	@echo "  make test-integration-visible  Run integration tests (visible UI)"
	@echo "  make test-all               Run all tests (unit + integration)"
	@echo "  make test-stats             Show test structure statistics"
	@echo "  make coverage               Run tests with coverage report"
	@echo "  make coverage-html          Run tests with HTML coverage report"
	@echo ""
	@echo "Mutation Testing (mutmut v2.5.1):"
	@echo "  make mutation               Run full mutation testing"
	@echo "  make mutation-mini          Quick test on utils module (~2min)"
	@echo "  make mutation-risk          Test risk analyzer only (~3min)"
	@echo "  make mutation-security      Test all security modules (~10min)"
	@echo "  make mutation-report        Run security mutation + report"
	@echo "  make mutation-report-bg     Run mutation in background"
	@echo "  make mutation-debug         Debug mutation setup"
	@echo "  make mutation-browse        Interactive results browser"
	@echo "  make mutation-results       Show mutation results"
	@echo "  make mutation-show MUTANT=N Show specific mutant"
	@echo "  make mutation-clean         Clean mutation cache"
	@echo ""
	@echo "Test Quality:"
	@echo "  make test-audit             Audit all test files"
	@echo "  make test-audit-file FILE=x Audit specific file"
	@echo "  make test-audit-priority    Audit priority files"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          Remove temp/build files"
	@echo "  make clean-db       Remove analytics database"
	@echo "  make clean-all      Remove all artifacts and database"
	@echo "  make roadmap        Show roadmap status"

# === Application ===

install:
	@./install.sh

uninstall:
	@./uninstall.sh

run:
	@uv run python -c "import sys; sys.path.insert(0, 'src'); from opencode_status_bar.app import main; main()"

run-debug:
	@OPENCODE_DEBUG=1 OPENCODE_LOG_LEVEL=DEBUG uv run python -c "import sys; sys.path.insert(0, 'src'); from opencode_status_bar.app import main; main()"

backfill:
	@uv run python scripts/backfill.py

# === Testing ===

test:
	@uv run pytest tests/unit/ tests/integration/database/ tests/integration/api/ -v -n 2

test-unit:
	@uv run pytest tests/unit/ -v -n 2

test-integration:
	@QT_QPA_PLATFORM=offscreen uv run pytest tests/integration/ -v -n 2

test-integration-visible:
	@uv run pytest tests/integration/ -v -n 8

test-integration-db:
	@uv run pytest tests/integration/database/ -v -n 4

test-integration-api:
	@uv run pytest tests/integration/api/ -v -n 4

test-all:
	@QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v -n 8

test-stats:
	@echo "=== Test Structure ==="
	@echo "Unit tests:"
	@uv run pytest tests/unit/ --collect-only -q 2>/dev/null | tail -1
	@echo "Integration tests:"
	@uv run pytest tests/integration/ --collect-only -q 2>/dev/null | tail -1
	@echo "Builder tests:"
	@uv run pytest tests/builders/ --collect-only -q 2>/dev/null | tail -1
	@echo ""
	@echo "Total:"
	@uv run pytest tests/ --collect-only -q 2>/dev/null | tail -1

coverage:
	@uv run pytest tests/ -n 8 --cov=src/opencode_status_bar --cov-report=term-missing

coverage-html:
	@uv run pytest tests/ -n 8 --cov=src/opencode_status_bar --cov-report=html
	@open htmlcov/index.html

# === Mutation Testing (mutmut v2.5.1) ===
# Note: v2 uses CLI options, not pyproject.toml config
# Output redirected to temp files to avoid verbose terminal output

# Paths to exclude from mutation (UI, dashboard, async-heavy code)
MUTMUT_EXCLUDE := src/opencode_status_bar/dashboard,src/opencode_status_bar/ui,src/opencode_status_bar/db,src/opencode_status_bar/monitor.py,src/opencode_status_bar/app.py

# Security modules (high priority for mutation testing)
SECURITY_PATHS := src/opencode_status_bar/security/

# Test runner command
MUTMUT_RUNNER := uv run pytest tests/ --ignore=tests/integration -x -q

# Temp file for mutation output
MUTMUT_LOG := /tmp/mutmut-output.log

mutation:
	@echo "Running full mutation testing (this takes a while)..."
	@echo "Excluding: $(MUTMUT_EXCLUDE)"
	@echo "Output: $(MUTMUT_LOG)"
	@uv run mutmut run \
		--paths-to-mutate src/opencode_status_bar/ \
		--paths-to-exclude "$(MUTMUT_EXCLUDE)" \
		--runner "$(MUTMUT_RUNNER)" > $(MUTMUT_LOG) 2>&1 || true
	@uv run mutmut results

mutation-mini:
	@echo "Running quick mutation test on utils module (~2min)..."
	@rm -f .mutmut-cache
	@uv run mutmut run \
		--paths-to-mutate src/opencode_status_bar/utils.py \
		--runner "uv run pytest tests/test_utils.py -x -q" > $(MUTMUT_LOG) 2>&1 || true
	@uv run mutmut results

mutation-security:
	@echo "Running mutation test on security modules (~10min)..."
	@rm -f .mutmut-cache
	@uv run mutmut run \
		--paths-to-mutate $(SECURITY_PATHS) \
		--runner "uv run pytest tests/test_risk_analyzer.py tests/test_mitre_tags.py tests/test_mitre_utils.py tests/test_correlator.py tests/test_sequences.py -x -q" > $(MUTMUT_LOG) 2>&1 || true
	@uv run mutmut results

mutation-risk:
	@echo "Running mutation test on risk analyzer only (~3min)..."
	@rm -f .mutmut-cache
	@uv run mutmut run \
		--paths-to-mutate src/opencode_status_bar/security/analyzer/risk.py \
		--runner "uv run pytest tests/test_risk_analyzer.py -x -q" > $(MUTMUT_LOG) 2>&1 || true
	@uv run mutmut results

mutation-browse:
	@uv run mutmut browse

mutation-results:
	@uv run mutmut results

mutation-clean:
	@rm -rf mutants/ .mutmut-cache
	@echo "Mutation cache cleaned"

mutation-show:
	@uv run mutmut show $(MUTANT)

mutation-report:
	@mkdir -p reports
	@LOGFILE="reports/mutation-$$(date +%Y%m%d_%H%M%S).log"; \
	echo "Starting mutation testing on security modules..."; \
	echo "Output: $$LOGFILE"; \
	echo "This may take 10+ minutes. Check progress with: tail -f $$LOGFILE"; \
	uv run mutmut run \
		--paths-to-mutate $(SECURITY_PATHS) \
		--runner "uv run pytest tests/test_risk_analyzer.py tests/test_mitre_tags.py tests/test_mitre_utils.py tests/test_correlator.py tests/test_sequences.py -x -q" \
		2>&1 | tee "$$LOGFILE"; \
	uv run mutmut results 2>&1 | tee -a "$$LOGFILE"

mutation-report-bg:
	@mkdir -p reports
	@LOGFILE="reports/mutation-$$(date +%Y%m%d_%H%M%S).log"; \
	echo "Starting mutation testing in background..."; \
	echo "Output: $$LOGFILE"; \
	nohup sh -c 'uv run mutmut run \
		--paths-to-mutate $(SECURITY_PATHS) \
		--runner "uv run pytest tests/test_risk_analyzer.py tests/test_mitre_tags.py tests/test_mitre_utils.py tests/test_correlator.py tests/test_sequences.py -x -q" \
		2>&1; uv run mutmut results 2>&1' > "$$LOGFILE" 2>&1 & \
	echo "PID: $$!"; \
	echo "Check progress: tail -f $$LOGFILE"

mutation-debug:
	@echo "Debug: testing risk.py with test_risk_analyzer.py"
	@rm -f .mutmut-cache
	@echo "Step 1: Verify tests pass normally..."
	@uv run pytest tests/test_risk_analyzer.py -x -q
	@echo ""
	@echo "Step 2: Run mutmut on single file..."
	@uv run mutmut run \
		--paths-to-mutate src/opencode_status_bar/security/analyzer/risk.py \
		--runner "uv run pytest tests/test_risk_analyzer.py -x -q"
	@echo ""
	@echo "Step 3: Results..."
	@uv run mutmut results

# === Test Quality Audit ===

test-audit:
	@./scripts/test-audit.sh

test-audit-file:
	@./scripts/test-audit.sh $(FILE)

test-audit-priority:
	@echo "=== Priority Files (Low Assertion Ratio) ==="
	@./scripts/test-audit.sh "tests/test_hybrid_indexer_resume.py tests/test_unified_indexer.py tests/test_dashboard_sync.py tests/test_mitre_tags.py tests/test_tooltips.py tests/test_correlator.py"

# === Maintenance ===

clean:
	@rm -rf .coverage htmlcov/
	@rm -rf mutants/ .mutmut-cache
	@rm -rf src/*.egg-info
	@rm -rf __pycache__ src/__pycache__ tests/__pycache__
	@rm -rf src/opencode_status_bar/__pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Build artifacts cleaned"

clean-db:
	@if [ -f ~/.config/opencode-status-bar/analytics.duckdb ]; then \
		rm -f ~/.config/opencode-status-bar/analytics.duckdb ~/.config/opencode-status-bar/analytics.duckdb.wal && \
		echo "Database cleaned: ~/.config/opencode-status-bar/analytics.duckdb (+ WAL)"; \
	else \
		echo "No database found at ~/.config/opencode-status-bar/analytics.duckdb"; \
	fi

clean-all: clean clean-db
	@echo "All artifacts and database cleaned"

roadmap:
	@cat roadmap/README.md 2>/dev/null || echo "No roadmap found"
