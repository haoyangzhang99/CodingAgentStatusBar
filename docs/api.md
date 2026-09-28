# OpenCode Status Bar API Documentation

REST API for accessing analytics and tracing data.

**Base URL**: `http://localhost:19876`

## Authentication

No authentication required (localhost only).

## Response Format

All endpoints return JSON with a standardized format:

```json
{
  "success": true,
  "data": [...],
  "meta": {
    "page": 1,
    "per_page": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

**Error Response**:
```json
{
  "success": false,
  "error": "Error message description"
}
```

## Pagination

List endpoints support pagination:

| Parameter | Type | Default | Max | Description |
|-----------|------|---------|-----|-------------|
| `page` | int | 1 | - | Page number (1-based) |
| `per_page` | int | 50 | 200 | Items per page |

**Note on Pagination Behavior:**
- Pagination parameters are **optional** for all endpoints (backwards compatible)
- If `page` and `per_page` are **not specified**, endpoints return **all results** without pagination
- If pagination parameters are provided, results are paginated as expected
- This design ensures backwards compatibility with clients expecting full result sets

Paginated responses include:
- `X-Total-Count` header with total item count
- `meta` object with pagination details

---

## Endpoints

### Health

#### GET /api/health

Basic health check.

**Response**:
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "analytics-api"
  }
}
```

#### GET /api/health/detailed

Detailed health check with database metrics.

**Response**:
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "analytics-api",
    "database": {
      "path": "/path/to/analytics.duckdb",
      "size_bytes": 12345678,
      "size_mb": 11.77,
      "tables": {
        "sessions": 150,
        "messages": 5000,
        "parts": 12000,
        "agent_traces": 800
      }
    }
  }
}
```

---

### Sessions

#### GET /api/sessions

Get paginated list of sessions.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Filter sessions from last N days |
| `limit` | int | 100 | Maximum total results |
| `page` | int | 1 | Page number |
| `per_page` | int | 50 | Results per page |

**Example**:
```bash
curl "http://localhost:19876/api/sessions?days=7&page=1&per_page=20"
```

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": "ses_abc123",
      "title": "Feature implementation",
      "directory": "/projects/myapp",
      "created_at": "2026-01-01T10:00:00",
      "updated_at": "2026-01-01T11:30:00"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

#### GET /api/sessions/search

Search sessions by title or directory.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | "" | Search query |
| `limit` | int | 20 | Maximum results |

**Example**:
```bash
curl "http://localhost:19876/api/sessions/search?q=refactor&limit=10"
```

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": "ses_abc123",
      "title": "Refactor database layer",
      "directory": "/projects/myapp",
      "created_at": "2026-01-01T10:00:00",
      "updated_at": "2026-01-01T11:30:00",
      "message_count": 25,
      "total_tokens": 150000
    }
  ]
}
```

---

### Session Details

#### GET /api/session/{session_id}/summary

Get complete session summary with KPIs.

**Response**:
```json
{
  "success": true,
  "data": {
    "meta": {
      "session_id": "ses_abc123",
      "generated_at": "2026-01-01T12:00:00",
      "title": "Feature implementation",
      "directory": "/projects/myapp"
    },
    "summary": {
      "duration_ms": 5400000,
      "total_tokens": 150000,
      "total_tool_calls": 45,
      "total_files": 12,
      "unique_agents": 3,
      "estimated_cost_usd": 0.85,
      "status": "completed"
    },
    "details": { ... },
    "charts": { ... }
  }
}
```

#### GET /api/session/{session_id}/tokens

Get token usage details.

#### GET /api/session/{session_id}/tools

Get tool usage details.

#### GET /api/session/{session_id}/files

Get file operation details.

#### GET /api/session/{session_id}/agents

Get agents involved in session.

#### GET /api/session/{session_id}/timeline

Get chronological event timeline.

#### GET /api/session/{session_id}/prompts

Get first user prompt and last response.

#### GET /api/session/{session_id}/messages

Get all messages with content.

#### GET /api/session/{session_id}/operations

Get tool operations for tree display.

#### GET /api/session/{session_id}/cost

Get detailed cost breakdown.

**Response**:
```json
{
  "success": true,
  "data": {
    "session_id": "ses_abc123",
    "total_cost_usd": 0.85,
    "breakdown": {
      "input": {
        "tokens": 100000,
        "rate_per_1k": 0.003,
        "cost_usd": 0.30
      },
      "output": {
        "tokens": 35000,
        "rate_per_1k": 0.015,
        "cost_usd": 0.525
      },
      "cache_read": {
        "tokens": 15000,
        "rate_per_1k": 0.0003,
        "cost_usd": 0.0045
      }
    },
    "by_agent": [
      {
        "agent": "executor",
        "tokens": 80000,
        "estimated_cost_usd": 0.55
      }
    ],
    "cache_savings_usd": 0.0405
  }
}
```

