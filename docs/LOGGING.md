# Logging System

Professional logging system for OpenCode Status Bar with human-readable and JSON formats, automatic file rotation, context tracking, and crash handling.

## Table of Contents

- [Overview](#overview)
- [Log File Locations](#log-file-locations)
- [Log Formats](#log-formats)
- [Usage](#usage)
- [Environment Variables](#environment-variables)
- [Log Level Guidelines](#log-level-guidelines)
- [Viewing Logs](#viewing-logs)
- [Troubleshooting](#troubleshooting)

## Overview

The logging system provides:

- **Dual output formats**: Human-readable logs for development, JSON logs for analysis
- **Automatic rotation**: Prevents disk space issues with configurable size limits and backup counts
- **Context tracking**: Correlate logs across requests with `request_id` and `session_id`
- **Crash handling**: Dedicated crash log captures unhandled exceptions
- **Flexible configuration**: Control verbosity via environment variables

## Log File Locations

All logs are stored in the standard macOS logs directory:

```
~/Library/Logs/OpenCodeStatusBar/
├── opencode-status-bar.log       # Human-readable format
├── opencode-status-bar.json      # JSON Lines format
└── crash.log                  # Crash reports
```

### File Rotation Policy

| File | Max Size | Backups | Total Max |
|------|----------|---------|-----------|
| `opencode-status-bar.log` | 10 MB | 5 | ~60 MB |
| `opencode-status-bar.json` | 20 MB | 3 | ~80 MB |
| `crash.log` | No rotation | - | - |

When a log file reaches its maximum size, it's renamed with a numeric suffix (e.g., `opencode-status-bar.log.1`) and a new file is created. Oldest backups are deleted when the backup count is exceeded.

## Log Formats

### Human-Readable Format

Optimized for terminal viewing and quick debugging:

```
2024-01-15 14:23:45.123 | INFO  | opencode.api | server.py:42 | Server started on port 8080
2024-01-15 14:23:46.456 | DEBUG | opencode.db  | pool.py:128  | Connection acquired from pool
2024-01-15 14:23:47.789 | ERROR | opencode.api | handler.py:95 | Request failed: Connection timeout
```

Format breakdown:
```
{timestamp} | {level:5} | {logger:12} | {file}:{line} | {message}
```

### JSON Lines Format

Each line is a complete JSON object, ideal for log aggregation and analysis:

```json
{"timestamp": "2024-01-15T14:23:45.123Z", "level": "INFO", "logger": "opencode.api", "file": "server.py", "line": 42, "message": "Server started on port 8080", "request_id": null, "session_id": null}
{"timestamp": "2024-01-15T14:23:46.456Z", "level": "DEBUG", "logger": "opencode.db", "file": "pool.py", "line": 128, "message": "Connection acquired from pool", "request_id": "abc-123", "session_id": "user-456"}
```

JSON fields:
- `timestamp`: ISO 8601 format with milliseconds
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logger`: Logger name (component identifier)
- `file`: Source file name
- `line`: Line number in source file
- `message`: Log message
- `request_id`: Request correlation ID (if set)
- `session_id`: Session identifier (if set)
- `extra`: Additional context data (if provided)

## Usage

### Basic Logging

Import the convenience functions for simple logging:

```python
from opencode_status_bar.utils.logger import debug, info, warn, error

# Simple messages
debug("Processing started")
info("Server listening on port 8080")
warn("Configuration file not found, using defaults")
error("Failed to connect to database")
```

### Component Logger

Create a named logger for your component to improve log organization:

```python
from opencode_status_bar.utils.logger import get_logger

logger = get_logger("mycomponent")

logger.debug("Component initialized")
logger.info("Processing request")
logger.warning("Deprecated method called")
logger.error("Operation failed", exc_info=True)
```

### Context Tracking

Use context managers to automatically include correlation IDs in all logs:

```python
from opencode_status_bar.utils.logger import log_context, info

# All logs within this block will include the request_id
with log_context(request_id="abc-123"):
    info("Processing request")  # Includes request_id="abc-123"
    process_data()
    info("Request completed")   # Includes request_id="abc-123"

# Nest contexts for additional tracking
with log_context(session_id="user-456"):
    with log_context(request_id="req-789"):
        info("Handling user request")  # Includes both IDs
```

### Logging with Extra Data

Include additional structured data in your logs:

```python
from opencode_status_bar.utils.logger import info

info("User action", extra={
    "user_id": "12345",
    "action": "login",
    "ip_address": "192.168.1.1"
})
```

### Exception Logging

Capture full stack traces when logging errors:

```python
from opencode_status_bar.utils.logger import error

try:
    risky_operation()
except Exception as e:
    error(f"Operation failed: {e}", exc_info=True)
```

## Environment Variables

Configure logging behavior without code changes:

| Variable | Description | Values | Default |
|----------|-------------|--------|---------|
| `OPENCODE_DEBUG` | Enable debug mode | `1`, `true`, `yes` | `false` |
| `OPENCODE_LOG_LEVEL` | Set minimum log level | `debug`, `info`, `warning`, `error`, `critical` | `info` |
| `OPENCODE_LOG_CONSOLE` | Enable console output | `1`, `true`, `yes` | `false` |

### Examples

```bash
# Enable debug logging
export OPENCODE_DEBUG=1

# Set log level to warning (only warnings and above)
export OPENCODE_LOG_LEVEL=warning

# Enable console output for development
export OPENCODE_LOG_CONSOLE=true

# Combine settings
OPENCODE_DEBUG=1 OPENCODE_LOG_CONSOLE=1 python -m opencode_status_bar
```

## Log Level Guidelines

Choose the appropriate level based on the situation:

### DEBUG
Development and troubleshooting information. Not shown in production by default.

```python
debug(f"Cache lookup for key: {key}")
debug(f"SQL query: {query}")
debug(f"Response payload size: {len(data)} bytes")
```

Use for:
- Variable values during debugging
- Detailed flow information
- Performance measurements
- SQL queries and cache operations

### INFO
Normal operational events worth recording.

```python
info("Server started on port 8080")
info(f"User {user_id} logged in")
info("Configuration reloaded")
```

Use for:
- Application startup/shutdown
- Configuration changes
- Significant state transitions
- User actions (at a high level)

### WARNING
Unexpected but recoverable situations.

```python
warn("Configuration file not found, using defaults")
warn(f"Retry attempt {attempt} of {max_retries}")
warn("Deprecated API endpoint called")
```

Use for:
- Missing optional configuration
- Deprecated feature usage
- Retry attempts
- Near-limit conditions

### ERROR
Operation failures that need attention.

```python
error("Database connection failed")
error(f"Failed to process file: {filename}", exc_info=True)
error("API request timeout after 30s")
```

Use for:
- Failed operations
- Caught exceptions that affect functionality
- External service failures
- Data validation failures

### CRITICAL
Severe errors requiring immediate attention.

```python
critical("Database corruption detected")
critical("Security breach attempt detected")
critical("Out of disk space")
```

Use for:
- Application cannot continue
- Data integrity issues
- Security incidents
- Resource exhaustion

## Viewing Logs

### macOS Console.app

1. Open **Console.app** (in `/Applications/Utilities/`)
2. Click **File** > **Open...** (or press `Cmd+O`)
3. Navigate to `~/Library/Logs/OpenCodeStatusBar/`
4. Select `opencode-status-bar.log`

Console.app provides filtering, search, and live updates.

### Terminal Commands

**Follow logs in real-time:**

```bash
# Human-readable logs
tail -f ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.log

# JSON logs
tail -f ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json
```

**View recent logs:**

```bash
# Last 100 lines
tail -n 100 ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.log

# Last 50 lines with line numbers
tail -n 50 ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.log | nl
```

**Search logs:**

```bash
# Find all errors
grep "ERROR" ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.log

# Find logs from specific component
grep "opencode.api" ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.log

# Case-insensitive search
grep -i "timeout" ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.log
```

### JSON Log Analysis with jq

The `jq` tool is powerful for analyzing JSON logs. Install with `brew install jq`.

**Pretty-print JSON:**

```bash
tail -n 1 ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json | jq .
```

**Filter by log level:**

```bash
# Show only errors
cat ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json | jq 'select(.level == "ERROR")'

# Show warnings and above
cat ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json | jq 'select(.level == "WARNING" or .level == "ERROR" or .level == "CRITICAL")'
```

**Filter by component:**

```bash
cat ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json | jq 'select(.logger | startswith("opencode.api"))'
```

**Filter by request ID:**

```bash
cat ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json | jq 'select(.request_id == "abc-123")'
```

**Extract specific fields:**

```bash
cat ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json | jq '{time: .timestamp, level: .level, msg: .message}'
```

**Count errors by component:**

```bash
cat ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json | jq -s 'map(select(.level == "ERROR")) | group_by(.logger) | map({logger: .[0].logger, count: length})'
```

**Time-based filtering (last hour):**

```bash
# Requires GNU date or gdate on macOS
SINCE=$(gdate -d '1 hour ago' -Iseconds)
cat ~/Library/Logs/OpenCodeStatusBar/opencode-status-bar.json | jq --arg since "$SINCE" 'select(.timestamp > $since)'
```

## Troubleshooting

### Logs not appearing

1. **Check log directory exists:**
   ```bash
   ls -la ~/Library/Logs/OpenCodeStatusBar/
   ```

2. **Check file permissions:**
   ```bash
   # Should be writable by your user
   touch ~/Library/Logs/OpenCodeStatusBar/test.txt && rm ~/Library/Logs/OpenCodeStatusBar/test.txt
   ```

3. **Verify log level setting:**
   ```bash
   echo $OPENCODE_LOG_LEVEL
   # If set to "error", debug/info/warning won't appear
   ```

### Debug logs not showing

Debug logs are hidden by default. Enable them:

```bash
export OPENCODE_DEBUG=1
# or
export OPENCODE_LOG_LEVEL=debug
```

### Log files too large

If logs grow unexpectedly large:

1. Check for excessive debug logging in production
2. Review log rotation settings
3. Manually clean old backups:
   ```bash
   rm ~/Library/Logs/OpenCodeStatusBar/*.log.[0-9]*
   rm ~/Library/Logs/OpenCodeStatusBar/*.json.[0-9]*
   ```

### Crash logs not created

The crash handler may not capture:
- Segmentation faults (native crashes)
- Killed processes (OOM killer)
- Force quit via Activity Monitor

Check `crash.log` for Python exceptions:

```bash
cat ~/Library/Logs/OpenCodeStatusBar/crash.log
```
