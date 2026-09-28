"""
Tests for database utilities.
Consolidated: 7 tests → 4 tests with stronger assertions.
"""

import pytest
import sqlite3
import tempfile
import os

from opencode_status_bar.utils.db import db_connection, db_cursor


class TestDbConnection:
    """Tests for db_connection context manager."""

    def test_connection_lifecycle_and_behavior(self):
        """Connection properly opens, operates, and closes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_lifecycle.db")

            # Database should not exist yet
            assert not os.path.exists(db_path)

            with db_connection(db_path) as conn:
                # Verify connection properties
                assert conn is not None
                assert isinstance(conn, sqlite3.Connection)

                # Verify it's functional - create and populate table
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO test VALUES (1, 'hello')")
                conn.execute("INSERT INTO test VALUES (2, 'world')")

                # Verify data access works
                result = conn.execute("SELECT value FROM test ORDER BY id").fetchall()
                assert len(result) == 2
                assert result[0][0] == "hello"
                assert result[1][0] == "world"

            # Database file should exist after creation
            assert os.path.exists(db_path)

            # Connection should be closed after context exit
            with pytest.raises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")


class TestDbCursor:
    """Tests for db_cursor context manager."""

    def test_cursor_auto_commits_on_success(self):
        """Cursor auto-commits all operations when context exits normally."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_commit.db")

            with db_connection(db_path) as conn:
                conn.execute(
                    "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, status TEXT)"
                )
                conn.commit()

                with db_cursor(conn) as cursor:
                    # Verify cursor type
                    assert isinstance(cursor, sqlite3.Cursor)

                    # Perform multiple operations
                    cursor.execute(
                        "INSERT INTO items (name, status) VALUES ('item1', 'active')"
                    )
                    cursor.execute(
                        "INSERT INTO items (name, status) VALUES ('item2', 'pending')"
                    )
                    cursor.execute(
                        "INSERT INTO items (name, status) VALUES ('item3', 'active')"
                    )
                    cursor.execute(
                        "UPDATE items SET status = 'done' WHERE name = 'item1'"
                    )

                # All operations should be committed
                result = conn.execute("SELECT COUNT(*) FROM items").fetchone()
                assert result[0] == 3

                # Verify update was committed
                updated = conn.execute(
                    "SELECT status FROM items WHERE name = 'item1'"
                ).fetchone()
                assert updated[0] == "done"

                # Verify we can query all data correctly
                all_items = conn.execute(
                    "SELECT name, status FROM items ORDER BY id"
                ).fetchall()
                assert len(all_items) == 3
                assert all_items[0] == ("item1", "done")
                assert all_items[1] == ("item2", "pending")
                assert all_items[2] == ("item3", "active")

    def test_cursor_rollback_on_exception(self):
        """Cursor rolls back all operations when exception occurs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_rollback.db")

            with db_connection(db_path) as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO test VALUES (1, 'original')")
                conn.commit()

                # Verify initial state
                initial_count = conn.execute("SELECT COUNT(*) FROM test").fetchone()[0]
                assert initial_count == 1

                # Operations that will be rolled back
                with pytest.raises(ValueError):
                    with db_cursor(conn) as cursor:
                        cursor.execute("INSERT INTO test VALUES (2, 'should_rollback')")
                        cursor.execute("INSERT INTO test VALUES (3, 'also_rollback')")
                        cursor.execute(
                            "UPDATE test SET value = 'modified' WHERE id = 1"
                        )
                        raise ValueError("Intentional test exception")

                # Verify rollback: count unchanged, original data intact
                final_count = conn.execute("SELECT COUNT(*) FROM test").fetchone()[0]
                assert final_count == 1

                original_value = conn.execute(
                    "SELECT value FROM test WHERE id = 1"
                ).fetchone()[0]
                assert original_value == "original"

                # Verify no orphaned data
                all_ids = [
                    row[0] for row in conn.execute("SELECT id FROM test").fetchall()
                ]
                assert all_ids == [1]

    def test_cursor_operations_with_queries(self):
        """Cursor supports full CRUD operations and queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_crud.db")

            with db_connection(db_path) as conn:
                conn.execute("""
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE
                    )
                """)
                conn.commit()

                with db_cursor(conn) as cursor:
                    # CREATE
                    cursor.execute(
                        "INSERT INTO users (name, email) VALUES (?, ?)",
                        ("Alice", "alice@test.com"),
                    )
                    cursor.execute(
                        "INSERT INTO users (name, email) VALUES (?, ?)",
                        ("Bob", "bob@test.com"),
                    )

                    # READ within same cursor context
                    cursor.execute("SELECT * FROM users WHERE name = ?", ("Alice",))
                    alice = cursor.fetchone()
                    assert alice is not None
                    assert alice[1] == "Alice"
                    assert alice[2] == "alice@test.com"

                    # UPDATE
                    cursor.execute(
                        "UPDATE users SET email = ? WHERE name = ?",
                        ("alice.new@test.com", "Alice"),
                    )

                    # DELETE
                    cursor.execute("DELETE FROM users WHERE name = ?", ("Bob",))

                # Verify final state after commit
                users = conn.execute(
                    "SELECT name, email FROM users ORDER BY name"
                ).fetchall()
                assert len(users) == 1
                assert users[0] == ("Alice", "alice.new@test.com")
