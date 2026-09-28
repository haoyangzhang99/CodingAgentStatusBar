"""
Tests for AnalyticsQueries - Consolidated test suite.

Tests verify:
1. Date filtering for tools, skills, and delegations
2. Query correctness with strict equality assertions
3. Edge cases and empty results
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest

from opencode_status_bar.analytics.db import AnalyticsDB
from opencode_status_bar.analytics.queries import AnalyticsQueries


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def analytics_db(tmp_path):
    """Create an in-memory analytics database for testing."""
    db_path = tmp_path / "test_analytics.duckdb"
    db = AnalyticsDB(db_path=db_path)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def queries(analytics_db):
    """Create AnalyticsQueries instance with test database."""
    return AnalyticsQueries(analytics_db)


# =============================================================================
# Test Data Helpers
# =============================================================================


def generate_id() -> str:
    """Generate a unique ID for test data."""
    return str(uuid.uuid4())


def insert_session(
    db: AnalyticsDB,
    session_id: str,
    created_at: datetime,
    directory: str = "/test/dir",
    title: str = "Test Session",
    parent_id: str | None = None,
    project_id: str | None = None,
    additions: int = 0,
    deletions: int = 0,
    files_changed: int = 0,
):
    """Insert a test session with all optional fields."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO sessions (id, directory, title, created_at, updated_at, parent_id, project_id, additions, deletions, files_changed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            session_id,
            directory,
            title,
            created_at,
            created_at,
            parent_id,
            project_id,
            additions,
            deletions,
            files_changed,
        ],
    )


def insert_message(
    db: AnalyticsDB,
    message_id: str,
    session_id: str,
    created_at: datetime,
    agent: str = "main",
    tokens_input: int = 100,
    tokens_output: int = 50,
    cost: float = 0.0,
    model_id: str | None = None,
    provider_id: str | None = None,
):
    """Insert a test message with all optional fields."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO messages (id, session_id, role, agent, created_at, tokens_input, tokens_output, cost, model_id, provider_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            message_id,
            session_id,
            "assistant",
            agent,
            created_at,
            tokens_input,
            tokens_output,
            cost,
            model_id,
            provider_id,
        ],
    )


def insert_tool(
    db: AnalyticsDB,
    part_id: str,
    message_id: str,
    tool_name: str,
    created_at: datetime,
    status: str = "success",
    duration_ms: int = 100,
):
    """Insert a test tool part."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO parts (id, message_id, part_type, tool_name, tool_status, created_at, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [part_id, message_id, "tool", tool_name, status, created_at, duration_ms],
    )


def insert_skill(
    db: AnalyticsDB,
    skill_id: str,
    message_id: str,
    session_id: str,
    skill_name: str,
    loaded_at: datetime | None = None,
):
    """Insert a test skill."""
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO skills (id, message_id, session_id, skill_name, loaded_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [skill_id, message_id, session_id, skill_name, loaded_at],
    )


