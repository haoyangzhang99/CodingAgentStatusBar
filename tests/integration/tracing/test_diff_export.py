"""
Integration tests for session diff export functionality.

Tests verify:
- FilesListWidget displays additions/deletions stats
- Export button emits diff_requested signal
- SessionOverviewPanel handles diff export and copies to clipboard
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtWidgets import QApplication

from ..conftest import SECTION_TRACING
from ..fixtures import MockAPIResponses, process_qt_events

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group(name="qt_tracing"),  # Force same worker for Qt UI tests
]


def _select_root_session(tracing) -> QModelIndex:
    """Helper to select root session in tree (QTreeView/QAbstractItemModel API)."""
    model = tracing._model
    root_index = model.index(0, 0)
    tracing._tree.setCurrentIndex(root_index)
    tracing._on_index_clicked(root_index)
    return root_index


class TestFilesListWidgetDiffStats:
    """Test FilesListWidget displays additions/deletions stats."""

    def test_header_displays_additions_deletions_when_provided(
        self, dashboard_window, qtbot, click_nav
    ):
        """Header should show +additions -deletions when stats are provided."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        files_widget.load_files(
            [
                {
                    "path": "file1.py",
                    "operation": "edit",
                    "additions": 15,
                    "deletions": 4,
                }
            ],
            session_id="ses_test",
        )
        process_qt_events()

        header_text = files_widget._header.text()
        assert "+15" in header_text, f"Header should show +15, got: {header_text}"
        assert "-4" in header_text, f"Header should show -4, got: {header_text}"

    def test_export_button_visible_when_stats_present(
        self, dashboard_window, qtbot, click_nav
    ):
        """Export button should be visible when additions/deletions are present."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        files_widget.load_files(
            [
                {
                    "path": "file1.py",
                    "operation": "edit",
                    "additions": 10,
                    "deletions": 5,
                }
            ],
            session_id="ses_test",
        )
        process_qt_events()

        assert files_widget._export_btn.isVisible(), "Export button should be visible"

    def test_export_button_hidden_when_no_stats(
        self, dashboard_window, qtbot, click_nav
    ):
        """Export button should be hidden when no additions/deletions."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        files_widget.load_files(
            [{"path": "file1.py", "operation": "edit", "additions": 0, "deletions": 0}]
        )
        process_qt_events()

        assert not files_widget._export_btn.isVisible(), (
            "Export button should be hidden when no stats"
        )


