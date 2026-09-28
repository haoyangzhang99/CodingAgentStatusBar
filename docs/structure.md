# Project Structure

## Overview

OpenCode Status Bar is a native macOS menu bar app with a PyQt6 dashboard for monitoring OpenCode instances.

```
opencode-status-bar/
│
├── bin/
│   └── opencode-status-bar              # Entry point script
│
├── src/
│   └── opencode_status_bar/             # Main Python package
│       ├── __init__.py
│       ├── app.py                    # Backwards-compatibility wrapper
│       │
│       ├── app/                      # Menu bar application
│       │   ├── core.py               # OpenCodeApp(rumps.App) main class
│       │   ├── handlers.py           # Event callbacks (HandlersMixin)
│       │   └── menu.py               # Menu building (MenuMixin)
│       │
│       ├── core/                     # Core monitoring functionality
│       │   ├── client.py             # OpenCode HTTP client
│       │   ├── models.py             # Data classes (State, Agent, Tool, etc.)
│       │   ├── usage.py              # Claude API usage fetching
│       │   └── monitor/              # Instance detection package
│       │       ├── __init__.py       # Re-exports
│       │       ├── ask_user.py       # MCP Notify ask_user detection
│       │       ├── fetcher.py        # Instance data fetching
│       │       ├── helpers.py        # Utility functions
│       │       └── ports.py          # Port scanning via netstat
│       │
│       ├── api/                      # REST API (Flask)
│       │   ├── __init__.py
│       │   ├── server.py             # Flask server setup
│       │   ├── client.py             # HTTP client for dashboard
│       │   ├── config.py             # API configuration
│       │   ├── tree_builder.py       # Tracing tree construction
│       │   └── routes/               # API endpoints
│       │       ├── _context.py       # Request context
│       │       ├── delegations.py    # /api/delegations
│       │       ├── health.py         # /api/health
│       │       ├── security.py       # /api/security
│       │       ├── sessions.py       # /api/sessions
│       │       ├── stats.py          # /api/stats
│       │       └── tracing/          # /api/tracing endpoints
│       │           ├── builders.py
│       │           ├── fetchers.py
│       │           └── utils.py
│       │
│       ├── analytics/                # Analytics system (DuckDB)
│       │   ├── __init__.py           # Public exports
│       │   ├── db.py                 # DuckDB database management
│       │   ├── loader.py             # Bulk data loading (deprecated, use indexer/)
│       │   ├── models.py             # Analytics data models
│       │   ├── materialization.py    # Materialized table management
│       │   ├── schema_analyzer.py    # Storage schema drift detection
│       │   │
│       │   ├── indexer/              # Unified indexer system
│       │   │   ├── __init__.py
│       │   │   ├── unified.py        # Main UnifiedIndexer class
│       │   │   ├── hybrid.py         # Hybrid indexing strategy
│       │   │   ├── bulk_loader.py    # Bulk loading operations
│       │   │   ├── handlers.py       # Event handlers
│       │   │   ├── parsers.py        # JSON parsing
│       │   │   ├── queries.py        # Indexer SQL queries
│       │   │   ├── sync_state.py     # Sync state management
│       │   │   ├── tracker.py        # Session tracking
│       │   │   ├── watcher.py        # File system watcher
│       │   │   ├── unified/          # Modular indexer components
│       │   │   │   ├── config.py     # Configuration (batch size, workers)
│       │   │   │   ├── core.py       # UnifiedIndexer orchestrator
│       │   │   │   ├── batch.py      # BatchProcessor for bulk INSERT
│       │   │   │   └── processing.py # FileProcessor for real-time
│       │   │   └── trace_builder/    # Trace construction
│       │   │       ├── builder.py
│       │   │       ├── helpers.py
│       │   │       └── segments.py
│       │   │
│       │   ├── loaders/              # Specialized data loaders
│       │   │   ├── __init__.py
│       │   │   ├── delegations.py    # Delegation loading
│       │   │   ├── enrichment.py     # Data enrichment
│       │   │   ├── files.py          # File operations
│       │   │   ├── messages.py       # Message loading
│       │   │   ├── parts.py          # Parts/tool calls
│       │   │   ├── sessions.py       # Session loading
│       │   │   ├── skills.py         # Skills loading
│       │   │   ├── traces.py         # Trace loading
│       │   │   └── utils.py          # Loader utilities
│       │   │
│       │   ├── queries/              # SQL query modules
│       │   │   ├── __init__.py
│       │   │   ├── base.py           # Base query class
│       │   │   ├── agent_queries.py
│       │   │   ├── delegation_queries.py
│       │   │   ├── dimension_queries.py
│       │   │   ├── enriched_queries.py
│       │   │   ├── session_queries.py
│       │   │   ├── time_series_queries.py
│       │   │   ├── tool_queries.py
│       │   │   └── trace_queries.py
│       │   │
│       │   └── tracing/              # Tracing data service
│       │       ├── __init__.py
│       │       ├── config.py         # Tracing configuration
│       │       ├── service.py        # TracingDataService
│       │       ├── detail_queries.py
│       │       ├── helpers.py
│       │       ├── list_queries.py
│       │       ├── session_queries.py
│       │       └── stats_queries.py
│       │
│       ├── dashboard/                # PyQt6 dashboard application
│       │   ├── __init__.py           # Public exports
│       │   ├── __main__.py           # Entry point
│       │   │
│       │   ├── sections/             # Dashboard sections
│       │   │   ├── __init__.py
│       │   │   ├── analytics.py      # Analytics section
│       │   │   ├── colors.py         # Color utilities
│       │   │   ├── monitoring.py     # Monitoring section
│       │   │   ├── security.py       # Security section
│       │   │   └── tracing/          # Tracing section
│       │   │       ├── __init__.py
│       │   │       ├── section.py
│       │   │       ├── helpers.py
│       │   │       ├── tree_builder.py
│       │   │       ├── tree_items.py
│       │   │       ├── tree_utils.py
│       │   │       ├── widgets.py
│       │   │       ├── detail_panel/
│       │   │       │   ├── panel.py
│       │   │       │   ├── components/
│       │   │       │   └── handlers/
│       │   │       └── tabs/         # Detail view tabs
│       │   │           ├── base.py
│       │   │           ├── agents.py
│       │   │           ├── files.py
│       │   │           ├── timeline.py
│       │   │           ├── tokens.py
│       │   │           ├── tools.py
│       │   │           └── transcript.py
│       │   │
│       │   ├── styles/               # Design system
│       │   │   ├── __init__.py
│       │   │   ├── colors.py         # Color palette
│       │   │   ├── dimensions.py     # Spacing, typography
│       │   │   ├── stylesheet.py     # Qt stylesheet
│       │   │   └── utils.py          # Style utilities
│       │   │
│       │   ├── widgets/              # Reusable UI components
│       │   │   ├── __init__.py
│       │   │   ├── badges.py         # Status badges
│       │   │   ├── cards.py          # Card components
│       │   │   ├── cell_badge.py     # Table cell badges
│       │   │   ├── controls.py       # Form controls
│       │   │   ├── navigation.py     # Sidebar navigation
│       │   │   └── tables.py         # Data tables
│       │   │
│       │   └── window/               # Main window
│       │       ├── __init__.py
│       │       ├── main.py           # DashboardWindow
│       │       ├── launcher.py       # Window launcher
│       │       ├── signals.py        # Qt signals
│       │       └── sync.py           # Data sync
│       │
│       ├── security/                 # Security audit system
│       │   ├── __init__.py
│       │   │
│       │   ├── analyzer/             # Risk analysis
│       │   │   ├── __init__.py
│       │   │   ├── command.py        # Command analysis
│       │   │   ├── patterns.py       # Risk patterns
│       │   │   ├── risk.py           # Risk scoring
│       │   │   └── types.py          # Type definitions
│       │   │
│       │   ├── auditor/              # Background scanner
│       │   │   ├── __init__.py
│       │   │   ├── core.py           # Main auditor
│       │   │   ├── _constants.py     # Constants
│       │   │   ├── _edr_handler.py   # EDR event handling
│       │   │   └── _file_processor.py
│       │   │
│       │   ├── db/                   # DuckDB storage (unified)
│       │   │   ├── __init__.py
│       │   │   ├── models.py         # Audit data classes
│       │   │   └── repository.py     # Database operations
│       │   │
│       │   ├── correlator.py         # Event correlation
│       │   ├── mitre_utils.py        # MITRE ATT&CK mapping
│       │   ├── reporter.py           # Report generation
│       │   └── sequences.py          # Kill chain detection
│       │
│       ├── ui/                       # Menu bar UI components
│       │   ├── __init__.py
│       │   ├── menu.py               # MenuBuilder class
│       │   └── terminal.py           # iTerm2 focus (AppleScript)
│       │
│       └── utils/                    # Utilities
│           ├── __init__.py
│           ├── datetime.py           # Date/time utilities
│           ├── db.py                 # Database utilities
│           ├── logger.py             # Logging to stderr
│           ├── settings.py           # Configuration management
│           └── threading.py          # Thread utilities
│
├── tools/
│   └── pycode/                       # Python analysis CLI
│       ├── __init__.py
│       ├── __main__.py               # Entry point
│       ├── deadcode.py               # Dead code detection
│       ├── diagnostics.py            # Lint & format check
│       ├── metrics.py                # Complexity metrics
│       ├── navigation.py             # Code navigation
│       └── report.py                 # Combined report
│
├── tests/                            # Unit & integration tests
│   ├── conftest.py                   # Pytest fixtures
│   ├── builders/                     # Test data builders
│   ├── mocks/                        # Mock objects
│   ├── integration/                  # Integration tests
│   └── test_*.py                     # Unit tests
│
├── docs/                             # Documentation
│   ├── README.md                     # Documentation index
│   ├── api.md                        # REST API reference
│   ├── structure.md                  # This file
│   ├── design-system.md              # UI design tokens
│   ├── sprints/                      # Active sprint records
│   ├── backlog/                      # Pending plans
│   └── archive/                      # Completed plans
│
├── .gitignore
├── pyproject.toml                    # Python project config (uv)
├── pyrightconfig.json                # Type checking config
├── uv.lock                           # Dependency lock file
├── Makefile                          # Dev commands
├── README.md                         # Main documentation
├── DEVELOPMENT.md                    # Development guide
├── QUICKSTART.md                     # Quick start guide
└── LICENSE                           # MIT License
```

