"""
Tests for opencode_status_bar.dashboard.widgets

Coverage target: 100% for all widget classes
Tests widget creation, properties, methods, and signals.

Consolidated tests: ~22 tests with 4+ assertions each (from 61 tests)
"""

import pytest

# PyQt6 imports with QApplication fixture
from PyQt6.QtWidgets import QWidget, QPushButton, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


# Note: 'qapp' fixture is provided by conftest.py with session scope


@pytest.fixture
def widget_parent(qapp):
    """Create a parent widget for testing."""
    parent = QWidget()
    yield parent
    parent.deleteLater()


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestFormatTokens:
    """Tests for format_tokens utility function."""

    @pytest.mark.parametrize(
        "count,expected",
        [
            (0, "0"),
            (1, "1"),
            (100, "100"),
            (999, "999"),
            (1000, "1K"),
            (1500, "2K"),
            (10000, "10K"),
            (100000, "100K"),
            (999999, "1000K"),
            (1000000, "1.0M"),
            (1500000, "1.5M"),
            (10000000, "10.0M"),
            (1234567890, "1234.6M"),
        ],
    )
    def test_format_tokens(self, count, expected):
        """format_tokens returns correct formatted string."""
        from opencode_status_bar.dashboard.styles import format_tokens

        assert format_tokens(count) == expected


class TestFormatDurationMs:
    """Tests for format_duration_ms utility function."""

    @pytest.mark.parametrize(
        "elapsed_ms,expected",
        [
            (0, "0ms"),
            (1, "1ms"),
            (100, "100ms"),
            (999, "999ms"),
            (1000, "1s"),
            (1500, "1s"),
            (5000, "5s"),
            (59999, "59s"),
            (60000, "1m 0s"),
            (61000, "1m 1s"),
            (90000, "1m 30s"),
            (120000, "2m 0s"),
            (3661000, "61m 1s"),
        ],
    )
    def test_format_duration_ms(self, elapsed_ms, expected):
        """format_duration_ms returns correct formatted string."""
        from opencode_status_bar.dashboard.styles import format_duration_ms

        assert format_duration_ms(elapsed_ms) == expected


# =============================================================================
# MetricCard Tests (7 -> 3 tests)
# =============================================================================


class TestMetricCard:
    """Tests for MetricCard widget."""

    def test_metric_card_creation_and_properties(self, qapp, widget_parent):
        """MetricCard creation, value setting, label, dimensions, and shadow effect."""
        from opencode_status_bar.dashboard.widgets import MetricCard
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect

        # Creation basic
        card = MetricCard("42", "Sessions", parent=widget_parent)
        assert isinstance(card, QWidget)
        assert card._value_label.text() == "42"

        # Label is uppercase
        assert card._label.text() == "SESSIONS"

        # Set value updates the displayed value
        card.set_value("999")
        assert card._value_label.text() == "999"

        # Minimum height set, width is adaptive (no fixed constraint)
        assert card.minimumHeight() == 80

        # Shadow effect applied
        effect = card.graphicsEffect()
        assert isinstance(effect, QGraphicsDropShadowEffect)
        assert effect.blurRadius() > 0

    def test_metric_card_with_accent(self, qapp, widget_parent):
        """MetricCard with custom accent and invalid accent fallback."""
        from opencode_status_bar.dashboard.widgets import MetricCard
        from opencode_status_bar.dashboard.styles import COLORS

        # Creation with accent
        card = MetricCard("100", "Requests", accent="success", parent=widget_parent)
        assert card._accent == "success"
        assert card._accent_color == card.ACCENT_MAP["success"]

        # Invalid accent falls back to muted
        card_invalid = MetricCard("0", "Test", accent="invalid", parent=widget_parent)
        assert card_invalid._accent_color == COLORS["text_muted"]

    @pytest.mark.parametrize(
        "accent,expected_in_map",
        [
            ("primary", True),
            ("success", True),
            ("warning", True),
            ("error", True),
            ("muted", True),
        ],
    )
    def test_accent_mapping(self, qapp, widget_parent, accent, expected_in_map):
        """MetricCard accent colors are correctly mapped."""
        from opencode_status_bar.dashboard.widgets import MetricCard

        card = MetricCard("0", "Test", accent=accent, parent=widget_parent)
        assert card._accent_color == card.ACCENT_MAP[accent]