def insert_todo(
    db: AnalyticsDB,
    todo_id: str,
    session_id: str,
    content: str,
    status: str = "pending",
    priority: str = "medium",
    position: int = 0,
    created_at: datetime | None = None,
):
    """Insert a test todo."""
    conn = db.connect()
    created_at = created_at or datetime.now()
    conn.execute(
        """
        INSERT INTO todos (id, session_id, content, status, priority, position, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            todo_id,
            session_id,
            content,
            status,
            priority,
            position,
            created_at,
            created_at,
        ],
    )


def insert_project(
    db: AnalyticsDB,
    project_id: str,
    worktree: str,
    vcs: str = "git",
    created_at: datetime | None = None,
):
    """Insert a test project."""
    conn = db.connect()
    created_at = created_at or datetime.now()
    conn.execute(
        """
        INSERT INTO projects (id, worktree, vcs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [project_id, worktree, vcs, created_at, created_at],
    )


def insert_delegation(
    db: AnalyticsDB,
    delegation_id: str,
    session_id: str,
    parent_agent: str,
    child_agent: str,
    child_session_id: str | None = None,
    created_at: datetime | None = None,
):
    """Insert a test delegation."""
    conn = db.connect()
    created_at = created_at or datetime.now()
    conn.execute(
        """
        INSERT INTO delegations (id, session_id, parent_agent, child_agent, child_session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            delegation_id,
            session_id,
            parent_agent,
            child_agent,
            child_session_id,
            created_at,
        ],
    )


# =============================================================================
# Date Filtering Tests
# =============================================================================


class TestDateFiltering:
    """Tests for date filtering across tools, skills, and skills_by_agent."""

    @pytest.mark.parametrize(
        "query_type,within_name,outside_name",
        [
            ("tools", "bash", "old_tool"),
            ("skills", "qml", "old_skill"),
            ("skills_by_agent", "agentic-flow", "old_skill"),
        ],
    )
    def test_date_filtering_includes_recent_excludes_old(
        self, analytics_db, queries, query_type, within_name, outside_name
    ):
        """Recent items are included, old items are excluded based on date range."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)
        three_days_ago = now - timedelta(days=3)

        # Recent data (within period)
        session1 = generate_id()
        message1 = generate_id()
        insert_session(analytics_db, session1, yesterday)
        insert_message(analytics_db, message1, session1, yesterday, agent="executor")

        # Old data (outside period)
        session2 = generate_id()
        message2 = generate_id()
        insert_session(analytics_db, session2, three_days_ago)
        insert_message(
            analytics_db, message2, session2, three_days_ago, agent="executor"
        )

        if query_type == "tools":
            insert_tool(analytics_db, generate_id(), message1, within_name, yesterday)
            insert_tool(
                analytics_db, generate_id(), message2, outside_name, three_days_ago
            )
        else:
            insert_skill(
                analytics_db, generate_id(), message1, session1, within_name, yesterday
            )
            insert_skill(
                analytics_db,
                generate_id(),
                message2,
                session2,
                outside_name,
                three_days_ago,
            )

        # Query for last 24 hours
        start_date = now - timedelta(days=1)
        end_date = now

        if query_type == "tools":
            results = queries._get_tool_stats(start_date, end_date)
            assert len(results) == 1, f"Expected 1 tool, got {len(results)}"
            assert results[0].tool_name == within_name
            assert results[0].invocations == 1
        elif query_type == "skills":
            results = queries._get_skill_stats(start_date, end_date)
            assert len(results) == 1, f"Expected 1 skill, got {len(results)}"
            assert results[0].skill_name == within_name
            assert results[0].load_count == 1
        else:  # skills_by_agent
            results = queries._get_skills_by_agent(start_date, end_date)
            assert len(results) == 1, f"Expected 1 skill by agent, got {len(results)}"
            assert results[0].skill_name == within_name
            assert results[0].agent == "executor"
            assert results[0].count == 1

    def test_tool_failure_counts_filtered_by_date(self, analytics_db, queries):
        """Tool failure counts respect date filtering."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)
        three_days_ago = now - timedelta(days=3)

        # Recent failed tool
        session1 = generate_id()
        message1 = generate_id()
        insert_session(analytics_db, session1, yesterday)
        insert_message(analytics_db, message1, session1, yesterday)
        insert_tool(
            analytics_db, generate_id(), message1, "bash", yesterday, status="error"
        )

        # Old failed tool
        session2 = generate_id()
        message2 = generate_id()
        insert_session(analytics_db, session2, three_days_ago)
        insert_message(analytics_db, message2, session2, three_days_ago)
        insert_tool(
            analytics_db,
            generate_id(),
            message2,
            "bash",
            three_days_ago,
            status="error",
        )

        start_date = now - timedelta(days=1)
        end_date = now
        tools = queries._get_tool_stats(start_date, end_date)

        assert len(tools) == 1
        assert tools[0].tool_name == "bash"
        assert tools[0].failures == 1
        assert tools[0].invocations == 1

    def test_period_stats_respects_date_filtering(self, analytics_db, queries):
        """get_period_stats filters all data by date."""
        now = datetime.now()
        yesterday = now - timedelta(hours=12)
        three_days_ago = now - timedelta(days=3)

        # Recent data
        session1 = generate_id()
        message1 = generate_id()
        insert_session(analytics_db, session1, yesterday)
        insert_message(analytics_db, message1, session1, yesterday, agent="main")
        insert_tool(analytics_db, generate_id(), message1, "read", yesterday)
        insert_skill(analytics_db, generate_id(), message1, session1, "qml")

        # Old data
        session2 = generate_id()
        message2 = generate_id()
        insert_session(analytics_db, session2, three_days_ago)
        insert_message(
            analytics_db, message2, session2, three_days_ago, agent="executor"
        )
        insert_tool(analytics_db, generate_id(), message2, "bash", three_days_ago)
        insert_skill(analytics_db, generate_id(), message2, session2, "clean-code")

        stats = queries.get_period_stats(days=1)

        assert stats.session_count == 1
        assert [t.tool_name for t in stats.tools] == ["read"]
        assert [s.skill_name for s in stats.skills] == ["qml"]


# =============================================================================
# Todos Tests
# =============================================================================


class TestTodos:
    """Tests for todo queries with filtering and statistics."""

    @pytest.mark.parametrize(
        "filter_type,expected_count",
        [
            ("none", 4),
            ("session", 2),
            ("status_pending", 2),
            ("status_completed", 1),
            ("session_and_status", 1),
        ],
    )
    def test_get_todos_with_filters(
        self, analytics_db, queries, filter_type, expected_count
    ):
        """get_todos filters correctly by session_id and/or status."""
        now = datetime.now()
        session1 = generate_id()
        session2 = generate_id()
        insert_session(analytics_db, session1, now)
        insert_session(analytics_db, session2, now)

        # Session 1: 2 todos (1 pending, 1 completed)
        insert_todo(analytics_db, generate_id(), session1, "Task 1", status="pending")
        insert_todo(analytics_db, generate_id(), session1, "Task 2", status="completed")
        # Session 2: 2 todos (1 pending, 1 in_progress)
        insert_todo(analytics_db, generate_id(), session2, "Task 3", status="pending")
        insert_todo(
            analytics_db, generate_id(), session2, "Task 4", status="in_progress"
        )

        if filter_type == "none":
            todos = queries.get_todos()
        elif filter_type == "session":
            todos = queries.get_todos(session_id=session1)
        elif filter_type == "status_pending":
            todos = queries.get_todos(status="pending")
        elif filter_type == "status_completed":
            todos = queries.get_todos(status="completed")
        else:  # session_and_status
            todos = queries.get_todos(session_id=session1, status="pending")

        assert len(todos) == expected_count

        # Verify content based on filter
        if filter_type == "session":
            assert all(t.session_id == session1 for t in todos)
        elif filter_type == "status_pending":
            assert all(t.status == "pending" for t in todos)
        elif filter_type == "status_completed":
            assert all(t.status == "completed" for t in todos)
        elif filter_type == "session_and_status":
            assert todos[0].session_id == session1
            assert todos[0].status == "pending"

    def test_todo_stats_calculates_correctly(self, analytics_db, queries):
        """get_todo_stats returns correct statistics for all statuses."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)

        # Create todos with all statuses
        insert_todo(
            analytics_db, generate_id(), session_id, "T1", "pending", created_at=now
        )
        insert_todo(
            analytics_db, generate_id(), session_id, "T2", "completed", created_at=now
        )
        insert_todo(
            analytics_db, generate_id(), session_id, "T3", "completed", created_at=now
        )
        insert_todo(
            analytics_db, generate_id(), session_id, "T4", "in_progress", created_at=now
        )
        insert_todo(
            analytics_db, generate_id(), session_id, "T5", "cancelled", created_at=now
        )

        stats = queries.get_todo_stats(days=1)

        assert stats.total == 5
        assert stats.pending == 1
        assert stats.completed == 2
        assert stats.in_progress == 1
        assert stats.cancelled == 1
        assert stats.completion_rate == 40.0  # 2/5 = 40%

    def test_todo_stats_empty_returns_none(self, analytics_db, queries):
        """get_todo_stats returns None when no todos exist."""
        stats = queries.get_todo_stats(days=1)
        assert stats is None


# =============================================================================
# Projects and Code Stats Tests
# =============================================================================


class TestProjectsAndCodeStats:
    """Tests for project queries and code change statistics."""

    def test_projects_and_stats(self, analytics_db, queries):
        """get_projects and get_project_stats return correct data."""
        now = datetime.now()
        project_id = generate_id()
        session_id = generate_id()

        insert_project(analytics_db, project_id, "/project/test", created_at=now)
        insert_session(
            analytics_db,
            session_id,
            now,
            project_id=project_id,
            additions=100,
            deletions=50,
            files_changed=5,
        )
        insert_message(analytics_db, generate_id(), session_id, now)

        # Test get_projects
        projects = queries.get_projects()
        assert len(projects) == 1
        assert projects[0].worktree == "/project/test"
        assert projects[0].vcs == "git"

        # Test get_project_stats
        stats = queries.get_project_stats(days=1)
        project_stat = next((s for s in stats if s.project_id == project_id), None)
        assert project_stat.sessions == 1

        # Test get_code_stats
        code_stats = queries.get_code_stats(days=1)
        assert code_stats["additions"] == 100
        assert code_stats["deletions"] == 50
        assert code_stats["files_changed"] == 5
        assert code_stats["sessions_with_changes"] == 1

    def test_empty_project_queries(self, analytics_db, queries):
        """Project queries return empty/zero for empty database."""
        assert queries.get_projects() == []
        assert queries.get_project_stats(days=1) == []

        code_stats = queries.get_code_stats(days=1)
        assert code_stats["additions"] == 0
        assert code_stats["deletions"] == 0
        assert code_stats["files_changed"] == 0


# =============================================================================
# Cost Stats Tests
# =============================================================================


class TestCostStats:
    """Tests for cost statistics."""

    def test_cost_stats_calculates_correctly(self, analytics_db, queries):
        """get_cost_stats returns correct totals."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)

        insert_message(analytics_db, generate_id(), session_id, now, cost=0.05)
        insert_message(analytics_db, generate_id(), session_id, now, cost=0.10)
        insert_message(
            analytics_db, generate_id(), session_id, now, cost=0.00
        )  # No cost

        stats = queries.get_cost_stats(days=1)

        assert stats["total_cost"] == pytest.approx(0.15, rel=0.01)
        assert stats["messages_with_cost"] == 2  # Only messages with cost > 0
        # avg_cost_per_message is AVG over ALL messages (including 0 cost)
        assert stats["avg_cost_per_message"] == pytest.approx(0.05, rel=0.01)  # 0.15/3

    def test_cost_stats_empty(self, analytics_db, queries):
        """get_cost_stats returns zeros for empty database."""
        stats = queries.get_cost_stats(days=1)
        assert stats["total_cost"] == 0.0
        assert stats["messages_with_cost"] == 0


# =============================================================================
# Delegation Tests
# =============================================================================


class TestDelegations:
    """Tests for delegation queries."""

    def test_delegation_metrics_and_patterns(self, analytics_db, queries):
        """Delegation metrics and patterns are calculated correctly."""
        now = datetime.now()
        session_id = generate_id()
        child_session = generate_id()
        insert_session(analytics_db, session_id, now)
        insert_session(analytics_db, child_session, now)
        insert_message(analytics_db, generate_id(), session_id, now)
        insert_message(analytics_db, generate_id(), child_session, now)

        # Add delegations: 3 executor->tester, 1 executor->quality
        for _ in range(3):
            insert_delegation(
                analytics_db,
                generate_id(),
                session_id,
                "executor",
                "tester",
                child_session,
                now,
            )
        insert_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "quality",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        # Test metrics
        metrics = queries._get_delegation_metrics(start_date, end_date)
        assert metrics.total_delegations == 4
        assert metrics.sessions_with_delegations == 1
        assert metrics.unique_patterns == 2

        # Test patterns
        patterns = queries._get_delegation_patterns(start_date, end_date)
        assert len(patterns) == 2
        tester_pattern = next(p for p in patterns if p.child == "tester")
        assert tester_pattern.parent == "executor"
        assert tester_pattern.count == 3

        # Verify percentages sum to 100
        total_percentage = sum(p.percentage for p in patterns)
        assert abs(total_percentage - 100.0) < 0.1

        # Test chains
        chains = queries._get_agent_chains(start_date, end_date)
        assert len(chains) == 2
        chain_strs = [c.chain for c in chains]
        assert "executor -> tester" in chain_strs
        assert "executor -> quality" in chain_strs

    def test_delegation_sessions_requires_multiple(self, analytics_db, queries):
        """_get_delegation_sessions only returns sessions with 2+ delegations."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)

        # Only 1 delegation - should not appear
        insert_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        sessions = queries._get_delegation_sessions(start_date, end_date)
        assert sessions == []

        # Add second delegation - now should appear
        insert_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "quality",
            created_at=now + timedelta(seconds=1),
        )

        sessions = queries._get_delegation_sessions(start_date, end_date)
        assert len(sessions) == 1
        assert sessions[0].delegation_count == 2

    def test_recursive_delegations_counted(self, analytics_db, queries):
        """Recursive delegations (agent to itself) are tracked."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)

        insert_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "executor",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        metrics = queries._get_delegation_metrics(start_date, end_date)
        assert metrics.recursive_delegations == 1

    def test_extended_chains(self, analytics_db, queries):
        """Extended chains (depth 3+) are detected."""
        now = datetime.now()
        session1, session2, session3 = generate_id(), generate_id(), generate_id()

        insert_session(analytics_db, session1, now)
        insert_session(analytics_db, session2, now)
        insert_session(analytics_db, session3, now)

        # Chain: executor -> tester -> quality
        insert_delegation(
            analytics_db, generate_id(), session1, "executor", "tester", session2, now
        )
        insert_delegation(
            analytics_db, generate_id(), session2, "tester", "quality", session3, now
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        chains = queries._get_extended_chains(start_date, end_date)
        assert isinstance(chains, list)


# =============================================================================
# Session Tests
# =============================================================================


class TestSessions:
    """Tests for session queries."""

    def test_top_sessions_and_token_stats(self, analytics_db, queries):
        """Session queries return correct data."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)
        insert_message(
            analytics_db,
            generate_id(),
            session_id,
            now,
            tokens_input=200,
            tokens_output=100,
        )
        insert_message(
            analytics_db,
            generate_id(),
            session_id,
            now + timedelta(minutes=30),
            tokens_input=150,
            tokens_output=75,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        # Test top sessions
        sessions = queries._get_top_sessions(start_date, end_date)
        assert len(sessions) == 1
        assert sessions[0].session_id == session_id
        # tokens is TokenStats with input, output, etc.
        total = sessions[0].tokens.input + sessions[0].tokens.output
        assert total == 525  # 200+100+150+75
        assert sessions[0].message_count == 2

        # Test token stats
        stats = queries._get_session_token_stats(start_date, end_date)
        assert stats.total_sessions == 1
        assert stats.avg_tokens == 525  # avg_tokens, not avg_tokens_per_session

        # Test avg duration (returns minutes, not seconds)
        duration = queries._get_avg_session_duration(start_date, end_date)
        assert duration == pytest.approx(30, rel=0.2)  # 30 minutes

    def test_session_hierarchy(self, analytics_db, queries):
        """Session hierarchy returns parent-child relationships."""
        now = datetime.now()
        parent_id = generate_id()
        child_id = generate_id()

        insert_session(analytics_db, parent_id, now, title="Parent Session")
        insert_session(
            analytics_db, child_id, now, parent_id=parent_id, title="Child Session"
        )

        # Check from parent's perspective
        parent_hierarchy = queries.get_session_hierarchy(parent_id)
        assert parent_hierarchy["current"] == parent_id
        assert len(parent_hierarchy["children"]) == 1
        assert parent_hierarchy["children"][0]["id"] == child_id
        # parents includes the session chain up to root (including current)
        assert len(parent_hierarchy["parents"]) == 1
        assert parent_hierarchy["parents"][0]["id"] == parent_id

        # Check from child's perspective
        child_hierarchy = queries.get_session_hierarchy(child_id)
        assert child_hierarchy["current"] == child_id
        assert len(child_hierarchy["children"]) == 0
        # parents includes [parent, child] in order
        assert len(child_hierarchy["parents"]) == 2
        assert child_hierarchy["parents"][0]["id"] == parent_id
        assert child_hierarchy["parents"][1]["id"] == child_id

    def test_session_hierarchy_nonexistent(self, analytics_db, queries):
        """Session hierarchy handles nonexistent session."""
        hierarchy = queries.get_session_hierarchy("nonexistent")

        assert hierarchy["current"] == "nonexistent"
        assert hierarchy["children"] == []
        assert hierarchy["parents"] == []

    def test_session_with_null_title_shows_untitled(self, analytics_db, queries):
        """Sessions with NULL title display as 'Untitled'."""
        now = datetime.now()
        session_id = generate_id()

        conn = analytics_db.connect()
        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at, updated_at)
            VALUES (?, ?, NULL, ?, ?)
            """,
            [session_id, "/test", now, now],
        )
        insert_message(analytics_db, generate_id(), session_id, now)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        sessions = queries._get_top_sessions(start_date, end_date)
        assert sessions[0].title == "Untitled"


# =============================================================================
# Agent Tests
# =============================================================================


class TestAgents:
    """Tests for agent queries."""

    def test_agent_stats(self, analytics_db, queries):
        """_get_agent_stats returns per-agent statistics."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)

        insert_message(
            analytics_db,
            generate_id(),
            session_id,
            now,
            agent="executor",
            tokens_input=200,
        )
        insert_message(
            analytics_db,
            generate_id(),
            session_id,
            now,
            agent="tester",
            tokens_input=100,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_agent_stats(start_date, end_date)

        assert len(stats) == 2
        agents = {s.agent: s for s in stats}
        assert "executor" in agents
        assert "tester" in agents

    @pytest.mark.parametrize(
        "role_type,delegates_to,receives_from,expected_role",
        [
            ("orchestrator", ["executor"], [], "orchestrator"),
            ("worker", [], ["executor"], "worker"),
            ("hub", ["tester"], ["coordinator"], "hub"),
        ],
    )
    def test_agent_roles(
        self,
        analytics_db,
        queries,
        role_type,
        delegates_to,
        receives_from,
        expected_role,
    ):
        """_get_agent_roles correctly identifies agent roles."""
        now = datetime.now()
        session_id = generate_id()
        child_session = generate_id()
        insert_session(analytics_db, session_id, now)
        insert_session(analytics_db, child_session, now)
        insert_message(analytics_db, generate_id(), session_id, now, agent=role_type)

        # Add delegations based on role
        for target in delegates_to:
            insert_delegation(
                analytics_db,
                generate_id(),
                session_id,
                role_type,
                target,
                child_session,
                now,
            )
        for source in receives_from:
            insert_delegation(
                analytics_db,
                generate_id(),
                session_id,
                source,
                role_type,
                created_at=now,
            )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        roles = queries._get_agent_roles(start_date, end_date)
        agent_role = next((r for r in roles if r.agent == role_type), None)

        assert agent_role.role == expected_role

    def test_agent_delegation_stats_with_fan_out(self, analytics_db, queries):
        """_get_agent_delegation_stats calculates fan-out correctly."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)
        insert_message(analytics_db, generate_id(), session_id, now, agent="hub")

        # Hub receives 2 and sends 4 = fan-out of 2.0
        for _ in range(2):
            insert_delegation(
                analytics_db,
                generate_id(),
                session_id,
                "coordinator",
                "hub",
                created_at=now,
            )
        for _ in range(4):
            insert_delegation(
                analytics_db, generate_id(), session_id, "hub", "worker", created_at=now
            )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        roles = queries._get_agent_roles(start_date, end_date)
        hub_role = next((r for r in roles if r.agent == "hub"), None)

        assert hub_role.fan_out == 2.0


# =============================================================================
# Dimension Stats Tests
# =============================================================================


class TestDimensionStats:
    """Tests for directory and model statistics."""

    def test_directory_stats(self, analytics_db, queries):
        """_get_directory_stats aggregates by directory."""
        now = datetime.now()
        session1, session2 = generate_id(), generate_id()

        insert_session(analytics_db, session1, now, directory="/project/a")
        insert_session(analytics_db, session2, now, directory="/project/a")
        insert_message(analytics_db, generate_id(), session1, now, tokens_input=100)
        insert_message(analytics_db, generate_id(), session2, now, tokens_input=200)

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_directory_stats(start_date, end_date)
        dir_stat = next((s for s in stats if s.directory == "/project/a"), None)

        assert dir_stat.sessions == 2

    def test_model_stats_with_percentage(self, analytics_db, queries):
        """_get_model_stats calculates percentages correctly."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)

        insert_message(
            analytics_db,
            generate_id(),
            session_id,
            now,
            model_id="claude-3-sonnet",
            provider_id="anthropic",
        )
        insert_message(
            analytics_db,
            generate_id(),
            session_id,
            now,
            model_id="gpt-4",
            provider_id="openai",
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        stats = queries._get_model_stats(start_date, end_date)

        assert len(stats) == 2
        total_percentage = sum(s.percentage for s in stats)
        assert abs(total_percentage - 100.0) < 0.1


# =============================================================================
# Anomalies Tests
# =============================================================================


class TestAnomalies:
    """Tests for anomaly detection."""

    @pytest.mark.parametrize(
        "task_count,failure_rate,expect_task_anomaly,expect_failure_anomaly",
        [
            (12, 0.0, True, False),  # Excessive tasks (>10)
            (10, 0.0, False, False),  # At threshold, not flagged
            (10, 0.3, False, True),  # High failure rate (>20%)
            (10, 0.2, False, False),  # At threshold, not flagged
            (12, 0.3, True, True),  # Both anomalies
        ],
    )
    def test_anomaly_detection(
        self,
        analytics_db,
        queries,
        task_count,
        failure_rate,
        expect_task_anomaly,
        expect_failure_anomaly,
    ):
        """Anomalies are correctly detected based on thresholds."""
        now = datetime.now()
        session_id = generate_id()
        message_id = generate_id()

        insert_session(analytics_db, session_id, now, title="Test Session Title")
        insert_message(analytics_db, message_id, session_id, now)

        # Add task calls
        for _ in range(task_count):
            insert_tool(analytics_db, generate_id(), message_id, "task", now)

        # Add tools with failures
        total_tools = 10
        failures = int(total_tools * failure_rate)
        for i in range(total_tools):
            status = "error" if i < failures else "success"
            insert_tool(
                analytics_db, generate_id(), message_id, "test_tool", now, status=status
            )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        anomalies = queries._get_anomalies(start_date, end_date)

        has_task_anomaly = any("task" in a.lower() for a in anomalies)
        has_failure_anomaly = any("failure" in a.lower() for a in anomalies)

        assert has_task_anomaly == expect_task_anomaly
        assert has_failure_anomaly == expect_failure_anomaly

    def test_get_anomalies_public_method(self, analytics_db, queries):
        """get_anomalies (public) works with days parameter."""
        anomalies = queries.get_anomalies(days=7)
        assert isinstance(anomalies, list)


# =============================================================================
# Tool Performance Tests
# =============================================================================


class TestToolPerformance:
    """Tests for tool performance queries."""

    def test_tool_performance(self, analytics_db, queries):
        """get_tool_performance returns correct duration statistics."""
        now = datetime.now()
        session_id = generate_id()
        message_id = generate_id()
        insert_session(analytics_db, session_id, now)
        insert_message(analytics_db, message_id, session_id, now)

        insert_tool(
            analytics_db, generate_id(), message_id, "bash", now, duration_ms=100
        )
        insert_tool(
            analytics_db, generate_id(), message_id, "bash", now, duration_ms=200
        )
        insert_tool(
            analytics_db, generate_id(), message_id, "read", now, duration_ms=50
        )

        perf = queries.get_tool_performance(days=1)

        assert len(perf) == 2
        bash_perf = next(p for p in perf if p["tool_name"] == "bash")
        assert bash_perf["invocations"] == 2
        assert bash_perf["avg_duration_ms"] == 150
        assert bash_perf["max_duration_ms"] == 200
        assert bash_perf["min_duration_ms"] == 100
        assert bash_perf["failures"] == 0


# =============================================================================
# Time Series Tests
# =============================================================================


class TestTimeSeries:
    """Tests for time series queries."""

    def test_hourly_and_daily_stats(self, analytics_db, queries):
        """Time series queries return data grouped by hour/day."""
        now = datetime.now()
        session_id = generate_id()
        insert_session(analytics_db, session_id, now)
        insert_message(analytics_db, generate_id(), session_id, now)
        insert_delegation(
            analytics_db,
            generate_id(),
            session_id,
            "executor",
            "tester",
            created_at=now,
        )

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(hours=1)

        # Test hourly usage
        hourly = queries._get_hourly_usage(start_date, end_date)
        assert len(hourly) == 1
        assert hourly[0].hour == now.hour

        # Test hourly delegations
        hourly_del = queries._get_hourly_delegations(start_date, end_date)
        assert len(hourly_del) == 1

        # Test daily stats
        daily = queries._get_daily_stats(start_date, end_date)
        assert len(daily) == 1


# =============================================================================
# Base Queries Tests
# =============================================================================


class TestBaseQueries:
    """Tests for base query utilities."""

    def test_get_date_range(self, analytics_db, queries):
        """_get_date_range calculates correct date range."""
        start, end = queries._get_date_range(7)

        assert (datetime.now() - end).total_seconds() < 1
        delta = end - start
        assert delta.days == 7


# =============================================================================
# Empty Results Tests
# =============================================================================


class TestEmptyResults:
    """Tests for empty database queries."""

    @pytest.mark.parametrize(
        "query_method,args,expected_empty",
        [
            ("get_todos", {}, []),
            ("get_projects", {}, []),
            ("get_project_stats", {"days": 1}, []),
            ("get_tool_performance", {"days": 1}, []),
            ("_get_directory_stats", {"start_date": "now-1d", "end_date": "now"}, []),
            ("_get_model_stats", {"start_date": "now-1d", "end_date": "now"}, []),
            ("_get_agent_roles", {"start_date": "now-1d", "end_date": "now"}, []),
            (
                "_get_agent_delegation_stats",
                {"start_date": "now-1d", "end_date": "now"},
                [],
            ),
            (
                "_get_hourly_delegations",
                {"start_date": "now-1d", "end_date": "now"},
                [],
            ),
            ("_get_daily_stats", {"start_date": "now-1d", "end_date": "now"}, []),
            ("_get_skills_by_agent", {"start_date": "now-1d", "end_date": "now"}, []),
            (
                "_get_delegation_patterns",
                {"start_date": "now-1d", "end_date": "now"},
                [],
            ),
        ],
    )
    def test_empty_queries_return_empty_list(
        self, analytics_db, queries, query_method, args, expected_empty
    ):
        """Empty database returns empty list for list-returning queries."""
        now = datetime.now()

        # Process date arguments
        processed_args = {}
        for key, value in args.items():
            if value == "now-1d":
                processed_args[key] = now - timedelta(days=1)
            elif value == "now":
                processed_args[key] = now
            else:
                processed_args[key] = value

        method = getattr(queries, query_method)
        result = method(**processed_args)

        assert result == expected_empty

    @pytest.mark.parametrize(
        "query_method,args",
        [
            ("_get_delegation_metrics", {"start_date": "now-1d", "end_date": "now"}),
            ("_get_session_token_stats", {"start_date": "now-1d", "end_date": "now"}),
            ("get_todo_stats", {"days": 1}),
        ],
    )
    def test_empty_queries_return_none(self, analytics_db, queries, query_method, args):
        """Empty database returns None for stats queries."""
        now = datetime.now()

        processed_args = {}
        for key, value in args.items():
            if value == "now-1d":
                processed_args[key] = now - timedelta(days=1)
            elif value == "now":
                processed_args[key] = now
            else:
                processed_args[key] = value

        method = getattr(queries, query_method)
        result = method(**processed_args)

        assert result is None