## Module Descriptions

### `app/` - Menu Bar Application

Main rumps application with modular design:

- **`core.py`**: `OpenCodeApp(rumps.App)` - combines handlers and menu mixins
- **`handlers.py`**: `HandlersMixin` - callback handlers for menu actions
- **`menu.py`**: `MenuMixin` - menu building and preferences

### `core/` - Core Monitoring

OpenCode instance detection and data fetching:

- **`client.py`**: Async HTTP client for OpenCode API
- **`models.py`**: Data classes (`State`, `Instance`, `Agent`, `Tool`, `Usage`)
- **`usage.py`**: Claude API usage fetching
- **`monitor/`**: Package for instance detection
  - Port scanning via `netstat`
  - Async data fetching
  - TTY detection for terminal focus

### `api/` - REST API

Flask-based API for dashboard data access:

- **`server.py`**: Flask server with CORS support
- **`client.py`**: HTTP client for dashboard
- **`routes/`**: API endpoints (sessions, traces, stats, etc.)

Architecture: The menubar (writer) owns DuckDB and runs the API server.
The dashboard (reader) uses the API client to fetch data.

### `analytics/` - Analytics System

DuckDB-based analytics with multiple subsystems:

- **`db.py`**: DuckDB database management (21 tables)
- **`materialization.py`**: Materialized table manager with incremental refresh
- **`schema_analyzer.py`**: Storage schema analyzer for drift detection
- **`loader.py`**: Legacy bulk loader (deprecated, use `indexer/` instead)
- **`indexer/`**: Unified indexer with real-time + backfill support
  - **`unified/`**: Modular indexer package
    - `config.py`: Configuration constants (batch size, throttle, workers)
    - `core.py`: `UnifiedIndexer` orchestrator (watcher + backfill threads)
    - `batch.py`: `BatchProcessor` for high-throughput bulk INSERT
    - `processing.py`: `FileProcessor` for real-time single file updates
  - **`trace_builder/`**: Trace construction for agent delegations