---

### Traces

#### GET /api/traces

Get paginated list of agent traces.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Filter from last N days |
| `limit` | int | 500 | Maximum total results |
| `page` | int | 1 | Page number |
| `per_page` | int | 50 | Results per page |

**Example**:
```bash
curl "http://localhost:19876/api/traces?days=7&page=1&per_page=20"
```

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "trace_id": "root_abc123",
      "session_id": "ses_xyz789",
      "parent_trace_id": null,
      "parent_agent": "user",
      "subagent_type": "executor",
      "started_at": "2026-01-01T10:00:00",
      "ended_at": "2026-01-01T10:30:00",
      "duration_ms": 1800000,
      "tokens_in": 50000,
      "tokens_out": 20000,
      "status": "completed",
      "prompt_input": "Implement feature X",
      "prompt_output": "Feature X implemented successfully"
    }
  ],
  "meta": { ... }
}
```

#### GET /api/trace/{trace_id}

Get full details of a specific trace.

**Response**:
```json
{
  "success": true,
  "data": {
    "trace_id": "root_abc123",
    "session_id": "ses_xyz789",
    "parent_trace_id": null,
    "parent_agent": "user",
    "subagent_type": "executor",
    "started_at": "2026-01-01T10:00:00",
    "ended_at": "2026-01-01T10:30:00",
    "duration_ms": 1800000,
    "tokens_in": 50000,
    "tokens_out": 20000,
    "status": "completed",
    "prompt_input": "...",
    "prompt_output": "...",
    "child_session_id": "child_ses_001",
    "session_title": "Feature implementation",
    "session_directory": "/projects/myapp",
    "children": [
      {
        "trace_id": "trace_child_001",
        "subagent_type": "tester",
        "status": "completed",
        "duration_ms": 300000
      }
    ],
    "tools": [
      {
        "tool_name": "read",
        "status": "completed",
        "duration_ms": 150,
        "created_at": "2026-01-01T10:01:00"
      }
    ]
  }
}
```

#### GET /api/tracing/tree

Get hierarchical tracing tree for dashboard.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Filter from last N days |
| `include_tools` | bool | true | Include tool calls |

---

### Delegations

#### GET /api/delegations

Get paginated list of agent delegations.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Filter from last N days |
| `limit` | int | 1000 | Maximum total results |
| `page` | int | 1 | Page number |
| `per_page` | int | 50 | Results per page |

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "parent_session_id": "ses_abc123",
      "parent_agent": "coordinator",
      "child_agent": "executor",
      "child_session_id": "ses_child_001",
      "created_at": "2026-01-01T10:00:00"
    }
  ],
  "meta": { ... }
}
```

---

### Statistics

#### GET /api/stats

Get database table counts.

#### GET /api/global-stats

Get global statistics for a time period.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Statistics period |

**Response**:
```json
{
  "success": true,
  "data": {
    "meta": {
      "period": {
        "start": "2025-12-02T00:00:00",
        "end": "2026-01-01T00:00:00"
      }
    },
    "summary": {
      "total_sessions": 150,
      "unique_projects": 12,
      "total_messages": 5000,
      "total_tokens": 2500000,
      "total_traces": 800,
      "total_tool_calls": 3500,
      "estimated_cost_usd": 45.50
    },
    "details": { ... }
  }
}
```

#### GET /api/stats/daily

Get daily aggregated statistics.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 7 | Number of days to retrieve |

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "date": "2026-01-01",
      "sessions": 15,
      "traces": 45,
      "tokens": 125000,
      "avg_duration_ms": 1200000,
      "errors": 2,
      "tool_calls": 180
    }
  ]
}
```

---

## Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 200 | Success |
| 404 | Resource not found |
| 500 | Internal server error |

---

## Examples

### Get recent sessions with pagination
```bash
curl "http://localhost:19876/api/sessions?days=7&page=1&per_page=10"
```

### Search for sessions
```bash
curl "http://localhost:19876/api/sessions/search?q=refactor&limit=5"
```

### Get trace details
```bash
curl "http://localhost:19876/api/trace/root_abc123"
```

### Get daily statistics
```bash
curl "http://localhost:19876/api/stats/daily?days=14"
```

### Get session cost breakdown
```bash
curl "http://localhost:19876/api/session/ses_abc123/cost"
```

### Check API health
```bash
curl "http://localhost:19876/api/health/detailed"
```