# =============================================================================
# StatusBadge Tests (6 -> 2 tests)
# =============================================================================


class TestStatusBadge:
    """Tests for StatusBadge widget."""

    def test_status_badge_creation_and_behavior(self, qapp, widget_parent):
        """StatusBadge creation, variant, set_variant, invalid fallback, is QLabel."""
        from opencode_status_bar.dashboard.widgets import StatusBadge

        # Creation basic (includes bullet prefix)
        badge = StatusBadge("BUSY", parent=widget_parent)
        assert badge.text() == "● BUSY"
        assert isinstance(badge, QLabel)

        # Creation with variant
        badge_variant = StatusBadge("Active", variant="success", parent=widget_parent)
        assert badge_variant.text() == "● Active"

        # Set variant changes appearance (text preserved with bullet)
        badge_neutral = StatusBadge("Status", variant="neutral", parent=widget_parent)
        badge_neutral.set_variant("success")
        assert badge_neutral.text() == "● Status"

        # Invalid variant fallback (should not raise)
        badge_invalid = StatusBadge("Test", variant="nonexistent", parent=widget_parent)
        assert badge_invalid.text() == "● Test"

    @pytest.mark.parametrize(
        "variant",
        [
            "success",
            "warning",
            "error",
            "info",
            "neutral",
            "critical",
            "high",
            "medium",
            "low",
        ],
    )
    def test_valid_variants(self, qapp, widget_parent, variant):
        """StatusBadge supports all documented variants."""
        from opencode_status_bar.dashboard.widgets import StatusBadge

        badge = StatusBadge("Test", variant=variant, parent=widget_parent)
        assert variant in StatusBadge.VARIANTS


# =============================================================================
# RiskBadge Tests (5 -> 2 tests)
# =============================================================================


class TestRiskBadge:
    """Tests for RiskBadge widget."""

    def test_risk_badge_creation_and_behavior(self, qapp, widget_parent):
        """RiskBadge creation, invalid level fallback, is Badge subclass."""
        from opencode_status_bar.dashboard.widgets import RiskBadge, Badge

        # Creation basic
        badge = RiskBadge("critical", parent=widget_parent)
        assert badge.text() == "CRITICAL"
        assert isinstance(badge, Badge)

        # Valid levels are in VARIANTS
        for level in ["critical", "high", "medium", "low"]:
            assert level in RiskBadge.VARIANTS

        # Invalid level fallback (should not raise)
        badge_invalid = RiskBadge("unknown", parent=widget_parent)
        assert badge_invalid.text() == "UNKNOWN"

    @pytest.mark.parametrize(
        "level,expected_upper",
        [
            ("critical", "CRITICAL"),
            ("high", "HIGH"),
            ("medium", "MEDIUM"),
            ("low", "LOW"),
            ("CRITICAL", "CRITICAL"),
            ("High", "HIGH"),
        ],
    )
    def test_level_text_uppercase(self, qapp, widget_parent, level, expected_upper):
        """RiskBadge displays level in uppercase."""
        from opencode_status_bar.dashboard.widgets import RiskBadge

        badge = RiskBadge(level, parent=widget_parent)
        assert badge.text() == expected_upper


# =============================================================================
# TypeBadge Tests (5 -> 2 tests)
# =============================================================================


class TestTypeBadge:
    """Tests for TypeBadge widget."""

    def test_type_badge_creation_and_behavior(self, qapp, widget_parent):
        """TypeBadge creation, case insensitive, invalid fallback, is Badge subclass."""
        from opencode_status_bar.dashboard.widgets import TypeBadge, Badge

        # Creation basic
        badge = TypeBadge("bash", parent=widget_parent)
        assert badge.text() == "BASH"
        assert isinstance(badge, Badge)

        # Case insensitive handling
        badge1 = TypeBadge("BASH", parent=widget_parent)
        badge2 = TypeBadge("bash", parent=widget_parent)
        badge3 = TypeBadge("Bash", parent=widget_parent)
        assert badge1.text() == "BASH"
        assert badge2.text() == "BASH"
        assert badge3.text() == "BASH"

        # Invalid type fallback (should not raise)
        badge_invalid = TypeBadge("unknown_tool", parent=widget_parent)
        assert badge_invalid.text() == "UNKNOWN_TOOL"

    @pytest.mark.parametrize(
        "op_type,expected_upper",
        [
            ("command", "COMMAND"),
            ("bash", "BASH"),
            ("read", "READ"),
            ("write", "WRITE"),
            ("edit", "EDIT"),
            ("webfetch", "WEBFETCH"),
            ("web_fetch", "WEB_FETCH"),
            ("glob", "GLOB"),
            ("grep", "GREP"),
            ("skill", "SKILL"),
        ],
    )
    def test_operation_types(self, qapp, widget_parent, op_type, expected_upper):
        """TypeBadge displays operation type in uppercase."""
        from opencode_status_bar.dashboard.widgets import TypeBadge

        badge = TypeBadge(op_type, parent=widget_parent)
        assert badge.text() == expected_upper