- **`loaders/`**: Specialized data loaders
- **`queries/`**: SQL query modules
- **`tracing/`**: Tracing data service

### `dashboard/` - PyQt6 Dashboard

Modern dashboard with sidebar navigation:

- **`sections/`**: Monitoring, Security, Analytics, Tracing
- **`styles/`**: Design system (colors, dimensions, stylesheet)
- **`widgets/`**: Reusable UI components
- **`window/`**: Main window and sync

### `security/` - Security Audit

Risk analysis and security monitoring:

- **`analyzer/`**: Command and file risk analysis
- **`auditor/`**: Background security scanner
- **`db/`**: Unified DuckDB storage (all security data in analytics.duckdb)
- **`correlator.py`**: Event correlation
- **`mitre_utils.py`**: MITRE ATT&CK technique mapping
- **`sequences.py`**: Kill chain detection (exfiltration, script execution, supply chain)
- **`reporter.py`**: Report generation

## Data Flow

### Menu Bar Monitoring

```
OpenCode Instances (http://127.0.0.1:PORT)
        ↓
    core/monitor/ (async port scan + HTTP)
        ↓
    core/models.py (State object)
        ↓
    app/core.py (in-memory state)
        ↓
    ui/menu.py (MenuBuilder)
        ↓
    rumps Menu Bar Display
```