class TestDiffExportSignal:
    """Test diff_requested signal emission."""

    def test_export_button_emits_signal_with_session_id(
        self, dashboard_window, qtbot, click_nav
    ):
        """Clicking export button should emit diff_requested with session_id."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        test_session_id = "ses_signal_test"
        files_widget.load_files(
            [{"path": "file1.py", "operation": "edit", "additions": 5, "deletions": 2}],
            session_id=test_session_id,
        )
        process_qt_events()

        received_session_id = None

        def capture_signal(session_id):
            nonlocal received_session_id
            received_session_id = session_id

        files_widget.diff_requested.connect(capture_signal)

        qtbot.mouseClick(files_widget._export_btn, Qt.MouseButton.LeftButton)
        process_qt_events()

        assert received_session_id == test_session_id, (
            f"Signal should emit session_id '{test_session_id}', got: {received_session_id}"
        )


class TestDiffExportToClipboard:
    """Test diff export copies to clipboard in git patch format."""

    def test_diff_copied_to_clipboard_in_git_format(
        self, dashboard_window, qtbot, click_nav, tmp_path
    ):
        """Clicking export should copy diff to clipboard in git patch format."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        test_session_id = "ses_clipboard_test"

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_data = [
            {
                "file": "src/auth/login.py",
                "before": "def login(user):\n    validate(user)\n    return token\n",
                "after": "def login(user, remember=False):\n    validate(user)\n    session = create_session(user, remember)\n    return session.token\n",
                "additions": 3,
                "deletions": 2,
            },
            {
                "file": "tests/test_auth.py",
                "before": "def test_login():\n    assert login(user)\n",
                "after": "def test_login():\n    assert login(user)\n\ndef test_login_remember():\n    assert login(user, remember=True)\n",
                "additions": 4,
                "deletions": 0,
            },
        ]
        diff_file = mock_diff_dir / f"{test_session_id}.json"
        diff_file.write_text(json.dumps(diff_data))

        files_widget.load_files(
            [
                {
                    "path": "src/auth/login.py",
                    "operation": "edit",
                    "additions": 3,
                    "deletions": 2,
                },
                {
                    "path": "tests/test_auth.py",
                    "operation": "edit",
                    "additions": 4,
                    "deletions": 0,
                },
            ],
            session_id=test_session_id,
        )
        process_qt_events()

        mock_clipboard = MagicMock()
        target_module = "opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview"
        with patch(f"{target_module}.Path.home", return_value=tmp_path):
            with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
                qtbot.mouseClick(files_widget._export_btn, Qt.MouseButton.LeftButton)
                process_qt_events()

        mock_clipboard.setText.assert_called_once()
        clipboard_text = mock_clipboard.setText.call_args[0][0]

        assert "diff --git a/src/auth/login.py b/src/auth/login.py" in clipboard_text
        assert "--- a/src/auth/login.py" in clipboard_text
        assert "+++ b/src/auth/login.py" in clipboard_text

        assert "diff --git a/tests/test_auth.py b/tests/test_auth.py" in clipboard_text
        assert "--- a/tests/test_auth.py" in clipboard_text
        assert "+++ b/tests/test_auth.py" in clipboard_text

        assert "@@" in clipboard_text, "Should have hunk headers"

        assert "-def login(user):" in clipboard_text, "Should show removed line"
        assert "+def login(user, remember=False):" in clipboard_text, (
            "Should show added line"
        )
        assert "-    return token" in clipboard_text, "Should show removed return"
        assert "+    return session.token" in clipboard_text, "Should show new return"

        assert "+def test_login_remember():" in clipboard_text, (
            "Should show new test function"
        )
        assert "+    assert login(user, remember=True)" in clipboard_text

        lines = clipboard_text.split("\n")
        diff_git_count = sum(1 for line in lines if line.startswith("diff --git"))
        assert diff_git_count == 2, f"Should have 2 file diffs, got {diff_git_count}"

        minus_lines = sum(
            1 for line in lines if line.startswith("-") and not line.startswith("---")
        )
        plus_lines = sum(
            1 for line in lines if line.startswith("+") and not line.startswith("+++")
        )
        assert minus_lines >= 2, (
            f"Should have at least 2 removed lines, got {minus_lines}"
        )
        assert plus_lines >= 5, f"Should have at least 5 added lines, got {plus_lines}"

    def test_no_crash_when_diff_file_missing(
        self, dashboard_window, qtbot, click_nav, tmp_path
    ):
        """Should not crash when session_diff file doesn't exist."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        files_widget.load_files(
            [{"path": "file.py", "operation": "edit", "additions": 1, "deletions": 1}],
            session_id="ses_nonexistent",
        )
        process_qt_events()

        mock_storage = (
            tmp_path / ".local" / "share" / "opencode" / "storage" / "session_diff"
        )
        mock_storage.mkdir(parents=True)

        error_raised = False
        target_module = "opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview"
        try:
            with patch(f"{target_module}.Path.home", return_value=tmp_path):
                qtbot.mouseClick(files_widget._export_btn, Qt.MouseButton.LeftButton)
                process_qt_events()
        except Exception:
            error_raised = True

        assert not error_raised, "Should not raise exception when diff file missing"

    def test_handles_empty_diff_data(
        self, dashboard_window, qtbot, click_nav, tmp_path
    ):
        """Should handle empty diff data gracefully."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        test_session_id = "ses_empty_diff"

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_file = mock_diff_dir / f"{test_session_id}.json"
        diff_file.write_text("[]")

        files_widget.load_files(
            [{"path": "file.py", "operation": "edit", "additions": 1, "deletions": 1}],
            session_id=test_session_id,
        )
        process_qt_events()

        mock_clipboard = MagicMock()
        target_module = "opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview"
        with patch(f"{target_module}.Path.home", return_value=tmp_path):
            with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
                qtbot.mouseClick(files_widget._export_btn, Qt.MouseButton.LeftButton)
                process_qt_events()

        mock_clipboard.setText.assert_not_called()

    def test_diff_format_is_valid_unified_diff(
        self, dashboard_window, qtbot, click_nav, tmp_path
    ):
        """Generated diff should be valid unified diff format parseable by git."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        test_session_id = "ses_valid_format"

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_data = [
            {
                "file": "src/module.py",
                "before": "class Foo:\n    pass\n",
                "after": "class Foo:\n    def bar(self):\n        return 42\n",
                "additions": 2,
                "deletions": 1,
            }
        ]
        diff_file = mock_diff_dir / f"{test_session_id}.json"
        diff_file.write_text(json.dumps(diff_data))

        files_widget.load_files(
            [
                {
                    "path": "src/module.py",
                    "operation": "edit",
                    "additions": 2,
                    "deletions": 1,
                }
            ],
            session_id=test_session_id,
        )
        process_qt_events()

        mock_clipboard = MagicMock()
        target_module = "opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview"
        with patch(f"{target_module}.Path.home", return_value=tmp_path):
            with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
                qtbot.mouseClick(files_widget._export_btn, Qt.MouseButton.LeftButton)
                process_qt_events()

        clipboard_text = mock_clipboard.setText.call_args[0][0]
        lines = clipboard_text.split("\n")

        has_diff_git = any(line.startswith("diff --git") for line in lines)
        has_minus_header = any(line.startswith("--- a/") for line in lines)
        has_plus_header = any(line.startswith("+++ b/") for line in lines)
        has_hunk = any(line.startswith("@@") and "@@" in line[2:] for line in lines)

        assert has_diff_git, "Missing 'diff --git' header"
        assert has_minus_header, "Missing '--- a/' header"
        assert has_plus_header, "Missing '+++ b/' header"
        assert has_hunk, "Missing '@@ ... @@' hunk header"

        for line in lines:
            if line.startswith("@@"):
                import re

                hunk_pattern = r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@"
                assert re.match(hunk_pattern, line), f"Invalid hunk format: {line}"

    def test_diff_with_special_content(
        self, dashboard_window, qtbot, click_nav, tmp_path
    ):
        """Diff should handle special characters and unicode correctly."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        process_qt_events()

        _select_root_session(tracing)
        process_qt_events()

        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        files_widget = overview_panel._files

        test_session_id = "ses_special_chars"

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_data = [
            {
                "file": "src/i18n/messages.py",
                "before": 'MSG = "Hello"\n',
                "after": 'MSG = "Bonjour 👋 été"\nDESC = "Ça marche!"\n',
                "additions": 2,
                "deletions": 1,
            }
        ]
        diff_file = mock_diff_dir / f"{test_session_id}.json"
        diff_file.write_text(json.dumps(diff_data, ensure_ascii=False))

        files_widget.load_files(
            [
                {
                    "path": "src/i18n/messages.py",
                    "operation": "edit",
                    "additions": 2,
                    "deletions": 1,
                }
            ],
            session_id=test_session_id,
        )
        process_qt_events()

        mock_clipboard = MagicMock()
        target_module = "opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview"
        with patch(f"{target_module}.Path.home", return_value=tmp_path):
            with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
                qtbot.mouseClick(files_widget._export_btn, Qt.MouseButton.LeftButton)
                process_qt_events()

        mock_clipboard.setText.assert_called_once()
        clipboard_text = mock_clipboard.setText.call_args[0][0]

        assert "Bonjour" in clipboard_text, "Should preserve unicode text"
        assert "👋" in clipboard_text, "Should preserve emoji"
        assert "été" in clipboard_text, "Should preserve accented chars"
        assert "Ça marche" in clipboard_text, "Should preserve special chars"