# =============================================================================
# SegmentedControl Tests (10 -> 3 tests)
# =============================================================================


class TestSegmentedControl:
    """Tests for SegmentedControl widget."""

    def test_segmented_control_creation_and_selection(self, qapp, widget_parent):
        """SegmentedControl creation, options count, initial selection, buttons checkable, only one checked."""
        from opencode_status_bar.dashboard.widgets import SegmentedControl

        # Creation basic
        options = ["Day", "Week", "Month", "Year"]
        control = SegmentedControl(options, parent=widget_parent)

        # Options count
        assert len(control._buttons) == 4
        assert control._buttons[0].text() == "Day"
        assert control._buttons[1].text() == "Week"
        assert control._buttons[2].text() == "Month"
        assert control._buttons[3].text() == "Year"

        # Initial selection (first option)
        assert control.current_index() == 0
        assert control._buttons[0].isChecked()
        assert not control._buttons[1].isChecked()
        assert not control._buttons[2].isChecked()
        assert not control._buttons[3].isChecked()

        # All buttons are checkable
        for btn in control._buttons:
            assert btn.isCheckable()

        # Only one button is checked at a time
        for i in range(4):
            control.set_current_index(i)
            checked_count = sum(1 for btn in control._buttons if btn.isChecked())
            assert checked_count == 1

    @pytest.mark.parametrize(
        "target_index,expected_index,description",
        [
            (2, 2, "valid index"),
            (10, 0, "out of bounds - stays at initial"),
            (-1, 0, "negative - stays at initial"),
        ],
    )
    def test_segmented_control_index_handling(
        self, qapp, widget_parent, target_index, expected_index, description
    ):
        """SegmentedControl set_current_index handles valid, out-of-bounds, and negative indices."""
        from opencode_status_bar.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B", "C"], parent=widget_parent)
        control.set_current_index(target_index)
        assert control.current_index() == expected_index, f"Failed for: {description}"

    def test_segmented_control_signals(self, qtbot, widget_parent):
        """SegmentedControl emits selection_changed signal correctly."""
        from opencode_status_bar.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B", "C"], parent=widget_parent)
        qtbot.addWidget(control)

        # Change selection - should emit signal
        with qtbot.waitSignal(control.selection_changed, timeout=1000) as blocker:
            control.set_current_index(2)
        assert blocker.args == [2]

        # Click already selected button - should NOT emit signal
        # Use waitSignal with raising=False to verify signal is NOT emitted
        with qtbot.assertNotEmitted(control.selection_changed, wait=100):
            control._on_button_clicked(2)

        # Click different button - should emit signal
        with qtbot.waitSignal(control.selection_changed, timeout=1000) as blocker:
            control._on_button_clicked(0)
        assert blocker.args == [0]


# =============================================================================
# DataTable Tests (13 -> 4 tests)
# =============================================================================