### Analytics Pipeline

```
OpenCode Storage (~/.local/share/opencode/storage)
        ↓
    analytics/indexer/ (real-time watcher + backfill)
        ↓
    analytics/db.py (DuckDB)
        ↓
    api/server.py (REST API)
        ↓
    dashboard/ (PyQt6 UI)
```

### Security Audit

```
OpenCode Storage Files
        ↓
    security/auditor/ (background scan)
        ↓
    security/analyzer/ (risk scoring + MITRE mapping)
        ↓
    security/db/ (DuckDB - unified with analytics)
        ↓
    api/routes/security.py
        ↓
    dashboard/sections/security.py
```

## Configuration

Settings stored in `~/.config/opencode-status-bar/settings.json`:

```json
{
  "usage_refresh_interval": 60
}
```

Database:
- `~/.config/opencode-status-bar/analytics.duckdb` (DuckDB) - All data (analytics + security)

## DuckDB Schema

The unified database (`analytics.duckdb`) contains 21 tables organized in 5 functional groups:

### Core Data Tables

```
┌─────────────────────────────────────────────────────────────────────────┐
│                               SESSIONS                                  │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ project_id       │ directory        │ title          │
│ parent_id        │ version          │ created_at       │ updated_at     │
│ additions        │ deletions        │ files_changed    │ is_root        │
│ ended_at         │ duration_ms      │ project_name     │                │
└─────────────────────────────────────────────────────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                               MESSAGES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ session_id (FK)  │ parent_id        │ role           │
│ agent            │ model_id         │ provider_id      │ mode           │
│ cost             │ finish_reason    │ working_dir      │                │
│ tokens_input     │ tokens_output    │ tokens_reasoning │                │
│ tokens_cache_rd  │ tokens_cache_wr  │ created_at       │ completed_at   │
└─────────────────────────────────────────────────────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                 PARTS                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ session_id (FK)  │ message_id (FK)  │ part_type      │
│ content          │ tool_name        │ tool_status      │ call_id        │
│ created_at       │ ended_at         │ duration_ms      │ arguments      │
│ result_summary   │ error_message    │ child_session_id │                │
│ reasoning_text   │ anthropic_sig    │ compaction_auto  │ file_mime/name │
└─────────────────────────────────────────────────────────────────────────┘
```

### Tracing Tables

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AGENT_TRACES                               │
├─────────────────────────────────────────────────────────────────────────┤
│ trace_id (PK)    │ session_id (FK)  │ parent_trace_id  │ parent_agent   │
│ subagent_type    │ prompt_input     │ prompt_output    │ started_at     │
│ ended_at         │ duration_ms      │ tokens_in        │ tokens_out     │
│ status           │ tools_used[]     │ child_session_id │ created_at     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                               DELEGATIONS                               │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ message_id (FK)  │ session_id (FK)  │ parent_agent   │
│ child_agent      │ child_session_id │ created_at       │                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                             FILE_OPERATIONS                             │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ session_id (FK)  │ trace_id (FK)    │ operation      │
│ file_path        │ timestamp        │ risk_level       │ risk_reason    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Auxiliary Tables

```
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│        SKILLS        │  │         TODOS        │  │       PROJECTS       │
├──────────────────────┤  ├──────────────────────┤  ├──────────────────────┤
│ id (PK)              │  │ id (PK)              │  │ id (PK)              │
│ message_id (FK)      │  │ session_id (FK)      │  │ worktree             │
│ session_id (FK)      │  │ content              │  │ vcs                  │
│ skill_name           │  │ status               │  │ created_at           │
│ loaded_at            │  │ priority             │  │ updated_at           │
│                      │  │ position             │  │                      │
│                      │  │ created_at           │  │                      │
│                      │  │ updated_at           │  │                      │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐
│     STEP_EVENTS      │  │       PATCHES        │
├──────────────────────┤  ├──────────────────────┤
│ id (PK)              │  │ id (PK)              │
│ session_id (FK)      │  │ session_id (FK)      │
│ message_id (FK)      │  │ message_id (FK)      │
│ event_type           │  │ git_hash             │
│ reason               │  │ files[]              │
│ snapshot_hash        │  │ created_at           │
│ cost                 │  │                      │
│ tokens_* (5 cols)    │  │                      │
│ created_at           │  │                      │
└──────────────────────┘  └──────────────────────┘
```

