"""Tests for FilesListWidget and ClickableLabel components."""

import pytest
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


class TestClickableLabel:
    """Tests for ClickableLabel widget."""

    def test_emits_clicked_signal_on_mouse_press(self, qtbot):
        """Should emit clicked signal when mouse is pressed."""
        from opencode_status_bar.dashboard.widgets.controls import ClickableLabel

        label = ClickableLabel("Test")
        qtbot.addWidget(label)

        with qtbot.waitSignal(label.clicked, timeout=1000):
            qtbot.mouseClick(label, Qt.MouseButton.LeftButton)

    def test_inherits_qlabel_functionality(self, qtbot):
        """Should support all QLabel methods."""
        from opencode_status_bar.dashboard.widgets.controls import ClickableLabel

        label = ClickableLabel("Initial")
        qtbot.addWidget(label)

        assert label.text() == "Initial"
        label.setText("Updated")
        assert label.text() == "Updated"

    def test_can_connect_slot_to_clicked(self, qtbot):
        """Should allow connecting slots to clicked signal."""
        from opencode_status_bar.dashboard.widgets.controls import ClickableLabel

        label = ClickableLabel("Click me")
        qtbot.addWidget(label)

        callback = MagicMock()
        label.clicked.connect(callback)

        qtbot.mouseClick(label, Qt.MouseButton.LeftButton)
        callback.assert_called_once()


class TestToolsBreakdownWidget:
    def test_shows_all_tools_without_truncation(self, qtbot):
        from collections import Counter
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ToolsBreakdownWidget,
        )

        widget = ToolsBreakdownWidget()
        qtbot.addWidget(widget)

        tools = Counter({f"tool_{i}": i + 1 for i in range(15)})
        widget.load_tools(tools, {})

        tool_labels = []
        for i in range(widget._container_layout.count()):
            item = widget._container_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, QLabel) and "tool_" in w.text():
                    tool_labels.append(w.text())

        assert len(tool_labels) == 15

    def test_last_tool_has_corner_prefix(self, qtbot):
        from collections import Counter
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ToolsBreakdownWidget,
        )

        widget = ToolsBreakdownWidget()
        qtbot.addWidget(widget)

        tools = Counter({"tool_a": 3, "tool_b": 2, "tool_c": 1})
        widget.load_tools(tools, {})

        tool_labels = []
        for i in range(widget._container_layout.count()):
            item = widget._container_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, QLabel) and "tool_" in w.text():
                    tool_labels.append(w.text())

        assert tool_labels[-1].startswith("└─")

    def test_non_last_tools_have_branch_prefix(self, qtbot):
        from collections import Counter
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ToolsBreakdownWidget,
        )

        widget = ToolsBreakdownWidget()
        qtbot.addWidget(widget)

        tools = Counter({"tool_a": 3, "tool_b": 2, "tool_c": 1})
        widget.load_tools(tools, {})

        tool_labels = []
        for i in range(widget._container_layout.count()):
            item = widget._container_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, QLabel) and "tool_" in w.text():
                    tool_labels.append(w.text())

        for label in tool_labels[:-1]:
            assert label.startswith("├─")


def _make_files(
    files_dict: dict[str, list[str]], with_stats: bool = False
) -> list[dict]:
    """Helper to convert old format to new format for tests."""
    result = []
    for op, paths in files_dict.items():
        for path in paths:
            result.append(
                {
                    "path": path,
                    "operation": op,
                    "additions": 5 if with_stats else 0,
                    "deletions": 2 if with_stats else 0,
                }
            )
    return result