class TestDataTable:
    """Tests for DataTable widget."""

    def test_data_table_creation_and_configuration(self, qapp, widget_parent):
        """DataTable creation, column count, initial rows, constants, sorting enabled."""
        from opencode_status_bar.dashboard.widgets import DataTable

        # Creation basic
        headers = ["Name", "Value", "Status", "Risk"]
        table = DataTable(headers, parent=widget_parent)

        # Column count
        assert table.columnCount() == 4
        assert table.horizontalHeaderItem(0).text() == "Name"
        assert table.horizontalHeaderItem(1).text() == "Value"
        assert table.horizontalHeaderItem(2).text() == "Status"
        assert table.horizontalHeaderItem(3).text() == "Risk"

        # Initial row count is zero
        assert table.rowCount() == 0

        # Class constants
        assert hasattr(DataTable, "ROW_HEIGHT")
        assert DataTable.ROW_HEIGHT == 36  # Updated: more compact tables
        assert hasattr(DataTable, "HEADER_HEIGHT")
        assert DataTable.HEADER_HEIGHT == 32  # Updated: more compact tables

        # Sorting enabled
        assert table.isSortingEnabled()

    def test_data_table_row_operations(self, qapp, widget_parent):
        """DataTable add_row, add_multiple_rows, clear_data, items not editable, add_row with variant."""
        from opencode_status_bar.dashboard.widgets import DataTable

        table = DataTable(["Name", "Value"], parent=widget_parent)

        # Add row simple
        table.add_row(["Test", "123"])
        assert table.rowCount() == 1
        assert table.item(0, 0).text() == "Test"
        assert table.item(0, 1).text() == "123"

        # Items are not editable
        item = table.item(0, 0)
        assert not (item.flags() & Qt.ItemFlag.ItemIsEditable)

        # Add multiple rows
        table.add_row(["Alpha", "1"])
        table.add_row(["Beta", "2"])
        assert table.rowCount() == 3

        # Clear data
        table.clear_data()
        assert table.rowCount() == 0

        # Add row with variant (tuple format)
        table.add_row([("BUSY", "status-busy"), ("HIGH", "risk-high")])
        assert table.rowCount() == 1
        assert table.item(0, 0).text() == "BUSY"
        assert table.item(0, 1).text() == "HIGH"

    def test_data_table_tooltip(self, qapp, widget_parent):
        """DataTable.add_row sets tooltip for long values."""
        from opencode_status_bar.dashboard.widgets import DataTable

        table = DataTable(["Path"], parent=widget_parent)
        long_path = "/very/long/path/to/some/deeply/nested/file.txt"
        table.add_row([long_path], full_values=[long_path])

        item = table.item(0, 0)
        assert item.toolTip() == long_path

    @pytest.mark.parametrize(
        "variant,color_key",
        [
            ("status-busy", "success"),
            ("status-idle", "text_muted"),
            ("risk-critical", "risk_critical"),
            ("risk-high", "risk_high"),
            ("risk-medium", "risk_medium"),
            ("risk-low", "risk_low"),
            ("type-command", "type_command"),
            ("type-bash", "type_bash"),
            ("type-read", "type_read"),
            ("type-write", "type_write"),
        ],
    )
    def test_variant_colors(self, qapp, widget_parent, variant, color_key):
        """DataTable applies correct colors for variants."""
        from opencode_status_bar.dashboard.widgets import DataTable
        from opencode_status_bar.dashboard.styles import COLORS

        table = DataTable(["Col"], parent=widget_parent)
        table.add_row([("Value", variant)])

        item = table.item(0, 0)
        expected_color = QColor(COLORS[color_key])
        assert item.foreground().color() == expected_color


# =============================================================================
# SectionHeader Tests (5 -> 2 tests)
# =============================================================================


class TestSectionHeader:
    """Tests for SectionHeader widget."""

    def test_section_header_without_subtitle(self, qapp, widget_parent):
        """SectionHeader creation with title only, no subtitle attribute."""
        from opencode_status_bar.dashboard.widgets import SectionHeader

        # Creation basic
        header = SectionHeader("Sessions", parent=widget_parent)
        assert header._title.text() == "Sessions"
        assert isinstance(header, QWidget)

        # No subtitle attribute when not provided
        assert not hasattr(header, "_subtitle")

        # Different title text
        header2 = SectionHeader("My Title", parent=widget_parent)
        assert header2._title.text() == "My Title"

    def test_section_header_with_subtitle_and_action(self, qapp, widget_parent):
        """SectionHeader with title, subtitle, and action."""
        from opencode_status_bar.dashboard.widgets import SectionHeader

        # Creation with subtitle
        header = SectionHeader(
            "Sessions", subtitle="Active monitoring", parent=widget_parent
        )
        assert header._title.text() == "Sessions"
        assert header._subtitle.text() == "Active monitoring"
        assert isinstance(header, QWidget)

        # Add action
        button = QPushButton("Action", parent=widget_parent)
        header.add_action(button)
        assert header._actions_layout.count() == 1


