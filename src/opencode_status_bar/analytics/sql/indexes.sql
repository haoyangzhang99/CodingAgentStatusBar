-- ============================================================================
-- PERFORMANCE INDEXES FOR MATERIALIZED TABLES ARCHITECTURE
-- ============================================================================
-- This file defines all indexes for maximum query performance.
-- Indexes are created on both base tables (for fast refresh) and
-- materialized tables (for ultra-fast queries).
--
-- Strategy: Aggressive indexing for read-heavy workload
-- Trade-off: More disk space for 100x query performance improvement
-- ============================================================================


-- ============================================================================
-- INDEXES ON BASE TABLES (for fast refresh operations)
-- ============================================================================

-- Messages: queries by session and role
CREATE INDEX IF NOT EXISTS idx_messages_session_role 
    ON messages(session_id, role, created_at);

CREATE INDEX IF NOT EXISTS idx_messages_session_created 
    ON messages(session_id, created_at);

-- Parts: queries by message and type
CREATE INDEX IF NOT EXISTS idx_parts_message_type 
    ON parts(message_id, part_type, created_at);

CREATE INDEX IF NOT EXISTS idx_parts_type_message 
    ON parts(part_type, message_id);

-- Step events: queries by message
CREATE INDEX IF NOT EXISTS idx_step_events_message_type 
    ON step_events(message_id, event_type);

-- Delegations: parent-child queries
CREATE INDEX IF NOT EXISTS idx_delegations_child 
    ON delegations(child_session_id, session_id);

CREATE INDEX IF NOT EXISTS idx_delegations_session 
    ON delegations(session_id);

-- Agent traces: session and hierarchy queries
CREATE INDEX IF NOT EXISTS idx_traces_session 
    ON agent_traces(session_id, started_at);

CREATE INDEX IF NOT EXISTS idx_traces_child_session 
    ON agent_traces(child_session_id);

CREATE INDEX IF NOT EXISTS idx_traces_parent 
    ON agent_traces(parent_trace_id);


-- ============================================================================
-- INDEXES ON MATERIALIZED TABLES (for ultra-fast queries)
-- ============================================================================

-- Exchanges: most queried table
CREATE INDEX IF NOT EXISTS idx_exchanges_session 
    ON exchanges(session_id, exchange_number);

CREATE INDEX IF NOT EXISTS idx_exchanges_date 
    ON exchanges(started_at, ended_at);

CREATE INDEX IF NOT EXISTS idx_exchanges_agent 
    ON exchanges(agent, started_at);

CREATE INDEX IF NOT EXISTS idx_exchanges_user_msg 
    ON exchanges(user_message_id);

CREATE INDEX IF NOT EXISTS idx_exchanges_assistant_msg 
    ON exchanges(assistant_message_id);

-- Exchange traces: timeline queries
CREATE INDEX IF NOT EXISTS idx_exchange_traces_exchange 
    ON exchange_traces(exchange_id, event_order);

CREATE INDEX IF NOT EXISTS idx_exchange_traces_session 
    ON exchange_traces(session_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_exchange_traces_type 
    ON exchange_traces(event_type, timestamp);

-- Session traces: hierarchy and aggregation queries
CREATE INDEX IF NOT EXISTS idx_session_traces_session 
    ON session_traces(session_id);

CREATE INDEX IF NOT EXISTS idx_session_traces_parent 
    ON session_traces(parent_session_id, depth);

CREATE INDEX IF NOT EXISTS idx_session_traces_date 
    ON session_traces(started_at, ended_at);

CREATE INDEX IF NOT EXISTS idx_session_traces_depth 
    ON session_traces(depth, started_at);


-- ============================================================================
-- STATISTICS UPDATE (for query planner optimization)
-- ============================================================================

ANALYZE messages;
ANALYZE parts;
ANALYZE step_events;
ANALYZE delegations;
ANALYZE agent_traces;
ANALYZE exchanges;
ANALYZE exchange_traces;
ANALYZE session_traces;