class TestFilesListWidget:
    """Tests for FilesListWidget."""

    def test_shows_all_files(self, qtbot):
        """Widget should show all files without truncation."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        widget.load_files(_make_files({"edit": [f"file{i}.py" for i in range(15)]}))

        visible_labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and "✏️" in w.text():
                visible_labels.append(w)
        assert len(visible_labels) == 15

    def test_no_more_indicator(self, qtbot):
        """Widget should not show '+N more...' indicator."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        widget.load_files(_make_files({"edit": [f"file{i}.py" for i in range(15)]}))

        more_labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and "more..." in w.text():
                more_labels.append(w)
        assert len(more_labels) == 0

    def test_header_shows_file_count(self, qtbot):
        """Header should display total file count."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        widget.load_files(_make_files({"edit": ["a.py", "b.py"], "read": ["c.py"]}))

        assert "(3)" in widget._header.text()

    def test_empty_files_shows_no_files_message(self, qtbot):
        """Empty files list should show 'No files accessed'."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        widget.load_files([])

        labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and "No files accessed" in w.text():
                labels.append(w)
        assert len(labels) == 1

    def test_prioritizes_edit_over_read(self, qtbot):
        """Should show edit files before read files."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        widget.load_files(_make_files({"read": ["read.py"], "edit": ["edit.py"]}))

        labels: list[str] = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel):
                text = w.text()
                if "✏️" in text or "📖" in text:
                    labels.append(text)

        assert "✏️" in labels[0]
        assert "📖" in labels[1]


class TestFilesListWidgetDiffExport:
    """Tests for diff export functionality (additions/deletions stats and signal)."""

    def test_load_files_computes_totals_from_per_file_stats(self, qtbot):
        """load_files should compute totals from per-file additions/deletions."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = [
            {"path": "file1.py", "operation": "edit", "additions": 10, "deletions": 3},
            {"path": "file2.py", "operation": "edit", "additions": 5, "deletions": 2},
        ]
        widget.load_files(files, session_id="ses_test")

        assert widget._total_additions == 15
        assert widget._total_deletions == 5
        assert widget._session_id == "ses_test"

    def test_header_shows_green_additions(self, qtbot):
        """Header should display additions in green color."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = [
            {"path": "file.py", "operation": "edit", "additions": 15, "deletions": 0}
        ]
        widget.load_files(files, session_id="ses_test")

        header_text = widget._header.text()
        assert "+15" in header_text

    def test_header_shows_red_deletions(self, qtbot):
        """Header should display deletions in red color."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = [
            {"path": "file.py", "operation": "edit", "additions": 0, "deletions": 8}
        ]
        widget.load_files(files, session_id="ses_test")

        header_text = widget._header.text()
        assert "-8" in header_text

    def test_export_button_visible_with_stats(self, qtbot):
        """Export button should be visible when files have diff stats."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = [
            {"path": "file.py", "operation": "edit", "additions": 5, "deletions": 3}
        ]
        widget.load_files(files, session_id="ses_test")

        assert not widget._export_btn.isHidden()

    def test_export_button_hidden_without_stats(self, qtbot):
        """Export button should be hidden when files have no diff stats."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = [
            {"path": "file.py", "operation": "edit", "additions": 0, "deletions": 0}
        ]
        widget.load_files(files)

        assert widget._export_btn.isHidden()

    def test_diff_requested_signal_emitted_on_export_click(self, qtbot):
        """Clicking export button should emit diff_requested signal."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = [
            {"path": "file.py", "operation": "edit", "additions": 1, "deletions": 1}
        ]
        widget.load_files(files, session_id="ses_signal_test")

        with qtbot.waitSignal(widget.diff_requested, timeout=1000) as blocker:
            qtbot.mouseClick(widget._export_btn, Qt.MouseButton.LeftButton)

        assert blocker.args == ["ses_signal_test"]

    def test_signal_not_emitted_without_session_id(self, qtbot):
        """Signal should not be emitted if session_id is None."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = [
            {"path": "file.py", "operation": "edit", "additions": 1, "deletions": 1}
        ]
        widget.load_files(files, session_id=None)

        signal_received = False

        def on_signal(sid):
            nonlocal signal_received
            signal_received = True

        widget.diff_requested.connect(on_signal)
        widget._on_export_clicked()

        assert not signal_received

    def test_per_file_stats_displayed(self, qtbot):
        """Per-file additions/deletions should be displayed in file list."""
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = [
            {"path": "file.py", "operation": "edit", "additions": 10, "deletions": 3}
        ]
        widget.load_files(files, session_id="ses_test")

        file_labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and "file.py" in w.text():
                file_labels.append(w.text())

        assert len(file_labels) == 1
        assert "+10" in file_labels[0]
        assert "-3" in file_labels[0]