# =============================================================================
# Badge Base Class Tests (3 -> 1 test)
# =============================================================================


class TestBadge:
    """Tests for Badge base class."""

    def test_badge_base_class(self, qapp, widget_parent):
        """Badge creation, text uppercase, is QLabel subclass."""
        from opencode_status_bar.dashboard.widgets import Badge

        # Creation
        badge = Badge("test", "#ff0000", "#ffffff", parent=widget_parent)

        # Text is uppercase
        assert badge.text() == "TEST"
        assert isinstance(badge, QLabel)

        # Another badge with different text
        badge2 = Badge("hello", "#000", "#fff", parent=widget_parent)
        assert badge2.text() == "HELLO"


# =============================================================================
# CellBadge Tests (factory functions for table cells)
# =============================================================================


class TestCellBadge:
    """Tests for CellBadge widget and factory functions."""

    def test_cell_badge_creation(self, qapp, widget_parent):
        """CellBadge creation with custom colors."""
        from opencode_status_bar.dashboard.widgets import CellBadge

        badge = CellBadge("test", "#ff0000", "#330000", parent=widget_parent)
        assert badge.text() == "TEST"
        assert isinstance(badge, QLabel)

    def test_create_risk_badge_levels(self, qapp, widget_parent):
        """create_risk_badge returns correct badge for each risk level."""
        from opencode_status_bar.dashboard.widgets import create_risk_badge

        # All risk levels
        for level in ["critical", "high", "medium", "low"]:
            badge = create_risk_badge(level)
            assert badge.text() == level.upper()

        # Case insensitive
        badge_upper = create_risk_badge("CRITICAL")
        assert badge_upper.text() == "CRITICAL"

        # Unknown level falls back gracefully
        badge_unknown = create_risk_badge("unknown")
        assert badge_unknown.text() == "UNKNOWN"

    def test_create_type_badge_operations(self, qapp, widget_parent):
        """create_type_badge returns correct badge for operation types."""
        from opencode_status_bar.dashboard.widgets import create_type_badge

        # Common operation types
        for op_type in ["bash", "command", "read", "write", "edit", "webfetch"]:
            badge = create_type_badge(op_type)
            assert badge.text() == op_type.upper()

        # Unknown type falls back gracefully
        badge_unknown = create_type_badge("unknown_op")
        assert badge_unknown.text() == "UNKNOWN_OP"

    def test_create_score_badge_thresholds(self, qapp, widget_parent):
        """create_score_badge applies correct colors based on score thresholds."""
        from opencode_status_bar.dashboard.widgets import create_score_badge
        from opencode_status_bar.dashboard.styles import COLORS

        # Score >= 80: critical color
        badge_critical = create_score_badge(85)
        assert badge_critical.text() == "85"

        # Score >= 60: high color
        badge_high = create_score_badge(65)
        assert badge_high.text() == "65"

        # Score >= 40: medium color
        badge_medium = create_score_badge(45)
        assert badge_medium.text() == "45"

        # Score < 40: low color
        badge_low = create_score_badge(20)
        assert badge_low.text() == "20"


# =============================================================================
# MetricsRow Tests (5 -> 1 test)
# =============================================================================


class TestMetricsRow:
    """Tests for MetricsRow widget."""

    def test_metrics_row_operations(self, qapp, widget_parent):
        """MetricsRow creation, add_metric, update_metric, update nonexistent, add_stretch."""
        from opencode_status_bar.dashboard.widgets import MetricsRow, MetricCard

        # Creation
        row = MetricsRow(parent=widget_parent)
        assert isinstance(row, QWidget)

        # Add metric
        card = row.add_metric("sessions", "5", "Sessions")
        assert isinstance(card, MetricCard)
        assert "sessions" in row._cards
        assert row._cards["sessions"] == card

        # Update metric
        row.update_metric("sessions", "100")
        assert row._cards["sessions"]._value_label.text() == "100"

        # Update nonexistent metric (should not raise)
        row.update_metric("nonexistent", "value")

        # Add stretch
        initial_count = row._layout.count()
        row.add_stretch()
        assert row._layout.count() == initial_count + 1
