"""Table definitions for analytics database.

Structured table schemas using dictionaries for maintainability.
"""

from typing import TypedDict


class ColumnDef(TypedDict):
    name: str
    type: str
    constraints: str


class IndexDef(TypedDict):
    name: str
    table: str
    columns: list[str]


class TableDef(TypedDict):
    name: str
    columns: list[ColumnDef]
    indexes: list[IndexDef]


SESSIONS_TABLE: TableDef = {
    "name": "sessions",
    "columns": [
        {"name": "id", "type": "VARCHAR", "constraints": "PRIMARY KEY"},
        {"name": "project_id", "type": "VARCHAR", "constraints": ""},
        {"name": "directory", "type": "VARCHAR", "constraints": ""},
        {"name": "title", "type": "VARCHAR", "constraints": ""},
        {"name": "created_at", "type": "TIMESTAMP", "constraints": ""},
        {"name": "updated_at", "type": "TIMESTAMP", "constraints": ""},
    ],
    "indexes": [
        {
            "name": "idx_sessions_created",
            "table": "sessions",
            "columns": ["created_at"],
        },
    ],
}

MESSAGES_TABLE: TableDef = {
    "name": "messages",
    "columns": [
        {"name": "id", "type": "VARCHAR", "constraints": "PRIMARY KEY"},
        {"name": "session_id", "type": "VARCHAR", "constraints": ""},
        {"name": "parent_id", "type": "VARCHAR", "constraints": ""},
        {"name": "role", "type": "VARCHAR", "constraints": ""},
        {"name": "agent", "type": "VARCHAR", "constraints": ""},
        {"name": "model_id", "type": "VARCHAR", "constraints": ""},
        {"name": "provider_id", "type": "VARCHAR", "constraints": ""},
        {"name": "tokens_input", "type": "INTEGER", "constraints": "DEFAULT 0"},
        {"name": "tokens_output", "type": "INTEGER", "constraints": "DEFAULT 0"},
        {"name": "tokens_reasoning", "type": "INTEGER", "constraints": "DEFAULT 0"},
        {"name": "tokens_cache_read", "type": "INTEGER", "constraints": "DEFAULT 0"},
        {"name": "tokens_cache_write", "type": "INTEGER", "constraints": "DEFAULT 0"},
        {"name": "created_at", "type": "TIMESTAMP", "constraints": ""},
        {"name": "completed_at", "type": "TIMESTAMP", "constraints": ""},
    ],
    "indexes": [
        {
            "name": "idx_messages_session",
            "table": "messages",
            "columns": ["session_id"],
        },
        {
            "name": "idx_messages_created",
            "table": "messages",
            "columns": ["created_at"],
        },
    ],
}

PARTS_TABLE: TableDef = {
    "name": "parts",
    "columns": [
        {"name": "id", "type": "VARCHAR", "constraints": "PRIMARY KEY"},
        {"name": "session_id", "type": "VARCHAR", "constraints": ""},
        {"name": "message_id", "type": "VARCHAR", "constraints": ""},
        {"name": "part_type", "type": "VARCHAR", "constraints": ""},
        {"name": "content", "type": "VARCHAR", "constraints": ""},
        {"name": "tool_name", "type": "VARCHAR", "constraints": ""},
        {"name": "tool_status", "type": "VARCHAR", "constraints": ""},
        {"name": "created_at", "type": "TIMESTAMP", "constraints": ""},
    ],
    "indexes": [
        {"name": "idx_parts_message", "table": "parts", "columns": ["message_id"]},
        {"name": "idx_parts_session", "table": "parts", "columns": ["session_id"]},
    ],
}

AGENT_TRACES_TABLE: TableDef = {
    "name": "agent_traces",
    "columns": [
        {"name": "trace_id", "type": "VARCHAR", "constraints": "PRIMARY KEY"},
        {"name": "session_id", "type": "VARCHAR", "constraints": "NOT NULL"},
        {"name": "parent_trace_id", "type": "VARCHAR", "constraints": ""},
        {"name": "parent_agent", "type": "VARCHAR", "constraints": ""},
        {"name": "subagent_type", "type": "VARCHAR", "constraints": "NOT NULL"},
        {"name": "prompt_input", "type": "TEXT", "constraints": "NOT NULL"},
        {"name": "prompt_output", "type": "TEXT", "constraints": ""},
        {"name": "started_at", "type": "TIMESTAMP", "constraints": "NOT NULL"},
        {"name": "ended_at", "type": "TIMESTAMP", "constraints": ""},
        {"name": "duration_ms", "type": "INTEGER", "constraints": ""},
        {"name": "tokens_in", "type": "INTEGER", "constraints": ""},
        {"name": "tokens_out", "type": "INTEGER", "constraints": ""},
        {"name": "status", "type": "VARCHAR", "constraints": "DEFAULT 'running'"},
        {"name": "tools_used", "type": "TEXT[]", "constraints": ""},
        {"name": "child_session_id", "type": "VARCHAR", "constraints": ""},
        {
            "name": "created_at",
            "type": "TIMESTAMP",
            "constraints": "DEFAULT CURRENT_TIMESTAMP",
        },
    ],
    "indexes": [
        {
            "name": "idx_traces_session",
            "table": "agent_traces",
            "columns": ["session_id"],
        },
        {
            "name": "idx_traces_parent",
            "table": "agent_traces",
            "columns": ["parent_trace_id"],
        },
    ],
}

TABLES: list[TableDef] = [
    SESSIONS_TABLE,
    MESSAGES_TABLE,
    PARTS_TABLE,
    AGENT_TRACES_TABLE,
]

TABLE_DEFINITIONS = {table["name"]: table for table in TABLES}