### Aggregation & Metadata Tables

```
┌──────────────────────┐  ┌──────────────────────┐
│    SESSION_STATS     │  │     DAILY_STATS      │
├──────────────────────┤  ├──────────────────────┤
│ session_id (PK)      │  │ date (PK)            │
│ total_messages       │  │ total_sessions       │
│ total_tokens_in/out  │  │ total_traces         │
│ total_tokens_cache   │  │ total_tokens         │
│ total_tool_calls     │  │ total_tool_calls     │
│ tool_success_rate    │  │ avg_session_duration │
│ total_file_reads     │  │ error_rate           │
│ total_file_writes    │  │                      │
│ unique_agents        │  │                      │
│ max_delegation_depth │  │                      │
│ estimated_cost_usd   │  │                      │
│ duration_ms          │  │                      │
│ updated_at           │  │                      │
└──────────────────────┘  └──────────────────────┘

┌──────────────────────┐
│      SYNC_META       │
├──────────────────────┤
│ id (PK)              │
│ last_sync            │
│ sync_count           │
└──────────────────────┘
```

### Security Tables

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          SECURITY_COMMANDS                              │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ file_id          │ content_hash     │ session_id     │
│ tool             │ command          │ risk_score       │ risk_level     │
│ risk_reason      │ command_timestamp│ scanned_at       │                │
│ mitre_techniques │ edr_sequence_bonus│ edr_correlation_bonus            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         SECURITY_FILE_READS                             │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ file_id          │ content_hash     │ session_id     │
│ file_path        │ risk_score       │ risk_level       │ risk_reason    │
│ read_timestamp   │ scanned_at       │ mitre_techniques │                │
│ edr_sequence_bonus│ edr_correlation_bonus                               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         SECURITY_FILE_WRITES                            │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ file_id          │ content_hash     │ session_id     │
│ file_path        │ operation        │ risk_score       │ risk_level     │
│ risk_reason      │ write_timestamp  │ scanned_at       │ mitre_techniques│
│ edr_sequence_bonus│ edr_correlation_bonus                               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         SECURITY_WEBFETCHES                             │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK)          │ file_id          │ content_hash     │ session_id     │
│ url              │ risk_score       │ risk_level       │ risk_reason    │
│ fetch_timestamp  │ scanned_at       │ mitre_techniques │                │
│ edr_sequence_bonus│ edr_correlation_bonus                               │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐
│   SECURITY_STATS     │  │  SECURITY_SCANNED    │
├──────────────────────┤  ├──────────────────────┤
│ id (PK)              │  │ part_id (PK)         │
│ total_files_scanned  │  │ scanned_at           │
│ total_commands       │  │                      │
│ last_full_scan       │  │                      │
└──────────────────────┘  └──────────────────────┘
```

### Table Summary

| Group          | Table                 | Purpose                              |
|----------------|-----------------------|--------------------------------------|
| **Core**       | sessions              | Session metadata and git stats       |
| **Core**       | messages              | Messages with token metrics          |
| **Core**       | parts                 | Content, tool calls, delegations     |
| **Tracing**    | agent_traces          | Task tool invocation traces          |
| **Tracing**    | delegations           | Agent delegation records             |
| **Tracing**    | file_operations       | File read/write/edit tracking        |
| **Auxiliary**  | skills                | Loaded skill tracking                |
| **Auxiliary**  | todos                 | Session todos                        |
| **Auxiliary**  | projects              | Project metadata                     |
| **Auxiliary**  | step_events           | Step start/finish events             |
| **Auxiliary**  | patches               | Git commit tracking                  |
| **Aggregation**| session_stats         | Pre-calculated session KPIs          |
| **Aggregation**| daily_stats           | Daily aggregated metrics             |
| **Metadata**   | sync_meta             | Dashboard sync signaling             |
| **Security**   | security_commands     | Audited bash commands with risk      |
| **Security**   | security_file_reads   | Audited file reads with risk         |
| **Security**   | security_file_writes  | Audited file writes with risk        |
| **Security**   | security_webfetches   | Audited web fetches with risk        |
| **Security**   | security_stats        | Security scan statistics             |
| **Security**   | security_scanned      | Security audit progress tracking     |

## Development

```bash
# Run the app
make run

# Run unit tests
make test

# Run integration tests
make test-integration

# Run all tests with coverage
make coverage-html
```