class TestSessionOverviewPanelDiffHandler:
    """Tests for SessionOverviewPanel._on_diff_requested handler."""

    def test_handler_loads_diff_file(self, qtbot, tmp_path):
        """Handler should load diff from session_diff directory."""
        import json
        from unittest.mock import patch
        from pathlib import Path
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            SessionOverviewPanel,
        )

        panel = SessionOverviewPanel()
        qtbot.addWidget(panel)

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_data = [
            {
                "file": "src/test.py",
                "before": "old\n",
                "after": "new\n",
                "additions": 1,
                "deletions": 1,
            }
        ]
        diff_file = mock_diff_dir / "ses_handler_test.json"
        diff_file.write_text(json.dumps(diff_data))

        from PyQt6.QtWidgets import QApplication

        mock_clipboard = MagicMock()

        with patch.object(Path, "home", return_value=tmp_path):
            with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
                panel._on_diff_requested("ses_handler_test")

        mock_clipboard.setText.assert_called_once()

    def test_handler_generates_unified_diff_format(self, qtbot, tmp_path):
        """Handler should generate proper unified diff format."""
        import json
        from unittest.mock import patch
        from pathlib import Path
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            SessionOverviewPanel,
        )

        panel = SessionOverviewPanel()
        qtbot.addWidget(panel)

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_data = [
            {
                "file": "src/module.py",
                "before": "line1\nline2\nline3\n",
                "after": "line1\nmodified\nline3\nnew_line\n",
                "additions": 2,
                "deletions": 1,
            }
        ]
        diff_file = mock_diff_dir / "ses_format_test.json"
        diff_file.write_text(json.dumps(diff_data))

        from PyQt6.QtWidgets import QApplication

        mock_clipboard = MagicMock()

        with patch.object(Path, "home", return_value=tmp_path):
            with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
                panel._on_diff_requested("ses_format_test")

        clipboard_content = mock_clipboard.setText.call_args[0][0]

        assert "diff --git a/src/module.py b/src/module.py" in clipboard_content
        assert "--- a/src/module.py" in clipboard_content
        assert "+++ b/src/module.py" in clipboard_content
        assert "@@" in clipboard_content
        assert "-line2" in clipboard_content
        assert "+modified" in clipboard_content
        assert "+new_line" in clipboard_content

    def test_handler_handles_missing_file(self, qtbot, tmp_path):
        """Handler should not crash when diff file doesn't exist."""
        from unittest.mock import patch
        from pathlib import Path
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            SessionOverviewPanel,
        )

        panel = SessionOverviewPanel()
        qtbot.addWidget(panel)

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        error_raised = False
        try:
            with patch.object(Path, "home", return_value=tmp_path):
                panel._on_diff_requested("ses_nonexistent")
        except Exception:
            error_raised = True

        assert not error_raised

    def test_handler_handles_invalid_json(self, qtbot, tmp_path):
        """Handler should not crash on invalid JSON."""
        from unittest.mock import patch
        from pathlib import Path
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            SessionOverviewPanel,
        )

        panel = SessionOverviewPanel()
        qtbot.addWidget(panel)

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_file = mock_diff_dir / "ses_invalid.json"
        diff_file.write_text("not valid json {{{")

        error_raised = False
        try:
            with patch.object(Path, "home", return_value=tmp_path):
                panel._on_diff_requested("ses_invalid")
        except Exception:
            error_raised = True

        assert not error_raised

    def test_handler_handles_empty_diff(self, qtbot, tmp_path):
        """Handler should not copy anything for empty diff."""
        import json
        from unittest.mock import patch
        from pathlib import Path
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            SessionOverviewPanel,
        )

        panel = SessionOverviewPanel()
        qtbot.addWidget(panel)

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_file = mock_diff_dir / "ses_empty.json"
        diff_file.write_text("[]")

        from PyQt6.QtWidgets import QApplication

        mock_clipboard = MagicMock()

        with patch.object(Path, "home", return_value=tmp_path):
            with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
                panel._on_diff_requested("ses_empty")

        mock_clipboard.setText.assert_not_called()

    def test_handler_processes_multiple_files(self, qtbot, tmp_path):
        """Handler should generate diff for multiple files."""
        import json
        from unittest.mock import patch
        from pathlib import Path
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
            SessionOverviewPanel,
        )

        panel = SessionOverviewPanel()
        qtbot.addWidget(panel)

        mock_storage = tmp_path / ".local" / "share" / "opencode" / "storage"
        mock_diff_dir = mock_storage / "session_diff"
        mock_diff_dir.mkdir(parents=True)

        diff_data = [
            {
                "file": "src/file1.py",
                "before": "old1\n",
                "after": "new1\n",
                "additions": 1,
                "deletions": 1,
            },
            {
                "file": "src/file2.py",
                "before": "old2\n",
                "after": "new2\n",
                "additions": 1,
                "deletions": 1,
            },
        ]
        diff_file = mock_diff_dir / "ses_multi.json"
        diff_file.write_text(json.dumps(diff_data))

        from PyQt6.QtWidgets import QApplication

        mock_clipboard = MagicMock()

        with patch.object(Path, "home", return_value=tmp_path):
            with patch.object(QApplication, "clipboard", return_value=mock_clipboard):
                panel._on_diff_requested("ses_multi")

        clipboard_content = mock_clipboard.setText.call_args[0][0]

        assert "diff --git a/src/file1.py" in clipboard_content
        assert "diff --git a/src/file2.py" in clipboard_content
